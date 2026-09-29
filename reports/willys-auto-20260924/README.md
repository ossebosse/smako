# Willys: automatisk kvalificering av textannonser

Den ordinarie reklambladsinsamlingen använder nu generella, konservativa textregler. Den behöver inte ett manuellt godkännande eller en produktlista för en ny PDF-hash. Det är ett **partiellt offers_only-flöde**, inte bevis för att alla kommande layouter eller kampanjveckor fungerar.

Butiker, kommuner och aktuella dokument kommer fortfarande från officiellt register, SCB-geometri och varje butiks aktuella offentliga reklambladslänk. Inget användarval, inköpsområde, skarpt schema eller produktionssystem har ändrats.

## Det manuella steget

Tidigare krävde `document_review()` en post för exakt PDF-hash i `flyer_review_20260923.json`. Saknad hash stoppade hela dokumentet. Granskaren hade skrivit in annonsens produktnamn/varianter, förpackning, rätt prisruta, medlemskap, kampanjperiod och köpgräns. Värdena fanns ofta i texten, men pris–produktkopplingen och villkorstolkningen saknade generella regler.

V2 skiljer nu tre saker:

- **Hela utgåvans godkännande:** behövs inte för automatiskt stödda annonser.
- **Saknade tolkningsregler:** vissa sammanslagna textblock, historiska prisintervall, variantbeskrivningar och prislayouter kräver fortfarande granskning även när en människa kan läsa dem entydigt.
- **Verklig osäkerhet:** exempelvis ospecificerade sorter/storleksintervall, oklar prisruta, okänd pant, vikt-/köpgräns, otillräcklig produktmängd eller text som inte överensstämmer mellan butikens viewer och PDF. Dessa poster stoppas. Vi har inte läst bilder för att fylla luckorna.

Parsern använder PDF-text, typsnitt och koordinater; bekräftar motsvarande sidtext i butikens aktuella viewer; kräver unik lokal pris–annonsrelation; tolkar hela annonsvillkoret; kontrollerar tryckt jämförpris mot förpacknings-/grupppriset där enheten medger det. Ett uttryckligt `Per st` ger en säljenhet, aldrig en uppskattad vikt. Okänd närliggande prisruta och pantmarkering, även under priset, stoppar automatisk kvalificering. Okopplade kritiska sidvillkor isoleras på sidnivå.

Tryckt lägsta 30-dagarspris blir inte ordinarie köppris. Priset förblir kampanj-/medlemsavtal, med okänt ordinarie pris. Inga GTIN, näringsvärden eller variantstorlekar skapas. Tidigare granskade poster kan fortfarande användas för exakt samma verifierade dokument; det ger inget godkännande åt nästa utgåva.

## Verkliga dokument och faktisk automatik

Verklig insamling 24 september 2026 bekräftade två olika dokument: Hemma (4 sidor, SHA börjar `81254651f45b58ae`) och Willys (12 sidor, `ed44e4eba3c68c45`). **Båda gäller 21–27 september, vecka 39.** De är olika regionala/formatmässiga utgåvor, inte ett verkligt tidsmässigt kampanjbyte.

Den publika viewern saknar aktiverat arkiv; ett begränsat anrop enligt dess publika arkivklient gav `d: null`. Ingen annan verklig kampanjvecka eller tidigare ogranskad PDF kunde beläggas. Vi har inte upprepat blockerade anrop eller konstruerat äldre/nästa PDF-länkar.

| Dokument | Identifierade textannonser | Automatiska poster | Ej automatiskt godkända annonser | OWN och separat automatisk PriceUniverse | Med tidigare exakt granskning: nu giltiga produkter |
|---|---:|---:|---:|---:|---:|
| Hemma v39 | 34 | 7 | 27 | 7 / 7 | 24 per butik |
| Willys v39 | 112 | 29 | 83 | 29 / 29 | 64 för Rosengård |

De separata automatiska importerna kördes med den äldre granskningsvägen avstängd. Tester med en saknad granskningsfil ger samma resultat. Den äldre dokumentgranskningen används som separat kontrollfacit för belopp, mängd, medlemskap, gräns och period — inte som indata till de automatiska reglerna. **Detta är inte ett blindprov på ett verkligt tidigare ogranskat blad:** båda tillgängliga PDF:erna fanns redan i det tidigare granskningsmaterialet.

De 27 respektive 83 har en enda primär automatisk stopporsak per annons:

