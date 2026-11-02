"""New culinary names obey fish exclusions and distinct meal categories."""
import copy
import json
from pathlib import Path

import pytest
from app.models.personal import MealSettings, MealSlot
from app.models.recipe import Recipe
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import matches_preferences
from app.services.diet_policy import ingredient_is_excluded, recipe_contains_fish
from app.services.personal_policy import distribution_ok, protein_category
from app.services.recipe_authoring import library_vocabulary, standardize
from app.services.recipe_library import current_recipes, matches_meal


@pytest.mark.parametrize('base', ['smako-swedish-sillsallad', 'smako-swedish-janssons-frestelse'])
def test_issued_fish_is_rejected_by_both_preference_paths_without_rewriting_content(base):
    recipe = next(r for r in current_recipes() if r.design.base_id == base and r.design.variant_id == 'simple')
    sealed = recipe.model_dump_json()
    assert recipe_contains_fish(recipe) and protein_category(recipe) == 'fish'
    prefs = RecipePreferences(mode='complete', allow_fish=False, min_ingredients=3, max_ingredients=20)
    assert not matches_preferences(recipe, prefs)
    meal = MealSettings(count=1, servings=4, recipe_choices={'min_ingredients': 1, 'max_ingredients': 40})
    assert not matches_meal(recipe, meal, prefs)
    assert recipe.model_dump_json() == sealed
    assert matches_preferences(recipe, prefs.model_copy(update={'allow_fish': True}))


def test_library_candidate_filter_removes_the_new_fish_identities():
    from app.services.recipe_library import candidates

    prefs = RecipePreferences(mode='complete', allow_fish=False, min_ingredients=3, max_ingredients=20)
    rows = candidates(prefs, 4)
    assert rows and not any(recipe_contains_fish(r) for r in rows)


@pytest.mark.parametrize('name', ['svensk ansjovis', 'svensk ansjovis med spad', 'ätklar inläggningssill'])
def test_explicit_fish_exclusion_includes_specific_finfish(name):
    assert ingredient_is_excluded(name, ['fisk'])
    assert not ingredient_is_excluded('corned beef på burk', ['fisk'])


def test_new_whole_chicken_keeps_chicken_distribution():
    recipe = next(r for r in current_recipes() if r.design.base_id == 'smako-indian-murgh-musallam' and r.design.variant_id == 'simple')
    assert protein_category(recipe) == 'chicken'
    meal = MealSettings(count=1, distribution={'chicken': 1})
    slot = MealSlot(id='dinner-1', day=1, meal_type='dinner', recipe=recipe)
    assert distribution_ok([slot], [meal])
    assert not distribution_ok([slot], [meal.model_copy(update={'distribution': {'meat': 1}})])


@pytest.mark.parametrize('name', ['råa skalade vannameiräkor', 'blåmusselkött utan skal'])
def test_new_shellfish_cannot_fill_a_fish_or_meat_quota(name):
    recipe = Recipe(name='Kategoriisolering', servings=4,
                    ingredients=[{'name': name, 'quantity': 200, 'unit': 'g'}], instructions=['Genomhetta.'])
    assert protein_category(recipe) == 'shellfish'
    assert not recipe_contains_fish(recipe)
    slot = MealSlot(id='dinner-1', day=1, meal_type='dinner', recipe=recipe)
    for kind in ('fish', 'meat'):
        assert not distribution_ok([slot], [MealSettings(count=1, distribution={kind: 1})])


def test_future_authoring_records_fish_flag_from_the_same_culinary_names():
    path = Path('backend/app/data/recipes/reviewed-expansion-round2-20261101/authoring-stage21.json')
    document = copy.deepcopy(json.loads(path.read_bytes()))
    for row in document['recipes']:
        row['version'] = '1.0.2'
    pack, _ = standardize(document, library_vocabulary(current_recipes()), reviewed_at='2026-11-01')
    assert all(r['design']['fish'] and not r['design']['vegetarian'] for r in pack['recipes'])


def test_fresh_chorizo_keeps_both_reviewed_meat_exclusions_and_meat_category():
    from app.services.diet_policy import recipe_respects_diet

    recipe = next(r for r in current_recipes() if r.design.base_id == 'smako-mexican-frijoles-puercos')
    assert protein_category(recipe) == 'meat' and not recipe.design.vegetarian
    for meat in ('fläskkött', 'nötkött', 'färsk chorizokorv'):
        assert ingredient_is_excluded('färsk chorizokorv', [meat])
        assert not recipe_respects_diet(recipe, preference='mixed', avoid_ingredients=[meat])
    assert not ingredient_is_excluded('färsk chorizokorv', ['kyckling', 'fisk'])


def test_salsiccia_alternative_keeps_pork_exclusion_and_meat_distribution():
    from app.services.diet_policy import recipe_respects_diet

    recipe = next(r for r in current_recipes() if r.design.base_id == 'smako-greek-spetsofai')
    assert protein_category(recipe) == 'meat' and not recipe.design.vegetarian
    assert not recipe_respects_diet(recipe, preference='mixed', avoid_ingredients=['fläskkött'])
    assert not recipe_respects_diet(recipe, preference='vegetarian')
    assert not ingredient_is_excluded('färsk salsicciakorv', ['kyckling', 'fisk'])


def test_fish_sauce_dip_keeps_meat_distribution_but_obeys_fish_exclusion():
    recipes = [r for r in current_recipes() if r.design.base_id == 'smako-thai-nam-prik-ong']
    assert len(recipes) == 3
    prefs = RecipePreferences(mode='complete', allow_fish=False, min_ingredients=3, max_ingredients=20)
    meal = MealSettings(count=1, servings=4, recipe_choices={'min_ingredients': 1, 'max_ingredients': 40})
    for recipe in recipes:
        assert recipe_contains_fish(recipe) and recipe.design.fish
        assert protein_category(recipe) == 'meat'
        assert not matches_preferences(recipe, prefs) and not matches_meal(recipe, meal, prefs)
        names = {i.canonical_name: i.quantity for i in recipe.ingredients}
        assert 'räkpasta' not in names
        assert names['fisksås'] == (20 if recipe.design.variant_id == 'simple' else 30)
