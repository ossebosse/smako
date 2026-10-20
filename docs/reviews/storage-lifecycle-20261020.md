# Självstädande lagring och uppdateringar, 2026-10-20

**Aktuell status:** aktiverad och efterkontrollerad 15:37–15:40 UTC.
Schedulern kör `source-ops-52c7d8291bb7`; båda publika menyproven passerade.
Nedan finns även historiken för de två kandidater som ersattes före aktivering.

## Orsak och ändring

Servern hade 4,12 GB ledigt mot uppskattat behov 15,42 GB. Backupen roterade
gamla kopior först efter att en ny stor kopia hade lyckats. Vid platsbrist
kom den därför aldrig fram till sin egen städning. Därtill saknades en
sammanhängande livscykel för gamla prisartefakter, källpayloads och
releasebackuper.

Den gemensamma retentionen kör före utrymmeskontrollen, vid schedulerstart
och via befintliga backup-/refreshjobb. Den använder ordinarie driftlås.
Policy, återställningsgolv och undantag finns i
[storage-maintenance.md](../storage-maintenance.md).

- `e9dbdbf`: begränsar egna backup-, pris-, rapport- och temporärfiler.
- `06c48dd`: rensar inaktiva källpayloads och kommunala försök med bevarad
  aktiv data, LKG, publicerad härkomst, fältbevis och importmetadata.
- `329991a`, `35afef0`: gemensamma roterande releasebackuper, platta
  slutbilder och retention av egna avslutade appimages/byggcache.
- `8f9221e`: exakt verifiering även när en äldre Pythonfil har CRLF.
- `928d6d9`: testernas temporärdata ligger på arbetskopians disk.

