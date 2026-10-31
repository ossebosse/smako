# Lagring och säker arkivering

## Arkiverad oanvänd appbild och byggcache, 2026-10-31

Vid [kontrasträttningen](releases/plan-notice-contrast-20261031/ACTIVATED.md)
säkrades den tidigare aktiverade bilden `app-562afbb53344-92f00d23` i en
åtkomstskyddad operatörskopia på D: under
`.local/beta-plan-contrast-20261031/protected-archive/app-562afbb53344-image.tar.gz`.
Alla åtta OCI-blobbar, exakt image-ID och tagg verifierades innan just den
oanvända bildens serverreferenser togs bort utan force. Ordinarie automatiska
regler ändrades inte: detta var en separat engångsgranskning av ägarskap,
tidigare aktivering samt alla container- och effektiva Compose-referenser.
Enbart oanvänd BuildKit-cache rensades därefter. Journalen redovisar uppmätt
nettovinst, inte summan av överlappande logiska Dockerstorlekar.
Aktiva, återställnings- och kandidatbilder samt alla containrar bevarades.
Privat IMAGE-EXTERNAL-ARCHIVED-markör vid den äldre releasens underlag
anger lokal kopia och återställningssteg. Ladda tillbaka exporten och verifiera
image-ID/tagg före användning av historiska overrides. Inga volymer eller
levande databaser ändrades av städningen.

## Flyttat avslutat releasearkiv, 2026-10-31

Vid [plan-/listaktiveringen](releases/plan-shopping-ui-20261031/ACTIVATED.md)
flyttades den redan verifierade gzip-filen
`/opt/smako/evidence/joint-week-refinement-e041451/backup-20261016T131323Z.tar.gz`
till en åtkomstskyddad operatörskopia i
`D:\Projects\Smako\.local\beta-plan-ui-20261031\protected-backup\legacy-joint-week-recovery.tar`.
Den innehåller ursprunglig gzip-fil, privat inventarium, kvitto och återställningsanvisning.
Gzip-filens tidigare dokumenterade SHA-256 verifierades både på servern och lokalt.
Först därefter togs just den oanvända serverfilen bort under driftlåset, med oförändrade
containrar och två aktuella återställningskopior kvar. Ursprungligt inventarium/kvitto
finns kvar på servern, liksom en privat EXTERNAL-ARCHIVED-markör med återställningsväg.
Äldre tabeller nedan är historiska; just denna gzip-fil finns nu i operatörskopian.
Installerad retention, reserv, aktiva databaser och användardata ändrades inte.

## Automatisk retention, 2026-10-20

Aktiverad på target 2026-10-20 15:37 UTC i schedulern
`source-ops-52c7d8291bb7`. Se [verifierad aktivering och mätvärden](reviews/storage-lifecycle-20261020.md).
Den första fullständiga körningen raderade 2,40 GB historiska filer och
frigjorde 420 MB återanvändbara sidor inne i SQLite, utöver den tidigare
rensningen på 83,36 GB. Appens menyalgoritm och RAM-cache ändrades inte av
denna schedulerrelease.

Den nya underhållsvägen är `deploy/scripts/storage_maintenance.py`. Den använder
befintligt driftlås och körs vid schedulerstart, före backupens utrymmeskontroll,
efter backup för rotation, samt högst var sjätte timme via ordinarie
refresh-arbetare. Ingen ytterligare timer behövs. Aktiveringsstatus dokumenteras
separat; att filerna finns i Git ändrar inte en redan körande scheduler.

