# Hemköp och Willys: återställning av prisinsamlingen

**Slutläge 2026-10-19 00:42 UTC:** Hemköps rättning är aktiv på betan och
alla återställda Hemköp- samt nya Willys-baskällor är publicerade och laddade
i Lund och Malmö. Båda reläkvittona finns. Det nya Windowsreläet är
installerat och verifierat, men **schemabytet är inte genomfört**: Windows
nekade åtkomst och UAC-starten avbröts. Befintlig uppgift pekar fortsatt på
`5b344ca3b50e`; se administratörssteget nedan.

Kodcommits: `c6607a095018f1e0efffb9541ef85742ede0d41f` (Hemköp),
`84b2de8d207fb536baf562f651f1d3f603fa6146` (Willys checkpoints) och
`2464596b6f07abae5b9cfe5e9432e19e77620892` (reläets publiceringstid), integrerade
och pushade till `main`. Användaren beställde driftkontroll, rättning, commit
och aktivering.

## Orsaker

Hemköps adapter använder Willys/Axfoods gemensamma produktparser. När den
senare började kräva den sparade butikskontexten för butiker med
`hasPickingBaseStore`, skickade Hemköp fortfarande bara en katalogsida i taget
utan kontextdokumentet. Upptäcktens `hasPickingBaseStore: false` bevarades,
men underlaget för den oberoende kontrollen tappades i adapteranropet.
Resultatet blev `price_context_unverified` på varje sida och noll parsade
produkter, trots komplett och butiksbunden hämtning. Hälsokontrollen stoppade
korrekt de tomma kandidaterna och behöll tidigare kvalificerade priser.

Rättningen skickar med de ursprungliga kontextdokumenten och råreferenserna
till den gemensamma parsern. Felaktig, saknad eller motstridig bindning stoppas
fortfarande. Parsern versionssätts till `hemkop-parser-v1.4-delegated-context`
och registreras för samma redan granskade schemaskillnader. Inga gränser för
fullständighet, priser, identitet eller kvalitet sänks.

Willys senaste lokala försök stoppades före insamling av
`insufficient_receiver_storage`. Exempel 18 oktober 15:30 UTC: 11,78 GB ledigt
mot 13,98 GB beräknat behov. Vid denna uppgifts första driftkontroll fanns
16,69 GB ledigt, efter den föregående releasens avslutade backupkomprimering.
Ett begränsat återförsök startades med det befintliga installerade reläpaketet
`5b344ca3b50e`, samma kommunregister, körfönster, takt och lås. Ingen
Windowsuppgift eller insamlingspolicy ändrades vid det första återförsöket.

Under återhämtningen upptäcktes ytterligare ett Willys-fel. Malmö hann tre
butiker innan körfönstrets konservativa budget sköt upp den fjärde. Nästa
insamling återanvände inte de färdiga butikernas checkpoints: SCB:s WFS-svar
innehåller en ny `timeStamp` vid varje hämtning. Identiteten undantog redan
yttre `observed_at`, men inkluderade fortfarande den inre tidsstämpeln och
råpayloadens hash. Två nya svar från SCB verifierade identiska gränsdata och
enbart ändrad `timeStamp`.

Checkpointfixen verifierar först originalpayloadens hash, och beräknar sedan
identiteten utan dessa transporttider och den härledda råhashen. Endast en
giltig tidsstämpel med tidszon undantas. Geometri, egenskaper, antal, CRS och
källmetadata ingår fortfarande. Råpayload, råhash och observationstid bevaras
oförändrade som evidens. Identitetsschema 2 återanvänder inte äldre v1-cache;
den gamla hashnyckeln räcker inte för att bevisa oförändrad geometri.

Malmöleveransen visade också att reläets hårda SSH-gräns på 30 minuter var
för kort för import och normal kommunpublicering. Den passerades 19 oktober
00:28:20 UTC medan samma serverjobb fortfarande arbetade under driftlåset.
`2464596` ger import/publicering 45 minuter och reserverar samma tid före
insamlingen. Kommuner skjuts upp om mindre än denna reserv plus tio minuters
insamlingsfönster återstår. Det totala reläfönstret 10 200 sekunder och
Windowsuppgiftens tretimmarsgräns ändras inte, och inga kvalitetsspärrar sänks.

## Verifiering före aktivering

