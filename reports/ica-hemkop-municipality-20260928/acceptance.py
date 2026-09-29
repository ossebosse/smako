"""Reconcile independent retained evidence; never substitutes inventory for serving."""
import hashlib
import json
from pathlib import Path
from xml.etree import ElementTree

P = Path(__file__).parent
R = P / 'results'


def read(name):
    return json.loads((R / (name + '.json')).read_bytes())


before = read('publish-serving-before')
after = read('publish-final-serving-after')
second = read('fault-final-serving-after')
restart = read('fault-final-serving-before')
policy = json.loads((P / 'policy.json').read_bytes())
assert hashlib.sha256((P / 'policy.json').read_bytes()).hexdigest() == '684952daee28c71123e5c5b2cc43f7c3ba1e043bcd02cf0270bea9603208bce1'
assert after['products_sha256'] == second['products_sha256'] == restart['products_sha256']
assert after['stores'] == second['stores'] == restart['stores']
assert all(before['stores'][key] == after['stores'][key] for key in policy['required_context_ids'])
preserved = {key: row for key, row in before['stores'].items()
             if row['chain'] == 'coop' or row['name'].casefold().startswith('x:-tra')}
assert preserved and all(after['stores'][key] == row for key, row in preserved.items())
reports = [json.loads(f.read_bytes()) for f in sorted((R / 'reports').glob('refresh-report-*.json'))]
final_report = reports[-1]
assert any(row['status'] == 'failed_optional_source' and row['error_type'] == 'ConnectionError'
           for row in final_report['hemkop_municipal'])
assert all(row['status'] == 'not_due' for row in final_report['ica_structured_offers'])
assert read('publish-final-result')['exit'] == read('fault-final-result')['exit'] == 0

source = read('source-audit-final')
assert source['scope_restart']['1281']['municipality_code'] == '1281'
assert source['scope_restart']['1280']['municipality_code'] == '1280'
assert all(row['replayed_final_parser_matches_own'] for area in source['hemkop'].values()
           for row in area['stores'])
assert all(r['all_hashes_valid'] for r in source['raw_reference_checks'].values())
due_check = read('ica-due-inventory-check')
assert due_check['same_approved_store_ids'] and due_check['same_price_schedule'] and due_check['external_price_requests'] == 0
malmo = read('malmo-scoped-result')
assert not malmo['lund_policy_used']
assert len(malmo['rebuilds']) == 2
assert malmo['rebuilds'][0]['products_sha256'] == malmo['rebuilds'][1]['products_sha256']
assert all(row['published_serving_products'] == 0 and row['publication_blocker'] for row in malmo['rebuilds'])
assert malmo['ica_status'] == malmo['hemkop_status'] == 'not_due'

profiles = json.loads((P / 'profile-summary.json').read_bytes())
assert len(profiles['cases']) == 4
assert all(row['http_status'] == 201 and row['audit']['passed'] and row['audit']['totals_reconciled']
           and row['saved_and_read_identical'] for row in profiles['cases'])
assert len(profiles['restarts']) == 4 and all(row['unchanged'] for row in profiles['restarts'])
actual = [json.loads(f.read_bytes()) for f in R.glob('actual-serving-*.json')]
assert len(actual) == 2 and all(row['products_sha256'] == after['products_sha256'] for row in actual)
assert read('http-raw-preflight')['all_valid']
purchases = read('representative-purchases')['cases']
assert {row['account'] for row in purchases} == {'1003452', '1004016', '1004268', '4517'}
assert all(row['audit']['passed'] and row['audit']['totals_reconciled'] for row in purchases)
tests = {}
for name in ['regression-final.xml', 'regression-final-delta.xml', 'campaign-tests.xml', 'store-choice-tests.xml']:
    for test in ElementTree.parse(P / name).iter('testcase'):
        tests[(test.get('classname'), test.get('name'))] = not any(
            test.find(kind) is not None for kind in ['failure', 'error', 'skipped'])
assert all(tests.values())
runtime = json.loads((P / 'runtime-verification.json').read_bytes())
assert not runtime['mismatched'] and runtime['pip_check_exit'] == 0
checks = json.loads((P / 'static-checks.json').read_bytes())
assert checks['ruff']['exit'] == checks['compileall']['exit'] == 0

result = {'status': 'PASS_LUND_MUNICIPAL_CHAIN', 'malmo_status': 'MUNICIPAL_SOURCE_AND_BUILD_PASS_PUBLICATION_BLOCKED',
    'production_activation': False, 'policy': policy['id'], 'required_context_ids': policy['required_context_ids'],
    'products_before': before['products'], 'products_after': after['products'], 'contexts_after': len(after['stores']),
    'all_required_bases_unchanged': True, 'coop_and_xtra_preserved_separately': True,
    'next_rebuild_and_restart_identical_products': True, 'products_sha256': after['products_sha256'],
    'optional_hemkop_failure_visible_and_base_retained': True,
    'no_due_source_jobs_made_no_price_requests': True, 'durable_municipal_scope_after_environment_removed': True,
    'malmo_candidate_products': malmo['rebuilds'][0]['products'], 'malmo_published_products': 0,
    'representative_purchase_accounts': [row['account'] for row in purchases],
    'profiles': [{'case': row['case'], 'cost': row['cost'], 'audit': row['audit']['passed']} for row in profiles['cases']],
    'unique_tests_passed': len(tests), 'runtime_files_verified': runtime['files'], 'image': runtime['image']}
(P / 'acceptance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=True))
