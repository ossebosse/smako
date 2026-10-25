# Smakos produktmål

Ägarens förtydligande 2026-10-25. Detta är den bestående målbilden för nya
uppdrag. Läs också [planeringsarkitekturen](PLANNING-ARCHITECTURE.md) och
aktuellt uppdrag i [HANDOFF](HANDOFF.md). Dokumentet beskriver mål, inte ett
påstående om att nuvarande implementation redan uppfyller dem.

## Användarens flöde

1. I **Mina val** anger användaren sin plats och väljer vilka butiker som
   får ingå i prisunderlaget, manuellt eller inom en vald radie. Befintligt
   kommunval kan fortsatt användas. Inga butiker utanför det valet tillkommer
   tyst, och saknat underlag för en vald butik ska redovisas.
2. Användaren väljer hur många av dessa butiker inköpen får fördelas över:
   från en butik upp till **alla valda butiker**. Detta är ett tak, inte ett
   krav på att besöka alla. Inköpslistan grupperas på de butiker som faktiskt
   används. Det nuvarande UI-taket tre är en begränsning att avlägsna, inte
   ett produktkrav. Pris-/butikskontexternas exakta identiteter ska bevaras.
3. Användaren väljer antal rätter/måltidstillfällen och antal portioner.
   Middag, valfri frukost och valfria mellanmål har egna inställningar.
4. Standardvärden gäller tills användaren ändrar dem. Förfiningarna nedan
   ska kunna kombineras, inte bara fungera var för sig.
5. Smako väljer recept och en gemensam inköpskorg med lägsta möjliga faktiska
   inköpskostnad inom de valda butikerna och alla gällande krav. Resultatet
   är kompletta recept och en sparad, användbar inköpslista per inköpsställe.

## Val som tillhör produkten

Följande omfattning kommer från ägarens beskrivning och sex UI-bilder
2026-10-25 samt de befintliga kontrakten. Den får inte begränsas till en
enkel standardprofil för att prestandamålet ska se uppnått ut.

| Område | Val och betydelse |
| --- | --- |
| Måltider | Antal tillfällen och portioner per måltidstyp; middag samt valfri frukost/mellanmål |
| Kost och fördelning | Kött, kyckling, vegetariskt, fisk; befintliga kostval, inklusive veganskt; möjlighet att utesluta fisk |
| Portions-/näringsgränser | Portionsvikt och valbara gränser för protein, kolhydrater, fett och kalorier, i UI:ts enheter och på rätt portionsnivå |
| Receptens omfattning | Minst/högst ingredienser, högst aktiv tillagningstid, total tid och väntetid; högst tillfällen med samma grundrätt |
| Matkök | Grekiskt, italienskt, mexikanskt, indiskt, thailändskt och svenskt; inget valt betyder alla; fri fördelning eller angivet variationskrav |
| Veckovariation | Minsta antal olika matkök/en rätt från varje valt matkök enligt befintliga val; högst middagar per huvudsaklig proteinkälla; blandrätter följer befintlig klassificering |
| Smak | Gillar/föredrar och ogillar är mjuka önskemål enligt befintligt kontrakt; uteslutningar och allergier är hårda krav. Tolkad fritext granskas före tillämpning |
| Ekologiskt | Minsta verifierade ekologiska kostnadsandel av köpta livsmedel efter rabatt, inklusive mat-extravaror; skafferi, avgifter och icke-livsmedel ingår inte. Okänd status räknas inte som ekologisk |
| Ekologiska animalier | Möjlighet att kräva ekologiskt för alla animaliska produkter, även ägg och mejeri; okänd status får inte godkännas |
| Överskott | Vald inköpsstrategi, inklusive att minimera överskott; större förpackningar/extraköp visar faktisk extra mängd och kostnad |
| Befintliga personliga data | Skafferi, extravaror, låsta val, medlemskap och giltiga inköpsvillkor fortsätter påverka planeringen enligt sina kontrakt |

