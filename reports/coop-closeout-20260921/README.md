# Coop: avgränsad avslutning

Fortsatt i `areas/municipality-audit-20260920`, samma separata arbetskopia.
Föregående 112-posters partiella releaseunderlag och rapporter är bevarade.
[Karantängruppering](QUARANTINE.md) · [Separat releaseunderlag](RELEASE.md).

## Resultat

| Butik | Prisimport före → efter | Mjöl matchat som vetemjöl | Checkout | Audit före → efter |
|---|---|---|---|---|
| Flöjtvägen 3839 | 44 → 44 | 0 → 1 kandidat | 2 × 2 kg = 26 kr | FAIL → PASS |
| Bulltofta 3815 | 68 → 68 | 0 → 1 kandidat | 2 × 2 kg = 26 kr | FAIL → PASS |

Antal frisläppta karantänposter: **0**. Totalt 112 godkända och 379 blockerade.
Samtliga sex köpbevis (mjöl, pasta, nötfärs i båda butiker) klarar audit efter
riktig ingrediensmatchning. Föregående pris-/villkors-/källobservationer bevaras.

## Grundorsak och liten rättning

Mjölets källförälder heter `Vetemjöl`, den exakta 2000 g-varianten
`Kärnvetemjöl`. Tidigare ingrediensnormalisering saknade synonymen. En vanlig
receptförfrågan ”vetemjöl” avvisades med `food_mismatch:requires_vetemjol`
när produktens reservidentitet var `karnvetemjol`.

Den föregående rapportens specifika LOW-audit hade också en verifieringsbrist:
den byggde en ProductCandidate direkt från PU-posten och hoppade över matchern.
Redan före rättningen kunde exakt förfrågan ”kärnvetemjöl” passera matchern.
Det är alltså fel att beskriva hela tidigare auditfelet som ett parserfel.

Nu har befintlig ingrediensnormalisering en belagd synonym. Den vanliga matchern
klassificerar vetemjölköpet med HIGH och samma auditgräns. En snäv synlig
namnkontroll hindrar specialmjöl, glutenfria blandningar, fullkorn, färdigrätter
och enbart generiskt ”mjöl” från att ärva godkännandet. Ingen GTIN, näring,
paketstorlek, pant eller ordinarie pris konstrueras. OWN-prisnormaliseringen
och row-approval har inte ändrats i denna avslutning.

Störst kvarvarande livsmedelsblock är variantblandade gruppköp: 172 varianter
med detta som huvudorsak (35 + 137), med ytterligare överlapp mot pant. Det
kräver ett bredare gemensamt gruppköpskontrakt och är inte ett belagt litet
klassificeringsfel. Vikt-/ungefärliga köp saknar motsvarande säkra köpmodell.
isPil och pant kräver mer källbevis. Den lilla rättning som kunde beläggas och
slutföras här är därför mjölkopplingen, inte ett påstående om maximalt möjliga
frisläppningar bland alla livsmedel. Ingen tid har lagts på att köpaktivera lampor.

## Karantänens riktiga nämnare

| Butik | Livsmedel: varianter/grupper | Övrigt: varianter/grupper | Okänt |
|---|---:|---:|---:|
| Flöjtvägen | 78 / 10 | 13 / 1 | 0 |
| Bulltofta | 185 / 31 | 103 / 9 | 0 |

263 + 116 = 379 unika varianter, 51 butik–grupper. Huvudorsaker är disjunkta
per variant. Gruppantal kan överlappa mellan orsaker, och alla överlapp redovisas
separat. Äldre summering innehöll upprepade felkoder: obelagd förpackning var
14/18 felkodsförekomster men **7/9 unika varianter**. isPil berör 13 varianter
i **8 grupper**, inte nio som den tidigare löptexten uppgav. Den nya grupperingen
korrigerar rapporteringen utan att ändra vilka poster som är köpblockerade.

## Reproduktion och bevis

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHONIOENCODING='utf-8'
py -3.12 reports/coop-closeout-20260921/group_quarantine.py
py -3.12 reports/coop-closeout-20260921/verify_isolated.py --input reports/coop-physical-fix-20260921/final-live-v2/sources --output reports/coop-closeout-next-verification
py -3.12 -m pytest backend/tests/test_coop_wheat_flour.py backend/tests/test_coop_physical_pipeline.py backend/tests/test_product_semantics.py backend/tests/test_product_matcher.py backend/tests/test_basket_auditor.py grocery_data/tests/test_coop_physical_structured.py grocery_data/tests/test_offer_rows.py grocery_data/tests/test_ica_area_offers.py backend/tests/test_ica_conditional_checkout.py -o addopts='' -q
```

Verifieringen använder collector och isolerad OWN-databas under befintligt lås,
OWN-provider, PriceUniverse, matcher, checkout och audit. Den gör **inga externa
anrop**; rapportens två request_count per butik är återanvända källbatchmått.
Output måste vara ny katalog. Slutbevis finns i `acceptance/result.json` och
sex `proof-*.json`; total körtid 3,385 s. Källorna är observerade 21 september
09:44 Stockholm; körningen skedde samma dag cirka 17:17. Koden förnyar inga tider.
Efter att underlaget åldrats ska historiska regressioner köras med testklockan,
inte presenteras som ny prisacceptans.

324 tester PASS på 18,46 s. Ruff/compileall PASS. Verkliga källfixturer verifierar
synonym, exakt gruppköp, avvisat enpaketsköp, medlemskap, köpgränser och oförändrad
karantän. Adversariala namn bevisar att synonymen inte breddar till andra mjöl.
Ingen kompletterad näringsdata, full 15/20-meny eller besparing påstås.

Officiella källor: [Flöjtvägen](https://www.coop.se/butiker-erbjudanden/coop/coop-flojtvagen/)
(`1297-40718-1065350`) och [Bulltofta](https://www.coop.se/butiker-erbjudanden/coop/coop-bulltofta/)
(`1267-40718-1065350`), titel Vetemjöl, opak variant `7310130006029`, 2 för 26 kr,
2 kg/st, publikt erbjudande 21–27 september. Källan belägger inte ett separat
styckköp för 13 kr. Produktbundna näringsvärden saknas fortfarande.
