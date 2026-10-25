# Beslut och implementeringsuppdrag till Sol: skalning och Axfood

**Aktuellt nästa steg efter PR #11:** följ
[CODEX-SOL-NEXT-20261025.md](CODEX-SOL-NEXT-20261025.md) för kortare väntan
vid nya personliga val och prisuppdateringar, med avgränsad testbudget.
Arkitekturkontrakten nedan gäller fortsatt; den tidigare fullmatrisen är stoppad.

Status: beslutad arkitekturriktning 2026-10-23; implementation återstår.
Bas: main `59e6f76f4f615a0e09ec980efc908665a64c1f37`.
Läs först `AGENTS.md`, `HANDOFF.md`, `DEVELOPMENT.md` och
[slutrapporten](reviews/integration-scaling-20261023.md). Denna instruktion
ersätter öppna arkitekturfrågor i `CODEX-NEXT-20261023.md`; tidigare mätningar
och deras begränsningar gäller fortfarande. Gör implementationen i små,
granskade commits och integrera färdiga delar till main enligt repoets flöde.

Ägaren har uttryckligen sagt: **”Jag accepterar Axfoods berikningen”** och
bett om arkitekturbeslut med implementation hos Sol. Principbeslutet om
Axfood-berikning är därmed taget; fråga inte om det igen. Den här leveransen
är enbart dokumentation. Den startar ingen insamling eller driftändring.
Sol får genomföra berikningen, inklusive kontrollerad kompletteringshämtning
om arkivet inte återfinns, och förbereda en granskad release. Innan ett
konkret produktionsbyte eller nytt automatiskt insamlingsschema verkställs
ska dess exakta paket, verifiering och rollback redovisas enligt BETA.md
och tidigare krav på separat driftbeslut. Det är ett beslut om en konkret
driftändring, inte ett nytt godkännande av berikningens syfte.

## 1. Arkitekturbeslut

Inför **en verifierad referensmeny med separat förbättringssökning**, och
**versionsbundna förberedda kvalificeringsresultat** i befintlig planner.
Axfood blir en versionsbunden kompletterande faktakälla i samma faktakedja.
Skapa ingen parallell pris-, korg-, närings-, jobbkös- eller refreshmotor.

Tre beslut är bindande:

1. En snabbare sökväg får inte ersätta en billigare, fortfarande giltig meny.
   Referenssökning och förbättringsspår behåller sina egna söktillstånd.
   Jämförelsen sker mellan färdiga, oberoende slutkontrollerade menyer.
2. Flytta återanvändbart arbete från varje förfrågan till förberedelse av
   exakt underlag. Ett rankningsmått får prioritera arbete men får inte
   permanent gallra recept utan ett giltigt bevis för den aktuella korgen.
3. Axfood kompletterar ingrediens-/näringsfakta för exakta artikelidentiteter.
   Det ändrar aldrig priser, butiksscope eller katalogens observationstid.

Större K, fler geometriska kohorter och proxy-topplistor löser inte i sig
problemet. Lund/fördelning missar mellanleden generation 8/11/12; dessutom
förlorar proxyprovet vid 5 000/K32 en meny för 480,97 kr och ger 487,85 kr.
Behåll `library_merge_generations=False` som nuvarande standard under arbetet.
En ny policy ska väljas med ett uttryckligt versionskontrakt; slå inte bara
på den befintliga flaggan och kalla det den nya arkitekturen.

## 2. Pris och giltighet: kontraktet

### Referens, kandidater och slutligt val

Pinna basbibliotekets **exakta receptvärden och publiceringsordning** från
262-receptsunderlaget; använd dess manifest/hash, inte ”de första 262” i
en ny sortering. Kör dagens per-paket-sökning med alla dess uttryckliga
parametrar på detta bibliotek som referens för varje ny exakt kontext.
Återanvänd resultatet endast när kontexten matchar. Därmed bevaras även
den gamla mellanliggande sökvägen som geometriska kohorter tappade.

