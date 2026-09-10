from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from grocery_data.app.services.plan_prewarm import (
    PlanPrewarmExecution,
    PlanPrewarmStatusRegistry,
    StandardPlanPrewarmConfig,
    prewarm_standard_plans,
)

NOW = datetime(2026, 8, 26, 12, tzinfo=UTC)


def test_standard_profile_matrix_defaults_to_modes_store_limits_and_five_by_four() -> None:
    profiles = StandardPlanPrewarmConfig().profiles()

    assert len(profiles) == 6
    assert {(profile.mode, profile.max_stores) for profile in profiles} == {
        (mode, max_stores)
        for mode in ("cheapest", "balanced", "varied")
        for max_stores in (1, 2)
    }
    assert {profile.recipes for profile in profiles} == {5}
    assert {profile.servings for profile in profiles} == {4}
    assert {profile.candidate_recipe_count for profile in profiles} == {80}
    assert {profile.beam_width for profile in profiles} == {30}


def test_standard_profile_matrix_is_bounded_and_configurable() -> None:
    config = StandardPlanPrewarmConfig(
        modes=("balanced",),
        max_stores=(2,),
        recipes=3,
        servings=6,
        candidate_recipe_count=40,
        candidate_search_limit=30,
        beam_width=15,
    )

    [profile] = config.profiles()
    assert profile.mode == "balanced"
    assert profile.max_stores == 2
    assert profile.recipes == 3
    assert profile.servings == 6
    assert profile.candidate_search_limit == 30


@pytest.mark.asyncio
async def test_prewarm_never_runs_before_successful_activation() -> None:
    calls = 0

    async def runner(_profile):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return PlanPrewarmExecution(cache_outcome="miss_filled")

    report = await prewarm_standard_plans(
        universe_id="universe-1",
        activated=False,
        config=StandardPlanPrewarmConfig(enabled=True),
        runner=runner,
        now=NOW,
    )

    assert report.status == "skipped_universe_not_activated"
    assert report.profiles_requested == 6
    assert calls == 0


@pytest.mark.asyncio
async def test_prewarm_profiles_fill_and_hit_the_same_active_cache() -> None:
    calls = 0

    async def runner(_profile):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        return PlanPrewarmExecution(
            cache_outcome="miss_filled" if calls in {1, 4} else "hit"
        )

    report = await prewarm_standard_plans(
        universe_id="universe-1",
        activated=True,
        config=StandardPlanPrewarmConfig(enabled=True),
        runner=runner,
        is_active=lambda universe_id: universe_id == "universe-1",
        now=NOW,
    )

    assert report.status == "complete"
    assert report.profiles_succeeded == 6
    assert report.profiles_failed == 0
    assert report.cache_misses_filled == 2
    assert report.cache_hits == 4
    assert report.universe_remained_active is True
    assert report.live_provider_requests == 0


@pytest.mark.asyncio
async def test_one_prewarm_failure_is_sanitized_and_does_not_deactivate_universe() -> None:
    active = {"universe_id": "universe-1"}
    calls = 0

    async def runner(_profile):  # type: ignore[no-untyped-def]
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("secret provider/token detail")
        return PlanPrewarmExecution(cache_outcome="hit")

    report = await prewarm_standard_plans(
        universe_id="universe-1",
        activated=True,
        config=StandardPlanPrewarmConfig(
            enabled=True,
            modes=("cheapest", "balanced", "varied"),
            max_stores=(2,),
        ),
        runner=runner,
        is_active=lambda universe_id: active["universe_id"] == universe_id,
        now=NOW,
    )

    assert calls == 3
    assert active["universe_id"] == "universe-1"
    assert report.status == "partial_failure"
    assert report.profiles_succeeded == 2
    assert report.profiles_failed == 1
    assert report.items[1].error_type == "RuntimeError"
    assert report.universe_remained_active is True
    assert "secret provider" not in report.model_dump_json()


@pytest.mark.asyncio
async def test_runner_cannot_report_live_provider_requests_as_success() -> None:
    async def invalid_runner(_profile):  # type: ignore[no-untyped-def]
        return {
            "cache_outcome": "miss_filled",
            "verified": True,
            "live_provider_requests": 1,
        }

    report = await prewarm_standard_plans(
        universe_id="universe-1",
        activated=True,
        config=StandardPlanPrewarmConfig(
            enabled=True,
            modes=("balanced",),
            max_stores=(2,),
        ),
        runner=invalid_runner,
        now=NOW,
    )

    assert report.status == "failed"
    assert report.items[0].error_type == "ValidationError"
    assert report.live_provider_requests == 0


def test_prewarm_registry_exposes_only_sanitized_report() -> None:
    registry = PlanPrewarmStatusRegistry()
    report_json = {
        "status": "runner_unavailable",
        "universe_id": "universe-1",
        "started_at": NOW,
        "finished_at": NOW,
        "profiles_requested": 6,
        "profiles_succeeded": 0,
        "profiles_failed": 0,
        "cache_hits": 0,
        "cache_misses_filled": 0,
        "cache_unchanged": 0,
        "items": (),
        "universe_remained_active": True,
        "live_provider_requests": 0,
    }
    from grocery_data.app.services.plan_prewarm import PlanPrewarmReport

    report = PlanPrewarmReport.model_validate(report_json)
    registry.publish("city:lund", report)

    assert registry.get("CITY:LUND") == report
    assert "token" not in json.dumps(report.model_dump(mode="json"))
