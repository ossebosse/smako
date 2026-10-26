# Recept, veckosökning och cache, 2026-10-26

Leverans enligt [uppdraget](../CODEX-SOL-NEXT-20261026-WEEK-SEARCH.md),
från main `574aabc`, via [PR #16](https://github.com/ossebosse/smako/pull/16).
Nio receptversioner rättas och den fyllda beräkningscachen kan nu lagra nytt
underlag och ge träffar efter omstart. Opt-in-sökningen minskar faktiskt
korg-/butiksarbete. **B levererar fortfarande ingen vecka:** API svarar
`SEARCH_BLOCKED` efter **45,10 s**. Det är ett avslag, inte uppnådd veckolatens.
Inga krav har sänkts. Legacy är standard, `library_merge_generations=False`;
mainintegration aktiverar ingen beta eller produktion.

## Publicerat innehåll och produktkrav

Author → validate → diff → import publicerar följande nio ersättare och
återkallar de nio tidigare versionerna:

| Bas | Tidigare → ny version | Varianter |
| --- | --- | --- |
| `smako-thai-chicken-pineapple-skewers` | 1.0.2 → 1.0.3 | simple, standard, extended |
| `smako-thai-paneer-mango-skewers` | 1.0.2 → 1.0.3 | simple, standard, extended |
| `smako-swedish-creamed-cabbage-chickpeas` | 1.0.0 → 1.0.1 | simple, standard, extended |

Spettens hela kedja är upptining → skärning av tinade, skalfria bitar →
trädning → ugn. Den senare instruktionen om fryst frukt i varm panna är
borta. Fruktens saft behålls. Befintlig upptiningsväntan och aktiv-/totaltid
kortas inte. Omvandlaren har nu skilda, explicit valda processer för spett
och direkt upphettning. Samma mango-/ananasersättningar omfattade ytterligare
tolv aktiva varianter av fyra pann-/glasyrbaser; deras korrekta direkt-fryst-
processer är granskade och byte-/innehållshashade som oförändrade.

Rågbrödsrättens tre varianter kräver nu `pack:rye_bread`, beskriver skivat
rågbröd och har ett verkligt rostningssteg. Rågbröd tillåts; generiskt pita,
wrap, tortilla, fylld smörgås och deklaration som motsäger rågkravet avvisas.
Den bevarade katalogen innehåller 14 uttryckligen namngivna rågbrödsprodukter;
tolv har granskats mot exakt produkt-/butiks-/snapshotbundna faktarader och
klarar formregeln. De tolv saknar full ingrediensdeklaration. Produktens
uttryckliga varuklass används för brödidentitet, utan att anta rågprocent,
allergenfrihet, näring eller ekologisk status. Okända allergener godkänns inte.
De andra två produktnamnen är inte därmed kvalificerade eller uttömmande avvisade.

[Receptkvittot](week-search-and-cache-20261026/recipe-review.json) innehåller
alla gamla/nya ID:n, innehållshashar, tider och de tolv oförändrade varianterna.
[Validate](week-search-and-cache-20261026/validate.json),
[diff](week-search-and-cache-20261026/diff.json),
[import](week-search-and-cache-20261026/import.json),
[återkallelser](week-search-and-cache-20261026/revocations.json) och
[produktgranskning](week-search-and-cache-20261026/rye-source-review.json)
är separata underlag. Tidigare utfärdade bytes och planreferenser bevaras;
omkörning av ändringsskripten verifierar utfärdade hashvärden och skriver
inte om historiska författarunderlag. Fortsatt **2 462 aktiva varianter/934
baser**, 39 aktuella och sju historiska paketgenerationer. Innehållet är inte
provlagat. Den gamla individuella täckningen 733/920 har inte inventerats om;
C:s tidigare pitabrödspris 108,45 kr är ingen ny rågbrödsreferens.

## Sammanhängande opt-in-förbättring

`library_search_policy="smako-current-library-v2"` använder befintlig
`MenuOptimizer.optimize_slots` mot hela den aktuella kvalificerade poolen,
med befintlig beam 8 och högst en fallback 64. Historiska meny-/paketkohorter
och förberedande fulla sökningar med snävare inköpsscope återspelas inte i
denna väg. Legacy/V1 behåller sina kontrakt. Historik används fortfarande
för proveniens/återläsning; profilen visar också kvarvarande historisk
modellmaterialisering i `share_issued_recipe_parts`, inte historiska menyförsök.
Slutlig korgberäkning, audit, ägarscope, sparande och GET använder samma API
och prismotor. En intern 60 s-deadline omfattar även inre dyra loopar och save;
ofärdigt arbete blir `SEARCH_INCOMPLETE`, aldrig en godkänd delplan.

Rena offentliga paketofferter kan återanvändas via befintlig `PackageCostCache`.
Nyckeln binder full produkt-/prisidentitet, mängd, enhet, metod och prisdatum.
Gemensamma värden saknar användarens radnamn. Medlemsprisvägar behåller lokala
värden och kopplade kampanjer går genom befintlig gemensam checkout. Fakta binds
till kanonisk innehållsidentitet. Ett delat kostnads-/sökindex är inget återanvänt
personligt närings-, allergen- eller ekogodkännande.

Butiksgallring gäller bara oberoende checkout: en lexikografiskt tidigare
butik får ersätta en senare endast med **samma radtäckning, samma verifieringsrang
per rad och inget högre faktiskt offertpris på någon rad**. Extra täckning är
inte ett tillräckligt villkor. Kandidatprodukter behålls för närings-/ekobyten.
Kopplade kampanjer kringgår denna gallring. Begärandeägda dominansmasker och
de redan befintliga butiksmängds-/offertcacherna begränsar upprepning.

Små uttömmande orakel jämför med ogallrad checkout över flera butikstak,
paketstorlekar och slumpfrön. En liten hel meny får exakt samma bästa
gemensamma korg **20** som alla kombinationer (separata recept hade kostat 40).
Övriga fall verifierar korg 25, närings-/ekokänsligt alternativ 28, kopplad
kampanj 75 samt rang/täckningsmotexempel 3 mot en felaktig förenklings 22.
Detta är korrekthetsbevis för dessa ändrade delproblem, inte globalt optimum
för Malmö eller bevisad prisparitet för alla personliga val.

## Fylld cache, versionsbyte och omstart

Den explicita koordinatorn låser och tilldelar en generation ett nytt CAS-token.
En sen äldre beräkning får returnera sitt korrekta minnesvärde men kan inte
skriva/gallra/markera den nyare generationen redo. Gallring omfattar bara
cacheformatets egna hashfilnamn, schema och nycklar inom exakt cacherot.
Källor, receptpaket och sparade planer ligger utanför denna retention.
Aktuella begärda poster skyddas; okända filer lämnas. Avbrott, sen skrivare,
fylld katalog, bytegräns, låskonkurrens och misslyckad ersättning har små
regressioner. Fel ger korrekt omberäkning utan falsk beredskapsmarkering.

Kapaciteten höjs inte: content 4 096 poster, övriga sorter åtta generationer
vardera, 32 MiB per sort. Offertcache och produktfingeravtrycksreferenser är
också begränsade. Cachefilskrivningar använder flush/close och atomisk replace
med validering vid återläsning; ingen ny garanti om överlevnad vid strömavbrott.

Den första verkliga förberedelsen på `43a008f` stoppades vid 120 s med
906 nya contentposter och `ready=false`. Alla 120,0053 s debiterades.
En separat mätning av fyra egna små cachefiler mätte **1,9872 s i fsync** och
0,0023 s i replace. Den nya per-post-fsyncen togs därför bort för just
återbyggbar cache, med bibehållen atomisk publicering/hashkontroll.
[Första stoppet](week-search-and-cache-20261026/preparation-first-stop.json)
och [I/O-diagnosen](week-search-and-cache-20261026/write-io-profile.json) bevaras.

På korrigerad kod `90fa724` och samma redan fyllda katalog:

| Mätning | Resultat |
| --- | --- |
| [Första färdiga förberedelse](week-search-and-cache-20261026/preparation-current.json) | 95,9679 s, wrapper 97,1587 s; ready, noll persistensfel |
| Skrivning/retention | 2 464 skrivningar, 2 461 äldre poster/1 561 653 byte gallrade, en egen avbruten temporärfil borttagen |
| Träffar vid denna förberedelse | 2 462, från exakt aktuell innehållsvy till portionsvyn |
| Ny B-process, återläsning | 4 926 diskcacheträffar, noll missar/skrivningar, ready |
| B:s gemensamma förberedelse | 19,1285 s efter källaddning 55,9603 s |
| Faktisk total disklagring, inklusive äldre kvarvarande delar/lås/metadata | 3 430 745 byte |
| Sorter | content 4 096; declarations 5; ingredient-search 5 |
| Högsta job-commit: färdig förberedelse/B | 1 245 057 024 / 1 577 111 552 byte (1,16 / 1,47 GiB) |

Full katalog tömdes inte inför provet. Nytt giltigt underlag är faktiskt
lagrat och återläst efter omstart. `declarations=0` är noll identifierade
deklarationsklasser i detta underlag, inte godkända okända allergener.
269 ingredienssökningar förbereds. B:s hela process inklusive laddning,
förberedelse, registrering och avslag tog 125,8943 s. Detta får inte beskrivas
som 45 s från en första installation. Endast en verklig matchbar pris-/faktaversion
finns; verklig veckouppdateringslatens och minne med två fulla prisversioner
överlappande är fortfarande omätta. De observerade jobben ligger under
minnesmålet 2,5 GiB och det hårda taket 3 GiB.

## Oförändrat B och kvarstående hinder

[B-kvittot](week-search-and-cache-20261026/B.json) använder byteidentiskt
normaliserat request mot föregående B: fem middagar × fyra portioner,
grekiskt/italienskt, minst 35 g protein, tre kyckling/två vegetariska,
högst tre samma huvudprotein, **52 tillåtna butikskontexter**, inköpstak två,
estimated och övriga tidigare standarder. Biblioteket innehåller de nio nya
Thai-/Sverigeversionerna; B:s råa/kvalificerade antal och första avslag är identiska.
Sökpolicy/metod skiljer sig uttryckligen från legacy-baslinjen.
**Rättelse av tidigare redovisning:** uppdraget och föregående rapport säger
55, men det faktiskt sparade `requests.json` och båda normaliserade B-kvittona
innehåller exakt 52 `allowed_store_ids`. Inga ID:n har lagts till eller tagits
bort i detta prov. Det är således ingen verifiering av ett 55-butiksanrop.

| Observerat arbete | Föregående B, partiellt vid cirka 60 s | Nytt B, slutligt avslag |
| --- | --- | --- |
| Råa → kvalificerade recept | 681 → 29 | 681 → 29 |
| Första avslag | policy 205, produkt 414, näringsgräns 33 | samma |
| Korgberäkningar | 2 356 | 1 555 |
| Butikskombinationer | 1 566 881 | 93 269 |
| Undvikna delmängder genom ny dominans | inte infört | 868 132 |
| Bortgallrade butikskontexter, summerat över korgar | inte infört | 36 748 |
| Paketberäkningar / delade paketträffar | inte separat räknat | 38 136 / 2 263 |
| Nytt B: kvalificering / veckosökning | — | 22,4117 / 14,7406 s |
| Fullständigt kontrollerad, sparad och återläst meny | nej vid 75 s | nej; HTTP 422 SEARCH_BLOCKED vid 45,0983 s |

Detta visar minskat faktiskt arbete vid samma kandidatfilter, men olika
slututslag och observationslängd gör det inte till en jämförelse av lyckad
användarlatens. Beam 8 och fallback 64 når båda djup fem utan godkänd meny;
0 fullständiga menyer prissätts där. Ingen vinnare, slutlig audit, sparad
lista eller totalsumma finns. Giltighets-/prisparitet för en verklig B-vinnare
är därför inte verifierad. Ingen ny dyr legacy-baslinje kördes.

Ett ytterligare budgeterat [strukturprov](week-search-and-cache-20261026/B-frontier-review.json)
återidentifierade exakt de 29 observerade singletonkvalificerade recepten
mot aktuella utfärdade recept: 25 kyckling och fyra vegetariska. Alla
`C(25,3) × C(4,2) = 13 800` kombinationer kontrollerades med befintliga
slutliga strukturpredikat: 2 160 hade upprepad bas och resterande 11 640
avvisades av kulinarisk variation. Ingen strukturell fullkombination fanns
i denna kvalificerade pool. Det normaliserade anropet har
**`max_same_primary_ingredient_meals=2`**, och den upplösta balanced-policyn
har samma tak. Samtidigt kräver B uttryckligen tre kyckling och tillåter
tre samma huvudprotein. Det är ett konkret policy-/modellhinder att reda ut
före ytterligare veckoprestandaprov. Provet bevisar inte omöjlighet för alla
tänkbara produkt-/receptdomäner och är ingen ny inköps-/näringsaudit.

B är inte ett lyckat ≤60 s-fall; villkoret för A och verkligt browserprov
av veckan uppfylldes därför inte. Inga sådana prov, ändrade profiler eller
identiska B-omtag gjordes. Endags-F:s tidigare browserresultat är fortsatt
historisk endagsevidens. **Faktisk klick→färdig veckolista är ännu overifierad.**

Nästa steg är att klarlägga och konsekvent redovisa förhållandet mellan
uttrycklig måltids-/huvudproteinfördelning och det separata variationspresetet,
utan tyst kravlättnad. Därefter behövs en giltig aktuell veckovinnare,
slutlig exakt checkout/save/GET och browserlatens samt matchad prisjämförelse.
Kvarvarande historisk materialisering och kompletterande samma-meny-jämförelser
efter en vinnare behöver också tidsmätas. Full V2, globalt optimum, större
UI-butikstak 1..N, godtycklig samtidighet och veckouppdatering är inte färdiga.
Limejuice, ingefärans ätliga mängdbasis och övriga källuckor är kvarstående
produkt-/faktabehov; ingen bred ny insamling har gjorts.

## Verifiering och samma budget

434 riktade innehållsprov passerade efter publiceringen. Därefter passerade
233 bredare kärnregressioner; senaste cache-/fallbackkörningen gav 31 PASS.
Slutlig samlad körning av de ändrade innehålls-, policy-, orakel- och
cacheproven gav **78 PASS**. Dessa körningar överlappar och summeras inte.
Ruff och compileall passerar på ändrade Pythonfiler. Ordinarie CI på
`43a008f` och den uppmätta runtimekoden `90fa724` är grön;
mainintegration kräver dessutom grön ordinarie CI på PR:ens slutliga
huvud inklusive browserproven, enligt DEVELOPMENT.

[Maskinsammanställningen](week-search-and-cache-20261026/delivery.json)
anger logg-/råunderlagshashar och källidentiteter. Det fulla B-kvittot är
25 874 429 byte och har bevarats lokalt med SHA. Det publicerade B-kvittot
utelämnar stora detaljlistor och behåller utfall/räknare samt råunderlagets SHA.
Ingen konto-/sessionidentitet eller hemlighet publiceras.

Samma [budgetjournal](recipe-integration-800-20261025/budget.json):
**4 226,3128 s använda, 2 973,6872 s kvar = 49,56 minuter av totalt 120.**
Denna etapp debiterar 370,8983 s, inklusive den misslyckade 120 s-förberedelsen,
I/O-diagnos, rågbrödsgranskning, lyckad förberedelse, B:s hela process och
strukturdiagnos. Två CPU och hårt 3 GiB commit på det faktiska Windows-
interpreterjobbet; ingen Linux-/cgroup- eller p95-latens påstås. Inga nya
budgetar, stor matris, nattlig fortsättning eller kvarlämnade mätarbetare.
Drift, scheduler, produktionsprofiler och betaaktivering är orörda.
