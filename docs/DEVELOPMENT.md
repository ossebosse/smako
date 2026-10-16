# Utveckla Smako från main

Utgå från `https://github.com/ossebosse/smako.git`, standardgren `main`.
På den befintliga utvecklingsdatorn är `D:\Projects\Smako` den permanenta
arbetskopian. En ny dator använder sin egen klon; gamla Codex-kataloger behövs inte.

## Installation och lokal start

Kräver Git och Python 3.12. Kör från den klonade projektroten:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m pip check
.venv/Scripts/python.exe scripts/dev.py --check
.venv/Scripts/python.exe scripts/dev.py --reload
```

På Linux/macOS: `python3.12 -m venv .venv` och `.venv/bin/python` i stället.
`requirements-dev.txt` använder befintliga requirements och versionslås.
Ingen Node-installation behövs för att köra de levererade webbassetsen.

Öppna http://127.0.0.1:8000/personal. `scripts/dev.py` sätter lokal miljö,
stänger av dotenv-inläsning, migrerar `.local/dev/grocery.sqlite` och använder
`.local/dev/plans.sqlite3` för planer. Priser är uttryckligen mock och komplett
receptplanering är avstängd tills verifierat underlag konfigurerats. Vissa
produkt- och planeringsflöden visar därför saknat underlag i denna tomma miljö.
Hjälparen startar ingen prisinsamling, reläuppgift eller deployment.

`--check` migrerar och kontrollerar appimport utan att starta servern.
`--port 8010` väljer annan lokal port. Stoppa servern med Ctrl+C.

## Tester utan privata data

Kör denna begränsade startkontroll från projektroten:

```powershell
.venv/Scripts/python.exe scripts/verify_offline.py backend/tests/test_background_plan_prewarm.py backend/tests/test_planner_admission.py backend/tests/test_beta_release_package.py -m 'not live'
```

`verify_offline.py` spärrar externt nät och dotenv och skriver kontrollunderlag
i `.local/verification`. Utöka med tester för de ändrade delarna. Kör Ruff
på ändrade Pythonfiler och compileall på relevanta paket. Hela sviten har
även tester som kräver separat historiskt dataunderlag; startkontrollen är
inte ett påstående om att hela sviten kan köras från en tom klon.

För browserprov:

```powershell
.venv/Scripts/python.exe -m playwright install chromium webkit
```

För ändringar i streckkodsläsarens byggkällor krävs Node/pnpm:

```powershell
pnpm --dir frontend/barcode-scanner install --frozen-lockfile
pnpm --dir frontend/barcode-scanner check
pnpm --dir frontend/barcode-scanner build
```

## Utveckling med verkliga priser och näringskopplingar

Begär ett behörigt, sammanhängande utvecklingsunderlag från projektets
förvaltare: aktivt PriceUniverse med manifest, grocery-databas och dess
refererade råsnapshots. Använd inte privata produktionsprofiler för tester.
De små fixturerna i Git räcker för enhetstester men ersätter inte detta underlag.
Gamla mätningar måste också köras med sina dokumenterade testklockor.

Historiska testfiler kan återställas med befintlig hashkontroll:

```powershell
.venv/Scripts/python.exe scripts/restore_local_data.py --backup <skyddad-backupkatalog>
.venv/Scripts/python.exe scripts/restore_local_data.py --backup <skyddad-backupkatalog> --check
```

För den egna datauppsättningen, använd separat lokal konfiguration med
`GROCERY_DATABASE_URL`, `GROCERY_RAW_SNAPSHOT_ROOT`, `PRICE_UNIVERSE_CACHE_ROOT`,
`PRICE_UNIVERSE_CITY`, `PRICE_UNIVERSE_REQUIRED=true`, `COMPLETE_RECIPES_ENABLED=true`
och en egen `PLAN_STORE_PATH`. Prisdata och dess källreferenser måste stämma
överens. Starta då Uvicorn direkt med denna miljö, inte `dev.py` som avsiktligt
väljer den tomma mockmiljön:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Se `.env.example`, aktuella fält i `backend/app/config.py` och
`grocery_data/app/config.py`. Hemligheter tillförs separat och får aldrig committas.
Använd Linux/macOS-separatorn `:` i `PYTHONPATH` på dessa system.

## Arbetsflöde och leverans

```powershell
git switch main
git pull --ff-only
git switch -c fix/min-andring
# Ändra och verifiera berörda delar.
git add <granskade-filer>
git commit -m "Beskriv ändringen"
git push -u origin fix/min-andring
```

Integrera granskade ändringar på `main` via PR eller kontrollerad merge,
och pusha huvudgrenen. Kloning och betarelease ska därefter kunna utgå från
`main`; en äldre arbetsgren ska inte behövas för att hitta aktuell kod.
En arbetskopia har en aktiv skrivare. Andra parallella uppgifter använder
uttryckliga Git-worktrees. Ändra inte någon annans checkout.

För betan: följ [BETA.md](BETA.md). Utvecklingsstart aktiverar ingen server.
Historiska reproduktionsinstruktioner finns i
[utvecklingshistoriken](development-history-20260929.md); de är inte standardstarten.