Samla följande fullständiga kandidater i ett gemensamt, begränsat arkiv:

- referenssökningens vinnare;
- tidigare levererad/verifierad vinnare för samma kontext och en fortfarande
  giltig delmängd av det nya biblioteket;
- vinnare från förbättringssökning på nya recept och från befintliga
  geometriska/småpoolsförsök.

Använd befintlig basket/evaluate, accepts och slutlig checkout-audit för
varje kandidat som kan vinna. En kandidat som fallerar audit tas bort;
prova nästa verifierbara kandidat. Pris jämförs med befintlig exakt
pengarepresentation, inte avrundade flyttal eller uppskattade portionspriser.
Behåll nuvarande policys för kostnadstak, inköpsvillkor, näring, variation
och sekundär rangordning. Bland kandidater som klarar dessa krav väljs
lägsta jämförbara kassasumma, sedan befintliga deterministiska skiljeregler.
Den föregående menyns pris är aldrig ett värde som kopieras in i en ny korg.

Arkivet behåller minst referens och aktuell vinnare; övriga platser är
begränsade och kan evikteras utan att förlora dessa två. Referensens
söktillstånd får inte muteras av förbättringsspåret. Vinnare uppdateras
atomiskt efter slutkontroll. Vid lika pris behålls tidigare vinnare om
ingen uttrycklig befintlig skiljeregel kräver annat.

### Garantins räckvidd

För **samma priser, fakta, klocka/prisdatum, användarkrav och policy**, med
oförändrade receptvärden som fortfarande är tillåtna, ska en ren utökning
av biblioteket inte ge dyrare levererad meny än referensen eller en tidigare
verifierad vinnare. Vid ändrade fakta/priser, återkallat recept, ändrat
skafferi eller användarkrav måste giltigheten omprövas. En prisökning då
är inte automatiskt en sökregression och får inte döljas av gammal cache.

Detta bevisar inte global optimalitet. En tidigare vinnare som bara finns
i varm processcache räcker heller inte för ett påstående om godtyckliga
kalla, oberoende körningar på olika biblioteksstorlekar.

För publicerade nästlade bibliotek: lagra en ordnad manifestkedja med
föregångarhash och verifierade vinnare per stödd kontext. Vid kall miss
återskapas referens och föregående publicerade steg deterministiskt, eller
anropet väntar på detta via befintligt planjobb. Hoppa inte över steg och
påstå ändå monotonicitet. Mellanstorlekar utan publicerat certifikat märks
som experiment. För privata kontexter lagras kedjan endast inom befintligt
användarägt planlager; ingen privat meny eller skafferiidentitet läggs i
offentliga prewarm-artifakter.

Begreppet ”certifikat” betyder här en verifierbar resultatpost, inte ett
bevis på globalt optimum. Posten binder kontext, bibliotek, föregångare,
receptidentiteter, verklig kassasumma, audit och metodversion med hashar.
Återkallelser och ändrat receptinnehåll bryter en append-only-kedja.

Kör även gamla sökningen på **samma fulla bibliotek** i releasevalideringen.
Ingen av de 14 benchmarkprofilerna får bli dyrare än den. Det är ett
strängare empiriskt leveransvillkor än basreferensen; referensarkivet ensamt
garanterar det inte. I förberedelsen för dessa profiler kan den gamla
fullbibliotekssökningens verifierade vinnare också läggas i arkivet.
Det arbetet måste redovisas som förberedelsekostnad, inte räknas bort.

### Budget och ofullständigt arbete

Förbättringar körs med versionsbundna gränser för utvärderingar, delningar
och minne. Välj ett fast, dokumenterat budgetvärde efter pilotmätningen;
budget får inte ökas automatiskt med receptantal i det snabba anropet.
Deterministisk ordning och antal utvärderingar styr kvalitetsexperiment;
väggtid används som säkerhetsavbrott och redovisas som avbrott.