Ändringarna är oberoende av receptskalningen. Kostnadsrättningen och den
delade cachens svaga ägarreferenser hör till
[skalningsgranskningen på arbetsgrenen](https://github.com/ossebosse/smako/blob/review/recipe-scaling-20261020/docs/reviews/recipe-scaling-review-20261020.md).

## Genomförd serveråtgärd

Under driftlåset togs 83 357 422 659 byte bort efter skrivskyddad inventering
med samma urval: åtta gamla dagsbackuper och 297 orefererade prisartefakter.
Alla aktiva prisfiler och tre dagsbackuper bevarades; de två senaste
hashverifierades före borttagning. Inga käll-/användardatabaser, kommunala
försök eller Dockerimages rensades av den körningen.

Efterkontroll 10:04 UTC: 94 192 029 696 byte ledigt, readiness 200 och samma
publicerade/laddade prismanifest. Senare läsning 10:43 UTC visade
86 628 896 768 byte ledigt, fortfarande över behovet 15 423 263 244 byte.
Normal pågående drift gör att ledigt utrymme varierar. Coop hade en
befintlig åldersvarning; de kvalificerade baspriserna var fortsatt användbara.

Detta är ett genomfört enstaka underhåll. Det bevisar inte att periodiska
hookar eller utökad källretention redan kör i den gamla schedulern.

## Verifiering

Fyra avgränsade offlinekörningar passerade:

- 93 PASS, 1 SKIP: käll-/kommunretention, backup, driftkontrakt,
  diagnostik och berörda ICA-jobb.
- 78 PASS, 1 SKIP: slutliga retentionsfall, backup/restore av partiellt
  godkända källor, kopierad databas, imageurval, paketering och
  generationssökningens oberoende startpunkter.
- 19 PASS, 1 SKIP: releasekonfiguration, imageurval och paketering.
- 21 PASS, 1 SKIP: paketeringens slutliga radslutskontroll, negativa
  härkomstfall och releasekonfiguration.

Windows saknar tillstånd för testets symlänk respektive Linux-Dockerprovet.
POSIX-skydden verifierades dessutom med en liten temporär fixtur i befintlig
Linuxruntime. Ruff och compileall passerade.

CI för `35afef0`:
[full Linuxkörning](https://github.com/ossebosse/smako/actions/runs/39410311242).
**2 862 PASS, 10 kända XFAIL, 53 SKIP**, inklusive webbläsare och Ruff.
Dockerprovet och POSIX-proven passerar där; de är inte bland de 53 skippen.
Antalen är räknade från pytest-progressen eftersom dubbla `-q` utelämnar
totalsammanfattningen. Efter denna kodversion tillkommer bara den separat
provade radslutshanteringen i paketeraren.

Den separat integrerade lagringskoden `d9f8dbf` på main har också
[grön full CI](https://github.com/ossebosse/smako/actions/runs/39411817580):
**2 836 PASS, 10 kända XFAIL, 53 SKIP**, inklusive webbläsare och Dockerprovet.
Alla drift-/releasefiler är hashidentiska med de granskade filerna på
skalningsgrenen. Efter detta ändras endast dokumentation.

Slutkandidatens egen Linuxruntime klarar dessutom **26 PASS, 0 SKIP** för
backup/restore, käll-/kommunretention, avbruten städning, skyddade referenser
och driftlåset. Provet använder temporära fixturer i en skrivskyddad
container utan nät eller produktionsvolymer, med 768 MiB minnesgräns.
Pytest tillfördes som tillfällig testkod i tmpfs; inget installerades i
imagen eller på servern. Kandidatens egna servicemoduler användes.

## Aktivering och kvarvarande avgränsning

### Verifierad scheduleraktivering 15:37 UTC

`source-ops-52c7d8291bb7` aktiverades 2026-10-20 15:37:12 UTC med image
`sha256:9611e23f2ee6ef6360ccff05889262240024fd1791b94bcfdd20d0c27f4f525e`.
Den enda Compose-ändringen är schedulerns image och BUILD_ID.
Cronfilen och mountarna är identiska. Appens och proxyns containeridentiteter
är oförändrade. Inga ordinarie källjobb avbröts.

Backup `20261020T144738Z` är komplett och verifierad. Alla tidigare 302
planrevisioner och 113 privata tillståndsrader finns både i backupen och i
den levande databasen. Alla aktiva prismanifest är byteidentiska.
Fingeravtryck för alla kolumner i `catalog_snapshots` utom `metrics`
(där retentionsmarkeringen läggs till), samt hela `raw_snapshots` och `collector_runs`, är
oförändrade. Importidentiteter och observationstider har alltså bevarats.

Den stora databasbackupens integritets-/relationskontroll tog 1 831,95
sekunder i den tillfälliga containern. Under verifieringen höjdes just dess
minnesgräns från 2 till 4 GiB för filcache, efter kontroll av 5 699 436 544
byte tillgängligt RAM. CPU-gränsen förblev 1. Containern var konfigurerad
med `--rm`; detta ändrade inte appens eller schedulerns resurskonfiguration.

De två uttryckligen ersatta kandidatbilderna togs därefter bort under
driftlåset. Aktiv image och återställningsbasen bevarades. Oanvänd
BuildKit-cache roterades med budgeten 2 GB. Efterkontroll 15:39:17 UTC:

- App, scheduler och proxy kör, med noll omstarter och `OOMKilled=false`.
- Schedulerns PID 1 är `cron`; loggrotation är fem filer à 10 MB.
- Tre dagsbackuper, totalt 24 716 243 845 byte, inklusive den nya kopian.
- 88 206 032 896 byte ledigt på serverns datadisk.

Efterkontrollen via `smako_ops.py status` och `municipalities` passerade:
readiness 200 i Lund och Malmö, identiska publicerade/laddade manifest och
alla 14 obligatoriska kontexter (5 + 9) kvalificerade med användbara baspriser,
publicerade och laddade. Coops `STALE` och Willys `AGING` är kvarvarande
åldersvarningar; de har inte dolts genom ändrade tider. Appdiagnostiken
15:38:56 UTC gav inga aktuella 5xx-mätposter. Windowsjobbet var
igång vid statusläsningen (`last_result=267009`); aktiveringen bevisar inte
en ny reläleverans. Senaste lästa kvitton är från 18 respektive 19 oktober,
utan väntande kvalificerad leverans.

Två sekventiella publika API-prov med nya syntetiska gästidentiteter passerade:

| Kommun | HTTP | Tid från POST till färdig plan | Betald korg |
| --- | ---: | ---: | ---: |
| Lund | 201 | 75,34 s | 550,13 kr |
| Malmö | 201 | 77,52 s | 553,65 kr |

Båda gav fem kompletta recept för fyra portioner, högst två tillåtna
butiker inom vald radie, godkänd korgrevision utan mängdunderskott eller
okända mängder, noll liveanrop till butikskällor och identisk återläsning
av den sparade planen. Appens BUILD_ID var fortsatt
`app-bac0fc15ca9a-512ef3ea`. Detta är fungerande efterkontroller, inte en
fryst jämförelse av algoritmens pris eller svarstid; appens sökning och
RAM-cache har inte aktiverats från utkast-PR #4.

Privata kvitton finns under
`.local/review-scaling-20261020/storage-release-v4/` och motsvarande
serverkatalog, särskilt `activation-success.json`,
`activation-maintenance-applied.private.json`, `postactivation-health.json`
och `obsolete-candidates-cleanup.json`. Lokalt finns även
`storage-http-evidence-all.json`, `storage-status-after.private.json` och
`storage-municipalities-after.private.json` i den överordnade evidenskatalogen.

### Genomförd utökad städning under aktiveringslåset

Det ordinarie Malmö-jobbet avslutades innan aktiveringen tog driftlåset
cirka 14:45 UTC. En ny komplett kontroll visade ready 200,
överensstämmande publicerat/laddat prismanifest och 81 512 042 496 byte ledigt.
Förhandsurvalet och den faktiska körningen gav samma filvolym:

| Typ | Genomfört urval | Borttagna byte |
| --- | ---: | ---: |
| Orefererade prisartefakter | 5 | 744 098 006 |
| Källhistorik | 32 snapshots, 11 921 råfiler | 570 675 842 |
| Kommunala försök | 79 poster | 1 088 141 475 |
| Totalt | | 2 402 915 323 |

Kvittot har `status=complete`, `applied=true` och observationstid
2026-10-20 14:47:38 UTC. Tre dagsbackuper behölls före den nya backupen;
två var fullständigt hashverifierade. SQLite har dessutom 420 208 640 byte
lediga sidor som kan återanvändas; detta är inte ytterligare frigjort
filsystemsutrymme. Den första källretentionen tog 839,51 sekunder under
driftlåset, med 2 GiB/1 CPU som processgräns. Alla 32 transaktioner och
råfilsstädningens framdrift kontrollerades.

Privat kvitto:
`.local/review-scaling-20261020/storage-maintenance-applied-pending-activation.private.json`.
Schedulerbytet och efterkontrollerna redovisas ovan.

### Slutligt prov av hela targetinventeringen

Efter indexförberedelsen visade det större provet ytterligare upprepning:
den skrivskyddade råfilsinventeringen gjorde om referensfrågorna för samma
snapshot i varje sidgrupp. Cirka 1,17 TB logiska läsningar observerades.
Vår inventeringscontainer stoppades före källradering, ny backup och byte.
De tre korrekt förberedda indexen behölls.

`52c7d8291bb7` använder en SQLite-cachebudget på 128 MiB och kontrollerar
varje snapshots relationer en gång per råfilsfas i förhandsvisningen.
Vid faktisk tillämpning behålls de färska kontrollerna för varje grupp och
skrivtransaktion. Ingen kvalificering eller referensregel mjukas upp.

Ett direkt skrivskyddat prov med denna kod och det ordinarie driftlåset
slutfördes mot target. Observation 14:06:59 UTC:

| Typ | Föreslaget urval | Byte |
| --- | ---: | ---: |
| Orefererade prisartefakter | 4 | 652 101 400 |
| Källhistorik | 32 snapshots, 11 921 råfiler | 570 675 842 |
| Kommunala försök | 77 poster | 1 072 292 539 |
| Totalt | | 2 295 069 781 |

Tre dagsbackuper bevarades. Provet tog inte bort några payloads.
De två första gruppernas relationella kontroller tog 28,69 respektive
9,95 sekunder; efterföljande unika grupper tog under två sekunder vardera.
Detta är observerade fasvärden, inte en garanti för hela underhållstiden.
Privat urvalsbevis: `.local/review-scaling-20261020/retention-probe-v4.json`.

Elva riktade källretentionsprov passerar efter uppföljningen, inklusive
ett fall med 201 råfiler för samma snapshot. Den slutliga imagen klarar
**31 PASS, 0 SKIP** i isolerad Linuxruntime med 768 MiB och utan nät eller
produktionsvolymer. Den föregående breda rättningen har grön full CI,
**2 840 PASS, 10 kända XFAIL, 53 SKIP**:
[CI för 90bfde3](https://github.com/ossebosse/smako/actions/runs/39433033585).
Den slutliga koden `52c7d82` har också
[grön full CI](https://github.com/ossebosse/smako/actions/runs/39436796990):
**2 841 PASS, 10 kända XFAIL, 53 SKIP**.

Slutkandidat:

- Image: `sha256:9611e23f2ee6ef6360ccff05889262240024fd1791b94bcfdd20d0c27f4f525e`.
- BUILD_ID: `source-ops-52c7d8291bb7`.
- Paket-SHA: `be76c69b684e5f6381680f1d1dde036abea0d1f54c0252dd5f489a735305e47b`.
- Tio ändrade runtimefiler och 623 hashidentiska; exakt konfiguration,
  två lager och 2 112 745 062 byte.
- Privat underlag: `.local/review-scaling-20261020/storage-release-v4/`
  och `/opt/smako/evidence/storage-maintenance-52c7d8291bb7/`.

De två tidigare kandidaterna är märkta `superseded_before_activation` i sina
respektive serverkataloger och ska inte aktiveras.

### Fördjupad targetkontroll efter godkännande

Användaren godkände scheduleraktiveringen. Driftkontrollen 13:14 UTC var
komplett, med ready 200 och samma publicerade/laddade prismanifest. Det
ordinarie källjobbet fick avslutas innan aktiveringsarbetaren tog driftlåset.
En ny kontroll under låset visade 89 105 842 176 byte ledigt.

Den skrivskyddade inventeringen i kandidat `8f9221e168d8` avslöjade ett
prestandafel: referensfrågorna läste hela historiken och skulle återupprepas
under varje snapshots skrivtransaktion. Efter drygt sju minuter hade
processen läst cirka 101,6 GB logiskt och 30,7 GB från disk. Vår exakt
identifierade inventeringscontainer stoppades; exit 137 kom från det
avsiktliga stoppet, inte en belagd OOM. Driftlåset frigjordes. Ingen
källretention, ny backup eller scheduleraktivering hann köras.

Rättning `90bfde350569` avgränsar relationella frågor till kandidatgrupper
och en snapshot vid skrivkontrollen. Tre ägda index stöder prisers
source-product-referenser, kampanjers price-observation-referenser och
råfilers sökvägar. Index skapas idempotent vid tillämpning; oförenliga
indexdefinitioner avvisas. Vid första aktivering förbereds de under samma
driftlås efter kontroll av minst två hashverifierade återställningskopior.
Ingen källobservation, prisrad eller tid ändras av indexförberedelsen.

Rättningen skyddar också relationer mellan snapshots som annars skulle
ändras genom `SET NULL`. Återupptagen råfilsstädning kontrollerar aktuella
referenser, och kandidat-/råfilsrader läses i små grupper.

29 riktade Windowsprov passerade, med ett känt symlänks-skip. Den nya
slutkandidatens egen Linuxruntime klarar **30 PASS, 0 SKIP**, med 768 MiB,
utan nät eller produktionsvolymer. Prestandaregressionen använder 50 000
ovidkommande historikposter per tabell och en begränsad budget av SQLite-
instruktioner. Ruff och compileall passerar.

Ersättningskandidat:

- Image: `sha256:6cb2dab0e9cc2b904bab85b4a960107f681dd58e6c5d2205c8279b3f8bfb3095`.
- BUILD_ID: `source-ops-90bfde350569`.
- Paket-SHA: `f22d35765377796ff65e0749ab5361a1d856f2d81745673335774e8540518f9c`.
- Tio ändrade runtimefiler och 623 hashidentiska; exakt verifierad
  imagekonfiguration, två lager, 2 112 744 265 byte.
- Privat underlag: `.local/review-scaling-20261020/storage-release-v3/`
  och `/opt/smako/evidence/storage-maintenance-90bfde350569/`.

Även denna mellanversion ersattes före aktivering. Både dess image och den
äldre kandidaten nedan har tagits bort. Den slutliga aktiveringen av
`52c7d8291bb7` och efterkontrollerna redovisas ovan.

### Tidigare byggunderlag, före targetinventeringen

Schedulerkandidaten paketeras med exakt granskade ändringar i tio filer på
den aktiva basen `c6607a095018`. Övrig runtime ska vara hashidentisk.
Privat slutunderlag finns i `.local/review-scaling-20261020/storage-release-v2/`.
En inledande byggstart avbröts före skrivning eftersom RAM-reserven var för
liten. När marginalen återkom upptäckte originalkontrollen CRLF/LF-skillnaden
i en fil; inga andra innehållsskillnader fanns mot dess Git-bas. Slutpaketet
verifierar den faktiska originalfilens hash innan exakt granskad kod skrivs.

Den då slutliga kandidaten `8f9221e` byggdes och verifierades, men aktiverades
aldrig. Den är senare ersatt och borttagen:

- Image: `sha256:c54f949d591c1d4cc2c48698ed5cff79babdde12faac9498e0e1f6805403394c`.
- Tag: `smako-storage:storage-maintenance-8f9221e168d8`.
- Image-BUILD_ID: `source-ops-8f9221e168d8`.
- Paket-SHA: `b69a70368d1c687d68db4c74b88e58bda20f03bdaf30f64f8a60d07aabb28cee`.
- Exakt tio ändrade runtimefiler; **623 övriga filer hashidentiska**.
- Slutbildens konfiguration är exakt som förväntad; berörda moduler går att
  importera i skrivskyddad container utan nät.
- **Två lager**, jämfört med basbildens 199; storlek 2 112 734 269 byte.
- Serverkvitto: `/opt/smako/evidence/storage-maintenance-8f9221e168d8/candidate.json`.

Förnyad inventering av källhistoriken sköts upp eftersom ordinarie driftlås
var upptaget. Inget prisjobb avbröts. Före aktivering krävs färsk driftstatus,
ledigt driftlås, backup och kontroll att samma bas fortfarande kör. Bytet ska
endast ändra scheduler-image/BUILD_ID; app, schema, volymer och övrig miljö
bevaras. Efteråt verifieras underhållskvitto, aktuella priser, readiness och
bevarade användardata. Återgång sker med föregående image, aldrig äldre DB.

Sista separata läsning 11:09 UTC: HTTP 200/ready i både Lund och Malmö,
oförändrad appversion och 82 913 460 224 byte ledigt. Den samlade
`smako_ops status`-läsningen nådde däremot sin 90-sekundersgräns vid
11:03-kontrollen och rapporterade serverdelen som **unknown**.
Direkt readiness ersätter inte den saknade fullständiga driftobservationen.

Vid denna tidigare läsning hade ingen app- eller scheduleraktivering,
ny timer eller ändring av Windowsuppgiften genomförts.
Då körde scheduler `hemkop-context-scheduler-c6607a095018`
och app `app-bac0fc15ca9a-512ef3ea`.

### Fortsatt policyavgränsning

Små spårbarhetsmetadata och användarskapade planer behålls. Okända historiska
operatörsarkiv, oregistrerade images och väntande releasekandidater raderas
inte automatiskt. Den nya policyn gäller de identifierade, ägda
driftartefakterna; den är inte ett löfte om konstant total lagring oavsett
datamängd och användning.
