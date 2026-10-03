# Efterprov av exakta nycklar, 2026-10-03

Den [separata prototypen](EXACT-RECIPE-KEY-PROTOTYPE.md), runtime `43cdc1a`,
kördes genom vanlig `MealPlanService` med samma fria Varierad-begäran och
stackinsamling som de två tidigare proven. **Profildiagnostik, inte rent benchmark.**
Inga sökbudgetar, kandidater, produkter eller källuppgifter ändrades.

| Mått | Ren receptmemo, 9daf580 | Dessutom valideringsmemo, de95691 | Dessutom exakta nycklar, 43cdc1a |
|---|---:|---:|---:|
| Väggtid | 909,652910 s | 516,210534 s | 334,860572 s |
| Process-CPU | 916,881973 s | 516,611871 s | 335,124692 s |
| Inköpstotal | 583,70 kr | 583,70 kr | 583,70 kr |
| Varukorgsberäkningar | 5 082 | 5 082 | 5 082 |
| Offertcache träff / miss | 891 325 / 41 769 | 891 325 / 41 769 | 891 325 / 41 769 |
| Produktmatchningsberäkningar | 3 805 | 3 805 | 3 805 |
| Butikskombinationer | 2 849 946 | 2 849 946 | 2 849 946 |
| Veckosökning, två spann | 854,514872 s | 479,927296 s | 301,572242 s |

Samtliga operationsräknare och spannens anropsantal är identiska. Hela planen
är strukturellt identisk med det ursprungliga HTTP-resultatet, med exakt fem
undantagna metadatafält: `app_version`, `build_id`, `personal.cache_identity`,
`personal.checks.timings_seconds`, `data.cache_state`. **0 skillnader**.
Fem middagar för två personer, två inköpsställen; receptversioner, mängder,
produkter, näring, inköpslista, audit och sökdiagnostik är oförändrade.

- Begäran: `d1d302aee2ee4495bc78ee1e046c3b63c8297424e2a174509387f708a7e25824`.
- Prisartefakt: `1335cbb6680237f5826912f19a1d5c348476089ec3091126cb073c4cc5a643e0`.
- Image: `sha256:65670569e3d142e9a58e823a237869a845f3f544b2292880f119e231f0df25e4`.
- Oförändrad sampler: `a99c534bb535e9d1a4dec88a32f3c7d6d7567240259e5563da1754b66c5223c1`.
- Gemensam jämförelseprojektion: `92632bc414b7f38b41993ce7c1756366817a58ae9270d129b78f17af7b6885e8`.
- Full efterplan: `7e4579aed5640222680772aa995657fb0ef1ce17fd57845c45ec7894ec019ff3`.
- Efterprovets summary: `09ecfb458d6a4d06f7816b3cfd440edc7e6c80cded4d5299a32f0c1f8574053e`.

Samma 2 CPU, 3 GiB, avstängt nätverk, skrivskyddat pris-/produktunderlag och
frysta klocka `2026-10-02T15:09:36.223910+00:00` användes. Inga sessionsdata
kopierades. Råplan, fulla stackräkningar och jämförelser ligger utanför Git i
`.local/varied-stack-43cdc1a`. Testcontainern avslutades och resursen lämnades
tillbaka efter hämtning; ingen produktions- eller HTTP-server ändrades.

5 424 samplingscykler gav 5 424 valda stackar, ingen overflow. Begärd kadens
50 ms; observerad median 55,493 ms och maximum 1,984469 s. Fångstblockens
summerade väggtid var 0,997221 s. All profileringsöverhead är inte isolerad;
GIL/nativekod påverkar vilka stackar som kan observeras. Tabellräknarna är
**stackobservationer, inte CPU-/väggtidsandelar eller anropsantal**.

Inga observationer av Pydantics rekursiva `hash_func` finns i efterprofilen;
det betyder inte att funktionen aldrig anropas. `content_hash` förekommer i 12
inkluderande observationer, den nya `key` i 127 och `forms_for` i 21. Kvarvarande
arbete syns bland annat vid ingredienskanonisering, produktbunden näring och
referensunderlag samt produktspårning. Dessa kontroller ändrades inte vidare.

