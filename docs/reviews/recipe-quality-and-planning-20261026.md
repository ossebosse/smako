# Receptkvalitet, köpbarhet och personlig planering, 2026-10-26

[PR #15](https://github.com/ossebosse/smako/pull/15) genomför det avgränsade
[uppdraget](../CODEX-SOL-NEXT-20261026-RECIPE-QUALITY-AND-PLANNING.md).
Start: ren `main` på `41e4c76`, hämtad från origin utan överskrivna ändringar.
Maskinöversikt: [delivery-summary.json](recipe-quality-and-planning-20261026/delivery-summary.json).

337 berörda receptvarianter har nya granskade versioner. Majskopplingen ger
33 ytterligare individuellt produktlösbara varianter i exakt läge och 38 i
uttryckligt estimated. Ett nytt kombinerat endagsval klarar checkout, save
och GET på **31,96 s i senast mätta API-kontrollen**; browserobservationen är
**28,10 s från knapptryck till synlig inköpslista och GET**. Femmiddagsfallen
är fortfarande ofärdiga vid 75 s. Produktmålet för fria veckoval är inte uppnått.
Ingen beta, produktion, profil, scheduler eller insamling har aktiverats.
Legacy är standard, `library_merge_generations=False`.

## Recept: hela den berörda klassen

[recipe-review.json](recipe-quality-and-planning-20261026/recipe-review.json)
redovisar vart och ett av de **337 ID:na/196 baserna**: tidigare och nytt
runtime-ID, uttrycklig process, aktiv-/väntetid/totaltid före och efter samt
innehållshash. Alla har disposition `corrected`; 14 kräver en ännu obelagd
färsk produktform. Tolv ingrediensklasser är genomgångna, inte bara de tre
exemplen i uppdraget. Recepten är AI-författade och **inte provlagade**.

- Kall mango på tapiokapudding skalas inte och ingår inte längre i stegen
  som kokar pärlor/socker. Frysta skalade tärningar tinas till kall topping.
  Motsvarande felaktiga `uses` rättas i fylld risdeg.
- Guacamole beskriver tinade skalade avokadotärningar och deras ätliga vikt.
- Båda ananasspetten tinar före skärning/trädning, oavsett om ugnstexten
  använder ordet rosta. Het ananasglasyr går direkt från fryst till upphettning.
- Frysta hackade örter vägs vid den faktiska användningen. Grönkål går direkt
  till värme; sparris/okra tinas före skärning. Okra torkas före stekning.
- Hallon behåller minst en minuts kokning. Kall användning behåller kylning;
  varm kompott får ingen extra kall väntan utan användningsskäl. Källstödet
  finns i [measurement-notes.json](recipe-quality-and-planning-20261026/measurement-notes.json).
- Nio varianter med fast grön mango och fem med fasta färska avokadostavar/
  klyftor får egna krav. Frysta mogna tärningar uppfyller dem inte. De två
  ingrediensdefinitionerna är `definition_only`: inga nya positiva SKU-bevis
  eller antagna ätliga andelar har lagts till.

Kall upptining är en författaruppskattning med explicit kontroll av genomtinad
råvara och förpackningens anvisningar: 120 min för små mängder upp till 200 g,
240 min för större mängder i tunt lager i kyl. Hallon för kall användning har
120 min kylning efter kokning. Detta är inte verifierade universella tider.
Nödvändig väntan och seriella beroenden finns kvar; ingen påhittad överlappning
eller tidskapning för att passera filter. Det gamla åttatimmarspåslaget ersätts
av granskad process, inte av fler värmeord i samma regex.

| Enkel variant | Aktiv/väntan/total före, min | Efter, min |
|---|---:|---:|
| Tapiokapudding med mango | 27/10/37 | 29/130/159 |
| Guacamole | 13/480/493 | 13/120/133 |
| Tofu-ananasspett | 23/40/63 | 25/280/305 |
| Kyckling-ananasspett | 30/525/555 | 30/285/315 |
| Fisk med ananasglasyr | 29/20/49 | 30/20/50 |

Ordinarie **author → validate → diff → import** har publicerat fyra paket
med sammanlagt 337 versioner `1.0.2`, följt av tre fiskförfiningar `1.0.3`.
Författarunderlag och separata kvitton finns i rapportkatalogen och
`backend/app/data/recipes/reviewed-frozen-20261026/`. Föregångare återkallas;
deras bytes, ID:n och sparade referenser behålls, även de tre mellanversionerna.
Det finns fortfarande **2 462 aktiva varianter/934 registrerade baser**,
38 aktuella och sju historiska paketgenerationer. De 166 originalfilerna och
ursprungliga 262 recepten är bevarade. Den gamla automatiska
`frozen_preparation` avvisar omkörning; rättningsverktyget verifierar redan
utgivna ID:n/hashes i stället för att återpublicera dem.

## Produktkoppling och kvarstående källor

Samma behöriga Malmöunderlag används i före/efterjämförelsen: 89 458 produkter,
71 138 faktarader, testklocka `2026-10-23T06:00:02.869273+00:00`.
Prisartefaktens SHA är `06cbf0b12e619f09dd3709b808916d1c74676859d246ad72f74d52d0e6d91857`;
faktafilerna matchar föregående imports bytes och version. Full bindning finns i
[purchase-coverage.json](recipe-quality-and-planning-20261026/purchase-coverage.json).

Befintliga frysta **Majskorn** fanns men saknades i aliasåtervinningen och fick
för svag semantisk identitet. Båda stegen rättas i den ordinarie matchvägen.
Det snäva fullständiga namnet plus fryst kategori tillåter hela korn;
kolv, blandningar, snacks och djurfoder avvisas. Faktadeklaration med smör,
salt, vatten eller andra grönsaker kan inte ärva godkännandet. Identitet är
inte allergen-, eko- eller näringsintyg. Produkt, butik, snapshot, förpackning,
pris och övriga faktagrindar behålls.

| Individuella insatsinköp, av 2 200 | Exakt | Uttryckligt estimated |
|---|---:|---:|
| Tidigare rapport | 704 | 888 |
| Efter korrekta färskformskrav, före majskoppling | 700 | 882 |
| Efter majskoppling | **733** | **920** |
| Förbättring från majskopplingen | **+33** | **+38** |
| Netto mot tidigare rapport | +29 | +32 |
| Fortfarande blockerade | **1 467** | **1 280** |

[coverage-disposition.json](recipe-quality-and-planning-20261026/coverage-disposition.json)
visar att alla fyra/sex förluster är de avsedda färskformskraven. Inga andra
statusförluster finns i jämförelsen. Talen avser alla ingredienser individuellt,
inte gemensam veckocheckout eller personliga närings-/allergikrav.

Den första inventeringen visade ingen förbättring innan även aliasåtervinningen
rättats. Nästa körning nådde tidsgränsen efter exakt checkpoint. Slutlig
estimated-körning återanvände färdigt exakt resultat och oförändrade scope;
ingen omstart av hela matrisen gjordes. Samtliga försök är debiterade.
[inventory-receipts.json](recipe-quality-and-planning-20261026/inventory-receipts.json)
bevarar SHA/tider till fullständiga rårapporter i ignorerad `.local`; kompakt
källbundet underlag finns i Git.

**105 ingrediens-/formgrupper återstår.**
[HINDER.md](recipe-quality-and-planning-20261026/HINDER.md) och
[remaining-blockers.json](recipe-quality-and-planning-20261026/remaining-blockers.json)
innehåller receptindex, krav, avslag och nästa källa. Störst exakt påverkan:
limejuice 445, ingefära 402, salladslök 139, mynta 131, purjolök 111.
Talen överlappar. Ren limejuice behöver full deklaration; ingefära och ansad
lök behöver rätt källbelagd ätlig mängd. Hela rötters/frukters bruttovikt blir
inte automatiskt receptvikt. Det är ett käll-/modellbehov, inte skäl att byta
alla recept till frysta produkter. Ingen bred ny insamling har gjorts.

## Verkliga personliga begäranden och observerad latens

[requests.json](recipe-quality-and-planning-20261026/requests.json) låser de
faktiska begärandena före respektive prov. A–E behålls oförändrade. F definierades
före första F-körningen; [ändringsnoteringen](recipe-quality-and-planning-20261026/request-revision-note.json)
bevarar tidigare hash. Inget misslyckat falls krav har lättats.
Alla sex är uttryckliga `estimated`-begäranden med tillåtna näringsuppskattningar,
såsom det bevarade UI-underlaget. Exakt läge mäts separat i produktinventeringen.

Alla fall väljer samma 55 butikskontexter, tomt privat skafferi och nya lokala
ägare. Butikstaket är två utom E. A:s faktiska serialiserade UI-standard har
null i middagens ingrediens-/tidsgränser trots toppnivåns 10–15; den begäran
har inte skrivits om till en påstådd 10–15-begränsning.

| Fall och val | Rå pool efter receptval → singletonkvalificerade | Observerat utfall efter laddat underlag |
|---|---:|---|
| A: 5 middagar × 4 portioner, faktiska standardval | 2 021 → 949 i slutprovet | Ingen färdig meny vid **75 s** |
| B: 5×4, grekiskt/italienskt, protein ≥35 g, 3 kyckling + 2 vegetariska, högst 3 samma huvudprotein | 681 → 29 | Före och efter ändringen: ingen färdig meny vid **75 s** |
| C: 1×2, svenskt, 5–7 ingredienser, aktiv ≤30/total ≤45 min | 3 → 2 | API **29,16 s**, 108,45 kr; browser **27,70 s**; innehållsreservation nedan |
| D: A + jordnötsallergi + 50 % ekologisk inköpskostnad | 2 021 → 0 | **24,89 s till HTTP 422 DATA_BLOCKED**, ingen meny |
| E: A med en butik | 2 021 → 864 | Ingen färdig meny vid **75 s** |
| F: ny ägare, 1×2, grekiskt/italienskt, 5–7 ingredienser, aktiv ≤30/total ≤45 min, protein ≥20 g | 14 → 4 | API **31,42 s**, senaste faktagrindskontroll **31,96 s**; browser **28,10 s**, **104,30 kr** |

A/B/E-siffror är partiella diagnostikkvitton omkring 60 s före stoppet, inte
slutliga sökresultat. Exakta avslag och faktiskt prissatta/sökta förslag per
fas finns i respektive JSON och maskinöversikten. A: 1 072 produktavslag.
B: 205 policy, 414 produkt, 33 näringsgräns; 29 kvar. E: 1 072 produktavslag
plus 85 butikstakavslag. D: 1 819 policy/allergenavslag och 202 produktavslag;
eko-steget når ingen kvalificerad meny och är därför inte godkänt. C: ett
produktavslag. F: tio produkt-/näringsdataavslag; fyra verkligt kvalificerade.
Tusentals inlästa recept är därmed inte bevis för tusentals sökbara kandidater.

C och F passerar aktuell gemensam checkout/audit, privat save och ägarbunden
GET. F väljer italienskinspirerad minestrone med vita bönor och pasta.
Näringskravet tillämpas: **ESTIMATED 20,7625 g protein per portion** mot 20 g.
Beräkningen summerar dokumenterade ätliga insatser med uttryckligt tillåtna
referenser; tillagad vikt, retention, densitet eller avrunnen andel antas inte.
C har `NOT_REQUESTED` för näring och styrker inget näringsmål.

C:s titel lovar rågbröd men den publicerade insatsen är generiskt bröd och
checkout väljer pitabröd. Detta är ett **kvarstående innehållsfel utanför den
frysta ändringsklassen**, dokumenterat med exakt ID i
[remaining-content-issues.json](recipe-quality-and-planning-20261026/remaining-content-issues.json).
C räknas som funktionell runtimeobservation, inte fullständigt innehållsgodkänd
acceptans. Nästa rättning måste använda ordinarie ny version.

Browserproven använder riktig Chromium, verklig UI-knapp och samma lokala
FastAPI/Uvicorn-app med verkliga pris-, plan-, save- och GET-anrop. Inga routes
eller pris-/plan-API:n ersätts. Appens egen utkaståterställning fyller valen;
postnummer och butiksval verifieras. F bevisar faktiskt skickat proteinmål 20,
exakt en plan-POST, synlig inköpslista, inga JS-fel samt återladdning av sparad
plan utan omräkning. UI utelämnar `use_pantry`, vilket ger modellstandard true mot ett tomt privat
skafferi; API har false. Normaliserade begäranden skiljer sig endast i det
valet, verifierat i `verification.json`. Effektiva ingredienskrav,
priser och butikscope matchar. [F-skärmbild](recipe-quality-and-planning-20261026/F-browser-shopping.png).
Det första C-browserförsöket stoppade före någon plan-POST på en skymd knapp;
felet och hela kostnaden behålls. Inga kontohemligheter eller sessions-ID:n
finns i Git.

API-tiden omfattar POST, audit/save och kontrollerad GET. Browserns tid börjar
vid klicket efter laddat underlag. F:s senaste uppmätta process tog **92,47 s totalt**,
varav **60,44 s uppstart/laddning** och **31,96 s API/GET**. Övriga laddningar
var cirka 52–69 s (första misslyckade browserförsöket cirka 85 s); de ingår i
budgeten men är inte klicklatens. Kö i lyckade API-fall var under en millisekund.
Detta är få lokala Windowsobservationer, inte p95, Linux-/betalatens eller
ett bevis för att kalla förstagångsanrop klarar 60 s. Senaste F-kontrollen
sammanföll delvis med riktad lokal verifiering; ingen förbättring tillskrivs
skillnaden mot tidigare F.

F:s API/browser/slutkontroll ger samma 104,30 kr och audit. Ingen jämförbar
äldre giltig personlig veckovinnare finns att regressionsjämföra med; tidigare
låsta menyer är andra krav. Fixturetester kontrollerar oförändrad vinnare,
pris och audit efter cacheändringen. Globalt billigaste korg påstås inte.
F är ett endagsfall: målet 30–60 s är observerat där, inte för fem middagar.

Efter sista mätningen utökades avvisningen av deklarerade tillsatser i
frysta majskorn till recept utan uttryckligt frystkrav. Alla elva uppmätta
majsscope i vardera köpläget hade redan frystkravet. Full CI fångade också
att den nya sammansättningsgrinden avvisade en tidigare giltig källdeklaration:
`Majskorn (Ungern)`. Den exakta ursprungsnoteringen bevaras nu; tillsatser i
parentes avvisas fortfarande. Den befintliga käll-/snapshotregressionen och
544 riktade prov passerar. F innehåller ingen majs. Ingen ny dyr mätning
startas. Metodhash för sista kodhuvudet finns i `verification.json`; varje
latenskvitto behåller sin egen uppmätta metodhash och påstås inte ha körts
på det senare kodhuvudet.

## Avgränsad prestandaändring, cache och resurser

B-profilen visade upprepad JSON-hashning av samma recept i diagnostik och stor
mängd gemensamma korg-/butiksutvärderingar. Den enda sammanhängande optimeringen
återanvänder befintlig **begärandeägd RecipeComputationCache** i
ProductPlanningTrace och tre identitetsanrop i PersonalPlanner. Samma fulla
receptsnapshot styr identiteten; ändrade ingredienser, former eller instruktioner
invaliderar återanvändning. Matchning, prissökning och användarkrav ändras inte.
Riktade tester kontrollerar mutering/kopior samt samma riktiga fixturesökning,
pris och audit. Ingen persistent profilcache införs.

B stoppade även efter ändringen vid 75 s. Vid cirka 60 s hade den före/efter
räknat cirka 1,506/1,567 miljoner butikskombinationer. Samplade löv i
receptidentitet var 55/468 före och 37/475 efter; det är inte en rigorös
latensvinst. Nästa flaskhals är fortfarande upprepad gemensam korgsökning och
historiska planeringspass. Ingen full V2 har implementerats och inget större
butikstak har exponerats; godtyckligt 1..N-stöd är inte färdigt.

[preparation-full-cache.json](recipe-quality-and-planning-20261026/preparation-full-cache.json)
mäter ordinarie gemensam CLI-förberedelse: **32,51 s**, 8 796 missar,
noll träffar/noll skrivningar när innehållscachen redan innehåller **4 096**
filer (2 589 445 byte). 3 178 referenser per portionsstorlek 1/2/4/12 omfattar
aktuella och historiska versioner; det är inte antalet sökbara aktuella recept.
Metodsignaturen binds i varje kvitto; senare snävare majsgate ger ny signatur,
så förberedelsemätningen på `b299b0f` påstås inte vara en ny hållbar slutversionscache.

Ett litet syntetiskt versionsbyte vid full kapacitet bevisar säker omberäkning
och bevarade gamla bytes, inte återkommande uppdateringsprestanda. Full cache
faller säkert tillbaka till minnesberäkning; kvarstående retention/kapacitet
hindrar hållbar delad beredskap för nya versioner. Bara **en** behörig matchbar
pris-/faktaversion fanns: verklig veckouppdateringslatens och minnesöverlapp
mellan två riktiga versioner är **omätta**. F mäter ny ägare/nya val på samma
version och ersätter inte versionsbytesdelen av uppdraget.

Alla mätarbetare kördes genom samma budgetverktyg/OS-lås med faktisk
interpreter bunden till Windows Job, två processorkärnor i affinitet och
3 GiB commitgräns. Högsta observerade privata commit för de personliga proven
var cirka **1,44 GiB**, working set cirka **1,45 GiB**. Browserklientens minne
är inte separat kvalificerat. Detta är inte Linux cgroup-mätning. Fasgränser
120 s för laddning och 75 s för personlig begäran ryms under totalgränsen;
fasbyte kan inte förlänga den gemensamma tidsbudgeten. Inga mätarbetare är kvar.

## Verifiering och fortsatt arbete

**544 PASS** i sista riktade offlinekörningen: frysta publicerade recept och
tidsfilter, majskorn/faktabyte/allergigrind, alla intakelänkar, identitetscache,
budget och full versionscache. Tidigare oförändrad struktur-/preparationssvit
samt verklig plannerfixture är verifierade; Ruff på samtliga ändrade Pythonfiler
och compileall passerar. Accesskontrollen visar inga gamla daterade källor
eller externa nätanrop. Paketens återimport är idempotent och historiska bytes
bevaras. Ordinarie full CI inklusive Chromium/WebKit passerade på `b299b0f`
och `03e955b`; PR:s sista huvud ska också ha grön ordinarie CI före mainmerge.
Se [CI](https://github.com/ossebosse/smako/actions/runs/40311873169) och PR-kontrollerna.

Samma [120-minutersjournal](recipe-integration-800-20261025/budget.json):
vid start **2 125,9999 s använda / 5 074,0001 s kvar**. Denna etapp kostade
**1 729,4146 s** inklusive misslyckanden, laddning, inventering, profilering
och omtag. Slut: **3 855,4145 s använda / 3 344,5855 s kvar**
(**64,26 / 55,74 minuter**). Ingen återställning eller stor matris.
Ordinarie CI och små relevanta regressioner ligger utanför mätbudgeten.

Nästa avgränsade steg är att förbereda versionsbundna gemensamma ingrediens-/
butiksdata för det aktuella biblioteket och återanvända dem i gemensam checkout,
med B:s oförändrade begäran som kontroll. Håll ny V2-väg opt-in, bevara
pris-/policykrav och legacy-standard. Samtidigt är nästa källkomplettering
ren limejuice samt ätlig mängdbasis för ingefära/ansade grönsaker; åtgärda
C:s precisa brödkrav separat. Ingen mer identisk veckotimeout behövs innan
en konkret ändring finns.
