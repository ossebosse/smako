"""Read verified native cell summaries; never run or qualify a planner."""
from __future__ import annotations

import hashlib
import itertools
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

PATH = Path('docs/reviews/preparation-memory-20261024/full-matrix-current.json')
AUDITED = 'AUDITED_PENDING_CROSS_CELL_GATES'
BLOCKED = 'OBSERVED_BLOCKED_NOT_GLOBAL_IMPOSSIBILITY'
V1 = 'smako-verified-reference-v1'
V5 = 'smako-full-library-reference-v5'
PROFILES = ('standard', 'protein40', 'all-macros', 'vegan', 'distribution',
            'organic-share', 'breakfast-snack-weight')
SIZES = (262, 1000, 2000, 5000)


def key(cell):
    return tuple(cell[field] for field in
                 ('facts_arm', 'city', 'profile', 'library_size', 'search_policy'))


def blocked_signature(cell):
    return {(row['code'], row['stage']) for row in cell['blocked_evidence']}


def write_review(output, result):
    metadata = {name: value for name, value in result.items() if name not in ('checks', 'pending')}
    lines = json.dumps(metadata, ensure_ascii=False, indent=2).splitlines()[:-1]
    lines[-1] += ','
    for name in ('checks', 'pending'):
        lines.append(f'  "{name}": [')
        rows = result[name]
        lines.extend('    '+json.dumps(row, ensure_ascii=False)+(',' if index+1 < len(rows) else '')
                     for index, row in enumerate(rows))
        lines.append('  ]'+(',' if name == 'checks' else ''))
    output.write_text('\n'.join([*lines, '}', '']), encoding='utf8')


def main():
    raw = PATH.read_bytes()
    data = json.loads(raw)
    expected = {(*arm, size, policy)
                for arm in itertools.product(('original', 'axfood_103'), ('malmo', 'lund'), PROFILES)
                for size, policy in [*itertools.product(SIZES, ('legacy', V1)), (262, V5)]}
    cells = {key(cell): cell for cell in data['cells']}
    assert len(cells) == len(data['cells']) == len(expected) == 252
    assert set(cells) == expected
    assert sum(bool(cell['evidence']) for cell in cells.values()) == data['measured_cells']
    checks, failures, waits = [], [], []

    def check(gate, current, against, **fields):
        row = {'gate': gate, 'cell': current, 'against': against, **fields}
        checks.append(row)
        if not fields['passed']:
            failures.append(row)

    for identity, cell in cells.items():
        if not cell['evidence']:
            continue
        assert cell['source_commit'] == data['source_commit']
        assert cell['status'] in (AUDITED, BLOCKED)
        footer = cell['shared_process_final_resource']
        assert footer['memory_target_passed'] and footer['target_enforced_for_current_runtime']
        assert footer['memory']['peak'] <= 2684354560 and footer['memory']['swap_current'] == 0
        if cell['status'] == AUDITED:
            assert len(cell['paid']) == len(cell['wall_seconds']) == len(cell['semantic_sha256']) == 4
            assert len(cell['warm_seconds']) == 3
            check('consistent_repeated_price', identity, identity,
                  passed=len({Decimal(str(price)) for price in cell['paid']}) == 1)
        else:
            assert len(cell['blocked_evidence']) == 4
            check('consistent_blocked_signature', identity, identity,
                  passed=len({(row['code'], row['stage']) for row in cell['blocked_evidence']}) == 1)

    for facts, city, profile, size in itertools.product(
            ('original', 'axfood_103'), ('malmo', 'lund'), PROFILES, SIZES):
        current = facts, city, profile, size, V1
        cell = cells[current]
        targets = [(facts, city, profile, size, 'legacy'),
                   (facts, city, profile, 262, 'legacy'),
                   (facts, city, profile, 262, V5)]
        if size != 262:
            targets.append((facts, city, profile, SIZES[SIZES.index(size)-1], V1))
        for against in dict.fromkeys(targets):
            reference = cells[against]
            if not cell['evidence'] or not reference['evidence']:
                waits.append({'cell': current, 'against': against})
                continue
            # Policy and library size vary; every input/context field must match.
            assert cell['inputs'] == reference['inputs'], (current, against, 'different context')
            assert cell['input_manifest_sha256'] == reference['input_manifest_sha256']
            if size == against[3]:
                assert cell['library_manifest_sha256'] == reference['library_manifest_sha256']
            if cell['status'] == BLOCKED:
                if reference['status'] == AUDITED:
                    check('outcome_preserved', current, against, passed=False)
                else:
                    check('blocked_signature_preserved', current, against,
                          passed=blocked_signature(cell) == blocked_signature(reference))
            elif reference['status'] == AUDITED:
                paid = max(Decimal(str(value)) for value in cell['paid'])
                bound = min(Decimal(str(value)) for value in reference['paid'])
                check('price_not_higher', current, against, passed=paid <= bound,
                      paid=str(paid), bound=str(bound))
            else:
                check('delivered_after_observed_blocked', current, against, passed=True)

        if size != 5000:
            continue
        small_key, legacy_key = (facts, city, profile, 262, V1), (facts, city, profile, 5000, 'legacy')
        small, legacy = cells[small_key], cells[legacy_key]
        if not all(c['evidence'] for c in (cell, small, legacy)):
            waits.append({'gate': 'warm_latency', 'cell': current})
        elif all(c['status'] == AUDITED for c in (cell, small, legacy)):
            ratio = max(cell['warm_seconds']) / min(small['warm_seconds'])
            check('warm_5000_over_262_at_most_1.25', current, small_key,
                  passed=ratio <= 1.25, ratio=ratio)
            check('warm_5000_not_slower_than_legacy', current, legacy_key,
                  passed=max(cell['warm_seconds']) <= min(legacy['warm_seconds']))

    result = {'schema': 'smako-independent-cross-cell-review-v1',
              'reviewer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'source_summary_sha256': hashlib.sha256(raw).hexdigest(),
              'source_commit': data['source_commit'],
              'measured_cells': data['measured_cells'],
              'required_cells': 252,
              'checked_comparisons': len(checks),
              'checks_by_gate': dict(Counter(row['gate'] for row in checks)),
              'pending_comparisons': len(waits),
              'native_failures': data['failures'], 'review_failures': failures,
              'all_sampling_complete': data['measured_cells'] == 252,
              'standard_qualified': False,
              'scope': 'Verified native metadata only; no new plans, no activation, blocked outcomes stay observations',
              'checks': checks, 'pending': waits}
    output = PATH.with_name('cross-cell-review-current.json')
    write_review(output, result)
    print(json.dumps({k: v for k, v in result.items() if k not in ('checks', 'pending')}, ensure_ascii=False))
    if failures or data['failures']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
