# Smako: snabb ny kombinerad 40/30/20-plan

2026-09-13. Appkod `98381e5`, release `personal-v2-fast-403020-20260913c`.
**PASS:** median 27,462 s för tre request-kalla HTTP-planer. Alla kvalitetskrav
bevarade, slutrelease driftsatt och mobilprov verifierat.

## Verifierad utgångspunkt och rättvis jämförelse

Den nya arbetsmappen var tom. En separat Git-worktree/gren skapades från den rena
föregående arbetsmappens `8023488`. VPS körde
`personal-v2-combined-403020-20260913b`, image
`f5d18c0ca8b8732a0f23c083e4df6f60b9d571de861e65e76c316eeb4ee119c9`.
Alla 105 appfiler jämfördes med Git-versionens normaliserade SHA-256 före staging.
Den andra förbättringens 105 basfiler verifierades på samma sätt mot `df4685a`.
[Första källmanifestet](performance-403020/release-a-source-manifest.json),
[slutligt källmanifest](performance-403020/release-source-manifest.json).

[Sanerad basrequest](performance-403020/request.json): middag 5×2 ≥40 g,
frukost 5×1 ≥30 g och mellanmål 5×1 ≥20 g protein **per portion**. Totalt
15 tillfällen och 20 portioner. Blandad, Balanserad, gemensamt butikstak två,
spårbara uppskattningar uttryckligen på. Postnummer 22350, inga medlemskap,
gilla/ogilla/uteslutningar/allergier, eko 0 %, animaliskt eko av, minimera
överskott, inga extravaror, tomt skafferi revision 0. Övriga näringsgränser är
null. Varierad-budget 25 % är ett inaktivt formulärvärde. Inget max 800 kcal,
fiskförbud eller annat tidigare testkrav har lagts till.

Fryst tid `2026-09-13T15:02:55.453714+00:00`. Prisversion
`price-universe:11e58c7ce1ae5efaf8da60d87c3f67e29adc43bde8b1fb321f7351d450715a46`;
faktaversion
`retained-catalog-facts-v3:c3f5ec2b567aa5f3f8ebc67be17106f48ed624f157348caf9abcd16378096b9a`.
Planpolicy `personal-policy-v2-7`; exakt referens-/beredningshash, normaliserad
request och prisartefaktens SHA finns i [baslinjen](performance-403020/baseline.json).
Generator, mappningar, variationspolicy och sökbudget är oförändrade:
beam 8, högst 256 näringsalternativ per produktkombinationssökning, deterministisk
ordning utan slumpseed. Rå pool 95 middagar +5 frukostar +5 mellanmål; kvalificerad
pool 10/2/2. **Hela de ordnade kandidatpoolerna är exakt lika**, inte bara antalen.
[Före](performance-403020/before-pools.json), [efter och inställningar](performance-403020/after-cases.json).

VPS: åtta AMD EPYC-Rome vCPU, 15 986 MiB RAM. Docker CPU `max 100000`, RAM `max`,
ingen särskild kvot. Last 0,00/0,00/0,00 före baslinjen. Samma resurser och
beroendeimage i alla jämförbara körningar. Testcontainrar kördes sekventiellt,
med nätverk av och egna testtillstånd. Produktion och scheduler lämnades igång;
inga tunga parallella acceptanstester kördes mot publik beta.
[Resurser](performance-403020/environment.json).

## Vad sex minuter faktiskt avsåg

Föregående rapportens 355,14 s avsåg **en** `PersonalPlanner.create()` för D,
efter konstruktion av planner och laddning av katalog/fakta. Dess 388,98 s och
senare 369,35 s avsåg två separata mobilprov, vardera en POST och en plan.
De var inte summan av A–D eller automatiska retries. Tidigare mobilskript stannade
klockan vid mottaget JSON-svar; de inkluderade inte säkert färdig frontendrendering.

Den nya oprofilerade baslinjen tog **357,670 s**, varav 0,078 s konstruktion
och 357,592 s `create`; CPU 357,584 s. Den återskapade exakt 574,92 kr.
Processstart inklusive import/laddning tog totalt 374,331 s till resultat.
Detta ger en reproducerad baslinje, men endast **n=1**, inte en före-median.

## Flaskhalsar och genomförda ändringar

Hela diagnostikkörningens exklusiva monotona steg visade 1 562 552 anrop till
`nutrition_evidence`, 63 636 till portionskontrollen, 341 gemensamma korgbyggen
och 7 335 anrop till befintlig korgoptimerare. Kandidatgenerering skedde en gång
per måltidstyp, `create` en gång. Extra planner-konstruktion avsåg samma fasta
menys jämförelse med ett lägre butikstak, inte ytterligare planlägen.

