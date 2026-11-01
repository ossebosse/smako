"""Issued successors scale process water without changing food inputs or authority."""
import json
import re
from pathlib import Path

import pytest
from app.models.personal import MealSettings
from app.models.recipe_preferences import RecipePreferences
from app.services.meal_library_content import identity, load_entries, manifest_entries
from app.services.recipe_library import (
    _registered_historical_portions,
    _scaled,
    candidates,
    current_recipes,
    meal_candidates,
    supports_servings,
    validate_recipe_design,
)

REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')


def test_successors_keep_food_inputs_and_original_bytes_and_have_complete_baskets():
    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    active = {identity(r): r for r in current_recipes()}
    review = json.loads((REPORT / 'portion-corrections.json').read_bytes())
    proof = json.loads((REPORT / 'qualification-portion-corrections.json').read_bytes())
    assert proof['pack_sha256'] == review['pack_sha256'] and not proof['input_only']
    expected = {r['runtime_id'] for r in review['recipes']}
    assert len(expected) == 50
    assert {r['id'] for r in proof['modes']['estimated']['recipes']} == expected
    assert all(r['status'] == 'verified' and r['audit']['passed'] for r in proof['modes']['estimated']['recipes'])
    for record in review['recipes']:
        old, new = issued[record['previous_id']], active[record['runtime_id']]
        assert old.design.content_sha256 == record['previous_content_sha256']
        assert new.design.content_sha256 == record['content_sha256']
        assert old.ingredients == new.ingredients
        assert record['previous_id'] in manifest['revocations'] and record['previous_id'] not in active
        for servings in (1, 2, 4, 8, 12):
            if not supports_servings(new, servings):
                with pytest.raises(ValueError, match='satser'):
                    _scaled(new, servings)
                continue
            scaled = _scaled(new, servings)
            assert validate_recipe_design(scaled)
            for before, after in zip(new.ingredients, scaled.ingredients, strict=True):
                assert after.quantity == pytest.approx(before.quantity * servings / new.servings)
                assert after.unit == before.unit and after.form == before.form
                assert after.product_requirements == before.product_requirements
            for step, result in zip(new.design.steps, scaled.design.steps, strict=True):
                for token, amount in step.scalable_amounts or ():
                    expected_token = f'{amount * servings / new.servings:g} ml'.replace('.', ',')
                    assert expected_token in result.text
                # Cooking temperatures and physical dimensions do not scale.
                for fixed in re.findall(r'\d+ (?:°C|cm)\b', step.text):
                    assert fixed in result.text


def test_count_specific_instructions_and_pasta_water_follow_actual_portions():
    active = {r.design.base_id: r for r in current_recipes() if r.design.variant_id == 'simple'}
    lapskojs = _scaled(active['smako-swedish-lapskojs'], 1)
    text = ' '.join(lapskojs.instructions)
    assert '21,25 ml vatten (hett)' in text and 'de två corned beef' not in text
    jansson = _scaled(active['smako-swedish-janssons-frestelse'], 1)
    assert 'väg den angivna avrunna mängden' in ' '.join(jansson.instructions)
    assert '158 g' not in ' '.join(jansson.instructions)
    cacio = _scaled(active['smako-italian-pasta-cacio-pepe'], 1)
    assert '75 ml vatten från pastakoket' in ' '.join(cacio.instructions)
    assert '20 ml vatten från pastakoket, ljummet' in ' '.join(cacio.instructions)
    hock = _scaled(active['smako-swedish-flasklagg-rotmos'], 8)
    assert '800 ml vatten från läggkoket' in ' '.join(hock.instructions)
    assert 'satser om 4 portioner' in hock.instructions[0]


def test_whole_piece_batches_are_filtered_before_scaling_in_all_candidate_paths():
    limited = {identity(r) for r in current_recipes() if r.design.servings_multiple}
    assert len(limited) == 6
    prefs = RecipePreferences(mode='complete', min_ingredients=3, max_ingredients=20)
    for servings in (1, 2, 5, 4, 8, 12):
        paths = [candidates(prefs, servings), _registered_historical_portions(servings)]
        if servings <= 8:  # Personal meal settings retain their existing maximum.
            meal = MealSettings(count=1, servings=servings, recipe_choices={'min_ingredients': 1, 'max_ingredients': 40})
            paths.append(meal_candidates(meal, prefs))
        for rows in paths:
            found = {identity(r) for r in rows} & limited
            assert found == (limited if servings % 4 == 0 else set())


def test_legacy_optional_design_field_stays_out_of_serialized_content():
    old = next(r for r in current_recipes() if r.design.version == '1.0.0')
    assert old.design.servings_multiple is None
    assert 'servings_multiple' not in old.design.model_dump()
