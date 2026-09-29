"""Assemble only recorded results; absent tests remain absent, never inferred passes."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
R = OUT/'results'
P = R/'physical-probe'
def read(path): return json.loads(path.read_bytes())
def write(name, value): (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def h(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def short(value): return str(value or '—').replace('|','/').replace('\n',' ')
coverage = read(R/'source-coverage.json')
http = read(P/'http-results.json')
final = read(P/'http-results-final.json')
servings = [read(f) for f in sorted(P.glob('actual-serving-*.json'))]
serving = next(s for s in reversed(servings) if str(s.get('runtime_planner_file','')).startswith('/srv/app/'))
builds = [read(f) for f in sorted(P.glob('build-*.json'))]
assert all(b['products_sha256']==serving['products_sha256'] for b in builds)
assert all(b['full_candidate_manifest_unchanged'] for b in builds)
offers = read(P/'served-offer-inventory.json')['offer_products']
by_source = {}
for product in offers:
    provenance=product['source_provenance']
    by_source.setdefault((product['chain'],provenance['provider_store_id']),product['store_id'])
store_rows=[]
for b in coverage['base']:
    if not b['oldest_observation'].startswith('2026-09-27'): continue
    s=next((s for s in serving['stores'].values() if s['store']==b['name']),None)
    store_rows.append({'chain':b['chain'],'id':b['store_external_id'],'store':b['name'],'municipality':'1281: official geometry' if b['chain']=='willys' else 'existing approved online context; municipality inventory not newly extended','channel':s['channel'] if s else 'unknown','observed_from':b['oldest_observation'],'observed_to':b['newest_observation'],'fetched':b['own_rows'],'own':b['own_rows'],'served':s['products'] if s else None,'date_valid':s['date_valid_products'] if s else None,'quarantine':0,'reasons':{'out_of_stock':b['own_rows']-s['products']} if s and b['own_rows']!=s['products'] else {},'capabilities':s['purchase_terms'] if s else {},'source':b['scope_key'],'snapshot':b['snapshot_id']})
for job,source in coverage['municipal_sources'].items():
    chain={'coop-municipal':'coop','lidl-municipal':'lidl','willys-flyer':'willys','citygross-municipal':'citygross'}[job]
    for store in source['stores']:
        o=store.get('last_outcome') or {};selection=store.get('selection') or {}
        if not o: continue # Willys online stores already have their own rows.
        context=by_source.get((chain,store['store_id']));s=serving['stores'].get(context,{})
        qual=store.get('qualification') or {}
        reasons=o.get('blockers') or dict(Counter((d.get('blockers') or d.get('reasons') or ['accepted'])[0] for d in qual.get('decisions',[])))
        reasons.pop('accepted',None)
        if qual.get('advertisement_decisions'):
            reasons=dict(Counter(d['reason'] for d in qual['advertisement_decisions'] if d.get('reason')))
        else:
            reasons.update(Counter(d['error_message'] for d in qual.get('retained_parser_quarantine',[])))
        store_rows.append({'chain':chain,'id':store['store_id'],'store':store['name'],'municipality':store['municipality_status']+': '+store['geographic_reason'],'channel':store['channel'],'observed_from':o.get('observed_at'),'observed_to':o.get('observed_at'),'fetched':o.get('retrieved_products',o.get('extracted_variants',o.get('extracted_ads'))),'own':o.get('own'),'served':s.get('products'),'date_valid':s.get('date_valid_products'),'quarantine':o.get('quarantine_count',o.get('quarantined')),'reasons':reasons,'capabilities':s.get('purchase_terms',{}),'source':o.get('source_url') or store['official_sources'].get('official_store_url'),'snapshot':o.get('snapshot_id'),'next_fetch':selection.get('next_fetch_at'),'next_transition':selection.get('next_transition_at'),'source_format':o.get('source_format') or ('document text' if store['store_id']=='3658' else 'structured official offers')})
        if o.get('editions'):
            store_rows[-1].update(fetched=sum(e.get('parsed_ads',0) for e in o['editions']),quarantine=o.get('quarantine'),reasons={'partial_document_text_qualification':o.get('quarantine')},source=o.get('official_store_url'))
for s in coverage['ica_structured']['stores']:
    identity=s['ica_account_id'];context=by_source.get(('ica',identity));served=serving['stores'].get(context,{})
    own=s.get('row_approved_own',0) or 0;fetched=s.get('fetched',0) or 0
    store_rows.append({'chain':'ica','id':identity,'store':s['name'],'municipality':'NOT a municipal assessment: locality '+s['area_membership']+' ('+s.get('locality','')+')','channel':'physical_store','observed_from':s.get('last_success_at'),'observed_to':s.get('last_success_at'),'fetched':fetched,'own':own,'served':served.get('products',0),'date_valid':served.get('date_valid_products',0),'quarantine':fetched-own if fetched else 0,'reasons':s.get('rejection_reasons',{}),'capabilities':served.get('purchase_terms',{}),'source':s.get('offers_url'),'snapshot':served.get('source_snapshots',[]),'next_fetch':coverage['ica_structured']['store_schedule'].get(identity,{}).get('next_fetch_at'),'source_format':'official structured weeklyOffers','scope_reason':s['area_reason'],'qualification':s.get('row_approved_result',{})})
    acceptance=(s.get('row_approved_result') or {}).get('acceptance',{})
    store_rows[-1]['reasons'].update(Counter(reason for d in acceptance.get('decisions',[]) for reason in d.get('blockers',[])))
write('store-results.json',store_rows)

cases=[]
for membership in ['original','plus']:
    for mode in ['exact','estimated']:
        cases.append({'case':'full-lund-'+membership+'-'+mode,'status':'NOT_RUN_REQUIRED_BASE_MISSING','cost':None,'seconds':None,'quality':None,'selected_stores':[],'exact':None,'estimated':None,'conditional':None,'reason':'Mandatory primat:ica:1004409 revalidated offers_only; no complete fresh federation or active full-Lund manifest.'})
for run,data in [('initial-physical',http),('final-package',final)]:
    for c in data['cases']:
        response=c.get('response',{});plan=response.get('plan',{});basket=plan.get('optimized_basket') or {};checks=plan.get('personal',{}).get('checks',{});items=[i for s in basket.get('stores',[]) for i in s['items']]
        row={'case':run+'/'+c['case'],'scope':c.get('scope',data['scope']),'http_status':c.get('http_status'),'status':'PASS' if c.get('http_status')==201 else response.get('code',c.get('status')),'cost':basket.get('total'),'seconds':c.get('seconds'),'quality':basket.get('verification_status'),'selected_stores':[{'id':s['store_id'],'name':s['store_name'],'channels':sorted({i['price_context_type'] for i in s['items']})} for s in basket.get('stores',[])],'exact':sum(i.get('quantity_confidence')=='exact' for i in items),'estimated':sum(i.get('quantity_confidence')=='estimated' for i in items),'conditional':sum((i.get('purchase_terms') or {}).get('variant_selection')=='required' for i in items),'items':items,'nutrition':[{'slot':n['slot_id'],'status':n['status'],'values':n.get('values'),'sources':n.get('sources')} for n in checks.get('nutrition',[])],'audit':checks.get('checkout_audit'),'reason':response.get('detail'),'roundtrip_identical':c.get('roundtrip_identical'),'plan_id':c.get('plan_id')}
        diag=response.get('planning_diagnostics',checks.get('planning_diagnostics',{}))
        row['first_stops']=dict(Counter(x['reason'].split('för ')[-1].split('. Kontrollera')[0] if 'Ingen verifierad' in x['reason'] else 'nutrition unit/preparation' for x in diag.get('candidate_details',[])))
        row['diagnostic_omissions']={k:diag.get('product_decisions',{}).get(k) for k in ['omitted_products','omitted_context_events']}
        cases.append(row)
write('profile-summary.json',{'source_date':'2026-09-27','historical_replay':False,'complete_lund_base':False,'physical_artifact_products':serving['products'],'physical_products_sha256':serving['products_sha256'],'cases':cases,'timing_note':'Initial exact precedes estimated in same process. Final package cheese is cold; initial cheese follows two failed profile runs. Not controlled performance comparisons.'})

table=['# Butik för butik – aktuell insamling 27 september 2026','', 'Alla PU-tal nedan gäller den separat publicerade OWN-kandidaten, inte en komplett Lund-federation. Datumgiltighet avser kördagen 2026-09-27. Antal är butiksposter, inte nya unika erbjudanden. Kommunurval gäller insamling, inte användarens butikstillåtelse.','', '| Källa/butik (ID) | Kommun/scope | Kanal | Verklig observation UTC | Hämtat / OWN / serving / datumgiltigt | Karantän / bortfall |','|---|---|---|---|---|---|']
for row in store_rows:
    table.append(f"| {short(row['store'])} ({row['id']}) | {short(row['municipality'])} | {row['channel']} | {short(row['observed_from'])} → {short(row['observed_to'])} | {row['fetched']} / {row['own']} / {row['served']} / {row['date_valid']} | {row['quarantine']}; {short(row['reasons'])} |")
table.extend(['','City Gross: 38 officiellt inventerade, 0 i Lund, 38 utanför. Ingen grannbutik har lånats.','', 'ICA Södra Sandby, Genarp och Veberöd ligger utanför det befintliga *ortsurvalet*. Detta är inte bevis för att de ligger utanför Lunds kommun. Den ordinarie ICA-jobbkopplingen saknar här gemensamt kommunläge. Hemköp använder tidigare godkända katalogkontexter, inte en ny fullständig kommuninventering.','', 'Karantänorsaker kan överlappa inom samma rad; summera inte orsakstal. Hämtat/OWN är separata från den slutligt serverade mängden. 192 katalograder är explicit out_of_stock (Willys 77+70, Hemköp 25+20). Gunnesbo: 29 OWN-rader → 27 serverade; OWN-projektionen avvisar Startkit Gel iQ och Gaständare som invalid_or_incomplete_product. Den generiska projektionens logg sparar inte det underliggande fältfelet. Dessa två är inte livsmedelsbortfall.','', 'Köpbarhet: datumgiltigt pris är inte samma som exakt köp eller näringsgodkännande. Lidl per butik: PurchaseTerms 26 exact, 2 estimated. Willys Hemma: 22 exact, 4 estimated, 3 variant_selection_required och 2 äldre kontrakt utan sådan klassificering. Övriga kedjors äldre kontrakt måste mängd-/medlemsprövas i checkout; de får inte räknas som automatiskt näringsgodkända. Faktiskt måltidsval och audit finns i profile-summary.json.','', 'Länkar och fullständiga käll-/snapshotuppgifter:'])
for row in store_rows:
    table.append(f"- {row['store']} ({row['id']}): {row['source']}. Nästa hämtning: {row.get('next_fetch','basens befintliga behovs-/färskhetsstyrning')}.")
(OUT/'STORE-RESULTS.md').write_text('\n'.join(table)+'\n',encoding='utf-8')

tests=read(OUT/'test-summary.json');image=read(OUT/'final-image.json');manifest=read(OUT/'source-manifest.json')
table=[]
for c in cases:
    table.append('| '+ ' | '.join(short(v) for v in [c['case'],c.get('http_status',c['status']),c['cost'],round(c['seconds'],3) if c['seconds'] else None,c.get('quality'),f"{c['exact']}/{c['estimated']}/{c['conditional']}",', '.join(s['name'] for s in c['selected_stores'])])+' |')
expiry=read(P/'expiry-admission.json')
expiry_lines='\n'.join(f"- {x['label']}: {x['inactive_campaign_products_in_artifact']} inaktiva kampanjposter, {x['inactive_products_retained_in_legacy_index']} kvar i äldre index, **{len(x['expired_purchase_admissions'])} godkända köp**; {x['actual_regular_price_candidates']} ordinarie priskandidater." for x in expiry['results'])
text=f'''# Lund 1281 – samlat aktuellt integrations- och driftprov

**Inte redo för separat aktiveringsbeslut. Ingen produktion eller aktiv schemaläggning har ändrats.**
Obligatoriska `primat:ica:1004409` (ICA Kvantum Malmborgs Clemenstorget) återvalideras nu av källan som `tier=offers_only`, `coverage=offers_only`, `selected=false`. Det tidigare verifierade kontraktet kräver `full_catalog`. Det saknas färsk komplett LKG. Den fullständiga federationen och dess atomiska publicering stoppas därför korrekt. [Aktuell identitetskontroll](results/primat-identity-check.json) visar det faktiska svaret, inte ett antaget nätfel. Gunnesbos identitet/täckning återvalideras fortfarande, men den obligatoriska bunten kan inte publiceras partiellt.

## Paket och bevarat arbete

- Git HEAD: `{manifest['git_head']}`; detta är **inte** en ren HEAD-byggning. Alla tidigare opublicerade ändringar ingår.
- Slutbild: `{image.get('image_id',image.get('id'))}`. Full identitet: [final-image.json](final-image.json).
- Källträd SHA-256: `{manifest['source_tree_sha256']}`. {len(manifest['files'])} paketerade filer verifierade mot bilden; `pip check` godkänd. App/collector/refresh ligger i samma bild.
- Föregående sökleverans: {len(manifest['prior_application_checks'])} kodhashar och {len(manifest['prior_evidence_checks'])} bevisfiler oförändrade. Inga recept, proteinmål, sökbudgetar, kampanjgodkännanden eller användarval har ändrats.
- Initial liveinsamling kördes före de smala integrationsrättningarna. Sparade verkliga svar återspelades därefter i slutlig kvalificeringsväg utan nät och utan nya observationer. Det första HTTP-provet använde den logiskt identiska bilden före Ruff-rättning av en blankrad i Coop-modulen; `http-results-final.json` verifierar det slutliga paketet på nytt. Detta får inte beskrivas som att hela liveinsamlingen upprepades i slutbilden.
- Testdata, databaser, manifest, sparade planer och rollback finns endast under `/var/tmp/smako-lund-integration-20260927`. Produktionsmanifest/data har inte skrivmonterats.

## Genomförda gemensamma integrationsrättningar

1. Coop-katalogen hade nya valfria `percentageDiscount`/`adjustedPercentageDiscount` samt beskrivande `localProduct`-fält. Den redan befintliga parsern hanterar procentfält tillsammans med uttryckligt absolut köppris. En snäv versionsbunden schemagranskare godkänner bara dessa specificerade tillägg, inte nya prisroller/villkor eller andra typbyten. Rå schemaavvikelse sparas.
2. Hemköps katalog hade valfria `energyDeclaration`-uppgifter för lampors EPREL-energimärkning, inte livsmedelsnäring. Granskaren tillåter dessa specificerade beskrivande fält och de verifierade array/null/objekt-differenserna. Sidornas antal/slutsentinel kontrolleras fortsatt. Inga generella godkännandeflaggor har införts.
3. Primat-refresh rapporterar nu första verkliga stoppet `exact_context_revalidation`. Om obligatorisk identitet/täckning fallerar utan giltig LKG stoppas körningen före de annars onödiga produktanropen. Befintligt stöd för giltig LKG och krav på komplett obligatorisk bas är oförändrat. Negativa tester för identitets- och täckningsdrift ingår.

Kod-/testlista: [integration-changes.json](integration-changes.json). **{tests['unique_test_cases']} unika regressionstestfall godkända**, {tests['executions']} testexekveringar inklusive riktade omkörningar. Ruff och compileall godkända. [Testresultat](test-summary.json).

## Faktiska aktuella källor

Ordinarie initial refresh tog 3894,82 s och avslutades med exit 1 på obligatorisk extern bas. Den lokala Willys-relayn tog 1482,83 s: 1254 faktiska HTTP-anrop, samtliga 200; 18 915 butiksposter, 10 486 unika Willys-produkt-ID. Primat gjorde 49 anrop i den ursprungliga körningen; två separata butikssvar hämtades sedan för diagnos (inga ytterligare produktanrop). Ett diagnostikskript behövde rättas efter serialiseringsfel; båda butikssvaren räknas som nätanrop. Inget spärrat fullprisflöde har upprepats utan ny grund.

Aktiva färska OWN-baskataloger: Coop Online Syd 11 481; Hemköp Karhögstorg 6188; Hemköp Brunnshög 5120; Willys Lund 10 242; Willys Nova 8673. Totalt 41 704 butiksposter före tillgänglighetsfilter. 192 markerades uttryckligen slut i lager; 41 512 återstår i PU. Coop och Karhögstorg importerades från samma dags sparade verkliga råsvar efter schemarättningen, med ursprungliga observationstider. Inga återspelningar räknas som nya hämtningar.

Första Willys-relayimporten avbröts med SQLite `OperationalError`; exakt underliggande SQLite-meddelande sparades inte. Oförändrad artefakt importerades sedan seriellt genom ordinarie inbox och godkändes, 18 915 rader/0 karantän/0 nya nätanrop. Grundorsaken till det första felet är inte bevisad. SHA-256 för relayartefakten finns i [relay-upload.json](relay-upload.json).

Kommuninventering: Coop/Stora Coop/X:-tra 10 av 778 innanför; Lidl 2 av 212; Willys 3 av 257 (två online och Hemma Stortorget som reklamblad); City Gross 0 av 38. Ingen okänd butik har tyst gjorts till Lundbutik. ICA-jobbet använder däremot befintligt ortsläge, 9 av 12 upptäckta; Hemköp befintliga godkända kontexter. Dessa är öppet redovisade kommunluckor, inte nyimplementerade funktioner.

Aktuella erbjudanden: Coop/X:-tra 503 butiksposter; ICA 219 godkända OWN → 217 PU; Lidl 28 per butik = **28 unika produkt-ID**, inte 56 nya erbjudanden; Willys Hemma 31 poster från 34 annonser/40 tolkade variant-/grupprader. Lidl: 387 kandidater per butik, 357 stoppade först vid obelagd butiksgiltighet/produkt–nationell kampanjbindning samt 2 parserkarantäner (oprövat rabattvillkor respektive icke-exakt jämförprisintervall). Det ger 28 + 359 = 387 utan dubbelräkning. Willys osäkra prisplaceringar, variant-/mängdgrupper och villkor kvarstår i karantän; gamla dokumentgodkännanden har inte flyttats till nya dokument.

[Butiksvis tabell med observationer, officiella länkar, OWN/PU, karantän och nästa uppdatering](STORE-RESULTS.md). [Fullständiga kvalificeringsuppgifter](results/source-coverage.json). Tal för prisimport betyder inte näringsgodkända produkter, och butikskopior räknas inte som ny unik täckning.

## Publicering och faktiskt serverat innehåll

Full Lund: ingen aktiv godkänd artefakt, inget serving-reload av ofullständig bas. De sex obligatoriska baskontexterna behölls. Felrapporten och manifestspärren är resultatet, inte en lyckad publicering.

Oberoende kontroll: **separat OWN-only-artefakt**, byggd med samma ordinarie PriceUniverse-byggare och aktiveringsvalidator; {serving['products']} poster i 27 kontexter. Den är aldrig ersättning för den fullständiga Lund-kandidaten. HTTP begränsades ytterligare till verifierade `physical_store` + `offers`, vilket utesluter Coop Online Syd, Willys online, Hemköps nätpris och Primats legacy-default för fysisk kanal.

Byggning och andra byggning: {builds[0]['seconds']:.3f} respektive {builds[-1]['seconds']:.3f} s väggtid. Samma produkt-/observationshash efter båda: `{serving['products_sha256']}`. Första ordinarie builderdelen tog {builds[0]['build']['timing_ms']['total']/1000:.3f} s, andra {builds[-1]['build']['timing_ms']['total']/1000:.3f} s; andra kördes med en laddad app och provprocess i samma begränsade container. Extra väggtid utanför builderns spann är inte fullständigt CPU-/I/O-profilerad och får inte tillskrivas en sökregression. Inga externa prisanrop, inga förändrade observationer. Läsning ur verklig serving-manager bekräftar identiskt innehåll. Dessa är två körningar av ordinarie byggare/atomisk aktivering, **inte** ett godkänt komplett federerat daily-refresh-prov.

## HTTP-planering – faktiska resultat

| Prov | HTTP/status | Varukorg kr | Sekunder | Köpstatus | Exakt/uppskattat/villkorat | Valda butiker |
|---|---|---:|---:|---|---|---|
{chr(10).join(table)}

Originalprofilens fyra kompletta jämförelser kördes inte: ingen färsk komplett bas kunde publiceras. Kostnad och valda rader är därför okända, inte noll. Historiska 484,73 kr används inte som nytt resultat. Originalets 15/20, 40/30/20, max två butiker, receptversioner och användarprofil är bevarade.

Det separata fysiska 15/20-provet har Willys Plus/Lidl Plus i en testkopia. Både exact och estimated stoppar med 422 DATA_BLOCKED: 96/96 middagskandidater avvisas vid produkt-/faktakvalificering, 0 når singleton-/menysökning. Första stopp utan dubbelräkning: rapsolja 17, tofu 15, rödlök 12, vitkål 12, tortillas 8, ägg 7, kokosmjölk 4, sojasås 4, linser 4, crème fraiche 3, svarta bönor/kidneybönor/kikärtor/nötfärs 1 vardera samt 6 närings-/beredningsunderlag (ris; ett fall även kyckling). Detta är begränsat till det aktuella fysiska erbjudandeunderlaget, inte bevis för global omöjlighet eller högre pris. Produktdiagnostiken är avgränsad: 551 produkter utelämnades ur detaljloggen per fritt prov, medan de 96 första receptstoppen finns sparade. Ingen full ekonomisk jämförelse finns för alternativ som stoppats tidigare.

Separat aktuell varm ostsmörgås, en frukostportion, tillåten Lidl Åkerlund och Rausings väg: **171,68 kr**, 1 exakt + 1 uppskattad rad, 0 villkorade. Lingongrova 500 g/17,90 kr med Lidl Plus; Hushållsost cirka 2,2 kg × 69,90 kr/kg = 153,78 kr, offentlig kampanj, max 3 förpackningar/hushåll. Giltigt 21–27 september. Receptet använder 100 g av varje, inte hela köpvikten. Befintliga verifierade produktdeklarationer ger 33,8 g protein mot 30 g; måltiden är `ESTIMATED` enligt insatsbaserad beredningsmetod. Priset är `VERIFIED_WITH_ESTIMATES`, audit PASS; inga produktlås, extraköp eller kandidatpatchar. Källor och deklarationshashar finns i den sparade HTTP-responsen, [officiell butik](https://www.lidl.se/s/sv-SE/butiker/lund/akerlund-och-rausings-vaeg-1/). Korgkostnaden avser hela köpet och är inte exakt slutkvitto eller påstådd besparing.

Separat åttaportionsprov för aktuellt Coop-flerköp med vanlig varm ostsmörgås och tillåtet butiksval stoppar vid saknat näringsunderlag med rätt enhet för bröd. Mängden per portion är samma 100 g bröd + 100 g ost, mål 30 g. Det är **inte ett godkänt aktuellt flerköpsmåltidsprov**; ingen ändring av mål eller gissad referens används för att få det grönt. Befintliga komponentregressioner bevisar inte detta saknade liveintegrationsfall.

Tiderna jämför inte identisk uppvärmning: första exact är kallare, estimated följer samma process; första ostprovet följer två misslyckade profilprov och det slutliga paketets ostprov är kallt. De får inte användas som en ny före/efter-prestandajämförelse. [Maskinläsbara resultat och valda produkter](profile-summary.json), [ursprungliga HTTP-responser](results/physical-probe/http-results.json), [slutpaketets HTTP-responser](results/physical-probe/http-results-final.json).

## Drift, giltighet, sparning och återställning

- Ordinarie full refresh: faktiskt genomförd och korrekt spärrad. Efterföljande ordinarie rebuildförsök utan ny extern insamling spärrat; globalt not_due för komplett Lund, komplett andra publicering/omstart och fyra kompletta profilprov är **inte verifierade**.
- Separat fysisk yta: atomisk publicering, faktiskt reload, andra builderkörning med identiska källposter och reload samt processomstart verifierade. Sparad ostplan identisk före/efter; ingen tyst omräkning.
- Frivillig Willys-källa: kopierat isolerat källtillstånd läser beständigt kommunval 1281, returnerar verkligt `not_due` med 0 prisanrop. Injicerat ConnectionError behåller giltiga godkända referenser. Återhämtning med sparade verkliga råsvar och explicit testklocka +16 minuter godkänner 31 rader; observationerna är oförändrade. Det är replay, inte ny insamling. [Driftbevis](results/optional-lifecycle.json).
- Verkligt publicerad artefakt under explicit framtidsklocka och nätförbud:
{expiry_lines}
  Äldre icke-ICA-index kan alltså fortfarande innehålla utgångna referenser tills färskhetsfiltret slår till; ordinarie användarprissättning avvisar dem före köp. ICA:s belagda kampanjundantag har separat slutdatum, inte ett generellt slopat 48-timmarskrav. Inga utgångna erbjudanden släpptes till köp i provet. [Giltighetsprov](results/physical-probe/expiry-admission.json).
- Klientprov: verklig Chromium-rendering, DOM-text och skärmbild sparade. Texten visar `ca 171,68 kr`, cirka-vikt, hel förpackning, minst 100 g användbar vikt, medlemskap och kampanjdatum. Ingen bildmodell/bildanalys. DOM-kontrollen är inte en pixelvis layoutgranskning. Allergenstatus är NOT_REQUESTED, inte verifierad allergisäkerhet.
- Isolerad rollback: gammal PersonalPlanner-modul från `/rollback`, separat kopierad plandatabas, GET 200 och identisk plan. Modulhash och faktisk planlagringssökväg finns i serving-beviset. Det bevisar **läskompatibilitet**, inte ny omräkning i äldre kod. Inga produktionsfiler har återställts eller ersatts.

## Kvarstående aktiveringsberoenden

1. Återställ/verifiera obligatorisk full bas för Clemenstorget hos Primat, eller fatta ett separat, uttryckligt beslut om annan belagd basstrategi. Denna körning tar inte bort kravet. Därefter måste komplett federering, andra ordinarie rebuild/restart/not_due och samtliga fyra fria profilprov köras med samma nya kompletta underlag.
2. Full kommuninventering i den befintliga ICA-/Hemköpsdriftkopplingen är inte visad här. En ny kedjeimplementation har inte påbörjats för att dölja detta.
3. Aktuellt fullständigt fysiskt 15/20-underlag saknas för angivna ingredienser/fakta. Aktuellt flerköpsmåltidsprov kvarstår vid brödets näringsunderlag. Öppna variantgrupper får fortsatt inte bli automatiska närings-/allergigodkända ingredienser.
4. Första relayimportens ursprungliga SQLite-fel har inte fullständig grundorsakslogg. Seriell återhämtning är visad, inte bevis att feltypen aldrig återkommer. Behåll operationslåset och undvik samtidiga tunga databasläsningar under import.
5. Malmö fullständiga aktuella publiceringsprov är separat och **olöst**. Det är inte orsaken till Lunds nuvarande Primat-stopp.
6. Historisk Lidl-fixture `reports/source-implementation-20260915/lidl_offer_adapter.py` saknas fortfarande. Dess gamla test kan inte samlas/köras: GTIN/variant/pack-/dokumentbindning, separat observationsgrund, kycklingberedning/avrunnen mängd, kolhydratgräns <0,5, korrupt deklaration och ost→recept→audit. Nyare tester och aktuellt ostprov täcker delar men ersätter inte exakt detta historiska skydd. Luckan är ett kvarstående releasebevis; den gör inte den aktuella källan automatiskt felaktig och förklarar inte Primat-felet.

Inför ett senare aktiveringsbeslut måste då förfallna källor uppdateras, 36/48-timmarsgränserna kontrolleras på verkliga observationer och kampanj-/medlems-/butiksgiltighet kontrolleras på nytt. Denna söndags flertalet erbjudanden går ut vid midnatt svensk tid; nästa befintliga kommunhämtning är 27 september 21:00 UTC (23:00 svensk tid), kampanjövergång 22:00 UTC. Det är sparad behovsplan, inte ett nyaktiverat schema. [Separat aktiveringsunderlag](ACTIVATION.md).
'''
(OUT/'VERIFICATION.md').write_text(text,encoding='utf-8')
write('PACKAGE.json',{'production_activation':False,'ready_for_activation_decision':False,'image':image,'source_tree_sha256':manifest['source_tree_sha256'],'prior_code_preserved':all(manifest['prior_application_checks'].values()),'prior_evidence_preserved':all(manifest['prior_evidence_checks'].values()),'changes':read(OUT/'integration-changes.json'),'tests':tests,'evidence_hashes':{f.relative_to(ROOT).as_posix():h(f) for f in OUT.rglob('*') if f.is_file() and '__pycache__' not in f.parts and f.name!='PACKAGE.json' and 'local-relay' not in f.parts}})
print('assembled actual results',len(store_rows),'source/store rows;',len(cases),'profile cases')
