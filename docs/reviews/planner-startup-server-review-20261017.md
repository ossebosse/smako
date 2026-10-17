# Full granskning för Claude: planner-startup-semantics

Datum: 2026-10-17. Granskad patch: 17 commits, importerade på `main` från
`46d834b` till `35dc44f`. Första granskningscommit: `00dcb8d`.
Denna rapport kompletterar och ersätter verifieringsbegränsningarna i
[den första granskningen](planner-startup-semantics-20261017.md).
Runtimekoden i patchen har inte ändrats under granskningen.

## Besked

Ändringarna passar Smakos syfte: köpbara hela måltider, fler granskade recept,
återanvändning av samma pris-/auditmotor och begripligare förklaringar när
butiksurvalet saknar fullständigt sortiment. **Patchen är inte releaseklar.**
Den når inte ett verifierat godkännande för prestanda, innehållskontrakt och CI.
Ägarens dokumenterade godkännande av äggregeln och näringskonfliktregeln gäller;
granskningen återkallar inte dessa beslut.

## Utförda uppdrag

| Uppdrag | Resultat |
| --- | --- |
| Handoff-granskning | Kod, tester, receptdiffar och reproduktioner genomgångna; se nedan. |
| Kall/varm tid på servern | Genomförd i båda kommunerna, med faktaläsning, plannerarbete och uppvärmning särredovisade. |
| Första GitHub CI | Körning `39032098776`: röd på en felaktig strikt xfail-markering. |
| Serverflagga | Genomförd 13:17 UTC: miljöfil, effektiv Compose-konfiguration och körande app visar `false`. |

## CI och regressioner

