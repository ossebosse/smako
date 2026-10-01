> Aktuell produktion: [genomförd aktivering 1–2 oktober](ACTIVATION-LIVE-20261001.md).
> Nedanstående svit- och releasebevis är tidigare körningar, inte omkörda under aktiveringen.

# Lund: verifierad kandidat och kvarstående aktiveringsspärrar

**Senaste status:** [TRANSITION.md](TRANSITION.md) och
[TRANSITION-EVIDENCE.json](TRANSITION-EVIDENCE.json) ersätter nedanstående
öppna kö-/återgångspunkter. Ny runtime `08c1374` innehåller köbevarande och
begränsad autentiserad läsdrift, med nya reproducerade paket, 168 fokustester
och isolerade Docker/HTTP-/omstartsprov. bdc9-livebeviset och tidigare
fullsvit/browserresultat nedan är bevarade tidigare bevis, inte nya körningar.
Enda aktuella driftordningen finns i [ACTIVATION.md](ACTIVATION.md).

## Bevarat ursprungligt releaseunderlag

**Senaste driftkomplettering:** [OPERATIONS.md](OPERATIONS.md), med
[Docker/HTTP-bevis](OPS-EVIDENCE.json) och [Windows-replay](WINDOWS-EVIDENCE.json).
Faktisk produktionsbild har nu provats: äldre GET tappar planfält och ger
500 för öppet kampanjval; originalpolicyn kan inte tömma den gamla kön med
lyckad publicering. **Obevakad S4U-livehämtning/leverans är nu PASS** för
operatörens körning 20261001T074423Z; se [S4U-LIVE.md](S4U-LIVE.md).
Det nya serving-manifestet har 44 066 poster; det ersätter inte bevisen
från äldre profil-, drift- eller förkontrollmanifest.
Ny bild återläser alla nya planer identiskt. Följande
ordinarie svitresultat är tidigare releasebevis, inte nya omkörningar.

**Status 2026-09-30:** implementerad och isolerat verifierad kandidat, inte
produktionsaktiverad. Runtime-paketens gemensamma källcommit är
`bdc9f7df417084641d0a712e3dad188dad1ad7d4` på
`release/lund-relay-20260929`. Dokumentationscommit kan ligga senare på samma
gren; `scripts/build_release.py --commit bdc9f7df4170` läser endast Git-blobbar
från den angivna commiten. Konsolideringstaggen pekar fortsatt på
`b9dd50d2ee77f4316559dfcfa5a10cbadb7e77fc`.

| Leverabel | Identifierare | SHA-256 |
| --- | --- | --- |
| Server-ZIP, 625 filer, 2 280 006 byte | `D:\Smako-release-work\packages-bdc9\smako-server-bdc9f7df4170.zip` | `9b377bf074109b8bcc5c67c763a4111160863d96050ac4725d2f30774556efca` |
| Windows-relä-ZIP, 625 filer, 2 280 011 byte | `D:\Smako-release-work\packages-bdc9\smako-windows-relay-bdc9f7df4170.zip` | `299ff34ecb7b5976e317afeef54719c9286d0ecd64c2807cee58533945de57d7` |
| Serverbild byggd från uppackad, hashverifierad server-ZIP | `smako-repo-lund:bdc9f7df4170-zip` | `sha256:2f81344208e05cbc57d16fa74a73c97b26bc729859936ca5d96ab150579fe221` |

Paket byggda oberoende i arbetsroten och ren klon fick byteidentiska hashvärden.
Bildens OCI-revision är den fullständiga runtime-commiten. Kontroll utan nät
stämde av 618 runtimefilers SHA-256, `pip check` och offline-uppstart av
Chromium. Compose-kontrollen band `app`, `migrate` och `scheduler` till samma
bild-ID utan lokalt bygge; collector/refresh ingår i denna serverbild. Relä-ZIP
installerades **endast som kandidat** under
`D:\smako-local-relay\releases\bdc9f7df4170`: 624 paketfiler verifierades,
Python 3.12.10 och `pip check` passerade. Konfiguration/tillstånd ligger
separat. Den aktiva Windows-uppgiften pekar fortfarande på den gamla
datumkatalogen.

