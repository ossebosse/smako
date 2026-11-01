"""Reviewed expansion inputs keep exact product and dietary boundaries."""
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models.plan import DietPreference
from app.models.provenance import SourceProvenance
from app.services.complete_recipes import product_form_compatible
from app.services.diet_policy import _excluded_by_diet
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.intake_product_links import (
    compatible,
    ingredient_product,
    project_reviewed_quantity,
)
from app.services.personal_policy import ProductFacts
from app.services.recipe_authoring import library_vocabulary

from backend.tests.test_personal_planning_v2 import product

PATH = Path(__file__).parents[1] / 'app/data/ingredients/expansion-20261101.json'
ROWS = json.loads(PATH.read_bytes())['ingredients']


def source(row):
    proof = row['reviewed_links'][0]
    p = product(proof['name'], proof['package_quantity'], proof['package_unit'], 20,
                identity=proof['product_id'], store=proof['store_id']).model_copy(update={
        'brand': proof['brand'], 'category': proof['category'], 'gtin': proof['gtin'],
        'sale_model': proof['sale_model'], 'quantity_confidence': proof['quantity']['confidence'],
        'source_provenance': SourceProvenance.model_validate({**proof['source_provenance'],
            'retailer_product_id': proof['retailer_product_id']})})
    f = ProductFacts(source='test-bound-retained-declaration-state', source_product_id=p.product_id,
                     source_snapshot_id=proof['source_snapshot_id'], retailer_product_id=proof['retailer_product_id'])
    return p, f


@pytest.mark.parametrize('row', ROWS, ids=lambda row: row['name'])
def test_reviewed_inputs_reject_changed_food_package_context_or_composition(row):
    p, f = source(row)
    p = project_reviewed_quantity(p, f, allow_estimates=True, required_unit=row['unit'])
    key = row['requirements'][0].removeprefix('pack:')
    assert compatible(key, p, f)
    recipe = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={row['name']:row['form']}),
        ingredients=[SimpleNamespace(name=row['name'], product_requirements=row['requirements'])])
    assert product_form_compatible(recipe,row['name'],p,f)
    for update in ({'name':p.name+' färdigrätt'}, {'brand':'unreviewed'},
                   {'store_id':'another-store'}, {'package_quantity':p.package_quantity+1},
                   {'usable_unit':'st'}, {'usable_quantity':p.usable_quantity+1}):
        assert not compatible(key, p.model_copy(update=update), f), update
    changed = replace(f, ingredients=('Ändrad sammansättning',), ingredients_complete=True)
    assert not compatible(key, p, changed)
    assert not compatible(key, p, replace(f, source_snapshot_id='unbound'))
    assert not ingredient_product('unreviewed input', row['form'], row['requirements'], p, f)


def test_sardell_drained_mass_is_declared_not_gross_or_composition_percentage():
    row = next(r for r in ROWS if r['name'] == 'sardeller')
    p, f = source(row)
    recipe = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={'sardeller':'preserved_drained'}),
        ingredients=[SimpleNamespace(name='sardeller', product_requirements=row['requirements'])])
    assert not product_form_compatible(recipe,'sardeller',p,f)
    q = project_reviewed_quantity(p,f,required_unit='g')
    assert q.package_quantity == 80 and q.usable_quantity == 43
    assert q.price == p.price and q.source_provenance == p.source_provenance
    assert product_form_compatible(recipe,'sardeller',q,f)
    assert not product_form_compatible(recipe,'sardeller',q,replace(f,source_snapshot_id='changed'))
    assert not product_form_compatible(recipe,'sardeller',q.model_copy(update={'usable_quantity':43.2}),f)


def test_whole_shallot_package_is_not_edible_mass_and_estimates_are_explicit():
    row = next(r for r in ROWS if r['name'] == 'schalottenlök')
    p, f = source(row)
    p = p.model_copy(update={'quantity_confidence':'exact'})
    key = row['requirements'][0].removeprefix('pack:')
    assert not compatible(key,p,f)
    assert project_reviewed_quantity(p,f,required_unit='g') is p
    q = project_reviewed_quantity(p,f,allow_estimates=True,required_unit='g')
    assert q.package_quantity == 250 and q.usable_quantity == 180
    assert q.quantity_confidence == 'estimated'
    assert q.price == p.price and q.source_provenance == p.source_provenance
    assert compatible(key,q,f)
    assert project_reviewed_quantity(p,f,allow_estimates=True,required_unit='ml') is p


@pytest.mark.parametrize('name', ['bruna bönor','evaporerad mjölk','svartögda bönor',
                                 'färska majskorn','grönsaksbuljong','hel kyckling'])
def test_specific_inputs_do_not_collapse_to_different_generic_foods(name):
    assert canonicalize_ingredient_name(name) == name


@pytest.mark.parametrize('name', ['fläskkarré','fisksås','kalvfärs','guanciale','ostronsås','sardeller'])
def test_animal_inputs_cannot_create_false_vegetarian_recipes(name):
    assert _excluded_by_diet(name,DietPreference.VEGETARIAN)
    assert _excluded_by_diet(name,DietPreference.VEGAN)


@pytest.mark.parametrize('name', ['parmesan','ghee','mjölkpulver','evaporerad mjölk'])
def test_new_dairy_inputs_are_excluded_from_vegan_requests(name):
    assert _excluded_by_diet(name,DietPreference.VEGAN)


def test_unknown_inputs_still_require_review_and_existing_defaults_are_preserved():
    vocabulary = library_vocabulary([])
    assert 'makrutlimeblad|raw_edible' not in vocabulary
    assert 'evaporerad mjölk|as_sold' not in vocabulary
    for row in ROWS:
        assert vocabulary[row['name']+'|'+row['form']] == (row['unit'],row['requirements'])


def test_spaghetti_shape_requirement_does_not_admit_arbitrary_pasta_shapes():
    from app.services.complete_recipes import _whole_food_identity
    from app.services.content_pack_requirements import compatible as pack_compatible
    from app.services.product_semantics import evaluate_product_semantics

    for name in ['Spaghetti', 'Spagetti Fullkorn']:
        assert pack_compatible(['spaghetti'], product(name, 500, 'g', 20), None)
    for name in ['Penne', 'Fusilli', 'Lasagneplattor', 'Makaroner']:
        assert not pack_compatible(['spaghetti'], product(name, 500, 'g', 20), None)
    for name in ['Gammaldags Idealmakaroner', 'Idealmakaroner Gammaldags']:
        assert evaluate_product_semantics('pasta', product(name, 500, 'g', 20)).compatible
        assert pack_compatible(['stewing_macaroni'], product(name, 500, 'g', 20), None)
        assert _whole_food_identity('pasta', 'dry', product(name, 500, 'g', 20), None,
                                    ['pack:stewing_macaroni'])
    for name in ['Snabbmakaroner', 'Spaghetti', 'Makaroner Majspasta Glutenfri']:
        assert not pack_compatible(['stewing_macaroni'], product(name, 500, 'g', 20), None)
    for name in ['Idealmakaroner Gammaldags Färdigrätt', 'Idealmakaroner Gammaldags med köttsås',
                 'Gammaldags Idealmakaroner Soppa']:
        assert not _whole_food_identity('pasta', 'dry', product(name, 500, 'g', 20), None,
                                        ['pack:stewing_macaroni'])
