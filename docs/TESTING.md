# Tester

## Varor och recept i CI

Jobbet `coverage-overview` räknar om hela bibliotekets produkt-/recepttäckning
mot en hash-låst offentlig Malmöreferens. Summary, full JSON och produktstatus
sparas som artefakten `coverage-overview` i 30 dagar. Även detta jobb krävs av
den gemensamma `backend`-grinden. Hela importnämnaren, förlorade originalrecept
och ofullständiga korgkontroller bevakas. Körning och definitioner:
[COVERAGE-OVERVIEW.md](COVERAGE-OVERVIEW.md).

Genereringens kall-/varmprestanda har ett separat konkret förslag där; tiderna
i täckningsjobbet är inventeringstid, inte latens för en veckomeny.

```powershell
.venv\Scripts\python.exe scripts\verify_offline.py backend/tests -m "not live" -q -rfEs
```

`verify_offline.py` kör pytest utan nätverk mot handlare och utan läsning
utanför repot. GitHub Actions (`.github/workflows/tests.yml`) kör samma
testurval i tre separata partitioner vid push till `main` och för varje pull
request, plus Ruff på ändrade Python-filer. Ett gemensamt `backend`-jobb kräver
att alla tre partitionerna lyckas. Nya filer ingår automatiskt i core;
fyra planerar-/provider-/browserfiler körs i planner och tretton hela filer
utan webbläsarkrav i integration. Det exakta urvalet finns i workflow-filen.
JUnit sparas i sju dagar och
de 30 långsammaste testerna skrivs ut. Ersatta PR-körningar avbryts.

## Snabbare körningar

Hela sviten är cirka 6 800 tester. Nästan alla tar under en halv sekund; ett
sextiotal tunga tester (≥ 4 s, fullbiblioteks-sökningar och kommunleverantörer)
är markerade `@pytest.mark.slow` och står för större delen av tiden.

| Läge | Kommando | Ungefärlig tid* |
| --- | --- | --- |
| Under arbete: berörda filer | `scripts\verify_offline.py backend/tests/test_x.py -m "not live" -q` | sekunder |
| Före PR: allt utom tunga | `scripts\verify_offline.py backend/tests -n auto --dist loadfile -m "not live and not slow" -q` | några minuter |
| Hela sviten (gör CI) | `scripts\verify_offline.py backend/tests grocery_data/tests -n auto --dist loadfile -m "not live" -q` | se nedan |

\*Uppmätt 2026-11-03 i en molnmiljö med två kärnor, hela `backend/tests` +
`grocery_data/tests`: 32 min seriellt före ändringarna, 16,5 min med `-n 2`
och 10,4 min med `-n 2` plus GC-ändringen nedan. Samma tester fallerade i alla
tre körningarna. Fler kärnor ger mer.

- `-n auto` kör med `pytest-xdist` en process per kärna. `--dist loadfile` håller
  varje testfil i samma process så att modulfixturer byggs en gång.
- `verify_offline.py` installerar nät- och källspärren även i varje
  xdist-process (via `conftest.py`) och slår ihop processernas
  `<etikett>-access.json`.
- `conftest.py` låter planerarens minnesåtervinning (`release_idle_memory`)
  göra en snabb GC av unga objekt i stället för full GC. I en testprocess med
  alla tidigare testers cacher tog full GC mer än halva tiden i
  fullbibliotekstester. Minnestesterna använder riktig GC;
  `SMAKO_TEST_FULL_GC=1` slår på den överallt.
- CI kör allt, även `slow`, med `-n auto` i alla tre partitioner.
- Ett nytt test som tar mer än cirka 4 s markeras `@pytest.mark.slow`.

## Lokal evidens (överhoppade tester)

Några tester spelar upp sparade källfångster under `reports/`. Där spåras bara
`*.py` och `*.md`; underlaget återställs från den skyddade backupen. I en ren
klon och i CI rapporteras sådana tester som **SKIPPED** med den saknade sökvägen
(`conftest.py`, gäller bara `FileNotFoundError` för filer under `reports/`).
På en maskin med underlaget återställt: sätt `SMAKO_REQUIRE_LOCAL_EVIDENCE=1`
så att en saknad fil åter blir ett fel. Kroken är bred: en felstavad framtida
sökväg under `reports/` skulle också bli ett skip. Uppföljning: ersätt den med
uttryckliga evidensfixturer per test.

## Webbläsartester

`test_personal_choices_browser.py` kräver Playwright-webbläsare
(`python -m playwright install chromium webkit`); CI installerar dem. Lokalt
utan webbläsare ger de ERROR vid uppsättning.

## Kända fel

Tio tester fallerar redan på `main` (46d834b) av andra skäl än saknad evidens
(fyra i `test_purchase_planning_modes.py`, två i `test_public_menu_errors.py`,
två i `test_public_beta_ui.py`, ett vardera i `test_municipal_runtime.py` och
`test_plan_api.py`). De är markerade `xfail(strict=True)` i `conftest.py`. När ett av dem rättas blir CI rött tills det tas bort ur
listan. `grocery_data/tests` ingår inte i CI ännu; de har egna kända fel som
behöver klassas på samma sätt.
