from pathlib import Path
import json

R = Path(__file__).parent


def read(name):
    return json.loads((R / name).read_text(encoding="utf-8"))


p = read("profile-summary.json")
t = read("tests-verified.json")
runtime = read("runtime-1280/ACCEPTANCE.json")
assert p["status"] == runtime["status"] == t["status"] == "PASS"
rows = []
for arm in ("before", "after"):
    for mode in ("exact", "estimated"):
        m = p["arms"][arm]["modes"][mode]
        rows.append(f"| {arm} / {mode} | {m['cost']:.2f} kr | {m['verification']} | {m['slots']}/{m['portions']} | {m['store_count']} |")
selection = p["arms"]["after"]["modes"]["estimated"]["selected"]
chosen = "\n".join(f"| {x['store']} | {x['product']} | {x['cost']:.2f} kr | {x['quantity_confidence']} |" for x in selection)
fresh = p["arms"]["after"]["modes"]["exact"]["freshness_at_test_clock"]
runtime_rows = []
next_checks = []
for mode in runtime["verified_modes"]:
    d = read(f"runtime-1280/result-{mode}.json")
    runtime_rows.append(f"| {mode} | {d['runner_exit']} | {d['health']}/{d['ready']} | {d['flyer_products']} |")
    if mode == "not_due":
        for x in d["source_plan"]["stores"]:
            if x.get("selected"):
                next_checks.append({k: x.get(k) for k in ("store_id", "next_fetch_at", "reason", "due")})
lidl_state = read("lidl-recovery-final/1281/source-state.json")
lidl_next = [{k: x.get(k) for k in ("store_id", "next_fetch_at", "reason", "due")}
             for x in lidl_state["selection"]["stores"] if x.get("selected")]
(R / "next-source-checks.json").write_text(json.dumps({
    "scope": "isolated persisted states, not production schedule changes",
    "willys_1280": next_checks, "lidl_1281": lidl_next,
    "clock": "2026-09-24T15:00:00Z (Lidl recovery +20 minutes)",
    "observations_rewritten": False,
}, ensure_ascii=False, indent=2), encoding="utf-8")

