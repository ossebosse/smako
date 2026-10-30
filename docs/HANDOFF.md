# 2026-10-30: Samlad CI-överblick för varor och recept

Starta i [COVERAGE-OVERVIEW.md](COVERAGE-OVERVIEW.md). Det nya obligatoriska
jobbet `coverage-overview` ger Summary, JSON, regressionsjämförelse och
produkt-CSV med faktiska produkt→receptkopplingar. Ingen serverkod aktiveras.
PR50 följer införandet. Baseline är 2 200 ursprungliga import-ID:n; hela
aktuella biblioteket mäts dessutom. Oprövade produkter och tidsgränser är okända,
inte avvisade eller lyckade. Samma antal lyckade recept får inte dölja förlorade ID:n.

Referensen är Malmöpriser 23 oktober/fakta 28 oktober, 89 458 produktposter,
inte aktuell beta eller den senare Stora Coop-kopplingen. Första fulla lokala
och hosted körning gav 1 142/2 024 insatslösta och 1 140/2 024 hela importerade
korgar (exakt/uppskattning), utan förlorade original-ID:n. Produktkandidater:
3 425/3 891. Uppskattat läge: 22 505 observerat stoppade och 63 062 ännu ej
visat användbara poster. Läs scope och kod-SHA innan talen återanvänds.

Prestandadokumentet föreslår separata kalla och varma menyprov med nya val,
kö/förberedelse/checkout/audit/sparning/återläsning. Täckningsjobbets väggtid
är inventeringstid, inte tid till levererad veckomeny. Referensbyte och
baselinebyte ska granskas; regenerera aldrig baseline för att tysta röd CI.

# 2026-10-29: Syd-baspriser hos tre Stora Coop, aktiverat

Se [aktiveringen](releases/stora-coop-syd-base-20261029/ACTIVATED.md).
Stora Coop Lund (2696), Forum Jägersro (3850) och Stadion (3853) har vardera
11237 baspriser från Online Syd och 454 egna kampanjposter. Mindre Coop/X:-tra
är oförändrade. Butiksvalens källmärkning och verklig varusökning är verifierade.
App och scheduler `source-ops-8a53beb80e43`; PR47–49 och slutlig main-CI gröna.
Faktaläsaren följer samma exakta källprodukt för ingredienser och näring.
Versionspolicyn ger distinkta laddade pris-ID:n i båda kommunerna.
Backup `20261029T211156Z`, tidigare användarrader och mountar verifierade.
Recept-/checkoutregler och tvånattspolicy består. Äldre journaler är historiska.

# 2026-10-29: Återstående Coop-källfel rättade och laddade

Se [aktiveringsjournalen](releases/coop-remaining-sources-20261029/ACTIVATED.md).
App `source-ops-2600390d3943`, scheduler `source-ops-47b1f0fdb717`; PR 44–46 och slutlig main-CI är gröna.
Fyra Malmö-källor är verifierat tomma med lyckad kontroll/noll fel och nästa måndag 03:17.
Lunds Online Syd har en färskt kvalificerad/laddad fullkatalog med 11237 produkter.
Malmös befintliga butiksscope består. Okända kampanjgränser och motstridiga typsammanfattningar
ger baspris; flerpackets styckgräns räknas till hela köpgrupper. Tidigare 2925 fysiska
kampanjpriser/källtider och ICA-baspriser består. Källtider från fullhämtningen återanvändes.
Backup `20261029T100721Z`, användarrader, kommunernas laddning och exakta runtimefiler är verifierade.
Recept-/beräkningskod och serverns tvånattspolicy består. Windowsregistreringen återstår
med administratör enligt nedan. Äldre rapporter är historiskt underlag.

# 2026-10-29: Coop environmentalCode rättat, tio butiker uppdaterade

Se [aktivering och butiksresultat](releases/coop-environmental-code-20261029/ACTIVATED.md).
Main-merge `d15f5f4ab049`, kod `1d092bc85f91`,
grön PR-CI. Både app och scheduler använder `source-ops-1d092bc85f91`.
Färska kampanjpriser är publicerade/laddade för fyra Lund- och sex Malmöbutiker;
dashboardens insamling visar succeeded, failed_attempts=0, totalt 2925 priser.
Parser v7 bevarar endast granskad `environmentalCode="A"` som opak metadata;
prisbyggarens versionslista och kvalificeringens felmetadata följer v7.
46 offline- och 36 ytterligare tester är godkända, båda bilderna verifierade.
Backup `20261029T060304Z`, tidigare användarrader och mountar
verifierade; retention complete. Receptmetodhash och tvånattspolicy består.

Separata Coop-fel återstår för Malmö Central, Kornettsgatan, Djupadal,
X:-tra Nydala samt Online Syds katalogkontrakt. Online Syd är fortfarande
onlinekontext, inte fysiska butikers baspriser. Windowsregistreringen nedan
återstår fortfarande; den ändrades inte av denna release.

# 2026-10-28: Dashboard rättad, Malmö-Willys kvitterat, Coop-källfel kvarstår

Ägarens driftgranskning är dokumenterad i
[aktiveringsjournalen](releases/dashboard-operations-20261028/ACTIVATED.md).
Appkod `fac3a7e021a0`, main-merge `c965426`, har grön PR- och main-CI.
BUILD_ID `app-fac3a7e021a0-9fcadbe1` är aktiv sedan 22:02:31 UTC.
Scheduler `beta-scheduler-2b65533af00d-contracts1` består. Fyra appfiler
patchades mot verifierad faktisk bas; backup `20261028T214850Z`, tidigare
planer/profiler/konton och båda pris-ID:n verifierades. Retention är complete.

Dashboarden visar nu baspriser separat: Gunnesbo 1 926, Clemenstorget 38
(äldre LKG), Caroli 1 213 och Västra Hamnen 1 432. Prispolicyn och nästa
måndag/torsdagstid är rättade. Alla sju Willys-reklamblad får sin befintliga
lyckade körhistorik i vyn. Publikt script verifierades som exakt kandidat;
admin utan inloggning gav 401 och båda kommunernas ready gav nytt BUILD_ID.

Malmö-Willys paket `bbba3548e426` från 28 oktober var redan laddat. Normal
återleverans återställde beständigt kvitto 21:35:49 UTC med `already_active`;
pending_delivery är false, inga nya priser hämtades och källtiderna består.
Lund-Willys senaste katalogobservationer är från 27 oktober. Windowsuppgiften
är fortfarande på gammalt paket/dagligt schema; administratörsskriptet nedan
återstår. Det steget ska inte påstås klart utifrån en lyckad manuell kvittens.

Coop har fortfarande fyra Lund- och sex Malmöbutiker avvisade på
`row.environmentalCode`, samt tre verifierade erbjudandesidetimeouter i
Malmö och separat X:-tra Nydala-fel. Online Syd 730400 har äldre kvalificerad
LKG och schemafel kring kampanjernas maxantal. Ingen prisgrind har sänkts.
Fortsatt källrättning behöver belägg för nya fält, negativt prov och pinnad
runtime; använd befintliga driftlås och källvägar. Se exakt underlag i journalen.

# 2026-10-28: Samlad beta aktiverad på servern, Windowsregistrering återstår

Ägarens beställda Malmö ICA, tvånattspolicy och hela det integrerade
recept-/beräkningsarbetet är nu aktiverade på servern. Se
[aktiveringsjournal och slutprov](releases/beta-ica-recipes-20261028/ACTIVATED.md).
Slutlig appkod `f596e1102fd7`, main-merge `45fa207`, har grön CI. Appen kör
`app-f596e1102fd7-09770600` sedan 21:04:28 UTC; slutlig scheduler kör
`beta-scheduler-2b65533af00d-contracts1`. 2 462 aktiva varianter och 66
granskade ingrediensdeklarationer ingår i vanlig faktaladdning.

Malmö har 24 officiella fysiska ICA-butiker och två kvalificerade Primat-
baskällor: Caroli och Maxi Västra Hamnen, 2 645 insamlade produktposter.
Lund har färska Gunnesbopriser och kvalificerad LKG för Clemenstorget, vars
aktuella Primat-täckning är offers-only. Ursprungliga källtider består.
Båda kommunernas nya pris-ID:n är publicerade och bekräftat laddade via
publik scoped readiness. Servern hämtar aktiverade källor måndag/torsdag 03:17
svensk tid; kvartskontroller gäller även lokala övergångar, inte daglig hämtning.

Första schedulerpaketet bevarade äldre modellavvikelser. Fullständiga
prisbyggen hittade detta innan felaktiga priser kunde publiceras. Fyra
redan granskade main-filer korrigerades; båda fullständiga byggen passerade
utan nätverk med 2 CPU/3 GiB. En cronuppstartsrace återställde ett första
byte; slutligt byte väntar på rätt jobb och bevarade appens container-ID,
profiler och planer. Senaste verifierade releasebackup: `20261028T205455Z`.

Windows fullpaket `2b65533af00d` är installerat och kontrollerat, men UAC
avbröts och S4U-registreringen kräver administratör. Uppgiften använder
fortfarande `2464596b6f07` och äldre starttider. Nästa operatör ska köra det
förberedda `.local/beta-all-20261028/activate_windows_admin.ps1` som
administratör och verifiera faktisk XML/03:17 måndag-torsdag. Ett pågående
reläjobb ska få avslutas. Installerat paket är inte registrerat veckoschema.
Skyddat återupptagnings-/verifieringsunderlag finns i `.local/beta-all-20261028/`.

Kompletterande appändring i PR41 förbereder det gemensamma V2-underlaget
automatiskt efter uppstart och prisreload, inklusive portioner 1–4. Den är
aktiverad och exakt kandidat passerade normal uppstart för båda städerna
på 191,98 s med 2 CPU/3 GiB, noll syntetiska planer/profiler och noll nätanrop.
Lund/Malmö gästprov på första appbilden passerade
50,45/53,02 s med tre recept/två portioner och reviderad hel korg efter manuell
gemensam förberedelse; första kalla Malmöprovet var ofullständigt vid 60,48 s.
Den historiska täckningen 2 024/2 200 är fortsatt en fryst referensmätning,
inte ett nytt mått på full täckning med dagens priser eller alla användarval.
Slutlig app gav godkända publika gästmenyer i Lund/Malmö på 50,89/52,36 s,
med helkorgsrevision och identisk återläsning. Första Lundprovet efter bytet
var ofullständigt vid 64,34 s; orsaken är inte fastställd. Det räknas inte
som lyckad kall latens. Ingen manuell förberedelse kördes efter sista bytet.
Ordinarie retention är complete och egna inaktiva diagnostikkopior är
pensionerade under driftlåset efter verifierad backup. Windowsregistreringen
är den kvarvarande aktiveringsåtgärden; se journal och sekretessrensad
[EVIDENCE.json](releases/beta-ica-recipes-20261028/EVIDENCE.json).

# 2026-10-28: Två insamlingsnätter och ICA Primat förberett, aktivering återstår

Historiskt granskningsläge 15:25 UTC; serverstatus ersätts av aktiveringen ovan.

Ägaruppdrag: aktivera ICA-baspriser via Primat och hämta alla aktiverade bas-
och kampanjkällor nätterna mot måndag/torsdag. PR #37 är integrerad på main
`49be2f6`, granskad kod/paket `3ebff6ab6e33`, med grön hosted CI i alla tre
testdelar. Se [förberedelsejournalen](releases/ica-twice-weekly-20261028/PREPARED.md)
och [körpolicyn](PRICE-COLLECTION.md). Källtider, kampanjdatum och åldersvarningar
bevaras. Ingen aktivering får påstås utifrån main eller installerat paket.

Serverförsöket avslutades 15:25 UTC med upptaget ordinarie driftlås efter
avgränsad väntan; den aktiva insamlingen från 14:45 fick fortsätta.
Inga live Primat-anrop eller serverbyten gjordes. Windows nya relä är installerat
och integritets-/importkontrollerat separat, men UAC-dialogen avbröts och
uppgiften använder fortfarande 2464596b6f07 med sitt tidigare schema.
Allt återupptagningsunderlag finns i `.local/ica-twice-weekly/`; ingen väntande
aktiveringsprocess lämnades igång. Återuppta först efter ny drift-/uppgiftskontroll
och bekräfta faktiska bilder, cron, båda kommunernas ready och Windowsregistrering.
Endast två ICA-baspriskontexter i Lund är idag verifierade i registret;
Malmö saknar ännu sådana kopplingar. Nya källfakta får inte fabriceras.

# 2026-10-28: Fem största grupperna lösta med befintliga butiker

[Rapport](reviews/top-five-ingredients-20261028.md): 2 024/2 200 hela
uppskattningskorgar, +160; 176 kvar. Exakt 1 142 insatslösta/1 140 hela,
+74 hela. 192 uttryckliga receptversioner och 24 exakta befintliga
produktrelationer löser tamarindpasta, masa harina, citrongräs, pärlkorn
och klibbigt ris. 32 berörda varianter har andra hinder. Alla original,
2 462 aktiva varianter och tidigare korgar består. Inga nya handlare/priser.
Alternativen är författade och inte provlagade; okända personliga fakta består.

A 278.76/278.76, hela B2 identisk 731,20.
API 53.72/52.47/32.63 s.
Alla 3166 kvittofiler verifierade. 335 riktade tester,
Ruff/compileall; alla 4258 CI-noder exakt en gång, 4 202 gamla bevarade.
450 ytterligare tester verifierar uppdaterade historiska versionskedjor.
Grön hosted CI krävs före integration. Offertkopiering och nyckelberäkning
snabbas upp utan ändrade priser, krav eller sökbudget.

Aktuella fakta och slutprov: .local/top-five-ingredients-20261028/
facts-reviewed-v1.json respektive final-v3. Samma obegränsade journal,
en tung arbetare, två CPU, 3 GiB. Fortsätt återstående 176 via befintliga
butiker och granskade alternativ; återuppta inte den externa källpiloten.
Ingen produktion/beta/scheduler/profil ändras.

# 2026-10-28: Nya nätbutiker stoppade, befintliga alternativ först

Ägaren har återkallat spåret med externa nätbutiker. PR #34 är stängd utan
merge; inga nya handlaridentiteter eller pilotinsamlare integreras i main.
Källgranskningen och dess råunderlag bevaras på den stängda arbetsgrenen.
Ingen prisaktivering, produktionsändring eller fraktimplementation gjordes.
Samma budgetjournal behåller även pilotens förbrukning.

Arbetsordningen för samtliga kvarvarande varor är nu uttrycklig:
kontrollera först alternativ i befintliga butiker och om Smako har sorterat
bort en lämplig produkt. En ny butik får bara övervägas när fysisk butik
och nätpublicerade butikspriser för rätt butik är verifierade. Ett separat
online-/fraktpris uppfyller inte det kravet. Ingen befintlig Coop-onlinekontext
får döpas om till fysisk hyllprisdata.

Kontrollera Hemköps Maizena artikel 100181152_ST mot receptens behov av
masa harina, och granska pärlkornsalternativ via befintligt sortiment och
Smakos faktiska sök-/klassningsbeslut. Kulinariskt olika ersättningar kräver
tydlig receptversion med granskade mängder och tillagning, inte falska alias.
Tidigare 1 864 hela korgar och nämnaren 2 200 består.

[Genomförd granskning](reviews/existing-store-alternatives-20261028.md):
Maizena 100181152_ST finns i nio kontexter och samtliga godkänns för
majsstärkelse; den är inte masa harina. Frebaco Kornris 101364286_ST /
7312560036232 finns redan i fem katalogkontexter med pris och två separata
fysiska Coop-erbjudanden. Granskningsregexen missade ordet kornris och är
nu rättad. Ingen automatisk ingrediens- eller prisauktorisering införs.
421 riktade tester samt Ruff/compileall passerar. Runtime och matdata är
oförändrade; pre-pilotens exakta metodhash 1bd67745a63fbcac37fda42e641f304b6e125f1f81e084651a61c36d411d9e83
är återställd efter två rena radslutsskillnader vid branchbytet.

Nästa konkreta kvalificering är Frebacos kornris i befintliga kontexter:
tillverkaren anger lätt polerat korn och 13–15 minuter i rikligt vatten;
vissa av de 27 aktuella recepten anger 30–40 minuter och absorption.
Granska hela formen och anpassa tillagningen i tydliga receptversioner där
det behövs innan nya korgar räknas. Korngryn och matvete finns också som
redan understödda alternativ. Ingen extern källpilot får återupptas.

# 2026-10-28: 1 864 hela korgar med verifierade hela majskolvar

[Rapport](reviews/whole-corn-20261028.md): +2 i båda lägen; 1 068 exakt
insatslösta/1 066 exakt hela, 1 864 inklusive uppskattningar, 336 kvar.
Två uttryckliga frysta receptversioner, en kolv per portion och exakt
två kolvar per befintlig Findus 400 g-artikel. Grossgram och antal hålls
isär i befintlig resolver och skafferijournal. Ingen ätlig massa/näring
antas. Alla original och tidigare korgar bevarade; inga nya priser.

A 278.76/278.76, B2:s hela korg identisk 731,20.
API 53.47/53.70/32.36 s; alla 2932 kvittohashar passerar.
595 riktade tester, Ruff/compileall. Alla 4201 CI-noder exakt en gång,
4 170 tidigare bevarade. Hosted CI krävs före integration.
PR32 integrerad 8270a9f med grön CI 7:44 mot tidigare 8:30.

Fortsätt mot alla 2 200. Slutfakta och prov i
.local/additional-source-review-20261028/facts-reviewed-v1.json och final-v3.
Mung/belugastudien ännu inte kvalificerad; exakt organisk mungkomplettering
väntar på främmande aktiv serverlease. Ny källpilot har uppdaterat
beslutsunderlag men inväntar beslut. Samma obegränsade journal och
resurs-/operationskrav; ingen produktion/beta/scheduler/profil ändras.

# 2026-10-28: PR31 integrerad, snabbare verifiering under arbete

PR #31 är integrerad på main `84c39008b3dc15a5262a0f372070a40866aeb271`.
Alla 4 170 hosted testnoder passerade utan fel, 63 historiska data-skippar,
510 sekunder. Samtliga leveranshashar verifierades efter integration.
Aktuella [CI-förbättringar](reviews/ci-balance-20261028.md) bevarar hela
testurvalet och alla skalningskontroller. Runtime/data är oförändrade;
PR31:s hashstabila korgverifiering återanvänds. Hosted CI måste passera
även för den nya testindelningen innan den integreras.

Fortsätt mot alla 2 200; fortsatt 1 862 hela inklusive uppskattningar och
338 kvar. Nio kokta mungböns-/linsvarianter har en ny primärstudie, men
produktanvisningarnas beredning skiljer sig och gross/rensad torr massa
måste hållas isär. Se tillämpningsgranskningen i CI-rapportens underlag.
Ingen ny beredning är aktiverad. Ny källpilot inväntar fortfarande beslut.
Samma obegränsade journal och resurs-/operationsgränser; ingen aktivering.

# 2026-10-28: 1862 hela korgar efter exakt granskade tunna risnudlar

[Rapport](reviews/thin-rice-noodles-20261028.md): +0 hela inklusive
uppskattningar, exakt 1066 insatslösta/1064 hela och 338 kvar.
Alla original, 2 462 aktiva och tidigare korgar består. Två exakta 400-g-artiklar
i 14 befintliga kontexter; inga nya priser, recept eller runtimeändringar.
Tunna torra nudlar kvalificeras separat från breda/runda. Näringskonflikten
bevaras, okända personliga fält och näringsvärden består.

A 278.76/278.76 kr, B2:s hela korg identisk 731,20 kr.
API 52.01/51.96/33.19 s.
Alla 2928 kvittohashar verifierade. 72 riktade tester, Ruff/compileall;
4170 CI-noder exakt en gång. Grön hosted CI krävs före integration.
PR #30 är integrerad 3eef049, grön CI 4 151 tester utan fel på 8:54.

Fortsätt mot alla 2 200. Aktuella fakta och slutprov finns i
.local/remaining-source-review-20261028/facts-reviewed-v1.json respektive final-v1.
Samma obegränsade journal, resurs- och källkrav. Ny källpilot inväntar beslut.
Ingen produktion/beta/scheduler/profil ändras.

# 2026-10-28: 1862 hela korgar, uppmätta myntablad

[Slutrapporten](reviews/mint-leaf-preparation-20261028.md) ger 32 nya hela
korgar inklusive uppskattningar. Exakt 1066 insatslösta/1064 hela,
338 insatshinder kvar. Alla original, 2 462 aktiva och gamla korgar består.
40 separata versioner plockar och väger blad. Begränsad primärstudie och
oberoende grovrensningsreferens används uttryckligen som inköpsuppskattning;
tio exakta befintliga källkontexter, inga nya priser eller bladnäringsantaganden.
Samma gemensamma inköp och journal bokför uppmätt råinsats, blad och svinn.
Kort utbyte stoppar förbrukning. Verkligt källprov klarar delat köp, halv
förbrukning, omräkning utan nya köp och oförändrad historik med skafferi av.

A 278.76/278.76 kr, B2:s hela korg identisk 731,20 kr;
API 51.98/53.72/32.45 s.
2928 aktuella kvittofiler verifierade. 74 riktade tester, båda browsermotorer,
Ruff/compileall, 53 ytterligare optimerarprov och 4151 CI-noder exakt en gång. Grön hosted CI krävs före integration.
PR #29 är integrerad ebf4f48, grön CI 4 134 tester utan fel på 8:08.

Fortsätt mot samtliga 2 200. Oförändrad fryst Malmöreferens och fakta-v3;
samma obegränsade journal/resurs-/operationsgränser. Separat källpilot är
inte aktiverad. Ingen produktion/beta/scheduler/profil ändras.

# 2026-10-28: 1 830 hela korgar och oförändrad exakt prisväg

[Slutkontrollen](reviews/plain-food-facts-20261028.md) ger +2 i båda lägen:
1 066 exakt insatslösta/1 064 hela, 1 830 inklusive uppskattningar, 370 kvar.
Alla original, 2 462 aktiva och tidigare korgar består. Nio exakta Garant
frysta edamamebaljor kvalificeras för receptens grossvikt. Vanligt Atair-
pektin avvisas efter full stegläsning: gult högmetoxylerat konfektpektin krävs.
Alla andra fakta och befintliga personliga/näringsfält består.

Befintlig anropscache återanvänder exakt fastpaketsmetadata efter ordinarie
mängdresolver/köpgräns; 156 920 fulla offerter identiska, isolerad median
6,517→6,089 s. A 278,76 kr i två nya ägare, API 53,66/53,70 s;
B2:s hela korg identisk 731,20 kr, 32,78 s. 2 896 kvittofiler verifierade.
78 riktade tester, Ruff/compileall passerar; 4 134 CI-noder exakt en gång.
Grön hosted PR-CI krävs före integration. PR #28 redan integrerad fb94b67,
hosted 4 121 noder utan fel på 8:06. Slutfakta och aktuellt metodhash i rapporten.

Fortsätt mot alla 2 200. Risnudelkön saknar ännu serverlease; inga anrop eller
låsövertaganden. Ny källpilot har separat beslutsunderlag, ingen aktivering.
Samma obegränsade journal, en tung arbetare, två CPU och 3 GiB består.

# 2026-10-28: 1 802 hela korgar, ytterligare +18

[Rapport](reviews/product-facts-20261028.md): exakt 1 062 hela/1 064
insatslösta och 1 802 inklusive uppskattningar. 398 insatshinder kvar.
Alla 2 200 original, 2 462 aktiva och tidigare korgar består. 19 nya
exakt granskade relationer: Garant platta torra risnudlar, Eldorado
sardiner 120/85 g och Ahmad Tea osmaksat Ceylon-löste 500 g. Inga priser
eller recept ändrade. All annan fakta/personliga fält består; sardinernas
avrunna näring är okänd. Torrt-form-undantaget kräver exakt granskad relation.

A 281,31 kr i båda slutprov; B2:s hela korg identisk 731,20 kr.
API/save/GET 52,04/53,76/32,36 s, separat förberedelse 96,31/75,83/76,33 s.
Alla 2 866 kvittohashar och aktuella beroenden passerar. Metod
249dbc07d415409a312427445504480a2e6dd5580ac267acfab9f9b6f1af65b3.
Fakta: .local/coverage-next-20261028/facts-final-v2.json,
SHA b56734ee54f2453c5e14bb1cbd38a1404ddd4a201259c51a15a88bfda09765e3.
Slutproven finns i .local/coverage-next-20261028/final-v2; tidigare
underkänt A-återprov bevaras i dess överkatalog. 338 riktade tester samt
Ruff/compileall passerar. Full klassning är identisk för alla 89 458 produkter
med två begränsade rena textcacher. CI har tre obligatoriska partitioner,
4 103 noder exakt en gång; green hosted PR-CI krävs före integration.
PR #26 är redan integrerad / main 5c329aa, hosted 4 100 tester utan fel.

Fortsätt med återstående mängd-/sortimentsbevis och gemensam äggberedning.
Stjärnäggs 1-kg-vikt är styrkt, men ofullständig och motstridig sammansättning
är inte godkänd. Källa och exakt scope behövs före ny handlare/allowlist.
Ägaren har ingen total tidsgräns; samma journal och resurs-/operationslås.
Ingen produktions-/betaaktivering, legacy standard och V2 opt-in.

# 2026-10-28: Ytterligare 37 hela receptkorgar verifierade

[Rapport](reviews/reviewed-drained-foods-20261027.md): 1 784/2 200 hela
korgar inklusive uppskattningar, exakt 1 049 hela/1 051 insatslösta.
416 kvar; alla original, 2 462 aktiva och tidigare korgar består.
Två Falkenbergräkpaket och Monte Castello kronärtskockshjärtan, Sevan vinblad
samt Stollenwerk surkål har exakta granskade produktrelationer och avrunnen
massa i CityGross Malmö. Ingen recept- eller prisändring. Vinbladens
omstridda näring förblir okänd och uttryckligen konfliktmärkt.

A 281,31 kr i båda nyägarproven; B2:s hela korg identisk 731,20 kr.
API/save/GET 52,00/52,16/32,58 s, separat förberedelse 97,53/76,23/77,77 s.
Alla 2 835 kvittohashar och aktuella beroenden passerar. Metod
1e6bd1c73f31acef2a4f4384d118084643346c1357c8267acda0e4c02e24fe92.
52 riktade slutregressioner, Ruff och compileall för fyra Pythonfiler passerar;
4 100 CI-noder exakt en gång. Integration kräver grön hosted PR-CI.

Fortsätt mot alla 2 200 med kvarvarande faktaluckor och gemensam äggberedning.
Aktuell lokal faktafil är .local/recipe-shrimp-review-20261027/facts-final-v2.json,
SHA f3d272dd0978101582386c3aeba92a1705a3126355af73494cbb1aba6ce4ad39.
Senaste driftstatus visar fortsatt äldre kvalificerad Coop Online Syd-bas och
öppen kvalificeringsincident 875e4d32e7da4aa0a8f4f388edea5747; diagnos ska
använda ordinarie reproduce, aldrig sänkt grind eller breddad allowlist.
Ägaren har ingen total tidsgräns. Samma journal, en tung arbetare, två CPU,
3 GiB, watchdog och operationslås består. Ingen produktions-/betaaktivering.

# 2026-10-27: Fortsatt täckning och halverad CI

[Rapport](reviews/coverage-continuation-20261027.md): 1747/2 200 hela korgar
inklusive uppskattningar (+30), exakt 1020 hela/1022 insatslösta.
453 återstår; alla original/2 462 aktiva och tidigare korgar består.
32 nya exakt granskade Axfoodkopplingar samt två Spicefieldetiketter följer
befintlig fakta-/mängdväg. 40 nya offentliga artikeldokument, 244 kompletterade
produktposter och inga faktakonflikter. Fem sammansättningsdeklarationer har
manuellt verifierad fullständighet; personliga egenskapskrav består.

A 281.31 och återprov 281.31 kr, B2:s hela korg identisk
731.20 kr. API/save/GET 51.86/52.17/32.25 s.
Statisk spärrfrasscope återanvänds; alla 89 458 produkters fulla klassningssvar
är identiska. Ny full kontroll och 2769 kvittohashar passerar.
Metod 52aeb5a649d98e38760aaa35b71ee850154712870d52e67b010c694eb7031554. 312 riktade tester, Ruff/compileall passerar.
Integration av täckningsändringen kräver grön PR-CI. CI-förbättringen är redan
integrerad via PR #24 / main e68627f: 9:50 mot 20:35, alla 4 069 tester ingår.

Ägarens senaste beslut är fortsatt arbete utan total tidsgräns. Samma journal
har null som total gräns, med all historik kvar; watchdog, en tung arbetare,
två CPU, 3 GiB och operationslås består. Ingen produktions-/betaaktivering.
Fortsätt med räkdeklarationernas varav-gram-parser, gemensam äggberedning och
övriga verkliga mängd-/sortimentsluckor. Ingen ny handlare/allowlist utan
separat konkret käll-/scopebeslut. Legacy standard, V2 opt-in.

# 2026-10-27: Fyravarugranskning klar — prisgrinden åter godkänd

[PR #23](https://github.com/ossebosse/smako/pull/23), från main `8dac239`.
[Slutrapporten](reviews/recipe-four-staples-20261027.md) ersätter den
underkända kontrollpunkten nedan. **1 717/2 200 hela korgar inklusive
uppskattningar**, +68; exakt 1 008 hela/1 010 insatslösta. Inga förlorade
korgar, samtliga original och 2 462 aktiva varianter kvar. 483 varianter
återstår; detta avslutar fyravarugranskningen, inte målet om full täckning.

91 generiska myntavarianter har granskade nya versioner för ansade blad och
mjuka stjälkar. Tio exakt bundna 25-g-poster använder källbelagda 85 procent
som uttrycklig uppskattning. 40 bladkrav är oförändrade. Ägarens två
Lundprodukter är separat verifierade; Coop 730400 förblir Online Syd.
Tamarind saknar belagd massa/koncentration; masa harina och pärlkorn behöver
exakt prissatta produkter av rätt form. Se rapportens konkreta källspår.

Sökningen beräknar statisk prioritet en gång per måltidsplats. Ordning,
krav, deadline och tolv sekunders slutreserv består. A **281.31 kr**
(tidigare 283,24), separat nyägarkörning **281.31 kr**; B2:s hela
korg oförändrad **731.20 kr**. API/save/GET 52.05/
52.16/33.41 s; separat förberedelse redovisas i
rapporten. Ny full bibliotekskontroll och 2 727 kvittohashar passerar.
Metod `70c233f8440dac886eeb8644da1e4583bb373e968e58c91e3e919001a81cefb5`.
530 unika riktade testfall, Ruff och compileall passerar. Integration sker
via PR efter grön CI; det tidigare A-stoppet är löst, inte undantaget.

Ägaren godkände +900 s och slutförande. Samma journal: **3991.5507 s använda,
508.4493 s kvar av 4500 s**. Ingen återställning av budgeten.
Legacy är standard, V2 opt-in. Ingen beta-/produktionsaktivering,
handlarinsamling, allowlist-, profil- eller schedulerändring.

# Historisk kontrollpunkt 2026-10-27: +68 korgar, då stoppad av A-pris

Arbetsgren `fix/four-ingredient-review-20261027`, från main `8dac239`/PR #22.
Se [granskningen](reviews/recipe-four-staples-20261027.md). **1 717 av 2 200**
hela korgar inklusive uppskattningar är verifierade, +68; exakt oförändrat
1 008 korgar/1 010 insatslösta. 483 varianter/68 grupper återstår.
Alla 2 200 original-ID:n och 2 462 aktiva varianter består, inga förlorade korgar.

91 ursprungliga generiska myntarecept har nya versioner med ansade blad och
mjuka stjälkar, samma ätliga gram och en extra aktiv minut. 40 uttryckliga
bladrecept är oförändrade. Matvaretabellen 06.259:s 85% ätliga andel är enbart
uppskattad och bunden till tio exakta 25-g-produktkontexter. Hemköp Karhögstorg
och Coop Online Syd i ägarens två länkar finns redan i Lundunderlaget och
är separat kontrollerade; Coop 730400 är fortsatt online, aldrig fysisk hyllpris.
Tamarind 435 ml finns men saknar verifierad gram-/koncentrationskoppling;
masa harina och pärlkorn saknar exakt kvalificerat prissatt SKU av rätt form.
Tamarind är nu enda ingredienshindret i 63 varianter, masa i 31, pärlkorn i 24.

**Integrera inte denna gren ännu.** Kall A gav 295,41 kr mot tidigare 283,24 kr.
Den tidigare menyn passerar en ny checkout på det nya underlaget för 283,24 kr.
B2:s hela korg är identisk, 731,20 kr. API/save/GET A 51,96 s/B2 33,09 s;
separat förberedelse 100,38/77,84 s. Slutverifieraren kontrollerar alla 2 727
kvitton och sparade begäranden, skriver `price_regression_gate_passed: false`
och avslutar med felkod. Täckningsvinsten upphäver inte prisregressionen.
Nästa kodarbete är att rätta den generella begränsade menysökningen utan
receptnamnsundantag, sänkta krav eller benchmark-frön. Ny runtime kräver
nya aktuella hela-biblioteket- och A/B2-bevis; gamla metodkvitton får inte bytas namn.

504 unika riktade testfall passerar över två körningar; Ruff och compileall
passerar. Ordinarie PR-CI redovisas separat. Metodhash
`c2108182d4c54d3cbe2f362fcba284160eef7a6c5ab3b2cc162cacd6c619e983`.
Samma pris-/faktafil, testklocka, kontexter, portioner och tvåbutikstak består.
Samma etappbudget: **3318.4442 s använda, 281.5558 s kvar av 3 600 s**.
Inget nytt budgetbeslut; kvarvarande tid räcker inte till en ny runtimeändring
med full nödvändig verifiering. Ingen automatisk fortsättning, merge, beta-/
produktionsaktivering eller schedulerändring. Legacy standard och V2 opt-in.

# 2026-10-27: Fortsättning — 1 649 fullkorgar och bevarat A/B2

Se [kontrollpunkten](reviews/recipe-weight-coverage-20261027.md), från main
`e8520bf`/PR #21. Ordinarie källbelagt kilopris kan nu användas för äldre
viktvaror vars erbjudande saknar verifierad rabattgränsenhet. Rabattens
villkor ligger kvar och tillämpas inte. Hela paket, explicit uppskattningsval,
känt mängdunderlag och uppmätt privat skafferiköp krävs fortfarande.

**1 010 exakt/1 649 inklusive uppskattningar är insatslösta; verifierade
hela tvåbutikskorgar är 1 008/1 649**, +0/+3 och inga förlorade korg-ID:n.
Alla 2 200 importerade och 2 462 aktiva varianter består. Samma pris-/faktafil,
52 kontexter, klocka, portioner och butikstak. Metodhash
`44adc0cb5d91d875b2d8d2d94ef85eabebce0a5e6bfb8f4b03c95860f98557ff`; 2 659 kvitton är kontrollerade.

**A 283,24 kr/52.19 s, B2 731,20 kr/34.55 s** API/save/GET.
Fulla begäranden är oförändrade och B2:s hela korg identisk. Separat
förberedelse 97.46/76.40 s. Ingen generell latency- eller optimumgaranti.
De två exakta avslagen kräver minst tre butiker efter giltiga mängdköp;
diagnostiska trebutikskorgar passerar, men räknas inte in i tvåbutiksmåttet.

**551 varianter/68 grupper återstår.** Alla 74 namn har också granskats i
ett separat kvalificerat Willys Malmöarkiv från 2026-10-27 utan nya lösta
faktahinder. Ett återförsök till den godkända 44-artikelskön stannade vid
upptagen lokal lease med noll handlaranrop. Berednings-/skafferiarbetet och
faktaluckorna i uppdraget kvarstår. Ingen delvis implementerad beredning är aktiv.

644 riktade regressioner plus ett nytt skafferifall passerar; slutlig ny
suite 28/28, Ruff och compileall passerar. Ordinarie PR-CI krävs före merge.
Samma etappjournal: **2417.2708 s använda, 1182.7292 s kvar av 3 600 s**.
Tidigare journaler/prefix är bevarade. Ingen automatisk fortsättning eller
produktion/beta/schedulerändring; legacy standard och V2 opt-in.

# 2026-10-27: Astra-kontrollpunkt — 1 646 fullkorgar och A 283,24 kr

Från main `9992d34`, se [uppdraget](CODEX-ASTRA-FULL-COVERAGE-20261027.md)
och [resultatrapporten](reviews/recipe-coverage-full-20261027.md).
Alla tidigare 76 grupper/595 varianter är granskade i en komplett arbetsmatris.
**1 010 exakt/1 646 inklusive uppskattningar är insatslösta; fulla verifierade
tvåbutikskorgar är 1 008/1 646**, +11/+41 utan förlorade original-ID:n.
Alla 2 200 importerade och 2 462 aktiva varianter är bevarade. Två tidigare
exakta checkout-avslag kvarstår; inga okontrollerade sökningar räknas som klara.

Fem exakt produktbundna leverantörsdeklarationer, explicit styckpaketmassa/
grampaketvolym, 18 fruktrelationer med källbundet uppskattat utbyte och
16 granskade köttrelationer använder befintlig mängd-/faktaarkitektur.
Prisfilen med 89 458 produkter/52 kontexter, klockan, portionsvalen och
tvåbutikstaket är oförändrade. Inga priser eller källtider har förnyats.
Slutfakta: `.local/recipe-coverage-full-20261027/facts-final-v2.json`, SHA
`30fd1d335bc43c4c67fad89aebcece4ae970106268b9a7cf8a64fa5cbb1ae0cd`.
Metodhash: `45431ee57444ceb60c7ae64d4c43783412990fa00d432add821b2f22f911234c`.
Samtliga 2 656 kvittofiler och aktuella beroenden är hashkontrollerade.

Generell omprövning av receptbyten efter förbättrad gemensam korg löser det
tidigare A-prisgapet i samma fullständiga sparade begäran: **283,24 kr,
52,04 s API/save/GET**, mot 317,82 kr och den verifierade referensen 290,82 kr.
**B2:s hela korg är identisk, 731,20 kr, 32,56 s.** Separat förberedelse är
98,10/76,12 s. In-process Windowsprov på två CPU/hårt 3 GiB; inget globalt
optimum, browsertransport eller allmänt prestandagodkännande påstås.

**Full täckning är inte klar: 554 varianter/69 grupper återstår.** Dokumenterad
äggdelning behöver fortsatt implementation av samköp, utfall, näring och
skafferibokföring i befintliga modeller; ingen halvfärdig beredning är aktiv.
Mungbönor och kaffe saknar verifierat massa-/slutvolymutbyte. Fyra exakt bundna
hela oxfiléartiklar stoppas fortfarande av viktprisavtalet i tre recept:
kilotaxan får inte behandlas som paketpris. Detta är tekniskt arbete, inte
ett ägarbeslut att sänka kraven. Nästa åtgärder och verkliga käll-/scopegränser
finns i uppdraget och arbetsmatrisen. Tre försök till samma tillåtna 44-artikelskö
stannade vid upptagen serverlease med noll handlaranrop; inget lås kringgicks.

640 riktade tester samt fyra ytterligare köttgränsfall passerar, liksom Ruff
och compileall. Ordinarie PR/CI krävs före integration. Separat etappjournal:
**1 311,3678 s använda, 2 288,6322 s kvar av 3 600 s**; äldre journaler är
orörda och inget överfört/nollställt. Detta är första granskningsbara
kontrollpunkten, inte uttömd budget eller slutleverans av full täckning.
Ingen automatisk fortsättning. Legacy är standard, V2 opt-in; ingen
beta-/produktionsaktivering eller schedulerändring.

# 2026-10-27: Fortsättning levererad — mängdspärr och 1 605 fullkorgar

Läs [rapporten](reviews/recipe-coverage-followup-20261027.md) och
[samtliga 2 200 utfall](reviews/recipe-coverage-followup-20261027/coverage.json).
Från main `4093d33`: separat mängdrättning `cac2a91`, samlad runtime/data
`e8c58ef`. Den granskade projektionen och efterföljande kvalificering använder
nu samma `_mass_blocking`-policy. Reproducerade `nutrition.package_quantity`
och okända `nutrition.*`-konflikter stoppas även efter uppvärmd cache.
Normal uppskattning utan full näringsfakta och rena näringskonflikter hålls
isär; motstridig näring blir inte godkänd näring för personliga krav.

**Individuellt lösta 999 exakt/1 605 inklusive uppskattningar**, +30/+36
mot PR #19, inga förlorade ID:n. **Fulla verifierade tvåbutikskorgar 997/1 605.**
Två exakta checkout-avslag kvarstår. Alla 2 200 kontrollerade utan avbrott;
606 kräver estimated för insatsstöd och 608 korgar är bara verifierade där.
Samma fasta Malmöprisfil, 52 kontexter, portioner och tvåbutikstak används.

Nio exakta GTIN-/förpackningsrelationer för Galbani mozzarella får Dabas-
deklarerade 125 g avrunnen mängd, inklusive åtta produktbundna, exakt
mängdangivna och variantupplösta ICA-erbjudanden med oförändrad checkout.
Åtta gramförpackade romansalladsrelationer får USDA SR28/11251-utbyte 94 %
enbart i uttryckligt estimated. Inga recept eller priser har skrivits om.
Fakta-SHA `4f808c14e8bc8ab3e3719805ee59a2a2257b7953271ba56d346ed764fafe4cd3`.
Metodhash och samtliga 2 604 kvittohashar finns i rapportpaketet; fulla kvitton
och fakta är lokala under `.local/recipe-coverage-followup-20261027/`.

**100 procent är inte klart:** 595 varianter/76 grupper återstår i estimated.
Mynta 131 (92 med bara den gruppen), tamarindpasta 93/53, masa harina 31/31,
pärlkorn 27/24. De är villkorade marginaler, inte redan uppnådda vinster.
Exakta nästa källåtgärder och alla sällsynta grupper finns i blockerlistan.
Myntabladens användbara vikt/utbyte saknas; tamarindkoncentratets ml/okända
styrka ersätter inte pasta i g. Vanligt/förkokt majsmjöl är inte styrkt masa
harina. Urtekram har rätt kornform, men inget exakt prissatt SKU verifierades
i den frysta referensen. Nytt sortiment måste få eget deklarerat scope.
Två försök till samma godkända sjuproduktskö avstod vid upptaget kommunrelälås,
med noll handlaranrop. Inget lås kringgicks eller driftläge ändrades.

A/B2 har exakt samma hela sparade begäran; B2 också samma hela **731,20-kr-korg**,
33,7535 s API/save/GET. A ger **317,82 kr på 52,4272 s**, men föregående
receptförslag verifierar korrekt skalat **290,82 kr** i aktuell checkout.
**Prisgapet 27 kr är ett kvarstående releasehinder.** Inget pris-/prestanda-
godkännande eller globalt optimum påstås. Laddning/förberedelse före API:t
101,9719/77,9956 s är separat. Inga nya browsertider eller aktiva 10–15-krav.

487 riktade regressioner, Ruff/compileall passerar; ordinarie CI krävs på
slutligt PR-huvud. Ny separerad 20-minutersjournal: **772,9932 s använda,
427,0068 s (7,12 minuter) kvar**. Källarbete slutade med 948,2167 s kvar,
före slutproven. Peak jobbcommit 1,462 GiB på två CPU, hårt 3 GiB.
Gamla journalen är orörd (7 172,6967/27,3033 s), inget överfört/nollställt.
En full omkontroll/sammanställning kostade 249 s; A/B2 inklusive laddning
cirka 271 s till. Ingen automatisk fortsättning. Prioritera kvarstående
källgap och det verifierade prisgapet; invänta faktisk källa/ledig lease
eller separat sortimentsbeslut. Legacy standard, V2 opt-in, ingen aktivering.

# 2026-10-27: Nästa Sol-etapp — mängdspärr och prioriterade källgap

Ägaren har godkänt nästa steg efter oberoende granskning av PR #19/main
`7c0e066`. Genomför
[COVERAGE-FOLLOWUP](CODEX-SOL-NEXT-20261027-COVERAGE-FOLLOWUP.md).
Först rättas att den nya mängdprojektionen returnerar före `_mass_blocking`:
`nutrition.package_quantity` kringgår spärren i reproducerat isolerat prov.
Normala uttryckligen tillåtna uppskattningar och separata näringskonflikter
ska fortsätta fungera enligt befintlig policy.

Därefter prioriteras mynta, tamarindpasta, masa harina, avrunnen mozzarella
och pärlkorn. Baslinjen är 969/1 569 insatslösta och 967/1 569 verifierade
tvåbutikskorgar av 2 200, med 631 kvarvarande insatshinder. Oberoende
granskning har kontrollerat alla korgkvitton och rätt portioner; 626 riktade
tester passerade. A:s hela sparade begäran och B2:s begäran/korg är jämförda.

Ny separat budget är **20 minuter tunga käll-/verifieringskörningar**, med
tio minuter reserverade för slutprov. Använd
[den nya journalen](reviews/recipe-coverage-followup-20261027/budget.json).
Den gamla journalen bevaras och nollställs inte. Ingen stor matris,
automatisk fortsättning eller driftaktivering. Slutmålet är fortsatt 100 %.

# 2026-10-27: Täckningsdelresultat — 1 569 verifierade tvåbutikskorgar

Läs [rapporten](reviews/recipe-coverage-20261027.md) och dess kompakta
[samtliga 2 200 ID:n](reviews/recipe-coverage-20261027/coverage.json).
Runtime `7697492` från main `be0c528` separerar granskad produkt-/formidentitet
från mängdbevis i befintligt register och kvalificeringsflöde. 139 konkreta
råvarurelationer får dokumenterade utbyten enbart i uttryckligt estimated.
Oförändrad livsmedelsidentitet/sammansättning följer stabil GTIN/artikelkod
över rena prisuppdateringar; aktuell fakta-/priskontext och nytt pris kontrolleras.
22 befintliga Axfood-artiklar granskades, 20 nya verifierade detaljdokument;
Keso/kvarg, limejuice, kapris, jordnötssmör, färsk potatisgnocchi och tonfisk
får fungerande käll-/form-/mängdstöd. Torra durumgnocchi förblir ett negativt fall.

**Individuellt lösta 969 exakt / 1 569 inklusive uppskattningar av 2 200,
+231/+638 och noll förlorade ID:n. Fullt verifierade tvåbutikskorgar
967/1 569.** Två exakta korgfall passerar separat med tre butiker och räknas
inte som tvåbutiksframgångar. Slutkontrollen har inga tidsavbrott/okontrollerade
lösta varianter. 602 korgar är verifierade endast i uppskattningskolumnen;
600 av dem saknar dessutom exakt insatsstöd. Ingen mängdstandard växlas.

**100 procent är inte klart:** 631 varianter har fortfarande insatshinder,
78 grupper. [Blockerlistan](reviews/recipe-coverage-20261027/blockers.json)
ger aktuella scope, berörda ID-index, nästa källåtgärd och hela restmängden.
Prioritera fortsatt täckning: mynta 131 (83 enbart denna grupp), tamarindpasta
93/53, masa harina 31/31, avrunnen mozzarella 30/30, pärlkorn 27/24 och
citrongräs 27/15. Dessa marginaler är övre villkorade antal. Myntakrukans
vikt, tamarindkoncentratets ml eller masalaträffar får inte ersätta saknade
bladutbyten, pasta i rätt styrka/g eller verklig masa harina. Flera sällsynta
SKU:er saknas i det frysta sortimentet; nytt sortiment/alternativ måste få
eget deklarerat scope och behålla originalreferenserna.

Den återupptagbara kontrollen körs genom `budgeted_check.py` med
`PYTHONPATH=backend;.;scripts/recipe_layer`. Kvittorna binder hela lästa
pris-/fakta-/recept-/metod-/villkorsversionen och återanvänds bara vid match.
Första tio avbrotten återupptogs korrekt. Nya fakta fick ny version och
samlad omkontroll. Slutligt detaljarkiv är
`b11ed75863be1547755ee78be5143ba737d5ea3564acc1cadaa0feb6b4ebf0a8` under
befintlig `D:/smako-data/axfood-product-details/releases/`; lokala frysta
fakta och fulla korgkvitton refereras i rapporten. Ingen aktiv källa ändrades.

B2 behåller exakt begäran och hela **731,20-kronorskorgen**, API/save/GET
32,6722 s. Slutliga A ger full sparad korg på **52,2790 s för 290,82 kr**;
tidigare receptkombination verifierar **297,18 kr** med samma aktuella
planner och rätt skalning till fyra portioner. A är därmed 6,36 kr billigare.
Det tidigare separata 276,38-kronorsprovet saknade portionsskalning och
är uttryckligen ogiltigförklarat/ersatt i rapporten. Ingen global prisoptimalitet
påstås. Laddning/förberedelse före API:t 98,5562/80,1325 s redovisas separat.
Inga nya browsertider eller aktiva måltidsbundna 10–15-gränser påstås.

674 riktade regressioner plus kontrollmodulens 30 slutprov (överlappar),
Ruff/compileall passerar. Ordinarie CI krävs på slutligt PR-huvud.
Etappen kostar 1 827,7125 s inklusive misslyckanden; gemensam journal har
**27,3033 s = 0,46 minuter kvar**, utan nollställning. Högsta observerade
jobbcommit 1,506 GiB på två CPU, hårt 3 GiB. Ingen stor matris eller
automatisk fortsättning. Enbart nästa samlade kontroll/sammanställning behöver
cirka fyra minuter, före nya källåtgärder; se rapportens fortsättningskostnad.
Legacy standard, V2 opt-in, ingen betaaktivering.

# 2026-10-27: Ägarprioritet — gör alla 2 200 varianter användbara

Aktuellt uppdrag är
[CODEX-SOL-NEXT-20261027-RECIPE-COVERAGE.md](CODEX-SOL-NEXT-20261027-RECIPE-COVERAGE.md).
Det ersätter fortsatt generell prestandatrimning som nästa huvuduppgift.
Läs uppdaterade PRODUCT-GOAL och PLANNING-ARCHITECTURE. Utgångspunkt är
PR #18/main `fd2dcb8`; inget nytt runtimearbete ingår i denna prioritering.

738/931 av 2 200 betyder individuellt produkt-/mängdstöd för samtliga
ingredienser i exakt läge/respektive inklusive tillåtna uppskattningar.
931 inkluderar 738. Det är 33,5/42,3 procent, inte full bibliotekstäckning
eller verifierade hela receptkorgar. Alla 2 200 är redan importerade.
I uppskattningsläget blockeras 1 269 varianter av 99 ingrediensgrupper;
782 av dessa varianter har bara en blockerande grupp. Registret innehåller
89 `definition_only`-identiteter som alla återfinns bland hindren.

Målet är 2 200/2 200 individuellt lösta varianter och verifierade fulla
receptkorgar i redovisat referensscope. Bevara exakta/uppskattade utfall,
alla ursprungs-ID:n och produkt-/pris-/personkrav. Läs instruktionernas
prioriterade ingrediensarbete och budget innan nya mätningar. Befintlig
journal har 1 855,0158 s (30,92 min) kvar; ingen nollställning/stor matris.
Legacy standard, V2 opt-in, ingen ny driftaktivering beslutad.

# 2026-10-26: Bred A-vecka levererad på 55,12 s i browser, 297,18 kr

Leverans enligt BROAD-WEEK från main `2dd7183`; mätkod `11b5b97`.
Läs [rapporten](reviews/broad-week-search-20261026.md) och maskinkvittona.
**Oförändrat A ger full checkout/audit/save/ägd GET på 53,3724 s;
verklig Chromium knapp→synlig full lista+GET 55,1185 s, 297,18 kr.**
Hela råa/normaliserade sparade begäran och hela korgen matchar exakt.
Samma 52 butiks-ID:n, fem middagar/fyra portioner, max två butiker,
gamla variationsregler och inget nytt variation-intent. Rättelse 2026-10-27:
råa globala 10–15 ingredienser gäller inte effektivt när måltidens egna
`recipe_choices` har tomma gränser; A:s valda recept har 5, 5, 5, 6, 6
ingredienser. Tiden kvalificerar därför inte ett aktivt 10–15-krav.
Skafferival False bevaras. A saknar personliga närings-/eko-/allergimål;
dess näringsstatus är NOT_REQUESTED, inga nya proteinvärden intygas.

**Matchat B2 behåller exakt hela 731,20-kronorskorgen och sparade val**,
API/save/GET 30,8191 s. Minst 35 g protein ESTIMATED, 3 kyckling/2 veg,
variation, butiker och aktuell audit passerar. Ingen prisregression.

Cacheutträngningen är rättad utan större LRU: väntande kvalificeringar och
fortsatt cache delar 256 fulla resultat. Ett 300-kandidatprov ger 44 nya/
256 återanvändningar och samma ordning/likaprisutfall som okachad sökning.
För bred genererad aktuell V2 prioriteras nu hela strukturella menyförslag
som prövas i befintlig checkout. Ingen dyr singleton/prefixprissättning
görs på sökdjup 1–4. Första giltiga hela A-kandidaten efter 34,9840 s;
509,64 kr förbättras till 297,18. 58/960 ankare och 316 giltiga hela korgar
prövas, resten är uppskjutet. Inget globalt optimumbevis.

En snävare deadline inne i förbättringscheckout reserverar tolv sekunder
för aktuell audit/save/svar och återställer yttre budget vid mjukt stopp.
Högst två fulla sökresultat och 4 096 kompakta menyidentiteter behålls;
privat allokering/lås behåller ordning. Ingen personlig vinnarcache delas.
Total observerad Windows-jobbcommit högst 1,506 GiB på två CPU, hårt 3 GiB;
bara en faktisk pris-/faktaversion, versionsöverlapp fortfarande omätt.

Ett nytt A-API-prov, ett verkligt A-browserprov och B2-regressionen räckte.
Två startfel före dataladdning/API kostar också 0,0496 s i journalen.
Samma journal: **5 344,9842 s använda / 1 855,0158 s kvar (30,92 min)**.
121 avslutande riktade regressioner inklusive Chromium/WebKit och små
korg-/kampanj-/närings-/ekoorakel passerar. Tidigare testkörningar överlappar.
Ruff/compileall samt ordinarie CI inklusive browser krävs inför mainintegration.

Ingen ny inventering: återanvänd 738 exakt/931 inklusive tillåtna uppskattningar
av 2 200; källor och centrala kvalificeringsfunktioner är verifierat oförändrade.
Största kvarvarande uppmätta del är personlig kvalificering cirka 26,8 s,
sedan API-/lagrings-/svarsarbete och begränsad prisförbättring. p95,
samtidighet, verklig veckouppdatering, prisversionsöverlapp, hela valkatalogens
kombinationer och UI-butikstak 1..N återstår. Ingen import/insamling/stor matris.
Legacy standard, V2 opt-in, ingen beta eller produktion aktiverad.

# 2026-10-26: Nästa Sol-uppdrag — bred A-vecka och återanvänd kvalificering

Aktuell startpunkt efter oberoende granskning av main `719b927`/PR #17:
[CODEX-SOL-NEXT-20261026-BROAD-WEEK.md](CODEX-SOL-NEXT-20261026-BROAD-WEEK.md).
Läs [granskningen](reviews/review-pr17-and-next-20261026.md). 116 riktade
regressioner inklusive Chromium/WebKit passerar. Sparade B2-anrop och hela
korgen har jämförts oberoende: samma 731,20 kr och val; uppmätt 31,86 s
i browser är ett verkligt fullständigt veckofall. Köpbarhet 738/931 av
2 200 är verifierad per ID, +5/+11 utan förluster.

A klarar fortfarande ingen lista på 60 s. En konkret reproducerad brist
är att de 960 kvalificerade enreceptskorgarna räknas om på sökdjup ett,
med noll cacheträffar: de sista 256 sparade resultaten trängs undan innan
de konsumeras. Rätta den minnesbegränsade överföringen och låt sökningen
nå en fullständig giltig vecka tidigt före fortsatt prisförbättring.
Bevara alla krav och aktuell slutlig checkout/audit/save. B2 är regression
för pris/giltighet; A ska inte göras lättare. Ingen ny import eller bred
insamling behövs för detta steg.

Samma mätbudget: senast **37,89 minuter kvar**. Högst tre nya A-försök,
bara efter konkreta ändringar, därefter delrapport vid kvarstående hinder.
Ingen stor matris. Legacy standard, V2 opt-in, ingen driftaktivering.

# 2026-10-26: Giltig B2-vecka på 31,86 s i browser; aktuell köpbarhet 738/931

[PR #17](https://github.com/ossebosse/smako/pull/17) genomför
VALID-WEEK-AND-COVERAGE. Läs [rapporten](reviews/valid-week-and-coverage-20261026.md)
och dess maskinkvitton före nya mätningar. Original-B är oförändrat negativt
underlag; ingen dyr omkörning av dess gamla konflikt gjordes.

B2 behåller 52 butiks-ID:n, fem middagar/fyra portioner, tre kyckling/två
vegetariska, grekiskt/italienskt, protein minst 35 g, högst tre samma
huvudprotein, butikstak två och estimated. Bara den kända kolliderande
huvudråvarustandarden ändras 2→3, genom nytt sparat fältursprung. Egna och
äldre okända gränser behålls. Effektiv regel/anpassning sparas och visas.
Legacy/V1 och gamla planers betydelse ändras inte. Nya sparade intentdata
får inte heller tyst ignoreras om miljön återgår till legacy.

**B2 API/checkout/save/ägd GET 30,2549 s, verklig Chromium knapp→full synlig
lista+GET 31,8625 s, 731,20 kr i båda. Hela sparade begäran och
hela korgen matchar strikt, inklusive `use_pantry=False`.** Ny ägare/process, ingen identisk
färdigplanscache. Fem olika baser, fyra grekiska/en italiensk, tre kyckling
och två vegetariska. Protein 48,882/48,631/45,188/36,755/39,965 g per portion,
ESTIMATED enligt uttryckligt tillåten spårbar insatsberäkning. Inköpsstatus
VERIFIED, checkout-audit passerar, två valda Malmöbutiker. Ett lyckat fall
är inte globalt optimum, prisparitet mot okänd äldre B2-vinnare eller p95.

Den aktuella fullinventeringen av samtliga 2 200 importerade varianter gav
före ny koppling samma 733 exakt/920 estimated som historiskt. Strikt rågbröd
ger noll förlorade varianter; alla tre rågbrödsvarianterna är fortsatt
insatslösta. Efter verifierat kokosalias: **738 exakt (33,5 %), 931 inklusive
tillåtna uppskattningar (42,3 %), +5/+11 och noll förluster**. De 262 andra
ursprungliga recepten ingår inte i dessa tal. Individuell insatslösbarhet
är inte gemensam korg-/närings-/allergen-/ekokvalificering. Bara kokosens
tolv kvantitetsscope ändrar utfall; inga recept eller mängder skrivs om.
Limejuice och ansad ätlig grönsaksmängd saknar fortfarande behövligt källstöd.
Köpbarhetsdelen kostade 168,4620 s = 2,81 av högst tolv minuter.

Deadline följer nu även personliga ändringar genom admission, async-jobb,
arbetstråd, inre loopar och lagring. Före commit rullas revision/reservation/
mutationskvitto tillbaka. Redan fullständigt committad revision redovisas
i timeoutstatus och kan GET:as eller återfås med identiskt återförsök utan
dubbelversion. Simulerad klocka, direkt/async, kö, rollback, sen commit,
avbrytning, annan ägare och legacy är provade.

Det enda extra A-provet gav **SEARCH_INCOMPLETE efter 60,2828 s**, ingen
levererad lista eller totalsumma. 2 021 råa/960 kvalificerade kandidater;
vid deadline bara 699 förslag på djup två. Upprepad gemensam korgberäkning
över denna större pool är nästa konkreta prestandahinder. Inget identiskt
timeoutomtag. Separat progressfilskrock i testhjälparen dokumenteras/fixas;
API-utfallet och budgetdebit behålls.

Kall första preparation/registrering före B2-anropet 112,38 s; browserns
gemensamma preparation 19,37 s med 4 926 träffar/noll missar. Det är inte
31,86 s från tom installation. Högsta uppmätta jobb-commit 1,464 GiB, under
2,5 GiB-målet/hårt 3 GiB på två CPU. Bara en verklig pris-/faktaversion:
veckouppdatering, två fulla prisversioners överlapp och samtidighet omätta.
Full V2, snabb bred A och UI-tak 1..N är fortsatt okvalificerade.

Samma journal: **4 926,7738 s använda / 2 273,2262 s kvar (37,89 min)**.
678 riktade regressioner före sista UI-rättningen samt hela browsermodulens
52 prov efter skafferi- och override-skydden passerar; antalen överlappar. Ruff/compileall passerar. Ordinarie
CI inklusive browser krävs grön på slutligt PR-huvud före mainintegration.
Första browserprovet på 30,78 s bevaras och debiteras men räknas inte som
exakt B2: det sparade skafferistandard True i stället för valt False. UI har
nu ett synligt återställt/skickat skafferival; slutprovet jämför alla fält.
Legacy standard och `library_merge_generations=False`. Ingen beta,
produktion, profiländring, bred insamling, stor matris eller nattlig fortsättning.

# 2026-10-26: Nästa Sol-uppdrag — giltig vecka, omräkning och köpbarhet

Aktuell startpunkt efter ägarens granskning av main `c94c229`/PR #16:
[CODEX-SOL-NEXT-20261026-VALID-WEEK-AND-COVERAGE.md](CODEX-SOL-NEXT-20261026-VALID-WEEK-AND-COVERAGE.md).
Det ersätter WEEK-SEARCH som nästa uppdrag; tidigare rapporter är bevarad evidens.

Lös uttryckliga val kontra ärvd standardvariation utan att ändra gamla
planers innebörd eller andra hårda krav. Behåll original-B som negativt
underlag; pröva separat B2 med dokumenterad policyändring och samma fem
middagar, fyra portioner, protein-/kostval och 52 tillåtna butikskontexter.
Täta också deadline-luckan i `api/personal.py`: omräkning/ändring av sparad
plan når arbetstråd och lagring utan nya planers 60 s-skydd.

Förbättra ett fåtal källstödda produkt-/mängdkopplingar och inventera aktuell
köpbarhet för alla 2 200 importerade varianter. Historiska 733 exakt/920
med tillåtna uppskattningar är inte ommätta efter rågbrödskravet; de är
inte ett personligt närings-/allergen-/ekogodkännande. Därefter behövs en
verkligt giltig, kontrollerad, sparad och återläst veckolista och browserprov
om veckan klarar 60 s. Ett 45,10 s-avslag kvalificerar inte produktmålet.

Samma mätbudget har senast **49,56 minuter kvar**, högst 12 minuter till
dyr köpbarhetsinventering/profilering i denna etapp. Ingen ny stor matris.
Legacy standard, V2 opt-in och separat driftaktivering kvarstår.

# 2026-10-26: Spett/rågbröd rättade, cache lagrar igen, B ger strukturellt avslag

[PR #16](https://github.com/ossebosse/smako/pull/16) genomför den avgränsade
leveransen i WEEK-SEARCH. Läs [rapporten](reviews/week-search-and-cache-20261026.md)
och maskinunderlagen före nästa mätning. Sex spettvarianter har 1.0.3 med
sammanhängande tina/skär/trä/ugn; tre rågbrödsvarianter har 1.0.1 med
`pack:rye_bread` och faktisk rostning. Tolv andra direkt-fryst-varianter
verifieras oförändrade. Historiska bytes/referenser bevaras; 2 462 aktiva
varianter/934 baser, 39 aktuella och sju historiska paketgenerationer.

Ny opt-in `smako-current-library-v2` söker aktuell kvalificerad pool utan
historiska menykohorter, återanvänder rena offentliga offertdelar och gallrar
bara bevisat dominerade butiker i oberoende checkout. Små uttömmande orakel
behåller bästa pris även för paket, kopplade kampanjer och närings-/ekoval.
Legacy förblir standard och `library_merge_generations=False`.

Fylld cache → nytt underlag → faktisk lagring → träff efter omstart fungerar:
95,97 s första färdiga förberedelse, 2 464 skrivningar/2 461 gallrade poster;
ny B-process ger 4 926 träffar, noll missar/skrivningar. Totalt 3 430 745 byte.
Första 120 s-stoppet och mätt per-post-fsync-flaskhals är bevarade; korrigerad
återbyggbar cache använder atomisk replace. Avbrott/omstart/CAS-fencing,
byte-/posttak och säker fallback har riktade prov. Bara en behörig verklig
pris-/faktaversion finns; veckouppdatering och två fulla prisversioners
överlapp är fortfarande omätta. Uppmätt högsta job-commit för B är 1,47 GiB.

Oförändrat B ger **HTTP 422 SEARCH_BLOCKED efter 45,10 s**, ingen färdig vecka,
audit, sparad lista, totalsumma eller browserlatens. Samma 681→29 kandidater
och samma första avslag; butikskombinationer minskar från 1 566 881 i det
gamla partiella 60 s-kvittot till 93 269 vid det nya slutliga avslaget.
868 132 delmängder undviks av dominans. Det är minskat arbete, ingen lyckad
veckolatens eller bevisad prisparitet. A/browservillkoret uppfylldes inte.

Budgeterat strukturprov på exakt B:s 29 kvalificerade recept: 25 kyckling,
fyra vegetariska, samtliga 13 800 kombinationer med 3+2 kontrollerade.
2 160 stoppas av upprepad bas och 11 640 av kulinarisk variation. Normaliserat
anrop har `max_same_primary_ingredient_meals=2`; upplöst balanced-policy har
samma tak samtidigt som B kräver 3 kyckling och tillåter 3 samma huvudprotein.
Klarlägg denna policykonflikt utan tyst
kravlättnad före fler dyra veckoprov. Kvarvarande historisk modellsharing
och jämförelser av samma meny efter en vinnare är också kvar att tidsmäta.

**Rättelse:** tidigare rapport/uppdrag säger 55 valda butikskontexter, men
det sparade B-underlaget innehåller 52 `allowed_store_ids`. Nya och gamla
normaliserade B-anrop är exakt lika; inga butiker lades till eller togs bort.
Detta kvalificerar inte ett 55-butiksanrop. Tidigare 733/920 individuell
produktlösbarhet har inte inventerats om; rågbröd är inget allergenintyg.

Samma journal: **4 226,3128 s använda / 2 973,6872 s kvar (49,56 min)**.
Senaste samlade riktade prov 78 PASS; innehåll 434, breda kärnregressioner 233
och senaste cacheprov 31 PASS överlappar. Ruff/compileall gröna; grön ordinarie
CI inklusive browser på slutligt PR-huvud krävs före mainintegration.
Ingen ny budget, stor matris, kvarlämnad mätarbetare eller betaaktivering.

# 2026-10-26: Nästa Sol-uppdrag — kvarstående receptfel, veckosökning och cache

Ägaren har efter granskningen av PR #15 gett nästa uppdrag till Sol:
[CODEX-SOL-NEXT-20261026-WEEK-SEARCH.md](CODEX-SOL-NEXT-20261026-WEEK-SEARCH.md).
Detta är aktuell startpunkt; föregående rapport och uppdrag är bakgrund.

Oberoende granskning av `6b2e946`: 457 riktade tester passerar. Sex aktuella
1.0.2-spettvarianter har ändå motsägande instruktioner: tina frukten, lägg
den sedan fryst i en panna, trots ugnsspett. Rätta båda basernas tre
varianter och den redan dokumenterade rågbröd/pitabröd-avvikelsen genom
vanliga nya versioner. Kontrollera även andra recept som samma ersättningar ändrat.

Prioritera därefter återanvändning i gemensam korg-/butikssökning och
beräkningscachens versionslivscykel. Mät det oförändrade femmiddagsfallet B
efter en konkret ändring. Endags-F:s 28–32 s ersätter inte veckomålet;
A/B/E saknar färdig meny vid 75 s. Ingen stor ny matris eller ny budget.
Senast **55,74 minuter kvar** i samma intake/V2-journal; läs aktuellt saldo.
Opt-in för ny sökväg, legacy som standard, separat driftaktivering kvarstår.

# 2026-10-26: Receptens frysta beredning rättad, verkliga personliga prov

[PR #15](https://github.com/ossebosse/smako/pull/15) och
[slutrapporten](reviews/recipe-quality-and-planning-20261026.md) genomför
CODEX-SOL-NEXT-20261026-RECIPE-QUALITY-AND-PLANNING.md.
337 berörda varianter/196 baser har nya versioner via author/validate/diff/import,
inklusive explicita processer, faktiska `uses`, upptining/kylning, tidsfilter
och 14 krav på färsk fast/grön råvara. Äldre bytes och original166/262 behålls.
Aktuellt: 2 462 varianter/934 registrerade baser, 38 aktuella + sju historiska
paketgenerationer. Recepten är inte provlagade; tiderna har beredskapskontroller.

Majskornens alias/identitet rättas med bibehållna källa-/mängd-/policygrindar.
Efter färskformskorrigeringen: exakt 700→733, estimated 882→920 individuellt
insatslösta varianter (+33/+38); netto +29/+32 mot föregående rapport.
1 467/1 280 kvarstår blockerade av 105 grupper. Läs den nya hinderlistan före
källarbete; limejuice445 och ingefära402 dominerar men överlappar andra hinder.

F är en ny ägare/nya val: en middag/två portioner, grekiskt/italienskt,
5–7 ingredienser, aktiv30/total45 min, protein≥20 g. API31,42 s, senaste uppmätta
API31,96 s; verklig Chromium klick→lista+GET28,10 s, 104,30 kr och
ESTIMATED protein20,7625 g. Checkout/save/ägar-GET passerar. A/B/E:s fria
femmiddagsfall är ofärdiga vid75 s. D (jordnöt+eko50 %) avvisas DATA_BLOCKED
24,89 s. C är funktionellt sparat men lovar rågbröd och köper pitabröd:
exakt kvarstående innehållsärende finns i rapporten och ska få vanlig ny version.
Endagsresultatet bevisar inte 30–60 s för veckor eller tusentals sökbara recept.

En begärandeägd identitetscache återanvänds i diagnostiken, ingen verifierad
veckolatensvinst. B räknar fortfarande över1,5 miljoner butikskombinationer.
Gemensam preparation32,51 s på redan full4096-cache gav noll skrivningar;
säker versionsfallback är testad men hållbar retention återstår. Bara en
behörig pris-/faktaversion finns: verklig veckouppdateringslatens är omätt.
Nästa prestandaändring ska angripa gemensam korgsökning/aktuellt bibliotek,
opt-in och med oförändrat B; återstarta inte den stora matrisen.

Samma journal: **3 855,4145 s använda / 3 344,5855 s kvar (55,74 min)**.
Ingen ny budget och inga kvarlämnade mätarbetare. Sista riktade offlinekörning
544 PASS, Ruff/compileall gröna; ordinarie CI inklusive browser krävs på sista
PR-huvudet före mainmerge. Legacy-default och library_merge_generations=False
består. Mainintegration är ingen betaaktivering; drift/profiler/insamling orörda.

# 2026-10-26: Nästa Sol-uppdrag efter oberoende granskning av PR #14

Läs först
[CODEX-SOL-NEXT-20261026-RECIPE-QUALITY-AND-PLANNING.md](CODEX-SOL-NEXT-20261026-RECIPE-QUALITY-AND-PLANNING.md).
Ägaren har beställt instruktioner till en ny Sol-session. Uppdraget är att
rätta de automatiska ändringarna till frysta ingredienser, förbättra de
produktkopplingar som ger störst faktisk effekt och göra få avgränsade prov
av personlig planering med det verkliga biblioteket.

Granskning av main `ed36c0f`: 472 riktade tester passerar, men fryst mango
har kvar skalningsinstruktioner och upphettning/upptining härleds felaktigt
ur ord i steg. 337 varianter har ändringar till frysta ingredienser, 99
har fått åtta timmars upptining; alla dessa är inte därmed felaktiga.
Detaljer och reproducerbara exempel finns i det nya uppdraget. Tidigare
uppgift om granskad struktur är inte ett slutligt innehållsgodkännande.

Massimporten är klar. Behåll de 2 200 importerade varianterna och historiken;
återgå inte till 45-importer. 704 individuellt produktlösbara varianter i
exakt läge/888 i uttryckligt estimated-läge är fortfarande utgångspunkten,
inte 2 200 fullt kvalificerade recept eller godkända veckomenyer.

Fortsätt samma 120-minutersjournal: senast **84,57 minuter kvar**, kontrollera
aktuellt saldo vid start. Ingen ny budget, gammal fullmatris eller nattlig
fortsättning. Full V2 och 1 000-/5 000-prov är inte krav för denna etapp;
produktmålet och V2-arkitekturen kvarstår. Denna handoff ändrar endast
dokumentation, inte recept/runtime, standardläge eller drift.

# 2026-10-26: Hela receptsamlingen integrerad — 2 200 källvarianter

[PR #14](https://github.com/ossebosse/smako/pull/14) och
[helhetsrapporten](reviews/recipe-integration-all-20261026.md) ersätter
45-variantersdelmängden som aktuellt leveransresultat. Samtliga **800
källkandidater/2 200 varianter** är representerade i utvecklingsbiblioteket:
**2 462 aktiva varianter/934 registrerade grundrätter**. Alla 166 originalfiler
är byteidentiska och de ursprungliga 262 recepten är oförändrade. Alla
2200 käll-ID:n har exakt rad/SHA → aktivt runtime-ID; noll innehållsavslag.
Recepten är AI-författade och inte provlagade.

13 processgrupper har gemensamma baser/familjer. Med tre tidigare avvisade
ny-basanspråk blir det 769 nya registrerade baser; global kulinarisk unikhet
påstås inte. Middagens 294 ingrediensantalsundantag kvarstår, fyra samgrupperade
baser saknar variant inom standardens 10–15. Standardfilter och dinner_level
är oförändrade. Stegkedjor, kylning och frysta varianter är uttryckliga;
tolv styckdetaljrättningar är nya 1.0.1-versioner med återkallade föregångare.
**33 aktuella + sju historiska generationer**, största paket 2 882 571 byte.
Återimport är idempotent och alla källvarianter valideras vid 1/2/4/12 portioner.

Den nya vägen har 92 ytterligare identiteter/381 produktreferensrader samt
89 granskade ingrediensdefinitioner med obligatoriska, ännu ouppfyllda
produktbevis. Inga låtsasrecept, tomma krav, antagna densiteter eller
ätliga/avrunna andelar. Kontrollera
[den prioriterade hinderlistan](reviews/recipe-integration-all-20261026/HINDER.md)
och dess JSON innan någon beskriver hela samlingen som köpbar. Där finns
exakta recept-ID:n, mängder, krav, avslag, produktförslag och nästa komplettering.
Fryst behörigt Malmöunderlag från 23 oktober används, inga nya källor samlas in.
1 812 gemensamma inputscope: 704/2 200 varianter har alla insatser lösta i
exakt köpläge, 1 496 är blockerade av 104 ingrediens-/formluckor. Efter ett
uttryckligt estimated-val är motsvarande antal 888/1 312. Detta är individuell
insatstäckning, inte godkända gemensamma veckokorgar eller näringsintyg.

Åtta låsta funktionella kontrollfall på `ce0b7e9` täcker sex kök och tre
måltidstyper med full checkout/audit, privat save och ägarbunden återläsning.
De är inte fria veckosökningar; näring var NOT_REQUESTED. Slutlig
innehålls-/portionsförberedelse och gemensam produktinventering binds till
`d181416` och respektive exakta artefakthash i rapporterna.
Ett nionde fall på slutlig runtime ger full checkout/save/GET för lammsoppa
med uttryckligt estimated-val, uppskattat 317,90 kr. Det separat avvisade
nötköttsfallet på rotselleri bevaras som avslag.

Fortsätt samma **120-minutersjournal** i
`docs/reviews/recipe-integration-800-20261025/budget.json`; ingen ny budget.
**2 125,9999 s = 35,43 minuter förbrukade; 5 074,0001 s = 84,57 minuter kvar.**
Ett stoppat överlapp är fullt debiterat och uteslutet från prestandapåståenden.
Budgetverktyget har nu OS-låsning mot samtidiga arbetare. V2:s fortsatta
sök-/arkitekturarbete och 30–60-sekundersmålet är inte redovisade som uppnådda.
Legacy-default, merge=False och separat betarelease består; ingen produktion,
profil, scheduler eller insamling har aktiverats.

# 2026-10-25: Första granskade receptimporten — 45 varianter, 18 nya grundrätter

[PR #13](https://github.com/ossebosse/smako/pull/13) genomför den första
granskade delmängden i
[receptuppdraget](CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md).
[Slutrapport och maskinunderlag](reviews/recipe-integration-800-20261025.md)
anger exakt käll-ID → aktivt ID, innehållsbeslut, produktavslag och mätgränser.
Utvecklingsbiblioteket har nu **307 aktiva varianter/183 grundrätter**,
tidigare 262/165. Nytt: **45 varianter av 18 nya och två befintliga baser**,
alla måltidstyper och sex kök. Samtliga 166 manifestbundna originalfiler
är bytebevarade. Recepten är inte provlagade.

Tolv uttryckligt granskade ingrediensidentiteter med 23 exakta bevarade
produktreferenser har införts genom befintlig författar-/produktväg.
Längre total-/väntetid, rå animalisk insats i kalla sluträtter,
diet/skaldjur, precisa namn/former, urkärning, portionsskalning och
importgräns har riktade regressioner. Ingen fri densitets-/ätlig-andels-
omräkning eller fabricerad närings-/allergen-/ekostatus har lagts till.

Tre ny-basanspråk avvisas efter jämförelse med gamla biblioteket: grekiska
färsbiffar och thailändsk laxsallad är nu varianter av befintliga baser;
bulgur-/linsfrukost ska bli framtida varianter av befintlig frukostbas men
är inte importerad. Därmed högst 797 nya baskandidater; global unikhet är
inte styrkt och 13 bredare familjegrupper återstår. Samgrupperingen bevarar
base_id, diversitetsfamilj och max_same_base_meals. Åtta tidigare separata/
felaktiga mellanversioner är återkallade med oförändrade historiska bytes.
Manifestet har **17 aktuella + sju historiska generationer**, idempotent
återimport och paket klart under 16 MiB; 128-gränsen är oförändrad.

Originalets nya native audit: 572 kompatibla, 1 626 ingrediensblockerade och
två kvarvarande originalavslag som har rättats i den importerade delmängden.
**2 155 originalvarianter återstår utan import**, varav 529 strukturellt
kompatibla men inte färdiggranskade. **183 exakta ingrediensidentiteter**
återstår; börja med salladslök 139, mynta 131, koriander/purjolök vardera
111, tamarindpasta 93. Effekterna överlappar. Recept-ID/rad och nästa
komplettering finns i rapportens `ingredient-blockers.json`. 294 avvikelser
från variantintervallen och sju middagsbaser utan 10–15-variant är verifierade.
Standardfilter och `dinner_level` ändras inte för variantnamnens skull.

Fryst behörigt Malmöunderlag från 23 oktober: gemensamt 201 inputscope,
23/45 individuellt produktlösbara varianter. Fyra låsta funktionella fall
ger full checkout/audit, privat save och ägarbunden återläsning; tre gamla
priser oförändrade, fjärde fallet provar lång blötläggning. Ingen allmän
närings-/eko-/allergikvalificering eller veckosöklatens påstås. Nytt kallt
recept-/portionsunderlag är förberett, även för historiska sparade referenser.

**Gemensam intake/V2-budget: 1 073,9377 s = 17,90 minuter förbrukade,
6 126,0623 s = 102,10 minuter återstår av samma 120 minuter.** Fortsätt
`docs/reviews/recipe-integration-800-20261025/budget.json`; starta inte en ny
120-minutersjournal. Alla starter, omtag och förberedelser är debiterade;
inga mätarbetare fortsätter. Windows-jobb med verklig interpreter, två CPU,
hårt 3 GiB commit; största verifierade private commitpeak 1,102 GiB.
De tre första wrapperminnesvärdena är ogiltiga och uttryckligen uteslutna.

122 riktade offlineprov och tre budgetprov, Ruff och compileall passerar.
Ordinarie full CI inklusive Chromium/WebKit passerar på runtime `81466b1`
(körning 40241622213); slutleveransens checkar finns på PR #13.
Legacy är fortsatt default, `library_merge_generations=False`; ingen beta,
produktion, scheduler, insamling eller produktionsprofil har ändrats.

**Nästa arbete:** bygg vidare med innehållsgranskning av de 529 kompatibla
varianterna och de prioriterade exakta produkt-/mängdluckorna, samt avsluta
likhetsgranskningen. Fortsätt sedan det separata
[V2-implementationsuppdraget](CODEX-SOL-NEXT-20261025-PREPARED-PLANNING.md)
med dessa verkliga recept och fryst 262-baslinje. Någon ny opt-in V2-sökväg,
1..N-butiksexponering, end-to-end-deadline eller 1 000-/5 000-kvalificering
har inte implementerats här. A–E/HTTP GET/browser/nya användarval är inte
ommätta på en ny V2-väg; 30–60-sekundersmålet är inte uppnått av denna import.

# 2026-10-25: 800 grundrätter mottagna; Sol färdigställer ingredienser och import

Ägaren beställde att receptleveransen läggs till i Smako och att Sol får
instruktioner. Nästa läsning är
[CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md](CODEX-SOL-NEXT-20261025-RECIPE-INTAKE.md),
före stora nya skalprov i det fortsatt gällande V2-uppdraget. Sammanlagd
benchmarkbudget för denna fortsatta etapp är fortfarande 120 minuter, inte
två separata budgetar. Produktmålet innehåller nu även ingrediensvarianter.

Alla 800 grundrättskandidater/2 200 varianter finns i 160 bytebevarade
författarpaket under `backend/app/data/recipes/incoming/authoring-800-20261025`.
Originalbilagor och bevarade filer har källmanifest med SHA-256.
[Mottagningsrapport](reviews/recipe-intake-800-20261025.md) och JSON redovisar
429 native-kompatibla varianter, 1 763 ingrediensblockerade, sex
standardiseringsfel och två valideringsavslag. Befintlig normalisering ger
189 saknade kanoniska identiteter, jämfört med författarens råa 198.

Samlingen är tillagd som komplett underlag i projektet. Ingen av dessa
varianter har ännu publicerats som konsumentrecept: aktivt manifest och
bibliotekets 262 recept är oförändrade. Sol ska rätta dokumenterade hinder,
granska innehåll, komplettera befintliga kopplingar och publicera korrekta
delmängder genom vanlig import. Importens 16 MiB/128-generationsgränser
kräver färre runtimepaket än de 160 författarpaketen. Ingen aktivering i beta.

# 2026-10-25: Bestående produktmål och ny planeringsriktning efter PR #12

Ägaren har förtydligat hela produkten: plats och valda butiker, butikstak
upp till alla valda, måltider/portioner och samtliga kombinerbara recept-,
kost-, närings-, smak-, allergi-, eko- och överskottsval. Billigast möjlig
giltig gemensam inköpslista ska nå användaren inom 30–60 sekunder även vid
nya val och med tusentals recept. Målet är ännu inte uppnått.

Bestående läsordning finns nu även i AGENTS och README:
[PRODUCT-GOAL.md](PRODUCT-GOAL.md) →
[PLANNING-ARCHITECTURE.md](PLANNING-ARCHITECTURE.md) →
[CODEX-SOL-NEXT-20261025-PREPARED-PLANNING.md](CODEX-SOL-NEXT-20261025-PREPARED-PLANNING.md).

Ny opt-in-riktning V2: gemensamt versionsbundet underlag, personlig sökning
mot aktuellt bibliotek, exakt checkout och butikshantering utan full
delmängdsmaterialisering. Historisk återspelning flyttas från V2:s anropskrav
till proveniens/validering; V1 bevaras. Ingen prisregressionstolerans eller
generell optimalitetsgaranti införs. E:s produkt-/faktaluckor behöver egen
utredning. Nästa etapp har 120 minuters sammanlagd benchmarkbudget och få
villkorade skalprov, inte gamla fullmatrisen.

Denna leverans är dokumentation och arkitekturbeslut. Inga runtimeändringar,
prestandaarbetare, defaultbyten eller produktionsaktiveringar har gjorts.
PR #12:s nio nya riktade offlineprov har omkörts: nio PASS.

# 2026-10-25: Personliga val — avgränsad förbättring och mätning avslutad

[PR #12](https://github.com/ossebosse/smako/pull/12) levererar runtime
`5e4d47f` med samma uppmätta appträd i slutleveransen. Granskad ändring:
återanvänd datumgiltig kampanjexistens per validerat prisobjekt/butik/svensk
dag och läs aktiv prisidentitet utan full readiness-skanning. Ingen cache av
personliga godkännanden, priser eller menyer; full kontext, aktuell giltighet,
checkout/audit, referens/legacy och ägargränser kvarstår.

[Slutrapport och kompakt maskinunderlag](reviews/personal-choice-latency-20261025.md).
Riktiga UI-begäranden, 262 recept, fryst godkänd partiell Axfood-arm, seriellt
två CPU/3 GiB. Genom sparad lista och GET: matkök **138,69 → 128,74 s**,
40 g protein **66,87 → 62,79 s**. Tre första A: median **200,72 → 187,50 s**,
samma pris/hash/audit. Förberett A **17,88 → 14,81 s**, återgång efter E
**17,18 → 16,42 s**. D timeout efter 300 s i båda armar. **E når inte målet**:
första svar 12,97 → 12,06 s är `SEARCH_BLOCKED`, ingen färdig lista. Endast
två av 66 recept kvalificeras; detta bevisar inte global omöjlighet.
Chromium visar samma blockerade E efter 13,47 s; A-listan synlig efter 199,56 s.

Verklig veckouppdateringslatens är **omätt**: två matchade behöriga frysta
prisversioner saknades. Syntetiska pris-/kampanj-/versions-/omstarts- och
single-flight-prov passerar; inget påstående om verkligt kampanjbyte görs.
Slutlig A/E-peak efter serialisering **1,245 GiB**, legacy **1,409 GiB**, ingen
swap/OOM. Rapporten skiljer tidigare V1-sampling före sista rapportskrivning.

Prestandajournalen är stängd: **117,13/120 minuter**, 172,16 s oanvända.
Avbrutna prototyper, verktygsrättningar, browseromtag och uppstarter ingår.
Inga mätarbetare, automatisk fortsättning, fullmatris eller 5 000-prov kvar.
Största återstående fas är riktig gemensam korgberäkning (228 s före D-stopp).
Nästa begränsade arbete bör utreda exakta paket-/offertdelar i befintlig
`PackageCostCache` samt E:s produkt-/faktaluckor; ingen ny stor körning beställd.

Riktade offlineprov, Ruff, compileall och ordinarie full CI inklusive
Chromium/WebKit kontrolleras på PR:ns slutkod före integrering. Standard är
fortsatt `legacy` och `library_merge_generations=False`. Ingen produktion,
scheduler, insamling, pris-/faktarelease eller samtidighet ändrad. Full
standardkvalificering påstås inte. Äldre nästa-steg-anteckningar nedan är historik.

# 2026-10-25: Nytt uppdrag till Sol om personliga val och användarväntan

Följ [CODEX-SOL-NEXT-20261025.md](CODEX-SOL-NEXT-20261025.md).
Beställaren vill prioritera kort väntan när en användare på varm server
ändrar matkök, proteinmål och kyckling/vegetariskt, samt efter kampanjbyte.
Uppdraget gäller implementation och avgränsad verifiering med dagens 262
recept. Högst två timmars sammanlagda prestandakörningar; gamla fullmatrisen
och 5 000-proven ska inte återupptas. 15/30 sekunder är utvecklingsmål för
förberett återanrop/nya vanliga val, inte uppmätta generella användartider.
Fulla kontext-/pris-/ägarkontrakt kvarstår; återanvänd oberoende delarbete
mellan krav utan att återanvända ett felaktigt personligt godkännande.

Denna leverans ändrar endast instruktioner. Ingen runtime, standardpolicy,
drift eller pris-/faktaversion har ändrats och inga nya benchmarkarbetare
har startats. Äldre löpande anteckningar om fortsatt matris nedan är historik.

# 2026-10-25: Etappen avslutad på begäran; fullmatris 91/252 uppmätt

Beställaren bad att 5 000-proven skulle hoppas över och leveransen avslutas
med befintligt underlag. Den pågående 5 000-arbetaren, båda styrprocesserna
och mätobservatören är stoppade. Inga nya matrisgrupper eller återstarter
är planerade. [Slutrapporten](reviews/preparation-memory-final-20261025.md)
sammanfattar resultat och varför hela verifieringen inte genomfördes.
Full standardkvalificering påstås inte; legacy/merge=False kvarstår.

Aktuell runtime `eeda184926f02e73ab76e71e50c740e9dcb01b02`, PR #10.
PR #10 är integrerad på main `ea7c7ae005f1ea10dd716b53d327427785e84e61`;
appfilerna är byteidentiska med den frysta runtime som fortsatt mäts.
Katalogfilen läses och valideras radvis med samma native produkt-/kandidat-
och indexvalidatorer samt full digest-/lineagekontroll. Stora JSON-buffertar
släpps före nästa graf. Befintlig atomisk filskrivning, validering och LKG kvar.
Tidigare misslyckanden på b5c242d (2,706 GiB) och 19ef0b2 (2,729 GiB) bevaras.

Tre versionsbytes-/serialiseringsprov **PASS**: cgroup **2,210 / 2,179 /
2,269 GiB**, med båda katalogernas 89 458 produkter och 71 138 faktarader
kvar. Hela skrivna filen är byteidentisk med fryst original i alla prov.
Ingen OOM/swap. 101 riktade parser-/katalog-/uppstarts-/minnesprov och full
CI inklusive Chromium/WebKit passerar på runtimekoden. Ingen meny/audit
påstås från dessa minnesdiagnostikprov.

Ny metodsignatur `17568fe52f2f4da372b1263979673cb79f74f731fa8ada05acc6fe8058e0d6b6`.
Slutkodens första planprov med tom appcache/ny ägarstore är klart:
662,83 s, sedan 11,66/11,86/12,19 s varmt, alla 988,32 kr/hash/audit PASS.
Slutlig cgroup-peak inklusive rapport/städning 1,882 GiB, ingen swap.
Hela fyranropsprocessen tog 756,71 s. Ytterligare två kalla processer är
klara: 649,49 / 664,50 s, pris/hash/audit PASS. Median över tre är 662,83 s,
högsta slutliga peak 1,882 GiB. Alla tretton cachelägesprocesser har nu
passerat; varm kvot 5 000/262 är 1,0873 i Malmö/fördelning/originalfakta.
Omstart och cacheförlust laddar elva certifikat utan omsökta publiceringar.
Tre nya ägarstore tog 641,40/637,84/641,36 s. Tre extra versionsbytesprov
utan mätverktygets fasstädning passerar också: **2,023/2,039/2,030 GiB**,
båda katalogerna och fakta kvar, exakt samma filhash, ingen OOM/swap.
Faktaprojektionen är klar för båda städerna, med oförändrade priser/request/
klocka och den partiella 103-dokumentsreleasen. Kvar följer
hela återstående matrisen. En seriell förgrundssekvens stannar
vid varje missad grind. B5-resultaten nedan är historik, inte automatiskt
slutkodens kvalificering. Standard förblir legacy och generationsmerge=False;
ingen drift, insamling, aktiv fakta/prisversion eller samtidighet ändrad.

[Rapport och maskinunderlag](reviews/preparation-memory-20261024.md).

Ny fasprofil klar: **666,03 s < 700 s**, 988,32 kr/hash/audit PASS,
hela processen 721,79 s, slutligt kvitto efter rapportserialisering **1,828 GiB**
utan OOM/swap. Matchad instrumenterad r2-referens 858,60 s: 22,43 procent
lägre tid, separat från vanliga treprovsmedianens 24,79 procent. Legacy native
200,30→61,16 s och 9 517→3 041 verkliga utvärderingar, alla elva föreslagna
priser identiska. Budgeterad förbättring kvar 437,33 s; kalkylatoranrop oförändrat
18 677. Kvalificering 207,00→101,90 s med samma 4 871 kalkylatoranrop.
Inläsningsmedianen är däremot 33,12→47,70 s; faserna förbättras inte likformigt.
Fullmatrisens första grupp är stängd: 573,48 s, 1,495 GiB, exit 0 utan OOM/swap.
V5-referensgruppen vid 262 är också stängd: 2 083,53 s, 1,496 GiB, exit 0
utan OOM/swap, med verifierat obegränsat referenskontrakt. Även Malmö/original/
1 000 är stängd: 4 101,51 s, 1,540 GiB, exit 0 utan OOM/swap. V1 ger
948,31 kr för protein40/all-macros mot legacy 1 027,79 och 262:s 1 000,86.
Organic-share v1 ger 318,96 kr mot legacy 321,16; första anropet tar
1 266,27 s, sedan 11,04–11,47 s varmt. Även 2 000-gruppen är stängd:
6 559,39 s, 1,789 GiB, exit 0 utan OOM/swap. V1 protein40/all-macros ger
897,31/834,06 kr mot legacy 904,82/951,42, lägre än 1 000:s v1-priser.
Organic-share v1 ger samma 318,96 kr; första anropet kostar 1 987,99 s
(33,13 minuter), sedan 11,50–11,83 s varmt. Totalt 91/252 uppmätta,
84 auditgodkända menyceller/336 anrop och sju vegan-SEARCH_BLOCKED-celler/
28 observationer med bevarad kod/steg. Inget globalt omöjlighetsbevis.
161 celler saknar fullständig mätning. Malmö/original/5 000 avbröts under
protein40/v1:s första anrop. Fyra legacy-observationer för 912,72 kr med audit
bevaras separat, utan slutligt resurskvitto eller nya fullständiga celler.
Ingen standardkvalificering och inga fortsatta matrisgrupper.
[Fullmatrisstatus](reviews/preparation-memory-20261024/full-matrix-current.json).
Separat läsande korsgranskning passerar 224 kontroller; 299 jämförelser saknar underlag.
Alla tillgängliga prisgränser, inklusive v5/262, är kontrollerade; ingen
standardkvalificering. Verktyg och resultat finns bredvid fullmatrisunderlaget.
Senaste arkiv 259 verifierade metadatafiler:
`3aeaa7292c6759602b50862b4c0e009b41505db5e1e56ef1dd1dee160a6af640`.


Pilotuppdatering: originalfakta/Malmö vid både 262 och 5 000 är klart,
tolv celler och 48 anrop med audit PASS. Slutliga processpeakar är
1,514 respektive **2,414 GiB**, exit 0 utan OOM/swap. V1 standard ger
492,15 kr vid båda storlekarna mot legacy 511,46. V1 fördelning går från
996,22 till 988,32 kr och organic-share från 321,16 till 316,26 kr.
Fem-tusen ger kallt/varmt: standard 743,97/11,66–12,45 s, fördelning
672,51/12,93–12,97 s och organic-share **3 992,65/12,44–12,78 s**.
Organic-shares kalla 66,54 minuter kvarstår som tydlig kostnad; ekologisk
sökning redovisar 3 365,56 s i överlappande fasdiagnostik. Varmkvoterna
mot 262 är 1,1391/1,1315/1,1925 och passerar 1,25, även mot legacytid/pris.
Även Lund/262 är nu klar: sex celler/24 anrop med audit PASS, 1,088 GiB
slutlig peak och exit 0 utan OOM/swap. Legacy och v1 ger samma priser:
standard 487,85, fördelning 761,45 och organic-share 314,24 kr. V1 kallt/varmt:
103,38/7,16–7,38 s, 91,67/7,58–7,79 s och 293,48/7,14–7,69 s.
Lund/5 000 är också klar: sex celler/24 anrop med audit PASS, 1,744 GiB
slutlig peak och exit 0 utan OOM/swap. V1 ger 477,84 / 699,10 / 286,32 kr
mot legacy 504,34 / 704,30 / 309,34 kr och är även billigare än vid 262.
V1 första/varmt: 808,89/8,10–8,56 s, 938,02/8,53–9,40 s och
2 890,91/7,72–7,85 s. Varmkvoter 1,1970/1,2405/1,0999 passerar 1,25 och
varma anrop är snabbare än legacy. Organic-shares kalla 48,18 minuter kvarstår.
Originalfakta-armen är därmed klar för pilotens tre profiler vid båda storlekarna
i båda städerna: totalt 24/48 pilotceller och 96 auditgodkända anrop.
Även Axfood/Malmö/262 är klar: sex celler/24 anrop med audit PASS, 1,708 GiB,
exit 0 utan OOM/swap. Samma priser som originalarmen. V1 första/varmt:
standard 174,51/10,54–10,83 s, fördelning 45,57/10,98–11,32 s och
organic-share 549,74/10,56–10,81 s. Explicita legacy-omprövningar verifierar
tidigare meny i alla tolv anrop, utan avvisningar; v1-menyer klarar aktuell audit.
Även Axfood/Malmö/5 000 är klar: sex celler/24 anrop med audit PASS,
slutlig peak **2,096 GiB**, exit 0 utan OOM/swap. V1 ger 492,15 / 988,32 /
316,26 kr mot legacy 511,46 / 988,32 / 316,26 kr. V1 första/varmt:
744,36/11,81–12,68 s, 678,53/12,50–12,88 s och 3 984,17/12,10–12,41 s.
Varmkvoter 1,2024/1,1731/1,1747 passerar 1,25, liksom pris/tid mot legacy
och pris mot 262. Organic-shares första förberedelse kostar 66,40 minuter.
Även Axfood/Lund/262 är klar: sex celler/24 anrop med audit PASS,
slutlig peak **1,257 GiB**, exit 0 utan OOM/swap. Legacy och v1 ger
487,85 / 761,45 / 314,24 kr, samma som originalarmen. V1 första/varmt:
106,76/7,25–7,40 s, 98,04/7,33–7,61 s och 305,73/7,16–7,26 s.
Även Axfood/Lund/5 000 är klar: sex celler/24 anrop med audit PASS,
slutlig peak **1,738 GiB**, exit 0 utan OOM/swap. V1 ger 477,84 / 699,10 /
286,32 kr mot legacy 504,34 / 704,30 / 309,34 kr och är billigare än vid 262.
V1 första/varmt: 858,03/7,88–8,01 s, 1 013,01/8,51–8,74 s och
3 146,17/7,91–8,22 s. Varmkvoter 1,1038/1,1929/1,1470 passerar, liksom
pris/tid mot legacy. Organic-shares första förberedelse kostar 52,44 minuter.
Totalt **48/48 pilotceller och 192 auditgodkända anrop**, med stabila priser
och menyhashar i varje cells fyra anrop. Högsta slutpeak 2,414 GiB, högsta
varmkvot 1,24054. Pilotarkiv SHA-256
`550b78946fd3cdfee0c29db04a6626474faa2a6a7085d102819fd66d121dcb26`,
94 unika metadatafiler verifierade. Ingen standardkvalificering eller ändrad default.

SSH-kanalen stängdes efter den avslutade Malmögruppen och sekvensen stannade
innan nästa arbetare. Kvitton och den tomma Lund/262-katalogen verifierades.
Återupptagningen hoppar bara över verifierade färdiga grupper, bevarar
ofullständig evidens och skriver fortsättningsloggen till disk även om
transporten stängs. Samtliga åtta pilotgrupper är nu avslutade inom samma gränser och frysta appkod.
Det kommande fasprovet får ett obligatoriskt kvitto efter sin rapportskrivning;
det ursprungliga profileringsverktyget och plananropets mätgränser är oförändrade.
Full CI på `ba256ea` och postnummerrättningen `d40ec5a` passerar inklusive browserprov.
Totalt 30 lokala evidenskontrakt samt Ruff/compileall passerar.
Första två HTTP-försöken gav 422 före jobbstart; andra svaret bevisar
postnummerfelet 22350 mot fryst Malmöområdes 21120. Första svarets detaljer
saknas. Provets transportbegäran använder nu underlagets entydiga postnummer,
även i köprovet. Inga input-bytes eller native API-grindar ändrade.
Försök 3 sparade fem måltider för 976,32 kr med audit PASS. Därefter stoppade
provverktygets felaktiga likhetsjämförelse mot CLI-priset 988,32 kr: native API
använder `all_advertised`, en annan priskontext. Slutpeak 2,006 GiB, exit 1
utan OOM/swap; ingen full HTTP-kvalificering. Provets återanrop jämför nu strikt
pris/hash/kontext mot den sparade API-menyn och gör ny aktuell audit. CLI-priset
kvarstår som separat övre gräns för första resultatet. Försök 4 körs separat;
alla tidigare kataloger/kvitton/källhashar och en säker resultatssummering bevaras.
Se [HTTP-status](reviews/preparation-memory-20261024/http-history-current.json).
HTTP-steget i försök 4 passerar nu: 976,32 kr/audit PASS, lyckad Save/GET,
annan ägare 404, köat avbrott 0,36 s och aktivt avbrott 6,56 s, högst ett
aktivt jobb. POST 1,21 s, begäran→sparat svar 754,02 s, hela processen 828,36 s.
Slutpeak **2,467 GiB**, cirka 34,15 MiB under målet, exit 0 utan OOM/swap.
En ASGI-observation med befintlig spårning, ingen last-/nätlatenskvalificering.
Första historikåteranropet ger exakt samma pris/hash/kontext på 52,59 s,
faktisk privat revision 1 och elva certifikat laddade utan omsökning.
Alla tre färskprocessprov med borttagen härledd cache passerar:
131,16 / 133,18 / 133,16 s plananrop (median 133,16 s), samma pris/hash/
kontext, privat revision 1 och elva certifikat laddade utan omsökning.
Historik och privat tillstånd bevarade; processerna 190,15 / 192,68 / 192,61 s,
slutpeakar 1,907 / 1,906 / 1,905 GiB, exit 0 utan OOM/swap.
Alla fem grundsteg är klara; kompletterande prov för nytillkomna sparade
menyidentiteter har startat. 43 verifierade metadatafiler i arkiv
`200fd54409e1ffaf1adb7a54071f6d7a95dc9a4a5103dd1acfbc77cfaeff4767`.
Full CI inklusive
Chromium/WebKit passerar även på senaste regressionen `5e7c66a`.
Efter HTTP/historik följer tre prover för var och en av fyra kombinationer
av nya menyidentiteter och cachevägar. Native `PlanStore.create` flyttar den
verkliga privata revisionen 1→2; efterföljande anrop använder faktisk revision
och oförändrade effektiva skafferiindata. Sök-/auditanrop räknas utan att
metoderna ersätts; tiderna inkluderar profileringskostnaden. Dessa storprov
har nu alla tre giltig/förberedd-prov klara: 265,00 / 263,42 / 265,63 s
inklusive profileringshook (median 265,00 s), 976,32 kr/audit PASS, noll
sökanrop och åtta auditanrop vardera, elva certifikat laddade utan omsökning.
Native seed tog 34,63 / 35,64 / 34,53 s, gav 984,22 kr och verklig Save
flyttade privat revision 1→2 i varje kopia. Ankomsterna bevarade två sparade
revisioner och privat tillstånd; högsta slutpeak 1,456 GiB, exit 0 utan OOM/swap.
Även tre giltig/certifikat-prov passerar: 266,52 / 301,05 / 287,82 s inklusive
profileringshook (median 287,82 s), samma 976,32 kr/audit, noll sökanrop och
åtta auditanrop. Elva publiceringar laddade utan omsökning, privat revision 2
och historik bevarade; högsta slutliga ankomstpeak 1,489 GiB, exit 0 utan OOM/swap.
Även tre ofullständig/förberedd-prov passerar: 267,44 / 263,87 / 262,98 s
inklusive profileringshook, median 263,87 s, fem måltider för 976,32 kr/audit
PASS, noll sökanrop och sju auditanrop vardera. Native fyramåltidsseed tog
33,30 / 33,24 / 33,71 s, gav 869,99 kr och sparades på vanligt sätt till
privat revision 2. Ankomsterna laddade elva certifikat utan omsökning och
bevarade historik/privat tillstånd; högsta slutpeak 1,528 GiB, ingen OOM/swap.
Även tre ofullständig/certifikat-prov passerar: 261,47 / 263,59 / 264,20 s
inklusive profileringshook, median 263,59 s, fem måltider för 976,32 kr/audit
PASS, noll sökanrop och sju auditanrop. Högsta slutliga ankomstpeak 1,459 GiB.
Totalt 12/12 ankomster och tolv seedarbetare klara, ingen OOM/swap. Alla 24
arbetares högsta peak 1,666 GiB; enbart ankomster högst 1,528 GiB.
Arkiv SHA-256 `d85fee402cb9e660af283168a94bdf41263668040af7f25cb3749620a83f444d`,
165 metadatafiler verifierade. Full CI på `46c0935` passerar inklusive browserprov.
Första matchade basprocessen på runtime `9162f0f` startade 05:24:43 UTC,
med samma frysta underlag, cacheläge och två CPU/3 GiB. Tre basprocesser
följs av separat instrumenterad fasprofil och därefter hela återstående matrisen.
Första basprovet är nu klart: 881,31 s plananrop, 926,36 s hela processen,
988,32 kr/förväntad hash/audit PASS, slutpeak 2,802 GiB, exit 0 utan OOM/swap.
Baslinjens överskridna 2,5-GiB-mål bevaras; hårda taket är fortsatt 3 GiB.
Även andra basprovet passerar: 879,93 s plananrop, 924,78 s hela processen,
988,32 kr/hash/audit PASS, slutpeak 2,818 GiB, exit 0 utan OOM/swap.
Tredje basprovet passerar på 900,77 s, hela processen 947,50 s, 988,32 kr/
hash/audit PASS, slutpeak 2,802 GiB utan OOM/swap. Baslinjens median är nu
881,31 s mot slutkodens 662,83 s (649,49–664,50 s): **218,48 s/24,79 procent
lägre median** i exakt detta frysta fall. Högsta slutpeak över tre sjunker
från 2,818 till 1,882 GiB, **33,20 procent**. Slutkodens processväggtider
756,71 / 704,55 / 719,74 s har olika anropsantal (4/1/1), ingen blandad median.
Vanliga och instrumenterade tider hålls separat. Ny fasprofil startade
06:11:22 UTC, dess 700-sekundersmål/minneskvitto är nu godkända enligt sammanfattningen ovan.
[Maskinunderlag](reviews/preparation-memory-20261024/matched-current.json),
184 verifierade metadatafiler, arkiv `711dfa0ccfebb7e12f4410d482e0129e070e3a015614565ee016a44bf77bfc59`.
Appfiler och metodsignatur är oförändrade;
fullmatrisens återstående celler och slutgranskning återstår.

---

# 2026-10-24 13:31 UTC: Cacheprov passerar; versionsbyte stoppar piloten

Runtime `b5c242d`, [PR #10](https://github.com/ossebosse/smako/pull/10), har nu
**tre kalla prov** med tom appcache/ny ägarstore: 674,71 / 641,28 / 665,08 s,
median 665,08 s, högst 2,115 GiB cgroup-peak. Alla 988,32 kr/hash/audit PASS.
Alla tretton cachelägesprocesser passerar, högst 2,118 GiB. Omstart och
borttagen härledd cache laddar elva certifikat utan omsökta publiceringar.
Varm 5 000/262-kvot 1,1116 i Malmö/fördelning. Store har noll vanliga
sparade leveranser; riktig historik/HTTP är förberett men ännu inte mätt.

**Versionsbyte/serialisering FAIL:** ordinarie skrivning nådde 2,548 GiB,
överlappande katalogversioner med gammal läsare och fakta kvar **2,706 GiB**.
Katalogernas produktdigest/tidsstämplar och skriven filhash är oförändrade.
Exit 0 utan OOM/swap ändrar inte grinden. **Piloten och fullmatrisen har
inte startat.** Minneskostnaden ska rättas före fortsatt standardkvalificering.
Full CI på `b5c242d` inklusive Chromium/WebKit passerar. Matchade tre basprov
och ny instrumenterad profil återstår. Standard är fortsatt `legacy` och
`library_merge_generations=False`; ingen drift eller samtidighet ändrad.

[Rapport, råhashar och motexempel](reviews/preparation-memory-20261024.md).

---

# 2026-10-24: Tredje ägarprovet missar minnesmål; nästa kandidat verifieras

PR #9 är integrerad på main `b46f608`. Dess runtime `193629f` klarar pris,
menyhash och audit i fyra primärplaner och 17 planer över elva cachelägen. Det tredje provet
med varm offentlig disk och ny syntetisk ägarstore nådde dock **2,624 GiB**
cgroup-peak. Målet 2,5 GiB är alltså **inte stabilt uppnått**; exit 0 utan
OOM ändrar inte det. Versionsbyte/serialisering startade inte eftersom
minnesgrinden stoppade sekvensen. Alla cachelägen och felet finns nu i
maskinunderlaget, inte bara de första åtta.

Nästa runtime `b5c242d`, [PR #10](https://github.com/ossebosse/smako/pull/10),
återanvänder exakt oförändrat legacy-prefix före terminal förfining och
komprimerar endast frysta modellers fältnamnsmetadata med kompatibelt
publikt set-/copy-/serializer-/pickle-beteende. 33 prefixprov, 23
metadata-kompatibilitetsprov passerar; full CI på `ea4bb08` inklusive
Chromium/WebKit passerar.
Ett inläsningsprov behöll priser/fakta och sänkte RSS efter GC/trim från
1 376 272 384 till 1 013 547 008 byte, cirka 346 MiB. Det är diagnostik,
inte en full plan-/minnesgrind. En fryst oracle på `ea4bb08` jämförde samtliga
elva legacy-kandidater med oberoende sökningar: exakt samma menyer och hela
korgar, 3 041 utvärderingar mot 9 517. Det vanliga första anropet tog
709,68 s (tidigare 778,95), cgroup cirka 1,80 GiB, audit PASS. Tre varma
anrop tog 12,31/11,88/11,80 s. Delmålet under 700 s missas; detta är ett prov.
Senaste runtime tillför kooperativa avbrott mellan arbetsenheter med fortsatt
admission och faktisk progress. Ett reproducerat traceback-läckage i avbrutna
jobb är rättat. 33 jobb-/admissionprov och full CI inklusive Chromium/WebKit
passerar på `b5c242d`. Dess första vanliga prov gav **674,71 s**, tre varma
12,36/11,69/12,32 s och cgroup **1,848 GiB**, alla 988,32 kr/hash/audit PASS.
Inläsning 49,52 s; körkommandot inklusive fyra anrop 772,42 s. Detta är
ett kallt processprov, inte tre. Matchad instrumentering är ännu inte
återkörd. Två ytterligare kalla processer och resten av cachelägesproven
pågår seriellt. Inte integrerad ännu.

**Ingen standardkvalificering:** fler kalla jämförbara prov, slutkodens
cachelägen, versionsbyte/serialisering, övrig pilot och slutmatris återstår.
`legacy` och `library_merge_generations=False` förblir standard. Ingen
produktion, aktiv fakta-/prisversion, insamling, schema eller samtidighet
har ändrats. [Rapport och underlag](reviews/preparation-memory-20261024.md).

---

# 2026-10-24: Förberedelseoptimering mätt; kvarstående kvalificering

Kandidat `193629f`, [PR #9](https://github.com/ossebosse/smako/pull/9).
Innehållscachens upprepade kataloginventering och onödig omparsning av
utfärdade recept har tagits bort. Prisavtal i produktindexet lagras kompakt
efter vanlig validering. GC och valfri glibc-trim återlämnar oanvända sidor
vid fasgränser. Oberoende legacy-sökningar och alla elva publiceringar kvarstår.

Fryst Malmö/fördelning/5 000, två CPU/3 GiB: första vanliga anropet
**778,95 s**, tre varma **10,18/10,11/10,29 s**. Alla ger **988,32 kr**, samma
menyhash och audit PASS. Cgroup-peak **2,327 GiB** i denna process; ingen OOM
eller extra swap. Det är ett kallt processprov, inte tre. Delmålet under
700 s är inte nått. Matchad inledande instrumentering på bas/mellanversion
gav 858,60 → 759,31 s och kvalificering 207,00 → 86,83 s, ett prov per arm.

Full CI på runtime `193629f` passerar inklusive Chromium/WebKit. Senast
100 fokuserade tester, Ruff och compileall passerar. Cachelägesmätningar
pågår seriellt med egna syntetiska ägarstore; ingen produktionsaktivering.
**Ingen standardkvalificering:** fler kalla prov, alla cachelägen,
versionsbyte/serialisering, övriga pilotfall och slutmatrisen återstår.
`legacy` och `library_merge_generations=False` är fortsatt standard.

Se [rapport och maskinunderlag](reviews/preparation-memory-20261024.md).
Cellinventeringen räknar 252 identiteter och skiljer uppmätt pilot från
ej körda/slutligt kvalificerade celler. Axfood är fortsatt partiell med
103 verifierade dokument; ingen ny fakta-/prisversion eller drift ändrad.

---

# 2026-10-24: Nästa uppdrag till Sol – minne, förberedelse och slutmatris

Fortsätt enligt [CODEX-SOL-NEXT-20261024.md](CODEX-SOL-NEXT-20261024.md).
Rättningarna i PR #8 är granskade och 126 riktade tester omkörda med PASS.
Nästa steg är att minska första förberedelsens kostnad och hålla minnet
inom målet 2,5 GiB, därefter slutföra verifieringen. Bevara referens-/legacy-
kandidater och rättningarna av båda cachevägarna samt Axfoods stagingflöde.
Det nya dokumentet är ett implementeringsuppdrag; inget nytt standardläge
eller någon produktionsaktivering har utförts.

---

# 2026-10-24: Granskningsfynd rättade; 5 000-prisfelet undanröjt – fortsatt opt-in

Runtimekod `9162f0f`, [PR #8](https://github.com/ossebosse/smako/pull/8).
Nya sparade menyidentiteter konkurrerar nu via båda cachevägarna utan att
publiceringarnas sökningar körs om. Ägar-/raderingsgränser och aktuell
checkout bevaras. Axfoods godkända katalog kan kombineras med basrelease;
LKG, negativa svar och avbrott/återupptagning är verifierade offline.

Gamla fullbibliotekssökningens oberoende vinnare förbereds och kassakontrolleras
per publicering/kontext. Förberedelsekostnaden redovisas. Fryst Malmö/fördelning,
5 000, två CPU/3 GiB: **988,32 kr i alla tre körningar för både legacy och v1**,
samma meny/hash, samtliga audit PASS. V1: 740,87 s första anropet inklusive
215,41 s extra legacy-förberedelse, därefter 8,44/8,37 s. Ny process med varm
disk/beständiga certifikat: 32,01/8,13/8,17 s; hela processen 98,60 s.
Upprepade anrop vid 262 tog 8,38/8,00 s; observerad försiktig 5 000/262-kvot
1,0214 i denna profil. Tolv godkända planer totalt.

**Fortfarande inte standardkvalificerat:** samlad cgroup-peak 2,906 GiB,
omstart 2,639 GiB; ingen OOM men målet 2,5 GiB missas. Hela matrisen,
övriga profiler/städer och isolerad kall v1-kontext/kall OS-disk återstår.
`legacy` och `library_merge_generations=False` är fortsatt standard.
126 riktade tester passerar; full PR-CI på runtimekoden: **3 106 PASS,
10 XFAIL, 53 SKIP**, inklusive Chromium/WebKit. Ruff/compileall godkända.
[Rapport, pinnar och maskinunderlag](reviews/sol-architecture-fixes-20261024.md).
Ingen produktionsaktivering, liveinsamling eller schemaändring utförd.

---

# 2026-10-24: Oberoende granskning – två nya fel att rätta

Se [granskningen](reviews/sol-architecture-review-20261024.md) för reproduktion
och rättningsanvisningar till Sol. En förberedd meny kan ignorera en billigare
giltig sparad meny från samma ägare/kontext; Axfoods kombination
`--approved-snapshot` + `--base-release` avbryts av sin egen stagingkontroll.
89 befintliga riktade prov passerar; två nya offlineprober reproducerar felen.
Appkoden är oförändrad. Tidigare pris-, minnes- och fullmatrisgrindar nedan
kvarstår; v1 ska fortsatt vara opt-in.

---

# 2026-10-23: Arkitektur implementerad opt-in; prisgrind stoppar standardbyte

Runtime är integrerad och pushad till main `c981d75`. Standarderna är fortsatt
`legacy` och `library_merge_generations=False`. V1 väljs uttryckligt med
`library_search_policy=smako-verified-reference-v1`. Referens, separat budgeterat
förbättringsspår, beständiga föregångarcertifikat och små ägarbundna
kvalificeringsvyer använder befintliga planjobb/admission/PlanStore.

**Slutkodens prisgrind faller:** Malmö/fördelning, 5 000 recept, samma frysta
originalfakta/priser/request/klocka, två CPU/3 GiB: legacy 988,32 kr mot v1
992,22 kr i alla tre körningar, samtliga audit PASS. Cgroup nådde 3 GiB,
OOMKilled=false; önskad marginal 2,5 GiB saknas. Ingen standard- eller
samtidighetsökning. Fullmatrisen är inte godkänd: 30 av 252 celler mätta,
övriga explicit ej körda efter prisfelet. Kall disk/ny process med varm disk/
eviction återstår. Se [slutrapport och cellstatus](reviews/verified-reference-axfood-20261023.md).

Alla 14 frysta faktapar vid 262 behöll utfall/pris; separat algoritmprov på samma
berikade fakta gav ingen regression vid 262. Totalt 126 anrop: 117 PASS och nio
fortsatt BLOCKED för Malmö/vegan. Det är inte ett globalt omöjlighetsbevis.
Full [app-CI 40019613139](https://github.com/ossebosse/smako/actions/runs/40019613139)
på `c981d75`: 3 094 PASS, 10 XFAIL, 53 SKIP inklusive Chromium/WebKit.
Riktade prov, Ruff och compileall passerar.

Axfood har 103 verifierade dokument (91 Willys/12 Hemköp), 18 negativa svar,
och immutable v3-release `16410fb3d4e21746a75cb6c34072bb4bcc159c20ceefec2ba1187bb883ac233a`
under både `D:/smako-data/axfood-product-details/releases/` och serverns
`/srv/smako/data/axfood-product-details/releases/`. Partiell täckning redovisas.
Katalograder utgör kön för nya koder; 30 dygn/negativjournal/retry/stopp är
implementerade. Historiska 361,81/340,64 är inte reproducerat: originalarkivet saknas.

[Separat reader-release](releases/axfood-reader-20261023/PROPOSED.md) är förberedd,
inte aktiverad: `source-ops-c981d757b081`, image
`sha256:92be15f2efa053f7c85bc398782d10618e9e1d06dbef24625528862753e6ffbf`.
Exakt tre runtimefiler på aktiv bas `c253cbd9ef93`, native 222-receptsbibliotek
bevarat, 14 native profilpar/tre upprepningar utan utfalls-/prisändring,
färsk faktaprojektion identisk och isolerad readiness/rollback 200 i båda städerna.
Readiness-klonen använde temporära databaser/syntetiska nycklar och hade
källfakta-prewarm avstängd; färsk projektion verifierades separat. Fullt
produktions-prewarm är inte mätt. Ingen produktionsdatabas monterades i
kandidatproven; prispekarna var oförändrade under klonprovet.

Produktion kör fortfarande `app-c253cbd9ef93-9940259d`. Inget schema eller
Axfood-runtimevärde har ändrats. Principgodkännandet är redan givet; ett konkret
appbyte/nytt automatiskt insamlingsschema kräver separat driftbeslut enligt BETA.md.

---

# 2026-10-23: Arkitektur beslutad, implementation lämnas till Sol

Ägaren har godkänt Axfood-berikningen. Implementeringsuppdraget finns i
[CODEX-SOL-ARCHITECTURE-20261023.md](CODEX-SOL-ARCHITECTURE-20261023.md).
Det beslutar verifierad referensmeny med separat förbättringssökning,
versionsbunden kvalificering och Axfoods lagring/uppdateringspolicy.
Principgodkännandet för berikningen ska inte efterfrågas igen; ett konkret
driftpaket följer fortfarande det dokumenterade releaseförfarandet.

Detta är en dokumentationsleverans. Ingen ny appimplementation, insamling,
schemaändring eller aktivering är utförd. Tidigare mätresultat nedan är
oförändrade; deras öppna arkitektur-/ägarfrågor ersätts av det nya beslutet.

---

# 2026-10-23: 238 skalningsprov slutförda – standardbyte underkänt, ej aktiverat

Granskad appkod `b139cd4`, samlad i
[PR #7](https://github.com/ossebosse/smako/pull/7). Rapport, kod-/datapinnar,
kommandon och maskinunderlag finns i
[integrationsgranskningen](reviews/integration-scaling-20261023.md).
Hämtad main `2efb62f`: full CI **2 950 PASS, 10 XFAIL, 53 SKIP**.
Kandidatens appkod: **3 012 PASS, 10 XFAIL, 53 SKIP**, inklusive webbläsartester.

**Verifierat med faktiska serverfakta:** 40/40 recept kvalificeras och
kassakontrolleras i båda städerna. Alla 97 godkända äggprodukter i Lund och
186 i Malmö är hela skalägg med användbara gram. Mängdspärren undantar bara
sju kända näringskonflikter; okända prefix blockerar. Alla 14 par av tidigare
och nuvarande standardsökning, tre iterationer per arm, behåller utfall/pris;
samtliga lyckade menyer har samma hash. Malmö vegan är blockerat i båda.
Slutkodens main/262 återkontrollerar också alla 14 mot ursprunglig main.

**Matrisen är komplett:** 238/238 celler, 221 godkända menyer och 17 väntade
Malmö-veganblockeringar. Strikt nästlade 262/1 000/2 000/5 000-bibliotek,
main/K16/K32/K48 samt v5-referens vid 262. Ingen giltig meny blev dyrare
mellan de uppmätta storlekarna för något K. Men alla tre K bryter main/262-
priskravet för Lund/fördelning vid samtliga fyra storlekar. Vid 262:
main/referens 761,45 kr, geo 783,42 kr. Vid 5 000: main 704,30 kr,
K32/K48 769,29 kr. **Sammanslagna kohorter förblir av som standard.**

Sökspåren förklarar missen: main går via generation 8/11/12 till den
billigare menyn; geo hoppar 2 → 13. Prefixarkiv v3 bevarar geo-vinnare
utan återkoppling till dess primära väg, men ersätter inte main-vägen.
Historiska Lund 1 000/K48 behåller 469,84 kr mot main 474,43 kr.
Små genererade utbytbara pooler söks uttömmande upp till 4 096 kombinationer,
med befintliga krav och slutkontroll; ingen global optimalitet påstås.

**Malmös minnesprov passerar:** alla 119 celler under oförändrat 3 GiB-tak.
Högsta RSS 3 149 504 512 byte, högsta cgroup-minne 3 167 059 968 byte
(cirka 2,95 GiB). Marginalen är liten; detta är ingen fleranvändarkapacitet.
Frysta registrerade receptdelar delas efter exakt innehållskontroll,
muterbara behållare förblir privata och offertbudgetens sidomappar räknas.
1 310 skalningar samt 1 310 kvalificerade värden/ID:n är identiska.

Två nya processer med samma slutkod, bibliotek, indata, inställningar och
varma diskcache ger samma Malmö 5 000/K48-meny/hash: hela processerna
187,02/188,11 s, planering 145,44/146,52 s. Båda har 8 217 träffar,
2 142 missar, noll skrivningar och noll ogiltiga poster. En exakt formgräns
undviker Malmös omöjliga veganveckosökning: en form, tak två, begärda tre.
Ingen regel eller klassificering sänks; samma `SEARCH_BLOCKED`.

**Proxyprovet underkänns för generell gallring:** 272/946 kandidater vid
1 000 behåller 487,85 kr, andra anropet 33,95 mot full pools 37,74 s.
Vid 5 000 behålls 528/4 946, men K32 blir dyrare: 487,85 mot 480,97 kr,
trots 50,07 mot 73,92 s. K48 behåller 487,85 kr, 51,03 mot 73,90 s.
Wrappern bevarar faktisk cacheåterlämning av 256 kvalificeringsresultat;
orakelprovet räknar om varje memoträff. Tidigare felinstrumentering bevaras
separat. Ingen produktionssamplare har införts.

**Skalningsmålet är alltså inte uppnått:** prisregressionerna och växande
beräkningstid kvarstår. Aktivera inte försökslägena med hänvisning till
de genomförda mätningarna. Sex positiva återkontroller på `b139cd4` matchar
Lunds `c9390dd`; AST-beviset binder den enda negativa kapacitetsskillnaden.
Kod-/tidsversioner och mätprotokoll är uttryckliga i varje underlag.

**Axfood återstår som separat ägardel:** detaljarkivet återfanns inte i kända
lokala worktrees. Varken berikade aktuella exporter eller det äldre
Malmö-fallet 361,81/340,64 kr är därför återverifierade. Tidigare 503
återstående Hemköp-koder, lagring, uppdateringsrytm och aktivering kräver
ägarbeslut; ett konkret lagrings-/verifieringsförslag finns i rapporten.

Alla benchmarkprocesser har avslutats. Bevara underlagen i
`.local/integration-scaling-20261023`, serverns motsvarande evidence-katalog
och de isolerade testbibliotekens worktrees. Ingen produktion, scheduler,
butiksinsamling eller aktivt prismanifest har ändrats av granskningen.

---

# 2026-10-23: Receptgrenen integrerad på main – ej aktiverad

`content/recipes-20261021` är sammanslagen med main: de 40 recepten, alla pack
av hela skalägg, Axfood-produktdetaljer (av i drift), exakta
prestandaförbättringar och screening av substitutioner (på, samma hash i alla
uppmätta fall). Geometriska kohorter är kvar som opt-in. Ingen release,
aktivering eller schemaändring är gjord.

Lokal offline-svit (Windows, CI:s kommando): 2 890 PASS, 10 kända XFAIL,
55 SKIP. 14 backup/återställnings-/driftsättningsfel fallerar identiskt på
main före integrationen (miljö); 43 webbläsartester saknar lokala
Playwright-webbläsare. Startkontroll och Ruff på ändrade filer godkända.
GitHub-CI ska bekräfta.

**Instruktioner till Codex:** [`docs/CODEX-NEXT-20261023.md`](CODEX-NEXT-20261023.md).

---

# 2026-10-23: Ägg, Axfood-fakta, utbackning och receptskalning – ej aktiverat

**Main:** `e6f7d32`/`ea847bb` är utbackade (`e190f3e`); resten integrerades
samma dag (se ovan). **Gren `content/recipes-20261021`:** de 40 recepten, alla pack
av hela skalägg i äggrecept (Lund 102, Malmö 192, alla med gram), Axfood-
produktdetaljer som fakta och exakta prestandaförbättringar (samma hash):
varm planering vid 5 000 recept 144 → 100 s i Lund och 176 → 109 s i Malmö.

Försök som inte är standard: geometriska kohorter med prediktorordning
(`library_merge_generations`, `library_substitution_slot_limit`) håller
veckosökningen på 17–29 s från 262 till 5 000 recept och gav lika eller
billigare menyer med fler recept (Malmö 5 000: 470,62 mot 507,00 kr), men
Lund 1 000 blev 0,8 % dyrare än dagens sökning; alla profiler måste mätas.

Axfood: Willys klar (10 766 dokument), Hemköp 503 koder kvar (hämtningen
stoppad på begäran, återupptagbar). I frysta Malmö-data: protein40 och
all-macros 915,84 → cirka 740 kr; vegan 21 kr dyrare (sökmiss). **Inte i
drift:** kräver `AXFOOD_PRODUCT_DETAIL_ROOT` i en granskad release.

Kvar: sökningen som standard, kvalificeringen (linjär, cirka 6 ms/recept
varmt; kallstart ska mätas om), minne vid 5 000 recept i Malmö (~3,6 GB),
Axfood i drift, integration av grenen i main efter full CI.
Underlag: [`docs/reviews/recipe-scaling-20261023.md`](reviews/recipe-scaling-20261023.md).

---

# 2026-10-22: Regression i veckosökningen på main, receptgranskning – ej aktiverat

**`e6f7d32` (från PR #4, på main sedan `d3ecf2c`) gör planeringen 2–5 gånger
långsammare vid samma meny**: Lund all-macros 116 s (P `92c4abd`) → 405 s
varm, korgberäkningar 12 441 → 42 001. Den slutförfinar varje
biblioteksgeneration; samma ändring backades ut ur kategorisökningens release
men kom tillbaka via PR #4-sammanslagningen. Aktiv produktion `c253cbd` saknar
den. Beslut krävs före nästa release från main.

Gren `content/recipes-20261021` (`6496586`): kockgranskning av 20
variety-recept med fyra rättelser. Mätt på frysta data 2026-10-18 i Lund och
Malmö: Codex 20 sänker menyer 2,6–9,8 %, variety 20 bara Lund standard
(−5,7 %). Sökgränserna gav aldrig dyrare meny. Äggrättelsen godkänner 79/144
rena äggpack (tidigare 6/0) och inga sammansatta äggprodukter. Axfoods
produktdetalj ger ingredienser och näring, men alla värden har precisionen
`CA` (cirka). Underlag och beslutspunkter:
[`docs/reviews/recipes-20261022.md`](reviews/recipes-20261022.md).

---

# 2026-10-22: Primat har ICA-baspriser i Lund och Malmö – verifierat live

Primat saknar inte generellt ICA-baspriser i området. Läsande kontroll med
Smakos befintliga API-åtkomst gav HTTP 200 från `/api/v3/stores?all=1`
2026-10-22 **13:26:13 UTC / 15:26:13 svensk tid**. Följande butiker har
källans `tier=full`, `available=true`, och verifierade produktpriser utan
aktiv kampanj:

| Ort | Butik | Primat store_id | Exempelpris, kr |
| --- | --- | --- | ---: |
| Lund | Maxi ICA Stormarknad Gunnesbo | `1088004` | 16,94 |
| Malmö | Maxi ICA Stormarknad Västra Hamnen | `1003569` | 17,85 |
| Malmö | ICA Kvantum Malmborgs Mobilia | `1004037` | 17,93 |
| Malmö | ICA Kvantum Malmborgs Caroli | `1004490` | 17,88 |
| Malmö | Maxi ICA Stormarknad Malmö, Cypressvägen | `1004492` | 17,50 |

Prisexemplet är samma Valio Mjölkdryck Laktosfri 3 %, 1 liter,
produkt-ID `1363406`, GTIN `6408432086564`. Samtliga exempel hade
`prices.regular` enligt tabellen, `offer=null`, inga medlems-/flerköpspriser
och `confirmed_at` den 22 oktober. Exempel:
[Gunnesbo](https://primat.nu/vara/ica/1088004/1363406),
[Mobilia](https://primat.nu/vara/ica/1004037/1363406).

Ett gemensamt `/api/v3/products?q=mjölk&stores=...&limit=100`-anrop med
de fem exakta butiks-ID:na gav HTTP 200 och 100 produkt-/butiksrader,
varav 98 hade positivt `regular` och `offer=null`. Alla fem butikerna
bidrog med sådana rader. Detta är ett begränsat stickprov;
`full` är Primats deklarerade täckning, inte en egen genomräkning av
hela sortimentet. Enligt [API-kontraktet](https://primat.nu/api/v3/openapi.json)
kan `regular` också innehålla offentliga kampanjpriser, varför fältet ensamt
inte bevisar ett ordinarie baspris. `confirmed_at` avser senaste kontroll,
medan `changed_at` anger senaste prisändring.

**Clemenstorget `1004409` är fortfarande `offers_only`**, liksom bland andra
Tuna, Brunnshög och Linero. Augustis äldre fullklassning får inte användas
som aktuell täckning. Den tidigare obligatoriska kombinationen av Gunnesbo
och Clemenstorget blockerades av Clemenstorgets ändrade källkontrakt;
det innebar inte att Gunnesbos baspriser saknades. Se
[tidigare kontraktsutredning](../reports/lund-base-strategy-20260928/PRIMAT-CONTRACT.md).

Aktuell scheduler hade vid kontrollen **`OWN_SOURCES_ONLY=true`** och
befintlig Primat-nyckel. I `grocery_data/__main__.py` hoppar detta läge över
Primat-uppdateringen med `explicit_own_sources_only` och noll leverantörsanrop.
Smakos nuvarande bortval av Primat ska därför skiljas från faktisk
datatillgång hos leverantören.

Möjlig fortsättning är att kvalificera de fem katalogerna i befintligt
prisflöde. Exakt butiksidentitet, priskanal, produktidentitet och
kampanjsemantik måste verifieras före integration. De kontrollerade
produktlänkarna pekar på ICA:s e-handel; fysiska hyllpriser är inte belagda.
Inga kataloger har importerats, ingen runtime/policy har ändrats och ingen
deployment har gjorts i denna kontroll. API-svar granskades i sessionen;
ingen separat råsvarsfil sparades och inga hemligheter dokumenteras.

---

# 2026-10-21: 40 recept, äggnamn i Malmö och faktalucka – ej aktiverat

Gren `content/recipes-20261021` ovanpå `d3ecf2c`: äggrättelse för Malmö,
Codex 20 tillväxtrecept och 20 nya recept. Lund standard: 548,76 → 486,85 kr
men varm planering 63,6 → 91,9 s. Willys/Hemköp saknar ingredienser och näring
i båda städerna; Malmö har ingen Coop-katalog. Instruktioner för nästa
granskning (mätning/regression, beslut om recepten, produktdetaljer från
Axfood): `docs/reviews/recipes-20261021.md`.

---

# 2026-10-21: Smakomedlemskap aktivt och liveverifierat

Aktiverat **11:07:40 UTC / 13:07:40 svensk tid**, kod `c253cbd9ef93`,
BUILD_ID `app-c253cbd9ef93-9940259d`. Full CI och publika medlemsprov är
godkända. Befintliga 310 planrevisioner och 119 privata tillståndsrader,
prismanifest, scheduler och proxy bevarades. Backup `20261021T101710Z`.
[Aktiveringsjournal](releases/membership-20261021/ACTIVATED.md).

**Efterretention pågår vid journalföringen.** Appbytet är klart och ska inte
upprepas. Releaseverktyget körde flera fulla lagringskontroller på cirka
40 minuter vardera; de två avslutade fristående kontrollerna frigjorde 0 byte.
Detta och backupen förklarar den långa väntan. Kontrollera det befintliga
releaseförsökets `storage-after-activate.json` innan driftsarbetet markeras helt
avslutat. Starta inte en ny aktivering eller parallell lagringskörning.

Gästläge är kvar med högst **3 recept per meny och 2 portioner per recept**.
Kostnadsfritt konto med e-post/lösenord låser upp planerarens befintliga större
menyer och ett kontokopplat skafferi mellan enheter. Registrering, inloggning,
utloggning och återställningskod finns under `/personal#account`. Befintlig
OIDC-inloggning fungerar fortsatt när den är konfigurerad.

API-spärrarna omfattar även personliga måltidstyper, egna recept, asynkrona
jobb och ändringar i sparade planer. Gästskafferi, profil och planer kan flyttas
atomärt till ett tomt konto; befintliga kontodata skrivs inte över. Manuell
skafferiinmatning har också rättats där ett odefinierat fält tidigare stoppade den.

Verifiering: **314 riktade tester godkända, 3 befintliga XFAIL**. Det omfattar
270 konto-/API-/planerings-/integritetstester, samtliga 42 formulärtester och
två regressionsfall för receptbyten. Kontoacceptans kördes i Chromium på
1280 px och WebKit på 390 px, med riktiga isolerade konton och skafferidata.
Ruff, compileall, JavaScript-syntax och diffkontroll är godkända. Underlag i
`.local/membership/`. Detta är riktad verifiering, inte hela projektets CI-svit.

Den separata granskade releasen lade till tre privata tabeller i den
befintliga plandatabasen med verifierad backup och bevarat äldre schema.
Ingen extern e-posttjänst eller betalning ingår. Återställningskoden
måste sparas av användaren. [Funktion, lagring och begränsningar](MEMBERSHIP.md).

---

# 2026-10-21: Kategorisökning aktiv och liveverifierad

Aktiverad **00:27:05 UTC / 02:27:05 svensk tid**. Runtimekod `73306ac`
är integrerad på main via PR #6. BUILD_ID `app-73306acc382d-0d139487`,
image `sha256:0ad2b6021e6a71b5a849edb42430d0a94c33ea152e58984353de8124182a0830`.
Både Lund och Malmö är ready. Endast appen byttes; scheduler, proxy,
volymer och aktiva prismanifest bevarades. Verifierad backup
`20261020T233117Z`. Samtliga tidigare 304 planrevisioner och 115 privata
tillståndsrader är bevarade inklusive radhashar.

Full CI är grön för koden och main-integrationen: 2 854 PASS, 10 XFAIL,
53 SKIP. 26 riktade tester, 24 frysta jämförelsekörningar och två
fullpoolskontroller är godkända. Blandade kategorier tar ungefär halva
tiden vid samma pris och matkök. Helt vegetariskt i Lund är något långsammare.
[Aktiveringsjournal](releases/category-search-20261020/ACTIVATED.md).
[Verifiering och driftåtgärd](reviews/category-aware-recipe-search-implementation-20261020.md).

Fyra publika menyer och två receptbyten är godkända i Lund/Malmö:
exakta kvoter, fem olika grundrätter, godkänd korg, högst två tillåtna
butiker, identisk sparad återläsning och bevarad äldre revision vid byte.

**Slutfört:** efterretentionen fick `complete` och releasekommandot exit 0
01:06 UTC. Cirka 823 MB filer togs bort under referensskydd, 32 snapshots
pensionerades. Nattens Malmöpaket återlevererades efter låskonflikt och
fördröjd laddningsbekräftelse; kvittens `already_active` 01:46:20 UTC, exit 0.
Slutkontroll 01:46 UTC: båda kommunerna ready med rätt BUILD_ID, alla 14
obligatoriska kontexter kvalificerade/publicerade/laddade och inga väntande
lokala reläleveranser. Coops basunderlag har kvar sin STALE-varning, cirka
74 timmar, med oförändrad källtid. Scheman och installerat relä är oförändrade.

Underlag: `.local/category-search-20261020/`, särskilt `final-status.json`,
`final-municipalities.json`, `deliver-malmo-confirm.log`, `http-evidence.json`
och `release-final/activate.json`. Appen är redan aktiverad; bygg eller
aktivera inte samma release igen. Alla operatörsjobb i denna uppgift är klara.

Willys-incidentens kvittens återställdes 2026-10-20 20:11:30 UTC via
installerat relä, exakt redan aktiv Lundartefakt och `already_active`.
Ingen ny insamling, förnyad observationstid eller schemaändring gjordes.
Äldre text nedan är historik.

---

# 2026-10-20: Självstädning aktiverad och efterkontrollerad

Godkänd scheduleraktivering är slutförd 15:37:12 UTC (17:37 svensk tid).
Aktiv runtime: `source-ops-52c7d8291bb7`, image
`sha256:9611e23f2ee6ef6360ccff05889262240024fd1791b94bcfdd20d0c27f4f525e`.
Endast schedulerns image och BUILD_ID ändrades. Cronfil, mountar,
app/proxy och aktiva prismanifest bevarades. Ordinarie Malmö-jobb fick
avslutas före driftlåset; inga källjobb stoppades.

Den genomförda körningen raderade 2 402 915 323 byte filer: 32 snapshots
pensionerade, 11 921 råfiler, fem prisartefakter och 79 kommunala poster.
SQLite har dessutom 420 208 640 återanvändbara byte. Detta tillkommer
utöver tidigare 83,36 GB rensade dagsbackuper/prisfiler. Periodiska hookar
är nu aktiva vid start, backup och ordinarie refresh.

Backup `20261020T144738Z` är verifierad. Alla tidigare 302 planrevisioner
och 113 privata tillståndsrader är bevarade, liksom källidentiteter och
observationstider. Tre dagsbackuper upptar totalt 24 716 243 845 byte.
De två ersatta kandidatbilderna är borttagna; aktiv image och
återställningsbasen finns kvar. Byggcachebudget 2 GB.
Efterkontroll 15:39 UTC: 88,21 GB ledigt, alla tre tjänster igång,
noll omstarter och ingen OOM-status.

Lund och Malmö har ready 200 och alla 14 obligatoriska kontexter
kvalificerade, publicerade och laddade. Två publika menyprov passerade:
fem kompletta recept, två tillåtna butiker, godkänd korgkontroll och
identisk återläsning av sparad plan. Svarstider 75,34/77,52 sekunder;
detta är funktionell efterkontroll, inte nytt prestanda-/prisbevis.
Coop STALE och Willys AGING är kvarvarande åldersvarningar.
Windowsjobbet körde vid statusläsningen; ingen ny reläleverans styrks här.

Slutkod `52c7d82` finns på main och har grön full CI:
2 841 PASS, 10 kända XFAIL, 53 SKIP. Slutbildens isolerade Linuxprov:
31 PASS, 0 SKIP. Retentionsfrågorna/indexen och SQLite-cachebudgeten är
verifierade mot target. Den tillfälliga backupcontainerns filcachebudget
höjdes till 4 GiB under kontrollen, med bevarad minnesreserv; detta ändrade
ingen permanent tjänstekonfiguration.

[Aktivering, kvitton, testresultat och begränsningar](reviews/storage-lifecycle-20261020.md).
[Analys av kategorikvoter och varierat urval](reviews/category-aware-recipe-search-20261020.md).
Appens receptsökning och RAM-cache är fortfarande det separata utkastet
[PR #4](https://github.com/ossebosse/smako/pull/4), inte aktiverade här.
Inga nya kategori-/urvalsgränser är införda. Äldre text nedan är historik.

---

# Tidigare leveransstatus 2026-10-20, före godkänd aktivering

Lagringsrättningarna är integrerade och pushade på main, avskilda från
receptskalningen: `9d6efed`, `429109a`, `8d5a49a`, `3825322`, `0b7e9a6`, `3e8a01a`.
De inför gemensam retention före backup, vid schedulerstart, under befintliga
refreshjobb och i appuppdateringsflödet. Aktuella priser, LKG,
importidentiteter, observationstider och minst två verifierade backuper
bevaras. Full CI för motsvarande granskade kod: 2 862 PASS, 10 kända XFAIL,
53 SKIP. Radslutstillägget klarar ytterligare 21 riktade tester.
Den separata main-integrationen `d9f8dbf` har grön full CI:
**2 836 PASS, 10 kända XFAIL, 53 SKIP**. Kandidatens egen Linuxruntime klarar
26 isolerade retentions-/backup-prov, med 768 MiB och utan produktionsvolymer.

En avgränsad serverrensning är genomförd: 83,36 GB gamla dagsbackuper och
orefererade prisartefakter borttagna. Efterkontroll ready 200 och identiska
publicerade/laddade manifest. Inga käll-/användardatabaser eller images
rensades av den körningen. Det är inte bevis för aktiverad periodisk städning.

Schedulerkandidat `storage-maintenance-8f9221e168d8` är byggd och verifierad:
image `sha256:c54f949d591c1d4cc2c48698ed5cff79babdde12faac9498e0e1f6805403394c`,
image-BUILD_ID `source-ops-8f9221e168d8`. Tio ändrade runtimefiler och
623 hashidentiska; exakt konfiguration, importprov utan nät och två lager
i stället för basbildens 199. **Inte aktiverad.** Ordinarie driftlås var
upptaget vid förnyad källinventering; inget jobb avbröts.
11:09 UTC svarade Lund/Malmö ready 200 och servern hade 82,91 GB ledigt.
Den föregående samlade statusläsningen nådde sin tidsgräns och gav
serverstatus unknown; en ny komplett driftkontroll behövs före aktivering.

Aktiv scheduler är fortfarande `hemkop-context-scheduler-c6607a095018`;
app `app-bac0fc15ca9a-512ef3ea`. Ingen Windowsuppgift eller timer ändrad.
Före schedulerbyte: nytt statusunderlag, ledigt lås, backup och oförändrad bas.
[Policy](storage-maintenance.md), [verifiering och exakt kandidat](reviews/storage-lifecycle-20261020.md).

Receptskalningen ligger fortsatt i utkast-PR #4. Färdiga generationsvinnare
bevaras nu (`e6f7d32`, `ea847bb`) och delad cache släpper pensionerade
prisuniversum (`cd9f148`). Syntetiska regressioner och full CI passerar;
nya oberoende pris-/tid-/minnesprov vid 1 000/2 000 recept saknas.
Skalningskod och appaktivering ska inte sammanblandas med lagringsleveransen.

---

# 2026-10-18/19: Priser återställda; reläschemabyte väntar administratör

Kod `c6607a0` (Hemköps butikskontext), `84b2de8` (Willys checkpoints) och
`2464596` (reläets tidsreserv) är integrerad och pushad till main.
97, 126 respektive 81 riktade testkörningar, Ruff, compileall och samtliga
tre kodcommitars GitHub-CI passerar.

Hemköps rättning är aktiv i scheduler sedan 18 oktober 20:22:58 UTC,
BUILD_ID `hemkop-context-scheduler-c6607a095018`. Sex kompletta kataloger
återspelades med 570 verifierade råhashar, 43 146 godkända produktposter och
ursprungliga observationstider. Alla sex är publicerade och laddade.
Willys har nya godkända kataloger: Lund 19 423 produkter, Malmö 39 949,
båda med noll fel och beständiga reläkvitton. Malmö kvitterades 19 oktober
00:40:16 UTC efter kontroll av redan aktiv artefakt, utan en andra ombyggnad.

Slutkontrollen visar alla 14 obligatoriska källkontexter FRESH, kvalificerade,
publicerade och laddade, med HTTP 200/ready och överensstämmande manifest.
Publika personliga menyprov passerar i båda kommunerna: fem recept, två
butiker, godkänd kassakontroll och identisk sparad GET. Lund 40,38 s och
Malmö 83,92 s. Appversionen är fortsatt `app-bac0fc15ca9a-512ef3ea`.
Alla 299 tidigare planrevisioner och 110 privata tillstånd är hashbevarade.
Inga omstarter eller OOM. Ledigt utrymme 30,97 GB mot högsta beräknade behov
15,28 GB efter verifierad backupkomprimering; ordinarie retention är bevarad.

Willys checkpointfix undantar SCB:s varierande transporttidsstämpel från
identiteten men bevarar verifierad geometri, råhashar och observationer.
Tidsrättningen reserverar 45 minuter för import/publicering inom oförändrat
totalt körfönster. Slutkandidaten `2464596b6f07` är separat installerad,
integritetskontrollerad och provkörd genom sin riktiga startpunkt: båda
kommunerna `not_due`, kod 0, utan nya insamlingar.

**Kvar:** Windowsuppgiften pekar fortfarande på `5b344ca3b50e`.
Set-ScheduledTask nekades åtkomst och UAC-starten avbröts. Konto, schema,
action och inställningar är oförändrade. Den befintliga uppgiften provkördes
00:40:50 UTC med LastTaskResult 0 och oförändrade färska kvitton; detta
aktiverar inte den nya koden. Förberett administratörssteg finns i
`.local/source-recovery-20261018/activate_relay_elevated.ps1` och kräver
slutkandidatens godkända bevis före bytet. Det nya schemabytet behöver
administratörsgodkännande och efterföljande verifiering.

[Rapport och evidens](releases/source-recovery-20261018/REPORT.md).
Separata kampanjposter med ej stödda villkor förblir spärrade. Historisk
`ops repair` kan märka en användbar publicering med exitkod 2 som `failed`;
bedöm den mot faktiska manifest och laddningsbevis innan något körs om.

---

# 2026-10-18: Betan aktiverad och skalningsuppgift till Claude committad

Aktiverad 19:39 UTC: BUILD_ID `app-bac0fc15ca9a-512ef3ea`, kod `bac0fc1`.
Uppstarts-/fakta-/recept-/sökrättningarna och exakt offertåteranvändning är
aktiva med 222 recept. De 20 experimentrecepten ingår inte.

Fyra publika menyprov PASS, inklusive kassakontroll och identisk sparad GET.
Lund 52,11/38,77 s; Malmö 55,23/52,23 s (första/nästa HTTP-prov).
295 tidigare planrevisioner och 106 privata tillstånd är hashbevarade.
Prewarm false; inga nya OOM eller omstarter. Scheduler, proxy, miljö,
volymer och prismanifest bevarades vid bytet. Befintliga källvarningar kvarstår.
Releasebackupen är komprimerad och hashverifierad. Slutkontroll 19:49 UTC:
ready/200, 16,69 GB ledigt mot beräknat behov 13,99 GB.

[Aktiveringsrapport och evidens](releases/planner-startup-20261018/ACTIVATED.md).
Releasepaketet bevarar uttryckligen betans tidigare admin-lösenordsinställning,
som saknas i main; se granskningen. Övriga 25 ändrade filer matchar Git exakt.
Full konsolidering av äldre serverändringar är fortfarande en separat uppgift.

[Uppgift till Claude: tusentals recept och variationer](CLAUDE-RECIPE-SCALING.md)
är committad i `540b123`: första milstolpe 1 000 recept, skalningsmatris,
bevarat pris/kvalitet och tydliga verifieringskrav.

---

# 2026-10-18: Exakta butiksjämförelser återanvänds – ej aktiverat vid granskningen

Slutversion `90ddeeb` minskar Malmös varma standardtid 55,88 → 52,21 s
(6,6 %) och kalla ekotid 219,45 → 196,26 s (10,6 %). Samma 242-receptbibliotek,
menyer, priser och fullständiga resultathashar. Söktak och kvalitetskrav är
oförändrade. Extra minne från första försöket är borttaget: ekoprovet använder
åter cirka 2 482 MiB RSS. Lund har ingen säkert visad tidsvinst.

[Full granskning, mätningar och begränsningar](reviews/planner-exact-speed-20261018.md).
Full lokal backendsvit: 2 835 PASS, 10 kända XFAIL, 2 SKIP. Slutversionens
GitHub-CI är grön, inklusive webbläsartester. Ingen produktionsaktivering;
de 20 nya recepten är fortsatt endast experimentunderlag.

---

# 2026-10-18: 20 author-recept och uppmätt bibliotekstillväxt – endast testbibliotek

20 nya prototyprecept skapade/importerade med ordinarie author. 222 → 242
recept, samtliga 20 köpbara i både Lund och Malmö och godkända av standardfiltret.
36 isolerade serverplaneringar passerar kvalitetskontrollerna. Varm standardtid:
Lund 37,94 → 37,11 s; Malmö 49,60 → 57,45 s (+15,8 %). Varm näringsprofil:
Lund 146,76 → 140,40 s; Malmö 24,79 → 30,51 s (+23,1 %).
Menyerna blir 2,6–9,8 % billigare; inga söktak ändrade. Standardprofilen
upprepad i omvänd ordning. Frysta priser/fakta och samma runtimekod i båda armarna.

[Full metod, kalla/varma värden, recept och underlag](reviews/recipe-growth-20261018.md).
Recepten ligger som experimentunderlag i docs, inte i produktionsbiblioteket.
Ingen aktivering. Testmiljön avslutad, 854 MB egna temporära filer rensade efter
verifiering. Slutkontroll 16:05 UTC: ready/200, prewarm false, 19,16 GB ledigt.

---

# 2026-10-18: Rättelsepaketet granskat och integrerat på main – ej aktiverat

Sex patchcommits `9ec318c..ad0411f` ovanpå `412ebd8` är granskade utan
ytterligare runtimeändringar. Full rapport för Claude:
[verifiering av rättelsepaketet](reviews/review-fixes-verification-20261018.md).

- De tidigare tre P2-felen är rättade: fullbiblioteksreferensen, partiellt
  persisterade faktaprojektioner och authors vatten-/decimalskalning.
- Alla sju profiler i båda städerna: 18/18 takpytest PASS. Alla 20 serverpar
  passerar; de 14 positiva har samma pris/hash, de sex negativa samma felutfall.
  Defaultresultaten matchar föregående granskning. Inga tak höjdes.
- Fullsviter: 4 743 PASS, exakt samma 15 kända fel, två separat körda taktester
  SKIP. Första PR-CI `39120341250` grön: 2 783 PASS, 10 XFAIL, 53 SKIP,
  inklusive fungerande webbläsartester. PR [#2](https://github.com/ossebosse/smako/pull/2).
- Alla 28 receptversioner och 55 vattenfall verifierade. 235 äggviktsbevis
  korrekta; enda faktadeltat är Lunds Brunchägg L/XL 6-pack, 360 g.
- ~~Kvarvarande P2~~ rättad på grenen `fix/full-library-reference-contract`:
  `--uncapped-reference` kräver nu uttryckligen `seed=0`, `refinement=0` och
  `seed_variant_shortlist=false` (typkontrollerat, `0`/`None` räknas inte) och
  avvisar äldre rapporter utan flaggan innan planeraren byggs. Nya referenser
  märks `reference_contract: smako-full-library-reference-v1`; omärkta rapporter
  med alla tre flaggor accepteras. Metodsignatur jämförs avsiktligt inte.
- Prestandamålet och reproducerbar releaseimage kvarstår. Äldre kall/varm-
  mätningar är historisk evidens; denna matris är ett funktionellt prov.
- Slutkontroll 11:59 UTC: ready/200, samma produktionsimage, prewarm false,
  backup complete och 20,02 GB ledigt mot 13,99 GB beräknat behov. Egna
  testunderlag arkiverade med hashkontroll; temporära cachefiler borttagna.

---

# 2026-10-18: Rättelser efter uppföljningsgranskningen – ej aktiverat

Gren `fix/review-20261018` ovanpå `d41339d`. De tre reproducerade P2-fynden i
`docs/reviews/planner-followup-review-20261018.md` är rättade med
regressionstester, och Brunchägg L/XL får standardvikt. Detaljer, tester och
granskningssteg: `docs/reviews/review-instructions-20261018.md`.
Prestandamålet och releaseimagen är fortsatt öppna punkter. Backupfelet har
åtgärdats efter patchens basversion; se lagringsposten nedan.

---

# 2026-10-18: Serverlagring rensad och backup återställd

22,41 GB netto frigjort under befintligt driftlås. Sex inaktiva arkivkataloger
komprimerades från 29,50 till 7,13 GB; alla 185 poster verifierades före
borttagning av originalen. Arkiv, privata inventarier och återställningspekare
är bevarade. Oanvänd Docker-byggcache rensades, men inga images, containrar,
levande databaser, prisartefakter eller ordinarie dagsbackuper raderades.

Ny backup `20261018T084659Z` är `complete` (Lund och Malmö, 68 filer/7,63 GB).
Efter backupen: 20,98 GB ledigt, tillräckligt enligt driftkontrollen;
HTTP 200/ready. Containerkonfigurationer, images och aktiva prismanifest är
oförändrade. Prewarm är fortsatt false. Inga scheman eller retention ändrades.
Det tidigare rapporterade backupfelet `InsufficientStorageError` är därmed
åtgärdat för den verifierade körningen. Se [lagringsrapporten](storage-maintenance.md)
och [kvittot](releases/storage-maintenance-20261018/VERIFIED.json).

---

# 2026-10-18: Uppföljningspatch granskad och integrerad på main – ej aktiverad

13 patchcommits `9aeda34..0765221` ovanpå `d09eaf4` är granskade.
Runtimekoden har inte ändrats under granskningen. Full rapport för Claude:
[uppföljning av planner, recept, server och CI](reviews/planner-followup-review-20261018.md).

- Hela icke-live-sviterna: backend 2 827 PASS, 10 kända FAIL, 2 separat körda
  taktester SKIP; grocery 1 909 PASS och 5 FAIL som reproduceras identiskt på
  `d09eaf4`. Inga nya svitefel. Första PR-CI `39099491097` är grön inklusive
  Ruff och webbläsare; den kör 2 776 PASS, 10 XFAIL och 53 evidensrelaterade SKIP.
- Båda städernas sju takprofiler: 9/9 pytest PASS per stad. Alla 20
  acceptanspar passerar; de 14 positiva har samma pris och hash, de sex
  negativa samma felkod. Inga tak höjdes och inga testkrav sänktes.
- Alla åtta närings-/ekoreferenser matchar exakt semantisk hash. Referensen
  isolerar de två sökmetoderna och offertcachen från `7feffcf`, med aktuellt
  innehåll/äggpolicy kvar. Alla 32 serverobservationer matchar mellan tak 90/0.
- Global låsväntan vid verkligt Lund/Malmö-överlapp: största väntan cirka
  0,00002 s, tidigare 14,9 s. Faktaläsning och CPU-arbete kostar fortfarande tid.
- Alla 28 versioner och 55 vattenskalningar godkända. Exakt köpbarhet för
  versionerna: Lund 28/28, Malmö 9/28; samtliga avslag redovisas. De två
  author-proven valideras men är avsiktligt inte registrerade för planering.
- Kvarstående P2: `--uncapped` behåller fyra seedvarianter per basrecept;
  icke-cachebara faktaprojektioner kan ändå diskpersisteras (även baslinjen);
  author skalar flera vattenmängder/decimaler fel. Körbara reproduktioner ingår.
- P1 inför bred lansering kvarstår: standard 66,6/46,8 s kall/varm i Lund,
  85,0/58,2 s i Malmö; eko med tak cirka 184/168 respektive 270/248 s.
  Detta är direkta plannerprov, inte HTTP-latens eller produktions-p95.
- Ingen aktivering. Samma live-image, HTTP 200/ready och
  `PRICE_UNIVERSE_PREWARM_ENABLED=false` i miljöfil och runtime verifierat.
  Backup misslyckas fortfarande med `InsufficientStorageError`: 6,33 GB ledigt
  mot cirka 13,99 GB behov. Egna tillfälliga servercacher är borttagna;
  mätunderlag och syntetiska planer bevarade. Inga granskningscontainrar kör.

Evidens och publika indata finns i separata ZIP-filer under
`.local/deliverables/`; rapporten anger metod, filnamn och reproduktion.
Första Malmö-pytestförsökets tidszonsfel i granskningsharness är bevarat och
redovisat; slutkörningen läser originalklockan i Python och passerar 9/9.
Äldre sidogrenar/worktrees är bevarade; senaste fetch visar ingen annan
nyare toppcommit än dåvarande main. Patchmotsvarigheter redovisas i rapporten.

---

# 2026-10-17: Dokumentation av prövade åtgärder och granskningsinstruktion

- Vad som har prövats, vad som infördes och varför vissa åtgärder förkastades:
  `docs/planner-performance.md`, avsnittet "Prövade åtgärder 2026-10-16–17".
- Hur Codex ska granska uppföljningspatchen (12 commits):
  `docs/reviews/review-followup-instructions-20261017.md`.

---

# 2026-10-17: Makroprofilen – vad som gick och inte gick att korta

1. **Committat (identiska resultat):** näringssökningens grannar byggs med
   tupelskivning i stället för en generator (101 M steg i makroprofilen) och
   kostnadsgränsens fasta del summeras en gång per sökning. all-macros
   813,38 kr, protein40 796,40 kr och distribution 766,11 kr med samma hash;
   all-macros 125,8 → 122,3 s kall (inom brus).
2. **Prövat och förkastat:** att hoppa över näringssökningen för delmenyer i
   beamsökningen. Snabbare (all-macros 122 → 92 s, protein40 72 → 61 s) men
   **dyrare menyer**: all-macros 823,37 kr (+9,99) och distribution 768,86 kr
   (+2,75). Bryter kravet att aldrig välja bort billigare recept; inte infört.

Läge: all-macros cirka 120 s kall i sandlådan, varav cirka 35 s kvalificering
som bakgrundsuppvärmningen tar bort i drift. Återstoden är cirka 1 500
näringssökningar med i snitt 8 exakta korgberäkningar vardera. Nästa realistiska
väg är exakta gränser som avbryter en hel näringssökning när dess bästa möjliga
korg inte kan påverka beamsökningens rangordning, vilket kräver ett nytt
gränssnitt mellan menyoptimeraren och planeraren.

---

# 2026-10-17: Ägg med standardvikt, test mot fullt bibliotek, faktalås – ej aktiverat

1. **Ägg (ägarbeslut):** M- och L-ägg räknas med standardvikt, 51 g respektive
   60 g ätbart per ägg (klassens mittvikt 58/68 g med skal, cirka 12 % skal).
   Blandat M/L räknas som M; Small, enbart XL och pack utan klass får ingen vikt.
   Ingen förklarande text. Ersätter klassminimum-härledningen.
2. **Taken får aldrig ge dyrare meny:** acceptansmatrisen har `--uncapped`
   (start och förfining över hela biblioteket) och `--uncapped-reference`
   som underkänner en körning med tak som betalar mer eller får annat utfall.
   `backend/tests/test_search_caps_vs_uncapped.py` gör samma jämförelse mot ett
   fryst underlag (`SMAKO_REVIEW_DATA`, profiler i `SMAKO_CAP_PROFILES`, hoppas
   över utan data). Standard och fördelning passerar i Lund. Kör det före
   ändrade tak och när många recept läggs till.
3. **Faktalåset (Codex P2):** hashning av råkällor sker utan lås och bara en
   projektion per nyckel körs åt gången; en förfrågan för redan cachad eller
   annan nyckel väntar inte längre. Integritetskontrollerna är oförändrade.
   Två trådar för samma nyckel kan i sällsynta fall projicera samtidigt
   (dubbelt arbete, inte fel resultat).

Kvar: makroprofilen (~125 s lokalt) – näringssökningens exakta prisräkning per meny.

---

# 2026-10-17: Kortare sökning i specialprofiler och förfiningstak – ej aktiverat

Gren `perf/planner-startup-and-semantics`, efter granskningsuppföljningen.
Svar på Codex P1 (långa specialprofiler). Inget av detta ändrar krav, prisregler
eller vilken meny som vinner i de uppmätta profilerna.

1. **Näringssökning:** efter godkänd näringskontroll prisräknas inte en
   kombination vars optimistiska kassa (auktoritativa radofferter, utan
   butikstak) inte är lägre än bästa exakta korg; bara strikt lägre total vinner.
   Samma kombinationer och budget; avstängt vid kopplade flerradserbjudanden.
2. **Ekosökning:** delmängder prövas i ordning efter lägsta kostnadsgräns och
   jämförs med (total, ursprungligt index), vilket ger samma vinnare.
3. **Omdöpta offerter** cachas per radnamn.
4. **`LIBRARY_REFINEMENT_POOL_LIMIT=90`** (0 = av): enkelbytesförfiningen prövar
   högst 90 recept per måltidstyp, valda som startsökningens tak. Parbyten,
   gemensamma byten och reservförsök är oförändrade. Tak 60 gav 5,15 kr dyrare
   fördelningsprofil och används inte.

Lund, frusen granskningsartefakt, estimerat inköpsläge, en kall körning per
profil i följd (1 CPU):

| Profil | Tak 0 | Tak 90 | Hash |
| --- | ---: | ---: | --- |
| standard | 71,3 s (sökning 30,2) | 61,6 s (21,8) | identisk |
| vegan | 46,2 s | 43,7 s | identisk |
| protein40 | 75,5 s | 75,4 s | identisk |
| all-macros | 127,3 s | 125,8 s | identisk |
| organic-share | 184,6 s (eko 120,2) | 135,1 s (eko 77,1) | identisk |
| distribution | 91,2 s | 91,7 s | identisk (tak 60: 771,26 kr i st. f. 766,11) |
| breakfast-snack-weight | 34,0 s | 36,2 s | identisk |
| impossible-protein / allergy-milk / organic-animals | samma felkod | samma felkod | – |

Före punkt 1–3 (samma sätt): all-macros 177,8 s, organic-share ekosökning 160,8 s.
Makroprofilen är fortfarande lång; resten av tiden är näringssökningens exakta
prisräkning per meny. Förberedd kvalificering vid publicering bedöms ge lite:
varm standardplan lägger 4,8 av 39,7 s på kvalificering.

## Granskning (Codex)

1. Kör acceptansmatrisen i Lund och Malmö med `LIBRARY_REFINEMENT_POOL_LIMIT=0`
   och `=90`; identisk hash krävs i alla positiva profiler.
2. Bekräfta att kostnadsgränsen i näringssökningen är en giltig undre gräns
   (samma `optimistic_relaxed_key` som ekosökningens gräns).
3. Mät makro- och ekoprofilerna på servern.

---

# 2026-10-17: Åtgärder efter Codex granskning (planner-startup-server-review) – ej aktiverat

Gren `perf/planner-startup-and-semantics`, ovanpå granskad patch (`35dc44f`).

| Granskningsfynd | Åtgärd |
| --- | --- |
| P2 konfliktmärkt fett som produktklassbevis | `declared_fat_g` ignorerar fett vid näringskonflikt; båda konsumenterna (`_requirements_compatible` thick, `compatible` cottage_cheese/creme_fraiche) testade. |
| P2 author tappar krav vid sammanslagning | Olika krav för samma `namn|form` stoppas med tydligt fel. |
| P2 author underräknar aktiv tid | Aktiv = alla icke-passiva steg; total = max(kritisk väg, aktiv); väntan = resten. Exemplet: 31/15/46. |
| P2 vatten skalas inte | 11 steg skrivna i ml med `scalable_amounts`; kontrollerat 1/2/4/8/12 portioner. `author` gör detta automatiskt och stoppar dl/l. |
| P2 namn/etikett mot produktkrav | Köttfärssås "kort pasta"; fiskgratäng "Torskfilé". |
| P2 rättelser tappade metadata | 16 nya versioner bär granskad innehållskälla vidare (säkerhetskällor, förvaring, metod/skalning) och aktiv tid därifrån; valideringen binder dem till nytt paket. |
| CI XPASS(strict) | Felaktig markering borttagen; tio kända fel kvar. |
| Ruff i rapportskript (23) + absoluta sökvägar | Ruff-rent; `SMAKO_RECIPE_WORK`, `SMAKO_REVIEW_DATA`. |
| Gammalt äggtest | Följer ägarbeslutet och kontrollerar bevisets grund. Kunde inte köras lokalt (saknad evidens). |

Paket `review-fixes-20261017`: 28 nya versioner, alla kvalificerar ensamma i Lund
(exakt, 2 butiker). Tidigare versioner är kvar i historiken. Låsningstesterna
(68) passerar.

**Öppna punkter:**
- Äggens presentationsklass: `DERIVED` visas som verifierad mängd medan grunden
  är klassminimum × populationsandel. Förslag: egen mängdklass eller tydlig
  radtext. Kräver beslut om visning.
- P1 långa specialprofiler (makro ~261 s, ekoandel ~278 s) och P2 faktalåset:
  inte åtgärdade i denna omgång.
- `test_browser_error_classes_retain_choices_and_identify_actual_field` kräver
  Playwright-webbläsare och fallerar lokalt utan dem; passerar i CI enligt granskningen.

## Granskning (Codex)

1. Kör den tidigare evidenspanelen igen med `--runxfail` och
   `SMAKO_REQUIRE_LOCAL_EVIDENCE=1`, inklusive det ändrade äggtestet.
2. Jämför de 28 versionerna mot föregående: endast tabellens fält får skilja.
3. Kör `tests.yml` på en PR (Ruff-steget körs bara då).

---

# 2026-10-17: Servergranskning, första CI och beställd prewarm-flagga

Patchen till `35dc44f` är importerad på main; första reviewcommit `00dcb8d`
pushades för den beställda GitHub-körningen. Hela uppföljningen finns i
[full server- och CI-granskning för Claude](reviews/planner-startup-server-review-20261017.md),
med mätmetod, tabeller, reproduktioner, handoffchecklista och rättningsordning.
Den ersätter den första granskningens begränsningar om saknade server-/CI-prov.

Alla 20 profiljämförelser matchar både mellan seedtak 0/40 och mot referensen
med äldre offert-/auditberäkning. Kvalificering i exakt läge: Lund 41/41,
Malmö 16/41; resterande stoppas på saknat underlag eller viktvaror.
Första GitHub-körningen `39032098776` är röd på ett `XPASS(strict)`:
browserprovet passerar men är felaktigt markerat som ett känt fel.
Ruff ger fortfarande 23 fel i rapportskript. Patchen är inte releaseklar;
konfliktfett, author-krav/tid, vattenmängder, receptmetadata och prestanda
behöver hanteras. Ägarens dokumenterade policybeslut respekteras.

Den särskilt beställda driftändringen genomfördes kl. 13:17 UTC under
befintligt driftlås: `PRICE_UNIVERSE_PREWARM_ENABLED=false` i serverns
miljöfil och effektiv runtime. En äldre override behövde överstyras.
Appen återskapades med samma image; planinnehåll, prismanifest, scheduler och
proxy verifierades bevarade. Patchens runtimekod har inte aktiverats.
Live-imagens nio källkodsavvikelser och en saknad datafil måste redas ut
före en senare kodrelease. Se rapporten för exakta avgränsningar.

---

# 2026-10-17: Patch importerad och granskad – kvarvarande releasehinder

17 patchcommits från bas `46d834b` till importerad `35dc44f` förs in på lokal
`main` enligt beställningen. 593 riktade/regressionstester passerar och
compileall är godkänd. Granskningen bekräftar dock problem med äggmängdens
bevisklass, användning av konfliktmärkt näring, uppvärmningens faktalås,
förlorade produktkrav, aktiv arbetstid och 23 Ruff-fel i rapportskripten.
Patchens runtimekod är bevarad för rättning; den är inte releasegodkänd.
Ingen push eller betaaktivering ingår. Se
[full granskning och branchinventering](reviews/planner-startup-semantics-20261017.md).

---

# 2026-10-17: Ägarbeslut – äggvikt och näringskonflikter godkända

Ägaren (Ossian) har godkänt båda reglerna från posten "Ägg i gram,
näringskonflikter, audit av vald meny, CI":

1. **Ägg:** räknade äggpack med viktklass M/L/XL får en härledd minsta ätbar
   vikt (antal × klassens minimivikt med skal enligt EU 589/2008 × 0,88).
   Detta ersätter den tidigare regeln att antal aldrig blir gram. Uppföljning:
   väg några förpackningar per klass och jämför med 0,88, eftersom källan anger
   ett populationsvärde och själv rekommenderar vägning.
2. **Näringskonflikter:** konflikter som bara gäller näring stoppar inte längre
   receptets produktval; deras näringsvärden används aldrig. Identitets- och
   innehållskonflikter stoppar som förut.

Codex granskar koden som vanligt; besluten gäller från aktivering, inte från
denna gren.

---

# 2026-10-17 (forts. 4): Ägg i gram, näringskonflikter, audit av vald meny, CI – ej aktiverat

Gren `perf/planner-startup-and-semantics`. **Ingen aktivering på betan.**

1. **Ägg:** räknade äggpack med viktklass (M/L/XL) får en härledd minsta ätbar
   vikt = antal × klassens lagstadgade minimivikt med skal (EU 589/2008 art. 4)
   × dokumenterad ätbar andel 0,88 (`DERIVED`, tillåten i exakt läge). Small,
   pack utan klass och sammansatta produkter får ingen vikt. 82 äggpack i Lund;
   båda ugnspannkakorna kvalificerar. **Ändrar den tidigare regeln att antal
   aldrig blir gram** – ägarbeslut.
2. **Näringskonflikter** (`nutrition_basis`, `nutrition.*`,
   `supplier_nutrition_conflict`) stoppar inte längre receptets formkontroll;
   identitets-/innehållskonflikter gör det. 512 av 43 907 Lund-produkter
   berördes. Näringskonsumenter avvisar fortfarande alla konflikter; testet
   `test_fact_proofs_remain_bound_and_nutrition_conflicts_are_not_erased`
   skrevs om till den nya regeln.
3. **Audit bara av vald meny:** sökningen jämför hela menyer utan audit;
   den valda räknas om och auditeras. Underkänns den görs hela sökningen om med
   audit av varje meny (tidigare beteende) och `audited_search_retry` sätts.
   Parad mätning 3×2 varm 27,4 → 22,4 s, identisk hash.
4. **Tester och CI:** `conftest.py` rapporterar `FileNotFoundError` för saknade
   filer under `reports/` som SKIPPED med sökväg (`SMAKO_REQUIRE_LOCAL_EVIDENCE=1`
   gör dem till fel igen). Elva fel som finns på `main` är `xfail(strict=True)`.
   Två inaktuella testantaganden rättades (designfält/antal i
   `test_recipe_value_interning`, `test_recipe_computation_cache`, faktaversion i
   `test_coop_energy_qualification`). `.github/workflows/tests.yml` kör
   `backend/tests` offline med Playwright-webbläsare och Ruff på ändrade filer.
   Se `docs/TESTING.md`. `grocery_data/tests` ingår inte ännu.

**Mätbrus:** samma kod gav 35–49 s varm standardplan vid olika tillfällen i
sandlådan; bara direkt parade mätningar är jämförbara.

## Granskning (Codex)

1. Ägarbeslut om äggregeln: **godkänt 2026-10-17** (se posten ovan).
2. Näringskonflikter: **godkänt 2026-10-17**. Bekräfta att inga näringsberäkningar använder fakta med konflikt.
3. Kör `tests.yml` på GitHub; webbläsartesterna har inte körts i sandlådan.

---

# 2026-10-17 (forts. 3): Billigare korgberäkning, uppvärmt receptbibliotek, `author` – ej aktiverat

Gren `perf/planner-startup-and-semantics`. **Ingen aktivering på betan.**

1. **Offertcachen träffade nästan aldrig.** Veckans inköpsrader heter
   `"<ingrediens> [n]"` där n beror på menyns sammansättning; nyckeln innehöll
   numret och ~95 % av uppslagen missade (121 891 av 128 037). Nyckeln ignorerar
   nu radnumret och en återanvänd offert får aktuell radetikett (rättar även
   inaktuella namn från den beständiga offertcachen). Standard- och
   proteinprofilen: identisk hash. Varm 3×2-plan 28,9 → 23,6 s.
2. **Kallstarten byggde hela receptbiblioteket i användarens jobb** (~24 s på
   1 CPU för aktuell och historisk innehållsförberedelse). Bakgrundsuppvärmningen
   (`source_facts_prewarm`) bygger nu dessa cachar först; första 3×2-planen efter
   uppvärmning 24,3 s i stället för 55,8 s. Varm/kall skillnad i tidigare tabeller
   beror främst på detta.
3. **`meal_library_cli author`** (`recipe_authoring.py`, `docs/recipes/AUTHORING.md`):
   kompakt format → standardiserat paket (vokabulär, enheter och köpkrav från
   biblioteket, komponentmängder, tider från stegens kritiska väg, kost,
   varningar), sedan valfritt import, förberedelse av portioner och kvalificering
   i ordinarie planerare. Exempel provkört: 11 räknade ingredienser, 16/30/46 min,
   väljs med standardval, kvalificerad 214,82 kr (exemplet är inte importerat).

Planerartester (43 + korgtester), offertcachetester (153), recept-/semantiktester
(28 + 4 nya): inga nya fel.

## Granskning (Codex)

1. Bekräfta att inget i `BasketItemQuote` utöver `ingredient` beror på
   radnumret (sök efter användning av `ingredient.canonical_name` i
   `basket_calculator.quote_item` och felmeddelanden).
2. Kör acceptansmatrisen före/efter: identisk hash krävs; mät varm och kall tid
   separat på servern.
3. Prova `author` med ett nytt recept mot aktiv artefakt utan `--facts`.

---

# 2026-10-17 (forts. 2): Tak för bibliotekets startsökning – ej aktiverat

Gren `perf/planner-startup-and-semantics`. **Ingen aktivering på betan.**

Startsökningen (beam 8) prövade alla kvalificerade recept per måltid, 111 i
standardprofilen, och stod för 3 066 av 4 570 korgberäkningar. Den får nu högst
`LIBRARY_SEED_POOL_LIMIT` (standard 40, 0 = av) recept per måltidstyp:
billigaste enskilda inköp, starkast delade förpackningar (limit/5) och de två
billigaste per matkök; recept utan underlag behålls alltid
(`stable_candidate_pool.library_seed_cap`, körs efter `library_variant_shortlist`).
Reservförsöket med hela urvalet och all förfining använder fortfarande hela
biblioteket. Fyra profiler gav identisk hash och 10–20 % kortare tid; tak 24 gav
sämre pris. Siffror: `reports/recipe-packs-20261017/README.md`.
Planerartester (43 filer) och recept-/semantiktester (28 filer): samma kända
fel före och efter; 4 nya enhetstester.

## Granskning (Codex)

1. Kör acceptansmatrisen med `LIBRARY_SEED_POOL_LIMIT=0` och `=40` mot aktiv Lund-
   och Malmöartefakt. Kravet är identisk hash i alla positiva profiler; vid någon
   avvikelse, jämför pris och höj taket hellre än att ta bort det.
2. Bekräfta att reservförsöket (`seed_full_pool_retry`) fortfarande körs med hela
   urvalet när den begränsade starten inte hittar en meny.
3. Mät tiden på servern; siffrorna här är 1 CPU och en körning per profil.

---

# 2026-10-17 (forts.): Paprika i grampack och 12 middagar i sex matkök – ej aktiverat

Gren `perf/planner-startup-and-semantics`. **Ingen aktivering på betan.**
Underlag i `reports/recipe-packs-20261017/` (`new_dinners.py`,
`dinners-20261017.json`, `qualification-*.txt`).

1. **Ingen styck→gram-omräkning behövdes för paprika.** Butikerna säljer
   färsk paprika i fasta grampack ("Paprika Mix Klass 1" 400 g, "Paprika Spets
   Mix" 200 g). Semantiken klassade "Mix" som grönsaksblandning. Färgmixade
   paprikapack godkänns nu (namnregel, endast hela söta paprikor; Stark, Sivri,
   Carli, wok-/frysblandningar och Snacks Mix är fortfarande uteslutna) och får
   den generiska SLV-referensen för rå paprika.
2. **Rökt paprikapulver**: hyllnamnen "Paprika Rökt", "Rökt Paprika", "Paprika
   Smoked" lades till som sökalias och klassas som krydda, aldrig färsk paprika.
3. **Rättelsepaketet**: 10 av 16 kvalificerar (tidigare 6). De sex övriga
   (thairätter) kunde inte handlas eftersom ingen basilika gick att köpa i exakt
   läge: krukbasilika har bara uppskattad vikt, Coops skurna basilika 50 g har
   faktakonflikten `nutrition_basis` (stoppar varan i `product_form_compatible`
   även utan näringsmål) och fryst finhackad basilika uteslöts av `pack:basil`.
   Paketet `basil-fixes-20261017` (2.2.0) tillåter fryst finhackad basilika; alla
   sex kvalificerar. **Fråga till granskaren:** ska en näringskonflikt stoppa en
   vara när ingen näring efterfrågas?
4. **Paket `smako-cuisine-dinners-20261017`**: 12 middagar, två per matkök
   (kycklingkorma, aloo gobi, jordnötsgryta, stekt ris med tofu, chili sin carne,
   kycklingtacos, grekisk citronsoppa, grekisk linsgryta, kycklingcacciatore,
   pasta e ceci, laxsoppa, köttfärslimpa). 11–15 räknade ingredienser, alla 12
   kvalificerar ensamma. Ej provlagade.

Planeringstid per biblioteksläge (samma kod, bara manifestet skiljer; 1 CPU,
en körning per läge; `reports/recipe-packs-20261017/README.md`):

| Läge | Kvalificerade | Korgberäkningar | Tid | Pris |
|---|---|---|---|---|
| Före receptarbetet | 117 | 3 667 | 78 s | 638,47 kr |
| + rättelser | 127 | 3 730 | 81 s | 638,47 kr |
| + 13 nya recept | 133 | 4 309 | 103 s | 600,15 kr |
| + 12 middagar | 145 | 4 491 | 109 s | 535,06 kr |
| + basilikarättelser | 151 | 4 570 | 99–101 s | 535,06 kr |

Startsökningen står för 3 066 av 4 570 korgberäkningar i fullt bibliotek. Recept-/semantiktester (28 filer) och
planerartester (43 filer): samma kända fel före och efter.

## Granskning (Codex)

1. Läs de 12 middagarna som kock (mängder, temperaturer, ordning, att stegen
   matchar `form`). Jämför särskilt köttfärslimpan utan ägg och pasta e ceci
   där pastan kokas i grytan.
2. Granska alla produkter som nu godkänns som `paprika` och `rökt
   paprikapulver` i aktiva Lund- och Malmöartefakter.
3. Mät tiden med acceptansmatrisen före och efter receptpaketen. Om tiden är
   oacceptabel: begränsa startsökningen per matkök innan fler recept läggs till.

---

# 2026-10-17: Recepträttelser och 13 nya recept – ej aktiverat

Gren `perf/planner-startup-and-semantics`. **Ingen aktivering på betan.**
Källor, författarskript och kvalificeringsresultat: `reports/recipe-packs-20261017/`.
Mätt mot granskningspaketets frysta Lund-artefakt, exakt inköpsläge, 2 butiker.

1. **Regler.** Kryddpåsar på skafferihyllan ("Paprika Påse", Santa Maria)
   godkändes som 180 g färsk paprika; nu krävs färskvarubevis för råvara i
   skafferikategori. Etiketterna "Paprika Rökt", "Rökt Paprika" och "Paprika
   Smoked" godkänns för `rökt paprikapulver` (sammansättningskontrollen kvar).
2. **Rättelsepaket `blocked-recipe-fixes-20261017`**: 16 nya versioner (x.1.0)
   via `validate` → `import`. Chiliflakes utan krav på mild/medium (0,3 g; ingen
   sådan märkning i sortimentet), majs som fryst naturell i stället för konserv,
   äldre poster fick härledda komponentmängder och aktiv/total tid (aktiv tid =
   tidigare enda uppskattning, övre gräns), nudelsalladens kycklingvariant metod
   `pan` (kycklingen steks med kärntemperaturkontroll). 6 av 16 kvalificerar;
   övriga stoppas av färsk paprika som viktvara eller basilika/limejuice i olika
   butiker. Kapris lämnades orörd: bibliotekets regel kräver avrunnen vikt.
3. **Nytt paket `smako-new-recipes-20261017`**: 6 middagar (köttfärssås,
   kålpuddinggryta, fiskgratäng, linssoppa, kycklinggryta, laxpasta), 4 frukostar
   och 3 mellanmål. Alla 13 kvalificerar ensamma. 11 har minst 10 ingredienser
   enligt `ingredient_count` (salt m.m. undantagna). Ej provlagade.
4. **Tester som låste originalbiblioteket** räknar nu även en granskad nyare
   version av samma rätt (samma bas/variant, högre version) som giltig; att
   varje utfärdat original finns kvar oförändrat i historiken kontrolleras.

Standardprofil 5×4/2 butiker: avvisade middagar 41 → 49 av 158 → 164
(16 paprikarätter kvalificerade tidigare bara via kryddpåsen), kvalificerade
117 → 115, veckopris 638,47 → 600,15 kr (685,85 kr före strimlad-rättelsen).
Frukost/mellanmål kvalificerar i veckoplan men väljs sällan på pris: fyra nya
frukostar × 2 portioner kostade 515,67 kr eftersom hela förpackningar köps.
Recept- och semantiktester (28 filer) och planerartester (43 filer): samma
kända fel före och efter.

## Granskning (Codex)

1. Läs varje nytt recept i `new-20261017.json` som kock: mängder per portion,
   ordning, temperaturer (kyckling 74 °C, fisk 63 °C), att alla ingredienser
   används och att texten stämmer med `form`.
2. Granska rättelserna med `diff` mot föregående version; endast de beskrivna
   fälten får ha ändrats.
3. Kör `qualify.py` (eller `meal_library_cli qualify`) mot aktiv Lund- och
   Malmöartefakt och jämför med `qualification-*.txt`.
4. Bekräfta att inget recept längre köper en kryddpåse som grönsak: sök i
   planer efter `paprika` med kategori Skafferi/Kryddor.
5. Bedöm om färsk paprika i styck (`Paprika 3-pack`) ska få en granskad
   styck→gram-referens; det skulle återställa cirka 20 middagar.

---

# 2026-10-16: Planerartid, faktauppvärmning och färdigrättsmatchning – ej aktiverat

Gren `perf/planner-startup-and-semantics`, bas `46d834b`. **Ingen aktivering på betan.**
Underlag: granskningspaketets frysta Lund-artefakt (universe `469136bc…`) och
produktfakta, offline, receptbiblioteket (`mode=complete`), 1 CPU.

1. **Audit endast för hela menyer.** Delmenyer i beamsökningen (`final=False`)
   auditeras inte; varje hel meny, bevarad incumbent och slutmeny auditeras som
   förut, och slutmenyn räknas alltid om med `final=True`. 0 av cirka 1 950
   delmenyaudits underkändes i två mätningar. Enhetstabellen i
   `purchase_quantity_resolver` byggs en gång och cachas. Fyra profiler
   (5×4 med 2/3 butiker, protein ≥ 40 g, 3×2): identisk SHA-256 för recept,
   korg, näring, audit och skafferifördelning; cirka 10 % kortare tid
   (t.ex. 50,7 → 42,9 s varm standard). Mätbrus några procent.
2. **Produktfakta laddas i bakgrunden vid uppstart** (`source_facts_prewarm.py`)
   med samma `load_retained_facts` och cache, utan planerarens admission-plats.
   `SOURCE_FACTS_PREWARM_ENABLED` (standard på, kräver kompletta recept).
   Effekten är **inte uppmätt**: råsnapshots saknades i underlaget.
   `deploy/.env.production.example` anger `PRICE_UNIVERSE_PREWARM_ENABLED=false`
   enligt startup-wait-rapporten; serverns verkliga miljö måste ändras separat.
3. **Tydligare fel när alla valda butiker bara har kampanjpriser**, med förslag
   på butiker med fullt sortiment. Endast text; krav, scope och prisregler
   oförändrade. Okänd coverage räknas inte som offers_only.
4. **Fyllda degrätter är färdigrätter.** Namn med dumpling, gyoza, wonton,
   dim sum, pirog, vårrulle/spring roll ger `ready_meal` (endast produktnamn,
   inte navigationskategori; sås/deg/skin undantas). Alla 35 träffar i Lund är
   verkliga färdigrätter; "Dumplings Kyckling" kan inte längre bli recepts kyckling.

5. **Strimlad råvara räknas som rå råvara** (`_whole_food_identity`, produce).
   "Vitkål Strimlad" (400 g, fast förpackning) godkänns nu för `vitkål`
   `raw_edible`; sammansättningskontrollen mot salt/olja/ättika är kvar.
   Standardprofilen 5×4/2 butiker: avvisade middagar 64 → 41 av 158,
   685,85 → 638,47 kr med mer varierad meny. Tid 44 → 66 s på grund av fler
   kvalificerade kandidater (1 CPU, enskilt prov). Kvarvarande avslag: chiliflakes
   (10, kräver mild/medium), fläskkött (8) och pepparrot (6) som viktvara, majs (6),
   kapris, bröd, pasta, ägg i gram, tonfisk.

Minnet är oförändrat: 92 MB pris-JSON blir cirka 745 MB modeller, fakta cirka
200 MB. Dedup av proveniens/strängar sänkte inte RSS och ingår inte.
Variationsgränser ändrades inte: upprepningen sågs i PersonalPlanner utan
`mode=complete`, en väg som inget gränssnitt använder.

43 befintliga planerar-/semantiktestfiler före och efter: samma 56 kända
fel/errors (främst saknade `reports/`-filer), inga nya. 11 nya tester, Ruff och
compileall passerar.

## Granskning (Codex)

Granska i denna ordning och stoppa vid första avvikelse:

1. **Audit endast för hela menyer** (`PersonalPlanner.basket`). Bekräfta att inget
   resultat med `final=False` kan bli returnerat, sparat eller visat: följ
   `qualified_results`/`remember_bounded`, beam-/bibliotekscachen i
   `menu_optimizer`, `_retain_scope_incumbent` och slutberäkningen
   `self.basket(chosen, final=True)`. Kontrollera även `meal_library_cli`
   (anropar med standard `final=True`).
2. **Samma resultat.** Kör acceptansmatrisen med ett verkligt underlag före och
   efter (`combined_performance_probe.py --matrix`, samma klocka). Kravet är
   identisk semantisk hash i alla positiva profiler och samma blockerade profiler.
   Redovisa tider separat; påstå ingen förbättring utan egen mätning.
3. **Faktauppvärmningen** (`source_facts_prewarm.py`, `main.py`). Bekräfta att
   anropet är exakt samma `load_retained_facts(prepared)` som planeraren gör,
   att tråden aldrig tar admission-platsen, att fel bara registreras, och att
   SQLite-åtkomst från en annan tråd är säker här. Mät första användarjobbet
   efter omstart med verkliga råsnapshots, med och utan
   `SOURCE_FACTS_PREWARM_ENABLED`. Är effekten noll eller negativ: stäng av den.
4. **Färdigrättsregeln** (`_is_filled_dough_dish`). Kör den mot aktiv Lund- och
   Malmöartefakt och granska varje träff. Endast produktnamn ska användas;
   komponentprodukter (sås, deg, skin) ska inte klassas som färdigrätt.
5. **Strimlad råvara.** Granska alla produkter med "strimlad" i aktiva Lund- och
   Malmöartefakter mot `produce`-reglerna; endast osmaksatt rå råvara får passera.
   Kör acceptansmatrisen och bekräfta att fler recept kvalificerar utan nya
   avvikelser i audit, näring eller skafferi.
6. **Kampanjbutikstexten** (`_campaign_only_scope_hint`). Endast meddelandet får
   ändras; felkod, scope och krav ska vara desamma. Pröva ICA-only och en
   blandning med Willys via HTTP.
7. **Regression.** Kör samma 43 testfiler före och efter och jämför listan av
   FAILED/ERROR (väntat: identiska 56 kända, främst saknade `reports/`-filer),
   plus de 11 nya testerna, Ruff och compileall.

Ingen aktivering ingår. `PRICE_UNIVERSE_PREWARM_ENABLED=false` på servern är en
separat driftåtgärd under ordinarie driftlås.

---

# 2026-10-16: Main och portabel utvecklings-/betastart

`main` samlar den tidigare huvudgrenen `master` (`bdf0a3a`) och de 25 senare
commits som slutar i `4eedaa5`, utan ombyggd historik. Historiska experiment-
och verifieringsgrenar bevaras; de ska inte blindmergas över aktuell kod.
README och DEVELOPMENT beskriver start från GitHub-klon. `scripts/dev.py`
migrerar en isolerad mockmiljö. BETA beskriver det versionshanterade appflödet
`beta_release.py prepare/build/activate`, återanvänt från verifierad appaktivering.
Det kräver operatörens SSH-behörighet och stödjer bara granskade appfiler;
scheduler, beroenden och databasschema behöver separat releasegranskning.

Ingen ny betaaktivering ingår i denna ändring av Git och utvecklingsverktyg.
Betan kör fortsatt `joint-week-refinement-app-e041544`. Uppstartsväntan nedan
är utredd men inte åtgärdad. Klon- och verifieringsresultat dokumenteras i
[main-onboarding-20261016](releases/main-onboarding-20261016.md).

# 2026-10-16: Uppstartsväntan undersökt

Gren `investigate/startup-prewarm-wait`, bas `b6ef5b8`. Ingen produktionsändring.
Malmös redan startade bakgrundsuppvärmning blockerar Lundanvändaren bakom
samma enda admission-plats. Historiska tider motsvarar cirka 7 min 40 s väntan;
exakt köspan saknas. Produktfakta 21,04 s ligger dessutom utanför create-tiden
43,79 s. Uppvärmningen använder äldre receptväg, fem rätter/två portioner/tre
butiker, medan användarprovet använder nytt receptläge och andra inställningar.
Åtta runtimefiler matchar lokal kod. Kontrollerad lokal reproduktion bekräftar
blockeringen och den äldre begäran; 17 befintliga kö-/uppvärmningstester passerar.
Nästa rekommenderade steg: stäng av helmenyuppvärmningen via befintlig flagga,
behåll separata pris-/ingrediensförberedelser och mät hela användarjobbet.
Se [utredning och sanerad evidens](../reports/startup-wait-20261016.md).

# 2026-10-16: Veckooptimeringen aktiverad på betan

Kodcommit `e041544` är pushad på `feature/joint-week-refinement` och aktiv som
`joint-week-refinement-app-e041544`. Endast appen byttes under befintligt
driftlås efter kontrollerad backup. Lund och Malmö är ready med ny version.
Fyra publika menyflöden passerar närings-/viktkrav, kassarevision och två
sparade återläsningar; tidigare data och scheduler/proxy är bevarade.
Första API-provet efter omstart tog 533,72 s trots 43,79 s intern planerartid;
följande prov tog 15,77–26,98 s. Uppstarts-/kötiden behöver följas upp.
Se [aktiveringsrapport](releases/joint-week-refinement-20261016/ACTIVATED.md)
för tider, exakt paket och verifiering. Nedanstående genomföranderapporter
beskriver historisk status före denna aktivering.

# 2026-10-16: Gemensamt giltiga veckobyten och mindre inköpsöverskott

Gren `feature/joint-week-refinement`, bas `4357323`. **Ingen aktivering på betan.**
Nästa steg från granskningen av punkt 5 är genomfört. Den tidigare sökvägen
inklusive dess 128 parförslag körs färdigt. Därefter prövas högst 256 förslag
och 32 nya helkorgsberäkningar per biblioteksökning från högst åtta kvalificerade
alternativ per position. Dessa behöver inte klara ett enskilt byte; två byten
kan återställa veckokraven tillsammans. Snävare butiksjämförelser har egna
budgetar. Befintlig prismotor, skafferi, erbjudanden och slutrevision återanvänds.

Vid `surplus_mode=minimize` väljs vid samma inköpssumma mindre kvarvarande
betalt varuvärde, sedan mindre förpackningsandel. Pant ingår inte; g/ml/st
hålls separata, okänt är inte noll och uppskattningar märks. `allow_larger`
avaktiverar jämförelsen. En separat bästa slutkorg bevaras utan att ändra den
tidigare sökvägen. Nya recept använder befintlig stratifiering och kvalificerade
prissignaler, utan ID-listor. Policy: `personal-policy-v2-10-joint-week-refinement`.

Tio profiler/19 frysta körningar: samma inköpspriser i alla sju positiva profiler
och samma tre blockerade profiler. Protein40, alla makronäringskrav och angiven
måltidsfördelning får vardera 160 g/15,09 kr mindre beräknat inköpsöverskott.
Övriga fyra har samma överskott. Ingen lägre inköpssumma påvisas i denna matris;
syntetiskt köpfall visar 60 → 10 kr genom gemensamt byte, skafferi och kampanj.
Standard varm 26,80 s (tidigare 25,94), protein40 varm 8,73 s (8,43), eko kallt
125,04 s (121,86). Högsta processminne 829,03 MiB. Inte ett lasttest eller bevis
på globalt lägsta pris. Eko behöver fortsatt prestandaarbete.

**460 tester passerar**, liksom Ruff och compileall. Offlineisoleringen är ren;
18 tidigare kända Pydantic-varningar. Full metod, jämförelse av överskott,
budgetar och rådatasökvägar: [rapport](../reports/joint-week-refinement-20261016.md).

# 2026-10-16: Prestandapunkt 3–4 klara, veckoptimeringens punkt 5 granskad

Gren `perf/eco-and-variant-selection`, bas `a294a71`. **Ingen aktivering på betan.**
Beställningen gäller mindre arbete i ekosökningen och begränsat varianturval,
därefter granskning av bättre optimering av hela veckans inköp.

Ekosökningen kan avvisa den ordinarie prismotorns exakta offertval på ekoandel
före bygge av korgmodeller. Gemensamma kampanjer/egna kalkylatorer behåller full
checkout; befintliga prisgränser, delmängdsordning, sökbudget och slutkontroller
är kvar. Högst 32 lyckade ekokorgar återanvänds inom samma planerare med exakta
värdenycklar för behov, kandidater/erbjudanden, ekoegenskaper och butiksvillkor.

Stora receptfamiljer får normalt fyra varianter per grundrecept i startsökningen.
Alla grundrecept, första kvalificerade variant, billigaste enskilda köp, starkast
produktöverlapp och efterfrågade näringsextremer skyddas; extrema värden kan höja
gränsen. Befintlig kulinarisk stratifiering återanvänds. Saknat urvalsunderlag
behåller hela familjen. Misslyckat begränsat startförsök följs av hela urvalet;
alla kvalificerade varianter finns kvar i senare byten. Nya recept kräver inga
särskilda ID-listor. Policy: `personal-policy-v2-9-eco-variant-search`.

Tio frysta profiler, 19 körningar: identiska semantiska resultat och priser i
alla sju positiva profiler, samma tre blockerade profiler. Eko kallt
**144,09 → 121,86 s (−15,4 %)**, samma 434,13 kr och ekoandel 23,4953 %.
45 476 korgval avvisas före modellbygge; den nya 32-posters ekocachen gav inga
träffar i detta fall. Standard varm 25,94 s, protein40 varm 8,43 s,
frukost/vikt varm 2,11 s: ingen tydlig förbättring i dessa profiler.
Varianturvalets nytta gäller främst framtida större familjer; 300 syntetiska
varianter och full fallback är testade. Processens högsta observerade minne
825,13 MiB. Ingen samtidig serverlast eller global kostnadsoptimalitet är bevisad.

**445 offlineprov**, Ruff och compileall passerar. Isoleringsloggar saknar
rapportläsningar och blockerade externa/gamla workspaceförsök. Full rapport,
mätmetod, begränsningar och granskning av punkt 5:
[eco-variant-selection-20261016.md](../reports/eco-variant-selection-20261016.md).
Råmätningar: `.local/eco-variant-selection/final/`.

Punkt 5 är granskad, inte färdigimplementerad i denna etapp. Veckokorgen hanterar
redan samlade behov, skafferi, förpackningar, butikstak och kampanjer samt enskilda
och parvisa byten. Nästa konkreta luckor: (1) parurval från kvalificerade recept
som **inte** måste vara giltiga var för sig när ett gemensamt byte klarar kraven,
(2) verifierat överskott som sekundärt kriterium vid samma betalda inköpssumma.
Behåll befintliga vinnare/förslag och separata sökbudgetar. Summera inte olika
mängdenheter och räkna aldrig fiktivt framtida restvärde som inköpsrabatt.

---

# 2026-10-16: Återanvänd bibliotekssökning och förbättra startmeny – lokalt verifierat

Användaren beställde punkt 1–2 för att minska beräkningstiden efter receptutökningen.
Gren `perf/incremental-library-search`, kod/resultat `1e8213a`, bas `6614ac9`.
**Ingen aktivering på betan.**

Vanlig nyplanering kvalificerar hela aktuella urvalet en gång per måltidstyp och
behåller samma privata planerare/cacher mellan bibliotekets generationer.
Första giltiga menyn hittas med befintlig beam. Nya paket får sedan konkurrera
genom enskilda byten, följt av omprövning av äldre alternativ och högst 128
parvisa förslag ur åtta alternativ per måltid. Hela korgen och alla hårda krav
kontrolleras; en dyrare meny ersätter inte föregående giltiga meny. Slutkontrollen
körs separat. Aktuella versioner styr starturvalet, äldre generatorfrukostar
ingår oförändrade och ändrade butikstak/köpval får separata planerare.

Tio frysta profiler, 19 körningar: sju positiva profiler med samma eller lägre
inköpssumma, tre fortsatt blockerade. Standard kall/varm **49,97/25,94 s** mot
85,78/58,46 s; pris 674,16 kr, samma recept i ändrad dagsordning. Eko kall
**144,09 s** mot 316,28 s; samma meny, 434,13 kr och ekoandel 23,4953 %.
Protein40 varm 8,30 s, pris 1 216,11 → 1 184,12 kr. Frukost/vikt varm 2,06 s,
oförändrat 85,55 kr. Måltidsfördelning varm 10,10 s, pris 1 119,68 → 1 107,34 kr.
Högsta observerade processminne 825,27 MiB. Ingen samtidig serverlast är mätt.

376 offlineprov passerar (375 i bred serie + kompatibilitetsprov för äldre
frukost), liksom Ruff och compileall. Inga rapport-/gamla källäsningar eller
externa anrop i isoleringsloggarna. Sökningen är begränsad: globalt lägsta pris
och frånvaro av framtida prisregressioner är inte bevisade. Två tidiga prototyper
stoppades av prisgrindarna; endast slutserien ovan är accepterad.

[Metod, mätningar och begränsningar](../reports/incremental-library-search-20261016.md)
· [Bibliotekstillväxt](flexible-recipes.md). Rådata: `.local/incremental-library/final/`.

---

# 2026-10-16: Flexibla receptfamiljer (steg 4) – lokalt verifierat

Användaren beställde steg 4 och stöd för framtida recept. Gren
`feature/flexible-recipe-families`, implementation `07f7fd7`, bas `094557a`.
**Ingen aktivering på betan.**

`meal_library_cli expand` omvandlar granskade familjer med råvarubyten och
uttryckliga mängdkombinationer till vanliga receptpaket. Befintlig validering,
import, historik, förberedelse, produkt-/näringskontroll och optimering används.
Max 16 listade varianter per familj; ingen automatisk kombinationsprodukt.
Varje variant har egna steg, komponenter, metadata och granskningsproveniens.
Nya grundrecept kan läggas till med data utan Pythonregistrering.

Första paketet tillför sju varianter från tre befintliga grundrätter.
Sex varianter och alla tre grundrecept klarar köp och fyra makronäringsvärden
i fryst återspelning. Kvargvarianten avvisas fortfarande för saknat köpunderlag.
Inga källkrav sänktes. Ett undantag i `matches_meal` är rättat så att
`adaptation=products` också avför frukost-/mellanmålsvarianter utan recipe_choices.

269 offlineprov, Ruff och compileall passerar. Fyra frysta menyprofiler passerar
med oförändrade inköpssummor. Frukostprofilen väljer automatiskt extra yoghurt
och får uppskattad serverad vikt 400 i stället för 300 g per portion; båda
ryms i användargränsen. Övriga tre har identisk full semantisk hash.

**Tidsregression:** standard kall/varm 85,78/58,46 s mot 61,56/37,74 s;
eko kall 316,28 s mot 216,52 s. Protein40 32,59/8,79 s, frukost/mellanmål
29,06/4,31 s. Det befintliga skyddet som jämför mot tidigare bibliotek ger
mer sökarbete när nya varianter kvalificerar. Återanvändning mellan generationer
behöver förbättras före stor innehållsexpansion; ingen snabbhet påstås här.

[Författarformat](flexible-recipes.md) ·
[Resultat och begränsningar](../reports/flexible-recipes-20261016.md).
Rådata och återspelningshjälpare finns i `.local/flexible-recipes/`.

---

# 2026-10-16: Snabbare ekosökning och återanvänd första måltid – lokalt verifierat

Användaren bad att genomföra nästa steg. Gren `perf/ecological-week-search`,
kodcommit `6449cea`, bas `cac3a2e`. **Ingen produktionsaktivering i denna etapp.**

Ekosökningen använder befintlig optimistisk prisgräns och exakta kostnadsnycklar
för att avföra delmängder som inte kan slå en redan godkänd korg. Ordning vid
lika pris, källa, medlemskap, kvantiteter och butikstak bevaras. Gruppkampanjer,
delade erbjudandegränser och egna kalkylatorer behåller full checkout.
Kostnadsnycklarna sorterar bort butiker utan kvalificerade varor på samma sätt
som befintlig checkout, utan att tappa svar för högre butikstak.

Receptkontrollens första måltid överförs till veckosökningens befintliga
256-posterscache, inom samma begäran. Ensamma måltider, redigeringar och
slutlig audit beräknas fortfarande. Ingen ny delad cache eller sänkt sökbudget.
Matrisens cachekatalog innehåller nu även profilnamnet för separata kallprov.

342 offlineprov i 18 moduler, Ruff och compileall passerar. Samma utfall i
alla tio frysta profiler; full semantisk hash matchar för de sju levererade
menyerna. Tre profiler ger fortsatt samma avslag. Inga rapportläsningar eller
blockerade källanrop i `.local/verification/ecological-week-final-access.json`.

Ekoandelsfallet: **482,48 → 216,52 s (55,1 % kortare tid)**, CPU
458,31 → 194,14 s, samma meny/korg på 434,13 kr och ekoandel 23,4953 %.
Fulla ekocheckouter minskar från 382 864 till 89 362. Detta är ett slutligt
kallprov per version. Varm standard/protein40: 37,74 / 7,98 s; förbättringen
för övriga varma profiler är liten. Högsta observerade processminne 805,21 MiB.
Ekofallet uppfyller fortfarande inte målet 30–60 s. Kötid och samtidig
serverkapacitet är inte mätta. Ingen global kostnadsoptimalitet påstås.

[Slutrapport](../reports/ecological-week-search-20261016.md) ·
[Arbetskontrakt och reproduktion](planner-performance.md).
Råfiler finns lokalt i `.local/ecological-week-search/verified/` och
`reports/ecological-week-search-20261016.json` (Git-ignorerade).

---

# 2026-10-16: Plannerförberedelser och testmatris – lokalt verifierade

Användaren beställde prioritet 1–2 med återanvändning av befintlig arkitektur.
Gren `perf/planner-preparation-matrix`, kodcommit `f2855df`, bas `b77e033`.
**Ingen produktionsaktivering.** Betan ligger kvar på versionen nedan.

Befintligt offlineprov har nu `--matrix` med tio profiler, frysta källhashar,
kall/varm körning, CPU/minne och identitetskontroll av hela meny-/korgresultatet.
PerformanceTrace räknar ekodelsökning och mäter admission-väntan när trace är aktiv.
Offlinekötid är okänd; ingen samtidig HTTP-belastning har gjorts.

84 ingredienssökningar förbereds via befintliga diskartefakter, universumets
begränsade cache, uppstart/omladdning och `meal_library_cli prepare/build --universe`.
Exakta alias, mängd-/källkrav och slutkontroller bevaras. Kodsignaturen binder
nu även näringsreferensernas och deklarationernas JSON-innehåll. En provad extra
gemensam näringscache togs bort eftersom jämförelserna inte visade tidsvinst;
befintliga käll-/näringscacher återanvänds.

411 offlineprov, Ruff och compileall passerar. Samma utfall för alla tio
profiler och identiska recept/korgar/näringskällor för de sju levererade menyerna.
Tre profiler ger fortsatt avslag; detta är inte generell täckningsgrad.
Separat 40-gramsprov: 10,29 s uppstartsförberedelse, sedan 22,88 s första meny
och 8,18 s varm. Ingen tydlig generell vinst för redan varma menyer.

Ekoandelsprovet tog 482,48 s: 382 864 ekodelmängder, 426,20 s i ekosökningen.
Nästa flaskhals är därmed belagd; inga sökbudgetar har sänkts. 30-/60-sekundersmålen
är inte uppnådda för hela matrisen. Data, kötid, serverkapacitet och globalt
lägsta kostnad får inte övertolkas från dessa lokala sekventiella prov.

[Mätresultat och verifiering](../reports/planner-preparation-20261016.md) ·
[Körbeskrivning och mål](planner-performance.md).

---

# 2026-10-15: Näringskopplingar och extraval – aktiverade på betan

Användaren begärde ”Aktivera på betan”. Appversion
`recipe-nutrition-extras-app-7e402a7` aktiverades 16:37 UTC (18:37 svensk tid).
17 ändrade runtimefiler matchar testad kod; 671 övriga filer oförändrade.
Gemensamt driftlås och integritetskontrollerade online-backuper användes.
Scheduler, Windowsuppgift, prismanifest och befintliga privata rader bevaras.

Fyra liveflöden passerar med 19 priskontexter inom 3 km från 22225:
fem middagar/fyra portioner/minst 40 g protein (43,19–53,51 g uppskattat),
samtidiga makro-/energigränser, frukost/mellanmål med uppskattad vikt
300/140 g samt tre veganska middagar. Alla ger HTTP 201, audit PASS,
noll okända mängder och identisk sparad GET vid två återläsningar.
Slutkontroll 16:41 UTC: 286 gamla revisioner/97 tillstånd hashbevarade,
291/102 totalt efter fem verifieringsplaner. Noll OOM/omstarter.
Lund/Malmö ready 200; befintlig AGING-varning för Malmö kvarstår.

Mjölkallergi, ekologiska animalier och varm tillagad vikt kan fortsatt
sakna källunderlag. Ekoandelsvalets tidigare svarstid kvarstår som begränsning.
[Aktivering, evidens och återgång](releases/recipe-nutrition-extras-20261015/ACTIVATED.md).

---

# 2026-10-15: Näringskopplingar och extraval – lokalt verifierade, inte aktiverade

Gren `fix/recipe-nutrition-extras`, kodcommit `7e402a7`, bas `fd783d1`.
Fjorton källbundna leverantörsdeklarationer, kompletterade nordiska
näringsreferenser och livsmedelsspecifik densitet rättar bland annat
citronjuice, rapsolja, kryddor, yoghurt, nötfärs och kokosmjölk.
Kokosmjölkens uttryckliga per-100-ml-deklaration bevaras som ml.
Faktapolicy `retained-catalog-facts-v11-nutrition-extras`, referenspolicy
`slv-component-input-v5-nordic-density`.

Användaren valde uppskattad tillagad vikt där underlag finns. Granskad kall
beredning och befintliga referensrätter med dokumenterat utbyte stöds;
övriga varma recept får ingen påhittad slutvikt. Äpplets receptmatchning
rättas. Veganfilter stoppar nu `yoghurt naturell` och `keso`; ett tidigare
falskt positivt vegantest ersattes med tre faktiskt veganska recept.

Slutligt lokalt prov med sparat underlag för samma 19 priskontexter inom
3 km från 22225: fem middagar/fyra portioner/minst 40 g protein passerar,
43,08–55,51 g per portion, 61 s. Samtidiga kolhydrat-, fett- och energigränser
passerar. Vegetariskt, veganskt, proteinfördelning, 20 % ekoandel samt frukost/
mellanmål med viktgräns passerar. Kassakontroller PASS och noll okända mängder.
554 samlade offlineprov och 14 browserprov i Chromium/WebKit passerar;
Ruff, compileall och JavaScript-syntax passerar.

Kvar: mjölkallergi och alla animalier ekologiska stoppas fortfarande av
saknat källunderlag. Ekoandelsprovet tog 459 s trots oförändrad sökning
med bättre cacheåteranvändning. Det är ingen fullständig källtäckning för
alla kombinationer. Ingen driftändring, prisinsamling eller privat
produktionstillståndsmutation har gjorts för denna ändring.

[Orsak, källor, prov och begränsningar](../reports/recipe-nutrition-extras-20261015.md).

---

# 2026-10-15: Receptens varukopplingar – aktiverade på betan

Gren `fix/recipe-product-links`, kodcommit `07af5ac`, bas `37cd882`. Användarens urval är alla
butiker inom 3 km från 22225. Saknade länkar mellan sparade Axfoodprodukter
och leverantörsdeklarationer rättas med exakt identitets- och mängdbindning.
Fullständiga livsmedelsnamn kompletteras och Zeinas citronjuice får en
källverifierad deklaration. Faktaversionen är
`retained-catalog-facts-v10-supplier-package-link`.

Alla sex felande ingredienser i skärmbilderna löses med Willys Lund inom
radien. Ett helt visat recept med 14 ingredienser passerar lokal planering,
kassakontroll och sparning/återläsning. 500 olika riktade testfall, Ruff och
compileall passerar. Näring per ml för citronjuice har inte antagits från
tillverkarens uppgifter per gram; sådana krav behöver fortfarande underlag.
Efter användarens ”Aktivera det” verifierades appbytet 12:34:32 UTC.
BUILD_ID `recipe-product-links-app-07af5ac`: sju ändrade filer ovanpå den
verkliga appbilden, 676 övriga runtimefiler oförändrade. Driftlås och
integritetskontrollerad online-backup användes. Scheduler, Windowsuppgift,
prismanifest och tidigare användartillstånd är oförändrade.

På betan passerar receptet från bilden (14 ingrediensbehov, 134,47 s) och
fem grekiska middagar (27 ingrediensbehov, 45,34 s), båda inom 3 km från
22225. Audit PASS, avstämda summor, noll okända mängder och identisk sparad
GET vid två återläsningar. API-prov under två separata verifieringsidentiteter;
inga nya browserprov. Lund/Malmö readiness 200. De 284 tidigare revisionerna
och 95 privata tillstånden är hashverifierat bevarade även efter proven.
Slutligt 286 revisioner och 97 tillstånd; noll nya OOM/omstarter.

[Aktivering, evidens och återgång](releases/recipe-product-links-20261015/ACTIVATED.md).

[Orsak, verifiering och avgränsningar](../reports/recipe-product-links-20261015.md).

---

# 2026-10-15: Stortorgets kampanjregister – följdrättning aktiverad

Gren `fix/willys-flyer-retained-inventory`, kodcommit `ad285c415df4`.
Den tidigare parserändringen lade till verifierat `hasPickingBaseStore: false`
i härledda metadata. Äldre sparade reklambladsregister innehöll redan fältet i
råkällan men saknade metadatafältet. Exakt rekonstruktion underkändes därför,
och Willys Hemma Lund Stortorget föll bort ur den nya prisversionen.

Rättningen medger endast den äldre utelämningen efter strikt råvalidering.
Identitet, geografi, urval, originalhashar och kampanjdatum jämförs fortsatt.
75 riktade tester passerar. Slutlig sourceimage återger Stortorgets verkliga
16 kampanjrader utan nätanrop. Serverfixen är aktiv sedan 11:02:24 UTC;
publicering/laddning och beständigt kampanjkvitto klara 11:19:36 UTC.
22225 visar åter 29 priskontexter. Äldre specifikt urval med Stortorget kvar
passerar i Chromium/WebKit; tremåltidsplan på 87,5 s, audit och identisk sparad
GET/omladdning godkända. Separat publik meny på 10,031 s med 17/17 kontroller.
282 tidigare planrevisioner och 94 privata tillstånd hashverifierat bevarade.
Appcontainern är oförändrad. Den separata misslyckade Hemköpshämtningen i Malmö
under det tidigare driftjobbet är inte åtgärdad eller maskerad här.

Windowsuppgiften är nu verifierat aktiverad på `5b344ca3b50e` sedan
09:26:11 UTC. Denna följdrättning behöver ingen ytterligare Windowsändring.

[Orsak, verifiering och aktiveringsstatus](releases/willys-flyer-inventory-20261015/REPORT.md).

---

# 2026-10-15: Willys parserrättning aktiverad på servern

Gren `fix/willys-picking-contract`, kodcommits `98eadc2b114c` och
`5b344ca3b50e`. `willys-parser-v6-picking-contract` accepterar det belagda
`hasPickingBaseStore: false` med strikt butiksbindning i transport, parser och
oberoende artefaktkontroll. Tidigare godkända v3/v4/v5-paket kan omkvalificeras.
145 riktade testfall, Ruff, compileall och autentiskt paket med 19 294 prisrader
har verifierats. Basprisretention och kampanjdatum bevaras.

Scheduler `willys-picking-scheduler-5b344ca3b50e` är aktiv sedan 08:07:12 UTC.
Lunds 19 294 prisrader återlevererades genom ordinarie relä; publicering,
laddning och kvitto klara 08:36:37 UTC. Alla fem baskontexter är FRESH och
laddade. 22225 fungerar, ny tremåltidsplan använder Willys, audit och sparad
GET/omladdning passerar. Malmömeny och readiness i båda kommuner verifierade.
280 tidigare planrevisioner och 93 privata tillstånd hashverifierat bevarade.
Appen är oförändrad. Vid slutprovet 08:40 UTC väntade Windowsbytet efter en
avbruten administratörsdialog. Bytet slutfördes senare 09:26:11 UTC, se ovan.

[Aktiveringsstatus, återhämtning och återgång](releases/willys-picking-20261015/ACTIVATED.md).

---

# 2026-10-15: Basprisretention aktiverad på betan

Gren `fix/base-price-retention`, kodcommit `0f54e51`, bas `bdf0a3a`. Användarens nya policy:
kvalificerade baspriser behålls tills de ersätts; kampanjer följer slutdatum
för alla kedjor. 36/48-timmarsvarningar och originaltider bevaras.
376 riktade testfall med omkörningar, Ruff, compileall och JS-syntax godkända.
Lund och Malmö är nu redo: 2/4 äldre Willys-baskontexter är åter användbara,
utan ändrade observationsdatum eller aktiva prismanifest.

Efter användarens "Aktivera och commita" driftsattes
`base-price-retention-app-0f54e51` och `base-price-retention-scheduler-0f54e51`
07:22:47 UTC. Selektiva patchar mot verkliga runtimebaser; fulla HEAD är inte
driftsatt. Driftlås, verifierade databasbackuper och radhashkontroll bevarade
278 befintliga planrevisioner och 92 privata tillstånd.
22225 fungerar i butikssökningen. Ett verkligt tremåltidsprov använder åter
Willys, kassakontrollen passerar och sparad GET/omladdning är identisk.
Chromium och WebKit verifierade. Inga insamlingsscheman ändrades.

Vid denna aktivering återstod ett separat Willys-schemafel kring
`hasPickingBaseStore`; den efterföljande parserrättningen redovisas ovan.
För driftåtgärder används `scripts/smako_ops.py` mot scheduler; äldre manuella
ops-profiler ingår inte i aktiveringen.
[Aktivering, belägg och återgång](releases/base-price-retention-20261015/ACTIVATED.md)
· [implementation](reports/base-price-retention-20261015.md).

---

# 2026-10-14: ICA-rättningar integrerade i det ordinarie Git-repot

Permanent projektrot är `D:\Projects\Smako`, remote
`https://github.com/ossebosse/smako.git`, huvudgren `master`.
Den separata återställda C:-kopian är historiskt underlag, inte utvecklingsbas.
Integrationen behåller den sammanhängande UI-/drifthistoriken från `38e4fd5`
och tillför ICA-rättningen `d4a7a84` samt uppdaterade regressionsförväntningar.

ICA-parser v9 accepterar källbelagd lös vikt och ungefärliga/intervallbaserade
förpackningsvikter, skiljer ut prydnadsväxter och märker antagen pant som
uppskattad. Beräkningsstödet och kampanjuppdateringen är gemensamma; den nya
automatiska källtolkningen gäller ICA. Ingen produktionsändring görs här.

97 riktade testfall verifierade genom första körningen och avgränsade omkörningar.
Ruff, compileall och JavaScript-syntax passerar. Ingen fullsvitsgaranti.
[Testurval, omkörningar och integrationsbas](releases/git-integration-20261014.json).

---

# 2026-10-14 19:51 UTC: Alternativ 3 aktivt på betan

Aktiv app `ui-option3-ff241807809b`, image `28f2638f27ef…`, sju statiska
frontendfiler ovanpå verkliga betan `ica-purchase-estimates-20261014-ui`.
Den senare ICA-koden bevaras; scheduler är fortsatt image `a5a55f723eaf…`.
676 övriga runtimefiler är identiska. Aktiverat på uttrycklig användarbegäran,
under driftlås efter ordinarie prisuppdatering, med backup. Ingen Git-push.

277/91 tidigare planrevisioner/privata tillstånd hashverifierat bevarade;
efter eget slutprov 278/92. Chromium/WebKit, nio dialoger, mobil/dator,
asset-hashar och cacheuppgradering v15→v16 passerar. Lunds verkliga plan med
alla tre måltider tog 119 s, audit PASS och identisk sparad GET.

Lund readiness 200. Malmö 503: fyra Willys-kontexter över 48 timmar.
Reproducerat med föregående betaimage vid tidpunkt före UI-bytet (50–51 h);
det är ett separat befintligt prisunderlagsproblem och är inte reparerat här.
UI:t och prisgränserna är oförändrat kopplade till verklig backend.

[Aktiveringsrapport, evidens, bilder och återgång](releases/ui-option3-20261014/ACTIVATED.md).
Den tidigare lokala rapporten nedan är historisk; detta avsnitt anger aktiv app.

---

# 2026-10-14: Godkänt konfigurations-UI alternativ 3 — endast lokalt

Branch `ui/approved-option-3`, bas `ad23943`. Befintliga `/personal` har nya
måltidskort, oberoende extra måltider, gemensamma utkastdialoger, explicita
fördelningskonflikter, granskning av smakförslag och mobil-/desktoplayout.
Backend, prisinsamling, schema, optimering och sparade produktionsval är orörda.
**Ingen push eller deployment.** Detta är inte aktuell produktionsrelease.

59 riktade UI/static-fall och 84 backendtester passerar. Riktig FastAPI med
kvarhållet verkligt Malmö-underlag, historisk testklocka och isolerad lagring
skapade en plan med alla tre måltider; korgaudit och identisk GET passerade.
Två äldre public-beta-texttester fallerar även på basversionen. Fysisk iOS
Safari är inte verifierad. Backend stöder enbart max energi, vilket bevaras.

[Implementation, API-kartläggning, testresultat och nya skärmbilder](../design/smako-ui-handoff/IMPLEMENTATION_REPORT.md).

---

# 2026-10-13 18:00 UTC: Förberedda priser och kommunvis menyförberäkning

Aktiv app `ops-prepared-pricing-32127ccf7e14`, image `3cf0bbe2ae51…`.
Gren `perf/prepared-pricing-20261013`; kodcommits `ec542ccf38d2` och
`32127ccf7e14`. Sex granskade appfiler ovanpå `ops-menu-reuse-334aeb2fa2a8`.
Source/scheduler är fortsatt `ops-price-recovery-7e28ff96f72d`;
ingrediensändringen `1518101` är inte driftsatt.

Oföränderliga erbjudandevillkor och exakta mängdberoende kassapriser återanvänds
begränsat; den inre butiksjämförelsen använder exakta heltalsören där kontexten
tillåter det. Samtliga kandidater och sök-/kvalitetsgränser är oförändrade.
Förberäkning i bakgrunden är aktiverad: 5 middagar, 2 portioner, 3 butiker,
balanserat val med alla tre alternativ, webbens exakta mängdpolicy och
annonserade medlemspriser. Samma kö gäller alla laddade och nya kommuner.

Fryst före/efter: 367,798 → 332,434 s kallt; 3,235 → 2,922 s varmt.
Hela planobjektet och sökräknarna identiska utom tider. 253 riktade testfall,
Ruff och compileall godkända. Separat kontroll med webbens exakta policy:
278,410 s förberäkning → 3,307 s i en ny tjänsteinstans, båda sökningarna
cacheträffar och samma meny/korg/kvalitet. En upptäckt 25/25.0-skillnad i
cacheidentiteten korrigerades och regressionstestades före aktivering.

Aktivering under operationslås med backup; alla tidigare 274 planrevisioner
och 90 privata tillstånd hashverifierat bevarade. Bara appen ersattes,
prismanifest och övriga containrar bevarades. Lund/Malmö readiness 200.
Slutprov: båda kommunernas bakgrundsberäkningar klara. Malmö 9,719 s i första
webbsessionen efter förberäkning, 8,172 s i en ny session, två cacheträffar/noll
missar i båda och 17/17 kontroller. Personlig meny 68,6 s med godkänd audit
och återläsning. Efter prov 277/91 sparade rader; inga nya OOM-händelser.

Se [resultat och evidens](releases/prepared-pricing-20261013/RESULTS.md).
Privata underlag: `.local/prepared-pricing-20261013/`. Backup/aktivering:
`/opt/smako/evidence/ops-prepared-pricing-32127ccf7e14/`. Återkör inte äldre
aktiveringsskript eller deploya hela lokala HEAD utan selektiv granskning.

# 2026-10-13: Menyåtgärder 5–6 verifierade

Aktiv app `ops-menu-reuse-334aeb2fa2a8` (image `2a0e9e029e0c…`).
Gren `perf/menu-reuse-20261013`, kodcommit `334aeb2fa2a8`.
Endast basket_optimizer.py lades ovanpå `ops-menu-7eab60a36fae`.
Source/scheduler är fortsatt `ops-price-recovery-7e28ff96f72d`;
ingrediensändringen `1518101` är inte driftsatt.

Punkt 5: begränsad återanvändning av kampanjstruktur, samma aktuella
mängdtak/källvalidering och oförändrad exakt sökning. Fryst hel meny
395,434 → 370,976 s kallt; varmt 2,989 → 3,065 s. Hela planobjektet och
sökräknarna är identiska utom tidsstatistik. 202 riktade testfall är godkända.
Punkt 6 införs inte: innehållscachens 952 träffar kunde spara 4,357 s men
nycklar/uppslag kostade 12,900 s. Minnesgränser är dokumenterade.

Live: publik meny 334.266 s kall / 8.141 s varm,
17/17 kontroller och identisk återläsning. Personlig meny 62.6 s,
godkänd checkout-audit/återläsning. Båda readiness 200 på rätt build.
Alla tidigare 271 planrevisioner och
89 privata tillstånd är hashverifierat
bevarade; efter prov 274/90.
Inga nya OOM-händelser. Aktiveringen inväntade operationslåset.
Samma förbättring gäller nya kommuner utan separata patchar.

Se [resultat och evidens](releases/menu-reuse-20261013/RESULTS.md).
Privata underlag: `.local/menu-reuse-20261013/`. Backup och aktiveringsbevis:
`/opt/smako/evidence/ops-menu-reuse-334aeb2fa2a8/`. Återkör inte gamla skript.

# 2026-10-13 15:04 UTC: Exakta menyoptimeringar driftsatta

Gren `perf/menu-exact-20261013`. Aktiv app `ops-menu-7eab60a36fae`
(image `3faff7284b50…`). Endast tre granskade appfiler lades ovanpå
`ops-runtime-d7bcd3571125`; source/scheduler är fortsatt
`ops-price-recovery-7e28ff96f72d`. Ingrediensändringen `1518101` är inte driftsatt.

Begränsad cache för ren textnormalisering, återanvändning av innehålls-ID och
egenskaper inom recepturvalet samt mindre arbete i den innersta exakta
butiksjämförelsen. Tomma butikskombinationer ger korrekt ofullständig korg
i stället för IndexError. Samma kod gäller befintliga och framtida kommuner.

Fryst full meny: 440,016 → 384,693 s kallt, 3,204 → 2,962 s varmt.
Hela planobjektet och alla sökräknare är identiska, utom tidsstatistik.
193 tester, 80 separata jämförelser av recepturval, Ruff och compileall är gröna.
Ingen minskning av sökutrymme eller kvalitetskrav. Första menyn är fortsatt långsam.

Live Malmö: 370,813 s kallt / 8,171 s varmt, 17/17 kontroller och identisk
återläsning; även recepten/korgarna/pris- och kvalitetsresultaten är identiska
mellan dessa körningar. Personligt liveprov: 56,9 s, godkänd audit/återläsning.
Båda readiness 200 på rätt build. Samtliga tidigare 268 planrevisioner och
88 privata tillstånd är hashverifierat bevarade efter slutproven; nu 271/89
med verifieringsplanerna. Inga nya OOM-händelser eller automatiska containeromstarter.

Se [åtgärder och evidens](releases/menu-optimization-20261013/RESULTS.md).
Privata prov: `.local/menu-optimization-20261013/`. Aktiveringsbevis och backup:
`/opt/smako/evidence/ops-menu-7eab60a36fae/`. Återkör inte gamla aktiveringsskript.

# 2026-10-13: Driftuppföljning och gemensamma kommunfixar slutförda

Gren `fix/operations-20261013`. Aktiv app `ops-runtime-d7bcd3571125`
(image `96408f133010…`), source och one-off-tjänster `ops-price-recovery-7e28ff96f72d`
(image `f45d9ae4ea87…`). Endast granskade filpatchar aktiverades.
Ingrediensändringen `1518101` är inte driftsatt.

Coop API-versioner och parser v3 är reparerade. Sparad fullkälla med 11 292
produkter återspelades nätverksfritt till `6a0f76920461481289bc6d3df523a481`,
med alla 819 råhashar/observationstider bevarade, och verifierades laddad i Lund.
ICA Bunkeflostrand, Hemköp 4247/4199 och City Gross 3211 är också godkända
på dokumenterad nivå och verifierat laddade i Malmö. Båda kommunerna har
readiness 200 och alla obligatoriska baskontexter är FRESH.

Kommunflödet äger sina fysiska Coop-erbjudanden. Exakt redan laddad publicering
kan kvitteras utan nytt bygge; verkligt förfallna källor går ordinarie väg.
Livekällan säkras till WAL/FULL under operationslåset före managed refresh eller
guarded replay, även efter restore. Det rättar personliga menyers databaslås
under prisjobb. Diagnostikens separata rågränser är 32 MB/fil och 128 MB/katalog.
Samma fixar gäller nya kommuner; Göteborg provas isolerat utan produktionsaktivering.

Offentlig Malmö-meny: 396 s kall / 8,7 s varm, 17/17 kontroller och identisk
återläsning. Personlig meny efter låsfixen: 61,3 s, godkänd audit/återläsning.
Första menyn är fortfarande långsam. Sex externa Coop/X:-tra-butiker saknar
kvalificerbart underlag och behåller backoff. Inga kvalitetsgränser har sänkts.

Full backup/restore-övning 60 filer/6,1 GB är godkänd. Alla tidigare 262
planrevisioner och 86 privata tillstånd är bevarade; verifieringsplaner har
tillkommit. Inga nya OOM-kill sedan 06:32 UTC. Båda reläer saknar väntande leverans.
Se [slutrapport och evidens](releases/operations-followup-20261013/RESULTS.md).
Privata körloggar finns i `.local/ops-followup-20261013/` och serverevidens under
`/opt/smako/evidence/` för exakt BUILD_ID. Starta inte om gamla repair-/crawlskript.

# 2026-10-13 07:39 UTC: Drift och prisuppdateringar granskade och reparerade

Gren `fix/operations-20261013`. Malmö hade readiness 503 efter tre avvisade
Willys-importer och fyra 57–58 timmar gamla kataloger. Parser v5 hanterar nu
den granskade nullable-number-övergången på katalogens `priceValue`, utan att
hitta på pris eller ändra generella kvalitets-/färskhetsgränser. Full offline
återspelning av kvarhållet underlag godkände 39 576 produktposter. City Gross-
diagnostiken läser nu kommunens korrekta godkända databasreferens. Ett separat
kvittensfel rättades: exakt redan laddad version kan bekräftas via scoped
readiness utan ett onödigt reload-anrop som fick timeout.

Slutlig source BUILD_ID `ops-price-recovery-2f44f4e1b13b`, image `885790a82a04…`.
Källcommits `1a7f5098942c`, `0fa290342376`, `2f44f4e1b13b`; endast granskade
källfiler paketerades ovanpå föregående aktiva image. Appen är oförändrat
`editable-sliders-7987bd5bc5d1`. Den nedan beskrivna ingrediensantalsändringen
är fortfarande lokal och ingår inte i denna produktionsaktivering.

Ordinarie Windowskörning 09:30 svensk tid lyckades, senaste resultat 0, nytt
Malmö-kvitto 09:36:19. Båda kommunerna är ready 200, publicerat = laddat och
samtliga obligatoriska baskontexter FRESH. Inga väntande reläleveranser.
Tidigare Willys-/prisbyggnadsincidenter är återhämtade i incidentindexet.

Sex appomstarter den 12 oktober kan knytas till kärnans OOM-logg. Två gamla
fristående testcontainrar stoppades reversibelt och frigjorde cirka 3,5 GiB;
appen omstartades inte. Inga nya OOM-händelser under granskningen. Dagens backup
hashverifierad. Alla ursprungliga 259 planrevisioner och 85 privata tillstånd
är bevarade; tre isolerade menyprov tillkom.

Publik och personlig Malmö-meny passerar prisaudit och identisk återläsning.
Kvarstår: publik femmiddagsoptimering tar 512/478 sekunder även vid upprepning
(personligt enmiddagsprov 40 s), sju butikskällor saknar godkänt underlag och
Coop Online Syd har ett transportfel med färsk LKG och ordinarie retry 11:00.
Prestandan är profilerad, inte reparerad. Håll kvar källornas backoff och
färskhetsgränser. Backupmanifest 11–12 oktober saknas, orsak ej fastställd;
ingen full återställningsövning gjord.

[Full driftgranskning, kvarstående källor och återgång](releases/operations-20261013/RESULTS.md).

---

# 2026-10-12: Ingrediensantal i Mina val — lokalt verifierat

Gren `feature/ingredient-count-choices` ersätter personliga receptstil-/nivåval
med synliga min/max-gränser per måltidstyp. Nya personliga förfrågningar använder
befintligt måltidsbibliotek utan nivåfilter; tomma gränser tillåter alla antal.
Äldre uttryckliga ingrediens-/tidsgränser återställs i formuläret, medan nya
förfrågningar inte återinför gamla nivåfilter. Sparade planrevisioner ändras inte.
Valen sparas även före inskickning i sessionen. Det äldre publika formuläret
behåller sitt befintliga receptlägesval.

41 tester passerade (Mina val i Chromium/WebKit samt måltidsbibliotek); sex
berörda browserfall återkörda efter layoutjustering, också godkända. Faktiska
bibliotekskandidater verifierade för intervallen 3–5 och 10–15; utan gräns ingår
både simple och crafted. Ruff, compileall och diff-kontroll passerade. Mobilvy
390 px visuellt granskad; separat prov bekräftade omladdning före inskickning.
API-svaren i browserproven är syntetiska; ingen live meny-/prisverifiering eller
produktionsaktivering utförd. Senaste aktiverade release beskrivs nedan.

---

# 2026-10-11 19:24 UTC: Fasta skalor och redigerbara reglage aktiverade

App `editable-sliders-7987bd5bc5d1` kör på betan. Fördelningens skalor följer
måltidsantalet och summan begränsas utan att andra kategorier flyttas. Alla
reglage har tangentbordsredigering av visade värden. Proteinets skala är 100 g,
kolhydraternas 400 g; äldre högre krav behålls synligt tills de ändras.
Medlemsprisavsnittet under Extraval är borttaget, prispolicyn är oförändrad.

18 fokuserade testfall passerar i Chromium/WebKit och API-kontrakt; berörda
fall återkördes efter slutjusteringar. Isolerad meny/omräkning, publik meny,
checkout-audit, identisk GET, mobilvy och tre statiska filhashar verifierade.
258 gamla planrevisioner och 84 privata tillstånd bevarades. Bara appimage
och BUILD_ID byttes under driftlås med säkerhetskopia; källor, scheduler,
Windowsuppgift och prismanifest ändrades inte.

Första publika planprovet fick SQLite `database is locked` i befintlig
produktunderlagsläsning under samtidig driftkontroll. Exakt incident sparad;
separat läsprov och nytt publikt planprov passerade. Låsägaren är inte fastställd
och ingen generell låsreparation påstås. Testcontainrar och tunnel är stängda.
[Verifiering och återgång](releases/editable-sliders-20261011/VERIFIED.md).

---

# 2026-10-11 18:24 UTC: Postnummer och måltidsfönster aktiverade

App `postcode-meals-93c4f9ac4505` kör på betan. Mina val börjar med postnummer,
ungefärlig 10-km-kontroll och val av butiker (1–5 km, kommun eller krysslista).
Måltidskort har tre dialogknappar och gemensamma min/max-reglage. Fördelningen
ryms alltid i måltidsantalet. Receptstil är kvar enligt användarens instruktion.
63 butiker i Malmö fungerar efter höjt explicit urvalstak; butikstaket för
själva korgen är oförändrat. Avstånd bygger på ungefärliga GISCO-referenspunkter,
och radieval gäller ett befintligt prisområde åt gången.

66 lokala testfall, isolerad riktig meny/omräkning, publik meny/audit/identisk
återläsning samt WebKit/Malmö-kontroll passerar. 257 tidigare planrevisioner
och 83 privata tillstånd är bevarade. Endast appen byttes under driftlås;
Windowsuppgift, scheduler, prismanifest och övrig miljö bevarades.
Testcontainrar och tunnel är stängda. Inga aktiveringsväntare återstår.
[Verifiering, geografiska begränsningar och återgång](releases/postcode-meal-dialogs-20261011/VERIFIED.md).

---

# 2026-10-11 15:07 UTC: Mina val aktiverad på betan

App `personal-choices-b48ca5925820` är aktiverad efter uttryckligt godkännande.
Huvudreglage för middagar, 1–6 portioner och butikstak; övriga val under Extraval,
valbar frukost/mellanmål, gemensam smak-/allergiprofil och näringsreglage.
Spårbara näringsuppskattningar och uppskattade köp tillåts i nya planer/omräkning.

256 tidigare planrevisioner och 82 privata tillstånd är bevarade; endast appen
byttes under driftlås. Scheduler, proxy, prismanifest, miljö och Windowsuppgift
är oförändrade. Publik Chromium-planering, checkout-audit, identisk återläsning
samt WebKit-mobilkontroller passerar. Låset är släppt och testappen stoppad.
Inga aktiveringsväntare ska återstartas.
[Verifiering och återgång](releases/personal-choices-20261011/VERIFIED.md).

---

# Lägg till nästa kommun — kort arbetsgång för Codex

Uppdaterad 2026-10-11. Vid kommunutökning: läs denna sektion och obligatoriska
AGENTS-/driftinstruktioner. Historiken nedanför behövs endast vid ett konkret fel.
Använd befintlig kedja; en ny kommun behöver normalt **ingen kodrelease, ny timer
eller ändring av Windowsuppgiften**. Registrering är inte bevis för färdigt utbud.

## 1. Läs nuläget en gång

Arbeta i `D:\Projects\Smako`. Kontrollera gren och arbetskopia före ändringar.
Läs [OPERATIONS](OPERATIONS.md), kör sedan:

```powershell
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py municipalities
ssh smako 'sudo -n docker exec --user 10001:10001 smako-scheduler-1 python -m grocery_data.municipal_cli list'
```

Spara JSON under `.local/municipal-<SCB-kod>/`; visa bara relevant kommun,
runtime, kapacitet och eventuella hinder. Undvik täta statuspollningar och bred
sökning i gamla releaser. Status är läsande och gör inga prisanrop.

Senast verifierat 2026-10-11 12:16 UTC: Lund **1281/22350** och Malmö
**1280/21120** är publicerade och laddade. Source `municipal-source-7b7fe72472dd`,
app `municipal-app-2b83475f5e68`. Windowsuppgiften **Smako Willys Local Relay**
är aktiverad och pekar på `D:\smako-local-relay\releases\7b7fe72472dd` med
`-Municipalities`, workspace `D:\smako-local-relay\scopes`. Administratörsbytet
är klart; kör inte installationssteget igen. Första schemalagda körningen efter
bytet var ännu inte observerad. Detta är en daterad baslinje, inte aktuell status.

## 2. Kontrollera kommun och mät kapacitet

Använd officiell fyrsiffrig SCB-kod och en unik femsiffrig bygg-/postnyckel.
Postnyckeln avgör inte kommungräns eller användarens position. Exemplet nedan
gäller Göteborg, som ännu **inte** är aktiverat; byt båda värdena för vald kommun.

```powershell
ssh smako 'sudo -n docker exec --user 10001:10001 smako-scheduler-1 python -m grocery_data.municipal_cli add --municipality 1480 --postal-code 41110 --dry-run'
```

Torrkörningen validerar registreringen, inte källtäckning eller kapacitet.
För en ny kommun behövs en komplett, uppmätt pilot i separat databas, rålagring
och artefaktrot. Återanvänd ett befintligt matchande underlag om det är yngre än
sju dagar och fortfarande beskriver tillgänglig kapacitet. Annars läs **endast
”Kapacitetsunderlag för nästa kommun” i [municipal_scaling](municipal_scaling.md#kapacitetsunderlag-för-nästa-kommun)**
för mätfält och pilotkrav. Ingen automatisk pilot finns i registreringskommandot.
Använd samma källkedja och gränser; kopiera inte Lunds eller Malmös mätvärden.

## 3. Registrera efter godkänd pilot

Placera den granskade pilotfilen läsbart för UID 10001 i serverns driftmiljö.
`/reviewed/pilot.json` nedan är en platshållare **inne i scheduler-containern**,
inte en lokal Windowsfil. Ersätt den med filens verifierade containersökväg.

```powershell
ssh smako 'sudo -n docker exec --user 10001:10001 smako-scheduler-1 python -m grocery_data.municipal_cli capacity --municipality 1480 --postal-code 41110 --capacity-evidence /reviewed/pilot.json'
# Kör nästa kommando endast efter PASS, inom användarens uppdrag att aktivera kommunen.
ssh smako 'sudo -n docker exec --user 10001:10001 smako-scheduler-1 python -m grocery_data.municipal_cli add --municipality 1480 --postal-code 41110 --capacity-evidence /reviewed/pilot.json'
```

`add` tar ordinarie driftlås, kontrollerar kapaciteten igen och skriver atomiskt.
Identisk registrering är idempotent. Vid upptaget lås: invänta ordinarie arbete;
starta inte en konkurrerande insamling. Server och Windowsrelä läser samma
register och tar kommunen vid kommande ordinarie pass. Reläets kö/kvitto får egen
`municipality-<SCB-kod>`-mapp under `scopes`. Bevara konton och scheman.

## 4. Verifiera innan nästa kommun

Kör `municipalities` efter en hel ordinarie uppdateringscykel. Redovisa separat:
upptäckta/kvalificerade/okända butiker, import, publicerat=laddat manifest för
rätt kommun, readiness/färskhet och motsvarande Willys-reläkvitto. Ett äldre
kvitto kan vara korrekt om senare erbjudanden har ändrat manifestet men samma
Willys-snapshot finns kvar. Kontrollera även att Lund/Malmö fortsatt fungerar.

Verifiera kommunval, egna butiksval, avståndsurval och en verklig meny med sparad
omladdning under separat testidentitet. Återanvänd
`scripts/release_verification/municipal_live_browser.py` och
`scripts/release_verification/public_menu_browser.py`; läs deras `--help` för
kommun, postnyckel, verifierad position och publicerade butikskontexter.
Rapportera produktposter, beräkningsindex och priskontexter som olika mått;
de är inte antal unika varor eller fysiska butiker.

**Stoppvillkor:** BLOCKED/okänd kapacitet, fel kommun-/butiksidentitet, saknat
källunderlag eller utebliven laddning/kvittens får inte redovisas som klart.
Rapportera exakt steg, orsak och minsta nästa åtgärd. Vid källfel använd
`smako_ops.py incidents` och riktad `reproduce`, inte en ny fullinsamling.
Behåll senaste giltiga data, backoff, 36/48-timmarsgränser och Coop-fullcrawl
endast `730400`. Fysiska Coop/X:-tra-erbjudanden är separata källor; saknat flöde
betyder okänd täckning. Registrering ändrar inte användarens sparade butiksval.

Avsluta med en kort daterad status här: kommun/byggnyckel, kapacitetsbevisets
sökväg/hash, runtime, publicerat/laddat ID, kvitto, täckningsluckor och nästa steg.
Länka detaljer i stället för att klistra in loggar. Ingen bred testsvit eller
ombyggnad behövs för ren registrering; vid kodfel testa den berörda ändringen.

---

# Historik — läs endast vid behov; senare verifiering ovan gäller före äldre väntelägen

# 2026-10-11 10:51 UTC: skalningsfunktioner aktiverade på servern

Källprocess **`municipal-source-7b7fe72472dd`**, image
`sha256:1f10310fbccfae541b816fdf66b06029adcf5860923ce0a5e1b40542d5f1803b`,
aktiverades 10:40:59 UTC under ordinarie driftlås. App, proxy, scheman, mounts,
Coop-allowlist och användarval är bevarade. Samtliga 256 planrevisioner och 82
privata tillstånd har verifierats oförändrade. Aktiveraren är avslutad och låset
släppt; kör inte om den daterade aktiveringen.

Implementerat: hashkontrollerade Willys-checkpoints per färdig butik, prioritering
efter deadline/väntetid med sparad tur före start, avgränsade Hemköpsvarv,
kapacitetskrav för nya kommuner, separat återförsök av väntande runtime-laddning,
samt `scripts/smako_ops.py municipalities` med kommunernas butiksplanering och
lokala reläkvitton. [Funktioner och pilotkrav](municipal_scaling.md).

Windowsinstallationen verifierades med 685 filer och låsta beroenden.
Det första uppgiftsbytet nekades av Windows med ”Åtkomst nekad”. Användaren
utförde därefter administratörssteget; läsande kontroll 12:16 UTC bekräftar
`7b7fe72472dd`, `-Municipalities`, rätt workspace och aktiverad uppgift.
Lokalt bevis: `.local/municipal-scaling/status-user-admin.json`.
Det tidigare adminhindret är löst; ingen ny installation behövs.

Det nya installerade reläet har manuellt verifierats med ny insamling uttryckligen
spärrad. Lunds tidigare saknade kvitto är nu återställt: `fe7461f2…`, server-snapshot
`94f905b1bca84bbab5392f291acb650b`, `already_active`, kvitto 10:44:39 UTC. Det krävde
varken ny prisinsamling eller nytt prisbygge. Malmö var inte insamlingsförfallet.
Båda kommunerna visar `pending_delivery: false`. Malmökvittots äldre manifest-ID
hör till den då levererade Willysfilen; senare kampanjpublicering har nyare ID.

Live 10:51 UTC: readiness 200 i båda kommuner, publicerat=laddat. Lund
`70789e42…`, 29 kontexter; Malmö `8c49ecda…`, 63 kontexter. Ordinarie serverpass
10:45 startade Malmö före Lund eftersom endast Malmö hade förfallet arbete.
Det passet var fortfarande pågående vid verifieringen; invänta ordinarie status,
starta ingen konkurrerande uppdatering. Full avbrottsprovning i produktion har
inte gjorts och ingen ytterligare kommun har aktiverats.

128 relevanta testfall är verifierade. Den första source-paketeringen saknade
`relay_storage.py` (två fel); slutbilden innehåller filen och 44 riktade prov
passerar. 118 tidigare PASS återanvänds med oförändrade kodhashar; tillsammans
127 unika releaseprov, plus ett prov för lokal kommun-/kvittoöversikt. Lund/Malmö
återupptagningsprov använder sparat officiellt register/geometri och syntetiska
kataloger, inga liveanrop. Ruff och compileall passerar. Den samlade adminläsaren
behövde större tidsbudget under pågående bygge: högst 180 sekunder för kommuner,
med fortsatt explicit unknown vid timeout. Slutkontrollen gav observed för både
server och Windows i båda kommuner.

En livekontroll utan kapacitetsmätningar gav BLOCKED för Göteborg och lämnade
registret oförändrat. Piloter behöver fortfarande utföras och mätas före nästa
kommun; kontrollerna fabricerar inga kapacitetsbevis. Coop/X:-tra-källuckorna
nedan och extern larmleverans är inte lösta av denna etapp.

[Maskinläsbara releasebevis](releases/municipal-scaling-20261011/ACTIVATED.json).
Privat serverevidens: `/opt/smako/evidence/municipal-scaling-7b7fe72472dd`.
Lokala körbevis: `.local/municipal-scaling/`. Endast ordinarie driftjobb kan
fortfarande köras; inga aktiverings-/leveransväntare ska återstartas.

---

# 2026-10-11 09:11 UTC: 106,49 GB frigjort, Malmö-Hemköp publicerat

Serverns lediga utrymme är **118,39 GB** efter verifierad arkivering av 15
oanvända testmiljöer och rensning av oanvänd Dockerbyggcache. Inga bilder,
containrar eller dagsbackuper raderades. Körande tjänster, återgångsversioner,
ICA-arbete och samtliga 256 planrevisioner/82 privata tillstånd är bevarade.
Det gemensamma driftlåset är släppt och underhållsväntaren är avslutad;
starta inte om den daterade körningen. Arkiven finns i
`/srv/smako/cold-test-archives`, med verifieringsbevis under
`/opt/smako/evidence/storage-reduction-20261011`.

Root-ägarskap på dagsbackup `20260914T123547Z` blockerade backupkontots åtkomst
och den befintliga retentionens rensning. Innehållsverifierad historisk kopia
sparades och ägarskapet rättades till 10001:10001 utan ändrade filinnehåll/modes.
14-dagarsretentionen är oförändrad. Nästa lyckade fulla backuprotation behöver
följas upp; den kördes inte som del av detta underhåll.

Ordinarie insamling före städningen promoverade **Hemköp Värnhem 4199**,
snapshot `5583bcc0ac8a4331a909cc827efb1606`, och **Elinegård 4212**,
snapshot `609c6dde3df84c2ead55e2b420ee8199`. De tidigare väntande liveförsöken
är därmed genomförda. Malmö har nu **2 607 produkter och 63 pris-/butikskontexter**,
varav åtta Hemköp-kontexter (fysiska erbjudanden och onlinepriser hålls isär).
Publicerat/laddat manifest är `8c49ecda4bf9a61a2388d0f73ddd46ecce0fe7ae91421f6ba7e545fed1e0c4c0`.
Readiness är 200/FRESH. Lund har fortsatt 2 263 produkter, 29 kontexter,
manifest `68761dcf…`, readiness 200 och befintlig AGING för Willys.
App/source/proxy/relä och scheman är oförändrade. Övriga källuckor nedan kvarstår.

[Lagringsrapport och återställning](storage-maintenance.md),
[maskinläsbara verifieringsbevis](releases/storage-reduction-20261011/VERIFIED.json).

---
# 2026-10-11 07:13 UTC: Coop publicerat, Hemköp Brunnshög återställt

Källprocess `municipal-source-0e2bacd95c03` är aktiverad. App `2b83475f5e68`,
proxy, relä, konton och scheman är bevarade. Föregående källrelease `17a75cf`
återställde Coop/Hemköp; slutpaketet lägger till kommunavgränsad driftstatus.
Inga aktiverings- eller publiceringsväntare ska startas om.

Malmö har **2542 produkter och 61 valbara pris-/butikskontexter**: 13 fysiska
Coop-butiker har tillkommit. Publicerat och laddat manifest är `77696ecb…`.
Lund har **2263 produkter och 29 kontexter**, med nio ytterligare fysiska
Coop-butiker. Manifest `68761dcf…` innehåller Hemköp Brunnshögs återställda
5103-varukatalog, snapshot `0fc4d1a4bd3e46938a2c037ed39ad479`.
Båda kommunerna ger readiness 200. Lund är AGING på grund av äldre Willysdata;
Malmö är FRESH. Kontrollera den ordinarie reläkörningen 07:30 UTC vid nästa uppföljning.

Hemköp Värnhem 4199 och Elinegård 4212 har granskade butiksspecifika minimigränser
6 300 respektive 5 800. Fullständiga autentiska underlag med 7 171/6 475 produkter
klarar den nya valideringen. **Ny liveinsamling och produktionspromovering av
dessa två kataloger återstår**: befintlig backoff till 08:02:19 UTC bevaras;
första möjliga ordinarie 15-minuterspass är normalt 08:15 UTC. Radera inte backoff eller
försvaga gamla snapshots sparade 8 000-gräns. Kontrollera ny snapshot, exakt
butikskoppling, publicering och laddning efter det ordinarie försöket.

Fyra Chromium/WebKit-fall för publik/personlig kommunkontroll passerar med 61
kontexter och sex avståndsval inom 1 km från den simulerade positionen. En verklig
meny med Willys Emporia och Stora Coop Stadion valda passerar audit och identisk
omladdning; den vinnande korgen använde endast Willys. Alla 255 tidigare
planrevisioner och 82 privata tillstånd är hashbevarade; verifieringen tillförde
en publik revision.

Kvarvarande källuckor: Coop Central/Kornettsgatan/Djupadal saknade kvalificerbara
erbjudanden vid nya liveförsök. Centralens verkliga HTTP 200-svar var `{}`.
X:-tra Söderkulla/Nydala saknar fungerande butiksegna publikationer. Dessa är
inte bevis för att butikerna saknar erbjudanden. Coop-fullinsamling endast 730400.
Den gemensamma diagnostiken läser nu rätt kommun och kan inte friskförklara
Malmö med Lunds manifest. City Gross 3211 visas dock som källbevis `unknown` i
denna läsare eftersom dess separata kommunala källdatabas inte omfattas;
publicerad kontext/readiness är verifierad separat. Dölj inte denna skillnad.

[Releasebevis](releases/municipal-source-repair-20261011/ACTIVATED.json) och
[prioriterad plan för större utrullning](municipal_scaling.md).
Detaljer finns i `.local/municipal-repair/` och skyddad serverevidens enligt JSON.
Göteborg är fortfarande endast torrkört; inga fler kommuner är aktiverade.

---

# Tidigare 2026-10-11: Malmö i kommunvis drift, platsval och butiksvisa återförsök verifierade

Permanent rot `D:\Projects\Smako`, gren `feature/municipality-rollout`.
Användarens administratörssteg för relä `f5b6aedc851d` är verifierat.
Malmö och Lund är tillgängliga; Malmö har 2529 produkter och
48 valbara butiks-/priskontexter. Detta är inte full kedjetäckning.

App `2b83475f5e68`, källinsamlare `f6a38b849035`, proxyfix `1fc4b6c` är aktiva.
Samma Windowsuppgift och servercron fortsätter kommunvis. Automatisk reläkontroll
23:30 UTC lyckades för båda kommunerna utan nya prisförfrågningar.
Källinsamlarens nya planering begränsar Hemköps återförsök till de butiker som
behöver uppdateras och sparar väntetid per butik. Kvalitetsgränser är oförändrade.

Fyra riktiga browserfall (publik/personlig, Chromium/WebKit) passerar med
produktionens platsåtkomst. Manuell butik, kommunspecifika sparade val och
avståndsurval är kontrollerade. GPS-positionen är simulerad; avstånds-API:t är äkta.
En riktig Malmömeny begränsad till Willys Emporia passerar beräkning, inköpskorg
och identisk omladdning. Alla tidigare privata rader är hashbevarade.

Detaljer, uppmätta kapacitetsgränser och nästa kommuns kommandon finns i
[kommunbeskrivningen](municipality_coverage.md) och
[releasebeviset](releases/municipal-rollout-20261011/ACTIVATED.json).
Första reläkvittot hör till första Malmömanifestet; senare normal publicering
har ett nyare manifest. Jämför aktuell publicering med laddad version och rätt
källsnapshot, inte med ett historiskt reläkvitto för samma oförändrade Willysfil.

Kvarvarande hinder: Coop/X:-tra saknar godkända Malmökanaler; Värnhem och
Elinegårds fullkataloger når inte befintlig 8 000-varugräns. Verifiera separata
butiksbaslinjer, utan att sänka kedjans generella kvalitetskrav. Lund 4224 har
fortsatt schemahold. Större kommuner kräver kapacitetskontroll och kan behöva
återupptagbar insamling per butik. Göteborg är bara torrkört, inte aktiverat.

Caddys korrekta runtimefil är nu explicit bunden till
`/opt/smako/overrides/Caddyfile.geolocation-1fc4b6c`. Den tidigare bindningen
motsvarade inte aktuella symlänksökvägen. Bevara denna exakta konfiguration.
Aktiveringarna ändrade inte appens användardata, taskkonto eller cron-schema.
Inga operatörsväntare ska återstartas efter deras bekräftade framgång.

---

# 2026-10-10: Jämförbarhetskandidaten AKTIVERAD – samlad på master

App `comparability-app-5786d5fa6a0f` / image `ca1b3532…` och källprocess
`comparability-source-5786d5fa6a0f` / image `63cc251f…` aktiverade
19:28:53 svensk tid. Runtime `5786d5fa6a0febb7a581a70e583e5c876d494da2`.
Readiness200, fullständiga recept på, samma publicerade/laddade manifest50c0.
Reläfe795, scheman, proxy och datamounts bevarade. Backup och komplett
Compose-diff granskade; endast app/scheduler image+BUILD_ID ändrade.

Live Chromium/WebKit shopping och produktsökning PASS. Publik femmiddagsmeny
PASS, audit, ett jobb/dubbelstart, omladdning, inköpslista och sparad GET.
247 tidigare revisioner/79 privata tillstånd hashbevarade; nya verifierings-
identiteter tillförde5 revisioner/3 tillstånd. Inga gamla data återställda.

**Scan65 ännu inte publicerad:** källfixen används nu, men Coops befintliga
backoff till20:00:40 svensk tid bevaras. Ordinarie nästa passande15min-kontroll
väntas20:15. Hämtning/publicering efter detta har ännu inte verifierats.
Nästa kontroll ska börja med `scripts/smako_ops.py status` och Coops källjournal,
inte ny installation eller bred utredning. Samtliga fem baser fortsatt FRESH.

[Utförd aktivering](releases/comparability-20261010/ACTIVATED.md),
[sanerade livebevis](releases/comparability-20261010/ACTIVATED.json).
`master` har fast-forwardats till det sammanhängande arbetet. Aktiveringscommit
`713e5d2` verifierades på både `origin/master` och
`origin/feature/comparability-20261010` efter vanlig push till GitHub
ossebosse/smako. Kandidatens tidigare ”ingen push/aktivering”
nedan beskriver dess historiska leveranstillstånd, inte nuvarande instruktion.

---

# 2026-10-10: Jämförbarhetsförslag implementerade – EJ AKTIVERADE

Gren `feature/comparability-20261010`, runtime
`5786d5fa6a0febb7a581a70e583e5c876d494da2`. Appimage `ca1b3532…`,
källimage `63cc251f…`, separata identifierade paket på D: under
`.local/comparability-fix-20261010/final-app-package/` och `final-source-package/`.
Imagearkiv med båda OCI-images, 166 hashverifierade blobs, ligger i etappens rot.

Scan65 återfunnet och kvalificerat i **både Värpinge3659 och Klostergården3820**.
Två riktade offentliga butikshämtningar 13:57 UTC, inga fullkataloghämtningar.
Exakt granskade buyAmount/payAmount/claim/weeklyTip rättade; köp3betala2 utan
variantpriser fortsatt blockerat. Inget fysiskt pris flyttat till Online Syd.
Vitlök57g från uttrycklig källtext, Willys verifierade styckgräns för viktpris,
och gemensamt explicit antal köpförpackningar för okänt innehåll implementerade.
956 av tidigare1390 blockerade rader kan väljas som antal köpförpackningar på
samma gamla artefakt; inte nya gram-/näringsgodkännanden. ICA/Willys öppna
kampanjval når nu snabbmenyn; Lidl befintlig uppskattningsväg bevarad.
City Gross saknar kvalificerad källa och visas som täckningslucka.

296 tester på levererad appimage PASS; 114 av dessa även på separat källimage.
Mobila Chromium/WebKit shoppingflöden och publik sökning PASS. Riktiga jobb,
dubbelklick1POST, audit, revision1/2, omladdning, ägare403. Inga pageerrors eller
nätfel i godkända körningar. Testmiljöfel och tidigt baskontrollstopp bevarade.
24 appfiler/7 källfiler/6 HTTP-filer hashkontrollerade; inga runtimekällmounts.

[Resultat per fall](releases/comparability-20261010/RESULTS.md),
[källbelägg/research](releases/comparability-20261010/RESEARCH.md),
[maskinbevis](releases/comparability-20261010/EVIDENCE.json),
[framtida separata aktiveringar](releases/comparability-20261010/ACTIVATION.md).
Ingen betaaktivering, reläändring, prispublicering, schemaändring eller push.
Senast observerad beta fortfarande return-session205; denna etapp har inte
utfört ny driftstatuskontroll. Ny privat testlagring stannar isolerat på D:.

---

# 2026-10-10: Alla annonserade medlemspriser + Scan-utredning – EJ AKTIVERAD

Gren `feature/member-prices-scan-20261010`, runtime
`f00f5304e5449bd8417f3dab4fcb547e27135de7`, image `7635779a…`,
BUILD_ID `member-prices-f00f5304e544`. Separat appdelta på viktkandidaten 0e7/205.
Nya menyer, omräkningar och sökning tar med alla sex generella medlemsprogram;
valda totalsummor märks med faktiskt nödvändiga medlemskap. Innehav ändras inte,
personliga kuponger aktiveras inte, äldre revisioner behåller sina villkor.
145 backend/källtester på hashidentisk backend, personliga mobila Chromium/WebKit
PASS (Satsumas 22,40 i replay, medlemsmärkning, revisioner/ägare/audit).
Publik slutimage PASS med riktigt jobb, dubbelstart, omladdning och sparad GET.
Föregående publika prov hittade readiness-timeout som lämnade knappen spärrad;
nu ny readiness-GET efter resultat och generationsskydd. Före-FAIL/efter-PASS
regression. Två nätavbrott finns kvar i slutprovet; inga pageerrors och korrekt
återhämtning. Ingen prestandaförbättring hävdas (190,8 s enskilt klickprov).

**Scan 65 kr/kg återfunnet** i fysisk Coop Värpinge Lund 3659, råsvar 9 oktober.
Snapshot avvisades på `priceInformation.buyAmount/claim/payAmount`.
Fältvärden/typer saknas i det bevarade strukturerade felsvaret; separat källfix
behöver normaltransportens fullständiga JSON. Online Syd visar 105 kr/kg utan
kampanj; inget butikspris flyttat till online. Källspärren är inte rättad av appen.
[Resultat](releases/member-prices-scan-20261010/RESULTS.md),
[Scan-belägg och reproduktion](releases/member-prices-scan-20261010/SCAN.md),
[evidens](releases/member-prices-scan-20261010/EVIDENCE.json),
[separat app-only-beslut](releases/member-prices-scan-20261010/ACTIVATION.md).
Paket/image på skyddad lokal D: `.local/member-scan-20261010/recovery-package/`.
Beta senast läst som return-session-205cd8ca0f31; ingen produktionsändring eller
push. Offentliga sparade källfakta exporterades läsande till isolerat test; ingen
ny prisinsamling eller kopiering av privata produktionsplaner.

---

# 2026-10-10: Viktprisjämförelse och synligt uppskattningsval – EJ AKTIVERAD

Gren `fix/weight-offers-20261010`, runtime `0e7c20dfa91183b622cce340093a8a6cca93a5a9`.
Appdelta på verklig 205-image, ny image `523caa8e…`, BUILD_ID
`weight-offers-0e7c20dfa911`. Beta/källprocess/relä/prispublicering oförändrade.
Kilopris visas med enhet genom befintliga köp- och mängdkontroller. Inköpslistan
har ett uttryckligt uppskattningsval och tydlig exakt-mode-stopporsak.
Samma ordinarie gemensamma korg, audit, näring, medlemskap och revisioner.
Satsumas 20 kr/kg belagt; 1 000 g behov => cirka 1 120 g / 22,40 kr i replay.
Scan 65 kr/kg från fysiskt blad saknar koppling till Online Syd-råsvaret
(105 kr/kg, inga kampanj-ID:n). Det priset har inte lagts på genom namnmatchning.
1 002 viktprisrader jämförbara; kvarstående okänd mängd/variant/köpgräns redovisad.
167 tester PASS mot paketerad runtime över två körningar; en saknad testfixture
i första körningen bevarad. Strikta mobila Chromium/WebKit-flöden PASS inklusive
sparad GET, omladdning, ny/äldre revision, ägare och misslyckad lägesändring.
10 runtimefilhashar och fyra serverade HTTP-filer verifierade. Inga liveplaner.
[Resultat](releases/weight-offers-20261010/RESULTS.md),
[källluckor](releases/weight-offers-20261010/RESEARCH.md),
[separat app-only-beslut](releases/weight-offers-20261010/ACTIVATION.md).
Paket/imagearkiv på D: `.local/weight-offers-20261010/package/`; inga privata data i Git.
Ingen push eller aktivering utförd i denna uppgift.

---

# 2026-10-10: Källvalidering, importmarginal och återkomstfix AKTIVERADE

Beta `return-session-205cd8ca0f31`, image `853d5b98…`, från 09:55 UTC.
Källprocess `source-ops-04e47c691e0c`, image `441e1a2b…`. Gren
`fix/source-return-recovery-20261010`; två avgränsade paket, ingen ny måltidsrelease.
Alla fem obligatoriska baser FRESH, `/ready` 200, laddat/publicerat manifest
`50c0bb0e83de…` vid 10:04 UTC. Willys exakt en import och beständigt kvitto.
Inga nya prishämtningar: autentiska 9 oktober-underlag återanvändes.
Fyra inaktiva testkataloger arkiverade/hashverifierade på skyddad D:, därefter
borttagna med befintligt godkännande. 11,32 GB frigjort; 16,19 GB ledigt på
servern efter arbetet mot 8,87 GB beräknat importbehov. Ingen gräns sänkt.
Windowsrelä fe795/S4U/Limited och scheman oförändrade; senaste manuella
behovskontroll not_due/0 prisanrop. Inga pauser kvar.
71 källtester, tre fulla paketerade replay och 30 534 produktjämförelser PASS.
Publik Chromium samt personlig inköpslista Chromium/WebKit PASS; bevarat
första felaktigt navigationsantagande i testverktyget redovisas separat.
240 gamla revisioner/74 privata tillstånd oförändrade; alla 246 revisioner läsbara.
Fyra faktiskt serverade filhashar matchar. Gästsessioner, inte alla OIDC-konton.
[Slutrapport](releases/source-return-recovery-20261010/RESULTS.md),
[utförda aktiveringar/återgång](releases/source-return-recovery-20261010/ACTIVATED.md).
Ingen push. Kör aktuell `smako_ops.py status` vid nästa driftärende.

---

# 2026-10-10: Fel vid återkomst – rättad kandidat, prisdrift fortfarande spärrad

Gren `fix/return-session-20261010`, runtime `205cd8ca0f31`.
Frontend återförsökte avsiktlig prisgate-503 som nätfel och återläste gamla
jobb före sparad korg. Rättat, 28 lokala + 28 paketerade tester och strikta
Chromium/WebKit-prov PASS. Fyra serverade filhashar verifierade.
**Inte aktiverad, ingen push.** Beta kvar på `shopping-list-6b10628f22d8`.
Senaste /ready 503 vid 2026-10-10 06:55 UTC: Willys >55 h, PlanStore/DB OK.
Källvalidering blockerar nya Willys- och Hemköpsunderlag; ingen dataradering.
Servermarginal otillräcklig för ordinarie import (5,20 GB ledigt mot 8,69 GB).
[Resultat, precis diagnos och återstående steg](releases/return-session-20261010/RESULTS.md),
[separat app-only-anvisning](releases/return-session-20261010/ACTIVATION.md).
Börja fortfarande med ordinarie `smako_ops.py status`, inte gamla statusvärden.

---

# 2026-10-09: Inköpslistan och snabbmenyn AKTIVERADE

Beta kör `shopping-list-6b10628f22d8`, image `a5b678ca…`, sedan 16:48 UTC.
Endast appens image/BUILD_ID bytta efter godkännande, backup och operationslås.
Receptflagga true, källor/relä/scheman/övriga containrar bevarade. /ready200.
234 gamla revisioner och 68 privata tillstånd bevarade. Chromium/WebKit
riktiga inköpslisteflöden inklusive omräkning/revisioner/ägarskydd PASS.
Publik femmiddagsknapp PASS, 145,125 s (inget 60-sekunderspåstående).
Willys AGING cirka 41 h vid kontroll, inom 48 h; övriga obligatoriska baser FRESH.
OIDC fortfarande ej konfigurerad; liveprov använder separata gästsessioner.
[Utförd aktivering och verifiering](releases/shopping-quick-menu-20261009/ACTIVATED.md).
Äldre noteringar om ej aktiverad kandidat nedan är historiska.

---

# 2026-10-09: Gemensam snabbmeny för inköpslistan

Gren `feature/shopping-quick-menu-20261009`, runtime `6b10628f22d8`.
En Lägg till vara-knapp, sökmeny med generiskt först och konkreta produkter
utan butiksväljare/priser. Tillbaka till generisk vara och redigering av
befintlig generisk rad. Produktkopplingar/one_of bevarade; ingen prisidentitet
härledd enbart från namn. Närmare generisk betydelse rankas först i förslagen.
59 lokala och 59 paketerade tester, Chromium/WebKit riktiga korgflöden PASS.
**Inte aktiverad.** Den äldre inköpslisteimagen har inte denna förbättring.
[Senaste resultat, image/paket och framtida aktivering](releases/shopping-quick-menu-20261009/RESULTS.md).

---

# 2026-10-08: Fristående inköpslista – implementerad, inte aktiverad

Gren `feature/independent-shopping-list-20261008`, runtime `38a85dafa18a`.
Exakta/generiska varor, prisfria förslag, uttryckliga antingen-eller-rader,
fristående eller gemensam receptkorg och ägarbundna vanliga val.
130 backendtester mot slutimagen PASS. Slutliga Chromium/WebKit-knappflöden
PASS med audit, ägarskydd, omräkning och revisionsläsning efter omstart.
Tidigare strikt underkända avbrutna sökförfrågningar bevaras; ingen generell
WebKit-/nätfelsdispens. Betan saknar OIDC-konfiguration; kontoflytt backendtestad.
[Resultat och begränsningar](releases/shopping-list-20261008/RESULTS.md),
[framtida separat appbeslut](releases/shopping-list-20261008/ACTIVATION.md).
Image `dce98e90…`, leveranspaket på D:, inget från denna funktion är aktiverat.
Beta är fortsatt `meal-library-42fab888ffd7` enligt nedan. Efter liveprov finns
232 revisioner/67 privata tillstånd, alla tidigare 228/65 bevarade.

---

# 2026-10-08: Måltidskandidaten aktiverad efter godkännande

Beta kör **meal-library-42fab888ffd7**, image **d17a4c07…** från 20:04 UTC.
54cb + åtta nya recept + senare status/incident/erbjudandesorteringsfixar.
Inga nya inköpslistefunktioner ingår. /ready200, samma manifest/fem färska baser.
Publik Chromium och personlig WebKit (15/30, byte, omräkning, revisioner) PASS.
228 gamla revisioner och 65 privata tillstånd bevarade. Gästsessioner, OIDC ej konfigurerad.
[Utfört byte och säkerhetskopior](releases/meal-activation-20261008/ACTIVATED.md).
Ny inköpslista utvecklas separat; använd inte dess källmount som releasepaket.

---

# 2026-10-08: Åtta ytterligare recept, alla måltidsklasser – isolerat PASS

Gren `content/all-meal-classes-20261008`. Två enkla middagar, två genomarbetade,
två frukostar och två mellanmål importerade genom oförändrad innehållsväg.
190 aktuella receptposter, tidigare versioner bevarade. **Inga programändringar**:
610 imageprogramfiler och 20 äldre receptfiler identiska med 54cb-basen.
8/8 kvalificeringar, 17 bibliotekstester, fem fria knappflöden och två explicita
åttareceptsflöden PASS. Chromium/WebKit mobil, kombinationsvecka 15/30,
omladdning/dubbelstart, byte/omräkning/revisions-GET och omstart testade.
Det första felkonfigurerade crafted-provet kvarstår FAIL; appen avvisade rätt.

[Resultat, recept och belägg](releases/all-meal-classes-20261008/RESULTS.md).
Innehållsimage `9784eb87…` ovanpå exakt 54cb/8a537fc4…, inte produktionsrelease.
Inga nya fakta; historisk replay 4 oktober. Inga protein-/allergenkrav i
individprovet, inga provlagningspåståenden. Egna testappen är stoppad efter prov;
state/image bevaras, återstart enligt REPRODUCE. **Beta är oförändrad enligt
aktiveringsrapporten nedan. Ingen aktivering eller push i denna receptetapp.**

---

# 2026-10-08: Appfix aktiverad efter godkännande

Beta kör **app-incident-293fc6c49400**, image **c7295a8e…**, sedan 17:02:10 UTC.
Det är den selektiva dd12-baserade appfixen, inte måltids-/sökoptimeringsgrenen.
Kompletta recept är påslagna, /ready200, samma prismanifest och fem färska baser.
Konsistenta plan-/grocery-backuper och privata konfigurationskopior finns på
skyddad serverlagring. Alla 222 gamla revisioner och 63 privata tillståndsrader
bevarades; gamla revisioner lästes med ny runtime. Publik Chromium och personlig
WebKit i mobil layout PASS: dubbelstart, omladdning, receptbyte, omräkning,
revisions-GET och ägarskydd. Inga nya 5xx observerade i efterkontrollen.
OIDC är inte konfigurerad; proven avser befintliga gästsessionsflöden.

[Utfört byte och belägg](releases/app-status-incident-20261008/ACTIVATED.md).
Användaren godkände också commit/push till origin; aktuell leveransgren är
`fix/app-status-incident-20261008`. Bygg inte hela senare grenen som appimage.
Prisdrift, D:-relä, source-ops, scheman och proxy bevarades. Inga nya pauser.
Originalets 500 nedan har fortfarande okänd grundorsak; första provet är FAIL.

---

# Tidigare 2026-10-08: Publikt status-500 avgränsat; då ej aktiverad

Börja med `.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status`.
För det historiska felet: `app-incident --request-id 9e96c548-6414-467b-ab7e-3d5e4fe6d779`
genom samma CLI. Det läser befintlig appmetrik även på dd12; inget källbyte behövs.

Klientloggen binder exakt jobb/start/statusreferens till 500 vid status-GET.
Klientens svarstid 14:51:20.452506 UTC är inte servermetrikens lagringstid
14:51:24.173961 UTC. Exceptionkedjan saknas och historisk grundorsak är okänd.
Samma rekonstruerade val och bevarade pris-/faktaunderlag gav 201 i isolerad dd12.
Sorteringshypotesen anropades inte där. Första försöket är fortfarande FAIL.

En belagd separat statusdefekt rättas selektivt med befintlig ab2718a:
PolicyConflict/PersonalConflict blir 422/409 i stället för 500. Ny bounded privat
incidentinsamling kompletterar request/job/steg/exceptionens kodställen utan
hemligheter. Ingen automatisk omstart eller extra genererings-POST tillagd.

Kandidatdelta **293fc6c49400f6f508eebb6772774d4fdfd995c9**, image **c7295a8e…**.
Paketet är dd12 + selektiv statusfix + incidentdelta; bygg INTE hela senare
arbetsgrenen som apprelease. 58 riktade prov på grenen och samma 58 mot paketet,
negativa imageprov även som UID10001, riktig Chromium mobil menyresa med
omladdning/offline/byte/omräkning/revisions-GET/ägarskydd PASS. Fullt planinnehåll
matchar före/efter utom versioner/tider. Egna isolerade appen är stoppad.

[Resultat och kvarstående kunskapslucka](releases/app-status-incident-20261008/RESULTS.md),
[exakt kandidat och framtida app-only-byte](releases/app-status-incident-20261008/ACTIVATION.md),
[maskinläsbara belägg](releases/app-status-incident-20261008/EVIDENCE.json).
Privata råprov: `.local/app-status-20261008/`. Inga nya fulla menyomkörningar
utan nytt belägg. Betan fortsätter dd12, samma container/starttid och /ready200;
källfix/relä/prisflöde bevarade. **Ingen aktivering eller push gjord.**

---

# 2026-10-08: Hemköp återställt och gemensam driftstatus aktiverad

**Prisdriften är återställd; en första publik HTTP 500-händelse kvarstår som
separat, oförklarad appanmärkning.** Läs först [OPERATIONS.md](OPERATIONS.md),
kör `.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status` i D:\Projects\Smako.
Fortsätt med `incidents`/`reproduce`; börja inte om med hela historikarkivet.

Slutlig source-runtime **ce326c1d7fcf5235e77ea4fcf2139d4fb25be849**, endast scheduler,
image **sha256:8fce7b9c72fbadc615aba9b46d2a2fec32a81dfb87231b33aae20ebca6547e3b**.
Betan är oförändrad dd12; fe795-reläet och Windows-XML oförändrade. Ingen
mål-/prestandakandidat aktiverad. Releasepaket/aktivering, 173 tester och resultat:
[RESULTS](releases/hemkop-operations-20261008/RESULTS.md),
[FINAL.json](releases/hemkop-operations-20261008/FINAL.json),
[ACTIVATION](releases/hemkop-operations-20261008/ACTIVATION.md).

Karhögstorgs exakta booleska tillägg rättat, ordinary replay med ursprungliga
observationer passerade. Brunnshögs gamla medlems/offentlig-källmotsägelse
bevarad; ett nytt komplett försök passerade utan att konfliktspärren ändrades.
Ytterligare TypeError i nullable erbjudandesortering rättad i källbyggaren.
Alla fem baser FRESH/laddade, /ready200 vid 15:17 UTC. Manifest bc39552c…;
2 232 råhashar verifierade. Samma Willys d53486fb… exakt en import, återleverans
gav already_active och beständigt kvitto 14:53:39 UTC. Ingen fullhämtning igen.

WebKit/personlig PASS; Chromium/publik först FAIL 500, sedan PASS utan appbyte.
Båda PASS-flödena omfattar omladdning, dubbelstart, receptbyte, omräkning,
tre revisions-GET och ägarisolering. Första felet: jobb
3218c89521084fc7a1c6b53b622c7276, app-request 9e96c548-6414-467b-ab7e-3d5e4fe6d779,
14:51:24 UTC internal_error. Exakt grundorsak okänd; påstå inte rättat av omkörningen.
En separat dd12-hjälparprob visar nullable-sorteringsfel för 26 produkter men
ingen bevisad koppling till detta HTTP 500. Eventuell konsumentapprelease kräver
separat omfattning; byt inte mat/prisdata eller aktivera 54cb för att maskera felet.
Råfel/testunderlag: skyddat D:\Projects\Smako\.local\hemkop-operations-20261008.

Alla gamla 216 revisioner/61 privata rader hashbevarade; nu 222/63 efter prov.
Server 13,32 GB, C:5,51 GB, D:664,22 GB ledigt. Ingen ny rensning i denna etapp.
Scheman inte pausade. Omedelbar demandkontroll not_due/0 anrop; äldre global
backoff 18:37:43 UTC kvar (första efterföljande tick18:45 UTC). Windows nästa
17:30 svensk tid vid kontrollen; manuell tidigare start är inte fler dygns driftbevis.
V2-index 13 incidenter, aktuella Hemköpsfall återhämtade. Äldre separata
Coop-fysiska schema-/Lidl-kvalificeringsincidenter öppna; de blockerar inte femkällorsbasen.
Ingen extern notifieringstjänst tillagd och inga skickade larm påstådda.
Sen avläsning 15:30:52 UTC: fortfarande /ready200/samma manifest. Windowskörning
15:30:01 UTC exit0, not_due/0 anrop; nästa registrerade start23:30 UTC. Ingen manuell
start av oss då; reläloggen anger inte startorsak, ingen flerdygnsdrift påstås.

# Tidigare kontroll 2026-10-08: Driftåterställning – konkreta Hemköp-blockerare

**Windows och serverutrymme är åtgärdade; prispublicering är inte återställd.**
Se [slutstatus](releases/drift-restoration-20261008/STATUS.md),
[FINAL.json](releases/drift-restoration-20261008/FINAL.json) och
[separata källstopp](releases/drift-restoration-20261008/BLOCKERS.md).

Uppgiften använder fe795e5b04f5, 625 filer matchar, övrig XML bevarad.
Verkligt S4U/session 0 parent/child-temp på D: PASS. Återleverans av nattens
bdc9-artifact gav exakt en promoverad import 72c524df46c34fe69af362158af38692.
Publiceringen misslyckades; paket kvar på D:, inget nytt last-success/kvitto.

Användarens förnyade säker-rensningsgodkännande användes för fem exakt
arkiverade testkataloger och 61 exakta reproducerbara byggcacheposter.
Fyra testdatabaser och alla aktiva data/images bevarade. Server 0→14,0 GB
som mest; 13,49 GB efter återhämtning. C: cirka 5,53 GB, D: 664,30 GB.
Ingen bred prune eller aktiv tempfilradering.

Ordinarie serveråterhämtning **avslutad** 12:37:43 UTC med exit 1; exec87815
är inte längre aktiv. Coops fullcrawl promoverad. Karhögstorg komplett men
rejected på två booleska hasPickingBaseStore-fält. Brunnshög ofullständig
på olika potentialPromotions för 101293703_ST. Råbevis och separata
stopporsaker bevarade; inga spärrar kringgångna. Separat förberedelse av
avgränsad schemafix efterfrågad, inget användarsvar vid denna notering.
Ingen källkod ändrad eller driftsatt.

Samma dd12-app/JS/flagga; /health200, /ready503, grocery/plan_store ok.
216 revisioner och 61 privata tillståndsrader exakt bevarade. Gammalt
manifest är fortsatt laddat med alla fem baser STALE. Menyproven blockerade.

Scheman inte pausade: Windows nästa 17:30 lokal tid; server var15min.
12:45 UTC demandkontroll not_due på **backoff**, inga prisanrop.
Global retry_at 18:37:43 UTC; möjlig cronåterhämtning20:45 lokal tid.
Ingen framtida automatisk framgång påstådd. Kontrollera verkliga jobb/lås
innan nya åtgärder. Ingen måltids-/sökaktivering eller Git-push.

# 2026-10-07 kväll: Endast driftåterställning – operatörsåtgärder återstår

Gren `ops/restore-price-flow-20261007`, ovanpå `72a936b`. Ingen ny apprelease
eller fortsatt prestandaetapp. Betan behåller dd12, kompletta recept på.
Ny faktisk kontroll 20:40 UTC: `/ready` 503, PlanStore
`SQLITE_IOERR_SHMSIZE`, serverns faktiska filsystem fortfarande 0 byte
tillgängligt. C: hade cirka 6,6 GB och D: cirka 688 GB vid etappens start.
Alla fem baser är STALE; aktiv prisartefakt och 2 236 råreferenser är
hashverifierade och ligger kvar i produktionens ordinarie rårot.

17:30-reläkörningen är avslutad men saknar slutkvitto och task_success.
Schemaläggarens slutkod 0 bevisar inte lyckad leverans. Uppgiften är
Ready/Enabled och använder fortsatt bdc9. Ingen paus eller insamling
har startats av oss i denna etapp. Nästa Windows-start 8 oktober 01:30;
serverns behovskontroll var 15:e minut och backup 02:47 svensk tid.

Operatören har tidigt fått exakt administratörskommando för
`scripts/activate_willys_storage_fix.ps1 -Apply`, commit `43a712a`.
Verktyget verifierar förväntad hel uppgifts-XML, paketmanifest och 625 filer,
bevarar konto/S4U/Limited/schema och respekterar båda lokala låsen. Endast
Actions Arguments/WorkingDirectory ändras; det startar ingen insamling.
Läsande förkontroll passerade. Ingen automatisk elevation eller ACL-ändring.

Nio inaktiva testdataobjekt under gamla `ops-verification` är arkiverade
direkt till skyddad D:-lagring. Arkivets 89 550 filer matchar originalens
SHA-256; full återställning med rätt filantal/storlek genomförd. Ytterligare
hashkontroll av återställda filer passerade för 39 532 filer inklusive alla
fyra databaser; resterande extra efterkontroll stoppades uttryckligen och
påstås inte genomförd. Inga hashfel observerade. Arkiv SHA-256
`21946e544ae4b8605c0d5f52aa32fad3ae21869052716c7c00207441a5f5e3f4`.
Ingen serverkopia är godkänd för ny radering. Exakt nioobjektslista har
lämnats till användaren för beslut; ingen radering före svar.
Exakt lista, arkiv-/återställningsbevis och nästa operatörssteg finns i
[aktuell driftstatus](releases/drift-restoration-20261007/STATUS.md) och
[arkivförslaget](releases/drift-restoration-20261007/ARCHIVE-PROPOSAL.md).
Målen saknar container-/öppna filreferenser; planer, konfigurationer,
produktionsrådata, köer och paket är undantagna. Kontrollera referenser och
innehåll igen efter ett eventuellt raderingsgodkännande. Gamla tillstånd,
paket och större råbevis finns utanför Git på D:. Ingen Git-push.

# 2026-10-07: Slutleverans – A blockerad, B kvalificerad i isolering

Arbetsgren `feature/willys-storage-search-20261007`. Ingen Git-push eller
aktivering av måltids-/prestandakandidaten. [Slutrapport](releases/willys-storage-search-20261007/RESULTS.md).

**A är inte återställd.** Full driftkontroll 15:05 UTC visade rätt dd12,
kompletta recept på, serverns faktiska datavolymer med 0 byte tillgängligt,
`/ready` 503 och `SQLITE_IOERR_SHMSIZE`. Alla fem obligatoriska baser var
över 48 timmar. Den separata reläkandidaten `fe795e5b04f5` är installerad,
men Windows nekade `Set-ScheduledTask`; uppgiften använder fortsatt bdc9.
Schema, konto, S4U/Limited och övriga inställningar är bevarade. Ordinarie
17:30-start observerades; det är ingen manuellt kontrollerad start.
Serverutrymme och administratörskörning av det redan avgränsade
`update_relay_task.ps1` behövs före fortsatt S4U-/driftverifiering.
Ingen kö eller tidigare data har raderats. Se tidsstämplad
[A-status](releases/willys-storage-search-20261007/A-STATUS.md).

**B är färdig och isolerat kvalificerad, inte aktiverad.** Runtime
`54cb2e8159a126de26fa11cb1d393dc275238fd3`, image
`sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3`.
ZIP SHA-256 `98446fac69395c8f7eded6c15f23f8194b5e26dffde1810e83cb5a9007338667`.
Verifierad imageexport SHA-256
`ec82580cc0a7c6d001bfda93dd0f2b8fc48938cda5d0ea5f57f7d93d9879ff19`.
Båda finns i `.local/willys-storage-search-20261007/package-54cb2e8159a1/`.
Senare commits gäller dokumentation/testverktyg; bygg inte om slutpaketet.

Tre kalla 5×-processer per sida: median 892,01→534,79 s (−40 %).
Tre varma nya 5×-beräkningar: 775,67→419,03 s (−46 %). Samma relevanta
620 recept och 12 781 veckoutvärderingar; samma begränsade sökbudget.
Huvudklick varmt 54,234 s Chromium/53,234 s WebKit; kallt 87,078 s når
fortfarande inte 60-sekundersmålet. Ingen global optimalitet hävdas.

37 fullständiga resultatpar matchar efter redovisad metadatanormalisering;
60 planresultat, 206 backendtester, 14 strikta webbläsarprov, fyra äldre
15/20-profiler och alla 24+6 receptkvalificeringar passerar. Individuell
receptkvalificering hade inget proteinmål. Import, invalidering, gemensamt
inköp, privat skafferi, ägarisolering, revisioner, omstart och flagga av
verifierade. Ursprungliga samtidighetsfel och telemetrivarningar bevaras;
SQLite-väntetiden rättades i testmiljön, inte i appimagen.
Alla tunga testsekvenser är avslutade. Se
[slutkontroll](releases/willys-storage-search-20261007/QUALIFICATION.json),
[mätgränser](releases/willys-storage-search-20261007/PERFORMANCE.md) och
[framtida app-only-anvisning](releases/willys-storage-search-20261007/ACTIVATION.md).

## Historiska delstatusar 7 oktober – ersatta av slutläget ovan

Uppdatering 14:35 UTC: basens tre varma 5×-nyberäkningar är klara,
775,67/775,73/771,76 s (median 775,67). Efterversionens motsvarande serie
pågår i `smako-search-after-scale5-warm-1`. Därefter kör den redan startade
sekvensen de fem profilparen och `container_followups.py` inklusive 30
kvalificeringar, invalidering, äldre lagring och imageexport. Kör inte en
andra tung sekvens parallellt. Slutkontroller finns förberedda som
`collect_followups.py`, `compare_all.py`, `validate_results.py`,
`final_gate.py` och `index_evidence.py` under samma lokala evidensrot.
14:11 UTC var servern fortsatt full och uppgiften fortsatt bdc9.

Uppdatering 13:32 UTC: tre kalla 5×-par klara. Hela processens median
892,01→534,79 s (cirka −40 %); varma 5×-nyberäkningar pågår därefter i
samma sekventiella matris. Runtime/image är fortfarande 54cb/8a537fc4d333.
Serverns faktiska appdatavolymer hade 0 byte ledigt 13:08 UTC; uppgiften
pekade fortsatt på bdc9. Se REPRODUCE.md för bevarade körkommandon.

Uppdatering 12:00 UTC: servern har fortfarande 0 byte tillgängligt och
Windows-uppgiften pekar fortsatt på bdc9. A är inte återställd. B:s
paketerade huvud-/webbläsar-/profilprov är utförda; längre sekventiell
1×/2×/5×-matris pågår via `.local/willys-storage-search-20261007/remaining_sequence.py`.
Den stoppar vid fel och kör aldrig parallella tunga prov. Slutlig runtime är
fortfarande `54cb2e8159a1`; senare commits gäller dokumentation och striktare
testverktyg. Se [testläget](releases/willys-storage-search-20261007/TESTS.md)
för bevarade SQLite-/testfel, korrigerad isolerad SQLite-väntetid och omkörningar.

Arbetsgren `feature/willys-storage-search-20261007`. Betan kör fortsatt rätt
dd12-image; ingen måltids-/prestandakod har aktiverats. Vid ny kontroll
7 oktober var serverns rotvolym åter full (0 byte tillgängligt), `/ready`
503 och planlagringen gav `SQLITE_IOERR_SHMSIZE`. Äldre 172 MB är historiskt.
[Aktuell A-rapport](releases/willys-storage-search-20261007/A-STATUS.md).

Lagringsfix `813eadda8e26`, separat ren reläkandidat ovanpå bdc9
`fe795e5b04f5a5ff973b71bb9bcdd28ca8668ce2`, installerad men ännu inte vald
av uppgiften. Den binder även temporärfiler till befintlig kommunarbetsyta
på D: och stoppar vid otillräcklig lokal/serverkapacitet. Windows nekade
`Set-ScheduledTask`; definitionen är verifierat oförändrad och fortsatt aktiv.
Användaren har fått ett avgränsat administratörsskript. S4U-prov och verklig
prisåterhämtning väntar på behörighet respektive serverutrymme. Köer, state,
rådata och tidigare paket bevaras. Inga nya prisanrop eller raderingar gjorda.

B utgår från fd2 och bevarar samtliga recept/fakta/import-/statusfiler.
Delprofil av exakt tidigare 176→880-korpus visade upprepad näringsprövning:
1,4 miljoner `input_evidence`-anrop i ett avbrutet 657-s-prov (inte ett
slutfört prestandaprov). Optimeringscommits `ada436763c8a` och
`54cb2e8159a126de26fa11cb1d393dc275238fd3` strömmar samma faktahash,
behåller ofta använda cacheposter inom samma gränser och delar
ingrediensunderlag efter separat validering av varje exakt recept.
Portionsberäkning, veckosökbudget och oberoende slutlig audit är oförändrade.

Paket `smako-server-54cb2e8159a1.zip`, SHA-256
`98446fac69395c8f7eded6c15f23f8194b5e26dffde1810e83cb5a9007338667`,
lokal image `sha256:8a537fc4d333d9fc17fd06916061ed481ba433951126688df51b6b4da19766f3`.
664 imagefiler hashkontrollerade. **Slutkvalificering pågår; ännu inte redo
för aktiveringsbeslut.** Första parade kalla huvudfallet: 98,94→90,07 s,
741,15 kr, full resultatekvivalens utom explicita mät-/byggmetadata och
ordning i medlemsmängden. Det är inte median eller klicktid. Råunderlag,
testloggar, isolerade profiler och pågående matris finns på D: under
`.local/willys-storage-search-20261007/`. Docker-data-VHDX ligger på D:.

# 2026-10-06: Statuskandidaten aktiverad; måltidsbibliotek färdig kandidat

Etapp A är genomförd med användarens uttryckliga app-only-godkännande:
beta.smako.nu kör dd12-image `c8362751b13a`, BUILD_ID
`status-reconnect-dd12cc80e98c`, kompletta recept på. Inga testdata eller
historisk klocka installerades. Samma mounts och aktuella data; alla tidigare
209 revisionsrader och 58 privata tillståndsrader har bevarade fingerprint.
Privat, integritetskontrollerad backup togs före bytet. Endast appen ersattes.
[Separat aktiveringsrapport](releases/status-activation-20261006/RESULTS.md).

Riktiga publika Chromium- och personliga WebKit-knappflöden passerade,
inklusive dubbelstart, omladdning/offline, byte, omräkning och revisions-GET.
Första WebKit-provet är bevarat som FAIL för statuslatens 16,12 s mot
testets 10 s-gräns, trots färdig meny utan sidfel. Servermetriken för samma
anrop är 159,367 ms; exakt fördröjningsorsak är fortsatt obelagd. Omkörning
är inte en appfix. Kontoinloggning är avstängd i faktisk drift; proven gäller gäster.

Etapp B är lokalt färdig på `feature/meal-library-20261006`, ovanpå eaf9dfd och dd12.
Låst implementation P2 `e2e5d248ee44`, slutlig runtime P3
`fd2cfda5490ac93295e6a2cef6b6b8408497f89e`, image
`sha256:b8541e165a2075c4c5657e1296c83e276f3aa8f59607292e32b653b60a7655fb`.
Senare lokala dokumentationscommits ändrar inte runtime. Den koden är inte
aktiverad. Receptformat, importerare, tre måltidstyper, gemensam veckokorg
och beständiga förberedelseartefakter är implementerade. 24 pilotrecept och
ett separat sexreceptspaket; ny data-only-import efter kodlåsning med
oförändrade runtimefiler. Två felaktiga versioner från det första
sexreceptsförsöket är återkallade, historiska GET bevaras.

Slutimagen har passerat strikta Chromium/WebKit-mobilflöden, gamla 15/20-
profiler, privat skafferi, ägarisolering, omstart och flagga av. 267 isolerade
historiska revisioner läses oförändrat. Hela P0–P3-matrisen med tre kalla
och tre varma nyberäkningar är färdig. Main 741,15 kr oförändrat;
nya fria enkla middagar 328,16→262,28 kr, kombinerat 495,44→418,17 kr.
De senare är olika receptval, inte billigare samma mat. Inga nya produktfakta.
Huvudklick utan omladdning 63,81/72,30 s: 60-sekundersmålet återstår; kall start är långsammare
än dd12, minnestoppen lägre. [Slutrapport](releases/meal-library-20261006/RESULTS.md).
Alla 30 slutkvalificeringar och 1×/2×/5×-skal-/invalideringsprov passerade.
5× huvudfall tog 919,89 s, topp 1,62 GiB: snabb storbibliotekssökning återstår.
Data-only-målet och återanvändning är verifierade; kandidaten är färdig för
separat aktiveringsbedömning, inte installerad. Fjorton strikta mobilprov; enkla
fem middagar för två tog 38,53 s via ordinarie knapp. Inga nya fakta/priser.

Beta är separat degraderad: planlagringen fungerar efter uttryckligt godkänd
arkivering av endast etappens nya byggmappar; `/health` 200 men `/ready` 503
för två för gamla Willys-underlag. Rätt dd12-image/JS och flagga på har
återverifierats. Senaste driftkontroll 20:36:31 UTC: bara 172 MB ledigt på rotvolymen.
Ingen ny insamling, ytterligare städning eller gränsändring har gjorts.
Ingen push, relä-, scheduler-, collector-, proxy- eller säkerhetsändring.

# 2026-10-06: Statusflöde och återanslutning – färdig lokal appkandidat

Gren `feature/status-reconnect-20261006`, slutlig paketerad runtime
**dd12cc80e98c79aa32c159223c8bc1ceeaaa7580**, ovanpå f5deaef/82de.
Senare commits för testverktyg och dokumentation ändrar inte runtime.
**REDO FÖR SEPARAT APP-AKTIVERINGSBESLUT.** Betan är oförändrad;
ingen aktivering, push, insamling, relä-, schema-, proxy- eller säkerhetsändring.
[Resultat och beslutsmatris](releases/status-reconnect-20261006/RESULTS.md),
[testbevis](releases/status-reconnect-20261006/TESTS.md),
[bevarade fel och osäkerheter](releases/status-reconnect-20261006/HISTORY.json),
[senaste app-only-anvisning](releases/status-reconnect-20261006/ACTIVATION.md).

Publikt och personligt flöde delar en sekventiell livscykelbunden statusläsare.
Egna avbrott stoppar klienten, aldrig serverjobbet. Sena svar spärras även
efter JSON-läsning. Begränsad återhämtning och manuell statusåterupptagning
behåller samma jobb; förlorat accepterat startsvar återfinns genom ägarbunden
GET med samma begäransreferens. Inget nytt beständigt bakgrundsjobbsystem.
Ofärdiga processminnesjobb överlever inte backendomstart; sparade revisioner gör det.

Slutimagen passerade 11 riktiga Chromium/WebKit-mobilresor, två separata
treägarkörningar (ostörd och kontrollerat statusavbrott), verklig gästcookieutgång,
cookieborttagning och omstart under ofärdigt jobb. En instrumenterad tung
beräkning per ursprungligt återhämtningsförsök, samma jobb och ägarisolering.
10 transport-, 41 backend- och 8 syntetiska frontendprov passerade.
Fullt resultat matchar 82de i 15 jämförelser, inklusive byte/omräkning;
741,15 / 787,56 / 910,39 kr är oförändrad historisk replay.
11 äldre HTTP-revisioner och 22 revisioner i separat lagringskopia läses
oförändrat. Flagga-av på samma image och äldre menyflöde fungerar.
Äldre binäråtergång och signerad kontosessionsexpiry är inte kvalificerade.

Ett nytt strikt WebKit-fel gav en reproducerad lucka före pagehide; beforeunload
stoppar nu pollningen tidigare. Exakt historisk WebKit-orsak och det separata
historiska socketfelet är fortfarande obelagda. Råa FAIL har bevarats.
Ostört huvudklick 67,81 s: 60-sekundersmålet återstår. Två CPU, 3 GiB och
en tung admissionplats är oförändrade. Recept, fakta, sökbudget, pris,
näring, variation och audit ändrades inte i denna etapp.

Paket `smako-server-dd12cc80e98c.zip`, SHA-256
`bc1ec3f2b03c228348bb63bcf3bba0f84f300b56aa375cdbe877f0dc8838484c`.
Verifierad image
`sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7`.
Använd just den nya app-only-anvisningen vid ett separat framtida beslut;
återställ aldrig äldre databas över senare användararbete.

# 2026-10-06: Hela förpackningsköp och uttrycklig veckovariation – lokal kandidat

Gren `feature/package-variation-20261005`, slutlig runtime
**82de80e1ae898e2ab005c16c8d95e6670898be93**. Källbasen är den senaste
sammanhängande receptkandidaten inklusive senare relevanta ändringar. Ingen
produktionsaktivering, push, relay-, insamlings-, kommun- eller policyändring.
[Resultat och kvarstående begränsningar](releases/package-variation-20261005/RESULTS.md),
[fulla menyer och inköp](releases/package-variation-20261005/MENU.md),
[käll- och kandidatspår](releases/package-variation-20261005/RESEARCH.md),
[testbevis](releases/package-variation-20261005/TESTS.md),
[separat app-only-anvisning](releases/package-variation-20261005/ACTIVATION.md).

Fryst historisk replay: samma fem recept och mängder **747,77 → 741,15 kr** i
hela betalningen efter exakt identifierad 1 kg-ärtförpackning; ny kod utan nya
fakta gav ingen sänkning. Använd mängd 494,93 → 495,13 kr. Paprikapulver 37 g
finns till 25,50 kr i samma snapshot men saknar belagd variantbunden mildhet
och har inte valts. Fritt R2: fyra indiska/en mexikansk. Uttryckligt minst tre
kök och proteintak: 787,56 kr; ett av vart och ett av fem kök: 910,39 kr.
Olika rätter jämförs inte som besparing för samma mat.

Tre kalla R2-processer median 80,92 s, tre varma nyberäkningar 54,49 s.
Chromium/WebKit huvudklick 70,72/61,56 s: 60-sekundersmålet återstår.
WebKit rapporterade åter ett status-`fetch`-fel precis vid avsiktlig omladdning;
rått underkänt prov bevaras. Tre samtidiga klienter klarade kö, dubbelstart,
ägarisolering och 3 GiB-gräns efter ett separat avbrutet första klientförsök.
Elva äldre planrevisioner lästes med identiska hashvärden av nya imagen från en
kopia av tidigare testlagring. Blandning av olika förpackningsstorlekar i samma
ingrediensköp är ännu inte implementerad. Den förberedda appimagen är **inte**
installerad; se aktiveringsanvisningen före något separat framtida beslut.

# 2026-10-05: Receptens användbarhet och beräkningskostnad – verifierad kandidat

Gren `feature/recipe-usability-20261005`, runtime
**2816d50e4a14dd118015a4c047f2346435b981ef**. Efterföljande b58e2c1 förbättrar
endast testloggning. Ingen produktionsaktivering eller push.
[Slutrapport](releases/recipe-usability-20261005/RESULTS.md),
[kvarstående källunderlag](releases/recipe-usability-20261005/RESEARCH.md),
[separat aktivering och återgång](releases/recipe-usability-20261005/ACTIVATION.md).

Alla 48 paketversioner prövade i båda köplägena på samma frysta underlag:
**11 → 27 uppskattat, 7 → 19 exakt; överlapp 19, union 27 efter ändringen**.
Paketets användbara grundrätter ökar 6 → 14 respektive 4 → 10. Över hela
biblioteket är ökningen 52 → 57 respektive 26 → 32. Alla äldre godkännanden
består: 96/104 uppskattat och 44/104 exakt, identiska versionsmängder.
Källbunden mildhet för Santa Maria 200 g, Garant Risoni 500 g och SLV 588 för
äpple införs i befintliga faktavägar. Mängder och receptversioner är oförändrade.
C är berikad historisk replay; källornas nya hämtningstider har inte backdaterats.

Samtliga 16 nytillkomna versioner har faktiskt prissatts i fri veckosökning.
Huvudkorgen minskar **768,04 → 747,77 kr**, använd mängd 566,87 → 494,93 kr.
IN03-base och IN04-kikartor väljs fritt. Bred Varierad minskar 591,65 → 590,08 kr;
nio andra lyckade profiler behåller inköpstotalen. Indisk vegetarisk femmiddagsprofil
stannar fortfarande i begränsad variationssökning. Ingen global omöjlighet påstås.

Tre kalla och tre varma nya beräkningar per A/B/C, samma 2 CPU/3 GiB:
median kall **92,17 → 79,25 s**, varm **66,68 → 54,80 s**. Med enbart ny kod
och gamla fakta (B) är medianerna 74,55/47,00 s. Parat färskprocessprov på mobil:
Chromium 82,14 → 70,20 s, WebKit 80,88 → 68,94 s klick till renderat resultat.
**60-sekundersmålet är inte uppnått.** Samtliga råtider och sidoprofilernas
regressioner redovisas, inklusive bred Varierad 117,89 → 120,47 s i HTTP-provet.

Begränsad återanvändning av exakta prisvektorer, rangordningsmönster, ren text och
negativa uppslag minskar dubbelarbete utan lägre budget eller mindre receptpool.
Mutable kandidater använder exakt skalär prövning; 40 g-regressionen i 522 är rättad.
Mellanversion 0da nådde 3 GiB efter åtta HTTP-profiler. 2816 frigör avslutade
felramars lokala variabler och oåtkomliga sökcykler inför nästa antagna jobb.
Slutmatrisens alla tolv profiler klarade samma process utan OOM. Slutaudit kvarstår.

**1 076 regressionstester PASS**, Ruff och riktad compileall PASS. Chromium och
WebKit mobil/desktop genomförde ordinarie knappflöden, omladdning, byte, explicit
omräkning och återläsning efter faktisk omstart. 28 explicita versions-/köplägesprov
(16 uppskattat/12 exakt) täcker alla nykvalificerade versioner, 58 revisioner
bevarade efter omstart. Tre samtidiga klienter, ägarisolering och dubbelstart PASS.
51 tidigare testrevisioner bevarade med flagga på/av. Isolerad slutbackup:
75 planer/141 revisioner, SQLite-integritet PASS. Inga produktionsdata återställda.

**Testanmärkning:** första WebKit-mobilförsöket fick ett statusanropsfel med
"access control checks" efter passerade funktioner. Full omkörning och parat
färskprocessprov passerade. Orsaken är inte fastställd eller påstått rättad;
underkänd rapport bevaras och ska beaktas vid framtida aktiveringskontroll.

Paket `.local/releases/recipe-usability-memory-20261005/smako-server-2816d50e4a14.zip`
(2 832 452 byte), SHA-256
`c74ad647643e949085f048644492432f6226c3d01a2bb90d6ae088b798f013b4`.
Image `sha256:362e0eabf703d515b96ffad1412bd80d0c97a42927738fa75e1a033db240415d`.
650 installerade runtimefiler manifestverifierade; pip check och offline browser PASS.
Föreskrivet framtida BUILD_ID `recipe-usability-2816d50e4a14`.
Aktivering kräver nytt beslut. Återgång: flagga av i samma nya image, bevara alla
revisioner; återställ aldrig äldre databas eller äldre binär över nyare planer.

Beta är fortsatt ready på **complete-recipes-17a9c1330dcc**, flagga true;
app, scheduler, Linux-relä och proxy har oförändrade container-/image-ID:n och
starttider. Windows-relä, insamling och scheman är orörda. Egna testcontainrar är
avslutade; isolerad backup och bevis bevaras i `.local/recipe-usability-20261005`
och `/var/tmp/smako-recipe-usability-20261005`. Manifestet binder rapporternas
råbevis till hashvärden. Privata sessionsuppgifter/databaser ligger utanför Git.

# 2026-10-05: Innehållspaket 24 + 24 integrerat, ej aktiverat

Gren `feature/recipe-content-pack-20261005`, runtime
**dbd89abbed0a0e3b9d8955badabb17615d6c8d09**, BUILD_ID `content-dbd89abbed0a`.
[Slutresultat, kvalificering och mätningar](releases/recipe-content-20261005/RESULTS.md),
[separat app-only-aktivering och funktionsåtergång](releases/recipe-content-20261005/ACTIVATION.md).
Ingen produktionsaktivering, Git-push, insamling eller driftpolicyändring.

Paketets färdiga innehåll infördes prioritet 1 före 2 utan ny receptgenerering.
24 familjeförslag jämfördes mot alla 104 aktuella versioner: 14 nya grundrätter,
10 befintliga familjer med motiverade variationer. 48 nya 2.0.0-versioner;
totalt 62 grundrätter/152 versioner. Alla äldre recept bevarade och hashoförändrade.
Komponentmängder, former, varianternas egna steg och processvatten bevaras.
Ny metod `smako-authored-input-v2` redovisar uppskattad näring och okända
beredningsförluster utan att kräva att källans avhällda kokvatten serveras.

På samma autentiska frysta pris-/faktaunderlag kvalificeras 11/48 nya versioner
med uppskattade köp och 7/48 med exakta köp. Uppskattad full näringsprofil:
96 → 107 kvalificerade versioner, 47 → 52 distinkta familjer. De 37 datastoppen
beror bland annat på milt paprikapulvers näring, chiliflakes, avrunnen majs,
pita/småpasta och ätbar mängd för ägg/tonfisk. Inga fakta eller mängder uppfanns.
Tidigare preliminära 23 kvalificerade/698,77 kr är underkända som slutacceptans
efter striktare kontroll mot innehållspaketets angivna ingredienser.

Huvudfallet bevarar exakt recept, produkter, mängder, näring, audit och rester:
768,04 kr inköp/566,87 kr använd mängd. Billigast 534,40 kr och Varierad 808,76 kr
är också oförändrade före/efter. Utbyggnaden ger längre söktid, ingen dold besparing:
huvudfall kall process 82,49 → 93,11 s, varm nyberäkning 58,00 → 64,93 s;
Billigast kall process 66,59 → 109,77 s (inklusive tidigare pools omvalidering),
Varierad 135,02 → 149,84 s. Samma 2 CPU/3 GiB, oförändrad sökbudget, en observation
per sidofall. 60-sekundersmålet är inte uppnått. Ingen färdigplancache används i måtten.

2 258 backendtester, deterministisk import, Ruff och compileall PASS.
48 versioner renderade i båda webbläsarna på mobil/desktop. Riktigt publikt
Chromium-flöde väljer nya IT04-base vid byte, omräknar och läser revisionerna
1–3 efter faktisk omstart; personlig WebKit-mobil gör motsvarande femköksflöde.
Ägarisolering/dubbelstart passerar. Angivet 500 g potatisskafferi används med
300 g utan automatisk restbokföring. Inga fysiska iPhone- eller provlagningspåståenden.

Serverpaket `.local/releases/recipe-content-final-20261005/smako-server-dbd89abbed0a.zip`,
SHA-256 `e6fe6c4698af816d1b1c8f8f36e23a7be770008237672927557ec38a27ebef4c`,
image `sha256:a7b0440c6efb19cc2f4b25ae12689656f19f881a2446d7e4f2249d00d0950727`.
Alla 649 installerade runtimefiler verifierade mot paketet. Produktion är fortsatt
ready på `complete-recipes-17a9c1330dcc`, flagga true, oförändrad image/starttid.
**Efter sparade 2.0.0-planer: funktionsåtergång med flagga av i samma nya image,
inte äldre binär eller återställd databas.**

Fulla lokala bevis `.local/recipe-content-20261005`, serverns isolerade bevis
`/var/tmp/smako-content-20261005`. Testcontainer `smako-content-isolated` stoppad,
eget tillstånd och alla revisioner bevarade med konsistent slutbackup. Frysta
indata från tidigare prestandaarbete har inte ändrats eller kopierats till produktion.

# 2026-10-04: Femköksplanering – testad prestandakandidat, ej aktiverad

På `perf/five-cuisine-planning`. Runtime **b89fadb96c4edc4576cb4daae6c5d80e553ad8ca**,
BUILD_ID `five-cuisine-b89fadb96c4e`. [Resultat och samtliga prov](releases/five-cuisine-performance-20261004/RESULTS.md),
[app-only-aktivering/återgång](releases/five-cuisine-performance-20261004/ACTIVATION.md).
Ingen Git-push eller produktionsaktivering. Det äldre godkännandet för 17a9c13
är inte ett beslut för denna kandidat. Produktion är fortsatt ready på 17a9c13,
flagga true, samma container/image; autentisk ursprungsrevision hashoförändrad.

Exakt sparad femköksbegäran återfanns: fem middagar × fyra, Balanserad,
10–15 ingredienser, 30 g protein, inget tidstak, fem tillåtna kök, butikstak tre,
uppskattade köp och separat näringsmedgivande. Fullt autentiskt pris-/faktaunderlag
frystes isolerat. Reproducerad meny, mängder, produkter, näring, audit och
768,04 kr är oförändrade. Historiska belopp är inga nya produktionspriser.

På samma 2 CPU/3 GiB och identiska beroenden: median kall ny process
**204,8 → 83,6 s**, varm **ny beräkning 179,2 → 58,9 s**, tre prov vardera.
Tre samtidiga användares sista resultat **582,7 → 194,1 s**, kö separat.
Brett Varierad **345,2 → 100,9 s**, identisk hel plan. **60-sekundersmålet
från klick är inte nått**: slutliga Chromium/WebKit-knappar gav 72,3/75,0 s.
Nästa kostnader är förpackningsberäkning, audit och kall fakta/indexberedning.

Begäranslokal begränsad återanvändning av kvalificerade kandidater, normaliserade
recept och näring; befintlig korgmotor undviker butiker som saknar varje kvalificerad
vara. Inga mindre sökbudgetar, receptmängder, alternativa prismotorer eller ändrade
insamlingsinställningar. Svenska näringsdecimaler och naturligare metodvisning
ändrar inte sparat receptinnehåll. Ett befintligt bytesfel reproducerades i 17a
och rättades genom tidigare kontroll mot de redan låsta rätterna.

2 226 backendtester och 1 664 tester för oförändrad grocery_data-kod PASS.
Alla 104 varianter renderade i Chromium/WebKit mobil/desktop. Riktiga publika
Chromium- och personliga WebKit-mobilflöden PASS: generation, omladdning, byte,
omräkning och revision 1–3 efter omstart. 19 tidigare testrevisioner oförändrade,
29 vid slutkontroll. Ingen fysisk iPhone eller fysisk provlagning påstås.

Paket `.local/releases/five-cuisine-final-20261004/smako-server-b89fadb96c4e.zip`,
SHA-256 `eafba3aa7b4ab59d8fb92e258c995792caff9b9a3eb41838c3481b47142f982b`.
Image `sha256:80dd265779182eb750453e3b12a2249e71a9ed845f62c6e9c3c5f1a3a86ee4d1`;
645 runtimefiler, pip check och offline-Chromium PASS.
Fulla privata bevis och testdata ligger i `.local/five-cuisine-20261004` och
`/var/tmp/smako-five-cuisine-20261004`. Testcontainer `smako-five-cuisine-isolated`
är stoppad efter slutförda prov; data och revisioner är bevarade. Den använder
enbart dessa isolerade data. Kopiera aldrig replayklockan/databaserna
till produktion. Tidigare UI-arbetskopia i `D:/Projects/Smako-worktrees/five-cuisine-presentation`
är bevarad; dess integrerade ändringar finns redan i root-branchens commits.

# 2026-10-03: Nya receptlagret aktiverat på beta.smako.nu

Uttryckligen godkänd app-only-aktivering är genomförd. Slutkontroll
**2026-10-03 15:38:23 UTC (17:38 svensk tid)**: beta.smako.nu är ready,
BUILD_ID **`complete-recipes-17a9c1330dcc`**, featureflagga **true**.
Aktiv runtime `17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`, image
`sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`.
Ingen Git-push. Ingen funktionsutveckling under aktiveringen.

[Full driftrapport](releases/complete-recipes-production-20261003/RESULTS.md),
[sanerade aktiveringsbevis](releases/complete-recipes-production-20261003/ACTIVATION-RESULT.json),
[faktisk produktionsmeny och inköp](releases/complete-recipes-production-20261003/LIVE-MENU.json).

På vanliga betasidan och `/personal`: **Receptstil → Välj receptläge →
Genomarbetade middagar**. Där finns matkök, ingrediensintervall, tid och
proteinmål. Befintliga vardagsrecept är kvar. Uppskattade köp och medgivande
till uppskattad näring är fortsatt separata val; formulärberoendet verifierat.

Före bytet körde produktion fortfarande 74c9077; alla 419 runtimefiler matchade
dess manifest. Kandidatpaketets fulla SHA och 651 filer verifierades lokalt
samt på servern. Installerad kandidatimage och 644 runtimefiler kontrollerades.
Befintlig Compose-wrapper `/opt/smako/compose` har fått beständig override sist:
`/opt/smako/overrides/complete-recipes-17a9c1330dcc.yaml`.
Exakt konfigjämförelse tillåter endast appens image, BUILD_ID och flagga.
`current`-länk, basfiler, scheduler, proxy, collector, migrate, backup-tjänst,
Windows-relä, insamling, scheman, policy och kommunurval är oförändrade.

Gemensamt driftlås, vilande app före omstart samt konsekventa online-backuper
före båda stegen. Privata backup-/konfig-/tillståndsbevis finns under
`/opt/smako/evidence/complete-recipes-20261003`:
`backups-off/20261003T150917Z` och `backups-on/20261003T152044Z`.
Alla **195 ursprungliga planrevisioner** och **52 ursprungliga personliga
tillstånd** är bevarade. Slutkontroll: **207 revisioner**, alla läsbara med
PlanStore och SQLite quick_check ok. Inga äldre databaser återställdes.

Flagga-av-prov: äldre publikt 101,781 s, personlig 15/20-profil 283,296 s,
401,35 kr och oförändrade 40/30/20-proteinkrav. Därefter beständig aktivering.
På faktisk HTTPS-beta passerade Chromium mobil/publikt (101,797 s), WebKit
mobil/publikt (92,610 s), WebKit desktop/personligt (92,797 s) samt ett nytt
äldre publikt desktopprov (102,688 s). De nya proven gav fem middagar för två,
grekiskt/mexikanskt, 10–15 ingredienser, högst två butiker, 40 min och 40 g,
beräknat inköp cirka 738,17 kr. Omladdning under generering, byte till annan
grundrätt, omräkning, revision 1–3, inköpslista, kvalitetsmärkning, DOM/layout
och ägarisolering kontrollerades. Äldre testägda planer/val återlästes efter
flaggbytet. Ingen fysisk iPhone och ingen syntetisk smakfeedback.

WebKit/personligt fick först en automatisk klick-timeout efter lyckat byte.
Samma ägares revision 2 öppnades igen via Min plan; den vanliga synliga och
aktiverade knappen räknade om på 13,281 s utan force-klick eller appändring.
Alla tre revisioner stämde efteråt. Både första verktygsutfall och fortsättning
är bevarade. Inget kvarstående konkret app-/datakompatibilitetsfel konstaterat.

Riktig klocka och aktuellt publicerat underlag användes: universe
`price-universe:a2eb6ab5ffec325392ad98c69e6483a3b901312359c5c659673ea7da5fadd0c6`,
byggt 2026-10-03 11:31:32 UTC. Inga replaypriser/testdatabaser kopierades till
produktion. Köp- och näringsuppskattningar är märkta; färskhetsgränser 36/48 h.
Kandidatens källluckor kvarstår enligt rapporterna nedan.

Återgång vid framtida fel: samma nya image, endast flagga av i den beständiga
overriden, exakt konfigjämförelse och enbart appåterskapning efter jobbslut.
Bevara senaste data och revisioner. Följ [nya receptlagrets aktiveringsordning](releases/complete-recipes-20261002/ACTIVATION.md),
inte den historiska Lund-/reläreleasens byte av current eller globala versioner.

# 2026-10-03: Nästa receptlager – testad kandidat levererad lokalt

Arbetet är slutfört på `feature/complete-recipe-layer`, från faktiska `402a5c9`
ovanpå publika `74c9077`. Ingen produktionsaktivering eller Git-push.
Runtime är låst till **`17a9c1330dcc72ff9750a3fa680fa6982f7ed99b`**.
Efterföljande commits ändrar dokumentation och acceptansskript, inte runtime.

[Slutredovisning](releases/complete-recipes-20261002/RESULTS.md),
[alla sju menyer, produkter och inköp](releases/complete-recipes-20261002/MENUS.md),
[kontrollerad aktivering och beständig flaggåtergång](releases/complete-recipes-20261002/ACTIVATION.md).

Paket `.local/releases/complete-recipes-20261002/smako-server-17a9c1330dcc.zip`,
2 739 005 byte, SHA-256
`d3327b9137d4310707118b5272bc826ed0403ebd6d0c0ab935bb1196efee060a`.
Image `sha256:99bf3bfcb4f395ec1a06df23649e0241903d52bb5bba40ca4336abbd2bbecc35`:
645 runtimefiler matchar; pip check och offline-Chromium som appanvändare PASS.
Featureflaggan är av som standard. Planrevisioner ska bevaras även vid återgång.

Både publikt och personligt flöde har matkök, ingrediensantal, tid, kost,
valfritt proteinmål och tillåtna variationer. Valen följer jobb, generering,
ordinarie pris-/korgmotor, sparning, receptbyte och uttrycklig omräkning.
Bibliotek 1.4.0 har **48 distinkta grundrätter och 56 variationer**.
Samtliga 104 är prövade på slutimagen: **94 kvalificerade versioner, 47/48
fungerande grundrätter, 43/48 original**. Alla sju fria femmiddagsmenyer PASS.
De tio verkliga källstoppen gäller kapris, kidneybönors mängdbasis och mjölkens
näringsbasis. Piccata saknar fungerande variant i detta underlag. Två produkter
med motstridiga energipar spärras; normal produktkvalificering hittar annan
färs och källstyrkt färdigt matbröd i 16 versioner utan ändrade receptmängder.
Ingen fysisk provlagning eller fysisk iPhone-testning har utförts.

Full offline-regression på oförändrad slutruntime: **3 887 PASS**, 0 fel eller
överhoppade, 2 042,099 s, inga spärrade nät-/äldre källåtkomster. 252 riktade
integrationsprov plus 6 slutliga HTTP-runner-kontrakt PASS. Ruff för samtliga
ändrade Python-filer, compileall och pip check PASS.
[TESTS.json](releases/complete-recipes-20261002/TESTS.json) bevarar även äldre körningar.

Ren slutmätning med identiska frysta underlag/beroenden och 2 CPU/3 GiB:

- Äldre publikt flöde 161,047 s kallt mot baseline 328,424 s (**−50,96 %**),
  2,264 s varmt. Recept, ingredienser och hela korgen identiska: 168,55 kr.
- Komplett grekisk/mexikansk 5×2, 10–15, 40 min/40 g, Billigast: 105,721 s
  kallt / 95,976 s varmt, samma korg 738,17 kr.
- Brett Varierad HTTP-prov: 359,675 s. Sex minuters väntan kvarstår som
  prestandabegränsning; ingen global optimalitet påstås.

Alla fem slutliga HTTP-fall PASS: gamla publika anrop, komplett 15/20-profil,
Varierad, exakt2→uppskattat2→uppskattat3 (796,15→682,23→665,62 kr) och tre
samtidiga användare. Tre klienter fick separata planer efter 24,66/48,29/70,82 s,
högst samplat 2,073 GiB. Befintlig kö med en aktiv beräkning användes.
Dubbelstart, ägarisolering och återläsning verifierades.
[HTTP-bevis](releases/complete-recipes-20261002/HTTP-ACCEPTANCE.json).

Slutliga Chromium mobil/personligt och WebKit desktop/publikt PASS:
generering 95,328 respektive 86,593 s, omladdning under jobb, receptbyte,
omräkning, versioner/redskap, DOM/layout och sparade revisioner. Kontrollerad
omstart bevarade alla 34 testrevisioner exakt, inklusive alla 28 äldre.
Två feedbackrader matchar sina sparade receptversioner vid skrivskyddad
DB-verifiering. Tidigare fyra browserfall täcker båda motorerna på mobil och
desktop, tillfälligt nätavbrott och flagga-av-omstart, med egna versionsbindningar.
[UI-bevis](releases/complete-recipes-20261002/UI-ACCEPTANCE.json),
[omstart](releases/complete-recipes-20261002/FINAL-PERSISTENCE.json).

Isolerat test kör på **http://127.0.0.1:18122** via befintlig SSH-tunnel,
BUILD_ID `recipe-candidate-17a9c133-0476bf36`, featureflagga på. Det använder
frysta historiska priser från 2026-10-02, inte löften om dagens inköp.
Inga acceptansjobb återstår på resursen. Fjärrrot
`/var/tmp/smako-complete-recipes-20261002`, endast syntetisk privat teststate.
Replayklocka/state/testlauncher får aldrig användas som produktionskonfiguration.

Produktion kontrollerad skrivskyddat 2026-10-03 10:12:15 UTC: HTTP200/ready,
fortfarande build `74c9077001b3084317f36630fd38ce48e4663473`. Relä, scheduler,
insamling, femkällorspolicy, kommunomfattning och 36/48-timmarsgränser orörda.
[Oberoende paket- och driftgränskontroll](releases/complete-recipes-20261002/PACKAGE-BOUNDARIES.md).
Råfiler och privata/syntetiska testplaner ligger utanför Git i `.local` och
befintliga agentworktrees. Återstående begränsningar är dokumenterade källluckor,
uppskattad näring/tillagningstid, utebliven fysisk provlagning och söktiderna.

# 2026-10-02: Uppföljning – korrekta fältfel och fungerande lång generering

Appen kör nu Git `74c9077001b3084317f36630fd38ce48e4663473`, image
`sha256:80e8ba59c9b04c8bff668062da2bf1937eae236881472449e2a0180f42387180`.
Det ersätter appversionen i följande historiknotering. Scheduler/källjobb
är fortfarande `08c1374`. [Full rapport och bevis](releases/public-menu-followup-20261002/RESULTS.md).

Två fel är reproducerade och rättade: postnummer utanför artefaktens
aktiverade täckning gav missvisande 503/prisuppdatering och avstängd knapp;
WebKit bröt lång generering efter cirka en minut. Postnummerfel ger nu
422 på rätt fält, dataproblem har egna koder och vanlig 503 beskrivs som
tjänstefel. Publika knappen använder sessionsbundna, begränsade planjobb
med korta statusanrop runt samma planner och samma sparning. Ingen
policy, optimeringsgräns eller medgivande ändrat. Oavslutade transportjobb
löper ut vid appomstart; färdiga planer ligger kvar i PlanStore.

Fem publika knapp-prov PASS: WebKit mobil Balanserad (kall 338,359 s)
och Billigast; Chromium ren session samt båda mobilvalen. Fem middagar × två,
max tre inköpsställen, exact/mixed, verkliga medlems-ID:n, fullständiga recept,
inköpslista, kostnad, kvalitet och identisk återläsning verifierade.
Balanserad 168,55 kr, Billigast 125,10 kr. 308 HTTP-anrop korrelerade med
backend; frontendhashar matchar. Fyra separata 15/20-regressioner i samma
isolerade image PASS, 440,72 kr. Ingen fysisk iPhone har provats.

App-only-byte under driftlås cirka 11:15 CEST. Alla 188 tidigare revisioner
oförändrade, 193 efter proven. Prismanifest, proxy, scheduler och miljö
(utom appens BUILD_ID) bevarade. Skyddad backup/återgång under
`/opt/smako/evidence/public-menu-followup-20261002`. Testtjänster stoppade,
bevis bevarade. Ingen Git-push, städning eller Malmö-aktivering.

Användarens Fel-ID från 10:19 är matchat till 503/1,658 ms i gamla builden,
men den historiska body:n och det aktuella postnumret är inte bekräftade.
Det enskilda försöket tillskrivs därför inte säkert postnummerfelet.
Kalla menyberäkningar tar fortfarande cirka fem–sex minuter.

# 2026-10-02: Publik veckomeny – app-hotfix efter aktiveringen

Se [felsökning, request-ID:n och offentlig knappacceptans](releases/public-menu-20261002/RESULTS.md).
Webbappen kör nu Git `14cc716ae54e2bb09ceaed5c4e3c2159e3a9c97d`, image
`sha256:7dcc2c5c9b35a0f0ab68e1e1b180eada790c3f0a045d8f6a63c883ee7461ebef`.
Scheduler/källjobb ligger avsiktligt kvar på nedanstående 08c1374-release.
Detta var ett app-only-byte under befintligt driftlås, inte en ny Lund-aktivering.
Relä, scheman, femkällorspolicy, autentisering, prismanifest och alla 179 tidigare
planrevisioner bevarades. Återgångsunderlag och plandatabackup ligger skyddade under
`/opt/smako/evidence/public-menu-20261002`; återgång återställer enbart appkod.

Grundfelet var att publika femmiddagsformulärets MealPlanService skapade en
liveprovider innan den förberedda lokala PriceUniverse-vägen valdes. Därmed gav
normal drift utan OWN_GROCERY_BASE_URL ett missvisande 422. PersonalPlanner-provet
15/20 använde en annan kodväg. Följdfel i exakt medlemsprojektion, frivillig
obegränsad butiksjämförelse och kampanjsökningens cache/nested-gränser rättades
med reproducerande regressioner. Felpresentationen skiljer nu fältfel,
dataspärr, timeout och serverfel och visar Fel-ID med bibehållna val.

Publika mobilprov för Balanserad och Billigast med 22350, 5 × 2, tre inköpsställen,
exact, mixed och sex faktiskt tillgängliga medlemsprogram har passerat via knappen:
168,55 respektive 125,10 kr, verifierad korg, fullständiga recept och identisk
sparning/GET. Ren desktopsession utan medlemskap passerar också: 168,55 kr,
313,984 s, identisk sparning/GET. Fyra separata 15/20-profiler passerar med
440,72 kr; alla sju anrop matchas mot backendlogg och nya build-ID:t.
Kall femmiddagsberäkning tar
fortfarande flera minuter. Ingen fysisk iPhone har provats. Ingen Git-push.

# 2026-10-02: Lund 1281 aktiverat i normal drift

**Aktiveringen är genomförd och båda schemana är återupptagna.** Läs
[aktuellt aktiveringsprotokoll](releases/lund-20260929/ACTIVATION-LIVE-20261001.md),
[dess sanerade bevis](releases/lund-20260929/ACTIVATION-LIVE-EVIDENCE.json) och
[drift-/återgångsordningen](releases/lund-20260929/ACTIVATION.md).
Äldre statusnoteringar nedanför är bevarad historik, inte aktuella blockerare.

Fem godkännanden är givna och tillämpade: femkällorspolicy, slutlig server,
bdc9-reläbyte, Windows 01:30/09:30/17:30 och serverns behovskontroll var 15:e
minut. Inhämta inte dessa igen för samma omfattning. Backup är fortsatt 02:47;
35h behov, 36h varning och 48h stopp är oförändrade. Ingen säkerhetspolicy ändrad.

Serverruntime `08c137475d9ca96a6ef7673245a639c8c5c9e922`, bild `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7`.
Alla fem Compose-jobb använder bilden. Windows använder oförändrat
`D:\smako-local-relay\releases\bdc9f7df4170`, separat kommunarbetsyta och
scheduler/receiver som transportmål. Återläst befintlig uppgift: Ready,
ossia/S4U/Limited, tre lokala tider, nästa 2 oktober 01:30. Övriga XML-fält/ACL
är bevarade. Servern kör faktisk `cron -f`, nästa kontroll vid återupptagandet
00:15. Framtida schemakörningar är ännu inte verifierade.

En autentisk Willys-leverans, en import, atomisk publicering, faktisk reload
och beständigt kvitto passerar. Återleverans `already_active`; både relä och
server `not_due` med noll prisanrop och oförändrade observationer. Serving
`57ca714e…`, 44 077 råproduktposter, samtliga 2 232 råfiler hashverifierade.
Fyra 15/20-profiler: 440,72 kr, två butiker, checkout PASS, 40/30/20 uppfyllt.
Näring är separat VERIFIED/ESTIMATED. Cirka-vikt/lösvikt/flerköp/villkorat
kampanjval och spärrar passerar. **Uttrycklig omräkning PASS**, revision 1→2;
nio verifieringsrevisioner identiska efter faktisk appomstart, fel ägare 403.
Alla 170 ursprungliga planrevisioner är oförändrade; totalt 179 vid kontrollen.

Backuper och gamla köer är bevarade. Inga gamla Primat-artefakter fick falskt
publiceringskvitto. Serverns skyddade backup ligger under
`/srv/smako/backups/lund-activation-20261001T2110Z`; lokala bevis/backup under
`.local/activation-live-20261001`. `/opt/smako/current` och `/opt/smako/compose`
använder nu slutpaketet och skyddad `activation-private.env`; äldre env/policy
är separat bevarade. Använd inte gamla bilden som återgångsmål.

Godkänd reservdrift är slutbildens `app.recovery`, senaste checkpointade
planbas read-only och befintlig autentisering; ingen nyplanering/omräkning/import.
Den är **inte aktiverad**. Full normal drift är aktiv. Begränsad fysisk
utbudstäckning, karantän och schema-/datorbortfallsrisker finns i protokollet.
Konservativ manifestgräns är 2 oktober 13:17:53 CEST; förfallna frivilliga
källkontroller beräknas omkring 00:30. Bekräfta verkliga kommande körningar,
använd aldrig rebuildtid som observationstid.

Ingen applikationskod eller identifierat paket ändrades under aktiveringen.
Verifieringsverktyg/driftunderlag har ändrats lokalt; ingen push, städning eller
Malmö-aktivering. Nästa separat etapp: kampanjfönstren söndag–måndag och
onsdag–torsdag samt mätning av basprisförändringar, inte implementerat här.

## Bevarad historik före genomförandet

# Aktivering 2026-10-01: schema godkänt, stopp vid Windows-behörighet

Alla fyra beslut är givna: femkällorspolicy, server med begränsad läsåtergång,
bdc9-reläbyte och lokala 01:30/09:30/17:30. Begär inte dessa igen.
Faktisk uppdatering/paus av befintlig uppgift nekades 19:50:00 UTC med
`0x80070005 E_ACCESSDENIED` för ossia utan förhöjning. Uppgiften är byteidentisk,
fortfarande Ready med enbart 01:30. Ingen paus/serverändring/insamling utförd.
Läs [aktuellt operatörssteg och bevis](releases/lund-20260929/ACTIVATION-OPERATOR-20261001.md).
Slutligt granskat skript `scripts/release_verification/set_lund_task_paused.ps1`
stagerar godkända Arguments/WorkingDirectory och tre lokala tider, lämnar
befintlig uppgift DISABLED och bevarar principal/övriga inställningar. Det ska
köras förhöjt som samma ossia, utan policyöverstyrning. Därefter läs tillbaka
och fortsätt serverförkontroller/paus/backup/samordnat byte enligt ACTIVATION.
Återuppta inte scheman före faktisk produktionsacceptans.
Nytt bdc9-not_due-prov på kopierat autentiskt tillstånd: 0 externa anrop,
byteidentiskt kvitto/källtid. Normal drift/nyplanering/uttrycklig omräkning/GET
är ännu inte provade i ny produktion. Inga gamla blockerare återinförs.

## Föregående stopp före det nu givna schemagodkännandet

**Tre produktionsbeslut är nu uttryckligen godkända, villkorat av förkontroller.**
Godkännandena ska inte begäras igen. Ingen aktivering har gjorts: bdc9-reläets
35-timmarsregel ihop med enbart daglig 01:30-start ger ett återkommande glapp
vid 48-timmarsstoppet. Användarens uttryckliga stoppvillkor i B gäller.
Läs [aktiveringsprotokollet](releases/lund-20260929/ACTIVATION-PREFLIGHT-20261001.md)
och [aktuella driftordningen](releases/lund-20260929/ACTIVATION.md).
Förslag till separat schemabeslut: behåll 01:30, lägg till 09:30/17:30-kontroller
med oförändrade behovsregler, konto och PT3H. Inget schema har ändrats.
Produktion kör fortsatt gammal bild; läsande kontroll visade stale och /ready 503,
170 planrevisioner. Inga planer, köer, policyer eller drifttillstånd ändrades.
Releaseidentitet/filer verifierade. Återstående aktuella aktiveringskontroller
är inte generellt PASS. Tidigare kö-/återgångs-/S4U-bevis gäller fortfarande.

## Bevarad releasebedömning före villkorat aktiveringsgodkännande

**REDO FÖR SEPARAT AKTIVERINGSBESLUT**, med begränsad återgång till sparad
planläsning. Köövergång och kompatibilitetsåtergång är implementerade och provade.
Läs [TRANSITION.md](releases/lund-20260929/TRANSITION.md), dess maskinläsbara
bevis och [ACTIVATION.md](releases/lund-20260929/ACTIVATION.md) före driftarbete.
Slutlig runtime är `08c137475d9ca96a6ef7673245a639c8c5c9e922`; server-/
återgångsbild `sha256:d8a166fa7ee162cd0570f9d8089ff800e00d9c949ac3c674e387c5fff1538dd7`.
Föreslaget Windows-relä förblir det oförändrade liveprovade bdc9-paketet.
Nytt Windows-ZIP är byggt men inte installerat/S4U-liveprovat.

Gamla kön arkiveras återupptagbart under befintliga lås och hålls separat;
blockerad gammal Primat-publicering behöver **inte** lyckas före bytet.
Återgångsmålet är slutbildens `app.recovery`, senaste checkpointade planbas,
read-only, befintlig autentisering och full sparad JSON. Det stöder läsdrift,
inte nyplanering/omräkning/import; de funktionerna vägras kontrollerat.
Ingen äldre databas eller kö återställs över nytillkommet tillstånd.
168 fokustester passerade i ren klon; paket reproducerade, Docker/HTTP-prov
och verklig omstart redovisade i det nya underlaget. Produktionsbild, aktiv
Windows-uppgift och säkerhetspolicy/scheman är oförändrade; ingen push.
Femkällorspolicy, serveraktivering (inklusive begränsad återgång) och byte av
Windows-uppgiften är fortfarande tre separata, ej fattade beslut.

## Bevarat S4U-livebevis och tidigare driftstatus

**Senaste granskning 2026-10-01: obevakad livehämtning och leverans PASS.**
Operatören körde den isolerade uppgiften 09:44:23–10:33:32 svensk tid.
`ossia`, S4U/Limited, session 0, icke-interaktivt; giltigt startkvitto.
1 255 verkliga Willys-anrop (två återhämtade HTTP 500), 18 939 produktposter,
ny artefakt `5b1a2b6b…`, exakt en mottagarimport `293e1533…`.
Faktisk reload och senare HTTP-läsning visar manifest `19cd1da8…`, **44 066**
råproduktposter; samma ID/hash i beständigt framgångskvitto. Mottagare,
relä, observatör och Task Scheduler rapporterar 0 för denna körning.
Se [S4U-LIVE.md](releases/lund-20260929/S4U-LIVE.md) och dess hashade bevis.
Granskningen startade inget nytt jobb, samlade inte in och ändrade inte drift.
Starta inte igen med stöd av gamla instruktioner eller gammalt startkvitto.

[Förkontrollen](releases/lund-20260929/S4U-PREFLIGHT.md) är historik:
dess 44 080-manifest har ersatts av denna liveleverans. Profilproven på
42 491 och de tidigare driftproven på 44 132 är fortfarande separata bevis.
Inga säkerhetspolicyer, uppgiftsargument eller produktionsbeslut ändrades.

**Historiska driftspärrar från 2026-09-30, ersatta av TRANSITION ovan.** Läs även
[OPERATIONS.md](releases/lund-20260929/OPERATIONS.md) och uppdaterad
[ACTIVATION.md](releases/lund-20260929/ACTIVATION.md). Runtime/paket är kvar
på bdc9f7d i det historiska underlaget; dess fortsättning ändrade endast provverktyg och underlag.
Faktisk produktionsbild `54dde838…` tappar 64/12 planfält och ger 500 för
`kind=campaign`, även efter omstart med gammalt manifest. Ny bild återläser
alla tre nya planer identiskt på 44 132-manifestet; samtliga 37 revisionsrader
bevarade. Originalpolicyn stoppar publicering av den gamla kön genom saknad
Primat-bas. Det nya Windows-paketets SSH-replay/kvittot/not_due passerar;
det är separat från det nu granskade obevakade liveprovet. Registrerings-
och S4U-livehindren är stängda för provad konfiguration. Versionsövergång
och säker återgång är fortsatt blockerade och har inte omprövats här.
Aktiva Windows-uppgiftens XML är byteidentisk före/efter. Produktionens
bild, policy och scheman är oförändrade; ingen push. De tre
produktionsbesluten är fortfarande separata och ej fattade.

### Ursprungligt releaseunderlag före driftkompletteringen

Arbeta i **D:\Projects\Smako** på `release/lund-relay-20260929`.
Runtime-källcommit för separat server- och Windows-reläpaket är
`bdc9f7df417084641d0a712e3dad188dad1ad7d4`; se
[resultat, källfärskhet, hashvärden och blockerare](releases/lund-20260929/RESULTS.md)
och [förberedd aktivering/återgång](releases/lund-20260929/ACTIVATION.md).
Konsolideringstaggen och originalmapparna är bevarade. Fem tidigare basfel är
utredda/rättade; de 16 autentiska Lidl-proven passerar. Kandidaten är byggd,
installerad som **inaktiv** relärelease och isolerat provad; den är inte
installerad eller aktiverad på produktionsservern och den aktiva Windows-uppgiften
har inte ändrats. Senaste isolerade faktiska serving hade 44 132 produkter i 33
kontexter efter behovsstyrd frivillig insamling, med fem giltiga obligatoriska
onlinebaser. Äldre mottagare kan inte ta ny kommunartefakt och ny mottagare
avvisar gammal city-scope-artefakt. Tillfälligt S4U-testjobb kunde inte
registreras (`Åtkomst nekad`); obevakad kandidatkörning är därför fortfarande
öppen. Statusen ovan ersätter tidigare oprövade återgångsantaganden.

---

## Bevarad konsolideringshandoff 2026-09-29

# Aktuell arbetsrot: lokal konsolidering 2026-09-29

Permanent rot: **D:\Projects\Smako**. Huvudgren: `master`.
Integrationsgren: `chore/consolidate-smako`. Lokal tagg:
`consolidation-20260929-local` (ingen produktionsrelease).

Konsolideringsverifiering: **672 godkända, fem befintliga fel, inga nya fel**
bland 677 unika testfall; samma resultat i ren klon. Planner/audit/sparning/
återläsning matchar basen. Frontend 30/30, Ruff, compileall och pip check PASS.
Dockerbygge och browser-E2E är inte körda. Alla 16 historiska Lidl-prov passerar.

Den samlade koden är arbetskopians smako-legacy-purchase-terms:20260929-v5,
inklusive dess tidigare ocommittade kommunflöden, PurchaseTerms, exakta/uppskattade/
villkorade köp, närings-/beredningskontroller, sökoptimering och planlagring.
Äldre autentiska Lidl-fixturer samt streckkodsläsarens byggkällor är återställda.
Historiska appalternativ bevaras, men ersätter inte rättad kod.

Ingen produktion har aktiverats eller undersökts på servern. Kandidatens tidigare
handoff redovisar isolerad verifiering, inte produktionsaktivering. Windows-jobb,
scheman och användarprofiler är oförändrade. Priserna behåller observationstiderna.

Start, test, bygg och återställning: [DEVELOPMENT.md](DEVELOPMENT.md).
Ursprung, backup och externa gamla sökvägar: [CONSOLIDATION.md](CONSOLIDATION.md).
Aktuella testresultat och basfel: [verifiering](consolidation/VERIFICATION.md).
Backup: D:\Smako-backups\consolidation-20260929. Stora testdata återställs med
hashmanifest; hemligheter och privata drift-/användardata tillförs separat vid
ett uttryckligt behov. Använd mockmiljön för lokal start.

Kvarvarande produktfrågor från tidigare handoff gäller bland annat okända
kampanjvillkor/källfakta, Malmös fullständiga publicering, originalpolicy/Primat,
ICA:s okända kommunträffar och Lidl/Willys-täckning. Den tidigare saknade
historiska Lidl-fixturen är nu återfunnen; testutfallet redovisas i verifieringen.

---

## Historiska handoff-anteckningar, bevarade nedan

# Smako – 29 september 2026: äldre importer anslutna till PurchaseTerms

[Resultat och före/efter](../reports/legacy-purchase-terms-20260929/RESULTS.md), [acceptans](../reports/legacy-purchase-terms-20260929/ACCEPTANCE.json), [hela nämnaren](../reports/legacy-purchase-terms-20260929/comparison.json).

PASS i isolering: ICA/Coop/Hemköp/X:-tra för vidare belagda fasta/styck-, cirka-/lösvikts-, flerköps- och villkorade variantköp till befintlig motor. Inga uppdiktade restpriser, vikter eller variantidentiteter. Oklart viktköp utan uttrycklig form spärras. Samma sparade underlag/köpdag: godkända källrader 277→824, 254→1 614, 42→333 respektive 7→11; exakt/uppskattat/villkorat och butikskopior särredovisas i rapporten. Noll nya återförsäljarhämtningar.

Lund serving 42 085→44 119; 33 kontexter och fem obligatoriska onlinebaser (41 512 produkter) bevarade. Andra ordinarie rebuilden med frivilligt Hemköp-fel, reload och faktisk omstart ger identiska produkter/köptermer. Sju verkliga API-köp, två negativa kontroller, sparning/återläsning och befintligt närings-/beredningsprov PASS. Alla fyra oförändrade 15/20-profiler: 201/445,29 kr; audit och sparning/omstart PASS. Tidigare planrevisioner, skafferi och privata tillstånd är bevarade.

457 berörda regressioner verifierade, ytterligare 31 UI/runtime-prov, Ruff/compileall PASS. Isolerad image `smako-legacy-purchase-terms:20260929-v5` (`eee77ff22794…`), femkällorskandidaten fortsatt alternativ; ingen produktion, Windows-/schema- eller originalpolicyändring. Observationer är oföryngrade och status AGING/degraded redovisas ärligt. Coop-v4, kommunstödet, Primat och tidigare femmiddagsmilstolpe kvarstår.

Kvar separat: saknade källuppgifter/pant och ännu ej modellerade kampanjvillkor, Malmös baspolicy/fullständiga publicering, ICA:s okända kommunträffar, Bunkeflostrands källväg, Lidl/Willys-täckning och historisk Lidl-fixture. Prisgodkännande ger inte närings-/allergigodkännande.

---

# Smako – 28 september 2026: ICA/Hemköp kopplade till gemensamt kommunläge

[Samlat resultat](../reports/ica-hemkop-municipality-20260928/RESULTS.md),
[butiksrader och nästa uppdatering](../reports/ica-hemkop-municipality-20260928/STORES.md),
[köp och audit](../reports/ica-hemkop-municipality-20260928/OFFERS.md),
[acceptans](../reports/ica-hemkop-municipality-20260928/acceptance.json).

Lund PASS i isolering: samma kommunval genom inventering, källurval, OWN, PriceUniverse och beständig uppdateringsstatus. ICA 12 butiker/277 godkända OWN/275 serverade; Hemköp 3/18/18, inklusive Dalby utan onlinekatalog. Total serving 42 003 → 42 085. Södra Sandby, Genarp och Veberöd inkluderas på verifierad kommuntillhörighet. Fem obligatoriska baser, Coop-v4 och X:-tra bevaras.

Ordinarie publicering/reload, nästa rebuild med synligt frivilligt Hemköp-fel och omstart ger identisk produkthash. Fyra HTTP-profiler 201/445,29 kr, audit och identisk sparning/GET efter omstart. Förfallen ICA-inventering behöll alla prisobservationer och godkännanden utan prisanrop. 217 tester, Ruff/compileall och 592 runtimefilhashar PASS. Isolerad image `smako-ica-hemkop-municipality:20260928-v8` (`0790b31f3d7a…`); ingen produktionsaktivering, Windows- eller schemaändring.

Malmö: ICA 24 verifierat innanför, 23 insamlade/560 OWN; Hemköp 4/24 OWN. Två identiska PU-kandidater med 580 produkter, men **0 aktiverad serving**: ordinarie kontrollkorg är ofullständig, ingen Lund-baspolicy används. Bunkeflostrand saknar verifierad strukturerad erbjudandelänk; 45 ICA-träffar har okänd kommunstatus. Full Malmö-publicering, äldre PurchaseTerms, komplexa kampanjvillkor, Lidl/Willys-täckning och historisk Lidl-fixture kvarstår separat. Tidigare femmiddagsmilstolpe, originalpolicy/Primat och sparade användarval bevaras.

---

# Smako – 28 september 2026: Coops aktuella butikskälla återställd i isolering

[Resultat och butiksrader](../reports/coop-source-binding-20260928/RESULTS.md),
[exakt källkonflikt och rättning](../reports/coop-source-binding-20260928/ANALYSIS.md),
[maskinellt avstämd acceptans](../reports/coop-source-binding-20260928/acceptance.json).

PASS: den missvisande butik-/källkonflikten var två nya villkorsfält i det strukturerade svaret. Parser v4 bevarar köpkrav/prissteg och spärrar berörda rader; providern medger granskade v3/v4, inte okända versioner. Ny faktisk insamling 28/9 11:01 UTC: nio Coop/Stora Coop, 254 godkända av 2 179 rader, 1 925 i karantän. Faktisk serving 41 755 → 42 003 poster. Fem onlinebaser oförändrade; X:-tra separat med sex oförändrade poster.

Ordinarie rebuild/reload, nästa rebuild med injicerat Coop-fel, faktisk omstart och kampanjreplay PASS. Fyra profilprov gav 201/445,29 kr, verifierad audit och identisk sparning/GET efter omstart. 152 tester, Ruff och compileall PASS. Isolerad image `smako-coop-source-binding:20260928-v4` (`fdaf9c4a61e9…`); ingen produktionsaktivering eller schema-/Windowsändring.

`lund-own-five-base-20260928-v1` bevaras som verifierad alternativ kandidat. Tidigare kandidat och 337 bevisfiler är oförändrade. Originalpolicy/Primat och övriga uttryckligen separata uppgifter kvarstår; tidigare femmiddagsmilstolpe påverkas inte. Ingen extern uppgift blockerar denna källfix; kvarstående villkorsrader ska fortsatt spärras.

---

# Smako – 28 september 2026: Lunds alternativa basstrategi verifierad i isolering

[Samlad rapport](../reports/lund-base-strategy-20260928/VERIFICATION.md),
[Primats faktiska kontrakt](../reports/lund-base-strategy-20260928/PRIMAT-CONTRACT.md),
[butikstäckning](../reports/lund-base-strategy-20260928/STORE-RESULTS.md),
[valda köp](../reports/lund-base-strategy-20260928/SELECTED-PURCHASES.md),
[profilresultat](../reports/lund-base-strategy-20260928/profile-summary.json),
[separat policy-/aktiveringsunderlag](../reports/lund-base-strategy-20260928/ACTIVATION.md).

**Originalpolicyn är fortfarande blockerad; ingen aktivering.** Primat 1004409
anger offers_only, oförändrad identitet. Coverage är lokal normalisering av
källans tier; selected är källurval och inte orsaken till full_catalog-avslaget.
Augustiexporter visar tier=full, men fullständigt historiskt HTTP-råsvar saknas;
dåtidens fullklassning var källdeklarerad med begränsade produktprov.

Separat testpolicy `lund-own-five-base-20260928-v1`: fem obligatoriska OWN-baser
(Coop Online Syd, Hemköp Karhögstorg/Brunnshög, Willys Lund/Nova) plus giltiga
frivilliga erbjudanden. 41 512 tillgängliga basposter + 243 erbjudandebutiksposter
= 41 755 serverade poster / 19 kontexter. Onlinebas och fysiska offers_only hålls
isär. Clemenstorget bidrar med 34 erbjudanden, ingen full katalog.

Fyra ordinarie HTTP 15/20-profiler (original/Plus × exact/estimated): alla 201,
445,29 kr, 15 exakta/0 uppskattade/0 villkorade köprader, Coop Online Syd och
Willys Lund. 159,07 / 180,31 / 154,05 / 182,97 s. 40/30/20-målen uppfyllda;
10 näringsresultat VERIFIED och 5 ESTIMATED. Audit PASS; fyra planer oförändrade
vid GET och faktisk omstart. Plus är aktiverat men inget valt medlemsprisköp.

Den första isolerade kopian saknade katalogernas råfiler. Felet är rättat i
initialize_job.py och genom 2 232 hashverifierade råfiler; HTTP har nu förkontroll.
De första DATA_BLOCKED-proven är sparade separat och är inte basstrategins resultat.
Inga observationer föryngrades. Appkoden är oförändrad: 589 filhashar matchar den
pinnade bilden 32e838155b0e…; pip check utan fel; 238 tidigare rapportbevis bevarade.
37 riktade regressioner godkända. Ordinarie andra rebuild/reload, omstart/not_due,
obligatorisk basavvisning utan LKG, frivilligt fel, kampanjutgång och replay-
återhämtning är verifierade och särredovisade. Sista basålder 15,72–16,54 h.

Alternativet kan nu bedömas separat för fortsatt release. Det är inte godkänt enligt
originalpolicyn och ändrar inga produktionskrav eller användarval. ICA-/Hemköps
kommunlucka, äldre köptermer, Malmö-publicering och historisk Lidl-fixture kvarstår.
Dagens nya fysiska Coop-hämtning är avvisad på butik-/källbeviskonflikt; endast
fortfarande giltiga godkända LKG-erbjudanden används. Före eventuell aktivering
måste aktuell basfärskhet, kampanjer, råfiler och policy kontrolleras igen.

---

# Smako – 27 september 2026: aktuellt Lund-prov, ingen aktivering

[Samlad verifiering](../reports/lund-integration-20260927/VERIFICATION.md),
[butik för butik](../reports/lund-integration-20260927/STORE-RESULTS.md),
[faktiska HTTP-resultat](../reports/lund-integration-20260927/profile-summary.json),
[separat aktiveringsunderlag](../reports/lund-integration-20260927/ACTIVATION.md).

**Lund är inte redo för aktiveringsbeslut.** Aktuell Primat-resolve anger
ICA Clemenstorget 1004409 som offers_only, medan obligatoriskt kontrakt kräver
full_catalog. Ingen färsk komplett LKG. Full federation/publicering och de fyra
fria kompletta 15/20-proven är därför spärrade, inte godkända eller omräknade
med historiska 484,73 kr. Gunnesbos fullständiga identitet kan fortfarande
återvalideras; den obligatoriska bunten publiceras inte partiellt.

Verklig insamling 27 september: 41 704 OWN-baskatalograder; 192 uttryckligen
slut i lager. Smala schemaöversyner för redan stödda Coop-procent-/beskrivningsfält
och Hemköps EPREL-lampmetadata återställer normal import från samma råsvar.
Primat avbryter nu tidigt och rapporterar exakt täcknings-/identitetsstopp utan
onödiga produktanrop när giltig LKG saknas. Inga pris-/näringsskydd sänkta.

Separat OWN-only publicering: 42 319 poster, 27 kontexter, samma posthash efter
andra byggning och faktiskt reload. Det är inte den kompletta Lund-kandidaten.
Fysisk 15/20 exact/estimated: 422; 96 middagskandidater stoppas vid produkt/fakta,
inte sökbudget eller styrkt ekonomiskt bortval. Aktuell varm ostsmörgås via HTTP:
171,68 kr (hela Lingongrova 500 g + Hushållsost cirka 2,2 kg), 1 exakt/1 uppskattad,
33,8 g protein mot 30 g, VERIFIED_WITH_ESTIMATES, beredningsnäring ESTIMATED,
audit PASS. Flerköpsmåltidsprovet saknar brödets näringsunderlag och är inte grönt.
Sparning, omstart, faktisk klienttext samt läskompatibilitet i separat äldre
rollbackkod verifierade. Äldre nyomräkning inte bevisad.

Willys-källans not_due/felinjektion/replayåterhämtning verifierad med oförändrade
observationer. Framtidsklocka visar noll utgångna kampanjer till köp; baskatalog
spärras efter 48 timmar. Hela federerade driftkedjan måste omprövas när basen finns.
597 unika regressioner godkända (676 körningar inklusive riktade omkörningar).
Slutbild sha256:32e838155b0ef2b4b4eb9944cb7d1b31324b37e7ea56eb6d840fc70fc9e1ff87.
589 paketfiler kontrollerade; tidigare sökleverans 9 kod-/546 bevishashar bevarade.
ICA:s aktuella driftkoppling är fortfarande ortsurval, Hemköp godkända kontexter;
full kommuninventering för dessa är inte visad. Malmö-publicering och historisk
Lidl-fixture är separata olösta kontroller. Ingen produktion, Windows-uppgift,
schemaläggning eller sparad användarprofil har ändrats.

---

# Smako – 27 september 2026: gemensam receptsökning och korrekta råvaruformer

[Verifierade resultat](../reports/recipe-search-20260927/VERIFICATION.md),
[alla 84 recept med ID och första stopp](../reports/recipe-search-20260927/RECIPE-RESULTS.md),
[kandidat- och källspårning](../reports/recipe-search-20260927/recipe-first-stops.json),
[inaktiv release/rollback](../reports/recipe-search-20260927/RELEASE.md).

Historisk replay 24 september, oförändrade recept/mängder/40–30–20-mål/tvåbutikstak.
33/84 före och efter: 32 godkännanden bevarade, nytt Tacos med tofu och gul lök
(40,2125 g protein/portion, hel varukorg 117,05 kr). Stekt ris med lax och vitkål
hade ett felaktigt tidigare godkännande med torkad kryddvitlök som rå vitlök.
Det återkallas: korrekt råvaruform ger högst 39,58 g mot 40 g. Målet om fler netto
samt alla 33 bevarade är alltså inte uppnått; detta får inte döljas.

51 återstående första stopp är nu styrkta proteinövre gränser inom det aktuella
kvalificerade underlaget, inte budgetstopp eller påstådd global omöjlighet.
Alla 29 tidigare budgetfall har nytt referensprov (4096 lokalt tak, 30 s/case).
28 avbryts av giltig näringsgräns; tacoreceptets 832 klasser uttöms med samma
117,05 kr som ordinarie 256-sökning. Ingen global budgethöjning.

Fri 15/20: 484,73 kr i alla fyra fall. Original exakt 146,965→102,989 s,
original uppskattat 166,500→117,835 s, Plus exakt 145,039→104,718 s,
Plus uppskattat 170,830→119,052 s. Coop Online Syd online_fulfillment + Willys Lund
online_store. 16 exakta köp, 0 uppskattade/villkorade; näring 10 VERIFIED/5 ESTIMATED.
Samma 37031 produkter och pool 41; inga nya priser eller föryngrade observationer.

Gemensamma ändringar: konservativa näringsgränser och förberäknade näringsklasser,
återanvända fakta, begäransbunden cache för förpackningskostnader, exakt GTIN-bunden
Dabasimport med uttryckliga 200 ml/200 g för Skånemejerier 13 %, rå-formkontroll
för potatis/vitlök och befintliga SLV-referenser 4457/371. Deklarationsprioritet,
opt-in, allergispärrar, GoGreen-konflikt och butik/kanal/prisroll bevaras.
Ingen ny receptversion. Slutlig kod med gamla deklarationer ger 32/84; med
nya belagda mängdfakta 33/84. Den laktosfria varianten får inte låna massuppgiften.

700 regressioner plus 32 riktade slutprov; Ruff/compileall godkända. Nytt tacorecept
verifierat via ordinarie HTTP i båda lägena, audit, lagring, omstart och säker
rollback (läsning identisk, omräkning 422 bevarar plan). Alla 720 tidigare
releasebevis bevarade. Produktion, användarprofiler och scheman är oförändrade.
Färsk komplett produktionsbas, Malmö-publicering och historisk Lidl-fixture
kvarstår separat. Se PACKAGE.json för exakta filer, hashar och testbevis.

---

# Smako – 26 september 2026: mängd- och näringskoppling efter beredningsstödet

[Verifierade körresultat](../reports/recipe-resolution-20260926/VERIFICATION.md),
[alla 84 första stopp](../reports/recipe-resolution-20260926/recipe-first-stops.json),
[kandidater före/efter](../reports/recipe-resolution-20260926/candidate-review.json),
[separat aktiveringsunderlag](../reports/recipe-resolution-20260926/RELEASE.md).

Inaktiv kandidat. Oförändrade v1-recept: beredning 84→84,
näringsprövning 48→84, numeriskt resultat
39→84, mål + varukorg + audit 19→33.
Alla 19 tidigare godkända bevarade. Ingen ny receptversion eller ingrediensändring denna etapp.

Gemensam matchare prövar identitet före grov låg källklassning. Officiell Dabasimport
är bunden till kontrollsiffergranskad GTIN, varumärke och konsumentförpackning.
Crème fraiche har en produktspecifik belagd ml/g-relation, ingen generell densitet.
Avrunnen vikt skiljs från nettovikt och från näringstabellens beredningsgrund.
Fyra nya SLV-referenser importerade med råvärden och verkliga svarstider.
Ägg använder dokumenterad skalandel endast som separat opt-in-uppskattning;
verifierad produktnäring prioriteras. Pris, receptversion och näringskvalitet hålls isär.
Gravad fisk, burek, soppgrönsaksblandning och ostkex får inte bli rena råingredienser.
Gula ärtor är egen identitet och källkategorin Blötmat spärras som djurfoder.
En definierad identitets-/formspärr kan inte kringgås av textmatchning när en
ingrediens saknas i det ekonomiska kandidatindexet. Uttryckliga köpformer och
varor utanför taxonomin behåller sin separata, kontrollerade reservväg.

Fri 15/20, 40/30/20, max två butiker: 484.73 kr,
146.965 s, VERIFIED. Detaljer om fyra lägen, separata
legacy-/rebuildprov, valda recept och tidsprofil finns i verifieringen. Rebuildens
nya kandidatpool ändrar receptutbudet och är ingen jämförbar besparingsmätning.

Första stopp: {"NUTRITION_TARGET_NOT_MET": 22, "SEARCH_BUDGET": 29, "PASS": 33}.
Referenssökning 4096 för de gamla 20 avslagen ger inga nya godkända; se exakt
budgetstatus i rapporten, ingen global omöjlighets- eller dyrare-slutsats.

Ordinarie HTTP, checkout/audit, sparning, processomstart och explicit rollbackmål
är verifierade. Rollback till närmast föregående v1-beredningsleverans läser
nya sparade planer; omräkning avslås säkert och planen bevaras. Äldre versioner
utan preparation-kontrakt är inte verifierade rollbackmål. Visuell desktopkontroll
av uppskattningsmärkning och mängdinstruktioner dokumenterad separat.

Historisk prisreplay 24 september; nya mängd-/näringskällor 26 september.
Ingen prisobservation föryngrad. Ingen produktionsaktivering, användarprofil- eller
schemaändring. Färsk komplett bas, Malmö-publicering och historisk Lidl-fixture
kvarstår separat. GoGreen svarta bönors motstridiga näringsvärden kvarstår spärrade.

<!-- recipe-resolution-20260926:end -->

# Smako – 26 september 2026: implementerat recept- och beredningsstöd, inaktiv kandidat

[Uppmätt verifiering](../reports/recipe-preparation-20260926/VERIFICATION.md),
[rå sammanställning](../reports/recipe-preparation-20260926/summary.json),
[exakta receptändringar](../reports/recipe-preparation-20260926/recipe-changes.json),
[beräkningsmetod](recipe-preparation.md),
[aktiveringsunderlag](../reports/recipe-preparation-20260926/RELEASE.md).

Generatorns 80 varma recept och fyra särskilda beredningsfall har separata
versionerade definitioner, mängder och validerade instruktioner. Legacy och
sparade recept bevaras. Oljan 5/7,5/10 ml per portion är receptutformning,
inte mätt upptag. Gemensam metod beräknar insatsbaserade makron per portion
med opt-in och ESTIMATED; den hittar inte på färdigvikt, retention eller
ätbara andelar. Pris-/korgkvalitet är separat. Metoden följer API/PlanStore.

84/84 passerar nu beredning, 48 når näringsprövning, 39 får numeriskt
näringsresultat, 19 klarar mål + varukorg + audit. Två väljs i fri 15/20.
Första kvarstående stopp: 36 köp-/matchningsfall (22 rödlök, 10 crème fraiche
med g/ml-lucka, 3 svarta bönor, 1 bönor); 9 mängd-/näringsfall (5 ägg,
1 kidneybönor, 2 kikärtor, 1 blandfärs); 20 utan funnen målgodkänd kombination
i begränsad sökning. Det sistnämnda bevisar inte global omöjlighet/dyrare.

15/20, 40/30/20, max två butiker: gamla recept 535,25 kr, nya 484,73 kr
för public/Plus och exact/estimated. Samma kompletta historiska bas/köpdag.
Coop Online Syd + Willys Lund, 12→16 exakta köprader, VERIFIED korg,
5 ESTIMATED +10 VERIFIED näringsresultat. Olika receptinnehåll: inte en
besparing för identisk mat. Gamla definitioner är kodregression.

Ordinarie HTTP + sparning/GET + verklig backendomstart: tidigare spärrad
tofumacka 107,64 kr, 36,4 g protein mot 30; separat varm Lidl-/Arla-smörgås
171,68 kr, 33,8 g protein mot 30. Arla hela cirka 2,2 kg kostar cirka
153,78 kr, 100 g används. Exakt läge stoppar cirka-osten, uppskattat passerar
VERIFIED_WITH_ESTIMATES. Inga produktlås, extraköp eller kandidatpatchar.

179 riktade regressioner, Ruff och compileall passerar. Privata replayjobb
använder fryst klocka 2026-09-24T21:16:35.494010Z; inga prisobservationer
föryngras. Separat officiell Zeta-kontroll gav ingen ny importerad faktarad;
direkt arkivering 403. Ätbar äggmängd, avrunna mängd-/faktakopplingar och
saknade enhets-/produktkopplingar kvarstår. Ingen produktion, profil eller
schemauppgift ändrad. Färsk bas, Malmö-release och historisk Lidl-fixture
är separata öppna kontroller. Tidigare underlag följer oförändrat nedan.

---

# Smako – 26 september 2026: verkliga erbjudanden i PersonalPlanner, inaktiv kandidat

[Genererad verifiering](../reports/personal-offers-20260926/VERIFICATION.md),
[före/efter](../reports/personal-offers-20260926/profile-summary.json),
[produktbeslut](../reports/personal-offers-20260926/product-decisions.json),
[84 beredningsfall](../reports/personal-offers-20260926/preparation-review.json),
[aktiveringsunderlag](../reports/personal-offers-20260926/RELEASE.md),
[paket](../reports/personal-offers-20260926/PACKAGE.json).

Rättat: uppskattade priskandidater får tillgång till breda index även utan
inlästa näringsfakta. Verkligt fryst prov ger 4→6 ostkandidater: ett Arla-erbjudande
i två Lidl-butiker, inte två nya unika priser. För profilen med näringsfakta nådde
Arla redan matched-indexet; ingen sådan överföringsförlust har påvisats där.
Verifierad leverantörsklassificering Matbröd kopplas nu via gemensam deklarations-
projektion till receptmatchning; det löser Lingongrovas tidigare kortnamnslucka.
Ingen ny produkt-/kampanjlista och inga nya priser eller näringsvärden importerades.

PlanRequest har frivilligt planbundet allowed_store_ids för PersonalPlanning;
standardläge/användarprofil/kommunval ändras inte. Diagnostik binder produkt,
källsnapshot, butik, recept, första stopp, faktiska sökhändelser och avgränsade
alternativa hela korgar. Checkout/audit följer sparat personligt resultat.

Oförändrad 15/20 med 40/30/20 och max två butiker: 535,25 kr före/efter för
public/Plus × exact/estimated. Coop Online Syd + Willys Lund, 12 exakta rader,
20 förpackningar. Måltidsnäring separat: 10 VERIFIED +5 tillåtna ESTIMATED.
Arla-alternativen prövades i fulla korgar men den befintliga 256-kombinations-
näringssökningen hittade ingen godkänd lösning under butikstaket. Detta bevisar
inte ”dyrare” eller global omöjlighet. Gouda behöver deklaration/tillämplig
referens (Vardagsfavoriter, tillfälligt parti; GTIN/fetthalt saknas). Fläskreceptet
stoppas före produktprövning av beredningsgrund. Frukterna efterfrågas inte i poolen.

Verklig HTTP PersonalPlanner-måltid PASS: vanlig ostsmörgås, Lidl Plus för
Lingongrova, uttryckligt Lidl Åkerlund och Rausings väg 1. Ingen produktlåsning
eller extravara. 100 g bröd +100 g Arla-ost ger 33,8 g protein mot minst 30 g.
Helt bröd 17,90 kr +cirka 2,2 kg ost för 153,78 kr =cirka 171,68 kr;
1 exakt +1 uppskattad köprad, VERIFIED_WITH_ESTIMATES, checkout/audit passerar.
POST/GET och ny backendprocess/GET bevarar planen. Exakt läge spärrar cirka-osten.
Föreversionens HTTP ignorerar det då okända butiksväljarfältet och väljer Coop
för 30,28 kr: detta är inte en jämförbar Lidl-kostnad eller besparing.

252 regressioner PASS; Ruff/compileall PASS. Två äggberedningar, stekt tofu,
avrunna kikärtor och 80 genererade varma recept har kvar legitima beredningsspärrar;
alla 84 har konkret ingrediens-/instruktionsredovisning. Tidigare kommun-, andra-
rebuild- och refreshbevis behålls; berörd runtime/persistens prövas igen här.

Alla priser är historisk replay vid 2026-09-24T21:16:35.494010Z, samma kompletta
2139-produktbas/9 kontexter och alla 6 obligatoriska. Arlas redan sparade deklaration
observerades 25 september. Inga observationer föryngras. Ingen produktion,
Windows-/schemaändring, användarprofiländring, bildanalys eller betalt modell-API.
ÖPPET: färsk komplett bas/komplett Malmö-publicering; historisk Lidl-fixturelucka;
ny oberoende verklig kampanjutgåva; återstående käll-/beredningsunderlag.

---

# Smako – 25 september 2026: gemensam köpplanering, inaktiv kandidat

Senaste underlag: [resultat](../reports/purchase-planning-20260925/README.md),
[verifiering](../reports/purchase-planning-20260925/VERIFICATION.md),
[aktiveringsunderlag](../reports/purchase-planning-20260925/RELEASE.md),
[paketmanifest](../reports/purchase-planning-20260925/PACKAGE.json),
[kontrakt](purchase-planning.md) och
[alla blockerartyper](../reports/purchase-planning-20260925/BLOCKERS.md).

Den befintliga arbetskopian är bevarad; tidigare kedjereleaser och Primat kvarstår.
Gemensamt PurchaseTerms-kontrakt går genom SourceOffer/collector/OWN/PriceUniverse
samt matchning, optimering, checkout/audit och personligt API/UI/sparning.
Exakt är standard; uttryckligt uppskattningsläge stödjer lösvikt och hela
cirka-förpackningar med synliga reservationer. Styckpris behöver inte gramvikt.
Öppna källbelagda variantgrupper kan väljas som villkorat extra inköp men är
inte specifika recept-/närings-/allergigodkännanden. Riktig uppmätt användbar
mängd krävs för lagerbokning av ungefärliga köp.

Identifierade blandgrupper använder befintlig PromotionGroup-motor med
explicit käll-ID/grupp-ID, samma butik/snapshot, verifierad delmängd,
hela flerköp utan fabricerat restpris och belagda gemensamma hushållstak.
SourceOffer→collector→OWN→PU→gruppköp/audit provas med syntetisk källa;
detta är inte bevis för identifierade varianter i alla verkliga öppna grupper.
Gamla serialiserade defaults/digests bevaras och beräkningscachen har ny version.

Fryst jämförelse 24 september, samma prisunderlag och medlemskontext:
Willys 87→108 deduplicerade prisposter; 21 nya grupposter överlappar en gammal
kampanj, alltså 20 nya kampanjpriser varav 18 livsmedel. 74 exakta livsmedelsköp
kvar, 8 tidigare kg-priser nu användbara uppskattat, 19 villkorade livsmedelsval.
Lidl 26→28 (26 exakta +2 uppskattade). Willys annonser 20→23 av 34 och 57→75
av 112; manuella aktuella poster 2/7 bevarade separat. Lidl hela 380-ID-nämnaren
kvar: 28 kvalificerade, 350 saknar tillräcklig bindning, 2 parserkarantäner.
Gram-kompatibel näring Willys 10→10 / Lidl 2→3. Arla Hushållsost 26 %, ca 2,2 kg har officiell
variantbunden deklaration; 200 g behov köper helt paket för cirka 153,78 kr. SLV 580
Persika är märkt referens för uppmätta ätbara gram, ingen gissad kärnandel.
5 verkliga officiella närings-/produkthämtningar, 0 nya prisnätanrop i etappen.

768 unika riktade regressioner passerar; Ruff/compileall/JS-syntax passerar.
Riktig oförändrad 15/20, 40/30/20, högst 2 inköpsställen: 535,25 kr och VERIFIED
före/efter i både exakt och uppskattat läge (alla faktiskt valda rader exakta).
Slutprovet har samma kompletta bas och 9 kontexter inklusive alla 6 obligatoriska.
Ett mellanprov saknade fryst federerad klocka och föll till 8 kontexter; det
räknas inte som komplett bas. Ingen produktionsfärskhetsregel ändrades.

Ordinarie isolerad runner/publicering/reload, andra rebuild, processomstart,
not_due utan prisanrop, hämtfel/LKG och återhämtning PASS med samma slutkod.
Willys 243 / Lidl 224 / City Gross 13 523 poster i Malmö-driftprovet; källobservationer
bevaras. Separat Lidl-jobb återkvalificerar råsvar efter injicerat fel och
återstartar not_due. Framtida testklocka spärrar för gammalt underlag.

ÖPPET: verklig bas är nu för gammal för aktuell komplett publicering;
fullständigt Malmö-publiceringsprov med aktuell komplett bas; historisk
Lidl-fixture test_reviewed_lidl_nutrition.py (lidl_offer_adapter.py saknas);
ny oberoende tidigare ogranskad verklig kampanjutgåva; källblockerarna i
BLOCKERS.md. Hundra procent är inte uppnått och dessa punkter är inte stängda.
Ingen produktion, Windows-/schemaändring, bildanalys eller betalt modell-API.

---

# Smako – 20 september 2026, lokal Qwen3-VL faktiskt prövad; ingen prisaktivering

[Resultat och råbevis](../reports/ica-flyer-local-20260920/README.md), [körbok](../reports/ica-flyer-local-20260920/RUNBOOK.md), [lokalt kontrakt](ica_flyer_local.md), [före/efter](../reports/ica-flyer-local-20260920/BEFORE-AFTER.md), [releaseförslag](../reports/ica-flyer-local-20260920/RELEASE.md).

- Samma branch/worktree `sources/lidl-ica-evaluation-20260914`. Tidigare ocommittat arbete och OpenAI-adapter bevarade. Inga betalda API-anrop är godkända eller utförda i denna etapp; tidigare API-nyckelfråga är inte nästa steg här.
- Konkret lokal adapter `grocery_data.scripts.ica_flyer_ollama`, samma `smako-public-flyer-page-v1`, Qwen3-VL 4B Instruct Q4_K_M via Ollama 0.34.2. Modellvikter lokala, ingen cloud/fallback, innehålls-/kontext-/viktcache, original-PDF-bindning och diagnostiska utsnitt med koordinattransform. Befintlig batch använder samma kommandoinställning och begränsad timeout.
- Verkligt fyrsidorsprov på befintlig CPU-server: Söderlivs 6 gav 4 annonser, 3 rätt huvudbelopp men Milda 12 i stället för 19; Linero 1 timeout efter 900 s; Linero 3 HTTP 500/OOM i testmodellen; Söderlivs 1 läste sju tal under en enda felaktig produktidentitet. 28,86 min totalt. Fryst visuellt facit 25 annonser: 4 rätt produkt–priskopplingar, 7 fel, 14 ej bedömbara p.g.a. sidfel. Assistentens separata visuella granskning, inte påstådd extern mänsklig attest.
- Två verkliga 240-dpi-utsnitt: Milda fick rätt 19/st och Jfr 38/liter, men fel geometri/okända villkor/identitet; Linero ris + Dusch/Deo + Donuts fick jämförpriser felaktigt som köppriser. 235,389/396,118 s. Explicit jämförprisgrind tillagd med verkligt modellsvar som regression. Ingen helsida blir komplett av ett utsnitt; Milda fortsatt isolerad.
- Resurser: laptop otillräckligt ledigt RAM/gammal GPU-driver; serverprov 2 CPU/6 GiB hårt modellminne, låg prioritet, offline nätverk utan publicerade portar. Vikter flyttade från tmpfs till vanlig disk med samma SHA-256. Ett minnesskyddsstopp och en OOM i testmodellen, inga OOM/omstarter i beta/scheduler. Slutkod släpper modellminne efter anrop (`keep_alive=0`); två utsnittsprov utan ny OOM. Ingen flerdagars- eller latensgaranti. Modellcontainern är nu stoppad, inga scheman/aktiveringar.
- 7 lokala chat-anrop (5 svar, 2 fel), 10 539 kända input-/5 915 output-token för avslutade svar; ofullständig tokenmätning för felanrop, inte noll. 0 USD API. Fyra cacheåterbindningar utan modellgenerering eller ändrad källobservation. 325 riktade regressioner samt Ruff/compileall PASS.
- 0 nya kvalificerade bildimporter. Tidigare Linero 14/Söderlivs 16/totalt 155 ICA-produkter bevarade. Pris-/planeringskoden är oförändrad; tidigare 15/20 = 560,33 kr i båda armarna är historisk verifiering, inget nytt menykörningsresultat. Primat kvar, blockerad ICA-baspriskatalog pausad. 54 återstående unika PDF-sidor/112 butik–sidkopplingar kvar i kön; storbatch och 8B inte godkända av pilotutfallet.

Det lokala backendet fungerar som verklig modelltransport men den prövade konfigurationen är **inte tillräcklig för automatisk prisimport**. Nästa tekniska arbete måste förbättra produkt–pris-/prisrollstolkning, annonsgeometri och små villkor samt verifiera resurser/återhämtning innan större batch. Behåll karantän, 95-procentsgrind, datum/färskhet och prisavtal. Ingen skarp aktivering utan separat beslut.

---

# Smako – 19 september 2026, konkret bildadapter; API-provet blockerat

[Leverans och exakta körkommandon](../reports/ica-flyer-vision-20260919/README.md), [kontrakt/konfiguration](ica_flyer_vision.md), [före/efter](../reports/ica-flyer-vision-20260919/BEFORE-AFTER.md), [15/20](../reports/ica-flyer-vision-20260919/PROFILE.md), [releaseförslag](../reports/ica-flyer-vision-20260919/RELEASE.md).

- Concrete Responses-bildadapter `grocery_data.scripts.ica_flyer_openai`, modell `gpt-4.1-mini-2025-04-14`, befintligt processkontrakt. Original-PDF/hash/sida kontrolleras av programmet, två bildpass med småtrycksförstoringar, separata prisroller, innehålls-/kontextcache, kostnadsbokföring, serialiserad återupptagning. Ingen parallell prissättare.
- Serverberoendet PyMuPDF 1.28.2 provat via isolerad Linux-wheel; produktionen inte ändrad. Verkliga original: Linero `btnvspch:3`, Söderlivs `pjv63t92:6`, sju renderade bilder vardera. HTTPS till OpenAI fungerar (401 utan autentisering). **Ingen modelltolkning har utförts:** API-nyckel saknas och betald ram är inte godkänd. 0 anrop, 0 USD, 0 bildimporter. Nyckeln ska konfigureras skyddat på servern, aldrig i chatt. Frågan lyftes tidigt och är obesvarad. 54 unika PDF-sidor kvarstår; kalla inte detta färdig bildinsamling.
- Belagd GTIN-bunden pant går via befintlig review/SourceOffer/OWN/prisavtal till checkout/audit: belopp per behållare × antal × köpta paket, inkluderad pant inte dubbelt. Okänd pant, fel variant och obelagda ordinarie restköp stoppas. Verifierat med uttryckliga fixtures, inte verklig ny bildprisimport.
- Slutkodens nya offentliga insamling 20:58–20:59 UTC: 655 oförändrade återobservationer mot förra leveransen, 0 nya. Linero 14, Söderlivs 16, totalt 155 ICA-produkter kvar. Linero 56/59 och Söderlivs 52/57 underkänner fortfarande fullsnapshotens 95-procentsgrind; partiella radavtal bevarade.
- Verkligt nytt 15/20-par, samma frysta originalbas/Primat/krav: 560,33 kr i båda armarna, två ställen, HTTP 201/PASS; 37,432/38,718 s HTTP, 212,382/213,912 s totalt. 36 657 basprodukter och 35 078 basfakta identiska. 155 ICA-produkter tillagda, inga valda i menyn. Linero 2 paket ris/50 kr och Söderlivs tomater 1 paket/30 kr passerar diagnostisk audit; de är befintliga strukturerade priser, inte nya bildpriser.
- 300 riktade tester PASS; Ruff/compileall PASS. Samma arbetsgren/worktree, äldre rapporter och ocommittat arbete bevarade. Ingen aktivering, källväxling eller schemaändring; Primat kvar, blockerad ICA-baspriskatalog pausad, Milda fortsatt isolerad. Nästa steg är nyckel/ram, verkligt modellprov och granskning före batch – inte ännu en inventering.

---

# Smako – 19 september 2026, radgodkänd ICA-import och färskt slutkodstest

[Leverans och kvarstående hinder](../reports/ica-flyer-import-20260919/README.md), [kvalitet](../reports/ica-flyer-import-20260919/QUALITY.md), [reklamblad](../reports/ica-flyer-import-20260919/FLYERS.md), [15/20-resultat](../reports/ica-flyer-import-20260919/PROFILE.md), [separat releaseförslag](../reports/ica-flyer-import-20260919/RELEASE.md). Samma branch/worktree, tidigare ocommittat arbete bevarat. Ingen produktion, källväxling eller schemaaktivering. Primat kvar; ICA:s blockerade direkta baspriskatalog fortsatt pausad.

- Explicit `partial-row-approved-offers-v1`, separat offers_only-scope och `complete=false`; ursprunglig fullsnapshotbedömning/nämnare/95-procentsgrind oförändrade. Okända parser-/schema-/gemensamma butiksfel stoppar berörda kandidater. Osäkra rader ligger kvar i karantän, LKG och baskontrakt påverkas inte.
- Färsk begränsad serverinsamling 19 september 16:30:12–16:30:57 UTC, befintligt operationslås och isolerad SQLite/rådata. Lund 12 upptäckta/9 inom verifierad adressort, Malmö 69/21 inventerat utan handlista. 655 råannonser, 633 parsade, 22 parseravslag. Linero 56/59 och Söderlivs 52/57 underkänner fortsatt fullgrinden men bidrar nu med 14 respektive 16 radgodkända OWN/PriceUniverse-produkter. Totalt 156 OWN/155 PriceUniverse; Gunnesbos gaständare stannar i OWN på explicit fixed_package-gräns.
- Parser v7 bevarar tryckt ordinarie kampanjreferens separat; inget fabricerat ordinarie köppris. Offentliga och berättigade allmänna medlemsavtal använder befintlig prissättning. Verifierad identisk lokal/central Söderlivs-äggkampanj deduplicerad med båda beläggen och ett gemensamt köptak. Tidigare sju identitetsrättningar kvar, Milda-kopplingen fortsatt karantän.
- Alla upptäckta nio unika utgåvor: 94 unika PDF-sidor plus fyra digitala läsarsidor hämtade. 40 PDF-sidor innehållsverifierat transkriberade; 54 unika PDF-sidor fortfarande ofullständigt extraherade. 179 av 687 butik–annonskopplingar har konkret strukturerad post, 508 blockerade/preliminära. Extra läsarbilder manuellt verifierade som instruktioner/navigation utan priser. Automatisk bildtolkning saknar konfigurerad tjänst i körmiljön. Generisk worker → review → SourceOffer → OWN-import är fixturetestad, men verkliga nya bildextraherade importer är **0**. Hela reklambladsuppdraget är inte färdigt.
- Riktig oförändrad 15/20, 40/30/20 g, max två ställen: båda HTTP 201, **560,33 kr före/efter**. HTTP 37,831/39,875 s, totalt 214,582/219,680 s. Samma färska frysta originalbas (inte sökprojektion), alla 36 657 basprodukter och 35 078 fakta exakt oförändrade. 155 ICA-prisprodukter/28 härledda fakta tillkommer. Inga tillskott valda; 15 individuellt näringsstödda, inga tillskott i profilens registrerade auditerade receptkorgar. Separata verkliga diagnostiska korgar klarar matcher/checkout/audit: Linero jasminris 2×1 kg/50 kr, Söderlivs tomater 500 g/30 kr. Näringsuppskattningar enligt oförändrad ursprungsprofil särredovisas.
- Nya källrader 43, ändrade 27, återobserverade oförändrade 585; en logisk äggdubblett. 155 produkter kallas inte 155 nya priser. 242 fokuserade tester samt Ruff/compileall PASS. Efter prisparet ändrades bara valfria kandidatjobbets uppstartsfelisolering/CLI-hook; berörda tester och hela fokuserade sviten kördes om. Pris-/parser-/matcher-/checkoutkod matchar paret. Inaktiv driftflagga och testad LKG-återhämtning finns, ingen observerad flerdagarsstabilitet.

Nästa kvarstående arbete: verklig bildtolkarintegration/acceptans, resterande annons-/text-/digital-layout-extraktion, pant- och variantbevis, samt styckvarans offers_only-projektion. Nya kampanjer måste ha aktuell relevant evidens. Läs README/FLYERS/QUALITY före fortsättning; gamla kampanjer och historisk replay är inte framtida releaseacceptans.

---

# Smako – 19 september 2026, ICA-täckningsluckor och återupptaget arbete

[Leverans och kvarstående hinder](../reports/ica-area-gaps-20260916/README.md), [butiksvis före/efter](../reports/ica-area-gaps-20260916/BEFORE-AFTER.md), [separat releaseförslag](../reports/ica-area-gaps-20260916/RELEASE.md). Samma branch/worktree från 14 september; befintliga ändringar bevarade. Ingen commit, produktionsaktivering eller schemainstallation. Primat kvar och ICA-baspriskatalog fortsatt pausad.

- Ny begränsad publik insamling 16 september 12:36 UTC: Linero 56/59 (94,915254 %), Söderlivs 45/49 (91,836735 %). Samma 95-procentsgrind/nämnare; sju pantposter saknar belagda variantspecifika belopp. Tydligare parserdiagnostik, verkliga råsvarsregressioner. Båda snapshots avvisade, 0 aktiva OWN/PriceUniverse. Jasminris/Pizzakit spårade till exakt snapshotblockerare; inga köpriser har fabricerats.
- Åtta identitetskonflikter utredda: sju fallbacknamn/skiftlägesskillnader rättade, Milda/Milda Culinesse-kopplingen kvar i karantän. Oberoende basfakta förblir orörda; priser/medlemsvillkor överförs inte. 35 207 gemensamma basfakta oförändrade, 20 tillagda faktaposter.
- Alla Lund 12/Malmö 69 butiker redovisas, 9/21 inom befintlig adressort. Granskningsbara konfigurationsförslag genereras från full inventering, även när butikens prisinsamling underkänns. Malmöinsamlingsstatus är omätt, inte tom.
- Reklamblad: 9 utgåvor/94 sidor/605 preliminärt inventerade rutor. 40 sidor avlästa kampanjvillkor, 54 kvar i granskning. Linero/Söderlivs 94 rutor: 89 kampanjmässigt täckta, fyra pantblockerade, en Ciabatta-butiksgiltighet att granska. Evidensbunden granskningsadapter till befintlig SourceOffer; ingen ny flyer-prisimport/liveacceptans. Datum/ruta/butik/villkor/hash och ursprunglig observation bevaras.
- Flerköpsfel rättat: gruppköp utan ordinarie pris kräver inte ett påhittat enstyckspris. Befintlig checkout kräver full grupp, giltighet, medlemsbehörighet och tak. Av 121 historiska produkter kan 104 publika pris-/mängdavstämmas, 36 får diagnostisk audit PASS, 68 har låg semantisk säkerhet; 17 medlemserbjudanden spärras utan medlemskap. Detta är inte receptkvalificering.
- Komplett verkligt 15/20-par före sista flerköpsfixen: 563,17 kr i båda armarna, två ställen, ingen ICA-selektion/besparing. 42 namnmatchade/22 semantiska/8 individuellt näringsstödda/1 auditerad enskild receptkorg. Efter sista fixen hann bara före-ledet slutföras. Återstart 19 september stoppas korrekt av det frysta Primat-underlagets ålder. Ingen bakdatering/föryngring. Nytt komplett par med färska jämförbara källor återstår före release; kalla inte gamla paret slutkodsacceptans.
- 189 fokuserade tester, Ruff och compileall PASS. Aktiva universummanifestet är oförändrat; befintlig drift har själv förnyat Primat-cachemanifestet den 19:e. Historiska ICA-observationer är nu STALE och är inget aktiveringsunderlag. Fulla rådata, ID:n, osäkerheter och nästa blockerare finns i leveransen.

---

# Smako – 16 september 2026, ICA-inventering per område och inaktiv erbjudandepilot

[Leverans och kvarstående luckor](../reports/ica-area-20260916/README.md), [butiksvis täckning](../reports/ica-area-20260916/COVERAGE.md), [separat releaseförslag](../reports/ica-area-20260916/RELEASE.md). Befintlig branch/worktree `sources/lidl-ica-evaluation-20260914` användes; tidigare ej committat arbete är bevarat. Ingen produktionsaktivering, ny cron, deploy eller baspriskataloginsamling. Primat och befintligt publikt ICA-flöde kvar.

- Automatisk officiell inventering: Lund 12/12 resultat, 9 verifierade adressorter inom området. Linero 1004598, Söderlivs 1004339, Clemenstorget 1004409 och Tuna 1003391 finns med. Södra Sandby, Genarp och Veberöd ligger utanför den befintliga adressortsgränsen. Samma CLI med Malmö: 69/69, 21 inom adressort Malmö. Full offentlig kartprojektion kompletterar paginerad SSR-lista; ingen Lund-lista eller ny radie/postnummergräns.
- Färska offentliga Lund-svar 16 september 05:39–05:40 UTC, därefter offline v6-replay med oförändrade observationer: 631 poster, 609 parsade, 22 avvisade, 508 aktiva i sju isolerade OWN-snapshots. Söderlivs/Linero understiger oförändrad 95 %-gräns och är blockerade, inte tomma. Nio PDF-utgåvor/94 sidor hämtade; alla bildbaserade, kampanjextraktionen ofullständig. Torsdag 17/9 i Malmborgs/Brunnshög särredovisas från veckogiltighet.
- Frivillig ICA-provider återanvänder OWN, ProductMatcher, PriceUniverse, personligt medlems-/datumval, A/C:s `price=None`, korgberäkning och audit. 121 exakta produkt-/förpackningskandidater (104 offentliga, 17 medlem) införda; bara sju har individuellt näringsstöd i faktiskt prövade recept. Trasigt valfritt underlag blockerar inte basbygget. Default drift är oförändrad.
- Riktig identisk 15/20-profil före/efter: båda HTTP 201/VERIFIED, 783,03 kr, inga ICA-tillskott valda. HTTP 70,883/71,579 s. Brunnshögs verkliga tomater 500 g/30 kr följer separat hela kedjan till 300 g behov → ett paket/30 kr, godkänd audit. Ingen menybesparing påstås. 156 riktade offline-tester, Ruff och compileall passerar.
- Faktakontroll: alla 34 980 basposter och deras sakvärden finns kvar, nio identitetsfaktaposter tillkommer. Åtta basposter får dock ordinarie härledd `identity_variant`-flagga vid tillskottet. Faktamängderna är inte helt identiska; exakt differens finns i rapporten och är granskningskrav före release. Aktiva manifest och Primat-cache är hashstabila.

---

# Smako – 15 september 2026, ICA-pausen avgränsad till baspriskatalogen

[Kontroll av befintligt erbjudandeflöde](../reports/ica-offer-flow-check-20260915/README.md). **Pausen gäller blockerad direkt baspriskatalog/browserinsamling, inte befintliga publika ICA-erbjudanden.** Befintlig OWN-erbjudandeinsamling ska behållas. Sparad dygnskörning har 206 parsade/promoted offers_only-poster: Gunnesbo 138 och Södra Sandby 68. Aktivt PriceUniverse innehåller ett exakt matchat Stämmis-kontrakt (Falukorv, 2 för 65 kr), men det saknas i de tre förberedda ingredienskandidatindexen och produktens paketstorlek saknas. Kopplingen läser bara medlemspriser; publika icke-medlemspriser stannar i OWN. Clemenstorgets 73 erbjudanden finns endast i separat utvärdering och saknar aktiv OWN-butikssnapshot. Nästa steg är befintlig erbjudandeintegration/produktkvalificering, inte retry av blockerad baspriskatalog. Kontrollen var skrivskyddad mot produktion: inga ICA-/Primatanrop, browserförsök, refresh eller aktivering.

---

# Smako – 15 september 2026, Lidls två näringsluckor lösta och 15/20 verifierad

[Leverans, källor, körkommandon och pilotunderlag](../reports/lidl-nutrition-20260915/README.md), [jämförbara resultat](../reports/lidl-nutrition-20260915/comparison.json), [precisa meny-/korgavslag](../reports/lidl-nutrition-20260915/choice-quotes.json).

- ICA:s direkta baspriskatalog är pausad; befintlig publik ICA-erbjudandeinsamling berörs inte. Inga ICA-/Primatanrop, ingen aktivering, croninstallation eller ändrad användarprofil/butikskrav/färskhetsgräns i denna etapp. Arbetsgrenen används. Aktiva prisartefakter, Primat-cache, manifest, image och cron oförändrade.
- Exakt Allerum Grevé 28 %, 12 mån, 670 g (GTIN 7393720092442): tillverkare + Dabas styrker 27 g protein/100 g, med explicit 0 g kolhydrat. Kronfågel naturell lårfilé 900 g: tillverkarartikel 8028 och dokumenterad identisk förpackningsbild kopplas till Lidl GTIN 7300328028001. Tillverkar-GTIN inte oberoende belagt. Rå deklaration 20 g protein/100 g; kolhydrat <0,5 g bevarad som gräns, inte noll.
- Opt-in `reviewed_product_nutrition` binder två befintliga `ProductFacts` till exakt granskad produkt/förpackning/snapshot. Ingen ny generell databas. Befintlig varm insatsuppskattning får separat lårfilérecept: 200 g rå filé/person, all mat/sky serveras. Ingen bröstfiléreferens eller obelagd tillagningsfaktor. Gamla bröstfilérecept avvisar lårfilén. Näringsregistret laddas inte i produktion.
- Tre HTTP-körningar, faktisk schedulerimage/miljö UID 10001, nätverk avstängt: normal bas, kontrollerat Lidl-tillskott, normal byggning med Lidl före ingrediensurval. Original-SQLite/råunderlag + fryst Primat-cache, ingen återbyggnad via begränsad lokal sökprojektion. Identiska basprodukter/observationer, kod, request, fakta och inköpsdag 2026-09-15 verifierade. **Alla: 15 tillfällen/20 portioner, 40/30/20 g, två ställen, 793,03 kr, inga Lidl-köp.** Coop Online Syd 506,91 kr + Willys Lund 286,12 kr. HTTP 68,348/76,550/73,657 s; originalbyggningar 150,177/148,324 s. Sparade observationer fortsatt färska, ingen ny prisinsamling.
- Alla tre erbjudanden når pris-/ingredienskandidatstegen. Osten näringskvalificerad i fem recept. Lårfiléreceptet blir en elfte godkänd middagskandidat; en verklig enskild måltid väljer en 900 g-påse för 99 kr, 400 g rå användning, total tvåbutikskorg 131,57 kr och godkänd audit. Normalgenereringens 106 recept är annars identiska mellan armarna. Detta är inget helt-menysparande.
- Fast Lidl-ost kostar 79,90 kr för behovet 80 g, mot vald Coop-förpackning 43,50 kr. Den fasta hela menyn kräver Coop + Lidl + tredje ställe för köpbar vitkål. Prövade lårfilébyten stoppas av variation eller kombinationer där kvalificerat ris kräver tredje ställe. Noll tillåtna tvåbutikskombinationer för de loggade köpberäkningarna; ingen global omöjlighet eller optimalitet påstås. Sökgränserna är oförändrade.
- 105 fokuserade regressioner (16 nya), Ruff/compileall PASS. Kampanj/snapshotgranskningen gäller endast blad 01a0664a-ccb7-7278-a66f-8af0278032c3, 14–20 september. Ordinarie Lidl-priser förblir okända, offers_only, maxantal och datum intakta. Nästa separata beslut kan avse frivillig funktionspilot för exakt granskat tillskott; underlaget visar ingen besparing för 15/20. Nästa blad kräver ny tillämplig granskning. Ingen aktivering är utförd.

---

# Smako – 15 september 2026, Gunnesbos serverdiagnostik avslutad

[Slutlig dokumentkontroll](../reports/gunnesbo-document-check-20260915/README.md), [oskickade frågor till ICA och Primat](../reports/gunnesbo-document-check-20260915/kontaktunderlag.md). En verklig lucka fanns: tidigare full Chromium prövade startsida + produkt-API, medan 50-prisbeviset gällde SSR-sökdokumentet. Exakt en vanlig navigation till den observerade `/stores/1088004/search?q=mj%C3%B6lk` genomfördes i samma fungerande full Chromium/schedulerkonfiguration. **Huvudrespons 403, text/html, 919 byte, “Request blocked”, 2026-09-15 15:00:09 UTC**. Ingen initial-state-/produktprojektion i det nya svaret; inga efterföljande produkt-API-svar observerades. Inget gammalt sidtillstånd användes. Körning 1,121 s, UID/GID 10001, operationslås. Serverdiagnostiken stoppas nu; ingen ytterligare retry utan medgiven fungerande dataväg från ICA/driftansvarig. Ingen specifik policy, inloggningsplikt eller permanent omöjlighet är bevisad. Inga app-/connector-/A/C-ändringar, ingen aktivering/cron; Primat och aktiva prisartefakter oförändrade.

---

# Smako – 15 september 2026, avgränsad Gunnesbo-åtkomstdiagnos

[Rapport, kommandon och evidens](../reports/gunnesbo-access-20260915/README.md). Arbetsgrenen används; ingen aktivering, croninstallation eller ändring av A/C, butikskrav, färskhet eller användarprofil. Primat och aktiva manifest/artefakter är oförändrade.

- Tidigare 50-prisbevis kom från `mcp__cua_repl`, **Codex In-app Browser (iab)**. Browserversion, binär, fysisk körplats och ny kontext är inte belagda. Ny flik bevisar inte tom sessionshistorik; anta inte användarens lokala dator. Produkt-XHR:s body/status sparades inte då; prisbeviset var SSR-projektionen.
- Samma schedulerimage/cronmiljö rekonstruerar standardstarten som **Chrome Headless Shell 145.0.7632.6**, verifierat via den startade processen. Full Chromium av samma version får ett separat Crashpad-startfel i read-only-miljön; egen temporär XDG-konfiguration löser detta offline. Befintlig insamlare har opt-in `--browser-channel chromium`, inga cookieimporter eller skyddsbypasser.
- Slutkodens nya helt obemannade nätkontroll **12:46:33–12:46:38 UTC, 5,100 s**, UID/GID 10001, faktisk cronmiljö: butiksdokument GET 200, normal sökning, produkt-GET **403, text/html, 919 byte, “Request blocked”**. Bounded diagnostics läser granskade felmarkörer utan råbody/headers/sessiondata. Transporthash `5aff1f84…ce1b7e`, diagnostik `de3ffd47…d6f74` matchar slutkod. Stopp utan fler ICA-anrop. 0 produkter; aktuellt totalantal/täckning okända. Ingen traversal/queryutökning eller automatisk cronstart.
- Miljörättningen löser browserstart, inte produktåtkomst. Full Chromium ensam räcker inte. Exakt bakomliggande åtkomstpolicy/session-/nätorsak är okänd. Fortsättning kräver en av ICA/driftpartner medgiven fungerande produktprisväg för 1088004 online från servermiljön; ingen ny blind retry.
- Bevarad Primat-råprojektion: 1 848 Gunnesbo-/71 Clemenstorgetsposter saknar bevarat kanalbelägg; exportvitlistan utelämnade flera kanalfält. Gamla normaliserade `physical_store` är därför fortsatt **okänd kanalproveniens** för båda butikerna. Framtida parser/discovery/cache har frivillig `price_context_evidence` som skiljer explicit källvärde, saknat/okänt fält och tilldelning från default/butik/persistent kontext. Legacy-fält utelämnas; gamla kanaler/tider skrivs inte om. Inte aktiverat.
- 173 fokuserade tester, Ruff och compileall passerar. Offline browserprov med syntetiska svar körda i rätt cronmiljö; 0 retaileranrop. Aktiva prisartefakter/manifester, cron och schedulerimage jämförda oförändrade; operationslåset taget/släppt efter körningen. Inga ändringar utanför tillåten Primat-proveniens bland 300 jämförda befintliga arbetsytefiler. Ingen flerdagarsstabilitet påstås.

---

# Smako – 15 september 2026, kod och obemannad källtransport

Arbetsgren `sources/lidl-ica-evaluation-20260914`, bas `02ad73b`. Ingen kod-/källaktivering: live är fortsatt `price-recovery-lund-20260914a`, Primat och sex pris-/butikskontexter kvar. [Samlad kodleverans](../reports/smako-source-implementation-20260915.md), [A: 15/20](../reports/source-implementation-20260915/A-1520-reproduction.md), [B: Gunnesbo](../reports/source-implementation-20260915/B-gunnesbo-unattended.md), [C: erbjudandemodell](../reports/source-implementation-20260915/C-offer-only-model.md).

- A: historisk riktig request/artefakt reproducerad till 560,33 kr med fryst testklocka/orörda observationer. De 25 mallarna användes bara i täckningsanalys; planeringen hade 105 råa kandidater. Felaktig återbyggnad genom LocalPriceUniverseProvider tappade kvalificerade middagar, 10→6. Korrekta faktorkontroller skiljer detta från sökningen.
- A: septemberrequesten är möjlig. Begränsad beam tappade fungerande prefix. Slutkod deduplicerar likvärdiga genererade dagpermutationer och gör högst ett explicit 8→64-försök efter uttömning och prunade olika prefix, endast utan skafferi/produktlås. Näringsstartpunkter inom tillåtna butiksdelmängder tillkommer; näringsbudget 256 och alla användarkrav kvar.
- Slutkodens riktiga 15/20 genom isolerad HTTP, sparning och återläsning: 201/VERIFIED, 805,23 kr, alla 40/30/20, Coop Online Syd + Willys Lund. Bas 109,197 s och Lidl 121,335 s HTTP. Ingen ny 30-sekunders-prestandaacceptans. Detta är arbetsgrensverifiering, inte ändrad livefunktion.
- C: price=None stöds utan fabricerat ordinarie pris genom normering, prisavtal, optimering, audit, redigering och UI. Datum/inköpsdag och hela korgens köpgräns följer med. Inaktivt erbjudande hoppas över utan att stoppa giltig basprodukt; syntetiska regressioner täcker före/under/efter, paketkostnad, gemensamt tak, vald kampanj och ingen förbättring.
- C: samma tre exakt granskade Lidl-priser/vecka 38/14–20 sep, offers_only, fysisk destination Åkerlund och Rausings väg 1 Lund. Observationer 05:56 UTC oförändrade, inga nya Lidl-anrop. Alla 3 passerar matchning/semantik/shortlist; ost/kyckling når personlig resolve men saknar kvalificerad näring. Ostdeklaration saknas, lårfilé får inte låna bröstfiléns referens. Inga Lidl-köp: fullprofil 805,23 med/utan; middag 67,16 med/utan. Kycklingpaket 99 mot 43,90 är dessutom dyrare; prisjämförelsen ensam förklarar inte näringsavslaget.
- B: körbar separat Playwrighttransport/CLI och browserimage från exakt schedulerbas. Riktig obemannad nätkörning UID/GID 10001/faktisk cronmiljö: dokumentGET 200, verkligt sökfält, observerat produktGET 403 efter 5,045 s. 0 prisposter/0 batcher, aktuellt totalantal okänt. Ingen retry/bypass/cookieimport. Slutliga saneringshärdningar testade offline, live- och slutkodhashar redovisade separat.
- B: full pagination >50 testad med 83 tydligt syntetiska UI-produkter, inte nätbelagd. Aktuell riktig plan ger 12 behov/32 förekomster; frivillig lista med 13 sökord sparad, belagd obemannad täckning 0/12 på grund av 403, faktisk källtillgång okänd. online_price hålls separat. Primat physical_store kan komma från default och är metadataosäkerhet, ingen tyst omklassning. Clemenstorget kvar på Primat.
- Verifiering: 70 ICA-tester,283 tidigare erbjudande/kompatibilitet, efter slutlig resolvefix 49 riktade och 55 slutlig A/C-samkörning PASS (överlappar, summera inte). Ruff/compileall/node syntax/diffcheck PASS. Slutliga HTTP-kodhashar matchar arbetsgrenen. Aktiva manifest/cache/snapshotpekare/cron/36–48 h/sex krav oförändrade, health/ready 200; delade låset återtaget och släppt efter prov.
- Inget schema installerat; helt kommenterat frivilligt ICA-shadowförslag finns. 0 lyckade automatiska flerdagarskörningar observerade. Nästa separata beslut: kodrelease med explicit prestandabedömning; Lidl fortsatt inaktivt tills aktuellt granskat blad/näringsstöd/pilotbeslut; Gunnesbo tillåten produktåtkomst före skuggschema/källbyte. Null-artefakter kräver kompatibel läsare; framtida rollback måste först välja giltig basartefakt före äldre appbild.

---

# Smako – 15 september 2026, Lidl/ICA-datablockerare

Live och Primat är oförändrade. [Samlad leverans](../reports/smako-source-unblock-20260915.md), [Lidl-kandidat och planering](../reports/lidl-lund-candidate-20260915.md), [Gunnesbo/Clemenstorget](../reports/ica-gunnesbo-clemenstorget-20260915.md).

- Lidl: samma parser v4 och schemafixar. Ny riktig liveinsamling i faktisk cronmiljö/UID 10001, manuellt startad: 391/389/2 hämtade/parsade/karantän, 12,872 s, snapshot PASS. Slutkodens LF-normaliserade hash stämmer med körningen. Ingen promotion.
- Nationellt reklamblad vecka 38 belägger tre specifikt granskade förpackningar via råprodukt-ID/GTIN, variant/packbilder, sid-ID och villkor: Stjärnägg 15 st 41,90, Allerum Grevé 670 g 79,90, Kronfågel lårfilé 900 g 99. Ägg/kyckling max 3 förp./hushåll. Kvalificerat för 15 september kl. 12, offers_only. Alla övriga region-1-poster saknar denna nya bevisning. Ingen lagersaldogaranti.
- Verklig Lidl-destination Åkerlund och Rausings väg 1, Lund, kontext context:lidl:05f1cb3d9fc89bc3. Isolerad middag 2 portioner/minst 40 g protein, 22350/max 2 ställen: VERIFIED 67,16 kr med och utan Lidl; bara Willys Lund, inga Lidl-köp, ingen besparing. Större 15/20-profilens basarm fick befintligt PolicyConflict; middagstestet är inte återacceptans av hela betaprofilen.
- Lidl-kandidatens slutliga offlinekvalificering i cronmiljön ger exakt samma testade kandidat. Hårda köpgränser och datum spärrar gissat ordinarie restpris. Ingen direkt produktionsimport: äldre obligatoriskt Product.price används bara som scoped verifierat köppris i experimentet; produktion behöver säker befintlig erbjudandeprojektion utan självständigt ordinarie pris.
- Gunnesbo 1088004: normal anonym browser via officiell butikssida → e-handel → mjölksökning fungerar. 50 publika faktiska köppriser i SSR-productEntities, 232 sök-ID:n; endast 50 prisposter, inte komplett katalog. Befintlig ICA-parser/normalizer återanvänds av isolerad adapter. 50/50/0 prisposter; ingen godkänd global kandidat.
- Gunnesbo vs färsk Primat-cache: 36 retailerProductId-par, 35 belagda lika förpackningar, 36 numeriskt lika priser. Direkt onlinepris vs Primat physical_store: 0 fullt likvärdiga jämförelser. Tidsavstånd 3 h 42 min 48 s; ingen överföring av Primat-GTIN. Räkost 1023643 saknar mängd i Primat.
- Normala browserpriser belagda, men en vanlig httpx-GET av observerad söksida ger 403 vid dokumentsteget. Rå XHR-metod/body/status och fullständig pagination saknas i browserverktyget; exakt sanerat underlag beskrivs i ICA-rapporten. Ingen cookieöverföring eller challenge-bypass. Offlineadapterreplay i scheduler 0,012 s/0 nätanrop är inte liveinsamling. Noll automatiska flerdagarskörningar.
- Clemenstorget 1004409: officiell näthandel pekar på Caroli/Mobilia, egen direkt baspriskatalog inte belagd. Inga nya gissade mappningsanrop, inga främmande butikspriser; Primat kvar. Blockerar inte Gunnesbo.
- 168 distinkta fokuserade tester PASS, Ruff/compileall PASS. Sex butikskrav, 36/48 h, cron, aktiva manifest/cache och Lidl-snapshots exakt bevarade före/efter; health/ready 200. Ordinarie nattkörning före arbetet hade förnyat aktivt universum till 495742a1…1e7a. Inga experimentella aktiveringar, kodreleaser, scheman eller obligatoriska beroenden.
- Nästa separata beslut: frivillig Lidl-pilot efter datum-/antalssäker integration; Gunnesbo parallell transport-/täckningsverifiering före eventuell flerdagarsacceptans; Clemenstorget behåll Primat. Återställning enligt befintligt atomiskt manifest/LKG/lås, aldrig via för gamla priser.

---

# Smako – 14 september 2026, Lidl/ICA-källutvärdering

Live är oförändrad: `price-recovery-lund-20260914a` (app och scheduler).
[Samlad leverans och beslutspunkt](../reports/smako-source-evaluation-20260914.md),
[Lidl](../reports/lidl-repair-evaluation-20260914.md),
[ICA](../reports/ica-direct-evaluation-20260914.md).

- Arbetsgren `sources/lidl-ica-evaluation-20260914`, bas `02ad73b`. Ingen experimentell kandidat aktiverad, Primat kvar, inga nya obligatoriska beroenden eller ändrade butikskrav.
- Lidl: ursprunglig schemaorsak avgränsad, prisparser v4 rättar bland annat felaktigt styckpris från `4 för 22`. Sparade källsvar/regressioner. Slutlig liveinsamling 386/384/2 hämtade/parsade/karantän; slutåterspelning i faktisk scheduleranvändare/miljö healthy och snapshotvaliderad, 0 nätverksanrop, 3,490 s. Observationerna 14:23 UTC bevarade.
- Lidl är fortsatt `offers_only`, standardregion 1. Fysisk Lund-giltighet och breda ordinarie priser obelagda. 159 pågående, 224 framtida och 1 utgånget fönster; 8 kuponger med okänd målgrupp exkluderas. Preliminärt 4/35 publika och 1/35 medlemsvillkorliga ingredienskrav; 0 fullt belagda globala Lund-priser för aktivering.
- ICA: officiella butikskort verifierar konto 1088004/BMS 17883 och konto 1004409/BMS 2771. 138+73 publika erbjudandegrupper parsade; Gunnesbos verifierade online-rout 403, Clemenstorget saknar verifierad online-URL. Isolerad diagnostik v2 kräver denna mappning och kan aldrig aktivera. Fäladstorget ersätter ingen butik; tidigare `collect` oklassificerat eftersom request/svarsbody saknas.
- 14 exakta ICA/Primat-GTIN-identitetspar, 0 fullt jämförbara prispar; två avvikelser förklarade med officiellt kampanj-/referenspris. Receptpotential 8/35 respektive 9/35 krav. Primat är jämförelsekälla. Ingen bred baspriskatalog och 0 lyckade automatiska flerdagarskörningar; inget ICA-byte rekommenderas.
- Diagnostiken kördes manuellt i verklig cronmiljö/UID 10001 med delat operationslås, inte som automatiska cron-event. 422 distinkta tester PASS, Ruff/compileall PASS. Slutkontroll 14:30:57 UTC: samma manifest/universum `927c331c…f34f9e2`, samma 6 färska kontexter, health/ready 200, gränser 36/48 h och cron oförändrade. Ingen kodrelease, prisaktivering eller användardataändring.
- Föreslagen senare aktivering och återställningsplan finns i samlad rapport. Aktivera inget utifrån teknisk `healthy` ensam; gamla observationer föryngras inte av replay/bygg.

---

# Smako – 14 september 2026

Live: `price-recovery-lund-20260914a` (app och scheduler).
[Återställningsrapport](../reports/smako-lund-price-recovery-20260914.md).

- Planering 22350 återställd: alla sex Lund-kontexter färska, samma universum på disk/i process `927c331c…f34f9e2`, health/ready 200. Gränser 36/48 h oförändrade.
- Exakt kvalificerad basrequest: 15 tillfällen/20 portioner, 40/30/20, max två butiker. HTTPS mobilvy 201/40,781 s efter omstart, 560,33 kr VERIFIED; byte 200/7,092 s. Noll externa källanrop. Ingen ny treprovs-prestandaacceptans.
- Willys-transportens fel rättat via befintlig driftcontainer/UID. Båda kontexter importerade med äkta observationer. Verkliga Windows-tasken återtestad: resultat 0; schema 01:30 oförändrat.
- Primats historiska ValueError är fortfarande oförklarat. Två isolerade kompletta 49-anropskörningar passerade även parsning/export/validering/context activation. Godkänd färsk export användes. Ny steg-/stack-/orsaksdiagnostik bevarar nästa fel; ingen specifik historisk Primat-fix hävdas.
- Obligatoriska kontexter kontrolleras vid aktivering, planering och ready. Driftstatus varnar vid 36 h och visar rebuild-/aktiveringsfel. Separata Coop-erbjudanden, Karhögstorg och Lidl-fel kvar enligt rapport.
- 139 tester PASS, Ruff/compileall PASS. Backup `20260914T123547Z`; samma VPS, Caddy och miljöfilens rättigheter bevarade. Föregående app är läskompatibel rollback; föregående schedulerbild sparad.

---

# Smako – 13 september 2026

Live: https://beta.smako.nu/personal · `personal-v2-fast-403020-20260913c` · appkod `98381e5`.
[Prestandaacceptans och reproduktion](../reports/smako-fast-combined-403020-20260913.md).
[Föregående kombinerade funktionsacceptans](../reports/smako-combined-403020-20260913.md).

- **30-sekundersmålet PASS.** Fryst request-kall beräkning 357,670 s (före n=1) → median 26,480 s (efter n=3). Slutrelease genom HTTP: 27,047 / 27,462 / 28,007 s, median 27,462 s, tre nya gäster och ingen färdig resultatcache.
- Middag 5×2 ≥40 g, frukost 5×1 ≥30 g, mellanmål 5×1 ≥20 g per portion. Totalt 15 tillfällen, 20 portioner, Blandad/Balanserad, max två inköpsställen gemensamt. Spårbara uppskattningar uttryckligen på enligt denna milstolpe. Inga extra kcal-, fisk-, eko- eller skafferikrav.
- Samma frysta priser/fakta ger exakt samma meny, kostnad 574,92 kr, variation och kravkontroller. Kandidatpooler 95/5/5 råa och 10/2/2 kvalificerade, sökbredd/policy/prismotor oförändrade. Request-lokal exakt näringsmemoization, ren textcache och hashverifierad offentlig faktacache ersätter upprepade beräkningar. Admission omfattar faktisk arbetstråd även vid avbrott.
- Processkall ASGI till resultat 48,537 s; varm HTTP 27,124 s. Mobilformulär via HTTPS 28,760 s med laddad katalog; första efter omstart 33,224 s. Byte dag fyra 4,562 s, hel korg 584,92 kr och alla 40/30/20-krav kvar. Browserprov 390×844; fysisk telefon/mobilnät inte mätt.
- Två samtidiga isolerade planer 27,301/55,544 s; en aktiv/en i kö, sök/health <0,16 s, korrekt ägarisolering, inga kvarvarande arbetare. Dubbelklick gav en POST; navigation/timeout gav inga automatiska retries. Befintliga 600/540 s timeoutgränser oförändrade.
- 477 distinkta fokuserade regressioner passerade; 79 berörda upprepades efter sista adapterändringen. Ruff/compileall PASS. Separata A/B/C, uppskattningar på/av, ändrat protein/portioner/skafferi, paket/kampanj, färskhet, köp/revisioner och isolering kontrollerade. Strikt A/D fortsatt datablockerat; B/C fungerar utan uppskattningar.
- Backup `20260913T194832Z`; 164 äldre revisioner hashbevarade, nu 168. Health/ready 200; scheduler och prismanifest oförändrade. Läskompatibel rollback till `personal-v2-fast-403020-20260913a` verifierad utan databasrestore. Mellanbild b aktiverades aldrig.
- Kvar: gemensam näringsalternativ-/paketsökning (7 335 korgoptimeringar), första råfaktaladdning, befintligt begränsad sökning, strikt middagsunderlag och okänd slutvikt. Inga nya källanrop, observationstider, recept, OIDC-, Willys-task/relay-, server- eller tjänsteändringar.
- Tidigare [fiskfria acceptansen](../reports/smako-fishfree-five-dinners-20260913.md) är historik och får inte ersätta 40/30/20-profilen.


## 2026-09-20 structured ICA release — blocked before activation

User authorized production release of structured ICA offers and campaign-driven refresh, no images/paid models. Continued on sources/lidl-ica-evaluation-20260914, HEAD 02ad73b with all previous dirty work retained; pre-edit archive in reports/ica-structured-release-20260920/prework.tar.gz.

Read reports/ica-structured-release-20260920/README.md, RELEASE.md, COVERAGE.md, CONTROL.md, PROFILE.md and release-gate.json before resuming. Concrete code/image ica-structured-lund-20260920a prepared, not deployed. Fresh final collection 2026-09-20 10:37–10:38 UTC: 12 discovered/9 inside strict official-address Lund locality; 654 offers, 155 row-approved OWN, 154 isolated PU, remaining quarantine preserved. Gaständare is the one extra OWN→PU rejection: normalized sold_by_piece conflicts with existing strict offers_only fixed-package contract; see exact retained error, not a generic nonfood exclusion.

Normal publication previously failed IneligibleMemberPriceError for two public Willys products whose independent public/member amount happened to coincide. Reused the existing dirty-tree fix and real source regression. Also fixed optional offer combinatorial overflow: unchanged 200000 exact limit, precomputed search size, same optimizer can return independently verified baseline with explicit warning instead of optional additions blocking it. New campaign evidence preserves null start, original observation and explicit end; bounded campaign policy distinct from unchanged base 36/48h. Durable 15-minute due checker reuses managed refresh/locks. Source promotion fingerprints, campaign transitions, row-only OWN inputs and 35h base deadlines covered. Willys local timer is independently owned and not falsely advertised as campaign-coalesced.

Final same-input real 15/20 HTTP tests PASS: without additions 560.33 SEK / 38.422s; with additions 560.33 SEK / 39.253s. 15/20, 40/30/20g, max2, membership off unchanged. 15 individual nutrition-supported products, none of the new ICA products selected. Actual separate matcher→checkout→audit proofs PASS for Linero mushrooms 250g/15 SEK, Söderlivs pizzakit 600g/19 SEK and mushrooms/20 SEK, Gunnesbo oats TWO 1500g packages/30 SEK; ordinary price null. Full isolated managed publication and restart/no-due/no-network PASS. 150 regression tests, last affected optimizer 28 rerun, last affected scheduler/relay 20 rerun, Ruff/compileall PASS.

CRITICAL EXTERNAL GATE: Set-ScheduledTask updating existing Smako Willys Local Relay action/trigger returned Access denied. Original daily task was re-enabled and verified unchanged. No server env/current link, price manifest, or cron changed. Existing beta remains version price-recovery-lund-20260914a, active PU 4832eaa0... built Sep16, health200/ready503. Production backup succeeded 20260920T104654Z; private env backup /opt/smako/rollback/ica-structured-lund-20260920a/. Inactive local relay export D:/smako-local-relay/releases/ica-structured-lund-20260920a. User was asked early to run configure-relay-admin.ps1 as Windows administrator; it configures the SAME task disabled pending coordinated release. No secrets requested. Waiting for this external permission/configuration; do not silently treat old daily relay as satisfying the new demand-policy gate.

production_ops.py activate checks actual task configuration before contacting deployment, and artifact/code/current campaign-day gates before stopping scheduler. Activation/switch/live_verify.py remain UNEXECUTED. User data untouched. Never reactivate stale Sep16 manifest as rollback: use newly validated compatible fresh baseline instead. If campaign day, code or source freshness changed, repeat affected fresh collection/acceptance before activation. Do not reuse today's PASS after midnight as current campaign evidence. No multiday stability claim.


# 2026-09-20 — separate municipality/source-audit branch

New work ONLY in C:/Users/ossia/Documents/Codex/2026-09-16/municipality-coverage-20260920, branch areas/municipality-audit-20260920. Inherited dirty baseline preserved; pending ICA release in original directory untouched. See reports/municipality-offers-20260920/README.md, SOURCES.md, NEXT.md, RELEASE.md and incremental.patch.

Opt-in municipality mode uses official SCB 2026 codes plus evidence-bound explicit retailer administrative addresses. Legacy locality remains default. Live ICA Lund 12 included vs 9 locality; Malmö 24 included, 10 outside, 35 unknown among 69 discovered. Four missing Malmö-locality addresses enriched via original transport; exact cross-query address evidence reused without renewing source time. Lantmäteriet metadata200 but geometry401: no coordinate membership fallback. All other-chain 50 physical candidates retained with unknown municipal membership.

Fresh bounded Windows source checks reused Willys/Hemköp/Coop/City Gross/Lidl connectors; public/group/member prices exist without images. 24 sample prices reported with raw IDs/time/terms and read-only OWN/active-PU comparison. Coop text loses periods, variant identities and full conditions (Yoggi not lactose-free), plus eight public prices acquire unproven ordinary role: recommended one next connector-local fix, NOT implemented or activated here. Hemköp applied=true vs offerStatus=Vilande flagged. Active beta PU remains Sep16; no fresh planning acceptance claimed, no prices/config/schedules/tasks changed. Municipality completeness explicitly partial; no new production activation proposal approved.


## 2026-09-21 — Coop physical offers correction, isolated only

Continued in areas/municipality-audit-20260920, same separate worktree. See reports/coop-physical-fix-20260921/README.md, COVERAGE.md, EXAMPLES.md and RELEASE.md. Existing browser now retains public DKE response with exact physical store/ledger, source hash/time and opaque variant IDs (not fabricated GTIN). Coop parser v3 preserves campaign/member/group roles, dates, packs and exclusions; ordinary price stays null. Existing SourceOffer → row-approved collector/OWN → PriceUniverse reused; explicit partial contract, full 95% gate and 36/48h unchanged. Online 730400 remains separate.

Final actual Windows collection Sept21 09:44 Stockholm: Flöjtvägen 22 groups/135 variants, 44 approved/91 quarantine; Bulltofta 56 groups/356 variants, 68 approved/288 quarantine. 112 isolated PU products, no active-beta change. Proportion/full snapshot remains broken; row candidate explicitly partial. Percentage lamps (74 variants) preserved without monetary purchase price. Newly observed isPil flag remains unresolved: 13 variants quarantined, 9 would otherwise qualify; do not reuse preliminary 77/121 totals as final.

Final acceptance uses final-live-v2 sources unchanged and final-acceptance-v2. Pasta 300g/15 SEK and member mince 500g/59.90 (max3) pass checkout/audit in both stores. Flour 2x2kg/26 SEK charges correctly but recipe audit fails LOW semantic confidence; not forced through. 184 regression tests pass, affected 22 rerun after lint-only refactor; Ruff/compileall pass. No full 15/20 or savings claim. Source times never renewed by replay. No server-runtime acceptance claimed.

Original pending ICA worktree 139 inherited file hashes and 415 release hashes verified unchanged. No production, Windows task, scheduler, server configuration, Primat or ICA-base-pause changes. No images/paid calls. Release proposal is separate and requires future fresh runtime/compatibility acceptance and explicit activation decision. Baseline archive plus incremental.patch separate these changes from inherited uncommitted work.


## 2026-09-21 — bounded Coop closeout, no activation

See reports/coop-closeout-20260921/README.md, QUARANTINE.md and RELEASE.md. Previous 112-price release artifacts retained unchanged. Classified all 379 quarantine variants: Flöjtvägen 78 food/10 groups +13 other/1; Bulltofta 185 food/31 +103 other/9; no unknown titles in this reviewed sample. Primary causes are disjoint per variant; overlap tables deduplicate repeated error codes. Prior package-error counts 14/18 were occurrences, actually 7/9 unique variants. isPil 13 variants spans 8 groups, correcting previous prose.

Small source-proven alias fix: Kärnvetemjöl parent Vetemjöl now matches recipe vetemjöl. Narrow visible-name gate rejects other flours/mixes even with incorrect structured identity. No nutrition, GTIN, ordinary prices or pantry assumptions added. Original flour audit bypassed matcher; old exact Kärnvetemjöl query already matched, ordinary vetemjöl rejected. before-matcher.json reproduces that with archived old modules. New actual same-source collector→OWN→PU→matcher→checkout→audit passes all six proofs; flour 2x2kg/26, no one-pack13 rest price. Approved totals remain44/68, quarantine379 unchanged; no new import claims. Nutrition-backed 15/20 still unverified.

324 focused/regression tests PASS18.46s; 18 affected tests rerun5.14s after import ordering; Ruff/compileall pass. No external fetch this closeout: original Sept21 09:44 source times retained, isolated verification at17:17 Stockholm3.385s. No production/Windows/schedule/config changes, no other chains, images or paid calls. Keep this additive closeout patch separate from both prior Coop patch and waiting ICA release.

## 2026-09-21 — Coop municipal store coverage, isolated only

Same separate worktree/branch. See reports/coop-municipality-20260921/README.md,
COVERAGE.md, EXAMPLES.md, RELEASE.md and coverage-final.json. National official
Coop map720 + X:-tra58 =778 store rows; SCB RegSO2025 position test yields Lund10
inside (9 Coop/Stora,1 X:-tra),768outside,0unknown. This follows municipality
boundaries2025-01-01, not address locality; Genarp/Veberöd included. No independent
business-list completeness claim. Same code offline Malmö18inside/759outside/
1unknown, preserved. Legacy area modes and user store selection unchanged.

Fresh individual physical feeds Sep21 19:55–19:58 Stockholm:499 OWN/isolatedPU
variants from2436, quarantine1937,372 store-campaign groups. Every full snapshot
still below95%; explicit row-approved contracts only. Previous112-artifact preserved;
Bulltofta outside Lund. 44 Flöjtvägen overlap;455 additional store-variant posts.
Map/StorePage account string/int comparison fixed without relaxing exact identity.
Stora source ageRestriction/simplifiedAgeRestriction retained and23 rows blocked;
unknown shared schema fields still fail closed. Existing isPil/deposit/group guards
unchanged. Same source campaign family+period conservatively shares household cap
across stores, never shares prices or grants store applicability.

Source→OWN→PU→matcher→checkout/audit:27 real ingredient proofs. Actual optimizer
max2 stores Genarp flour26 + Veberöd pasta15 =41 SEK, auditPASS. Cross-store2+2
mince packages rejected against sharedmax3;2+1 allowed. 356 testsPASS33.36s;
Ruff/compileallPASS. No nutrition-backed menu/savings/server-runtime claim.
OWN legacy postcode helper rejects247xx; isolated verification uses existing
/stores by known source locality + exact source ID and normal provider.get_offers,
not fabricated postcodes. Future beta area selection must consume explicit inventory.

X:-tra3658/account216525 official link -> eight PDF text pages all fetched.
Status document_text_unintegrated,0imports,advertisementcountunknown, not empty
and not image-only. Page8 validThu24–Sun27, notMonday. No image/paid API.
Primat, Online730400, ICA-basepause, pendingICApackage, production, userprofiles,
Windows task/schedules/serverconfig unchanged. Separate release proposal only.

## 2026-09-22 – X:-tra retained PDF text import, separate partial candidate

Same municipality worktree/branch; reports/xtra-text-20260922/README.md and
RELEASE-COOP.md / RELEASE-XTRA.md are the latest bounded delivery. No deployment.
New opt-in coop-xtra-pdf-text-v1 uses existing PyMuPDF text spans/grid and original
source binding, no OCR/model/API. SourceOffer → collector → partial OWN → normal
provider/PU → matcher/checkout/audit. No GTIN or ordinary price fabrication.
Source PDF Skansvägen3658/account216525 SHA065efd248050a6761a45adad7695186048484f76e9d6d1aebe05f18458c4aa18,
observed2026-09-21T17:56:02.943342Z, week39 Sep21–27; page8 Sep24–27 only.
Final actual local-time verification Sep22 07:46:32, age11.842h, runtime1.892s.
8 pages,57 detected textual ads,10 approved OWN,9 current PU,1 future,47 blocked.
Unknown additional image ads remain unknown; not complete flyer coverage.
Fullsnapshot10/57 remainsbroken;95%unchanged. Couscous15, tomato2x200g30,
onion3kg19.90 matcher/checkout/auditPASS. Honey30 priceimported, ingredientmatch
blocked. No nutrition-backed menu. Future cappedmemberads blocked pending
verified cross-store campaign identity; PDF hash is not shared household evidence.
125testsPASS49.55s; finalaffected20PASS16.58s includes1newtest; Ruff/compileallPASS.
Coop499approved/1937quarantine preserved, replay25auditPASS21.077s. CurrentPU493:
six Stora meal variants expiredSep21 (exact IDs in expired-difference.json), not lost.
Previous27proofs preserved;2additionalStora proofs reused hashstable, not newnetwork.
Separate Coop release remains independent of Xtra; real unchanged15/20 with fresh
frozen base arms/nutrition/max2 is still pending. No external calls/production writes.
Primat, pendingICA, users, Windows/schedules/serverconfig unchanged.


## 2026-09-22 – municipal Coop controlled 15/20, no activation

Same isolated municipality worktree/branch. Latest decision:
reports/coop-1520-20260922/RELEASE-COOP.md, PROFILE.md, COVERAGE.md.
New optional CoopMunicipalityOfferProvider and two explicit builder arguments
coop_offer_database / coop_municipality_inventory reuse collector/OWN/full-source
builder; official municipal IDs include Genarp/Veberod without changing profiles.
Exact physical contexts, Online730400 separate, household cap IDs retained.
Missing/corrupt optional source retains baseline with diagnostic. No drift wiring.

Fresh actual server browser collection Sep22 06:39:02-06:39:38 UTC:
9 stores,493approved/1937quarantine. Six Stora day-only Sep21 rows remain excluded.
Uses pre-existing smako-ica-shadow:20260915 Python3.12/Playwright runtime; prepared
ordinary scheduler image lacks playwright. No installation/production changes.
Full live source DB+validated Primat frozen08:32:48 Stockholm under shared lock;
latest ordinary live collection, not an extra full-base crawl or search projection.
Oldest usable base CoopOnlineSep21T01:17:55Z (<36h); same exact fullsources botharms.

Final real HTTP A/B, identical request hash0bac8f0da2dfdaa922dfacc9a57527ff4c083d2d987ceba3ea242d11619b7d6c,
identical application code/baseproduct hash/nutrition facts and106 frozen recipes.
15slots20portions40/30/20,max2,membershipsOFF,existingallow_nutrition_estimates unchanged.
A536.27 SEK,HTTP40.440s,total215.421s; B536.27 SEK,HTTP43.731s,total234.415s.
Same CoopOnlineSyd+WillysLund, zero municipalCoop selected.493retainedprices,
22actualproductnutritionlookups,0supported: verified product facts/identity missing.
No guessed GTIN/nutrition.332Bbasket auditsPASS;both201+identical savedreadback,
health/ready200,privateidentity/planDB,networkdisabled.141regressionsPASS14.578s.
No demonstrated saving; not ready as a verified15/20 improvement. Separate
browser-enabled Coop deployment integration still required; do not deploy dirty
worktree/pendingICA package wholesale. Xtra is independent and not a blocker.
Production already refreshed overnight toSep22 before this task; originalimage
price-recovery-lund-20260914a remains, same active manifest, users/schedules unchanged.
Rollback and publication fault evidence: server-results/publication-result.json.
No production activation, Windows/schedule/server configuration/image/model changes.


## 2026-09-22: Coop-näring och separat browserpaket (ingen aktivering)

Fortsatt i `areas/municipality-audit-20260920`, bevarat ärvt/ocommittat arbete.
Se `reports/coop-nutrition-20260922/README.md`, `22-POSTER.md`, `PACKAGE.md` och
`RELEASE-COOP.md`. 22 tidigare näringsprövade rader = 7 källvariant-ID:n.
Strikt faktaöverföring via befintlig Coop-katalogidentitet/variant/förpackning
(ingen prisöverföring eller ny GTIN), bibehållna näringsgränser och smala
plommontomatalias: 14/22 nu näringskvalificerade, åtta färska pastor spärrade.
Samma fullständiga frysta baskällor/faktaversion i slutlig 15/20 A/B: 536,27 kr
båda, samma 12 produkter/2 kontexter, noll valda fysiska Coop-rader. Separata
Cheddar/Gouda-receptprov klarar näringskrav och checkout/audit; högre paketkostnad.
Nio färska flöden: 493 godkända/1937 karantän. Slutlig separat serverimage
`smako-coop-candidate:nutrition-20260922` (hash i PACKAGE), UID 10001, befintlig
Playwright/Chromium, operationslås, inga kodoverlay, verklig begränsad hämtning.
125 fokuserade tester + Ruff/compileall PASS. Privat publicering/rollback PASS.
Redo för separat tidsbunden aktiveringsprövning; ingenting aktiverat. Giltig
rollbackbas stoppar 2026-09-23 03:17:55 Europe/Stockholm, varning 22/9 15:17:55.
Ny kontroll/insamling krävs efter tidsgräns. Primat, produktion, väntande ICA,
Windows/scheman och X:-tra är oförändrade. Inkrementell patch utgår från denna
etapps säkerhetskopierade smutsiga arbetsläge, inte från ren HEAD.


## 2026-09-22 – bestående kommunacceptans Coop/Stora Coop/X:-tra

Separat arbetskopia/gren oförändrad. Se `reports/coop-municipal-contract-20260922/README.md`, COVERAGE.md och RELEASE.md. Samma kod har körts med officiella kommunkoder 1281/1280, färsk inventering av 778 upptäckta butiker per prövning. Lund 10 inne/0 okända; Malmö 18 inne/1 okänd (X:-tra Kirseberg 3548, gränsnära). Alla rader finns i STORES-1281/1280.md.

`approved_municipal_stores` binder om kommunbevis i urval/provider/X:-tra-import; sparat inside räcker inte. `collect_coop_municipality` kopplar befintlig strukturerad insamling och befintlig PDF-textimport till isolerat OWN/PriceUniverse. X:-tra-länkar upptäcks ur varje aktuell officiell butikssida; inga fasta Skansvägen-/Lundutgåvor. `coop_municipal_refresh.update_selection` återanvänder kampanjpolicy, sparar omstarts-/retrytider och behåller alla butiker. Inget förfallet arbete ger noll prisanrop och ingen tom ersättningskandidat.

Färsk 22 september: Lund 493 strukturerade + 9 aktuella X:-tra-poster; Malmö 532 + 9. Separata X:-tra-PDF:er Skansvägen/Söderkulla, vardera 8 sidor/57 identifierade textannonser/10 OWN (1 framtida)/47 karantän. Texttäckning är partiell, okänd layout/bildannonser är inte noll. X:-tra Nydala saknar weeklyOffersLink. Malmö har dessutom tre ConnectorFetchError samt två gemensamma invalid offer quantity-fel (Stadion/Jägersro). Spärrar bevarade. Slutkod återspelad offline med exakt samma observationer/antal; checkout/audit för tre X:-tra-ingredienser per butik PASS. 105 unika berörda tester, Ruff/compileall PASS.

Ingen produktion, användarprofil, server, Windows eller scheduler ändrad. Tidigare Coop-näringspaket och väntande ICA-release bevaras separat. Ny kommunorkestrering har verifierats lokalt, inte byggts in i serverimagen; se RELEASE för återstående server-/aktiveringskontroller. Tidigare 15/20=536,27 kr per arm är oförändrat historiskt bevis, inte en ny körning för Malmö/X:-tra.


## 2026-09-22 – samlat Lundsunderlag och faktisk driftlucka

Senaste underlag: `reports/coop-lund-activation-20260922/RELEASE-LUND.md`, decision.json och UPDATES.md. Ingen ny inventering/aktivering/schema-/Windows-/serverkonfigurationsändring. Ny separat slutimage `smako-coop-candidate:lund-activation-20260922`, SHA00fd55cc75d824dfcfb1aa2c6abbee882c0af95a574ad190c2a6932db0064622. Paketet innehåller senaste kommun-/pris-/näringskod, CLI, BeautifulSoup/soupsieve/PyMuPDF-pins samt befintlig browser. Inga runtimeinstallationer i produktion.

Färsk serverinsamling nio Lunds-Coop:493 OWN/PU,1937 karantän, inga gemensamma kritiska blockerare. Skansvägens aktuella PDF upptäckt/hämtad i slutpaketet:10 OWN/9 aktuella PU/47 karantän, separat valfritt tillägg. Befintlig full builder tar fortfarande bara Coop/Stora; Xtra exkluderat ur fullkandidaten.

Fullständiga baskällor nyfrysta under operationslås, byteidentiska med tidigare underlag/cache. Full Coop-kandidat b893fb0448ca2e70d6a7e5a980dbf740fb3b8727ed8fb1b6b9d8b63eccdd2888 passerar befintlig privat publicering, lineage-/invalid-/stale-rollback-felprov och återstart. Produktionsmanifest oförändrat. Slutbildens riktiga15/20:536,27kr,HTTP201,43,949s HTTP/91,272s totalt,332 audits,sparning/återläsningPASS,inga fysiskaCoopval. 78 unika berörda tester+Ruff/compileallPASS.

Rättad releasepolicy: Coop/Xtra saknar ICA:s kampanjundantag från48h. Begränsa därför lyckad källas nästa hämtning till35h, behåll36hvarning/48hstopp, tidigare kampanjbyte och retry. Serverpolicyprovet verifierar omstart/15min-felretry. Beräknad nästaCoop23/9cirka22:28, Xtra22:34; inget installerat. Bas35h22/9 14:17:55, varning15:17:55, stopp/rollback23/9 03:17:55 Stockholm. Faktiskt oförändrat cron03:17nästa dag ger bara55sek marginal tillstopp och är inte tillräcklig säker insamlingsmarginal.

INTE REDO FÖR ÅTERKOMMANDE AKTIVERING: grocery_data.__main__._build_production_price_universe skickar ännu inte coop_offer_database/coop_municipality_inventory till byggaren; run_daily_refresh läser inte kommun-Coop:s beständiga källpekare/uppdateringsurval. Engångsartefakt fungerar, nästa normala rebuild riskerar tappa tillskottet. Nästa avgränsade kodsteg: explicit avstängd koppling av godkända källor+kommuninventering+durabelLKG/version till befintlig rebuild/publicering/reload, andra-rebuild/fel/omstartstester. Xtra kan fortsatt lämnas avstängt; Malmöfel är källbundna och ska inte blockera nio Lundsbutiker. Ingen aktivering före nytt beslut.

Testutrymmet i /tmp(tmpfs) blev fullt vid första backupen. Endast denna körnings data flyttades intakta till /var/tmp/smako-coop-lund-activation-20260922; ofullständig backup är bevarad i failed-base-disk-full. Ingen rensning av äldre data. Där lyckades full backup; datadisken har gott om plats. Primat, betan, användarnas val och väntande ICA-release bevarade.


## 2026-09-22: Coop/X:-tra i ordinarie refresh/rebuild (ingen aktivering)

Separat arbetskopia `municipality-coverage-20260920`, gren
`areas/municipality-audit-20260920`; tidigare ocommittat arbete är bevarat.
Underlag: `reports/coop-refresh-integration-20260922/RELEASE-COOP-REFRESH.md`.
Inkrementell patch jämför mot denna körnings säkerhetskopior, inte mot HEAD.

Ordinarie `run_daily_refresh.py`/`grocery_data daily-refresh` tar nu kommunens
förfallna källor genom befintlig collector/OWN och läser beständiga godkända
källreferenser vid varje efterföljande PriceUniverse-build. Kommunval, valfri
X:-tra-flagga, samtliga butiksstatusar, relativa snapshotreferenser med hash,
uppdateringstider och separata publicerings-/reloadkvitton sparas atomiskt under
`COOP_MUNICIPAL_OFFERS_ROOT` (standard bredvid grocery-databasen).
`docs/coop_refresh_integration.md` beskriver kontrakt och konfiguration.

Slutimage: `smako-coop-candidate:refresh-integration-20260922`,
`sha256:73371776b99a8b240435e2d575473d746bda5f694d1b3a6a485273be2ff12924`.
285 moduler hashverifierade. Appkod var inte monterad från utvecklarkatalog.
Privata beständiga serverdata: `/var/tmp/smako-coop-refresh-integration-20260922/data`.
Detta testunderlag innehåller även märkta felinjektioner och får inte kopieras
som produktionsstate.

493 fysiska Coop-poster behölls över basrebuild och omstart. Verklig Primat-
uppdatering, kontrollerat hämtfel, verklig återhämtning och X:-tra av/på
(493/502) verifierades. Slutkoden verifierade normal parser/collector för ett
uttryckligt muterat nollsvar: bara Värpinges 55 poster återkallades. Testad
framtida köpdag i Coop-provider gav noll Coop-avtal med giltig bas kvar;
observationer ändrades aldrig. Verklig återhämtning gav åter 493 poster.
Reloadfel gav separat väntestatus; efterföljande riktig reload lyckades.
Privat publicering/rollback, avvisad ogiltig artefakt och avvisad för gammal
rollback passerade.

Slutkodens efterföljande rebuild + riktiga 15/20-anrop: 536,27 kr,
50,288 s, HTTP 201, 332 passerande audits, identisk sparning/återläsning.
Max två inköpsställen, oförändrade 40/30/20-krav och samma receptpool.
Näringsreferensversion och valda näringskontroller är identiska med B2;
katalogens samlade facts_version skiljer sig mellan de nya insamlingarna.
Detta är ingen ny parad besparingsjämförelse. 202 unika regressioner,
Ruff och compileall passerade.

Redo för separat aktiveringsbeslut, inte aktiverat. Förberedd
`deploy/coop-runtime.override.yaml` har endast konfigurationskontrollerats.
Ny färskhetskontroll, förfallen basinsamling och kodkompatibelt giltigt
rollbackunderlag krävs vid faktisk aktivering. Kontrollens äldsta basobservation
är 2026-09-21 01:17:55Z; hårt stopp 2026-09-23 01:17:55Z. Rapportens byggtid
föryngrar inte detta. Se aktuella per-källa-tider i `decision-state.json`.
Ingen Windows-, aktiv scheduler- eller produktionsändring; väntande ICA-release,
Primat och användarval är bevarade. Malmö-/X:-tra-formatluckor hålls separata.

## Willys kommunstöd 2026-09-22, slutkontroll 2026-09-23

Fortsatt separat arbetskopia `municipality-coverage-20260920`, gren
`areas/municipality-audit-20260920`. Befintligt ocommittat ICA/Coop/X:-tra-arbete
bevarat. Ingen produktions-, Windows- eller aktiv schemaändring.

Willys har explicit kommunurval från hela officiella registret och SCB RegSO 2025,
samma kod för Lund 1281 och Malmö 1280. Alla 258 registerrader kvarstår: 257
namngivna butiker och okänd rad 2002. Lund 3 kommunbutiker varav 2 online,
Malmö 10 varav 4 online. Priserna är butiksknuten online_price, inte belagda
fysiska hyllpriser. Sju butiker saknar verifierad transport i denna väg.

Ny persistent relay `source-scope.json` och serverinställning
`WILLYS_MUNICIPAL_CONFIG` styr ordinarie import/byggare; ingen fast butikslista.
Självständig kommun-/sidvalidering i source artifact. OWN-matchning behåller
exakt butik, fysisk identitet och kanal även över adressorter; ett faktiskt
postnummerformatfel är rättat. Saknad godkänd butik stoppar nu publicering.
Oförändrad prisparser, medlemskap, 35h behovsstyrning och 36/48h-gränser.

Lund: 18 824 käll-/OWN-poster, 18 642 i PriceUniverse. Ordinarie privata
refresh/rebuild/publicering/reload, andra rebuild och omstart ger identisk
prispostsignatur; 493 Coop-poster bevaras, health/ready 200. Riktiga ursprungliga
Willys-observationer 21/9 23:31–23:59Z återanvända utan föryngring.
Malmö: ny faktisk insamling 22/9 16:18–17:11Z, 39 274 OWN-poster och 38 950
i OWN-only PriceUniverse. Samma import och produktionsbyggare efter omstart
ger identisk prispostsignatur. Ett fullständigt federerat Malmö-publicerings-
och reloadprov med aktuell komplett Primat-bas återstår; det har inte ersatts
med Lunds bas eller sökprojektion.

180 regressioner passerar, Ruff/compileall passerar. 276 paketerade Python-filer
hashjämförda utan avvikelse även efter återupptagandet. Två verkliga relästarter
utan förfallet arbete gör noll externa anrop. Explicit +49h-test spärrar gamla
Willys-kontexter. Ingen ny 15/20-jämförelse eller besparing påstås.

VIKTIGT vid fortsatt releasebeslut: 23/9 cirka 08:08 Stockholm är Willys-källorna
fortfarande under 36h, men en annan baskälla i gårdagens privata Lund-testbas
är nu över 48h och spärras (`degraded`, en utesluten kontext). Den gamla basen
är inte giltigt aktiverings-/rollbackunderlag utan förfallen uppdatering.
Nästa beräknade Willys-hämtning: Lund 23/9 12:31, Malmö 24/9 05:18 Stockholm;
ingen ny skarp körning installerad. Skarpt manifest ändrades över natten utanför
denna uppgifts privata tester; endast läskontroll utförd.

City Gross: befintlig full onlinekatalog/OWN/PriceUniverse finns redan;
kommunbevis och genererat storeNumber/siteId-urval återstår. Lidl: befintligt
offers_only-flöde och nationell bevisväg finns, men kommun-/regiongiltighet
måste knytas till faktiskt omfattade butiker och aktuella kampanjer.
Ingen ny bred kedjeinsamling eller parserombyggnad gjord.

Se `reports/willys-municipality-20260922/{README,COVERAGE,CHAIN-STATUS,VALIDATION,RELEASE}.md`,
`decision-current.json`, samtliga registerrader i `ALL-STORES.md`,
före-läget i `initial-state.json`/`backups` samt avgränsad patch och filhashar.
`deploy/willys-municipality.override.yaml` är förberedd, inte applicerad.
Väntande ICA-release och dess operatörssteg är fortsatt separata.

## 2026-09-23 – City Gross kommunstöd, separat kandidat utan aktivering

Ovanstående City Gross-lucka är nu implementerad i samma kommunfunktion:
officiella PageData/sites → SCB RegSO → exakt storeNumber/siteId → befintlig
onlineconnector → OWN → PriceUniverse. Lund 1281 ger verifierat noll; Malmö 1280
endast Hyllie 3211/site 169; positiv kontroll Staffanstorp 1230 ger 3229/site 11.
Stora Bernstorp lånas inte till Malmö. Samtliga 38 nationella registerrader
per kommun och okända/felorsaker sparas.

Verklig kataloginsamling gav 13 523 respektive 13 780 godkända OWN-rader,
0 produktkarantän. Slutparser v4 återspelar källorna utan föryngring eller nät.
Kampanjfält som tappades för ItemsTotal×1 bevaras; villkor som minsta köpbelopp
spärrar rabattavtalet. Separat källbelagt varukorgstak följer provenance till
checkout/audit. Offers-only kan kvalificeras ur faktiska partiella svar och
ersätter inte fortfarande giltig full LKG.

Kommunval/status är beständigt och ansluter till ordinarie daily-refresh,
behovsplan, builder, publicering och reload. Avstängt som standard.
Explicit befintligt OWN_SOURCES_ONLY respekteras även i daily-refresh;
standardens kompletta externa bas och färskhetsgrindar består.
Isolerade drift- och köpbevis, slutkodhashar samt nät-/replayavgränsning finns
i reports/citygross-municipality-20260923. Full federerad Malmö-publicering
med aktuell komplett Malmö-/Primat-bas återstår och ersätts inte av Lund.

Willys sju onlinebortval har konkret onlineStore=false: Lund Stortorget 2863;
Malmö Lindängen 2843, Lugnet 2851, Möllevången 2870, Söderkulla 2865,
Oxie Centrum 2879 och Rosengård 2352. Varje butik har separat verifierad
officiell reklambladslänk, men befintlig connector importerar inte bladen.
Avsaknad av katalog betyder inte avsaknad av erbjudanden. Willys kod, tester och tidigare
releaseunderlag behålls och hashkontrolleras i separat release-manifest.

Köpprovets explicita färska tomat passerar matcher/checkout/audit. Generellt
tomaturval kan även acceptera passata; detta kvarstående matcharfel är
redovisat, inte ombyggt här. Lidls nästa steg: samma officiella kommunurval
och belagd butiksgiltighet för aktuella erbjudanden i befintlig offers-only-väg.
Ingen produktion, Windows-/schemakonfiguration, bildanalys eller modell-API
aktiverad. Se separat RELEASE-CITYGROSS.md och docs/citygross_municipality.md.


## 2026-09-24: Willys/Lidl automatisk kvalificering och näring

Senaste verifierade delresultat: reports/offer-nutrition-20260924/README.md,
RELEASE.md och PACKAGE.json. Samma dokument: Willys automatiska varianter
16→22 och 46→56, total unik import fortfarande 24/64. Lidl senaste
29-sidorsrevision 14→23, nio nya livsmedelspriser. SLV-spårad g-näring
0→3/5/2 i jämförda dokument; ingen automatisk tillagad receptgaranti.
427 tester passerar. Isolerad drift, två rebuilds/omstart, not_due,
fel/återhämtning och samtliga 438 prisraders datumspärr verifierade.
Ingen produktion eller schemaändring. Hela målet är inte färdigt:
fler produkt-/kampanj- och deklarationsbindningar återstår, inklusive
tillgängliga tillverkarkällor. Historisk Lidl-fixture och full komplett
Malmö-publicering är fortsatt öppna. Bevara föregående releaser.

## 2026-09-24: större Willys/Lidl-hinder och officiella produktfakta

Senaste delresultat: `reports/offer-expansion-20260924/README.md`,
`RELEASE.md`, `PACKAGE.json`, `profile-summary.json` och `runtime-summary.json`.
Föregående offer-nutrition-underlag och alla kedjereleaser kvarstår.

Garant Majskorvar/Gyros har återanvändbar officiell deklarationsimport med
entydig full identitet och förpackning. Bevarad officiell katalog kan ge
fakta genom kontrollerad råpost/GTIN-bindning; inga priser flyttas mellan
butiker. Pågenlimpan/Pizzamjöl får användbar gramdeklaration, kokosmjölk
saknar fortfarande belagd ml→g-konvertering. Mango har SLV 574 per 100 g
ätbar del, opt-in, ingen antagen fruktvikt.

Fryst före/efter: Willys 77→87 unika priser (två nya exakta livsmedelsköp,
åtta kg-priser utan exakt paketplanering), Lidl 23→26 exakta livsmedelsköp.
Willys automatiska annonser 17→20 av 34 och 51→57 av 112; manuella varianter
2→2 respektive 8→7 efter deduplicering. Gyros automatisk bindning/namnbyte
är inget nytt pris. Unik gram-kompatibel näring Willys 6→10, Lidl 2→2.
Pågenlimpan har separat nytt receptprov. Kycklingvingar får exakt paketköp
men kan inte bli generella gram kycklingkött i recept.

453 riktade unika testfall passerar, Ruff/compileall passerar. Riktig
oförändrad 15/20 på samma kompletta bas och frysta klocka: VERIFIED,
535,25 kr före/efter, två butiker; slutkod verifierad. Privat faktisk
Coop 730400-hämtning: 11 309 produkter/825 anrop; inga produktionsskrivningar.
Basen var AGING, ingen STALE-kontext; får inte beskrivas som nyhämtad i sin helhet.

Driftprovet har publicering/reload, andra rebuild, omstart, fel/LKG och
återhämtning. Hela not_due-provet är PARTIAL: bevarad City Gross-bas var
förfallen enligt ordinarie 35h-gräns, Willys/Lidl hade inget förfallet arbete.
Full komplett Malmö-publicering, oberoende ogranskad utgåva och historisk
Lidl-fixturelucka är fortsatt öppna. Hela ursprungliga nämnaren kvarstår:
38 Willys variant-/intervallfall och 81 regionalt aktuella Lidl-livsmedel
har kvarstående hinder, utöver övriga dokumenterade grupper. Detta är
inte full täckning. Ingen produktion, Windows-/schemaändring eller modell-API.


## Gemensam äggberedning: nästa verifierade kontrollpunkt 2026-10-28

1 828/2 200 hela korgar inklusive uppskattningar, +26; exakt 1 062 hela och
1 064 insatslösta, 372 insatshinder kvar. Alla original och tidigare korgar
består. Versionerad äggseparering delar inköp, reserverar rå insats och
bokför uppmätta gula/vita separat i befintlig transaktionsjournal.
A 281,31 kr två gånger och B2:s hela korg identisk 731,20 kr; alla 2 892
kvittohashar passerar. Se [rapport](reviews/egg-preparation-20261028.md).
Samma obegränsade totaljournal och resurs-/källkrav gäller. Full täckning
återstår. Fem exakta torrvaror hos tre nya handlare har ett separat
[beslutsunderlag](reviews/coverage-source-pilot-20261028.md); utökningen
är inte beslutad här. Ingen driftaktivering ingår. Hosted CI och
integration måste passera innan denna kontrollpunkt integreras.