Ett fullständigt cProfile-prov av en fast D-meny med samma 15 tillfällen tog
82,358 s lokalt: 107 405 näringsuppslag, 63,627 s kumulativt i näringsunderlaget,
5 386 853 textnormaliseringar, 3 707 portionskontroller. Paket-/butiksoptimering
tog endast cirka 1,17 s. Detta motiverade beräkningsåteranvändning först.

1. **Request-lokalt näringsunderlag.** Exakta produkt- och butiksidentiteter,
   ingrediens, enhet, begärda näringsfält, hela receptvärdet och opt-in ingår.
   Receptvärdet omfattar namn, portioner, alla ingredienser med oavrundade mängder
   och instruktioner. Receptets muterbara listor identifieras inte med objekt-ID.
2. **Request-lokal portionsberäkning.** Samma använda mängder, valda produkter,
   skafferiallokeringar, beredning, portionsgränser och viktunderlag återanvänds.
   Slot-ID sätts separat i svaret. Avslag lagras som värden, utan kvarhållna
   undantagsstackar. Allokering, hela gemensamma korgen och slutkrav består.
3. **Ren textnormalisering.** Exakt textnyckel, högst 8 192 poster och 4 096
   tecken per cachad indatasträng. Inga produktpriser, profiler eller planer i
   denna cache. Näringscacherna är privata för planner-instansen och begränsas
   till 16 384 respektive 2 048 poster; de försvinner med begäran.
4. **Faktacachens verkliga beroenden.** Mobilprovet på första förbättringen tog
   fortfarande 36,331 s och receptbytet 13,957 s. Den gamla globala faktacachen
   använde databasens/WAL-filens ändringstid: driftloggning kunde ogiltigförklara
   oförändrad katalog och upprepa cirka nio sekunders parsning/kvalificering.
   Nu används de relevanta, snapshotbundna produkt-/råkällraderna som nyckel.
   **Varje distinkt råfil SHA-verifieras även vid träff**, med strömmande hashning.
   Ändrade källkopplingar, saknade eller korrupta filer kan alltså inte återanvända
   gamla fakta, inte ens om filstorlek/ändringstid bevarats. Högst fyra globala
   faktaversioner, endast offentlig kataloginformation. Faktainnehållet är exakt
   oförändrat; inga observationstider eller mappningar ändrades.
   Ett separat varmt faktaprofileringsprov fann därefter 34 650 upprepade
   sökvägskontroller: `Path.resolve` 4,217 s kumulativt, `is_relative_to` 2,705 s
   i ett 8,710 s instrumenterat prov. Varje exakt råfilsökväg löses nu en gång
   per begäran. Rotkontroll och strömmande innehållshashning behålls.
5. **Arbetstråden omfattas av admission.** Även nödvändig faktainläsning och
   konstruktion sker i den tillåtna arbetstråden. Vid asyncio-avbrott behålls
   kapacitetsplatsen tills den faktiska tråden har avslutats. Annars kan en
   avbruten `to_thread`-väntan lämna CPU-arbetet kvar medan nästa jobb släpps in.
   Två upprepade cancellation-signaler och en köande beräkning testas konkret.

Inga måltider, portioner, kandidater, sökbudgetar, variationstester eller
produktkontroller togs bort. Ingen heuristisk undergräns, separat summering av
måltidstyper, ny prismotor, parallella Uvicorn-workers eller resultatcache infördes.
Prisfärskhet och kampanjdatum kontrolleras i varje ny planner efter köväntan.
Fakta-/receptcacherna räknar aldrig förpackningsöverskott som uppäten näring.

Det fasta lokala profileringsprovet föll 82,358 → 9,951 → 6,696 s i två steg.
Full VPS-profil efter beräkningsändringarna: 58,731 s instrumenterad väggtid,
58,714 CPU-s. Bara 3 976 verkliga näringsunderlagsberäkningar och 497 verkliga
portionsberäkningar återstod; 341 korgbyggen och 7 335 korgoptimeringar är kvar.

Exklusiva monotona huvudsteg i full D-diagnostik (sekunder; instrumenterade,
inte acceptanstider). Varje nästlat steg dras av från sin förälder:

| Steg | Före | Efter beräkningsändring |
|---|---:|---:|
| Näringsunderlag | 332,198 | 6,666 |
| Portionskrav | 34,405 | 6,668 |
| Produktkvalificering | 7,051 | 2,741 |
| Näringsalternativsökning | 11,938 | 15,870 |
| Butiker och paket-/kampanjpris | 11,942 | 17,732 |
| Gemensam korgberedning/audit | 4,046 | 5,435 |
| Menysökning/resultat | 1,732 | 3,349 |

