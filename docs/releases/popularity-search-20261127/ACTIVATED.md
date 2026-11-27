# Receptpopularitet och receptsök (2026-11-27)

Aktiverad 2026-11-27 19:28 UTC. App **app-fded9fa7277b-9c2634f2**
(`sha256:04d0b887fd0e…`), bas `sha256:4bb19dc36a86…` (app-72815cacaa24-bdd50ebd).
Scheduler orörd. Backup före byte: `/srv/smako/backups/20261127T191450Z`.

Releasegren `release/popularity-20261127` (`fded9fa`) = aktiv
`release/varied-proteins-20261126` (`72815ca`) + tre commits från main
(`3a47e26`, `043de1f`, `980b764`). Main-ändringen i `personal_planner.py`
(felmeddelandet "Vi hittar inte varor till recepten…") är inte med, eftersom
den inte heller fanns i den aktiva bilden.

## Ändringar

- **Popularitet** (ägarbeslut 2026-11-27): alla 1 467 rätter har betyg 1–5
  (`data/recipe_popularity.json`). Planeraren väljer bland rätter med minst
  betyg 3 (adminregel `popularity_floor`) och tar sedan de billigaste.
  Gillade rätter går alltid igenom; ett skrivet "Gillar extra" låser upp rätter
  som nämner det när ingen populär rätt gör det. Finns ingen vecka sänks gränsen
  ett steg i taget. Fler val: "Vilka rätter?".
- **Receptsök** (ägarönskemål 2026-11-27): `/api/recipe-search` och
  `/api/recipe-library/{id}`; panelen "Sök recept" i UI A och B lägger receptet
  i matplanen (ny middag eller i stället för en måltid) eller dess ingredienser
  i inköpslistan.

## Prov

- `test_recipe_popularity.py` (inkl. riktig plan som sänker gränsen),
  `test_recipe_search_20261127.py`, webbläsarprov för söket i A och B.
  Kända fel på main före ändringen: `test_variation_bases_20261121` (2) och
  `test_ui_language` (ordet "giltig" i mine.js).
- Kandidatbild utan nätverk (3 GB): `from app.main import app` ok, sök
  "köttfärssås" ger rätten med betyg 5.
- Efter aktivering: Lund ready/fresh, Malmö ready/degraded som före, nytt
  BUILD_ID, `/api/recipe-search?q=köttbullar` svarar, inga fel i apploggen,
  befintligt tillstånd bevarat, lagringsunderhåll efter byte `complete`.

Bygge och aktivering kördes fristående på servern (`setsid nohup`) med samma
workerkod som `beta_release.py`, från laptopens skal.