## Utgångspunkt, repo och testsvit

Utgången `master` var ren och matchade konsolideringsrapport/tagg. Befintliga
v5-adaptrar för PurchaseTerms, Coops källa/version, kommunval, gemensam
köpplanering, näring/beredning och sökindex behölls. Äkta historiska
Lidl-fixturer återställdes med verifierat hashmanifest från
`D:\Smako-backups\consolidation-20260929`; alla **16 Lidl-prov** passerade.
Den rena klonen återställde 887 stora testfiler inklusive råfiler för
produkt-/näringskoppling. Reporotens tidigare reläkod inventerades längs 213
AST-importberoenden: samtliga fanns redan i Git, 78 var nyare än den gamla
datumkopian. Tillagda delar är reproducerbar paketering, start/installation,
konfigurations- och uppgiftsmallar, låsta beroenden och riktade reläprov.
Ingen separat manuellt underhållen reläkopia eller separat repo skapades.
Spårade sökvägar/innehåll granskades för hemligheter och drifttillstånd;
lokala token, profiler, köer och loggar är utanför Git.

De fem i konsolideringen rapporterade felen återskapades först som **5 fel,
35 godkända** i fokuserad körning. Efter rättning gav samma urval **40
godkända**:

| Test-ID | Före → efter och grundorsak |
| --- | --- |
| `backend/tests/test_coop_physical_pipeline.py::test_real_own_universe_checkout_and_audit[3839-44]` | 44 förväntade rader mot 93 faktiska; äldre statisk kardinalitet ignorerade kvalificerade källrader. Källbelagd förväntan rättad; PASS. |
| `backend/tests/test_coop_physical_pipeline.py::test_real_own_universe_checkout_and_audit[3815-77]` | 77 mot 246 av samma skäl; PASS utan sänkt kvalificeringskrav. |
| `grocery_data/tests/test_coop_municipal_contract.py::test_actual_second_municipality_pdf_bound_to_store_not_shared_prices` | 10 mot 18 kvalificerade och 39 fel-/karantänrader; verkligt andra kommun-PDF-underlag saknades i äldre antagande. Butiksbindning och karantän bevarade; PASS. |
| `grocery_data/tests/test_coop_municipality.py::test_real_stora_age_conditions_stay_in_quarantine_not_global_failure` | 77 mot 384 kvalificerade och 156 karantänrader, däribland 23 åldersvillkor; förväntan uppdaterad till faktisk autentisk källa, åldersrader fortsatt spärrade; PASS. |
| `backend/tests/test_benchmark_diversity_modes.py::test_mock_diversity_benchmark_uses_one_snapshot_for_all_modes` | Äldre benchmark anropade ny receptgenerator utan giltiga recept; benchmarken fäster uttryckligen `recipe_version=legacy` och verifierar samma snapshot/version; PASS. |

Ren klon på föregående runtime-commit `a7fb854` gav **3446 godkända, 23
varningar** i ordinarie Windows-svit; Linux/Docker gav **3445 godkända, 1
plattformsskip, 23 varningar**. Slutcommiten `bdc9f7d` lade till en snäv
Willys-schemaöversyn för faktiskt observerad `energyDeclaration.image`
sträng→null; nio nya tester, berörda parser-/schemafall **38 godkända**.
Slutcommitens uppdelade rena Windows-svit: `grocery_data/tests` **1649
godkända**; första `backend/tests` **1805 godkända, 1 tidskänsligt fel** när
två `/health`-/`/ready`-anrop tog 0,221 s mot gräns 0,200 s under samtidiga
tunga prov. Samma test passerade direkt vid isolerad omkörning, utan
kravändring. Hela `backend/tests` kördes därefter om ostört med **1806
godkända, 0 fel**. Slutcommitens rena, uppdelade nämnare är alltså **3455
godkända, 0 fel, 0 skip**. En fullskalig slutkörning på C: gav tio SQLite-/diskutrymmesfel
vid cirka 280 MB ledigt; alla tio passerade på D:. En andra full körning på D:
avbröts vid 91 % utan pytest-summering. Dessa körningar redovisas som
infrastruktur-/ofullständiga och får inte räknas som full PASS. Hela
Linux-sviten på just `bdc9f7d` kördes inte om; dess schemaändring täcks av
Windows-fokustest, paketbildens hashkontroll och autentisk import genom den
slutliga Dockerbilden.

