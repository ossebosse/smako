"""Reviewed combinations enter the existing registry, never runtime free edits."""
import copy
import json
from pathlib import Path

import pytest
from app.models.personal import MealSettings
from app.models.recipe import Recipe, RecipePreparation
from app.models.recipe_preferences import RecipePreferences
from app.services import meal_library_content as content
from app.services import recipe_library as library
from app.services.flexible_recipes import expand_pack

SOURCE = Path(__file__).parents[1] / 'app/data/recipes/flexible-families-v1.json'


@pytest.fixture
def raw():
    return json.loads(SOURCE.read_bytes())


def expand(tmp_path, raw):
    path = tmp_path / 'families.json'
    path.write_bytes(content.encoded(raw))
    return expand_pack(path)


def reseal(row):
    recipe = Recipe.model_validate(row)
    sha = library.content_hash(recipe)
    row['design']['content_sha256'] = sha
    row['preparation'] = RecipePreparation(version='smako-authored-input-v2',
        origin='smako_recipe_design', parent_sha256=sha, family=recipe.design.family,
        input_forms={i.canonical_name:i.form for i in recipe.ingredients}).model_dump(mode='json')


def test_expansion_is_deterministic_bounded_and_sealed(tmp_path, raw):
    original = copy.deepcopy(raw)
    result = expand(tmp_path, raw)
    assert result == expand(tmp_path, raw) and raw == original
    assert len(result['recipes']) == sum(len(f['variants']) for f in raw['families']) == 7
    for row in result['recipes']:
        recipe = Recipe.model_validate(row)
        library._structural_check(recipe)
        assert recipe.design.provenance.cooking_test == 'not_cooked'
        assert recipe.design.content_source.sha256 == content.digest(content.encoded(raw))
        for servings in (1, 2, 4, 12):
            library._structural_check(library._scaled(recipe, servings))


@pytest.mark.parametrize('problem', ['range', 'step', 'unknown', 'double_change',
    'components', 'steps', 'duplicate', 'base_id', 'extra', 'budget', 'unchanged',
    'parent_hash', 'replacement_basis', 'primary', 'cold_raw_meat'])
def test_invalid_combinations_fail_before_publication(tmp_path, raw, problem):
    f = raw['families'][0]; v = f['variants'][0]
    if problem == 'range': v['quantities']['kikärtor|cooked_drained'] = 440
    if problem == 'step': v['quantities']['kikärtor|cooked_drained'] = 330
    if problem == 'unknown': v['quantities']['nonexistent|dry'] = 10
    if problem == 'double_change':
        f['variants'][1]['quantities']['couscous|dry'] = 100
    if problem == 'components': v['components'][0]['amounts'][0]['quantity'] = 1
    if problem == 'steps': v['steps'][0]['ingredient_keys'].append('unknown|dry')
    if problem == 'duplicate': f['variants'].append(copy.deepcopy(v))
    if problem == 'base_id': v['variant_id'] = 'base'
    if problem == 'extra': v['nutrition'] = {'protein_g': 100}
    if problem == 'budget': f['variants'] = [v] * 17
    if problem == 'unchanged': v['quantities'] = {}
    if problem == 'parent_hash': f['base']['name'] += ' edited'
    if problem == 'replacement_basis': f['variants'][1]['substitutions'][0]['replacement']['unit'] = 'ml'
    if problem == 'primary': v['cooking']['primary_ingredient'] = 'kyckling'
    if problem == 'cold_raw_meat':
        v = raw['families'][2]['variants'][1]
        replacement = v['substitutions'][0]['replacement']
        replacement.update(name='kyckling', canonical_name='kyckling', form='raw_edible')
        v['cooking']['primary_ingredient'] = 'kyckling'
        for c in v['components']:
            for a in c['amounts']:
                if a['ingredient_key'] == 'kvarg|as_sold': a['ingredient_key'] = 'kyckling|raw_edible'
        for s in v['steps']:
            s['ingredient_keys'] = ['kyckling|raw_edible' if k == 'kvarg|as_sold' else k for k in s['ingredient_keys']]
    with pytest.raises(ValueError):
        expand(tmp_path, raw)


