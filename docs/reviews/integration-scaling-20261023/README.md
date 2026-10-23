# Reproducerbar granskning 2026-10-23

Status och bedömningar finns i [rapporten](../integration-scaling-20261023.md).
`results.json` innehåller endast avslutade jämförelser; saknade celler är
uttryckligen okända. `memory-and-cache.json` är en separat kontroll med
det tidigare 5 000-biblioteket, inte en cell i slutmatrisen.

## Pinnar och bevarade underlag

| Underlag | Pinne/SHA-256 |
| --- | --- |
| Hämtad main och serverns ursprungliga screeningjämförelse | `2efb62f219b31fa6a81c16ba71363b4207cb2dfe` |
| Lunds lyckade slutmätningar efter K32:s minnesfel | `c9390ddb9fbc362548a4b93261168b4764e44c16` |
| Kanoniskt Git-arkiv, `candidate-memory-v6.zip` (`backend`, `grocery_data`) | `4049f3cf56002e3b49041afd01d0846b5561d03a3659fb05b33ea4041e1f4053` |
| Lunds metodsignatur, kanoniska Git-byte | `f211cf4a197f0a7cf78b05a1026ea9309e2395e7a71dd14c7894f10044183b37` |
| Malmö och uppföljningar, med nödvändig kapacitetskontroll | `b139cd4630c03bc4e01f4c5c0ba0e7ead7e50314` |
| Kanoniskt Git-arkiv, `candidate-capacity-v7.zip` | `e10ad2621aae70d74ab0e26067ccfa70234a6ad811ac1186ed537d6c02430abc` |
| Malmös metodsignatur | `b84ccfab6c612e42a91ab5a79e2ccde4bebcfe310f9834c42fbf2d244a340bf9` |
| Verkliga frysta serverexporter, `public-data.zip` | `a30a3e082ab90db43eef998dfd5b3f7c8a458262142478b73f6c6200a246c136` |
| Nästlade testbibliotek, `nested-libraries.zip` | `e099132fca1c72a3b99d754d55723310ffdea0da68e0885a4bab108fda0764ac` |
| Befintlig image, använd endast som isolerad beroendebas | `sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072` |

Arkiv, fullständiga mätningar och körkvittenser ligger utanför Git i
`D:\Projects\Smako\.local\integration-scaling-20261023` samt serverns
`/opt/smako/evidence/integration-scaling-20261023`. Råpriser, faktabevis och
lokala miljöer ska inte läggas i indexet. Arkivhashar och varje stads
`matrix-inputs.json` måste verifieras före återspelning. Frysta klockor får
inte ersättas med dagens tid. Inga privata produktionsprofiler används.

## Bibliotek

Syntetiska förslag kommer från
`reports/recipe-scaling-20261019/generate_library.py --recipes 4738`.
Varje paket gick genom ordinarie `meal_library_cli author --import` i
isolerade worktrees. Main-checkoutens bibliotek ändrades inte.

Den första byggaren i `../recipe-scaling-20261023/build_libraries.sh`
bevarar receptmängderna men ger olika proveniens för det sista delpaketet
vid varje storlek. För slutmatrisen bevarades hela det importerade
1 000-biblioteket, därefter importerades intervallen 738–1 738 i två
500-paket till 2 000. Detta bibliotek bevarades och intervallen
1 738–4 738 importerades i sex 500-paket till 5 000. Alla intervall är
nollbaserade förslagspositioner med exkluderande slutposition.

`libraries/nested-proof.json`, kodverifieringen `nested-proof-v6.json`
och `nested-*-recipe-hashes.json` i det
lokala underlaget verifierar antalet, metodsignaturen och SHA-256 för
varje fullständigt receptvärde. Varje tidigare identitet måste finnas med
exakt samma värde. `nested-archive.json` binder detta till det bevarade
arkivet. Ny standardisering en annan dag ändrar granskningsdatum;
använd det hashverifierade arkivet för exakt återspelning.

