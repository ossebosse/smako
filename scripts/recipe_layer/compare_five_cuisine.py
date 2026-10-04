"""Compare complete replay output, allowing only timings and membership-set order."""
import argparse
import hashlib
import json
import statistics
from pathlib import Path


def semantic(plan):
    result = json.loads(json.dumps(plan))
    result.get('personal', {}).get('checks', {}).pop('timings_seconds', None)
    if 'membership_programs_used' in result:
        result['membership_programs_used'] = sorted(result['membership_programs_used'])
    return result


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def main(args):
    rows, identities = {}, {}
    for arm in ('before', args.after_arm):
        rows[arm] = []
        for n in range(1, 4):
            folder = args.evidence / 'results' / f'{arm}-{n}'
            summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
            for row in summary['runs']:
                plan = json.loads((folder / (row['phase'] + '-plan.json')).read_text(encoding='utf-8'))
                identity = digest(semantic(plan))
                identities[f'{arm}-{n}-{row["phase"]}'] = identity
                rows[arm].append({'run': n, **row, 'semantic_sha256': identity})
    assert len(set(identities.values())) == 1, 'Material replay difference: inspect full saved outputs'
    metrics = {}
    for arm, runs in rows.items():
        metrics[arm] = {}
        for phase in ('cold', 'warm'):
            selected = [r for r in runs if r['phase'] == phase]
            values = [r['wall_seconds'] for r in selected]
            metrics[arm][phase] = {
                'new_calculation_seconds': values, 'median_seconds': statistics.median(values),
                'min_seconds': min(values), 'max_seconds': max(values),
                'range_seconds': max(values) - min(values),
                'cpu_seconds': [r['cpu_seconds'] for r in selected],
                'peak_rss_kib': [r['peak_rss_kib'] for r in selected],
                'process_entry_to_serialized_seconds': [r['cold_process_to_serialized_seconds'] for r in selected],
                'initial_artifact_load_seconds': [json.loads((args.evidence / 'results' / f'{arm}-{r["run"]}' / 'summary.json').read_text(encoding='utf-8'))['load_seconds'] for r in selected],
            }
    report = {'complete_semantic_equality': True, 'compared_full_outputs': identities,
              'excluded_fields': ['personal.checks.timings_seconds'],
              'set_order_normalized': ['membership_programs_used'],
              'metrics': metrics, 'statistical_p95_claimed': False,
              'frozen_inputs': {k: v for k, v in json.loads((args.evidence / 'inputs/freeze.json').read_text(encoding='utf-8')).items() if k != 'raw_sha256'}}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'equal': True, 'metrics': metrics}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--evidence', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--after-arm', default='after-final')
    main(parser.parse_args())
