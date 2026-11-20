"""The meal choice "meat" keeps dishes built on meat or poultry and nothing else."""

import pytest
from app.models.personal import MealSettings
from app.models.recipe import Recipe, RecipeIngredient
from app.services.diet_policy import recipe_respects_diet
from pydantic import ValidationError


def recipe(*names):
    return Recipe(name="Middag", servings=4,
                  ingredients=[RecipeIngredient(name=n, quantity=100, unit="g") for n in names],
                  instructions=["Tillaga."])


@pytest.mark.parametrize("name", ["nötfärs", "fläskkött", "kyckling", "lammfärs", "bacon", "falukorv", "kalkon"])
def test_meat_keeps_beef_pork_poultry_and_other_meat(name):
    assert recipe_respects_diet(recipe("ris", name), preference="meat")


@pytest.mark.parametrize("names", [("lax",), ("räkor",), ("kikärtor",), ("ägg", "ost"), ("gelatin", "grädde"), ("lax", "bacon")])
def test_meat_leaves_out_fish_vegetarian_and_dishes_where_fish_is_the_main_part(names):
    assert not recipe_respects_diet(recipe("ris", *names), preference="meat")


def test_meat_still_honours_what_the_user_has_excluded():
    assert not recipe_respects_diet(recipe("ris", "fläskkött"), preference="meat", avoid_ingredients=["fläskkött"])
    assert recipe_respects_diet(recipe("ris", "nötfärs"), preference="meat", avoid_ingredients=["fläskkött"])


def test_meat_distribution_accepts_meat_and_chicken_and_rejects_the_rest():
    assert MealSettings(count=4, diet="meat", distribution={"meat": 2, "chicken": 1}).diet == "meat"
    for protein in ("fish", "vegetarian"):
        with pytest.raises(ValidationError, match="kött"):
            MealSettings(count=4, diet="meat", distribution={protein: 1})


def test_trial_interfaces_offer_meat_for_dinners_only():
    from pathlib import Path

    core = (Path(__file__).resolve().parents[1] / "app" / "static" / "next" / "core.js").read_text(encoding="utf-8")
    assert '["meat", "Kött"' in core
    assert 'saved.settings.diet === "meat" && type !== "dinner" ? "mixed" : saved.settings.diet' in core and "diet: mealDiet(type)" in core


# Owner report 2026-11-19: Kött with "Ät inte fläsk" gave a recipe with blodpudding.
@pytest.mark.parametrize("name", ["blodpudding", "bacon", "falukorv", "lufttorkad skinka", "blandfärs", "fläskfärs"])
def test_avoiding_pork_also_avoids_foods_made_of_pork(name):
    from app.services.personal_policy import mentions_avoided

    assert mentions_avoided("fläsk", name)


@pytest.mark.parametrize("name", ["nötfärs", "kycklingfilé", "korvbröd", "grissini", "pistagenötter"])
def test_avoiding_pork_keeps_what_is_not_pork(name):
    from app.services.personal_policy import mentions_avoided

    assert not mentions_avoided("fläsk", name)


def test_avoided_pork_product_is_stopped_on_its_name():
    from types import SimpleNamespace

    from app.models.personal import TasteProfile
    from app.services.personal_policy import PolicyConflict, check_product

    product = SimpleNamespace(name="Blodpudding Skivad 500g", canonical_name="blodpudding", category="Kött", food_family=None)
    with pytest.raises(PolicyConflict, match="fläsk"):
        check_product(product, TasteProfile(exclusions=["fläsk"]), None)


def test_distribution_only_offers_what_the_diet_allows():
    from pathlib import Path

    core = (Path(__file__).resolve().parents[1] / "app" / "static" / "next" / "core.js").read_text(encoding="utf-8")
    assert 'meat: ["chicken", "meat"], pescetarian: ["vegetarian", "fish"]' in core
    assert "for (const [key, name] of kinds)" in core
    assert "Kött ger bara rätter med kött eller kyckling" not in core