När budgeten tar slut returneras bästa färdiga, verifierade kandidat.
Finns ingen sådan är resultatet ”sökning ofullständig” genom befintligt
jobb-/felkontrakt, inte ”omöjligt”. Bevara skillnaden mellan saknade fakta,
heuristisk sökmiss och bevisad kapacitetsbrist. Ett negativt kapacitetsbevis
gäller bara den fullständigt kvalificerade pool det faktiskt undersökte.
Fältet `week_search_method` ska beskriva varje fas rätt; ett uttömmande litet
prefix får inte märka hela den senare sökningen som uttömmande.

## 3. Kvalificering och beräkningstid

### Två nivåer av återanvändning

Utöka befintliga cache-/förberedelsemoduler, med en gemensam serializerad
kontextdefinition som också används av arkiv och single-flight:

- **Receptnivå:** exakt utfärdat innehåll, återkallelseversion, portioner,
  förberedelse-/normaliseringsversion och immutabla strukturvärden.
- **Kontextnivå:** PriceUniverse-manifest, faktainnehåll inklusive Axfood,
  tillåtna butikskontexter och källstrategi, prisdatum/kampanjgränser,
  inköpsläge, medlemskap/kuponger där relevant, alla profil-/närings-/
  variationskrav, låsta produkter/platser, skafferi och versionsbundna
  algoritm-/inställningsvärden som den cachade funktionen faktiskt läser.

Inventera läsberoendena i koden; listan ovan ersätter inte den kontrollen.
Personliga indata eller härledda priser ska inte spridas i offentliga
cachefiler/loggar. Delning över användare tillåts bara för bevisat rena,
opersonliga delresultat. På disk behövs stabil innehållsidentitet;
processens `id(...)` eller Python `hash()` är inte beständiga nycklar.

Lagra små immutabla kvalificeringsposter och referenser till gemensamma
recept, inte hela duplicerade planner-/produktgrafer per profil. En träff
får återanvända en tidigare kvalificering, men ersätter aldrig audit av den
slutliga gemensamma korgen. Pantry-allokering och lås är anropsägda.

Det första genomförandet invaliderar hela kontextnivån när universum/fakta
ändras. Inom identisk kontext kvalificeras bara tillagda/ändrade recept.
Behåll den enkla, korrekta invalidationen tills mätning visar behov av
finare beroendeindex. Ett senare index måste även fånga nya möjliga
produkter som inte tidigare var valda; endast använda produkt-ID:n räcker
inte för korrekt invalidation.

Färdigställ och publicera ett manifest för en komplett kvalificeringsvy
atomiskt. Ofärdiga, felaktigt hashade eller versionsfrämmande poster är
missar. Fallera inte hela planeringen för en korrupt cachepost; återskapa
den genom ordinarie kod. Testa bortfall och processkrasch mellan skrivningar.

### Livscykel och resursgräns

Återanvänd `plan_jobs.py`, `planner_admission.py`, `plan_prewarm.py`,
befintlig PriceUniverse-manager och förberedelsecache. En kall kontext
förbereds som ett avgränsat jobb; identiska anrop delar jobbet. Befintligt
jobbgränssnitt visar väntan och slutförande. Inför ingen ny fristående
köteknik eller mikroservice. Avslutade planer ändras inte tyst när ett
senare förbättringsjobb hittar något bättre.

En tung planberäkning åt gången per budgeterad worker är startläget.
Bakgrundsarbete lämnar företräde åt användaranrop; förbättringar ska kunna
avbrytas mellan bounded arbetsenheter. Ingen dubblering av 3 GiB-processer
för att dölja latens. Admission är i dag processlokal: flera ASGI-workers
kräver gemensam resurskontroll eller en uttryckligt budgeterad total.