text = f"""# Slutverifiering

## Riktig oförändrad 15/20-profil

Körningen använder den riktiga `PersonalPlanner` i privat Linux-kandidatmiljö med avsedd scheduler-image, icke-root, skrivskyddad kod/root och `network=none`. Ingen produktions-HTTP-endpoint eller aktiv användardatabas används. Förfrågan är den sparade riktiga 15/20-profilen: fem middagar à två portioner, fem frukostar och fem mellanmål; proteinminimum **40/30/20 g**, högst **två inköpsställen**. Det ordinarie recepturvalet och sökkraven är oförändrade (96 middagskandidater, 5 frukostar, 5 mellanmål). Näringsuppskattnings-opt-in kvarstår. Denna profil har inga medlemsprogram aktiverade i något jämförelseled.

Före/efter använder **samma kompletta bas, baskällornas snapshot-ID, källcache, köpdag 24 september och testklocka 2026-09-24 21:16:35.494010 UTC**. De gamla respektive nykvalificerade Willys-/Lidl-tillskotten körs genom slutkoden. Mellan exakt och uppskattat läge ändras endast `purchase_planning_mode`. Samtliga sex obligatoriska baskontexter finns i båda artefakterna; totalt {len(p['arms']['after']['contexts'])} kontexter. Inget pris- eller observationstidfält har skrivits om.

| Underlag / läge | Varukostnad | Kvalitetsstatus | Måltider/portioner | Inköpsställen |
|---|---:|---|---:|---:|
{chr(10).join(rows)}

Alla faktiskt valda köprader är exakta även när uppskattningsläget är tillåtet. Därför är `VERIFIED` korrekt för just dessa slutmenyer. De nya uppskattade/öppna erbjudandena måste inte väljas för att vara användbara; deras separata verkliga köp-/näringsprov redovisas i README och comparison.json. Ingen uppskattad besparing hävdas.

| Inköpsställe | Faktiskt vald produkt | Kostnad | Mängdunderlag |
|---|---|---:|---|
{chosen}

Källfärskhet vid jämförelseklockan: **{fresh['status']}**, äldsta användbara pris **{fresh['oldest_usable_price_age_hours']:.3f} timmar**. Vid slutrapportens verkliga kontroll är den äldsta observationen {p['arms']['after']['oldest_age_hours_now']:.2f} timmar gammal. Det historiska kompletta underlaget får alltså **inte** användas som ett påstående om aktuell publiceringsfärskhet. Ordinarie 36/48-timmarsgränser är bevarade.

Ett tidigare mellanprov hade bara åtta kontexter eftersom federerad källfiltrering fortfarande använde väggklockan. Det provet räknas inte som komplett bas. Den slutliga provklockan omfattar även federerad filtrering och innehåller en uttrycklig kontroll att samtliga obligatoriska baskontexter finns kvar. Produktionskoden och färskhetsgränserna ändrades inte för denna rättning.

Bevis: `profile-summary.json`, `profile/before-*-restored-original*.json`, `profile/after-*-restored-original*.json`, båda fulla PriceUniverse-artefakterna samt deras in-/utdata. Databas och extern cache är verifierat oförändrade; byggaren registrerar noll externa nätförsök.

## Kommun och ordinarie drift

Samma officiella inventering och kommunfunktion kördes för Lund 1281 och Malmö 1280, utan nya hårdkodade produktionsbutikslistor. `final/verification-1281.json` och `final/verification-1280.json` innehåller första och andra byggnaden med samtliga importerade kvalificerade butiksposter. Lund: **87**, Malmö: **467**. De byggnaderna är isolerade tilläggsprov, inte kompletta baskällsprov.

Slutkodens återkommande driftprov använder separat uvicorn-instans, ordinarie runner, verklig underprocess för rebuild och serving-reload mot isolerade filer. Bevarad City Gross-bas har 13 523 produkter, Willys 243 och Lidl 224. Ingen aktiv produktionskonfiguration ändras. Testklockan är **24 september 15:00 UTC**, så att kontrollen utan förfallet arbete faktiskt ligger före respektive källas förfallotid.

| Fas | Runner exit | Health/ready HTTP | Willys-poster bevarade |
|---|---:|---|---:|
{chr(10).join(runtime_rows)}

Alla faser har samma slutkodshashar, produktsignaturer och källobservationer. Omstarten är en ny process med beständigt kommunval/status. `not_due` startar ingen prishämtning eller rebuild-underprocess. Vid injicerat hämtfel behålls giltiga LKG-priser och basen fungerar; återhämtningen kör ordinarie källväg med sparade faktiska svar. En framtida runtimeklocka +49 timmar utesluter för gamla kontexter och anger förfallet källarbete. Separata datumtester spärrar erbjudanden före start och efter kampanjslut.

Lidls separata jobbprov (`lidl-recovery-verification.json`) injicerar hämtfel, kontrollerar att godkända referenser behålls, kvalificerar därefter samma verkliga råsvar genom slutversionens collector och får åter **28 poster per Lundbutik**. Omstart utan nytt kommunvärde ger `not_due`. Prisobservationerna är oförändrade. Fullflödets varning om partiell kvalificering finns kvar; 28 av 380 är inte en komplett Lidl-katalog.

Nästa källkontroller i det **isolerade** beständiga läget ligger för Willys Malmö den **25 september 18:41 UTC** och för Lidl Lund den **26 september 01:35 UTC**, enligt redan befintlig 35-timmars behovsregel. Exakta tider per butik finns i `next-source-checks.json`. Detta är inte ändrade produktionsscheman eller ett löfte om att källor har hämtats vid dessa framtida tider.

## Tester och metodgränser

**{t['unique_cases']} unika testfall passerar**, deduplicerade på testnamn inklusive parametrar med senast verifierat resultat. Den breda slutkörningen hade 678 passerade tester; övriga riktade checkout-/cache-/kompatibilitetsprov ger det större unika antalet. Original-XML/loggar och tidigare misslyckade mellanprov finns kvar. `tests-verified.json` visar exakt vilket slutprov varje testresultat kommer från. Ruff, compileall och JavaScript-syntaxkontroll passerar (`quality-final.json`).

Regressionsgruppen omfattar kg-/cirka-/styckköp, hela paket och överskott, öppna och verifierade variantgrupper, blandade hela flerköp utan restpris, gemensamma hushållstak, pant, fel butik/variant/medlemskap/datum, pris-/textkonflikt, SLV-opt-in och enheter, deklarationsidentitet, allergi-/receptspärrar, API-läge, sparade val, uppmätt lagerbokning samt kedje-/providerbakåtkompatibilitet. Den nya generiska blandgruppsbryggan provas genom riktig collector/OWN/PU med **syntetisk källa**; detta ökar inte antalet verkliga kampanjer.

**Historisk Lidl-fixturelucka kvarstår öppen**, utanför dessa passerade fall. Den har inte dolts med skip eller fabricerad fixture. De tidigare verkliga dokumentrevisionerna är inte ett nytt oberoende holdout. Fullständig aktuell Malmö-publicering och färskt komplett produktionsbasunderlag kvarstår separat.

Nätinsamling hålls isär: **0 nya prisnätanrop**, **5 nya officiella närings-/produktnätanrop**. Driftens replay, testklocka och felinjektion utgör inte livehämtning. Ingen bildanalys, bildmodell eller betald modell-API användes.
"""
(R / "VERIFICATION.md").write_text(text, encoding="utf-8")
print("verification written")
