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

import logging

WARM_LIMITS = {"min_protein_g": 0, "min_carbs_g": 0, "min_fat_g": 0, "max_kcal": 4000}
WARM_SECONDS = 45.0


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


def warm_nutrition(settings, prepared, *, seconds=WARM_SECONDS):
    """Run in a worker thread. Returns a short status for logs."""
    from app.services.personal_planner import PersonalPlanner
    from app.services.plan_jobs import PlanningDeadlineExceeded, planning_deadline

    state = {"id": "nutrition-prewarm", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}
    try:
        with planning_deadline(seconds):
            PersonalPlanner(warm_request(prepared), settings, prepared, state).create()
        return "complete"
    except PlanningDeadlineExceeded:
        return "deadline"
    except Exception as exc:  # noqa: BLE001 -- optional warming; the outcome is only logged.
        logging.getLogger(__name__).info("nutrition_prewarm_stopped error_type=%s", type(exc).__name__)
        return "stopped"