Sätt sammanlagda byte- och antalsgränser för cache, arkiv, kö och
materialiserade vyer, inklusive gamla versioner som ännu har läsare.
Bygg och pensionera versioner under samma minnesbudget; dubbelbuffer får
inte förutsätta två fulla 5 000-bibliotek i RAM. Bevara diskcache och
rollbackunderlag även när RAM-poster evikteras.

**Mål för implementationen, inte redan uppmätta löften:** på två CPU och
3 GiB ska alla profiler slutföras; sikta på högst 2,5 GiB cgroup-peak för
att få marginal. För ett färdigförberett bibliotek ska andra och senare
anrop vid 5 000 ta högst 1,25 gånger respektive profils tid vid 262, och
inte vara långsammare än nuvarande jämförbara fullbiblioteksanrop.
Mät separat återhämtning efter eviction. En full kall genomgång och en
helt ny personlig kontext får fortfarande växa med biblioteket: det arbetet
ska vara synligt, budgeterat och mätt. Konstant total beräkningstid för
godtyckliga indata plus garanterat optimal meny är inte arkitekturens löfte.

## 4. Axfood: beslutad utformning

### Lagring, inhämtning och uppdatering

Använd `D:\smako-data\axfood-product-details` som lokal arkivrot och
`/srv/smako/data/axfood-product-details` som granskad serverkopia.
Under roten finns `staging/<run-id>` och immutabla `releases/<manifest-hash>`.
Varje release behåller läsarens befintliga layout
`<chain>/<code>.json` och `<code>.meta.json`. Sätt runtimevariabeln
`AXFOOD_PRODUCT_DETAIL_ROOT` till **en bestämd releasekatalog**, read-only
i containern. Inga pågående nedladdningar får skriva i den katalogen.
Lagra manifest med filhashar, källkedja, valideringsversion och täckning.
Använd befintlig lagringsretention; skydda aktiv, rollback och refererad
evidens. Rådata och metadata ska inte in i Git.

Inventera först kända arkiv/backuper och dokumenterade sökvägar utan att
ändra dem. Saknas arkivet byggs det åter med befintlig
`scripts/fetch_axfood_product_details.py` och exakta koder från validerade
kataloger. ”503 kvar” är historik, inte en aktuell att-göra-lista.
Spara en ny kodlista och dess hash. Behåll befintliga verifierade
butiks-/källavgränsningar och klienter; ingen bredare kataloginsamling ingår.

Vald policy: nya koder köas efter varje godkänd katalog; befintliga
detaljdokument omprövas efter **30 dygn**. Tiden är en uppdateringsrytm,
inte ett nytt närings-/allergensäkerhetsbevis. Dokumentens verkliga ålder
visas och befintliga säkerhetskrav gäller. Vid känt motstridigt innehåll
eller återkallad identitet ska fakta spärras, inte behållas som giltiga
bara för att nästa schemalagda tid inte infallit.

Högst **1 begäran/s för Willys, 0,1/s för Hemköp**, en hämtning åt gången
per kedja och gemensamt driftlås för insamlingsoperationen. Retry transient
fel högst tre gånger med backoff; 429, åtkomstspärr eller challenge stoppar
körningen och respekterar Retry-After utan kringgående. 404/410 journalförs
och omprövas tidigast efter sju dygn om koden fortfarande finns i en
godkänd katalog. Övriga permanenta fel ska vara synliga, inte loopas.
Fel får inte skriva över senaste verifierade dokument eller förnya dess
observationstid. Känd återkallelse hanteras separat från nätfel.

Fixera återupptagbarheten före ny hämtning: dagens skript hoppar över varje
kod med befintlig `.meta.json`, även negativa eller trasiga poster. Nytt
urval ska skilja verifierat dokument, dags för omprövning, retry, permanent
saknad och korrupt par. Publicering ska vara atomisk på releasenivå så
råfil och metadata aldrig kan läsas från olika revisioner.

### Fakta och identitet

