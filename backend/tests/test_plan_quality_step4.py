"""Step 4: plans that feel reasonable (owner decisions 2026-11-15, docs/PLANNING-ARCHITECTURE.md)."""
from typing import get_args

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import (
    MealSettings,
    MealSlot,
    PersonalPlanning,
    PortionLimits,
    Staple,
    TasteProfile,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import TASTE_WEIGHT_KR, mixed_week_ok, preference_score
from app.services.staples import STAPLES, reference_identity

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, run, state


def dish(name, *ingredients):
    return Recipe(name=name, servings=2, instructions=["Laga."],
                  ingredients=[RecipeIngredient(name=n, quantity=100, unit="g") for n in ingredients])


def test_likes_count_for_every_recipe_and_inside_compound_words():
    likes = TasteProfile(likes=["kyckling"])
    one = dish("Pasta med kycklingfilé", "kycklingfilé", "pasta")
    two = dish("Kycklinggryta", "kyckling", "ris")
    none = dish("Linssoppa", "linser", "morot")
    assert preference_score([one], likes) == -1
    assert preference_score([one, two, none], likes) == -2
    assert preference_score([none], likes) == 0
    assert preference_score([dish("Kycklingfri gryta", "bönor")], likes) == 0
    assert preference_score([two], TasteProfile(dislikes=["ris"])) == 1
    assert TASTE_WEIGHT_KR == 15


def test_allt_means_a_mixed_week_of_dinners():
    kinds = {"veg": "vegetarian", "kyckling": "chicken", "lax": "fish", "korv": "meat"}
    classify = lambda r: kinds[r.name]
    week = lambda *names: [dish(n, "x") for n in names]
    assert not mixed_week_ok(week("veg", "veg", "veg"), 3, partial=False, classify=classify)
    assert not mixed_week_ok(week("korv", "kyckling"), 2, partial=False, classify=classify)
    assert mixed_week_ok(week("veg", "korv", "veg"), 3, partial=False, classify=classify)
    assert mixed_week_ok(week("lax", "veg"), 2, partial=False, classify=classify)
    # A partial week passes while the remaining places can still mix it.
    assert mixed_week_ok(week("veg", "veg"), 3, partial=True, classify=classify)
    assert mixed_week_ok(week("veg", "veg", "veg"), 4, partial=True, classify=classify)
    assert not mixed_week_ok(week("veg"), 1, partial=True, classify=classify)


def test_an_extra_store_must_save_at_least_ten_kronor():
    def plan(ica_bread):
        p = prepared(product("mjölk", 1000, "ml", 15), product("bröd", 500, "g", 25),
                     product("bröd", 500, "g", ica_bread, identity="bröd-ica", store="ica"))
        slots = [MealSlot(id="d", day=1, meal_type="dinner", recipe=Recipe(
            name="Mjölk och bröd", servings=1, instructions=["Servera."],
            ingredients=[RecipeIngredient(name="mjölk", quantity=200, unit="ml"),
                         RecipeIngredient(name="bröd", quantity=80, unit="g")]))]
        return run(p, request(slots=slots, meals=[MealSettings(count=1, servings=1)])).optimized_basket
    small = plan(18)  # ICA saves 7 kr: not worth the trip.
    assert small.store_count == 1 and small.total == 40 and small.max_stores == 2
    large = plan(14)  # ICA saves 11 kr.
    assert large.store_count == 2 and large.total == 29


def _staple_plan(**personal):
    p = prepared(product("mjölk", 1000, "ml", 15), product("bröd", 500, "g", 25), product("salt", 1000, "g", 8))
    meal = personal.pop("meal", MealSettings(count=1, servings=1))
    slots = [MealSlot(id="d", day=1, meal_type="dinner", recipe=Recipe(
        name="Bröd med salt", servings=1, instructions=["Servera."],
        ingredients=[RecipeIngredient(name="mjölk", quantity=200, unit="ml"),
                     RecipeIngredient(name="bröd", quantity=80, unit="g"),
                     RecipeIngredient(name="salt", quantity=2, unit="g")]))]
    return run(p, request(slots=slots, meals=[meal], **personal))


def _bought(result):
    return {i.ingredient.split(" [")[0] for s in result.optimized_basket.stores for i in s.items}


def test_staples_at_home_are_not_bought_and_are_listed():
    plain = _staple_plan()
    assert "salt" in _bought(plain) and not plain.personal.at_home
    home = _staple_plan(staples_at_home=["salt"])
    assert "salt" not in _bought(home) and home.optimized_basket.total == plain.optimized_basket.total - 8
    assert home.personal.at_home == [{"name": "salt", "quantity": 2, "unit": "g", "sources": ["d"]}]
    assert not any(r["name"] == "salt" for r in home.personal.remaining_demands)


def test_staples_are_still_bought_where_they_must_be_checked():
    spec = PersonalPlanning(meals=[MealSettings(count=1, servings=1)], staples_at_home=["salt", "rapsolja"])
    p = PersonalPlanner(PlanRequest(recipes=1, servings=2, personal=spec),
                        Settings(), prepared(product("salt", 1000, "g", 8)), state(), facts={}, now=NOW)
    meal, food = MealSettings(count=1, servings=1), dish("Gryta", "salt")

    def row(name="salt", **change):
        return {"name": name, "profile": TasteProfile(), "product_key": None, "properties": [], **change}
    assert p._at_home(row(), meal, food)
    assert p._at_home(row("Rapsolja"), meal, food)
    assert not p._at_home(row("svartpeppar"), meal, food)  # Not ticked.
    assert not p._at_home(row(), meal, None)  # An own extra row is bought as asked.
    assert not p._at_home(row(profile=TasteProfile(allergies=["gluten"])), meal, food)
    assert not p._at_home(row(product_key="a" * 32), meal, food)
    assert not p._at_home(row(), MealSettings(count=1, servings=1, limits=PortionLimits(max_kcal=600)), food)


def test_staple_vocabulary_matches_the_request_model_and_references():
    assert set(STAPLES) == set(get_args(Staple))
    assert reference_identity("salt", "g") == "slv:1975:ready"
    assert reference_identity("rapsolja", "ml") is None  # The reviewed reference is per gram.
