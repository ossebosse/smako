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
ändrade mängder och steg får separata beräkningsnycklar.

Vid vanlig nyplanering kvalificeras hela det aktuella urvalet en gång per
måltidstyp. Bibliotekets publiceringsordning används för att hitta en första
giltig meny med den befintliga begränsade veckosökningen. Billigast börjar
med grundbiblioteket; övriga lägen börjar med de två ursprungliga paketen.
Saknas en måltidstyp eller hittas ingen giltig meny prövas nästa större urval.
Återkallade eller ersatta versioner återinförs aldrig som startrecept.

Inför startsökningen begränsas stora familjer normalt till fyra varianter per
grundrecept. Alla grundrecept finns kvar. Första kvalificerade varianten, lägsta
enskilda inköpssumma, starkast överlapp med andra familjers kvalificerade produkter
och min/max för efterfrågade näringsmått skyddas. Skyddade alternativ kan höja
gränsen: högst tre plus två gånger antalet efterfrågade mått. Befintlig kulinarisk
stratifiering fyller återstående platser med stöd av exakta produktidentiteter.
Saknas jämförelseunderlag för en variant behålls hela familjen.

Detta är sökurval, inte ett billigare beräknat veckopris eller ett näringsgodkännande.
Om det begränsade urvalet inte ger en meny prövas hela samma generations urval
innan nästa generation. Alla kvalificerade varianter finns kvar i de senare
bytesstegen. Nya familjer och varianter följer samma regler utan särskilda ID:n.
Kvalificeringen av hela biblioteket och de enskilda bytesproven växer fortfarande
med antalet recept; endast startens kombinationssökning begränsas här.

När en giltig meny finns får senare pakets nya recept konkurrera genom byten
av en måltid åt gången. Högst två genomgångar per utökat urval görs, och den
andra behövs bara efter en förbättring. Hela korgen med alla måltider, tillägg
och skafferifördelning räknas för varje förslag. En dyrare meny ersätter inte
den tidigare lösningen. Vid samma pris används befintlig smak-/namnordning.
Till sist prövas högst två bytesgenomgångar med hela det kvalificerade urvalet,
så att också äldre recept kan dra nytta av de nya råvarukombinationerna.
Metoden gäller också framtida grundrecept och vanliga receptpaket, utan nya
ID-listor eller specialkod. Ett avslutande parsteg prövar högst 128 förslag från
de åtta bäst rankade alternativen per måltid i den sista bytesgenomgången.
Det fångar också en del byten som bara blir billigare tillsammans, till exempel
vid förpackningsgränser eller krav på ekoandel. Varje par kontrolleras och
prissätts som en hel meny; rankningen är ingen prisgräns eller kvalificering.
Kombinationer utanför urvalet och byten av fler måltider kan missas. Sökningen
bevisar inte globalt lägsta pris.

Recept- och produktberäkningar delar samma privata planerare. Upp till 256
exakta del-/helkorgar återanvänds mellan biblioteksförsöken, separat från den
befintliga begränsade beamcachen. Måltidsordning, dag, typ, hela receptvärdet
och slut-/delkontroll ingår i nyckeln. Inga resultat delas mellan användare,
ändrade butikstak, köpval eller andra begäranden. Slutmenyn kontrolleras alltid
på nytt. Redigeringar och egna injicerade sökare behåller sin tidigare väg.

Ekosökningen återanvänder högst 32 exakta lyckade korgar inom samma planerare.
Mängder, enheter, ordning, produkt-/erbjudandevärden, ekoegenskaper, matklassning,
butiker, butikstak och ekokrav ingår i nyckeln. Korgar med otillräcklig ekoandel
kan avvisas på den vanliga prismotorns exakta offertval innan fulla resultatmodeller
byggs. Gemensamma kampanjer behåller full checkout. Delmängdsordning, högst 256
ekoförsök, prisgränser och den oberoende slutkontrollen är oförändrade.

Formatet tillåter högst 16 varianter per familj, 256 familjer och 4 096 utökade
recept per paket, inom befintlig filgräns. Fel stoppar hela expansionen före
publicering. Detta begränsar expansionen, men fler relevanta varianter innebär
fortfarande fler recept- och korgkontroller. Utöka efter konkreta täckningsluckor
och mät pris, kravuppfyllelse och tid med befintlig acceptansmatris. Denna etapp
bevisar inte globalt lägsta pris eller svarstid för ett godtyckligt stort bibliotek.
