"""Controlled local reproduction; no prices, provider calls or private state."""

import asyncio
import json
from time import perf_counter
from types import SimpleNamespace
from unittest.mock import patch

from app.config import Settings
from app.services import plan_prewarm
from app.services.complete_recipes import enabled
from app.services.performance_trace import activate_performance_trace
from app.services.planner_admission import PlannerAdmissionController


async def capture_background_request():
    captured = {}

    class Captured(Exception):
        pass

    class Service:
        async def create_plan(self, request):
            captured.update(
                complete_recipes=enabled(request),
                personal=request.personal is not None,
                recipes=request.recipes,
                servings=request.servings,
                max_stores=request.max_stores,
                mode=str(request.diversity_mode.value),
            )
            raise Captured()

    prepared = SimpleNamespace(
        universe=SimpleNamespace(
            universe_id="fixture", key=SimpleNamespace(postal_codes=("21120",), membership_map={})
        ),
        status=lambda **_: SimpleNamespace(status="fresh"),
        menu_search_cache=SimpleNamespace(stats=SimpleNamespace(hits=0, misses=0)),
    )
    manager = SimpleNamespace(get_active=lambda _: prepared)
    settings = Settings(
        price_universe_prewarm_enabled=True,
        complete_recipes_enabled=True,
        price_universe_prewarm_postal_code="21120",
        price_universe_prewarm_modes=("balanced",),
        price_universe_prewarm_max_stores=(3,),
        price_universe_prewarm_servings=2,
    )
    runner = plan_prewarm.BackendStandardPlanPrewarmRunner(
        settings,
        manager,
        scope_id="city:malmo",
        universe_id="fixture",
        service_factory=lambda *_: Service(),
    )
    try:
        await runner(plan_prewarm.standard_plan_prewarm_config(settings).profiles()[0])
    except Captured:
        pass
    assert captured["complete_recipes"] is False and captured["personal"] is False
    return captured


async def run(background):
    admission = PlannerAdmissionController(max_concurrent=1, max_queued=4)
    app = SimpleNamespace(state=SimpleNamespace(planner_admission=admission))
    prepared = SimpleNamespace(
        universe=SimpleNamespace(
            universe_id="fixture",
            key=SimpleNamespace(scope_id="city:malmo", city="Malmo", postal_codes=("21120",)),
        )
    )
    manager = SimpleNamespace(get_active=lambda scope: prepared if scope == "city:malmo" else None)
    entered, release, user_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    order = []

    class Service:
        async def create_plan(self, request):
            order.append("malmo_background_started")
            entered.set()
            await release.wait()
            order.append("malmo_background_finished")
            return "fixture"

    async def runner(settings, *, manager, service_factory):
        await service_factory(settings, manager).create_plan(None)
        return SimpleNamespace(status="complete", profiles_succeeded=1)

    async def user_work():
        order.append("lund_user_started")
        user_entered.set()
        return "user_result"

    queue = plan_prewarm.BackgroundPlanPrewarm(app, manager=manager, runner=runner, delay=0.001)
    settings = Settings(price_universe_prewarm_enabled=True)
    with patch.object(plan_prewarm, "_default_service_factory", lambda *_: Service()):
        if background:
            queue.enqueue(settings, prepared)
            await asyncio.wait_for(entered.wait(), 2)
        with activate_performance_trace() as trace:
            started = perf_counter()
            user = asyncio.create_task(admission.run("fixture-lund-user", user_work))
            # Give the real admission controller enough event-loop turns to
            # accept the user; the blocked worker is controlled by an event.
            for _ in range(200):
                stats = await admission.stats()
                if stats.queued == 1 or user_entered.is_set():
                    break
                await asyncio.sleep(0.001)
            if background:
                assert stats.active == 1 and stats.queued == 1
                assert not user_entered.is_set()
                await asyncio.sleep(0.2)
                assert not user_entered.is_set()
                release.set()
            assert await asyncio.wait_for(user, 2) == "user_result"
            elapsed = perf_counter() - started
            if background:
                await asyncio.wait_for(queue.task, 2)
            result = {
                "background": background,
                "order": order,
                "user_wall_seconds": elapsed,
                "queue_wait_ms": trace.snapshot().timings_ms["planner_queue_wait"],
                "user_waited_until_background_finished": background
                and order.index("lund_user_started") > order.index("malmo_background_finished"),
            }
        await queue.close()
    return result


async def main():
    result = [await run(True), await run(False)]
    assert result[0]["queue_wait_ms"] >= 190
    assert result[0]["user_waited_until_background_finished"]
    result = {"queue_cases": result, "actual_prewarm_request": await capture_background_request()}
    print(json.dumps(result, indent=2))


asyncio.run(main())
