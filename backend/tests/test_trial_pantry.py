"""The pantry the trial interfaces fill in is used by the meal planner.

Synthetic products; the recipe comes from the library. A pantry row without a
chosen product is used only when its form is the one the recipe asks for,
which is why the interfaces ask for the form before saving the row.
"""
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, MealSlot, PantryItem, PersonalPlanning
from app.models.recipe_preferences import RecipePreferences
from app.services.pantry_usage import usual_recipe_use
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.recipe_library import candidates

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

STATIC = Path(__file__).resolve().parents[1] / "app" / "static"


def plan_with(pantry):
    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")
    recipe = candidates(prefs, 2)[0]
    products = [product(i.name, max(100, i.quantity), i.unit, 10).model_copy(update={
        "category": "Kryddor" if i.form == "dry" else "Frukt & grönsaker" if i.form == "raw_edible" else "Mat",
        "name": "Grekisk Yoghurt Naturell 10%" if i.name == "yoghurt naturell" else i.name + " Malen" if i.name == "spiskummin" else i.name,
    }) for i in recipe.ingredients]
    request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs,
        personal=PersonalPlanning(meals=[MealSettings(count=1, servings=2)], use_pantry=True,
            slots=[MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=recipe)]))
    facts = {(p.store_id, p.product_id): ProductFacts(source="synthetic_test_declaration", source_product_id=p.product_id,
        source_snapshot_id="v2-frozen", ingredients=(p.name,), ingredients_complete=True) for p in products}
    items = [PantryItem(**row) for row in pantry(recipe)]
    result = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(*products), state(items), facts=facts, now=NOW).create()
    return recipe, result


def home(recipe):
    """An ingredient the user has at home, enough for the whole recipe."""
    return next(i for i in recipe.ingredients if i.form in {"raw_edible", "dry"} and i.unit == "g")


def test_pantry_row_with_the_recipes_form_is_used_instead_of_bought():
    recipe, result = plan_with(lambda r: [{"name": home(r).name, "quantity": home(r).quantity, "unit": "g", "form": home(r).form}])
    wanted = home(recipe)
    assert [(a["name"], a["quantity"], a["unit"]) for a in result.personal.allocations] == [(wanted.name, wanted.quantity, "g")]
    assert result.optimized_basket.total == 10 * (len(recipe.ingredients) - 1)
    bought = {row.ingredient for store in result.optimized_basket.stores for row in store.items}
    assert not any(wanted.name == name.split(" [")[0] for name in bought)


def test_pantry_row_without_form_is_left_alone_and_everything_is_bought():
    recipe, result = plan_with(lambda r: [{"name": home(r).name, "quantity": home(r).quantity, "unit": "g"}])
    assert result.personal.allocations == []
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)


def test_part_of_the_need_at_home_means_the_rest_is_bought():
    recipe, result = plan_with(lambda r: [{"name": home(r).name, "quantity": home(r).quantity / 2, "unit": "g", "form": home(r).form}])
    assert [a["quantity"] for a in result.personal.allocations] == [home(recipe).quantity / 2]
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)


@pytest.mark.parametrize("name, form, unit", [("ris", "dry", "g"), ("gul lök", "raw_edible", "g"), ("krossade tomater", "as_sold", "g")])
def test_the_proposed_form_and_unit_are_the_ones_recipes_use(name, form, unit):
    assert usual_recipe_use(name) == {"form": form, "unit": unit, "used_in_recipes": True}


def test_unknown_name_gets_no_proposal():
    assert usual_recipe_use("tandborste") == {"form": None, "unit": None, "used_in_recipes": False}


def test_trial_interfaces_have_account_pantry_and_purchase_built_in():
    mine = (STATIC / "next" / "mine.js").read_text(encoding="utf-8")
    for needed in ('"/api/personal/pantry"', "/api/personal/pantry-use", "/api/account/", '"purchase"', '"consume"', "measured_purchase_quantities", "migrate-guest"):
        assert needed in mine, needed
    for name in ("a", "b"):
        html = (STATIC / "next" / f"{name}.html").read_text(encoding="utf-8")
        script = (STATIC / "next" / f"{name}.js").read_text(encoding="utf-8")
        assert html.index("/static/next/core.js") < html.index("/static/next/mine.js") < html.index(f"/static/next/{name}.js")
        assert "skafferi()" in script and "konto()" in script and "N.afterShopping" in script
        # The ordinary interface is no longer where the pantry and the account are.
        assert "finns i vanliga Smako" not in script


def test_pantry_api_as_the_trial_interfaces_use_it(monkeypatch, tmp_path):
    """Typed item -> proposed form -> saved row with that form -> read back, per owner."""
    from app.api import account, personal, plan
    from fastapi.testclient import TestClient

    from backend.tests.test_privacy_erasure import _application

    application, factory, settings = _application(tmp_path)
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    application.include_router(personal.router)
    personal.install_handlers(application)
    with TestClient(application) as first, TestClient(application) as second:
        typed = first.post("/api/personal/interpret-extra", json={"text": "ris 1 kg"}).json()
        assert (typed["query"], typed["quantity"], typed["unit"], typed["food"]) == ("ris", 1000, "g", True)
        assert first.post("/api/personal/interpret-extra", json={"text": "tandborste 1 st"}).json()["food"] is False
        use = first.get("/api/personal/pantry-use", params={"name": typed["query"]}).json()
        assert use == {"form": "dry", "unit": "g", "used_in_recipes": True, "food": True}
        assert first.get("/api/personal/pantry-use", params={"name": " "}).status_code == 422
        row = {"id": "rice-1", "name": typed["query"], "quantity": typed["quantity"], "unit": typed["unit"],
               "product_key": None, "unusable": False, "food": True, "form": use["form"]}
        saved = first.put("/api/personal/pantry", json={"revision": 0, "items": [row]})
        assert saved.status_code == 200
        item = saved.json()["items"][0]
        assert (item["name"], item["quantity"], item["form"], item["available"], item["reserved"]) == ("ris", 1000, "dry", 1000, 0)
        # The stale revision the interface would send after a change elsewhere is refused, not merged.
        assert first.put("/api/personal/pantry", json={"revision": 0, "items": []}).status_code == 409
        assert second.get("/api/personal/state").json()["items"] == []
    factory.kw["bind"].dispose()