`capacity-code-proof.json` binder de två kodversionerna: all befintlig kod i
de två ändrade modulerna är AST-identisk efter att den nya kapacitetsmetoden
och dess anrop tagits bort. Variabeln skuggar ingen tidigare lokal bindning.
En redan accepterad komplett meny visar att det nödvändiga avvisningsvillkoret
är falskt. Lyckade Lund-mätningar återanvänds därför med sin ursprungliga
kod-/tidsversion. Blockerade fall mäts med den nya kontrollen. Sammanställaren
jämför samma metodsignatur inom varje stad; den blandar inte plattformarnas
tider. Detta är ingen allmän garanti för alla privata indata.

## Slutmatris

`run_matrix.py` startas i en ny process per stad och bibliotek. Den laddar
priser/fakta en gång och skapar ny tom syntetisk privat status för varje
plan. Offentlig förberedelse återanvänds som i en varm appprocess. Skilj
detta från en ny process med varm diskcache. Färdig plan/planner släpps och
`gc.collect()` körs mellan anropen; detta är inte ett fleranvändarlastprov.

Exempel på Windows, i rätt worktree med valt receptbibliotek och
kanoniska källbyte:

```powershell
$env:PYTHONPATH='<worktree>\backend;<worktree>'
$env:PYTHON_DOTENV_DISABLED='1'
D:\Projects\Smako\.venv\Scripts\python.exe -X utf8 -u `
  D:\Projects\Smako\docs\reviews\integration-scaling-20261023\run_matrix.py `
  --inputs D:\Projects\Smako\.local\integration-scaling-20261023\current\data\lund `
  --output D:\Projects\Smako\.local\integration-scaling-20261023\final-grid\lund `
  --size 1000 --preparation-cache-root <separat-cache> `
  --execution-environment 'Windows local, one planner process'
```

Malmö körs seriellt i en isolerad Docker-container per bibliotek med
`--network none --read-only --cpus 2 --memory 3g --memory-swap 3g`, UID/GID
10001, skrivbar temporärkatalog och endast särskilda resultat-/cachemappar.
Kod och frysta indata monteras skrivskyddat; det valda biblioteket monteras
vid `/srv/app/backend/app/data/recipes`. `PYTHONPATH` är
`/srv/app/backend:/srv/app`. Kommandot är samma hjälpare med Linux-sökvägar.
Kompletta Docker-kommandon bevaras i `final-grid-v7-runner.log` och
`final-grid-v7-progress.json`, serverresultaten i `final-grid-v7/malmo`.
Lunds kvittenser heter `final-local-runner.log` och `final-local-progress.json`.
Ingen kod monteras in i driftens containrar.

Standardarmarna är main/K16/K32/K48 för alla sju profiler. Vid 262 körs
också den obegränsade v5-referensen, med alla sju sökinställningar angivna.
`--arms` och `--cases` kan avgränsa felsökning. Återanvändning kräver samma
indata, metodsignatur, bibliotek och sökinställningar. Inkompatibla filer
skrivs inte över. En ofullständig körning är inte ett godkänt prisvillkor.

## Ny process med varm diskcache

Använd det ordinarie acceptansverktyget i en ny process och en uttrycklig,
redan fylld cache från samma metodkod och bibliotek:

```text
python -m backend.scripts.planner_acceptance_matrix
  --inputs <frysta-indata> --output <ny-resultatmapp>
  --matrix-case standard --label warm-disk --repeat 1
  --preparation-cache-root <samma-cache>
  --merge-generations --substitution-pool 0 --slot-limit 48
```

Kontrollera metodsignatur, bibliotek, alla indatahashar, sökinställningar,
resultathash och cacheträffar/missar mellan processerna. Mät hela processen
med en yttre monoton klocka; verktygets planeringstid räknar inte import,
filinläsning eller containerstart. Äldre lokala tider med överlappande
minneskrävande jobb får inte användas för en isolerad cacheeffekt.

## Sammanställning

Hämta avslutade serverrapporter till `final-grid/malmo` bredvid de lokala
Lund-rapporterna och kör:

```text
python docs/reviews/integration-scaling-20261023/summarize.py
  --evidence .local/integration-scaling-20261023
  --output docs/reviews/integration-scaling-20261023/results.json