| Innehåll | Policy |
| --- | --- |
| Dags- och nya releasebackuper | Högst tre/32 GiB och högst 14 dagar; minst två fullständiga, hashverifierade återställningskopior bevaras även om budgeten överskrids. |
| Publicerade prisartefakter | Alla aktiva kommuners manifest och deras exakta filer bevaras. Orefererade hashfiler får två dygns läsarmarginal. |
| Avbrutna prisbyggen/backupförsök | Endast exakta egna temporärnamn, efter ett dygn och under driftlåset. |
| Ordinarie refreshrapporter | 14 dagar/högst 128; de två senaste bevaras. Operatörskataloger omfattas inte. |
| Containerloggar | Befintlig Compose-policy: högst fem loggfiler à 10 MB per container. Verifierad för app, scheduler och proxy på target 2026-10-20. |
| Inaktiva källpayloads | 14 dagar; aktuella/LKG, två senaste per källscope, publicerad härkomst, incidenter och fältvalideringsreferenser undantas. Högst 32 snapshots behandlas per körning. |
| Kommunala försök | 14 dagar; aktuell referensgraf, de två senaste försöken och äldre råfiler som fortfarande används av kopierade databaser bevaras. |

Importidentiteter, ursprungliga observationstider och metadata behålls när stora
inaktiva produktposter/råkroppar tas bort. Metadata får en uttrycklig
retentionsmarkering. `reproduce` visar `retired_by_retention`, aldrig ett påstått
lyckat återspel. Lediga SQLite-sidor återanvänds; ingen exklusiv fullständig
VACUUM körs mot levande drift. Nya kommunala databaskopior rensas före användning;
den tidigare immutabla källan ändras inte.

Saknade eller felaktiga manifest, ändrade filer, länkar och okända namn ger
bevarande eller blockerad kategori. Okända gamla test-/releasekataloger och
privata användardata omfattas inte. Detta är en avgränsad datalivscykel, inte
en generell `rm` eller Docker-volymrensning. Aktiv data och nödvändiga
återställningskopior kan överstiga budgeten; då redovisas det i driftkvittot.
Varje körning ersätter `reports/operations/storage-maintenance.json`.

Samma granskade kod kan köras genom den installerade schedulern utan att först
byta dess image:

```powershell
.venv/Scripts/python.exe scripts/target_storage.py
.venv/Scripts/python.exe scripts/target_storage.py --apply
```

Första kommandot inventerar; det andra tillämpar policyn under samma driftlås.
`beta_release.py build/activate` använder denna väg före allokering och efter
aktivering. Nya appreleaser använder den ordinarie roterande backupkatalogen,
inte ytterligare databasdubletter i `/opt/smako/evidence`.
Efter bygge roteras tidigare aktiverade images som ägs av apphjälparen; aktiva
och stoppade containrars images, närmast föregående bas, de två senaste
kandidaterna samt okända eller ännu ej aktiverade images bevaras.
Oanvänd BuildKit-cache får en budget på 2 GB. Befintliga historiska images utan
det nya ägarskapsmärket raderas inte automatiskt.

Apphjälparen och källpatchpaketeraren skapar en ny slutbild från det granskade
filsystemet. Tidigare patchlager följer inte med som en växande föräldra-kedja.
Appbygget kräver identisk runtimekonfiguration och exakt granskad fildiff.
Källpaketets `IMAGE-CONFIG.json` ska jämföras med den byggda bildens `Config`
före separat aktivering. Volumes, OnBuild och Healthcheck i basbilden kräver
en separat fullrelease; verktyget avbryter hellre än att tappa metadata.
Dockerprovet bygger två följduppdateringar helt utan nät och kontrollerar
filer, konfiguration och antal lager.

Retentionen sätter inte ett tak på användarskapade planer eller nödvändig
prisdata. Små härkomstposter behålls för spårbarhet. Gamla operatörsarkiv och
okända images behöver en separat engångsgranskning; de räknas inte som
automatiskt städade av den nya policyn.

### Verifierad avgränsad rensning 2026-10-20

Den första versionen (`e9dbdbf`) kördes först skrivskyddat, därefter med samma
urval under driftlåset. **83 357 422 659 byte** togs bort: åtta äldre
dagsbackuper (47,79 GB) och 297 orefererade prisartefakter (35,57 GB).
Tre verifierade dagsbackuper och alla aktiva prisartefakter bevarades.
Inga källdatabaser, användardata, kommunala försök eller Dockerimages rensades
av denna körning. Den utökade källretentionen ska inte räknas som aktiverad av
detta kvitto.

