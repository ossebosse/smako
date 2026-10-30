# Samlad CI-överblick: varor, recept, täckning och prestanda

Öppna jobbet **coverage-overview** i senaste `tests`-körningen på
[GitHub Actions](https://github.com/ossebosse/smako/actions/workflows/tests.yml).
Jobbets Summary innehåller huvudtalen och topplistorna. Artefakten
**coverage-overview** innehåller maskinläsbar `overview.json`, `comparison.json`,
sammanfattningen och en komprimerad CSV med varje produktposts status per läge.
Det gemensamma obligatoriska `backend`-jobbet kräver även detta jobb.

## Underlag och jämförbarhet

CI räknar om **hela det aktuella biblioteket** genom den ordinarie resolverns
produkt-/form-/prisregler och `PersonalPlanner.basket(final=True)`. Den frysta
referensen innehåller 89 458 produktposter i Malmö från 23 oktober 2026 och
granskade, källbundna produktfakta från 28 oktober. Den är en reproducerbar
referens, **inte dagens beta eller den nyare Stora Coop-kopplingen**.

`ci/coverage-reference.json` låser två offentliga datatillgångar med SHA-256 och
storlek före och efter komprimering. Filerna ligger som separata release assets;
databaser, råa nätverkssvar, autentisering och användardata ingår inte. Själva
mätningen spärrar nätverk och läser inga produktionsprofiler. Den aktiverar
inget i betan. Prisklockan för kampanjer är uttryckligen fryst; ingen
observationstid förnyas.

JSON anger kodrevision, analyskodens hash, PriceUniverse-ID, snapshots,
produkt-/faktahash, receptmanifest, beräkningsmetod, butiker, butikstak,
portioner, medlems-/prisval, skafferi och klocka. Referensen använder högst två
butiker, fyra middagsportioner och en frukost-/mellanmålsportion. Recept skalas
med ordinarie författade skalning. Exakt läge och uttryckligt uppskattningsläge
mäts var för sig. Inga allergier eller särskilda ekologiska krav är beställda;
rapporten lovar inte täckning för alla personliga val.

## 1. Hur mycket av varorna kan användas?

Produktpost betyder `(store_id, product_id)`: samma vara hos olika butiker
räknas separat. Detta behövs eftersom priser, faktaunderlag och köpbarhet kan
skilja sig. En låg andel innebär därför inte samma andel unika livsmedel.

Alla poster i PriceUniverse fördelas i tre grupper som summerar till nämnaren:

| Status | Betydelse |
| --- | --- |
| `recipe_candidate` | Ordinarie resolver har godkänt posten för minst en ingrediens i ett aktuellt, författat recept. |
| `rejected_in_tested_paths` | Minst ett faktiskt stopp har observerats och ingen receptväg har godkänt posten. |
| `not_demonstrated` | Ingen godkänd väg eller observerad avvisning. Kan vara saknat recept, otillräcklig sökklassning eller en vara som inte hör hemma i matlagning. |

Topplistan redovisar unika poster per observerad stoppfas och konkreta
orsaksexempel. Orsaksgrupper kan överlappa; ett stopp i ett recept gör inte
varan avvisad om ett annat recept kan använda den. Produktionsspårningens
urval på 256 kampanjposter används **inte** som nämnare här.

Kandidat i ett recept med verifierad hel korg och faktiskt köpt produkt
redovisas separat. Att inte vara billigast är ingen datakvalitetsavvisning.
Att hela korgen fungerar bevisar inte att varje alternativ produkt har provats
i en egen korg. Avvisningar **före** PriceUniverse ingår inte: importerade
råposter/insamlingens bortfall måste läsas i driftöverblicken och får inte
blandas in med en annan nämnare.

## 2. Hur många importerade recept kan användas?

Rapporten behåller alla **2 200 ursprungliga import-ID:n**, inklusive deras
uttryckligen granskade efterföljare. De äldre recepten räknas dessutom i en
separat totalsumma för hela det aktiva biblioteket; de får inte förändra
importnämnaren.

Per recept redovisas stöd för alla ingredienser och därefter ett eget resultat
från slutlig checkout: `verified`, `data_blocked`, `checkout_blocked`,
`search_incomplete` eller `not_checked`. Kontroll av en hel korg innefattar
ordinarie mängder, förpackningar, prisvillkor och slutlig audit. Det är inte ett
bevis på en hel veckomeny eller globalt lägsta pris.

Hindren grupperas som **råvara / tillagningsform / enhet**. Varje recept räknas
högst en gång per grupp även när råvaran används i flera komponenter. Kolumnen
”enda ingredienshindret” visar hur många recept som skulle få stöd för alla
ingredienser om just gruppen löstes. Det är ett övre tak, inte ett löfte om
giltig checkout. Gruppernas antal får inte summeras till unika recept.

CI jämför original-ID:n med `ci/coverage-baseline.json`: lika många lyckade
recept får inte dölja att andra recept slutat fungera. Förlorat ingrediensstöd
eller en konkret förlorad korg gör jobbet rött. Ett tidigare verifierat recept
som når tidsgränsen markeras **ofullständigt**, gör också jobbet rött och får
inte beskrivas som bevisat omöjligt. Sammanfattningen och detaljerna sparas även
vid en misslyckad jämförelse. Inga nätanrop eller omhämtningar används för att
göra ett prov grönt.

## 3. Vilka recept ska läggas till?

`ingredient_coverage` binder varje råvara/form/enhet till recept-ID:n,
grundrätter, antal produktkandidater samt hur många recept som klarar samtliga
ingredienser respektive hela korgen. Detta skiljer många varianter av samma
grundrätt från verklig receptbredd.

`recipe_opportunities` prövar kända författarnamn/alias genom befintlig generisk
produktresolver. Den listar kvarvarande produktposter som har sådant
kandidatstöd men som inget befintligt recept använder:

- **Lägg till och granska recept** när ingen författad ingrediens finns.
- **Granska form/varufakta** när råvaran redan förekommer men produkterna ändå
  inte passerar recepten. Fler recept löser inte automatiskt detta.

Listan prioriteras efter antal sådana produktposter. Den är en arbetslista för
receptförfattande, inte ett automatiskt godkännande av genererade recept.
Generiskt stöd saknar receptets form- och beredningskrav; föreslagna recept
måste få verkliga mängder, instruktioner och samma slutliga checkout.
Interna insamlings-ID:n som `milk`/`cheese` är inte nya råvaror vid sidan av
`mjölk`/`ost`. Oklassificerade varor fångas också i `uncovered_categories` och
produkt-CSV:n; de etiketteras för granskning, inte som bevisad receptbrist.

Målet är täckning av relevanta livsmedel och former. Det kräver inte ett eget
recept för varje förpackning, varumärke eller städprodukt. Börja med hindren i
de 2 200 importerade recepten enligt produktmålet och använd sedan listan för
recept som breddar användningen av verkligt tillgängliga råvaror.

## 4. Förslag: prestanda i två nivåer

Den nya överblicken redovisar tid för dataladdning, planerarkonstruktion,
ingrediensupplösning, enskilda checkouter och täckningssonder. Det är **kostnaden
för inventeringen**, inte latens för att generera en veckomeny.

För menyhastighet rekommenderas ett separat, opt-in benchmarkjobb på ett fast
referensunderlag med befintliga `quality_personal_probe.py`,
`http_acceptance.py`, `http_measurements.py` och `performance_trace.py`:

| Fall | Förberedelse | Vad klockan ska omfatta |
| --- | --- | --- |
| Första installation/kall data | Ny process, tom härledd cache | Uppstart + delad förberedelse till ready, och första fullständiga användarresultatet inklusive eventuell väntan. |
| Kall process, förberedd data | Ny process, bevarad giltig härledd cache | Inläsning/återställning separat och första begäran. |
| Varm server, **nya val** | Färdig server, ny syntetisk ägare och varierade begäranden | Kö, kvalificering, menysökning, gemensam checkout, audit, sparning och återläsning. Detta är huvudfallet. |
| Varm identisk upprepning | Samma exakta begäran | Cacheträff redovisas separat; den kvalificerar inte prestandamålet för nya val. |
| Efter pris-/receptbyte | Ny giltig dataversion | Tid tills förberedelsen är redo, invalidation och första nya begäran. |

Använd samma fullständiga A/B2-profiler som tidigare och komplettera med
gränsfall för kost/allergier, näring, ekologiskt, få/fler butiker, 1–12
portioner och nya kombinationer. Kör seriellt först; ett separat belastningsprov
behöver sedan mäta kö och samtidighet. Använd en tillfällig PlanStore med
syntetiska användare och granska att resultat faktiskt sparas och återläses.

I varje resultat ska följande finnas:

- Fullständig giltig meny eller tydlig felstatus, kontrollernas utfall,
  receptantal, totalpris och samma kostnadsreferens. Snabba avslag och timeout
  räknas inte som lyckad generering.
- End-to-end-väggtid, kö, uppstart/förberedelse, kandidatkontroll, menysökning,
  offert/checkout, nutrition/audit, sparning och HTTP-/UI-återläsning.
- CPU-tid, högsta minne, cacheträffar, antal prövade menyer/offerter,
  kod-/data-/receptversion, maskin och resursgränser.

Befintliga `performance_trace`-spann kan vara **nästlade**. De får inte adderas
som en tidsfördelning på 100 procent. Visa dem som anropsprofil med antal anrop
och max/total tid; mät separata yttre fasgränser för en additiv tidslinje.

På GitHub-hostade runners: några upprepningar per fall, redovisa median och
intervall samt operationstal. Gör inte små väggtidsskillnader till hårda grindar.
För en stabil 30–60-sekundersgrind: separat maskin/container med fast CPU/minne,
samma underlag och fler upprepningar. P95 kräver tillräckligt många prov och får
inte döljas bakom ett enda lyckat anrop. Inget nytt schemalagt jobb eller någon
betabelastning är aktiverat av denna ändring.

Historisk jämförelse, inte ny mätning: [28 oktobers A/B2-prov](reviews/top-five-ingredients-20261028.md)
gav A **53,72 s**, A-repeat med separat ny ägare **52,47 s**, B2 **32,63 s**
för API, sparning och återläsning. Separat förberedelse var **98,81/77,95/77,56 s**.
Detta bevisar alltså inte kall end-to-end inom 60 sekunder. Nytt benchmarkjobb
enligt matrisen ovan behövs för aktuella genereringstider.

## Köra och hämta rapporten

Från reporoten med Python 3.12 och projektets dependencies:

```powershell
.venv/Scripts/python.exe scripts/coverage_reference_asset.py fetch --output .local/coverage-inputs
.venv/Scripts/python.exe scripts/coverage_overview.py --reference ci/coverage-reference.json --input-root .local/coverage-inputs --baskets --variant-seconds 5 --output .local/coverage-overview
.venv/Scripts/python.exe scripts/check_coverage_overview.py --report .local/coverage-overview/overview.json --output .local/coverage-overview/comparison.json
```

För agenter som inte ska räkna om allt: hitta senaste **lyckade** main-körningen,
verifiera körningens head SHA och läs först sammanfattningen. Exempel:

```powershell
gh run list --workflow tests.yml --branch main --status success --limit 5
gh run download <run-id> --name coverage-overview --dir .local/coverage-ci/<run-id>
```

JSON-kontrakt: börja med `status`, `scope`, `code_revision`,
`modes.estimated.imported_recipes`, `modes.estimated.blockers` och
`modes.estimated.recipe_opportunities`. Läs exaktläget också när uppskattningar
inte är tillåtna. En rapport från en annan commit eller ett annat underlag är
referensmaterial, inte belägg för aktuell beta.

Ett nytt sammanhängande och behörigt underlag kan mätas med samma kommando:

```powershell
.venv/Scripts/python.exe scripts/coverage_overview.py --universe <universe.json> --facts <facts.json> --clock <tidszonssatt-ISO-tid> --name <referensnamn> --baskets --output .local/coverage-new
```

Nytt CI-underlag ska granskas för datainnehåll och publiceras som en **ny**
hashlåst referensversion. Ändra inte en befintlig release asset i efterhand.
Byt manifest och baseline i samma granskade ändring; jämför databyten separat
från kodregressioner. Att sätta `--write-baseline` är ett explicit byte av
jämförelsen, aldrig en automatisk reaktion på röd CI.
