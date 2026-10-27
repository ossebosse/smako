"""Identity, edible mass, consent and receipt dependency boundaries."""
import copy
from dataclasses import replace
from pathlib import Path

import pytest
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.axfood_product_details import explicit_drained_quantity
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_policy import ProductFacts
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from backend.tests.test_personal_planning_v2 import product


@pytest.fixture
def scallion(monkeypatch):
    key, row = next((k, copy.deepcopy(r)) for k, r in links.entries().items() if r['name'] == 'salladslök')
    proof = row['reviewed_links'][0]
    p = product(proof['name'], proof['package_quantity'], 'g', 20,
                identity=proof['product_id'], store=proof['store_id']).model_copy(update={
        'category': proof['category'], 'brand': proof['brand'], 'gtin': proof.get('gtin'),
        'source_provenance': SourceProvenance.model_validate(proof['source_provenance'])})
    row['reviewed_links'] = [proof]
    proof.pop('composition_sha256', None)
    monkeypatch.setattr(links, 'entries', lambda: {key: row})
    links._quantity_reviews.cache_clear()
    yield key, row, proof, p
    links._quantity_reviews.cache_clear()


def test_edible_yield_requires_consent_and_preserves_gross_package(scallion):
    key, row, _proof, p = scallion
    assert project_usable_quantity(p, None, required_unit='g') is p
    assert not links.compatible(key, p)
    projected = project_usable_quantity(p, None, allow_estimates=True, required_unit='g')
    assert projected.package_quantity == p.package_quantity == 100
    assert projected.usable_quantity == 96 and projected.quantity_confidence == 'estimated'
    assert p.usable_quantity == 100
    assert links.ingredient_product('salladslök', 'raw_edible', row['requirements'], projected)
    assert not links.ingredient_product('salladslök', 'cooked_drained', row['requirements'], projected)
    checkout = PurchaseQuantityResolver().resolve(projected, required_quantity=100, required_unit='g')
    assert checkout.packages_needed == 2 and checkout.purchased_quantity == 200
    assert checkout.purchased_usable_quantity == 192 and checkout.total_price == 40
    assert project_usable_quantity(p, None, allow_estimates=True, required_unit='ml') is p


@pytest.mark.parametrize('field,value', [('name', 'Salladslök sås'), ('category', 'Mejeri'),
    ('package_unit', 'st'), ('package_quantity', 200), ('brand', 'Other'), ('gtin', 'unreviewed'),
    ('sale_model', 'sold_by_weight')])
def test_changed_product_cannot_borrow_reviewed_yield(scallion, field, value):
    key, _row, _proof, p = scallion
    changed = p.model_copy(update={field: value})
    assert project_usable_quantity(changed, None, allow_estimates=True, required_unit='g') is changed
    assert not links.compatible(key, changed)


def test_missing_source_and_contradictory_composition_fail_closed(scallion):
    _key, _row, proof, p = scallion
    changed = p.model_copy(update={'source_provenance': None})
    assert project_usable_quantity(changed, None, allow_estimates=True, required_unit='g') is changed
    fact = ProductFacts(source='synthetic test', source_product_id=p.product_id,
                        source_snapshot_id=p.source_provenance.source_snapshot_id, ingredients=('Salt, salladslök',))
    assert project_usable_quantity(p, fact, allow_estimates=True, required_unit='g') is p
    proof['quantity']['source'].pop('sha256')
    assert project_usable_quantity(p, None, allow_estimates=True, required_unit='g') is p


