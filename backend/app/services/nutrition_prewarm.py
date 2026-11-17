"""Warm the shared per-100 nutrition evidence after a new price universe.

Step 3 of the 2026-11-14 beta test report: nutrition limits ran out of time
because every request computed source nutrition evidence for every candidate
product again. ``PersonalPlanner`` now keeps that evidence in a bounded,
versioned process cache; this runs one ordinary planner request with
trivially satisfied limits for all four macros (protein, carbohydrates, fat
>= 0 and energy <= 4000 kcal per portion) for each meal type, so the first
person who sets a limit finds the evidence ready.

It only runs when the planner is idle, stops at its own deadline, keeps no
plan and writes nothing; a partial run still leaves useful evidence.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import os

WARM_LIMITS = {"min_protein_g": 0, "min_carbs_g": 0, "min_fat_g": 0, "max_kcal": 4000}
WARM_SECONDS = 45.0
# Step 6 (2026-11-16): a round that reaches its deadline leaves its evidence in
# the shared cache, so the next round continues from there. Each round waits
# for an idle planner again, so people always go first.
WARM_ROUNDS = 3


def warm_request(prepared):
    from app.models import PlanRequest

    stores = sorted({store.store_id for store in prepared.stores})
    meal = {"count": 3, "servings": 2, "diet": "mixed", "limits": WARM_LIMITS,
            "recipe_choices": {"min_ingredients": 1, "max_ingredients": 40}}
    return PlanRequest.model_validate({
        "postal_code": prepared.universe.key.postal_codes[0],
        "recipes": 3, "servings": 2, "max_stores": min(2, len(stores)), "allowed_store_ids": stores,
        "purchase_planning_mode": "estimated", "recipe_preferences": {"mode": "complete"},
        "personal": {"allow_nutrition_estimates": True, "use_pantry": False,
                     "meals": [{**meal, "meal_type": t} for t in ("dinner", "breakfast", "snack")]},
    })


def plain_request(prepared):
    """The everyday choice: dinners for two in every store of the area.

    Per-recipe qualification is kept without likes, dislikes or the number of
    dinners (PersonalPlanner._qualification_context), so this fills it for any
    plain dinner week in the whole area, as the owner's 2026-11-17 speed goal
    asks of Smako as a whole rather than of one city.
    """
    from app.models import PlanRequest

    stores = sorted(s.store_id for s in prepared.request_view().stores)
    return PlanRequest.model_validate({
        "postal_code": prepared.universe.key.postal_codes[0],
        "recipes": 3, "servings": 2, "max_stores": min(2, len(stores)), "allowed_store_ids": stores,
        "purchase_planning_mode": "estimated", "recipe_preferences": {"mode": "complete"},
        "personal": {"allow_nutrition_estimates": True, "use_pantry": True,
                     "staples_at_home": ["salt", "svartpeppar", "rapsolja"],
                     "meals": [{"meal_type": "dinner", "count": 3, "servings": 2, "diet": "mixed",
                                "recipe_choices": {"min_ingredients": 1, "max_ingredients": 40}}]},
    })


def warm_nutrition(settings, prepared, *, seconds=WARM_SECONDS):
    """Run in a worker thread. Returns a short status for logs."""
    from app.services.personal_planner import PersonalPlanner
    from app.services.plan_jobs import PlanningDeadlineExceeded, planning_deadline

    state = {"id": "nutrition-prewarm", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}
    try:
        for request in (plain_request(prepared), warm_request(prepared)):
            with planning_deadline(seconds):
                PersonalPlanner(request, settings, prepared, state).create()
        return "complete"
    except PlanningDeadlineExceeded:
        return "deadline"
    except Exception as exc:  # noqa: BLE001 -- optional warming; the outcome is only logged.
        logging.getLogger(__name__).info("nutrition_prewarm_stopped error_type=%s", type(exc).__name__)
        return "stopped"


def enabled() -> bool:
    return os.getenv("SMAKO_NUTRITION_PREWARM", "1") != "0"


async def _warm_when_idle(application, settings, prepared, manager, *, delay, attempts):
    try:
        return await _warm_attempts(application, settings, prepared, manager, delay=delay, attempts=attempts)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 -- optional; only the type is logged.
        logging.getLogger(__name__).warning("nutrition_prewarm_failed error_type=%s", type(exc).__name__)
        return "failed"


async def _warm_attempts(application, settings, prepared, manager, *, delay, attempts):
    from app.services.planner_admission import PlannerAdmissionBusy

    scope = prepared.universe.key.scope_id

    async def work():
        if manager.get_active(scope) is not prepared:
            return "superseded"
        # Lowest CPU priority and at most one worker (planner_processes), so
        # people's plans always get the cores first.
        from app.services.planner_processes import run_in_background_thread
        return await asyncio.wrap_future(run_in_background_thread(
            lambda: warm_nutrition(settings, prepared), name="smako-nutrition-prewarm"))

    rounds = 0
    for _ in range(attempts):
        await asyncio.sleep(delay)
        if manager.get_active(scope) is not prepared:
            return "superseded"
        try:
            status = await application.state.planner_admission.run(
                f"prewarm-nutrition:{scope}:{prepared.universe.universe_id}:{rounds}", work, only_if_idle=True)
        except PlannerAdmissionBusy:
            continue
        rounds += 1
        logging.getLogger("uvicorn.error").info("nutrition_prewarm scope=%s universe=%s round=%s status=%s",
                                                scope, prepared.universe.universe_id, rounds, status)
        if status != "deadline" or rounds >= WARM_ROUNDS:
            return status
    return "busy"


def schedule_nutrition_prewarm(application, settings, prepared, manager=None, *, delay=20.0, attempts=30):
    """Start warming in the background; independent of the standard plan prewarm setting."""
    if not enabled():
        return "disabled"
    if manager is None:
        from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
        manager = GLOBAL_PREPARED_PRICE_UNIVERSES
    tasks = getattr(application.state, "nutrition_prewarm_tasks", None)
    if tasks is None:
        tasks = application.state.nutrition_prewarm_tasks = set()
    task = asyncio.get_running_loop().create_task(
        _warm_when_idle(application, settings, prepared, manager, delay=delay, attempts=attempts))
    tasks.add(task)
    task.add_done_callback(tasks.discard)
    return "scheduled"


async def close_nutrition_prewarm(application):
    for task in list(getattr(application.state, "nutrition_prewarm_tasks", ())):
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError, Exception):  # Shutting down optional work.
            await task
