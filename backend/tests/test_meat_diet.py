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
    assert 's.diet === "meat" && type !== "dinner" ? "mixed" : s.diet' in core
