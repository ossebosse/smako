"""Acceptance-runner contracts only; these are not authentic API results."""
import copy
import importlib.util
import json
from pathlib import Path

from app.models import PlanRequest

spec = importlib.util.spec_from_file_location('recipe_http_acceptance', Path(__file__).parents[2] / 'scripts/recipe_layer/http_acceptance.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
PROFILE_SOURCE, cases, complete_request = runner.PROFILE_SOURCE, runner.cases, runner.complete_request


def test_scenarios_keep_original_fifteen_slots_twenty_portions_and_thresholds():
    scenarios = cases()
    for source in json.loads(PROFILE_SOURCE.read_bytes())['cases']:
        request = scenarios['legacy-1520-' + source['case']]
        assert request == source['request']
        meals = request['personal']['meals']
        assert sum(m['count'] for m in meals) == 15
        assert sum(m['count'] * m['servings'] for m in meals) == 20
        assert [m['limits']['min_protein_g'] for m in meals] == [40, 30, 20]
        assert 'recipe_preferences' not in request
        assert request['max_stores'] == 2


def test_four_person_and_monotonic_inputs_only_change_stated_scope():
    four = complete_request(servings=4)
    assert four['recipes'] == 5 and four['personal']['meals'][0]['servings'] == 4
    assert four['personal']['meals'][0]['count'] == 5
    exact = complete_request(mode='cheapest', purchase='exact')
    estimated = complete_request(mode='cheapest', purchase='estimated')
    equivalent = copy.deepcopy(estimated)
    equivalent['purchase_planning_mode'] = 'exact'
    assert exact == equivalent
    assert exact['personal']['allow_nutrition_estimates'] is True


def test_runner_scenarios_are_real_validated_requests_not_product_patches():
    for name, value in cases().items():
        request = PlanRequest.model_validate(value)
        assert not request.personal.slots, name
        assert not request.personal.product_locks, name
        assert not request.personal.extras, name


def test_extended_choices_are_explicit_and_do_not_silently_loosen_negative_case():
    scenarios = cases()
    assert scenarios['mixed-four']['recipe_preferences']['max_minutes'] == 45
    assert scenarios['mixed-four-time-negative']['recipe_preferences']['max_minutes'] == 40
    custom = scenarios['custom-ingredients']['recipe_preferences']
    assert (custom['min_ingredients'], custom['max_ingredients'], custom['cuisines']) == (12, 13, [])
    assert scenarios['products-only']['recipe_preferences']['adaptation'] == 'products'
    assert scenarios['mixed-vegetarian']['personal']['meals'][0]['diet'] == 'vegetarian'
