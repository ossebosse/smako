"""Produce the bounded release record from measured packaged results."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE=Path(__file__).resolve().parent
ROOT=HERE/'server-results/lifecycle'
def read(p): return json.loads(p.read_bytes())
def local(value):
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZoneInfo('Europe/Stockholm')).strftime('%Y-%m-%d %H:%M:%S') if value else '—'

checks=read(ROOT/'final-checks.json')
verification=read(HERE/'verification.json')
decision=read(HERE/'decision-state.json')
state=read(ROOT/'municipal/1281/source-state.json')
package=read(HERE/'package-result.json')
final=read(ROOT/'cycle-final-plan.json')
assert checks['final_recovered_rows']==final['coop_products']==493
assert decision['publication']['status']=='reloaded'
assert final['planning']['status']==201 and final['planning']['saved_equals_readback'] and all(final['planning']['audits'])
labels={
 'cycle-a':'A: verklig insamling, första publicering',
 'cycle-b':'B: ny lokal rebuild, ingen Coop-hämtning',
 'cycle-base':'B2: verkligt uppdaterad Primat-bas, kvarvarande Coop',
 'cycle-c':'C: ny process, endast beständigt kommun-/källtillstånd',
 'cycle-fetch-failure':'D: injicerat transportfel för en förfallen butik',
 'cycle-recovery':'Verklig återhämtning från samma butik',
 'cycle-xtra':'X:-tra på, verklig butiksspecifik PDF-hämtning',
 'cycle-xtra-off':'X:-tra av, Coop kvar',
 'cycle-reload-failure':'Injicerat reloadfel, separat väntestatus',
 'cycle-withdrawal':'Slutkod: verifierat nollsvar (muterat testunderlag)',
 'cycle-expiry':'Slutkod: kampanjutgång (explicit köpdatum i Coop-provider)',
 'cycle-final-recovery':'Slutkod: verklig återhämtning efter nollsvar/utgångsprov',
 'cycle-final-plan':'Slutkod: nästa rebuild, reload och 15/20'}
lines=[]
for mode,label in labels.items():
    r=read(ROOT/(mode+'.json'))
    lines.append(f"| {label} | {r['coop_products']} | {r['exit_code']} | {r['seconds']:.1f} s | {r['health']}/{r['ready']} |")
rows=[]
for r in state['selection']['stores']:
    if not r['selected']:continue
    disabled=r['concept']=='X:-tra' and not decision['configuration']['xtra_enabled']
    rows.append(f"| {r['name']} ({r['store_id']}) | {local(r.get('last_fetch_at') or r.get('last_success'))} | {local(r.get('next_fetch_at'))} | {'Avstängd; sparad tid gäller vid återaktivering. ' if disabled else ''}{r.get('reason')} |")
base=[]
for name,r in decision['schedule']['sources'].items():
    base.append(f"| {name} | {local(r.get('observed_at'))} | {local(r.get('next_fetch_at'))} | {local(r.get('hard_stop_at'))} | {r['reason']} |")
plan=final['planning'];p=plan['plan'];basket=p['optimized_basket']
ids=sorted({i['product_id'] for store in basket['stores'] for i in store['items']})
selected_coop=[i for store in basket['stores'] for i in store['items'] if i.get('chain')=='coop' and i.get('coverage')=='offers_only']
store_names=', '.join(store['store_name'] for store in basket['stores'])
summary={
 'at':decision['at'],'image_id':package['image_id'],'private_universe_id':final['universe_id'],
 'coop_rows':493,'xtra_enabled_rows':9,'activated_in_production':False,
 'technical_status':'verified_partial_release_candidate','planning':{k:plan[k] for k in ['status','seconds','cost','saved_equals_readback']},
 'audits':{'count':len(plan['audits']),'all_pass':all(plan['audits'])},
 'store_count':basket['store_count'],'selected_product_ids':ids,'selected_municipal_coop_rows':len(selected_coop),
 'next_updates':decision['schedule']['sources'],'source_schedule':state['selection']['stores'],
 'rollback':checks['private_publication'],'remaining_code_blockers':[],
 'operator_prerequisites':['Separate activation decision','Fresh base/offer and compatible rollback checks at activation','Approved image and flags in existing durable volumes; never copy test state','Coordinate separately with pending ICA package and existing demand tick']}
(HERE/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
text=f'''# Coop/X:-tra: ordinarie refresh/rebuild – separat releaseunderlag

Kontrollerat {local(decision['at'])} Europe/Stockholm. **Tekniskt verifierat i isolerad driftmiljö; inget aktiverat i produktion.** Ingen Windows- eller aktiv schemaändring. Ingen bildmodell eller betald API. Den väntande ICA-leveransen, Primat och användardata är bevarade.

## Beslut och exakt omfattning

Redo för separat aktiveringsbeslut för den partiella kommunstyrda Coop/Stora Coop-integrationen. Slutkodens ordinarie byggväg ger **493 aktuella butik–variantposter i nio Lundbutiker**. X:-tra kan aktiveras separat: den verkliga textinsamlingen gav **9 aktuella poster**, totalt 502 när tillägget var på. Full reklambladstäckning eller komplett sortiment påstås inte.

Inga kvarstående kodblockerare identifierades i dessa kontroller. Operatörsbeslut och ny färskhetskontroll krävs före skarp aktivering. Testvolymen innehåller även tydligt märkta felfall och får **inte kopieras till produktion**; ett rent första ordinarie jobb skapar riktiga beständiga källreferenser.

Verifierad image: `smako-coop-candidate:refresh-integration-20260922`, `{package['image_id']}`. {verification['packaged_modules_verified']} paketerade moduler hashkontrollerade mot slutkoden. Samma befintliga startväg, `/opt/ica-venv` och UID 10001 verifierade; Playwright {package['runtime']['dependencies']['playwright']}. Appkoden ligger i imagen. Endast privata data och testharness monterades. Två CPU och 5 GiB minnesgräns; ingen flerdagarsstabilitet påstås.

## Ändrad ordinarie väg

`deploy/scripts/run_daily_refresh.py` → befintligt operationslås → `python -m grocery_data daily-refresh` → `coop_offer_job.run_offer_job` för förfallna kommunbutiker → befintlig collector/validering/OWN → `_build_production_price_universe` läser godkända beständiga källreferenser → befintlig PriceUniverse-byggare/publicering → skyddad runtime-reload. Alla senare byggen läser källreferenserna automatiskt; inga manuella Coop-byggargument behövs.

`source_plan` är en lokal förfallokontroll utan prisanrop. Kommunval, källversioner, kampanjtillämplighet och publiceringsstatus ingår i lokal byggversion. Giltigt underlag hämtas inte om vid basrebuild. En separat publicerings-/reloadretry behövs även om Coop-innehållet är oförändrat.

Beständig standardroot: `/srv/app/var/grocery/coop-municipal-offers` i befintlig grocery-volym. `config.json` sparar kommun, flaggor och city-bindning; `<kommunkod>/source-state.json` sparar hela inventeringen, val, felstatus, godkända relativa OWN-referenser med hash, nästa uppdatering, byggkvitto, publicering och reload. `attempts/` bevarar immutable råunderlag och snapshots. Befintlig demand-status ligger i `DEMAND_REFRESH_STATE_PATH`. Ingen ny prisdatabasarkitektur eller parallell prissättare.

Hämtning, källgodkännande, publicering och reload har separata tidsfält. Misslyckad hämtning behåller endast fortfarande giltiga godkända referenser. Validerat tomt flöde återkallar just den butikens tidigare referenser; felaktigt/saknat/otydligt flöde är inte tomt. Alla försök använder befintligt operationslås och atomiska tillståndsbyten.

## Uppmätta cykler

| Prov | Coop + eventuell X:-tra i publicerat PU | Jobbexit | Körtid | Health/ready |
|---|---:|---:|---:|---|
{chr(10).join(lines)}

Första nio-butiksinsamlingen och basuppdateringen gjorde verkliga nätanrop. Omstart återanvände samma beständiga testvolym, utan initial inventeringsfil eller kommunflaggor. Pris, fysisk butik, paket, kampanjvillkor och proveniens jämfördes mellan A/B/basrebuild, inte bara HTTP-status eller antal.

Felfallet på Värpinge var en explicit transportinjektion. Nollsvarsprovet muterade ett bevarat verkligt källsvar och körde normal parser, collector, OWN, rebuild och reload; det är **inte** ett påstående om ett verkligt tomt flöde. Endast Värpinges 55 poster försvann: 493 → 438. Ny verklig hämtning återställde kvalificerat underlag. Produkterna är återobserverade, inte 55 nya produktidentiteter.

Utgångsprovet satte en uttrycklig framtida **inköpsdag i Coop-providern**, efter de bevarade kampanjernas slut. Samma ordinarie jobb publicerade då noll Coop-poster med giltig bas kvar. Baskällornas färskhet använde verklig klocka. Separat checkoutprov avvisade det utgångna gruppköpet. Inga observationstider flyttades. Verkliga kampanjbyten över flera dagar har inte observerats. Färska källor ersatte äldre underlag; utgångna Stora Coop-avtal återanvändes inte som fallback. Antalen avser de faktiska nya källsvaren.

Reloadfelet gav exit 2 och `publication_or_reload_pending`, med oförändrad senaste lyckade reload och 15 minuters retry. Slutprovet kvitterade exakt publicerat PU-ID och återställde `reloaded`. Publiceringsvalidering avvisade en injicerad ogiltig artefakt utan att ändra privat aktivt manifest. Giltig rollback och omstartens återläsning passerade; rollback med +48 h testklocka avvisades.

## Slutkodens planering och prisbevis

Ny ordinarie rebuild efter återhämtningen följdes av verkligt HTTP-planeringsanrop mot privat app och separat testidentitet: HTTP {plan['status']}, **{plan['cost']:.2f} kr**, {plan['seconds']:.3f} s. Oförändrad 15/20-profil, fryst receptpool, 40/30/20-krav, inga medlemskap och högst två inköpsställen. {len(plan['audits'])} interna basket-audits passerade; sparad plan var identisk efter återläsning. Full meny, valda produkter, butikskombination och köp finns i `server-results/lifecycle/cycle-final-plan.json`. Ingen ny besparing påstås.

Representativt Coop-gruppköp verifierades separat med riktig produkt/matchning/checkout/audit: Kärnvetemjöl, **2 × 2 kg för 26 kr**, utan fabricerat ordinarie restpris. Godkända produkter tvingades inte in i vinnande meny. Prisroller, medlemskap, köpgränser och tidigare näringsrättningar behölls. Näringsreferensversion och samtliga 15 valda näringskontroller är identiska med B2. Katalogens samlade facts_version skiljer sig mellan insamlingscyklerna; detta är inte en ny parad besparingsjämförelse. Båda versionerna finns i `facts-continuity.json`.

Slutligt privat PU: `{final['universe_id']}`. Produktionsmanifestets SHA-256 är fortsatt `{decision['production_manifest_sha256']}`; produktionens image och health/ready kontrollerades separat i `live-health.json`.

## Nästa uppdatering och färskhet vid beslutet

Alla tider nedan är Europe/Stockholm. Det är **testkandidatens beräknade tider**, inte ett installerat produktionsschema.

| Baskälla | Verklig äldsta observation | Nästa kontroll/hämtning | Hårt stopp | Skäl |
|---|---|---|---|---|
{chr(10).join(base)}

En redan passerad tid betyder förfallet arbete för nästa ordinarie behovskontroll. Baspriserna har kvar varning vid 36 h och stopp vid 48 h. Fulla källsnapshotar användes; den begränsade lokala sökprojektionen byggdes aldrig om till bas. Primat uppdaterades med verklig transport under B2; andra fortfarande giltiga baskällors ursprungliga observationer bevarades.

| Kommunbutik | Senaste lyckade verkliga observation | Nästa källkontroll | Skäl/status |
|---|---|---|---|
{chr(10).join(rows)}

Coop/X:-tra behåller sin befintliga 35 h kontroll före 36/48 h-gränserna, eller tidigare kampanjgräns. Detta är ingen daglig fullhämtning. Misslyckad källa får 15 minuters första retry och begränsad backoff; källans giltighet förlängs aldrig. Kampanjstart/-slut utlöser lokal ombyggnad, medan checkout också kontrollerar köpdatum oberoende av scheduler. Nästa inventeringskontroll: {local(state['selection']['next_inventory_check'])}. X:-tra avstängt innebär inga X:-tra-prisanrop.

Verifierat rollbackunderlag: `{checks['private_publication']['rollback_sha256']}`. Äldsta basobservation {local(checks['private_publication']['oldest_base_observed_at'])}; hårt stopp {local(checks['private_publication']['rollback_valid_until'])}. Dessa tider måste kontrolleras på nytt vid aktivering; artefaktens byggtid är inte dess prisobservation.

## Tester, evidens och nästa operatörssteg

{verification['pytest_unique_cases']} unika berörda regressioner passerade, Ruff och compileall passerade. Se `verification.json`, `code-closure.json`, `scheduler-bootstrap.json`, `compose-check.json` och `server-results/lifecycle/final-checks.json`. Schedulerbootstrap skapade endast privat containerkonfiguration; ingen cron-daemon eller produktionsuppgift startades. Malmö och X:-tra-formatluckor från tidigare leverans kvarstår separat; ingen ny kommuninventering gjordes.

1. Besluta separat om Coop-aktivering och eventuell X:-tra-opt-in. Bekräfta image-SHA, beständig volym och körkonto. Använd det förberedda `deploy/coop-runtime.override.yaml` med befintlig Compose och `--no-build`; det har ännu inte tillämpats.
2. Hämta förfallna baskällor genom deras befintliga godkända transport och säkerställ färskt kodkompatibelt rollbackunderlag precis före aktivering. Återanvänd inte denna rapports gamla tidsstämplar som nytt underlag.
3. Låt rent ordinarie refresh-jobb skapa municipal state i produktionsvolymen, validera, publicera och kvittera reload. Ingen manuell tillskottslista eller särskilt byggskript behövs. Behåll användarnas profiler och områdes-/butiksval.
4. Samordna bild/tagg/flaggor och befintlig lätt demand-tick med den väntande ICA-releasen som **separat operatörssteg**. Denna leverans ändrar inte ICA-aktivering, Windows-uppgift eller aktiva scheman. Kontrollera health/ready och ett separat sparat/återläst testanrop efter ett framtida godkänt skarpt steg.

Exakta genomförda kommandon och privata kataloger finns i `COMMANDS.md`. Inget av ovanstående operatörssteg har utförts i produktion.
'''
(HERE/'RELEASE-COOP-REFRESH.md').write_text(text,encoding='utf8')
print('Wrote measured release record')
