# Slutlig recept- och menykvalificering, 2026-10-03

**94/104 receptversioner, 47/48 grundfamiljer och 43/48 originalversioner kvalificerades på slutruntime `17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`.** Detta är den nya omkörningen efter energi- och brödrättningarna; de lika stora historiska antalen avsåg ett underlag med felaktig näring.

Exakt image: `sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`. Paket, 645 runtimehashar, pip check och offline-Chromium är verifierade i [imagebeviset](IMAGE-17A-VERIFICATION.md). Recept-/menykörningarna använde inga runtimekällmounts, avstängt nätverk, 2 CPU och 3 GiB. De kördes sekventiellt utan annan plannerlast, med samma oförändrade skript och requests som de äldre bevisen. Inga recept, produkter eller kampanjer låstes eller handpatchades.

Kvalificeringsrapportens SHA-256: `c46c148b4c2fc5d9174f314ed4024c8ba3cc4291e4cc67847acbae2eb3152a80`. Samtliga 104 versioner prövades med den vanliga PersonalPlanner-vägen mot det frysta publicerade underlaget från 2026-10-02. De sju menyerna använde vanlig MealPlanService. Exekveringsbindning, källreferenser, request och råplanshashar finns i [evidence.json](evidence.json); kompletta menyer och inköp i [MENUS.md](MENUS.md).

## Kvalificering per matkök

| Matkök | Distinkta grundrätter | Kvalificerade familjer | Original | Kvalificerade versioner / alla |
| --- | ---: | ---: | ---: | ---: |
| Grekiskt | 8 | 8 | 8 | 16 / 16 |
| Italienskt | 8 | 7 | 7 | 14 / 16 |
| Mexikanskt | 8 | 8 | 6 | 16 / 20 |
| Indiskt | 8 | 8 | 8 | 16 / 16 |
| Thailändskt | 8 | 8 | 8 | 16 / 16 |
| Svenskt | 8 | 8 | 6 | 16 / 20 |

Det oförändrade biblioteket innehåller 48 grundrecept och 56 godkända variationer, varav 23 vegetariska grundrecept. Innehållshash `1c623aa7e4a8e8f9cde292807198c59d6f191f0dd3030462a254893995e7e90c` är identisk före och efter källrättningarna. Mängder, instruktioner, portionsgrund, tidsplaner och receptversioner ändrades inte för att få provet att passera.

## Tio första faktiska stopp

Tabellen återger motorns första stopp, inte ett påstående om att alla tänkbara inköp är omöjliga. Ett tomt instrumenterat steg anges uttryckligen; felorsaken fylls inte ut med ett påhittat senare steg.

