"""Explicit alternatives keep source scope, old identities and edible mass separate."""
import json
import re
from collections import Counter
from dataclasses import replace
from functools import lru_cache
from pathlib import Path

import pytest
from app.models import Product
from app.models.personal import TasteProfile
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.complete_recipes import product_form_compatible
from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
from app.services.personal_policy import PolicyConflict, ProductFacts, check_product
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver
from app.services.recipe_library import _scaled, current_recipes, validate_recipe_design
from app.services.recipe_preparation import input_evidence

REPORT = ROOT.parents[3] / 'docs/reviews/top-five-ingredients-20261028'
SOURCES = json.loads((REPORT / 'source-declarations.json').read_bytes())['sources']


def source_fixture(slug, proof):
    source = SOURCES[slug]
    p = Product(product_id=proof['product_id'], store_id=proof['store_id'], store_name='Exact source test fixture',
        name=proof['name'], canonical_name=source['name'], brand=proof['brand'], category=proof['category'],
        gtin=proof['gtin'], chain=proof['source_provenance']['chain'], price=10,
        package_quantity=source['pack'], package_unit=source['unit'],
        usable_quantity=source['pack'], usable_unit=source['unit'],
        quantity_confidence='exact', semantic_confidence='exact',
        source_provenance=SourceProvenance.model_validate(proof['source_provenance']))
    fact = ProductFacts(source='synthetic exact declaration', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id=proof['retailer_product_id'],
        ingredients=tuple(source['ingredients']), ingredients_complete=bool(source['ingredients']),
        ingredient_evidence_kind='product_declaration' if source['ingredients'] else 'unknown')
    return p, fact


@pytest.fixture(params=list(SOURCES))
def reviewed(request):
    slug = request.param
    key = 'intake_all_shape_top5_' + slug
    row = links.entries()[key]
    p, fact = source_fixture(slug, row['reviewed_links'][0])
    return key, row, p, fact


@lru_cache(maxsize=1)
def recipes():
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries([*manifest['current'], *manifest['history']], ROOT)}
    active = {identity(r): r for r in current_recipes()}
    return json.loads((REPORT / 'recipe-review.json').read_bytes()), issued, active


def test_every_exact_existing_context_qualifies_without_any_new_price():
    review, issued, active = recipes()
    count = 0
    for slug, source in SOURCES.items():
        key = 'intake_all_shape_top5_' + slug
        row = links.entries()[key]
        transition = next(t for t in review['corrected'] if source['group'] in t['groups'])
        new, old = active[transition['runtime_id']], issued[transition['previous_id']]
        for proof in row['reviewed_links']:
            p, fact = source_fixture(slug, proof)
            assert links.compatible(key, p, fact)
            assert product_form_compatible(new, source['name'], p, fact)
            assert not product_form_compatible(old, source['group'], p, fact)
            quote = PurchaseQuantityResolver().resolve(p, required_quantity=source['pack'] + 1,
                                                       required_unit=source['unit'])
            assert quote.resolved and quote.packages_needed == 2 and quote.total_price == 20
            assert quote.purchased_quantity == quote.purchased_usable_quantity == 2 * source['pack']
            assert quote.quantity_confidence == 'exact'
            assert fact.nutrition == {} and fact.animal is fact.organic is None
            assert not fact.allergens_checked
            count += 1
    assert count == 24


@pytest.mark.parametrize('changed', [
    {'name': 'Unreviewed food'}, {'brand': 'Other'}, {'gtin': 'other'},
    {'store_id': 'unreviewed-store'}, {'package_quantity': 123}, {'package_unit': 'st'},
    {'usable_quantity': 123}, {'quantity_confidence': 'estimated'}, {'source_provenance': None},
])
def test_review_cannot_cross_identity_quantity_or_store_boundaries(reviewed, changed):
    key, _row, p, fact = reviewed
    assert not links.compatible(key, p.model_copy(update=changed), fact)


def test_composition_and_source_conflicts_are_not_personal_approval(reviewed):
    key, row, p, fact = reviewed
    assert not links.compatible(key, p, replace(fact, ingredients=('Unreviewed mixture',)))
    assert not links.compatible(key, p, replace(fact, source_snapshot_id='unreviewed'))
    assert not links.compatible(key, p, replace(fact, conflicts=('quantity.unknown',)))
    assert links.compatible(key, p, replace(fact, conflicts=('supplier_nutrition_conflict',)))
    with pytest.raises(PolicyConflict):
        check_product(p, TasteProfile(allergies=['mjölk']), fact)
    assert not links.ingredient_product(row['name'], 'cooked_drained', row['requirements'], p, fact)


