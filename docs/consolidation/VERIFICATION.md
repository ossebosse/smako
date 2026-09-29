# Verifiering av lokal konsolidering

**Konsolideringsverifieringen är godkänd inom den redovisade testomfattningen.**
Den samlade roten och en ren lokal klon gav samma resultat: **672 godkända,
fem befintliga fel, inga nya fel** bland 677 unika testfall. Detta är inte ett
påstående att hela projektets testsamling eller en produktionsrelease är godkänd.
Ingen olöst funktionell kodkonflikt har identifierats.

## Körningar och jämförelse

| Körning | Godkända | Fel | Betydelse |
| --- | ---: | ---: | --- |
| Första baspasset i isolerad kopia | 586 | 25 failed + 21 errors | Fyra gamla assertion-fel, saknad historisk Lidl-fixture och ännu ej kopierade stora underlag |
| Basomkörning efter dataåterställning | 63 | 2 failed | En ytterligare PDF som sedan återställdes; befintligt benchmarkfel |
| Samlad rot, 655 testfall | 650 | 5 failed | Samma fem produkt-/testfel som i basen, inga fixture-/importfel |
| Kompletterande rådata-/testutdataprov | 23 | 0 | 22 ytterligare fall och ett omkört fall efter flytt av testutdata |
| Ren klon, 655 testfall | 650 | 5 failed | Samma resultat med egen miljö och egna återställda data |
| Uppdaterad ren klon, kompletterande prov | 23 | 0 | Verifierar sista testutdataändringen och separata råfakta |

De fyra sista raderna omfattar 677 unika fall i vardera arbetskopian; omkörda
fall dubbelräknas inte. Maskinellt resultat per fall och XML-hashar finns i
`verification-results.json`. Råloggar finns i respektive `.local/verification`
och kopieras till backupens separata `consolidation-results` vid avslut.

Den rena klonen skapades med `git clone --no-hardlinks` under
`D:\Smako-consolidation-work\clean-clone`. Python 3.12-venv skapades på nytt och
beroenden installerades från manifest/låsning med lokalt wheel-arkiv.
887 lokala underlag återställdes med storleks- och SHA-256-kontroll från backupen.
Inga gamla datum-mappar användes som runtime-/fixturekälla. Python-audit spärrade
fil-/SQLite-läsning från det gamla Codex-området, och i klonen även från den
permanenta arbetskopian. Externa socketanslutningar spärrades; inga blockerade
försök registrerades. Detta är en Python-kontroll, inte en OS-sandbox.

## Fem kända basfel, oförändrade

- `backend/tests/test_coop_physical_pipeline.py::test_real_own_universe_checkout_and_audit[3839-44]`: 93 produkter mot äldre förväntan 44.
- Samma test `[3815-77]`: 246 mot 77.
- `grocery_data/tests/test_coop_municipal_contract.py::test_actual_second_municipality_pdf_bound_to_store_not_shared_prices`: 18 mot 10.
- `grocery_data/tests/test_coop_municipality.py::test_real_stora_age_conditions_stay_in_quarantine_not_global_failure`: 384 mot 77.
- `backend/tests/test_benchmark_diversity_modes.py::test_mock_diversity_benchmark_uses_one_snapshot_for_all_modes`: Too few quality-valid candidates.

Dessa tester finns kvar utan xfail eller försvagade assertions. De behöver
separat produkt-/testbedömning; konsolideringen ändrar inte deras förväntningar.
Historiska rapporters uppgift om 457 godkända regressioner ersätter inte denna
verifiering av den faktiskt återfunna arbetskopian.

## Funktioner och representativ återspelning

Testurvalet omfattar kedje-/kommunflöden, gemensamma PurchaseTerms, exakta,
uppskattade och villkorade köp, närings-/beredningskontroller, sök-/beamoptimering,
personlig planering, API-vägar, revisioner, audit och lagring. Alla 16 prov i den
tidigare blockerade `test_reviewed_lidl_nutrition.py` passerade med autentiskt
återfunnet underlag och ursprungliga bildhashar.

