# Näringskopplingar och extraval, 2026-10-15

Status: lokal utveckling på `fix/recipe-nutrition-extras`, kodcommit `7e402a7`, bas `fd783d1`.
Ingen aktivering av denna ändring på beta.smako.nu. App, scheduler,
Windowsuppgift, prisunderlag och användartillstånd har inte ändrats.

## Orsak och ändring

Begäran `c94cc5a9-0433-4746-8a80-e5d850b023da` stoppades av saknat
kvalificerat näringsunderlag, innan gränsen 40 g protein kunde jämföras.
Den tidigare aktiveringen `07af5ac` rättade köpbara varor men verifierade
inte denna näringskombination.

- Fullständiga råvarunamn, kryddor och relevanta färska/frysta former får
  smala kopplingar till befintliga referenser. Mejeriprodukten Crème Bonjour
  Vitlök kan inte bli rå vitlök när varumärket tas bort ur matchningen.
- Fjorton nya leverantörsdeklarationer importeras från Garant och Dabas.
  GTIN, varumärke, variant och förpackning binds till befintliga prisprodukter.
  Namnbindning använder en unik, fullständig varumärkes-/variant-/mängdidentitet.
  Ingen prisidentitet skapas genom osäker textlikhet.
- Kokosmjölkens uttryckliga deklaration per 100 ml bevaras som ml i såväl
  katalog- som erbjudandevägen. Gram ommärks inte till milliliter.
- Saknade generiska referenser för rena kryddor, fetaost och ströbröd
  kompletteras från Matvaretabellen och DTU. Referenserna är uppskattningar,
  inte deklarationer för ett visst varumärke. Ofullständiga eller motstridiga
  produktdeklarationer fylls inte med antagna nollor.
- Pressad citronjuice och ren rapsolja kan använda livsmedelsspecifik
  referensdensitet för näringsberäkning när uppskattningar tillåts.
  Förpackningsmängd, pris och originaldeklaration ändras inte.
- Portionsvikt kan uppskattas för exakt granskade kalla recept utan
  tillagningsförlust, och för de befintliga referensrätter som har
  livsmedelsspecifikt tillagningsutbyte. Slutvikten märks som uppskattad.
  Generell råvaruvikt används inte som tillagad vikt. Soppor med ospecificerat
  vatten och övriga varma recept utan utbyte saknar fortsatt viktunderlag.
- Äpplets redan granskade identitet kopplas till receptmatchningen, med
  bibehållna separata mängd- och prisgrindar.
- Veganfiltret kompletteras med `yoghurt naturell` och `keso`. Ett tidigt
  vegantest visade sig innehålla vanlig yoghurt och har underkänts och ersatts.
  Slutprovet använder tre andra, veganska recept.
- Ekoalternativ använder den befintliga exakta beräkningscachen. Antalet
  sökta kombinationer, kandidater, prisvillkor och butikstak har inte minskats.
- Feltext skiljer dataluckor från ett beräknat för lågt näringsvärde.
  Dubblerade receptnamn i diagnostiken tas bort. Viktens källa och enhet
  visas separat från ingrediensernas näringskällor.

Faktaversion: `retained-catalog-facts-v11-nutrition-extras`.
Referenspolicy: `slv-component-input-v5-nordic-density`; det kanoniska
innehållet i de två nya referensfilerna ingår i versionshashen.

## Källor

De 14 leverantörsposterna har återskapats exakt med respektive parser från
SHA-256-kontrollerade, sparade offentliga källsvar. Fullständiga hämtningar
och körresultat finns lokalt under `.local/recipe-nutrition-extras/` och är
inte nya priser eller en aktivering av butikskällor.

