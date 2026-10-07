# VÄNTAR PÅ EXAKT OPERATÖRSÅTGÄRD

Kontroller 7 oktober 2026 kl. 20:38–21:25 UTC. Endast driftåterställning;
ingen ny apprelease, sökoptimering, prisinsamling eller Git-push.

Slutkontroll 21:25 UTC: fortfarande rätt dd12, kompletta recept på,
`/ready` 503 och 0 byte tillgängligt på serverns datavolym. Ingen radering,
import, publicering eller reload har utförts. Inga nya prisanrop av oss.

| Värd/volym | Ledigt före | Ledigt efter arkiv och återställningsprov |
| --- | ---: | ---: |
| Windows C: | 6 638 108 672 byte | 6 629 289 984 byte |
| Windows D: | 687 617 093 632 byte | 664 460 079 104 byte |
| Server `/dev/vda1` | 0 byte | 0 byte |

D:-skillnaden omfattar arkivet, den fulla återställningskopian och evidens.
Serverns original är kvar. Ingen kvarlämnad egen verifieringsprocess eller
paus; administratörsregistrering och exakt raderingsgodkännande väntar.

## Operatörssteg: registrera D:-reläet

Kör i PowerShell 7 **som administratör**:

```powershell
& 'C:\Users\ossia\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe' -NoProfile -NonInteractive -File 'D:\Projects\Smako\scripts\activate_willys_storage_fix.ps1' -Apply
```

Verifierad PowerShell-version 7.6.5.500. Skript SHA-256:
`53be1b7467d1e9f1c223a31696af2a36da1ed0cebe2aac99406619bcd399ef8a`.
Skriptet passerade läsande förkontroll av alla 625 paketfiler och exakt
nuvarande uppgifts-XML. Det vägrar vid ändrad definition. Endast Arguments
samt WorkingDirectory byts till installerade fe795e5b04f5. Nya starter
spärras kort och återaktiveras i finally; befintliga två lås respekteras.
Ingen insamling startas. Övrig återläst XML ska vara oförändrad.

Uppgiften använder ännu bdc9. Konto ossia, S4U/Limited, pinnad PowerShell,
IgnoreNew, tre timmars körgräns och 01:30/09:30/17:30 bevaras. Installerad
fe795e5b04f5 är verifierad men ännu inte faktiskt körd under S4U i denna etapp.
Ingen automatisk elevation, ACL- eller execution-policy-ändring.

## Utrymme och klassning

- Windows C: 6 638 108 672 byte ledigt; D: 687 617 093 632 byte vid start.
- Server `cloud-server-10639692`, `/dev/vda1`: 415 381 426 176 byte totalt,
  **0 byte tillgängligt**, 4 % inoder använda. Samma filsystem för verkliga
  inbox-, rådata-, grocery-, plan- och prisvägar. D: är en annan värd/volym.
- `/var/tmp`: 136 588 546 048 allokerade byte, huvudsakligen historiska
  testmiljöer. `/var/tmp/smako-repo-release-20260929`: 63 688 630 272 byte.
  Klass C tills en exakt arkiverad delmängd har godkänts.
- `/srv/smako/backups`: 60 942 983 168 allokerade byte; skyddat, klass A.
  `/srv/smako/data`: 27 284 963 328 byte; skyddat, klass A.
- `/opt/smako/evidence`: 16 945 647 616 byte; bevarat underlag, klass A här.
- Faktisk Docker/containerd-lagring: cirka 164,7 GB i `/var/lib/containerd`,
  Docker-metadata/loggar cirka 73 MB i `/var/lib/docker`. Docker rapporterar
  delade image-/bygglager; dessa summeras inte som oberoende frigörbara byte.
  39 skrivlager tillsammans cirka 1,23 MB, alltså inte den stora posten.
  Klassning blandad A/C; ingen image, byggcache eller intern overlay är
  vald för borttagning. Aktiva och delade lager bevaras.
