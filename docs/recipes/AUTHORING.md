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
  Ett steg får ta högst 24 timmar. Summerad väntetid och total tid får vara
  högst 48 timmar, så kylupptining följd av långkok kan redovisas korrekt.
  Aktiv kontroll, omrörning och överföring ska vara egna aktiva steg.
  Kortare tidsgränser som användaren väljer respekteras fortfarande.
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
`servings_multiple` kan ange ett granskat helt portionssteg, exempelvis 4
för en fylld hel kyckling som bara godkänns för 4, 8 eller 12 portioner.
Användaren får fortfarande välja andra portionsantal; då väljs andra recept.
Detta avrundar inte inköp eller tillåter automatiskt rester från en större sats.

Gamla receptversioner omtolkas inte: ändrad process kräver ny innehållsgranskad
version med eget innehållshash. Funktionen ersätter inte provlagning.

## Skalbara mängder (ägarbeslut 2026-11-24)

Nya recept anger ett granskat intervall för de råvaror som rimligen kan bli
mer eller mindre, så att Smako kan nå en måltids näringsgränser (protein,
kolhydrater, fett, energi) utan att rätten slutar vara densamma:

- `range: [minst, mest]` och valfritt `step` på ingrediensen, i samma enhet
  och för samma antal portioner som `quantity`. Standardsteg 10 g/ml eller
  1 st. Intervallet måste omsluta `quantity`, ligga mellan halva och dubbla
  mängden, och steget måste gå jämnt upp och träffa `quantity`.
- Bara rollerna `primary` (huvudråvara), `side` (tillbehör) och `vegetable`
  får skalas. Sås, smaksättning och stekfett står kvar.
- Granskningen godkänner hela intervallet: varje mängd på steget räknas som
  granskad. Skriv stegen så att de stämmer för hela intervallet, till exempel
  "stek kycklingen" i stället för "stek 300 g kyckling".
- En skalbar torr råvara (`form: dry`, till exempel ris, pasta, torra linser)
  får inte kokas i en fast vattenmängd ("N ml vatten" i ett steg som använder
  den); då stoppas receptet. Kött, fisk, tofu eller konserverade bönor får
  sjuda i en fast mängd. Recept med omätta processförluster kan inte ha intervall.
- Ägarbeslut 2026-11-25: smaksättning, marinad, sås och fett i huvudråvarans
  komponent kan följa med: `"follows": "kyckling"`. Bara mängden i den
  komponenten skalas, så salt till tillbehöret står kvar. Mjölk, grädde, mjöl
  och mannagryn ska inte följa, eftersom de håller ihop en redning, deg eller
  stanning.
- En middag utan skalbar huvudråvara får en varning.

Utan näringsgränser använder planeraren alltid `quantity`. Med gränser väljer
den mängder på stegen som når gränserna och ligger närmast receptets mängder;
priset avgör bara mellan lika nära alternativ. Äldre recept har ingen
skalning (minst = mest = mängden) och görs om i omgångar som nya versioner.

`author` sätter `design.scaling: "reviewed_ranges"` när receptet har intervall.
Bara sådana recept skalas; äldre flexibla familjer har intervall med en annan
betydelse och skalas inte. När biblioteket läses får receptet upp till fyra
skalade syskon (`<variant>-m125s100` osv., `scalable_recipes.py`): mer
huvudråvara och/eller tillbehöret på sitt minsta. De förbereds och prövas som
vanliga recept.

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


## Varje ingrediens måste gå att köpa (ägarbeslut 2026-11-20)

Ett nytt recept importeras inte förrän varje ingrediens har minst en köpbar vara
i både Lund och Malmö med dagens priser och varufakta. Byt aldrig tyst ut en
ingrediens för att den är blockerad. Gör i stället så här:

1. **Leta upp varan och se varför den är blockerad.** Kör kvalificeringen på
   servern mot de aktiva prisunderlagen (se nedan). Finns varan i butikerna men
   stoppas, rätta orsaken: saknad eller inaktuell granskad länk, ändrat namn eller
   märke, ny innehållsförteckning, kedjebunden artikel.
2. **Hittas varan inte**, nämn den för ägaren innan receptet importeras.
3. **Är det klarlagt att varan inte säljs i de stora svenska kedjorna**, föreslå
   en ersättningsingrediens för ägaren.

Kvalificeringen körs i en tillfällig container från appens image, med appens
miljö, skrivskyddade datamappar och kandidatbiblioteket monterat, så att den
körande appen inte påverkas:
`scripts/recipe_layer/qualify_candidate_library.py` (ett recept per vecka,
uppskattat inköpsläge, högst 2 butiker). Varje stoppat recept anger den
ingrediens som saknar köpbar vara.

## Språk som går att laga efter

- Skriv ett kort namn på rätten, helst högst 80 tecken. Beskriv en faktisk
  skillnad mellan varianter, till exempel ”med gurka och dill”. Använd inte
  suffix som ”enkel”, ”vardag”, ”standard” eller ”utökad”. Lägg upptining,
  produktkrav och granskningshistorik i rätt steg eller i metadata.
- Ange råvaran och handlingen: ”Smula fetaosten och finhacka dillen”, inte
  ”finhacka fasta bitar och färska örter”. Ge inga instruktioner om ingredienser
  som saknas. Yoghurt och salt ska röras ihop, inte hackas.
- Ett väntesteg ska säga vad som väntar, hur länge och hur man ser att det är
  klart. Exempel: ”Sjud linserna i 15 minuter tills de är mjuka.” Använd aldrig
  ”Låt momentet fortsätta tills den angivna tiden …” eller ett inledande
  ”Förbered och påbörja momentet”. Dela bara aktivt arbete och väntan när
  båda stegen har en egen konkret instruktion och granskad tidsuppskattning.
- Skriv ”rätten”, ”såsen” eller det faktiska tillbehöret i stället för
  ”huvudkomponenten” och ”komponentmängder”. Håll beräkningsantaganden i
  metodinformationen. Behåll praktiska anvisningar om vad som ska användas,
  hällas bort, kylas eller genomhettas i själva steget.
- Namnge råvaran även vid kontroll av tillagningen: ”kikärtorna är genomvarma
  och auberginen är mjuk”, inte ”huvudråvaran är färdig”. Hänvisa bara till
  grönsaker som faktiskt finns i steget. Skriv ”nästa steg” om ordningsföljden
  behöver förklaras, inte ”nästa aktiva steg”. Ingrediensnamn ska inte innehålla
  interna versionsanteckningar som ”ny receptdos”.
- Skriv naturlig svenska utan reklamfraser, superlativ eller påståenden om
  provlagning och autenticitet som saknar stöd. Ange anpassningar som ändrar
  rättens identitet tydligt. ”Grekiskt” kan vara en kategorietikett; receptets
  faktiska ursprung och anpassning hör hemma i innehållsgranskningen.
- Språkändringar får inte ändra mängder, råvaruformer, temperaturer,
  allergenkrav, kylkedja, processvatten eller portionsskalning. Publicera en
  ny version och bevara tidigare paket. Att en strukturkontroll går igenom
  är inte samma sak som att rätten är provlagad.

Författarverktyget varnar för vanliga mallfraser och överlånga namn.
Den tidigare automatiska uppdelningen i förberedelse och ett tomt väntesteg
är avvecklad. Den granskade språkändringen 2026-11-02 låser äldre recepts
underlag för omgångstider i `batch_scaling`, så att andra verb eller förenade
steg inte ändrar beräkningen för fler portioner.
