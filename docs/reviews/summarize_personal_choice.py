"""Export compact evidence from this task's closed batches; never read stores."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_error(error):
    result = {k: error[k] for k in ('code', 'detail', 'stage') if k in error}
    diagnostic = error.get('planning_diagnostics', {})
    result['qualification'] = {k: diagnostic[k] for k in ('pools', 'candidate_rejections', 'singleton_passed', 'search') if k in diagnostic}
    return result


def compact_row(row):
    keys = ('case', 'owner', 'outcome', 'http_status', 'timeout_seconds', 'post_seconds',
        'saved_response_seconds', 'through_get_seconds', 'history_read_passed', 'paid',
        'audit_passed', 'semantic_sha256', 'unknown_quantities', 'distinct_recipes',
        'nutrition', 'week_distribution', 'stages', 'planner_timings',
        'initialization_seconds', 'save_seconds', 'peak_bytes', 'arithmetic_stats',
        'server_saved_seconds', 'code', 'stage', 'exception_type')
    result = {k: row[k] for k in keys if k in row}
    request = row.get('normalized_request')
    if request:
        result['normalized_request_sha256'] = hashlib.sha256(json.dumps(request,
            ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        result['native_normalization'] = {k: request.get(k) for k in (
            'postal_code', 'membership_price_policy', 'recipe_diversity_overrides', 'strategy', 'debug')}
        result['actual_pantry_revision'] = (request.get('personal') or {}).get('pantry_revision')
    if 'error' in row:
        result['error'] = compact_error(row['error'])
    reference = row.get('verified_reference')
    if reference:
        result['reference'] = {k: reference.get(k) for k in (
            'policy', 'context', 'global_optimum_proven', 'loaded_publications',
            'replayed_publications', 'improvement_limits')}
        result['reference']['publication_count'] = len(reference.get('publications', []))
        result['reference']['legacy_candidates'] = [
            {'publication_size': p.get('publication_size'), **p['legacy_full_library_preparation']}
            for p in reference.get('publications', []) if 'legacy_full_library_preparation' in p]
    if row.get('profile'):
        result['profile'] = row['profile']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    journal = json.loads((args.root / 'budget.json').read_bytes())
    assert all(row['status'] == 'closed' for row in journal), 'Close the active batch first'
    used = sum(row['wall_seconds'] for row in journal)
    assert used <= 7200
    result = {'schema': 'smako-personal-choice-evidence-v1', 'budget': journal,
        'charged_wall_seconds': used, 'remaining_seconds': 7200 - used, 'arms': {},
        'source_scope': 'Only closed reports/receipts in this task directory; no owner DB, cookies or credentials exported'}
    for entry in journal:
        folder = args.root / entry['arm']
        report_path, receipt_path = folder / 'result/report.json', folder / 'receipt.json'
        if not report_path.is_file():
            continue
        report = json.loads(report_path.read_bytes())
        receipt = json.loads(receipt_path.read_bytes())
        arm = {k: report[k] for k in ('inputs', 'policy', 'method', 'library', 'recipe_count',
            'instrumented', 'startup_seconds', 'process_seconds', 'status', 'boundary',
            'background_preparation', 'requests_sha256', 'final_memory') if k in report}
        arm['report_sha256'] = sha(report_path)
        arm['receipt_sha256'] = sha(receipt_path)
        arm['command_sha256'] = sha(folder / 'command.json')
        arm['resources'] = receipt['resources']
        arm['state'] = {k: receipt['state'][k] for k in ('ExitCode', 'OOMKilled', 'StartedAt', 'FinishedAt')}
        arm['image'] = receipt['image']
        arm['probe_sha256'] = receipt.get('probe_sha256')
        arm['runner_sha256'] = receipt.get('runner_sha256')
        arm['product_comparison_eligible'] = '-ui-' in entry['arm'] or entry['arm'].endswith('-ui')
        if 'browser' in entry['arm']:
            arm['boundary'] = 'Isolated HTTP server supporting browser.json; client timings are separate'
        if not arm['product_comparison_eligible'] and 'browser' not in entry['arm']:
            arm['excluded_reason'] = 'Initial explicit legacy defaults and 0.2s polling; diagnostic only, not native UI latency evidence. Arithmetic prototypes were reverted.'
        if arm['product_comparison_eligible'] and arm['probe_sha256'] is None:
            arm['probe_sha256'] = sha(args.root / 'probe-ui-v1.py')
        arm['records'] = [compact_row(row) for row in report.get('records', [])]
        final_path = folder / 'result/final-resource.json'
        if final_path.exists():
            arm['final_resource'] = json.loads(final_path.read_bytes())
            arm['final_resource_sha256'] = sha(final_path)
        result['arms'][entry['arm']] = arm
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


if __name__ == '__main__':
    main()
