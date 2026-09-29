from pathlib import Path
import json,collections,hashlib
P=Path(__file__).parent;R=P/'results'
def read(name):return json.loads((R/name).read_bytes())
assert read('http-raw-preflight.json')['all_valid']
assert all(r['http_status']==201 for r in read('http-results.json')['cases'])
cases=[]
for row in read('http-results.json')['cases']:
 response=row['response'];plan=response.get('plan',{});basket=plan.get('optimized_basket',{});checks=plan.get('personal',{}).get('checks',{})
 items=[x for s in basket.get('stores',[]) for x in s['items']]
 cases.append({'case':row['case'],'seconds':row['seconds'],'http_status':row['http_status'],'cost':basket.get('total'),'purchase_status':basket.get('verification_status',response.get('code')),'selected_line_status':dict(collections.Counter(x.get('verification_status','unknown') for x in items)),'stores':[{'id':s['store_id'],'name':s['store_name'],'channels':sorted({x['price_context_type'] for x in s['items']})} for s in basket.get('stores',[])],'api_reported_membership_programs_used':plan.get('membership_programs_used'),'actual_selected_member_rows':sum(x.get('eligibility')=='member' for x in items),'actual_selected_membership_programs':sorted({x['membership_program'] for x in items if x.get('membership_program')}),'selected_products':[{'id':x['product_id'],'name':x['product_name'],'store':x['store_name'],'channel':x['price_context_type'],'packages':x['packages_needed'],'purchased':x['purchased_quantity'],'unit':x['purchased_unit'],'required':x['required_quantity'],'cost':x['total_price'],'quality':x['verification_status']} for x in items],'nutrition_status':dict(collections.Counter(x['status'] for x in checks.get('nutrition',[]))),'nutrition':checks.get('nutrition',[]),'audit':checks.get('checkout_audit'),'saved_and_read_identical':row.get('roundtrip_identical'),'plan_id':row.get('plan_id'),'first_stop':response.get('detail'),'diagnostic_summary':{k:response.get('planning_diagnostics',{}).get(k) for k in ['pools','candidate_rejections','singleton_passed','missing_needs','search']}})
result={'policy':'lund-own-five-base-20260928-v1','production_activation':False,'purchase_date':'2026-09-28','historical_comparison_not_expected_cost':484.73,'cases':cases,'restarts':read('http-results.json')['restarts'],'scope':'Same preserved five-base policy and corrected current Coop additions; actual isolated HTTP, exact/estimated and original/Plus. Network disabled during consumer planning.'}
(P/'profile-summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print([(x['case'],x['http_status'],x['cost'],round(x['seconds'],2),x['purchase_status'],x['selected_line_status']) for x in cases])
