"""Mass proofs stay independently bound when nutrient declarations disagree."""
from dataclasses import replace

import pytest
from app.services.official_product_facts import project_usable_quantity, supplement_catalog_facts

from backend.tests.test_personal_planning_v2 import product


def sourced_beans():
    p = product("Vita Bönor Stora", 480, "g", 19.95, brand="Zeta", gtin="7350027796831")
    f = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    return p, f


@pytest.mark.parametrize("conflict", [
    "supplier_nutrition_conflict", "nutrition_basis", "nutrition.energy", "nutrition.kcal",
    "nutrition.protein_g", "nutrition.carbs_g", "nutrition.fat_g",
])
def test_nutrient_disagreement_keeps_exact_drained_mass_and_conflict(conflict):
    p, f = sourced_beans()
    f = replace(f, conflicts=(conflict,))
    projected = project_usable_quantity(p, f, required_unit="g")
    assert projected.usable_quantity == 290
    assert projected.package_quantity == 480 and projected.price == p.price
    assert f.conflicts == (conflict,)


@pytest.mark.parametrize("conflict", [
    "usable_quantity", "package_quantity", "unknown_identity_conflict",
    "official_declaration_conflict", "nutrition_unknown", "nutrition.package_quantity",
])
def test_unknown_or_quantity_disagreement_blocks_even_with_nutrient_conflict(conflict):
    p, f = sourced_beans()
    f = replace(f, conflicts=("supplier_nutrition_conflict", conflict))
    assert project_usable_quantity(p, f) == p


@pytest.mark.parametrize("field,value", [
    ("bound_product_id", "other"), ("bound_store_id", "other"),
    ("bound_snapshot_id", "other"), ("source_package_quantity", 500),
    ("source_package_unit", "ml"), ("sha256", ""),
    ("quantity", True), ("quantity", float("nan")), ("quantity", -1),
])
def test_nutrient_conflict_never_relaxes_mass_proof_binding(field, value):
    p, f = sourced_beans()
    proof = {**f.field_sources["usable_quantity"][0], field: value}
    f = replace(f, conflicts=("supplier_nutrition_conflict",),
                field_sources={**f.field_sources, "usable_quantity": (proof,)})
    assert project_usable_quantity(p, f) == p


def test_multiple_quantity_proofs_stay_ambiguous_despite_nutrient_only_conflict():
    p, f = sourced_beans()
    proof = f.field_sources["usable_quantity"][0]
    f = replace(f, conflicts=("nutrition.kcal",), field_sources={
        **f.field_sources, "usable_quantity": (proof, {**proof, "quantity": 280}),
    })
    assert project_usable_quantity(p, f) == p
