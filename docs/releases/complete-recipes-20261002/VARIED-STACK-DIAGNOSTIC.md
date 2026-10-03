# Stackdiagnos av fri Varierad, 2026-10-03

Detta är en profilerad diagnostisk körning, **inte ett rent prestandaprov**.
Den vanliga `MealPlanService` skapade samma fullständiga resultat som det tidigare
HTTP-provet: fem middagar för två personer, **583,70 kr**, två inköpsställen.
Inga recept eller produkter låstes, inga källuppgifter ändrades och sökbudgetarna
behölls. Beräkningen tog 909,652910 s väggtid och 916,881973 s process-CPU.
Skillnaden mot HTTP-provets 1 056,924 s är inte en uppmätt ren prestandavinst.

## Versionsbundet underlag

- Stage/runtime: `9daf5805e6b8dfd46c3b2ace47e07fd767324153`; appändringarna är
  `2abf67cf4715e14e1e879918e2678fe2855a8263` ovanpå `38ee1aa5ecbc64045801a4f40f9c0302ed0e4a09`.
- Oförändrad serverimage: `sha256:65670569e3d142e9a58e823a237869a845f3f544b2292880f119e231f0df25e4`.
  Isolerad testcontainer, 2 CPU, 3 GiB, nätverk avstängt, fryst källdata skrivskyddad.
- Fall: `unrestricted-varied`. Den ursprungliga begäran har **inget** `max_minutes`-fält.
  Ingen matkökbegränsning, 10–15 ingredienser, godkända variationer, uppskattade köp,
  uttrycklig näringsopt-in, tomt skafferi revision 0 och oförändrat standardkostnadstak.
- Begärans SHA-256: `d1d302aee2ee4495bc78ee1e046c3b63c8297424e2a174509387f708a7e25824`.
- Ursprunglig HTTP-rapport: `bdcb1ec28fc47607a894be32ad894538c12a54166e6b603df3343a3570f4266e`.
- Fryst prisartefakt: `1335cbb6680237f5826912f19a1d5c348476089ec3091126cb073c4cc5a643e0`.
- Fryst beräkningsklocka: `2026-10-02T15:09:36.223910+00:00`.
- Samplingsskript: `a99c534bb535e9d1a4dec88a32f3c7d6d7567240259e5563da1754b66c5223c1`.

Vanlig inläsning av behållna produktfakta användes. Ingen session eller privat
kontodata kopierades. Fulla planer, källmanifest och stackräkningar ligger utanför
Git i `.local/varied-stack-9daf580` och motsvarande markerade fjärrtestkatalog.

## Resultatlikhet

Hela planobjektet jämfördes strukturellt med HTTP-resultatet efter att exakt dessa
körningsberoende fält utelämnats:

- `app_version`
- `build_id`
- `personal.cache_identity` (det nya tomma testutrymmet har en separat identitet)
- `personal.checks.timings_seconds`
- `data.cache_state`

Resultat: **0 skillnader**. Recept, mängder, hela varukorgen, måltidsplatser,
näringsvärden, kassaudit, källversion och sökdiagnostik är identiska. Jämföraren
kontrollerades även med en ändring på 1e-8 i en ingrediensmängd, som upptäcktes.
Båda jämförelseprojektionerna har SHA-256
`92632bc414b7f38b41993ce7c1756366817a58ae9270d129b78f17af7b6885e8`.
Den fulla nya planfilens SHA-256 är
`014b883965c214b0ce6597441831ef681561e2426d35fa97893e473131429cc9`.

## Metod och tolkningsgräns

`sys._current_frames` samplades från en separat tråd. Endast fil, funktionsnamn,
radnummer och anropskedja lästes; inga lokala variabler, globala värden, sessionsdata
eller källkodstexter samlades. 8 535 cykler gav 8 534 valda trådstackar och 8 536
ignorerade trådstackar. Inga stackar tappades till gränsen för antal unika stackar.

