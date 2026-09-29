# Lokal konsolidering av Smako, 2026-09-29

Permanent projektrot är **`D:\Projects\Smako`**, uttryckligen vald av användaren
eftersom C: saknade utrymme. Detta är ett lokalt utvecklingsrepository, ingen
produktionsrelease. Originalmapparna har inte flyttats, raderats eller ändrats.
Ingen remote har skapats i projektet och inget har pushats.

## Vald bas och ursprung

Basen är arbetskopian `2026-09-16/municipality-coverage-20260920` under
`C:\Users\ossia\Documents\Codex`, på `areas/municipality-audit-20260920`,
HEAD `02ad73b8491f4b30679b3151b52686e27bedb8e6` **plus dess faktiska lokala arbete**.
Alla 593 källfiler i den senaste återfunna kandidatens paketmanifest matchade
arbetskopians SHA-256. Kandidat: `smako-legacy-purchase-terms:20260929-v5`,
image `sha256:eee77ff22794b02c80d20457a33d7fc4aacf11fd4a3f277860e93fb12f7c0eba`.
Manifestet finns i `consolidation/baseline-package.json`. Inget senare lokalt
manifest med avvikande aktiv implementation återfanns. Datum och ändringstid
användes inte som ensam grund för valet.

Inventerade fullständiga arbetskopior, med sökvägar relativt källområdet:

| Rot | Typ och ursprunglig branch | HEAD | Beslut |
| --- | --- | --- | --- |
| `2026-08-20/jag-vill-att-du-bygger-en` | Vanlig projektkopia, ingen Git | – | Frontendkällor, låsfil, testisolering och tre skript integreras; övrigt arkiveras |
| `2026-09-10/milestone-smako-v2-personlig-planering-skafferi` | Gemensamt självständigt Git-repo, `codex/personal-v2-gaps` | `01ee7b7` | Historik och lokalt tillstånd bevaras |
| `2026-09-12/milestone-l-s-upp-fem-middagar` | Worktree, `milestone/five-dinners-20260912` | `3e53363` | Äldre implementation, bevaras |
| `2026-09-12/milestone-prisv-rd-och-bred-femmiddagsplanering` | Worktree, `milestone/affordable-five-dinners-20260912` | `8a2a946` | Äldre implementation, bevaras |
| `2026-09-13/milestone-f-anv-ndarens-kombinerade-40` | Worktree, `milestone/combined-40-30-20` | `8023488` | Äldre implementation, bevaras |
| `2026-09-13/milestone-fr-n-sex-minuter-till` | Worktree, `perf-combined-403020` | `02ad73b` | Historik och rapporter bevaras |
| `2026-09-13/milestone-leverera-fem-middagar-utan-fisk` | Worktree, `milestone/fishfree-20260913` | `4cb6bc8` | Äldre implementation, bevaras |
| `2026-09-14/n-sta-delm-l-f-r` | Worktree, `sources/lidl-ica-evaluation-20260914` | `02ad73b` | Fem autentiska Lidl-beroenden integreras; tidigare appversion arkiveras |
| `2026-09-16/municipality-coverage-20260920` | Worktree, `areas/municipality-audit-20260920` | `02ad73b` | Aktuell arbetskopia är basen |

Dessutom inventerades och säkerhetskopierades det partiella checkpoint-underlaget
`2026-09-07/for-the-poc-with-the-recipe`. Dess handoff hänvisar till augustiroten.
Övriga tomma uppgiftsmappar och andra projekt under källområdet lämnades orörda.
Det orelaterade juli-projektet distribution-intelligence ingår inte.

Samtliga äldre milestone-branches är anfäder till basens HEAD. Inga remotes,
tags, stashes, submoduler, shallow-gränser eller Git-alternates återfanns.
Index, unstaged/untracked/ignored tillstånd och reflogar finns i backupen.
Basens index hade inga staged ändringar; en initial inventeringsserialisering
tappade första statusradens inledande blanksteg, vilket kontrollerades separat.
Ingen avsiktlig filborttagning i basens arbetskopia återfanns att återuppliva.

## Skillnader och integration

`consolidation/comparisons.json` innehåller filklassificering och normaliserade
hashar för alla jämförda kodkopior. 849 av 863 avvikande äldre filversioner
matchar Git-objekt eller sparade historiska kodfiler exakt efter CRLF-normalisering
(`old-change-evidence.json`). De återstående 14 gäller augustis ignore-regler,
septemberhandoff och redan vidareutvecklad OWN-, korg-, faktakälle-, kommun-,
ICA- och PurchaseTerms-kod med tillhörande tester.