De fullständiga JSON-spåren innehåller också data/initiering och kandidatgenerering
för middag/frukost/mellanmål. Korgstegen har oförändrat anropsantal; större
instrumenterad eftertid där är inte ett bevis på långsammare oprofilerad prissättning.
Kö, lås, lagring och serialisering mäts separat i den verkliga HTTP-livscykeln.

Viktiga funktioner i det fullständiga efter-cProfile-spåret:

| Funktion | Anrop | Egen tid, s | Kumulativ, s |
|---|---:|---:|---:|
| `optimize_slots` | 1 | 0,006 | 54,418 |
| `PersonalPlanner.basket` | 341 | 0,848 | 53,629 |
| `_qualified_nutrition_basket` | 339 | 3,563 | 33,107 |
| `BasketOptimizer.optimize` | 7 335 | 0,591 | 17,668 |
| `quote_item` | 44 407 | 0,682 | 7,682 |
| `_check_nutrition` | 63 636 | 3,144 | 6,440 |
| `nutrition_evidence` | 653 526 | 1,959 | 5,147 |

Kumulativa tider överlappar och får inte summeras. Ingen SQLite-, nätverks- eller
serialiseringskostnad per söknod kunde beläggas. Den dominerande gamla kostnaden
var ren CPU-beräkning av återkommande identiska näringsproblem.

Alla `.prof` och fulla sorterade profiler finns i [rapportmappen](performance-403020/).
Avgränsning: ursprungliga VPS-diagnostikens cProfile samlade de första 53,157 s;
en mellandump stängde cProfile. De exklusiva stegen fortsatte hela körningen
(403,604 s). Detta är markerat i JSON och används inte som oprofilerad jämförelse.
Det fasta före-provet och VPS-efter-provet har kompletta cProfile-spår. Skriptets
mellandump är korrigerad. CPU-/väggtid, anropsantal, egen/kumulativ tid och RSS
sparas utan profiluppgifter, cookies eller tokens.

## Slutliga tider

**30-sekundersmålet: JA för request-kall nyplanering, inklusive HTTP.**

| Avgränsning | Individuella sekunder | Median / spann / n |
|---|---|---|
| Före, request-kall beräkning | 357,670 | En basobservation, n=1 |
| Efter, samma frysta beräkning | 26,480; 26,273; 26,662 | 26,480 / 26,273–26,662 / n=3 |
| Efter, request-kall genom HTTP, tre nya gäster | 27,047; 27,462; 28,007 | 27,462 / 27,047–28,007 / n=3 |
| Processkall, fryst beräkningsfixture före → efter | 374,331 → 44,076 | n=1 per version |
| Processkall, ordinarie ASGI inklusive första HTTP-resultat | 48,537 | n=1 |
| Första HTTP efter ASGI-start, råfakta ännu oladdade | 31,878 | n=1 |
| Varm HTTP-upprepning | 27,124 | n=1, ny ägd plan |

Den jämförbara rena beräkningen blev cirka **13,5 gånger snabbare** (92,6 % mindre
tid), jämfört med basobservationen. Ingen före-median eller p95 påstås.
Beräkningskoden är identisk mellan slutliga tre fixtureprov och slutrelease;
den sista ändringen berör enbart källadapter som fixtureprovet redan har laddat.
Slutrelease kördes dessutom genom hela HTTP-livscykeln i tre oprofilerade,
sekventiella request-kalla prov. Alla sju HTTP-planerna saknade färdig resultatcache.

CPU i de tre rena slutproven: 26,469 / 26,263 / 26,654 s. Peak RSS 1 019,5 MiB,
mot 1 017,8 MiB före; processen använder ungefär en kärna. Under det isolerade
HTTP-provet observerades 100,10 % av en CPU, medan produktionsappen använde
0,16 % och scheduler 0 %. Ingen extra beräkningsparallellism infördes.
[Frysta slutprov](performance-403020/final.json), [HTTP-livscykel](performance-403020/http.json).

ASGI-start tog 16,489 s. Första råfaktaladdningen tog 6,069 s; följande
request-kalla underlagskontroller 0,764 / 0,809 / 1,543 s, inklusive hashverifiering.
Sparandet tog 0,011–0,016 s och svarsserialiseringen 0,0009–0,0017 s.
Dessa är inte dominerande flaskhalsar. Peak RSS för hela HTTP-processen var
1 040,5 MiB, med egen SQLite och telemetri. Driftloggning i samma databas
ogiltigförklarar inte längre identiska katalogfakta.

