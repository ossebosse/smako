# Mottagning och importgranskning av receptcheckpoint 72

2026-11-01. **72 grundrätter / 199 varianter är mottagna som fullständiga
utkast. Inget är importerat eller aktiverat.** 50 varianter passerar Smakos
ordinarie strukturkontroll; 149 stoppas av saknade ingrediensidentiteter.
Strukturresultatet räcker inte för att publicera recepten med rätt insatser.

## Underlag och verifiering

Granskad kod: `c49f1a23ae3c950c0484d9528c63bf1d56f749e3`.
Bibliotekssignatur före/efter:
`68a142625914bdeae7d03d1d41d76f7a440ae2ab1239d2f31e2e4ebc435f3516`.
Aktuellt bibliotek: 934 grundrätter / 2 462 varianter; historiska identifierare
ingick i kollisionskontrollen. Ingen appkod, ingrediensregel eller
runtime-manifest har ändrats i denna mottagning.

Originalen och ZIP-inventeringen finns i
[mottagningsjournalen](../../../backend/app/data/recipes/incoming/authoring-1000-20261101/checkpoint-72/README.md).
ZIP-filen är 10 864 875 byte med SHA-256
`82bd9cb881182c3e80062c6a08a36a75f6d1fe7f2bc0202ccbb44889cde93053`.
Alla 42 medlemsfiler har kontrollerad sökväg, storlek, CRC och hash. JSON-filer
har lästs med spärr mot dubbla objektnycklar. De fyra föregående rapporterna
är identiska; de sex receptpaketen matchar rapporternas deklarerade hashvärden.
De medföljande Pythonprogrammen har inte körts.

[NATIVE-AUDIT.json](NATIVE-AUDIT.json) kommer från befintliga
`scripts/recipe_layer/audit_authoring_delivery.py`. Okända råvaror tillfördes
inte ett fabricerat vokabulär för att få kontrollen att passera.
[VALIDATION.json](VALIDATION.json) redovisar kompletterande kontroller:

- Alla 199 poster passerar JSON-schemat från det ursprungliga författarunderlaget.
  Detta är ett kompletterande strukturschema, inte Smakos native-validator.
- Ingrediensräkning, 1 401 steg, beroenden, aktiv tid, kritisk väg, total tid
  och väntan har räknats om från recepten och stämmer med leveransrapporten.
  Det är tidsaritmetik, inte uppmätta tillagningstider.
- Alla 72 familjer har förväntade variant-ID:n och rätt portionsantal;
  middag 4, frukost/mellanmål 1. Inga ID-krockar finns mot aktuell eller
  historisk utgivning. Kandidatregistret innehåller exakt dessa författade baser.
- 50 varianter klarar `standardize`, `validate_pack_bytes`, `pack_diff`
  utan konflikt och lokal `prepare_content`. Portionsskalning till 1, 4 och
  12 klarar strukturell kontroll: 150 skalade poster. Det tillfälliga
  native-paketet är endast ett lokalt prov och har inte importerats.
- 49 av dessa varianter hör till 20 kompletta baser i paket 001/006.
  `smako-italian-pizzoccheri:1.0.0:simple` är den femtionde; syskonvarianterna
  är registerblockerade. Hela familjen ligger kvar som utkast.

## Konkreta fynd före import

### 1. Bevara de avsedda ingredienserna genom normaliseringen

Leveransen har **63 okända bokstavliga namn/form-identiteter**, fördelade
över 52 baser/149 varianter. Den befintliga auditens kanoniska antal är **62**:

- `evaporerad mjölk|as_sold` normaliseras till `mjölk|as_sold`, vars befintliga
  standardenhet är ml. Carlota använder en annan mjölkprodukt i gram. Vanlig
  mjölk får inte godtas som samma ingrediens. Båda Carlota-varianterna är
  fortfarande blockerade av andra okända insatser; ingen har släppts igenom.
- `bruna bönor|dry` normaliseras till `bönor|dry`, som också är okänd.
  Alla tre varianter av bruna bönor med fläsk behöver bevara den specifika
  bönidentiteten. Ett generiskt bönregister löser inte sakgranskningen.

Åtgärd i Smako: granska exakta identiteter, former, enheter och produktkrav
innan dessa förslag får användas. Ändra inte originalrecepten till närliggande
råvarunamn enbart för att passera valideringen.

### 2. Kända identiteter kan innebära frysta insatser

**15 av de 50 tekniskt kompatibla varianterna** ärver `frozen_edible`-krav
från `intake-all-20261026.json`. Det gäller avokado, koriander, mango, ananas
och lingon. Exakta varianter och krav finns i valideringskvittot.

Innehållsläsningen visar bland annat:

- Salpicón standard/extended och samtliga enfrijoladas skär/serverar avokado
  utan ett uttryckligt upptiningsmoment för den insats som kraven anger.
- Tub tim krob extended tärnar mango direkt till kall servering.
- Ma hor skär ananas till plana munsbitar, vilket behöver stämma med den
  faktiskt godtagna produktens bitform, upptining och hantering av saft.
