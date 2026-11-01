# Beställa fler recept till Smako

Bestående arbetsgång för en agent som får en begäran om instruktioner till
Chat eller annat receptförfattande. Ägarens förtydliganden 2026-11-01 ligger
till grund för detta dokument. Läs också [produktmålet](../PRODUCT-GOAL.md),
[täckningsöverblicken](../COVERAGE-OVERVIEW.md) och [författarformatet](AUTHORING.md).

## Ägarens preferenser

- Prioritera klassiska, etablerade rätter och verklig kulinarisk bredd.
  Regionala rätter och tydligt märkta anpassningar är möjliga; inga påhittade
  klassiker eller nya köksetiketter på samma generella rätt.
- Fördela nya grundrätter så jämnt som möjligt över de sex stödda köken:
  grekiskt, italienskt, mexikanskt, indiskt, thailändskt och svenskt.
- Skapa fullständiga varianter med olika ingrediensantal under samma `base_id`.
  Räkna grundrätter och varianter separat. Ingen utfyllnad av ingredienser.
- Granska likhet både mot hela aktuella biblioteket och inom den nya
  leveransen. Namnbyte, garnering eller enkelt protein-/tillbehörsbyte ger
  inte automatiskt en ny grundrätt. Förbättringar av befintliga rätter
  redovisas separat och räknas inte som nya.
- Prioritera recept som breddar användningen av relevanta livsmedel i
  produktunderlaget som ännu saknar fungerande receptvägar. Vid likvärdiga
  förslag väger belagd efterfrågan och användning i svensk vardagsmat tungt.
  Popularitet, sortimentsbredd och faktisk köpbarhet är skilda mått.
- Föreslagen täckningsvinst ska senare mätas med ordinarie ingredienskontroll
  och fullständig checkout. Saknade fakta får inte döljas med nya alias,
  gissade mängder, falska produktkrav eller ändrad nämnare.

## Aktuell beställning och redan skickat underlag

**2026-11-01: instruktioner skickade till Chat enligt ägaren.** Beställningen
är 1 000 nya grundrätter: 750 middagar, 125 frukostar och 125 mellanmål.
Tre varianter per middag och två per frukost/mellanmål ger 2 750 variantposter.
Ingen ny leverans från denna beställning var mottagen eller importerad när
denna journal skrevs. Ägaren bad därefter om ingrediensprioritering; tillägget
är framtaget, men det är inte bekräftat att ägaren har skickat just det.

Bevarade, skickbara texter finns i
[ursprungligt uppdrag](requests/20261101/INSTRUKTIONER-TILL-CHAT.txt) och
[ingrediensprioritering](requests/20261101/TILLAGG-TILL-CHAT.txt).
Deras antal, datum, produkturval och hänvisningar till bilagor är historiska.
Skicka dem inte utan aktuella bilagor och granskning av vad som redan levererats.
De gamla ZIP-filerna i `.local` är lokala arbetsartefakter, inte en förutsättning
för en ny klon. Förfrågningens texter ska bevaras även om arbetsartefakterna saknas.

| Kök | Middag | Frukost | Mellanmål | Grundrätter |
| --- | ---: | ---: | ---: | ---: |
| greek | 125 | 21 | 21 | 167 |
| italian | 125 | 21 | 20 | 166 |
| mexican | 125 | 21 | 21 | 167 |
| indian | 125 | 21 | 21 | 167 |
| thai | 125 | 21 | 21 | 167 |
| swedish | 125 | 20 | 21 | 166 |
| Totalt | 750 | 125 | 125 | 1 000 |

750/125/125 och antalet 1 000 gäller denna beställning. Vid en senare beställning
kan samma proportioner användas som ett tydligt angivet förslag om ägaren inte
anger annat. Kontrollera först tidigare leveranser så att en fortsättning inte
misstas för en ny beställning av ytterligare samma antal.

## Ta fram nästa förfrågan

### 1. Fastställ beställning och aktuellt bibliotek

Kontrollera rot, branch och arbetsstatus enligt AGENTS. Läs senaste HANDOFF,
denna beställningsjournal och eventuella mottagningsrapporter. Skriv uttryckligen
om antalet avser grundrätter eller alla varianter. Ange måltidsfördelning,
portionsantal och en exakt kvottabell som summerar rätt. Visa rimliga antaganden
och fråga bara om något som inte går att avgöra från ägarens instruktioner.