| Grundrecept / variant | Steg | Kod | Första stopp |
| --- | --- | --- | --- |
| `smako-italian-piccata` / `base` | ej separat angivet | DATA_BLOCKED | Ingen verifierad köpbar vara för kapris, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| `smako-italian-piccata` / `protein` | ej separat angivet | DATA_BLOCKED | Ingen verifierad köpbar vara för kapris, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| `smako-mexican-lentil-chili` / `base` | ej separat angivet | DATA_BLOCKED | Ingen verifierad köpbar vara för kidneybönor, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| `smako-mexican-lentil-chili` / `protein` | ej separat angivet | DATA_BLOCKED | Ingen verifierad köpbar vara för kidneybönor, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| `smako-mexican-corn-soup` / `base` | product_qualification | DATA_BLOCKED | Majs- och bönsoppa med ostquesadilla och tomatsalsa: näringsunderlag med rätt enhet saknas för mjölk (1 av 15 ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde. |
| `smako-mexican-corn-soup` / `protein` | product_qualification | DATA_BLOCKED | Majs- och bönsoppa med ostquesadilla och tomatsalsa: näringsunderlag med rätt enhet saknas för mjölk (1 av 15 ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde. |
| `smako-swedish-beef-patties` / `base` | product_qualification | DATA_BLOCKED | Pannbiff med svampsås, rostade rotfrukter och gurka: näringsunderlag med rätt enhet saknas för mjölk (1 av 14 ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde. |
| `smako-swedish-beef-patties` / `protein` | product_qualification | DATA_BLOCKED | Pannbiff med svampsås, rostade rotfrukter och gurka: näringsunderlag med rätt enhet saknas för mjölk (1 av 14 ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde. |
| `smako-swedish-green-pea-soup` / `base` | product_qualification | DATA_BLOCKED | Grön ärt- och bönsoppa med spenat och ostbröd: näringsunderlag med rätt enhet saknas för mjölk (1 av 14 ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde. |
| `smako-swedish-green-pea-soup` / `protein` | product_qualification | DATA_BLOCKED | Grön ärt- och bönsoppa med spenat och ostbröd: näringsunderlag med rätt enhet saknas för mjölk (1 av 14 ingrediensbehov). Underlaget har saknade eller konfliktfyllda värden. Detta är ett datahinder, inte ett beräknat för lågt proteinvärde. |

Piccata är den enda grundfamilj som fortfarande saknar kvalificerad variant i detta underlag. För övriga stoppade original finns redan innehållsgranskade, versionsbundna variationer med vita bönor, crème fraiche eller vattenpanad. De väljs bara när användaren tillåter godkända receptvariationer. Saknad avrunnen mängd, motstridig deklaration och gram-/milliliterunderlag omvandlas inte till gissade fakta.

## Sexton vanliga produktbyten efter källspärren

| Produktbehov | Historisk, nu spärrad produkt | Kvalificerat normalt val | Berörda receptversioner |
| --- | --- | --- | ---: |
| Nötfärs | Nötfärs 20%, GTIN `7392055078800`, 500 g / 67,50 kr; råparet 1100 kcal / 250 kJ är motstridigt | Nötfärs Naturbeteskött, GTIN `7300156583260`, produkt `a4bb1cf3d3024d7c99b4d4829be14d49`, 500 g / 86,50 kr; kvalificerad deklaration 210 kcal / 900 kJ | 12 |
| Bröd | Rostbröd, GTIN `7300156594488`, 700 g / 21,55 kr; råparet 1000 kcal / 240 kJ är motstridigt | Bröd Varsågod Skivad, Skogaholm, GTIN `7312200016945`, produkt `47655948c20c4766b308ab7e27b28cde`, 715 g / 25,51 kr; kvalificerad deklaration 270 kcal / 1150 kJ | 4 |

Färsbytet gäller bas/protein i keftedes, polpette, beef-fajita, keema och beef-broccoli samt water-panade/water-panade-protein i svenska pannbiffar. Brödbytet gäller ribollita bas/protein och grön ärtsoppa crème-fraiche/crème-fraiche-protein. Alla sexton val gjordes i den vanliga motorn. Övriga 78 kvalificerade receptkorgar behöll samma produktset som tidigare. Inget av de två spärrade produkt-ID:na finns i slutkvalificeringens eller de sju slutmenyernas näringsunderlag.

Brödformen stöds av den exakta publicerade råpostens kategori Matbröd, uttrycklig uppgift att brödet kan ätas som det är och positiv spannmålssammansättning. Marknadsnamn och GTIN ensamma ger inget undantag. Fryst, halvgräddat, obligatorisk tillagning, fyllning, smaksättning och okänd sammansättning har separata negativa prov. De ursprungliga energiuppgifterna byts aldrig plats eller räknas om till en påstådd korrigerad deklaration.

Exempel på nya beräkningar per portion: keftedes bas 793,81 kcal / 44,973 g protein; ribollita bas 712,25 kcal / 33,636 g protein; grön ärtsoppa crème-fraiche 832,29 kcal / 38,651 g protein. Alla är fortfarande märkta som näringsuppskattningar enligt den godkända beredningsmetoden.

## Sju fria menyer på slutimagen

Samtliga sju gav fem distinkta middagar för två personer, högst två inköpsställen, Balanserad och uttryckligt medgivande till uppskattade köp samt näringsuppskattningar. Blandad meny behåller dessutom kraven 10–15 ingredienser, minst 40 g protein och högst 40 minuter. De äldre priserna nedan är historik, inte giltiga näringsacceptanser eller nya prisutfästelser.

| Meny | Historiskt pris | Slutpris | Slutprov, s | Samma fem grundrätter |
| --- | ---: | ---: | ---: | --- |
| Grekiskt | 682.23 kr | 682.23 kr | 30.833 | ja |
| Italienskt | 647.98 kr | 651.94 kr | 28.674 | ja |
| Mexikanskt | 673.87 kr | 673.87 kr | 31.572 | ja |
| Indiskt | 628.95 kr | 647.95 kr | 26.306 | ja |
| Thailändskt | 638.99 kr | 638.99 kr | 30.006 | ja |
| Svenskt | 730.09 kr | 734.05 kr | 30.760 | ja |
| Grekiskt/mexikanskt 40 g/40 min | 738.17 kr | 738.17 kr | 75.997 | ja |

Tiderna är funktionella körningar i nya processer. De ersätter inte releasekandidatens separata kontrollerade kalla/varma benchmark eller samtidighetsprov. Global optimalitet är inte bevisad; redovisningen gäller hittade kvalificerade menyer inom valen.

I den blandade menyn är de orundade proteinvärdena 40,17199999999999,
43,532500000000006, 52,45450000000001, 55,489 och 41,515 g per portion.
Samtliga är minst 40 före visningsavrundning. Rätterna har 12–14 ingredienser
och uppskattade tider 35–40 minuter.

## Samordnade paket, kampanj och uppskattat köp

Den slutliga blandade menyn delar **en 1 000-g-förpackning Långkornigt Ris för
21,95 kr** mellan fyra rätters behov på `100 + 130 + 130 + 110 = 470 g`.
Risraden är `VERIFIED`, vald hos Hemköp Lund Brunnshög. Två rätters
citronjuicebehov `36 + 30 = 66 ml` delar **en 200-ml-förpackning för 8,99 kr**
hos Coop Online Syd, GTIN `7340191116641`, också `VERIFIED`. Det är verkliga
samordnade inköp i den fria veckoplanen. De 530 g ris och 134 ml juice som
återstår är planerade rester; de bokförs inte som uppmätt skafferi eller
dras av från betalningen. Full slutplan SHA-256:
`03245b3f2ffa4ea6a0697b7b905f081a5177903b7f2aab2f88411318014fbfad`.

Den grekiska menyn köper normalt vald **Kycklinglårfilé, GTIN
`7300156600080`, 1 × 450 g för 46,90 kr**, Coop Online Syd, för 340 g i
citronkycklingen. Köpet är `VERIFIED` och kampanjen är offentlig utan
medlemskrav, med deklarerad giltighet 2026-09-27–2026-10-04. Den prövas på
replayens köpdatum 2026-10-02; den presenteras inte som ett aktuellt erbjudande.
Ingen kampanjprodukt tvingades in i menyn.

Den blandade menyn använder samtidigt **Paprika Grön Klass 1** från Hemköp
Lund Brunnshög: receptbehov 200 g, ett köp med uppskattad vikt cirka 200 g
och planerat belopp 11,79 kr. Raden är `VERIFIED_WITH_ESTIMATES` och
`variable_weight=true`. Mängdosäkerheten hålls skild från den separat
medgivna näringsuppskattningen. Båda exemplen ingår i måltidernas vanliga
inköps- och näringskvalificering, inte som fristående extraköp.

## Kvalitetsnivåer hålls åtskilda

| Dimension | Slutresultat |
| --- | --- |
| Receptinnehåll | Modellstödd innehållsgranskning och maskinell strukturvalidering; **0 fysiska provlagningar** |
| Källunderlag | Motstridiga energipar spärras; vanlig brödform kräver exakt källbevis. Saknade uppgifter förblir synliga |
| Köpbarhet | 94 korgar med PASS i audit: 44 VERIFIED och 50 VERIFIED_WITH_ESTIMATES |
| Näring | 94 ESTIMATED; inga motstridiga källvärden omtolkas. Tio stoppade versioner saknar ett komplett kvalificerat resultat |
| Allergener | De 94 fullständiga resultaten anger NOT_REQUESTED; detta är inget intyg om allergensäkerhet. Negativa allergenprov redovisas separat |

Råhistoriken ligger kvar utanför Git, inklusive de äldre felgrundade resultaten och mellanliggande dd3-diagnostik. Äldre sparade användarplaner har inte skrivits om. Denna omkörning ersätter de tidigare siffrornas näringsacceptans, inte deras separata observationer av statuspollning, åtkomstisolering eller lagring.
