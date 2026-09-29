# Kommunläge och strukturerade erbjudanden – avgränsad leverans

Verifierat 20 september 2026, Europe/Stockholm. Kod i separat arbetskopia `C:/Users/ossia/Documents/Codex/2026-09-16/municipality-coverage-20260920`, branch `areas/municipality-audit-20260920`, bas `02ad73b8491f4b30679b3151b52686e27bedb8e6` plus bevarade ocommittade rättningar. Originalgrenen och dess förberedda ICA-release har inte ändrats.

Kommunläget är implementerat och nätverifierat med administrativ adressinformation. **Full kommunbaserad täckning är ännu inte verifierad.** Andra kedjors kommunbedömning och 35 ICA-kandidater i Malmöundersökningen behöver ytterligare geografiskt bevis. Gränsgeometrin från Lantmäteriet krävde tjänstebehörighet (401). Ingen rad har därför fått kommunstatus enbart från namn, adressort, postnummer eller URL.

| ICA, samma kod | Adressort | Kommun: inkluderade | Exkluderade | Okända | Upptäckta i källans sökresultat |
| --- | ---: | ---: | ---: | ---: | ---: |
| Lund, 1281 | 9 | 12 | 0 | 0 | 12/12 |
| Malmö, 1280 | 21 | 24 | 10 | 35 | 69/69 |

Lunds tillskott är Genarp, Veberöd och Södra Sandby. Malmö får fyra verifierade kompletteringar i Limhamn, Oxie och Bunkeflostrand; Toftanäs tillhör adressortsurvalet men saknar ännu kommunbevis. Därför är Malmöskillnaden **+4 belagda, −1 okänd**, inte en tyst flytt av befintliga planer. Tio av Malmölistans närliggande butiker är belagt i Lund och exkluderas från Malmö. 12/12 respektive 69/69 avser listans egen nämnare, inte oberoende bevis att alla kommunens butiker har hittats.

| Kedja | Identifierade fysiska kandidater Lund / Malmö | Ny verklig priskontroll | Viktigt utfall |
| --- | --- | --- | --- |
| Willys | 3 / 10 | Lund 2176 och Malmö Emporia 2244, en katalogsida och 3 detaljer vardera | Kampanjer finns redan i SourceOffer, OWN och äldre aktivt PU. Ingen ny connector behövs. |
| Hemköp | 2 / 4 | Brunnshög 4224 och Kronprinsen 4114, en katalogsida och 3 detaljer vardera | Kampanjer bevaras; `applied=true` och `offerStatus=Vilande` förekommer tillsammans. Parsern tappar statusfältet. Elinegård hittades i färsk nationell lista genom adressorten Limhamn. |
| Coop | 7 / 13 | Flöjtvägen 3839 och Bulltofta 3815 | 19 respektive 51 lästa prisrader, 19/43 SourceOffer. Datum, variantidentiteter och viss villkorstext tappas. 8 Bulltoftarader blir ordinarie priser utan belagd ordinarie roll. |
| City Gross | 0 / 2 namnkandidater | Hyllie 3211, fysisk site 169, en utökad sida om 100 rader | 4 strukturerade kampanjer. En oklar förpackning `2DL/1L`; tre tydliga exempel finns. Stora Bernstorp med adressort Arlöv är inte kommunbekräftad. |
| Lidl | 2 / 7 | Ett separat standardregionflöde: 30 råa, 27 parsade, 3 avvisade | Publika och allmänna Lidl Plus-priser finns utan bilder. Ingen automatisk giltighet för dessa nio butiker. |

Willys Limhamn 2144 och Hemma Oxie 2879 återfinns också i den färska nationella listan när kompletterande upptäckta adressorter prövas.

Kedjeantal är **upptäcktskandidater**. Alla 50 fysiska kandidater från de fem kedjorna står kvar; deras kommunstatus är okänd tills adress-/gränsbevis tillkommer. Lidl-regionkontexten räknas inte som en tionde fysisk butik. Coop Online Syd 730400 räknas inte som varje Coops fysiska butik.

- [Alla ICA-butiker och geografiska bevis](MUNICIPALITIES.md).
- [Alla övriga identifierade butiker, källor och datasteg](STORES.md), maskinläsbart i `store-matrix.json`.
- [24 verkliga prisexempel från sju butikskontexter och ett regionalt flöde](EXAMPLES.md). Tre per priskontrollerad kontext; datum-/statusluckor markeras öppet. Prisrapport är inte köpacceptans.
- [Källgranskning och tappade fält](SOURCES.md).
- [Ett avgränsat nästa steg: Coops fysiska erbjudandetext](NEXT.md).
- [Separat releaseförslag för kommunläget](RELEASE.md).

## Drift och kvalitet

Read-only serverkontroll visar att nyare OWN-data faktiskt finns: Willys 19/9, Hemköp Brunnshög 20/9 och Coop Online Syd 20/9. Aktiva PriceUniverse är oförändrat `price-universe:4832eaa0fc9d8be4a5941cdf3ef87c2b25f2c48593d68199b7f15dc5fbddc87e`, byggt 16/9. Den befintliga basens ålder överstiger 48 timmar. Ingen ny aktuell planeringsacceptans eller besparing hävdas. Detta ändrar inte beslutet att den redan förberedda releasen väntar på Windows-administratörssteget.

Slutkodens 95 fokuserade tester passerade på 14,82 sekunder, inklusive 21 kommunregressioner samt ICA-discovery, radgodkända erbjudanden, provider och kampanjpolicy. Ruff och compileall passerade. Inga prisvalideringsgränser ändrades. Slutkodens områdesresultat återspelades med nätverket uttryckligen spärrat och oförändrade observationstider; de riktiga nätanropen och deras råsvar är separata.

## Reproducerbara kommandon

Från den nya arbetskopian, PowerShell:

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONPATH='backend;.'
py -3.12 -m pytest grocery_data/tests/test_municipality_area.py grocery_data/tests/test_ica_area_offers.py grocery_data/tests/test_ica_connector.py grocery_data/tests/test_official_store_discovery.py grocery_data/tests/test_offer_rows.py grocery_data/tests/test_campaign_refresh_policy.py backend/tests/test_ica_area_offer_provider.py -o addopts='' -q
py -3.12 grocery_data/scripts/collect_ica_area_offers.py --city Lund --area-mode municipality --municipality-code 1281 --inventory-only --skip-flyers --output reports/municipality-recheck-new-lund
py -3.12 grocery_data/scripts/collect_ica_area_offers.py --city Malmö --area-mode municipality --municipality-code 1280 --inventory-only --skip-flyers --output reports/municipality-recheck-new-malmo
```

Välj nya outputvägar; collectorn vägrar skriva över tidigare evidens och tar befintligt operationlås. Inga prisrader hämtas/importeras med `--inventory-only`. Adressortsläget är fortsatt standard utan de två kommunflaggorna. `replay_municipalities.py` visar hur samma exakta adressbevis återanvänds mellan två områdens inventeringar utan att förnya tiden; replayns outputkataloger måste också vara nya.

`probe_chains.py`, `probe_details.py` och `probe_coop_context.py` dokumenterar de avgränsade verkliga proven. De är manuella rapportskript, inte nya connectors eller scheman. Kör inte om dem som standard: redan sparade svar räcker för fortsatt parserutredning. `build_report.py` bygger om tabellerna offline. Nya stora crawls har inte godkänts.
