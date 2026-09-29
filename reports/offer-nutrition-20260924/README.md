# Willys och Lidl: pris och näring, 24 september 2026

Verifierad delutökning, **inte 100 procent och inte färdig totalleverans**. Nio ytterligare unika Lidl-livsmedelserbjudanden når OWN och PriceUniverse. Willys får 16 ytterligare automatiska variantgodkännanden över de två dokumenten. De ersätter befintliga manuella godkännanden: nettotillskottet av unika Willys-priser är fortfarande noll. Näringskoppling och användbara exakta produktköp förbättras för båda kedjorna.

Ingen produktion, Windows-uppgift, aktiv schemaläggning, sparat användarval, bildanalys eller betald modell har ändrats/använts. Tidigare kedjearbete, Primat och releaseunderlag ligger kvar.

## Fryst jämförelse

Köpdag 2026-09-24, samma butik och medlemskontext före/efter. Samma rådata, PDF-hash och verkliga observationer används. Lidl avser den senast sparade **29-sidiga** v39-revisionen från 24 september 14:35 UTC. Blanda inte den med äldre 28-sidorsutfallet 3 manuella + 14 automatiska. Det äldre bladet får nu 21 automatiska, där de tre gamla manuella deduplicerats. Två torsdagserbjudanden är fortfarande framtida vid dess observation den 23 september.

| Samma underlag | Hela nämnaren | Automatiska annonser/bindningar före → efter | Automatiska varianter före → efter | Manuella varianter efter deduplicering | Datumgiltiga varianter i OWN/PU |
|---|---:|---:|---:|---:|---:|
| Willys Hemma, fyra sidor | 34 annonser | 13 → 17 (38,2 → 50,0 %) | 16 → 22 | 8 → 2 | 24 → 24 |
| Willys, tolv sidor | 112 annonser | 42 → 51 (37,5 → 45,5 %) | 46 → 56 | 18 → 8 | 64 → 64 |
| Lidl, 29 sidor | 380 unika käll-ID; 157 dokumentrubriker | 14 → 23 | 14 → 23 | 0 → 0 | 14 → 23 |

Historiken från första automatiken var Willys 7/34 och 29/112. Tabellen börjar vid senaste genomförda steget 13/34 och 42/112; föregående förbättringar räknas inte igen. En annons kan innehålla flera varianter eller upprepas. Totalt variantantal bakom öppna grupper är okänt. Willys-dokumenten har även gemensamma produkter; summera inte deras rader till en kedjeunik produktmängd. Ingen ökning bygger på butikskopior.

Willys har 23 respektive 63 importerade livsmedelsvarianter samt en befintlig Knoppljung per dokument. Den får inte ingrediens-/näringsgodkännande. Alla 16 nya automatiska Willys-varianter och nio tillkommande Lidl-priser är livsmedel.

## Återanvändbara kodändringar

Willys regler v4 använder en snäv lokal priskolumn där den är entydig, med fortsatt en-till-en-kontroll mellan pris och annons. Kompletta upprepade produktnamn i beskrivningen behandlas som redundans. Utskrivna egenskaper som krispig, glutenfri, italiensk och extra virgin bevaras. Sluten grammatik utvecklar utskriven ellips i passerade/krossade tomater. Undantaget ”ej ekologisk” bevaras i identiteten. Samma fullständiga variant, avtal och villkor dedupliceras mellan automatisk och gammal manuell import. Ingen ny veckolista används. Den äldre granskningen är testfacit, inte parserindata.

Lidl regler v3 kan läsa komplett varumärke över flera rader och en första typografiskt avgränsad variantbeskrivning som del av den exakta identiteten. Tomma prisspann ignoreras. Multipackens ×/x normaliseras utan mängdändring. Historiskt 30-dagarspris blir inte ordinarie pris. Dokument och struktursvar måste överensstämma om hushållsgräns, sammansättningstext och avrunnen vikt. Prisgeometri, unikt prisfält och jämförprisaritmetik kontrolleras separat. Torsdag–söndag-perioder bevaras. Samma prisruta får inte bevisa flera produktannonser. Personliga kuponger, okända sidvillkor och öppna varianter stoppas fortfarande.

