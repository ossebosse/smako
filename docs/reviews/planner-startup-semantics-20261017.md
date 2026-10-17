# Granskning av planner-startup-semantics, 2026-10-17

## Resultat och integration

De 17 commitsen i `smako-planner-startup-semantics.patch` applicerades utan
konflikter ovanpå `46d834b`. Importerad slutcommit är `35dc44f`.
Författaruppgifter, commitmeddelanden och uppdelning bevarades med `git am`.
Granskning gjordes på `review/planner-startup-semantics`, för integration på
lokal `main` enligt beställningen. Inga runtimeändringar har lagts ovanpå
patchen i denna granskning. Ingen push eller betaaktivering ingår.

Ändringarna passar Smakos mål: fler köpbara recept, återanvändning av befintlig
prismotor, mindre sökarbete och bättre feltext. Patchen är **inte färdig för
betarelease**. Nedanstående fel behöver åtgärdas eller uttryckligen hanteras.
Gröna befintliga tester räcker inte som acceptans för dessa beteenden.

## Fynd

### 1. P1: En populationsuppskattning blir verifierad äggmängd i exakt läge

`backend/app/services/official_product_facts.py:411` och `:462–470`.
Klassens minsta skalvikt multipliceras med 0,88 och projiceras som `DERIVED`
även när `allow_estimates=False`. Referensfilen beskriver däremot uttryckligen
andelen som `documented_population_estimate` och rekommenderar vägning för
att verifiera ett ätbart minimum. En undre gräns för skalvikt tillsammans med
en genomsnittlig ätbar andel bevisar ingen undre gräns för ätbar vikt.

Reproduktion: ett 15-pack M ger 699,6 g och `derived` utan uppskattningsmedgivande;
bevisets egen kvalitet är samtidigt `documented_population_estimate`.
`PersonalPlanner` presenterar mängder som `VERIFIED` när ingen köprad är
`estimated`. Det kan därför ge missvisande mängdgaranti vid förpackningsgränser.

Patchens HANDOFF dokumenterar ägarens godkännande av affärsregeln. Det ändrar
inte bevisets kvalitet. Behåll en tydlig uppskattnings-/policyklassificering,
eller inför ett separat verifierat underlag för en verklig undre gräns.
Granskningen ändrar inte det dokumenterade ägarbeslutet på eget initiativ.

### 2. P2: Näringskonflikter används fortfarande för att kvalificera produkter

`backend/app/services/complete_recipes.py:226`, med konsumenter på `:267–268`
och `backend/app/services/content_pack_requirements.py:55`.
Den nya regeln släpper igenom `nutrition.*`, men kraven `thick`, `cottage_cheese`
och `creme_fraiche` kan fortfarande läsa fett från just dessa osäkra fakta.

Reproduktion: `Grekisk Yoghurt Naturell` utan fettprocent i namnet godkänns för
`plain, thick` med `nutrition.fat_g`-konflikt och `fat_g=10`. Tar man bort det
konfliktmärkta fettvärdet underkänns samma vara. Detta är nytt genom att den
tidigare övergripande konfliktspärren har tagits bort. Näringssummeringarnas
spärrar finns kvar, men produktvalet följer inte löftet att konfliktvärden
aldrig används. Spärra näringsfallback vid konflikt i båda konsumenterna.

### 3. P2: Uppvärmningen kan fortfarande blockera användarens faktaläsning

`backend/app/services/source_facts_prewarm.py:56–62`, tillsammans med
`backend/app/services/personal_source_facts.py:691`.
Tråden använder inte planner admission, men `_load_retained_catalog_facts`
håller ett gemensamt `_LOCK` under databasläsning, hashning och projektion.
En användare som behöver fakta medan uppvärmningen läser en annan kommun
väntar på samma lås. Modulens påstående att användaren i värsta fall bara
upprepar inläsningen stämmer därför inte.

Kontrollerad trådreproduktion med tillfällig SQLite-databas visar att
användaranropet inte ens når databasanslutningen förrän uppvärmningen släppts.
Detta är ett låsbeteendeprov, ingen mätning av produktionslatens. Begränsa
låsningen till cachepublicering eller inför prioritering/per-underlagslås,
och mät kalla användaranrop under faktisk kommunuppvärmning.
Den äldre helmenyuppvärmningen stängs inte heller av av denna patch;
dess serverflagga är fortsatt en separat driftåtgärd.

### 4. P2: Sammanslagna ingredienser tappar senare komponenters produktkrav

`backend/app/services/recipe_authoring.py:90–96`.
Nyckeln är bara `canonical|form`. `setdefault` bevarar första komponentens
`product_requirements`, medan senare komponenter bara adderar mängd.

