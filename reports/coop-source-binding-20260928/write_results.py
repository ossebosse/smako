import json
import xml.etree.ElementTree as ET
from pathlib import Path

P=Path(__file__).parent
def read(name):return json.loads((P/name).read_bytes())
a=read('acceptance.json');image=read('image.json');profiles=read('profile-summary.json')
assert a['status']=='PASS'
bindings={r['id']:r for r in read('binding-comparison.json')}
transition=read('campaign-transition.json')
source=read('results/final-source-audit.json')
coverage=read('results/source-coverage.json')
tests=ET.parse(P/'final-regression.xml').getroot().find('testsuite').attrib
assert tests['failures']==tests['errors']==tests['skipped']=='0'
lines=['# Resultat: återställd aktuell Coop-källa', '',
    '**PASS i isolerad femkällorskandidat. Ingen produktionsaktivering.**', '',
    'Grundorsak och förväntade/observerade identitetsfält finns i [ANALYSIS.md](ANALYSIS.md). Två nya villkorsfält avvisades av det stängda schemat och gav missvisande identitetsfel. Nu bevaras villkoren och spärras per berörd rad. Providerns explicita versionslista omfattar v3 och den granskade v4; okända versioner är fortsatt spärrade.', '',
    '## Faktisk insamling och serving', '',
    'Ny verklig insamling: 28 september 2026, 11:01 UTC, från varje upptäckt butiks egen officiella sida/API-bindning. Kommuninventeringen har tio inside och 768 outside, inga unknown: nio strukturerade Coop/Stora Coop samt separat X:-tra. Inventeringen återanvändes inom giltig kontrolltid. Inga erbjudanden kopierades mellan butiker.', '',
    '| Butik (ID) | Källa/ledger | Godkänd kampanjperiod | Hämtade varianter | Källbindning/schema | Radgodkända | Karantän | Serving före → efter | Nästa rebuild/omstart |',
    '|---|---|---|---:|---|---:|---:|---:|---:|']
for r in sorted(a['rows'],key=lambda r:r['store_id']):
    ledger=bindings[r['store_id']]['expected']['ledger_account_number']
    periods=', '.join(start+'–'+end for start,end in r['periods'])
    lines.append(f"| {r['name']} ({r['store_id']}) | [API {ledger}]({r['source_url']}) | {periods} | {r['parsed']} | PASS | {r['approved']} | {r['quarantined']} | {r['serving_before']} → {r['serving_after']} | {r['after_next_rebuild']} / {r['serving_after']} |")
lines += ['',f"Totalt {sum(r['parsed'] for r in a['rows'])} hämtade butiksbundna variantrader, {sum(r['approved'] for r in a['rows'])} godkända och {sum(r['quarantined'] for r in a['rows'])} karantän. Det är butiksposter, inte lika många unika varor. Ingen av de nio butikerna har noll godkända poster. Detta är fortsatt partiell erbjudandetäckning, inte godkänt fullsortiment. Befintlig full-snapshotstatus och kvalitetsgräns har inte skrivits om.", '',
    'X:-tra Skansvägen (3658) är separat: befintligt officiellt PDF-underlag observerat 28 september 07:03 UTC, kampanj 28 september–4 oktober, sex serving-poster före/efter/rebuild/omstart. Ingen ny X:-tra-hämtning gjordes; dess källa, felstatus och nästa hämtning hålls separat.', '',
    f"Den faktiska appinstansen ökade från {a['products_before']} till {a['products_after']} poster. Samtliga fem obligatoriska onlinekontexters poster, source-snapshots och observationer är exakt oförändrade. Coop Online Syd är fortfarande online_fulfillment/online_price, inte en fysisk Coop-butik.", '',
    '## Publicering, omstart och negativt prov', '']
for label,title in [('publish','Ordinarie import/rebuild/publicering/reload med slutlig image'),('fault-final','Nästa ordinarie rebuild med uttryckligt injicerat frivilligt Coop-jobbfel')]:
    run=read('results/'+label+'-result.json')
    lines.append(f"- {title}: exit {run['exit']}, {run['seconds']:.2f} s; reload verifierad mot faktisk appinstans.")
