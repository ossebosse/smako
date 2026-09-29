"""Reconcile actual collection, serving, rebuild, restart and profiles."""
import json
from pathlib import Path

P=Path(__file__).parent;R=P/'results'
def read(name):return json.loads((R/(name+'.json')).read_bytes())
before=read('refresh-serving-before');after=read('publish-serving-after')
second=read('fault-final-serving-after');policy=json.loads((P/'policy.json').read_bytes())
source=read('final-source-audit');rows=[]
for source_row in source['rows']:
    name=source_row['name'].casefold()
    found=[(key,row) for key,row in after['stores'].items() if row['name'].casefold()==name and row['channel']=='physical_store']
    assert len(found)==1,source_row['store_id']
    context,row=found[0]
    assert row['count']==source_row['approved'] and row['expired_offers']==0 and row['future_offers']==0
    assert row==second['stores'][context]
    rows.append({**source_row,'context_id':context,'serving_before':before['stores'].get(context,{}).get('count',0),
        'serving_after':row['count'],'after_next_rebuild':second['stores'][context]['count']})
base_unchanged=all(before['stores'][key]==after['stores'][key]==second['stores'][key] for key in policy['required_context_ids'])
assert base_unchanged
assert after['products_sha256']==second['products_sha256']
actual=[json.loads(p.read_bytes()) for p in sorted(R.glob('actual-serving-*.json'))]
assert len(actual)>=2
assert all(s['products_sha256']==after['products_sha256'] for s in actual)
for s in actual:
    for row in rows:
        assert s['stores'][row['context_id']]['products']==row['serving_after']
        assert s['stores'][row['context_id']]['expired_offer_rows']==0
profiles=json.loads((P/'profile-summary.json').read_bytes())
assert len(profiles['cases'])==4
assert all(p['http_status']==201 and p['saved_and_read_identical'] and p['audit']['passed']
           and p['audit']['totals_reconciled'] for p in profiles['cases'])
assert len(profiles['restarts'])==4 and all(p['unchanged'] for p in profiles['restarts'])
retry=read('publish-result');fault=read('fault-final-result')
assert retry['coop_state_after']['approved']==fault['coop_state_after']['approved']
xtra=[k for k,v in before['stores'].items() if v['name'].casefold().startswith('x:-tra')]
assert xtra and all(before['stores'][k]==after['stores'][k]==second['stores'][k] for k in xtra)
result={'status':'PASS','policy':policy['id'],'production_activation':False,'rows':rows,
    'products_before':before['products'],'products_after':after['products'],
    'all_required_bases_unchanged':base_unchanged,'xtra_separate_unchanged':True,
    'next_rebuild_unchanged_products':True,'optional_coop_failure_retains_approvals':True,
    'restart_serving_product_hashes':[s['products_sha256'] for s in actual],
    'profiles':[{'case':p['case'],'cost':p['cost'],'audit_passed':p['audit']['passed'],
        'saved_and_read_identical':p['saved_and_read_identical']} for p in profiles['cases']]}
(P/'acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS',result['products_before'],'->',result['products_after'],'with identical bases/rebuild/restart and four audited saved profiles')
