# Receptskalning, första mätning och två exakta rättelser, 2026-10-19

Uppgift: [CLAUDE-RECIPE-SCALING.md](../CLAUDE-RECIPE-SCALING.md). Detta är steg 1
(reproducerbar referens och profilering) plus två ändringar som bevisat inte
ändrar resultatet. Ingen beskärning, inga tak och inga kvalitetskrav är ändrade.
Inga syntetiska recept ligger i produktionsbiblioteket.

## 1. Beslut

**1 000 recept klarar inte 30 sekunder idag.** Varm standardplanering tar
cirka 106 s i Lund och 151 s i Malmö efter rättelserna (125 s och 165 s före).
Med 222 recept är tiden 43–56 s i denna miljö. Kostnaden växer ungefär
linjärt med antal nya recept, plus en kvadratisk del som nu är borttagen.

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
3. **Kandidatkvalificering per anrop.** En enreceptskorg per kandidat och
   anrop: 12–20 s varmt vid 1 000 recept, 34–45 s kallt. Samma arbete görs om
   i nästa anrop med samma priser, scope och profil.
4. **Minne.** Malmö når 2,7 GB peak RSS vid 1 000 recept. Med serverns
   3 GiB-gräns är 2 000 recept i Malmö sannolikt inte möjligt utan
   minnesåtgärd. Inte uppmätt här.

## 2. Ändringar

| Commit | Ändring | Varför resultatet är oförändrat |
| --- | --- | --- |
| `e16ba57` | `LazyPairwiseSimilarities`: kulinarisk parlikhet räknas när sökningen frågar efter ett par, inte alla n·(n−1)/2 par före sökningen | Samma nycklar, värden, ordning och argumentordning som den tidigare dicten. Testat mot den tidigare loopen på 70 riktiga middagar (exakt flyttalslikhet) och med samma resultathash i båda städerna vid 222 och 1 000 recept |
| `00fe91f` | Variantbevis (`variant_search_evidence`) behålls för varje kvalificerat recept i anropet; tidigare fast LRU på 2 048 | Seed-tak, variantlista och gemensamma förslag behåller alla recept *utan* bevis. Över 2 048 varianter förstorades därför seedsökningen tyst. Ingen skillnad under 2 048 (alla mätningar här) |

Den kvadratiska delen var 404 550 jämförelser och cirka 28 s per anrop vid
1 000 recept (profil). Vid 5 000 recept hade den varit cirka 12,5 miljoner.

Kvarstående begränsningar: lås, prisursprung, produktidentitet, allergen-,
närings- och verifieringskrav samt slutlig checkout-audit är orörda. Ingen
cache delas mellan anrop.

## 3. Mätningar

Kod `00123b7` (före) och `e16ba57` (efter). Två CPU (Intel Xeon 2,8 GHz),
7 GiB minne, Python 3.12.3, nätverk blockerat av matrisen. Frysta indata från
`smako-followup-public-data-20261018.zip` (SHA-256 `d3a93b88…`), klocka
`2026-10-18T05:12:49.467392+00:00`, samma som granskningen 2026-10-18.
En process per rad: en kall och två varma planeringar. Ingen upprepning i
omvänd ordning ännu; spridningen mellan varma körningar är upp till 14 s vid
1 000 recept. Denna miljö är cirka 15–20 % långsammare än serverns referens
(Malmö 222 varm: 58,5 s här, 49,6 s där). `00fe91f` påverkar inte dessa
storlekar (under 2 048 varianter) och är inte separat tidsmätt.

Bibliotek: nuvarande 222 recept (189 middagar: 94 grundrätter, 95 variationer).
Testbiblioteken lägger till syntetiska middagar via ordinarie `author --import
--prepare 4` i isolerade worktrees: 500 recept (467 middagar: 224 grundrätter,
243 variationer) och 1 000 (967: 457 / 510). Noll author-varningar och
avvisningar. Detaljer och hashar: [library-manifest.json](../../reports/recipe-scaling-20261019/library-manifest.json).

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

Sökfaser i Lund (ett kallt anrop, [search-phases.json](../../reports/recipe-scaling-20261019/search-phases.json)):

| Fas | 222: korgar | 500: korgar | 1 000: korgar |
| --- | ---: | ---: | ---: |
| Seed (generation 2, tak 40) | 919 | 959 | 959 |
| Substitution, äldre generationer | 218 | 218 | 218 |
| Substitution, ny generation (två svep) | – | 1 059 | 2 932 |
| Förfining (tak 90, två svep) | 601 | 454 | 242 |
| Parvis och gemensam förfining | 132 | 142 | 117 |

Rådata per körning: [measurements.json](../../reports/recipe-scaling-20261019/measurements.json).

## 4. Inte gjort än

- 2 000 och 5 000 recept, övriga sex profiler och negativa fall,
  fullbiblioteksreferens (`seed=0`, `refinement=0`, ingen variantlista),
  omvänd körordning, samtidighet, HTTP-kö och förberedelsetid efter pris-,
  fakta- eller receptändring.
- Full regression körs på grenen; GitHub-CI kräver push.

## 5. Rekommenderat nästa steg

1. **Exakt återanvändning inom korgberäkningen** (punkt 2 ovan): behovsrader
   och upplösta val per (plats, receptidentitet, måltidskrav) i stället för
   per vecka. Kräver samma hash för alla profiler; ingen beskärning.
2. **Kvalificering mellan anrop** (punkt 3): enreceptsresultat nyckade på
   receptversion, mängder, prismanifest, faktaversion, butiksscope,
   inköpsläge, medlemskap, klocka/kampanjdatum och profilkrav. Endast för
   anrop utan skafferi och produktlås.
3. **Substitutionen** (punkt 1) är huvudfrågan för 2 000+. Den kräver antingen
   en bevisad undre kostnadsgräns som håller för kampanjgrupper och butikstak,
   eller ett produktbeslut om hur nya generationer ska sökas. Att bara sätta
   ett tak är inte tillåtet enligt uppgiften och görs inte utan beslut.

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
