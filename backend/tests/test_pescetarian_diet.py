"""Pescetarian keeps fish and seafood but removes meat and poultry."""

import pytest
from app.models.personal import MealSettings
from app.models.recipe import Recipe, RecipeIngredient
from app.services.diet_policy import excluded_ingredients, recipe_respects_diet
from pydantic import ValidationError


def recipe(*names):
    return Recipe(name="Middag", servings=4,
                  ingredients=[RecipeIngredient(name=n, quantity=100, unit="g") for n in names],
                  instructions=["Tillaga."])


@pytest.mark.parametrize("name", ["lax", "torsk", "räkor", "musslor", "fisksås", "ägg", "ost"])
def test_pescetarian_allows_fish_seafood_and_vegetarian_food(name):
    assert recipe_respects_diet(recipe("ris", name), preference="pescetarian")


@pytest.mark.parametrize("name", ["kyckling", "nötfärs", "bacon", "fläskkött", "kalkon", "gelatin"])
def test_pescetarian_removes_meat_and_poultry(name):
    assert not recipe_respects_diet(recipe("ris", name), preference="pescetarian")


def test_pescetarian_sits_between_mixed_and_vegetarian():
    pescetarian = excluded_ingredients("pescetarian")
    assert "kyckling" in pescetarian and "lax" not in pescetarian
    assert pescetarian < excluded_ingredients("vegetarian")
    assert not recipe_respects_diet(recipe("lax"), preference="vegetarian")


def test_pescetarian_distribution_accepts_fish_and_rejects_meat():
    meal = MealSettings(count=4, diet="pescetarian", distribution={"fish": 2, "vegetarian": 1})
    assert meal.diet == "pescetarian"
    for protein in ("chicken", "meat"):
        with pytest.raises(ValidationError, match="Pescetarisk"):
            MealSettings(count=4, diet="pescetarian", distribution={protein: 1})
