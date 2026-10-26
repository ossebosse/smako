# Oberoende granskning av PR #17, 2026-10-26

Granskat main `719b927` efter uppdraget VALID-WEEK-AND-COVERAGE.
Bedömning: ett tydligt framsteg. Den första uppmätta fullständiga B2-veckan
når produktens tidsintervall, och köpbarhetsökningen är spårbar. Det breda
standardfallet A är fortfarande ett konkret releasehinder för ett nytt
generellt standardläge. Ingen aktivering rekommenderas genom denna granskning.

## Vad som har kontrollerats

- Läste runtimeändringar, regressionsprov och
  [leveransrapporten](valid-week-and-coverage-20261026.md), inklusive
  ursprung för variationskrav, personlig omräkning, deadline/lagring,
  kokosalias, UI-återställning och borttagna kompletterande checkouter.
- Körning med `scripts/verify_offline.py`: **116 PASS på 220,66 s**.
  Moduler: `test_variation_intent_v2`, `test_personal_change_deadline`,
  `test_grated_coconut_link`, `test_current_library_policy`,
  `test_current_week_checkout_oracle`, `test_store_dominance_oracle` och
  `test_personal_choices_browser`, med `-m 'not live'`. Browsermodulen
  omfattar Chromium/WebKit. Detta är riktade regressioner, inte en ny
  full CI-körning eller nya verkliga prestandaprov.
- Kontrollerade API-/browserkvittonas käll-, fakta-, biblioteks- och
  metodidentiteter, SHA för båda lokala sparade planerna samt exakt likhet
  för hela sparade `request` och `optimized_basket`. `use_pantry=False`
  är bevarat. Det första felaktiga browserförsöket räknas inte som acceptans.
- Kontrollerade 2 200 unika aktuella recept-ID:n och före/efter-mängderna
  i köpbarhetsinventeringen. Nettot är +5 exakt/+11 med tillåtna
  uppskattningar, inga förluster eller dolda historiska ID-byten.

Ingen ny blockerande korrekthetsregression hittades i de granskade
ändringarna. Det är inte ett intyg för alla möjliga användarval.

## Bekräftat resultat och gränser

| Mått | Resultat |
| --- | --- |
| Individuellt köpbara importerade varianter, exakt | 738/2 200, 33,5 %, tidigare 733 |
| Inklusive uttryckligen tillåtna mängduppskattningar | 931/2 200, 42,3 %, tidigare 920 |
| B2, fem middagar/fyra portioner | 731,20 kr, API/save/GET 30,2549 s |
| B2, Chromium knapptryck till full lista och GET | 31,8625 s |
| Bredare A | SEARCH_INCOMPLETE efter 60,2828 s; ingen levererad lista |
| Kall laddning/förberedelse före första B2 | 112,3767 s, utanför användaranropet |
| Kvar i gemensam mätbudget | 2 273,2262 s = 37,89 minuter |

B2 behåller verkliga 52 valda butikskontexter och inköpstak två,
tre kyckling/två vegetariska, grekiskt/italienskt och protein minst 35 g.
Den dokumenterade standardkonflikten ändras; original-B är fortsatt ett
annat, negativt fall. Näringen är ESTIMATED enligt explicit policy.
Köpbarhetstalen är individuell insatslösbarhet, inte personligt
närings-/allergen-/ekogodkännande eller en färdig gemensam korg.

Detta styrker ett nytt lyckat veckofall med förberett underlag. Det
styrker inte alla val, globalt billigaste meny, matchad prisparitet mot
en äldre B2-vinnare, p95, samtidighet eller första installation inom 32 s.

## P2: redan kvalificerade korgar räknas om innan veckan kan byggas

A:s maskinkvitto visar 960 kvalificerade kandidater. På sökdjup ett görs
**960 nya utvärderingar och noll träffar i överförda resultat**. Sedan
hinner djup två bara 697 påbörjade/696 färdiga utvärderingar. Ingen
femmåltidsmeny nås. Detta är en verifierad kvarstående prestandabrist,
inte ett påstående om att PR #17 introducerade den.

`backend/app/services/personal_planner.py:2503` behåller de sista
256 kvalificeringsresultaten. `menu_optimizer.py:1346` överför dem
till samma begränsade cache som sedan fylls med omräknade äldre kandidater
i ordinarie ordning vid rad 1417–1421. De sparade resultaten hinner då
kastas ut innan iterationen når dem. Problemet är inte bara ett lågt
antal träffar på olika personliga anrop; detta är samma anrops redan
utförda arbete med samma första måltid.

Ett litet isolerat kontrollprov använde riktiga `MealSlot`, `Recipe`
och `MenuOptimizer.optimize_slots`, men en billig räknande evaluator:
300 olika första-måltidskandidater, de sista 256 resultaten i
`initial_evaluations`, en andra måltid och beam ett. Utfallet var
**300 nya första-måltidsutvärderingar, noll återanvändningar**. Det
reproducerar cacheutträngningen utan nytt prisunderlag eller dyr mätning.

Rätta överföring och konsumtion med begränsat minne och bevarad
krav-/prissemantik. Att enbart höja gränsen över 960 flyttar problemet
till nästa bibliotek. Att enbart spara 256 träffar räcker sannolikt inte
heller för A: sökningen behöver nå en fullständig kandidat tidigt i
stället för att prissätta hela bredden på varje ofullständigt djup.

## Nästa steg

[Nästa Sol-uppdrag](../CODEX-SOL-NEXT-20261026-BROAD-WEEK.md) avgränsar
arbetet till A:s sökning, säkert återanvänt arbete och tidigare komplett
veckokandidat. B2 blir ett regressionsfall för giltighet, pris och latens.
Återanvänd köpbarhetsinventeringen när dess beroenden är oförändrade.
Störst enskild återstående källucka är limejuice: i det aktuella
underlaget är 112 exakta/160 estimated-varianter blockerade enbart av
den gruppen. Det är en övre möjlig vinst, inte bevis att rätt produkter
eller innehållsdeklarationer redan finns. Källberikning blir en separat
avgränsad etapp; ny massimport eller samma fullinventering igen är inte
den mest värdefulla nästa insatsen.