`scripts/planner_replay.py` återspelar det befintliga riktiga ostsmörgåsprovet
med klockan **2026-09-24 21:16 UTC**. Bas, samlad rot och ren klon gav identisk
korg, närings-/beredningsevidens och audit: **171,68 kr**, audit PASS och identisk
sparning/återläsning i nya SQLite-instans­er. Köp av ost: 153,78 kr för 2 200 g,
100 g använt. Näringskontrollen är fortfarande ESTIMATED; observationsdatum
och begränsningar har inte föryngrats.

Råfaktaproven läser både den sparade 2 024 501 248-byte-databasen och dess
separata källfiler. Databasen kopierades under skrivspärr och återställdes med
fullständig SHA-256-verifiering. En extra read-only `PRAGMA quick_check`-helscan
avbröts efter långvarig disk-I/O utan slutresultat och räknas inte som godkänd;
de riktade databas-/råfaktaproven passerade i båda arbetskopiorna.
Ett befintligt test skrev tidigare sin resultatsammanställning till en historisk
rapport. Utdata ligger nu i `tmp_path`; alla assertions är kvar. Rapportens
originalhash verifierades oförändrad.

## Övriga kontroller och begränsningar

- Ruff på backend/app, grocery_data/app och nya Python-hjälpare: PASS.
- Compileall på backend, grocery_data och scripts: PASS; den sista teständringen
  kördes dessutom i båda arbetskopiorna.
- `pip check`: PASS i båda miljöerna.
- Frontend: 30/30 tester, syntaxkontroller och esbuild PASS. Byggd JavaScript
  matchar basen efter CRLF-normalisering; originalbytes behölls i arbetskopian.
- 583 av kandidatmanifestets 593 filer är fortfarande byteidentiska i den nya
  roten. De tio avvikelserna är åtta browserhjälpares portabla sökvägar och två
  kompletterade beroendefiler; ingen appmodul ändrades. Exakt lista finns i
  `runtime-package-check.json`.
- 35 spårade fixtures har samma arbetskopiebytes men korrigerad Git-textbehandling
  för att bevara sina hashkontrollerade radslut efter kloning. Detta är inte en
  omformatering av källornas innehåll. Återfunnen adapter behåller sin historiska
  avslutande blankrad; den avsiktliga whitespace-anmärkningen finns dokumenterad.
- Git fsck: PASS; dangling blob-notiser är bevarade objekt, inga integritetsfel.
  Alla tio ursprungliga refs verifierades före huvudgrenens fast-forward;
  en tidigare oåtkomlig commit har en arkivgren. Ingen alternate eller gammal
  worktree-pekare finns i den nya lagringen.
- 56 059 filers storlek/mtime i de nio originalkopiorna var oförändrade vid
  efterkontroll. Backupen omfattar även nio filer i den partiella checkpointen.
- Staged innehåll och storlekar granskades före varje commit. Tokenmönstersökning
  gav inga fynd. Nyckelfältsgranskning i JSON-fixtures hittade endast två offentliga
  butikstelefonfält; inga privata användaruppgifter. Historiska driftdatabaser
  finns ändå kvar i Git-historiken och kräver separat granskning före publicering.
- Fullsviteförsöket avbröts på grund av långsam SQLite-I/O och räknas inte som en
  färdig totalsvit. Live-insamling, verklig produktion och browser-E2E kördes inte.
  Docker-daemon saknades: containerbygge är inte verifierat och ingen daemon
  startades. Lokal frontendbyggnad och Pythonkontroller är verifierade.
- Två oläsbara gamla pytest-tempkataloger ingår inte i backupens verifierade
  omfattning; se CONSOLIDATION.md. Originalen är kvar. Ingen städning godkänns
  av denna lokala konsolideringsverifiering.

Avsedd huvudgren är `master`, med lokal tagg `consolidation-20260929-local`.
Taggen avser konsolideringen och innebär ingen produktionsaktivering.