Efterkontrollen 2026-10-20 10:04 UTC visade **94 192 029 696 byte ledigt**,
mot beräknat driftbehov 15 423 263 244 byte. Readiness var HTTP 200 och
publicerat/laddat prismanifest stämde överens. Mätningen av ledigt utrymme
inkluderar annat normalt driftarbete mellan observationerna; den är inte en
separat exakt nettomätning av städningens effekt.

## Prisåterställning 2026-10-18, kväll

Hemköps återspelning ökade databasens storlek så att publiceringens
utrymmeskontroll åter stoppade arbetet. Under samma driftlås arkiverades den
avslutade, tidigare verifierade releasebackupen
`/opt/smako/evidence/willys-picking-5b344ca3b50e/backup-20261015T080331Z`.
Aktuella container-, process- och servicereferenser kontrollerades före och
efter arkiveringen. Alla tre arkivposter, inklusive de två databasernas
filhashar, ägare och rättigheter, verifierades och originalet kontrollerades
som oförändrat innan just denna backupkatalog togs bort.

6 399 434 752 byte blev ett arkiv på 1 559 849 655 byte, med **4,84 GB netto
frigjort** och **19,40 GB ledigt** efteråt. Arkivet finns intill den tidigare
katalogen som `backup-20261015T080331Z.tar.gz` med SHA-256
`a7cc54869dab1c26ae8702becf92b5301ca6aec147ed81938e825abc30b41d17`.
Intill finns privat inventarium, kvitto och `backup-20261015T080331Z.ARCHIVED.txt`
med återställningskommando. Återställ under driftlåset till den frånvarande
originalsökvägen, aldrig över levande data.

Ordinarie dagsbackuper, retention, aktiva databaser, prisartefakter och
containerimages ändrades inte av arkiveringen. Den nya källreleasens egen
backup är också verifierad och komprimerad; se
[prisåterställningens rapport](releases/source-recovery-20261018/REPORT.md).

## Ytterligare avslutade releasebackuper, 2026-10-19

Under driftlåset verifierades och komprimerades ytterligare tre avslutade
releasebackuper. 15,02 GB frigjordes netto; 32,69 GB var
ledigt efteråt. Samtliga filhashar, ägare och behörigheter jämfördes mot
originalen före borttagning av just de okomprimerade backupkatalogerna.
Aktiva containrar och prismanifest var oförändrade över hela åtgärden.

| Arkiv under `/opt/smako/evidence/` | Byte | SHA-256 |
| --- | ---: | --- |
| `joint-week-refinement-e041451/backup-20261016T131323Z.tar.gz` | 1629737973 | `fbbc31b866b99279532e7440f22c16580453286bac768f3e6efd0803609db052` |
| `recipe-nutrition-extras-7e402a7/backup-20261015T162938Z.tar.gz` | 1604587092 | `89623d2791292e611adf4555a100b7ea6384caec52623fdca93bad5e62614e4f` |
| `willys-flyer-retained-20261015/backup-20261015T105559Z.tar.gz` | 1603850980 | `b6bd6b0f956838633fd377c4495787befa26de63c2de5de78a415c28ec01181a` |

Varje arkiv har ett intilliggande privat inventarium, kvitto och `.ARCHIVED.txt`
med exakt återställningskommando. Återställ endast under driftlåset till den
frånvarande originalsökvägen, aldrig över aktiva data. Kontrollera utrymme
för expanderade filer och driftmarginal först. Ordinarie dagsbackuper och
retention är oförändrade. Dessa är lokala återställningskopior, inte extern backup.

Samlat kvitto: `/opt/smako/evidence/hemkop-context-c6607a095018/additional-archive-receipt.json`.

## Underhåll 2026-10-18

Ny inventering fann bara 6,20 GB ledigt och återkommande
`InsufficientStorageError` för dagsbackupen. Under befintligt driftlås
frigjordes **22,41 GB netto** genom verifierad komprimering av sex inaktiva
arkivkataloger och rensning av oanvänd Docker-byggcache. Ledigt utrymme
efter arkiveringen, före ny backup, var **28,61 GB**.

