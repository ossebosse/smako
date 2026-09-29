# Verifiering och reproduktion

Arbetsgren `areas/municipality-audit-20260920`, bas-HEAD `02ad73b8491f4b30679b3151b52686e27bedb8e6`. Tidigare ocommittat arbete bevarat. `initial-state.json` och `backups/` beskriver läget före denna ändring; `incremental-changes.patch` avgränsar tillägget från tidigare ICA/Coop/X:-tra-arbete. Ingen commit eller återställning utförd.

## Regressioner

180 tester, 0 fel, 0 överhoppade, 236,330 s (`tests-final.xml`). Testklockor och sparade fixtures är **inte** färsk nätinsamling. Fixture-registret/SCB-gränserna kommer från den verkliga kontrollen; testernas prisrader är uttryckliga syntetiska kontraktsfall.

```powershell
$env:PYTHONPATH = "backend;."
py -3.12 -m pytest -q grocery_data/tests/test_willys_parser.py grocery_data/tests/test_willys_client.py grocery_data/tests/test_source_artifact.py grocery_data/tests/test_local_relay.py grocery_data/tests/test_willys_municipality.py grocery_data/tests/test_municipality_area.py grocery_data/tests/test_coop_municipal_contract.py grocery_data/tests/test_campaign_refresh_policy.py backend/tests/test_own_provider.py backend/tests/test_willys_municipal_provider.py backend/tests/test_production_price_universe_build.py backend/tests/test_coop_refresh_wiring.py backend/tests/test_campaign_demand_refresh.py
```

Verifierat: kommunurval Lund/Malmö, Limhamn/Oxie trots annan adressort, okänd position, dubblett-ID, fel kommunkontext, obligatoriskt explicit tillval, oberoende fullständighetskontroll, identisk omkvalificering utan föryngring, ändrat pris med gammal tid avvisat, idempotent import, förhindrad tyst återgång till gammalt adressortsurval, återstartat relä utan förfallet arbete, 48-timmarsstopp, exakt butik/adress/kanal samt stopp före publicering när en godkänd kommunbutik saknas. Befintliga kampanj-/Coop-regressioner ingår.

Ruff för alla ändrade applikations-/testfiler och compileall för berörda moduler passerade. Konfigurationsöverlagringen har kontrollerats separat: den förmedlar bara `WILLYS_MUNICIPAL_CONFIG`, utan image-, volym- eller schemaändringar.

## Verklig källinsamling

```powershell
# Endast separat lokal insamling; ingen push/import till betan.
py -3.12 -m grocery_data.source_cli collect willys --municipality 1281 --workspace <ny-beständig-Lund-testkatalog>
py -3.12 -m grocery_data.source_cli collect willys --municipality 1280 --workspace <ny-beständig-Malmö-testkatalog>
```

Använd inte dessa kommandon för att i onödan hämta om redan giltigt underlag. Ordinarie relä läser sparat kommunval och uppdateringskvittens från samma katalog och kontrollerar förfallotid lokalt. **Reläets ordinarie överförings-/aktiveringssteg riktar sig till drift: kör dem först efter ett separat beslut.** `not_due.py` injicerar spärrar mot samtliga sådana anrop och visar två verkliga separata processer med noll externa anrop.

Lund: återanvändning av komplett verklig insamling 22 september 01:31–01:59 Stockholm, omkvalificerad med samma råfält och observationer. Ingen ny Lund-prisobservation påstås. Registret och båda kommungränserna kontrollerades på nytt 22 september 18:14.

Malmö: faktisk insamling 22 september 18:18–19:11 Stockholm. Första försöket stannade på den äldre tvåbutiksbudgeten 1 500 anrop, utan HTTP-/åtkomstfel. Slutkoden beräknar budget från kommunurvalet (4 100 för fyra onlinebutiker). `resume_malmo.py` återanvände endast de två oberoende verifierade kompletta butiksbatcherna med originaltider; ofullständiga sidor återanvändes inte. Ytterligare 1 261 verkliga anrop, samtliga HTTP 200, 0 challenges. Totalt 2 761 betjänade anrop i kontrollen; kvarvarande slutartefakt innehåller 2 557 dokument. Källa, nätanrop och återanvändning redovisas separat i `malmo-resume-result.json`.

## Paketerad privat serverkörning

`remote.py` bygger från befintligt verifierat Coop-paket, med aktuell applikationskod **kopierad i imagen**. Ingen monterad utvecklarkod, ingen skarp datavolym. 276 paketerade Python-filer har hashjämförts mot arbetskopian: inga skillnader (`package-code-closure.json`). Isolerad sökväg `/var/tmp/smako-willys-municipality-20260922/data`, UID 10001, 2 CPU, 5 GiB, nätverk avstängt utom processens loopback. Testdrivern är separat från applikationskoden.

Lunds vanliga `run_daily_refresh._run_locked` → `build_refresh_command` → källinbox → validering/OWN-promotion → produktionsbyggare → privat atomisk publicering → reload kördes under befintligt operationslås. `--chain citygross --no-external-refresh` begränsar provet till lokal rebuild av redan komplett underlag; inga City Gross-anrop görs. Komplett tidigare testdatabas och hashkontrollerad full Primat-cache används, inte sökprojektionen. 493 kommunbaserade Coop-poster bevaras.

Andra rebuild och ytterligare omstart använder samma beständiga volym, konfiguration och källreferenser i nya processer. Det är upprepade lokala rebuilds, **inte** två nya basinsamlingar. `server-results/result-cycle-final-a.json`, `result-cycle-b.json` och `result-cycle-restart.json` innehåller prispostsignaturer, verkliga observationer, publicering/reload, health/ready och explicit framtida testklocka.

Malmös fulla Willys-katalog importeras via samma inbox/collector och byggs med samma produktionsbyggare under operationslås. Omstart och ombyggnad använder samma volym. Detta är en **OWN-only kandidat**, inte ett fullständigt federerat Malmö-driftprov med färsk Primat-bas. Ingen sådan bas har gissats eller ersatts med Lunds priser. Därför påstås inte att Malmös hela ordinarie federerade publicering/reload är nätverifierad.

## Säkerhetsgränser

Inga bildmodeller, betalda modell-API:er, Windows-uppgifter, aktiva scheman eller produktionsmanifest ändrades. `production-readonly-check.json` visar skarpt manifest och image vid läskontrollen. Första privata körningen tappade Willys på grund av postnummerformat; den är sparad som felsökningsbevis och räknas inte som acceptans. Rättningen och stoppkontrollen ingår i alla slutliga lyckade rebuilds.

Ingen ny 15/20-jämförelse eller besparing påstås. Denna etapp verifierar kommunurval, dataväg och återkommande livscykel; tidigare Coop-menykontroll är separat evidens.
