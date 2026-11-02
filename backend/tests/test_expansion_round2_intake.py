"""Reviewed recipes preserve source bytes, published identities and basket scope."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from app.services.meal_library_content import (
    ROOT,
    encoded,
    identity,
    load_entries,
    manifest_entries,
    validate_pack_bytes,
)
from app.services.recipe_library import current_recipes

REPORT = Path('docs/reviews/recipe-unblock-round2-20261101')
AUTHORED = ROOT / 'reviewed-expansion-round2-20261101'
SOURCE = ROOT / 'incoming/authoring-1000-20261101'


@pytest.fixture
def scripts(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def test_new_stage_preflight_catches_unscaled_water_before_issue(scripts):
    from admit_expansion_round2_20261101 import check_process_water

    current = current_recipes()
    pindi = next(r for r in current if r.design.base_id == 'smako-indian-pindi-chole')
    check_process_water([pindi])
    step = pindi.design.steps[0].model_copy(update={'scalable_amounts': (), 'text': 'Blötlägg i 1200 ml kallt vatten.'})
    design = pindi.design.model_copy(update={'steps': (step, *pindi.design.steps[1:])})
    broken = pindi.model_copy(update={'design': design})
    with pytest.raises(ValueError, match='so it scales'):
        check_process_water([broken])


def test_review_search_finds_spaced_labels_without_approving_fresh_or_dried_identity(scripts):
    from review_product_search import review_search_key, review_search_matches

    queries = [review_search_key(q) for q in ('makrut', 'limeblad', 'kaffir')]
    assert review_search_matches(review_search_key('Lime Blad Torkade'), queries)
    assert review_search_matches(review_search_key('Lime-blad Torkade'), queries)
    assert not review_search_matches(review_search_key('Limejuice'), queries)
    assert not review_search_matches(review_search_key('Lime Blad Torkade'), [''])
    ledger = json.loads((REPORT / 'ingredient-blockers.json').read_bytes())
    leaf = next(r for r in ledger['blockers'] if r['identity'] == 'makrutlimeblad|raw_edible')
    assert leaf['retrieved_product_rows'] == 2
    assert leaf['status'] == 'pending_source_form_or_content_review'
    assert 'färska blad' in leaf['reason']


def test_each_issued_stage_matches_reviewed_source_changes_and_complete_basket_proof(scripts):
    from admit_expansion_round2_20261101 import amount_changes

    manifest = manifest_entries()
    issued = {identity(r): r for r in load_entries(manifest['current'] + manifest['history'])}
    accepted = set()
    for stage in (*range(1, 34), *range(35, 61)):
        authors = json.loads((AUTHORED / f'authoring-stage{stage}.json').read_bytes())['recipes']
        raw = (AUTHORED / f'standardized-stage{stage}.json').read_bytes()
        review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
        receipt = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        proof_raw = (REPORT / f'qualification-stage{stage}.json').read_bytes()
        proof = json.loads(proof_raw)
        checked = validate_pack_bytes(raw)
        assert not checked['rejections']
        assert sha(raw) == review['pack_sha256'] == receipt['pack_sha256'] == proof['pack_sha256']
        assert receipt['idempotent_reimport'] and receipt['basket_status'] == 'verified_estimated'
        assert receipt['qualification_sha256'] == sha(proof_raw) and not proof['input_only']
        assert proof['scope']['max_stores'] == 2 and proof['deadline_seconds'] == 20
        assert len(authors) == len(review['recipes']) == len(checked['recipes'])
        ids = set()
        for author, record in zip(authors, review['recipes'], strict=True):
            source_path = SOURCE / record['source_file']
            assert sha(source_path.read_bytes()) == record['source_sha256']
            original = next(r for r in json.loads(source_path.read_bytes())['recipes']
                            if ':'.join(r[k] for k in ('base_id', 'version', 'variant_id')) == record['source_id'])
            assert json.loads(encoded(amount_changes(original, author))) == record['amount_changes']
            assert record['source_id'] not in accepted
            accepted.add(record['source_id'])
            ids.add(record['runtime_id'])
            recipe = issued[record['runtime_id']]
            assert recipe.design.content_sha256 == record['content_sha256']
            assert recipe.design.provenance.cooking_test == record['cooking_test'] == 'not_cooked'
        baskets = proof['modes']['estimated']['recipes']
        assert {r['id'] for r in baskets} == ids and len(baskets) == len(ids)
        assert all(r['status'] == 'verified' and r['audit']['passed'] for r in baskets)
    assert len(accepted) == 252


def test_every_received_identity_has_one_final_decision_and_old_imports_are_retained():
    queue = json.loads((REPORT / 'queue.json').read_bytes())
    summary = json.loads((REPORT / 'summary.json').read_bytes())
    rows = queue['variants']
    assert len(rows) == len({r['source_id'] for r in rows}) == 501
    assert len({r['base_id'] for r in rows}) == 189
    assert sum(r['status'] == 'imported_reviewed_version' for r in rows) == 360
    assert sum(r['status'] == 'pending_qualified_input' for r in rows) == 20
    assert summary['newly_imported_variants'] == 252
    assert summary['newly_imported_bases'] == 97
    assert summary['current_variants'] == 2822 and summary['current_bases'] == 1072
    assert summary['preserved_issued_variants'] == 3625
    assert summary['original_reference_ids'] == 2200
    assert summary['corrected_new_versions'] == 77 and summary['corrected_current_variants'] == 74
    assert summary['rejected_local_versions'] == 1
    assert summary['batch_limited_variants'] == 6
    assert not summary['beta_activation'] and summary['cooking_test'] == 'not_cooked'
    active = {identity(r): r for r in current_recipes()}
    for row in rows:
        if row['status'] == 'imported_reviewed_version':
            assert active[row['runtime_id']].design.content_sha256 == row['content_sha256']
        if row['status'] == 'pending_qualified_input':
            assert row['input_blocks'] and all(b['code'] == 'DATA_BLOCKED' for b in row['input_blocks'])
        if row['status'] == 'pending_register_or_authoring':
            assert row['reason']


def test_fifth_delivery_retains_its_actual_counts_and_all_source_bytes():
    root = SOURCE / 'continuation-24/source'
    manifest = json.loads((root / 'SOURCE-MANIFEST.json').read_bytes())
    for file in manifest['preserved_files']:
        raw = (root / file['path']).read_bytes()
        assert len(raw) == file['bytes'] and sha(raw) == file['sha256']
    recipes = [r for path in sorted((root / 'paket').glob('*.json'))
               for r in json.loads(path.read_bytes())['recipes']]
    assert len(recipes) == 62 and len({r['base_id'] for r in recipes}) == 24


def test_second_additive_transition_preserves_old_content_and_original_comparison(scripts):
    from coverage_reference import (
        checked_additive_transition,
        digest,
        imported_recipes,
        reviewed_recipe_transition,
    )

    review = json.loads((REPORT / 'library-transition.json').read_bytes())
    previous = json.loads(Path('docs/reviews/recipe-unblock-20261101/library-transition.json').read_bytes())
    assert previous['after_manifest_file_sha256'] == review['before_manifest_file_sha256']
    assert checked_additive_transition(review) == review
    assert review['preserved_active_variants'] == 2570
    refs, recipes = imported_recipes()
    ids = [identity(r) for r in recipes]
    assert len(refs) == len(ids) == 2200 and review['corrected'] == []
    before = {'manifest_sha256': previous['before_manifest_file_sha256'], 'recipe_ids_sha256': digest(ids)}
    after = {**before, 'manifest_sha256': review['after_manifest_file_sha256']}
    assert reviewed_recipe_transition(before, after, [{'current_id': i} for i in ids]) == ids
    for bad in ('before_manifest_file_sha256', 'after_manifest_file_sha256'):
        with pytest.raises(ValueError, match='unreviewed additive manifest'):
            checked_additive_transition({**review, bad: 'unreviewed'})
    mutated = copy.deepcopy(review)
    mutated['added'][0]['content_sha256'] = 'changed'
    with pytest.raises(ValueError, match='unreviewed additive recipes'):
        checked_additive_transition(mutated)
    mutated = copy.deepcopy(review)
    mutated['after_manifest']['current'].pop(0)
    with pytest.raises(ValueError, match='unreviewed additive manifest'):
        checked_additive_transition(mutated)
    for change in ('baseline', 'hash', 'successor', 'duplicate', 'unexplained'):
        mutated = copy.deepcopy(review)
        row = mutated['superseded_new_versions'][0]
        if change == 'baseline':
            old_id = ids[0]
            mutated['new_revocations'][old_id] = 'Unauthorized baseline revocation'
            mutated['after_manifest']['revocations'][old_id] = 'Unauthorized baseline revocation'
        elif change == 'hash':
            row['previous_content_sha256'] = 'changed'
        elif change == 'successor':
            row['runtime_id'] = ids[0]
        elif change == 'duplicate':
            mutated['superseded_new_versions'].append(copy.deepcopy(row))
        else:
            mutated['superseded_new_versions'].pop()
        mutated['after_manifest_file_sha256'] = sha(encoded(mutated['after_manifest']))
        with pytest.raises(ValueError, match='unreviewed new-version revocations'):
            checked_additive_transition(mutated)
    corrections = {r['previous_id']: r for r in review['superseded_new_versions']}
    chained = [r for r in corrections.values() if r['runtime_id'] in corrections]
    assert len(chained) == 3  # 1.0.1 -> 1.0.2 -> 1.0.3, all bytes retained.
    mutated = copy.deepcopy(review)
    first = chained[0]
    second = next(r for r in mutated['superseded_new_versions'] if r['previous_id'] == first['runtime_id'])
    second.update(runtime_id=first['previous_id'], content_sha256=first['previous_content_sha256'])
    with pytest.raises(ValueError, match='unreviewed new-version revocations'):
        checked_additive_transition(mutated)


def test_unqualified_stage_cannot_be_finalized(scripts, tmp_path, monkeypatch):
    import admit_expansion_round2_20261101 as admission

    stage = 21
    original = json.loads((REPORT / f'qualification-stage{stage}.json').read_bytes())
    monkeypatch.setattr(admission, 'REPORT', tmp_path)
    for name in (f'recipe-review-stage{stage}.json', f'import-stage{stage}.json'):
        (tmp_path / name).write_bytes((REPORT / name).read_bytes())
    receipt_before = (tmp_path / f'import-stage{stage}.json').read_bytes()
    for problem in ('input_only', 'pack', 'timeout', 'audit', 'missing_id'):
        probe = copy.deepcopy(original)
        if problem == 'input_only':
            probe['input_only'] = True
        elif problem == 'pack':
            probe['pack_sha256'] = 'other'
        elif problem == 'timeout':
            probe['modes']['estimated']['recipes'][0]['status'] = 'timeout'
        elif problem == 'audit':
            probe['modes']['estimated']['recipes'][0]['audit']['passed'] = False
        else:
            probe['modes']['estimated']['recipes'].pop()
        path = tmp_path / 'probe.json'
        path.write_bytes(encoded(probe))
        with pytest.raises(AssertionError):
            admission.admit(stage, path)
        assert (tmp_path / f'import-stage{stage}.json').read_bytes() == receipt_before
    with pytest.raises(ValueError, match='already issued and immutable'):
        admission.build(stage)


def test_rejected_local_stage_is_hash_bound_and_never_changes_old_reference_scope(scripts):
    from coverage_reference import checked_additive_transition

    review = json.loads((REPORT / 'library-transition.json').read_bytes())
    row, = review['rejected_new_versions']
    assert row['runtime_id'] == 'smako-thai-khao-tom-mat:1.0.1:simple'
    assert row['runtime_id'] not in {identity(r) for r in current_recipes()}
    assert checked_additive_transition(review) == review
    for change in ('hash', 'proof_hash', 'proof_path', 'duplicate', 'unexplained', 'reason'):
        mutated = copy.deepcopy(review)
        rejected = mutated['rejected_new_versions'][0]
        if change == 'hash':
            rejected['content_sha256'] = 'changed'
        elif change == 'proof_hash':
            rejected['qualification_sha256'] = 'changed'
        elif change == 'proof_path':
            rejected['qualification_path'] = 'ci/coverage-reference.json'
        elif change == 'duplicate':
            mutated['rejected_new_versions'].append(copy.deepcopy(rejected))
        elif change == 'unexplained':
            mutated['rejected_new_versions'] = []
        else:
            rejected['reason'] = ''
        with pytest.raises(ValueError, match='unreviewed'):
            checked_additive_transition(mutated)
