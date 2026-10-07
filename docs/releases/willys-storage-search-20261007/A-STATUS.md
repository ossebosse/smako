# A – aktuell driftkontroll och lagringskandidat

Pågående arbete. **Prisflödet är ännu inte återställt.** Kontrollerat 7 oktober
2026 kl. 09:05 UTC, ingen appinstallation eller prisinsamling utförd i denna etapp.

Återkontroll **10:59:38 UTC**: fortfarande 0 byte tillgängligt på de verkliga
rådata-/pris-/databas-/planvolymerna, rätt dd12 och kompletta recept på,
`/health` 200, `/ready` 503, `SQLITE_IOERR_SHMSIZE`. Alla fem baserna är då
äldre än 48 timmar: Coop 48,48 h; Hemköp 57,96/58,22 h; Willys
67,48/67,17 h. Enbart Willys räcker därmed inte för återställd readiness.
Ordinarie återhämtning för övriga baser behövs också, med samma policy.
Willys har 10 217 respektive 8 647 aktiva rader från faktiskt
`source_snapshot_id=5ddb11e6ddd54fe9ad7c75a6a06e52bf`.
Den första probens tomma snapshot-lista berodde på fel fältnamn i
diagnostikskriptet (`snapshot_id`); råa observationstider och manifestets
hash var rätt. Den korrigerade proben och den ursprungliga finns båda kvar.
Ingen priskälla har anropats av dessa läskontroller.

## Verifierad drift

- Beta kör fortfarande dd12, image `c8362751b13a`, BUILD_ID
  `status-reconnect-dd12cc80e98c`, kompletta recept på.
- `/health` 200; `/ready` 503. Planlagringen svarar `SQLITE_IOERR_SHMSIZE`.
- Serverns verkliga inbox-, rådata-, databas-, pris- och planvolymer delar
  `/dev/vda1`: **0 byte tillgängligt**, även sett från appens datavägar.
  Tidigare 172 MB används inte som aktuell kapacitet.
- Windows: C: 2 655 670 272 byte, D: 694 419 279 872 byte ledigt vid första
  kontrollen. Senare lokala paketbyggen förbrukar eget utrymme på D:.
- Aktivt manifest `price-universe:387cc368662cc45b3ee4714aaf57ed42e4a6ff1123a814d7fb62e25f5ead80e9`,
  prisartefaktens hash verifierad. Åldrar vid samma kontroll:

| Obligatorisk kontext | Äldsta observation UTC | Ålder timmar |
| --- | --- | ---: |
| Coop `23eaae11c9661e68` | 5 okt 10:30:54 | 46,58 |
| Hemköp `3288e04edd97e349` | 5 okt 01:01:52 | 56,06 |
| Hemköp `756955d0e6e05f23` | 5 okt 00:46:18 | 56,32 |
| Willys Lund `383650ec6ff5a636` | 4 okt 15:31:05 | 65,57 |
| Willys Lund Nova `4a671428fc484e43` | 4 okt 15:49:42 | 65,26 |

Krav på 36/48 timmar och fem baser kvarstår. Nya planprov väntar på återställd
lagring och giltiga priser; inga misslyckade driftprov redovisas som PASS.

## Relä och bevarad kö

Faktisk uppgift `Smako Willys Local Relay`: ossia, S4U/Limited, pinnad
PowerShell, IgnoreNew, PT3H, 01:30/09:30/17:30. Befintlig arbetsyta är
`D:\smako-local-relay\scopes\municipality-1281`. Rådata, SQLite inklusive WAL,
normaliserade data, kö, kvitton och loggar låg redan här. Startskriptet saknade
styrning av TEMP/TMP, vilket är den rättade avvikelsen.

Senaste schemakörning 7 oktober 07:30 UTC slutade med exit 1 i transporten.
Detaljerat fjärrfel saknas där. Körningen 6 oktober hämtade 1 253 svar och
19 109 rader, levererade artefakten men mottagaren rapporterade att den inte
aktiverades. Tillgänglig logg belägger inte exakt var den historiska diskbristen
först slog till. Råa fel finns kvar.

Artefakten `8f4be22e8b594d0ea09c3e3d783564fa.smako-source` ligger kvar,
3 974 025 byte, SHA-256
`1e4b3036ac09bd25b0d80f47502c0f40d0fa851b5d7da69b13457e4e8b47d1ab`.
Observationer från 6 oktober 07:31 UTC. `last-success` avser fortfarande
4 oktober; kvalificering har inte förväxlats med publicering.
Automatisk återleverans har en befintlig 24-timmarsgräns; källans separata
48-timmarsvalidering och ordinarie behovsgräns har inte ändrats.

