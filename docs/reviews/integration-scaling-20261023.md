# Integrationsgranskning och fortsatt receptskalning, 2026-10-23

Utgångspunkt är main `2efb62f219b31fa6a81c16ba71363b4207cb2dfe` och
[`CODEX-NEXT-20261023.md`](../CODEX-NEXT-20261023.md). Granskningen omfattar verkliga frysta
serverfakta, full CI, 84 screeningiterationer och 238 skalningsceller. **Sammanslagna
kohorter förblir av som standard.** Prisvillkoret faller och kvalificeringstiden växer
fortfarande med biblioteket. Ingen produktionsaktivering, schedulerändring, butiksinsamling
eller skrivning till aktiva prismanifest har utförts av denna granskning.

## Verifierad integration

Full CI på hämtad main: **2 950 PASS, 10 XFAIL, 53 SKIP**, [körning
39907572666](https://github.com/ossebosse/smako/actions/runs/39907572666). Full CI på
slutkandidatens appkod `b139cd4`: **3 012 PASS, 10 XFAIL, 53 SKIP**, [körning
39932160676](https://github.com/ossebosse/smako/actions/runs/39932160676). Båda inkluderar
Chromium/WebKit och webbläsartester. Lokala riktade prov, Ruff och compileall passerar för
ändrade delar.

Exporten läste de faktiska aktiva prisartefakterna och `load_retained_facts` mot serverns
SQLite/råsnapshots, monterade skrivskyddat. Artefakternas manifesthashar verifierades före
läsning. Axfood-produktdetaljer var avstängda; inga butikskällor anropades. Lunds frysta
klocka är `2026-10-23T05:58:59.183522+00:00`, Malmös `2026-10-23T06:00:02.869273+00:00`.
Senare ordinarie prisuppdateringar ändrar inte dessa återspelningsunderlag. Alla
indatahashar finns i [maskinunderlaget](integration-scaling-20261023/results.json).

| Kontroll | Lund | Malmö |
| --- | ---: | ---: |
| Prisprodukter / produktfakta | 44 754 / 42 697 | 89 458 / 71 138 |
| De 40 recepten: kvalificering och kassakontroll | 40/40 | 40/40 |
| Äggnamn granskade | 190 | 333 |
| Godkända hela skalägg, samtliga med användbara gram | 97 | 186 |

Alla godkända unika äggnamn granskades: hela skalägg, inga sammansatta äggprodukter.
Råbesluten bevarar produkt-/butiksidentitet, snapshot, förpackning, ingredienser och mängd.
Detta är sortimentet vid exporten, inte en garanti för framtida produkter.

Innehållskontrollen omfattar alla 40 recept vid 1/2/4/6 portioner: 160
struktur-/mängdkontroller, beroendeordning, 16 kött-/fiskrecepts 63/72/74 °C och 53 skalbara
vattenmängder. Tidigare redovisad ospecificerad mängd kokvatten och linstyp kvarstår som
redaktionella begränsningar. Recepten har inte provlagats.

`_mass_blocking` undantar nu endast de sju faktiskt kända näringskonflikterna. Okända namn
med prefixet `nutrition` blockerar mängdbeviset. Näringsspärren bevaras. Negativa prov
omfattar annan produkt, butik, snapshot, mängd och enhet, saknad hash samt motstridiga
mängdbevis; 93 riktade prov passerar.

### Tidigare och nuvarande screening

Original-main kördes med `--screen-margin -1` respektive dagens 0,1 för sju profiler i båda
städerna, tre iterationer per arm, seriellt med två CPU och 3 GiB. Alla **14 par behåller
utfall och pris i samtliga tre iterationer**. De 13 lyckade profilerna har dessutom identisk
semantisk hash. Malmö vegan är `SEARCH_BLOCKED` i båda armarna. Varm median avser de två
senare anropen, ingen kö-/lastkapacitet.

| Stad/profil | Pris i båda, kr | Varm median tidigare → standard, s |
| --- | --- | --- |
| Lund standard | 487,85 | 26,26 → 24,83 |
| Lund protein40 | 775,32 | 52,74 → 51,11 |
| Lund all-macros | 802,68 | 118,92 → 118,35 |
| Lund vegan | 347,90 | 12,84 → 12,85 |
| Lund distribution | 761,45 | 29,26 → 29,67 |
| Lund organic-share | 314,24 | 96,61 → 79,31 |
| Lund breakfast-snack-weight | 64,06 | 2,70 → 2,76 |
| Malmö standard | 511,46 | 30,82 → 28,98 |
| Malmö protein40 | 1000,86 | 16,47 → 16,55 |
| Malmö all-macros | 1000,86 | 17,15 → 16,73 |
| Malmö vegan | spärrad | 4,02 → 3,77 |
| Malmö distribution | 996,22 | 18,30 → 17,17 |
| Malmö organic-share | 321,16 | 145,84 → 132,58 |
| Malmö breakfast-snack-weight | 53,16 | 6,05 → 6,08 |

[Standardregressionen](integration-scaling-20261023/default-regression.json) kontrollerar
dessutom slutkodens main/262 mot alla tre ursprungliga main-iterationer, efter identiska
indata och sju sökinställningar: alla 14 profiler har samma utfall/pris och samtliga lyckade
menyer har oförändrad semantisk hash.

## Sökning och prisvillkor

Alla 238 celler är avslutade: main/K16/K32/K48, två städer, sju profiler, 262/1 000/2 000/5
000 recept samt den obegränsade v5-referensen vid 262. Varje bibliotek byggdes med ordinarie
`author --import` i isolerade Git-worktrees. Varje tidigare fullständigt receptvärde,
proveniens och hash bevaras i nästa storlek. Main-checkoutens receptinnehåll ändrades inte.
Den ursprungliga byggarens olika sista delpaket gav olika proveniens och ersattes därför
före slutmätningen.

Lund använder en Windowsprocess per bibliotek med källa `c9390dd`; Malmö kör `b139cd4`
seriellt i isolerade containrar med två CPU, 3 GiB, `--memory-swap 3g`, skrivskyddad
kod/indata och avstängt nät. Varje plan har ny tom syntetisk användarstatus; offentlig
förberedelse delas inom processen. Det är en observation per cell. Tiderna är inte upprepade
kapacitetsmätningar och städernas plattformstider ska inte jämföras direkt.

Lunds 5 000-block återupptogs efter att kontrollprocessen hade avslutats före första
planresultatet, utan belagd OOM. Startup/logg bevarades separat. Samtliga 28 accepterade
celler kommer från en enda ny process med samma kod/indata och befintlig förberedelsecache.
Första planens tid är därför inte en mätning av tom diskcache. Detta står även i
körkvittensen.

Enda appskillnaden mellan dessa kodversioner är den nödvändiga negativa kapacitetskontrollen
nedan. [AST-beviset](integration-scaling-20261023/capacity-code-proof.json) verifierar att
befintlig kod är oförändrad när tillägget tas bort. En tidigare godkänd komplett meny visar
att avvisningsvillkoret är falskt. Sex nya körningar av standard/fördelning/vegan med main
och K48 i Lund/262 på `b139cd4` ger också exakt samma priser, semantiska hashar och godkänd
slutkontroll som de återanvända mätningarna. Kod-/tidsversionerna står uttryckligen per
cell; blockerade Malmöfall mäts med den nya kontrollen.

| Stad/profil | Main 262, kr | K48 262 | K48 1 000 | K48 2 000 | K48 5 000 |
| --- | --- | --- | --- | --- | --- |
| Lund standard | 487,85 | 487,85 | 487,85 | 487,85 | 487,85 |
| Lund protein40 | 775,32 | 775,32 | 683,83 | 681,57 | 681,57 |
| Lund all-macros | 802,68 | 802,68 | 727,37 | 713,70 | 701,60 |
| Lund vegan | 347,90 | 335,35 | 315,53 | 315,53 | 315,53 |
| Lund distribution | 761,45 | 783,42 | 775,53 | 773,83 | 769,29 |
| Lund organic-share | 314,24 | 314,24 | 310,86 | 310,86 | 286,32 |
| Lund breakfast-snack-weight | 64,06 | 64,06 | 64,06 | 64,06 | 64,06 |
| Malmö standard | 511,46 | 501,24 | 496,53 | 492,78 | 488,88 |
| Malmö protein40 | 1000,86 | 1000,86 | 1000,86 | 904,82 | 904,82 |
| Malmö all-macros | 1000,86 | 1000,86 | 1000,86 | 951,42 | 919,11 |
| Malmö vegan | spärrad | spärrad | spärrad | spärrad | spärrad |
| Malmö distribution | 996,22 | 996,22 | 996,22 | 996,22 | 996,22 |
| Malmö organic-share | 321,16 | 321,16 | 318,96 | 318,96 | 297,99 |
| Malmö breakfast-snack-weight | 53,16 | 53,16 | 53,16 | 53,16 | 53,16 |

Tabellen illustrerar K48; maskinunderlaget innehåller alla fyra sökarmar vid samtliga
storlekar. Även samma storlek visar sökmissar: Lund 1 000/standard ger main 483,43 kr mot
K48 487,85 kr. Lund 5 000/fördelning ger main 704,30 kr mot K48 769,29 kr.

Antal brutna pris-/utfallsvillkor per arm (samma cell kan bryta båda jämförelserna):

| K | Mot main/262 | Mot föregående storlek | Godkänd som standard |
| --- | --- | --- | --- |
| 16 | 4 | 0 | nej |
| 32 | 4 | 0 | nej |
| 48 | 4 | 0 | nej |

Även v5-referensen vid 262 har kontrollerats för samtliga armar/profiler. De enda
priserna över denna referens är Lund/fördelning med K16/K32/K48.

De giltiga menyerna blev inte dyrare mellan de fyra nästlade storlekarna i de 126 uppmätta
angränsande jämförelserna; Malmös veganprofil förblev blockerad. Detta är en empirisk
kontroll, inte en garanti för godtyckliga bibliotek. Samtliga basprisbrott ovan gäller
Lund/fördelning vid de fyra storlekarna.

Lund 262/fördelning är ett tydligt motexempel: main och v5-referensen 761,45 kr, samtliga K
783,42 kr (+21,97 kr, +2,89 %). Den billigare menyn är giltig. De nya sökspåren börjar båda
vid 999,19 kr. Main går via generation 8 (934,94), 11 (819,17) och 12 (764,96), sedan
parförfining vid 13 till 761,45. Den geometriska sökningen hoppar från generation 2 till 13
och stannar på 783,42. Oberoende slutkontroller bekräftar båda menyerna. Prefixarkivet
bevarar det sammanslagna lägets färdiga vinnare; det återskapar inte per-paket-sökningens
andra mellanliggande väg. Större K är ingen monoton kvalitetsgaranti: fler prov ändrar även
sökvägen. Lund vegan vid 262 förbättras 347,90 → 335,35 kr med uttömmande småpoolsökning,
men tar längre tid. Den förbättringen upphäver inte prisregressionerna.

### Historiska Lund 1 000 (+0,8 %)

Exakt tidigare serverunderlag återfanns med faktahash
`409ac1fbbba7c81bd87cce69434c60e85121862938ca252238c1f4fbbcb36c2e`. Per-paket-main ger
474,43 kr, K16 474,43, K32 478,35 och K48 469,84 kr. K32 följer en annan ersättningsföljd
via 479,85 till 478,35; main når 474,43 i andra förfiningen. Kraven ogiltigförklarar inte
den billigare menyn. Det är ett lokalt minimum i den begränsade sökningen.

Kontrakt `smako-merged-library-search-v3` arkiverar färdiga vinnare vid hela
publiceringsprefix upp till 512 och vid 1 000/2 000/5 000 gånger tiopotenser.
Prefixförfiningar återförs inte till den geometriska huvudsökningen: en första sådan variant
tappade den billigare menyn och ersattes. K48 på det exakta historiska underlaget behåller
nu 469,84 kr (125,96 s första anrop, 36,12 s varmt, lokalt). K32:s alla sökmissar är inte
därmed generellt lösta.

Små utbytbara genererade pooler genomsöks uttömmande när högst 4 096 veckokombinationer
finns, utan privata skafferiuttag eller produktlås. Alla befintliga krav körs och vinnaren
slutkontrolleras oberoende. Riktade prov omfattar en billigare meny som kräver tre samtidiga
byten, privat skafferi, olika måltidstyper och avvisad slutkontroll. Detta bevisar inte
globalt lägsta produkt-/näringspris eller monotonicitet för alla godtyckliga bibliotek.

Diagnostikfältet `week_search_method` kan ange uttömmande kombinationer efter ett litet
prefix även när resten av biblioteket söks begränsat. Prefixradernas omfattning måste därför
läsas; `global_optimum_proven` är alltid falskt.

Det specifika äldre Malmö/Axfood-fallet 361,81 kr trots en giltig meny för 340,64 kr är inte
empiriskt återverifierat här: detaljarkivet saknas i de kända underlagen. Småpoolsstrategin
är genomförd och testad, men den nya serverexportens blockerade veganprofil ersätter inte
provet på de äldre berikade fakta.

## Kvalificering, processstart och minne

Standardprofilens planeringsdelar, sekunder (en observation; första main-cellen innefattar
processens första planförberedelse, K48 kommer senare i samma process):

| Stad | Recept | Main totalt | K48 totalt | K48 kvalificering | K48 veckosökning |
| --- | --- | --- | --- | --- | --- |
| Lund | 262 | 62,27 | 22,73 | 4,71 | 15,38 |
| Lund | 1000 | 121,89 | 32,29 | 7,76 | 21,68 |
| Lund | 2000 | 225,29 | 42,38 | 10,82 | 28,40 |
| Lund | 5000 | 382,44 | 62,80 | 22,27 | 36,42 |
| Malmö | 262 | 60,05 | 64,41 | 9,94 | 49,49 |
| Malmö | 1000 | 72,97 | 84,43 | 14,09 | 65,23 |
| Malmö | 2000 | 117,40 | 97,28 | 20,17 | 71,67 |
| Malmö | 5000 | 125,78 | 134,08 | 37,15 | 90,29 |

Svårare profiler tar fortfarande flera minuter: Malmö 5 000/organic-share tog 497,88 s med
main och 412,41 s med K16. Ingen generell latens- eller lastgaranti följer av dessa prov.

Proxyprovet använder samma `b139cd4`, Lund 1 000, K48, bibliotek, frysta indata och
sökinställningar som sin fullpoolskontroll. Hela basbiblioteket behålls; bland tilläggen
väljs de åtta lägst rankade per generation, måltidstyp och proteinkategori. Alla behållna
recept går genom ordinarie kvalificering och slutkontroll. Provet körs seriellt på Linux med
två CPU och 3 GiB efter Malmömatrisen, med separat gemensam förberedelsecache.

| Experiment | Pris, kr | Första anrop, s | Andra anrop, s | Senaste rangordning, s | Behållna/tillgängliga |
| --- | --- | --- | --- | --- | --- |
| full pool | 487,85 | 60,85 | 37,74 | — | hela poolen |
| proxy | 487,85 | 47,51 | ej mätt | 8,82 | 272/946 |
| proxy-memo-oracle | 487,85 | 47,02 | ej mätt | 9,46 | 272/946 |
| proxy-memo | 487,85 | 45,99 | 33,95 | 1,18 | 272/946 |

Alla tre proxyvarianter behåller exakt samma receptidentiteter och ger ingen prisregression
i detta fall. Den lokala radmemon binder namn/mängd/enhet och samma faktiska frysta
kandidatobjekt. Orakelprovet räknar om varje träff med ursprunglig offertfunktion och
bekräftar samma minima. Det är ett validerat experiment för en profil, inte ett tillräckligt
underlag för allmän produktionsgallring. Process-/cacheordningen gör tiderna till
observationer, inte en isolerad orsakskvot.

Ytterligare två matchade jämförelser vid **5 000 recept**, på samma Linuxresurser och
slutkod, kontrollerar proxy med radmemo mot hela poolen för K32 och K48. Varje arm körs två
gånger i en ny process; andra anropet redovisas nedan. Första platsens
kvalificeringsresultat återlämnas till ordinarie sökcache i alla proxykörningar.

| K | Full pool, kr | Proxy, kr | Full pool andra anrop, s | Proxy andra anrop, s | Behållna/tillgängliga | Ej dyrare |
| --- | --- | --- | --- | --- | --- | --- |
| 32 | 480,97 | 487,85 | 73,92 | 50,07 | 528/4946 | nej |
| 48 | 487,85 | 487,85 | 73,90 | 51,03 | 528/4946 | ja |

Proxyurvalet förlorar en billigare giltig fullpoolsmeny i minst ett av dessa fall. Det får
därför inte införas som generell gallring; den bättre tiden vid 1 000 upphäver inte
prisregressionen.

Två nya Linuxprocesser med varm diskcache från samma slutkod, Malmö 5 000/K48, verifierar
identiska indata, metodsignatur, bibliotek, sju sökinställningar, kontrakt, pris och
semantisk hash mot matrisen. Yttre monoton tid innefattar Dockerstart, Pythonimport,
läsning/hashning/parsing, planering, kassakontroll, rapport och avslut. Båda processerna
rapporterar varm disk vid start.

| Process | Hela processen, s | Modellinläsning, s | Planering, s | Träffar/missar/skrivningar |
| --- | --- | --- | --- | --- |
| process-warm-a | 187,02 | 33,10 | 145,44 | 8217/2142/0 |
| process-warm-b | 188,11 | 33,31 | 146,52 | 8217/2142/0 |

Den begränsade cachen måste inte innehålla alla bibliotekets nycklar: innehållstaket är
fortsatt 4 096. Missar återberäknas och ogiltiga poster blir aldrig auktoritativa. En full
katalog undviker upprepade storleksskanningar via en begränsad ändringstidsbunden
ögonblicksbild; varje verklig skrivning kontrolleras fortfarande mot ordinarie
antal-/bytegränser.

Offertbudgeten räknar nu även namngivna offerter, frysta korgrader, radoberoende
offertuppsättningar och strukturella sidomappar. Historikens register återanvänder exakt
samma registrerade källobjekts skalade modeller; äldre eller andra källobjekt skalas
separat. Full struktur-/innehållskontroll och spärr mot motstridiga utfärdade versioner
består. Ingrediens-/designträd delas bara när de är rekursivt frysta, efter full
kvalificeringsvalidering och exakt utfärdat innehåll. Muterbara listor/formulärdata
kopieras. Svaga referenser i den rena ID-cachen håller inte avslutade anrops recept vid liv.
**1 310 skalningar och 1 310 kvalificerade värden/ID:n är identiska** med tidigare kod, utan
ändrade källrecept.

Alla 119 Malmöceller, inklusive samtliga sju profiler och båda portionsstorlekarna i samma
biblioteksprocess, slutfördes under oförändrat **3 GiB-tak**. Högsta rapporterade RSS är **3
149 504 512 byte** (2,93 GiB), högsta cgroup-minne **3 167 059 968 byte**. Processernas
toppvärden är kumulativa över föregående profiler. Detta verifierar matrisens minnesbudget,
inte många samtidiga användare eller alla kombinationer av portionsstorlekar. Serverns
ordinarie drift kan förekomma parallellt på värddatorn; containergränsen är ingen
reservation av dedikerade CPU-kärnor.

Tidigare misslyckanden är bevarade: `5e5bc89` dödades av 3 GiB vid första Malmö 5
000-standardcellen efter 327,64 s. `652e7ac` klarade main och K16 men K32 gav verifierad
Docker-OOM efter 472,03 s totalt. Att en standardcell passerade var alltså otillräckligt.
Dessa och lokala parallella körningar som uttömde minnet är felsökningsunderlag, inte
slutmatrisens resultat. Äldre varmdiskmätningar med olika bibliotek/kod eller överlappande
jobb används inte som slutkandidatens isolerade hastighetskvot.

### Bevisat omöjlig veganpool

`c9390dd` slutförde 12 positiva Malmö 5 000-celler, men vegan/main gav inget resultat efter
887,81 s och stoppades kontrollerat. Det var inget OOM. Kvalificeringen lämnade 852 recept,
samtliga med rättformen `plated_meal`. Tak två per form och begärda tre middagar innebär
kapacitet **2 < 3**.

`b139cd4` använder samma uttryckliga mappning/skiftlägeshantering som acceptansen för att
bevisa denna nödvändiga brist före veckosökningen. Okända former, avstängt tak och anpassade
resolvrar/optimerare ger inget avvisningsbevis. Tillräcklig kapacitet garanterar aldrig en
giltig meny. Ingen klassificering eller regel sänks.

Kallt prov med samma underlag: `BLOCKED`/`SEARCH_BLOCKED`, veckosteget 0,624 ms, hela
processen inklusive Docker/import/inläsning 216,83 s, varav 172,24 s planering inklusive
kall förberedelse/kvalificering; peak RSS 2 635 038 720 byte. Det tidigare avbrottet är
ingen fullständig tidsreferens och används inte som total hastighetskvot. Fem riktade prov
innefattar uttömmande små formtilldelningar/menyer; 110 fokuserade sök-/ integrationsprov
passerar. Bevisets räckvidd är den kvalificerade poolen.

## Reproduktion och avgränsning

[README](integration-scaling-20261023/README.md) innehåller kod-/arkivpinnar,
biblioteksbygge, mätprotokoll och kommandon.
[results.json](integration-scaling-20261023/results.json) innehåller alla priser, tider,
indata-, metod-, biblioteks- och originalrapporthashar samt villkoren mot main/262,
föregående storlek och v5-referensen.
[followups.json](integration-scaling-20261023/followups.json) binder processstarter,
proxyprov och sökspår till deras kommandon/rapporter. Fullständiga rapporter och
hashverifierade offentliga exportarkiv bevaras utanför Git i
`.local/integration-scaling-20261023` och serverns
`/opt/smako/evidence/integration-scaling-20261023`.

De tidigare redovisade 503 Hemköp-koderna, lagring, uppdateringsrytm och aktivering av
`AXFOOD_PRODUCT_DETAIL_ROOT` kräver separat ägarbeslut. Den tidigare detaljsamlingen
återfanns inte i klonens kända underlag; berikning med den kan inte redovisas som
verifierad. Ingen hämtning eller aktivering gjordes. [PR
#7](https://github.com/ossebosse/smako/pull/7) samlar den granskade koden och mätningarna;
ett push till main aktiverar ingen beta.

Ett konkret förslag till detta separata beslut är värdlagring utanför Git,
`D:\smako-data\axfood-product-details` för insamling och en granskad kopia under
`/srv/smako/data/axfood-product-details` på servern. Containerexponering fastställs i
releasen. Nya koder tas från varje validerad katalog, med uttryckliga tak 1/s för Willys och
0,1/s för Hemköp; omprövningsrytmen för befintliga dokument behöver fastställas. Varje råfil
måste ha motsvarande metadata med status 200, identisk SHA-256 och exakt artikelkod; angivet
GTIN måste matcha. Observationstiden bevaras och befintliga deklarationer/priser skrivs inte
över.

När det betrodda arkivet finns ska `backend/scripts/augment_review_facts.py` skriva nya,
separata Lund-/Malmöexporter. Priser, begäran och klocka behålls byteidentiskt, medan
faktahasharna uppdateras. Alla sju profiler i båda städerna måste därefter mätas före en
eventuell aktivering. Inga föreslagna lagringsmappar, insamlingsjobb eller aktiveringar har
skapats av förslaget.