De sex katalogerna omfattade 29,50 GB allokerat och tar nu 7,13 GB som
gzip/tar-arkiv. Alla 185 arkivposter kontrollerades, inklusive SHA-256 för
varje vanlig fil, ägare, behörigheter och symlänkar. Ursprunget hashas igen
och kontrolleras mot container-, process- och servicereferenser före
borttagning. Alla containeridentiteter, konfigurationer, image-ID:n och
aktiva prismanifest är oförändrade över underhållet. Levande databaser,
prisartefakter, ordinarie dagsbackuper och backupretention rensades inte.

Arkiven och privata inventarier finns i
`/srv/smako/cold-test-archives/storage-maintenance-20261018/`.
Körjournal, före/efter-kvitton och operatörsskript finns i
`/opt/smako/evidence/storage-maintenance-20261018/`.
Varje tidigare katalog har en intilliggande `*.ARCHIVED-20261018.txt`
med arkivnamn, SHA-256 och exakt återställningskommando. Detta gäller:

- `status-activation-20261006/current-state-backup`
- `complete-recipes-20261003/backups-off`
- `complete-recipes-20261003/backups-on`
- `base-price-retention-0f54e51/backup-20261015T071523Z`
- `recipe-product-links-07af5ac/backup-20261015T122602Z`
- `ops-price-recovery-8d4327ea4227/restore-rehearsal/restored`

Samtliga ursprungliga sökvägar ligger under `/opt/smako/evidence/`.
Äldre aktiveringsrapporter som pekar på dessa kataloger ska nu följas via
arkivanvisningen. Återställ endast under driftlåset, till en frånvarande
ursprunglig sökväg, med kontrollerad arkivhash och tillräckligt utrymme.
Inget arkiv återställs över aktuella produktionsdata.

Docker rapporterade 1,196 GB logisk byggcache, men större delen delade lager
med bevarade images. Använd nettomätningen ovan, inte summan av logiska
Dockerstorlekar. Ingen image-, container- eller volym-prune kördes.

Ny ordinarie backup **`20261018T084659Z`** slutfördes 09:01:48 UTC och
verifierade 68 filer, 7,63 GB, med återställningsunderlag för både Lund och
Malmö. Efter backupen fanns **20,98 GB ledigt**, över driftkontrollens
uppskattade behov på 13,99 GB. Backupstatus är `complete`, readiness är
HTTP 200/`ready` och `PRICE_UNIVERSE_PREWARM_ENABLED=false` är kvar.
Backupen använde befintlig kod för SQLite-integritet, främmande nycklar,
filhashar och komplett manifest; inget nytt fullständigt återställningsprov
kördes. Befintliga käll-/åldersvarningar påverkas inte av lagringsunderhållet.

Slutlig backup- och driftkontroll: se
[maskinverifieringen](releases/storage-maintenance-20261018/VERIFIED.json).

## Inventering 2026-10-11

Inventeringen 2026-10-11 fann 403,1 GB använt och 12,3 GB ledigt på rotfilsystemet.
Serverdisken är 400 GiB; rotfilsystemets användbara storlek är 415,4 GB i decimala
enheter. Använd samma enhet när före/efter jämförs.

| Katalog | Allokerat före, GB | Innehåll |
| --- | ---: | --- |
| `/var/lib/containerd` | 161,4 | Containerbilder, lager och byggcache |
| `/var/tmp` | 116,7 | Historiska utvecklings-/testmiljöer, ofta med egna databaser |
| `/srv/smako/backups` | 65,0 | Dagliga och särskilda återställningspaket |
| `/srv/smako/data` | 33,6 | Databaser, råunderlag, prisuniversum, planer och rapporter |
| `/opt/smako/evidence` | 17,7 | Tidigare verifierings- och återställningsunderlag |

Detta är fysisk katalogstorlek. Dockers redovisning av bilder och byggcache
delar lager och får inte adderas som oberoende diskutrymme. `/tmp` är tmpfs;
dess användning är inte förklaringen till att rotfilsystemet fylldes.

