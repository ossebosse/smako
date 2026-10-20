# Receptskalning: mätning och exakta förbättringar, 2026-10-19

Uppgift: [CLAUDE-RECIPE-SCALING.md](../CLAUDE-RECIPE-SCALING.md). Steg 1
(reproducerbar referens och profilering), tre ändringar som inte ändrar
resultatet, ett prövat och förkastat förslag, en mätning av om en bevisad
kostnadsgräns kan beskära substitutionen, samt ett nytt tak för substitutionen
(ägarbeslut 2026-10-20, avsnitt 4). Inga kvalitetskrav är ändrade.
Inga syntetiska recept ligger i produktionsbiblioteket.

## 1. Beslut

**1 000 recept: cirka 44 s i Lund och 52 s i Malmö, inte under 30 s.**
Varm standardplanering före allt arbete: 125 s och 165 s. Med 2 000 recept:
61 s och 76 s (utan substitutionstaket 136 s och 202 s). Med dagens 222 recept:
33–36 s. De exakta ändringarna ger samma resultathash som före. Substitutionstaket
(160) ger samma pris som hela svepet i alla 14 profil/stad-körningar vid
1 000 recept och i de fyra körningarna vid 2 000; 13 av 14 har samma hash.

Det som hindrar nästa nivå, i storleksordning:

1. **Generationssubstitutionen saknar tak.** Sökningen startar på
   generation 2 (seed, tak 40) och prövar sedan *varje* recept från senare
   generationer i *varje* middagsplats, två svep. Vid 1 000 recept är det
   7 778 förslag och 2 932 hela korgberäkningar, 54 % av alla korgar.
   Seed (959 korgar) och förfining (tak 90) är konstanta. Se tabell 3.
2. **Korgberäkningen är dyr i planerarlagret.** Varm profil vid 1 000:
   `basket()` 121 s kumulativt för 5 417 anrop, varav bara 49 s i
   `BasketOptimizer.optimize`. Resten är behovsrader, `resolve`
   (310 000 anrop), pydantic-objekt och spårning, upprepat för varje vecka
   trots att fyra av fem recept är desamma som i föregående förslag.
   Delvis åtgärdat i `c638ee6`.
3. **Kandidatkvalificering per anrop.** En enreceptskorg per kandidat och
   anrop: 12–20 s varmt vid 1 000 recept, 34–45 s kallt. Samma arbete görs om
   i nästa anrop med samma priser, scope och profil. Produktupplösningen
   delas nu (`c638ee6`); att dela hela korgen gav ingen nettovinst.
4. **Minne.** Malmö når 2,7 GB peak RSS vid 1 000 recept. Med serverns
   3 GiB-gräns är 2 000 recept i Malmö sannolikt inte möjligt utan
   minnesåtgärd. Inte uppmätt här.

## 2. Ändringar

| Commit | Ändring | Varför resultatet är oförändrat |
| --- | --- | --- |
| `9653e29` | `LazyPairwiseSimilarities`: kulinarisk parlikhet räknas när sökningen frågar efter ett par, inte alla n·(n−1)/2 par före sökningen | Samma nycklar, värden, ordning och argumentordning som den tidigare dicten. Testat mot den tidigare loopen på 70 riktiga middagar (exakt flyttalslikhet) och med samma resultathash i båda städerna vid 222 och 1 000 recept |
| `5468645` | Variantbevis (`variant_search_evidence`) behålls för varje kvalificerat recept i anropet; tidigare fast LRU på 2 048 | Seed-tak, variantlista och gemensamma förslag behåller alla recept *utan* bevis. Över 2 048 varianter förstorades därför seedsökningen tyst. Ingen skillnad under 2 048 (alla mätningar här) |

Den kvadratiska delen var 404 550 jämförelser och cirka 28 s per anrop vid
1 000 recept (profil). Vid 5 000 recept hade den varit cirka 12,5 miljoner.

| `c638ee6` | Inom ett anrop: behovsrader per (plats, rensat recept, måltid) inklusive `demand_key` byggs en gång; sammanslagen profil och JSON för anropskonstanta modeller i cachenycklar räknas en gång per objekt. Mellan anrop: `resolve()` (kvalificerade, prissatta kandidater eller ett fel utan diagnostik) delas i en processlokal LRU, 4 scope × 32 768 poster | Samma värden som tidigare beräknades per rad. Delningens scope täcker allt `resolve` läser utöver sin nyckel: exakt prisuniversum, faktaversion (innehållshash), vy-identitet (kontexter, urval, Stockholmsdatum), användbara butiker, medlemskap/kuponger, prisdatum, inköpsläge, complete-läge och inställningar. Scope läses från planerarens aktuella attribut vid varje miss. Spårade produkthändelser spelas upp som vid en lokal träff. `SMAKO_PLANNER_SHARED_RESOLUTION=0` stänger av. Testerna börjar med tom cache |

