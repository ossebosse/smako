""""Suggest a recipe" for a meal never brings back a recipe removed from it."""
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, MealSlot, PersonalPlanning
from app.models.recipe import RecipeIngredient
from app.services.personal_planner import PersonalPlanner, removed_recipe_key
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator

from backend.tests.test_personal_planning_v2 import NOW, prepared, recipe, state
from backend.tests.test_personal_planning_v2 import product as priced_product


def _dish(name, food, grams):
    return recipe(name=name, ingredients=[RecipeIngredient(name=food, quantity=grams, unit="g")])


BREAD = _dish("Bröd", "bröd", 100)
CHEAP = _dish("Billig kyckling", "kyckling", 100)
DEAR = _dish("Dyr kyckling", "kyckling", 600)


def _suggest(monkeypatch, removed):
    meal = MealSettings(meal_type="snack", count=3, servings=1, distribution={"chicken": 1, "vegetarian": 2})
    slots = [MealSlot(id="s1", day=1, meal_type="snack", removed_recipes=removed),
             MealSlot(id="s2", day=2, meal_type="snack", recipe=BREAD),
             MealSlot(id="s3", day=3, meal_type="snack", recipe=BREAD)]
    req = PlanRequest(recipes=0, diversity_mode="cheapest", personal=PersonalPlanning(meals=[meal], slots=slots))
    p = prepared(priced_product("bröd", 500, "g", 10), priced_product("kyckling", 500, "g", 20))
    monkeypatch.setattr(DeterministicRecipeCandidateGenerator, "generate_for_meal_type",
                        lambda *a, **kw: [BREAD, CHEAP, DEAR])
    result = PersonalPlanner(req, Settings(price_provider="mock"), p, state(), now=NOW).create(replace_slot="s1")
    return result.personal.slots[0]


def test_suggestion_skips_the_removed_recipe(monkeypatch):
    assert _suggest(monkeypatch, []).recipe.name == "Billig kyckling"
    slot = _suggest(monkeypatch, [removed_recipe_key(CHEAP)])
    assert slot.recipe.name == "Dyr kyckling"
    # The meal keeps its removal history for the next suggestion.
    assert slot.removed_recipes == [removed_recipe_key(CHEAP)]


def test_removed_recipe_key_uses_the_design_base_for_smako_recipes():
    from app.services.recipe_library import current_recipes

    designed = next(r for r in current_recipes() if r.design)
    assert removed_recipe_key(designed) == f"base:{designed.design.base_id}"
    assert removed_recipe_key(CHEAP).startswith("recipe:")


def test_slots_without_removals_serialize_as_before():
    slot = MealSlot(id="s1", day=1, meal_type="dinner")
    assert "removed_recipes" not in slot.model_dump()
    assert MealSlot(id="s1", day=1, meal_type="dinner", removed_recipes=["recipe:x"]).model_dump()["removed_recipes"] == ["recipe:x"]


def test_remove_records_the_recipe_on_the_meal(tmp_path, monkeypatch):
    from app.api import personal, plan
    from app.models.recipe import Recipe
    from app.services.personal_planner import PersonalPlanner as RealPlanner
    from fastapi.testclient import TestClient

    from backend.tests.test_personal_planning_v2 import request, run
    from backend.tests.test_privacy_erasure import _application

    application, _, settings = _application(tmp_path, price_provider="mock",
                                             library_search_policy="smako-current-library-v2")
    for module in (plan, personal):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    application.include_router(plan.router)
    application.include_router(personal.router)
    personal.install_handlers(application)
    p = prepared(priced_product("mjölk", 1000, "ml", 10), priced_product("bröd", 500, "g", 20))
    meal = MealSettings(meal_type="dinner", count=1, servings=1)
    req = request(meals=[meal], slots=[MealSlot(id="d1", day=1, meal_type="dinner", recipe=recipe())])
    initial = run(p, req)

    async def build(*args):
        return initial
    monkeypatch.setattr(plan, "_run_admitted_plan", build)
    monkeypatch.setattr(personal.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_for_request", lambda *a, **kw: p)
    monkeypatch.setattr(personal, "PersonalPlanner",
                        lambda r, s, prep, private, **kw: RealPlanner(r, s, prep, private, facts={}, now=NOW, **kw))
    with TestClient(application) as client:
        saved = client.post("/api/plans", json=req.model_dump(mode="json"))
        assert saved.status_code == 201, saved.text
        saved = saved.json()
        pantry = client.get("/api/personal/state").json()
        removed = Recipe.model_validate(saved["plan"]["personal"]["slots"][0]["recipe"])
        result = client.post(f"/api/personal/plans/{saved['plan_id']}/change", json={
            "action": "remove", "slot_id": "d1", "revision": saved["revision"],
            "pantry_revision": pantry["revision"]})
        assert result.status_code == 200, result.text
        slot = result.json()["saved"]["plan"]["personal"]["slots"][0]
        assert slot.get("recipe") is None
        assert slot["removed_recipes"] == [removed_recipe_key(removed)]
