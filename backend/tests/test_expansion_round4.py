"""Reviewed products and nine new recipes retain identity, amounts and history."""
import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from app.services.intake_product_links import compatible, ingredient_product
from app.services.meal_library_content import ROOT, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary
from app.services.recipe_library import _scaled, current_recipes, validate_recipe_design

from backend.tests.recipe_language_history import (
    assert_current_language_version,
    before_language_id,
    current_language_cohort,
)
from backend.tests.test_expansion_ingredients import source

REPORT = Path('docs/reviews/recipe-unblock-round4-20261102')
AUTHORED = ROOT / 'reviewed-expansion-round4-20261102'
ROWS = json.loads((ROOT.parent / 'ingredients/expansion-round4-20261102.json').read_bytes())['ingredients']


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def new_recipes():
    return current_language_cohort('reviewed-expansion-round4-')


def authoring_rows():
    return {':'.join(r[k] for k in ('base_id', 'version', 'variant_id')): r
            for path in AUTHORED.glob('authoring-stage*.json')
            for r in json.loads(path.read_bytes())['recipes']}


@pytest.mark.parametrize('row', ROWS, ids=lambda r: r['name'])
def test_reviewed_sources_reject_other_foods_units_packages_and_changed_evidence(row):
    p, f = source(row)
    key = row['requirements'][0].removeprefix('pack:')
    assert compatible(key, p, f)
    assert library_vocabulary(current_recipes())[row['name'] + '|' + row['form']] == (row['unit'], row['requirements'])
    for change in ({'name': 'Pesto Rucola'}, {'name': 'Rosvatten'}, {'store_id': 'unreviewed'},
                   {'package_quantity': p.package_quantity + 1}, {'usable_quantity': p.usable_quantity + 1},
                   {'usable_unit': 'ml' if row['unit'] == 'g' else 'g'}, {'brand': 'Other'}):
        assert not compatible(key, p.model_copy(update=change), f)
    assert not compatible(key, p, replace(f, ingredients=('Ändrat innehåll',), ingredients_complete=True))
    assert not compatible(key, p, replace(f, source_snapshot_id='unbound'))
    assert not ingredient_product('other food', row['form'], row['requirements'], p, f)


def test_only_separately_reviewed_leaf_bag_and_flower_water_are_registered():
    water, rocket = ROWS
    assert (water['name'], water['unit'], len(water['reviewed_links'])) == ('apelsinblomsvatten', 'ml', 7)
    assert all(p['name'] == 'Apelsinblom Vatten' and p['package_quantity'] == 300 for p in water['reviewed_links'])
    assert (rocket['name'], rocket['unit'], len(rocket['reviewed_links'])) == ('rucola', 'g', 8)
    assert all(p['name'] == 'Ruccola Klass 1' and p['package_quantity'] == 125 for p in rocket['reviewed_links'])
    assert all(p['retailer_product_id'] == '101316310_ST' for p in rocket['reviewed_links'])


def test_every_new_recipe_has_unchanged_source_and_hash_bound_basket_receipt():
    accepted = set()
    for stage, count in ((1, 3), (2, 2), (3, 4)):
        raw = (AUTHORED / f'standardized-stage{stage}.json').read_bytes()
        checked = validate_pack_bytes(raw)
        assert not checked['rejections'] and len(checked['recipes']) == count
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
        for r in review['recipes']:
            assert sha((ROOT / 'incoming/authoring-1000-20261101' / r['source_file']).read_bytes()) == r['source_sha256']
            assert_current_language_version(r['runtime_id'], r['content_sha256'])
    assert len(accepted) == 9


@pytest.mark.parametrize('servings', [1, 4, 12])
def test_food_process_water_and_temperature_checks_scale_as_authored(servings):
    recipes = new_recipes()
    assert len(recipes) == 9
    for recipe in recipes:
        scaled = _scaled(recipe, servings)
        assert validate_recipe_design(scaled)
        for old, new in zip(recipe.ingredients, scaled.ingredients, strict=True):
            assert new.quantity == pytest.approx(old.quantity * servings / recipe.servings)
            assert new.unit == old.unit and new.product_requirements == old.product_requirements
        for old, new in zip(recipe.design.steps, scaled.design.steps, strict=True):
            for _, amount in old.scalable_amounts or ():
                assert f'{amount * servings / recipe.servings:g} ml'.replace('.', ',') in new.text
            for temperature in ('25 °C', '72 °C', '75 °C', '175 °C', '250 °C', '4 °C'):
                if temperature in old.text:
                    assert temperature in new.text