Nya Lidl-varianter: Skivad salami 2×100 g, Serranoskinka 240 g, Majssnacks ost & bacon 100 g, Hamburgare 1,8 kg, Lingongrova 500 g, Vita bönor 540 g/400 g avrunnet, Biscuitkaka 600 g, Pulled pork 550 g och Chicken nuggets 750 g. De sista två gäller 24–27 september. Regionala priser får aldrig nationell giltighet utan den enskilda produktens bevis.

Produktmatchern kan nu köpa exakt hela det redan kvalificerade erbjudandets namn, även nuggets eller paella. Det kräver bevarad fysisk erbjudandeproveniens och kampanjbevis. En generisk receptbegäran om kyckling får fortfarande inte nuggets. Katalog-/Primat-regler ändras inte av reservvägen.

## Näring redovisas separat

Tio ytterligare officiella SLV-livsmedel har hämtats med råsvar, URL och verklig tid: kalkonbröst, vitlök, koriander, grönmynta, gurka, extra jungfruolivolja, crème fraiche 32 %, ingefära, fläskfärs 20 % och frysta gröna ärtor. Databasen anger version 2026-07-01; individuella poster behåller egen version och ursprungliga värden. Gamla observationer skrivs inte över. Källa: [Livsmedelsverkets databas](https://soknaringsinnehall.livsmedelsverket.se/), exakta API-länkar i `slv/references.json` och `backend/app/data/nutrition/slv-20260924.json`.

Generiska referenser kräver fortsatt opt-in. Typ, sammansättning, fetthalt, form och enhet kontrolleras. Ospecificerad mynta blir inte grönmynta; korianderfrö blir inte färsk koriander; kalkon blir inte kyckling. En verklig brist i äldre kycklingkoppling — vilken bröstfilé som helst — har rättats. Rå kalkon eller fläsk blir inte automatiskt en tillagad deklaration.

| Samma exakta produktfrågor | Matchning/köp före → efter | Näringsunderlag i användbar g-enhet före → efter | Ytterligare referens endast för separat uppvägda gram |
|---|---:|---:|---:|
| Willys Hemma, 24 varianter | 19 → 23 | 0 → 3 | 1: gurka i styck |
| Willys tolv sidor, 64 varianter | 48 → 63 | 0 → 5 | 3: gurka, crème fraiche, olivolja |
| Lidl, 14 → 23 varianter | 8 → 23 | 0 → 2 | 1: olivolja i ml |

Mätningen i `nutrition-comparison.json` använder samma exakta produktfråga före/efter. Den säger inte att tidigare Smako saknade all näringsfunktion. Ml/st räknas inte som gram. Referenstillgång är inte samma sak som godkänt huvudmålsrecept. Lidl får generisk kalkon och återanvänd Pågen-deklaration för exakt Lingongrova-GTIN/variant/500 g. Deklarationen behåller sin ursprungliga observation över självständigt kvalificerade kampanjer. Övriga prisposter ligger kvar trots saknad näring.

En avgränsad kall beredning av uppvägd ätbar koriander och vitlök har verifierats genom matchning, näring, checkout och audit: 20 g + 5 g ger 13,8 kcal totalt med generiska referenser. Inget kokutbyte, vätskeförlust eller densitet antas. Nya tillagade recept och deras utbyten kvarstår separat.

Åtta officiella Lidl-produktsidor har hämtats utan fullständiga användbara näringsdeklarationer. Hamburgarens marknadsföringstext avviker från PDF/strukturerad sammansättning; ingen generisk köttblandning väljs för att dölja konflikten. Officiell Garant-deklaration för Majskorvar och City Gross sida för Garant Gyros har också sparats. De är **ännu inte importerade produktfakta**: exakt återanvändbar deklarationskoppling till Willys dokumentvariant återstår. City Gross-priset används inte som Willys-pris. Detta är kvarvarande implementeringsarbete, inte behörighetsbrist.

## Hela bortfallet

`willys-denominator.json` och butikernas `result.json` innehåller alla annonsbeslut, även automatiskt stoppade fall som har gammalt manuellt godkännande.

| Exklusiv automatisk huvudorsak | Hemma | Tolv sidor |
|---|---:|---:|
| Automatisk kvalificering | 17 | 51 |
| Öppen variant/mängdintervall/ungefärlig vikt | 7 | 39 |
| Webbvisare/PDF-konflikt | 0 | 8 |
| Pris-/annonskoppling inte entydig | 0 | 4 |
| Okänd närliggande prisruta | 1 | 1 |
| Pant/variant inte belagd | 3 | 3 |
| Okänd rubrikstruktur | 2 | 2 |
| Hel/delad vara med olika priser | 2 | 2 |
| Köpgräns i annan enhet | 1 | 1 |
| Örter/Citron oklassificerad varianttext | 0 | 1 |
| Dubbel annons | 1 | 0 |
| Hela nämnaren | 34 | 112 |

Antal eventuella bildexklusiva annonser är okänt, inte noll. Bilder har inte analyserats. Manuella godkännanden är bundna till gammal dokumenthash och ärvs inte av nya utgåvor.

Lidl: 380 käll-ID = 23 godkända + 355 utan kvalificerad produkt–nationell kampanjbindning + 2 parserkarantäner (oprövat rabattvillkor respektive icke exakt jämförprisintervall). Samtidiga underorsaker sparas per rad, huvudräkningen är exklusiv. De tidigare 27 oprövade prisfältsposterna löstes i föregående parsersteg; de räknas inte som 27 nya importer här. Saknad bindning kvarstår där den inte beläggs.

157 dokumentrubriker: 23 kvalificerade, 86 utan unik komplett sammansatt identitet, 33 utan unik livsmedelsidentitet i struktursvaret, 4 okänd villkors-/varianttext, 3 utan fast förpackning, 3 kritiskt sidvillkor, 3 behöver pantbelägg, 2 avvikande förpackning. Detta är en annan nämnare än käll-ID.

Officiell kategorihierarki och källans butiksdatum ger följande för alla 380. Analysfältet ”Food” används inte eftersom även rengöringsmedel är märkta så. Regionalt datumbevis är fortfarande inte nationell butiksgiltighet.

| Status vid verklig observation | Livsmedel | Icke-livsmedel | Okänd typ |
|---|---:|---:|---:|
| Aktuell | 105 | 68 | 2 |
| Framtida | 132 | 64 | 3 |
| Utgången | 0 | 0 | 0 |
| Okänt datum | 5 | 1 | 0 |

23 av 105 aktuella regionala livsmedelskandidater är butikskvalificerade. Övriga 82 döljs inte. Slutlig nämnare för alla faktiskt tillämpliga nationella/butiksspecifika erbjudanden är ännu okänd. Något 100-procentspåstående kan inte göras.

## Kommuner och riktiga köp

Alla kvalificerade poster behandlas. Lund: Willys 24 + Lidl 46 = 70 i isolerad PU, 69 livsmedelsköp med audit. Malmö: Willys 184 + Lidl 184 = 368, 362 livsmedelsköp med audit. De sju övriga är befintlig Knoppljung, avvisad som livsmedel. Butikskopior är driftskontroller, inte nya erbjudanden. Se `STORES.md`.

Exempel ur officiellt v39-underlag, 21–27 september; ordinarie pris förblir okänt:

- Willys Hemma: koriander 25 g 9,90 kr och vitlök i kapsel 100 g 9,90 kr, offentligt styckkampanjpris. Inget ytterligare medlems-/köpgränsvillkor anges i kvalificerade annonser. [Officiellt blad](https://reklamblad.willys.se/willys/2863/). SLV avser använd ätbar gramvikt.
- Lidl: kalkonbröstfilé 1 kg 99 kr offentlig kampanj; Lingongrova 500 g 17,90 kr med Lidl Plus; vita bönor 540 g netto/400 g avrunnet 13,90 kr. Behov av 450 g avrunnet kräver två burkar, 27,80 kr. [Officiell publikation](https://www.lidl.se/c/reklamblad/s10018018). Exakt text, sida, period och villkor i `lidl-final.json`.
- Hamburgare 1,8 kg 159 kr kräver Lidl Plus, högst två förpackningar per hushåll. Samma hushållsavtal bevaras över butiker och recept; inget restpris uppfinns. Priset är verifierat, näringen inte godkänd via gissad köttblandning.

## Drift och verifieringsgränser

Verklig hämtning 24 september cirka 15:55–15:56 UTC: Willys representativa dokument 3+3 anrop, Lidl upptäckt/metadata/PDF/produkter 12 anrop. Resultat 24/64/23. Slutkodens replay ger samma antal utan nya anrop eller föryngring. Transporttal i sparade batcher är historiska, inte nya replay-anrop.

`runtime-1280/ACCEPTANCE.json`: avsedd appstart och ordinarie refresh-runner, isolerad OWN-bas med City Gross, Willys och Lidl. Första publicering, andra rebuild och separat omstart kördes på mellanliggande kod. Slutkodens två fulla rebuild/publicering/reload vid injicerat hämtfel och återhämtning bevarar Willys 184, Lidl 184 och City Gross-innehållets signatur. Varje fas har separat serverprocess. Slutkodens not_due gör ingen rebuild eller prishämtning. Bootstrapkontrollen som upptäckte kodändring byggde om lokalt; den sparas separat och räknas inte som lyckat tomt kontrollvarv.

`lidl-recovery-verification.json`: ordinarie jobb, gammal faktisk capture → injicerat fel med bevarad godkänd referens → slutkodens replay av ny faktisk capture → omstart med beständigt kommunval → not_due. Retry-klockan flyttas 20 minuter enbart i provet. Utgångna snapshotreferenser kan behållas för spårbarhet; det gör inte priserna köpbara. Alla 438 importerade butiksposter spärras dagen före start och dagen efter slut. Runtime-testklockan spärrar även för gammal bas.

Isolerad City Gross-bas: äldsta observation 2026-09-23 08:04:51 UTC; 32,23 timmar vid slutkontroll 24 september 16:18 UTC. Nästa bashämtning 24 september 19:04:51 UTC, aging 20:04:51 UTC, hårt stopp 25 september 08:04:51 UTC. Komplett aktuell Malmö-bas har inte verifierats. Exakta källplaner sparas i slutrapporterna; inget aktivt schema ändras.

**427 tester passerar, noll fel/skip**, samt Ruff på ändrad kod. Slutlogg `tests-final.xml`; äldre loggar med inaktuella räkneförväntningar sparas som mellanresultat. Verklig v40-PDF ger fem bindningar men noll aktuella köp vid v39-observationen. Den var tidigare undersökt och är inget oberoende ogranskat hållprov. Ingen ny ogranskad Willys-kampanjvecka har verifierats; två v39-format bevisar inte nästa vecka.

Historisk Lidl-testlucka är **olöst**: `test_reviewed_lidl_nutrition.py` saknar `reports/source-implementation-20260915/lidl_offer_adapter.py`. Den avser exakt GTIN/variant/förpackning, deklarationsversion/näringsbas, ny kampanj/gammal snapshot, rå lårfilés beredning och ost genom köp/audit. Nya tester täcker delar av isoleringen, men ersätter inte hela historiska ost-/lårfiléflödet. Testet ingår inte i de 427.

## Kvarstående arbete

1. Willys har ännu inget nettotillskott av unika priser. Öppna variantgrupper/okänd vikt behöver exakta officiella produktuppgifter; åtta PDF/webbvisarkonflikter måste lösas utan att välja billigast källa.
2. Lidl behöver fler exakta produktbindningar. Utökad text-/villkorsgrammatik och återanvändbara officiella identiteter är kvarvarande kodarbete. Regionalflödet får inte ärva nationell giltighet.
3. Deklarationskoppling för sammansatta produkter återstår. Två konkreta officiella källfynd är sparade men inte anslutna. Detta är möjligt fortsatt implementeringsarbete, inte ett behörighetshinder; totaluppdraget kallas därför inte färdigt.
4. Gramreferenser löser inte ml/st, ätlig andel eller tillagningsutbyte. Dessa kräver belagda fakta/beredningsregler. Prisposter bevaras under tiden.
5. Oberoende ny kampanjvecka, historisk Lidl-fixture och komplett Malmö-publiceringsprov förblir öppna. Bildexklusiva fakta kvarstår under körningens bildförbud.
