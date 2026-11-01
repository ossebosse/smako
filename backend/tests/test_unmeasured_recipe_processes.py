"""Unknown process loss never becomes zero, full retention or an approval."""
import copy
from types import SimpleNamespace

import pytest
from app.models.personal import MealSettings, MealSlot, PortionLimits
from app.services import recipe_library
from app.services.meal_library_content import encoded, validate_pack_bytes
from app.services.personal_nutrition import calculation_basis
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.recipe_authoring import standardize
from app.services.recipe_computation_cache import RecipeComputationCache
from app.services.recipe_portion_weight import estimate_portion_weight
from app.services.recipe_preparation import (
    input_evidence,
    input_evidence_identity,
    pantry_evidence,
    wrap_evidence,
)


def source():
    return {'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'synthetic-loss-test', 'recipes': [{
        'base_id': 'smako-swedish-process-test', 'version': '1.0.0', 'variant_id': 'simple',
        'name': 'Syntetiskt processprov', 'servings': 1, 'cuisine': 'swedish', 'family': 'test',
        'primary': 'tofu', 'method': 'pan', 'side': 'ingen', 'flavor': ['neutral'], 'equipment': ['panna'],
        'components': [{'id': 'food', 'name': 'Mat', 'ingredients': [
            {'name': 'tofu', 'quantity': 100, 'unit': 'g', 'form': 'as_sold', 'role': 'primary'},
            {'name': 'rapsolja', 'quantity': 50, 'unit': 'ml', 'form': 'as_sold', 'role': 'cooking'}]}],
        'steps': [{'text': 'Stek tofun i den uppmätta oljan och låt rinna av på galler. Oljans upptag är okänt.',
                   'uses': ['tofu', 'rapsolja'], 'minutes': 10, 'after': []}],
        'unmeasured_processes': [{'step': 1, 'ingredients': ['tofu', 'rapsolja'],
            'operation': 'deep_fry_and_drain', 'description': 'Olja och vätska rinner av; ingen kvarhållen mängd är uppmätt.'}],
    }]}


def checked(document=None):
    pack, _ = standardize(document or source(), {'tofu|as_sold': ('g', []), 'rapsolja|as_sold': ('ml', [])}, reviewed_at='2026-11-01')
    return validate_pack_bytes(encoded(pack))


@pytest.fixture
def recipe(monkeypatch):
    result = checked()
    assert not result['rejections']
    # Only unit-level calculation checks use structural validation in place
    # of issuing synthetic food. Real registry qualification is separate.
    monkeypatch.setattr(recipe_library, 'validate_recipe_design', recipe_library._structural_check)
    return result['recipes'][0]


def test_new_contract_does_not_register_a_recipe_or_reinterpret_old_content():
    result = checked()
    r = result['recipes'][0]
    assert r.preparation.version == 'smako-authored-losses-v3'
    assert r.design.unmeasured_processes[0].ingredient_keys == ('tofu|as_sold', 'rapsolja|as_sold')
    with pytest.raises(ValueError):
        recipe_library.validate_recipe_design(r)
    old = source()
    old['recipes'][0].pop('unmeasured_processes')
    previous = checked(old)['recipes'][0]
    assert previous.preparation.version == 'smako-authored-input-v2'
    assert 'unmeasured_processes' not in previous.design.model_dump(mode='json')
    assert previous.design.content_sha256 != r.design.content_sha256
    assert [i.quantity for i in r.ingredients] == [i.quantity for i in previous.ingredients]


@pytest.mark.parametrize('change', ['step', 'ingredient', 'duplicate_ingredient', 'duplicate_process', 'coefficient', 'extra_factor'])
def test_loss_metadata_requires_existing_steps_and_inputs_and_no_fake_factor(change):
    document = source()
    processes = document['recipes'][0]['unmeasured_processes']
    if change == 'step':
        processes[0]['step'] = 99
    elif change == 'ingredient':
        processes[0]['ingredients'] = ['mjölk']
    elif change == 'duplicate_ingredient':
        processes[0]['ingredients'] *= 2
    elif change == 'duplicate_process':
        processes.append(copy.deepcopy(processes[0]))
    elif change == 'extra_factor':
        processes[0]['retention_factor'] = 0.1
    else:
        processes[0]['operation'] = 'assume_ten_percent_absorption'
    try:
        result = checked(document)
    except ValueError:
        return
    assert result['rejections'] and not result['recipes']


def test_known_product_or_pantry_nutrients_cannot_prove_served_nutrients(recipe):
    cache = RecipeComputationCache()
    assert input_evidence_identity(recipe, 'tofu', cache) is None
    assert input_evidence(recipe, None, 'tofu', 'g', True, None) is None
    assert pantry_evidence(recipe, 'tofu', 999999) is None
    assert wrap_evidence(recipe, 'tofu', SimpleNamespace(nutrition={'kcal': 100})) is None
    assert PersonalPlanner._nutrition_evidence(None, None, 'tofu', 'g', {'kcal'}, recipe) is None
    assert estimate_portion_weight(recipe, {}) is None
    with pytest.raises(PolicyConflict, match='okänt utbyte'):
        calculation_basis(recipe, allow_estimates=True)


