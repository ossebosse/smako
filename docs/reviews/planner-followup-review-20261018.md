# Smako: granskning av uppföljningspatchen, 2026-10-18

Slutrapport för Claude. Alla sex beställda granskningsavsnitt är genomförda.
Runtimekoden är oförändrad under granskningen; inga testkrav har sänkts.

## Omfattning och kod

Granskad patch: `smako-review-followup.patch`, 13 importerade commits
`9aeda34..0765221` ovanpå `d09eaf4`. Instruktionsfilen anger 12; patchen
innehåller 13. Endast en HANDOFF-konflikt behövde lösas: både den förra
rapporten och de nya handoff-posterna bevarades. Ingen produktionsaktivering.

Första PR: [#1](https://github.com/ossebosse/smako/pull/1).
Första CI: [39099491097](https://github.com/ossebosse/smako/actions/runs/39099491097).

## Bedömning och återkoppling till Claude

Ändringarnas inriktning passar Smako: produktkrav och förvaring bevaras,
ägarnas äggpolicy följs och samma pris-/auditmotor används. CI-hindren från
förra granskningen är rättade. Det är fortfarande inte ett releasegodkännande:
fullbiblioteksreferensen, felaktigt persisterade faktaprojektioner och
skalningen i author har reproducerade avvikelser. Prestandan har förbättrats i flera profiler, men långa jobb kvarstår.
Den tidigare P1-bedömningen inför bred lansering kvarstår; se avsnitt 6.

| Föregående handoffpunkt | Bedömning i denna granskning |
| --- | --- |
| Konfliktmärkt fett används som klassbevis | Rättad: `declared_fat_g` spärrar konflikter för båda konsumenterna; regression passerar. Namnets uttryckliga fetthalt är fortsatt separat bevis. |
| Author tappar krav vid sammanslagning | Rättad: skilda krav för samma inköpsrad ger uttryckligt fel; test passerar. |
| Author underräknar aktiv tid | Rättad enligt beställt kontrakt: alla aktiva steg summeras, även parallella. 31/15/46 i exemplet. Totalens max-formel är en tidsmodell, inte en verifierad resursplan för en ensam kock. |
| Vatten, namn och etiketter i de utfärdade recepten | Rättade i de 28 versionerna; generell author-skalning har kvarstående avvikelse nedan. |
| Förlorad innehålls-/säkerhetsmetadata | Återställd i samtliga 16 berörda recept. |
| Felaktig XPASS, Ruff och gammalt äggtest | Rättade; första PR-CI grön och äggtestet passerar med lokalt underlag. |
| Globalt faktalås | Dyrt arbete flyttat ut; diskcachekontraktet har ett separat kvarstående basfel. Överlappsmätningen finns i avsnitt 4. |
| Långa specialprofiler | Förbättringar i flera profiler, men inte uppfyllt 30-sekundersmål; se avsnitt 6. |

## 1. Regression och CI

**Bedömning: godkänd mot dokumenterad baslinje och grön första PR-CI; fullsviterna är inte felfria.**

Backend med återställd lokal evidens, `SMAKO_REQUIRE_LOCAL_EVIDENCE=1`,
`--runxfail`: 2 827 PASS, exakt 10 dokumenterade FAIL, 0 ERROR, 2 SKIP
(de separat körda evidensberoende taktesterna). Totalt 2 839, 869,048 s.
Samtliga 28 lästa rapportfiler fanns; inga förbjudna läsningar eller
nätverksanrop registrerades av offlinevakten. Ägg-/receptupplösningen:
39/39 PASS. Webbläsare: 42/42 PASS. Ekosökningens gränstester: 22/22 PASS.

Första PR-CI är grön: 2 776 PASS, 10 XFAIL, 53 SKIP och inget XPASS.
51 skip är från lokal evidens som inte finns i ren klon, två är taktesterna.
Ruff-steget kördes och passerade. Lokal Ruff på ändrade Python-filer,
compileall och `git diff --check` passerade också.

De tio faktiska backendfelen matchar exakt listan i `conftest.py` och
`docs/TESTING.md`: municipal runtime (1), plan API (1), offentlig UI (2),
publika menyfel (2) och purchase planning modes (4). Inga markeringar togs
bort för att få denna granskning grön.

Grocery-sviten kördes också komplett och separat: 1 909 PASS, 5 FAIL,
0 SKIP/ERROR, totalt 1 914 på 1 300,046 s. Samtliga fem ICA-fel
reproducerades i en ren, tillfällig worktree på `d09eaf4` med samma
felmeddelanden (bortsett från minnesadresser). Källträdet `grocery_data`
är hashidentiskt före/efter. Se `grocery-baseline-comparison.json`.
Den sviten ingår fortfarande inte i GitHub-jobbet. Båda fullsviterna
omfattar totalt 4 753 icke-live-fall: 4 736 PASS, 15 verifierade basfel
och två evidensberoende taktester som körs separat. Baseline-worktreen
är borttagen efter att resultaten sparats.

## 2. Taken och referensen utan tak

**Bedömning: de namngivna takjämförelserna godkända på frysta data; avvikelse i fullbiblioteksreferensens definition.**

Alla 20 matrispar har `uncapped_check: ok`. Samtliga 14 positiva par
har identiskt pris och semantisk hash, godkänd slutlig audit och inga
okända mängder. De sex negativa paren har samma felkod; stage-fältet är tomt i båda armarna.
Ingen profil blev dyrare; taken behövde därför inte höjas.

| Stad | Profil | Default 40/90 | Seed 0/refinement 0 | Hash/utfall |
| --- | --- | ---: | ---: | --- |
| lund | standard | 548.76 kr | 548.76 kr | `2d9bf97b3d91` lika |
| lund | vegan | 455.28 kr | 455.28 kr | `cce8b34593e8` lika |
| lund | protein40 | 796.40 kr | 796.40 kr | `a8818669069c` lika |
| lund | all-macros | 813.14 kr | 813.14 kr | `f7a88c18677d` lika |
| lund | organic-share | 352.22 kr | 352.22 kr | `f5ed145e94e6` lika |
| lund | distribution | 775.86 kr | 775.86 kr | `3c89adb5b68b` lika |
| lund | breakfast-snack-weight | 64.06 kr | 64.06 kr | `14e57e4cfe49` lika |
| lund | allergy-milk | DATA_BLOCKED | DATA_BLOCKED | Steg ej angivet i båda |
| lund | organic-animals | DATA_BLOCKED | DATA_BLOCKED | Steg ej angivet i båda |
| lund | impossible-protein | NUTRITION_TARGET_NOT_MET | NUTRITION_TARGET_NOT_MET | Steg ej angivet i båda |
| malmo | standard | 534.92 kr | 534.92 kr | `4fbc3f8f6847` lika |
| malmo | vegan | 473.17 kr | 473.17 kr | `0473a4f5b74e` lika |
| malmo | protein40 | 1012.83 kr | 1012.83 kr | `acb93f04e83f` lika |
| malmo | all-macros | 1012.83 kr | 1012.83 kr | `c04e077c9543` lika |
| malmo | organic-share | 352.12 kr | 352.12 kr | `9b832c119e6a` lika |
| malmo | distribution | 1089.72 kr | 1089.72 kr | `cd34685afa91` lika |
| malmo | breakfast-snack-weight | 60.16 kr | 60.16 kr | `1ea5e05e78cf` lika |
| malmo | allergy-milk | DATA_BLOCKED | DATA_BLOCKED | Steg ej angivet i båda |
| malmo | organic-animals | DATA_BLOCKED | DATA_BLOCKED | Steg ej angivet i båda |
| malmo | impossible-protein | NUTRITION_TARGET_NOT_MET | NUTRITION_TARGET_NOT_MET | Steg ej angivet i båda |

Separat `test_search_caps_vs_uncapped.py`:

- lund: 9 PASS (två jämförelsetester + samtliga sju verkliga profiler), 0 FAIL/ERROR/SKIP; 1230.2 s enligt JUnit.
- malmo: 9 PASS (två jämförelsetester + samtliga sju verkliga profiler), 0 FAIL/ERROR/SKIP; 1321.9 s enligt JUnit.

Båda parametriserade pytest-körningarna gjordes lokalt med frysta serverdata.
Lunds acceptansmatris kördes lokalt; Malmös kördes på servern med två arbetare
efter den seriella tidsmätningen och överlappsprovet. Dessa funktionstesters
tider används inte som prestandabevis.

Ett godkänt prov gäller dessa profiler på detta frysta underlag; det bevisar
inte att ett heuristiskt tak aldrig kan ge dyrare planer vid framtida recept-
eller prisändringar. Testet behöver följa sådana ändringar.
`--uncapped` sätter både seed och refinement till 0; serverns tidsjämförelse
sätter endast refinement till 0 och behåller seed=40. Dessa referenser får
inte blandas ihop.

Granskningsharness: första separata Malmöförsöket gav två PASS och sju
FAIL före planering eftersom PowerShell `ConvertFrom-Json` gjorde UTC-strängen
till lokal `DateTime`; miljövariabeln blev `2026-10-18 07:12:49` utan tidszon.
Färskhetskontrollens spärr fungerade och stoppade alla sju profiler. Fellogg
`malmo-cap-pytest-clock-error.*` är bevarad. `run_cap_pytest.py` läser i stället
originalsträngen direkt i Python och kräver tidszon före start; hela körningen
upprepades med oförändrad appkod och oförändrade testkrav. Båda städernas separata pytest-körningar gav vardera tre Pydantic-
serialiseringsvarningar om strängvärden i enum-fälten `quantity_confidence`
och `semantic_confidence` i ekoprofilen; de finns kvar i loggen.
De är inte testfel och motsvarande matrisplan klarar slutlig audit.

**Avvikelse P2: `--uncapped` använder fortfarande ett varianturval i seed.**
`backend/app/services/personal_planner.py:2872`, `select_seed_options`, anropar
`library_variant_shortlist` före kontrollen av `library_seed_pool_limit`.
`limit_per_base=4` är alltså fortfarande aktivt när båda taken är noll.
Reproduktionen använder den verkliga selektorfunktionen, sex nuvarande
linsschilivarianter och syntetisk kvalificeringsevidens: bara fyra behålls.
Förfiningen ser fortfarande hela sin kvalificerade pool; däremot är påståendet
att startsökningen prövar hela biblioteket fel. Matrisen kan jämföra de två
namngivna taken men kan inte ensam styrka den bredare referensbeskrivningen.

Åtgärd till Claude: låt explicit fullbiblioteksreferens även koppla bort
varianturvalet och lägg ett test med fler än fyra varianter i samma familj.
Kör om jämförelsen därefter. Detta är inte ett krav på globalt optimal
kombinationssökning: beam, näringssökning och ekosökning har fortfarande
uttryckliga budgetar.

Repro: `repro_uncapped_seed.py`; resultat: `uncapped-seed-repro.json`.

Dokumentationsförtydligande: det nya refinement-urvalet påverkar även vilka
finalister som matar parbytena. Parbytesalgoritmen och dess budget är
oförändrade, men dess kandidater behöver inte vara det. Joint-proposals
byggs fortfarande från `previous`, alltså hela den tidigare poolen.

## 3. Närings- och ekosökningens vinnare

Kodgranskning: kostnadsgränsen använder auktoritativa radofferter med
förpackningsavrundning, medlemsvillkor och tillämpliga raderbjudanden.
Varje rad får välja själv bland alla tillåtna butiker utan butikstak.
Det kan bara sänka eller behålla kostnaden jämfört med en genomförbar korg.
Minimera pris oberoende av verifieringsrang är också optimistiskt.
Kopplade flerradskampanjer/delade erbjudandetak stänger av gränsen via
`restriction_cost_bounds`; injicerade specialkalkylatorer använder också
ordinarie väg. Den fasta delen innehåller endast icke-varierande rader;
resterande klassgränser adderas separat. Saknad gräns ger ingen beskärning.

Näringssökningens kö, räknade kombinationer och budget behålls. Endast strikt
lägre pris ersätter `best`; därför får en gräns som är `>= best.total`
hoppas över. Likaprisvinnaren är fortsatt den först besökta kvalificerade
korgen. Gränsen är inte ett slutligt köpbeslut eller näringsgodkännande.

Ekosökningen jämför `(total, ursprungligt index)`. Ett särskilt prov tvingade
den nya lägsta-gränsordningen att besöka andra delmängder först: gränserna
var 20/21/22 kr men flera verkliga korgar kostade 30 kr med butikstak 1.
Den ursprungliga första delmängden vann fortfarande: exakt samma korg,
30 kr, 100 % eko och samma kontroller. Se `probe_ecological_tie.py` och
`ecological-tie.json`. De befintliga likapris-, paket-, kampanj- och
butikstakstesterna passerade också i fullsviten.

**Bedömning: godkänt för de åtta begärda jämförelserna och granskade gräns-/likaprisfallen.**

| Stad | Profil | Kandidat och referens: samma semantiska SHA-256 (prefix) |
| --- | --- | --- |
| lund | protein40 | `a8818669069c9a4f` |
| lund | all-macros | `f7a88c18677d7d66` |
| lund | organic-share | `f5ed145e94e677f8` |
| lund | distribution | `3c89adb5b68bdcdd` |
| malmo | protein40 | `acb93f04e83f84ab` |
| malmo | all-macros | `c04e077c9543b09f` |
| malmo | organic-share | `9b832c119e6ae202` |
| malmo | distribution | `cd34685afa912cb0` |

Referensen behåller kandidatens recept, äggpolicy, fakta och tak men använder
de två sökmetoderna och BasketOptimizer före prestandaändringen (`7feffcf`).
Den är en dokumenterad sammansatt referens, inte hela den gamla releasen.
Hashen omfattar fullständiga receptobjekt, inköpskorg, näringskontroller,
kassaudit och allokeringar; diagnostiska tider ingår inte.
Detta isolerar optimeringen från avsiktliga innehållsändringar. Varje arm har
egen cachekatalog och identiska frysta indata; den riktiga matrisens
`--baseline` kräver exakt `semantic_sha256`. De återställda metoderna och hela referensens BasketOptimizer är dessutom
AST-jämförda med `7feffcf`; resten av planerarmodulen är AST-identisk med
kandidaten. Referensfilerna SHA-256-verifierades mellan lokal miljö och server.
CLI:s vanliga `method_signature` beskriver det monterade backendträdet,
inte importöverskuggningen; referensens egna filhashar ligger därför i ett
separat manifest. De två armarna delar aldrig cachekatalog.
Lokala parallella testtider används inte som serverprestanda.

## 4. Faktalås och integritet

SQL-läsningen, stabil nyckelberäkning och hashning av varje distinkt råfil
sker utanför `_LOCK`. `_CACHE` och `_KEY_LOCKS` läses/ändras under `_LOCK`.
Projektionen sker under ett separat nyckellås, utanför det globala låset.
Råkällornas hash kontrolleras även vid cacheträff; projektionen gör dessutom
en andra hashkontroll efter läsning. Identitets- och scopevillkoren är kvar.
Ordinarie tester för korruption med bevarade filattribut passerar.

| Arbete i `_load_retained_catalog_facts` / `_project_facts` | Hållet Python-lås |
| --- | --- |
| SQLite-anslutning/lästransaktion, nyckelberäkning och första filhashning | Inget `_LOCK` eller nyckellås; SQLite har sin vanliga lästransaktion. |
| Första cachekontroll och registrering av nyckellås, rad 778–781 | `_LOCK`, kort sektion. |
| Väntan på samma nyckel, rad 783 | Endast nyckellåset väntas in; `_LOCK` är släppt. |
| Andra cachekontroll, rad 784–786 | Nyckellåset och kortvarigt `_LOCK`. |
| Diskcache/projektion/andra filhashning, rad 787 och 794–847 | Nyckellåset; inte `_LOCK`. |
| Publicering/eviktering i `_CACHE`, rad 849 ff. | Nyckellåset och kortvarigt `_LOCK`. |
| Borttagning ur `_KEY_LOCKS`, rad 789–791 | `_LOCK`; det egna `with key_lock` har avslutats. |

SQL:s läsning och filhashning görs fortfarande per anrop. Flytten ur det
globala låset gör inte detta arbete gratis och tar inte bort all möjlig
I/O- eller CPU-konkurrens. Samma nyckel kan avsiktligt vänta på nyckellåset;
docstringens generella löfte att användaren som värst upprepar arbete bör
preciseras till skillnaden mellan samma och olika nycklar.

**Avvikelse P2: ett icke-cachebart projektionsresultat kan sparas på disk.**
`backend/app/services/personal_source_facts.py:842`: `_project_facts` anropar `read_prepared(..., compute_projection)`. Om en
läsning misslyckas efter den första hashningen sätter `project()` sin lokala
cacheflagga till false, men returnerar ändå ett partiellt resultat.
`meal_prepared_artifacts.prepared` skriver detta innan flaggan kontrolleras.
Minnescachen undviks första gången, men nästa lyckade integritetskontroll
kan återläsa det partiella diskresultatet och sedan minnescacha det.

Reproduktion med ett övergående OSError, oförändrad råfil och ny cache:
första resultatet 0 rader, 0 minnesposter, 1 diskpost; nästa försök fortfarande
0 rader; med ny cache 1 korrekt rad. Samma fel reproducerades på `d09eaf4`.
Det är alltså ett kvarstående basfel, inte introducerat av låsuppdelningen,
men granskningskravet ”icke-cachebart resultat aldrig lagras” är inte uppfyllt.
Det kan ge bestående falska dataluckor och begränsa produkturvalet tills
cachen byts eller invalidieras.

Åtgärd till Claude: låt compute-protokollet uttryckligen avstå från lagring
vid projektionsfel; invalidiera eventuella äldre partiella artefakter och
testa både läsfel och ändrad fil mellan de två hashningarna.
Repro: `repro_facts_cache.py`; resultat: `facts-cache-repro.json`.

Den kända samtidighetsluckan är verklig: en väntare kan hålla en referens
till det gamla nyckellåset när den föregående ägaren tar bort det ur registret.
En tredje tråd får då ett nytt lås. Vid lyckad cachefyllnad räddar den andra
cachekontrollen normalt situationen; vid icke-cachebara resultat/eviktering
kan samma nyckel ändå projiceras parallellt. Det ändrar inte pris- eller
identitetsreglerna, men kan dubblera CPU/minne. Acceptabel som redovisad
tillfällig prestandabegränsning, inte som ett löfte om single-flight.
En räknad låslivslängd som omfattar både ägare och väntare är en möjlig fix.

Verkligt överlappsprov på servern: Lund-anropet kom när Malmös
bakgrundstråd nådde faktaladdningen. Största globala låsväntan för
användartråden var **0.000020 s**, summerat 0.000040 s
över 4 låstagningar, mot tidigare 14,9 s. Användarjobbet tog
76.91 s: fakta 35.61 s och planner
41.30 s. Planens audit är godkänd. Detta bekräftar
att den tidigare långa globala blockeringen är borta i detta överlapp;
det mäter inte frekvensen eller all möjlig samtidighet. 5 GiB RAM användes
för två laddade stadsartefakter. Se `cross-city-overlap.json`.

**Bedömning: låsuppdelning och bevarad hashkontroll godkända; avvikelse i
kravet att ett icke-cachebart resultat aldrig persisteras.**

## 5. Recept, vatten, ägg och author

28 nya versioner verifierade mot föregående versioner. Ingredienser och
produktkrav är oförändrade. Fältskillnaderna motsvarar handoff: metadata,
aktiv tid, de två etiketterna, pastanamnet, vattensteg samt nödvändiga
versions-/provenienshashar. Alla 16 återställningar bevarar ursprungliga
säkerhetskällor, förvaringsråd, metod-/skalningsnoter, timing_basis och
active_minutes. Åtta priority-ändringar återställer också ursprunglig metadata.
Samtliga 11 vattensteg kontrollerades vid 1/2/4/8/12 portioner: 55/55 rätt.
Se `recipe-version-audit.json`, `recipe-audit-summary.json`, `water-scaling.json`.

Ägg: 98 räknade skaläggspack i Lund och 184 i Malmö. Alla 234 utfärdade
standardviktsbevis motsvarar antal × 51 g (M, M/L) eller × 60 g (L, L/XL).
Small/Small-Medium och okänd klass får inget sådant bevis. XL-enbart
kontrolleras i regeltesterna; inget sådant utfärdat bevis hittades i inventeringen.
Alla äggnamn, även andra äggprodukter och köksredskap, finns i inventeringsfilen.

Sex erkända pack per stad saknar ändå standardviktsbevis. I Lund: fyra
erbjudandepack utan ProductFacts, ett M/L-pack med `nutrition_basis`-konflikt
och Brunchägg L/XL vars legitima ingredienstext ”ÄGG från frigående höns
inomhus” inte passerar den snäva ordlistan. Malmö: sex pack utan fakta.
Det är konservativa dataluckor, inte felräknade vikter. Brunchägg är en
konkret täckningsförbättring till Claude; den ska inte lösas genom att
generellt koppla bort ingrediens-/konfliktkontrollerna.

CLI `author`: exemplet och ett eget recept med parallella steg, nytt ID och
200 ml processvatten valideras utan varningar/avslag. Båda: 11 räknade
ingredienser, 31 min aktivt, 15 min väntan, totalt 46 min. Eget vatten skalar
rätt till 100/200/400/800/1200 ml vid 1/2/4/8/12 portioner. Ingen import till
den riktiga bibliotekskatalogen gjordes av dessa granskningsrecept.

**Avvikelse P2: två vattenmängder i samma author-steg kan skalas fel.**
`backend/app/services/recipe_authoring.py:130–131` registrerar båda tokensträngarna, men `backend/app/services/recipe_library.py:201–207` (`_scaled`)
ersätter dem efter varandra i redan ändrad text. ”100 ml vatten … 200 ml
vatten” för två portioner blir ”400 ml … 400 ml” för fyra, i stället för
200/400. Paketvalideringen accepterar receptet. Även decimaler läses fel: 125,5 ml registreras som token ”5 ml” och
blir 125,10 ml vid dubblering, i stället för 251 ml. Se samma repro med
`--decimal` och `author-water-decimal-repro.json`. De 11 utfärdade enkla
vattenstegen är korrekta; author-funktionen är alltså inte generellt färdig.
Åtgärd: ersätt ursprungliga mängdpositioner i ett enda pass, med avgränsade
tal, och testa flera mängder samt tal som ingår i andra mängdsträngar.
Repro: `repro_author_water.py`; resultat: `author-water-repro.json`.

Enreceptskvalificering av 28 versioner och de två author-recepten:

- lund: 28/30 PASS i exakt inköpsläge, högst två butiker; 2 blockerade. De 28 versionerna: 28/28 PASS. Author: 0/2 PASS.
- malmo: 9/30 PASS i exakt inköpsläge, högst två butiker; 21 blockerade. De 28 versionerna: 9/28 PASS. Author: 0/2 PASS.

De två author-recepten är avsiktligt inte registrerade i biblioteket.
Deras `SEARCH_BLOCKED` i båda städerna är därför den förväntade publiceringsspärren, inte ett recept- eller prisfel. CLI-validering innebär inte godkänd publicering eller styrkt köpbarhet.
Övriga blockeringar gäller kvalificering i exakt inköpsläge och datatäckning; inga sådana testfall har hoppats över.
Fullständiga orsaker och recept-ID finns i respektive `*-recipe-qualification.json`.

Blockerade i lund:

| Recept | Kod / orsak |
| --- | --- |
| Kycklingsouvlaki med ugnspotatis, tzatziki och tomatsallad (`smako-greek-chicken-souvlaki-potatoes:1.0.0:base`) | SEARCH_BLOCKED: Receptversionen eller mängden saknar godkänd innehållsgranskning. |
| Spiskumminkyckling med ugnspotatis, gurkyoghurt och tomatsallad (`smako-review-cumin-chicken-20261018:1.0.0:base`) | SEARCH_BLOCKED: Receptversionen eller mängden saknar godkänd innehållsgranskning. |

Blockerade i malmo:

| Recept | Kod / orsak |
| --- | --- |
| Kikärtsmasala med rostad potatis och gurkraita (`smako-indian-chana-cauliflower:2.2.0:in01-base`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Vit bönmasala med rostad potatis och gurkraita (`smako-indian-chana-cauliflower:2.2.0:in01-vita-bonor`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Tostadas med svarta bönor, majs och limekål (`smako-mexican-bean-tostadas:2.2.0:base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Tostadas med vita bönor, majs och limekål (`smako-mexican-bean-tostadas:2.2.0:mx01-vita-bonor`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Rökig kycklingpanna med potatis, paprika och limekräm (`smako-mexican-smoky-potato-pan:2.2.0:base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Rökig tofupanna med potatis, paprika och limekräm (`smako-mexican-smoky-potato-pan:2.2.0:mx02-tofu`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Basilikastekt fläskfärs med vitkål och vitlöksris (`smako-thai-basil-tofu:2.3.0:th03-base`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Basilikastekt smulig tofu med vitkål och vitlöksris (`smako-thai-basil-tofu:2.3.0:th03-tofu`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Majs- och linspanna med osttäcke och limekål (`smako-mexican-lentil-chili:2.2.0:mx04-base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Majs- och färspanna med osttäcke och limekål (`smako-mexican-lentil-chili:2.2.0:mx04-fars`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Syrlig risnudelsallad med kyckling, kål och jordnötter (`smako-thai-sour-noodle-salad:2.3.0:base`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Syrlig risnudelsallad med tofu, kål och jordnötter (`smako-thai-sour-noodle-salad:2.3.0:th01-tofu`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Kokosbräserad torsk med spenat, lime och ris (`smako-thai-chicken-coconut-curry:2.3.0:th02-base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för fisk, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Kokosbräserad kyckling med spenat, lime och ris (`smako-thai-chicken-coconut-curry:2.3.0:th02-kyckling`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Rostad broccoli och tofu med ingefärsglaze och nudlar (`smako-thai-tofu-satay:2.2.0:th04-base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för limejuice, ml. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Rostad broccoli och kyckling med ingefärsglaze och nudlar (`smako-thai-tofu-satay:2.2.0:th04-kyckling`) | DATA_BLOCKED: Ingen verifierad köpbar vara för limejuice, ml. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Fiskgratäng med spenat, dill och potatismos (`smako-swedish-fish-gratin-mash:1.1.0:base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för fisk, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Aloo gobi med kikärtor och citronris (`smako-indian-aloo-gobi-chickpeas:1.1.0:base`) | DATA_BLOCKED: ingefära finns som viktvara. Välj Tillåt uppskattad vikt och kostnad under Inköpsberäkning för att pröva dessa varor. Slutbeloppet beror på faktisk vikt; övriga krav gäller fortfarande. |
| Chili sin carne med svarta bönor, morot och majs (`smako-mexican-black-bean-carrot-chili:1.1.0:base`) | DATA_BLOCKED: Ingen verifierad köpbar vara för majs, g. Kontrollera mängden, egenskaperna eller exakt produkt. |
| Kycklingsouvlaki med ugnspotatis, tzatziki och tomatsallad (`smako-greek-chicken-souvlaki-potatoes:1.0.0:base`) | SEARCH_BLOCKED: Receptversionen eller mängden saknar godkänd innehållsgranskning. |
| Spiskumminkyckling med ugnspotatis, gurkyoghurt och tomatsallad (`smako-review-cumin-chicken-20261018:1.0.0:base`) | SEARCH_BLOCKED: Receptversionen eller mängden saknar godkänd innehållsgranskning. |

**Bedömning: versionsdiffar, de 55 vattenfallen och äggvikterna godkända; avvikelse i author för flera mängder och decimaler. Redovisade dataluckor i exakt inköpsläge kvarstår; author-publiceringsspärren fungerar som avsett.**

## 6. Servermätningar

Alla 32 kall/varm-observationer gav godkänd plan. För varje profil och
stad är pris och semantisk hash identiska i alla fyra observationer.
Seed=40 i båda kolumnparen. Tider i sekunder; pris/hash gäller båda lägena.

| Stad | Profil | Tak 90 kall | Tak 90 varm | Tak 0 kall | Tak 0 varm | Pris båda, kr | Hash båda (prefix) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| lund | standard | 66.58 | 46.78 | 87.04 | 57.17 | 548.76 | `2d9bf97b3d91` |
| lund | all-macros | 165.46 | 145.42 | 181.08 | 154.16 | 813.14 | `f7a88c18677d` |
| lund | organic-share | 184.32 | 167.82 | 256.73 | 240.72 | 352.22 | `f5ed145e94e6` |
| lund | distribution | 106.84 | 86.01 | 102.65 | 85.29 | 775.86 | `3c89adb5b68b` |
| malmo | standard | 85.01 | 58.24 | 80.62 | 59.79 | 534.92 | `4fbc3f8f6847` |
| malmo | all-macros | 54.97 | 33.44 | 56.08 | 34.31 | 1012.83 | `c04e077c9543` |
| malmo | organic-share | 269.76 | 248.36 | 351.51 | 334.89 | 352.12 | `9b832c119e6a` |
| malmo | distribution | 122.65 | 102.65 | 119.33 | 104.27 | 1089.72 | `cd34685afa91` |

Artefaktåterställning, utanför tabellens tider: 14.60–29.03 s per process. Fulla tider, faktatider, planerartider, minnesmax och hashes finns i JSON.

Jämfört med föregående kandidats standardprov var Lund 73,5/54,8 s kall/varm och Malmö 78,5/58,5 s. Den äldre main-baslinjen var 130,4/117,6 respektive 155,5/135,0 s. Jämför detta med tabellen ovan, med reservation för ändrat underlag/innehåll.

Tidigare Lund-specialprov var cirka 261 s för makro och 278 s för eko **utan faktaläsning**. Den nya tabellen inkluderar fakta; JSON-fältet `plan_seconds` möjliggör motsvarande avgränsning. Flera specialprov är snabbare, men detta är inte en isolerad före/efter-procentmätning.

Lunds standardpris har ökat från 535,06 till 548,76 kr mellan granskningarna. Samma 548,76 kr erhålls utan seed- och förfiningstak. Det är ingen observerad takregression; jämförelsen isolerar inte prisunderlag och innehållsändringar.

**Bedömning: mätningen genomförd, prestandamålet inte godkänt.** De långa specialjobben och standard över 30 s gör att tidigare P1 inför bred lansering kvarstår. En enda kall/varm observation per läge ger ingen produktions-p95 eller kökapacitetsgaranti.

Planeringsläge `estimated`, högst två butiker och näringsestimat tillåtna.
Standard: fem middagar × fyra portioner. Makro: samma antal, protein 40–90 g,
kolhydrater 10–130 g, fett 1–60 g och högst 1 000 kcal per portion.
Eko: tre middagar × fyra portioner och minst 20 % ekologisk inköpskostnad.
Fördelning: fem middagar × fyra portioner, en kyckling, en fisk, en kött,
två vegetariska och minst 25 g protein per portion. Fulla requests finns i JSON.

Metod: samma befintliga serverimage som vid förra granskningen,
`sha256:93bbfd2ebe3764cddd559422ed1fce53197359b6f0aabde50619dfc6a81cd8f7`,
med kandidatens backend monterad läsbart i separat container. Samtliga 19
ändrade backendfiler SHA-256-verifierades mot arbetskopian; se
`server-source-verification.json`. En mätcontainer
åt gången, 2 CPU, 3 GiB RAM, inget nätverk, inga privata användartillstånd.
Serverns publika katalogdatabas och råkällor är läsbara; produktionsplaner
och miljöfiler är inte monterade. Ny cache per profil/tak, ny planerare per
iteration. Första anropet är processkallt, andra processvarmt. OS-filcache
töms inte. Tiden omfattar faktaladdning plus planner.create och dess slutliga
audit; återställning av prisartefakten redovisas separat. HTTP-kö, admission,
nätverk och persistering av riktiga planer är inte mätta. Förberedande
exportförsök behövde rättade skrivrättigheter och stadsvisa 5 GiB-containrar;
`prepare.log` bevarar försöksfelet. Dessa exportförsök ingår inte i tidsserien.

Fryst klocka: `2026-10-18T05:12:49.467392+00:00`.
Lund: 43 821 produkter, 42 357 faktaposter.
Malmö: 88 340 produkter, 70 916 faktaposter.
Artefakterna var aktiva när de frystes. De skiljer från föregående rapports
2026-10-17-underlag; recept/äggpolicy har också ändrats. Jämförelsen med
förra rapportens siffror är därför en observation, inte en isolerad mätning
av enbart kodens hastighetsvinst. Default mot refinement=0 här är däremot
parat på samma indata.

## Drift och grenar

`PRICE_UNIVERSE_PREWARM_ENABLED=false` är fortfarande aktivt i appcontainern.
Ingen ny driftändring eller aktivering gjordes. Appens image är oförändrad.
Slutkontroll 2026-10-18 07:10:23 UTC: HTTP 200, `ready`, samma image och
build `joint-week-refinement-app-e041451`. Både serverns miljöfil och den
körande containern har flaggan `false`. Inga granskningscontainrar kör längre.
43 egna, tillfälliga cachekataloger (151,9 MB) togs bort efter sparad evidens;
rapporter, skript, syntetiska planer och frysta indata är bevarade.
Se `final-runtime-status-public.json` och `cache-cleanup-receipt.json`.

Serverstatus vid granskningens start visade ett separat driftsproblem: senaste backupen misslyckades
med `InsufficientStorageError`; cirka 6,69 GB ledigt mot uppskattat behov
13,99 GB. Granskningen raderade inga andra data och kopierade ingen databas.
Frysta prisunderlag använder hårdlänkar på servern. Frigör/utöka utrymme och
verifiera nästa backup som en separat driftåtgärd. Slutkontrollen visar
fortfarande `failed/InsufficientStorageError`, senast 07:00 UTC: 6,33 GB
ledigt mot 13,99 GB uppskattat behov. Felet fanns redan före granskningen.

Vid fetch fanns ingen annan gren med senare toppcommit än tidigare main
2026-10-17; den nya reviewgrenen låg 13 commits före. Äldre divergerande
grenar finns fortfarande, bland annat recipe-integration (45 egna commits),
recipe-library (13), recipe-ui (22) och recipe-quote-reuse (12). De har
toppcommits från 2026-10-03 och är inte nyare releaser. De och deras
worktrees är bevarade; se `branch-ahead-inventory.json` för exakt ahead/behind
mot dåvarande main `d09eaf4`.

Avvikande Git-historik betyder inte automatiskt att arbetet saknas på main.
`git cherry d09eaf4 <gren>` visar följande för icke-mergecommits:

| Äldre gren | Patchmotsvarighet redan på main | Ingen identisk patch hittad |
| --- | ---: | ---: |
| `feature/recipe-integration` | 43 | 2 |
| `feature/recipe-library` | 4 | 8 |
| `feature/recipe-ui` | 22 | 0 |
| `perf/recipe-quote-reuse` | 11 | 1 |

Patch-id avgör inte om återstående ändringar har införlivats via squash eller
manuell integration. Ingen av dessa grenar integrerades eller togs bort i
uppdraget. `older-branch-patch-equivalence.json` bevarar jämförelsen.

## Underlag och reproduktion

Kör från `D:\Projects\Smako` med Python 3.12 och `PYTHONPATH=backend;.`.
Sätt `PYTHON_DOTENV_DISABLED=1`. Testdata innehåller endast publika
pris-/produktuppgifter och syntetiska planer, inga miljöfiler eller databaser.

`run_functional.py` kör den verkliga acceptansmatrisen med `--uncapped`,
`--uncapped-reference` och `--baseline`, plus det begärda parametriserade
taktestet. `reference-manifest.json` beskriver den isolerade optimeringsreferensen.
Serverns `orchestrate.py`, `probe.py`, `prepare.py` och överlappsprov ingår.
Fullständiga hashes finns i JSON-underlaget; tabeller kan visa förkortningar.

## Rekommenderad nästa åtgärd för Claude

1. Rätta fullbiblioteksreferensen och kör om båda städernas sju profiler. Om
   default blir dyrare, höj aktuellt tak och behåll testet och den fallerande evidensen.
2. Förhindra diskpersistens av icke-cachebara faktaprojektioner och lägg
   regression för övergående läsfel samt filbyte mellan hashkontrollerna.
3. Gör vattenersättning i ett enda pass över ursprunglig text och stöd eller
   avvisa decimaler uttryckligen. Behåll testerna för de redan rätta 11 stegen.
4. Fortsätt minska verkligt sökarbete för långsamma profiler med identisk
   vinnare; ta inte bort audit, integritetskontroller eller produktkrav.
5. Separat driftarbete: återställ fungerande backup och bygg/verifiera en
   reproducerbar releaseimage före någon kodaktivering. Den tidigare rapportens
   live-imageavvikelser (nio appfiler och en saknad datafil) försvinner inte av
   att patchen finns på main; appens image har inte ändrats här.

Alla tre P2-reproduktionerna, referenskoden och exakta kvitton följer med i
`smako-followup-review-for-claude-20261018.zip`. Det separata publika
dataarkivet behövs för att upprepa stadsjämförelserna. Se `REPRODUCTION.md`
och arkivets manifest för sökvägar och SHA-256. Ingen aktivering ingår.
