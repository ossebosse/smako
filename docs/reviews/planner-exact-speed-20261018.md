# Kortare planering med samma meny och pris, 2026-10-18

**Slutversionens varma standardprov i Malmö: 55.88 → 52.21 sekunder (6.6 % kortare tid), med samma meny och pris 482,75 kr.** Ändringen återanvänder exakta butiksjämförelser och släpper mellanlagringen när den färdiga sammanställningen finns. Recepturval, söktak, prisregler, näringskrav och slutkontroller är oförändrade.

Kod: `90ddeeb2fea833047ae4b4f7153236cf91408240`, ovanpå första optimeringen `fefccce7f1595f34d5e6539b8b5f465176c66243`. [PR #3](https://github.com/ossebosse/smako/pull/3). Ingen produktionsaktivering ingår. De 20 nya prototyprecepten är fortsatt experimentunderlag.

## Slutversionens tidsjämförelse

Här jämförs **originalkoden** med **slutversionen**, med 242 recept i båda armarna. Sekunder, median. Kall betyder ny process och separat tom förberedelsecache. Varm är nästa kompletta planering i samma process. Indataladdning ligger utanför tidtagningen; konstruktion av PersonalPlanner och create ingår. Ingen profileringsinstrumentering används i dessa tider.

| Stad/profil | Läge | Före | Efter | Skillnad | Antal före / efter |
| --- | --- | ---: | ---: | ---: | ---: |
| Malmö, ekoandel | kall | 219.45 | 196.26 | -10.6 % | 1 / 1 |
| Malmö, standard | kall | 65.68 | 62.23 | -5.3 % | 1 / 1 |
| Malmö, standard | varm | 55.88 | 52.21 | -6.6 % | 2 / 2 |

Detta är en begränsad förbättring, inte en garanti för alla profiler eller lastnivåer. Standardfallet når fortfarande inte 30 sekunder. Ekoprovet har bara en observation per arm. Servern hade samtidigt ordinarie bakgrundsarbete; resultaten är inte ett p95- eller samtidighetstest.

## Samma pris och fullständiga resultat

Alla **11 slutkontroller** (referens och kandidat) passerar kvalitetskontroller och full checkout-audit. Kandidaten provas i samtliga fem stad/profil-fall nedan mot tidigare hashverifierade referenser. Dessutom passerade **40 körningar av första versionen och dess referenser** innan minnesrättelsen. De två versionernas tider blandas inte.

Hashen omfattar kompletta recept, varukorg inklusive köp-/prisvillkor och källbevis, näringsresultat, audit samt skafferifördelning. Samma hash är starkare än endast samma slutsumma. Ingen jämförd meny blir dyrare.

| Slutversionens kontroll | Pris före och efter, kr | Resultat-hash | Kandidatens tider, s (kall först) |
| --- | ---: | --- | --- |
| Malmö, standard | 482.75 | identisk | 62.23, 51.84, 52.57 |
| Malmö, alla makron | 915.84 | identisk | 35.68 |
| Malmö, ekoandel | 317.21 | identisk | 196.26 |
| Lund, standard | 516.54 | identisk | 42.28 |
| Lund, alla makron | 792.10 | identisk | 137.83 |

De tre fallen utan en ny originalkodskörning i denna slutserie är funktionella kontroller mot tidigare referenser. Deras tider används inte som bevis för en tidsvinst. Sökräknare redovisas i mätfilerna. Seed 40, refinement 90 och befintligt varianturval är oförändrade. Detta bevarar befintlig vinnare; det är inget nytt bevis för globalt optimum utanför de befintliga söktaken.

## Varför ändringen är exakt

1. Varje butik behåller sin billigaste tillåtna offert enligt hela den ordinarie sorteringsnyckeln, inklusive regler vid lika priser.
2. Butikerna besöks i den ordningen. Den första butik som ingår i en viss kombination är exakt samma vinnare som en separat jämförelse av alla dess offerter.
3. Bitmasker samlar kombinationerna med samma vinnare. Alla kombinationer finns kvar, inklusive lika vinnare och saknade varor. Mönstret återanvänds bara vid samma fullständiga butiksordning. Aktuella offertobjekt levererar alltid aktuellt belopp och verifieringsnivå.
4. Samma exakta summering, butiksmängd och slutliga produktjämförelse används. Kopplade kampanjer behåller sin separata beräkning. Avvikande Decimal-precision/exponenter behåller reservvägen.
5. All ny återanvändning ligger inom befintlig offertsession. Starka referenser hindrar felaktig återanvändning av objekt-id. Mellanlagringen släpps efter kompilering; vid ändrad Decimal-kontext kan den exakta sammanställningen byggas om från den bevarade oföränderliga vektorn. Sessionens återstående cache rensas vid avslut.

Fakta-, berednings- och integritetslås är oförändrade. Runtimeändringen ligger enbart i `backend/app/services/basket_optimizer.py`.

## Minnesrättelsen

Första ekoprovet blev 11,6 % snabbare men ökade RSS från cirka 2 480 till 2839 MiB. Det visade att både strukturella bitmasker och deras färdiga sammanställning hölls kvar. Slutversionen släpper den förbrukade mellanlagringen. Samma ekoprov använder nu 2482 MiB RSS efter planering. Regressionstestet kontrollerar att mellanlagringen faktiskt släpps och att byte av Decimal-kontext fortfarande ger exakt samma värden och statusflaggor.

RSS efter planering, median; peak-RSS är högsta rapporterade värdet i respektive arm. Containrarna har 3 GiB minnesgräns. Detta är ingen garanti för högsta möjliga minne vid andra indata eller samtidiga anrop.

| Slutversionens par | RSS före, MiB | RSS efter, MiB | Peak före / efter, MiB |
| --- | ---: | ---: | ---: |
| Malmö, ekoandel | 2479 | 2482 | 2480 / 2482 |
| Malmö, standard | 2496 | 2496 | 2497 / 2497 |

## Regression och CI

- Full lokal backendsvit för slutversionen: **2 835 PASS, 10 XFAIL, 2 SKIP**, exit 0. Tio redan kända fel kvarstår. Två taktester kräver särskilt `SMAKO_REVIEW_DATA`; inga markeringar eller krav har lättats.
- [Slutversionens GitHub CI 39151816555](https://github.com/ossebosse/smako/actions/runs/39151816555): **2 784 PASS, 10 XFAIL, 53 SKIP**, grön inklusive webbläsartester. CI saknar den lokala historiska evidensen för ytterligare 51 tester. Även första versionens [CI 39146825090](https://github.com/ossebosse/smako/actions/runs/39146825090) var grön.
- Fokuserade optimizer-, kampanj-, sökåteranvändnings- och ekvivalenstester passerar. Det nya testet jämför med uttömmande offertval vid lika priser, saknade butiker, olika mängder, förpackningar och butikstak samt ändrad Decimal-precision, exponenter och flaggor.
- Ruff på ändrade Pythonfiler och compileall passerar. Grocery-koden är oförändrad; dess tidigare fullsviter har inte körts om.

## Första versionens bredare mätning — före minnesrättelsen

Detta avser `fefccce`, inte slutversionen `90ddeeb`. Malmö standard förbättrades i båda körordningarna. Lund standard bytte riktning mellan blocken och gav ingen säker tidsvinst; Lunds näringsprofil blev 1–2 % långsammare i sitt enda kalla/varma par. Små skillnader ska tolkas försiktigt. Dessa resultat förklarar både avgränsningen och varför en minnesrättelse behövdes.

| Stad/profil | Läge | Original | Första versionen | Skillnad | Antal före / efter |
| --- | --- | ---: | ---: | ---: | ---: |
| Malmö, alla makron | kall | 35.99 | 36.04 | +0.1 % | 2 / 2 |
| Malmö, alla makron | varm | 29.80 | 28.63 | -3.9 % | 4 / 4 |
| Malmö, ekoandel | kall | 228.20 | 201.82 | -11.6 % | 1 / 1 |
| Malmö, standard | kall | 66.84 | 62.39 | -6.7 % | 2 / 2 |
| Malmö, standard | varm | 57.71 | 53.60 | -7.1 % | 4 / 4 |
| Lund, alla makron | kall | 131.93 | 134.27 | +1.8 % | 1 / 1 |
| Lund, alla makron | varm | 134.63 | 136.52 | +1.4 % | 1 / 1 |
| Lund, standard | kall | 42.66 | 42.66 | +0.0 % | 2 / 2 |
| Lund, standard | varm | 37.13 | 35.75 | -3.7 % | 3 / 3 |

## Reproducerbarhet och drift

- Baslinje: runtime från main `cfc0457`, samma kod som `ad0411f`. Alla 430 Pythonfiler i serverns baslinje verifierades mot Git. Slutversionens normaliserade SHA-256 för basket_optimizer.py: `888c3f6cccbb08309a2107c5abdc4f0107d35e0e1ef9e8d239656f6f15d0f5ac`.
- Pinnad image: `sha256:93bbfd2ebe3764cddd559422ed1fce53197359b6f0aabde50619dfc6a81cd8f7`. Sekventiella isolerade testcontainrar, 2 CPU, 3 GiB, nätverk avstängt och kod/bibliotek skrivskyddade. Ingen produktionsdatabas eller privat planlagring monteras.
- Samma frysta klocka `2026-10-18T05:12:49.467392+00:00`, priser, fakta och bibliotek som i [recepttillväxtprovet](recipe-growth-20261018.md). Den befintliga `planner_acceptance_matrix.py --baseline` verifierar indatamanifest och resultat-hash.
- Dataarkivets SHA-256: `ea895f92ec8bb6f4d6d953eb93243fcfebc37bf6df809ec118bbfc053aeee670`. Biblioteksmanifestets SHA-256: `2339a8a1451ac7242ee61e8c6bb50ff9cc2ea3701a287e97d24ed7660c02d110`.
- Testets lagringsgräns stoppade en fortsättning när ledigt utrymme föll till cirka 12 GB. En öppen temporär `source.sqlite3` på 6,62 GB identifierades under ordinarie prisuppdaterings `refresh-candidates` och lämnades orörd. Utrymmet återgick mellan faserna till cirka 18 GB. Testets egna hashverifierade indata packades därefter upp en stad åt gången; lagringsgränsen sänktes inte.
- Servern var inte fri från bakgrundsarbete. Körordning och upprepningar minskar men eliminerar inte mätosäkerhet. En administrativ statusläsning nådde sin timeout; det är inte godkänd full driftstatus. Publik `/ready` svarade därefter ready med samma build. Webbkö, HTTP-latens och p95 under last har inte mätts.

[Slutversionens mätdata](planner-exact-speed-20261018/measurements.json) och [första versionens 40 observationer](planner-exact-speed-20261018/initial-measurements.json) är separata. Fulla isolerade loggar, profiler och källkvitton bevaras lokalt och under serverns `evidence/planner-exact-speed-20261018`.

## Slutkontroll och arkivering

Slutkontrollen 18:17 UTC lyckades läsa administrativ lagringsstatus: **18,78 GB ledigt**, jämfört med beräknat behov **13,99 GB**. Publik `/ready` svarar 200/ready med oförändrad build `joint-week-refinement-app-e041451` och image ovan. `PRICE_UNIVERSE_PREWARM_ENABLED=false` är verifierat både i körande container och serverns miljöfil. Inga av experimentets containrar är kvar. Detta ersätter den tidigare okända lagringsstatusen, men är inte ett nytt fullständigt drift- eller lasttest.

Experimentets rapporter, loggar, profiler, körskript och båda kodversioner är arkiverade i `evidence/planner-exact-speed-20261018/experiment-results.zip` på servern och kopierade lokalt. Arkivet innehåller 87 poster, är 539 294 byte och har SHA-256 `129bcf3065d45e6082af9113623f5cd85ecc868e7cd533dea2cdcf6de473f37c`. Innehåll och CRC verifierades före rensning; den lokala kopians hash och CRC verifierades efter hämtning. Slutrensningen tog bort 168 503 956 byte egna temporära indata och förberedelsecache. Originalarkivet med frysta indata finns kvar; ingen produktionsdata raderades.