def test_tamarind_volume_never_acquires_a_gram_conversion():
    row = links.entries()['intake_all_shape_top5_tamarind_concentrate']
    p, fact = source_fixture('tamarind_concentrate', row['reviewed_links'][0])
    quote = PurchaseQuantityResolver().resolve(p, required_quantity=20, required_unit='ml')
    assert quote.resolved and quote.purchased_quantity == 435
    assert not PurchaseQuantityResolver().resolve(p, required_quantity=20, required_unit='g').resolved
    assert not links.ingredient_product('tamarindpasta', 'as_sold', row['requirements'], p, fact)


def test_successors_preserve_all_originals_other_ingredients_safety_and_scaling():
    review, issued, active = recipes()
    assert len(active) == 2727 and len(review['corrected']) == 192
    assert Counter(g for t in review['corrected'] for g in t['groups']) == {
        'tamarindpasta': 93, 'masa harina': 31, 'pärlkorn': 27, 'citrongräs': 27, 'klibbigt ris': 20}
    for t in review['corrected']:
        old, new = issued[t['previous_id']], active[t['runtime_id']]
        assert t['previous_id'] not in active
        assert old.design.content_sha256 == t['before_content_sha256']
        assert new.design.content_sha256 == t['content_sha256']
        assert new.design.provenance.cooking_test == 'not_cooked'
        assert new.servings == old.servings and new.design.ingredient_count == old.design.ingredient_count
        assert (new.design.vegetarian, new.design.fish) == (old.design.vegetarian, old.design.fish)
        assert len(new.ingredients) == len(old.ingredients)
        assert set(re.findall(r'\d+ °C', ' '.join(old.instructions))) <= set(re.findall(r'\d+ °C', ' '.join(new.instructions)))
        for before, after in zip(old.ingredients, new.ingredients, strict=True):
            if before.canonical_name not in t['groups']:
                assert before == after
        for servings in (1, 4, 12):
            scaled = _scaled(new, servings)
            assert validate_recipe_design(scaled)
            for food in scaled.ingredients:
                if food.canonical_name == 'tamarindkoncentrat':
                    components = [a for c in scaled.design.components for a in c.amounts
                                  if a.ingredient_key == 'tamarindkoncentrat|as_sold']
                    assert all(a.quantity == 5 * servings and a.unit == 'ml' for a in components)
                    assert food.quantity == sum(a.quantity for a in components) and food.unit == 'ml'
                    # The extended mung dish has both an onion side and a separate gravy.
                    assert len(components) == (2 if new.design.base_id ==
                        'smako-indian-cooked-sprout-gravy-crisp-chickpea-bread'
                        and new.design.variant_id == 'extended' else 1)
                if food.canonical_name == 'citrongräs':
                    assert food.quantity == 12.5 * servings and food.form == 'as_sold'
                    assert links.gross_purchase_input(scaled, 'citrongräs')
                    assert input_evidence(scaled, None, 'citrongräs', 'g', None, None) is None


def test_rice_and_grain_methods_are_actual_cooking_changes():
    review, _issued, active = recipes()
    for t in review['corrected']:
        new = active[t['runtime_id']]
        text = ' '.join(new.instructions)
        if 'klibbigt ris' in t['groups']:
            assert 'TORRA risvolymen' in text and '15 minuter' in text
            assert not any(s.duration_minutes in (237, 240, 357) for s in new.design.steps)
            assert not any(i.canonical_name == 'klibbigt ris' for i in new.ingredients)
            assert 'klibbigt ris' not in new.name.casefold()
        if 'pärlkorn' in t['groups']:
            assert '13–15 minuter' in text and 'durkslag' in text
            assert 'pärlkorn' not in text and 'vätskan absorberad' not in text
        if 'masa harina' in t['groups']:
            assert 'förkokt majsmjöl' in new.name
            assert 'masa harina' not in text


def test_all_original_coverage_identities_follow_the_reviewed_transition(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    from coverage_reference import digest, file_sha, imported_recipes, reviewed_recipe_transition

    prior = json.loads((REPORT.parent / 'whole-corn-20261028/coverage.json').read_bytes())
    refs, current = imported_recipes()
    scope = {**prior['scope'], 'manifest_sha256': file_sha(ROOT / 'library-manifest.json'),
             'recipe_ids_sha256': digest([identity(r) for r in current])}
    assert refs == [r['original_id'] for r in prior['variants']]
    assert reviewed_recipe_transition(prior['scope'], scope, prior['variants']) == [identity(r) for r in current]
    with pytest.raises(ValueError, match='unreviewed'):
        reviewed_recipe_transition(prior['scope'], {**scope, 'manifest_sha256': 'unknown'}, prior['variants'])
