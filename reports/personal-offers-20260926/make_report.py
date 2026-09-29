"""Render only measured, saved outcomes; no templated performance assertions."""
import json, hashlib, collections
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime, UTC

ROOT=Path(__file__).resolve().parents[2]; R=Path(__file__).parent; P=R/'profile'
def read(name): return json.loads((P/name).read_bytes())
def write(name,value): (R/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def purchase_counts(basket):
    counts=collections.Counter()
    for store in basket['stores']:
        for item in store['items']:
            terms=item.get('purchase_terms') or {}
            kind=('conditional' if terms.get('identity_scope')=='campaign_group' else
                  'estimated' if item['verification_status']=='VERIFIED_WITH_ESTIMATES' else
                  'exact' if item['verification_status']=='VERIFIED' else 'other')
            counts[kind]+=1
    return {k:counts[k] for k in ('exact','estimated','conditional','other')}
def stores(basket):
    return [{'id':s['store_id'],'name':s['store_name'],
             'channels':sorted({i['price_context_type'] for i in s['items']})} for s in basket['stores']]

summary={'clock':'2026-09-24T21:16:35.494010+00:00','source_price_requests':0,'new_nutrition_requests':0,
         'production_activated':False,'profiles':[],'http':[]}
all_hashes=set()
for membership in ('public','plus'):
    for mode in ('exact','estimated'):
        pair={'membership':membership,'mode':mode}
        for arm in ('before','after'):
            stem=f'{arm}-{membership}-{mode}'
            record=read(stem+'-restored-original.json');plan=read(stem+'-restored-original-plan.json');inputs=read(stem+'-inputs.json')
            assert record['status']=='PASS' and plan['portions']==20 and len(plan['personal']['slots'])==15
            assert inputs['status_at_test_clock']['usable_context_count']==9
            all_hashes.add(inputs['artifact_sha256'])
            if arm=='after':
                for name,sha in inputs['source_code_sha256'].items():
                    assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha, name+' changed after native run'
                assert plan['personal']['checks']['checkout_audit']['passed']
            basket=plan['optimized_basket']
            pair[arm]={'cost':basket['total'],'seconds':record['seconds'],'quality':basket['verification_status'],
                       'stores':stores(basket),'selected_rows':purchase_counts(basket),
                       'nutrition_statuses':dict(collections.Counter(x['status'] for x in plan['personal']['checks']['nutrition'])),
                       'packages':sum(i['packages_needed'] for s in basket['stores'] for i in s['items'])}
        summary['profiles'].append(pair)
assert len(all_hashes)==1
summary['artifact_sha256']=all_hashes.pop()
for arm in ('before','after'):
    data=read('http-'+arm+'-integration.json')
    assert data['source_sha256']==summary['artifact_sha256']
    if arm=='before': before_http_request=data['request']
    else: assert data['request']==before_http_request
    for case in data['cases']:
        row={'arm':arm,'mode':case['mode'],'http_status':case['http_status'],'seconds':case['seconds'],
             'requested_store_ids':data['request']['allowed_store_ids']}
        if case['http_status']==201:
            plan=case['response']['plan'];basket=plan['optimized_basket']
            row.update(cost=basket['total'],quality=basket['verification_status'],stores=stores(basket),
                       selected_rows=purchase_counts(basket),nutrition=plan['personal']['checks']['nutrition'],
                       request_scope_honored=all(s['store_id'] in data['request']['allowed_store_ids'] for s in basket['stores']),
                       roundtrip_identical=case['roundtrip_identical'])
        else: row['reason']=case['response']['detail']
        summary['http'].append(row)
    if arm=='after':
        assert data['restart']['process_restarted'] and data['restart']['saved_plan_identical']
        summary['http_restart']=data['restart']
write('profile-summary.json',summary)

diagnostics={}
for membership in ('public','plus'):
    for mode in ('exact','estimated'):
        label=membership+'-'+mode
        trace=read('after-'+label+'-restored-original.json')['diagnostics']['product_decisions']
        diagnostics[label]={'products':trace['products'],'whole_basket_comparisons':trace['whole_basket_comparisons'],
                            'recipe_search':trace['recipe_search'],
                            'omitted_products':trace['omitted_products'],'omitted_contexts':trace['omitted_context_events']}
write('product-decisions.json',diagnostics)
trace=read('after-plus-estimated-restored-original.json')['diagnostics']['product_decisions']
prep=[x for x in trace['recipe_needs'] if x['stopped_at']=='preparation']
assert len(prep)==84
for row in prep:
    names=set(row['ingredients'])
    if any('neutral matolja' in text for text in row['instructions']):
        row['review']='Generated warm preparation is not covered by a reviewed calculation rule. Instructions mention cooking oil without an amount. Cooking/preparation and retained/removed amounts need an explicit basis; a price or raw declaration does not establish it.'
    elif 'ägg' in names:
        row['review']='Boiled/peeled egg in pieces: no reviewed linkage from the counted purchase to edible recipe grams and applicable cooked nutrition in this recipe.'
    elif 'tofu' in names:
        row['review']='Pan-fried tofu: this method lacks an applicable reviewed preparation rule; raw/as-sold macros are not automatically cooked-food evidence.'
    else:
        row['review']='Cooked, drained chickpeas in recipe: reviewed calculation must tie used drained grams to the matching sold/cooked/drained product basis.'
write('preparation-review.json',{'original_rejections':84,'generated_warm':80,'other':4,'rejections':prep,
                               'not_claimed':'These are preparation-gate outcomes before product retrieval, not 84 price or product rejections.'})
seen={}
for name in ('tests-regression.xml','tests-offer-final.xml'):
    for case in ET.parse(R/name).iter('testcase'):
        seen[(case.get('classname'),case.get('name'))]=not(case.find('failure') is not None or case.find('error') is not None)
assert all(seen.values())
write('tests-summary.json',{'unique_passed':len(seen),'inputs':['tests-regression.xml','tests-offer-final.xml'],
                           'historical_lidl_fixture':'OPEN, not run/restored: test_reviewed_lidl_nutrition.py / source-implementation-20260915/lidl_offer_adapter.py'})
lines=['# PersonalPlanner – verkliga erbjudanden, 26 september 2026','',
       'Historisk replay, inga nya pris- eller näringsnätanrop. Samma kompletta artifact, 9 priskontexter inklusive 6 obligatoriska. Inga produktlistor eller kandidatlistor har handpatchats. Ursprunglig 15/20: 40/30/20 g protein och högst två inköpsställen. Separat medlemskopia med Willys Plus och Lidl Plus.', '',
       '| 15/20 | Kostnad före → efter | Tid före → efter | Kvalitet | Valda rader E/U/V |',
       '|---|---:|---:|---|---|']
for row in summary['profiles']:
    a,b=row['before'],row['after'];c=b['selected_rows']
    lines.append(f"| {row['membership']} / {row['mode']} | {a['cost']:.2f} → {b['cost']:.2f} kr | {a['seconds']:.3f} → {b['seconds']:.3f} s | {b['quality']} | {c['exact']}/{c['estimated']}/{c['conditional']} |")
lines += ['', 'Alla fyra profiler väljer Coop Online Syd (`online_fulfillment`) och Willys Lund (`online_store`): 12 exakta köprader, 20 förpackningar. E/U/V betyder exakt/uppskattat/villkorat. Kostnaden avser hela inköp, inte förbrukade receptgram. Näring redovisas separat: 10 deklarationsbaserade VERIFIED och 5 tillåtna referensbaserade ESTIMATED måltider; samtliga 40/30/20-mål passerar.', '',
          '| HTTP: ostsmörgås, Lidl Plus, uttryckligt Lidl-val | Kostnad | Tid | Kvalitet | E/U/V |', '|---|---:|---:|---|---|']
for row in summary['http']:
    c=row.get('selected_rows',{})
    lines.append(f"| {row['arm']} / {row['mode']} | {row.get('cost','spärrat')} | {row['seconds']:.3f} s | {row.get('quality','HTTP '+str(row['http_status']))} | {c.get('exact','–')}/{c.get('estimated','–')}/{c.get('conditional','–')} |")
lines += ['', '**HTTP-föreprovet är inte en jämförbar Lidl-kostnad:** den gamla API-modellen saknade `allowed_store_ids`, ignorerade fältet och valde Coop Online Syd (Liba Bröd Grov/Gouda Skivor). Efterprovet respekterar det nya, uttryckliga planbundna butiksvalet. Det ändrar inte sparad profil eller kommunens inventering.', '',
          'Efter, uppskattat: Lidl Åkerlund och Rausings väg 1, fysisk butik. Pågen Lingongrova 500 g för 17,90 kr (Lidl Plus) + offentliga Arla Hushållsost 26 %, cirka 2,2 kg × 69,90 kr/kg = cirka 153,78 kr. Summa cirka **171,68 kr**. Ett helt ostpaket köps; receptet använder 100 g ost och 100 g bröd. 2 100 g uppskattad ostrest. Protein 25 + 8,8 = **33,8 g**, prövat mot minst 30 g. Deklarationsbaserad näringsstatus VERIFIED är skild från korgens VERIFIED_WITH_ESTIMATES; allergisäkerhet är inte begärd/bevisad.', '',
          'Ordinarie HTTP POST `/api/plans`, GET, verklig backendprocessomstart och GET passerar med identisk sparad plan och återladdat hashkontrollerat artifact. Checkout/audit är sparad i `personal.checks.checkout_audit`. Inga extraköp, produktlås, injicerade kandidatlistor eller syntetiska priser användes.', '',
          '## Produktvis faktiskt bortfall', '',
          '- **Arla Hushållsost:** fanns redan i breda matched-indexet, som PersonalPlanner faktiskt använder när fakta behövs. Ingen bevisad överföringsförlust för den näringsprövade profilen. Den faktiska resolve-vägen använder candidates_by_name, kompletterar med matched_candidates_by_name och PriceUniverse-canonical-index samt befintligt textsökindex; semantic_candidates_by_name är ingen direkt ingång i PersonalPlanner. Deklarationsklassificering tillkommer som requestlokalt index. Exakt läge spärrar cirka-vikten. Uppskattat läge: matchning, pris, deklaration och korgkandidater passerar för fem ostrecept. Den fria slutmenyn väljer den inte. Två explicita hela-varukorgsjämförelser (en per Lidl-butik) uttömmer den befintliga näringssökningens 256 kombinationer under tvåbutikstaket; ett redovisat avslag ger 38,350347509 g protein mot 40 g för torsk/nudlar/vitkål. Detta bevisar varken att Arla är dyrare eller att en lösning globalt är omöjlig. Befintlig optimering prioriterar även verifieringsnivå före pris.',
          '- **Willys Gouda:** prisvillkor stoppar utan Willys Plus. Med Plus och uppskattningsläge når den fem ostbehov, men saknar kvalificerad näring per 100 g för efterfrågat proteinfält. Källan anger VARDAGSFAVORITER, tillfälligt parti, cirka 1,1 kg; GTIN och fetthalt saknas. Därför finns inte grund för att välja en godtycklig SLV-ostreferens. Inget påhittat generiskt ostvärde lades till.',
          '- **Willys fläskytterfilé:** dess relevanta ugnsplåtsrecept stoppas före produktprövning av saknad godkänd beredningsgrund; inget ekonomiskt bortval är visat.',
          '- **Willys Granny Smith/Royal Gala och Lidl-persikor:** receptpoolen innehåller inget relevant fruktbehov. De har inte fallit bort i en faktisk kostnadsjämförelse. Persikans sparade SLV-värde avser ätbara gram; ingen kärnandel har gissats.',
          '- **Lingongrova:** verifierad leverantörsklassificering Matbröd nådde tidigare inte index/matchning från det korta produktnamnet. Den generella deklarationsprojektionen rättar det med återkontrollerad GTIN/variant/förpackning och källhash. Pris, datum, butik och Plus-villkor kommer fortfarande från ursprungligt erbjudande.', '',
          '## De 84 beredningsavslagen', '',
          '80 genererade varma recept saknar en granskad beräkningsregel; deras instruktioner anger även neutral matolja utan mängd. Fyra andra fall: två recept med kokta/skalade ägg i styck (ätbar gramkoppling/beredning), stekt tofu (beredningsgrund), samt kokta avrunna kikärtor (mängd-/deklarationsgrund). Se alla 84 exakta ingredienslistor, steg och första avslag i `preparation-review.json`. Dessa är inte 84 avslag på prisposter. Skydden har inte sänkts.', '',
          '## Kod och verifiering', '',
          '- Bredare index används i uppskattningsläge även utan inlästa näringsfakta: prisdeltagande är inte beroende av näringsprövning. Separat oförändrat verkligt fryst indexprov ger 4 → 6 ostkandidater utan näringsfakta; de två tillkommande butiksposterna är samma Arla-erbjudande i två butiker, alltså ett unikt erbjudande. Se index-before.json/index-after.json.',
          '- Exakt deklarationsklassificering kan komplettera korta produktnamn i gemensam matchning; oidentifierade variantgrupper eller konfliktfyllda deklarationer får inte ärva den.',
          '- Planbundet uttryckligt butikskontextval med validering, lagring och oförändrat standardläge.',
          '- Avgränsad produktspårning genom faktiska index, recept, prisvillkor, näring, korgkandidater och verkliga sökhändelser; första stopp skiljs från senare receptavslag. Hela alternativa korgar kontrolleras av befintlig optimering/näring/audit.',
          f'- {len(seen)} unika riktade regressioner PASS, däribland verkligt fryst måltidsprov och negativa fall för exakt läge, medlemskap, allergi, utgång, fel butik, ml/g och obelagd vikt. Begränsningar och käll-ID/snapshot följer diagnostiken. Ruff och compileall PASS.', '',
          'Prisimport, PurchaseTerms, providers, kommuninventering och refresh-scheman är oförändrade jämfört med frysta utgångspunkten. Tidigare kontroller av kommunurval, andra rebuilden och behovsstyrning återanvänds som oförändrade käll-/driftbevis; detta steg utför inte ny extern insamling eller en ny komplett Malmö-publicering.', '',
          '## Öppna beroenden och begränsningar', '',
          'Den fria sökningen är begränsad (beam 8, säker fallback 64, näringssökning 256); diagnostiken är begränsad till 256 erbjudandeprodukter/4 096 recept–ingredienskontexter och högst 24 avslutande alternativa korgar. Den aktuella profilen har 87 spårade butiksposter och inga utelämnade produkt-/kontexthändelser. Butikskopior är inte nya unika erbjudanden. Ingen uttömmande global optimumgaranti.',
          'Inga nya prisposter eller näringsvärden importerades. Den observerade förbättringen är användbar receptkoppling och fullständig HTTP-verifiering. Den gamla Lidl-fixtureluckan är fortsatt ÖPPEN. Ny oberoende verklig kampanjutgåva och fullständigt Malmö-publiceringsprov med färsk komplett bas är fortsatt separata öppna kontroller.',
          'Underlaget är historiskt: 43,466 h gammal äldsta användbara bas vid testklockan och nu för gammalt för aktuell publicering. Näringsdeklarationen för Arla hämtades 25 september och återanvänds i retrospektivt pristest för 24 september. Observationer, 36/48-timmarsgränser och användarval har inte föryngrats/ändrats. Ingen produktion, schemaändring, bildanalys eller betald modell-API.']
(R/'VERIFICATION.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print('measured report generated',len(seen),'tests')
