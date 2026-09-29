"""Join saved results by exact store + source variant, never by cheapest price."""
import json,hashlib,collections
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
R=Path(__file__).resolve().parent;ROOT=R.parents[1]
def read(p):return json.loads(p.read_bytes())
def save(name,d):(R/name).write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf8')
old=read(ROOT/'reports/coop-1520-20260922/product-qualification.json')
lineage=read(R/'offer-lineage.json');before={r['normalized_id']:r for r in lineage['before']}
after={(r['store_external_id'],r['external_product_id']):r for r in lineage['after']}
profile=R/'server-results/profile';A=read(profile/'baseline-acceptance.json');B=read(profile/'coop-acceptance.json')
assert A['request_sha256']==B['request_sha256']==read(ROOT/'reports/coop-1520-20260922/server-results/profile/baseline-acceptance.json')['request_sha256']
for field in ['base_products_sha256','baseline_facts_version','baseline_facts_count','purchase_date','generation_trace','code_sha256']:
 assert A[field]==B[field],field
assert A['saved_equals_readback'] and B['saved_equals_readback']
assert all(x['passed'] for d in [A,B] for x in d['basket_audits'])
facts={x['product_id']:x for x in read(profile/'coop-acceptance-product-facts.json')}
trace={x['product_id']:x for x in B['request_candidate_trace']}
rows=[]
for oldrow in old:
 if not(oldrow['nutrition_missing_recipes'] or oldrow['nutrition_supported_recipes']):continue
 o=before[oldrow['product_id']];new=after[(o['store_external_id'],o['external_product_id'])];pid=new['normalized_id'];fields=json.loads(new['source_fields']);f=facts[pid]['facts'];t=trace[pid]
 ischeese='Mature' in new['name'];ispasta='Pasta' in new['name']
 row={'store_id':new['store_external_id'],'store':oldrow['store_name'],'official_url':oldrow['official_source'],
  'source_offer_variant_id':new['external_product_id'],'source_variant_id':fields['source_variant_id'],
  'product':new['name'],'brand':new['brand'],'package':new['package_text'],'gtin_on_offer':new['gtin'],
  'before_product_id':o['normalized_id'],'after_product_id':pid,
  'ingredient':oldrow['resolved_ingredients'],'searched_nutrition':('Coop retained explicit EAN '+fields['source_variant_id']+'; 100 g as_sold' if ischeese else 'SLV 845 dry pasta versus fresh product' if ispasta else 'Existing SLV 364 raw tomato; estimates opt-in unchanged'),
  'before':'NUTRITION_EVIDENCE_UNQUALIFIED',
  'cause':('Verified retained declaration not bound across catalog and offer namespaces' if ischeese else 'No verified declaration; fresh pasta not equivalent to required dry pasta' if ispasta else 'Missing singular/word-order alias for existing raw tomato reference'),
  'after':'QUALIFIED' if t['individual_nutrition_supported_recipes'] else 'BLOCKED',
  'after_detail':('Exact ID+name+brand+package+concurrent source facts; no price transfer' if ischeese else 'Fresh/dry preparation remains incompatible; no fabricated declaration' if ispasta else 'Existing opt-in estimated reference, not a product declaration'),
  'supported_recipes':t['individual_nutrition_supported_recipes'],'missing_recipes':t['individual_nutrition_missing_recipes'],
  'source_observed_before':o['fetched_at'],'source_observed_after':new['fetched_at'],'source_sha256':fields['source_sha256'],
  'fact_source':f,'selected':next(r['selected'] for r in B['coop_trace'] if r['product_id']==pid)}
 rows.append(row)
assert len(rows)==22
save('22-before-after.json',rows)
lines=['# De 22 tidigare näringsprövade raderna','',
 '22 butik–variantposter, sju skilda källvariant-ID:n och fem produktnamn. Siffer-ID på erbjudandet är fortsatt ett opakt Coop-ID, inte en påhittad GTIN. De fyra tomat-ID:na är inte belagda som en och samma globala SKU. Samma identitetsutredning återanvänds mellan butikerna; priser och villkor stannar i respektive butik.', '',
 '| Butik / ID | Produkt / förpackning | Källpost | Ingrediens / sökt referens | Före → efter |', '|---|---|---|---|---|']
