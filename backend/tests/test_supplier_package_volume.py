"""Explicit supplier volume is bound to one mass-labelled retail package."""
from dataclasses import replace

import pytest
from app.services.official_product_facts import (
    facts_for_quantity_unit,
    project_usable_quantity,
    supplement_catalog_facts,
)
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from backend.tests.test_personal_planning_v2 import product


def kefir():
    p = product('Kefir Naturell', 1000, 'g', 30, brand='Skånemejerier', gtin='7310867511407')
    f = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    return p, f


def test_declared_volume_buys_whole_packages_and_preserves_mass_nutrition():
    p, f = kefir()
    before = p.model_dump_json()
    projected = project_usable_quantity(p, f, required_unit='ml')
    assert (projected.package_quantity, projected.package_unit) == (1000, 'g')
    assert (projected.usable_quantity, projected.usable_unit) == (1000, 'ml')
    purchase = PurchaseQuantityResolver().resolve(projected, required_quantity=1100, required_unit='ml')
    assert purchase.packages_needed == 2 and purchase.total_price == 60
    assert purchase.purchased_usable_quantity == 2000
    assert project_usable_quantity(p, f, required_unit='g') is p
    assert f.nutrition_unit == 'g'
    for current in [p, projected]:
        volume_fact = facts_for_quantity_unit(current, f, 'ml')
        assert volume_fact.nutrition_unit == 'ml'
        assert volume_fact.nutrition == f.nutrition
    assert p.model_dump_json() == before


@pytest.mark.parametrize('field,value', [
    ('bound_product_id', 'other'), ('bound_store_id', 'other'), ('bound_snapshot_id', 'other'),
    ('source_package_quantity', 900), ('source_package_unit', 'ml'), ('sha256', ''),
    ('unit', 'g'), ('quantity', -1), ('quantity', True), ('quantity', float('nan')),
])
def test_volume_and_nutrients_reject_changed_binding_even_on_a_projected_copy(field, value):
    p, f = kefir()
    projected = project_usable_quantity(p, f, required_unit='ml')
    proof = {**f.field_sources['usable_quantity'][0], field: value}
    changed = replace(f, field_sources={**f.field_sources, 'usable_quantity': (proof,)})
    assert project_usable_quantity(p, changed, required_unit='ml') is p
    assert facts_for_quantity_unit(projected, changed, 'ml') is changed


@pytest.mark.parametrize('conflict', ['nutrition.package_quantity', 'usable_quantity', 'unknown'])
def test_volume_conflicts_fail_closed(conflict):
    p, f = kefir()
    changed = replace(f, conflicts=(conflict,))
    assert project_usable_quantity(p, changed, required_unit='ml') is p
    assert facts_for_quantity_unit(p, changed, 'ml') is changed


def test_nutrient_conflict_keeps_independent_quantity_but_not_volume_nutrition():
    p, f = kefir()
    changed = replace(f, conflicts=('nutrition.kcal',))
    assert project_usable_quantity(p, changed, required_unit='ml').usable_unit == 'ml'
    assert facts_for_quantity_unit(p, changed, 'ml') is changed
    without = replace(f, field_sources={k: v for k, v in f.field_sources.items() if k != 'usable_quantity'})
    assert project_usable_quantity(p, without, required_unit='ml') is p
    assert facts_for_quantity_unit(p, without, 'ml') is without


def test_volume_nutrition_uses_declared_ratio_and_never_water_density():
    p, f = kefir()
    proof = {**f.field_sources['usable_quantity'][0], 'quantity': 800}
    changed = replace(f, field_sources={**f.field_sources, 'usable_quantity': (proof,)})
    volume = facts_for_quantity_unit(p, changed, 'ml')
    assert volume.nutrition == {k: v*1.25 for k, v in f.nutrition.items()}
    assert project_usable_quantity(p, changed, required_unit='ml').usable_quantity == 800


def test_counted_gelatin_package_uses_exact_variant_net_mass():
    p = product('Gelatinblad', 12, 'st', 12.5, brand='DR. OETKER', gtin='5701073066478')
    f = supplement_catalog_facts([p], {})[(p.store_id, p.product_id)]
    projected = project_usable_quantity(p, f, required_unit='g')
    assert (projected.package_quantity, projected.package_unit) == (12, 'st')
    assert (projected.usable_quantity, projected.usable_unit) == (20, 'g')
    purchase = PurchaseQuantityResolver().resolve(projected, required_quantity=21, required_unit='g')
    assert purchase.packages_needed == 2 and purchase.total_price == 25
    assert not f.ingredients_complete and not f.nutrition
