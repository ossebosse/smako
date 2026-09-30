from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from app.api import plan as plan_api
from app.config import Settings
from app.models import PlanRequest
from app.services.planner_admission import (
    PlannerAdmissionController,
    PlannerAdmissionOverloaded,
)
from fastapi import HTTPException
from fastapi import Request as FastAPIRequest


def test_distinct_cold_jobs_are_admitted_one_at_a_time() -> None:
    async def scenario() -> None:
        controller = PlannerAdmissionController(max_concurrent=1, max_queued=5)
        active = 0
        peak_active = 0

        async def build(value: int) -> int:
            nonlocal active, peak_active
            active += 1
            peak_active = max(peak_active, active)
            await asyncio.sleep(0.01)
            active -= 1
            return value

        results = await asyncio.gather(
            *(controller.run(f"profile-{value}", lambda value=value: build(value)) for value in range(5))
        )
        stats = await controller.stats()

        assert results == [0, 1, 2, 3, 4]
        assert peak_active == 1
        assert stats.peak_active == 1
        assert stats.peak_queued >= 4
        assert stats.in_flight_keys == 0

    asyncio.run(scenario())


def test_identical_in_flight_requests_share_one_result() -> None:
    async def scenario() -> None:
        controller = PlannerAdmissionController(max_concurrent=1, max_queued=2)
        started = asyncio.Event()
        release = asyncio.Event()
        calls = 0

        async def build() -> dict[str, str]:
            nonlocal calls
            calls += 1
            started.set()
            await release.wait()
            return {"plan": "same deterministic result"}

        leader = asyncio.create_task(controller.run("same-key", build))
        await started.wait()
        follower = asyncio.create_task(controller.run("same-key", build))
        await asyncio.sleep(0)
        release.set()
        first, second = await asyncio.gather(leader, follower)
        stats = await controller.stats()

        assert calls == 1
        assert first == second
        assert stats.admitted == 1
        assert stats.coalesced == 1
        assert stats.in_flight_keys == 0

    asyncio.run(scenario())


def test_membership_profiles_have_separate_keys_and_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = SimpleNamespace(
        universe=SimpleNamespace(universe_id="price-universe:test")
    )
    monkeypatch.setattr(
        plan_api.GLOBAL_PREPARED_PRICE_UNIVERSES,
        "get_for_request",
        lambda *_args, **_kwargs: prepared,
    )
    settings = Settings(price_provider="mock")
    ica_request = PlanRequest(memberships=["ICA_STAMMIS"])
    coop_request = PlanRequest(memberships=["COOP_MEMBER"])
    ica_key = plan_api._planner_admission_key(ica_request, settings)
    coop_key = plan_api._planner_admission_key(coop_request, settings)

    assert ica_key != coop_key

    async def scenario() -> None:
        controller = PlannerAdmissionController(max_concurrent=1, max_queued=2)
        calls: list[str] = []

        async def build(program: str) -> str:
            calls.append(program)
            await asyncio.sleep(0)
            return program

        ica, coop = await asyncio.gather(
            controller.run(ica_key, lambda: build("ICA_STAMMIS")),
            controller.run(coop_key, lambda: build("COOP_MEMBER")),
        )
        stats = await controller.stats()

        assert (ica, coop) == ("ICA_STAMMIS", "COOP_MEMBER")
        assert calls == ["ICA_STAMMIS", "COOP_MEMBER"]
        assert stats.admitted == 2
        assert stats.coalesced == 0

    asyncio.run(scenario())


def test_distinct_work_is_rejected_before_factory_when_queue_is_full() -> None:
    async def scenario() -> None:
        controller = PlannerAdmissionController(max_concurrent=1, max_queued=0)
        started = asyncio.Event()
        release = asyncio.Event()
        rejected_factory_called = False

        async def active_build() -> str:
            started.set()
            await release.wait()
            return "active"

        async def rejected_build() -> str:
            nonlocal rejected_factory_called
            rejected_factory_called = True
            return "must-not-run"

        active = asyncio.create_task(controller.run("active", active_build))
        await started.wait()
        with pytest.raises(PlannerAdmissionOverloaded):
            await controller.run("different", rejected_build)
        release.set()
        assert await active == "active"
        assert rejected_factory_called is False
        assert (await controller.stats()).rejected == 1

    asyncio.run(scenario())


def test_failed_leader_releases_slot_and_propagates_to_follower() -> None:
    async def scenario() -> None:
        controller = PlannerAdmissionController(max_concurrent=1, max_queued=2)
        started = asyncio.Event()
        release = asyncio.Event()

        async def fail() -> str:
            started.set()
            await release.wait()
            raise ValueError("closed failure")

        leader = asyncio.create_task(controller.run("failure", fail))
        await started.wait()
        follower = asyncio.create_task(controller.run("failure", fail))
        await asyncio.sleep(0)
        release.set()
        outcomes = await asyncio.gather(leader, follower, return_exceptions=True)

        assert [type(outcome) for outcome in outcomes] == [ValueError, ValueError]
        assert await controller.run("next", lambda: asyncio.sleep(0, result="ok")) == "ok"
        assert (await controller.stats()).active == 0

    asyncio.run(scenario())


def test_api_admission_overflow_is_a_retryable_safe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared = SimpleNamespace(
        universe=SimpleNamespace(universe_id="price-universe:test")
    )
    monkeypatch.setattr(
        plan_api.GLOBAL_PREPARED_PRICE_UNIVERSES,
        "get_for_request",
        lambda *_args, **_kwargs: prepared,
    )
    started = asyncio.Event()
    release = asyncio.Event()
    service_calls: list[tuple[str, ...]] = []

    class FakeService:
        async def create_plan(self, request: PlanRequest):
            service_calls.append(tuple(program.value for program in request.membership_programs))
            started.set()
            await release.wait()
            return "closed-result"

    monkeypatch.setattr(plan_api, "_service", lambda _request: FakeService())
    settings = Settings(price_provider="mock")
    controller = PlannerAdmissionController(max_concurrent=1, max_queued=0)
    http_request = FastAPIRequest(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/plans",
            "headers": [],
            "app": SimpleNamespace(
                state=SimpleNamespace(planner_admission=controller)
            ),
        }
    )

    async def scenario() -> None:
        first = asyncio.create_task(
            plan_api._run_admitted_plan(PlanRequest(), http_request, settings)
        )
        await started.wait()
        with pytest.raises(HTTPException) as caught:
            await plan_api._run_admitted_plan(
                PlanRequest(memberships=["COOP_MEMBER"]),
                http_request,
                settings,
            )
        assert caught.value.status_code == 503
        assert caught.value.headers == {
            "Retry-After": "10",
            "X-Error-Code": "planner_admission_full",
        }
        assert caught.value.detail == (
            "Det är många som skapar menyer just nu. "
            "Försök igen om några sekunder."
        )
        release.set()
        assert await first == "closed-result"

    asyncio.run(scenario())
    assert service_calls == [()]


def test_admission_limits_are_configurable_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLANNER_MAX_CONCURRENT_REQUESTS", "2")
    monkeypatch.setenv("PLANNER_MAX_QUEUED_REQUESTS", "7")

    settings = Settings.from_env()

    assert settings.planner_max_concurrent_requests == 2
    assert settings.planner_max_queued_requests == 7


def test_negative_admission_queue_is_rejected() -> None:
    with pytest.raises(ValueError, match="PLANNER_MAX_QUEUED_REQUESTS"):
        Settings(planner_max_queued_requests=-1)