## Genomfört 2026-10-11 09:11 UTC

**106,49 GB netto frigjort**, mätt över underhållsfönstret. Använt utrymme gick
från 403,47 till 296,98 GB, och ledigt från 11,89 till **118,39 GB**. `df` visar
nu 72 % använt, jämfört med 98 % före underhållet. Mellan den första inventeringen
och driftlåsets början slutfördes en ordinarie prisuppdatering; därför skiljer
sig startvärdet något från tabellen ovan.

- 15 oanvända testmiljöer: **60,05 GB → 13,56 GB** komprimerade arkiv. Samtliga
  54 018 poster kontrollerades; varje vanlig fils SHA-256 återlästes ur arkivet
  före borttagning av originalträdet. Ägare, behörigheter och symlänkar verifierades.
- `docker builder prune --all --force` rensade oanvänd byggcache. Docker redovisade
  83,38 GB logisk cache, medan faktisk containerd-lagring minskade från **161,42
  till 101,18 GB**. 146 bilder och 40 containrar, varav fem körande, finns kvar.
  Den verkliga nettovinsten ovan kommer från filsystemsmätningen, inte summan
  av Dockers delvis överlappande storlekstal.
- Backup `20260914T123547Z` ägdes av root med 0700/0600 och kunde inte läsas eller
  rensas av backupkontot 10001. Den befintliga rotationskoden avbryts vid sådana
  åtkomstfel. Ägarskapet rättades till 10001:10001; filhashar, behörigheter och
  ändringstider är bevarade och kontots åtkomst provad. En separat verifierad
  historisk kopia på **0,188 GB** sparades före ändringen eftersom backupen också
  nämns i äldre releasebevis. Dagsbackuperna har inte raderats av underhållet,
  och 14-dagarsinställningen är oförändrad. Nästa fullständiga backuprotation
  återstår att observera; den räknas inte som genomförd här.

Arkivkatalogen inklusive inventarier och historisk backup tar 13,76 GB.
`/var/tmp` minskade till 56,66 GB. Återstående testmiljöer har container-/process-
eller ICA-beroenden och ingick inte i urvalet. Bilder för drift, återgång och
väntande arbete är bevarade; detta var inte en generell image-/container-prune.

Underhållet väntade på ordinarie prisinsamling, tog det befintliga driftlåset
och släppte det efter verifiering. Alla fem körande containeridentiteter/bilder,
mounts, konfiguration, cron och prismanifest är oförändrade över underhållet.
Alla **256 planrevisioner och 82 privata tillstånd** är hashbevarade. Inga
containrar startades om. Sex isolerade arkivtester, Ruff och compileall passerade.

Efterkontroll 09:11 UTC: readiness 200 i Lund och Malmö, rätt publicerat och
laddat manifest i båda. Malmö har 2 607 produkter och 63 pris-/butikskontexter
(FRESH), Lund 2 263 och 29 (befintlig AGING för Willys). Den ordinarie uppdateringen
före städningen godkände Hemköp Värnhem/Elinegård och publicerade Malmös nya
manifest `8c49ecda…`; det var inte arkiveringen som ändrade priserna.

Exakta mätvärden, arkivhashar, kontroller och snapshots finns i
[VERIFIED.json](releases/storage-reduction-20261011/VERIFIED.json).

## Arkiveringsverktyget

`scripts/archive_cold_test_tree.py` är en operatörsprimitiv för **en explicit
granskad** kall testkatalog direkt under `/var/tmp`. Den är inte en automatisk
städare. Anroparen måste först ta befintligt gemensamt produktionslås enligt
`RefreshRunLock`/`production_refresh_lock_path`. Avbryt eller vänta om upptaget;
stoppa inte pågående insamling. Kör inte samtidigt med en annan operatör.

Verktyget avvisar symlänkade rötter, ICA-namn, specialfiler, utökade attribut och
referenser från processer, samtliga Dockercontainrar (även stoppade) eller aktuell
servicekonfiguration. Operatören måste dessutom granska planerade releaser och
externa referenser; automatisk referenssökning ersätter inte den granskningen.