Utöka `axfood_product_details.py` och nuvarande faktaladdning. Kräv status
200, matchande payload-SHA-256, giltig observationstid, rätt kedja/käll-URL,
metadata-kod och råfilens kod samt exakt katalogartikel. Validera filnamn/
sökväg och hantera trasig JSON/metadata som avvisad evidens med räknare.
GTIN normaliseras med en dokumenterad exakt regel och måste matcha när
jämförbara identiteter finns; saknad identitet är inte en fuzzy match.
Behåll nuvarande konservativa kontroll om katalog-GTIN finns men råfilens
GTIN saknas. Försvaga inte denna för att öka täckningen.

Befintlig fallback Hemköp → Willys får användas endast med exakt samma
Axfood-artikelkod och godkänd GTIN-bindning enligt ovan, och proveniensen
måste uttryckligen visa `axfood_shared_article_code`. Fel i ett eget
dokument får inte döljas av fallbackens lyckade träff i diagnostiken.

Komplettera bara saknade ingrediens-/närings-/animal-fält via befintlig
`project_raw_facts`/`ProductFacts`. Skriv inte över en deklaration och låt
inte en motstridig komplettering godkänna ett recept. Bevara råkälla,
hämtningstid, hash, bindningsmetod och konfliktinformation per fält.
Ingen prisuppgift från produktdetaljen får läsas in i PriceUniverse.
Axfoods manifest/parser och härlett faktainnehåll ingår i invalidationen
av kvalificering och menyer. Berikning är alltså ett nytt faktaunderlag,
inte en återanvändning av den gamla faktaversionens godkännanden.

### Verifiering och release

Kör `backend/scripts/augment_review_facts.py` till nya Lund-/Malmömappar.
Behåll priser, request och testklocka byteidentiska. Verifiera samtliga
ingående manifesthashar före läsning och uppdatera alla påverkade
utdatahashar; nuvarande hjälpare ska härdas om den bara kontrollerar pris
eller bara uppdaterar en av flera ändrade filers hash.

Jämför alla sju profiler, tre upprepningar per stad/arm, med/utan berikning
och med samma plannerkod. Reauditera den gamla menyn mot **nya** fakta:
om den fortfarande är giltig ska den kunna fungera som kandidat så att
en sökmiss inte gör berikningen dyrare. Om den blir ogiltig, redovisa exakt
faktum/krav; behåll inte dess pris som ett tvingande tak. Gör separat
före/efter-jämförelse för algoritmändringen på identiska berikade fakta.

Återskapa Malmöfallet 361,81/340,64 om dess exakta historiska arkiv finns.
Om det saknas ska det anges som ej reproducerat, och en deterministisk
regressionsfixtur för samma sökmisstyp tillföras. Den är inte historiskt
bevis. Kontrollera ingredienser, näringsenheter, konflikter, äggidentitet,
saknat GTIN, hashfel, kedjefel, 404 och halvskrivna uppdateringar.

Förbered ett separat Axfood-releasepaket med kod/image, faktamanifest,
read-only-mount, miljövärde, täckningsrapport, readiness- och rollbackprov.
Källan får vara partiell om täckning och bortfall redovisas sanningsenligt;
saknade detaljer lämnar befintliga fakta/gates oförändrade. Aktivering får
inte smygas in genom att skriva i en redan monterad katalog. Rollback ska
återställa tidigare fakta-/konfigurationsversion och invalidera härledda
cacher utan att ändra prismanifest. En senare automatisk uppdatering ska
använda samma validerade staging/publiceringsflöde och befintligt driftlås.

## 5. Sols arbetsordning och leveransgrindar

1. **Kontrakt och regressioner:** lägg till riktade prov för referens +
   oberoende förbättringsspår, audit-fallback, identiteter och budgetslut.
   Bevara 761,45 mot 783,42 i Lund/fördelning samt proxy-motexemplet.
   Inkludera kall/varm körning, borttagen cache, append-only-utökning,
   återkallat recept, ändrade fakta och privata indata. Gör inga stora nya
   benchmarkkörningar innan dessa små prov passerar.