- Läsprovet för öppna borttagna filer visade systembibliotek och memfd,
  inget stort Smako-objekt i det avgränsade utdraget. Ingen process stoppad.

Samma sex logiska områden inventerade 09:22 och 20:48 UTC hade exakt samma
filantal och byteantal. Historisk tillväxt före dessa mätningar är okänd;
Willys får inte tillskrivas den utan bevis.

Tidigare godkänt arkiv över tolv byggmappar har hashverifierats igen.
Elva servervägar saknas; `build-b6505868b1de` finns nu. Det objektet tas
inte bort på antagandet att det fortfarande är samma arkiverade innehåll.
Inget nytt objekt har raderats med det äldre godkännandet.

## Begränsat nytt arkivförslag

Nio exakta objekt listas i ARCHIVE-PROPOSAL.md och STATUS.json. De är
inaktiva testkopior av grocery, rådata och prisartefakter. Planfiler,
privata konfigurationsfiler, köer, kvitton, produktionsdata och paket ingår
inte. Ingen container, även stoppad, har en mount som överlappar målen;
inga öppna fil-/cwd-referenser hittades. Aktuell driftkonfiguration saknar
referenser till dem. Äldre testskript kan behöva återställa arkivet för
att köras igen; arkivet bevarar deras testunderlag.

Arkivet är överfört direkt till skyddad D:-lagring (ärvd åtkomst endast ossia
samt SYSTEM), utan stor mellanfil på server eller C:. GNU tar bevarar
rättigheter, numeriska ägare och ACL/xattr-metadata. Samtliga 89 550
arkiverade filer matchar originalens SHA-256, storlek och UID/GID/mode.
Hela innehållet har återställts på D: med rätt filantal och storlek.
Ytterligare SHA-256-kontroll av återställda filer passerade för 39 532 filer,
inklusive samtliga fyra databaser. Den extra kontrollens återstående filer
kontrollerades inte; ingen full SHA-kontroll av hela återställningsmappen
påstås. De kontrollerade avbrotten/omstarterna gäller endast den egna lokala
verifieraren och finns i arkivevidensen. Inget hashfel har observerats.
Unixidentiteter tillämpas inte som Windowskonton vid NTFS-provet.
Ingen radering är godkänd eller utförd i denna etapp.

Mottagarens ordinarie förkontroll, UID 10001, kräver 7 521 539 842 byte
plus 536 870 912 byte reserv = **8 058 410 754 byte**. Grocery med journal
är 3 500 412 928 byte; största prisfil 92 584 833 byte. Arkivförslaget
skulle även ge utrymme utöver nästa ungefär 3,5 GB backup, men är ingen
obegränsad retentionlösning. Frigjorda byte ska mätas efter godkänd åtgärd.

## Bdc9-körningen och D:-vägar

17:30-körningen är avslutad, Schemaläggaren rapporterar slutkod 0.
Reläloggen slutar vid `collection_start`; progress anger 600 av 2 100
anrop och `collecting`. Inget nytt färdigt paket, `task_end` eller
`task_success` finns. Detta är **inte** verifierad lyckad körning.
TaskScheduler Operational-loggen är avstängd, så exakt avslutsorsak kan
inte beläggas där. Ingen logginställning ändrad.

Råsvar, SQLite samt WAL/SHM finns i den befintliga D:-arbetsytan,
`D:\smako-local-relay\scopes\municipality-1281`.
Sista kvalificerade paket är 8f4be22e8b594d0ea09c3e3d783564fa från 6 oktober;
sista publiceringskvittot är fortfarande från 4 oktober. Paketets ordinarie
48-timmarsvalidering passerade i denna etapp med oförändrad SHA-256
`1e4b3036ac09bd25b0d80f47502c0f40d0fa851b5d7da69b13457e4e8b47d1ab`.
Observationerna når 48 timmar den 8 oktober 07:31 UTC. Automatisk återupptagning
har en separat oförändrad 24-timmarsgräns; en kontrollerad återleverans
kräver ny aktuell validering och ordinarie slutkvittens. Ingen artefakt
har återlevererats i denna etapp. Fe-paketets verkliga TEMP/TMP- och
barnprocessprov via Scheduler återstår tills administratörsregistreringen
är genomförd. Windows globala temporärkataloger ändras inte.