- [Garant, kokosmjölk](https://www.garantskafferiet.se/vara-produkter/smaksattare/smaksattare-till-mat/kokosmjolk/)
  anger 1,8 g protein per **100 ml**, 250 ml förpackning och GTIN 7311043017881.
- [Matvaretabellen API](https://www.matvaretabellen.no/api/) används för
  de frysta referensposterna i `nordic-20261015.json`. Attribution:
  **Matvaretabellen 2026. Mattilsynet. www.matvaretabellen.no**.
- [DTU FCDB citronjuice](https://fcdb.fooddata.dk/food/268) och
  [rapsolja](https://fcdb.fooddata.dk/food/1483), utgåva 6.1 maj 2026,
  anger densitet 1,038 respektive 0,92 g/ml. Citronjuicens densitet används
  uttryckligen som referens för i huvudsak ren pressad juice; inte koncentrat.
- Befintliga Livsmedelsverksreferenser ger råvaruidentiteter och dokumenterade
  före-/eftervikter. Vid portionsvikt räknas endast huvudråvarans slutvikt;
  källreceptets eventuella tillsatta salt läggs inte till Smakoreceptet.

Originalvärden, näringsenheter, källadresser, hämtningstid och hash finns i
de versionshanterade datafilerna. De utgör inte allergen- eller ekocertifiering.

## Verifiering mot sparat butiksunderlag

26 840 produkter, 19 priskontexter från användarens tidigare val av butiker
inom 3 km från 22225. Coop Online Syd, som saknar avstånd i urvalet, har inte
lagts till. Underlaget exporterades läsande från den då laddade versionen
`price-universe:5539233425d7b341ad9e0785adad69e461893356e71eedd3b5a9bb6ab3642aed`.
Prisklockan är fryst till 2026-10-15 13:00 UTC; nya näringskällor hämtades
senare samma dag. Dessa är lokala återspelningar, inte nya produktionsmenyer.

| Prov | Resultat |
| --- | --- |
| Fem middagar, fyra portioner, minst 40 g protein | PASS, 43,08–55,51 g per portion, cirka 61 s |
| Samma antal, protein 40–90 g, kolhydrater 10–130 g, fett 1–60 g, högst 1000 kcal | PASS, cirka 11 s med redan byggda index |
| Tre vegetariska middagar, minst 25 g protein | PASS |
| Tre veganska middagar, minst 20 g protein | PASS efter rättat veganfilter; 23,99–36,87 g protein |
| Fem middagar: en kyckling, en fisk, en kött, två vegetariska | PASS |
| Frukost 100–600 g och mellanmål 100–400 g | PASS; uppskattat 300 respektive 220 g |
| Minst 20 % ekologisk kostnadsandel, tre middagar | PASS, men 459 s är en kvarvarande prestandabegränsning |
| Alla animalier ekologiska | DATA_BLOCKED; bland annat okänt animaliskt innehåll/ekostatus för ströbröd |
| Mjölkallergi | DATA_BLOCKED; fullständigt explicit allergenunderlag saknas |
| Minst 300 g protein | NUTRITION_TARGET_NOT_MET; beräknade gränser inom kvalificerade kandidater, inte global omöjlighet |

Alla godkända prov har PASS i kassakontrollen, avstämda kostnader/mängder,
noll okända mängder och högst två valda butiker. Beräknad näring och vikt
märks `ESTIMATED`; det är ingen påstådd uppmätt slutvikt.

De viktigaste produktfallen finns även som versionshanterade frysta
regressionstestdata i `backend/tests/fixtures/recipe_nutrition_links.json`.
Negativa tester täcker fel variant, förpackning, enhet, källa, tillsatser,
koncentrat, motstridiga/partiella fakta och avstängda uppskattningar.
Viktgränser och cachelikvärdighet provas genom den riktiga planeraren.

Slutlig samlad offlinekörning: **554 tester passerar**, 138,33 s.
18 serializer-varningar kommer från syntetiska `semantic_confidence="low"`
i befintliga kombinationstester; inga testfel. Därutöver passerar **14
browserprov i Chromium och WebKit** för extravalsdialoger, intervall,
standardbegäran, återställda val och bevarade krav vid serverfel.
Ruff, compileall för 17 ändrade Pythonfiler, JavaScript-syntaxkontroll och
`git diff --check` passerar. Ingen extern butikstrafik tillåts av testköraren.

Samlad körning gjordes med `scripts/verify_offline.py` och etiketten
`nutrition-extras-final-union`, på testmodulerna `test_recipe_nutrition_extras`,
`test_recipe_product_links`, `test_nutrition_reference`,
`test_personal_planning_v2`, `test_personal_qualified_facts`,
`test_personal_source_facts`, `test_recipe_preparation`,
`test_recipe_preparation_cache`, `test_complete_recipe_supplier_facts`,
`test_complete_recipe_integration`, `test_recipe_library`, `test_meal_library`,
`test_consumer_planner_v1`, `test_combined_profile`, `test_fish_exclusion`,
`test_consumer_static_ui`, `test_official_offer_facts`,
`test_variable_purchase_nutrition` och `test_official_product_declarations`.
Browserprovens etikett är `nutrition-extras-browser`.

[Kompakt resultatdata och hashar för de fullständiga lokala körresultaten](recipe-nutrition-extras-20261015.json).

## Kvarvarande begränsningar

Detta löser 40-gramsfelet och flera blockerade extraval, men är inte komplett
källtäckning för varje kombination. Allergener och ekologiska animalier får
inte godkännas genom avsaknad av uppgifter. De kräver ytterligare spårbara
produktdeklarationer/klassificeringar i det tillåtna butiksunderlaget.
Varma kompletta recept utan tillagningsutbyte kan fortfarande inte väljas
med portionsvikt. Ekoandelsökningen är fortfarande långsam i det stora provet.

Ingen del av dessa lokala prov verifierar en ny aktivering, produktionsbild,
produktionssparning eller återläsning av användarens privata plan.