246 riktade tester passerade före körningen. En oberoende skrivskyddad granskning
fann ingen ekvivalenslucka i snapshot, hashkollision, aliasordning, cachegränser
eller custom-normalizer-beteende. Den breda sökningen är fortfarande ett arbete
på flera minuter på denna resursnivå. Ett rent jämförbart slutprov och HTTP-prov
på den slutliga paketerade versionen återstår; dessa diagnostider ersätter dem inte.

## Topp 20 inkluderande stackräknare

| Fil och funktion | Stackobservationer |
|---|---:|
| `backend/app/services/meal_plan_optimizer.py` · `<lambda>` | 5424 |
| `threading.py` · `run` | 5424 |
| `thread.py` · `run` | 5424 |
| `threading.py` · `_bootstrap_inner` | 5424 |
| `threading.py` · `_bootstrap` | 5424 |
| `thread.py` · `_worker` | 5424 |
| `backend/app/services/personal_planner.py` · `create` | 5271 |
| `backend/app/services/personal_planner.py` · `_create` | 5271 |
| `backend/app/services/personal_planner.py` · `basket` | 5149 |
| `backend/app/services/menu_optimizer.py` · `_optimize_slots` | 4948 |
| `backend/app/services/menu_optimizer.py` · `optimize_slots` | 4948 |
| `backend/app/services/personal_planner.py` · `evaluate` | 4924 |
| `backend/app/services/personal_planner.py` · `nutrition_evidence` | 2531 |
| `backend/app/services/personal_planner.py` · `_nutrition_evidence` | 2233 |
| `backend/app/services/recipe_preparation.py` · `input_evidence` | 2114 |
| `backend/app/services/ingredient_normalizer.py` · `canonicalize_ingredient_name` | 1143 |
| `backend/app/services/personal_planner.py` · `resolve` | 780 |
| `backend/app/services/nutrition_reference.py` · `reference_evidence` | 692 |
| `backend/app/services/product_planning_trace.py` · `event` | 662 |
| `backend/app/services/nutrition_reference.py` · `product_reference` | 643 |

## Topp 20 bladpositioner

| Fil och funktion | Stackobservationer |
|---|---:|
| `backend/app/services/ingredient_normalizer.py:318` · `canonicalize_ingredient_name` | 903 |
| `backend/app/services/nutrition_reference.py:159` · `reference_options` | 347 |
| `backend/app/services/product_planning_trace.py:86` · `event` | 323 |
| `backend/app/services/product_planning_trace.py:87` · `event` | 318 |
| `__init__.py:186` · `sub` | 191 |
| `backend/app/services/recipe_computation_cache.py:37` · `__hash__` | 177 |
| `backend/app/services/nutrition_reference.py:161` · `reference_options` | 136 |
| `backend/app/services/personal_planner.py:933` · `basket` | 82 |
| `backend/app/services/personal_planner.py:237` · `source_facts` | 74 |
| `backend/app/services/recipe_computation_cache.py:19` · `recipe_value` | 72 |
| `backend/app/services/personal_planner.py:853` · `basket` | 68 |
| `backend/app/services/ingredient_normalizer.py:186` · `_search_text` | 64 |
| `backend/app/services/basket_optimizer.py:606` · `_calculate_quote` | 60 |
| `main.py:263` · `__init__` | 51 |
| `main.py:253` · `__init__` | 49 |
| `backend/app/services/nutrition_reference.py:391` · `product_reference` | 48 |
| `grocery_data/app/services/fixed_checkout_price.py:34` · `money` | 47 |
| `backend/app/services/personal_planner.py:840` · `<genexpr>` | 37 |
| `backend/app/services/ingredient_normalizer.py:302` · `canonicalize_ingredient_name` | 37 |
| `__init__.py:177` · `search` | 35 |