Alla filer hashas före arkivering. Ett privat gzip/tar-arkiv och inventarium
skrivs och fsyncas. Varje arkivmedlem verifieras inklusive filinnehåll, ägare,
behörigheter och symlänkar; hela ursprungsträdet måste fortfarande vara
oförändrat och oanvänt innan just den granskade roten tas bort. Fel behåller
originalet. Befintliga arkiv skrivs aldrig över. Misslyckade/avbrutna försök
kräver granskning före omkörning och kan lämna ett partiellt arkiv.

Linuxprov (sex isolerade fall, inga produktionsanrop):

```sh
python -m unittest discover -s scripts -p test_archive_cold_test_tree.py -v
```

Vid containerprov krävs minst 1 GiB ledigt i testets tmpfs eftersom
arkiveringsverktyget reserverar ytterligare 512 MiB i staging-kontrollen.

## Återställning av ett kallt testträd

Arkiv finns i `/srv/smako/cold-test-archives`, skyddade med katalogläge 0700 och
filläge 0600. Bevis och exakt urvalslista finns i
`/opt/smako/evidence/storage-reduction-20261011`. De är lokala återställningskopior,
inte en ersättning för extern backup.

Den extra historiska backupkopian heter
`backup-baseline-20260914T123547Z.tar.gz`; inventariet ligger i beviskatalogens
`backup-owner-before.private.json`. Återställ den i en isolerad katalog för
granskning. Återinför inte en root-ägd daterad katalog i den dagliga rotationen.

1. Välj exakt arkiv från resultatlistan, kontrollera dess SHA-256 mot resultatet
   och kör `verify(archive, expected)` med tillhörande privata inventarium.
2. Ta driftlåset och kontrollera att den ursprungliga sökvägen är ledig samt att
   utrymme finns för inventariets expanderade filstorlek och driftmarginal.
3. Packa upp just det betrodda, verifierade arkivet med `tar -xpf <arkiv.tar.gz>
   -C /var/tmp` som administratör. GNU tar detekterar gzip vid läsning.
4. Verifiera återställda filhashar, symlänkar, ägare och behörigheter. Inode/ctime
   blir nya efter återställning och ska inte jämföras som identiska.

Återställning startar ingen container och ändrar ingen produktionskonfiguration.

## Historiska driftrekommendationer före retentionen 2026-10-20

Backup- och releasebeteendet i denna äldre lista ersätts av policyn
**Automatisk retention, 2026-10-20** ovan. Referensskydden för okända arkiv,
volymer och väntande arbete gäller fortsatt.

- Skapa inga nya fullständiga daterade projekt-/databaskopior på servern som
  standard. Använd det permanenta repot och avgränsade fixtures; arkivera granskade
  avslutade testmiljöer efter verifiering.
- Rensa endast oanvänd byggcache genom Dockers API i ett ledigt driftfönster.
  Radera aldrig containerd-lager direkt. Cache kan byggas om; bilder, containerdata
  och volymer har annan betydelse och får inte följa med i en generell prune.
- Behåll körande/stoppade containerreferenser, nuvarande release, återgångsversion
  och väntande ICA-arbete. Äldre bildhistorik kan granskas separat mot dessa
  referenser. Att Docker kallar något reclaimable är inte tillräckligt beslut.
- Backupkodens standard är 14 dagar, men rensning sker först efter en lyckad ny
  verifierad backup. Särskilda aktiveringspaket följer inte den dagliga rotationen.
  Kontrollera faktisk inställning och lyckad återställning innan retention ändras.
- Inför större kommunutrullning behövs retention för råunderlag, gamla
  prisartefakter och rapporter som respekterar aktiva/LKG-/plan-/auditreferenser,
  samt kommunövergripande verifierad backup. Kommunantal ensamt dimensionerar
  inte lagring; antal butiker, katalogstorlek och sparad historik avgör tillväxten.

Inga scheman, källkvalitetsgränser eller backupretention ändras av arkiveringen.
