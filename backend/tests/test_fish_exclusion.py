"""A fish preference excludes fish species; it never certifies allergen absence."""

from types import SimpleNamespace

import pytest
from app.models.personal import TasteProfile
from app.models.recipe import Recipe, RecipeIngredient
from app.services.diet_policy import recipe_respects_diet
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product


def evidence(**updates):
    return ProductFacts(source="retained:test", source_product_id="p", source_snapshot_id="s",
                        **updates)


@pytest.mark.parametrize("name", ["lax", "torsk", "tonfisk", "sej"])
def test_fish_exclusion_covers_recipe_species(name):
    recipe = Recipe(name="Middag", servings=4,
                    ingredients=[RecipeIngredient(name=name, quantity=600, unit="g")],
                    instructions=["Tillaga."])
    assert not recipe_respects_diet(recipe, preference="mixed", avoid_ingredients=["fisk"])
    assert recipe_respects_diet(recipe, preference="mixed")


@pytest.mark.parametrize("name,canonical,family", [
    ("Laxfilé", "lax", "fish"), ("Sejfilé", "sej", "fish"),
    ("Produkt med exakt fiskklassning", "okänd", "fish"),
])
def test_fish_exclusion_checks_product_classification(name, canonical, family):
    product = SimpleNamespace(name=name, canonical_name=canonical, food_family=family)
    with pytest.raises(PolicyConflict, match="hårda val"):
        check_product(product, TasteProfile(exclusions=["fisk"]), evidence(ingredients_complete=True))


def test_positive_species_in_compound_declaration_is_a_conflict():
    product = SimpleNamespace(name="Fylld pasta", canonical_name="pasta")
    with pytest.raises(PolicyConflict, match="produktdeklarationen"):
        check_product(product, TasteProfile(exclusions=["fisk"]),
                      evidence(ingredients_complete=True, ingredients=("Durumvete, lax (20 %), salt",)))


def test_unknown_ingredients_and_allergens_stay_blocked():
    product = SimpleNamespace(name="Naturell tofu", canonical_name="tofu", food_family="tofu")
    with pytest.raises(PolicyConflict) as error:
        check_product(product, TasteProfile(exclusions=["fisk"]), evidence())
    assert error.value.code == "DATA_BLOCKED"
    with pytest.raises(PolicyConflict) as error:
        check_product(product, TasteProfile(allergies=["fisk"]), evidence(ingredients_complete=True))
    assert error.value.code == "DATA_BLOCKED"
    check_product(product, TasteProfile(exclusions=["fisk"]), evidence(ingredients_complete=True))


def test_excluding_one_species_does_not_expand_to_all_fish():
    product = SimpleNamespace(name="Laxfilé", canonical_name="lax", food_family="fish")
    check_product(product, TasteProfile(exclusions=["torsk"]), evidence(ingredients_complete=True))