def test_price_update_reuses_stable_article_but_rebinds_current_facts(scallion):
    key, _row, proof, p = scallion
    old = ProductFacts(source='old-catalogue', source_product_id=p.product_id,
                       source_snapshot_id=p.source_provenance.source_snapshot_id)
    proof['composition_sha256'] = links.composition_signature(old)
    fresh = p.model_copy(update={'product_id': 'new-price-row', 'price': 30,
        'source_provenance': p.source_provenance.model_copy(update={'source_snapshot_id': 'new-price-snapshot'})})
    facts = replace(old, source='new-catalogue', source_product_id=fresh.product_id,
                    source_snapshot_id=fresh.source_provenance.source_snapshot_id)
    assert links.composition_signature(old) == links.composition_signature(facts)
    projected = project_usable_quantity(fresh, facts, allow_estimates=True, required_unit='g')
    assert projected.usable_quantity == 96 and projected.price == 30
    assert projected.source_provenance.source_snapshot_id == 'new-price-snapshot'
    assert links.compatible(key, projected, facts)
    assert project_usable_quantity(fresh, old, allow_estimates=True, required_unit='g') is fresh
    changed = replace(facts, ingredients=('Salladslök, salt',))
    assert project_usable_quantity(fresh, changed, allow_estimates=True, required_unit='g') is fresh
    wrong_context = fresh.model_copy(update={'store_id': 'other-context'})
    assert project_usable_quantity(wrong_context, facts, allow_estimates=True, required_unit='g') is wrong_context


def drained_case():
    p = product('Kapris Medelstora', 120, 'g', 20, identity='synthetic-capers')
    raw = {'description': 'Medelstora kapris. 205 gram, avrunnen vikt 120 gram.',
           'displayVolume': '205/120g', 'code': 'synthetic-code'}
    provenance = {'binding': 'exact_retailer_article_code', 'document_chain': 'willys',
                  'document_url': 'https://example.invalid/synthetic-only', 'payload_sha256': 'f' * 64,
                  'fetched_at': '2026-10-27T00:00:00Z', 'validation_version': 'axfood-detail-evidence-v3'}
    proof = explicit_drained_quantity(p, raw, provenance)
    fact = ProductFacts(source='synthetic-only', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id=raw['code'],
        field_sources={'usable_quantity': (proof,)})
    return p, raw, provenance, fact


def test_explicit_drained_mass_keeps_purchased_mass_separate():
    p, _raw, _provenance, fact = drained_case()
    projected = project_usable_quantity(p, fact, required_unit='g')
    assert projected.package_quantity == 205 and projected.usable_quantity == 120
    checkout = PurchaseQuantityResolver().resolve(projected, required_quantity=125, required_unit='g')
    assert checkout.packages_needed == 2 and checkout.purchased_quantity == 410
    assert checkout.purchased_usable_quantity == 240 and checkout.waste_quantity == 115
    assert checkout.total_price == 40 and checkout.quantity_confidence == 'exact'
    assert project_usable_quantity(p, replace(fact, retailer_product_id='other'), required_unit='g') is p
    assert project_usable_quantity(p, replace(fact, conflicts=('usable_quantity',)), required_unit='g') is p


@pytest.mark.parametrize('update', [{'description': ''}, {'description': 42},
    {'displayVolume': '205g'}, {'displayVolume': '205/125g'},
    {'description': '100 gram, avrunnen vikt 120 gram.'},
    {'description': '205 gram, avrunnen vikt 120 gram. 205 gram, avrunnen vikt 120 gram.'}])
def test_ambiguous_or_contradictory_quantity_is_unknown(update):
    p, raw, provenance, _fact = drained_case()
    assert explicit_drained_quantity(p, {**raw, **update}, provenance) is None


def test_plain_dairy_and_english_juice_labels_remain_whole_foods():
    from types import SimpleNamespace

    from app.services.complete_recipes import _whole_food_identity, plain_juice_composition
    from app.services.reviewed_cold_meals import plain_quark

    p = product('Keso Naturell 4%', 250, 'g', 20, brand='Keso')
    assert _whole_food_identity('keso', 'as_sold', p, None)
    assert not _whole_food_identity('keso', 'as_sold', p.model_copy(update={'name': 'Keso Vanilj'}), None)
    f = SimpleNamespace(animal=True, ingredients=('MJÖLK, syrningskultur',), conflicts=(), nutrition_preparation='as_sold')
    q = product('Naturell Mild Kvarg 0,2%', 1000, 'g', 20)
    assert plain_quark(q, f)
    assert not plain_quark(q.model_copy(update={'name': 'Naturell Vanilj Kvarg'}), f)
    assert not plain_quark(q, SimpleNamespace(**{**vars(f), 'ingredients': ('Mjölk, socker',)}))
    assert plain_juice_composition('limejuice', 'Lime juice')
    assert not plain_juice_composition('limejuice', 'Lime juice, sugar')