Septemberversionernas skillnader granskades: den nya basen tillför kommun- och
källbindning, gemensamma PurchaseTerms, verifierade kampanj-/viktvillkor,
konservativ behandling av osäkra ordinarie Coop-priser, kompletterande närings-
och råformsfakta, sökoptimering samt frysta testklockor. Dessa rättningar får inte
ersättas med äldre filer. Historiska snapshots som visar ersatta versioner listas
i `supersession.json`. Ingen olöst funktionell kodkonflikt identifierades.

Integrerat från äldre arbete, med exakta ursprung och SHA-256 i
`consolidation/integrated-files.json`:

- Streckkodsläsarens `frontend/barcode-scanner` med källor, tester, licensnotiser,
  paketmanifest och pnpm-låsfil. Den befintliga byggda filen matchade basen.
- Rotens `conftest.py`, som isolerar tester från utvecklarens dotenv.
- `scripts/refresh_prices.ps1`, `start_field_server.ps1`, `start_field_tunnel.ps1`.
  Dessa bevaras som verktyg; de kördes inte och innebär ingen aktivering.
- Lidl-adaptern i `reports/source-implementation-20260915`, ursprunglig
  `lidl-lund-candidate.json`, `public-declarations.json` och två PNG-bevis.
  Inga ersättningsfixturer fabricerades och inget test togs bort.

Åtta browserhjälpares absoluta `D:/codex-smako-loading-hotfix-20260909/...` har
ersatts med Playwrights installerade browser. Ingen massformatering eller
arkitekturomläggning gjordes. Historiska rapporters sökvägar och tidpunkter är kvar.

## Git-lagring och historik

Den nya roten har en egen `.git`-katalog, egna objekt utan alternates/hårdlänkar
och inga worktree-pekare till datum-mapparna. Användbara ursprungliga branches
och objekt bevaras. Den oåtkomliga committen
`20240154f06365966784c0351398b0bd908dd9ed` har förankrats som
`archive/pre-consolidation-20240154`; dess skillnader mot närliggande nåbar commit
är historiska rapporter. Den ursprungliga Codex-checkpoint-refen till ett träd
har också bevarats. Ursprungliga reflogar och worktreeadministration finns i
backupen, utan att göra den nya arbetskopian beroende av dem.

Integration sker på `chore/consolidate-smako`. Befintlig Git-identitet används.
Separata commits avser aktuell implementation, återfunnet arbete, portabilitet
och utvecklingsdokumentation. Avsedd huvudgren är den befintliga `master`, som
kan fast-forwardas utan historikomskrivning efter konsolideringsverifieringen.
En lokal konsolideringstagg är uttryckligen inte en produktionstagg.

## Säkerhetskopia och lokalt tillstånd

Backup: **`D:\Smako-backups\consolidation-20260929`**.
56 068 filer, 33 226 714 403 byte. Alla kopierade filer hashverifierades mot
destinationen. Windows-läshandtag som nekade WRITE/DELETE hölls över hela
säkerhetskopieringen; källornas metadata kontrollerades före/efter. Inga Smako-
skrivprocesser eller andra aktiva Smako-agentuppgifter återfanns då. Git-data och
faktiskt arbetskopietillstånd kopierades, inte bara commits eller textdiffar.
Lokala databaser kopierades under samma skrivspärr; inga driftjobb stoppades.

`checksums.jsonl`, fullständig `inventory.json`, `verification.json` och
`snapshot/` finns i backupen. Backupens behörigheter begränsades till aktuell
Windows-användare och SYSTEM. Manifestets hash finns i
`consolidation/backup-verification.json`.

**Dokumenterade luckor:** två kataloger under checkpointen 2026-09-07 nekade
läsning: `reports/deployment-verification-20260907/pytest-startup-temp` och
`reports/deployment-verification-20260907/pytest-temp`. Inga rättigheter ändrades
på originalen. Deras innehåll är inte verifierat säkerhetskopierat. Tretton pnpm-
länkar bevarades som länkmetadata med målens filer i snapshoten; node_modules
återskapas i utvecklingsroten. Därför lämnas samtliga original kvar.

