# Reproducera innehållsprovet

Kör från `D:\Projects\Smako` med befintlig Python 3.12:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/library.py validate backend/app/data/recipes/all-meal-classes-20261008.json
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/library.py diff backend/app/data/recipes/all-meal-classes-20261008.json
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/library.py import backend/app/data/recipes/all-meal-classes-20261008.json
```

På levererad gren ska omimport rapportera åtta `unchanged`. Innehållet är
redan importerat. Ingen manuell Python-registrering behövs. [Format och
alla CLI-steg](../../recipes/MEAL-LIBRARY.md).

Det exakta första importförsöket kördes även i en innehållsimage byggd från
`smako-week-search:54cb2e8159a1-packaged`, vars ID först kontrollerades mot
`8a537fc4d333…`. Dockerfile kopierar bara paketet och kör samma CLI:s
validate/diff/import/import. Ingen källkodsmount används för appen.

Privat lokal provrot: `.local/all-meal-classes-20261008/`:

- `runtime-lock.json`, `data-only.json`: före/efter-hashar.
- `validate.json`, `diff.json`, `import.json`, `reimport.json`.
- `prepare-first.json`, `prepare-second.json`, `library-candidate/`.
- `qualification-command.json`: fullständigt containerkommando med skrivskyddat
  befintligt `smako-search-20261007-inputs`, två CPU, 3 GiB och explicit
  replayklocka. `qualification-container.json` har alla korgar, näring och spår.
- `free-*/command.json`: faktiska befintliga Chromium/WebKit-knappkommandon.
  Begärandena `request-*-explicit.json` anger måltidsval. För genomarbetad mat
  måste `personal.meals[dinner].recipe_choices.dinner_level` vara `crafted`.
- `fixed_browser.py`: separat diagnos av åtta uttryckligt valda recept,
  idempotens, rendering och sparad GET. Resultatet är inte fri ekonomi.
- `fixed-webkit/report.json`: återläsning efter riktig containeromstart.
- `free-crafted/`: det bevarade felaktigt konfigurerade provet; skriv inte över.
- `pytest.log`, `build.log`, `build-retry.log`, `app-command.json`.

Den lokala appens namn är `smako-content-http-20261008`, port
`http://127.0.0.1:18128`. Efter avslut kan just den redan skapade testcontainern
startas med `docker start smako-content-http-20261008` när porten är ledig.
Den använder isolerad lagring och historiska priser. Ladda aldrig dessa
testvolymer eller denna replay-startväg i produktion.

För ett nytt kvalificeringsförsök används samma vanliga CLI i innehållsimagen:
`python -m app.services.meal_library_cli qualify --pack /content/pack.json
--universe /inputs/universe.json --clock 2026-10-04T07:19:16.028059+00:00
--allow-nutrition-estimates --output /results/ny-kvalificering.json`, med
miljö/mounts enligt `qualification-command.json`. Använd ett nytt försöksnamn
så tidigare råfel inte skrivs över.

Arkiv `.local/all-meal-classes-20261008/all-meal-classes-20261008-library.zip`
är ett innehållsarkiv, inte ett nytt serverpaket. Det byggdes med befintlig
`library.py build`, inkluderar versionshistoriken och kontrollerades genom
återläsning av zipmedlemmarna. Bytehash och storlek finns i PACKAGE.json.