Kvarstående begränsningar: lås, prisursprung, produktidentitet, allergen-,
närings- och verifieringskrav samt slutlig checkout-audit är orörda. Endast
produktupplösning delas mellan anrop; korgar, näring och audit beräknas alltid
i det egna anropet. Den delade cachen ökade peak RSS med cirka 20 MB.

### Effekt per ändring (varm standard, median av två, sekunder)

| Stad, recept | Före | + parlikhet vid behov | + återanvändning i anropet | + delad upplösning |
| --- | ---: | ---: | ---: | ---: |
| Lund, 222 | 43,4 | 44,5 | – | 35,9 |
| Lund, 1 000 | 124,9 | 105,8 | 95,3 | 85,1 |
| Malmö, 222 | 58,5 | 56,0 | – | 40,5 |
| Malmö, 1 000 | 165,4 | 151,1 | – | 126,0 |

Kall tid (ny process, tom cache) vid 1 000: Lund 138,7 → 106,6 s, Malmö
178,3 → 147,5 s. Den delade upplösningen hjälper bara anrop med samma scope
(samma butiker, medlemskap, inköpsläge och dag); kalla och nya scope får
endast de två första förbättringarna.

### Prövat och förkastat: delad enreceptskvalificering

Hela enreceptskorgen och variantbeviset delades mellan anrop med identiskt
anrop (scope plus hash av hela begäran och privat tillstånd). Kvalificeringen
sjönk från cirka 8 s till 2,7 s vid 1 000 recept, men veckosökningen blev lika
mycket långsammare: kvalificeringskorgarna värmer optimerarens offert- och
paketcacher som veckokorgarna sedan använder. Netto Lund 85,1 → 90,9 s,
Malmö 126,0 → 124,8 s, inom spridningen, och +110 MB minne i Lund. Inte
committad; patchen finns i
[rejected-shared-qualification.patch](recipe-scaling-20261019/rejected-shared-qualification.patch).

### Substitutionen: en bevisad gräns räcker inte

Vid 1 000 recept i Lund jämfördes varje hel veckokorg med en konservativ
undre gräns från samma kvalificerade kandidater: billigaste enstaka förpackning
per ingrediensgrupp, grupper med gemensam produkt sammanslagna, noll för
produkter med kampanj, vikt- eller styckpris utan fast pris. Den gränsen kan
aldrig överstiga det verkliga beloppet (0 överträdelser på 3 661 veckor), men
den är bara 28–51 % (median 37 %) av det verkliga beloppet. Högsta gräns var
371,73 kr; den vinnande menyn kostar 497,19 kr. **Noll veckor hade kunnat
beskäras.** En gräns som tar hänsyn till mängder, butikstak och kampanjer är i
praktiken samma beräkning som korgen själv. Se
[bound-tightness-lund-1000.json](recipe-scaling-20261019/bound-tightness-lund-1000.json)
och `bound_tightness.py`.

Att göra substitutionen billigare kräver därför ett produktbeslut, till exempel
att nya generationer söks med samma seed-urval (tak 40) som det första
biblioteket i stället för varje nytt recept i varje plats. Det är en heuristik
och ska valideras mot fullbiblioteksreferensen innan den används.

## 3. Mätningar

Kod `00123b7` (före) och `9653e29` (efter). Två CPU (Intel Xeon 2,8 GHz),
7 GiB minne, Python 3.12.3, nätverk blockerat av matrisen. Frysta indata från
`smako-followup-public-data-20261018.zip` (SHA-256 `d3a93b88…`), klocka
`2026-10-18T05:12:49.467392+00:00`, samma som granskningen 2026-10-18.
En process per rad: en kall och två varma planeringar. Ingen upprepning i
omvänd ordning ännu; spridningen mellan varma körningar är upp till 14 s vid
1 000 recept. Denna miljö är cirka 15–20 % långsammare än serverns referens
(Malmö 222 varm: 58,5 s här, 49,6 s där). `5468645` påverkar inte dessa
storlekar (under 2 048 varianter) och är inte separat tidsmätt.

Bibliotek: nuvarande 222 recept (189 middagar: 94 grundrätter, 95 variationer).
Testbiblioteken lägger till syntetiska middagar via ordinarie `author --import
--prepare 4` i isolerade worktrees: 500 recept (467 middagar: 224 grundrätter,
243 variationer) och 1 000 (967: 457 / 510). Noll author-varningar och
avvisningar. Detaljer och hashar: [library-manifest.json](recipe-scaling-20261019/library-manifest.json).