Driftdatabaser, dotenv, privata svar, sessioner, caches, miljöer och stora exporter
är inte nya Git-filer. Tre historiskt spårade SQLite-filer togs bort ur det nya
indexet, men inte ur historiken eller säkerhetskopian:
`grocery_data/.cache/scanner_mobile_smoke.sqlite`,
`grocery_data/.lund_production_refresh_20260826_v2.sqlite`,
`grocery_data/grocery_data.sqlite`.

Rapportkatalogerna analyserades för Python-importer, filöppningar och testdata.
Aktiv rapportkod och dokumentation bevaras i Git; äldre kodsnapshots förblir
arkivunderlag. Stora JSON/PDF-/databas-/råfilberoenden har separata hashmanifest
och ett kontrollerat återställningsverktyg. JSON ignoreras inte generellt.
Lidl-fixturerna har uttryckliga ignore-undantag. `.gitattributes` bevarar bytes
i de återfunna Lidl-bevisen och hashkontrollerade fixtures även efter kloning.

Mönstersökning av 1 694 historiska Git-blobbar och 4 015 arbetskopiefiler gav
inga högkonfidensfynd av token-/nyckelvärden. Detta är ingen garanti om all
historisk data. Gamla driftdatabaser finns fortfarande i historiken och behöver
separat sekretessgranskning före eventuell extern publicering. Ingen sådan
publicering ingår eller har genomförts; historiken har inte skrivits om.

## Sökvägskarta och externa beroenden

- Aktiv kod i vald bas → samma relativa sökväg under `D:\Projects\Smako`.
- Äldre ointegrerade versioner → respektive oförändrade original och motsvarande
  `snapshot/<datum>/<uppgift>/` i säkerhetskopian.
- Selektivt lokalt rapportunderlag → samma relativa `reports/...`, med
  `evidence-*.jsonl` och `test-data.jsonl` som exakt gammal→ny-karta.
- Browserbinär i gamla hotfixkatalogen → Playwrights installerade browser.
- Nya lokala databaser och användartillstånd → ignorerad `.local/runtime/`.

Windows-uppgiften **Smako Willys Local Relay** använder fortfarande augustiroten
som arbetskatalog och `-Repository`, samt dess
`deploy/scripts/collect_willys_local.ps1`. Lokalt relay-tillstånd ligger i
`D:\smako-local-relay`. Uppgiften var Ready vid inventeringen; nästa körning
redovisades som 2026-09-30 01:30. Inga uppgifter, aktiva scheman, serverinställningar
eller sparade användarprofiler har ändrats. Innan augustiroten kan avvecklas krävs
ett separat beslut och verifiering av dessa externa sökvägar.

Ingen ny lokal checkout gör historiska priser färska. Den senaste kandidatens
produktionstillstånd är **inte aktiverad enligt dess lokala handoff**; aktuell
serverstatus har inte undersökts eller ändrats.

## Verifiering

Slutlig konsolideringsverifiering: 672 godkända och fem befintliga fel bland
677 unika testfall, med identiskt utfall i ren klon och inga nytillkomna fel.
Alla 16 återställda Lidl-prov passerar. 887 lokala testunderlag har kontrollerad
återställning. Huvudgrenen etableras genom fast-forward; lokal tagg är
`consolidation-20260929-local`, utan innebörd som produktionsrelease.

Slutresultat och kvarstående basfel redovisas i det separata
`consolidation/VERIFICATION.md`. Isolerade återspel använder historiska klockor,
sparade rådata, mock-/lokala API:er och spärr mot externa nätverksanrop.
Ett inledande fullsviteförsök avbröts på grund av långsam temporär SQLite-I/O och
räknas inte som ett avslutat testpass. Relevanta avgränsade tester, ren klon,
planner/audit/sparning/återläsning, Python- och frontendkontroller redovisas var för sig.

## Öppna rätt projekt

Öppna/lägg till den lokala mappen `D:\Projects\Smako` som projekt i Codex och
gör den till primär mapp om projektet innehåller fler mappar. Börja nya uppgifter
där och kontrollera rot/branch/status. Alternativt kan CLI startas med
`codex --cd D:\Projects\Smako`. Gamla chattar behåller sina gamla arbetskataloger;
de flyttas inte automatiskt. Inga interna chattdatabaser har ändrats.
Se [OpenAI: Projects and chats](https://learn.chatgpt.com/docs/projects).
