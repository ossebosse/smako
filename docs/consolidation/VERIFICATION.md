# Verifiering av lokal konsolidering

Verifieringen pågår på konsolideringsgrenen. Denna mellanliggande commit etablerar
återställningsrutinen så att den kan prövas från en ren klon. Slutresultat läggs
till i en efterföljande commit innan huvudgren och lokal tagg etableras.

## Jämförelsebas

Applikationskoden i den valda arbetskopian matchade samtliga 593 filer i v5-paketet.
Basproven kördes med denna kod i isolerad kopia, med nytt Python 3.12-venv,
dotenv avstängt, sparat underlag och spärrade externa anslutningar/äldre kodrötter.
Första avgränsade passet: 586 passed, 25 failed, 21 errors. Fyra assertion-fel gäller
Coops äldre produktantal; övriga avser saknat historiskt Lidl-underlag eller stora
PDF-/JSON-filer som ännu inte kopierats. Dessa fel räknas inte som produktregressioner.
Efter autentisk dataåterställning gav omkörningen 63 passed och två fel: ytterligare
en PDF som därefter återställdes samt ett befintligt mock-benchmarkfel.

Basfel som ska jämföras med slutversionen:

- `backend/tests/test_coop_physical_pipeline.py::test_real_own_universe_checkout_and_audit[3839-44]`: 93 produkter mot äldre förväntan 44.
- Samma test `[3815-77]`: 246 mot 77.
- `grocery_data/tests/test_coop_municipal_contract.py::test_actual_second_municipality_pdf_bound_to_store_not_shared_prices`: 18 mot 10.
- `grocery_data/tests/test_coop_municipality.py::test_real_stora_age_conditions_stay_in_quarantine_not_global_failure`: 384 mot 77.
- `backend/tests/test_benchmark_diversity_modes.py::test_mock_diversity_benchmark_uses_one_snapshot_for_all_modes`: Too few quality-valid candidates.

Dessa tester har inte tagits bort, markerats xfail eller ändrats för att skapa
ett grönt resultat. Fullsviteförsöket före de avgränsade proven avbröts och räknas
inte som ett färdigt testresultat. Historiska rapporters påstådda 457 regressioner
är inte ersättning för denna nya verifiering.

## Redan utfört

- Historiskt plannerprov från `test_warm_offer_meal.py`: planering, audit,
  SQLite-sparning och återläsning PASS; testklocka 2026-09-24 21:16 UTC.
- Ruff på `backend/app`, `grocery_data/app` och nya Python-hjälpare: PASS.
- Compileall på backend, grocery_data och scripts: PASS.
- `pip check`: PASS.
- Frontend: 30/30 tester, syntaxkontroller och esbuild PASS. Byggd JavaScript
  matchar basen efter CRLF-normalisering; originalets bytes behölls i arbetskopian.
- Staged kontroll före commits: inga tokenmönster, förbjudna lokala tillståndsfiler
  eller ogranskade filer över 5 MB. Autentiska fixturers ursprungliga radslut
  bevaras. 35 redan spårade fixturer har samma arbetskopiebytes men korrigerad
  Git-textbehandling så att en klon behåller deras hashkontrollerade innehåll.
- Docker-daemon var inte tillgänglig. Ingen containerbyggnad eller browser-E2E
  med installerade browserbinärer har körts; daemon/jobbtjänster startades inte.

## Återstår i denna mellanliggande commit

Slutligt avgränsat testpass, ren lokal klon med återställda data, jämförelse av
plannerresultat och Git-integritetskontroll. Ingen slutlig konsolideringstagg ännu.
