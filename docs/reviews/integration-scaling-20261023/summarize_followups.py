"""Validate offline follow-ups against pinned matrix data; retain missing states."""
import argparse
import hashlib
import json
from pathlib import Path

parser=argparse.ArgumentParser(description="Validate pinned review reports without network access.")
parser.add_argument('--evidence',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=args.evidence
target=args.output
out={'schema':'smako-scaling-followups-v2','source_commit':'b139cd4630c03bc4e01f4c5c0ba0e7ead7e50314',
     'positive_recheck_namespace':'followups-v7','proxy_namespace':'proxy-v8',
     'superseded_proxy':'V7 proxy did not preserve __wrapped__, disabling the ordinary first-slot qualification cache handoff. Its timings are preliminary only; V8 retains wraps metadata and verifies actual handed-back evaluations.',
     'positive_branch_rechecks':[],'proxy':[],'large_proxy_comparisons':[],
     'new_process_warm_disk':None,'complete':False}
receipt_path=root/'followups-v7/commands.json'
if receipt_path.exists():
    receipts=json.loads(receipt_path.read_bytes())
    out['positive_recheck_commands']=[r for r in receipts if r['label'].startswith('lund262-')]
proxy_receipt=root/'proxy-v8/commands.json'
if proxy_receipt.exists():out['proxy_commands']=json.loads(proxy_receipt.read_bytes())
large_receipt=root/'proxy-5000-v8/commands.json'
if large_receipt.exists():out['large_proxy_commands']=json.loads(large_receipt.read_bytes())

def read(path):
    raw=path.read_bytes();report=json.loads(raw)
    return report,hashlib.sha256(raw).hexdigest()

for case in ('standard','distribution','vegan'):
    for arm in ('main','geo48'):
        name=f'lund262-{case}-{arm}-{case}.json';path=root/'followups-v7'/name
        row={'case':case,'arm':arm,'complete':path.exists()}
        if row['complete']:
            report,sha=read(path);old,oldsha=read(root/'final-grid/lund'/f'L262-{arm}-{case}.json')
            assert report['inputs']==old['inputs']
            assert report['library_version']==old['library_version']
            assert report['search_limits']==old['search_limits']
            assert report['method_signature']=='b84ccfab6c612e42a91ab5a79e2ccde4bebcfe310f9834c42fbf2d244a340bf9'
            record=report['records'][0];prior=old['records'][0]
            assert record['outcome']=='PASS' and record['audit_passed']
            assert all(record.get(k)==prior.get(k) for k in ('outcome','paid','semantic_sha256'))
            row.update(report_sha256=sha,comparison_report_sha256=oldsha,
                       same_result=True,method_signature=report['method_signature'],
                       inputs=report['inputs'],library_version=report['library_version'],
                       search_limits=report['search_limits'],result=record)
        out['positive_branch_rechecks'].append(row)

full_path=root/'proxy-v8/lund1000-full-standard.json'
if full_path.exists():
    full,fullsha=read(full_path)
    assert len(full['records'])==2 and all(r['outcome']=='PASS' and r['audit_passed'] for r in full['records'])
    out['proxy_full_pool_reference']={'report_sha256':fullsha,'report':full}
    identity=None
    for label,count in (('proxy',1),('proxy-memo-oracle',1),('proxy-memo',2)):
        path=root/'proxy-v8'/f'lund1000-{label}-standard.json'
        row={'label':label,'complete':path.exists()}
        if row['complete']:
            report,sha=read(path)
            assert len(report['records'])==count
            for key in ('inputs','method_signature','library_version','search_limits','merged_search_contract'):
                assert report[key]==full[key],key
            for record in report['records']:
                assert record['outcome']=='PASS' and record['audit_passed']
                assert record['paid']<=full['records'][0]['paid']
                ranking=record['proxy_review'][-1]
                assert ranking['first_slot_qualified_result_handoff']
                assert ranking['qualification_results_handed_back']>0
                signature=ranking['retained_identity_sha256']
                if identity is None:identity=signature
                assert signature==identity
                if label=='proxy-memo-oracle':
                    assert ranking['verified_every_hit'] and ranking['row_quote_memo_hits']>0
            row.update(report_sha256=sha,report=report,no_price_regression_in_this_case=True,
                       same_retained_identities=True)
        out['proxy'].append(row)

for slot in (32,48):
    paths=[root/'proxy-5000-v8'/f'lund5000-geo{slot}-{mode}-standard.json' for mode in ('full','memo')]
    row={'slot_limit':slot,'complete':all(path.exists() for path in paths)}
    if row['complete']:
        full,fullsha=read(paths[0]);proxy,proxysha=read(paths[1])
        assert len(full['records'])==len(proxy['records'])==2
        for key in ('inputs','method_signature','library_version','search_limits','merged_search_contract'):
            assert full[key]==proxy[key],key
        assert all(r['outcome']=='PASS' and r['audit_passed'] for r in full['records']+proxy['records'])
        for record in proxy['records']:
            ranking=record['proxy_review'][-1]
            assert ranking['first_slot_qualified_result_handoff'] and ranking['qualification_results_handed_back']>0
        assert len({r['proxy_review'][-1]['retained_identity_sha256'] for r in proxy['records']})==1
        row.update(full_report_sha256=fullsha,proxy_report_sha256=proxysha,full_report=full,proxy_report=proxy,
                   no_price_regression=all(r['paid']<=min(old['paid'] for old in full['records']) for r in proxy['records']))
    out['large_proxy_comparisons'].append(row)

warm_path=root/'process-warm-v7/process-timings.json'
if warm_path.exists():
    warm,sha=read(warm_path)
    if (root/'process-warm-v7/complete.json').exists():
        assert len(warm)==2 and all(r['same_matrix_result'] and r['exit_code']==0 for r in warm)
        assert all(r['peak_rss_bytes']<3*1024**3 for r in warm)
        reports=[]
        expected,expected_sha=read(root/'final-grid/malmo/L5000-geo48-standard.json')
        for measurement in warm:
            report,report_sha=read(root/'process-warm-v7'/f"{measurement['label']}-standard.json")
            assert report_sha==measurement['report_sha256']
            for key in ('inputs','method_signature','library_version','search_limits','merged_search_contract'):
                assert report[key]==expected[key],key
            assert report['preparation_disk_present_at_start']
            assert all(report['records'][0].get(k)==expected['records'][0].get(k)
                       for k in ('outcome','paid','semantic_sha256','audit_passed'))
            reports.append({'report_sha256':report_sha,'report':report})
        out['new_process_warm_disk']={'complete':True,'receipt_sha256':sha,'processes':warm,
                                     'matrix_reference_sha256':expected_sha,'reports':reports}
out['complete']=(all(r['complete'] for r in out['positive_branch_rechecks'])
                 and len(out['proxy'])==3 and all(r['complete'] for r in out['proxy'])
                 and all(r['complete'] for r in out['large_proxy_comparisons'])
                 and bool(out['new_process_warm_disk']))
target.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps({'complete':out['complete'],'rechecks':sum(r['complete'] for r in out['positive_branch_rechecks']),
                  'proxy':sum(r['complete'] for r in out['proxy']),'warm_disk':bool(out['new_process_warm_disk'])}))
