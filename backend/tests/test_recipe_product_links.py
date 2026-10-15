"""Retained Willys products must resolve through the ordinary recipe planner."""
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest, Product, Store
from app.models.personal import TasteProfile
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import (
    _whole_food_identity,
    plain_juice_composition,
    product_form_compatible,
)
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.official_product_facts import project_usable_quantity, supplement_catalog_facts
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.personal_source_facts import project_raw_facts
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import PreparedPriceUniverse
from app.services.product_semantics import evaluate_product_semantics
from app.services.recipe_library import candidates

from backend.tests.test_personal_planning_v2 import state
from grocery_data.app.services.product_declarations import declarations, parse_zeinas_juice

ROWS = json.loads((Path(__file__).parent / 'fixtures/recipe_product_links.json').read_bytes())['rows']
CLOCK = datetime(2026, 10, 15, 12, tzinfo=UTC)


def prepared(product):
    key = PriceUniverseKey.create(city='Lund', postal_codes=['22225'],
        snapshot_ids=[product.source_provenance.source_snapshot_id],
        source_strategy_version='retained-regression', normalizer_version='v1', taxonomy_version='v1')
    return PreparedPriceUniverse(universe=PriceUniverseBuilder().build(key, [product], built_at=CLOCK),
        stores=(Store(store_id=product.store_id, name=product.store_name, chain=product.chain, city='Lund'),),
        economic_pool=EconomicIngredientPool(), source_name='retained-regression')


def retained(row):
    product = Product.model_validate(row['product'])
    fact = project_raw_facts(row['raw'], chain=product.chain, product_id=product.product_id,
        snapshot_id=product.source_provenance.source_snapshot_id,
        source_reference=row['retained_source'], observed_at=product.source_provenance.source_observed_at.isoformat())
    return product, fact


@pytest.mark.parametrize('row', ROWS, ids=lambda r: r['ingredient'])
def test_retained_product_resolves_in_its_own_store_with_authored_form(row):
    product, fact = retained(row)
    before = product.model_dump_json()
    facts = supplement_catalog_facts([product], {(product.store_id, product.product_id): fact})
    prefs = RecipePreferences(mode='complete')
    recipe = next(r for r in candidates(prefs, 2) if r.name == row['recipe'])
    ingredient = next(i for i in recipe.ingredients if i.canonical_name == row['ingredient'])
    request = PlanRequest(recipes=1, recipe_preferences=prefs, allowed_store_ids=[product.store_id])
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(product), state(),
        facts=facts, now=CLOCK)
    resolved = planner.resolve(ingredient.name, ingredient.quantity, ingredient.unit,
                               profile=TasteProfile(), recipe=recipe)
    assert len(resolved) == 1
    candidate = resolved[0][1]
    assert (candidate.product_id, candidate.store_id) == (product.product_id, product.store_id)
    assert candidate.usable_quantity == row['expected_quantity']
    assert candidate.usable_unit == ingredient.unit
    assert candidate.price == product.price
    assert product.model_dump_json() == before
    assert not facts[(product.store_id, product.product_id)].allergens_checked
    # The fix must never silently expand the user's store selection.
    planner.store_ids = {'another-store'}
    planner.lookup_cache.clear()
    with pytest.raises(PolicyConflict):
        planner.resolve(ingredient.name, ingredient.quantity, ingredient.unit,
                        profile=TasteProfile(), recipe=recipe)


@pytest.mark.parametrize('change', [
    {'brand': 'Other'}, {'name': 'Kikärtor med sås'}, {'package_quantity': 240},
    {'package_unit': 'ml'}, {'gtin': '7350002402962'}, {'product_id': 'other'},
    {'sale_model': 'unknown'}, {'source_provenance': None}, {'store_id': 'other'},
])
def test_image_identity_cannot_cross_variant_package_or_source(change):
    row = next(r for r in ROWS if r['ingredient'] == 'kikärtor')
    product, fact = retained(row)
    product = product.model_copy(update=change)
    result = supplement_catalog_facts([product], {(product.store_id, product.product_id): fact})
    assert 'usable_quantity' not in result[(product.store_id, product.product_id)].field_sources


@pytest.mark.parametrize('volume', ['380/240g', '400/230g', '230g', '230/380g', '380/230ml', '380/230g + sås'])
def test_slash_quantity_needs_exact_supplier_corroboration(volume):
    row = next(r for r in ROWS if r['ingredient'] == 'kikärtor')
    product, fact = retained({**row, 'raw': {**row['raw'], 'displayVolume': volume}})
    result = supplement_catalog_facts([product], {(product.store_id, product.product_id): fact})
    assert 'usable_quantity' not in result[(product.store_id, product.product_id)].field_sources


@pytest.mark.parametrize('change', [{'snapshot_id': 'old'}, {'product_id': 'other'},
    {'source': 'unrelated'}, {'method': 'guessed'}, {'gtin': 'invalid'}])
def test_retained_image_proof_must_be_bound_to_the_actual_source(change):
    product, fact = retained(next(r for r in ROWS if r['ingredient'] == 'kikärtor'))
    proof = {**fact.field_sources['retailer_image_gtin'][0], **change}
    fact = replace(fact, field_sources={**fact.field_sources, 'retailer_image_gtin': (proof,)})
    result = supplement_catalog_facts([product], {(product.store_id, product.product_id): fact})
    assert 'usable_quantity' not in result[(product.store_id, product.product_id)].field_sources