Begärt intervall var 50 ms; observerad median var **82,169 ms**, längsta intervall
**2,245692 s**. Själva fångstblockens uppmätta sammanlagda väggtid var 1,441335 s.
Detta är **inte** all profileringsöverhead: trådschemaläggning, GIL-konkurrens och
annan påverkan är inte isolerade i ett separat kontrollprov och får inte dras av.

Tabellerna räknar observerade stackar, inte anrop eller CPU-/väggtidsandelar.
Inkluderande räknare överlappar. GIL och anrop till nativekod kan snedfördela
observationerna. Exempelvis syns `BasketOptimizer.optimize` i 3 100 stackar trots
att dess vanliga uppmätta spann summerar till cirka 28,882 s av 909,653 s. Att
översätta stackandelar till procent av hela körningstiden vore fel.

## Observerade flaskhalsar och begränsad åtgärd

`nutrition_evidence → _nutrition_evidence → input_evidence → validate →
validate_recipe_design → _structural_check → content_hash` validerar samma
oförändrade recept upprepade gånger för olika produktunderlag. `content_hash`
är blad i 2 527 stackobservationer. Det ger stöd för återanvändning av den rena
beredningsvalideringen per exakt recept inom en plannerbegäran. Det bevisar inte
en viss besparing i sekunder.

Prototypen lägger en valfri, plannerägd `RecipeComputationCache` på `input_evidence`.
Endast `validate(recipe)` återanvänds. Nyckeln kopierar ingrediens- och steglisterna
och formordboken, bevarar orundade mängder och hela frysta designen inklusive
proveniens/version. Den använder inte bara innehålls-SHA eller objektidentitet.
Produktfakta, källbindning, konflikter, opt-in, ingrediensform, avrunnen mängd,
enheter och näring kontrolleras fortsatt per input. Felaktig validering cachelagras
inte. Standardanrop utan cache har kvar sin tidigare betydelse. Gränsen 512 och
requestlivslängden är oförändrade; inga kandidat- eller sökgränser ändras.

Lokalt verifieras alla 104 aktuella tvåportionskandidater med de fyra faktiska
rena funktionerna: recept-ID, proteinkategori, kulinarisk profil och
beredningsvalidering. Det ger exakt **416 cacheposter**, även efter en andra
full genomgång med återinlästa recept. Gränsen 512 räcker för detta kandidaturval;
den är inte höjd. Större andra indata kan fortfarande tömma cachen enligt den
befintliga gränsen och då valideras innehållet igen.

Validering av prototypen: 209 distinkta riktade tester passerar, inklusive 11 nya
cachegräns-/ekvivalenstester och befintlig beredning, receptbibliotek, komplett
integration, personlig planering och kvalificerade produktfakta. Ruff och
compileall passerar. Två befintliga syntetiska tester ger en Pydantic-varning om
strängvärdet för en enum; inga testfel eller överhoppade prov.

Andra synliga rena kostnader är Pydantics `hash_func` (806 inkluderande
observationer), `resolve` (865) och ingredienskanonisering (604). Offertberäkning,
penningavrundning, kassaudit och produktspårning syns också. Dessa har inte ändrats
i denna prototyp. Ett rent jämförbart prov krävs innan man bedömer nyttan av fler
ingrepp; listnycklar eller modellidentitet ensamt är inte säkra ersättningar för
exakta cachevärden.

Vanliga spann, med två underliggande veckosökningar inklusive kostnadsjämförelsen:

| Spann | Anrop | Summerad väggtid (s) |
|---|---:|---:|
| Veckosökning | 2 | 854,515 |
| Kandidatgenerering och kvalificering | 2 | 38,888 |
| Produktfakta | 4 | 10,979 |
| Personlig förpackningsberäkning | 5 074 | 29,929 |
| Varukorgsoptimering | 5 072 | 28,882 |
| Personlig audit | 5 072 | 23,818 |
| Slutlig måltidsnäring | 5 992 | 2,088 |

