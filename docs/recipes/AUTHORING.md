# Lägga in recept med `author`

För en ny förfrågan till Chat: börja med
[arbetsgången för fler recept](REQUESTING-RECIPES.md), dess mall och exportverktyg.
Den binder författaruppdraget till aktuellt bibliotek, produkttäckning och ägarens
preferenser. Följ nedanstående format vid leverans och mottagning.

`author` gör ett kompakt receptutkast till ett vanligt `smako-meal-pack-v1`-paket
och kan i samma körning importera, förbereda och kvalificera det. Författaren
skriver bara det en kock bestämmer; allt Smako härleder räknas fram på samma sätt
för varje recept. Exempel: `docs/recipes/examples/authoring-example.json`.

## Format `smako-recipe-authoring-v1`

Per recept: `base_id`, `name`, `servings`, `meal_type` (dinner/breakfast/snack),
`cuisine`, `family`, `primary`, `method`, `side`, `flavor`, `equipment`, valfritt
`level` (simple/crafted), `version` (1.0.0), `variant_id` (base) och `notes`.

- `components`: `id`, `name` och `ingredients` med `name`, `form`, `quantity`,
  `role` och `label` (visningsnamn). `unit` och `requirements` behövs bara när de
  ska avvika från bibliotekets standard för samma `namn|form`.
- `steps`: `text`, `uses` (ingrediensnamn), `minutes`, valfritt `after`
  (stegnummer från 1) och `passive: true` för väntetid (ugn, sjudning, jäsning).
- Valfritt `unmeasured_processes`: granskad avrinning eller borttagning där
  slutligt utbyte saknas. Varje post har exakt `step` (stegnummer från 1),
  `ingredients` (namn som används i det steget), `operation` och `description`.
  Tillåtna operationer är `drain_after_cooking`, `remove_after_infusion`,
  `deep_fry_and_drain`, `strain_whey`, `peel_after_cooking` och
  `remove_bones_after_cooking`, `trim_before_cooking` och `drain_before_cooking`.
  Ingen absorptionsprocent, densitet eller annan förlustfaktor accepteras.

Ett sådant recept får det separata beredningskontraktet
`smako-authored-losses-v3`. Hela råvaruinsatsen måste kunna köpas, inklusive
frityrolja eller mjölk vars vassle senare silas bort. Näring och färdig
portionsvikt visas som **okända**. Receptet stoppas om användaren har valt
närings- eller portionsviktsgränser; det får inte använda en insatsbaserad
näringsuppskattning eller en tidigare cachepost som bevis för dessa gränser.
Produkt-, kost-, allergen-, butiks- och priskontroller gäller som vanligt.
En fullständigt kontrollerad varukorg utan näringsgränser är därför inte ett
bevis för näringsvärden. Mätningar kräver ett framtida separat granskat underlag.
Gamla receptversioner omtolkas inte: ändrad process kräver ny innehållsgranskad
version med eget innehållshash. Funktionen ersätter inte provlagning.

## Det verktyget standardiserar

- **Identitet och köpkrav:** enhet och produktkrav tas från det befintliga
  biblioteket för varje `namn|form`. Okända identiteter stoppas med förslag.
  Ett uttryckligt granskat tillägg finns i
  `backend/app/data/ingredients/authoring-20261025.json`. Det löser bootstrap
  med källbundna produktreferenser och obligatoriska produktkrav, utan
  låtsasrecept. Det är ingen närings-, allergen- eller ekoattest.
- **Mängder:** komponentmängder, sammanslagna inköpsrader och mängdintervall.
- **Tider (en kock):** aktiv tid = alla icke-passiva stegs minuter, även parallella
  grenar. Total tid = den längsta av stegens kritiska väg och den aktiva tiden.
  Väntetid = resten av totaltiden. `estimated_minutes` = total.
  Total tid får vara upp till 2 880 minuter, väntetid upp till 1 440 och
  aktiv tid upp till 180. Befintliga personliga API-/UI-fält för total- och
  väntetid har dessa gränser och bevaras vid sparning. Gamla
  `recipe_preferences.max_minutes` är fortsatt ett filter upp till 180 minuter.
  Ett långt recept får inte kortas för att passera det filtret.
- **Processvatten:** skriv "N ml vatten" i stegtexten; mängden skalas då med
  portionerna. Vatten i dl eller l stoppas.
- **En inköpsrad, ett kravset:** samma `namn|form` i flera komponenter måste ha
  samma produktkrav, annars stoppas receptet.
- **Kost:** vegetarisk/fisk härleds från ingredienserna.
- **Varningar:** middagar utanför standardvalets 10–15 räknade ingredienser (salt,
  peppar och vatten räknas inte), saknad säkerhetstext (74 °C kyckling, 72 °C färs,
  63 °C fisk), ingredienser som inget steg använder (stoppas).

## Körning

```powershell
$env:PYTHONPATH='backend;.'
.venv\Scripts\python.exe -m app.services.meal_library_cli author utkast.json `
  --output .local/recipes/paket.json --report .local/recipes/rapport.json `
  --import --prepare 2 --prepare 4 `
  --universe prepared-universe.json --clock 2026-10-16T18:12:49+00:00
```

- `--import` publicerar paketet i biblioteket (samma import som `import`).
- `--prepare N` förbereder receptstruktur och portionsskalning för N portioner, så
  att den första planeringen efter import inte bygger dem i användarens jobb.
- `--universe`/`--clock` kvalificerar varje recept som en egen vecka i ordinarie
  planerare (exakt inköpsläge och 2 butiker som standard; `--purchase-mode`,
  `--max-stores`). `--facts` använder en offline-export av produktfakta.

Rapporten anger per recept räknade ingredienser, tider, kost, varningar,
`default_selection` (väljs med standardinställningarna) och kvalificeringen.
Ett stoppat recept eller en avvisning ger exit-kod 1. Verktyget godkänner inte
provlagning, allergener eller näring; innehållsgranskningen gäller som förut.

För den granskade 800-leveransen används separata källfiler och review-kvitton
under `backend/app/data/recipes/reviewed-800-20261025`. Kör vanlig
`author -> validate -> diff -> import -> prepare` per korrigerat paket.
Importera den sparade standardiserade filen igen för idempotenskontroll;
författarkommandots granskningsdatum är kördagens datum. Källoriginalen
under `incoming` ska aldrig skrivas över.
