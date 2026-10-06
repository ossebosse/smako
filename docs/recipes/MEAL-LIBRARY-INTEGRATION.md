# Gemensam måltidsväg

Måltidsbiblioteket utökar befintliga modeller och tjänster. Ingen separat
frukost-, mellanmåls- eller prismotor införs.

| Del | Integration |
| --- | --- |
| Innehåll | `Recipe` och `RecipeDesign`, JSON-paket och hashbundet manifest i `backend/app/data/recipes` |
| Import | `meal_library_content`: validering, diff, atomisk import, historiska versioner |
| Förberedelse | `meal_prepared_artifacts`: receptstruktur, ingrediensberoenden, deklarationsindex; befintlig portionsskalning |
| Produktfakta | `personal_source_facts`: samma exakta SQLite-/råfilskopplingar, med beständig offentlig projektion |
| Urval | `recipe_library.meal_candidates`: måltidstyp och statiska användarfilter före produkt-/korgarbete |
| Veckosökning | `PersonalPlanner.create`: alla slots i samma befintliga sökning och gemensamma korg |
| Köp | Befintliga PriceUniverse, PurchaseTerms, kampanjgrupper, förpackningsavrundning och checkout-audit |
| Näring | Befintlig receptkontroll på faktiskt använda produkter och oberoende slutkontroll |
| Webb | Gemensamma complete-recipes-kontroller; ordinarie publika och personliga menyknappar |
| Jobb | dd12:s admission, ägarbundna jobb, idempotens och livscykelbundna statusläsare |
| Sparning | Befintlig PlanStore och oföränderliga revisioner; hela veckans villkor prövas vid byte |

## Tre beroenden

**Innehåll:** exakt receptmodell, schema och metodkod binder strukturartefakten.
Oförändrade recepttexter behöver inte tolkas om för nya priser. Ett index från
kanonisk ingrediens och form till utfärdade receptidentifierare visar berörd
innehållsmängd. Det är inte ett permanent receptgodkännande.

**Källor:** fullständiga produktrader och faktaversion binder deklarationsindexet.
Katalogprojektionen binds till de exakta databaskopplingarna; varje refererad
råfil hashas även vid återanvändning. Ett tillagt tidigare saknat produkt-ID
eller ändrad produktrad bryter även en negativ cacheträff. Invalideringen är
konservativ: en källändring kan bygga om hela källindexet. Vi påstår inte
selektiv ombyggnad av enbart en produkt när implementationen gör mer arbete.

**Begäran:** datum, butiker, kanal, medlemskap, kampanjavtal, portioner,
skafferi och reservationer, kost, allergener, näringsmedgivande och variation
prövas fortfarande i ordinarie planering och audit. Dessa privata villkor
lagras inte i de gemensamma förberedelseartefakterna. Färdiga menyer används
inte som bevis för snabb nyberäkning.

## Måltidsval

`personal.meals` bär separata antal, portioner, näringsgränser,
`recipe_choices` och `max_same_base_meals`. En kombination 5×4 middagar,
5×1 frukostar och 5×1 mellanmål ger 15 tillfällen och 30 portioner.
Den äldre profilen med middagar för två ger fortfarande 15 tillfällen och
20 portioner. Noll tillfällen ger inga slots eller varubehov för kategorin.

Middagsnivå, ingrediensantal, aktiv tid, total tid och väntetid är separata
egenskaper. Middagens köksfördelning och huvudproteintak överförs inte till
frukost eller mellanmål. Upprepning räknas på stabil grundrätt per måltidstyp.
Proteinmål är frivilliga; numeriskt beräkningsbar näring är inte i sig ett
godkännande för 30 eller 40 gram.

Gamla anrop utan de nya fälten behåller tidigare semantik och äldre
frukost-/mellanmålskandidater. Nya explicita biblioteksval väljer författat,
versionsbundet innehåll genom samma inköpsmotor. Prisresultatet är lägsta
hittade kostnad inom valen när global optimalitet inte har bevisats.
