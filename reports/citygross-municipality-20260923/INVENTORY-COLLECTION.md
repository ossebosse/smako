# City Gross: officiell kommuninventering och insamling

Avgränsad lokal körning den 23 september 2026. Ingen produktion eller schemakonfiguration ändrad. Samma kod, hela officiella butiksregistret och samma SCB RegSO 2025-kontroll används för samtliga kommuner. Namn, adressort och postnummer avgör inte kommuntillhörighet.

| Kommun | Butiksregister | Site-register | Inom kommunen | Okänd kommun | Urval |
|---|---:|---:|---:|---:|---|
| Lund 1281 | 38 | 38 | 0 | 0 | 0 |
| Malmö 1280 | 38 | 38 | 1 | 0 | 3211 |
| Staffanstorp 1230 | 38 | 38 | 1 | 0 | 3229 |

Lund har noll City Gross-butiker i det kompletta publicerade registret; alla publicerade koordinater är verifierat utanför Lunds SCB-kommungräns. Ingen Staffanstorps- eller Malmöbutik lånas in. Malmö Stora Bernstorp (storeNumber 3203/siteId 59) ligger utanför Malmö enligt samma gränsprövning trots namnet. Malmö Hyllie är 3211/169, Staffanstorp är 3229/11.

## Officiella källor och identitet

- [Nationella butikssidor](https://www.citygross.se/api/v1/PageData/stores): namn, adress, siteId, koordinater och butikslänk.
- [Officiellt site-register](https://www.citygross.se/api/v1/sites?siteTypeId=3): exakt siteId → storeNumber.
- [SCB RegSO](https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/regso/): kommunkodsbunden geometri. Inom 10 meter från en RegSO-kant behålls okänd kommun enligt det befintliga kontraktet.

Original, observationstid och SHA-256 finns i `inventory-{kommunkod}/registry.json`, `boundary.json` och `inventory.json`. Urvalet omberäknas från dessa källor före insamling och drift; sparade inside-flaggor eller butiksegenskaper kan inte ersätta originalbevis. Alla butiks-/site-rader utan entydig koppling behålls med konkret orsak. Nya storeNumber/siteId-kopplingar kommer från registret, aldrig från en kodlista.

## Verkliga nätanrop

| Butik | Faktiska kataloganrop | Hämtade | Parsade/OWN | Karantän | Äldsta prisobservation UTC |
|---|---:|---:|---:|---:|---|
| Malmö Hyllie 3211/169 | 136 | 13523 | 13523 | 0 | 2026-09-23T08:04:51.365362+00:00 |
| Staffanstorp 3229/11 | 138 | 13780 | 13780 | 0 | 2026-09-23T08:07:38.127747+00:00 |

Utöver katalogerna gjordes sex registeranrop och tre SCB-anrop för de tre kommunprövningarna. Katalogcollectorns äldre total request_count inkluderar två redan hämtade registerdokument per butik; `actual_catalog_network_requests` visar verkliga nya kataloganrop. Begränsade källprover för erbjudandeutredningen redovisas separat. Lunds collector gör noll prisanrop och returnerar tomt urval.

Första Hyllie-processens rapportläsning använde fel SQL-kolumn efter att ordinarie collector redan hade godkänt och promoverat snapshoten. Rapporten korrigerades från den oförändrade databasen; ursprungsrapporten finns som `*.initial-report.json` och orsaken i `initial_report_error`. Ingen ny insamling eller ändrad observation följde av rättningen.

## Slutkod och bevarad betydelse

Båda ursprungliga livekörningarna behålls i `live-{1280,1230}/collection`. Parser v4 prövas på exakt samma råsvar i separata `final-v4-replay-{1280,1230}` med befintlig DatabaseReplayService. Replay har förbjudna nätentrypoints, noll nätanrop och jämför produktidentitet/observationstid med originalet innan rapporten godkänns. Mellanversion v3 i `final-replay-1280` är inte releaseunderlag; den avbrutna Staffanstorpkopian `final-replay-1230` är inte accepterad.

Kanalen är butiksspecifik `online_store`/`online_price`, inte verifierat fysiskt hyllpris. En separat radgodkänd offers_only-väg kan återanvända kvalificerade kampanjrader från en ofullständig katalog med originalens butik, datum, produkt/variant, förpackning och villkor. Fullkatalogens ursprungliga fel och karantän finns kvar; ingen fullständighetsgrind sänks. Fysiska butikserbjudanden har inte fabricerats ur onlinekanalen.

## Reproducerbara gränssnitt

- `grocery_data.app.connectors.citygross.municipality_inventory.discover(area, output)` och `approved_citygross_stores(inventory)`.
- `grocery_data.scripts.collect_citygross_municipality.collect(inventory, store_ids, output)` använder GroceryCollector, exakta allowlists och en isolerad databas per butik.
- `python -m grocery_data.scripts.collect_citygross_municipality --municipality-code 1281 --output NY_KATALOG` använder samma kod även för nollurval.
- `python -m grocery_data.scripts.replay_citygross_municipality --collection LIVE_COLLECTION --output NY_REPLAY_KATALOG` återanvänder befintlig replay utan nätanrop.

Fokuserade kommunregressioner omfattar Lund/Malmö/Staffanstorp, dynamisk registerkoppling, saknad koordinat, saknad/ambivalent identitetskoppling, manipulerat sparat urval och adress, butik i grannkommun, nollurval utan nätanrop, bevarat hämtfel och kampanjfallback från partiellt svar. Se gemensam testredovisning för slutlig totalsvit.
