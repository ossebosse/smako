"""Exact pod/pectin reviews cannot clear a different food or edible basis."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.complete_recipes import product_form_compatible
from app.services.personal_policy import ProductFacts
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver
from app.services.recipe_library import current_recipes

from backend.tests.test_personal_planning_v2 import product


def reviewed(name):
    key, row = next((k, r) for k, r in links.entries().items() if r['name'] == name and r['form'] == 'as_sold')
    proof = row['reviewed_links'][0]
    p = product(proof['name'], proof['package_quantity'], 'g', 20,
        identity=proof['product_id'], store=proof['store_id']).model_copy(update={
            'brand': proof['brand'], 'category': proof['category'], 'gtin': proof.get('gtin'),
            'source_provenance': SourceProvenance.model_validate(proof['source_provenance'])})
    f = ProductFacts(source=proof['quantity']['source']['url'], source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id=proof['retailer_product_id'],
        ingredients=(proof['quantity']['declared_ingredients'],), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration')
    return key, row, p, f


@pytest.mark.parametrize('name,other', [('edamame i balja', 'sojabönor')])
def test_exact_plain_review_preserves_checkout_and_authored_food(name, other):
    key, row, p, f = reviewed(name)
    assert links.compatible(key, p, f)
    recipe = next(r for r in current_recipes() if any(row['requirements'][0] in (i.product_requirements or ()) for i in r.ingredients))
    assert product_form_compatible(recipe, name, p, f)
    quote = PurchaseQuantityResolver().resolve(p, required_quantity=p.package_quantity + 1, required_unit='g')
    assert quote.packages_needed == 2 and quote.purchased_quantity == 2 * p.package_quantity
    assert quote.total_price == 40
    assert not links.ingredient_product(other, 'as_sold', row['requirements'], p, f)
    assert not links.ingredient_product(name, 'raw_edible', row['requirements'], p, f)
    assert links.gross_purchase_input(recipe, name) == (name == 'edamame i balja')
    assert not f.nutrition and not f.allergens_checked and f.organic is None


@pytest.mark.parametrize('name', ['edamame i balja'])
@pytest.mark.parametrize('changed', [
    {'name': 'Sojabönor utan balja'}, {'brand': 'another brand'},
    {'package_quantity': 1}, {'gtin': 'unreviewed'}, {'store_id': 'another context'},
])
def test_plain_review_cannot_cross_label_package_identity_or_context(name, changed):
    key, _row, p, f = reviewed(name)
    assert not links.compatible(key, p.model_copy(update=changed), f)


@pytest.mark.parametrize('name', ['edamame i balja'])
def test_plain_review_requires_current_complete_composition_and_bound_fact(name):
    key, _row, p, f = reviewed(name)
    assert not links.compatible(key, p, replace(f, ingredients=('socker, pektin',)))
    assert not links.compatible(key, p, replace(f, ingredients_complete=False))
    assert not links.compatible(key, p, replace(f, source_snapshot_id='unreviewed'))
    assert not links.compatible(key, p, replace(f, conflicts=('nutrition.package_quantity',)))
    # An unresolved nutrient discrepancy cannot become food identity approval.
    assert links.compatible(key, p, replace(f, conflicts=('supplier_nutrition_conflict',)))


def test_no_gtin_pod_rows_keep_the_exact_retained_article_and_context_gate():
    key, row = next((k, r) for k, r in links.entries().items() if r['name'] == 'edamame i balja')
    proof = next(p for p in row['reviewed_links'] if p.get('gtin') is None)
    assert proof['retailer_product_id'] == '101328931_ST'
    p = product(proof['name'], 500, 'g', 20, identity=proof['product_id'], store=proof['store_id']).model_copy(update={
        'brand': proof['brand'], 'category': proof['category'], 'gtin': None,
        'source_provenance': SourceProvenance.model_validate(proof['source_provenance'])})
    f = ProductFacts(source='retained exact article', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id='101328931_ST',
        ingredients=(proof['quantity']['declared_ingredients'],), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration')
    assert links.compatible(key, p, f)
    assert not links.compatible(key, p, replace(f, retailer_product_id='a-shelled-bean-article'))


def test_plain_citrus_pectin_does_not_clear_yellow_high_methoxyl_confectionery():
    key, row = next((k, r) for k, r in links.entries().items() if r['name'] == 'pektin')
    authored = Path(__file__).parents[1] / 'app/data/recipes/incoming/authoring-800-20261025/paket/smako-recept-paket-152.json'
    recipes = json.loads(authored.read_bytes())['recipes'][:2]
    assert all('gult högmetoxylerat pektin avsett för fast fruktkonfekt' in r['steps'][0]['text'] for r in recipes)
    assert 'högmetoxylerat' in row['definition']
    p = product('Pektinpulver', 10, 'g', 20).model_copy(update={'brand': 'ATAIR', 'gtin': '7350053730205'})
    f = ProductFacts(source='exact ordinary pectin declaration', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id, retailer_product_id='101243514_ST',
        ingredients=('Pektin E440. Framställt av citrusfrukter.',), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration')
    assert not links.compatible(key, p, f)


def test_pod_gross_grams_cannot_become_edible_bean_nutrition():
    from app.services.recipe_preparation import input_evidence

    _key, row, p, f = reviewed('edamame i balja')
    recipe = next(r for r in current_recipes() if any(row['requirements'][0] in (i.product_requirements or ()) for i in r.ingredients))
    f = replace(f, nutrition={'protein_g': 11, 'kcal': 130}, nutrition_unit='g', nutrition_basis='per_100_g')
    assert input_evidence(recipe, p, 'edamame i balja', 'g', True, f) is None
