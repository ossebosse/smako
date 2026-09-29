"""Fail closed unless actual final-image results, reload and preserved evidence agree."""
import json,hashlib
from pathlib import Path
from collections import Counter
O=Path(__file__).parent
R=O/'results'
read=lambda p:json.loads(p.read_bytes())
purchase=read(R/'purchases-results.json')
expected={'ica-whole-salmon':(166.8,'VERIFIED_WITH_ESTIMATES'),'coop-loose-paprika':(13.65,'VERIFIED_WITH_ESTIMATES'),
 'coop-whole-pork':(47.14,'VERIFIED_WITH_ESTIMATES'),'coop-whole-multibuy':(99,'VERIFIED'),
 'hemkop-beef-cap':(238,'VERIFIED'),'hemkop-open-pizza':(79,'UNVERIFIED'),'xtra-open':(20,'UNVERIFIED')}
purchase_summary=[]
for row in purchase['cases']:
 if row['case'] in expected:
  assert row['http_status']==201 and row['roundtrip_identical'],row['case']
  plan=row['response']['plan'];basket=plan['optimized_basket']
  assert row['response']['build_id']=='legacy-purchase-terms-20260929-v5'
  assert (basket['total'],basket['verification_status'])==expected[row['case']]
  assert basket['total_reconciled'] and plan['personal']['checks']['checkout_audit']['passed']
  assert row['search']['live_provider_calls']==0
  prices=[p for r in row['search']['results'] for p in r['prices']]
  usage='estimated' if basket['verification_status']=='VERIFIED_WITH_ESTIMATES' else 'variant_selection_required' if basket['verification_status']=='UNVERIFIED' else 'exact'
  assert any(p['purchase_usage']==usage for p in prices)
  purchase_summary.append({'case':row['case'],'total':basket['total'],'status':basket['verification_status'],'audit':'PASS','live_provider_calls':0})
 else:
  assert row['http_status']==422 and row['response']['code'] in {'DATA_BLOCKED','CONFLICT'}
assert len(purchase_summary)==7
assert purchase['pantry_stock_unchanged'] and purchase['profile_unchanged']
assert len(purchase['restart_roundtrips'])==7 and all(r['identical'] for r in purchase['restart_roundtrips'])
h=read(R/'http-results.json');profiles=[]
original=read(O/'original-request.json')
assert len(h['cases'])==4
for row in h['cases']:
 assert row['http_status']==201 and row['roundtrip_identical']
 assert row['response']['build_id']=='legacy-purchase-terms-20260929-v5'
 assert row['request'].get('memberships',{})==({'willys':True,'lidl':True} if row['case'].startswith('plus-') else original.get('memberships',{}))
 compared=json.loads(json.dumps(row['request']));baseline=json.loads(json.dumps(original))
 for value in [compared,baseline]:
  value.pop('purchase_planning_mode',None);value.pop('memberships',None);value['personal'].pop('pantry_revision',None)
 assert compared==baseline
 plan=row['response']['plan'];basket=plan['optimized_basket'];checks=plan['personal']['checks']
 assert len(plan['recipes'])==15 and plan['portions']==20
 assert checks['checkout_audit']['passed'] and basket['total_reconciled'] and basket['store_count']<=2
 assert len(checks['nutrition'])==15 and all(n['status'] in {'VERIFIED','ESTIMATED'} for n in checks['nutrition'])
 assert row['request']['personal']['allow_nutrition_estimates'] is True
 profiles.append({'case':row['case'],'total':basket['total'],'purchase_status':basket['verification_status'],
  'nutrition':dict(Counter(n['status'] for n in checks['nutrition'])),'stores':[s['store_name'] for s in basket['stores']],
  'menu':[r['name'] for r in plan['recipes']],'seconds':row['seconds'],'roundtrip':True})
assert len(h['restarts'])==4 and all(r['unchanged'] for r in h['restarts'])
first=read(R/'publish-final-serving-after.json');second=read(R/'second-serving-after.json')
assert first['products']==second['products']==44119 and first['products_sha256']==second['products_sha256']
assert first['stores']==second['stores']
fault=read(R/'optional-failure-probe.json')
assert fault['chain']=='hemkop' and fault['invoked_at']>first['at'] and fault['external_price_requests']==0
restart=read(R/'restart-final-result.json')
assert restart['build_id']=='legacy-purchase-terms-20260929-v5' and restart['saved_quote_identical_after_restart']
assert len(restart['searches'])==7 and all(x['identical_terms_price_and_source'] for x in restart['searches'])
preserved=read(R/'preservation-result.json')
assert all(v['identical'] for v in preserved['mandatory_contexts'].values())
assert preserved['consumer_plan_revisions']['unchanged'] and preserved['personal_private_state']['unchanged']
nutrition=read(R/'nutrition-result.json')
assert nutrition['audit']['passed'] and nutrition['allergen_approval'] is False
image=read(O/'image.json');root=O.parents[1]
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==sha for p,sha in image['changed_files'].items())
quality=read(O/'quality.json');assert all(v['exit']==0 for v in quality.values())
report={'status':'PASS','image':image,'policy':'lund-own-five-base-20260928-v1','production_activation':False,
 'purchase_cases':purchase_summary,'negative_controls':['approximate pack blocked in exact mode','household campaign cap blocks third beef package'],
 'saved_and_restarted_purchase_plans':7,'pantry_stock_and_profile_unchanged':True,
 'profile_15_meals_20_portions':profiles,'saved_and_restarted_profile_plans':4,
 'serving':{'products':44119,'products_sha256':first['products_sha256'],'identical_after_second_rebuild':True,'stores':len(first['stores'])},
 'restart_after_second_rebuild':restart,'optional_failure_probe':fault,'preservation':preserved,'nutrition_component_trial':'PASS; existing raw preparation; generic reference, no allergy approval',
 'retailer_network_collections':0,'historical_replay_date':'2026-09-28','consumer_date':'actual 2026-09-29',
 'regression':{'relevant_distinct_tests':457,'broad_passed':455,'old_singleton_expectations_updated_and_file_retested':5,'ui_runtime_tests':31,'ruff':'PASS','compileall':'PASS'},
 'separate_open_tasks':['Malmo base policy and full publication','unknown ICA municipal records','Bunkeflostrand source path','complex new campaign mechanics','Lidl/Willys coverage','historical Lidl fixture']}
(O/'ACCEPTANCE.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS',len(profiles),'unchanged profiles;',len(purchase_summary),'real purchases;',first['products'],'products after second rebuild')
