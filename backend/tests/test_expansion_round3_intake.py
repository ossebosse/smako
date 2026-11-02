"""The next small delivery preserves history, quantity bases and truthful gates."""
import copy
import hashlib
import json
import re
from pathlib import Path

import pytest
from app.services.meal_library_content import ROOT, identity, validate_pack_bytes
from app.services.recipe_library import _scaled, current_recipes, validate_recipe_design

from backend.tests.recipe_language_history import (
    assert_current_language_version,
    current_language_cohort,
)

REPORT = Path('docs/reviews/recipe-unblock-round3-20261102')
AUTHORED = ROOT / 'reviewed-expansion-round3-20261102'
SOURCE = ROOT / 'incoming/authoring-1000-20261101'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def test_sixth_delivery_and_decisions_preserve_actual_bytes_counts_and_old_acceptances():
    source = SOURCE / 'continuation-21/source'
    manifest = json.loads((source / 'SOURCE-MANIFEST.json').read_bytes())
    assert manifest['counts'] == {'base_dishes': 21, 'recipe_variants': 55, 'authoring_packs': 3}
    assert len(manifest['preserved_files']) == 35
    for item in manifest['preserved_files']:
        raw = (source / item['path']).read_bytes()
        assert len(raw) == item['bytes'] and sha(raw) == item['sha256']
    queue = json.loads((REPORT / 'queue.json').read_bytes())
    rows = {r['source_id']: r for r in queue['variants']}
    assert len(rows) == len(queue['variants']) == 556
    assert len({r['base_id'] for r in rows.values()}) == 210
    prior = json.loads(Path('docs/reviews/recipe-unblock-round2-20261101/queue.json').read_bytes())
    for row in prior['variants']:
        if row['status'] == 'imported_reviewed_version':
            assert rows[row['source_id']]['runtime_id'] == row['runtime_id']
            assert rows[row['source_id']]['content_sha256'] == row['content_sha256']
    summary = json.loads((REPORT / 'summary.json').read_bytes())
    assert summary['newly_imported_variants'] == 20 and summary['newly_imported_bases'] == 8
    assert summary['pending_variants'] == 176 and summary['total_incoming_imported_variants'] == 380
    assert summary['deliveries']['continuation-21']['pending_variants'] == 35
    assert not summary['beta_activation'] and not summary['warm_menu_timing']
    assert summary['cooking_test'] == 'not_cooked'


def test_every_new_version_has_exact_source_review_and_full_estimated_basket():
    accepted = set()
    for stage in (1, 2, 3):
        raw = (AUTHORED / f'standardized-stage{stage}.json').read_bytes()
        checked = validate_pack_bytes(raw)
        assert not checked['rejections']
        review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
        receipt = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        probe_raw = (REPORT / f'qualification-stage{stage}.json').read_bytes()
        probe = json.loads(probe_raw)
        assert sha(raw) == review['pack_sha256'] == receipt['pack_sha256'] == probe['pack_sha256']
        assert sha(probe_raw) == receipt['qualification_sha256']
        assert receipt['basket_status'] == 'verified_estimated' and receipt['idempotent_reimport']
        assert probe['scope']['manifest_sha256'] == receipt['after_manifest_sha256']
        assert not probe['input_only'] and probe['deadline_seconds'] == 20
        expected = {identity(r) for r in checked['recipes']}
        assert not expected & accepted
        accepted |= expected
        results = probe['modes']['estimated']['recipes']
        assert len(results) == len(expected) and {r['id'] for r in results} == expected
        assert all(r['status'] == 'verified' and r['audit']['passed'] for r in results)
        for row in review['recipes']:
            assert sha((SOURCE / row['source_file']).read_bytes()) == row['source_sha256']
            assert_current_language_version(row['runtime_id'], row['content_sha256'])
            assert row['cooking_test'] == 'not_cooked'
    assert len(accepted) == 20


@pytest.mark.parametrize('servings', [1, 4, 12])
def test_all_new_recipes_scale_food_process_water_and_keep_temperatures(servings):
    new = current_language_cohort('reviewed-expansion-round3-')
    assert len(new) == 20
    for recipe in new:
        scaled = _scaled(recipe, servings)
        assert validate_recipe_design(scaled)
        for original, changed in zip(recipe.ingredients, scaled.ingredients, strict=True):
            assert changed.quantity == pytest.approx(original.quantity * servings / recipe.servings)
            assert changed.unit == original.unit and changed.product_requirements == original.product_requirements
        for original, changed in zip(recipe.design.steps, scaled.design.steps, strict=True):
            for _, amount in original.scalable_amounts or ():
                assert f'{amount * servings / recipe.servings:g} ml'.replace('.', ',') in changed.text
            for fixed in re.findall(r'\d+ (?:°C|cm)\b', original.text):
                assert fixed in changed.text


