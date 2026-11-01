"""New product support keeps food identity, unit and source boundaries."""
import copy
import json
from pathlib import Path

import pytest
from app.models.plan import DietPreference
from app.services.diet_policy import _excluded_by_diet
from app.services.intake_product_links import compatible, project_reviewed_quantity
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes

from backend.tests.test_expansion_ingredients import source

ROOT = Path(__file__).parents[1] / 'app/data'
ROWS = json.loads((ROOT / 'ingredients/expansion-round2-20261101.json').read_bytes())['ingredients']


@pytest.mark.parametrize('row', ROWS, ids=lambda row: row['name'])
def test_source_bound_whole_products_reject_changed_food_or_quantity(row):
    p, f = source(row)
    p = project_reviewed_quantity(p, f, allow_estimates=True, required_unit=row['unit'])
    key = row['requirements'][0].removeprefix('pack:')
    assert compatible(key, p, f)
    for update in ({'name': p.name+' färdigrätt'}, {'brand': 'Other'}, {'store_id': 'other'},
                   {'package_quantity': p.package_quantity+1},
                   {'usable_quantity': p.usable_quantity+1},
                   {'usable_unit': 'ml' if row['unit']=='g' else 'g'}):
        assert not compatible(key, p.model_copy(update=update), f)


def test_grape_stems_are_not_food_and_population_yield_needs_explicit_estimates():
    row = next(r for r in ROWS if r['name'] == 'vindruvor')
    p, f = source(row)
    p = p.model_copy(update={'quantity_confidence': 'exact'})
    key = row['requirements'][0].removeprefix('pack:')
    assert not compatible(key, p, f)
    assert project_reviewed_quantity(p, f, required_unit='g') is p
    q = project_reviewed_quantity(p, f, allow_estimates=True, required_unit='g')
    assert q.usable_quantity == p.package_quantity * .96
    assert q.quantity_confidence == 'estimated' and compatible(key, q, f)
    assert q.price == p.price and q.source_provenance == p.source_provenance
    assert project_reviewed_quantity(p, f, allow_estimates=True, required_unit='ml') is p


def stompa_source():
    path = ROOT / 'recipes/incoming/authoring-1000-20261101/continuation-24/source/paket/021-registergranskning.json'
    doc = json.loads(path.read_bytes())
    row = next(r for r in doc['recipes'] if r['base_id']=='smako-swedish-stompa' and r['variant_id']=='simple')
    return {**doc, 'recipes': [copy.deepcopy(row)]}


def test_weighted_filmjolk_keeps_explicit_volume_recipes_and_review_separate():
    vocabulary = library_vocabulary(current_recipes())
    old_unit, old_requirements = vocabulary.by_unit[('filmjölk|as_sold', 'ml')]
    assert old_unit == 'ml'
    assert library_vocabulary([])['filmjölk|as_sold'] == (old_unit, old_requirements)
    gram_row = next(r for r in ROWS if r['name']=='filmjölk')
    assert vocabulary.by_unit[('filmjölk|as_sold', 'g')] == ('g', gram_row['requirements'])
    document = stompa_source()
    item = next(i for c in document['recipes'][0]['components'] for i in c['ingredients'] if i['name']=='filmjölk')
    assert item['unit']=='ml'
    original_quantity = item['quantity']
    old_pack, _ = standardize(document, vocabulary, reviewed_at='2026-11-01')
    old = next(i for i in old_pack['recipes'][0]['ingredients'] if i['name']=='filmjölk')
    assert old['product_requirements']==old_requirements and old['unit']=='ml'
    # A separately authored gram amount, not a conversion or new product fact.
    item.update(unit='g', quantity=47)
    new_pack, _ = standardize(document, vocabulary, reviewed_at='2026-11-01')
    new = next(i for i in new_pack['recipes'][0]['ingredients'] if i['name']=='filmjölk')
    assert new['product_requirements']==gram_row['requirements'] and new['unit']=='g'
    assert new['quantity']==47 and old['quantity']==original_quantity
    item['requirements'] = old_requirements
    with pytest.raises(ValueError, match='tappa granskade produktkrav'):
        standardize(document, vocabulary, reviewed_at='2026-11-01')


def test_reviewed_unit_choice_does_not_supply_a_density():
    row = next(r for r in ROWS if r['name']=='filmjölk')
    p, f = source(row)
    gram_key = row['requirements'][0].removeprefix('pack:')
    old_key = library_vocabulary([])['filmjölk|as_sold'][1][0].removeprefix('pack:')
    assert compatible(gram_key, p, f)
    assert not compatible(old_key, p, f)


def test_whole_shell_eggs_are_counted_without_claiming_raw_or_boiled_weight():
    row = next(r for r in ROWS if r['name'] == 'ägg')
    assert row['form'] == 'as_sold' and row['unit'] == 'st'
    p, f = source(row)
    key = row['requirements'][0].removeprefix('pack:')
    assert compatible(key, p, f)
    assert not compatible(key, p.model_copy(update={'usable_unit': 'g'}), f)
    assert all(link['quantity']['basis'] == 'as_sold'
               and link['quantity']['unit'] == 'st'
               and link['quantity']['usable_quantity'] == link['package_quantity']
               and not link['quantity'].get('edible_fraction')
               for link in row['reviewed_links'])
    vocabulary = library_vocabulary(current_recipes())
    assert vocabulary['ägg|raw_edible'][0] == 'g'
    assert vocabulary['kokta ägg|cooked_drained'][0] == 'g'
    assert vocabulary['ägg|as_sold'] == ('st', row['requirements'])


def test_fish_based_worcestershire_keeps_vegetarian_and_vegan_exclusions():
    assert _excluded_by_diet('worcestershiresås', DietPreference.VEGETARIAN)
    assert _excluded_by_diet('worcestershiresås', DietPreference.VEGAN)
