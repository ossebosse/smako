"""The pantry the trial interfaces fill in is used by the meal planner.

Synthetic products; the recipe comes from the library. A pantry row without a
chosen product counts as uncooked (owner decision 2026-11-13), so it serves
recipes that want the food raw, dry or as sold.
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


def can(name, quantity):
    """A can whose declared drained weight is 60 % of the package."""
    return {"name": f"Vita {name}" if name == "bönor" else name.capitalize(), "package_quantity": round(quantity / 0.6),
            "usable_quantity": quantity, "usable_unit": "g", "category": "Konserver"}


def plan_with(pantry, index=0):
    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")
    recipe = candidates(prefs, 2)[index]
    products = [product(i.name, max(100, i.quantity), i.unit, 10).model_copy(update={
        "category": "Kryddor" if i.form == "dry" else "Frukt & grönsaker" if i.form == "raw_edible" else "Mat",
        "name": "Grekisk Yoghurt Naturell 10%" if i.name == "yoghurt naturell" else i.name + " Malen" if i.name == "spiskummin" else i.name,
        **(can(i.name, i.quantity) if i.form == "cooked_drained" else {}),
    }) for i in recipe.ingredients]
    request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs,
        personal=PersonalPlanning(meals=[MealSettings(count=1, servings=2)], use_pantry=True,
            slots=[MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=recipe)]))
    facts = {(p.store_id, p.product_id): ProductFacts(source="synthetic_test_declaration", source_product_id=p.product_id,
        source_snapshot_id="v2-frozen", ingredients=(p.name,), ingredients_complete=True,
        # A can's drained weight, declared by the source.
        **({"field_sources": {"usable_quantity": ({"basis": "drained", "unit": "g", "quantity": p.usable_quantity, "source": "synthetic_label"},)}}
           if p.usable_quantity else {})) for p in products}
    universe = prepared(*products)
    key = {universe.universe.products[positions[0]].name: k for k, positions in universe.product_search_index.groups.items()}
    items = [PantryItem(**row) for row in pantry(recipe, key)]
    result = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(items), facts=facts, now=NOW).create()
    return recipe, result


def home(recipe):
    """An ingredient the user has at home, enough for the whole recipe."""
    return next(i for i in recipe.ingredients if i.form in {"raw_edible", "dry"} and i.unit == "g")


def test_pantry_row_with_the_recipes_form_is_used_instead_of_bought():
    recipe, result = plan_with(lambda r, _key: [{"name": home(r).name, "quantity": home(r).quantity, "unit": "g", "form": home(r).form}])
    wanted = home(recipe)
    assert [(a["name"], a["quantity"], a["unit"]) for a in result.personal.allocations] == [(wanted.name, wanted.quantity, "g")]
    assert result.optimized_basket.total == 10 * (len(recipe.ingredients) - 1)
    bought = {row.ingredient for store in result.optimized_basket.stores for row in store.items}
    assert not any(wanted.name == name.split(" [")[0] for name in bought)


def test_pantry_row_without_form_counts_as_uncooked_and_is_used():
    recipe, result = plan_with(lambda r, _key: [{"name": home(r).name, "quantity": home(r).quantity, "unit": "g"}])
    wanted = home(recipe)
    assert [(a["name"], a["quantity"]) for a in result.personal.allocations] == [(wanted.name, wanted.quantity)]
    assert result.optimized_basket.total == 10 * (len(recipe.ingredients) - 1)


def test_pantry_row_stated_as_cooked_is_not_used_for_an_uncooked_need():
    recipe, result = plan_with(lambda r, _key: [{"name": home(r).name, "quantity": home(r).quantity, "unit": "g", "form": "cooked_drained"}])
    assert result.personal.allocations == []
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)


def drained(recipe):
    return next(i for i in recipe.ingredients if i.form == "cooked_drained" and i.unit == "g")


def test_a_chosen_can_kept_as_drained_weight_covers_a_drained_need():
    """The pantry keeps a can as its drained weight, as a registered purchase does."""
    recipe, result = plan_with(lambda r, key: [{"name": drained(r).name, "quantity": drained(r).quantity, "unit": "g",
                                                "product_key": key[can(drained(r).name, 0)["name"]]}], index=3)
    need = drained(recipe)
    assert [(a["name"], a["quantity"]) for a in result.personal.allocations] == [(need.name, need.quantity)]
    assert result.optimized_basket.total == 10 * (len(recipe.ingredients) - 1)


def test_a_typed_name_alone_is_not_used_for_a_drained_need():
    recipe, result = plan_with(lambda r, _key: [{"name": drained(r).name, "quantity": drained(r).quantity, "unit": "g"}], index=3)
    assert result.personal.allocations == []
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)


def test_part_of_the_need_at_home_means_the_rest_is_bought():
    recipe, result = plan_with(lambda r, _key: [{"name": home(r).name, "quantity": home(r).quantity / 2, "unit": "g", "form": home(r).form}])
    assert [a["quantity"] for a in result.personal.allocations] == [home(recipe).quantity / 2]
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)


@pytest.mark.parametrize("name, unit", [("ris", "g"), ("gul lök", "g"), ("krossade tomater", "g")])
def test_the_unit_is_the_one_recipes_use(name, unit):
    use = usual_recipe_use(name)
    assert (use["unit"], use["used_in_recipes"]) == (unit, True)


def test_usable_counts_follow_the_planners_rule_for_named_rows():
    """Onion by name is enough for every recipe; chicken by name for none, since recipes ask for a cut."""
    onion, chicken, rice = (usual_recipe_use(n)["usable"] for n in ("gul lök", "kyckling", "ris"))
    assert onion[0] == onion[1] > 100
    assert chicken[0] == 0 and chicken[1] > 100
    assert 0 < rice[0] < rice[1] / 2
    chickpeas = usual_recipe_use("kikärtor")["usable"]
    assert chickpeas[2] > chickpeas[1] / 2 and chickpeas[0] <= chickpeas[1] - chickpeas[2]


def test_unknown_name_gets_no_proposal():
    assert usual_recipe_use("tandborste") == {"form": None, "unit": None, "used_in_recipes": False, "usable": [0, 0, 0]}


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
        assert (use["unit"], use["used_in_recipes"], use["food"]) == ("g", True, True)
        assert len(use["usable"]) == 3
        assert first.get("/api/personal/pantry-use", params={"name": " "}).status_code == 422
        row = {"id": "rice-1", "name": typed["query"], "quantity": typed["quantity"], "unit": typed["unit"],
               "product_key": None, "unusable": False, "food": True}
        saved = first.put("/api/personal/pantry", json={"revision": 0, "items": [row]})
        assert saved.status_code == 200
        item = saved.json()["items"][0]
        assert (item["name"], item["quantity"], item.get("form"), item["available"], item["reserved"]) == ("ris", 1000, None, 1000, 0)
        # The stale revision the interface would send after a change elsewhere is refused, not merged.
        assert first.put("/api/personal/pantry", json={"revision": 0, "items": []}).status_code == 409
        assert second.get("/api/personal/state").json()["items"] == []
    factory.kw["bind"].dispose()


def test_pantry_product_reports_the_drained_weight_the_planner_uses(monkeypatch, tmp_path):
    from app.api import account, personal, plan
    from fastapi.testclient import TestClient

    from backend.tests.test_privacy_erasure import _application

    application, factory, settings = _application(tmp_path)
    for module in (account, personal, plan):
        monkeypatch.setattr(module, "get_settings", lambda: settings)
    application.include_router(personal.router)
    personal.install_handlers(application)
    beans = product("bönor", 400, "g", 12).model_copy(update=can("bönor", 240))
    loose = product("Potatis", 1000, "g", 20)
    universe = prepared(beans, loose)
    monkeypatch.setattr(personal.GLOBAL_PREPARED_PRICE_UNIVERSES, "get_for_request", lambda *_: universe)
    monkeypatch.setattr("app.services.personal_source_facts.load_retained_facts", lambda _prepared: {})
    key = {universe.universe.products[positions[0]].name: k for k, positions in universe.product_search_index.groups.items()}
    with TestClient(application) as client:
        found = client.get("/api/personal/pantry-product", params={"product_key": key["Vita bönor"]}).json()
        assert (found["usable_quantity"], found["usable_unit"], found["package_quantity"], found["less_than_package"]) == (240, "g", 400, True)
        found = client.get("/api/personal/pantry-product", params={"product_key": key["Potatis"]}).json()
        assert (found["usable_quantity"], found["less_than_package"]) == (1000, False)
        assert client.get("/api/personal/pantry-product", params={"product_key": "x"}).status_code == 422
        assert client.get("/api/personal/pantry-product", params={"product_key": "0" * 32}).status_code == 404
    factory.kw["bind"].dispose()

