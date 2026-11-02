"""Bind accepted recipes, untouched issued history and remaining intake decisions."""
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from admit_expansion_round3_20261102 import OUTPUT, REPORT, SOURCE, STAGES, sha
from app.services.meal_library_content import ROOT, encoded, identity, load_entries
from app.services.recipe_authoring import library_vocabulary
from app.services.recipe_library import current_recipes
from audit_expansion_queue import audit
from coverage_reference import checked_additive_transition, imported_recipes

BASE = 'c62ba6a4e4f38a393d1bad4a0dc2692c2d33e4a3'


def main():
    current = current_recipes()
    active = {identity(r): r.design.content_sha256 for r in current}
    previous = json.loads(Path('docs/reviews/recipe-unblock-round2-20261101/queue.json').read_bytes())
    accepted = {r['source_id']: r for r in previous['variants'] if r['status'] == 'imported_reviewed_version'}
    records, proofs = [], []
    modes = {mode: Counter() for mode in ('exact', 'estimated')}
    scope = None
    for stage in STAGES:
        review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
        receipt = json.loads((REPORT / f'import-stage{stage}.json').read_bytes())
        raw = (REPORT / f'qualification-stage{stage}.json').read_bytes()
        probe = json.loads(raw)
        pack = (OUTPUT / f'standardized-stage{stage}.json').read_bytes()
        assert receipt['basket_status'] == 'verified_estimated'
        assert sha(pack) == review['pack_sha256'] == receipt['pack_sha256'] == probe['pack_sha256']
        assert sha(raw) == receipt['qualification_sha256']
        assert probe['scope']['manifest_sha256'] == receipt['after_manifest_sha256']
        assert not probe['input_only'] and probe['deadline_seconds'] == 20
        stable = {k: probe['scope'][k] for k in ('clock', 'conditions', 'facts_sha256', 'universe_sha256',
            'max_stores', 'pantry', 'servings', 'store_ids', 'imported_reference_ids_sha256', 'recipe_ids_sha256')}
        if scope is None:
            scope = stable
        assert stable == scope
        expected = {r['runtime_id']: r['content_sha256'] for r in review['recipes']}
        assert all(active[key] == value for key, value in expected.items())
        for mode, counts in modes.items():
            rows = probe['modes'][mode]['recipes']
            assert len(rows) == len(expected) and {r['id'] for r in rows} == expected.keys()
            counts.update(r['status'] for r in rows)
            if mode == 'estimated':
                assert all(r['status'] == 'verified' and r['audit']['passed'] for r in rows)
        for row in review['recipes']:
            assert row['source_id'] not in accepted
            assert sha((SOURCE / row['source_file']).read_bytes()) == row['source_sha256']
            accepted[row['source_id']] = row
        records.extend(review['recipes'])
        proofs.append({'stage': stage, 'variants': len(expected), 'pack_sha256': sha(pack), 'qualification_sha256': sha(raw)})
    before_raw = subprocess.check_output(['git', 'show', BASE + ':backend/app/data/recipes/library-manifest.json'])
    before = json.loads(before_raw)
    after_raw = (ROOT / 'library-manifest.json').read_bytes()
    after = json.loads(after_raw)
    old = {identity(r): r.design.content_sha256 for r in load_entries(before['current'] + before['history'])}
    new = {identity(r): r.design.content_sha256 for r in load_entries(after['current'] + after['history'])}
    assert all(new[k] == v for k, v in old.items())
    previous_active = current_recipes(generation=len(before['current']))
    transition = {'base_commit': BASE, 'before_manifest_file_sha256': sha(before_raw), 'after_manifest_file_sha256': sha(after_raw),
        'before_manifest': before, 'after_manifest': after, 'added_entries': after['current'][len(before['current']):],
        'corrected': [], 'added': [{'runtime_id': k, 'content_sha256': v} for k, v in new.items() if k not in old],
        'preserved_issued_variants': len(old), 'preserved_active_variants': len(previous_active)}
    checked_additive_transition(transition)
    assert {r['runtime_id'] for r in transition['added']} == {r['runtime_id'] for r in records}
    (REPORT / 'library-transition.json').write_bytes(encoded(transition))
    queue, _ = audit(SOURCE, library_vocabulary(current))
    assert accepted.keys() <= {r['source_id'] for r in queue['variants']}
    prior = {r['source_id']: r for r in previous['variants']}
    for row in queue['variants']:
        row['source_native_status'] = row.pop('status')
        if row['source_id'] in accepted:
            record = accepted[row['source_id']]
            assert active[record['runtime_id']] == record['content_sha256']
            row.update(status='imported_reviewed_version', runtime_id=record['runtime_id'], content_sha256=record['content_sha256'])
        elif row['source_id'] in prior:
            row.update(prior[row['source_id']])
        else:
            row['status'] = 'pending_register_or_authoring'
            row.setdefault('reason', 'Native compatibility is not content or full-basket approval; see pending-known-inputs.json.')
            if 'mysore-pak' in row['base_id']:
                row['reason'] = 'Tiny hot-sugar batch, equipment and reliable minimum batch size still need practical review; not admitted solely because products resolve.'
    pending = [r for r in queue['variants'] if r['status'] != 'imported_reviewed_version']
    queue['status'] = dict(Counter(r['status'] for r in queue['variants']))
    queue['ranked_register_blockers'] = [
        {**r, 'source_ids': sorted(set(r['source_ids']) - accepted.keys()), 'variants': len(set(r['source_ids']) - accepted.keys()),
         'only_register_blocker': sum(p['unknown_ingredients'] == [r['identity']] for p in pending)}
        for r in queue['ranked_register_blockers'] if set(r['source_ids']) - accepted.keys()]
    queue['ranked_register_blockers'].sort(key=lambda r: (-r['variants'], r['identity']))
    (REPORT / 'queue.json').write_bytes(encoded(queue))
    received_by_base, admitted_by_base = defaultdict(set), defaultdict(set)
    for r in queue['variants']:
        received_by_base[r['base_id']].add(r['source_id'])
        if r['source_id'] in accepted:
            admitted_by_base[r['base_id']].add(r['source_id'])
    refs, _ = imported_recipes()
    summary = {'received_bases': len(received_by_base), 'received_variants': len(queue['variants']),
        'newly_imported_variants': len(records), 'newly_imported_bases': len({r.design.base_id for r in current}) - len({r.design.base_id for r in previous_active}),
        'current_bases': len({r.design.base_id for r in current}), 'current_variants': len(current),
        'total_incoming_imported_variants': len(accepted), 'total_incoming_bases_with_import': len(admitted_by_base),
        'whole_incoming_families_imported': sum(ids == admitted_by_base.get(base) for base, ids in received_by_base.items()),
        'partly_imported_incoming_families': sum(ids != received_by_base[base] for base, ids in admitted_by_base.items()),
        'pending_variants': len(pending), 'preserved_issued_variants': len(old), 'preserved_active_variants': len(previous_active),
        'original_reference_ids': len(refs), 'basket_modes_new_variants': {m: dict(c) for m, c in modes.items()},
        'stages': proofs, 'scope': scope, 'cooking_test': 'not_cooked', 'beta_activation': False, 'warm_menu_timing': False,
        'deliveries': {delivery: {'received_variants': len(rows), 'received_bases': len({r['base_id'] for r in rows}),
            'imported_variants': sum(r['source_id'] in accepted for r in rows), 'pending_variants': sum(r['source_id'] not in accepted for r in rows)}
            for delivery in sorted({r['source_file'].split('/')[0] for r in queue['variants']})
            for rows in [[r for r in queue['variants'] if r['source_file'].split('/')[0] == delivery]]}}
    (REPORT / 'summary.json').write_bytes(encoded(summary))
    print({k: v for k, v in summary.items() if k not in {'stages', 'scope'}}, flush=True)


if __name__ == '__main__':
    main()
