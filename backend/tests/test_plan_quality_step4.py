"""Step 4: plans that feel reasonable (owner decisions 2026-11-15, docs/PLANNING-ARCHITECTURE.md)."""
from typing import get_args

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import (
    MealSettings,
    MealSlot,
    PersonalMutation,
    PersonalPlanning,
    PortionLimits,
    Staple,
    TasteProfile,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import (
    LIKE_MISSING_KR,
    TASTE_WEIGHT_KR,
    mixed_week_ok,
    preference_score,
)
from app.services.staples import STAPLES, reference_identity
from pydantic import ValidationError

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
    """Owner decisions 2026-11-15 and 2026-11-22: meat or chicken in about half of the dinners."""
    from app.services.personal_policy import animal_dinners_needed

    kinds = {"veg": "vegetarian", "kyckling": "chicken", "lax": "fish", "korv": "meat"}
    classify = lambda r: kinds[r.name]
    week = lambda *names: [dish(n, "x") for n in names]
    assert [animal_dinners_needed(n) for n in range(1, 8)] == [1, 1, 1, 2, 2, 3, 3]
    ok = lambda names, n, partial=False: mixed_week_ok(week(*names), n, partial=partial, classify=classify,
                                                       meat_needed=animal_dinners_needed(n))
    assert not ok(["veg", "veg", "veg"], 3)
    assert not ok(["korv", "kyckling"], 2)
    assert ok(["veg", "korv", "veg"], 3)
    # Fish is welcome but is not a meat dinner.
    assert not ok(["lax", "veg"], 2)
    assert not ok(["korv", "lax", "veg", "veg", "veg"], 5)
    assert ok(["korv", "kyckling", "lax", "veg", "veg"], 5)
    assert not ok(["korv", "kyckling", "veg", "veg", "veg", "veg", "lax"], 7)
    assert ok(["korv", "kyckling", "korv", "veg", "veg", "veg", "lax"], 7)
    assert ok(["korv"], 1) and not ok(["veg"], 1)
    # A partial week passes while the remaining places can still mix it.
    assert ok(["veg", "veg"], 3, partial=True)
    assert not ok(["veg", "veg", "veg"], 4, partial=True)
    assert ok(["veg", "veg"], 4, partial=True)


def test_kott_is_not_only_pork():
    """Owner report 2026-11-22: "Kött" gave only pork."""
    from app.services.personal_policy import meat_kind, meat_kind_cap, meat_kinds_ok

    meats = {"Fläskgryta": "fläskkött", "Korvstroganoff": "falukorv", "Kycklinggryta": "kyckling",
             "Köttbullar": "nötfärs", "Lammfärsbiffar": "lammfärs", "Lasagne": "blandfärs", "Leverbiff": "kycklinglever"}
    classify = lambda r: "chicken" if meats[r.name] == "kyckling" else "meat"
    kinds = {name: meat_kind(dish(name, meat), classify) for name, meat in meats.items()}
    assert kinds == {"Fläskgryta": "fläsk", "Korvstroganoff": "fläsk", "Kycklinggryta": "fågel", "Köttbullar": "nöt",
                     "Lammfärsbiffar": "lamm", "Lasagne": "blandfärs", "Leverbiff": "fågel"}
    assert [meat_kind_cap(n) for n in range(2, 8)] == [1, 2, 2, 3, 3, 4]
    week = lambda *names: [dish(n, meats[n]) for n in names]
    assert not meat_kinds_ok(week("Fläskgryta", "Korvstroganoff"), cap=1, classify=classify)
    assert meat_kinds_ok(week("Fläskgryta", "Köttbullar", "Korvstroganoff"), cap=2, classify=classify)
    assert not meat_kinds_ok(week("Fläskgryta", "Korvstroganoff", "Fläskgryta"), cap=2, classify=classify)


def test_fish_and_vegetarian_has_fish_dinners():
    """Owner decisions 2026-11-17 and 2026-11-22: about half of the dinners are fish."""
    from app.services.personal_policy import fish_dinners_needed, fish_week_ok

    kinds = {"veg": "vegetarian", "lax": "fish", "räkor": "shellfish"}
    classify = lambda r: kinds[r.name]
    week = lambda *names: [dish(n, "x") for n in names]
    assert [fish_dinners_needed(n) for n in range(1, 8)] == [1, 1, 1, 2, 2, 3, 3]
    assert not fish_week_ok(week("veg", "veg"), 2, partial=False, classify=classify)
    assert fish_week_ok(week("veg", "lax", "veg"), 3, partial=False, classify=classify)
    assert not fish_week_ok(week("veg", "lax", "veg", "veg"), 4, partial=False, classify=classify)
    assert fish_week_ok(week("räkor", "lax", "veg", "veg", "veg"), 5, partial=False, classify=classify)
    assert not fish_week_ok(week("räkor", "lax", "veg", "veg", "veg", "veg"), 6, partial=False, classify=classify)
    # A partial week passes while the remaining places can still hold the fish.
    assert fish_week_ok(week("veg", "veg"), 4, partial=True, classify=classify)
    assert not fish_week_ok(week("veg", "veg", "veg"), 4, partial=True, classify=classify)
    # Fewer fish dishes in the library than wanted: as many as there are.
    assert fish_week_ok(week("lax", "veg", "veg", "veg"), 4, partial=False, classify=classify, needed=1)


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


def test_a_week_without_a_required_like_ranks_as_much_dearer():
    spec = PersonalPlanning(profile=TasteProfile(likes=["kyckling"]), meals=[MealSettings(count=2, servings=2)])
    p = PersonalPlanner(PlanRequest(recipes=2, servings=2, personal=spec), Settings(),
                        prepared(product("salt", 1000, "g", 8)), state(), facts={}, now=NOW)
    p._required_likes = ("kyckling",)
    chicken = MealSlot(id="a", day=1, meal_type="dinner", recipe=dish("Kycklinggryta", "kycklingfilé"))
    lentils = MealSlot(id="b", day=2, meal_type="dinner", recipe=dish("Linssoppa", "linser"))
    assert p._preference_cost([chicken, lentils]) == -TASTE_WEIGHT_KR
    assert p._preference_cost([lentils]) == LIKE_MISSING_KR
    assert LIKE_MISSING_KR >= 1000


def test_the_cheaper_recipe_preview_is_only_for_replacing_one_dinner():
    PersonalMutation(revision=1, pantry_revision=0, action="replace", slot_id="d", preview_without_like="kyckling")
    for wrong in ({"action": "remove", "slot_id": "d"}, {"action": "replace"},
                  {"action": "replace", "slot_id": "d", "recipe_id": "x:1:a"}):
        with pytest.raises(ValidationError):
            PersonalMutation(revision=1, pantry_revision=0, preview_without_like="kyckling", **wrong)


def test_oil_at_home_gets_nutrition_from_reviewed_reference_and_density():
    from app.services.staples import volume_evidence

    oil = volume_evidence("rapsolja", "ml")
    assert oil is not None and oil.nutrition_unit == "ml" and oil.evidence_kind == "food_specific_density_estimate"
    assert 800 < oil.nutrition["kcal"] < 840  # About 900 kcal per 100 g x 0.92 g/ml.
    assert volume_evidence("rapsolja", "g") is None and volume_evidence("olivolja", "ml") is None


def test_the_week_without_likes_ranks_as_if_nothing_were_liked():
    spec = PersonalPlanning(profile=TasteProfile(likes=["kyckling"], dislikes=["svamp"]),
                            meals=[MealSettings(count=2, servings=2)])
    p = PersonalPlanner(PlanRequest(recipes=2, servings=2, personal=spec), Settings(),
                        prepared(product("salt", 1000, "g", 8)), state(), facts={}, now=NOW)
    p._required_likes = ("kyckling",)
    lentils = MealSlot(id="b", day=2, meal_type="dinner", recipe=dish("Linssoppa med svamp", "linser", "svamp"))
    p._ignore_likes = True
    assert p._preference_cost([lentils]) == TASTE_WEIGHT_KR  # The dislike still counts; no missing like.
    p._ignore_likes = False
    assert p._preference_cost([lentils]) == TASTE_WEIGHT_KR + LIKE_MISSING_KR


def test_several_recipes_are_switched_in_one_change():
    PersonalMutation(revision=1, pantry_revision=0, action="replace", recipe_ids={"d1": "a:1:x", "d2": "b:1:x"})
    for wrong in ({"action": "remove"}, {"action": "replace", "slot_id": "d1"}, {"action": "replace", "recipe_id": "a:1:x"}):
        with pytest.raises(ValidationError):
            PersonalMutation(revision=1, pantry_revision=0, recipe_ids={"d1": "a:1:x"}, **wrong)