@pytest.mark.parametrize('limits', [{}, {'min_protein_g': 1}, {'max_kcal': 1000}, {'min_weight_g': 1}])
def test_checkout_preserves_constraints_and_reports_unknown_without_zero_values(recipe, limits):
    planner = object.__new__(PersonalPlanner)
    planner.meals = {'dinner': MealSettings(meal_type='dinner', count=1, servings=1, limits=PortionLimits(**limits))}
    slot = MealSlot(id='test-slot', day=1, meal_type='dinner', recipe=recipe)
    if limits:
        with pytest.raises(PolicyConflict, match='inte uppmätt') as exc:
            planner._check_nutrition_uncached([slot], {}, [], [])
        assert exc.value.code == 'DATA_BLOCKED'
    else:
        rows = planner._check_nutrition_uncached([slot], {}, [], [])
        assert rows[0]['status'] == 'UNKNOWN'
        assert rows[0]['values'] == {} and rows[0]['sources'] == []


def test_metadata_and_version_are_part_of_the_content_seal(recipe):
    changed = recipe.model_copy(update={'design': recipe.design.model_copy(update={'unmeasured_processes': None})})
    with pytest.raises(ValueError):
        recipe_library._structural_check(changed)
    changed = recipe.model_copy(update={'preparation': recipe.preparation.model_copy(update={'version': 'smako-authored-input-v2'})})
    with pytest.raises(ValueError, match='Beredningsmetoden'):
        recipe_library._structural_check(changed)


@pytest.mark.parametrize('base', ['smako-indian-gulab-jamun', 'smako-swedish-bohuslansk-aggost',
                                 'smako-swedish-blodpalt', 'smako-indian-murgh-musallam',
                                 'smako-italian-pasta-cacio-pepe'])
def test_issued_food_with_unmeasured_losses_rejects_hard_limits(base):
    # Exercise the real issued content seal, without the synthetic fixture's
    # registry monkeypatch. Purchased input quantities still do not prove
    # the mass or nutrients served after frying, straining, peeling or trimming.
    r = next(r for r in recipe_library.current_recipes()
             if r.design.base_id == base and r.design.variant_id == 'simple')
    recipe_library.validate_recipe_design(r)
    assert r.preparation.version == 'smako-authored-losses-v3'
    assert r.design.unmeasured_processes
    assert estimate_portion_weight(r, {}) is None
    meal_type = r.design.meal_types[0]
    slot = MealSlot(id='issued-loss', day=1, meal_type=meal_type, recipe=r)
    planner = object.__new__(PersonalPlanner)
    for limit in ({'min_weight_g': 1}, {'max_weight_g': 3000}, {'min_protein_g': 1}, {'max_kcal': 3000}):
        planner.meals = {meal_type: MealSettings(meal_type=meal_type, count=1, servings=1,
                                               limits=PortionLimits(**limit))}
        with pytest.raises(PolicyConflict) as exc:
            planner._check_nutrition_uncached([slot], {}, [], [])
        assert exc.value.code == 'DATA_BLOCKED'
    planner.meals[meal_type] = MealSettings(meal_type=meal_type, count=1, servings=1, limits=PortionLimits())
    result = planner._check_nutrition_uncached([slot], {}, [], [])
    assert result[0]['status'] == 'UNKNOWN' and result[0]['values'] == {}


@pytest.mark.parametrize('name,unit', [('ägg', 'st'), ('hel kyckling', 'g'),
                                     ('oxsvans med ben', 'g'), ('rimmat fläsklägg', 'g'),
                                     ('nötblod', 'ml'), ('ungnötslever', 'g'),
                                     ('råa skalade vannameiräkor', 'g'), ('blåmusselkött utan skal', 'g')])
@pytest.mark.parametrize('method', ['salad', 'cold_assembly', 'refrigerated_assembly'])
def test_gross_raw_animal_inputs_still_require_a_hot_method(name, unit, method):
    document = source()
    row = document['recipes'][0]
    row['components'][0]['ingredients'][0].update(name=name, unit=unit)
    row['steps'][0]['uses'][0] = name
    row['unmeasured_processes'][0]['ingredients'][0] = name
    vocabulary = {f'{name}|as_sold': (unit, []), 'rapsolja|as_sold': ('ml', [])}
    warm, _ = standardize(document, vocabulary, reviewed_at='2026-11-01')
    assert not validate_pack_bytes(encoded(warm))['rejections']
    row['method'] = method
    cold, _ = standardize(document, vocabulary, reviewed_at='2026-11-01')
    result = validate_pack_bytes(encoded(cold))
    assert not result['recipes']
    assert 'rå animalisk ingrediens kräver varm metod' in result['rejections'][0]['reason']
