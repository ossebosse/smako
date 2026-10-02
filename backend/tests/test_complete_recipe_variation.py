"""Authored diversity semantics; structural tests, not market acceptance."""
from itertools import combinations

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import diversity_policy, prepare_request
from app.services.culinary_similarity import CulinarySimilarity
from app.services.meal_plan_optimizer import MealPlanService
from app.services.personal_planner import personal_policy_request
from app.services.recipe_library import candidates


@pytest.mark.parametrize('cuisine', ['greek', 'italian', 'mexican', 'indian', 'thai', 'swedish'])
def test_authored_five_dinner_variety_can_share_side_or_heat_source(cuisine):
    service = MealPlanService(Settings(price_provider='mock'))
    request = prepare_request(PlanRequest(recipes=5, recipe_preferences={'mode': 'complete', 'cuisines': [cuisine]}),
                              Settings(complete_recipes_enabled=True))
    pool = [r for r in candidates(request.recipe_preferences, 2) if r.design.variant_id == 'base']
    policy = diversity_policy(request, service._diversity_policy_for(request, request.diversity_mode))
    constraints = service._culinary_constraints(pool, policy)
    assert any(service.menu_optimizer.accepts_recipes(menu, constraints) for menu in combinations(pool, 5))
    assert constraints.max_same_recipe_family == 2
    assert constraints.max_same_primary_ingredient_meals == 2
    assert constraints.max_pairwise_recipe_similarity == .85


def test_explicit_limits_survive_json_reload_and_default_limits_do_not_appear():
    settings = Settings(complete_recipes_enabled=True)
    service = MealPlanService(Settings(price_provider='mock'))
    for explicit in ({}, {'max_same_cooking_method_meals': 1, 'max_same_carbohydrate_meals': 2}):
        original = prepare_request(PlanRequest(recipe_preferences={'mode': 'complete'}, **explicit), settings)
        reread = prepare_request(PlanRequest.model_validate_json(original.model_dump_json()), settings)
        for request in (original, reread):
            policy = diversity_policy(request, service._diversity_policy_for(personal_policy_request(request, 5), request.diversity_mode))
            assert policy.max_same_cooking_method_meals == explicit.get('max_same_cooking_method_meals')
            assert policy.max_same_carbohydrate_meals == explicit.get('max_same_carbohydrate_meals')
            assert policy.max_same_recipe_family == 2
            assert policy.max_same_primary_ingredient_meals == 2
            assert policy.max_pairwise_culinary_similarity == .85
        assert original.recipe_diversity_overrides == reread.recipe_diversity_overrides


def test_legacy_policy_and_similarity_guards_remain_unchanged():
    service = MealPlanService(Settings(price_provider='mock'))
    request = PlanRequest()
    policy = service._diversity_policy_for(request, request.diversity_mode)
    assert diversity_policy(request, policy) is policy
    assert policy.max_same_cooking_method_meals == 2
    assert policy.max_same_carbohydrate_meals == 2
    assert 'recipe_diversity_overrides' not in request.model_dump()


def test_authored_profiles_use_declared_main_side_sauce_and_variants_remain_same_dinner():
    similarity = CulinarySimilarity()
    pool = candidates(RecipePreferences(mode='complete', cuisines=['mexican']), 2)
    fajita = next(r for r in pool if r.design.base_id.endswith('beef-fajita') and r.design.variant_id == 'base')
    profile = similarity.build_profile(fajita)
    assert profile.primary_protein == 'nötfärs'
    assert profile.primary_carb == 'tortillas'
    assert profile.sauce_base == 'yoghurt naturell'
    variant = next(r for r in pool if r.design.base_id == fajita.design.base_id and r.design.variant_id != 'base')
    assert similarity.compare_recipes(fajita, variant).score >= .90
    soup = next(r for r in pool if r.design.base_id.endswith('corn-soup') and r.design.variant_id == 'base')
    assert similarity.compare_recipes(fajita, soup).score < .85
