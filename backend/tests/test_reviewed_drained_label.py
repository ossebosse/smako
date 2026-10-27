"""Exact declared contents retain gross purchase and source/context boundaries."""
import copy
from dataclasses import replace

import pytest
from app.models.product import QuantityConfidence, SaleModel
from app.services import intake_product_links as links
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_policy import ProductFacts
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from backend.tests.test_personal_planning_v2 import product


@pytest.fixture
def reviewed(monkeypatch, request):
    registry = copy.deepcopy(links.entries())
    key = next(k for k, r in registry.items() if r['name'] == getattr(request, 'param', 'vattenkastanjer'))
    row = registry[key]
    proof = row['reviewed_links'][0]
    p = product(proof['name'], proof['package_quantity'], 'g', 20, identity=proof['product_id'], store=proof['store_id']).model_copy(
        update={**{k: proof[k] for k in ('gtin', 'brand', 'category', 'sale_model')},
                'sale_model': SaleModel(proof['sale_model']),
                'source_provenance': product_provenance(proof), 'quantity_confidence': QuantityConfidence.DERIVED})
    f = ProductFacts(source=proof['quantity']['source']['url'], source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id,
        ingredients=(proof['quantity']['declared_ingredients'],), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration', field_sources={'usable_quantity': (
            {'basis': 'drained', 'unit': 'g', 'quantity': proof['quantity']['usable_quantity'], 'source': proof['quantity']['source']['url']},)})
    assert links.composition_signature(f) == proof['composition_sha256']
    monkeypatch.setattr(links, 'entries', lambda: registry)
    links._quantity_reviews.cache_clear()
    yield key, proof, p, f
    links._quantity_reviews.cache_clear()


def product_provenance(proof):
    from app.models.provenance import SourceProvenance
    return SourceProvenance.model_validate(proof['source_provenance'])


@pytest.mark.parametrize('reviewed', ['vattenkastanjer', 'bambuskott'], indirect=True)
def test_declared_drained_mass_is_exact_without_estimate_consent_and_rounds_gross_packs(reviewed):
    key, _proof, p, f = reviewed
    before = p.model_dump_json()
    q = project_usable_quantity(p, f, required_unit='g')
    assert q.package_quantity == p.package_quantity and q.usable_quantity == _proof['quantity']['usable_quantity']
    assert q.quantity_confidence == 'exact'
    assert links.compatible(key, q, f)
    quote = PurchaseQuantityResolver().resolve(q, required_quantity=q.usable_quantity + 10, required_unit='g')
    assert quote.packages_needed == 2 and quote.purchased_quantity == 2*p.package_quantity
    assert quote.purchased_usable_quantity == 2*q.usable_quantity and quote.total_price == 40
    assert q.source_provenance == p.source_provenance and p.model_dump_json() == before
    assert not f.nutrition and f.organic is None and not f.allergens_checked


@pytest.mark.parametrize('changed', [
    {'store_id': 'other'}, {'gtin': 'other'}, {'name': 'Water Chestnut Whole'},
    {'brand': 'Other'}, {'package_quantity': 410}, {'package_unit': 'ml'},
])
def test_exact_label_does_not_cross_product_package_or_store(reviewed, changed):
    _key, _proof, p, f = reviewed
    altered = p.model_copy(update=changed)
    assert project_usable_quantity(altered, f, required_unit='g') is altered


@pytest.mark.parametrize('changed', [
    {'usable_quantity': True}, {'usable_quantity': 0}, {'usable_quantity': 221},
    {'declared_net_quantity': 221}, {'basis': 'raw_edible'}, {'confidence': 'estimated'},
    {'source': {}}, {'label_source': {}},
])
def test_only_the_declared_drained_quantity_and_supported_source_kind_can_project(reviewed, changed):
    _key, proof, p, f = reviewed
    proof['quantity'].update(changed)
    assert project_usable_quantity(p, f, required_unit='g') is p


def test_quantity_conflicts_and_changed_composition_still_block_the_label(reviewed):
    _key, _proof, p, f = reviewed
    for altered in [replace(f, conflicts=('nutrition.package_quantity',)),
                    replace(f, ingredients=('Different formula',)),
                    replace(f, source_product_id='other')]:
        assert project_usable_quantity(p, altered, required_unit='g') is p


def test_known_nutrient_conflict_does_not_invent_or_approve_nutrition(reviewed):
    _key, _proof, p, f = reviewed
    conflict = replace(f, conflicts=('supplier_nutrition_conflict',))
    assert project_usable_quantity(p, conflict, required_unit='g').usable_quantity == 140
    assert not conflict.nutrition and conflict.conflicts == ('supplier_nutrition_conflict',)


def test_actual_authored_drained_form_requires_the_bound_quantity_fact_as_well_as_identity(reviewed):
    from app.services.complete_recipes import product_form_compatible
    from app.services.recipe_library import current_recipes

    _key, _proof, p, f = reviewed
    recipe = next(r for r in current_recipes() if any(i.name == 'vattenkastanjer' for i in r.ingredients))
    q = project_usable_quantity(p, f, required_unit='g')
    assert product_form_compatible(recipe, 'vattenkastanjer', q, f)
    assert not product_form_compatible(recipe, 'vattenkastanjer', q, replace(f, field_sources={}))