def test_liver_and_wheat_losses_stay_unknown_and_checks_remain_active():
    authors = authoring_rows()
    for r in new_recipes():
        steps = {s.id: s for s in r.design.steps}
        authored_steps = authors[before_language_id(identity(r))]['steps']
        assert r.design.active_minutes == sum(s['minutes'] for s in authored_steps if not s.get('passive'))
        if 'magiritsa' in r.design.base_id:
            assert r.preparation.version == 'smako-authored-losses-v3'
            liver = next(i for i in r.ingredients if i.canonical_name == 'ungnötslever')
            assert liver.form == 'as_sold' and liver.quantity == 480
            assert {p.operation for p in r.design.unmeasured_processes} == {'trim_before_cooking', 'drain_after_cooking'}
            assert not authored_steps[7].get('passive') and '72 °C' in steps['s8'].text
            assert not authored_steps[9].get('passive') and '75 °C' in steps['s10'].text
            assert 'utan skal' in steps['s9'].text and 'ungnötslever' in r.name
        if 'pastiera' in r.design.base_id:
            assert r.preparation.version == 'smako-authored-losses-v3'
            assert any(p.step_id == 's3' and p.operation == 'drain_after_cooking' for p in r.design.unmeasured_processes)
            assert not authored_steps[5].get('passive') and '25 °C' in steps['s6'].text
            assert not authored_steps[8].get('passive') and '72 °C' in steps['s9'].text
            if r.design.variant_id == 'extended':
                assert any(i.canonical_name == 'kanderade apelsinskal' and i.quantity == 10 for i in r.ingredients)


def test_three_cheeses_do_not_alias_stracchino_and_frozen_basil_is_baked():
    for r in new_recipes():
        ingredients = {i.canonical_name: i for i in r.ingredients}
        if 'focaccia-formaggio' in r.design.base_id:
            assert 'stracchino' not in ingredients
            assert {k: ingredients[k].quantity for k in ('ricotta', 'färskost', 'mozzarella')} == {'ricotta': 140, 'färskost': 130, 'mozzarella': 130}
            assert ingredients['mozzarella'].form == 'preserved_drained'
            assert 'ricotta, färskost och mozzarella' in r.name
            if r.design.variant_id == 'extended':
                assert 'basilika' in r.instructions[2] and '75 °C' in r.instructions[4]
        if 'bouyiourdi' in r.design.base_id:
            assert 'kasseri' not in ingredients and ingredients['gruyère'].quantity == 20
            assert r.preparation.version == 'smako-authored-losses-v3'
            assert any(p.operation == 'trim_before_cooking' for p in r.design.unmeasured_processes)


def test_additive_history_and_queue_preserve_every_previously_accepted_recipe(monkeypatch):
    monkeypatch.syspath_prepend(str(Path('scripts/recipe_layer').resolve()))
    from coverage_reference import (
        checked_additive_transition,
        digest,
        imported_recipes,
        reviewed_recipe_transition,
    )

    transition = json.loads((REPORT / 'library-transition.json').read_bytes())
    previous = json.loads(Path('docs/reviews/recipe-unblock-round3-20261102/library-transition.json').read_bytes())
    assert previous['after_manifest_file_sha256'] == transition['before_manifest_file_sha256']
    assert transition['preserved_active_variants'] == 2842 and transition['preserved_issued_variants'] == 3975
    assert checked_additive_transition(transition) == transition
    refs, recipes = imported_recipes()
    ids = [identity(r) for r in recipes]
    assert len(refs) == len(ids) == 2200
    before = {'manifest_sha256': previous['before_manifest_file_sha256'], 'recipe_ids_sha256': digest(ids)}
    after = {**before, 'manifest_sha256': transition['after_manifest_file_sha256']}
    assert reviewed_recipe_transition(before, after, [{'current_id': k} for k in ids]) == ids
    broken = copy.deepcopy(transition)
    broken['added'][0]['content_sha256'] = 'unreviewed'
    with pytest.raises(ValueError, match='unreviewed additive recipes'):
        checked_additive_transition(broken)
    queue = json.loads((REPORT / 'queue.json').read_bytes())
    rows = {r['source_id']: r for r in queue['variants']}
    old = json.loads(Path('docs/reviews/recipe-unblock-round3-20261102/queue.json').read_bytes())
    assert len(rows) == 556
    for r in old['variants']:
        if r['status'] == 'imported_reviewed_version':
            assert rows[r['source_id']]['runtime_id'] == r['runtime_id']
            assert rows[r['source_id']]['content_sha256'] == r['content_sha256']
    assert sum(r['status'] == 'imported_reviewed_version' for r in rows.values()) == 389
    screen = json.loads((REPORT / 'pending-known-inputs.json').read_bytes())
    assert screen['queue_sha256'] == sha((REPORT / 'queue.json').read_bytes())
    pending = {r['source_id'] for r in rows.values() if r['status'] != 'imported_reviewed_version'}
    assert len(pending) == 167 and {r['source_id'] for r in screen['variants']} == pending
    assert all(not r['recipe_approved'] and not r['basket_checked'] for r in screen['variants'])