def test_fish_losses_follow_thaw_insertion_and_egg_mixing_follows_cooling():
    for recipe in current_recipes():
        if recipe.design.base_id != 'smako-swedish-fiskpudding-ris-mjolk':
            continue
        assert recipe.preparation.version == 'smako-authored-losses-v3'
        steps = {s.id: s for s in recipe.design.steps}
        assert recipe.design.waiting_minutes >= 720
        processes = recipe.design.unmeasured_processes
        fish = next(p for p in processes if 'fisk|raw_edible' in p.ingredient_keys)
        assert fish.operation == 'drain_after_cooking' and fish.step_id == 's5'
        assert 'Häll bort kokspadet.' in steps[fish.step_id].text
        assert 'högst 25 °C' in steps['s7'].text and 'utan skal' in steps['s7'].text
        assert 'minst 72 °C' in steps['s9'].text
        assert any('ärtor|as_sold' in p.ingredient_keys and p.step_id == 's9' for p in processes)
        if recipe.design.variant_id != 'simple':
            assert any('dill|raw_edible' in p.ingredient_keys for p in processes)


def test_substitutions_remain_explicit_and_do_not_become_false_ingredient_aliases():
    recipes = current_recipes()
    pie = next(r for r in recipes if r.design.base_id == 'smako-greek-kolokithopita-sot-pumpapaj' and r.design.variant_id == 'extended')
    ingredients = {i.canonical_name: i for i in pie.ingredients}
    assert 'apelsinskal' not in ingredients and ingredients['kanderade apelsinskal'].quantity == 5
    assert ingredients['strösocker'].quantity == 10 and 'kanderat' in pie.name
    for recipe in recipes:
        if recipe.design.base_id == 'smako-italian-pallotte-cacio-uova':
            ingredients = {i.canonical_name: i for i in recipe.ingredients}
            assert 'pecorino romano' not in ingredients and ingredients['lagrad pecorino'].quantity == 140
            assert any(p.operation == 'trim_before_cooking' for p in recipe.design.unmeasured_processes)
        if recipe.design.base_id == 'smako-mexican-coyotas-piloncillo':
            ingredients = {i.canonical_name: i for i in recipe.ingredients}
            assert 'piloncillo' not in ingredients and ingredients['mörkt muscovadosocker'].quantity == 18
            text = ' '.join(_scaled(recipe, 4).instructions)
            assert '8 ml vatten' in text and 'per vald portion' in text and 'muscovado' in recipe.name


def test_additive_edge_preserves_original_2200_and_rejects_unreviewed_changes(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('scripts/recipe_layer').resolve()))
    from coverage_reference import (
        checked_additive_transition,
        digest,
        imported_recipes,
        reviewed_recipe_transition,
    )

    transition = json.loads((REPORT / 'library-transition.json').read_bytes())
    previous = json.loads(Path('docs/reviews/recipe-unblock-round2-20261101/library-transition.json').read_bytes())
    assert previous['after_manifest_file_sha256'] == transition['before_manifest_file_sha256']
    assert checked_additive_transition(transition) == transition
    assert transition['preserved_active_variants'] == 2822
    assert transition['preserved_issued_variants'] == 3955
    refs, recipes = imported_recipes()
    ids = [identity(r) for r in recipes]
    assert len(refs) == len(ids) == 2200
    before = {'manifest_sha256': previous['before_manifest_file_sha256'], 'recipe_ids_sha256': digest(ids)}
    after = {**before, 'manifest_sha256': transition['after_manifest_file_sha256']}
    assert reviewed_recipe_transition(before, after, [{'current_id': key} for key in ids]) == ids
    broken = copy.deepcopy(transition)
    broken['added'][0]['content_sha256'] = 'unreviewed'
    with pytest.raises(ValueError, match='unreviewed additive recipes'):
        checked_additive_transition(broken)


def test_pending_screen_covers_all_176_without_turning_resolved_inputs_into_approval(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('scripts/recipe_layer').resolve()))
    from screen_pending_recipe_inputs import summarize

    raw = (REPORT / 'queue.json').read_bytes()
    queue = json.loads(raw)
    report = json.loads((REPORT / 'pending-known-inputs.json').read_bytes())
    pending = {r['source_id'] for r in queue['variants'] if r['status'] != 'imported_reviewed_version'}
    assert len(pending) == len(report['variants']) == 176
    assert {r['source_id'] for r in report['variants']} == pending
    assert report['queue_sha256'] == sha(raw)
    assert report['status'] == {'known_inputs_blocked': 81, 'known_inputs_resolved_only': 95}
    assert all(not r['recipe_approved'] and not r['basket_checked'] for r in report['variants'])
    assert summarize(copy.deepcopy(report)) == report
    mysore = [r for r in queue['variants'] if 'mysore-pak' in r['base_id']]
    assert len(mysore) == 2 and all(r['status'] == 'pending_register_or_authoring' for r in mysore)
