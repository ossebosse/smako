"""Equivalent food calculations, exact cache dependencies and bounded lifetimes."""

import asyncio
import threading
from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, MealSlot, PantryItem, PersonalPlanning, PortionLimits
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.reviewed_cold_meals import candidates

from backend.tests.test_combined_profile import products
from backend.tests.test_personal_planning_v2 import NOW, key_for, request, run, state


def planner(minimum=22):
    prepared, facts = products()
    recipe = candidates("snack", 1)[0]
    slot = MealSlot(id="snack-1", day=1, meal_type="snack", recipe=recipe)
    req = request(
        slots=[slot],
        meals=[
            MealSettings(
                meal_type="snack", count=1, servings=1, limits=PortionLimits(min_protein_g=minimum)
            )
        ],
    )
    return PersonalPlanner(
        req, Settings(price_provider="mock"), prepared, state(), facts=facts, now=NOW
    ), slot


def test_repeated_slot_keeps_identity_but_reuses_equal_food_calculation():
    p, slot = planner()
    other = slot.model_copy(update={"id": "snack-2", "day": 2})
    with patch.object(p, "_check_nutrition_uncached", wraps=p._check_nutrition_uncached) as check:
        result = p.basket([slot, other])
    assert check.call_count == 1
    rows = result["checks"]["nutrition"]
    assert [r["slot_id"] for r in rows] == ["snack-1", "snack-2"]
    assert [r["values"]["protein_g"] for r in rows] == [22, 22]


def test_unrounded_quantity_limits_and_mutable_preparation_do_not_alias():
    p, slot = planner()
    p.basket([slot])
    original = slot.recipe.ingredients[0]
    slot.recipe.ingredients[0] = original.model_copy(update={"quantity": 200 - 1e-9})
    with pytest.raises(PolicyConflict, match="protein_g"):
        p.basket([slot])
    slot.recipe.ingredients[0] = original
    p.meals["snack"].limits.min_protein_g = 22 + 1e-10
    with pytest.raises(PolicyConflict, match="protein_g"):
        p.basket([slot])
    p.meals["snack"].limits.min_protein_g = 22
    slot.recipe.instructions.append("Koka och häll av.")
    with pytest.raises(PolicyConflict, match="beredningsgrund"):
        p.basket([slot])


def test_other_fact_versions_and_accounts_cannot_share_nutrition():
    p, slot = planner()
    p.basket([slot])
    changed = {k: replace(v, nutrition={"protein_g": 5}) for k, v in p.facts.items()}
    other = PersonalPlanner(p.request, p.settings, p.prepared, state(), facts=changed, now=NOW)
    with pytest.raises(PolicyConflict, match="protein_g"):
        other.basket([slot])
    assert other.nutrition_cache is not p.nutrition_cache
    assert other.slot_nutrition_cache is not p.slot_nutrition_cache


@pytest.mark.parametrize("servings,minimum,stock", [(1, 30, 0), (2, 32, 0), (1, 30, 100)])
def test_joint_free_search_equals_uncached_with_changed_profile_and_stock(servings, minimum, stock):
    prepared, facts = products()
    req = PlanRequest(
        recipes=0,
        max_stores=2,
        personal=PersonalPlanning(
            meals=[
                MealSettings(
                    meal_type="breakfast",
                    count=3,
                    servings=servings,
                    limits=PortionLimits(min_protein_g=minimum),
                ),
                MealSettings(
                    meal_type="snack", count=2, servings=1, limits=PortionLimits(min_protein_g=20)
                ),
            ],
        ),
    )
    inventory = state(
        [
            PantryItem(
                name="Kvarg Naturell 0,2%",
                quantity=stock,
                unit="g",
                product_key=key_for(prepared, "Kvarg Naturell 0,2%"),
            )
        ]
        if stock
        else []
    )
    before = deepcopy(inventory)
    fast = run(prepared, req, inventory, facts=facts)
    with (
        patch.object(PersonalPlanner, "nutrition_evidence", PersonalPlanner._nutrition_evidence),
        patch.object(
            PersonalPlanner, "_check_nutrition", PersonalPlanner._check_nutrition_uncached
        ),
    ):
        ordinary = run(prepared, req, inventory, facts=facts)
    assert inventory == before
    for attribute in ("optimized_basket", "ingredients", "recipes", "personal"):
        assert getattr(fast, attribute) == getattr(ordinary, attribute)
    assert not stock or fast.personal.allocations


def test_cancelled_real_thread_keeps_admission_and_duplicate_key_until_it_exits():
    from app.api.plan import _run_personal_thread
    from app.services.planner_admission import PlannerAdmissionController

    async def scenario():
        controller = PlannerAdmissionController(max_concurrent=1, max_queued=1)
        started, release = threading.Event(), threading.Event()
        calls = []

        def slow():
            calls.append("first")
            started.set()
            assert release.wait(timeout=5)
            return 1

        first = asyncio.create_task(controller.run("first", lambda: _run_personal_thread(slow)))
        try:
            while not started.is_set():
                await asyncio.sleep(0.001)
            first.cancel()
            await asyncio.sleep(0.01)
            first.cancel()  # Repeated cancellation must not abandon the worker.
            second = asyncio.create_task(
                controller.run(
                    "second", lambda: _run_personal_thread(lambda: calls.append("second"))
                )
            )
            await asyncio.sleep(0.01)
            stats = await controller.stats()
            assert stats.active == 1 and stats.queued == 1
            assert calls == ["first"]
        finally:
            release.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        await second
        assert calls == ["first", "second"]
        assert (await controller.stats()).in_flight_keys == 0

    asyncio.run(scenario())