Konfiguration, uppgifts-XML, ACL, kvitton, loggar och kompletta köartefakter har
kopierats till D: under båda befintliga lokala låsen. Kökopiorna är hashkontrollerade.
3 797 filer inventerade, cirka 310 MB, inget flyttat eller raderat. Ingen aktiv
SQLite-fil har flyttats. Skyddat underlag ligger i
`.local/willys-storage-search-20261007/` utanför Git.

## Separat lagringsfix

Integrerad commit `813eadda8e2664db233c92fce4efa51760b25499`.
Ren reläcommit ovanpå bdc9: `fe795e5b04f5a5ff973b71bb9bcdd28ca8668ce2`.
Sex ändrade filer, ingen måltidskod. Den senare CLI-spärren för begränsad
läsåtergång har också bevarats. Paket:
`smako-windows-relay-fe795e5b04f5.zip`, SHA-256
`e0e0cd4923f6c05cb934f05c66f5532a07f5631b8b7341278d76036fcdc067c1`.
Installerat separat i `D:\smako-local-relay\releases\fe795e5b04f5`;
625 manifestfiler verifierade. Python 3.12.10 och samtliga installerade
beroendeversioner matchar bdc9. Gamla paketet är orört.

TEMP, TMP, TMPDIR och SQLITE_TMPDIR sätts till arbetsytans `tmp` innan
PowerShells processhantering och Python startar. Saknad arbetsyta eller
omdirigering via reparse point stoppas; inget systemomfattande miljöbyte.
Faktiska tempfiler i förälder och barn har verifierats interaktivt med paketet.
S4U-provet återstår.

Insamlingsmarginal: max(512 MiB, två gånger största bevarade körning) plus
512 MiB reserv. Största uppmätta körningen är 98 539 519 byte, varav
54 571 008 byte databas; cirka 44 MB rå-/mellanmaterial. Befintlig kö och
rådata är redan förbrukat diskutrymme och dubbeldebiteras inte. Under körning
kontrolleras dessutom utrymme var hundrade förfrågan. Paketeringen behåller
kontroll mot okomprimerad mängd, atomisk publicering och felsäker temporärfil.

Mottagarkontrollen körs med befintlig autentiserad UID 10001, före insamling,
leverans och import. Den summerar faktiskt berörda filer per filsystem och
reserverar utrymme för rådata, SQLite/journal, prisartefakt och leveransfil.
Den kan stoppa arbetet utan att konsumera kön. Det är en konservativ
förkontroll, inte en garanti mot senare skrivfel.

47 riktade Python-prov passerade, inklusive transportåterförsök, omstart med
väntande artefakt, idempotent import, lokala lås, barnprocessavslutning och
lagringsfel. Sju lagringsprov omkörda efter korrigering av databas-URL med
query-parametrar. Ruff och compileall passerade. Det är isolerade prov;
verklig ny leverans/import/publicering är ännu inte utförd.

## Konkreta blockerare

Återkontroll **13:08:17 UTC** från appens faktiska miljösökvägar: samma fyra
datavolymer har fortfarande 0 byte ledigt, dd12 och receptflaggan är oförändrade.
Windows 13:07:38 UTC: C: 436 301 824 byte, D: 688 816 566 272 byte ledigt.
Uppgiften är fortsatt Ready/Enabled med bdc9, S4U/Limited. Ingen återhämtning
eller S4U-körning med det nya paketet kan därför redovisas som genomförd.
En föregående direkt `df` mot en antagen värdvolymsökväg fick åtkomstfel;
den används inte som volymbevis. Den efterföljande proben läser appens
verkliga miljösökvägar inne i den körande containern.

Återkontroll 2026-10-07 12:00:50 UTC: samma servervolym har fortfarande
0 byte tillgängligt. Windows-uppgiften är fortsatt Ready och pekar på bdc9.
Ett separat [retentionförslag med läsinventering](RETENTION-DRY-RUN.md)
redovisar filantal och byte; inga objekt är godkända för radering.

1. Servern behöver ledigt utrymme. Ingen bred radering eller Docker-prune utförs.
2. Windows nekade `Set-ScheduledTask` med **Åtkomst nekad**. Hela uppgifts-XML
   är verifierat oförändrad; ordinarie starter är fortsatt aktiverade.
   Den färdiga, avgränsade ändringen finns i
   `.local/willys-storage-search-20261007/update_relay_task.ps1` för administratör.
   Den byter enbart Arguments/WorkingDirectory och jämför övrig XML.

Efter operatörsåtgärder: kontrollera faktisk definition, kör den engångsmarkerade
lagringsproben genom Scheduler, verifiera session 0 och D:-filer, och återuppta
befintlig leverans-/import-/publiceringsväg med aktuell giltighetskontroll.
Kontrollerad Scheduler-start ska redovisas som sådan. Ingen fler dygns
obevakad drift är bevisad. B utvecklas separat och får inte aktiveras.