def test_variable_source_pack_preserves_gross_rate_and_edible_rounding(scallion):
    key, _row, proof, p = scallion
    proof['sale_model'] = 'variable_weight_package'
    p = p.model_copy(update={'sale_model': 'variable_weight_package', 'sale_price': 100,
                            'sale_unit': 'kg', 'comparison_price': 100, 'comparison_unit': 'kg'})
    projected = project_usable_quantity(p, None, allow_estimates=True, required_unit='g')
    assert links.compatible(key, projected)
    checkout = PurchaseQuantityResolver().resolve(projected, required_quantity=100, required_unit='g')
    assert checkout.packages_needed == 2 and checkout.purchased_quantity == 200
    assert checkout.purchased_usable_quantity == 192 and checkout.total_price == 20
    assert checkout.quantity_confidence == 'estimated'


def test_reviewed_identity_does_not_supply_allergen_or_organic_facts(scallion):
    from app.models.personal import TasteProfile
    from app.services.personal_policy import PolicyConflict, check_product

    key, _row, _proof, p = scallion
    projected = project_usable_quantity(p, None, allow_estimates=True, required_unit='g')
    assert links.compatible(key, projected)
    with pytest.raises(PolicyConflict):
        check_product(projected, TasteProfile(allergies=['mjölk']), None)
    with pytest.raises(PolicyConflict):
        check_product(projected, TasteProfile(), None, organic_animals=True)


def test_receipt_invalidation_and_damage(tmp_path, monkeypatch):
    import sys

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    sys.modules.pop('check_recipe_coverage', None)
    from check_recipe_coverage import atomic_json, digest, read_receipt

    evidence = {'audit': {'passed': True}, 'basket': {'total': 20}}
    row = {'dependencies': 'scope-v1', 'status': 'verified', 'evidence': evidence, 'evidence_sha256': digest(evidence)}
    path = tmp_path / 'variant.json'
    atomic_json(path, row)
    assert read_receipt(path, 'scope-v1') == row
    assert read_receipt(path, 'changed-facts-price-clock-method-request-or-recipe') is None
    row['evidence']['basket']['total'] = 1
    atomic_json(path, row)
    assert read_receipt(path, 'scope-v1') is None


def test_verified_article_gtin_can_supply_supplier_identity_without_changing_product():
    from app.services.axfood_product_details import retained_article_identity
    from app.services.official_product_facts import (
        _retained_supplier_identity,
        _supplier_package_matches,
    )

    p = product('Tonfisk Vatten', 150, 'g', 20, brand='Abba', identity='test-tuna')
    fact = ProductFacts(source='test-catalog', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id='test-code')
    raw = {'name': p.name, 'manufacturer': p.brand, 'code': 'test-code',
           'ean': '7311171007013', 'displayVolume': '200/150g'}
    provenance = {'binding': 'exact_retailer_article_code', 'document_chain': 'willys',
                  'document_url': 'https://example.invalid/test-document', 'payload_sha256': 'f' * 64}
    identity = retained_article_identity(p, fact, raw, provenance)
    p = p.model_copy(update={'chain': 'willys', 'source_provenance': p.source_provenance.model_copy(update={'store_id': p.store_id})})
    enriched = replace(fact, field_sources={'retailer_detail_gtin': (identity,)})
    assert p.gtin is None
    assert _retained_supplier_identity(p, enriched) == identity
    row = {'package_quantity': 200, 'package_unit': 'g', 'net_quantity': 200, 'net_unit': 'g',
           'comparison_quantity': 150, 'comparison_unit': 'g', 'comparison_basis': 'Per avrunnen vikt'}
    assert _supplier_package_matches(p, row, identity)
    assert not _supplier_package_matches(p, {**row, 'comparison_quantity': 120}, identity)
    assert _retained_supplier_identity(p, replace(enriched, retailer_product_id='other')) is None
    assert retained_article_identity(p, fact, {**raw, 'manufacturer': 'Other'}, provenance) is None
    assert retained_article_identity(p, fact, {**raw, 'ean': 'invalid'}, provenance) is None


