# Reproducerbara kommandon och avgränsning

Arbetskopia: `C:\Users\ossia\Documents\Codex\2026-09-16\municipality-coverage-20260920`.
Gren: `areas/municipality-audit-20260920`. Befintlig smutsig arbetskopia bevarad;
`incremental.patch` jämför mot denna körnings egna säkerhetskopior, inte mot HEAD.
Ingen commit, reset, clean eller produktionsaktivering gjordes.

## Lokala regressioner

PowerShell, Python 3.12:

```powershell
$env:PYTHONPATH = 'backend;.'
$env:PYTHONUTF8 = '1'
py -3.12 -m pytest grocery_data/tests/test_coop_offer_job.py grocery_data/tests/test_coop_connector.py grocery_data/tests/test_coop_physical_structured.py backend/tests/test_coop_refresh_wiring.py -q
py -3.12 -m pytest grocery_data/tests/test_coop_release_entrypoint.py grocery_data/tests/test_coop_release_freshness.py grocery_data/tests/test_coop_municipal_contract.py grocery_data/tests/test_offer_rows.py backend/tests/test_coop_municipality_provider.py backend/tests/test_coop_physical_pipeline.py backend/tests/test_coop_municipality_household.py backend/tests/test_campaign_demand_refresh.py -q
py -3.12 -m compileall -q backend/app grocery_data/app grocery_data/scripts deploy/scripts
```

Ruff kördes för samtliga ändrade Pythonmoduler; exakta testfall och resultat finns
även i de sex JUnit-filer som sammanställs i `verification.json`. Oförändrade
ICA-gräns-, checkout-, närings- och byggtester återanvänds där deras kod är hashstabil.

## Privat paketerad serverkörning

`remote.py` använder befintlig SSH-åtkomst utan att skriva ut miljöhemligheter.
Inga betalda API-anrop. Testkatalogen är
`/var/tmp/smako-coop-refresh-integration-20260922`; datavolym `data/lifecycle`.
Container `smako-coop-refresh-integration-test`, UID 10001, högst två CPU/5 GiB,
512 MiB temporärdisk. Applikationskoden ligger enbart i imagen. Befintliga
produktionskällor är skrivskyddade; det ordinarie operationslåset återanvänds
vid den inledande källfrysningen. Cyklernas egna publiceringar använder privat lås.

Genomförda kommandon, med prefix
`py -3.12 reports/coop-refresh-integration-20260922/remote.py`:

```text
freeze
initialize
prepare-raw
stage
build
cycle-a
cycle-b
cycle-base
cycle-c
cycle-fetch-failure
cycle-recovery
cycle-xtra
cycle-xtra-off
cycle-reload-failure
stage
build
cycle-withdrawal
stage
cycle-expiry
cycle-final-recovery
cycle-final-plan
final-checks
retrieve
```

`stage/build` återkom när slutkoden eller endast testharnessen ändrades;
`package-result.json` och `code-closure.json` binder den sista imagen till koden.
Kontrollera tidsstämpel och image-SHA i releaseunderlaget. Tidigare cykelevidens
återanvänds endast för oförändrade delar; ändrad nollsvarshantering och därefter
färsk hämtning, rebuild och planering kördes om på slutimagen.

Cyklerna kör ordinarie `run_daily_refresh.main()` eller dess befintliga låsta
refresh/reload-väg. Lokal basrebuild använder befintligt
`--chain citygross --no-external-refresh`; detta är inte ett Coop-byggargument.
`cycle-base` hämtar verklig Primat-bas och bygger med den kompletta frysta OWN-basen.
Kommuninsamlingen väljs automatiskt från beständigt tillstånd även när byggjobbet
begär enbart basuppdatering. Ingen särskild testbyggare ersätter publiceringskedjan.

Felinjektionerna och köpdatumsklockan finns **bara i testharnessen**. Nollsvarsprovet
muterar ett sparat butiksspecifikt svar, bevarar observationstid och kör riktig
parser/collector/OWN. Utgångsprovet ändrar Coop-providerns köpdatum, inte basens
färskhetsklocka eller källobservationer. Återhämtningen gör ett nytt verkligt anrop.
Dessa prov får aldrig köras med produktionsdata som skrivbar testvolym.

En ny oberoende återkörning ska ha en ny uttryckligt namngiven privat testkatalog
och ny källfrysning. Skripten vägrar skriva över initialiserade bevis; rensa inte
föregående data för att återanvända ett namn. Tidsgränser och kampanjer måste
valideras på nytt. Inga gamla rapportdatum räknas som aktuella.

Övriga genomförda kontroller:

```powershell
py -3.12 reports/coop-refresh-integration-20260922/package_inventory.py
py -3.12 reports/coop-refresh-integration-20260922/check_compose.py
py -3.12 reports/coop-refresh-integration-20260922/scheduler_probe.py
py -3.12 reports/coop-refresh-integration-20260922/decision_snapshot.py
py -3.12 reports/coop-refresh-integration-20260922/inspect_live.py
py -3.12 reports/coop-refresh-integration-20260922/verify_delivery.py
py -3.12 reports/coop-refresh-integration-20260922/build_report.py
```

Composekontrollen parsar endast konfiguration. Schedulerprovet skriver endast i
en privat containers tmpfs och fångar cron-starten innan en daemon startas.
`decision_snapshot.py` och `inspect_live.py` läser status. Verklig skarp start
är ett separat operatörsbeslut enligt `RELEASE-COOP-REFRESH.md`.
