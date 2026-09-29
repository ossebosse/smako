"""Supplier quantities and raw-food identity remain independent of prices."""

import pytest
from app.services.nutrition_reference import product_reference
from app.services.official_product_facts import project_usable_quantity, supplement_catalog_facts

from backend.tests.test_personal_planning_v2 import product
from backend.tests.test_personal_qualified_facts import facts


def cream(**changes):
    return product(
        "Lätt Crème Fraiche 13%", 200, "ml", 17, gtin="7310867003841", brand="Skånemejerier"
    ).model_copy(update=changes)


def test_exact_supplier_mass_reaches_purchase_projection_without_repricing():
    p = cream()
    key = (p.store_id, p.product_id)
    f = supplement_catalog_facts([p], {})[key]
    projected = project_usable_quantity(p, f, required_unit="g")
    assert (projected.usable_quantity, projected.usable_unit) == (200, "g")
    assert projected.price == p.price and projected.source_provenance == p.source_provenance
    assert f.nutrition["protein_g"] == 2.9
    assert f.field_sources["usable_quantity"][0]["document_version"] == "2026-02-09"
    assert project_usable_quantity(p, f, required_unit="ml") == p
    for changed in (
        p.model_copy(update={"product_id": "other"}),
        p.model_copy(update={"store_id": "other"}),
    ):
        assert project_usable_quantity(changed, f, required_unit="g") == changed


@pytest.mark.parametrize(
    "changes",
    [{"brand": "Other"}, {"package_quantity": 500}, {"gtin": "7310867523868"}, {"gtin": None}],
)
def test_same_name_never_grants_another_variant_mass(changes):
    p = cream(**changes)
    f = supplement_catalog_facts([p], {}).get((p.store_id, p.product_id))
    assert project_usable_quantity(p, f, required_unit="g") == p


def test_supplier_conflict_is_preserved_and_never_replaced_by_generic_values():
    p = cream()
    prior = facts(p, nutrition={"protein_g": 99}, nutrition_unit="g", nutrition_basis="per 100 g")
    f = supplement_catalog_facts([p], {(p.store_id, p.product_id): prior})[
        (p.store_id, p.product_id)
    ]
    assert f.nutrition == prior.nutrition
    assert "supplier_nutrition_conflict" in f.conflicts
    assert not f.allergens_checked


@pytest.mark.parametrize(
    "name,category,composition,ingredient,expected",
    [
        ("Potatis Fast Tvättad", "Frukt & grönt > Potatis", [], "potatis", 4457),
        ("Minipotatis Italienska kryddor", "Potatis", ["Potatis, olja, kryddor"], "potatis", None),
        ("Vitlök Finhackad", "Kryddor R - Ö", ["Vitlök"], "vitlök", None),
        ("Vitost Tärnad Vitlök & persilja", "Fetaost", ["Ost, vitlök"], "vitlök", None),
        ("Vitlök", "Frukt & grönsaker > Lök", [], "vitlök", 371),
        ("Vitlök hackad", "Grönsaker", ["Vitlök 95%, olja"], "vitlök", None),
    ],
)
def test_raw_input_needs_compatible_form_even_with_product_nutrition(
    name, category, composition, ingredient, expected
):
    p = product(name, 100, "g", 10).model_copy(update={"category": category})
    f = facts(p, ingredients=tuple(composition), nutrition={"protein_g": 17}, nutrition_unit="g")
    assert product_reference(p, ingredient, f) == expected