def test_fresh_potato_gnocchi_needs_potato_and_durum_shapes_stay_rejected():
    from app.services.complete_recipes import _requirements_compatible, _whole_food_identity
    from app.services.product_semantics import evaluate_product_semantics

    p = product('Gnocchi Färsk Pasta', 500, 'g', 20, brand='Eldorado')
    f = ProductFacts(source='test', source_product_id=p.product_id,
                    source_snapshot_id=p.source_provenance.source_snapshot_id, ingredients=('Potatispuré, vetemjöl, salt',))
    assert _whole_food_identity('gnocchi', 'as_sold', p, f)
    assert evaluate_product_semantics('gnocchi', p).compatible
    assert _requirements_compatible('gnocchi', ['pack:gnocchi'], p, f)
    assert not _requirements_compatible('gnocchi', ['pack:gnocchi'], p,
                                       replace(f, ingredients=('DURUMVETE',)))
    assert not _whole_food_identity('gnocchi', 'as_sold', p.model_copy(update={'name': 'Fylld Gnocchi Tomat Mozzarella'}), f)


def test_peanut_certification_note_is_not_an_extra_ingredient():
    from app.services.complete_recipes import plain_peanut_composition

    assert plain_peanut_composition('INGREDIENSER JORDNÖTTER* 99,7%, havssalt 0,3%. *Ekologisk ingrediens.')
    assert not plain_peanut_composition('Jordnötter*, kokosolja. *Ekologisk ingrediens.')


def test_each_real_yield_link_reproduces_its_cited_refuse_record():
    import json

    reference = json.loads((Path(__file__).parents[1] / 'app/data/nutrition/produce-yields-20261027.json').read_bytes())
    for row in links.entries().values():
        for proof in row.get('reviewed_links', ()):
            q = proof['quantity']
            assert row['kind'] == 'definition_only' and row['form'] == q['basis'] == 'raw_edible'
            assert q['confidence'] == 'estimated' and q['method'] == 'usda_sr28_refuse_v1'
            record = reference['records'][row['name']]
            assert q['source']['record'] == record
            assert q['source']['sha256'] == reference['source']['food_des_sha256']
            assert q['edible_fraction'] == round(1 - record['refuse_percent'] / 100, 8)
            assert q['usable_quantity'] == round(proof['package_quantity'] * q['edible_fraction'], 8)


@pytest.mark.parametrize('field', ['facts_sha256', 'universe_sha256', 'clock', 'method_signature', 'max_stores'])
def test_receipt_identity_changes_with_each_authoritative_dependency(monkeypatch, field):
    from app.models.recipe import Recipe, RecipeIngredient

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    from check_recipe_coverage import receipt_key

    recipe = Recipe(name='Synthetic recipe', servings=1,
                    ingredients=[RecipeIngredient(name='ris', quantity=100, unit='g')],
                    instructions=['Synthetic instructions.'])
    scope = {'facts_sha256': 'facts-v1', 'universe_sha256': 'prices-v1', 'clock': '2026-10-23',
             'method_signature': 'method-v1', 'max_stores': 2}
    first = receipt_key(scope, recipe, 'exact', 'checker-v1')
    assert first != receipt_key({**scope, field: 'changed'}, recipe, 'exact', 'checker-v1')
    assert first != receipt_key(scope, recipe, 'estimated', 'checker-v1')
    changed = recipe.model_copy(update={'ingredients': [recipe.ingredients[0].model_copy(update={'quantity': 200})]})
    assert first != receipt_key(scope, changed, 'exact', 'checker-v1')