Standardprofilen (fem middagar, fyra portioner, två butiker, estimated):

| Stad | Recept | Kod | Pris, kr | Hash | Kall, s | Varm, s (median, n=2) | Korgar | Peak RSS |
| --- | ---: | --- | ---: | --- | ---: | ---: | ---: | ---: |
| Lund | 222 | före | 548,76 | `2d9bf97b3d91` | 48,8 | 43,4 | 2 043 | 1,55 GB |
| Lund | 222 | efter | 548,76 | `2d9bf97b3d91` | 50,7 | 44,5 | 2 043 | 1,55 GB |
| Lund | 500 | före | 502,60 | `4d90e34b98e4` | 81,4 | 63,9 | 3 283 | 1,63 GB |
| Lund | 1 000 | före | 497,19 | `a42011665fa8` | 138,7 | 124,9 | 5 419 | 1,81 GB |
| Lund | 1 000 | efter | 497,19 | `a42011665fa8` | 127,5 | 105,8 | 5 419 | 1,77 GB |
| Malmö | 222 | före | 534,92 | `4fbc3f8f6847` | 70,6 | 58,5 | 1 472 | 2,47 GB |
| Malmö | 222 | efter | 534,92 | `4fbc3f8f6847` | 68,4 | 56,0 | 1 472 | 2,47 GB |
| Malmö | 500 | före | 493,65 | `5385f1b0a8ee` | 92,3 | 90,2 | 3 293 | 2,54 GB |
| Malmö | 1 000 | före | 495,85 | `77cf63bdd55f` | 178,3 | 165,4 | 5 720 | 2,71 GB |
| Malmö | 1 000 | efter | 495,85 | `77cf63bdd55f` | 173,0 | 151,1 | 5 720 | 2,68 GB |

222-receptspriserna 548,76 och 534,92 kr är desamma som serverns referens i
[recepttillväxten](recipe-growth-20261018.md). Fler recept ger billigare
menyer (som väntat), men de syntetiska recepten är inte provlagade och priserna
säger inget om verkliga recept. Malmö 1 000 är 2,20 kr dyrare än Malmö 500:
ett exempel på att den begränsade sökningen inte bevisar optimum. Det ska
utredas mot en fullbiblioteksreferens innan någon sökändring godkänns.

Sökfaser i Lund (ett kallt anrop, [search-phases.json](recipe-scaling-20261019/search-phases.json)):

| Fas | 222: korgar | 500: korgar | 1 000: korgar |
| --- | ---: | ---: | ---: |
| Seed (generation 2, tak 40) | 919 | 959 | 959 |
| Substitution, äldre generationer | 218 | 218 | 218 |
| Substitution, ny generation (två svep) | – | 1 059 | 2 932 |
| Förfining (tak 90, två svep) | 601 | 454 | 242 |
| Parvis och gemensam förfining | 132 | 142 | 117 |

Rådata per körning: [measurements.json](recipe-scaling-20261019/measurements.json).

## 4. Substitutionstak (ägarbeslut 2026-10-20)

`LIBRARY_SUBSTITUTION_POOL_LIMIT` (standard 160, 0 = hela svepet som förut,
`f88dfd6`, `99e2d62`, `1d2e620`). Varje nyare generations recept rangordnas med
samma regel som seed-taket (billigaste kvalificerade enreceptsköp, delade
förpackningar, två billigaste per kök) och högst 160 per måltidstyp prövas i
varje plats. En generation inom taket prövas helt, som förut. Hela den
aktuella poolen går fortfarande in i förfiningen (tak 90), parvisa och
gemensamma byten. Detta är en heuristik precis som övriga tak.

**Val av tak, 1 000 recept, alla sju matrisprofiler, pris jämfört med hela
svepet** ([substitution-limit-sweep.json](recipe-scaling-20261019/substitution-limit-sweep.json)):

| Tak | Utfall |
| ---: | --- |
| 40 | Lund standard 5,08 kr dyrare (502,27 mot 497,19) |
| 80 | Lund standard 11,32 kr *billigare* (485,87): sökningen är inte monoton |
| 120 | Fördelningsprofilen dyrare: Lund +10,94 kr, Malmö +24,15 kr |
| 160 | Samma pris i alla 14 körningar. Samma hash i 13; Lund fördelning valde en annan meny med samma pris (703,56 kr) |

Vid 2 000 recept gav 160 samma pris och hash som hela svepet i Lund och Malmö
standard och samma pris (annan likvärdig meny) i Lund fördelning. En första
körning med taket gav `IndexError` för frukost/mellanmål när en generation inte
tillförde någon rätt av måltidstypen; rättat i `1d2e620` och omkört (samma pris).

