# Reproducerbar granskning 2026-10-23

Status och bedömningar finns i [rapporten](../integration-scaling-20261023.md).
`results.json` innehåller endast avslutade jämförelser; saknade celler är
uttryckligen okända. `memory-and-cache.json` är en separat kontroll med
det tidigare 5 000-biblioteket, inte en cell i slutmatrisen.

## Pinnar och bevarade underlag

| Underlag | Pinne/SHA-256 |
| --- | --- |
| Hämtad main och serverns ursprungliga screeningjämförelse | `2efb62f219b31fa6a81c16ba71363b4207cb2dfe` |
| Slutmatrisens applikationskod | `652e7ace1359374ec8368e9373f2471c0b44cea6` |
| Kanoniskt Git-arkiv, `candidate-memory-v5.zip` (`backend`, `grocery_data`) | `30808025a469cd5bcf783db9b3b5a0a7d062700376b7bb24fab612d459cfc74d` |
| Metodsignatur, samma byte i Windows och Linux | `2b996b1133054cbebe202258c864b4776b61e2923a672cc4ee61447a51951f9b` |
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

`libraries/nested-proof.json` och `nested-*-recipe-hashes.json` i det
lokala underlaget verifierar antalet, metodsignaturen och SHA-256 för
varje fullständigt receptvärde. Varje tidigare identitet måste finnas med
exakt samma värde. `nested-archive.json` binder detta till det bevarade
arkivet. Ny standardisering en annan dag ändrar granskningsdatum;
använd det hashverifierade arkivet för exakt återspelning.

## Slutmatris

`run_matrix.py` startas i en ny process per stad och bibliotek. Den laddar
priser/fakta en gång och skapar ny tom syntetisk privat status för varje
plan. Offentlig förberedelse återanvänds som i en varm appprocess. Skilj
detta från en ny process med varm diskcache.

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
Kompletta Docker-kommandon bevaras i `final-grid-runner.log` och
`final-grid-progress.json`. Ingen kod monteras in i driftens containrar.

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
