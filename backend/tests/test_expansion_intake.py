"""Received bytes, reviewed content, and old coverage identities stay separate."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from app.services.meal_library_content import ROOT, encoded, identity, validate_pack_bytes
from app.services.recipe_authoring import library_vocabulary
from app.services.recipe_library import current_recipes

REPORT = Path('docs/reviews/recipe-unblock-20261101')
AUTHORED = ROOT / 'reviewed-expansion-20261101'
SOURCE = ROOT / 'incoming/authoring-1000-20261101'


@pytest.fixture
def scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))


def test_all_admitted_variants_keep_original_quantities_and_reviewed_hashes():
    review = json.loads((REPORT / 'recipe-review.json').read_bytes())
    authors = json.loads((AUTHORED / 'authoring.json').read_bytes())['recipes']
    active = {identity(r): r for r in current_recipes()}
    assert len(review['recipes']) == len(authors) == 108
    assert len({r['base_id'] for r in authors}) == 41
    for author, record in zip(authors, review['recipes'], strict=True):
        path = SOURCE / record['source_file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == record['source_sha256']
        original = next(r for r in json.loads(path.read_bytes())['recipes']
                        if ':'.join(r[k] for k in ('base_id', 'version', 'variant_id')) == record['source_id'])
        amounts = lambda r: [[(i['name'], i['quantity'], i['unit'], i['form'])
                              for i in c['ingredients']] for c in r['components']]
        assert amounts(author) == amounts(original)
        assert active[record['runtime_id']].design.content_sha256 == record['content_sha256']
        assert active[record['runtime_id']].design.provenance.cooking_test == 'not_cooked'


def test_reviewed_preparation_is_in_the_recipe_and_not_only_a_registry_tag():
    from app.services.egg_preparation import OPERAND

    rows = json.loads((AUTHORED / 'authoring.json').read_bytes())['recipes']
    for row in rows:
        base = row['base_id']
        text = ' '.join(s['text'] for s in row['steps'])
        items = [i for c in row['components'] for i in c['ingredients']]
        if base.endswith(('wallenbergare', 'biff-greta')):
            assert 'separera gula och vita' in text and 'uppskattning' in text
            assert all(OPERAND in i['requirements'] for i in items if i['name'] == 'äggula')
        if base.endswith('ma-hor'):
            assert 'upptiningssaft' in text and 'ingen iskärna' in text
            assert any(s.get('passive') and s['minutes'] == 720 for s in row['steps'])
        if base.endswith('mandelmusslor'):
            assert 'hallonkompott' in row['name'] and 'minst en minut' in text
            assert 'Skölj och torka hallonen' not in text
        if base.endswith('spaghetti-assassina'):
            assert all('pack:spaghetti' in i['requirements'] for i in items if i['name'] == 'pasta')


@pytest.mark.parametrize('name', ['fläskkarré', 'kalvfärs', 'nötinnanlår', 'högrev', 'nötstek',
                                 'nötkött för snabbstekning', 'hel kyckling', 'rimmat fläsk'])
@pytest.mark.parametrize('method', ['salad', 'cold_assembly', 'refrigerated_assembly'])
def test_expansion_raw_animal_inputs_require_a_hot_method(name, method):
    pack = json.loads((AUTHORED / 'standardized.json').read_bytes())
    recipe = next(r for r in pack['recipes'] if r['design']['base_id'].endswith('plommonspackad-flaskkarre'))
    recipe['design']['method'] = method
    ingredient = next(i for i in recipe['ingredients'] if i['canonical_name'] == 'fläskkarré')
    ingredient.update(name=name, canonical_name=name)
    result = validate_pack_bytes(encoded({**pack, 'recipes': [recipe]}))
    assert not result['recipes']
    assert 'rå animalisk ingrediens kräver varm metod' in result['rejections'][0]['reason']


def delivery(tmp_path, *, duplicate=False):
    row = next(r for r in json.loads((AUTHORED / 'authoring.json').read_bytes())['recipes']
               if r['base_id'].endswith('fasolada'))
    directory = tmp_path / 'batch/source'
    (directory / 'paket').mkdir(parents=True)
    raw = encoded({'schema_version': 'smako-recipe-authoring-v1', 'pack_id': 'test', 'recipes': [row]})
    entries = []
    for name in (['one.json', 'two.json'] if duplicate else ['one.json']):
        path = directory / 'paket' / name
        path.write_bytes(raw)
        entries.append({'path': 'paket/' + name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    (directory / 'SOURCE-MANIFEST.json').write_bytes(encoded({'preserved_files': entries}))
    return directory / 'paket/one.json'


def test_queue_recounts_without_approving_or_changing_originals(scripts, tmp_path):
    from audit_expansion_queue import audit

    path = delivery(tmp_path)
    before = path.read_bytes()
    manifest = (ROOT / 'library-manifest.json').read_bytes()
    report, compatible = audit(tmp_path, library_vocabulary(current_recipes()))
    assert report['received_variants'] == len(compatible) == 1
    assert report['status'] == {'native_compatible_not_approved': 1}
    assert path.read_bytes() == before
    assert (ROOT / 'library-manifest.json').read_bytes() == manifest


@pytest.mark.parametrize('problem', ['changed', 'unmanifested', 'duplicate'])
def test_queue_fails_closed_on_unbound_or_duplicate_sources(scripts, tmp_path, problem):
    from audit_expansion_queue import audit

    path = delivery(tmp_path, duplicate=problem == 'duplicate')
    if problem == 'changed':
        path.write_bytes(path.read_bytes() + b' ')
    elif problem == 'unmanifested':
        (path.parent / 'unreviewed.json').write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match={'changed': 'Changed original', 'unmanifested': 'Unmanifested',
                                         'duplicate': 'Duplicate received'}[problem]):
        audit(tmp_path, library_vocabulary(current_recipes()))


def test_additive_manifest_chain_preserves_the_original_comparison(scripts):
    from coverage_reference import (
        checked_additive_transition,
        digest,
        imported_recipes,
        reviewed_recipe_transition,
    )

    review = json.loads((REPORT / 'library-transition.json').read_bytes())
    assert checked_additive_transition(review) == review
    _references, recipes = imported_recipes()
    ids = [identity(r) for r in recipes]
    before = {'manifest_sha256': review['before_manifest_file_sha256'], 'recipe_ids_sha256': digest(ids)}
    after = {**before, 'manifest_sha256': review['after_manifest_file_sha256']}
    assert reviewed_recipe_transition(before, after, [{'current_id': i} for i in ids]) == ids
    with pytest.raises(ValueError, match='unreviewed'):
        reviewed_recipe_transition(before, {**after, 'recipe_ids_sha256': digest(ids[1:])},
                                   [{'current_id': i} for i in ids])
    for field in ['before_manifest_file_sha256', 'after_manifest_file_sha256']:
        with pytest.raises(ValueError, match='unreviewed additive manifest'):
            checked_additive_transition({**review, field: 'unreviewed'})
    changed = copy.deepcopy(review)
    changed['added'][0]['content_sha256'] = 'unreviewed'
    with pytest.raises(ValueError, match='unreviewed additive recipes'):
        checked_additive_transition(changed)
    changed = copy.deepcopy(review)
    changed['after_manifest']['current'].pop(0)
    with pytest.raises(ValueError, match='unreviewed additive manifest'):
        checked_additive_transition(changed)