Request-kall betyder färdigladdade oförändrade pris-/produkt-/näringsdata, men
ny planner med tomma kvalificerings- och sökcacher, ingen färdig plan. Ren
normalisering av offentlig katalogtext får återanvändas. Varm HTTP skapar också
en ny ägd plan, med nytt plan-ID; funktionen har ingen färdig personlig resultatcache.
Ingen uppvärmning av just testsvaret har gjorts. Data-/processinitiering redovisas
separat och har inte flyttats till en dold bakgrundskörning.

## Resultat, UI och regression

Alla huvudprov har exakt samma 574,92-kronorskorg, hela produktrader,
förpackningsantal, kampanjregler, ingredienser, valda recept, oavrundade
näringsvärden, näringskällor och sökdiagnostik som baslinjen. Detta belopp är en
tillåten exakt historisk jämförelse eftersom request och pris-/faktaartefakter
återskapades. Livepriser tvingades aldrig till beloppet.

Oförändrad målfunktion: `(hela korgens kostnad + smakpoäng×2, korgkostnad,
ordnade receptnamn)`. Smakprofilen är neutral, så kostnadsleden är båda 574,92.
Alla gränser klaras före avrundning; middagens lägsta protein är
40,24450812834225 g, frukost 35,5 g och mellanmål 22,0 g per portion.
Coop Online Syd 226,21 kr + Hemköp Lund Brunnshög 348,71 kr, två inköpsställen
för **hela** korgen. Coop påstås inte vara ett fysiskt Lund-hyllpris.

Variation redovisas separat: fem skilda middagar, fem receptfamiljer/former,
fyra tillagningsmetoder, tre huvudproteiner och tre kolhydrater. Protein:
kyckling 2, linser 1, fisk 2. Kolhydrat: ris 2, pasta 1, nudlar 2. En återkommande
frukost och två mellanmål är samma avsedda policy som före.
[Alla mått](performance-403020/variation.json).

Separata VPS-prov: middag 461,80 kr, frukost 74,12 kr, mellanmål 38,50 kr.
Uppskattningar av blockerar fortsatt A/D på data, medan B/C klaras med
deklarationer. Ändrad frukostgräns 32 g gav 74,12 kr, två portioner 118,79 kr,
300 g exakt skafferikvarg 54,12 kr. Alla tre jämfördes mot den ocachade
beräkningen och blev exakt lika. Skafferiet ändrades inte av genereringen.

Ordinarie mobilformulär via `https://beta.smako.nu/personal`, Chromium 390×844:

| Prov | Klick → HTTP-svar | Klick → användbart, renderat resultat | Receptbyte → användbart |
|---|---:|---:|---:|
| Första plan efter releaseomstart, råfakta kalla | 32,968 s | 33,224 s | 4,611 s |
| Ny gäst och ny plan, katalog laddad | 28,599 s | 28,760 s | 4,562 s |

Detta är två browserprov över verklig HTTPS, inte mätningar på en fysisk telefon
eller ett mobilnät. Sluttid kräver synlig full plan, aktiverade kontroller och två
renderingsvarv. Alla recept, produktrader, mängder, korgekonomi, kontroller och
diagnostik matchar fryst baslinje exakt även här; endast versions-/tidsmetadata
och den tidsberoende färskhetsidentiteten skiljer sig. Formulärets skickade
basrequest är exakt samma. [Maskinell jämförelse](performance-403020/final-summary.json),
[första provet](performance-403020/mobile-c-first/acceptance.json),
[laddad katalog](performance-403020/mobile-final/acceptance.json).

Båda receptbytena gav HTTP 200, nudelpanna med lax på dag fyra, **584,92 kr**
för hela korgen och bibehållna 15 tillfällen, 20 portioner, 40/30/20-gränser och
gemensamt butikstak. Det andra bytet tog 4,535 s till svar, 4,562 s till användbart
resultat. Bildbevis för formulär, plan och byte finns bredvid respektive JSON.

Det lilla isolerade samtidighetsprovet skickade två planer samtidigt från olika
gäster: 27,301 och 55,544 s till svar, hela vågen 55,568 s. Andra begärans
admissionkö tog 27,204 s; en aktiv och en köande var toppvärdena. Sex
health/ready-anrop tog 0,056–0,152 s, tre produktsökningar 0,029–0,133 s,
samtliga HTTP 200. Planerna fick skilda ägare/ID, korsläsning avvisades och
in-flight-räknaren blev noll. Den isolerade ASGI-tråden avslutades kontrollerat.

