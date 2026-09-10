from __future__ import annotations

from app.models.recipe import Recipe, RecipeIngredient
from app.services.recipe_profile import RecipeProfileBuilder, build_recipe_profile


def recipe(
    name: str,
    ingredients: list[tuple[str, float, str]],
    instructions: list[str],
) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=canonical,
                canonical_name=canonical,
                quantity=quantity,
                unit=unit,
            )
            for canonical, quantity, unit in ingredients
        ],
        instructions=instructions,
    )


def test_profile_models_curry_structure_and_major_ingredients() -> None:
    profile = build_recipe_profile(
        recipe(
            "Linscurry med ris",
            [
                ("linser", 300, "g"),
                ("ris", 320, "g"),
                ("gul lök", 300, "g"),
                ("kokosmjölk", 400, "ml"),
                ("vitlök", 30, "g"),
            ],
            ["Fräs löken.", "Låt linser och kokosmjölk sjuda.", "Koka riset."],
        )
    )

    assert profile.recipe_family == "gryta"  # No curry seasoning is listed.
    assert profile.cooking_method == "simmer"
    assert profile.dish_form == "stew"
    assert profile.primary_protein == "linser"
    assert profile.primary_carb == "ris"
    assert profile.sauce_base == "kokosmjölk"
    assert profile.vegetables == ("gul lök",)
    assert set(profile.major_ingredients) == {
        "gul lök",
        "kokosmjölk",
        "linser",
        "ris",
    }
    assert "vitlök" not in profile.ingredient_weight_map


def test_profile_distinguishes_oven_tray_technique_and_form() -> None:
    profile = RecipeProfileBuilder().build(
        recipe(
            "Ugnsplåt med korv och potatis",
            [("korv", 500, "g"), ("potatis", 1200, "g"), ("morot", 500, "g")],
            ["Lägg allt på en plåt.", "Tillaga i ugn vid 225 grader."],
        )
    )

    assert profile.recipe_family == "ugn"
    assert profile.cooking_method == "oven"
    assert profile.dish_form == "oven_tray"
    assert profile.primary_protein == "korv"
    assert profile.primary_carb == "potatis"
    assert profile.sauce_base is None


def test_profile_uses_existing_alias_normalization() -> None:
    profile = build_recipe_profile(
        recipe(
            "Kycklingpasta",
            [
                ("kycklingfilé", 600, "g"),
                ("spaghetti", 400, "g"),
                ("morötter", 500, "g"),
            ],
            ["Stek kycklingen och koka pastan."],
        )
    )

    assert profile.primary_protein == "kyckling"
    assert profile.primary_carb == "pasta"
    assert profile.vegetables == ("morot",)
    assert {"kyckling", "morot", "pasta"} <= set(profile.major_ingredients)
