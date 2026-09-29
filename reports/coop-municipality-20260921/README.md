# Coop kommuninsamling – separat partiellt releaseunderlag

Utfört i befintlig separat arbetskopia, branch `areas/municipality-audit-20260920`,
HEAD `02ad73b8491f4b30679b3151b52686e27bedb8e6` plus bevarat ocommittat arbete.
Ingen produktion aktiverad. [Butikstäckning](COVERAGE.md), [27 erbjudanden](EXAMPLES.md),
[alla registerbutiker](ALL_STORES.md), [releaseförslag](RELEASE.md).

Resultat: 10 kommunbutiker upptäckta, 9 strukturerade butiksflöden fungerar,
499 butik–variantposter i isolerat OWN och PriceUniverse. 1 937 varianter i karantän.
X:-tra Skansvägen ingår med åtta hämtade textsidor men saknar kvalificerad prisimport.
Tidigare 112-posters releaseunderlag och Bulltofta-verifiering bevaras separat.
Detta Lundunderlag överlappar Flöjtvägens 44 poster; 499 + 112 är alltså inte ett
antal unika butiksposter. 455 poster gäller åtta nytillkomna verifierade Lundbutiker.
Det påstås inte att deras kampanjpriser aldrig observerats någonstans tidigare.

## Implementation

- Befintlig Coop-locator observerar hela den offentliga nationella kartresponsen
  via samma vanliga Chromium-transport. Ingen ny autentisering/API-nyckel.
- X:-tras eget officiella register parsas från publicerad siddata; 58 poster
  kontrolleras mot alla butikslänkar. Namn/koncept, käll-ID, konto, adress,
  position, källhash och butikslänkat reklamblad sparas.
- Kedjegemensam kommunprövning får explicit SCB RegSO 2025-positionsbevis.
  Okända/motsägande/nära gräns förblir okända. Adressortsläget är oförändrat.
- Urvalet byggs från inventeringsresultatet; inga Lundbutiker hårdkodas i
  produktionskoden. Samma kod verifierad offline för Malmö: 18 inom, 1 okänd,
  759 utanför; 16 Coop och 2 X:-tra inom. Den okända butiken behålls.
- Strikt butikskontroll normaliserar bara konto-ID:s text/heltalrepresentation.
- Stora Coops uttryckliga åldersvillkor sparas och stoppar de berörda raderna;
  övriga självständigt verifierade erbjudanden kan användas. Inga okända
  fält tyst ignoreras och inga isPil-/pant-/blandgruppskarantäner löses här.
- Samma källkampanjfamilj (`eagId`) och period delar konservativ hushållsgräns
  över Coop-butiker. Detta är bara en striktare konsumtionsgräns, aldrig bevis
  för gemensamt pris eller generell butiksgiltighet. Priser/villkor förblir
  butikspostbundna. Saknat kampanj-ID blockerar en begränsad rad.
- OWN:s gamla postnummerhjälp har inte breddats. Explicit insamlat kommunurval
  följs via vanliga `/stores?chain=coop&city=...` plus exakt käll-ID och
  provider.get_offers. Inget nytt prisregister eller ny prissättare.

## Reproducerbara kommandon

Kör från arbetskopians rot. Varje outputkatalog måste vara ny. Användaren väljer
kommun-ID; listan genereras utan en manuellt angiven butikssamling.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 -m grocery_data.scripts.collect_coop_municipality --municipality-code 1281 --output reports/coop-municipality-next
py -3.12 reports/coop-municipality-20260921/verify_isolated.py --input reports/coop-municipality-next/collection/sources --output reports/coop-municipality-next-verified
```

Byt `1281` till exempelvis `1280` för Malmö; inga kodändringar behövs för
inventering/insamling. Nästa kommando är en verklig nätinsamling, inte en fixture.
Källfel kan ge ett ofullständigt kandidatresultat; läs samtliga butikars status.
Importverifieraren är ett fail-closed acceptansprov och kan stoppa om någon
insamlad kandidat saknar ett verifierbart underlag.

```powershell
py -3.12 -m pytest backend/tests/test_coop_municipality_household.py grocery_data/tests/test_coop_municipality.py grocery_data/tests/test_municipality_area.py backend/tests/test_coop_wheat_flour.py backend/tests/test_coop_physical_pipeline.py backend/tests/test_product_semantics.py backend/tests/test_product_matcher.py backend/tests/test_basket_auditor.py grocery_data/tests/test_coop_physical_structured.py grocery_data/tests/test_offer_rows.py grocery_data/tests/test_ica_area_offers.py backend/tests/test_ica_conditional_checkout.py -o addopts='' -q
py -3.12 reports/coop-municipality-20260921/verify_two_store.py
```

Sista kommandot använder dagens sparade isolerade PriceUniverse och aktuell
inköpsdag. Det ska sluta fungera när kampanjen/färskheten inte längre gäller;
ingen testklocka maskerar en gammal acceptanskörning. Historiska pytest-fixturer
har uttrycklig inköpsdag/testklocka och är separata från faktisk insamling.

## Bevis och testresultat

- Färska butikssvar 21 september kl. 19:55–19:58 Stockholm. Första nioförsöket
  46,029 s; separat ny Stora-hämtning efter schemaåtgärd 7,967 s.
- Slutparserns collector → OWN API/provider → PriceUniverse: 16,492 s,
  499 poster, oförändrade källobservationer. `verified-final/result.json`.
- 25 första ingrediensköp plus två ytterligare Stora-köp: 27 PASS.
- Genarp mjöl 2 × 2 kg för 26 kr + Veberöd pasta 300 g för 15 kr:
  verklig BasketOptimizer med max två fysiska butiker, 41 kr och audit PASS.
  `two-store-checkout.json`. Ingen menyoptimering eller besparing påstås.
- 2 + 2 paket nötfärs i samma kampanj över två butiker stoppas vid max tre;
  2 + 1 tillåts. Lokalt avvikande pris förblir lokalt i separat adversarialtest.
- 356 regressionstester PASS, 33,36 s. Efter dokumentproveniensändringen kördes
  alla 29 berörda kommun-/områdestester om: PASS på 15,59 s. Ruff och compileall PASS.
- Separat regression på tidigare faktiska källor: exakt 112 godkända, 379 i
  karantän och sex audit-PASS. Ursprungliga observationstider och källhashar
  oförändrade. Originalets 139 ärvda filer och 415 väntande ICA-releaseposter
  kontrollerade med hash utan avvikelser.
- Primat, Coop Online, ICA-baspaus, produktion, profiler och Windows-uppgift
  har inte ändrats. Inga bildmodeller eller betalda API-anrop.

Nätverifieringen kördes i befintlig Windowsmiljö, inte på betaservern.
Ingen flerdagarsstabilitet, serverdrift eller komplett reklambladstäckning påstås.

Beroenden är befintliga Python 3.12, Playwright/Chromium, httpx, BeautifulSoup och
PyMuPDF (endast befintlig PDF-textläsning). Inga nya paket installerades.

## Evidensstruktur

`acceptance/inventory/` innehåller nationell karta, X:-tra och SCB-källbindning.
`acceptance/collection/` innehåller första riktiga prisinsamlingen, inklusive
Storas underkända del. `stora-final/` har Storas nya lyckade hämtning.
`final-sources/` är en byteidentisk sammanställning av dessa prisbatcher;
`verified-final/` har slutkodens isolerade import. `coverage-final.json` är den
sammanhållna slutrapporten. Förkörningar har inte skrivits över eller räknats
som slutgodkända. `prework.tar.gz` och `baseline.json` avgränsar kodändringarna.