| Orsak | Hemma | Willys |
|---|---:|---:|
| Variant-/mängd-/prisintervall eller ungefärlig mängd | 11 | 42 |
| Återstående otolkad villkors-/varianttext | 4 | 22 |
| Viewer/PDF-text skiljer sig på sidan | 0 | 8 |
| Pris–annonsrelation inte unik | 4 | 3 |
| Okänd närliggande prisruta | 2 | 2 |
| Pant/variant behöver granskning | 3 | 3 |
| Annonsstruktur saknar stödd produkttext | 2 | 2 |
| Köpgränsens enhet saknar stöd | 1 | 1 |
| **Summa** | **27** | **83** |

Detta är automatisk kvalificeringsstatus, inte 27/83 separata köpbara varor. I det kombinerade aktuella Hemma-underlaget återstår 14 karantänannonser och en dublett; 19 kvalificerade annonser ger 24 varianter. Rosengård har 52 karantänannonser, en dublett och en redan utgången annons; 58 aktiva kvalificerade annonser ger 64 varianter. Den utgångna annonsen gäller glass 21–23 september och har inte fått hela veckans giltighet.

De kända textannonserna identifierades, men antalet eventuella annonser eller kritiska uppgifter som enbart finns i bilder är **okänt**. Noll oklassificerade textblock i denna kontroll betyder inte noll bildinnehåll.

## Butiker och import

Samtliga sju upptäcks med samma kommunfunktion. Deras `onlineStore=false` påverkar inte reklambladsinsamlingen. De sex Hemma-butikerna har varsin officiell bekräftelse av samma aktuella Hemma-dokument; Rosengård har det andra dokumentet. Inga onlinepriser eller obelagda grannbutikspriser används.