Alla tillämpade standardkrav ska gå att förstå. Ett dolt standardfilter får
inte förväxlas med ett uttryckligt användarval. `Billigast`, `Balanserad`
och `Varierad` måste ha tydlig betydelse om de exponeras; ett dyrare
variationsmål får inte tyst beskrivas som strikt lägsta pris. Ändra inte
sparade planers tidigare semantik när mål eller standarder utvecklas.

Spårbara näringsuppskattningar får användas där befintligt kontrakt och
användarval medger det, med korrekt livsmedelsform och tydlig status. Det
innebär inte att okända allergener eller ekologiska egenskaper får antas.

## Tid och skala

**Målet är en färdig receptplan och inköpslista inom 30–60 sekunder även
för nya kombinationer av tillåtna inställningar, med tusentals recept.**
Sikta på 30 sekunder; 60 sekunder är produktens övre leveransmål. Dagens
cirka 262 recept är startunderlag, inte en permanent avgränsning. Utvecklingen
ska prövas mot exempelvis 1 000 och 5 000 recept med redovisat innehåll.
Duplicerade testrecept kan mäta viss datavolym men bevisar inte verklig
variations-, täcknings- eller sökskala.

Tiden räknas från knapptryck till synliga kompletta recept och sparad,
återläsbar inköpslista: kö, serverarbete, aktuell checkout/audit, save,
transport och UI ingår. Ett mottaget jobb, en delmeny eller ett snabbt avslag
är inte en levererad plan. En varm server räcker inte som belägg: nya krav,
ny ägare och första anrop efter pris-/kampanjbyte ska också undersökas.

Förbered gemensamt underlag före användarens begäran, vid recept-, fakta-
och prisuppdatering. Mät även förberedelsens kostnad och tiden tills nytt
underlag är redo. Dölj inte väntan genom att börja klockan efter förberedelse
eller kö. En första installation ska bygga nödvändigt underlag som del av
uppstarten; eventuell användarväntan under uppstart redovisas ärligt.

Målet omfattar alla val produkten tillåter, även kombinerade närings-, eko-
och variationskrav och fler än tre butiker. Testa hela funktionernas
omfattning genom riktade gränsfall och kombinationer; återanrop av en enda
profil kvalificerar inte produkten. Redovisa maskin, bibliotek, butiksantal,
datatäckning och belastning. Ett isolerat prov bevisar ingen tidsgräns vid
godtycklig samtidighet; kapacitet och kö behöver egen verifiering.

## Pris, giltighet och ärliga begränsningar

Minimera verklig gemensam kassakostnad enligt befintlig checkout, inklusive
förpackningar och tillämpliga kampanjvillkor. Använd inte summan av
receptens jämförpriser och dra inte av ett antaget framtida värde av rester.
Tillåt inte ett prislyft eller sämre kravuppfyllelse för att klara tidsmålet.
Det finns inget ägarbeslut om en procentuell tolerans för dyrare resultat.

**Billigast möjligt är optimeringsmålet; bevisat globalt billigast är ett
separat påstående som kräver bevis.** Nuvarande sökningar bevisar inte detta
generellt. En tidsbegränsad sökning ska redovisa bästa verifierade resultat,
sökningens fullständighet och, när en giltig undre gräns finns, avstånd till
den. En jämförelse inom en shortlist bevisar inte optimum i hela biblioteket.
Målet får inte tyst omdefinieras till ”billigt nog”.

Vissa inställningar kan vara motsägande eller sakna stöd i tillgängliga
recept/produkter. Ingen algoritm kan skapa en giltig meny när den inte finns.
Skilj då bevisad omöjlighet, saknat produkt-/faktaunderlag och ofullständig
sökning. Ett korrekt besked inom tidsmålet är bra felhantering men räknas
inte som en lyckad meny i prestanda-/täckningsrapporten. Ändra aldrig krav
utan användarens uttryckliga val och fyll aldrig faktaluckor med påhitt.

Projektet är framgångsrikt när både pris/kvalitet, funktionernas täckning,
tusentals recept och användarens väntetid fungerar tillsammans. Aktivering
i drift följer fortsatt repoets separata releaseförfarande.