## Faktiskt serverat underlag

Rätt dd12-image `c8362751b13a`, BUILD_ID `status-reconnect-dd12cc80e98c`,
kompletta recept på. `/health` 200, `/ready` 503, PlanStore
`SQLITE_IOERR_SHMSIZE`. Aktivt manifest och processens status pekar på
`price-universe:387cc368662cc45b3ee4714aaf57ed42e4a6ff1123a814d7fb62e25f5ead80e9`.
Prisartefaktens hash och alla 2 236 råreferenser från dess 19 snapshots
är verifierade. Råfilerna finns under produktionens ordinarie rårot;
arkivförslagets testkopior behövs inte för denna aktiva råfilkedja.

Åldrar vid 20:40:59 UTC, autentiska observationer:

| Bas | Äldsta observation UTC | Ålder | Snapshot | Serving |
| --- | --- | ---: | --- | --- |
| Coop Online Syd | 2026-10-05T10:30:54.804399Z | 58.17 h | `ff6e64a1bd9e435c9b9178e8aebec3f2` | STALE |
| Hemköp Brunnshög | 2026-10-05T01:01:52.060296Z | 67.65 h | `07e930083562494c8e787094c85d4098` | STALE |
| Hemköp Karhögstorg | 2026-10-05T00:46:18.267865Z | 67.91 h | `645904c1548549119c0e7892c36dd3ab` | STALE |
| Willys Lund | 2026-10-04T15:31:05.108770Z | 77.17 h | `5ddb11e6ddd54fe9ad7c75a6a06e52bf` | STALE |
| Willys Lund Nova | 2026-10-04T15:49:42.410373Z | 76.85 h | `5ddb11e6ddd54fe9ad7c75a6a06e52bf` | STALE |

Samtliga fem obligatoriska kontext-ID:n matchar processens krav.
36/48-timmarsgränserna gäller. Inga aktuella priser har publicerats.

## Återstående driftkedja och scheman

1. Administratörsregistrering och faktiskt återläst uppgift; därefter ett
   kontrollerat Scheduler-prov med befintlig lagringsmarkör, utan prisanrop.
2. Godkänd exakt arkivradering, ny kapacitetsmätning och ordinarie
   operationslås. Befintliga mottagar-/importstatusar inventeras först.
3. Giltig artefakt återanvänds; annars ordinarie behovsstyrd hämtning.
   Samordna alla fem baser, följ hash genom import/publicering/manifest/kvitto.
4. Publikt och personligt knappflöde, audit, sparad GET, omräkning,
   revisioner och ägarisolering samt omedelbar `not_due`-kontroll.

Inga nya menyprov körda: serverlagringen och fem baser blockerar dem.
Ingen reload, import eller ny kvittens kan redovisas som lyckad ännu.
Windows-uppgiften är Ready/Enabled, nästa start 8 oktober 01:30 svensk tid.
Serverns återlästa cron kör behovskontroll var 15:e minut och backup 02:47
Europe/Stockholm. Vid slutkontrollen är nästa serverkontroll 7 oktober 23:30 svensk tid,
nästa Windows-start 8 oktober 01:30 och nästa backup 8 oktober 02:47.
Ingen framtida framgång påstås. Inga scheman eller pauser har ändrats av oss.

Stora råbevis och privata tillstånd ligger utanför Git på D: under
`.local/drift-restoration-20261007/`. Ingen ny måltidsrelease eller Git-push.
