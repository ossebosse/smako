# Resultat: hela inköp och tydligare veckovariation

Slutlig lokal runtime `82de80e1ae898e2ab005c16c8d95e6670898be93` på gren `feature/package-variation-20261005`. Ingen produktionsaktivering eller Git-push har gjorts. Betan, reläerna, insamlingsscheman, kommunomfattning, femkällorspolicy, färskhetsgränser och befintliga användardata har lämnats orörda.

De maskinläsbara skillnaderna per led, inklusive faktiskt bortfall och tillkomst av produkter, finns i [COMPARISON.json](COMPARISON.json).

**Alla belopp nedan är berikad historisk replay**, med exakt samma frysta prisartefakt från 4 oktober och faktiska separata faktatider. Det är inte en aktuell prisoffert. [BASELINE.md](BASELINE.md) låser begäran, prisfilen, de 2 233 verifierade råfilerna och jämförelseleden. Fullständiga receptmängder, butiker/kanaler och inköpsrader finns i [MENU.md](MENU.md) och [MENUS.json](MENUS.json).

## Mätbar effekt

| Led | Fast meny: hela inköpet / använd mängd | Fri meny: hela inköpet / använd mängd | Köksfördelning i fri meny |
| --- | ---: | ---: | --- |
| R0: föregående kod och fakta | 747,77 / 494,93 kr | 747,77 / 494,93 kr | indiskt 4, mexikanskt 1 |
| R1: ny kod, samma fakta | 747,77 / 494,93 kr | 747,77 / 494,93 kr | indiskt 4, mexikanskt 1 |
| R2: R1 + tidsstämplad ärtdeklaration | 741,15 / 495,13 kr | 741,15 / 495,13 kr | indiskt 4, mexikanskt 1 |
| R3: minst tre kök, högst två middagar per huvudprotein | annan meny | 787,56 / 554,33 kr | indiskt 3, italienskt 1, mexikanskt 1 |
| R3: minst en middag från vart och ett av fem kök | annan meny | 910,39 / 575,93 kr | ett vardera: grekiskt, indiskt, italienskt, mexikanskt, thailändskt |

R0–R2 har identiska recept-ID:n, versioner, portioner och ingrediensmängder både i det fasta provet och i den fritt omvalda veckomenyn. **Samma mat blir 6,62 kr billigare att köpa först i R2**, genom att två 600 g-påsar ärtor från Coop (41,54 kr) byts mot en identifierad 1 kg-påse från Willys (34,92 kr). Veckobehovet är 640 g. Användningskostnaden ökar 0,20 kr; betalning och använd mängd är skilda mått, och återstående ärtor har inget avdraget framtida värde. Coop Online Syd i `online_fulfillment` går från 536,55 till 495,01 kr och Willys Lund i `online_store` från 211,22 till 246,14 kr. Båda ligger redan inom butikstaket.

Det nya ärtfaktumet har öppnat ett **verkligt produkt- och korgalternativ**, med egen näring och godkänd slutlig receptnäring. Ingen ytterligare hel receptversion har därför räknats som räddad utan ett separat fullständigt kvalificeringsprov. [RESEARCH.md](RESEARCH.md) anger exakt identitetskedja, källa, hämtningstid och hash. [CANDIDATES.json](CANDIDATES.json) ger maskinläsbara kandidatbeslut.

Näringsfördelningen följer det nya produktvalet: de två ärträtterna går från 31,589 till 31,909 respektive 31,2745 till 31,5945 g protein per portion före visningsavrundning; de tre andra rätterna är oförändrade i protein. Samtliga fem ligger fortfarande över 30 g. Den slutliga kontrollen görs på orundade värden.

Paprikapulver 37 g för 25,50 kr finns i samma frysta Coop-snapshot som den valda 200 g-förpackningen för 74,50 kr. Den mindre har egen makrodeklaration men inget belagt variantbundet mildhetsbesked. Den stoppas före helkorgsjämförelse; 200 g-variantens källbundna mildhet har inte lånats. De andra frysta 70/100 g-raderna saknar full kvalificering. Detta förklarar varför hög restandel på 186 g inte i sig bevisar en giltig besparing. Tofu, kikärtor och spenat har också granskats efter utlägg och restmängd; se [CANDIDATES.json](CANDIDATES.json). Den utökade kandidatrangordningen gav ingen ytterligare säker R1-sänkning.

## Uttryckliga variationsval

Formulären för publikt och personligt flöde har nu tre tydliga lägen: fritt ur tillåtna kök (standard för gamla anrop), minst angivet antal kök, eller minst en rätt ur varje valt kök. Ett frivilligt tak räknar middagar per verklig huvudproteinkälla. ”Mer omväxling” visar minst tre kök och högst två middagar per huvudprotein innan användaren startar. Billigast, Balanserad och Varierad behåller sin ekonomiska betydelse. Ogiltiga kombinationer stoppas före dyr sökning.