for r in rows:
 ref=('produktdeklaration 100 g, befintligt EAN '+r['source_variant_id'] if 'Mature' in r['product'] else 'SLV 845: torr pasta ≠ färsk' if 'Pasta' in r['product'] else 'SLV 364 rå tomat, tillåten uppskattning')
 lines.append(f"| [{r['store']}]({r['official_url']}) / {r['store_id']} | {r['product']}, {r['package']} | {r['source_offer_variant_id']} | {', '.join(r['ingredient'])}; {ref} | Underkänd → {'godkänd för prövade recept' if r['after']=='QUALIFIED' else 'spärrad: färsk/torr + saknad deklaration'} |")
lines += ['', 'Exakta interna före/efter-ID:n, råkällhashar, observationstider, recept och deklarationsbevis finns i `22-before-after.json`. Osternas deklarationer observerades 21 september och bevaras i `retained-cheese-declarations.json`; de föryngras inte av den nya erbjudandeinsamlingen. Kolhydrat <0,5 g är en sparad gränsuppgift, inte ett exakt tal. En profil som kräver saknade exakta kolhydratuppgifter får inte använda den som 0 eller 0,5. Tomatreferensen används endast med profilens befintliga allow_nutrition_estimates=true.', '',
 'Åtta pastarader förblir spärrade. Officiell exakt deklaration saknas bland de bevarade, godkända fakta som granskats; dessutom kräver de berörda recepten torr durumvetepasta. Att enbart hämta näring för färsk fettuccine löser inte detta formkrav. Inga externa deklarationsanrop behövdes för de relevanta ostarna eller tomatreferensen.']
(R/'22-POSTER.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
summary={'same_request':True,'same_complete_base_products':True,'same_fact_version':A['baseline_facts_version'],'same_recipes':True,'purchase_date':A['purchase_date'],
 'before_nutrition_lookups':22,'before_nutrition_qualified':0,'after_nutrition_lookups':sum(bool(t['individual_nutrition_missing_recipes'] or t['individual_nutrition_supported_recipes']) for t in trace.values()),'after_nutrition_qualified':sum(bool(t['individual_nutrition_supported_recipes']) for t in trace.values()),
 'unique_source_variant_ids':len({r['source_variant_id'] for r in rows}),
 'retailer_fact_links':sum(bool(f['facts']) for f in facts.values()),'linked_with_some_nutrition':sum(bool(f['facts'] and f['facts']['nutrition']) for f in facts.values()),
 'funnel':{'imported':len(facts),**{s:sum(bool(p['stages'][s]) for p in B['coop_trace']) for s in ['matched_candidates_by_name','semantic_candidates_by_name','candidates_by_name']}},'arms':{},'production_activation':False}
for label,d in [('A',A),('B',B)]:
 plan=read(profile/(('baseline' if label=='A' else 'coop')+'-acceptance-plan.json'))
 summary['arms'][label]={k:d[k] for k in ['cost','http_seconds','total_seconds','baseline_facts_count','universe_id','isolated_health','isolated_ready','saved_equals_readback','slots','portions','stores','verification']}
 summary['arms'][label].update(build_timing_ms=d['source_build']['timing_ms'],audits=len(d['basket_audits']),audit_all_pass=True,
  selected_stores=[{'id':s['store_id'],'name':s['store_name']} for s in plan['optimized_basket']['stores']],
  selected_products=[i for s in plan['optimized_basket']['stores'] for i in s['items']],
  selected_coop_offer_rows=sum(p['selected'] for p in d['coop_trace']))
save('comparison.json',summary)
print(json.dumps({k:v for k,v in summary.items() if k!='arms'},ensure_ascii=False))
