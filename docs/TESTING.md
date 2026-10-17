# Tester

```powershell
.venv\Scripts\python.exe scripts\verify_offline.py backend/tests -m "not live" -q -rfEs
```

`verify_offline.py` kör pytest utan nätverk mot handlare och utan läsning
utanför repot. GitHub Actions (`.github/workflows/tests.yml`) kör samma
kommando för `backend/tests` vid push till `main` och för varje pull request,
plus Ruff på ändrade Python-filer.

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
