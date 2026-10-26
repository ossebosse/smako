"""Origin-preserving rules; no price/latency acceptance claims."""
from dataclasses import replace

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.services.complete_recipes import diversity_policy, prepare_request
from app.services.meal_plan_optimizer import MealPlanService
from app.services.personal_planner import personal_policy_request
from app.services.personal_policy import PolicyConflict
from app.services.recipe_library import current_recipes
from app.services.variation_intent import resolve_current_variation
from pydantic import ValidationError


def request(origin='default', **kwargs):
    return PlanRequest.model_validate({'recipe_preferences':{'mode':'complete','max_same_main_protein_dinners':3},
        'max_same_primary_ingredient_meals':2,
        'variation_intent':{'field_origins':{'max_same_primary_ingredient_meals':origin}},
        'personal':{'meals':[{'count':5,'servings':4,'distribution':{'chicken':3,'vegetarian':2}}]}, **kwargs})


def resolve(req, mode='smako-current-library-v2', recipes=None):
    req=prepare_request(req, Settings(complete_recipes_enabled=True, library_search_policy=mode))
    service=MealPlanService(Settings(price_provider='mock'))
    policy=diversity_policy(req,service._diversity_policy_for(personal_policy_request(req,5),req.diversity_mode))
    recipes=recipes or [r for r in current_recipes() if r.design.base_id.startswith('smako-greek-') and 'chicken' in r.design.base_id][:35]
    constraints=service._culinary_constraints(recipes,policy)
    return req,policy,constraints,resolve_current_variation(req,policy,constraints,recipes)


def test_known_default_yields_minimally_and_other_rules_survive_roundtrip():
    req,old,constraints,(policy,new,evidence)=resolve(request())
    assert old.max_same_primary_ingredient_meals==2
    assert policy.max_same_primary_ingredient_meals==new.max_same_primary_ingredient_meals==3
    assert policy.model_dump(exclude={'max_same_primary_ingredient_meals'})==old.model_dump(exclude={'max_same_primary_ingredient_meals'})
    assert replace(new,max_same_primary_ingredient_meals=2)==constraints
    assert evidence['adjustments'] and evidence['effective_primary_limit']==3
    loaded=PlanRequest.model_validate_json(req.model_dump_json())
    assert loaded.variation_intent==req.variation_intent
    assert resolve(loaded)[3][0].model_dump()==policy.model_dump()


@pytest.mark.parametrize('origin',['explicit','unknown'])
def test_two_hard_or_unknown_constraints_do_not_auto_relax(origin):
    with pytest.raises(PolicyConflict,match='Fördelningen kräver 3') as error:
        resolve(request(origin))
    assert error.value.code=='RECIPE_CHOICES_CONFLICT'


def test_legacy_and_original_serialized_request_keep_prior_meaning():
    original=request().model_dump(mode='json');original.pop('variation_intent')
    req=PlanRequest.model_validate(original)
    prepared=prepare_request(req,Settings(complete_recipes_enabled=True,library_search_policy='smako-current-library-v2'))
    assert prepared.variation_intent is None
    assert prepared.recipe_diversity_overrides['max_same_primary_ingredient_meals']==2
    legacy=prepare_request(request(),Settings(complete_recipes_enabled=True))
    assert legacy.recipe_diversity_overrides['max_same_primary_ingredient_meals']==2


def test_nondefault_cannot_be_disguised_as_inherited_and_overrides_remain_hard():
    with pytest.raises(ValidationError,match='ärvd standard'):
        request(max_same_primary_ingredient_meals=1)
    with pytest.raises(PolicyConflict):
        resolve(request(recipe_diversity_overrides={'max_same_primary_ingredient_meals':2}))


def test_mixed_protein_cap_and_base_identity_are_not_the_culinary_primary_cap():
    recipes=[r for r in current_recipes() if r.design.base_id.startswith('smako-greek-') and 'chicken' in r.design.base_id][:35]
    r=next(r for r in recipes if len(r.design.primary_ingredient)>0)
    from app.services.recipe_week_variation import accepts_week, main_protein_sources
    assert 'kyckling' in main_protein_sources(r)
    req=request(); req.recipe_preferences=req.recipe_preferences.model_copy(update={'max_same_main_protein_dinners':2})
    with pytest.raises(PolicyConflict,match='huvudprotein'):
        resolve(req,recipes=recipes)
    assert not accepts_week([r,r,r],req.recipe_preferences,dinner_count=3,final=True)