Frontendens befintliga timeout är 600 s och planeringsproxyns 540 s. Dessa
ökades inte. Dubbelklick gav en enda POST. Två separata, tydligt simulerade
browserfelprov höll begäran före serverdispatch: navigation/återbesök behöll
senast mottagna plan; en förkortad testklocka utlöste den verkliga timeouttexten
utan automatisk retry. Ingen extra produktionsplan startades av felproven.
Om sidan lämnas före svaret kan servern slutföra beräkningen, men klienten känner
bara senast mottagna plan-ID; ingen ny jobbåterhämtningsarkitektur har införts.
Avbrott får däremot inte lämna en oreglerad arbetstråd; det verifieras separat
med verkliga trådar och admissionräknare. Inga arbetande testcontainrar lämnas kvar.

477 distinkta fokuserade regressioner omfattar även inaktiva måltidskrav,
allokering utan automatisk förbrukning, historiska köp/revisioner,
användarisolering, flerköp/förpackningar, medlemskap, utgångna kampanjer och
prisfärskhet. Berörda tester upprepades efter ändringen i faktacachen; oförändrad
kod återanvänder tidigare hashstabil verifiering. Ruff och Python 3.12 compileall
passerar. Inga externa källanrop i nätverkslösa konsumentprov, och varje verkligt
HTTPS-resultat rapporterar `live_chain_requests=0`.

## Deployment och kvarvarande arbete

Backup `20260913T194832Z` slutfördes före slutlig aktivering. Release
`personal-v2-fast-403020-20260913c`, appkod `98381e5`, image
`sha256:9669be2e3b411588778b95e816adc5e3f3d12fd164a47ade81df2e6b425d6235`
är aktiverad via befintligt gemensamt refresh-/backup-lås och atomisk
releasepekare. Bara appkod/image och versionsvärden ändrades; samma befintliga
beroendeimage och resurser. App och Caddy återskapades enligt tidigare rutin.

164 befintliga planrevisioner var hashbevarade efter aktivering; SQLite integrity
var `ok`, scheduler-container och aktiva prismanifest oförändrade. Automatisk
återgång går till `personal-v2-fast-403020-20260913a`; den imageversionen har
konkret läst alla tre nya planpayloads exakt, utan databasrestore. Även den
ursprungliga kvalificerade releasen har verifierad läskompatibilitet.
[Aktivering](performance-403020/deployment.json), [rollback](performance-403020/rollback-final.json).
Mellanbilden `personal-v2-fast-403020-20260913b` testades isolerat men aktiverades
aldrig; den extra sökvägsrättningen kvalificerades före slutlig aktivering.

Efter de två kompletta mobilproven verifierades 164 gamla revisioner fortfarande
oförändrade, nu 168 totalt. HTTPS `/health` och `/ready` svarade 200 med rätt
release. Endast app, Caddy och befintlig scheduler kördes; inga testarbetare
lämnades kvar. Produktionsappen låg därefter på 0,19 % CPU och 917,7 MiB resident
containeranvändning. [Slutstatus](performance-403020/final-health.json).

Största kvarvarande beräkningskostnaden är den befintliga gemensamma sökningen
över näringsalternativ och korrekt paket-/kampanjekonomi: 7 335 korgoptimeringar
per D-plan. Den fullständiga efterprofilen visar cirka 17,73 exklusiva sekunder
i butik/paket och 15,87 i näringsalternativens sökarbete, inklusive profilerings-
overhead. Det är inte en ny global optimalitetsgaranti: den befintliga begränsade
sökningen och kvalitetsnivån är bevarade. Första råfaktaladdningen kostar fortfarande
tid och redovisas i processkallt prov.

Ingen receptutökning, datainsamling, OIDC-ändring, Willys-task/relay-ändring,
ändrad källobservation, ny server eller betald tjänst ingår.

Reproduktion: `combined_performance_probe.py` kör releasebilden med de frysta
`combined-prices.json`, `combined-facts.json`, `combined-request.json` och
`combined-runtime.json` monterade på `/inputs`, rapportmapp på `/output` och
`--network none`. `--repeat 3` skapar tre nya planners; `--profile --fixed`
använder den historiska fasta D-menyn för mindre diagnostik.
`combined_performance_cases.py` jämför pooler och små profiländringar;
`combined_performance_http.py` testar isolerad ASGI/HTTP med eget planlager;
`combined_performance_browser.py` mäter ordinarie HTTPS-formulär i 390×844.
Stora offentliga råfixtures ligger kvar under `reports/private` och på VPS,
inte i den incheckade rapporten. Inga privata kontodata kopieras till arbetsmappen.
