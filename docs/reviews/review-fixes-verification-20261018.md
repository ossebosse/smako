# Smako: granskning av Claudes rättelsepaket, 2026-10-18

Slutrapport för Claude. Alla fem uppgifter i rättelsepaketets granskningsinstruktion är genomförda.

## Omfattning

Paketet `smako-till-codex-20261018.zip` innehåller sex commits och fem
granskningsuppgifter. Paketets sex manifestposter har verifierats mot storlek
och SHA-256. ZIP: `675d23f5a147f3b36d343d5bdf8605178b8a5f9c2117ac12edc48f7c3deec1f7`.
Patch: `73feb3eea49bedefa587d6bc21ce7d743e0b7acdd846e5670f7c6bfb08384bdd`.

Import på granskningsgrenen ovanpå aktuell main `412ebd8`, inte paketets äldre
bas `d41339d`: `9ec318c..ad0411f`. Endast HANDOFF behövde sammanfogas;
lagringsåtgärden bevarades och den inaktuella uppgiften om backupfelet
korrigerades. Kandidatens runtimekod är oförändrad under granskningen.
PR [#2](https://github.com/ossebosse/smako/pull/2).

## Bedömning

De tre reproducerade P2-felen från förra granskningen är rättade:
fullbiblioteksreferensen innehåller nu alla kvalificerade varianter,
misslyckade faktaprojektioner skrivs inte till disk och author skalar flera
vattenmängder samt decimaler rätt. Äggändringen ger avsedd, snäv förbättring.
Ändringarna passar Smakos befintliga pris-, fakta- och receptarkitektur.

Ett kvarvarande P2-fynd gäller valideringen av **inlästa äldre referensfiler**,
se nedan. Det påverkar inte denna granskning, där alla referenser skapas om
med den granskade koden och deras inställningar kontrolleras.
Prestandamålet inför bred lansering och reproducerbar releaseimage är
fortfarande öppna. Detta är ingen produktionsaktivering.

## 1. Regression och CI

Lokalt backend med återställt underlag, `SMAKO_REQUIRE_LOCAL_EVIDENCE=1`
och `--runxfail`: **2 834 PASS, exakt 10 kända FAIL, 2 SKIP, inga ERROR**.
Samtliga tio fel har samma testidentitet och felmeddelande som föregående
granskning. De två skippen är datakrävande taktester som körs separat.
Sju tillkomna regressionstestfall passerar. Offlinevakten registrerade
28 rapportläsningar och inga blockerade åtkomster.

Grocery komplett: **1 909 PASS, 5 kända FAIL, inga SKIP/ERROR**, 1 914 fall.
Alla fem fel matchar föregående körnings testidentiteter och felmeddelanden
(minnesadresser normaliserade). Dessa fel reproducerades då även i ren
worktree på `d09eaf4`. Källträdet `grocery_data` har exakt samma Git-trädhash
nu: `37ef1c86200aa553cc629916f44d6d7aafe023fc`. Offlinevakten registrerar inga
blockerade åtkomster. Båda fullsviterna tillsammans: **4 743 PASS,
15 verifierade basfel och två separat körda taktester SKIP**, totalt 4 760.
Detta är inga nya svitefel, men fullsviterna är inte felfria.

Första PR-CI [39120341250](https://github.com/ossebosse/smako/actions/runs/39120341250)
är **grön** på `ad0411f`: Chromium/WebKit, uppstartskontroll, Ruff och hela
offline-backendsteget passerar: **2 783 PASS, 10 XFAIL, 53 SKIP**.
CI saknar det lokala historiska underlaget;
dess evidensberoende skip ersätts därför av den lokala strikta körningen.
40 fokuserade testfall passerar. Ruff för alla 13 ändrade Python-filer och
compileall passerar. Inga testkrav eller kända felmarkeringar har tagits bort.

## 2. Sju takprofiler och acceptansmatris

Takpytest: **9/9 PASS i Lund och 9/9 PASS i Malmö**, utan skip eller fel.
Det omfattar alla sju beställda profiler samt två kontroller av själva
jämförelselogiken. De tre Pydantic-serialiseringsvarningarna per stad
fanns även i föregående körning och är bevarade i loggarna.

**20/20 matrispar godkända.** Alla 14 positiva par har identiskt pris och
semantisk hash, godkänd slutlig audit och noll okända mängder. De sex
negativa paren har samma felkod; stage är tomt i båda armarna. Samtliga
standardresultat matchar också föregående granskning i pris/hash eller
felutfall. Inga tak har höjts och inget test har tagits bort.

| Stad | Profil | Default, kr/utfall | Hela biblioteket, kr/utfall | Hash lika |
| --- | --- | ---: | ---: | --- |
| lund | standard | 548.76 | 548.76 | ja |
| lund | vegan | 455.28 | 455.28 | ja |
| lund | protein40 | 796.40 | 796.40 | ja |
| lund | all-macros | 813.14 | 813.14 | ja |
| lund | organic-share | 352.22 | 352.22 | ja |
| lund | distribution | 775.86 | 775.86 | ja |
| lund | breakfast-snack-weight | 64.06 | 64.06 | ja |
| lund | allergy-milk | DATA_BLOCKED | DATA_BLOCKED | samma blockering |
| lund | organic-animals | DATA_BLOCKED | DATA_BLOCKED | samma blockering |
| lund | impossible-protein | NUTRITION_TARGET_NOT_MET | NUTRITION_TARGET_NOT_MET | samma blockering |
| malmo | standard | 534.92 | 534.92 | ja |
| malmo | vegan | 473.17 | 473.17 | ja |
| malmo | protein40 | 1012.83 | 1012.83 | ja |
| malmo | all-macros | 1012.83 | 1012.83 | ja |
| malmo | organic-share | 352.12 | 352.12 | ja |
| malmo | distribution | 1089.72 | 1089.72 | ja |
| malmo | breakfast-snack-weight | 60.16 | 60.16 | ja |
| malmo | allergy-milk | DATA_BLOCKED | DATA_BLOCKED | samma blockering |
| malmo | organic-animals | DATA_BLOCKED | DATA_BLOCKED | samma blockering |
| malmo | impossible-protein | NUTRITION_TARGET_NOT_MET | NUTRITION_TARGET_NOT_MET | samma blockering |


Fullbiblioteksreferensen använder `seed=0`, `refinement=0` och
`seed_variant_shortlist=false`. Default är `40/90/true`. Det är hela det
kvalificerade biblioteket vid detta urvalssteg, inte ett matematiskt bevis
på globalt optimum: övriga sökheuristiker och kvalificeringsregler kvarstår.

Det separata selektionsreprot använder sex verkliga linschilivarianter:
tidigare kod behöll fyra trots tak 0/0; kandidaten behåller alla sex med
varianturval avstängt och fyra med default. Det bekräftar att rättelsen
träffar den tidigare förlorade delen av biblioteket.

### Kvarvarande P2: en gammal begränsad referens kan godkännas

`backend/scripts/planner_acceptance_matrix.py:223` kontrollerar endast
identiska indata och `uncapped=true` när `--uncapped-reference` läses.
En referens från föregående version hade just dessa egenskaper men behöll
fyra varianter per bas. Dess `search_limits` saknar
`seed_variant_shortlist`; den kan därför fortfarande accepteras och ge
ett missvisande godkänt takprov om operatören återanvänder samma frysta indata.

Reproduktion: `audit_results.py` kör exakt valideringsassertion från CLI:ns
AST mot den bevarade tidigare Lund-standardrapporten. Den accepteras.
`repro_legacy_reference_cli.py` bekräftar dessutom samma sak genom den riktiga
CLI:n med originalunderlag och originalrapport: valideringen passerar och
en testspärr stoppar körningen precis före konstruktion av planeraren.
Detta testar valideringsgränsen; ingen ny plan beräknas i reprot.
Resultat: `legacy-reference-validation.json` och `legacy-reference-cli.json`.

Till Claude: kräv uttryckligen `seed=0`, `refinement=0` och
`seed_variant_shortlist is False` för en fullbiblioteksreferens; avvisa
äldre rapporter som saknar uppgiften. Versionsmärk gärna referenskontraktet.
Testa gammal rapport, felaktiga tak/variantflagga och en korrekt ny rapport.
En generell likhetskontroll av metodsignatur behöver ta hänsyn till avsiktliga
jämförelser mellan kodversioner; kontraktets sökinställningar måste däremot
alltid vara explicita.

## 3. Faktacache, integritet och lås

Det ursprungliga reprot med ett övergående läsfel och oförändrad råfil ger:

| Kod | Rader efter fel | Minnesposter | Diskposter | Rader vid omförsök |
| --- | ---: | ---: | ---: | ---: |
| Baslinje `d09eaf4` | 0 | 0 | 1 | 0 |
| Kandidat `ad0411f` | 0 | 0 | 0 | 1 |

Råfilens hash är oförändrad; en separat färsk cache ger en rad i båda fallen.
De två nya regressionstesterna täcker både läsfel och filändring mellan
hashningarna. `storable` frågas efter beräkningen, och identitetsmarkören
`complete-projection-v2` gör att äldre partiella diskartefakter inte läses.
Det innebär också att berörda faktaprojektioner behöver byggas på nytt vid
första användningen efter kodbytet.

Kodgranskningen bekräftar att råfilshashning före cacheuppslag och andra
hashningen efter läsning finns kvar. SQL, hashning och projektion ligger
fortfarande utanför det globala faktalåset. Det globala låset skyddar
cache-/nyckellåsregistret; nyckellåset skyddar beräkningen för samma nyckel.

Den tidigare dokumenterade luckan i nyckellåsets livslängd är oförändrad:
en väntare kan behålla ett gammalt lås efter att registerposten tagits bort,
medan en ny anropare får ett nytt. Icke-cachebara resultat kan därmed
beräknas dubbelt. Det är en kvarvarande CPU-/minnesbegränsning; patchen
lovar inte single-flight och försvagar inte integritetskontrollen.
Förra serverns överlappsprov återanvänds som historisk evidens; det har inte
körts om eller presenterats som ett nytt resultat.

## 4. Recept, author och ägg

Alla 28 tidigare utfärdade receptversioner är oförändrade av patchen och
omgranskade mot sina föregångare. Samtliga 16 metadataåterställningar bevarar
säkerhetskällor, förvaring och övrig ursprunglig metadata. De 11 vattenstegen
passerar vid 1/2/4/8/12 portioner: **55/55**.

De ursprungliga author-reprona passerar: `100 ml ... 200 ml` för två
portioner blir `200 ml ... 400 ml` för fyra; `125,5 ml` dubbleras till
`251 ml`. Ersättning sker i ett pass över originaltexten, så ett redan
skalat tal kan inte skalas igen. Decimalpunkt och decimalkomma läses;
utdata använder kommatecken. Inget granskningsrecept har publicerats i
det riktiga biblioteket.

Ägginventeringen omfattar alla 189 respektive 330 produktnamn med ”ägg”
i Lund och Malmö, även andra äggprodukter. **235 standardviktsbevis**:
Lund 83 (63 × M/M-L-policy, 20 × L/L-XL-policy), Malmö 152 (121 respektive 31).
Varje bevis har rätt antal × 51 eller 60 gram och samma projicerade mängd.
Ingen sammansatt äggprodukt har fått nytt bevis.

Exakt en faktarad ändras: Lunds `Brunchägg Frigående L/XL 6-pack`,
produkt `ab2247ee321546e4a10630cd13116065` i
`context:coop:23eaae11c9661e68`, får **6 × 60 = 360 g**. Ingrediensraden
”ÄGG från frigående höns inomhus” passerar nu den avgränsade ordlistan.
Inga andra faktavärden ändras; Malmö är semantiskt oförändrat.
Krav på räknat pack, produktidentitet, källa och konfliktkontroll kvarstår.
Saknad fakta eller olämplig viktklass blir fortfarande inte ett viktbevis.

## 5. Underlag, server och mätgränser

Priser, ursprungliga fakta och testklocka kommer från föregående verifierade
frysning: `2026-10-18T05:12:49.467392+00:00`. Lund har 43 821 produkter/
42 357 faktaposter; Malmö 88 340/70 916. Inför denna körning tillämpades
kandidatens äggregel på de frysta faktaraderna. Alla ursprungliga inputhashar
kontrollerades först. Endast ovanstående bevis tillkom. Detta är deterministisk
omprojektion av sparade publika fakta, ingen ny insamling från butikerna.

Matrisen körs i separata containrar på befintlig server, 2 CPU/3 GiB,
en åt gången, utan nätverk. Kandidatens backend monteras skrivskyddad på
den tidigare använda imagen
`sha256:93bbfd2ebe3764cddd559422ed1fce53197359b6f0aabde50619dfc6a81cd8f7`.
Alla 524 filer i kandidatutdraget matchar servern exakt med SHA-256.
Arbetskopian matchar också efter normalisering av Git-radslut; inga
kodskillnader finns. Kvittot listar de berörda CRLF-filerna.
Endast frysta publika underlag och egen resultatyta används; en syntetisk
tom planstore ligger i containerns temporära katalog.

De nya matristiderna avser funktionell jämförelse med en processkall
observation per arm. Faktaunderlaget är redan inläst när `wall_seconds`
mäter `planner.create`; inläsning redovisas separat som `load_seconds`.
De är **inte** en omkörning av förra granskningens
kall/varm-mätning med faktaladdning och isolerat förfiningstak. Referensen
här stänger dessutom av både seedtak och varianturval. Tidigare P1 kvarstår;
denna patch gör inget anspråk på att uppfylla 30-sekundersmålet.
De positiva matrisfallens `planner.create` tog 10,47–263,49 s med default
och 9,76–510,59 s i fullbiblioteksreferensen. Det är enstaka funktionella
observationer, inte ett nytt kall/varm- eller kapacitetsbenchmark.

Förra granskningens uppmätta default kall/varm var exempelvis Lund standard
66,58/46,78 s och Malmö eko 269,76/248,36 s. Full tabell och mätmetod finns
i [föregående rapport](planner-followup-review-20261018.md#6-servermätningar).
Sökningens undre kostnadsgränser och likaprisordning har inte ändrats av
denna patch; de åtta äldre optimeringsreferenserna är historisk evidens,
inte åtta nykörda försök.

Backupfelet i inkommande instruktion är inaktuellt. Lagringsåtgärden på
main `412ebd8` följdes av komplett backup `20261018T084659Z` för båda städerna,
68 filer/7,63 GB. Se [lagringsrapporten](../storage-maintenance.md).
Ingen återställningsövning har gjorts. Slutkontroll **11:59 UTC**: HTTP 200,
`ready`, oförändrad image och build `joint-week-refinement-app-e041451`.
`PRICE_UNIVERSE_PREWARM_ENABLED=false` i både miljöfil och körande container.
Inga granskningscontainrar kör längre. Ingen produktionsaktivering har gjorts.

Kontrollen 11:38 UTC visade samtidigt **12,69 GB ledigt mot 13,99 GB
beräknat kapacitetsbehov**, `adequate=false`. Slutkontrollen visar däremot
**20,02 GB ledigt mot 13,99 GB behov**, `adequate=true`; backupen är fortfarande
`complete`. Vår avgränsade städning omfattade 833,39 MB härledda testunderlag
och 45,87 MB temporära cachefiler. Alla 14 datafiler verifierades mot ZIP:ens
SHA-256 före borttagning; arkiv och återställningspekare är bevarade. Den
större förändringen i totalt ledigt utrymme tillskrivs inte denna städning.
Se `final-runtime-status-public.json`, `data-archive-verification.json`
och `cache-cleanup.json`.

Efter `git fetch origin` låg bara denna granskningsgren sex commits före
main `412ebd8`. Ingen annan gren hade en nyare toppcommit. Äldre divergerande
receptgrenar finns fortfarande: `feature/recipe-integration` (45 egna commits),
`feature/recipe-library` (13), `feature/recipe-ui` (22) och
`perf/recipe-quote-reuse` (12). Deras toppcommits är från 3 oktober och de
är bevarade. Avvikande historik är inte ett bevis på att funktionalitet
saknas på main; föregående rapport redovisar patchmotsvarigheter.
`branch-inventory.json` redovisar
ahead/behind och datum mot main vid granskningens start.

## Leverans och nästa steg till Claude

De sex patchcommitsen och denna granskning är integrerade på `main`.
Leveransen är en enda ZIP med rapport, inkommande patch, full spårad
källkod för `ad0411f`, frysta publika underlag för båda städerna, råresultat,
JUnit, CI-logg, reproduktioner och SHA-256-manifest. Reproduktionsanvisningar
finns i `LAS-MIG-FORST.txt`. Privata driftstatusfiler ingår inte.

Det tidigare evidenspaketet medföljer för historiska mätningar. Det nya
paketets slutrapport gäller framför äldre, nu rättade fynd. Underlaget
för hela den historiska `reports/`-sviten kräver fortsatt separat återställd
utvecklingsbackup; paketet är ingen komplett backup av utvecklingsdatorn.

Prioritera valideringen av äldre fullbiblioteksreferenser. Separat återstår
prestandamålet och en reproducerbar releaseimage. Behåll testerna, priskraven,
de verkliga dataluckorna och den historiska felbaslinjen synliga.
