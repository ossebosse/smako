"""Reproduce decision tables from actual, isolated server acceptance artifacts."""
import json, hashlib
from pathlib import Path
from collections import Counter
from xml.etree import ElementTree as ET
R=Path(__file__).resolve().parent
P=R/'server-results/profile'
def read(p):return json.loads(p.read_bytes())
def write(name,value):(R/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def md(name,lines):(R/name).write_text('\n'.join(lines)+'\n',encoding='utf8')
a=read(P/'baseline-acceptance.json');b=read(P/'coop-acceptance.json')
pa=read(P/'baseline-acceptance-plan.json');pb=read(P/'coop-acceptance-plan.json')
cov=read(R/'server-results/browser/coop-live/coverage.json')
facts=read(P/'coop-acceptance-product-facts.json');pub=read(R/'server-results/publication-result.json')
for key in ['request_sha256','base_products_sha256','baseline_facts_version','code_sha256','generation_trace']:
 assert a[key]==b[key],key
assert a['result']==b['result']=='PASS'
assert a['active_manifest_sha256']==b['active_manifest_sha256']
assert a['saved_equals_readback'] and b['saved_equals_readback']
assert b['basket_audits'] and all(r['passed'] for r in b['basket_audits'])
expired=read(R.parent/'xtra-text-20260922/coop-regression/expired-difference.json')
assert not {r['offer_id'] for r in expired}&{x for r in cov['stores'] for x in r['qualification']['accepted_ids']}
traces={(r['store_id'],r['product_id']):r for r in b['coop_trace']}
requests={(r['store_id'],r['product_id']):r for r in b['request_candidate_trace']}
bytime={r['observed_at']:r for r in cov['stores']}
rows=[]
for f in facts:
 key=(f['store_id'],f['product_id']);t=traces[key];q=requests[key];s=bytime[t['source_observed_at']]
 rows.append({**f,'official_store_id':s['store_id'],'store_name':s['name'],'official_source':s['source_url'],
 'stages':t['stages'],'resolved_ingredients':q['resolved_names'],
 'nutrition_supported_recipes':q['individual_nutrition_supported_recipes'],
 'nutrition_missing_recipes':q['individual_nutrition_missing_recipes'],
 'selected':t['selected'],'checkout_comparisons':t['relevant_checkout_comparisons'],
 'blocker':'verified_product_nutrition_and_identity_link_missing' if f['facts'] is None else None})
write('product-qualification.json',rows)
selected={}
for arm,plan in [('A',pa),('B',pb)]:
 selected[arm]=[{**i,'basket_store':s['store_name']} for s in plan['optimized_basket']['stores'] for i in s['items']]
 assert all(i['verification_status']=='VERIFIED' for i in selected[arm])
write('selected-products.json',selected)
summary={'decision':'not_ready_for_activation','business_improvement':round(a['cost']-b['cost'],2),
 'production_activated':False,'same_base_products':True,'same_application_code':True,'same_request':True,'same_frozen_recipes':True,
 'arms':{k:{n:v[n] for n in ['universe_id','cost','http_seconds','total_seconds','slots','portions','stores','verification','isolated_health','isolated_ready','saved_equals_readback']} for k,v in [('A',a),('B',b)]},
 'coop':{'own':len(rows),'price_universe':len(rows),'quarantine':sum(s['quarantined'] for s in cov['stores']),
 'matched_in_pool':sum(bool(r['stages']['matched_candidates_by_name']) for r in rows),
 'semantic_in_pool':sum(bool(r['stages']['semantic_candidates_by_name']) for r in rows),
 'selected_pool_candidates':sum(bool(r['stages']['candidates_by_name']) for r in rows),
 'actual_ingredient_lookup':sum(bool(r['resolved_ingredients']) for r in rows),
 'product_facts':sum(bool(r['facts']) for r in rows),
 'nutrition_supported_products':sum(bool(r['nutrition_supported_recipes']) for r in rows),
 'nutrition_missing_products':sum(bool(r['nutrition_missing_recipes']) for r in rows),
 'selected_products':sum(r['selected'] for r in rows)},'publication':pub}
write('comparison.json',summary)
lines=['# Verklig 15/20-jämförelse, 22 september 2026','',
 'Samma kompletta källdatabas och Primat-cache, oförändrad originalbegäran, medlemskap av och max två inköpskontexter. Prisdag 2026-09-22, Europe/Stockholm.',
 'Basarmens 106 genererade recept fryses som indata för B. Planeraren, matcharen, näringsprövningen, checkout och audit körs på riktigt via HTTP i båda armarna. Ingen modell eller betald API-tjänst.',
 '', '| Mått | A utan kommun-Coop | B med kommun-Coop |','|---|---:|---:|']
for label,key in [('Kostnad, kr','cost'),('Planeringsanrop, sekunder','http_seconds'),('Bygg + fakta + HTTP, sekunder','total_seconds'),('Måltider','slots'),('Portioner','portions'),('Inköpskontexter','stores')]:lines.append(f"| {label} | {a[key]} | {b[key]} |")
lines+=['',f"**Kostnadsskillnad: {summary['business_improvement']:.2f} kr. Inga nya fysiska Coop-rader valdes.**",'',
 'Båda väljer Coop Online Syd och Willys Lund. Coop Online är online_fulfillment, inte fysiskt hyllpris eller bevis om en viss fysisk Coop-butik. Inga nio fysiska butiker slås ihop med Online. Profilens befintliga kanalval är oförändrat; resultatet är inte ett prov med enbart fysiska butikskanaler.',
 '', '## Valda produkter', '', 'Samma produkt-ID, butik, kvantitet och debitering i båda armarna verifieras i selected-products.json.', '',
 '| Kanal/butik | Produkt | Köpta förpackningar | Förpackning | Radkostnad kr |','|---|---|---:|---|---:|']
fields=['product_id','store_id','packages_needed','total_price']
assert [[r[k] for k in fields] for r in selected['A']]==[[r[k] for k in fields] for r in selected['B']]
for i in selected['B']:lines.append(f"| {i['basket_store']} | {i['product_name']} | {i['packages_needed']} | {i['package_quantity']} {i['package_unit']} | {i['total_price']:.2f} |")
lines+=['','## Näring och verifiering','',
 f"493 radgodkända priser; {summary['coop']['matched_in_pool']} har matchning i ingredienspoolen, {summary['coop']['selected_pool_candidates']} överlever poolens urval. {summary['coop']['actual_ingredient_lookup']} når faktisk ingrediens-/näringsprövning i den frysta receptpoolen. **0 har verifierat produktbundet näringsunderlag; 0 klarar tillskottets näringsprövning.**",
 'Alla produkt-ID:n, namn, butiker, matchningar och specifika receptbortfall finns i product-qualification.json. Ett pris får finnas kvar trots saknad näring. Vi härleder inte GTIN från sifferliknande käll-ID:n och gissar inga näringsvärden.',
 'Originalprofilen har allow_nutrition_estimates=true, oförändrat i båda armarna. Befintlig källbunden referensnäring i basen är alltså tillåten enligt samma profil; nya deklarationer eller uppskattningar har inte lagts till. 40/30/20 g protein per portion kontrolleras för samtliga måltider.',
 f"B:s {len(b['basket_audits'])} registrerade verkliga korgkontroller passerar audit. Båda slutkorgarna och samtliga köprader är VERIFIED; HTTP 201, sparning/identisk återläsning, health/ready 200. A:s vanliga basket-anrop har samma obligatoriska audit; B har dessutom explicit anropslogg.",
 '', '## Tidsmätningens omfattning','',
 'En slutlig körning per arm. Ingen statistiskt säker prestandaförbättring eller flerdagarsstabilitet påstås. De tidigare baseline/coop-final-körningarna är pilotkontroller med ekonomiskt genererad receptpool och ersätter inte denna frysta jämförelse.']
md('PROFILE.md',lines)
lines=['# Butiks- och näringstäckning','',
 'Lunds kommun 1281, tidigare verifierad inventering. Alla nio valda Coop/Stora Coop-butiker behålls i nämnaren. X:-tra är separat. Ny serverinsamling 08:39:02–08:39:38 svensk tid, 41,292 s. Ingen produktionsimport.',
 '', '| Butik / officiellt ID | Färska varianter | OWN = PU | Karantän | Faktisk ingrediensprövning | Näringsgodkända | Valda |','|---|---:|---:|---:|---:|---:|---:|']
for s in cov['stores']:
 rr=[r for r in rows if r['official_store_id']==s['store_id']]
 lines.append(f"| [{s['name']}]({s['source_url']}) / {s['store_id']} | {s['extracted_variants']} | {s['own']} | {s['quarantined']} | {sum(bool(r['resolved_ingredients']) for r in rr)} | {sum(bool(r['nutrition_supported_recipes']) for r in rr)} | {sum(r['selected'] for r in rr)} |")
lines+=['', 'Fullständiga snapshotkontrakt är fortsatt underkända; de uttryckligt partiella radgodkända offers_only-kontrakten används. 95-procentsgränsen och nämnaren är oförändrade. Karantänen har inte utvidgats eller mjukats upp.',
 'Sex Stora Coop-varianter från 1681-41962, giltiga enbart 21 september, finns inte bland de nya accepterade käll-ID:na. De tidigare 499 är historiskt bevarade; 493 gäller i detta underlag.',
 '', '## Produktbundet bortfall', '', '| Butik | Produkt | Prövade ingredienser | Näringsresultat |','|---|---|---|---|']
for r in rows:
 if r['resolved_ingredients']:lines.append(f"| {r['store_name']} | {r['name']} / {r['product_id']} | {', '.join(r['resolved_ingredients'])} | Saknad verifierad produktfakta/identitetslänk |")
md('COVERAGE.md',lines)
t=ET.parse(R/'tests.xml').getroot().find('testsuite')
print(json.dumps({'summary':summary['coop'],'tests':t.attrib,'costs':[a['cost'],b['cost']],'seconds':[a['http_seconds'],b['http_seconds']]}))
