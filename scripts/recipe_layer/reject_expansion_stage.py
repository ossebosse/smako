"""Retain, revoke and record an issued local stage with proven input blockers."""
import argparse
import json
from pathlib import Path

from admit_expansion_round2_20261101 import OUTPUT, REPORT, sha
from app.services.meal_library_content import ROOT, encoded, identity, revoke_recipe
from app.services.recipe_library import current_recipes


def reject(stage, qualification, reason):
    review = json.loads((REPORT / f'recipe-review-stage{stage}.json').read_bytes())
    receipt_path = REPORT / f'import-stage{stage}.json'
    receipt = json.loads(receipt_path.read_bytes())
    proof_raw = qualification.read_bytes()
    proof = json.loads(proof_raw)
    pack = (OUTPUT / f'standardized-stage{stage}.json').read_bytes()
    assert proof['pack_sha256'] == review['pack_sha256'] == receipt['pack_sha256'] == sha(pack)
    assert not proof['input_only'] and reason.strip()
    expected = {r['runtime_id']: r['content_sha256'] for r in review['recipes']}
    rows = proof['modes']['estimated']['recipes']
    assert {r['id'] for r in rows} == expected.keys() and len(rows) == len(expected)
    assert all(r['status'] == 'data_blocked' and r['input_blocks']
               and all(b['code'] == 'DATA_BLOCKED' for b in r['input_blocks']) for r in rows)
    assert receipt['basket_status'] == 'pending_local_qualification'
    active = {identity(r): r.design.content_sha256 for r in current_recipes()}
    assert all(active[key] == value for key, value in expected.items())
    target = REPORT / f'qualification-stage{stage}.json'
    target.write_bytes(proof_raw)
    before = (ROOT / 'library-manifest.json').read_bytes()
    for key in expected:
        revoke_recipe(key, reason)
    after = (ROOT / 'library-manifest.json').read_bytes()
    rejected = [{**r, 'reason': reason, 'qualification_path': target.as_posix(),
                 'standardized_pack_path': (OUTPUT / f'standardized-stage{stage}.json').relative_to(Path.cwd()).as_posix(),
                 'pack_sha256': sha(pack),
                 'qualification_sha256': sha(proof_raw)} for r in review['recipes']]
    (REPORT / f'rejected-stage{stage}.json').write_bytes(encoded({
        'stage': stage, 'recipes': rejected, 'before_manifest_sha256': sha(before),
        'after_manifest_sha256': sha(after), 'new_revocations': dict.fromkeys(expected, reason)}))
    receipt.update(basket_status='data_blocked_revoked', qualification_sha256=sha(proof_raw))
    receipt_path.write_bytes(encoded(receipt))
    print({'stage': stage, 'revoked_local_versions': len(expected), 'original_source_retained': True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', type=int, required=True)
    parser.add_argument('--qualifying-report', type=Path, required=True)
    parser.add_argument('--reason', required=True)
    args = parser.parse_args()
    reject(args.stage, args.qualifying_report, args.reason)
