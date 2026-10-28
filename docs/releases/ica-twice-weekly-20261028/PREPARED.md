# ICA-baspriser och två insamlingsnätter: förberett, inte aktiverat

Senare status: [samlad serveraktivering](../beta-ica-recipes-20261028/ACTIVATED.md)
ersätter denna förberedelses aktuella driftstatus. Serverns app och scheduler
är nu bytta tillsammans med receptarbetet; Windowsregistreringen kräver
fortfarande administratör. Nedan bevaras granskningsläget 15:25 UTC.

Status 2026-10-28 15:25 UTC: implementationen är integrerad via
[PR #37](https://github.com/ossebosse/smako/pull/37), merge `49be2f6`.
Granskad kod och paketeringsreferens är `3ebff6ab6e33219c6fc9739adcbf93b9aeb0fc7e`.
**Serverns runtime, dess schema och Windowsuppgiften är fortfarande oförändrade.**

Ägarbeslutet är ICA-basprisinsamling via Primat och samtliga aktiverade bas-
och kampanjkällor natten mot måndag och torsdag. Starttid är 03:17 svensk tid.
Se [den gemensamma policyn](../../PRICE-COLLECTION.md). Begränsade källåterförsök
får starta inom samma tre timmar; lokala kampanjutgångar, publicering, laddning
och daglig backup fortsätter genom den befintliga arbetaren. Källtider,
verkliga kampanjdatum, 36/48-timmarsvarningar och kvalitetsgränser bevaras.

## Verifiering och paket

- Alla CI-delar passerade på den exakta kodreferensen:
  [körning 40710524709](https://github.com/ossebosse/smako/actions/runs/40710524709).
  Core 5:58, integration 5:56 och planner 8:58, följt av grön samlingskontroll.
- Riktade offlinegrupper: 43, 67 och 78 passerade prov; dessa urval överlappar.
  Nytt schemakontrakt har 15 prov, inklusive sommartid, samtliga kampanjplaner,
  saknad ICA-bas i aktiv artefakt och försenad Windowsstart. Separat sluturval
  med schemakontrakt och befintligt cron-kontrakt passerade också.
- Ruff, compileall och exakt patchmatchning mot de befintliga runtimefilerna
  passerade. Kandidatbildernas bygge och live Primat-verifiering återstår.
- Schedulerpaket: 10 avgränsade Pythonfiler ovanpå
  `sha256:9611e23f2ee6ef6360ccff05889262240024fd1791b94bcfdd20d0c27f4f525e`.
  Paketets SHA-256 är `a7706c52343b6f2373af3d5d9c8dc685439b71a72f7c49cb2dbb34a79e08aec4`.
- Apppaket: endast `grocery_data/app/services/freshness.py`, för sanningsenlig
  veckovis tidsprojektion, ovanpå
  `sha256:dc23ba03be3ca2370d28d6230d392160a63fb278a56f5b0171ebe91947713072`.
  Paketets SHA-256 är `6cfde89c5f151d7e0b754142b0d456d012e70531d6ca9e96e912940da4ae56fe`.
  Inga nya recept, planeringsalgoritmer eller beroenden paketeras i apppatchen.
- Windows fullpaket SHA-256:
  `dd3b88d3971de5217d0be9026085002a8f255895924b17ecc558eeb346d155a2`.
  Installerat separat i `D:\smako-local-relay\releases\3ebff6ab6e33`, med egna
  Python 3.12-beroenden från låsta lokala hjul. `pip check` och paketets
  integritets-/importkontroll passerade för samtliga 1 016 källfiler, utan
  insamling. Den aktiva uppgiften använder ännu `2464596b6f07`.

## Exakt återstående arbete

Serverns ordinarie refresh från 14:45 UTC höll fortsatt kernel-låset vid
15:25 UTC. Processen arbetade aktivt. Det avgränsade väntande försöket
avslutades med `lease_busy`; ingen konkurrerande insamling, backup, bildbyggnad
eller aktivering startades. Inga Primat-anrop gjordes i denna förberedelse.

Vid ledigt driftlås ska samma granskade paket verifieras som kandidatbilder,
med exakt fil-/konfigurationsjämförelse och isolerade planer mot Lund och
Malmö. En avgränsad Primat-kontroll är 49 anrop i det befintliga kontraktet.
Därefter krävs ordinarie verifierad backup, kontrollerat image-/miljöbyte,
oförändrade data/mountar, faktisk cronfil och ready för båda kommunerna.
Äldre produktionsdata får aldrig återställas som del av ett kodbyte.

Windows kräver administratörsrättighet för att ändra den befintliga
S4U-uppgiften. Den vanliga UAC-dialogen avbröts. Ingen uppgiftsändring
registrerades och ingen körning startades. Det versionsbundna
`deploy/scripts/set_price_collection_schedule.ps1` är förhandskontrollerat:
veckotrigger måndag/torsdag 03:17, ny verifierad reläversion och
`-CollectionCadence mon_thu`, med bevarat konto, transport och inställningar.

Privat återupptagningsunderlag finns i
`D:\Projects\Smako\.local\ica-twice-weekly`. `build_candidates.py` innehåller
det förberedda, låsta serverförfarandet; det är avslutat utan aktivering.
`activate_windows_admin.ps1` innehåller den konkreta Windowsändringen och
kontrollerar att uppgiften fortfarande motsvarar förhandsgranskningen.
Om runtime, uppgift eller kandidatunderlag har ändrats måste det granskas på nytt.
Publicera en separat aktiveringsjournal först efter bekräftat resultat.

## Aktuellt källstöd

Det befintliga registret har två fullständiga, exakt verifierade ICA-kontexter
i Lund: Clemenstorget `primat:ica:1004409` och Maxi Gunnesbo
`primat:ica:1088004`. Dessa måste fortfarande återvalideras mot aktuell Primat-
upplösning före produktimport. Övriga sju befintliga Primat-kopplingar i Lund
är erbjudandekontexter. Malmö saknar verifierade Primat-baspriskopplingar i
huvudregistret. Den egna kampanjkällan är separat och omfattar även andra
butiker. Ingen erbjudandekontext eller osäker butiksidentitet uppgraderas
automatiskt till baspris. Den nya aktiveringsflaggan inventerar och använder
bara den befintliga, kvalificerade baskontextvägen.