Spannen kan överlappa och ska inte summeras som en exklusiv tidsfördelning.
Näringsspannet omfattar inte den upprepade beredningsvalideringen per produkt.
Sökningen utförde 5 082 varukorgsberäkningar; offertcachen hade 891 325 träffar och
41 769 missar. Inga slutsatser om en global optimal lösning dras av dessa räknare.

## Topp 20 inkluderande stackräknare

Tabellen återger rålistans första 20 utan att ta bort tråd- och serviceomslag.

| Fil och funktion | Stackobservationer |
|---|---:|
| `backend/app/services/meal_plan_optimizer.py` · `<lambda>` | 8534 |
| `threading.py` · `run` | 8534 |
| `threading.py` · `_bootstrap_inner` | 8534 |
| `threading.py` · `_bootstrap` | 8534 |
| `thread.py` · `run` | 8534 |
| `thread.py` · `_worker` | 8534 |
| `backend/app/services/personal_planner.py` · `_create` | 8388 |
| `backend/app/services/personal_planner.py` · `create` | 8388 |
| `backend/app/services/personal_planner.py` · `basket` | 8263 |
| `backend/app/services/menu_optimizer.py` · `optimize_slots` | 7991 |
| `backend/app/services/menu_optimizer.py` · `_optimize_slots` | 7991 |
| `backend/app/services/personal_planner.py` · `evaluate` | 7957 |
| `backend/app/services/personal_planner.py` · `nutrition_evidence` | 3428 |
| `backend/app/services/basket_optimizer.py` · `optimize` | 3100 |
| `backend/app/services/personal_planner.py` · `_nutrition_evidence` | 2569 |
| `backend/app/services/recipe_library.py` · `validate_recipe_design` | 2566 |
| `backend/app/services/recipe_preparation.py` · `validate` | 2566 |
| `backend/app/services/recipe_preparation.py` · `input_evidence` | 2566 |
| `backend/app/services/recipe_library.py` · `_structural_check` | 2562 |
| `backend/app/services/recipe_library.py` · `content_hash` | 2558 |

## Topp 20 bladpositioner

| Fil och funktion | Stackobservationer |
|---|---:|
| `backend/app/services/recipe_library.py:45` · `content_hash` | 2527 |
| `_model_construction.py:555` · `hash_func` | 581 |
| `backend/app/services/ingredient_normalizer.py:318` · `canonicalize_ingredient_name` | 502 |
| `backend/app/services/basket_optimizer.py:1517` · `optimize` | 281 |
| `grocery_data/app/services/fixed_checkout_price.py:34` · `money` | 226 |
| `_model_construction.py:553` · `hash_func` | 225 |
| `backend/app/services/basket_optimizer.py:1516` · `<genexpr>` | 222 |
| `backend/app/services/basket_optimizer.py:606` · `_calculate_quote` | 193 |
| `backend/app/models/basket.py:165` · `validate_quantities` | 190 |
| `backend/app/services/product_planning_trace.py:86` · `event` | 181 |
| `backend/app/services/product_planning_trace.py:87` · `event` | 178 |
| `backend/app/services/basket_optimizer.py:1517` · `<genexpr>` | 150 |
| `backend/app/services/basket_calculator.py:47` · `money` | 130 |
| `backend/app/services/basket_optimizer.py:337` · `<genexpr>` | 111 |
| `main.py:253` · `__init__` | 99 |
| `backend/app/services/basket_optimizer.py:1516` · `optimize` | 95 |
| `backend/app/services/basket_optimizer.py:1321` · `<genexpr>` | 92 |
| `<string>:1` · `<lambda>` | 72 |
| `backend/app/services/basket_optimizer.py:1335` · `_quote_sort_key` | 71 |
| `backend/app/services/basket_optimizer.py:783` · `_candidate_quotes_with_key` | 63 |