| Kommun | Butik och ID | Officiell aktuell källa | OWN | PriceUniverse / publicering |
|---|---|---|---:|---|
| Lund 1281 | Hemma Lund Stortorget 2863 | [Reklamblad](https://reklamblad.willys.se/willys/2863/) | 24 | 24 i validerad inaktiv kandidat; publicering spärrad av ofullständig/för gammal bas |
| Malmö 1280 | Hemma Malmö Lindängen 2843 | [Reklamblad](https://reklamblad.willys.se/willys/2843/) | 24 | 24, privat publicering/reload verifierad |
| Malmö 1280 | Hemma Malmö Lugnet 2851 | [Reklamblad](https://reklamblad.willys.se/willys/2851/) | 24 | 24, privat publicering/reload verifierad |
| Malmö 1280 | Hemma Malmö Möllevången 2870 | [Reklamblad](https://reklamblad.willys.se/willys/2870/) | 24 | 24, privat publicering/reload verifierad |
| Malmö 1280 | Hemma Malmö Söderkulla 2865 | [Reklamblad](https://reklamblad.willys.se/willys/2865/) | 24 | 24, privat publicering/reload verifierad |
| Malmö 1280 | Hemma Oxie Centrum 2879 | [Reklamblad](https://reklamblad.willys.se/willys/2879/) | 24 | 24, privat publicering/reload verifierad |
| Malmö 1280 | Malmö Rosengård 2352 | [Reklamblad](https://reklamblad.willys.se/willys/2352/) | 64 | 64, privat publicering/reload verifierad |

Totalt 208 butik–produktposter: 71 från automatiska regler och 137 från tidigare exakt dokumentgranskning. Det är sju verkliga butiker, inte 208 butiker. Presentationsurvalet har aldrig begränsat insamlingen till 2–3 poster.

## Styckköp och representativa köp

Den gamla spärren träffade tre Hemma-produkter och fyra Rosengård-produkter: uttrycklig gurka 9,90 kr/st, ljungplantering 59,90 kr/st, knoppljung **3 för 79 kr**, samt Rosengårds papaya 19,90 kr/st. Det var inte fyra belagda restpaketspriser. De uttryckliga styckpriserna och hela tregruppen kan använda befintlig offers_only-checkout. Knoppljung har fortfarande inget styck-, restköps- eller ordinarie pris: 1, 2 eller 4 exemplar stoppas; 3 kostar 79 kr och 6 kostar 158 kr. Ingen ny prissättare används.

Varje Hemma-butik i tabellen har följande verifierade exempel via sin egen länk, alla **21–27 september 2026**:

- Pågenlimpan, Pågen **900 g, 24,90 kr**, Willys Plus, **max 3 köp/hushåll**.
- Gurka, Spanien, klass 1, **9,90 kr/st**, gäller ej ekologisk, **max 3 köp/hushåll**, publikt erbjudande. Ingen styckvikt har antagits.
- Kycklingbröstfilé, Kronfågel, Sverige, **900 g, 99,90 kr**, Willys Plus, **max 3 köp/hushåll**.

Rosengårds [officiella blad](https://reklamblad.willys.se/willys/2352/) belägger under samma vecka:

- Pizzadeg, Monte Castello, **400 g/förpackning, 2 för 25 kr**, Willys Plus, **max 3 kampanjköp/hushåll**. Ett obelagt restpaket prissätts inte.
- Pågenlimpan, Pågen **900 g, 24,90 kr**, Willys Plus, **max 3 köp/hushåll**.
- Kycklingbröstfilé, Kronfågel, Sverige, **900 g, 99,90 kr**, Willys Plus, **max 3 köp/hushåll**.

De rena automatiska PriceUniverse-proven gav tre godkända representativa matköp per kommun genom matcher, checkout och audit. Det kombinerade slutprovet gav fyra i Lund och 23 över Malmös sex butiker. Brie fick ingen godkänd receptmatchning i det representativa provet trots verifierat pris. Knoppljungens belopp och mängd stämmer i köpberäkningen men blomman blir inte godkänd receptmat. De exakta faktaregisterna gav inga godkända produktdeklarationskopplingar för dokumentannonserna; inga näringsvärden eller näringsgodkännanden har skapats. Hushållsgränser kontrolleras över recept och butiker, även när äldre och automatiska regler skiljer sig i versaler eller numerisk representation.

## Driftprov och kvarvarande releasekontroller

Den faktiska huvudinsamlingen gjorde **13 offentliga källanrop** (3 Lund, 10 Malmö). Tidiga käll-/arkivundersökningar redovisas separat. Alla efterföljande import-, bygg- och driftprov är märkta **replay**, med originalobservationer. Fel och framtida klocka är uttryckligen injicerade. Ingen ny observation skapades av replay eller rebuild.

Malmö använder ordinarie CLI/runner, ett riktigt separat appförlopp och loopback-reload med den bevarade City Gross-basen och Lidl-tillägget. Första publicering, andra rebuild, processomstart, ej förfallet arbete, hämtfel och återhämtning passerade. De 184 reklambladsposterna och övriga produkter behöll samma signaturer. Första behovskontrollen i den nya privata behovsfilen behövde en publiceringskvittens och byggde lokalt; nästa kontroll blev `not_due`, utan barnbygge eller prisanrop. Båda resultaten är sparade.

Lunds tidigare Willys-onlinebas var äldre än 48 timmar. Vi har inte föryngrat den eller lånat Malmös bas. Ett vanligt publiceringsförsök med enbart reklamblad nådde validerad prisbyggnad men stoppades av `IncompleteBasketError`; 24 poster finns dessutom i en separat validerad inaktiv PriceUniverse. **Lunds fullständiga publicering kräver en aktuell komplett bas.** City Gross Malmö hade verklig observation 23 september 08:04:51Z och var färsk vid slutkontrollen; nästa basuppdatering enligt 35-timmarsregeln är 24 september 21:04 svensk tid.

Nästa beräknade reklambladskontroll är **25 september cirka 20:40–20:41 svensk tid**, per butikens ursprungliga observation +35 h; kampanjgränsen är **28 september 00:00 svensk tid**. Det är status i de privata proven, inte installerade scheman. Faktiska käll- och kampanjvillkor måste fortfarande verifieras vid varje hämtning.

Syntetiska tester täcker en okänd PDF-hash, nästa kampanjperiod, årsskifte, kortare datum, nya kritiska villkor, sidisolering och spärr före/efter giltighet. De är **inte bevis för nästa verkliga reklamblad**. Verkligt tidsmässigt utgåvobyte och en tidigare ogranskad verklig utgåva återstår när officiellt underlag finns.

Lidls separata granskningsberoende pilot och historiska saknade fixture är oförändrade. Det saknade gamla testets skydd för produktdeklaration/preparering och kolhydratgräns påstås inte verifierat här. Fullständigt Malmö-publiceringsprov med aktuell komplett federerad bas/Primat är fortsatt separat. Ingen produktionsaktivering, Windows-/schemaändring, bildanalys eller betald modell-API har utförts.

Maskinläsbart bevis: `FINAL-QUALIFICATION.json`, `automatic-only-*/proof.json`, `runtime-*/purchases-final.json`, `runtime-1280/ACCEPTANCE.json`, `base-freshness.json`, test-XML och `PACKAGE.json`.
