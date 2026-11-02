# Beställa fler recept till Smako

Bestående arbetsgång för en agent som får en begäran om instruktioner till
Chat eller annat receptförfattande. Ägarens förtydliganden 2026-11-01 ligger
till grund för detta dokument. Läs också [produktmålet](../PRODUCT-GOAL.md),
[täckningsöverblicken](../COVERAGE-OVERVIEW.md) och [författarformatet](AUTHORING.md).

## Senaste läge: fem leveranser mottagna 2026-11-01

**189 grundrätter / 501 varianter** är faktiskt mottagna, inklusive senaste
ZIP med 24/62. Fördelningen är 123 middagar, 17 frukostar och 49 mellanmål.
Nästa nyskrivna paket är **022**. Mot beställningen återstår **811
grundrätter / 2 249 varianter**: 627 middagar, 108 frukostar och 76 mellanmål.

Biblioteket är nu **1 072 baser / 2 822 varianter**. Från denna beställning
är 360 varianter importerade i 138 baser (135 hela familjer, tre delvis).
141 varianter återstår med dokumenterade hinder. Både importerade och alla
kvarvarande mottagna utkast ska ingå i nästa dubblettunderlag. Se
[senaste rapporten och kön](../reviews/recipe-unblock-round2-20261101/REPORT.md).
Den nya mängd-/processhanteringen gör inte okänd näring eller saknat
produktstöd godkänt. Fortsätt enligt ägarens preferenser nedan.

Vid nästa mindre ZIP: komplettera `audit_expansion_queue.py` med
`scripts/recipe_layer/screen_pending_recipe_inputs.py` på den nya kön och
det deklarerade frysta produkt-/faktaunderlaget. Dess `ranked_combined_blocks`
visar även produktbrister bakom ett registerfel. En löst känd ingrediens
är fortfarande varken ett godkänt recept eller en verifierad hel korg.
Se körkommando och resultat i senaste rapporten.

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

**Historisk importstatus före femte leveransen 2026-11-01:** 41 av de 165 mottagna grundrätterna,
108 av 439 varianter, är nu granskade och importerade som nya versioner.
Biblioteket har 975 baser / 2 570 varianter. De nedanstående mottagnings- och
tidsrapporterna beskriver tidigare steg före importen. Ingen betaaktivering
har gjorts i hinderarbetet. Utgå från [åtgärdsrapporten](../reviews/recipe-unblock-20261101/REPORT.md),
[hela variantkön](../reviews/recipe-unblock-20261101/queue.json) och
[ingredienshindren i prioritetsordning](../reviews/recipe-unblock-20261101/ingredient-blockers.json).
Ta med både originalutkast och granskade efterföljare i dubblettunderlaget;
de är samma grundrätter och ska inte räknas två gånger.

**2026-11-01: instruktioner skickade till Chat enligt ägaren.** Beställningen
är 1 000 nya grundrätter: 750 middagar, 125 frukostar och 125 mellanmål.
Tre varianter per middag och två per frukost/mellanmål ger 2 750 variantposter.
**Komplett mottagning senare 2026-11-01:** ZIP-filen kompletterar de fyra
tidigare rapportbilagorna med alla sex receptpaketen och stödregister.
72 grundrätter / 199 varianter är mottagna: 55 middagar, 3 frukostar och
14 mellanmål. Se [aktuell mottagningsjournal](../../backend/app/data/recipes/incoming/authoring-1000-20261101/checkpoint-72/README.md)
och [importgranskning](../reviews/recipe-checkpoint-72-20261101/REPORT.md).
50 varianter passerar native strukturkontroll; 149 har registerhinder.
63 föreslagna namn/form-identiteter behöver sakgranskning, inklusive två
olämpliga normaliseringar. Beredning av frysta insatser, processolja och
råvaruformer behöver också hanteras före import. Inga recept från denna
beställning var då importerade eller betaaktiverade.

[Isolerad varm tidsjämförelse](../reviews/recipe-checkpoint-72-timing-20261101/REPORT.md):
2 462 → 2 512 varianter gav en middag 21,236 → 21,612 s och tre middagar
49,028 → 49,028 s. Detta gäller de 50 tekniskt testbara utkasten och de
deklarerade valen, inte hela leveransen eller 1 000 nya grundrätter.
Mätningen ändrar inte importstatus eller kvarstående innehållskrav.

**Tre fortsättningar mottagna senare 2026-11-01:** ytterligare 93 grundrätter /
240 varianter (22/54, 41/108 och 30/78). Totalt faktiskt mottaget är nu
**165 grundrätts-ID:n / 439 variant-ID:n**: 109 middagar, 13 frukostar,
43 mellanmål. De nya filerna har 48 native-kompatibla och 192 ingrediens-
blockerade varianter. Innehållshinder kvarstår även i den kompatibla gruppen.
Se [samlad mottagning och granskning](../reviews/recipe-continuations-20261101/REPORT.md).
Vid den mottagningskontrollen gjordes ingen import eller betaaktivering.

**Ägarens rättelse 2026-11-01:** det finns inget separat 72/194-arkiv.
Hänvisningarna till det i författarens rapporter är felaktiga och ska inte
utlösa fler efterfrågningar eller hindra importarbete. Räkna endast faktiskt
mottagna receptfiler (nu 189/501), inte de 70/190 refererade extra ID:na.
Nya ZIP-leveranser kommer löpande med cirka 10–40 grundrätter åt gången.
Varje leverans ska bytebevaras och räknas efter sitt faktiska innehåll;
kontrollera ID, innehåll och koncept mot biblioteket och alla mottagna utkast.
Rapporterade krockar mot det obefintliga arkivet är obestyrkta, inte bevisade
dubbletter. Verkliga ID-krockar ska fortfarande utredas utan överskrivning.

Ägaren har nu gett uppdraget att åtgärda hindren och släppa in godkända recept,
med de hinder som blockerar flest varianter först. Skilj löst registerhinder,
verifierat produktstöd, granskad receptberedning och importerad hel familj.
Sakgranska identiteter/former och använd befintliga produkt-/beredningsvägar.

Nästa nyskrivna författarpaket är **022**; återstående mål mot faktiskt
mottagna utkast är **811 grundrätter / 2 249 varianter**, fördelat på
627 middagar, 108 frukostar och 76 mellanmål. Detta är inte en slutlig
nyhetsbedömning av de 189 baserna. Bevara deras ID:n, räkna inte pilotpaketet
igen och ta med alla mottagna recept i nästa dubblettunderlag även före import.
Författarens referenser till obefintliga äldre leveranser är inte mottagna recept.
[Återkoppling på checkpointen](requests/20261101/ATGARDER-CHECKPOINT-72-TILL-CHAT.txt)
är förberedd, inte skickad. Ingrediensprioriteringens tidigare tillägg är också
framtaget; det är fortfarande inte uttryckligen bekräftat att ägaren skickat det.

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

Ingrediensregistrets `unit_options` visar separat granskade enheter med
respektive produktkrav, exempelvis gram och ml filmjölk. Det är inga
omräkningsfaktorer; välj en enhet och författa dess mängd uttryckligen.
Receptdetaljerna inkluderar också beredningsversion och okända
processförluster, så att dessa villkor följer med i författarunderlaget.

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
