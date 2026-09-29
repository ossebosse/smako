# Lokal utveckling i Smako

Permanent rot: `D:\Projects\Smako`. Huvudgren: `master`. Konsolidering sker på
`chore/consolidate-smako`. Ingen del av dessa instruktioner aktiverar produktion.

## Kontrollera arbetskopian

```powershell
Set-Location D:\Projects\Smako
Get-Location
git rev-parse --show-toplevel
git branch --show-current
git status --short
```

En ändring har en ansvarig skrivare. Parallella agentuppgifter använder uttryckliga
Git-worktrees i detta repository, aldrig nya fristående datumkopior.

## Återskapa miljön

Python 3.12 används. `.venv` och `node_modules` återskapas och versionshanteras inte.
`requirements-dev.lock` anger den verifierade Windows-miljön; befintliga manifest
är kvar och kompletterade med den faktiskt importerade PDF-parsern PyMuPDF.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
pnpm --dir frontend/barcode-scanner install --frozen-lockfile
```

Det lokala wheel-arkivet `D:\Smako-consolidation-work\wheelhouse` kan användas med
`--no-index --find-links` som alternativ till pip-nätverk. Det är inte Git-innehåll.
Browserprov kräver dessutom `python -m playwright install chromium webkit` i vald
miljö. Browserhjälpare använder nu Playwrights installation; `--webkit` i
`personal_v2_browser_check.py` tillåter ett uttryckligt alternativ.

## Återställ sparade testdata

De granskade små fixturerna finns i Git. Stora råsvar, PDF:er och lokala databaser
ingår i den separata säkerhetskopian. `docs/consolidation/test-data.jsonl` anger
exakt sökväg, storlek, SHA-256 och ursprung för testunderlaget, inklusive råfiler
som används för produktfakta. En databas ensam är inte en fullständig återställning.

```powershell
.\.venv\Scripts\python.exe scripts/restore_local_data.py --backup D:\Smako-backups\consolidation-20260929
```

Verktyget vägrar skriva över en avvikande fil. `--check` verifierar utan skrivning.
`--all-evidence` återställer även övrigt selekterat historiskt rapportunderlag i
`evidence-*.jsonl`. Fullständiga ursprungliga arbetskopior, inklusive privata data,
finns endast i den behörighetsskyddade säkerhetskopian. Kopiera inte privata data
till delade testmiljöer. Att en fil ignoreras av Git innebär inte att den backas upp.
Nytt lokalt tillstånd behöver en separat konsistent backup när inga skrivare kör.

## Testa och bygg

Kör från projektroten. Testverktyget spärrar externa nätverksanslutningar och
läsningar under det gamla Codex-källområdet. Loopback till isolerade testservrar
är tillåtet. `PYTHON_DOTENV_DISABLED` skyddar tester mot lokal driftkonfiguration.

```powershell
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$files=Get-Content docs/consolidation/focused-tests.json | ConvertFrom-Json
.\.venv\Scripts\python.exe scripts/verify_offline.py @files -m 'not live'
.\.venv\Scripts\python.exe scripts/planner_replay.py .local/planner-replay.json
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q backend grocery_data
pnpm --dir frontend/barcode-scanner check
pnpm --dir frontend/barcode-scanner build
```

När Docker redan är tillgängligt kan rotens fristående Dockerfile byggas lokalt
med `docker build -t smako:local .`. Detta kommando har inte verifierats här
eftersom Docker-daemon saknades. De historiska kandidat-Dockerfilerna i `deploy`
kräver dessutom uttryckligt `BROWSER_BASE`/`release-wheels`; deras gamla image-
kedja ersätter inte miljöåterskapandet ovan. `.local` ingår inte i byggkontexten.

För hela befintliga sviten, utelämna `@files`. Kända basfel och prov som inte körts
redovisas i `CONSOLIDATION.md`; ingen grön totalsvit påstås. Testdatabaser använder
TEMP/TMP. Under konsolideringen användes en separat temporär katalog på C: för
snabbare SQLite-skrivningar, med kontroll av ledigt utrymme.

## Starta en lokal mockmiljö

```powershell
New-Item -ItemType Directory -Force .local/runtime | Out-Null
$env:PYTHONPATH='backend;.'
$env:PYTHON_DOTENV_DISABLED='1'
$env:APP_ENV='development'
$env:PRICE_PROVIDER='mock'
$env:OPENAI_API_KEY=''
$env:FIELD_MODE_ENABLED='false'
$env:PLAN_STORE_PATH='.local/runtime/plans.sqlite3'
$env:GROCERY_DATABASE_URL='sqlite+pysqlite:///.local/runtime/grocery.sqlite'
$env:GROCERY_RAW_SNAPSHOT_ROOT='.local/runtime/raw_snapshots'
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Detta är en lokal utvecklingsstart med mockpriser. Historiska integrationstester
använder sina ursprungliga observationstider och uttryckliga testklockor.
`.env.example` innehåller inga hemligheter. Verkliga API-/driftuppgifter måste
tillföras separat. Kör inte refresh-, relay-, tunnel- eller deployskript som en
sidoeffekt av utvecklingsstart.

## Ren klon

Klona lokalt med `git clone --no-hardlinks D:\Projects\Smako <tom-katalog>`.
Återskapa `.venv` och testdata enligt ovan. Ange vid verifiering
`$env:SMAKO_FORBIDDEN_ROOTS='D:\Projects\Smako'` i klonen för att även förbjuda
läsning från den permanenta arbetskopian. Använd sedan samma testkommandon.
Git-lagring och testunderlag måste vara självständiga; symlänka inte till äldre rötter.