def test_fact_proofs_remain_bound_and_nutrition_conflicts_are_not_erased():
    row = next(r for r in ROWS if r['ingredient'] == 'crème fraiche')
    product, original = retained(row)
    original = replace(original, nutrition={'fat_g': 99}, nutrition_unit='g')
    fact = supplement_catalog_facts([product], {(product.store_id, product.product_id): original})[(product.store_id, product.product_id)]
    assert fact.nutrition == {'fat_g': 99}
    assert 'supplier_nutrition_conflict' in fact.conflicts
    projected = project_usable_quantity(product, fact, required_unit='g')
    assert projected.usable_unit == 'g'
    assert project_usable_quantity(product.model_copy(update={'store_id': 'other'}), fact).usable_unit == 'ml'
    recipe = next(r for r in candidates(RecipePreferences(mode='complete'), 2) if r.name == row['recipe'])
    assert not product_form_compatible(recipe, row['ingredient'], projected, fact)


@pytest.mark.parametrize('name,accepted', [('Salt med Jod', True), ('Salt utan jod', True),
    ('Salt', True), ('Salt & vinäger chips', False), ('Örtsalt', False),
    ('Salt Spray Styling Original', False), ('Salt med vitlök', False), ('Grovt Salt', False)])
def test_salt_has_a_whole_food_match(name, accepted):
    assert evaluate_product_semantics('salt', {'name': name}).compatible is accepted


def test_reversed_red_onion_label_corrects_stale_yellow_class_without_crossing_foods():
    product, _ = retained(next(r for r in ROWS if r['ingredient'] == 'rödlök'))
    assert product.canonical_food == 'gul lök'  # Actual retained misclassification.
    assert canonicalize_ingredient_name(product.name) == 'rödlök'
    assert evaluate_product_semantics('rödlök', product).compatible
    assert not evaluate_product_semantics('gul lök', product).compatible
    for name in ('Lök Gul Klass 1', 'Lök Röd Picklad', 'Chips Lök Röd', 'Lök Röd Pulver'):
        changed = product.model_copy(update={'name': name})
        assert not _whole_food_identity('rödlök', 'raw_edible', changed, None)


@pytest.mark.parametrize('name,accepted', [('Tomater Babyplommon Klass 1', True),
    ('Tomat San Marzano Klass 1', True), ('Tomat Runda Import Klass 1', True),
    ('Tomater Soltorkade Klass 1', False), ('Tomat San Marzano Sås', False),
    ('Tomater Babyplommon i Olja', False), ('Tomat Kumato Kex', False)])
def test_tomato_variety_is_not_permission_for_a_prepared_product(name, accepted):
    product, _ = retained(next(r for r in ROWS if r['ingredient'] == 'tomat'))
    assert bool(_whole_food_identity('tomat', 'raw_edible', product.model_copy(update={'name': name}), None)) is accepted


def test_image_bound_dairy_requires_the_retained_volume_to_agree():
    row = next(r for r in ROWS if r['ingredient'] == 'crème fraiche')
    product, fact = retained({**row, 'raw': {**row['raw'], 'displayVolume': '5dl'}})
    result = supplement_catalog_facts([product], {(product.store_id, product.product_id): fact})
    assert 'usable_quantity' not in result[(product.store_id, product.product_id)].field_sources


def test_juice_keeps_native_nutrient_basis_and_does_not_invent_density():
    row = next(r for r in ROWS if r['ingredient'] == 'citronjuice')
    product, original = retained(row)
    fact = supplement_catalog_facts([product], {(product.store_id, product.product_id): original})[(product.store_id, product.product_id)]
    assert fact.nutrition_unit == 'g'
    assert product.usable_unit == 'ml'
    assert 'usable_quantity' not in fact.field_sources
    assert plain_juice_composition('citronjuice', fact.ingredients[0])
    for text in ('Citronjuice 50%, eterisk olja (från citronskal)',
                 'Citronjuice, eterisk olja (från citronskal)',
                 'Citronjuice 99,9%, rapsolja', 'Citronjuice 99,9%, socker'):
        assert not plain_juice_composition('citronjuice', text)
    for change in ({'package_quantity': 500}, {'brand': 'Other'}, {'name': 'Citronjuice sötad'},
                   {'gtin': '7350002402955'}):
        changed = product.model_copy(update=change)
        assert not supplement_catalog_facts([changed], {}).get((changed.store_id, changed.product_id))


def test_manufacturer_parser_preserves_the_explicit_gram_basis():
    # Reduced HTML contract; nutritional facts from the retained manufacturer
    # declaration. Full acquisition SHA is retained in the shipped registry.
    row = next(r for r in declarations() if r.get('parser') == 'zeinas-explicit-juice-declaration-v1')
    body = ('<h1 class="product_title">Citronjuice</h1>'
        '<div class="woocommerce-product-details__short-description">Zeinas Citronjuice '
        'FÖRPACKNINGSSTORLEK: 200 ML</div><div id="tab-description">'
        '<h3>INGREDIENSER:</h3><p>' + row['ingredients'] + '</p>'
        '<h3>NÄRINGSVÄRDE PER 100G:</h3><table>'
        '<tr><td>Energi</td><td>117 kJ / 28 kcal</td></tr>'
        '<tr><td>Fett</td><td>0,1 g</td></tr><tr><td>Kolhydrat</td><td>2 g</td></tr>'
        '<tr><td>Protein</td><td>0,3 g</td></tr></table></div>').encode()
    acquisition = {**row['source'], 'sha256': hashlib.sha256(body).hexdigest()}
    parsed = parse_zeinas_juice(body, acquisition)
    assert parsed['nutrition'] == row['nutrition']
    assert parsed['basis_unit'] == 'g' and parsed['package_unit'] == 'ml'
    assert parsed['gtin'] is None
    with pytest.raises(ValueError, match='unverified'):
        parse_zeinas_juice(body + b'changed', acquisition)
    with pytest.raises(ValueError, match='unverified'):
        parse_zeinas_juice(body, {**acquisition, 'url': 'https://example.org/'})
