# Efterprov av beredningsvalidering, 2026-10-03

Den oförändrade fria Varierad-begäran kördes igen med samma stackinsamling,
image, klocka, prisartefakt och resursgräns som i
[föreprovet](VARIED-STACK-DIAGNOSTIC.md). Ändringen i runtime
`de95691` återanvänder endast den rena receptvalideringen inom samma planner.
Provet är **profilerad diagnostik, inte ett rent benchmark**.

| Mått | Före, 9daf580 | Efter, de95691 |
|---|---:|---:|
| Väggtid | 909,652910 s | 516,210534 s |
| Process-CPU | 916,881973 s | 516,611871 s |
| Inköpstotal | 583,70 kr | 583,70 kr |
| Middagar / portioner / inköpsställen | 5 / 2 / 2 | 5 / 2 / 2 |
| Varukorgsberäkningar | 5 082 | 5 082 |
| Offertcache träff / miss | 891 325 / 41 769 | 891 325 / 41 769 |
| Produktmatchningsberäkningar | 3 805 | 3 805 |
| Butikskombinationer | 2 849 946 | 2 849 946 |
| Veckosökning, summerat två spann | 854,514872 s | 479,927296 s |

Samtliga operationsräknare och spannens anropsantal är identiska. Hela efterplanen
är strukturellt identisk med det ursprungliga HTTP-resultatet när exakt
`app_version`, `build_id`, `personal.cache_identity`,
`personal.checks.timings_seconds` och `data.cache_state` utelämnas. Inga andra
fält undantas. Resultatet har samma fem receptversioner, mängder, produkter,
butiker, näring, inköpslista, audit och sökdiagnostik. **0 skillnader**.

Versionsbindning:

- Begäran: `d1d302aee2ee4495bc78ee1e046c3b63c8297424e2a174509387f708a7e25824`.
- Prisartefakt: `1335cbb6680237f5826912f19a1d5c348476089ec3091126cb073c4cc5a643e0`.
- Image: `sha256:65670569e3d142e9a58e823a237869a845f3f544b2292880f119e231f0df25e4`.
- Sampler, oförändrad: `a99c534bb535e9d1a4dec88a32f3c7d6d7567240259e5563da1754b66c5223c1`.
- Gemensam jämförelseprojektion: `92632bc414b7f38b41993ce7c1756366817a58ae9270d129b78f17af7b6885e8`.
- Efterplanens fulla fil: `b50a343b4d7eb8e47dc6fed21ace0a5e4b1ff91a03f6c97c58c93dbc606cacec`.
- Efterprovets summary: `631f1a9fe4391e17effa1c05601d719fde28c2ca60042eb0924ec63e233937a5`.

Råresultat, fulla stackräkningar och jämförelsefiler finns utanför Git i
`.local/varied-stack-de95691`. Isolerad körning startade 08:07:32 UTC med 2 CPU,
3 GiB och avstängt nätverk. Containern avslutades och fjärrresursen lämnades
tillbaka efter hämtning. Ingen körande HTTP-server eller produktionsdrift ändrades.

8 529 samplingscykler gav 8 529 valda stackar, ingen overflow. Begärt intervall
50 ms; observerad median **55,498 ms**, maximum **1,964653 s**. Fångstblockens
sammanlagda väggtid var 1,566779 s; all profileringsöverhead är fortfarande inte
isolerad. Samplertråden påverkades alltså annorlunda av GIL än i föreprovet.
Stackräknare är observationer, inte tidsandelar eller anropsantal.

`validate_recipe_design` syns nu i 10 inkluderande stackar och `content_hash` i 8,
mot 2 566 respektive 2 558 före. Kvarvarande profil visar bland annat Pydantics
rekursiva hash (2 169), ingredienskanonisering (1 931), `resolve` (1 668) och
generiska referensalternativ (452). Detta motiverar att pröva en **separat** liten
prototyp för exakta förberäknade receptnycklar och rena formsignaturer. Den
prototypen ingår inte i detta resultat. Produkt-, pris- och näringsbeslut ska
fortsätta genom samma kontroller; ingen sökbudget eller receptmängd ändras.

## Topp 20 inkluderande stackräknare efter ändringen

| Fil och funktion | Stackobservationer |
|---|---:|
| `threading.py` · `run` | 8529 |
| `thread.py` · `_worker` | 8529 |
| `thread.py` · `run` | 8529 |
| `backend/app/services/meal_plan_optimizer.py` · `<lambda>` | 8529 |
| `threading.py` · `_bootstrap_inner` | 8529 |
| `threading.py` · `_bootstrap` | 8529 |
| `backend/app/services/personal_planner.py` · `create` | 8384 |
| `backend/app/services/personal_planner.py` · `_create` | 8383 |
| `backend/app/services/personal_planner.py` · `basket` | 8211 |
| `backend/app/services/menu_optimizer.py` · `optimize_slots` | 7992 |
| `backend/app/services/menu_optimizer.py` · `_optimize_slots` | 7992 |
| `backend/app/services/personal_planner.py` · `evaluate` | 7926 |
| `backend/app/services/personal_planner.py` · `nutrition_evidence` | 4542 |
| `backend/app/services/personal_planner.py` · `_nutrition_evidence` | 2669 |
| `backend/app/services/recipe_preparation.py` · `input_evidence` | 2510 |
| `_model_construction.py` · `hash_func` | 2169 |
| `backend/app/services/ingredient_normalizer.py` · `canonicalize_ingredient_name` | 1931 |
| `backend/app/services/personal_planner.py` · `resolve` | 1668 |
| `backend/app/services/personal_planner.py` · `<genexpr>` | 1109 |
| `backend/app/services/product_planning_trace.py` · `event` | 777 |

## Topp 20 bladpositioner efter ändringen

| Fil och funktion | Stackobservationer |
|---|---:|
| `_model_construction.py:555` · `hash_func` | 1560 |
| `backend/app/services/ingredient_normalizer.py:318` · `canonicalize_ingredient_name` | 1531 |
| `_model_construction.py:553` · `hash_func` | 609 |
| `backend/app/services/product_planning_trace.py:87` · `event` | 391 |
| `backend/app/services/product_planning_trace.py:86` · `event` | 369 |
| `backend/app/services/nutrition_reference.py:159` · `reference_options` | 313 |
| `__init__.py:186` · `sub` | 241 |
| `backend/app/services/nutrition_reference.py:161` · `reference_options` | 125 |
| `backend/app/services/recipe_computation_cache.py:16` · `recipe_value` | 115 |
| `backend/app/services/personal_planner.py:855` · `basket` | 93 |
| `backend/app/services/ingredient_normalizer.py:186` · `_search_text` | 92 |
| `backend/app/services/personal_planner.py:237` · `source_facts` | 84 |
| `backend/app/services/personal_planner.py:935` · `basket` | 80 |
| `backend/app/services/ingredient_normalizer.py:302` · `canonicalize_ingredient_name` | 63 |
| `backend/app/services/basket_optimizer.py:606` · `_calculate_quote` | 58 |
| `main.py:263` · `__init__` | 55 |
| `__init__.py:177` · `search` | 53 |
| `main.py:253` · `__init__` | 51 |
| `backend/app/services/nutrition_reference.py:295` · `<genexpr>` | 50 |
| `backend/app/services/personal_planner.py:841` · `basket` | 50 |