Exportera det aktuella biblioteket genom befintliga laddare. Det återanvändbara
verktyget läser recept och granskat ingrediensvokabulär; det importerar inga
recept, hämtar inga priser och läser inga användarprofiler:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe -X utf8 scripts/recipe_layer/export_authoring_reference.py --output .local/recipe-request-YYYYMMDD/reference
```

Välj en ny utdatakatalog. Verktyget skriver grundrättsindex, samtliga aktuella
varianters ingredienser och instruktioner, reserverade ID:n även från historik,
ingrediensregister, formatexempel, källrevision och hashmanifest. Det kontrollerar
formatexemplet med `standardize` och native `validate_pack_bytes`. Resultatet
är referensmaterial, inte nya recept eller bevis på produktstöd. På Linux används
`.venv/bin/python` och `PYTHONPATH=backend:.`.

### 2. Hämta aktuell täckning

Följ [COVERAGE-OVERVIEW](../COVERAGE-OVERVIEW.md). Hitta senaste lyckade main-CI
och hämta dess **coverage-overview**-artefakt till en ny lokal katalog:

```powershell
gh run list --workflow tests.yml --branch main --status success --limit 5 --json databaseId,headSha,createdAt
gh run download RUN_ID --name coverage-overview --dir .local/recipe-request-YYYYMMDD/coverage
```

Kontrollera `overview.json`: kodrevision, `scope.manifest_sha256`, receptantal,
frysta källdatum, butiker, portioner och exact/estimated. Jämför bibliotekets
signatur med exporten. En nyare kodrevision med samma receptmanifest kräver
också bedömning av om resolver-/mängdregler ändrats sedan rapporten. Vid skillnad
ska rapportens äldre scope anges eller ordinarie analys köras om; kalla den
inte aktuell av bara datumet. Den frysta CI-referensen är inte live beta.

Läs `ingredient_coverage`, `recipe_opportunities`, `blockers`,
`all_library_blockers`, `uncovered_categories` och produkt-CSV:erna. CSV-fältet
`recipe_indexes` pekar på positioner i samma läges `recipes`-lista. Om en
kompakt bilaga skapas måste indexordningen bevaras. Bevara originalrapporten
lokalt samt dess hash/körningslänk. Ingen ny insamling behövs för denna export.

### 3. Granska och prioritera ingredienser

Skilj på:

1. Relevant råvara/form som saknar författad användning.
2. Få befintliga grundrätter trots fungerande råvarustöd.
3. Befintliga recept där produktform, identitet, mängd eller varufakta hindrar
   fler produktkandidater; lägg dessa i en teknisk granskningslista.
4. Oklassificerade träffar och varor som inte hör hemma i recept.

`not_demonstrated` betyder att stöd inte har visats. `rejected_in_tested_paths`
betyder avslag i prövade vägar. Inget av dem bevisar en receptlucka. Generiska
råvarusonder och namnträffar måste granskas mot verklig vara; exempelvis innehöll
buljongsonden fiskbullar i buljong. Samma matvara hos flera butiker räknas inte
som flera nya livsmedel. Deduplicera med kända GTIN där det är möjligt och
redovisa okända identiteter, överlapp och skillnaden mot butiksposter.

Rangordna tydliga innehållsluckor efter belagd efterfrågan, dokumenterad
sortimentsbredd, rimlig möjlighet till kvalificering och relevans för nya
klassiker inom kökskvoterna. Använd faktisk försäljnings-/konsumtionsdata när
den finns; ange källa, år, geografi, mått och kategorinivå. SCB:s försäljningsvärde
är inte köp-/ätfrekvens, och antal artikelnummer är inte popularitet. Saknad
evidens ska vara okänd; en vardagsbedömning märks uttryckligen som bedömning.

Beakta återstående nytta efter redan valda förslag: många recept med samma olja
ökar inte produkttäckningen lika många gånger. Förslaget får fortfarande
använda täckta stödingredienser. Föreslagen matchning är inte godkänd köpbarhet.

Historiska startspår 2026-11-01 var olivolja, salsiccia, bacon, buljong/fond,
färdig pesto, vissa frysta blandningar och chorizo. Dessa måste omprövas mot
nästa bibliotek och produktunderlag. De är inga permanenta luckor eller en
uppmätt popularitetslista. Se det daterade tillägget för begränsningarna.

### 4. Skriv och paketera instruktionen

Utgå från [REQUEST-TEMPLATE.txt](REQUEST-TEMPLATE.txt), fyll i alla platshållare
och använd de daterade förfrågningarna för mer detaljer om formatet.
Leverera instruktion och aktuella bilagor tillsammans, gärna som ZIP.

- Bilagor: aktuellt bibliotek/index, reserverade ID:n, ingrediensregister,
  AUTHORING och exempel, källmanifest, aktuell täckning och granskad
  ingrediensprioritering med produktreferenser och efterfrågekällor.
- Nya paket ska följa `smako-recipe-authoring-v1`. Använd inte Chat för att
  hitta på runtimehashar, godkännanden, produktfakta, priser eller näringsvärden.
- Kandidatgranskning före full författning, ett litet pilotpaket som ingår i
  totalen, därefter kompletta numrerade paket och kumulativ bokföring.
- Varje variant har egna mängder och steg. Ingrediensantal räknas på unika
  kanoniska namn/former, med salt/peppar/vatten undantagna enligt befintlig
  räknare. `variant_id` och `level` är skilda dimensioner.
- Dubblettgranska även köksöverskridande och köksneutrala befintliga rätter.
  Avvikande kvoter, saknade identiteter och osäkra likhetsfall redovisas öppet.
- Kontrollera JSON-läsbarhet, antal, kvottsummor, ID:n och ZIP-innehåll.
  Hashmanifest ska avse slutliga filer; uppdatera det om bilagorna ändras.

### 5. Lämna en spårbar överlämning

Spara det konkreta skickade uppdraget och en kort beställningsjournal under
`docs/recipes/requests/YYYYMMDD/`; länka från denna sida och HANDOFF.
Skriv beställt antal, användarens beslut, källa/revision, vad som faktiskt
skickats respektive bara förberetts samt mottaget/importerat status.
Stora genererade exportfiler och rå produktdata ligger fortsatt utanför Git.
De ska kunna återskapas med verktyget och den refererade CI-artefakten.

Vid mottagen leverans: bevara original, granska nyhet och innehåll, följ
`author -> validate -> diff -> import -> prepare` enligt AUTHORING och mät
täckningen med samma deklarerade referens. En förfrågan om instruktioner
innebär inte att recept har skapats, importerats eller aktiverats på betan.
