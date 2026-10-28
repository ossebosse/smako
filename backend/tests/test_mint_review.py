"""Trimmed mint is estimated, context-bound and never evidence for picked leaves."""
import copy
import json
from pathlib import Path

import pytest
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
from app.services.official_product_facts import project_usable_quantity
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver
from app.services.recipe_library import current_recipes

from backend.tests.test_personal_planning_v2 import product

KEY = 'intake_all_shape_trimmed_mint'
LEAF = 'intake_all_3f61df003596'


@pytest.fixture
def mint(monkeypatch):
    registry = copy.deepcopy(links.entries())
    proof = registry[KEY]['reviewed_links'][0]
    proof.pop('composition_sha256', None)
    registry[KEY]['reviewed_links'] = [proof]
    p = product(proof['name'], 25, 'g', 20, identity=proof['product_id'], store=proof['store_id']).model_copy(update={
        'category': proof['category'], 'brand': proof['brand'], 'gtin': proof.get('gtin'),
        'source_provenance': SourceProvenance.model_validate({**proof['source_provenance'],
            'retailer_product_id': proof['retailer_product_id']})})
    monkeypatch.setattr(links, 'entries', lambda: registry)
    links._quantity_reviews.cache_clear()
    yield registry, proof, p
    links._quantity_reviews.cache_clear()


def test_mint_yield_rounding_preserves_price_and_leaf_only_boundary(mint):
    registry, _proof, p = mint
    assert project_usable_quantity(p, None, required_unit='g') is p
    q = project_usable_quantity(p, None, allow_estimates=True, required_unit='g')
    assert q.package_quantity == 25 and q.usable_quantity == 21.25
    assert q.quantity_confidence == 'estimated' and q.source_provenance == p.source_provenance
    assert links.ingredient_product('mynta', 'raw_edible', registry[KEY]['requirements'], q)
    assert not links.compatible(LEAF, q)
    assert not links.compatible(KEY, p)
    checkout = PurchaseQuantityResolver().resolve(q, required_quantity=25, required_unit='g')
    assert checkout.packages_needed == 2 and checkout.purchased_quantity == 50
    assert checkout.purchased_usable_quantity == 42.5 and checkout.total_price == 40


@pytest.mark.parametrize('update', [
    {'package_quantity': 429}, {'package_unit': 'st'}, {'name': 'Mynta Burk'},
    {'name': 'Kattmynta'}, {'store_id': 'unreviewed-physical-store'}, {'gtin': 'other'},
])
def test_mint_estimate_cannot_cross_product_or_store_boundary(mint, update):
    _registry, _proof, p = mint
    changed = p.model_copy(update=update)
    assert project_usable_quantity(changed, None, allow_estimates=True, required_unit='g') is changed


def test_real_mint_links_share_cited_population_record_and_keep_coop_online_scope():
    reference = json.loads((ROOT.parent / 'nutrition/mint-yield-20261027.json').read_bytes())
    row = links.entries()[KEY]
    for proof in row['reviewed_links']:
        q = proof['quantity']
        assert q['source'] == reference['source']
        assert q['source']['record']['food_id'] == '06.259'
        assert q['edible_fraction'] == q['source']['record']['edible_percent'] / 100 == 0.85
        assert q['usable_quantity'] == proof['package_quantity'] * 0.85 == 21.25
        assert q['confidence'] == 'estimated'
        if proof.get('gtin') == '7300156599834':
            assert proof['source_provenance']['provider_store_id'] == '730400'
            assert proof['source_provenance']['price_context'] == 'online_fulfillment'
    assert not links.entries()[LEAF].get('reviewed_links')


def test_mint_recipe_review_preserves_history_quantities_and_leaf_recipes():
    review = json.loads((ROOT.parents[3] / 'docs/reviews/recipe-four-staples-20261027/recipe-review.json').read_bytes())
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries([*manifest['current'], *manifest['history']], ROOT)}
    active = {identity(r): r for r in current_recipes()}
    egg = json.loads((ROOT.parents[3] / 'docs/reviews/egg-preparation-20261028/recipe-review.json').read_bytes())
    successors = {r['previous_id']: r['runtime_id'] for r in egg['corrected']}
    assert len(active) == 2462 and len(review['corrected']) == 91 and len(review['verified_unchanged']) == 40
    for row in review['corrected']:
        before, after = issued[row['previous_id']], issued[row['runtime_id']]
        assert successors.get(row['runtime_id'], row['runtime_id']) in active
        assert row['previous_id'] not in active
        assert before.design.content_sha256 == row['before_content_sha256']
        assert after.design.content_sha256 == row['content_sha256']
        assert [(i.canonical_name, i.quantity, i.unit, i.form) for i in before.ingredients] == [
            (i.canonical_name, i.quantity, i.unit, i.form) for i in after.ingredients]
        assert after.design.active_minutes == before.design.active_minutes + 1
    for row in review['verified_unchanged']:
        recipe = issued[row['runtime_id']]
        assert successors.get(row['runtime_id'], row['runtime_id']) in active
        assert recipe.design.content_sha256 == row['content_sha256']
        assert all('pack:' + LEAF in i.product_requirements for i in recipe.ingredients if i.canonical_name == 'mynta')


def test_comparison_allows_only_hash_bound_reviewed_successors(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    import coverage_reference as reference

    path = tmp_path / 'review.json'
    path.write_text(json.dumps({'before_manifest_file_sha256': 'before', 'after_manifest_file_sha256': 'after',
                               'corrected': [{'previous_id': 'old', 'runtime_id': 'new'}]}))
    monkeypatch.setattr(reference, 'MINT_REVIEW', path)
    scope = {'manifest_sha256': 'before', 'recipe_ids_sha256': reference.digest(['old', 'kept'])}
    compared = {'manifest_sha256': 'after', 'recipe_ids_sha256': reference.digest(['new', 'kept'])}
    rows = [{'current_id': 'old'}, {'current_id': 'kept'}]
    assert reference.reviewed_recipe_transition(scope, compared, rows) == ['new', 'kept']
    for changed in ({**compared, 'manifest_sha256': 'unreviewed'},
                    {**compared, 'recipe_ids_sha256': reference.digest(['new', 'unreviewed'])}):
        with pytest.raises(ValueError, match='unreviewed'):
            reference.reviewed_recipe_transition(scope, changed, rows)


def test_delivery_price_gate_cannot_be_overridden_by_more_recipe_coverage(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    from verify_full_coverage_delivery import benchmark_price_regression

    assert benchmark_price_regression('A', {'total': 283.24}, {'total': 295.41})
    assert benchmark_price_regression('A', {'total': 280}, {'total': 283.24})
    assert benchmark_price_regression('A', {'total': 283.24}, {'total': 283.24}) is None
    assert benchmark_price_regression('B2', {'total': 731.20, 'items': ['old']},
                                      {'total': 731.20, 'items': ['changed']})
    assert benchmark_price_regression('B2', {'total': 731.20}, {'total': 731.20}) is None