lines += ['- Andra bygget behöll exakt samma produkthash och godkända Coop-källreferenser. Felet redovisas i ordinarie refreshrapport som failed_optional_source/ConnectionError. Fungerande obligatorisk bas och fortfarande giltiga Coop-erbjudanden finns kvar.',
    '- Två faktiska appstarter vid HTTP-proven läste samma serving-innehåll. Samtliga nya Coop-kontexter och antal verifierades efter omstart; noll utgångna fysiska Coop-erbjudanden fanns i serving.',
    '- Dessa lokala rebuild-/HTTP-prov kördes utan extern nätåtkomst. Orelaterade optional-hämtningar var uttryckligen uppskjutna i testharnessen, men deras ordinarie provider/import var kvar. Inga basobservationer föryngrades.', '',
    '## Kampanjövergång med verkliga sparade utgåvor', '',
    'Replay av 27 september respektive de faktiskt nyhämtade svaren 28 september, med respektive oförändrade observationstider. Detta är inte en ny hämtning. För alla nio butiker skiljer sig dokumenthash och nytt radgodkännande. Ett gammalt dokumentgodkännande återanvänds inte för den nya utgåvan.', '',
    '| Butik | Godkända i sparad 27/9-utgåva | Utgångna vid 28/9 | Godkända i ny utgåva | Utgångna som följde med |',
    '|---|---:|---:|---:|---:|']
for r in sorted(transition['rows'],key=lambda r:r['store_id']):
    lines.append(f"| {bindings[r['store_id']]['name']} | {r['old_approved']} | {r['old_expired_by_new_date']} | {r['new_approved']} | {r['expired_reappearing']} |")
lines += ['', 'De sex tidigare fortsatt giltiga Stora Coop-raderna hade period 21 september–4 oktober. Aktuella butiksbundna källsvar och godkännanden prövas på nytt; tidigare bevis tillåter inte andra butiker eller nya villkor.', '',
    '## Planering, checkout/audit och sparning', '',
    'Ordinarie /api/plans på samma godkända femkällorsprofil: 15 måltider/20 portioner, samma näringskrav, butikstak och ursprungliga val. Original/Plus-kopian och exact/estimated prövas separat. Ingen receptändring eller höjd sökbudget.', '',
    '| Profil | HTTP | Kostnad kr | Köpstatus | Checkout/audit | Sparad GET / omstart |',
    '|---|---:|---:|---|---|---|']
for r in profiles['cases']:
    lines.append(f"| {r['case']} | {r['http_status']} | {r['cost']:.2f} | {r['purchase_status']} | PASS, totals reconciled | PASS / PASS |")
lines += ['', 'Fulla requests, produktval, antal förpackningar, nutrition och audit finns i `results/http-results.json` och `profile-summary.json`. Planeringens nätåtkomst var spärrad. Godkänd källimport betyder inte att varje erbjudande har nödvändiga närings-/receptmappningar eller blir valt av planeraren.', '',
    '## Kvarstående hinder och releasebeslut', '',
    'Ingen extern uppgift behövs för den rättade schema-/versionskonflikten. Nya krav på andra inköp och prissteg är fortfarande uttryckligt spärrade eftersom den befintliga köpmodellen inte hanterar dem. Övriga redan kända radblockerare är kvar; exempelvis pant kräver uttryckligt belopp och rörliga paket kräver faktiskt köpunderlag. Dessa får inte göras köpbara genom antaganden.', '',
    '`lund-own-five-base-20260928-v1` kvarstår som verifierad alternativ releasekandidat med detta isolerade Coop-tillägg. Originalpolicyn och dess Primat-hinder är oförändrade. ICA/Hemköps kommunluckor, äldre PurchaseTerms-kopplingar, Lidls/Willys nya kampanjbortfall, Malmö-publicering och historisk Lidl-fixture är separata, fortsatt olösta uppgifter. Tidigare femmiddagsmilstolpe påverkas inte.', '',
    f"Slutregression: {tests['tests']} tester PASS, Ruff och compileall PASS; 589 imagefiler hashverifierade, beroendekontroll PASS. Lund och annan kommun täcks av befintliga retained-data-regressioner; ingen ny Malmö-publicering påstås. Tidigare kandidatens 337 bevisfiler är hashverifierat oförändrade.", '',
    f"Isolerad image: `{image['tag']}`, `{image['image']}`. Produktion står kvar på `/opt/smako/releases/price-recovery-lund-20260914a`. Privat basbackup, tidigare kandidat och samtliga mellanresultat finns kvar. Ingen ändring av produktionspolicy, schemaläggning, Windows, databasstruktur, Primat, användarval eller betalt API."]
(P/'RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