- Äggakaka har 20 minuters vila med ”lingonen tina vid behov”, men behöver
  ett tydligt slutvillkor för helt tinade bär och väntetid som passar insatsen.
- Sabudana vada extended använder koriander i kall dipp. Cafreal använder
  koriander i en senare upphettad pasta; den ska bedömas efter sin egen metod,
  inte automatiskt få samma upptiningstid som kalla tillbehör.

Åtgärd: bind till rätt granskad insatsform och korrigera beredning/beroenden
och tidsuppgifter tillsammans. Färsk hel frukt får inte ersätta en fryst
ätlig mängd utan separat produkt-/mängdunderlag. Fryst är inte i sig ett fel.

### 3. Processolja och andra insatser som inte äts helt

Sabudana vada listar **150 ml rapsolja per mellanmålsportion** och pa tong ko
**350 ml per frukostportion**. Alla fyra varianterna är tekniskt kompatibla,
men texterna anger att oljan är processbad och att maten ska rinna av.
Ingen fördelning mellan inköp, kvarvarande olja och konsumerad mängd finns
i utkasten. En anteckning i `notes` ändrar inte mängd-/näringsmodellen.

Författaren har flaggat totalt 18 varianter för särskild process-/utbytesgranskning,
inklusive andra rätter med skal, ben, blad eller lag. Den flaggan är inte ett
uttömmande bevis för att övriga recept saknar sådana frågor.

Åtgärd: håll berörda varianter utanför import tills befintlig beredningsväg
kan representera faktiska insatser och utfall, eller en matmässigt granskad
receptversion med annan metod finns. Anta inte en oljeupptagsprocent och
räkna inte hela badet som konsumerad olja.

### 4. Produktens funktion och råvarans form behöver stämma

Panfortes två varianter vill strimla och kandera apelsinskal. Det ärvda kravet
`pack:intake_all_501512903e2c` definierar däremot **finrivet yttre skal utan
det vita**. Det behöver en avsiktlig granskning, inte bara ett känt namn.
Risflingor till chivda, sötad kondenserad mjölk till pan de elote och lämplig
tapiokapärlstyp är ytterligare konkreta produktfunktioner att kontrollera.

Flera ärvda krav har `definition_only`. Det betyder att en kulinarisk
definition finns; faktisk kvalificering sker fortfarande genom befintliga
granskade länkar/deklarationer och mängdresolver. Den etiketten bevisar
varken köpbarhet eller avsaknad av köpbara produkter i dagens underlag.

### 5. Nyhet och klassisk identitet är fortfarande granskningsfrågor

Samtliga 50 tekniskt kompatibla varianters mängder och steg har lästs här.
Författarens jämförelser har granskats översiktligt och flera närliggande
recepttexter har lästs ur biblioteket. Det är **inte** en färdig oberoende
kulinarisk dubblettgranskning av alla 72 baser eller verifiering av de 81
källposterna. Nya ID:n och maskinpoäng bevisar inte tillräcklig kulinarisk skillnad.

Behåll de 7 öppna kandidatfallen och 5 avvisade utanför utgivningen.
Varianternas anpassningar ska vara synliga; inga ersättningar får göras
till ”autentiska” råvarualias. Inga rätter är provlagade i denna granskning.

## Prioriterad fortsättning

1. Rätta insatsform/beredning i den kompatibla delmängden och slutför
   innehålls-/nyhetsgranskningen. Gör ändringar i separata granskade utkast,
   med spårning till originalfil/variant; skriv inte över leveransoriginalen.
2. Granska nya identiteter efter marginalnytta och befintligt produktunderlag.
   Olivolja berör 43 varianter, fisksås/fläskkarré/makrutlimeblad 12 vardera,
   parmesan/schalottenlök/ättiksprit 10 vardera. Talen överlappar och avser
   receptberoenden, inte popularitet, nya köpbara varor eller upplåsta hela recept.
   Använd senaste täckningsunderlaget enligt [arbetsgången](../../recipes/REQUESTING-RECIPES.md).
3. Kör ordinarie validering/diff/import/förberedelse först för en uttryckligen
   sakgranskad delmängd och mät sedan produktstöd och hela inköpskorgar i samma
   deklarerade referens. Bevara alla 2 200 ursprungsreferenser.
4. Fortsätt författarbeställningen från **007**. Resterande 928 baser/2 551
   varianter är skillnaden mot mottagna utkast; antalet slutligt godkända nya
   baser är ännu inte fastställt. Nästa förfrågan måste inkludera denna
   checkpoint i dubblettunderlaget och fortsatt ingrediensprioritering.

[Återkoppling till Chat](../../recipes/requests/20261101/ATGARDER-CHECKPOINT-72-TILL-CHAT.txt)
är förberedd och inte skickad. Beta och det publicerade receptbiblioteket
är oförändrade av denna mottagning.