def test_future_recipe_import_history_preferences_and_no_free_amounts(tmp_path, raw, monkeypatch):
    # Unknown future base ID, no registration code or built-in recipe edits.
    raw['families'] = [raw['families'][2]]
    family = raw['families'][0]
    family['include_base'] = True
    family['base']['design']['base_id'] = 'smako-breakfast-future-independent-family'
    reseal(family['base'])
    output = expand(tmp_path, raw)
    path = tmp_path / 'expanded.json'; path.write_bytes(content.encoded(output))
    root = tmp_path / 'registry'; root.mkdir()
    (root / content.MANIFEST.name).write_bytes(content.encoded({
        'schema_version':content.MANIFEST_SCHEMA, 'current':[], 'history':[]}))
    first = content.import_pack(path, root=root)
    before = (root / content.MANIFEST.name).read_bytes()
    content.import_pack(path, root=root)
    assert (root / content.MANIFEST.name).read_bytes() == before
    manifest = content.manifest_entries
    load = content.load_entries
    monkeypatch.setattr(content, 'manifest_entries', lambda root=root: manifest(root))
    monkeypatch.setattr(content, 'load_entries', lambda entries, root=root: load(entries, root))
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path / 'cache'))
    library.reset_library_caches()
    try:
        meal = MealSettings(meal_type='breakfast', servings=2, count=1)
        prefs = RecipePreferences(mode='complete')
        candidates = library.meal_candidates(meal, prefs)
        assert len(candidates) == 3
        assert all(library.validate_recipe_design(r) for r in candidates)
        base_only = library.meal_candidates(meal, prefs.model_copy(update={'adaptation':'products'}))
        assert [r.design.variant_id for r in base_only] == ['base']
        old = next(r for r in candidates if r.design.variant_id == 'flex-more-yoghurt')
        # A range is an authoring limit, not approval to edit an issued portion.
        changed = old.model_dump(mode='json')
        next(i for i in changed['ingredients'] if i['canonical_name'] == 'yoghurt naturell')['quantity'] = 400
        next(a for a in changed['design']['components'][0]['amounts']
             if a['ingredient_key'] == 'yoghurt naturell|as_sold')['quantity'] = 400
        reseal(changed)
        with pytest.raises(ValueError, match='granskning'):
            library.validate_recipe_design(Recipe.model_validate(changed))
        family['version'] = '1.1.0'
        family['variants'][0]['name'] += ' ny version'
        path.write_bytes(content.encoded(expand(tmp_path, raw)))
        content.import_pack(path, root=root)
        library.reset_library_caches()
        assert library.validate_recipe_design(old)
        assert next(r for r in library.meal_candidates(meal, prefs)
                    if r.design.variant_id == 'flex-more-yoghurt').design.version == '1.1.0'
        assert (root / first['published_file']).exists()
    finally:
        library.reset_library_caches()


def test_different_substitutions_and_amounts_have_distinct_computation_keys(tmp_path, raw):
    from app.services.recipe_computation_cache import RecipeComputationCache
    cache = RecipeComputationCache()
    recipes = [Recipe.model_validate(row) for row in expand(tmp_path, raw)['recipes']]
    assert len({cache.key(r) for r in recipes}) == len(recipes)
    broccoli = next(r for r in recipes if r.design.variant_id == 'flex-broccoli')
    assert cache.forms_for(broccoli, 'broccoli') == (('raw_edible', ()),)
    assert cache.forms_for(broccoli, 'morot') == ()


def test_later_family_extends_prepared_search_in_the_same_price_universe(tmp_path, raw, monkeypatch):
    from app.services import meal_prepared_artifacts as artifacts

    from backend.tests.test_personal_planning_v2 import prepared, product
    base = Recipe.model_validate(raw['families'][2]['base'])
    future = next(Recipe.model_validate(r) for r in expand(tmp_path, raw)['recipes']
                  if r['design']['variant_id'] == 'flex-quark')
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path / 'prepared'))
    monkeypatch.setattr(library, '_registered', lambda: (base,))
    monkeypatch.setattr(library, 'library_version', lambda: 'before-import')
    universe = prepared(product('Kvarg Naturell', 500, 'g', 20))
    before = artifacts.prepare_ingredient_search(universe)
    assert 'kvarg' not in before
    monkeypatch.setattr(library, '_registered', lambda: (base, future))
    monkeypatch.setattr(library, 'library_version', lambda: 'after-import')
    after = artifacts.prepare_ingredient_search(universe)
    assert after['kvarg'] == frozenset({0})
    assert all(after[name] == matches for name, matches in before.items())
    assert artifacts.prepare_ingredient_search(universe) is after