**Tid, varm standard (median av två, sekunder):**

| Stad | Recept | Hela svepet | Tak 160 | Korgar | Pris | Peak RSS |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lund | 222 | 35,9 | 36,1 | 2 043 / 2 043 | 548,76 | 1,56 GB |
| Lund | 1 000 | 85,1 | 44,4 | 5 419 / 2 944 | 497,19 | 1,76 GB |
| Lund | 2 000 | 136,1 (n=1) | 61,0 | 10 035 / 4 045 | 518,55 | 2,06 GB |
| Malmö | 222 | 40,5 | 33,1 | 1 472 / 1 472 | 534,92 | 2,47 GB |
| Malmö | 1 000 | 126,0 | 51,9 | 5 720 / 2 917 | 495,85 | 2,66 GB |
| Malmö | 2 000 | 201,7 (n=1) | 76,4 | 9 713 / 3 867 | 487,75 | 2,96 GB |

Vid 222 recept binder taket inte (samma korgar och hash); skillnaden i Malmö
där är mätvariation mellan körtillfällen, inte taket. Kall tid med tak 160:
Lund 67/105 s, Malmö 75/122 s vid 1 000/2 000 recept, varav 31–61 s kvalificering.

Observationer att granska:

- Lund 2 000 recept ger 518,55 kr, dyrare än 1 000 recept (497,19), även med
  hela svepet. 2 000-biblioteket importerades som två generationer (778 + 1 000)
  och sökvägen blir en annan. Uppgiftens krav att behålla en tidigare giltig
  kandidat vid bibliotekstillväxt är alltså inte uppfyllt av dagens sökning.
  Det är inte orsakat av taket.
- Malmö 2 000 recept når 2,96 GB peak RSS, nära serverns 3 GiB-gräns.
- Vid 2 000 recept är kandidatkvalificeringen nu den största enskilda kostnaden
  vid kall start (cirka 60 s), och växer linjärt.
- Fullbiblioteksreferensen (`--uncapped`, nu även med substitution 0) är inte
  körd vid 1 000/2 000; jämförelsen ovan är mot hela substitutionssvepet med
  övriga tak oförändrade.

## 5. Inte gjort än

- 5 000 recept, övriga profiler vid 2 000, negativa fall,
  fullbiblioteksreferens (`seed=0`, `refinement=0`, ingen variantlista,
  substitution 0) vid 1 000/2 000, omvänd körordning, samtidighet, HTTP-kö och
  förberedelsetid efter pris-, fakta- eller receptändring.
- GitHub-CI kräver push. Lokal full offline-svit på `f88dfd6`: 2 760 PASS,
  10 XFAIL (kända), 53 SKIP (saknad lokal evidens); 41 webbläsartester kunde
  inte starta en webbläsare i denna miljö och ska verifieras i CI.

## 6. Rekommenderat nästa steg

1. **Fullbiblioteksreferens vid 1 000 och 2 000** för att pröva taken mot hela
   biblioteket, och åtgärd för att större bibliotek inte ska ge dyrare meny.
2. **`BasketOptimizer.optimize`** är nu största delen av varje korg. Exakt
   återanvändning mellan veckor som delar fyra av fem recept kräver ändringar i
   den gemensamma optimeraren och en egen granskning.
3. Mät övriga profiler, 2 000 recept (minne i Malmö) och omvänd körordning.

## Reproduktion

```bash
export PYTHONPATH=backend:. PYTHON_DOTENV_DISABLED=1
# Testbibliotek i en isolerad worktree (aldrig i main-checkouten)
git worktree add --detach ../lib-1000 HEAD && cd ../lib-1000
python reports/recipe-scaling-20261019/generate_library.py --recipes 778 --output drafts-1000.json
python -m app.services.meal_library_cli author drafts-1000.json --output pack-1000.json \
  --report author-1000.json --import --prepare 4
python -X utf8 backend/scripts/combined_performance_probe.py --matrix \
  --inputs <server-data>/data/lund --output out --label lib1000 --matrix-case standard --repeat 3
python reports/recipe-scaling-20261019/search_phases.py --inputs <server-data>/data/lund \
  --case standard --output phases.json
python reports/recipe-scaling-20261019/summarize.py out/lund/*.json
```

`generate_library.py` är deterministisk och nästlad: de första N recepten i ett
större bibliotek är exakt det mindre biblioteket. Indataarkivet checkas inte in;
det finns i Codex leveranspaket `smako-allt-till-claude-20261018.zip`.
