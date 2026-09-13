from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from app.models.personal import TasteProfile
from app.services.nutrition_reference import product_reference
from app.services.personal_nutrition import calculation_basis
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product
from app.services.recipe_profile import RecipeProfileBuilder
from app.services.reviewed_ingredients import enrich_ingredients, reviews
from app.services.reviewed_warm_meals import candidates, evidence, preparation


def fact(**changes):
    return ProductFacts(
        source="synthetic", source_product_id="p", source_snapshot_id="s", **changes
    )


@pytest.mark.parametrize(
    "ingredient",
    [
        "fiskbuljong",
        "fisksås",
        "sardellpasta",
        "bonitoflingor",
        "ANSJOVIS",
        "laxextrakt",
        "tonfisk",
    ],
)
def test_compound_fish_positive_does_not_require_complete_data(ingredient):
    with pytest.raises(PolicyConflict, match="produktdeklarationen"):
        check_product(
            SimpleNamespace(name="Sås", canonical_name="sås"),
            TasteProfile(exclusions=["fisk"]),
            fact(ingredients=(f"Vatten, {ingredient}, salt",)),
        )


def test_ingredient_choice_and_allergy_trace_are_separate():
    product = SimpleNamespace(name="Pasta", canonical_name="pasta")
    source = fact(
        ingredients_complete=True, ingredients=("Durumvete. Kan innehålla spår av fisk.",)
    )
    check_product(product, TasteProfile(exclusions=["fisk"]), source)
    with pytest.raises(PolicyConflict):
        check_product(product, TasteProfile(allergies=["fisk"]), source)
    with pytest.raises(PolicyConflict) as error:
        check_product(
            product, TasteProfile(allergies=["fisk"]), replace(source, ingredients=("Durumvete",))
        )
    assert error.value.code == "DATA_BLOCKED"


def test_irrelevant_missing_facts_cannot_determine_ingredient_presence():
    product = SimpleNamespace(name="Morot", canonical_name="morot")
    source = fact(
        ingredients_complete=True,
        ingredients=("morot",),
        conflicts=("nutrition_basis", "organic"),
        organic=None,
    )
    check_product(product, TasteProfile(exclusions=["fisk"]), source)
    with pytest.raises(PolicyConflict):
        check_product(
            product, TasteProfile(exclusions=["fisk"]), replace(source, ingredients_complete=False)
        )
    with pytest.raises(PolicyConflict):
        check_product(
            product, TasteProfile(exclusions=["fisk"]), replace(source, conflicts=("ingredients",))
        )


def test_new_recipe_ground_requires_opt_in_and_exact_preparation():
    for recipe in candidates():
        assert preparation(recipe)
        assert calculation_basis(recipe, allow_estimates=True)["cooked_weight"] == "NOT_VERIFIED"
        with pytest.raises(PolicyConflict):
            calculation_basis(recipe, allow_estimates=False)
        edited = recipe.model_copy(deep=True)
        edited.instructions.append("Häll av kokvätskan.")
        with pytest.raises(PolicyConflict):
            calculation_basis(edited, allow_estimates=True)
    assert len({RecipeProfileBuilder().build(r).cooking_method for r in candidates()}) == 4


def test_mapping_forms_are_not_interchangeable():
    def product(name):
        return SimpleNamespace(name=name)

    assert (
        product_reference(
            product("Röda linser"), "linser", fact(ingredients=("Torkade röda linser",))
        )
        == 884
    )
    assert (
        product_reference(
            product("Röda linser"), "linser", fact(ingredients=("Röda linser, vatten, salt",))
        )
        is None
    )
    assert (
        product_reference(product("Långkornigt Ris"), "ris", fact(ingredients=("Ris parboiled",)))
        is None
    )
    assert product_reference(product("Spaghetti"), "pasta", fact(ingredients=("Durumvete",))) == 845
    assert (
        product_reference(product("Spaghetti"), "pasta", fact(ingredients=("Röda linser",))) is None
    )
    assert evidence(884, candidates()[1]) is None


def test_reviewed_sources_remain_hashed_explicit_and_separate_from_allergy():
    rows = reviews()
    assert len(rows) == 25
    assert len([r for r in rows if r["chain"] == "willys"]) == 12
    for row in rows:
        assert row["sha256"] and row["observed_at"] and row["source"]
        if row["kind"] == "reviewed_single_unprocessed_crop":
            assert row["category"] and row["description"] and row["review_rationale"]


def test_review_enrichment_requires_exact_identity_package_and_recent_observation():
    row = next(r for r in reviews() if r["retailer_product_id"] == "101358420_ST")
    stamp = datetime.fromisoformat(row["observed_at"])
    fields = {
        "store_id": "willys",
        "product_id": "p",
        "chain": "willys",
        "name": row["name"],
        "package_quantity": 200,
        "package_unit": "g",
        "brand": row["brand"],
        "source_provenance": SimpleNamespace(source_observed_at=stamp),
    }
    source = fact(retailer_product_id=row["retailer_product_id"])

    def apply(changes=None, original=source):
        p = SimpleNamespace(**(fields | (changes or {})))
        return enrich_ingredients(
            SimpleNamespace(universe=SimpleNamespace(products=[p])), {("willys", "p"): original}
        )[("willys", "p")]

    result = apply()
    assert result.ingredients_complete and not result.allergens_checked
    for changes in (
        {"name": "Annan tofu"},
        {"package_quantity": 400},
        {"brand": "Annat märke"},
        {"source_provenance": SimpleNamespace(source_observed_at=stamp + timedelta(days=8))},
    ):
        assert not apply(changes).ingredients_complete
    assert not apply(original=replace(source, retailer_product_id="unknown")).ingredients_complete
    assert not apply(
        original=replace(source, ingredients=("Soja, fiskbuljong",))
    ).ingredients_complete
