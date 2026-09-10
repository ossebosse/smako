import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.ingredient_normalizer import (
    IngredientNormalizer,
    canonicalize_ingredient_name,
    normalize_quantity,
)


@pytest.mark.parametrize(
    ("quantity", "unit", "expected_quantity", "expected_unit"),
    [
        (1.2, "kg", 1200, "g"),
        (2, "l", 2000, "ml"),
        (3.5, "dl", 350, "ml"),
        (4, "cl", 40, "ml"),
        (6, "st", 6, "st"),
        (2, "pcs", 2, "st"),
    ],
)
def test_normalize_quantity(
    quantity: float, unit: str, expected_quantity: float, expected_unit: str
) -> None:
    assert normalize_quantity(quantity, unit) == (expected_quantity, expected_unit)


def test_aggregate_same_ingredient_across_recipes() -> None:
    recipes = [
        Recipe(
            name="Kycklingpasta",
            servings=4,
            ingredients=[RecipeIngredient(name="Kycklingfilé", quantity=0.6, unit="kg")],
            instructions=["Tillaga."],
        ),
        Recipe(
            name="Kycklinggryta",
            servings=4,
            ingredients=[RecipeIngredient(name="kyckling", quantity=700, unit="g")],
            instructions=["Koka."],
        ),
    ]

    ingredients = IngredientNormalizer().normalize_and_aggregate(recipes)

    assert len(ingredients) == 1
    assert ingredients[0].canonical_name == "kyckling"
    assert ingredients[0].required_quantity == 1300
    assert ingredients[0].unit == "g"
    assert ingredients[0].source_recipes == ["Kycklingpasta", "Kycklinggryta"]


def test_dimensionally_different_quantities_are_not_invented_or_merged() -> None:
    recipes = [
        Recipe(
            name="A",
            servings=4,
            ingredients=[RecipeIngredient(name="gul lök", quantity=2, unit="st")],
            instructions=["Laga."],
        ),
        Recipe(
            name="B",
            servings=4,
            ingredients=[RecipeIngredient(name="lök", quantity=300, unit="g")],
            instructions=["Laga."],
        ),
    ]

    ingredients = IngredientNormalizer().normalize_and_aggregate(recipes)

    assert [(row.required_quantity, row.unit) for row in ingredients] == [
        (2, "st"),
        (300, "g"),
    ]


def test_swedish_aliases_are_conservative() -> None:
    assert canonicalize_ingredient_name("Riven ost") == "ost"
    assert canonicalize_ingredient_name("Spaghetti") == "pasta"
    assert canonicalize_ingredient_name("Wok Mix Thai") == "frysta grönsaker"
    assert canonicalize_ingredient_name("Blandfärs") == "blandfärs"
    assert canonicalize_ingredient_name("Nötfärs") == "nötfärs"
    assert canonicalize_ingredient_name("margarin") != "smör"


@pytest.mark.parametrize(
    ("quantity", "unit"),
    [(0, "g"), (-1, "kg"), (1, "näve"), (float("nan"), "g")],
)
def test_invalid_quantity_or_unit_fails(quantity: float, unit: str) -> None:
    with pytest.raises(ValueError):
        normalize_quantity(quantity, unit)
