# Flexibla receptfamiljer

Steg 4 använder den befintliga receptregistreringen och planeraren. En familj
beskriver ett grundrecept, godkända råvarubyten och uttryckliga mängdkombinationer.
`meal_library_cli expand` bygger vanliga, fullständiga receptposter. Efter import
prissätts och kvalificeras dessa av samma kod som övriga recept. Ingen separat
pris-, närings- eller substitutionsmotor körs vid användarens beställning.

## Författning och granskning

Se `backend/app/data/recipes/flexible-families-v1.json` för tre kompletta exempel
med grönsaksbyte, byte av proteinkälla/tillbehör och alternativa mängder.
Formatet `smako-flexible-meal-pack-v1` innehåller:

- `pack_id` och `families`.
- Varje familj har `base`: ett komplett, förseglat grundrecept från den vanliga
  valideringen, samt `version` för de nya varianterna. `include_base: true`
  inkluderar också grundreceptet i det byggda paketet, för ett nytt recept.
- `quantity_ranges` anger granskade `minimum`, `maximum` och `step` per exakt
  `kanoniskt namn|form`. Mängderna gäller grundreceptets portionsantal och enhet.
  Ett nytt intervall ändrar aldrig en redan utfärdad grundversion.
- Varje variant har ett stabilt `variant_id`, namn, `quantities` och/eller
  `substitutions`. Ett byte anger den gamla ingrediensnyckeln och en fullständig
  ny ingrediens med form, enhet, mängd, intervall, komponent och produktkrav.
  Samma ingrediens får inte både bytas och mängdjusteras i samma variant.
- Varje variant har fullständiga `components`, `steps`, `cooking` och `review`.
  Komponentmängderna måste summera till inköpsbehovet. Alla ingredienser måste
  användas i stegplanen. Primär ingrediens, tillbehör, metod, utrustning, kosttyp
  och uppskattad tid anges uttryckligen; de ärvs inte blint efter ett råvarubyte.

Granska också instruktionernas språk och faktisk tillagningsmetod. Maskinkontrollen
kan kontrollera nycklar, mängder, beroenden och tid men kan inte bevisa att en
instruktion smakar bra eller är rätt för råvaran. Fysisk provlagning är inte gjord
för det första paketet. Inga näringsvärden eller köpbarhet godkänns av författaren.

Ett intervall är en gräns vid författning, inte rätt att ändra en sparad meny.
Endast de uttryckligen listade kombinationerna registreras. Byten multipliceras
inte automatiskt med varandra, och min/max/step genererar inte en mängdmatris.
Flera förändringar som ska användas tillsammans måste ha en egen granskad
variant med sammanhängande steg och komponenter.

## Arbetsflöde för nya och befintliga recept

Kör från projektroten med Python 3.12 och `PYTHONPATH=backend;.` på Windows.

```powershell
.venv\Scripts\python.exe -m app.services.meal_library_cli expand backend/app/data/recipes/flexible-families-v1.json --output .local/flexible-recipes/expanded.json
.venv\Scripts\python.exe -m app.services.meal_library_cli validate .local/flexible-recipes/expanded.json --output .local/flexible-recipes/validation.json
.venv\Scripts\python.exe -m app.services.meal_library_cli diff .local/flexible-recipes/expanded.json --output .local/flexible-recipes/diff.json
.venv\Scripts\python.exe -m app.services.meal_library_cli import .local/flexible-recipes/expanded.json --output .local/flexible-recipes/import.json
```

Importen ovan ändrar det lokala biblioteket. Den aktiverar inte betan. Kör sedan
befintliga `prepare`, `qualify` och testmatrisen med ett explicit prisunderlag
och klockslag. `qualify --protein 40 --allow-nutrition-estimates` använder
befintlig näringskontroll; ett avslag är inget skäl att sänka användarkravet.

För ett helt nytt grundrecept används samma vanliga innehållsvalidering först.
Lägg det validerade receptet i en ny familj och sätt `include_base: true`.
Inga Pythonlistor över grundrecept, ingredienser eller variant-ID:n behöver ändras.
Ändra `version` när en utfärdad variant ändras. Samma ID/version med nytt innehåll
avvisas som konflikt; äldre utfärdade planer förblir läsbara och validerbara.
Återkallelse görs med befintligt `revoke` för varje berörd variantidentitet.

## Planering och bibliotekstillväxt

Varianter delar `base_id` med grundreceptet, så befintlig upprepningskontroll
behandlar dem som samma grundrätt. Valet `adaptation=products` avför varianter
för samtliga måltidstyper. Allergier, kost, näring, portionsvikt och exakta
produktkrav prövas på variantens faktiska ingredienser. Grundreceptets värden
återanvänds inte som variantens näring eller tillagade vikt.

Biblioteksmanifest, exakt receptinnehåll och befintliga kod-/källsignaturer styr
förberedelsecacherna. Nya ingredienser följer automatiskt med i sökförberedelsen;
ändrade mängder och steg får separata beräkningsnycklar. Tidigare bibliotekets
giltiga lösning jämförs fortfarande av den befintliga planeraren.

Formatet tillåter högst 16 varianter per familj, 256 familjer och 4 096 utökade
recept per paket, inom befintlig filgräns. Fel stoppar hela expansionen före
publicering. Detta begränsar expansionen, men fler relevanta varianter innebär
fortfarande fler recept- och korgkontroller. Utöka efter konkreta täckningsluckor
och mät pris, kravuppfyllelse och tid med befintlig acceptansmatris. Denna etapp
bevisar inte globalt lägsta pris eller svarstid för ett godtyckligt stort bibliotek.