Frontendens 30 tester, `check` och bygge passerade i ren klon efter
runtime-commiten. Ruff, `compileall` och `pip check` passerade för berörda
Python-delar. Slutcommitens rena browserprov körde två flöden i Chromium och
två i WebKit: exact utan medlemskap/högst två butiker samt estimated med
Willys Plus/Lidl Plus och en butik; alla fyra gav rätt form-JSON och inga
sidfel. Den tidigare bredare UI-hjälparen hade 18 kontroller per browser före
den sista, enbart serverbaserade schemaöversynen. Browserprovet kontrollerade UI-formulärens JSON;
planpris, köp och sparning kördes separat mot verklig paketerad HTTP-app.

## Isolerad källkedja och faktiskt serving-innehåll

Privat serverrot `/var/tmp/smako-repo-release-20260929/data` innehöll båda
SQLite-databaserna, snapshots och refererade råfiler. Det frysta profilpaketet
`data-profiles-bdc9` verifierade **2232 aktiva råfiler, 0 saknade/felaktiga
hashar**, före planeringsanrop. Dess `grocery.sqlite` SHA-256 var
`85630489ac026d0263e37d76eb8fbfc7d3a11115061aacc0f8b23bcdfa5b7874`,
`plans.sqlite` `d1e1a63c4ba21244be907b18ebe576f4f6025be283acd01131632d099936d7ee`
och aktivt manifest `d14fba039e70a5bf66cdd6908033979aac6bd811e029ffad6ced5326049804ff`.
Rebuild, kopiering och autentisk replay behöll källobservationernas tider.

Windows-reläet hämtade på riktigt 1254 förfrågningar med 18 954 rader för
kommun 1281 (en HTTP 500, hel insamling slutförd). Artefakten
`fffd9384d1724db9acbc4f104b74af71.smako-source`, SHA-256
`76eabee073a1f0b5dfe08f51b65eb1154c991ec0207ffaa032c0e30c955b5325`,
innehöll kommunbundna käll-ID:n 2176/2354, 10 500 distinkta produkter,
observationer 2026-09-30 09:13:34–09:45:14 UTC, parser v3 och
PurchaseTerms/schema-hashar. Första importen hittade en verklig ändrad
Willys-responstyp; snäv versionsbunden översyn lades till och samma artefakt
importerades via ordinarie inbox. OWN-snapshot
`a3806a4fa4614cabb451eca73a1426d0` gav Willys Lund 10 180 och Lund Nova
8 594 serverade rader med ursprungliga tider. Dubblettleverans returnerade
`already_active`, beständigt kvitto behöll hash/tillstånd och omedelbar omkörning
gav `not_due`, **0 externa prisanrop**. Den faktiska reload-kontrollen såg
manifestbyte `e08d…`→`31016…`. Ett första reload-försök fick HTTP 401 därför
att testharnessen hade olika slumpade admin-token i app och importer; harnessen
rättades, samma artefakt importerades utan dubblett och reload passerade.
Operationslåset behölls; importeraren loggar nu fullständig SQLite-felorsak.

Det frysta manifestet `1e1b3695…` hade **42 491 produkter/20 kontexter**.
Fem obligatoriska onlinebaskontexter var aktuella och faktiskt laddade:

| Bas | Rader | Senaste autentiska observation (UTC) |
| --- | ---: | --- |
| Coop Online Syd | 11 413 | 2026-09-29 12:20 |
| Hemköp Brunnshög | 5 098 | 2026-09-29 12:50 |
| Hemköp Karhögstorg | 6 242 | 2026-09-29 12:36 |
| Willys Lund | 10 180 | 2026-09-30 09:25 |
| Willys Lund Nova | 8 594 | 2026-09-30 09:45 |

