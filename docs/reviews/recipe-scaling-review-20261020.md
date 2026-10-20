# Granskning av receptskalningen, 2026-10-20

**Beslut:** den fristående referensrättningen `9e6b7a9` är godkänd och
integrerad/pushad på `main`. Skalningspaketet är ännu inte godkänt som färdig
skalningsmilstolpe. Det ligger med granskningsrättelser i
[utkast-PR #4](https://github.com/ossebosse/smako/pull/4), gren
`review/recipe-scaling-20261020`. Ingen produktionsaktivering, insamling eller
import i ordinarie receptbibliotek har gjorts.

Granskade inkommande grenar: `origin/perf/recipe-scaling-20261019` vid
`d4672aa` och `origin/fix/full-library-reference-contract` vid `9e6b7a9`,
båda från `00123b7`. Instruktion:
[review-instructions-20261020.md](review-instructions-20261020.md).
Granskningskod: merge `7ada8a4`, tester/CLI `ef676a6`, analysrättning och
reproduktion `a898412`.

## Fynd och åtgärder

### P1 rättat i kod: tidigare generationers färdiga vinnare bevaras inte

`MenuOptimizer.optimize_library_slots` kör substitution för generationerna,
men förfining, parvisa byten och gemensamma byten först efter sista
generationen. `PersonalPlanner.create` hoppar samtidigt över
`retain_library_comparison` när `_library_search_handled` är satt. Därmed
jämförs inte den större sökningen med den tidigare generationens **färdiga**
resultat. Att varje substitution förbättrar sin egen startpunkt räcker inte.

En liten reproduktion med den verkliga optimeraren bekräftar luckan:

```powershell
$env:PYTHONPATH='backend;.'
.venv/Scripts/python.exe reports/recipe-scaling-20261019/reproduce_generation_retention.py
```

| Bibliotek | Vald meny | Pris i syntetiskt prov |
| --- | --- | ---: |
| Generation 1–2 | B, B | 2 |
| Generation 1–3 före rättning | C, C | 6 |
| Generation 1–3 efter rättning | B, B | 2 |
| B, B omprissatt i det utökade scenariot | B, B | 2 |

Provet använder ett avsiktligt ändrat förfiningsurval när poolen växer och
ingen substitutionsbegränsning. Det isolerar mekanismen; det är inte en ny
Lundmätning. Den inkommande rapportens Lundobservation 497,19 → 518,55 kr
har **inte** återkörts färdigt här.

`e6f7d32` slutför varje kumulativ publiceringsgeneration och behåller dess
vinnare under samma aktuella priser och krav. `ea847bb` håller dessa
prefixförfiningar åtskilda från den större sökningens ursprungliga
sekundära startpunkter. Ett särskilt prov bevarar därför även en billigare
slutvinnare som bara den större sökningen hittar. Korgcachen är fortsatt
begränsad till 256 poster; äldre fulla planner-anrop återkörs inte rekursivt.
Ett ändrat prisprov visar att tidigare vinnare omprissätts och kan förlora.
Rättningen gäller kumulativa publiceringsprefix med oförändrade kandidater,
inte godtyckligt utbyte/återkallande av recept eller ett globalt optimalitetsbevis.
Extra förfiningsarbete per generation måste fortfarande mätas vid 1 000/2 000.

### P2 rättat i kod: cache behöll pensionerade prisuniversum i RAM

`cd9f148` ersätter cachens starka ägarreferens med en svag referens och tar
bort tillhörande scope när universumets sista verkliga ägare släpper det.
Objektidentitet kontrolleras vid återanvändning. GC-provet verifierar att
universumet och dess cacheposter frigörs. Det är en verifierad livscykelfix;
det är ännu ingen ny mätning av maximal RSS vid 2 000 recept.

### P2 rättat: pytest-referensen behöll substitutionstaket

`test_search_caps_vs_uncapped.py` stängde av seed, förfining och varianturval
men lämnade det nya substitutionstaket på 160. Testets referens var därmed
inte sökning över hela det kvalificerade biblioteket.

Det använder nu `full_library_search_limits`, samma funktion som CLI:n.
Det sammanslagna kontraktet är `smako-full-library-reference-v2` och kräver
uttryckliga heltalsnollor för seed, förfining och substitution samt booleskt
`False` för varianturvalet. Saknad substitution, gammalt v1-kontrakt och
`False` som heltalsnolla avvisas. Verkliga CLI-prov täcker avvisningen.
Felaktig kombination `--uncapped --substitution-limit` avvisas före stora
indata läses eller utdatakatalog skapas.

På `main`, som fortfarande saknar substitutionsbegränsningen, gäller den
fristående rättningens v1-kontrakt. v2 följer med skalningsgrenen.

### P2 rättat: kostnadsgolvet använde dagens kampanjdatum

Analysverktyget `bound_tightness.py` använde `offer.is_active()` utan datum
trots fryst historisk planeringsklocka. En historiskt giltig rabatt kunde
därmed få ett för högt golv när samma analys kördes senare. Ett syntetiskt
historiskt två-för-tio-erbjudande med ordinarie paketpris 20 reproducerar detta.

Golvet är nu konservativt noll för kandidater med något erbjudande, oavsett
datum. Testerna täcker detta och att ett delat produktpaket bara räknas en
gång. Verktyget kan importeras utan att starta planering, och dess tillfälliga
instrumentering återställs efter körning. Den gamla 51-procentsmätningen är
historisk evidens; den har inte ersatts med en påhittad ny siffra. Verktyget
styr ingen runtimebeskärning.

### CI-rättelser

Två fel i inkommande tester hade stoppat PR:s Ruff-steg: importordning i
`test_lazy_pairwise_similarity.py` och oanvänd `valid` i
`test_variant_evidence_retention.py`. Importen är rättad och det senare
testet kontrollerar nu även antal godkända kandidater.

## Övrig kodgranskning

- Lat parlikhet: runtimeanroparen gör uppslag med `get`, inte heliteration.
  Intervallkontrollen sker vid beräkning; även NaN avvisas. Nyckelordning och
  jämförelseordning bevaras. Ingen ny avvikelse funnen.
- Behovsrader: mängder och övriga toppnivåfält kopieras per korg; muterbara
  listor för egenskaper och produktkrav kopieras särskilt. Den sammanfogade
  profilen läses under anropet. Framtidsförslaget ändrar en djupkopierad
  måltid och bygger en separat planner.
- Delad upplösning: scope binder prisobjektets identitet, faktaversion,
  butiksvy, tillåtna butiker, medlemskap, Stockholmsdatum, inköpsläge,
  fullreceptläge och settings. Ingrediensnyckeln binder profil, enhet,
  egenskaper och receptets formkrav. Produktionsvägen bygger faktaversionen
  genom innehållshash i `FactsCollection`; den bevaras vid oförändrade fakta.
  Injekterad data som själv skriver över `.version` måste fortfarande hålla
  det kontraktet. Cachebeskrivningens felaktiga uppgift om starka referenser
  till faktaobjekt har korrigerats.
- Cacheproven verifierar faktisk omberäkning vid ändrade allergifakta,
  medlemskap och kampanjdag, separata felobjekt utan föregående anrops
  annoteringar samt samtidig upplösning med olika profiler. Ingen ny
  pris-/allergiavvikelse hittades. Minneskapaciteten för fyra scope är
  däremot inte slutverifierad under last.
- Tomma substitutionsgrupper är tillåtna; seed-vägen anropas fortfarande
  först när samtliga slotgrupper har alternativ. Tak 160 är en heuristik,
  inte ett optimalitetsbevis.
- Importgränsen kontrolleras före publiceringsskrivning. Största befintliga
  JSON-paketet, inklusive bevarade versioner, är 1 287 825 byte, långt under
  16 MiB. Importens feltext anger byteantal och att utkastet måste delas;
  CLI:n visar fortfarande felet som `ValueError`, inte en strukturerad
  standardiseringsrapport.
- Samma pris men annan meny är inte automatiskt ett fel i en ändrad
  sökheuristik; full hash måste däremot bevaras för rent beräkningsmässiga
  optimeringar. Sekundära mål/tie-break måste ingå när retentionen rättas.

## Verifiering och dess gränser

Uppföljningen `35afef0` har
[grön full CI](https://github.com/ossebosse/smako/actions/runs/39410311242):
**2 862 PASS, 10 kända XFAIL, 53 SKIP**, inklusive webbläsare och Ruff.
Kostnads- och cachelivscykelrättningarna ingår. Den efterföljande
paketerarrättningen `8f9221e` klarar 21 riktade tester och ett verkligt
schedulerkandidatbygge. Självstädningen och den genomförda avgränsade
serverrensningen redovisas i [lagringsrapporten](storage-lifecycle-20261020.md).
Ingen app- eller scheduleraktivering har gjorts av uppföljningen.

Granskningskod före uppföljningsrättningarna, `a898412`, har
[grön full CI](https://github.com/ossebosse/smako/actions/runs/39394944178):
**2 834 PASS, 10 kända XFAIL, 53 SKIP**, inklusive webbläsartester och Ruff
på alla ändrade Pythonfiler. Efter denna kodcommit ändras endast rapport och
handoff. Detta bevis avser den äldre koden; uppföljningens verifiering
redovisas separat och ersätter inte de saknade stora acceptansmätningarna.

Den separat integrerade main-rättningen `9e6b7a9` har
[grön full CI](https://github.com/ossebosse/smako/actions/runs/39395018419):
**2 807 PASS, 10 kända XFAIL, 53 SKIP**, inklusive webbläsartester.

Den första granskade kodversionen `ef676a6` har
[grön Linux-CI](https://github.com/ossebosse/smako/actions/runs/39393340700):
**2 831 PASS, 10 kända XFAIL, 53 SKIP**, inklusive webbläsartester. CI-antalen
räknas från pytest-progressen eftersom dubbla `-q` utelämnar totalsammanfattningen.
De 53 överhoppade fallen är 51 tester med saknad lokal historisk evidens och
två separat aktiverade taktester.

Slutversionens fokuserade offlinekörning passerar **91 tester, 0 fel,
0 överhoppade** (JUnit, 157,725 s). Den täcker kontrakt, delad cache,
samtidighet, parlikhet, inkrementell sökning, variantbevis, import och
kostnadsgolv. Den fristående main-rättningen har dessutom 30 godkända
kontraktstester. Ruff på alla ändrade Pythonfiler, compileall och
`git diff --check` passerar.

Den lokala fullsviten avbröts efter 798 testmarkörer när Windows nådde minnes-
och växlingsfilgränsen. Ett fel hade markerats i
`test_diversity_mode_api_contract.py`; hela den filen kördes därefter om
isolerat med **5 PASS**. Det finns ingen avslutad lokal fullsvit och ingen
bevarad traceback som fastställer orsaken till den avbrutna körningens fel.
Grocery-koden är oförändrad och dess fullsvit har inte körts om.

## Skalningsunderlag och avbrutna mätningar

1 000-receptbiblioteket återskapades genom ordinarie author/import i
`D:\Projects\Smako-worktrees\review-scaling-20261020`, en isolerad worktree.
Ordinarie checkout har kvar 222 recept. Datum för standardisering frystes
till 2026-10-19; utan det blir paketet inte samma innehåll.

- Utkastets generator/seed: `generate_library.py`, 778 recept, 20261019.
- Standardiserat pakets SHA-256:
  `4d2fcf61550a9c4426a0be824d69f830bd68aa7dafb330f70b73517b826f7089`.
- Biblioteksmanifestets SHA-256:
  `10b7bdae8148e44eb0b99601aca2931b4b41af79849cb4a86f6d8e12aaae598e`.
- Båda matchar inkommande manifest exakt. Noll author-varningar/avvisningar;
  största publicerade paket 9 451 804 byte.

Försök med två CPU och 3 GiB lokalt i Docker slutfördes inte. Första
försöken avbröts vid långsam Windows-bindmonterad filåtkomst. Nästa försök
använde exakt samma källor på containerns lokala disk, men värddatorn nådde
sin minnes-/växlingsfilgräns och Dockertransporten bröts (`unexpected EOF`).
Dockerstatus visade exit 255 och `OOMKilled=false` för det sista försöket.
Detta bevisar **inte** container-OOM vid 3 GiB. Ingen lyckad
planeringsrad, pris/hash eller jämförbar tid producerades.

Alltså saknas här nya servermätningar, fullbiblioteksreferenser vid
1 000/2 000, omvänd körordning, 2 000-receptsminne, tracemalloc-jämförelse
och full sjuprofilsserie. Inkommande råmätningar är fortfarande författarens
evidens, inte oberoende upprepningar. Inga tak har höjts eller kvalitetskrav
sänkts för att få ett godkännande.

Lokalt granskningsunderlag ligger i `.local/review-scaling-20261020/`:
CI-loggar, testloggar, syntetisk reproduktion, authorpaket, exakt
runtimearkiv och avbrutna containerloggar. Frysta pris-/faktaindata hämtades
från den redan återställda
`.local/followup-review-20261018/server-data/data/`.
De fyra egna testcontainrarna är borttagna efter kontroll att de var stoppade
och efter arkivering/hashkontroll av de partiella cachefilerna. Inga andra
Dockerresurser eller historiska arbetskopior rensades.

## Separata driftobservationer

Den läsande statuskontrollen 08:14 UTC gav HTTP 200/ready och samma
publicerade/laddade manifest. Coop Online Syd var STALE men dess kvalificerade
baspriser var användbara enligt policyn. Servern hade cirka 11,45 GB ledigt
mot statusverktygets uppskattade behov 15,42 GB. Windowsreläets senaste jobb
hade `OSError` och resultat 1; uppgiften pekade nu på `2464596b6f07`.

Det är aktuella observationer, inte en driftreparation. Ingen scheduler,
Windowsuppgift, profil, servermiljö eller produktionsdatabas ändrades.
