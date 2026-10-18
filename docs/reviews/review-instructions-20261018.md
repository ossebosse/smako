# Granskning: rättelser efter planner-followup-review-20261018

Gren `fix/review-20261018`, ovanpå `main` `d41339d`. Patch:
`smako-review-20261018-fixes.patch` (tillämpa med `git am -3` på en gren från
`origin/main`, t.ex. `review/fixes-20261018`). Ingen aktivering ingår.

| Fynd i granskningen | Rättelse | Test |
| --- | --- | --- |
| P2 `--uncapped` behöll varianturvalet (fyra per bas) | `PersonalPlanner._select_library_options`; `LIBRARY_SEED_VARIANT_SHORTLIST` (standard sant) stängs av tillsammans med båda taken i matrisens `--uncapped` och i bevistestet | `test_library_full_reference.py` (sex linschilivarianter: 4 med urval, 6 utan) |
| P2 icke-cachebar faktaprojektion persisterades | `prepared(..., storable=)` skriver inte när projektionen träffat läsfel eller ändrad fil; identiteten får `complete-projection-v2` så äldre diskartefakter används inte | två regressionstester i `test_personal_source_facts.py`, båda fallerar utan rättelsen |
| P2 flera vattenmängder och decimaler i author | ersättning i ett pass över ursprunglig text med heltalsgränser; author registrerar varje mängd en gång och läser decimalkomma; skalade decimaler skrivs med komma | `test_recipe_authoring.py`: flera mängder, decimal, tal i annat tal, de 11 utfärdade stegen oförändrade vid 1/2/4/8/12 |
| Brunchägg L/XL saknade standardvikt | ord för ursprung/hållning (från, frigående, höns, inomhus, utomhus, svenska) räknas som vanligt ägg; övriga ord markerar sammansatt produkt | `test_egg_standard_weight.py` |

## Redan kört

Lund, granskningens frysta underlag (klocka 2026-10-18T05:12:49.467392+00:00):
`test_search_caps_vs_uncapped.py` med den nya fullbiblioteksreferensen
(seed 0, refinement 0, inget varianturval) för standard, vegan, protein40,
all-macros, organic-share, distribution och breakfast-snack-weight:
9 PASS, 0 FAIL. Malmö är inte kört här (minnet i sandlådan räcker inte för
Malmös artefakt).

## Att granska

1. Kör `test_search_caps_vs_uncapped.py` för Lund och Malmö med samtliga sju
   profiler och den nya referensen (`SMAKO_REVIEW_DATA`, `SMAKO_REVIEW_CLOCK`,
   `SMAKO_CAP_PROFILES`), samt acceptansmatrisen `--uncapped` /
   `--uncapped-reference`. Om default blir dyrare: höj taket eller stäng av
   varianturvalet, behåll testet och den fallerande evidensen.
2. Kör `repro_facts_cache.py` från granskningen: kandidaten ska ge 0 diskposter
   efter felet och 1 rad vid omförsök.
3. Kör `repro_author_water.py` inklusive `--decimal`: 200/400 ml vid fyra
   portioner och 251 ml för 125,5 ml dubblerat.
4. Inventera äggpack i båda städerna igen; Brunchägg L/XL ska få 60 g/ägg,
   inga sammansatta äggprodukter.
5. Fullsviten offline och CI som tidigare; inga nya fel utöver listan i
   `docs/TESTING.md`.

Kvar sedan tidigare och inte del av denna patch: prestandamålet (P1), backup
på servern och reproducerbar releaseimage.