Den efterföljande **äkta behovsstyrda** körningen 2026-09-30 11:17–11:30
UTC gjorde inga nya fullhämtningar av dessa ännu giltiga baser. Den hämtade
förfallna frivilliga källor och publicerade/reloadade `624e4de9…` atomiskt:
**44 132 produkter/33 kontexter**, 11 Coop (inklusive online), 5 Hemköp,
12 ICA, 2 Lidl och 3 Willys. Efteråt var `due_sources=[]` och ingen källåtgärd
förfallen. Coop hade 10 valda fysiska butiker inom kommunen, 1625
kvalificerade kandidat-rader och 565 rapporterade karantänrader; 1623 rader
serverades (två PDF-kandidater kvalificerade inte för serving). Hemköps tre
fysiska butiker gav 45+46+49=140 serverade erbjudanden. ICA:s 12 valda
butiker gav 824 serverade rader. Två Lidl-butiker gav vardera 2 kvalificerade
och 367 karantänrader; en fysisk Willys-butik gav 14 kvalificerade och 20
karantänrader. City Gross hade 0 valda/bidragande butiker. Inom de *valda*
Coop-, Lidl- och Willys-raderna var kommunstatus 10/2/1 `inside`; detta är
inte ett påstående om att alla potentiellt upptäckbara kommunträffar är kända
eller bidrar. Full erbjudandetäckning är varken uppnådd eller releasekrav.
`offers_only` ändrades inte till `full_catalog`. Ursprunglig Primat-policy
ligger kvar separat; Malmö-publicering beslutas separat.

## HTTP-köp, kvalitetsgränser och felprov

På **exakt samma frysta 42 491-raders manifest** gav fyra ordinarie
`POST /api/plans` för fria 15/20-profiler HTTP 201: original respektive separat
Willys Plus/Lidl Plus-kopia, vardera exact och estimated. Samtliga gav 15
slots (fem middag, fem frukost, fem mellanmål), 20 portioner, högst två
inköpsställen och **442,41 kr/22,12 kr per portion**. Receptversioner,
40/30/20-proteingränser och övriga val behölls; kontrollen fann minimum
40,8/35,5/22 g. Middagarnas näringsstatus var `ESTIMATED`, frukost/mellanmål
`VERIFIED`; allergenstatus `NOT_REQUESTED`, inte ett tyst godkännande.
Köpaudit och total var verifierade, okända mängder 0; alla fyra sparade
planer gav byteidentiskt GET även efter faktisk Uvicorn-processomstart.
`reproducible=true` och `recalculation_available=false` skiljer läsbarhet
från omräkning. Prisvärdet är uppmätt på detta underlag, inget historiskt
acceptansvärde. Inga användaranrop gjorde externa prisförfrågningar.
Nästa ordinarie import-/rebuild-/publiceringspipeline kördes två gånger på
den separata plan-kopian utan externt nät; frivilliga insamlingshooks var
uttryckligen uppskjutna. Båda körningarna byggde en kandidat men gav
`degraded`/exit 2 för det avgränsade insamlingsläget och behöll samma faktiskt
laddade manifest `1e1b3695…`; de får inte maskeras som full käll-PASS.
Efter första rebuild låg samtliga fyra ursprungliga planers sparade
`response_json` kvar oförändrad i `plans.sqlite`. En ny anonym session fick
förväntat HTTP 403 på en annan sessions plan. En ny källbelagd plan skapad
med bevarad sessionskaka gav HTTP 200 och identisk plan/ursprungligt
PriceUniverse-ID efter **andra rebuild och faktisk appomstart**.
`price_version_status=current`, `recalculation_available=false`; detta
bevisar sparad läsning på ny kod, inte äldre kods omräkning av nya planer.

Representativa källbelagda köp mot samma app/manifest gav:

| Källa och villkor | HTTP och pris | Mängd, näring, allergen |
| --- | --- | --- |
| ICA lax, cirka 1 200 g, 139 kr/kg | estimated 201, 166,80 kr, `VERIFIED_WITH_ESTIMATES`; exact 422 `DATA_BLOCKED` | 200 g behov, 1 000 g möjlig rest; näring ej bekräftad för dessa extraköp, allergen `NOT_REQUESTED` |
| ICA lösviktsgodis, 89 kr/kg | estimated 201, 31,15 kr, `VERIFIED_WITH_ESTIMATES` | 350 g; näring ej bekräftad, allergen `NOT_REQUESTED` |
| ICA krossade tomater, hela 3 för 25 kr | exact 201, 25 kr, `VERIFIED` | 390 g behov, 780 g möjlig rest; näring ej bekräftad, allergen `NOT_REQUESTED` |
| Hemköp pizza, välj variant, 2 för 79 kr | exact 201, 79 kr, **`UNVERIFIED`** | öppet variantval, ingen automatiskt godkänd receptingrediens/näring/allergen |

Alla fyra lyckade köpen gick att GET-läsa identiskt efter omstart.
Separat prov med verklig nyimporterad fysisk Hemköp-koriander och vitlök
klarade varukorgsaudit och rå berednings-/näringsberäkning från angivna
Livsmedelsverket-referenser: 6,9 kcal och 0,52 g protein per portion.
Det är **generisk referens för uppmätt ätbar rå mängd**, inte verifierad
produktdeklaration eller allergengodkännande (`allergen_approval=false`).
Framtidsklocka på faktiskt aktivt manifest: efter 49 timmar fanns 0
baspris-kandidater, efter alla kampanjslut 0 kandidater och 0 läckta
utgångna köp. En injicerad 49 timmar gammal obligatorisk Coop-bas avvisades
av atomisk publicering utan aktivt manifest i separat rot. Frivilligt
Willys-fel behöll senaste godkända källa; autentiska sparade källbytes replay
återhämtade källan utan föryngring och utan ändring av huvudmanifestet.
Första versionen av just testharnessen valde en äldre sparad råfil med osorterad
`glob`; korrigerad körning valde senaste autentiska råfilen och visade
oförändrad observation. Inget av dessa felprov är ett verkligt butikshaveri.

## Kompatibilitet, installation och beslut

Ny kommunbunden reläartefakt avvisades av den **nuvarande
produktionsmottagaren** i skrivskyddat prov. Gammal city-scope-reläartefakt
avvisades korrekt av den nya kommunmottagaren som otillåten tyst ersättning.
Alltså krävs ett samordnat kort avbrott mellan server och Windows-relä; inget
obevakat server-först-fönster. Nytt relä + ny mottagare, återleverans,
operationslås och faktiskt reload är verifierade i isolering. En separat
registrering av tillfällig S4U/Session-0-testuppgift nekades av Windows med
`Åtkomst nekad`; det versionsbundna paketet har körts interaktivt med skild
testkonfiguration/tillstånd, men dess **obevakade** körning är ännu inte
verifierad. Den aktiva uppgiften är oförändrad (kanonisk XML identisk med
exporten före arbetet), senast resultat 1 och nästa schemalagd körning
2026-10-01 01:30 lokal tid. Varken serverpaket, femkällorspolicy eller nytt
Windows-jobb har installerats/aktiverats i produktion.

Aktiverings-/återgångsordning och exakta ändringar finns i
[ACTIVATION.md](ACTIVATION.md). Kvarstående tekniska spärrar är
obevakad S4U-verifiering av kandidatpaketet, gemensam versionsövergång med
säker köhantering och nu **belagd** läsinkompatibilitet i återgångsbilden;
se driftkompletteringen ovan. De **tre separata besluten** om policy,
serveraktivering och aktiv Windows-uppgift är ytterligare godkännanden,
inte ersättning för teknisk beredskap. Testresultatens tidsstämplar och
källfärskhet måste kontrolleras igen vid själva aktiveringen; denna rapport
gör dem inte evigt giltiga.

**INTE REDO** för skarp aktivering på detta underlag.