[Första GitHub-körningen](https://github.com/ossebosse/smako/actions/runs/39032098776)
körde exakt `00dcb8d` den 17 oktober, 12:20–12:28 UTC. Installation av Chromium
och WebKit samt startup-kontrollen lyckades. Testloggens resultattecken ger
2 767 pass, 51 skips för saknad lokal evidens, 10 xfails och ett
`XPASS(strict)` som gör jobbet rött. Ruff-steget hoppades över eftersom det
bara körs för pull requests. `grocery_data/tests` ingår fortfarande inte i
workflowens testurval; de 51 evidensberoende testerna är inte verifierade
av denna GitHub-körning. Den breda `FileNotFoundError`-hooken för
`reports/` bör senare ersättas med uttryckliga evidensfixturer, så att en
felstavad framtida filsökväg inte maskeras som ett normalt skip.

Det röda testet är
`test_public_menu_errors.py::test_browser_error_classes_retain_choices_and_identify_actual_field`.
Själva webbläsartestet passerar. Patchen klassar det felaktigt som ett känt
baslinjefel. En separat lokal återspelning med `--runxfail` på både `46d834b`
och kandidaten gav samma resultat: **43 pass, 10 fail**, inklusive alla
42 parametriserade tester i `test_personal_choices_browser.py` (Chromium och
WebKit) och det felklassade testet som pass. De övriga tio listade felen
reproduceras på båda versionerna. Ta bort endast den felaktiga markeringen
och behåll synlig uppföljning av de tio faktiska baslinjefelen.

Samma deterministiskt valda panel med 43 planerarfiler kördes på båda
versionerna med `--runxfail` och `SMAKO_REQUIRE_LOCAL_EVIDENCE=1`.
Handoffens exakta tidigare lista med 43 filer finns inte dokumenterad;
granskningens egen lista medföljer som `regression-files.json`.
17 nödvändiga offentliga evidensfiler kopierades till den isolerade baslinjen
och SHA-256-kontrollerades så att underlaget var identiskt. Åtkomstloggarna
är identiska och innehåller inga blockerade externa åtkomstförsök.

| Version | Pass | Fail | Error | Skip/xfail |
| --- | ---: | ---: | ---: | ---: |
| Baslinje `46d834b`, samma evidens | 986 | 26 | 0 | 0 |
| Kandidat `35dc44f` | 1 035 | 1 | 0 | 0 |

De 26 gamla felen gäller inaktuella antal/fält i cache-/interningtester som
patchen rättar. Det nya kvarvarande felet är
`test_recipe_resolution.py::test_shell_mass_projection_requires_separate_purchase_opt_in`:
dess förväntan följer den gamla äggpolicyn. Anpassa testet till det godkända
beslutet och lägg samtidigt till en kontroll av den faktiska bevisklass som
ska visas. Felet syns inte i ren GitHub-klon eftersom just dess evidens saknas.

Tidigare körda 593 riktade/regressionstester passerade utan skips eller xfails.
En extra felinjektion med permanent auditfel stoppar planeringen och lämnar
ingen plan; även den passerar. `compileall` och `git diff --check` passerade.
Ruff på patchens samtliga ändrade Pythonfiler ger **23 fel i sex rapportskript**.
Det är ytterligare ett verkligt CI-hinder för en PR med hela patchen.
Felen fördelas på `builder.py` (2), `make_basil_fix.py` (2), `make_fixes.py` (5),
`new_dinners.py` (5), `new_recipes.py` (2) och `qualify.py` (7).
Rapportskriptens absoluta `/home/claude/...`-sökvägar behöver också göras
konfigurerbara för att påståendet om reproducerbarhet ska gälla utanför
författarens miljö. Den här granskningen använder därför egna sparade prober
mot det registrerade innehållet och serverns verkliga råkällor.

## Fynd som behöver hanteras

### Långa specialprofiler är fortfarande ett driftproblem

I den sekventiella Lundmatrisen med seedtak 40 tog makroprofilen cirka
261 sekunder och 20 procent ekologisk inköpskostnad cirka 278 sekunder,
utan faktaläsning. `planner.timings` visar cirka 247 sekunder veckosökning
för makroprofilen och 232 sekunder ekologisökning för ekologiprofilen.
Dessa faser är nästlade och ska inte summeras. Auditen av den valda menyn
är redan en mycket liten del av tiden.

Servern är verifierad till en samtidig planerarplats och fyra köplatser.
Långa användarjobb ger därför även väntan för andra användare.
**P1 för bred lansering:** profilera och begränsa det kvarvarande dyra
sökarbetet med bevarade krav, giltiga incumbents och ärlig rapportering av
sökbudget. En startuppvärmning löser inte denna del. Observationerna är
enskilda prov på en delad server, inte en skattad produktions-p95.
De separata slutliga kall/varm-proven redovisas i mättabellen.

### Näringskonflikter används ändå i produktkvalificering

`complete_recipes.py:226` släpper nu igenom näringskonflikter, vilket följer
ägarbeslutet. Men `_requirements_compatible` och
`content_pack_requirements.compatible` läser fortfarande konfliktmärkt fett
för `thick`, `cottage_cheese` och `creme_fraiche`. Grekisk naturell yoghurt
utan fettprocent i namnet godkänns som tjock med konfliktmärkt `fat_g=10` och
underkänns när just det värdet tas bort. Näringssummeringens spärr är kvar;
produktvalets näringsfallback är inte spärrad. **P2:** ignorera konfliktsatta
värden även här och testa båda konsumenterna.

### Faktauppvärmningen kan blockera och lämnar dyrt arbete i varma anrop

`personal_source_facts._load_retained_catalog_facts` håller ett globalt
`RLock` över databasfrågor, filhashning och projektion. En kontrollerad
trådreproduktion visar att även en annan kommuns användaranrop väntar på
låset. Påståendet i `source_facts_prewarm.py` att användaren som mest
upprepar inläsningen stämmer inte. Inga SQLite-anslutningar delas felaktigt
mellan trådarna, och uppvärmningen tar inte planner admission, men det
eliminerar inte väntan på faktalåset. **P2:** flytta dyrt arbete utanför
publiceringslåset och mät samtidiga anrop. Bevara kontrollen av saknade,
utbytta och korrupta råkällor; ta inte bort den för att få lägre mättid.

### Author tappar produktkrav när komponenter slås ihop

`recipe_authoring.py:90–96` slår ihop på enbart `canonical|form` och behåller
första komponentens krav. 150 g yoghurt med `plain` + 20 g med `plain, thick`
blir 170 g med endast `plain`, och paketet godkänns. **P2:** avvisa
oförenliga krav eller förena dem med en uttrycklig kompatibilitetsregel.

### Author underräknar aktiv matlagningstid

`recipe_authoring.py:48–58,123` räknar aktiv tid som total tid minus passiv
tid på den kritiska kedjan. Arbete i parallella grenar försvinner. Exemplet
har 31 minuters aktiva steg men publicerar 16 aktiva minuter, 30 vänteminuter
och 46 totalt. Då kan ett recept passera användarens gräns på 20 aktiva
minuter. **P2:** summera aktiv arbetsinsats separat från väggtid och överlapp.

### Nya recept skalar inköpen men inte vatten i instruktionerna

Elva nya steg saknar `scalable_amounts` trots fasta vattenmängder i texten.
Vid 12 portioner innehåller grekisk citronsoppa 480 g ris och 1 500 g kyckling
men fortfarande bara instruktionen ”8 dl vatten”. Pasta e ceci skalar till
840 g torr pasta men behåller 8 dl; rådet att späda vid behov mildrar bara
det senare problemet. Befintlig portionsskalning kan hantera deklarerade
processmängder. **P2:** använd den och verifiera 1, 2, 4, 8 och 12 portioner.

### Recepttext och tillåten produkt stämmer inte alltid

Den nya köttfärssåsen heter ”… spaghetti …” men ingrediensen har `pack:pasta`,
vars regel bara tillåter kort pasta och utesluter spaghetti. Den nya
fiskgratängens komponentetikett erbjuder torsk/sej, medan `pack:cod` bara
tillåter torsk. **P2:** gör namn, komponentetiketter och produktkrav
samstämmiga; en kvalificerad korg bevisar inte att köparen får textens vara.

### Rättelsepaketet ändrar mer än handoffen beskriver

Jämförelsen visar exakt 25 nya recept och 16 ändrade befintliga, inga borttagna.
Ingrediensändringarna följer beskrivningen: chili, fryst majs, sex
basilikarättelser och stekmetod för kycklingnudelsalladen. Kapris har inte
ändrats. Men alla 16 rättelser tar också bort `content_source.safety_sources`
och ersätter konkreta förvaringsråd med allmän förpackningstext. Metod- och
skalningsnoter byts också. `complete-recipes.js:338` visar förvaringsnoten
i användargränssnittet under ”Rester och förvaring”. **P2:** bevara den granskade metadatan eller
redovisa och motivera varje sådan ändring. Historiska versioner finns kvar.

### Ägg: godkänt policybeslut, kvarvarande fråga om presentationens bevisklass

Ägarbeslutet tillåter antal × klassens lägsta skalvikt × 0,88 i exakt läge.
Koden följer detta. Men referensen säger `documented_population_estimate`,
medan 15 M-ägg blir 699,6 g `DERIVED` och kan ge presentationen `VERIFIED`.
En lägsta skalvikt gånger genomsnittlig ätbar andel bevisar ingen lägsta
ätbar vikt. Detta är **en kvarvarande policy-/presentationsfråga**, inte
ett påstående att ägarbeslut saknas. Visa grunden sanningsenligt och följ
handoffens beslutade vägning. Granskningen ändrar inte regeln på eget initiativ.

## Kod och innehåll som bedöms hålla

- Offertåterbruket: `canonical_name` används i `quote_item` till radetikett
  och feltext; de beräknade pris-/mängdfälten beror inte på radnumret.
  Återanvänd offert märks med aktuell ingrediens. Produkt, kvantitet,
  prissammanhang och kampanjvillkor ligger kvar i nycklarna.
- Audit: slutmenyn räknas om och auditeras; en auditunderkänd vinnare utlöser
  ny sökning med audit. Bevarade giltiga alternativ auditeras på nytt.
  Permanent auditfel ger ingen plan i den extra reproduktionen.
- Seedtaket: full-pool-reservförsöket och efterföljande förfining behåller
  hela urvalet. Taket är en urvalsheuristik, ingen optimalitetsgaranti;
  skyddade kök/okända underlag kan dessutom göra urvalet större än 40.
- Innehåll: de 25 nya recepten har granskats mot ingredienser, former, steg
  och angivna kontroller. Köttfärslimpa utan ägg är en rimlig konstruktion
  med blötlagd smula/mjölk; pasta e ceci kokas avsiktligt i grytan.
  Portionsskalningen ovan behöver rättas. Ingen provlagning har utförts.
- Paprika: köpbara grampack är en bättre direkt grund än att göra en
  genomsnittlig styckvikt till exakt massa. Inför inte en sådan omräkning
  som ”verifierad” utan separat stöd och tydlig policy för uppskattning.

## Acceptansmatris: samma resultat med optimering och seedtak

**20 av 20 profiljämförelser är identiska** för kandidatens seedtak 0 mot 40.
Även **20 av 20 är identiska** mot den separata optimeringsreferensen med
samma innehåll. Det innebär 14 positiva profiler med identisk semantisk
SHA-256 och sex blockerade med samma felkod. Fakta-versionerna är identiska
inom varje jämförelse. Kall och varm standardplan ger också samma hash i
samtliga sex matrisprocesser.

Hashen omfattar hela recepten, korgen med köp-/prisvillkor, näring, audit och
skafferifördelning. Alla positiva resultat passerar kontroll av audit,
underskott, mängder, kost/näringskrav, fördelning, eko och butiksurval.
Inga externa nätanrop tillåts.

| Profil | Lund, kr/resultat | Malmö, kr/resultat |
| --- | ---: | ---: |
| standard | 535.06 | 534.92 |
| protein40 | 796.40 | 1012.83 |
| all-macros | 813.14 | 1012.83 |
| vegan | 455.28 | 473.17 |
| distribution | 775.86 | 1089.72 |
| organic-share | 352.22 | 352.12 |
| breakfast-snack-weight | 64.06 | 60.16 |
| allergy-milk | DATA_BLOCKED | DATA_BLOCKED |
| organic-animals | DATA_BLOCKED | DATA_BLOCKED |
| impossible-protein | NUTRITION_TARGET_NOT_MET | NUTRITION_TARGET_NOT_MET |

Tabellen gäller den gemensamma kandidaten med båda seedtaken och
optimeringsreferensen. Den är inte ett påstående om att gamla main, med andra
recept och semantik, ska ge samma meny eller pris. Blockerade allergi- och
eko-djurprofiler visar att underlagskraven består; de räknas inte som
framgångsrikt planerade menyer.

## Kvalificering och produktgranskning i Lund och Malmö

Varje ändrat aktuellt recept låstes till en plats och kördes genom ordinarie
`PersonalPlanner`, exakt inköpsläge, högst två butiker, tomt syntetiskt
skafferi, fyra portioner för middag och en för frukost/mellanmål.

| Aktuella ändrade recept | Lund | Malmö |
| --- | ---: | ---: |
| Kvalificerade | 41/41 | 16/41 |
| Stoppade med `DATA_BLOCKED` | 0 | 25 |

I Malmö stoppas tio av ingefära som viktvara, sju av majs, två vardera av
fisk, limejuice, tortillas och jordnötssmör. Alla 16 rättade äldre recept
stoppas där; av de 25 helt nya kvalificerar 16. Den kompletta listan med
recept-ID, version, pris eller felorsak finns i `malmo-supplement.json`.
Detta är ett faktiskt kommunberoende köpbarhetsresultat, inte bevis för ett
nytt kodfel i varje recept. Lunds gamla kvalificeringsrapport kan inte
användas som generell garanti för Malmö. Behåll exakta krav och visa varför
alternativ saknas; gör ingen tyst övergång till uppskattad vikt.

Produktinventeringen omfattar 306 relevanta rader i Lund och 635 i Malmö.
Namn/kategori, identitetsbeslut och receptform har jämförts. De färska
paprikaträffarna är gröna/gula/röda/orange paprikor, färgmix och spets,
alla i färskvarukategorier. Rökt paprika ligger i krydd-/skafferikategorier.
Ingen kryddpåse passerar båda kontrollerna som färsk paprika i inventeringen.

| Kontroll | Lund | Malmö |
| --- | ---: | ---: |
| Paprika, godkänd identitet + receptform | 26 produktrader | 53 produktrader |
| Rökt paprikapulver, samma två kontroller | 6 | 11 |
| Strimlad vitkål, samma två kontroller | 5 | 8 |
| Fyllda-deg-markörer, samtliga täckta | 59 rader | 105 rader |
| Unika namn klassade som färdigrätt | 36 | 32 |

De godkända strimlade grönsakerna heter `Vitkål Strimlad`/`Vitkål Strimlad
Klass 1`; ingen strimlad morot/rödkål passerar i dessa underlag. Även de
strimlade kycklingträffarna har granskats; de godkända namnen är rå
kycklingfilé/bröstfilé, inte färdigrätter. Samtliga fyllda-deg-träffar
kontrollerades mot den exakta namnregelns markörer, inklusive normaliserade
stavningar. Ingen träff saknas i inventeringen och ingen klassad färdigrätt
accepteras som de kontrollerade råingredienserna.
`Gyoza Sauce`, `Gyoza Skin Deg Fryst` och `Spring Roll Sauce` undantas korrekt
i båda städerna. Alla produktnamn och beslut medföljer i
`inventory-review.json` och respektive stads supplement/coverage-fil.

HTTP-provet ger `422 DATA_BLOCKED` i båda städerna för både ICA-only och
ICA + Willys. Den särskilda texten om enbart kampanjpriser finns bara för
ICA-only, som avsett. Provet använder appens riktiga requestvalidering och
felserialisering samt riktiga plannerfel, men injicerar worker-steget för
att låsa fakta/klocka/tillstånd. Det bevisar inte admission, persistens eller
produktionsköernas beteende.

## Author mot verkliga råkällor utan faktadump

Ett nytt recept, ”Spiskumminkyckling med ugnspotatis, gurkyoghurt och
tomatsallad”, skapades från det kompakta formatet med ett nytt ID och
spiskummin i stället för exemplets oregano. I båda städerna kördes
`meal_library_cli author --import --prepare 2 --prepare 4 --universe ...`
med låst klocka och **utan `--facts`**. Nätverk var avstängt.

Author, import och förberedelse lyckades utan rejections. Receptet har elva
räknade ingredienser, är valbart med standardval och kvalificerar i exakt
inköpsläge med högst två butiker: **220,73 kr i Lund och 227,60 kr i Malmö**.
Det nya paketet importerades bara i containerns disponibla kodkopia;
originalmanifestets hash förblev oförändrad. Detta ändrade inte repo eller beta.

Första provet saknade `grocery_data` bredvid den tillfälliga backendkopian
och stoppade i cache-signaturens filkontroll. Provmiljön fick därefter en
länk till samma skrivskyddade stödkatalog och omkörningen lyckades. Den första
miljömissen och slutresultaten finns båda i underlaget. Inget runtimefel
”rättades” för att få provet att passera. CLI-resultatet rapporterar fortfarande
16 aktiva minuter för den granskade stegstrukturen, vilket inte undanröjer
fyndet om 31 minuters faktiskt aktivt arbete.

## Spårning mot handoffens granskningspunkter

| Handoffpunkt | Kontroll och slutsats |
| --- | --- |
| Delmenyaudit och vald meny | Flöden till slutmeny/incumbent följda; slutlig audit och omförsök kvar. Permanent auditfel ger ingen plan. |
| Offertens radnummer | Endast etikett/feltext använder namnet; pris-/mängdresultat och kampanjvillkor påverkas inte. |
| Samma resultat före/efter optimering | Separat referens med samma innehåll och återställd offert-/auditberäkning; se matristabellen. |
| Seedtak 0/40 i båda kommunerna | Samma artefakt, fakta och klocka; positiva hashvärden och negativa felkoder jämförs. Full-pool-reservvägen kvar. |
| Verklig kall/varm servermätning | Ny process respektive andra plan i samma process; faktaläsning särredovisad. |
| Faktauppvärmning och trådsäkerhet | Samma loader, egna SQLite-anslutningar och ingen admission-plats. Gemensamt lås blockerar ändå; se fynd och överlappsprov. |
| Paprika/rökt paprika, fyllda degrätter och strimlad råvara | Full träffinventering mot båda låsta aktiva artefakterna, med namn, kategori och formbeslut. |
| Kampanjbutikstext | `/api/plan` med verkliga plannerfel och tom syntetisk state; ICA-only mot ICA + Willys. Worker-injektionen avgränsar bort admission/persistens. |
| Samma regressioner och nya tester | 43-filerspanelen, delade evidenshashar, 593 riktade tester, felinjektion och browseråterspelning redovisade ovan. |
| 13 + 12 nya recept | Mängder/form/ordning och praktisk rimlighet granskade; vattenmängder och två etikettkontrakt behöver rättas. Ingen provlagning. |
| Endast beskrivna fält i 16 rättelser | Avvikelse: säkerhetskällor, förvaringsråd och ytterligare metadata ändras också. |
| Kvalificering Lund/Malmö | Alla 41 ändrade aktuella recept provas enskilt i ordinarie PersonalPlanner, exakt inköpsläge, högst två butiker. |
| `author` utan `--facts` | Nytt spiskumminkycklingrecept, author → import → prepare 2/4 → qualify, i en disponibel kodkopia med verkliga råkällor. |
| Ägg och näringskonflikter | Ägarbesluten respekteras. Konfliktfett används fortfarande i produktkrav; äggens presentationsklass behöver förtydligas. |
| GitHub-browser/CI | Körningen är genomförd: browserinstallationen fungerar, men felaktig strikt xfail gör CI röd. |
| Serverns price-universe-flagga | Miljöfil och effektiv runtime verifierade till false, samma image och bevarade planer. |

## Föreslagen arbetsordning för Claude

1. Rätta konfliktmärkt näringsfallback och lägg regressioner för båda
   produktkravskonsumenterna. Behåll ägarens regel att en ren näringskonflikt
   inte i sig stoppar produktidentitet/form.
2. Rätta author-sammanslagning och tidsdefinition. Lägg exempel med skilda
   produktkrav och parallella aktiva steg; godkänn inte borttappade krav.
3. Publicera rättade receptversioner med skalbart processvatten, samstämmiga
   etiketter och bevarad/motiverad säkerhets- och förvaringsmetadata. Behåll
   tidigare utfärdade versioner oförändrade i historiken.
4. Ta bort den felaktiga xfail-markeringen, rätta de 23 Ruff-felen och uppdatera
   det gamla äggtestet till den beslutade policyn med ärlig bevisklass.
   Kör browserfallen och evidenspanelen igen för berörda ändringar.
5. Profilera ekologisökning och dyra makroprofiler. Flytta faktaläsningens
   dyra arbete utanför det globala publiceringslåset utan att förlora kontroll
   av råkällornas integritet. Återspela exakt samma matris/klocka och jämför
   både semantiska hashvärden och separata kalla/varma tider.
6. Red ut live-imagens källkodsavvikelser före en senare kodrelease. En release
   kräver egen aktiveringsauktorisation; denna granskning har bara aktiverat
   den beställda miljöflaggan.

## Mätmetod och avgränsning

Mätningarna kördes på Smakos server i separata containrar med högst
två CPU:er och 3 GiB RAM per process, utan nätverk. Den slutliga parade
kall/varm-serien kördes en process i taget efter driftändringen. Funktionella
hash-/matrisjämförelser körs delvis två åt gången efter att appens omstart
frigjort minne; deras tider används inte som parade prestandabevis. Databas och råkällor är
skrivskyddat monterade. Ingen produktionsplan eller användarprofil används;
planeraren får tomt syntetiskt tillstånd. Den aktiva appen driftsätts inte
med patchen. Samma aktiva basimage används för båda Git-versionernas kod.

Lunds och Malmös aktiva artefakter kopierades och låstes med SHA-256;
pris-/giltighetsklockan är `2026-10-17T12:22:12.873633+00:00` för alla fall.
Fakta laddas från kvarhållna serverråkällor, inte från Claudes faktadump.
Faktaversionerna sparas för att upptäcka förändrat underlag.

| Låst input | SHA-256 |
| --- | --- |
| `lund.json` | `3f3b6d7918f0900f81306ea5c7b1eb73705eec723eb10414ae162033a8a4794e` |
| `malmo.json` | `8423bc2f8265c9b8929863de018282e491d14ad1f1aa0f157de1dd2bb3f23bd8` |

”Kall” betyder ny Pythonprocess och ny receptförberedelsecache. OS-filcachen
har inte tömts. ”Varm” betyder andra standardplanen i samma process, med ny
planner och ny faktisk `load_retained_facts`. Artefaktåterställning mäts
separat. Övriga matrisfall använder samma redan laddade faktasamling och
mäter därför plannerarbete, inte hela requestens faktaläsning.

Det är en delad server med pågående ordinarie underhåll. Enstaka sekventiella
prov ger varken p95, kapacitetsgaranti eller säkra procentsatser för produktion.
Detta är direkt planerarmätning, inte verklig HTTP-latens inklusive kö,
autentisering, persistens och transport. Skillnader mellan gammal main och
hela patchen kan bero på både recept/semantik och optimering; identisk hash
kan därför inte krävas för hela den jämförelsen. Tak 0 mot 40 på samma
kandidat är däremot en direkt jämförelse av samma innehåll och regler.

En separat optimeringsreferens behåller kandidatens recept, regler och fakta
men återställer offertcachen från `011fa0e^` och auditerar varje sökkorg.
Det är en dokumenterad diagnostisk kodkombination, inte en publicerad commit.
Dess ändrade filhashar följer med som `optimization-reference-manifest.json`.
Den jämförs med kandidaten utan seedtak för att skilja optimering från
innehållsändringar.

## Slutlig kall och varm servermätning

Standardprofil: fem middagar × fyra portioner, högst två butiker,
uppskattad inköpsvikt tillåten, samma låsta prisunderlag och klocka.
Serien kördes efter den verifierade driftändringen, en provcontainer i taget.
Alla tider är sekunder; totalsumman är faktaläsning plus plannerarbete.

| Stad/version | Kall totalt | Fakta | Planner | Varm totalt | Fakta | Planner | Pris, kr |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| lund / 46d834b | 130.4 | 17.9 | 112.6 | 117.6 | 7.3 | 110.3 | 612.57 |
| lund / 35dc44f, tak 40 | 73.5 | 19.1 | 54.4 | 54.8 | 5.2 | 49.6 | 535.06 |
| malmo / 46d834b | 155.5 | 21.7 | 133.8 | 135.0 | 8.9 | 126.2 | 646.03 |
| malmo / 35dc44f, tak 40 | 78.5 | 20.4 | 58.1 | 58.5 | 9.0 | 49.4 | 534.92 |

Artefaktläsning/återställning ingår inte i tabellen: lund baseline-cap0: 13.9 s; lund candidate-cap40: 14.5 s; malmo baseline-cap0: 27.8 s; malmo candidate-cap40: 28.2 s.

Detta är en kall och en varm observation per version och kommun, ingen
kapacitets- eller p95-skattning. Hela patchen ändrar också receptutbud och
semantik; skillnaden mot gamla main isolerar därför inte enbart optimering.
Kall och varm plan ger samma resultat inom respektive version.

### Färdig faktauppvärmning och verklig samtidighet

En separat kandidatprocess körde den faktiska uppvärmaren färdigt före första
användarjobbet (`start=False`). Förberedelsen redovisas separat, inte som
försvunnen kostnad. Samma pris/hash erhölls som kandidatens standardplan.

| Stad | Uppvärmning | Första användarjobbet | Andra användarjobbet |
| --- | ---: | ---: | ---: |
| lund | 31.2 s | 56.7 s | 74.3 s |
| malmo | 41.3 s | 62.8 s | 61.2 s |

I ett verkligt överlappsprov startade ett Lund-jobb när Malmös bakgrundstråd
höll det ordinarie faktalåset. Ingen konstgjord fördröjning lades in.
Användartråden väntade **14.9 sekunder på låset**. Hela användarjobbet tog
85.9 s, varav faktaläsning inklusive väntan 37.0 s
och plannerarbete 48.9 s. Planen klarade samma kvalitetskontroller.
Detta verifierar låsfyndet med riktiga råkällor, men är ett avsiktligt valt
överlapp, ingen skattning av hur ofta en verklig användare drabbas.
Överlappscontainern fick 5 GiB för båda kommunernas artefakter; övriga fick 3 GiB.

Uppvärmningsproven isolerar den faktiska uppvärmarfunktionen och användarens
fakta-/plannerarbete i nya processer. De är inte en genomkörning av hela
FastAPI-uppstarten med samtidiga inloggade HTTP-klienter. En senare
kodaktivering behöver därför också en sådan start- och belastningskontroll.

## Genomförd driftändring

Den 17 oktober kl. **13:17:04 UTC (15:17 svensk tid)** sattes
`PRICE_UNIVERSE_PREWARM_ENABLED=false` i
`/opt/smako/current/activation-private.env`. En äldre Compose-override tvingade
värdet till `true`; därför lades en sista, avgränsad override till som läser
värdet från miljöfilen. Den effektiva Compose-diffen verifierades till exakt
`app.environment.PRICE_UNIVERSE_PREWARM_ENABLED: true -> false`.

Åtgärden väntade på och tog det befintliga driftlåset. Efter kontroll av
inaktiv användarplanering och en verifierad säkerhetskopia av planlagret
återskapades endast appcontainern, med **samma image**
`sha256:93bbfd2ebe3764cddd559422ed1fce53197359b6f0aabde50619dfc6a81cd8f7`.
Ingen patchkod aktiverades. Scheduler och proxy behöll sina container-ID:n.
Planinnehållets radhasher, prismanifestens filhashar och båda städernas laddade
universe-ID:n var oförändrade. Runtimeflaggan är `false` och båda städerna
svarar `ready` med samma build-ID. En upprepad kontroll kl. 14:08 UTC
bekräftade samma flagga, image, build och universe-ID:n; resultatet finns i
`final-runtime-check.json`.

`ready` betyder här att tjänstens gällande användbarhetskrav uppfylls.
Prisunderlagen rapporterar samtidigt `degraded`/`requires_attention`, med
äldsta användbara grundpriser cirka 63 timmar i Lund och 81 timmar i Malmö.
Den befintliga policyn `retain-until-replaced` har inte ändrats. Detta är
ett separat datadriftsläge, inte något som konfigurationsbytet löser.
Privata miljö- och databasbackuper ligger skyddade på servern och exporteras
inte i granskningspaketet.

## Server, brancher och underlag

Den aktiva appen kör `joint-week-refinement-app-e041451`; `e041451` är anfader
till main. Efter normalisering av radslut skiljer sig nio
appfiler (admin, konfiguration, Coop-provider och butiksdrift) från både
`e041451`, `46d834b` och `35dc44f`. Dessutom saknas
`data/recipes/all-meal-classes-20261008.json` i live-imagen. Det är ingen
byteidentisk full live-baslinje. Filhasharna finns i
`live-code-comparison.json`. En senare release måste reda ut dessa skillnader
innan någon kod skrivs över; konfigurationsåtgärden använder samma image.

Ingen befintlig remote-branch var före eller nyare än main vid inventeringen.
Äldre lokala grenar har egna historiska commits; de redovisas i första
granskningen. De har inte slagits ihop eller ändrats.

Verifieringsskript, maskinläsbara resultat, testlistor och receptdiffar finns
i `smako-review-for-claude-20261017.zip`, med en manifestfil som anger SHA-256 för varje
medföljande fil. Serverns låsta underlag och prober finns i
`/opt/smako/evidence/planner-review-20261017-00dcb8d`. Paketet innehåller inga
privata miljöfiler, databaser, användarprofiler eller produktionsplaner.
Syntetiska planer från granskningens tomma testtillstånd ingår som
reproduktionsunderlag.
