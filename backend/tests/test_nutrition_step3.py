"""Step 3 of the 2026-11-14 beta test report: nutrition that is fast and always shown.

- Per-100 nutrition evidence is shared across requests (same products, facts
  and reference data) and computed for all four macros at once.
- A product that declares only some of the four keeps its declaration.
- The final plan shows values per portion even when no limit was set; this
  never blocks a plan.
"""
from unittest.mock import patch

from app.config import Settings
from app.models.personal import MealSettings, MealSlot, PortionLimits
from app.services.nutrition_reference import reference_options
from app.services.personal_planner import PersonalPlanner

from backend.tests.test_nutrition_reference import dinner, products
from backend.tests.test_personal_planning_v2 import NOW, request, run, state
from backend.tests.test_personal_qualified_facts import facts


def plain_dinner(**kwargs):
    return request(slots=[MealSlot(id="d", day=1, meal_type="dinner", recipe=dinner())],
                   meals=[MealSettings(count=1, servings=4)], **kwargs)


def test_the_final_plan_shows_nutrition_per_portion_without_limits():
    plan = run(products(), plain_dinner(allow_nutrition_estimates=True))
    row = plan.personal.checks["nutrition"][0]
    assert row["status"] in {"ESTIMATED", "VERIFIED"}
    assert set(row["values"]) == {"kcal", "protein_g", "carbs_g", "fat_g"}
    assert row["values"]["protein_g"] > 0


def test_without_estimates_nothing_is_invented_and_the_plan_still_works():
    plan = run(products(), plain_dinner(allow_nutrition_estimates=False))
    assert plan.personal.checks["nutrition"][0]["status"] == "NOT_REQUESTED"
    assert plan.personal.checks["nutrition"][0]["values"] == {}


def test_evidence_is_computed_once_for_all_macros_and_reused_by_the_next_request():
    universe = products()
    p = universe.universe.products[0]
    calls = []
    original = PersonalPlanner._nutrition_evidence

    def counting(self, product, name, unit, requested, recipe):
        calls.append(frozenset(requested))
        return original(self, product, name, unit, requested, recipe)

    def planner(limits):
        return PersonalPlanner(request(slots=[MealSlot(id="d", day=1, meal_type="dinner", recipe=dinner())],
                                       meals=[MealSettings(count=1, servings=4, limits=PortionLimits(**limits))],
                                       allow_nutrition_estimates=True),
                               Settings(), universe, state(), facts={}, now=NOW)

    with patch.object(PersonalPlanner, "_nutrition_evidence", counting):
        first = planner({"min_protein_g": 20}).nutrition_evidence(p, "kycklingbröstfilé", "g", {"protein_g"}, None)
        second = planner({"max_kcal": 700}).nutrition_evidence(p, "kycklingbröstfilé", "g", {"kcal"}, None)
    assert calls == [frozenset({"kcal", "protein_g", "carbs_g", "fat_g"})]
    assert first is second


def test_a_partial_declaration_is_not_replaced_by_a_reference_estimate():
    universe = products()
    p = universe.universe.products[0]
    declaration = facts(p, nutrition={"protein_g": 23}, nutrition_unit="g", nutrition_basis="per 100 g",
                        nutrition_preparation="as_sold")
    planner = PersonalPlanner(plain_dinner(allow_nutrition_estimates=True), Settings(), universe, state(),
                              facts={(p.store_id, p.product_id): declaration}, now=NOW)
    with patch.object(PersonalPlanner, "_nutrition_evidence", lambda self, product, name, unit, requested, recipe: tuple(sorted(requested))):
        assert planner.nutrition_evidence(p, "kycklingbröstfilé", "g", {"protein_g"}, None) == ("protein_g",)


def test_reference_options_are_built_once():
    assert reference_options() is reference_options()


def test_the_prewarm_request_asks_for_all_four_macros_without_restricting_anything():
    from app.services.nutrition_prewarm import WARM_LIMITS, warm_request
    from app.services.personal_nutrition import requested_nutrients

    warm = warm_request(products())
    assert [m.meal_type for m in warm.personal.meals] == ["dinner", "breakfast", "snack"]
    for meal in warm.personal.meals:
        assert requested_nutrients(meal.limits) == {"kcal", "protein_g", "carbs_g", "fat_g"}
    assert all(v == 0 for k, v in WARM_LIMITS.items() if k.startswith("min_")) and WARM_LIMITS["max_kcal"] >= 4000
    assert warm.personal.use_pantry is False and warm.personal.allow_nutrition_estimates


def test_nutrition_prewarm_runs_only_through_idle_admission(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.services import nutrition_prewarm
    from app.services.planner_admission import PlannerAdmissionController

    monkeypatch.setenv("SMAKO_NUTRITION_PREWARM", "1")
    universe = products()
    ran = []
    monkeypatch.setattr(nutrition_prewarm, "warm_nutrition", lambda settings, prepared: ran.append(prepared) or "complete")
    manager = SimpleNamespace(get_active=lambda scope: universe)

    async def scenario():
        app = SimpleNamespace(state=SimpleNamespace(planner_admission=PlannerAdmissionController(max_concurrent=1, max_queued=2)))
        assert nutrition_prewarm.schedule_nutrition_prewarm(app, Settings(), universe, manager, delay=0.01, attempts=3) == "scheduled"
        (task,) = app.state.nutrition_prewarm_tasks
        assert await task == "complete"
        monkeypatch.setenv("SMAKO_NUTRITION_PREWARM", "0")
        assert nutrition_prewarm.schedule_nutrition_prewarm(app, Settings(), universe, manager) == "disabled"

    asyncio.run(scenario())
    assert ran == [universe]


def test_a_prewarm_round_that_reaches_its_deadline_continues_in_another_round(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.services import nutrition_prewarm
    from app.services.planner_admission import PlannerAdmissionController

    monkeypatch.setenv("SMAKO_NUTRITION_PREWARM", "1")
    universe = products()
    outcomes = iter(["deadline", "deadline", "complete", "complete"])
    rounds = []
    monkeypatch.setattr(nutrition_prewarm, "warm_nutrition",
                        lambda settings, prepared: rounds.append(1) or next(outcomes))
    manager = SimpleNamespace(get_active=lambda scope: universe)

    async def scenario():
        app = SimpleNamespace(state=SimpleNamespace(planner_admission=PlannerAdmissionController(max_concurrent=1, max_queued=2)))
        nutrition_prewarm.schedule_nutrition_prewarm(app, Settings(), universe, manager, delay=0.01, attempts=10)
        (task,) = app.state.nutrition_prewarm_tasks
        return await task

    assert asyncio.run(scenario()) == "complete"
    assert len(rounds) == 3  # Two rounds hit the deadline; the third finished. Never more than WARM_ROUNDS.