2. **Arkiv och sökpolicy:** implementera referens, publiceringskedja,
   budgeterad förbättring och korrekt diagnostik opt-in. Bevisa att en
   dyrare/ogiltig kandidat inte kan ersätta giltig vinnare. En cachemiss
   får inte tyst minska garantins räckvidd.
3. **Förberedelse:** implementera exakt återanvändning och inkrementella
   recepttillägg, atomicitet, minnesgränser och befintlig admission.
   Mät pilot 262/5 000 för standard, fördelning och organic-share i båda
   städerna. Jämför samma kod, resurser, underlag, profiler och cacheläge.
4. **Axfood separat:** härda arkiv/inhämtning/identitet, återfinn eller bygg
   underlag, berika och kör de 14 profilparen. Leverera separat granskbart
   releaseunderlag; låt inte ett långvarigt sökexperiment blockera en
   i övrigt verifierad faktaberikning.
5. **Slutmatris och standardbeslut:** sju profiler × två städer ×
   262/1 000/2 000/5 000, gamla respektive nya policyn; v5 vid 262.
   Använd frysta hashbundna originalfakta och dessutom Axfood-underlag för
   den release som ska använda berikningen. Kör minst tre mätningar för
   latensjämförelser. Behåll separata mått för kall disk, ny process med
   varm disk, första anrop, upprepade anrop, kö, förberedelse,
   kvalificering, sökning, audit och peak RSS/cgroup.

Standardbyte kräver noll oförklarade pris-/utfallsregressioner mot bas,
föregående publicerade storlek och gamla sökningen på samma storlek för
hela matrisen. Inga kvalitetskrav sänks. Latensmålet ovan och 3 GiB-taket
ska verifieras; missad 2,5 GiB-marginal ska redovisas och åtgärdas före
ökad samtidighet. En prewarm-träff är inte bevis för snabb kallstart.

Kör relevanta riktade offlineprov, Ruff, compileall och slutligen full CI
inklusive browserprov för appändringarna. Spara kommandon, pinnar, alla
hashar, status per cell och maskinläsbara jämförelser. Uppdatera HANDOFF med
vad som faktiskt är implementerat, verifierat, aktiverat och återstående.
Om någon grind faller: lämna den nya sökpolicyn opt-in och rapportera det
konkreta motexemplet. Skriv inte ”klart” för enbart passerade smoke tests.

## 6. Kodens integrationspunkter

| Ansvar | Befintliga delar att utgå från |
| --- | --- |
| Kandidater, kontext, basket, audit | `backend/app/services/personal_planner.py` |
| Sökspår och kandidatarkiv | `menu_optimizer.py`, `library_search_cohorts.py`, `week_refinement.py` i samma katalog |
| Receptidentitet/förberedelse | `recipe_library.py`, `recipe_preparation.py`, `recipe_computation_cache.py` |
| Delad resolution och resurser | `planner_shared_cache.py`, `planner_admission.py`, `plan_jobs.py`, `plan_prewarm.py` |
| Axfood-fakta och export | `axfood_product_details.py`, `backend/scripts/augment_review_facts.py` |
| Kontrollerad detaljhämtning | `scripts/fetch_axfood_product_details.py` och befintliga kedjeklienter |
| Benchmark och tidigare evidens | `backend/scripts/planner_acceptance_matrix.py`, `docs/reviews/integration-scaling-20261023/` |

Små interna moduler för kontext och resultatarkiv är lämpliga om de förenklar
ansvaret; håll dem under samma planner och befintliga lager. Lägg ingen
global optimeringslösare, approximativ produktidentitet eller ny extern
infrastruktur på den kritiska vägen i detta uppdrag.