Reproduktion utifrån det medföljande exemplet: 150 g yoghurt med `plain` och
20 g yoghurt med `plain, thick` blir en validerad rad på 170 g med endast
`plain`. Tjockhetskravet försvinner utan avvisning. Samma fel kan gälla olika
styckningsdetaljer eller andra packkrav. Avvisa motstridiga krav eller hantera
dem med en uttrycklig kompatibilitetsregel innan mängder slås ihop.

### 5. P2: Aktiv arbetstid tappar arbete utanför den kritiska kedjan

`backend/app/services/recipe_authoring.py:48–58` och `:123`.
`active = total - waiting` använder väntan på endast den längsta kedjan.
Aktivt arbete som görs under ugnstiden i andra grenar försvinner ur aktiv tid.

Det medföljande souvlakiexemplet har aktiva steg på 6 + 6 + 5 + 4 + 10 =
31 minuter, men verktyget publicerar 16 aktiva och 30 vänteminuter. Receptet
kan då passera användarens gräns på exempelvis 20 minuters aktiv matlagning.
Beräkna aktivt arbete över alla aktiva steg och modellera överlapp/väntan
separat. Valideringen och exemplet behöver följa samma tidsdefinition.

### 6. P2: Patchens nya PR-kontroll faller på dess egna rapportskript

`.github/workflows/tests.yml:29–33` och `reports/recipe-packs-20261017/*.py`.
Ruff-steget granskar alla ändrade Pythonfiler. Samma urval lokalt ger 23 fel,
samtliga i de sex nya rapportskripten: imports, oanvända namn, `SIM115`,
`C408` och `RUF059`. En PR med patchen blir därför röd i den nya kontrollen.
Rätta skripten; dölj inte felen genom att ta bort den avsedda kontrollen.

## Verifiering

- Python 3.12.10, offline via `scripts/verify_offline.py`.
- 250 tester passerar i de sju riktade filerna för authoring, äggklass,
  seedtak, offertåterbruk, uppvärmning, kampanjbutikstext och produktsemantik.
- 343 tester passerar i elva regressionsfiler för komplett receptintegration,
  receptpaket/bibliotek, produktlänkar, scope-incumbents, tidigare uppvärmning,
  admission, betapaketering, beräkningscache, värdeinterning och Coop-energi.
  Åtta Pydantic-varningar. Inga skips eller xfails i dessa två serier.
- Båda seriens åtkomstloggar: inga rapportläsningar eller blockerade externa
  nät-/gamla workspaceförsök.
- `compileall` på app, backendtester och nya rapportskript passerar.
  `git diff --check` passerar. Ruff på hela ändringsmängden ger de 23 felen ovan.
- Den valda menyn räknas om och auditeras före leverans. Testet för omförsök
  efter auditfel passerar. Ingen konkret väg för att leverera en oauditerad
  korg hittades i granskningen.

Lokala råresultat: `.local/verification/patch-small.{log,xml}`,
`patch-regression.{log,xml}`, motsvarande `*-access.json`, samt
`patch_review_repro.py` och `patch-review-repro.json`. Reproduktionerna är
diagnosprober som bekräftar dagens fel, inte nya godkännandeprov.

Ingen fullsvit, verklig kallstartsmätning, parad före/efter-matris eller
ny Lund/Malmö-kvalificering mot aktuella prisunderlag utfördes. Patchens
historiska prestandatal är därför inte självständigt verifierade här.
De elva globala xfail-markeringarnas påstådda baslinjefel har inte återspelats;
de användes inte av ovanstående 593 tester. Den breda FileNotFoundError-hooken
under `reports/` bör på sikt ersättas med uttryckliga evidensfixturer så att
framtida felaktiga filsökvägar inte ser ut som normala skips.

## Brancher före importen

`git fetch --all --prune` lyckades. Lokal `main` och `origin/main` pekade båda
på `46d834b`. Ingen befintlig lokal eller hämtad remote-branch hade en nyare
senaste commit än den. Alla remote-brancher var redan anfäder till `main`.

Äldre lokala sidogrenar har fortfarande commits som inte är anfäder till main:

| Gren | Egna commits | Commits bakom main |
| --- | ---: | ---: |
| `feature/recipe-integration` | 45 | 365 |
| `feature/recipe-library` | 13 | 308 |
| `feature/recipe-ui` | 22 | 365 |
| `perf/recipe-quote-reuse` | 12 | 296 |
| `release/willys-storage-20261007` | 1 | 387 |
| `archive/pre-consolidation-20240154` | 1 | 407 |

Därtill finns tio `verification/meal-library-p1-*` med var sin egen historisk
verifieringscommit, 166–191 commits bakom main. Egna commits betyder inte att
deras funktionalitet saknas på main; senare integration kan ha annan historik.
De har inte blindmergats och deras arbetskopior har inte ändrats.
