# Självstädande lagring och uppdateringar, 2026-10-20

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

Tre avgränsade offlinekörningar passerade:

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

Schedulerkandidaten paketeras med exakt granskade ändringar i tio filer på
den aktiva basen `c6607a095018`. Övrig runtime ska vara hashidentisk.
Privat slutunderlag finns i `.local/review-scaling-20261020/storage-release-v2/`.
En inledande byggstart avbröts före skrivning eftersom RAM-reserven var för
liten. När marginalen återkom upptäckte originalkontrollen CRLF/LF-skillnaden
i en fil; inga andra innehållsskillnader fanns mot dess Git-bas. Slutpaketet
verifierar den faktiska originalfilens hash innan exakt granskad kod skrivs.

Slutkandidat `8f9221e` är **byggd och verifierad, inte aktiverad**:

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

Ingen app- eller scheduleraktivering, ny timer eller ändring av
Windowsuppgiften ingår i den genomförda rensningen.
Aktiv scheduler är fortfarande `hemkop-context-scheduler-c6607a095018`
och app `app-bac0fc15ca9a-512ef3ea`.

Små spårbarhetsmetadata och användarskapade planer behålls. Okända historiska
operatörsarkiv, oregistrerade images och väntande releasekandidater raderas
inte automatiskt. Den nya policyn gäller de identifierade, ägda
driftartefakterna; den är inte ett löfte om konstant total lagring oavsett
datamängd och användning.
