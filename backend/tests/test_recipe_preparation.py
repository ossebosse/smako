"""Input method boundaries; no synthetic case is a live-source proof."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.personal_nutrition import calculation_basis
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.recipe_preparation import (
    OIL,
    adapt,
    content_hash,
    input_evidence,
    pantry_evidence,
    validate,
)


def original():
    return Recipe(
        name="Testad tofupanna",
        servings=2,
        ingredients=[
            RecipeIngredient(name="tofu", quantity=300, unit="g"),
            RecipeIngredient(name="ris", quantity=160, unit="g"),
        ],
        instructions=["Stek i lite olja."],
    )


@pytest.mark.parametrize(
    "family", [f for f in OIL if not f.endswith("toast") and f != "egg_tomato"]
)
def test_designed_versions_validate_preserve_original_and_explicit_oil(family):
    old = original()
    saved = old.model_dump_json()
    new = adapt(old, family)
    assert old.model_dump_json() == saved
    assert new.preparation.parent_sha256 == content_hash(old)
    assert validate(new)
    oil = next((i for i in new.ingredients if i.name == "rapsolja"), None)
    assert (oil.quantity if oil else 0) == 2 * OIL[family]
    basis = calculation_basis(new, allow_estimates=True)
    assert basis["per_100g_cooked"] == "NOT_AVAILABLE"
    assert basis["retention_factors"] == "NOT_MEASURED"
    assert Recipe.model_validate_json(new.model_dump_json()) == new
    with pytest.raises(PolicyConflict):
        calculation_basis(new, allow_estimates=False)
    with pytest.raises(PolicyConflict):
        calculation_basis(old, allow_estimates=True)


@pytest.mark.parametrize("change", ["instructions", "oil", "form", "unit", "ingredient"])
def test_metadata_cannot_approve_changed_recipe(change):
    r = adapt(original(), "panna")
    if change == "instructions":
        r = r.model_copy(update={"instructions": ["Stek och häll bort oljan."]})
    if change == "oil":
        r = r.model_copy(update={"ingredients": r.ingredients[:-1]})
    if change == "form":
        r = r.model_copy(
            update={
                "preparation": r.preparation.model_copy(
                    update={"input_forms": {"tofu": "dry", "ris": "dry", "rapsolja": "as_sold"}}
                )
            }
        )
    if change == "unit":
        r = r.model_copy(
            update={
                "ingredients": [
                    r.ingredients[0].model_copy(update={"unit": "st"}),
                    *r.ingredients[1:],
                ]
            }
        )
    if change == "ingredient":
        r = r.model_copy(
            update={
                "ingredients": [
                    r.ingredients[0].model_copy(update={"name": "korv"}),
                    *r.ingredients[1:],
                ]
            }
        )
    with pytest.raises(PolicyConflict):
        calculation_basis(r, allow_estimates=True)


def fact(unit="g"):
    return ProductFacts(
        source="verified-test-declaration",
        source_product_id="food",
        source_snapshot_id="snapshot",
        nutrition_unit=unit,
        nutrition_basis="per 100 " + unit,
        nutrition={"protein_g": 15.0, "fat_g": 8.0},
        field_sources={"nutrition.protein_g": ({"source": "test", "observed_at": "2026-09-01"},)},
    )


def test_used_grams_do_not_require_cooked_or_package_mass_and_stay_estimated():
    r = adapt(original(), "panna")
    f = fact()
    p = SimpleNamespace(name="Tofu Naturell Fast", usable_quantity=None)
    e = input_evidence(r, p, "tofu", "g", True, f)
    assert e.nutrition == f.nutrition and e.evidence_kind == "recipe_design_input_estimate"
    assert e.field_sources["nutrition.protein_g"][0]["observed_at"] == "2026-09-01"
    assert e.field_sources["nutrition.protein_g"][-1]["cooked_quantity_g"] is None
    assert input_evidence(r, p, "tofu", "ml", True, f) is None
    assert input_evidence(r, p, "tofu", "g", False, replace(f, conflicts=("nutrition",))) is None


def test_volume_declaration_is_used_directly_no_density():
    r = adapt(original(), "panna")
    f = fact("ml")
    p = SimpleNamespace(name="Rapsolja")
    assert input_evidence(r, p, "rapsolja", "ml", True, f).nutrition_unit == "ml"
    assert input_evidence(r, p, "rapsolja", "ml", False, fact("g")) is None


def test_drained_food_needs_explicit_both_purchase_and_nutrition_basis():
    old = original().model_copy(
        update={
            "ingredients": [
                RecipeIngredient(name="kikärtor", quantity=120, unit="g"),
                RecipeIngredient(name="bröd", quantity=80, unit="g"),
                RecipeIngredient(name="tomat", quantity=80, unit="g"),
            ]
        }
    )
    r = adapt(old, "chickpea_toast")
    p = SimpleNamespace(name="Kikärtor", usable_quantity=230)
    assert input_evidence(r, p, "kikärtor", "g", True, fact()) is None
    f = replace(
        fact(),
        nutrition_preparation="cooked_drained",
        field_sources={
            **fact().field_sources,
            "usable_quantity": (
                {"basis": "drained", "quantity": 230, "unit": "g", "source": "official-test"},
            ),
        },
    )
    assert input_evidence(r, p, "kikärtor", "g", False, f)
    assert (
        input_evidence(
            r, SimpleNamespace(name="Kikärtor", usable_quantity=380), "kikärtor", "g", False, f
        )
        is None
    )
    assert pantry_evidence(r, "kikärtor", 3815)
    assert pantry_evidence(r, "kikärtor", 881) is None
    generic = replace(
        f, nutrition={}, ingredients=("Ingredienser: Ekologiska kikärtor, vatten, salt.",)
    )
    result = input_evidence(r, p, "kikärtor", "g", False, generic)
    assert result and result.source != f.source
    assert (
        result.field_sources["nutrition.protein_g"][-1]["input_evidence_kind"]
        == "generic_reference"
    )
    assert (
        input_evidence(
            r, p, "kikärtor", "g", False, replace(generic, ingredients=("Kikärtor, olja, kryddor",))
        )
        is None
    )


def test_dry_input_cannot_use_cooked_declaration():
    r = adapt(original(), "panna")
    p = SimpleNamespace(name="Ris kokt")
    assert input_evidence(r, p, "ris", "g", True, fact()) is None


def test_old_recipe_json_shape_is_unchanged():
    assert "preparation" not in original().model_dump()


def test_complete_canned_declaration_does_not_qualify_raw_tomato_input():
    old = original().model_copy(
        update={"ingredients": [RecipeIngredient(name="tomat", quantity=200, unit="g")]}
    )
    recipe = adapt(old, "gryta")
    assert (
        input_evidence(
            recipe, SimpleNamespace(name="Körsbärstomater hela"), "tomat", "g", True, fact()
        )
        is None
    )
    assert input_evidence(recipe, SimpleNamespace(name="Tomater"), "tomat", "g", True, fact())


def test_egg_carton_mass_is_not_edible_mass_or_piece_conversion():
    old = original().model_copy(
        update={"ingredients": [RecipeIngredient(name="ägg", quantity=2, unit="st")]}
    )
    recipe = adapt(old, "panna")
    assert (
        input_evidence(
            recipe,
            SimpleNamespace(name="Ägg 12-pack M/L", usable_quantity=636),
            "ägg",
            "g",
            True,
            fact(),
        )
        is None
    )
    assert input_evidence(
        recipe,
        SimpleNamespace(name="Flytande hela ägg", usable_quantity=1000),
        "ägg",
        "g",
        True,
        fact(),
    )