97 riktade tester passerade: Hemköps parser, picking-kontrakt, schemagranskning,
replay-scope och orkestrering samt Willys picking-kontrakt. De nya testen
kopplar faktisk butiksupptäckt till katalog- och detaljparsning, kontrollerar
råreferenser och avvisar saknad/felaktig/motstridig butikskontext. Ruff och
compileall passerade.

GitHub-CI är också godkänd för samtliga tre kodcommits:
[Hemköp](https://github.com/ossebosse/smako/actions/runs/39162401140),
[checkpointfix](https://github.com/ossebosse/smako/actions/runs/39172146552) och
[tidsrättning](https://github.com/ossebosse/smako/actions/runs/39181249942).

Ytterligare 126 riktade tester passerade för checkpointidentitet, återupptagen
hämtning, lokalt relä och källartefakter. Även där passerade Ruff och
compileall. En ändrad geometri eller annan relevant gränsmetadata ger fortsatt
en annan identitet. Två autentiska SCB-svar med olika råhashar gav samma
nya identitet, med oförändrat originalunderlag.

Tidsrättningen klarade ytterligare 81 riktade tester, Ruff och compileall.
Testen verifierar själva SSH-kommandots tidsgräns och att tid som första
kommunen använder minskar nästa kommuns insamlingstid, med bevarad reserv
för import/publicering. För litet återstående fönster ger uppskjuten körning.

Den första Windowskandidaten `84b2de8d207f` bygger på den faktiskt installerade releasen
`5b344ca3b50e8fb670e4ef05332aed6464c46793`. Endast
`grocery_data/app/services/catalog_checkpoint.py` ändras, exakt till Git;
684 andra runtimefiler är hashidentiska. Paketet installerades separat med
låsta befintliga offlineberoenden, godkänd `pip check` och integritetskontroll
av alla 685 filer. Paket-SHA:
`393ea70352419ca741502892e7272cdca725b93819aaa967c5cf8cfa76efeee4`.

Det exakt installerade kandidatpaketet verifierade Lunds tidigare levererade
artefakt och återanvände sedan båda butikernas **1 268 rådokument** efter ändrad
WFS-tidsstämpel. Originalobservationer och hashvärden var identiska, och ett
förbjudet återhämtningsanrop anropades aldrig. Provet spärrade nätanslutning
och gjorde noll källanrop. Testharnessens första körning stoppades av spärren
vid Windows eventloops interna lokala socketpar, före checkpointprovet;
eventloopen initierades därefter före nätspärren. Ingen produktionskod ändrades
för detta testproblem.

Slutlig Windowskandidat är `2464596b6f07`. Den innehåller både checkpointfixen
och tidsrättningen: två runtimefiler exakt lika med Git, 683 andra filer
hashidentiska med den faktiskt installerade basen. Paket-SHA:
`329ab94c5ec1bea8fe0ba830a3514c8e359299ab9949021c3624e71d4207b303`.
Separat offlineinstallation, `pip check` och integritetskontroll av alla 685
filer passerade. Det exakta installerade paketet prövades med nätet spärrat:
SSH-gränsen är 2 700 sekunder, och ett första kommunjobb på 4 500 sekunder
lämnar 3 000 sekunder insamling plus 2 700 sekunder publicering åt nästa.
Checkpointprovet återanvänds med hashidentisk kod; 684 runtimefiler är
oförändrade från den första kandidaten. Ingen ny prisinsamling behövdes.

Kandidatbilden byggdes utan nätverk ovanpå den faktiskt aktiva schedulerbilden.
Bara `grocery_data/app/connectors/hemkop/parser.py` och
`grocery_data/app/services/collector.py` ändrades, båda exakt lika med Git.
628 andra runtimefiler är hashidentiska med basbilden.

- Bas: `sha256:8f25b16ea86cf5cd93d385f87db7d20b73a2543bdc70cb9c08b7beb52ec15a10`.
- Kandidat: `sha256:5209ddf7d5544d90d7aa0b1b2bf88002e3b236486434f38e114d1b1083713980`.
- BUILD_ID: `hemkop-context-scheduler-c6607a095018`.
- Paket-SHA: `0c4f4f66c107dd251ad35fac232ec03d6219819411a9b63dea3d36845bbd6b7b`.

Den exakta kandidatbilden prövades med avstängt nät och skrivskyddade
produktionsvolymer mot sex kompletta sparade kataloger från 18 oktober.
570 råfiler hashverifierades. Samma connector, fullständighetsavstämning och
produktnormalisering accepterade 43 146 produktposter utan karantän:

| Butik | Ursprunglig snapshot | Produktposter |
| --- | --- | ---: |
| Hemköp 4123 | `4f8ffad7753d4d32927c0a81e797a197` | 6 290 |
| Hemköp 4224 | `fa4ef3e71d074fe1946736d7c89d3592` | 5 039 |
| Hemköp 4114 | `5714654515b142539f1bdf36d66d25c9` | 8 773 |
| Hemköp 4199 | `ecd5bd796ddd451ebf18a12f3b413e59` | 7 188 |
| Hemköp 4212 | `6adaa109e6344e5b86ab0fa2a1b742aa` | 6 493 |
| Hemköp 4247 | `d8090055ea9f4991b33d7d53b98a23d8` | 9 363 |

Alla sex klarade också den normala hälsokontrollen mot respektive aktiv
baslinje, inklusive granskning av schemaskillnader, utan anomalier.
Detta är återspel av verkliga observationer, inte nya observationstider.
Fältet request_count i det isolerade processeringsresultatet beskriver sparade
rådokument; körningen gjorde noll nätanrop.

## Aktivering och återhämtning

Aktiverad **2026-10-18 20:22:58 UTC** under befintligt driftlås. Endast
schedulers image och BUILD_ID ändrades. Appens container, alla källmounts,
övrig miljö och aktiva prismanifest bevarades vid bytet. Appen är fortsatt
`app-bac0fc15ca9a-512ef3ea`.

SQLite-backuperna klarade quick_check. Releasens egen grocery-backup
komprimerades och återlästes med identisk SHA-256 före borttagning av endast
dess okomprimerade kopia. Backupkatalog:
`/opt/smako/evidence/hemkop-context-c6607a095018/backup-20261018T201459Z/`.
`grocery-compression.json` innehåller båda hashvärdena; grocery-data finns i
`grocery.sqlite.gz` och planerna i `plans.sqlite3`.

Efter aktiveringen verifierades **299 tidigare planrevisioner och 110 privata
tillstånd** som hashbevarade. App, scheduler och proxy kör utan omstarter eller
OOM. Cirka 14,93 GB var ledigt mot beräknat driftbehov 13,99 GB.

Återspelningen avslutades **20:27:46 UTC**: alla sex snapshots blev healthy
och promoverades, totalt 43 146 produkter och noll karantänposter. Varje ny
snapshot jämfördes mot originalets samtliga råhashar, observationstider och
råsökvägar; alla var identiska. Nätanslutning var spärrad även i själva
återspelningen. Inga schemaspärrar åsidosattes.

Återställningen använde befintlig DatabaseReplayService och promotion-hook
under driftlåset. Den avgränsade körningen kontrollerade sex exakta öppna
incidenter, fulla signaturer, snapshot-ID:n, tidigare aktiva källor, runtime,
parserversion, färska originalhashar och just det belagda parserfelet före
skrivning. Normal `ops repair replay` stöder enbart schema-incidentklassen;
dess generella tillåtna åtgärder breddades inte för detta adapterfel.
En beständig separat återställningsjournal hindrar oavsiktlig omkörning.

Efter återspelningen underskred tillgängligt utrymme åter publiceringens
beräknade behov. Den avslutade releasebackupen från 15 oktober arkiverades
förlustfritt efter aktuell referens- och hashkontroll under driftlåset.
Det frigjorde 4,84 GB och gav 19,40 GB ledigt. Aktiva data, ordinarie backuper,
retention och lagringsgränser bevarades. [Arkiv och återställning](../../storage-maintenance.md).

För att nästa dagsbackup inte åter skulle förbruka samma marginal granskades
ytterligare tre avslutade releasebackuper. Efter den ordinarie kommunrefreshen
komprimerades de under driftlåset **22:47:07–22:51:59 UTC**. Alla elva
arkivposter, filhashar, ägare och behörigheter verifierades före borttagning
av de okomprimerade kopiorna. Ytterligare **15,02 GB netto** frigjordes och
**32,69 GB** var ledigt efteråt. Aktiva containrar och prismanifest var
hashidentiska över åtgärden. Exakta arkiv, SHA-256 och återställningsvägar
finns i lagringsjournalen. Detta är uppmätt marginal, inte en garanti mot
framtida tillväxt; dagsbackupernas 14-dagarsretention är oförändrad.

Lunds första publicering avslutades 20:48:52 UTC. Appens scoped readiness
visade HTTP 200 och exakt det nya manifestet
`price-universe:216bde650841a36b35b58f22f027d8692bd50359cc7e2f475f5f4c0a2c4b793a`.
Diskmanifestet innehåller båda återställda Hemköp-snapshots.
Den normala refreshens exitkod 2 betyder användbar publicering med varningar
(Willys gamla baspriser). Befintlig `ops repair` skriver ändå `failed` för
alla koder utom 0; detta är en missvisande historiketikett och inte ett
belägg för misslyckad publicering. Den separata laddningskontrollen används
som kvitto. Samma publiceringsförsök kördes inte om.

Willys nya Lund-katalog blev healthy med 19 423 produkter och noll fel.
Reläets fullständiga körning räknade 1 272 anrop inklusive upptäckt,
med originalobservation från 20:12:31 UTC. Valideringen och serverns
lagringskontroller före uppladdning respektive import passerade.
Lund fick server- och lokal kvittens **21:11:27/29 UTC**. Importerad snapshot
`8c8c90da789d491ab6b287384717f18b` är publicerad och laddad i manifest
`price-universe:5f33658b2b419cf2d5f7cb5569325e4fb1a5c30b7df6f87353e4a1560ed2371b`.
Driftkontrollen visar alla fem obligatoriska källkontexter FRESH, publicerade
och laddade. Reläartefaktens SHA-256 är
`606e0cbf144d6d72150c95a3e3feac0354fe1ce8048b0bc09cb0762deb1827cd`.

Lunds offentliga personliga menyflöde gav HTTP 201, fem recept och två butiker
(Hemköp och Willys), med godkänd kassakontroll, identisk sparad GET och noll
kedjeanrop under planeringen. Total 548,78 kr, 40,38 s. Ett extra äldre
smoke-testfält för icke-personliga planer saknas i detta svar; testharnessen
rättades till den befintliga personliga kassakontrollen och provet upprepades.
Det första svarets kassakontroll hade också passerat; ingen appkod ändrades.

Malmös första publicering avslutades **21:47:47 UTC**, med samma användbara
varningskod 2 medan Willys-insamlingen fortfarande pågick. Appens scoped
readiness verifierade exakt manifest
`price-universe:2efff3be65824bde3abf4fa072f4b5566984d94de26d8780edd08941834fe78c`,
som innehåller samtliga fyra återställda Hemköp-snapshots. Därmed är alla
sex Hemköp-katalogerna publicerade och laddade. Detta var före Willys slutliga
Malmöleverans nedan.

Malmös första lokala återförsök sköt upp fjärde butiken när det återstående
körfönstret inte räckte. Ingen ofullständig kandidat promoverades. Ett nytt
avgränsat standardfönster om 7 200 sekunder körde befintlig `source_cli.collect`
med oförändrad installerad runtime och samma kommun-, workflow- och
insamlingslås. Checkpointfelet ovan gjorde att denna redan startade körning
hämtade samtliga fyra butiker på nytt; den avbröts inte för att byta kod.

Katalogen blev **healthy 23:29:01 UTC**, med **39 949 produkter och noll fel**.
Ordinarie export och artefaktverifiering blev kompletta **23:31:07 UTC**:
2 588 HTTP 200, noll HTTP-fel, noll utmaningar, 4 685,84 sekunder totalt.
Artefakt-SHA:
`48c60063910c19df1e3efc633eed87bec3d35ae159647825106cef71b4061ba6`.
Alla ursprungliga observationer bevaras, med första butik från 22:13:16 UTC.
Operatörshjälparens efterföljande JSON-utskrift saknade datumserialisering och
gav TypeError efter lyckad export. Den beständiga `collection-metrics.json`
visar `complete`; felet ligger efter ordinarie artefaktvalidering. Det är
korrigerat i hjälparen och ledde inte till en ny insamling.

Den befintliga relävägen i kandidat `84b2de8d207f` validerade och levererade
artefakten. En avgränsad operatörshjälpare väntade högst 30 minuter åt gången
på endast det belagda `RefreshAlreadyRunningError`; övriga fel behöll normal
hantering. Den spärrade ny insamling och krävde exakt ovanstående artefakthash.
Kvalificering, lagringskontroller, transport, import, publicering och kvitto
ägdes hela tiden av befintliga relä-/source_cli-funktioner. Installerade filer
ändrades inte, och ordinarie serverjobb avbröts inte.

Efter SSH-timeouten fortsatte samma serverjobb. När det var klart bekräftade
den ordinarie idempotenta importvägen `already_active`, med exakt scoped
readiness, utan en andra ombyggnad. Malmö kvitterades **2026-10-19 00:40:16 UTC**
och reläkörningen slutade med kod 0. Importerad snapshot:
`f4c94d116cce4f1d8f90d8926f7fa521`. Manifest:
`price-universe:e641b93a02ed2b5e936d391619e0f54bc7414ef15e500af556f967c7404d6d36`.
Originalobservationen är **2026-10-18 22:13:09 UTC**, inte kvittots tid.

Slutlig kommunstatus 00:40–00:41 UTC visar alla **14 obligatoriska kontexter**
(5 Lund, 9 Malmö) FRESH, kvalificerade, publicerade och laddade. Båda kommunerna
har HTTP 200/ready och samma manifest på disk och i appen. Alla sex Hemköp-ID:n
och båda Willys-artefakthasharna kontrollerades mot deras faktiska källor.
Ledigt utrymme är **30,97 GB**, mot högsta beräknade behov **15,28 GB**.

Malmös publika personliga menyprov gav HTTP 201 efter **83,92 s**, fem recept,
två butiker och total **553,65 kr**. Kassakontroll, totalsummor och identisk
sparad GET passerade, med noll kedjeanrop under planeringen. Provet använde
exakt ovanstående nya manifest. Tiden är ett enstaka prov, ingen lastgaranti.

Slutlig datakontroll **00:42:52 UTC** verifierade alla **299 tidigare
planrevisioner och 110 privata tillstånd** som hashbevarade. Efter de isolerade
proven finns 302/113. Appcontainern är oförändrad; app, scheduler och proxy
kör utan omstarter eller OOM.

## Windowsuppgiften: verifierad drift, versionsbyte väntar administratör

Den befintliga uppgiften provkördes **00:40:50 UTC**: LastTaskResult 0,
Ready, båda kommunerna `not_due`, oförändrade kvitton och oförändrad
uppgiftskonfiguration. Detta prov gällde uttryckligen den gamla releasen
`5b344ca3b50e`. Det är inte en aktivering av de två nya reläfixarna.

Det slutliga paketet `2464596b6f07` kördes också genom sin riktiga installerade
startpunkt **00:42:10 UTC**, med normal kommunregistrering och samma privata
transportkonfiguration. Båda kommunerna blev `not_due`, kod 0, utan nya
insamlingar eller ändring av Windowsuppgiften.

`Set-ScheduledTask` nekades åtkomst trots att uppgiften var ledig. Ett vanligt
UAC-försök avbröts enligt Windows; det upprepades inte utan användarens klartecken.
Action, Principals, Triggers och Settings verifierades därefter som oförändrade.
Förberett, syntaxkontrollerat administratörssteg på denna dator:
`.local/source-recovery-20261018/activate_relay_elevated.ps1`.
Det kräver den exakta slutkandidatens godkända bevis, verifierar den gamla
actionen och använder befintlig `enable_municipal_relay.ps1` för att enbart
byta release/startpunkt, med konto och schema bevarade. Efter godkänt byte
ska `verify_task.ps1` köras med standardvärdet `2464596b6f07`; detta nya
schemalagda steg är ännu inte verifierat eller påstått aktivt.

## Avgränsning och underlag

Den normala publiceringsvägen kör även förfallna,
separata kampanjjobb. Deras befintliga avvisningar av ej stödda kommersiella
villkor kvarstår och får inte likställas med basprisernas parserfel eller
godkännas genom att sänka kvalitetskrav.

Privat arbetsunderlag: `.local/source-recovery-20261018/` och serverns
`/opt/smako/evidence/hemkop-context-c6607a095018/`. Rådata, sessionsuppgifter,
fulla användarsvar och databasbackuper checkas inte in.

## Återställning av kod

Verifiera först aktuell compose mot aktiveringsbeviset och bevara eventuella
senare appändringar. Ta befintligt driftlås, återställ releasens sparade `compose-wrapper.before`
och återskapa endast scheduler med den tidigare bilden. Bevara aktuella
databaser, användarplaner och prismanifest. Den äldre koden återintroducerar
Hemköps kontextförlust vid nästa insamling; källpriser får inte föryngras eller
ersättas med äldre databaskopior för att återställa kod.
