from types import SimpleNamespace

from app.models.personal import MealSettings, PortionLimits
from app.services.personal_planner import (
    _QUALIFICATION_MEMORY,
    PersonalPlanner,
    _qualification_meal,
)
from app.services.planner_context import content_digest


def test_a_nutrition_requirement_keeps_what_the_ordinary_choices_rejected(monkeypatch):
    monkeypatch.setattr(_QUALIFICATION_MEMORY, "rows", type(_QUALIFICATION_MEMORY.rows)())
    planner = SimpleNamespace(_qualification_context=lambda ordinary=False: {"stores": ["a"]},
                              diagnostics=SimpleNamespace(pools=[{"raw": 4}]))
    ordinary = MealSettings(count=3, servings=2)
    limited = ordinary.model_copy(update={"limits": PortionLimits(min_protein_g=30)})
    rejected = {"status": "rejected", "reason": "Ingen vara", "stage": "product_qualification", "code": "DATA_BLOCKED"}
    choices = {"status": "rejected", "reason": "x", "stage": "policy_taste", "code": "RECIPE_CHOICES_CONFLICT"}
    _QUALIFICATION_MEMORY.put(content_digest([{"stores": ["a"]}, _qualification_meal(ordinary), ()]), {"rows": {
        "r1": rejected, "r2": {"status": "passed", "evidence": None}, "r3": choices, "r4": rejected}})
    own = {"status": "rejected", "reason": "protein", "stage": "nutrition", "code": "NUTRITION_TARGET_NOT_MET"}
    rows = PersonalPlanner._with_ordinary_rejections(planner, limited, (), {"r4": own})
    # Rejections carry over; a passed recipe and content-filter decisions are
    # qualified again; the requirement's own rows win.
    assert rows == {"r1": rejected, "r4": own}
    assert planner.diagnostics.pools[-1]["ordinary_rejections_reused"] == 1
    # Other stores: nothing to reuse.
    other = SimpleNamespace(_qualification_context=lambda ordinary=False: {"stores": ["b"]}, diagnostics=SimpleNamespace(pools=[{}]))
    assert PersonalPlanner._with_ordinary_rejections(other, limited, (), {}) == {}


def test_the_ordinary_context_is_the_same_request_without_requirements():
    """Every meal's requirements are in the context, so a limited request
    must look up the ordinary rows under the ordinary request's context."""
    from app.config import Settings
    from app.models.personal import PersonalPlanning
    from app.models.plan import PlanRequest
    from app.models.recipe_preferences import RecipePreferences

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    universe = prepared(product("pasta", 500, "g", 10))
    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")

    def planner(limits):
        request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs, personal=PersonalPlanning(
            meals=[MealSettings(count=1, servings=2, limits=limits)]))
        return PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(), facts={}, now=NOW)

    ordinary, limited = planner(PortionLimits()), planner(PortionLimits(min_protein_g=30, max_kcal=700))
    assert content_digest(limited._qualification_context()) != content_digest(ordinary._qualification_context())
    assert content_digest(limited._qualification_context(ordinary=True)) == content_digest(
        ordinary._qualification_context())