```

Sammanställaren jämför större bibliotek med både main vid 262 och föregående
storlek, med identiska indata och metodsignaturer. Förlust av giltig meny,
dyrare meny och ändrad blockeringsorsak kräver bedömning. Blockerat till
giltigt räknas som förbättring. Saknade resultat blir aldrig godkända genom
frånvaro. Ett godkänt prisvillkor är inte bevis för globalt optimum eller
serverns kö-/lastkapacitet.

`default-regression.json` jämför dessutom slutmatrisens main/262 med alla tre
ursprungliga main-iterationer per stad/profil. Indata och samtliga sju
sökinställningar måste matcha innan utfall, pris och semantisk hash jämförs.
Ofullständiga jämförelser markeras uttryckligen och räknas inte som godkända.

Valideringsunderlagen kan återskapas separat:

```text
python docs/reviews/integration-scaling-20261023/compare_default_results.py
  --evidence .local/integration-scaling-20261023
  --output docs/reviews/integration-scaling-20261023/default-regression.json
python docs/reviews/integration-scaling-20261023/summarize_followups.py
  --evidence .local/integration-scaling-20261023
  --output docs/reviews/integration-scaling-20261023/followups.json
```

`complete` avser avslutade mätningar. Prisspärrar redovisas separat och kan
vara underkända även när alla efterfrågade prov har slutförts.

## Proxy och sökspår

`proxy_review.py` är ett separat offlineexperiment ovanpå det ordinarie
acceptansverktyget, inte en produktionsinställning. Hela den kvalificerbara
basen till och med generation 13 behålls; hjälparen kräver att den basen har
262 recept. Tillägg rangordnas med summan av radernas billigaste offert,
åtta per generation/måltidstyp/proteinkategori. De behållna recepten genomgår
sedan ordinarie full kvalificering, veckosökning och oberoende kassakontroll.

Kör först full pool med samma kod, bibliotek, indata och cachekatalog, sedan
proxy utan memo, memo med `--verify-rows` och memo utan orakel. Exempel:

```text
python docs/reviews/integration-scaling-20261023/proxy_review.py
  --inputs <frysta-Lund-indata> --output <separat-resultatmapp>
  --matrix-case standard --label proxy-memo --repeat 2
  --preparation-cache-root <gemensam-samma-kod-cache>
  --merge-generations --substitution-pool 0 --slot-limit 48
  --proxy-limit 8 --proxy-memo
```

Fullpoolskontrollen använder `python -m backend.scripts.planner_acceptance_matrix`
med samma argument, utan `--proxy-limit`/`--proxy-memo`. Radmemon gäller bara
samma faktiska frysta kandidatobjekt, namn, mängd och enhet. Orakelflaggan
räknar om varje memoträff med den ursprungliga offertfunktionen. Kontrollera
samma behållna identitetshash mellan proxyvarianterna, pris mot full pool,
kassakontroll och alla indata-/metod-/bibliotekspinnar. En enda godkänd profil
är inte en allmän garanti för urvalets kvalitet.

Wrappern bevarar ordinarie metodmetadata med `functools.wraps` och redovisar
att första platsens kvalificerade korgresultat faktiskt återlämnas till
sökcachen. Slutjämförelsen ligger i `proxy-v8`; det tidigare v7-proxyprovet
tappade denna metadata och används inte som matchad tidsjämförelse.

`trace_matrix.py` tar samma CLI-argument och lägger till förbättrande/behållna
menyer och det ordinarie sökspåret. Det används för orsaksgranskning, inte
för prestandatider i slutmatrisen. Exakta mätfilers SHA-256, Docker-kommandon
och rapporter bevaras med körkvittenserna i `followups-v7` för sökspår och
`proxy-v8` för den matchade proxyjämförelsen; proxyrapporten
binder även sin egen scriptfil. Den spårhjälpare som levereras här har endast
fått oanvända importer borttagna jämfört med den bevarade mätfilen.

`verify_capacity_change.py` återskapar AST-beviset från Git-objekten för
`c9390dd` och `b139cd4`. Kör från projektroten med båda commits tillgängliga;
inga verkliga pris-/faktaunderlag behövs för denna kodkontroll.
