# Coop-rättning: slutleverans 21 september 2026

Kod och isolerad verifiering slutförda på `areas/municipality-audit-20260920`.
Ingen produktionsaktivering. [Täckning och exakta bortfall](COVERAGE.md),
[före/efterexempel](EXAMPLES.md), [separat releaseförslag](RELEASE.md).
Kontraktet finns i `docs/coop_physical_offers.md`.

112 kvalificerade varianter nådde isolerad OWN och PriceUniverse: Flöjtvägen
44, Bulltofta 68. 379 av 491 varianter är i karantän. Totalt 78 annonsgrupper.
Fyra av sex konkreta checkout/audit-fall PASS; mjölets två köp prissätts rätt
men har semantisk auditblockerare. Inget påstående om komplett täckning,
näringsgodkänd slutmeny eller besparing.

## Körkommandon (PowerShell, från den separata arbetskopian)

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 grocery_data/scripts/collect_coop_physical_offers.py --inventory reports/municipality-offers-20260920/coop-audit.json --store-id 3839 --store-id 3815 --output reports/coop-physical-next-live
py -3.12 reports/coop-physical-fix-20260921/verify_isolated.py --input reports/coop-physical-next-live/sources --output reports/coop-physical-next-acceptance
```

Output-katalogerna måste vara nya; befintligt underlag skrivs aldrig över.
Första kommandot gör begränsade verkliga publika anrop. Det andra använder
oförändrade råsvar, utan nät och utan föryngrade observationer. Vid senare
replay kan priser korrekt vara för gamla/utgångna; använd då testfixturerna med
explicit testklocka för historiska regressioner, inte som färsk acceptans.

Befintlig Playwright Chromium och Python 3.12 krävs. Inga nya beroenden.
`ICA_FLYER_VISUAL_COMMAND_JSON` används inte. Coop Online-allowlist och Primat
berörs inte. Inventeringsfilen och butik-ID:n är parametrar för den begränsade
kontrollen, inte en ny hårdkodad upptäcktslista. Inga kommuner gissas.

## Verifiering

184 tester PASS (26,46 s). Efter en beteendeoförändrad lintjustering kördes
berörda 22 tester igen (10,40 s), därefter isolerad slutacceptans mot exakt
samma färska källhashar (3,457 s). Ruff och compileall PASS på ändrade Pythonfiler.
Tester omfattar verkliga källfixturer, prisroller, procent/reference/ordinarie,
medlemskap, variantundantag, gruppköp/restmängd, köpgränser över alias, pant
okänd, tidsvillkor, fel butik, gemensamt schemafel, ICA och Coop Online.

```powershell
py -3.12 -m pytest grocery_data/tests/test_coop_physical_structured.py backend/tests/test_coop_physical_pipeline.py grocery_data/tests/test_coop_connector.py grocery_data/tests/test_coop_browser_integrity.py grocery_data/tests/test_coop_offers_acceptance.py grocery_data/tests/test_coop_online_catalog_parser.py grocery_data/tests/test_offer_rows.py grocery_data/tests/test_ica_area_offers.py grocery_data/tests/test_municipality_area.py backend/tests/test_own_provider.py backend/tests/test_own_provider_grocery_data_contract.py backend/tests/test_ica_area_offer_provider.py backend/tests/test_ica_conditional_checkout.py backend/tests/test_verified_offer_deposit.py -o addopts='' -q
```

Slutbevis: `final-live-v2/coverage.json`, dess oförändrade `sources/`,
`final-acceptance-v2/result.json`, `price-universe.json` och sex `proof-*.json`.
Föregående kods jämförelse: `before-parser-comparison.json`. Alla mellanresultat
ligger kvar för spårbarhet, inklusive Bulltoftas initiala schemastopp.
`baseline.json` och `prework.tar.gz` bevarar läget före denna rättning.
`incremental.patch` och `delivery-manifest.json` avgränsar leveransen från
ärvda ändringar; `preservation-check.json` redovisar originalets integritet.