R3 med minst tre kök kostar **46,41 kr mer** än fritt R2. Den har fem olika grundrätter, tre kök och huvudproteiner tofu 2, linser 2, kyckling 1, bönor 1, keso 1 och ost 1; blandrätter räknas i varje verklig källa men bara som en middag. Femkökfallet kostar **169,24 kr mer** än fritt R2. Dessa prisskillnader avser andra maträtter och är inte besparing eller merpris för samma mat. Metadata visar bredare fördelning, inte provlagad kvalitet eller bättre smak. [CLASSIFICATION.md](CLASSIFICATION.md) versionsbinder regeln och skiljer huvudprotein, grundrätt, rättfamilj och tillagningssätt.

Alla redovisade veckor har giltig uppskattad köpstatus, separat uppskattad näringsstatus över 30 g protein per portion, allergenstatus `NOT_REQUESTED` och godkänd oberoende checkout/audit. Sökningen är begränsad; inget globalt prisoptimum påstås. R0/R1/R2 fri sökning registrerade sex näringssökningar och 2 404 beskurna veckoförslag; R3 minst tre kök 2 118, R3 varje kök 1 356. En giltig lösning finns i båda R3-fallen. [MENUS.json](MENUS.json) behåller full sökbudget och separata statusar.

## Kod och integration

Den befintliga `PersonalPlanner`-, `PriceUniverse`-, korg-, köpterms-, närings- och auditvägen används även för de nya valen. Behoven samordnas för veckan före heltalsavrundning. Kandidater rangordnas nu efter offert för faktisk behovsmängd, med tidigare giltig kandidat kvar som jämförelse. Egna produktfakta följer varje alternativ. Köptermer som medlemskap, kampanjperiod, gruppköp, begränsningar, pant, tillgänglighet, butik och kanal prövas av samma checkout. Ingen gammal prisrad eller faktakoppling har importerats från en annan snapshot.

Hårda variationsvillkor kontrolleras för hela veckan vid planering, sparning, receptbyte och uttrycklig omräkning. Gamla requests får inga nya krav. Cacheidentiteten omfattar den versionsbundna klassificeringen och det befintliga pris-/fakta-/recept-/villkorsunderlaget; kampanjgiltighet och ägarisolering kvarstår. Teknikspår stannar i diagnostik medan resultatet visar svensk sammanfattning av faktiskt valda kök och huvudproteiner.

Slutimagen läste även 11 äldre testplanrevisioner från en kopia av föregående runtimes isolerade lagring: varje ägarbunden GET och tidigare SHA-256 för sparad kärndata stämde, utan att gamla begäranden fick nya variationsfält. Det motsatta binärbytet, äldre image mot nya variationsplaner, är inte kvalificerat. [OLD-PLAN-READBACK.json](OLD-PLAN-READBACK.json) anger resultaten utan privata sessionstoken.

## Väntetid och öppna punkter

På samma två CPU/3 GiB som föregående kandidat gav tre slutliga R2-prover kall process **80,92 s i median** (80,72–81,83), mot R0 79,25 s. Tre varma nyberäkningar gav **54,49 s i median** (52,95–54,55), mot R0 54,80 s. Kallprocessen är alltså något långsammare, varm nyberäkning ungefär oförändrad. Högsta uppmätta RSS i de sex R2-körningarna var 2 186 776 KiB. [PERFORMANCE.json](PERFORMANCE.json) innehåller varje körning, CPU-tid, minne och deltid. Kall process, varm nyberäkning, klick till resultat och kötid är olika mått.

Målet under 60 sekunder från klick är inte uppnått i de två inledande slutliga mobilproven: Chromium **70,72 s**, WebKit **61,56 s**. Slutlig webbrese- och samtidighetslogg redovisas i [TESTS.md](TESTS.md).

Tre samtidiga ägare fick 0,00, 59,75 och 120,87 s serverkötid. En separat fullständig omkörning passerade dubbelstart, ägarisolering och återläsning; det första försöket tappade en klientanslutning under statuspollning och bevaras därför som anmärkning i [CONCURRENCY.json](CONCURRENCY.json). Högsta serverrapporterade RSS i omkörningen var 2 662 308 KiB inom 3 GiB.

**Kvar:** säkert sammansatta köp av *olika* förpackningsstorlekar i samma ingrediensrad har inte införts i denna kandidat; motorn jämför hela köp av varje kvalificerad förpackningsstorlek och heltalsantal, men gör ännu ingen generell blandstorleksoptimering. Paprika 37 g behöver exakt mildhetsbevis; billigare kikärtor behöver avrunnen mängd/näringsbasis eller annan oberoende kvalificering. Tidigare prioriterade luckor för chiliflingor, majs, rökt paprika, pita, mjölk och ägg återstår. Fortsatt prestandaarbete behövs för 60-sekundersmålet, och begränsad sökning ger inget globalt optimalitetsbevis.

Paket- och imageidentitet samt separat app-only-anvisning finns i [ACTIVATION.md](ACTIVATION.md). Ingen installation har gjorts.
