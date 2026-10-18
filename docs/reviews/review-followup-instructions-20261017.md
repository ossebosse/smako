# Granskning: uppföljning efter planner-startup-server-review (2026-10-17)

Patch: `smako-review-followup.patch`, 12 commits ovanpå den granskade patchen
(`c0c86db` lokalt = `35dc44f` på main). Tillämpa med `git am -3`.
Bakgrund och mätningar: `docs/planner-performance.md`, avsnittet
"Prövade åtgärder 2026-10-16–17", och de översta posterna i `docs/HANDOFF.md`.
Ingen aktivering ingår.

Granska i ordning; stoppa vid första avvikelse och rapportera fil, rad och
reproduktion.

## 1. Regression och CI

1. `scripts/verify_offline.py backend/tests -m "not live" -q -rfEs`:
   inga FAILED/ERROR utöver webbläsartester utan Playwright lokalt. Tio
   `xfail(strict=True)` i `conftest.py` ska vara XFAIL, inga XPASS.
2. Samma körning med `SMAKO_REQUIRE_LOCAL_EVIDENCE=1` på en maskin med
   återställt `reports/`-underlag, plus `--runxfail`, och jämför med listan i
   `docs/TESTING.md`. Kontrollera särskilt det omskrivna äggtestet i
   `test_recipe_resolution.py`.
3. Kör `tests.yml` via en PR (Ruff-steget körs bara då).

## 2. Taken får aldrig välja bort billigare recept

1. `SMAKO_REVIEW_DATA=<artefaktmapp> SMAKO_CAP_PROFILES=standard,vegan,protein40,all-macros,organic-share,distribution,breakfast-snack-weight`
   `pytest backend/tests/test_search_caps_vs_uncapped.py` för Lund och Malmö.
2. Acceptansmatrisen per profil: först `--uncapped`, sedan default med
   `--uncapped-reference <rapport>`. Varje rad ska ha `uncapped_check: ok`.
3. Om någon profil blir dyrare med tak: höj `LIBRARY_REFINEMENT_POOL_LIMIT`
   eller `LIBRARY_SEED_POOL_LIMIT` hellre än att ta bort testet, och dokumentera
   profilen i prestandadokumentets tabell "Prövat och inte infört".

## 3. Samma vinnare i närings- och ekosökningen

1. Kostnadsgränsen i `_qualified_nutrition_basket`: bekräfta att
   `restriction_cost_bounds`/`optimistic_relaxed_key` är en giltig undre gräns
   för `optimize` (radofferter med förpackningsavrundning, inget butikstak) och
   att den stängs av vid kopplade flerradserbjudanden. Bara strikt lägre total
   ersätter `best`, därför är `>=` rätt villkor för att hoppa över.
2. Ekosökningen: ordningen efter gräns plus jämförelse på
   `(total, ursprungligt index)` ska ge samma vinnare som den ursprungliga
   ordningen. Verifiera med en körning där två delmängder har samma total.
3. Kör all-macros, protein40, distribution och organic-share före/efter med
   matrisens `--baseline`; identisk `semantic_sha256` krävs.

## 4. Faktalåset

1. `personal_source_facts._load_retained_catalog_facts`: hashning sker utan
   lås; `_CACHE` och `_KEY_LOCKS` ändras bara under `_LOCK`; projektionen körs
   under nyckellåset men inte under `_LOCK` (testet kontrollerar detta).
2. Bekräfta att integritetskontrollen (hash per råkälla, även vid cacheträff)
   är oförändrad och att ett icke-cachebart resultat aldrig lagras.
3. Känd begränsning: två trådar för samma nyckel kan i sällsynta fall
   projicera parallellt (dubbelt arbete, inte fel resultat). Bedöm om det är
   acceptabelt.

## 5. Recept och ägg

1. `review-fixes-20261017`: 28 nya versioner. Endast fälten i HANDOFF-tabellen
   får skilja mot föregående version. De 16 rättelserna ska ha
   `content_source.safety_sources` och förvaringsråd kvar.
2. Processvatten: skala tre recept till 1, 2, 4, 8 och 12 portioner och läs
   stegtexten.
3. Ägg (ägarbeslut): M = 51 g, L = 60 g ätbart per ägg, blandat M/L som M,
   Small/XL-enbart/okänd klass utan vikt. Kontrollera alla äggpack i aktiva
   Lund- och Malmöartefakter mot `egg_standard_weight`.
4. `author`: kör exemplet och ett eget recept med parallella steg och vatten i
   ml; aktiv tid ska vara summan av aktiva steg.

## 6. Mätning på servern

Mät kall och varm tid för standard, all-macros, organic-share och
distribution med default och med `LIBRARY_REFINEMENT_POOL_LIMIT=0`. Jämför med
granskningens 25–125 s (standard) och 261/278 s (makro/eko). Sandlådans
siffror är 1 CPU och ska inte användas som serverns.

## Rapportera

Per avsnitt: godkänt eller avvikelse med reproduktion. För mätningar:
profil, stad, kall/varm, tid, pris och hash för default och utan tak.
