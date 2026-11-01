"""Final culinary alternatives retain batch, source, waiting and loss boundaries."""
import json
from pathlib import Path

import pytest
from app.models.personal import MealSettings
from app.models.recipe import RecipeDesign, RecipeStep
from app.models.recipe_preferences import RecipePreferences
from app.services.diet_policy import ingredient_is_excluded
from app.services.meal_library_content import identity, load_entries, manifest_entries
from app.services.recipe_library import (
    _scaled,
    current_recipes,
    matches_meal,
    validate_recipe_design,
)

REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')


def test_lamb_successors_change_only_the_reviewed_cut_and_gross_basis_and_keep_history():
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    current = {identity(r): r for r in current_recipes()}
    review = json.loads((REPORT / 'lamb-corrections.json').read_bytes())
    proof = json.loads((REPORT / 'qualification-lamb-corrections.json').read_bytes())
    assert len(review['recipes']) == 9
    assert proof['pack_sha256'] == review['pack_sha256'] and not proof['input_only']
    assert {r['id'] for r in proof['modes']['estimated']['recipes']} == {r['runtime_id'] for r in review['recipes']}
    assert all(r['status'] == 'verified' and r['audit']['passed'] for r in proof['modes']['estimated']['recipes'])
    for row in review['recipes']:
        before, after = issued[row['previous_id']], current[row['runtime_id']]
        assert before.design.content_sha256 == row['previous_content_sha256']
        assert after.design.content_sha256 == row['content_sha256']
        assert row['previous_id'] in manifest['revocations'] and row['previous_id'] not in current
        old = {i.canonical_name: i for i in before.ingredients}
        new = {i.canonical_name: i for i in after.ingredients}
        lamb, leg = old.pop('lammkött'), new.pop('benfri lammstek')
        assert old == new
        assert lamb.quantity == leg.quantity and lamb.unit == leg.unit == 'g'
        assert lamb.form == 'raw_edible' and leg.form == 'as_sold'
        assert lamb.product_requirements != leg.product_requirements
        assert after.preparation.version == 'smako-authored-losses-v3'
        assert any(p.operation == 'trim_before_cooking' and p.step_id == 's3' for p in after.design.unmeasured_processes)
        assert after.design.steps[1].duration_minutes == 1440
        assert 1440 < after.design.waiting_minutes < after.design.total_minutes <= 2880
        for portions in (1, 4, 8):
            scaled = _scaled(after, portions)
            validate_recipe_design(scaled)
            assert scaled.design.steps[1].duration_minutes == 1440
            assert '24 timmar' in scaled.instructions[1]
        assert ingredient_is_excluded('benfri lammstek', ['lammkött'])


def test_long_thaw_is_accepted_by_content_contract_but_not_short_user_time_limits():
    recipe = next(r for r in current_recipes() if r.design.base_id == 'smako-indian-rogan-josh')
    prefs = RecipePreferences(mode='complete', min_ingredients=3, max_ingredients=20)
    meal = MealSettings(count=1, servings=4, recipe_choices={'min_ingredients': 1, 'max_ingredients': 40})
    assert matches_meal(recipe, meal, prefs)
    limited = meal.model_copy(update={'recipe_choices': meal.recipe_choices.model_copy(update={'max_waiting_minutes': 1440})})
    assert not matches_meal(recipe, limited, prefs)
    RecipeDesign.model_validate(recipe.design.model_dump())
    with pytest.raises(ValueError):
        RecipeDesign.model_validate({**recipe.design.model_dump(), 'waiting_minutes': 2881})
    with pytest.raises(ValueError):
        RecipeStep.model_validate({**recipe.design.steps[1].model_dump(), 'duration_minutes': 1441})


def test_spinach_variants_retain_meaningful_spices_and_casing_loss_is_bound_to_removal():
    recipes = current_recipes()
    pies = {r.design.variant_id: r for r in recipes if r.design.base_id == 'smako-italian-torta-pasqualina'}
    simple = {i.canonical_name for i in pies['simple'].ingredients}
    standard = {i.canonical_name for i in pies['standard'].ingredients}
    extended = {i.canonical_name for i in pies['extended'].ingredients}
    assert {'mejram', 'muskot'} <= standard - simple
    assert {'tomat', 'basilika', 'rödvinsvinäger'} <= extended - standard
    assert 'mangold' not in standard | extended
    for variant in ('standard', 'extended'):
        assert '600' == f"{next(i.quantity for i in pies[variant].ingredients if i.canonical_name == 'spenat'):g}"
        assert any(p.operation == 'drain_after_cooking' for p in pies[variant].design.unmeasured_processes)
    for recipe in recipes:
        if recipe.design.base_id != 'smako-mexican-frijoles-puercos':
            continue
        process, = recipe.design.unmeasured_processes
        step = next(s for s in recipe.design.steps if s.id == process.step_id)
        assert process.ingredient_keys == ('färsk chorizokorv|as_sold',)
        assert 'kasta fjälstret' in step.text
        assert any('72 °C' in s.text for s in recipe.design.steps)


def test_selected_frozen_products_receive_reviewed_preparation_without_food_dose_changes():
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    current = {identity(r): r for r in current_recipes()}
    review = json.loads((REPORT / 'selected-product-corrections.json').read_bytes())
    proof = json.loads((REPORT / 'qualification-selected-product-corrections.json').read_bytes())
    assert len(review['recipes']) == 8 and proof['pack_sha256'] == review['pack_sha256']
    assert not proof['input_only']
    assert {r['id'] for r in proof['modes']['estimated']['recipes']} == {r['runtime_id'] for r in review['recipes']}
    assert all(r['status'] == 'verified' and r['audit']['passed'] for r in proof['modes']['estimated']['recipes'])
    for row in review['recipes']:
        old, new = issued[row['previous_id']], current[row['runtime_id']]
        assert old.design.content_sha256 == row['previous_content_sha256']
        assert new.design.content_sha256 == row['content_sha256']
        assert old.ingredients == new.ingredients
        assert row['previous_id'] in manifest['revocations'] and row['previous_id'] not in current
        text = ' '.join(new.instructions)
        if new.design.base_id.endswith('spaghetti-aglio-olio'):
            assert new.design.version == '1.0.3' and new.preparation.version == 'smako-authored-losses-v3'
            assert any(p.ingredient_keys == ('pasta|dry',) and p.operation == 'drain_after_cooking'
                       for p in new.design.unmeasured_processes)
            assert 'all uppvägd persilja. Sjud' in text
            assert 'minst tre minuter' in text
        elif new.design.base_id.endswith('sopa-de-lima'):
            assert new.design.steps[1].duration_minutes == 1440
            assert 'minst 74 °C' in text and 'all upptiningsvätska' in text
        else:
            assert 'Sjud vitlöken med 20 ml vatten' in text
            scaled = _scaled(new, 2)
            assert 'Sjud vitlöken med 40 ml vatten' in ' '.join(scaled.instructions)
