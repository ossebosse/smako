# BLOCKERAD AV KONKRET KVARSTÅENDE FEL

Slutkontroll 8 oktober 2026, 12:44–12:47 UTC (14:44–14:47 svensk tid).
Windowsregistreringen och serverns kapacitetsbrist är åtgärdade. Ordinarie
återhämtning körd till slut, exit 1 kl. 12:37:43 UTC. Två nya Hemköp-stopp
hindrar en godkänd federation; `/ready` är 503. Ingen kvalitetskontroll sänkt.

## Nästa konkreta åtgärder

1. Karhögstorg 4123: granska och separat versionsbind stöd för de två nya
   booleska `hasPickingBaseStore`-fälten i `store_context`/`stores`. Isolerad
   replay av sparade fullständiga råsvar samt negativa schema-/kanalprov behövs.
   Inget nytt runtimepaket eller tillstånd att aktivera det finns i denna etapp.
   Avgränsad förberedelse har efterfrågats; inget användarsvar vid slutnoteringen.
2. Brunnshög 4224: ordinarie nytt fullständigt, sammanhängande underlag krävs.
   Produkt 101293703_ST har olika kampanjvillkor i två kategorisvar. Behåll
   konfliktspärren. En schemafix ensam löser inte denna andra blockerare.
3. Efter godkända baser: ordinarie rebuild/publicering/reload, idempotent
   återleverans av kvarvarande Willys-paket för slutkvitto och riktiga menyprov.

Full rå-/effektiv diff och separata orsaker: [BLOCKERS.md](BLOCKERS.md),
[HEMKOP-SCHEMA-BLOCKER.json](HEMKOP-SCHEMA-BLOCKER.json) och
[HEMKOP-CAMPAIGN-BLOCKER.json](HEMKOP-CAMPAIGN-BLOCKER.json).
Inget nytt Windowskommando behövs för registreringen.

## Utrymme och utförda åtgärder

Alla byte nedan är faktiskt uppmätta; GB avser decimal GB.

| Värd/volym | Före, byte | Efter, byte |
| --- | ---: | ---: |
| Windows C: | 5 762 117 632 | 5,528,621,056 |
| Windows D: | 664 353 087 488 | 664,303,230,976 |
| Server /dev/vda1 | 0 | 13,488,459,776 |

Serverns inbox, raw, grocery, planer och PriceUniverse ligger på samma
415 381 426 176-byte filsystem; inoder var 4 % använda. D: är separat Windowslagring.
Ingen C:-rensning gjord. D:-arkiv och full återställningskopia bevarade.

Användarens uttryckliga godkännande 8 oktober användes för fem arkiverade,
hash- och beroendekontrollerade testkataloger under
`/var/tmp/smako-repo-release-20260929/ops-verification/`:
`old-pair-data/raw`, `old-pair-data-v2/raw`,
`old-pair-data-v2/price-universes`, `rollback-data-v2/raw` och
`rollback-data-v2/price-universes`. Fyra testdatabaser lämnades kvar.

Befintligt skyddat arkiv på D: har SHA-256
`21946e544ae4b8605c0d5f52aa32fad3ae21869052716c7c00207441a5f5e3f4`.
89 550 originalfiler jämförda med arkivet; full återställning kontrollerad
för antal/storlek. Extra efterkontroll av återställda hashvärden omfattade
39 532 filer. Arkivet och samtliga originalhashar återverifierades före radering.
Ingen ny stor mellanfil på servern/C:. Metadata och skyddad privat evidens bevarade.

Dessutom togs 61 exakt identifierade oanvända, icke delade reproducerbara
Smako-byggcacheposter bort. Ingen bred prune, image- eller volymradering.
Fem tidigare försök med enbart rot-ID frigjorde 0 byte; det döljs inte.
Testkopior gav 8 737 947 648 byte; cache gav ytterligare cirka 5,27 GB,
inte verktygets nominella 7,481 GB. Topp ledigt var 14 007 619 584 byte.
Exakta vägar, ID:n och deltamätningar: [CLEANUP.json](CLEANUP.json).

Befintligt mottagarskydd krävde 7 521 539 842 byte + 536 870 912 reserv.
Tillfällig byggdatabas var cirka 3,55–3,61 GB; som lägst uppmätt omkring
9,87 GB fritt under den andra ombyggnaden. Ordinarie tempstädning återgav
utrymmet efter avslut. Inga aktiva temporärfiler togs bort av oss.
Skillnad topp→slut cirka 0,52 GB efter insamling; fördelningen mellan alla
skrivare är inte isolerat uppmätt. Framtida retention är separat: äldre
backupbestånd cirka 60,9 GB får granskas med referenser/dry-run, inte raderas
som följd av denna rapport. Ingen ny automatisk retention eller schemaläggning.

## Windows, paket och faktisk D:-användning

`Smako Willys Local Relay` är återläst med Arguments och WorkingDirectory
på `D:\smako-local-relay\releases\fe795e5b04f5`. Alla 625 paketfiler
matchar manifest. Paket `smako-windows-relay-fe795e5b04f5.zip`, SHA-256
`e0e0cd4923f6c05cb934f05c66f5532a07f5631b8b7341278d76036fcdc067c1`.
Konto ossia, S4U/Limited, pinnad PowerShell 7.6.5.500, IgnoreNew, PT3H,
StartWhenAvailable, WakeToRun och hela XML utom Actions är oförändrade.
Ingen omregistrering gjord av oss. [TASK.json](TASK.json) är kontroll under
körning; FINAL.json innehåller slutstatus Ready/Enabled och faktisk slutkod 1.

Kontrollerad Scheduler-start 11:02:55 UTC gav lagringsprov PASS i verklig
session 0 kl. 11:03:09. Förälder/barn skapade temp direkt på D:; inga
prisanrop. [STORAGE-PROBE.json](STORAGE-PROBE.json).
Den efterföljande kontrollerade starten 11:07:19 använde verkligen fe795;
slutkod 1 avser publiceringsfelet, inte den historiska bdc9-körningen.

Datatrot `D:\smako-local-relay\scopes\municipality-1281` är bevarad:
`runs/` råsvar/snapshots/lokal databas, `tmp/` process- och barntemp,
`completed/` paket/kö, `logs/`, last-qualified-source och last-success.
TEMP/TMP/TMPDIR/SQLITE_TMPDIR sätts processlokalt före barnen. Ingen global
TEMP-ändring eller fallback till C:. Privat konfiguration ligger utanför Git
på `D:\smako-local-relay\config\relay.json`.
Återleveransen skapade ingen ny lokal insamlingsdatabas; återanvända råsvar,
databas och paket låg redan på D:. Tidigare isolerade paketeringsprov gäller
oförändrad kod och räknas inte som nya liveprov.

## Hämtning, import och publicering

- Nattens **bdc9** hämtade 19 060 Willys-rader med 1 254 anrop. Paket
  `989f961ccfc64984a830de9584d437d5`, 3 977 155 byte, SHA-256
  `d53486fb8c90740ecb68901bb6a333148eed2a37aefe9bb84ed8958715686c98`.
  Råobservationer från 7 oktober 23:31 UTC. Morgonens transport misslyckades.
- **fe795** återlevererade samma giltiga paket. Lokal/mottagarvalidering,
  upload och import passerade. Exakt en import även i slutkontrollen:
  snapshot `72c524df46c34fe69af362158af38692`, promoted/active.
- Första ordinarie publiceringsförsöket slutade 11:30:47 med ValueError och
  refresh_not_usable; ingen reload. Kvitto och last-success är oförändrade,
  paketet finns fortfarande på D: med samma hash. Inget task_success fabricerat.
- Efterföljande ordinarie serveråterhämtning kördes kontrollerat under samma
  lås/appkonto. Coops första underlag föll på produktbortfall; dess befintliga
  fullcrawl-fallback gav 11 472 produkter och godkänt snapshot
  `0e91c5c39f9d490ba28a11af81c6a76b` kl. 12:02:42 UTC.
- Karhögstorg hämtades komplett (6 304 produkter, 20/20 kategorier) men
  rejected av effektiv schemadiff. Brunnshög blev ofullständig (15/20)
  på verklig kampanjkonflikt. HTTP-fel och rate limits var noll för båda.
- Ordinarie ombyggnad avslutades 12:37:43 med exit 1. Ingen partiell
  federation publicerad, ingen reload. Råfel och båda försöken bevarade.

Färska promoverade källor finns nu för Coop och båda Willys-kontexterna,
men **de är ännu inte betans serverade prisunderlag**. Aktuellt och laddat
manifest är fortfarande `price-universe:387cc368662cc45b3ee4714aaf57ed42e4a6ff1123a814d7fb62e25f5ead80e9`.
Artefakt SHA-256 `963cd15324de1925222d4958c5ee6b77e43d2baff83adf3fb95d8e89da951f50`
återkontrollerad; samma ID rapporteras av processen. Föregående råreferensprov
(2 236 hashvärden) återanvänds för oförändrat skyddat manifest, inte nykört.

## De fem baserna som faktiskt serveras

Åldrar vid 12:44:40 UTC. Observationstider är UTC. Alla är över 48 timmar.

| Bas | Äldsta observation | Ålder h | Snapshot | Serving |
| --- | --- | ---: | --- | --- |
| Coop Online Syd | 2026-10-05 10:30:54 | 74.23 | `ff6e64a1bd9e435c9b9178e8aebec3f2` | STALE |
| Hemköp Brunnshög | 2026-10-05 01:01:52 | 83.71 | `07e930083562494c8e787094c85d4098` | STALE |
| Hemköp Karhögstorg | 2026-10-05 00:46:18 | 83.97 | `645904c1548549119c0e7892c36dd3ab` | STALE |
| Willys Lund | 2026-10-04 15:31:05 | 93.23 | `5ddb11e6ddd54fe9ad7c75a6a06e52bf` | STALE |
| Willys Lund Nova | 2026-10-04 15:49:42 | 92.92 | `5ddb11e6ddd54fe9ad7c75a6a06e52bf` | STALE |

## App, användardata och menyprov

Samma dd12-container/image
`sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7`,
BUILD_ID `status-reconnect-dd12cc80e98c`, kompletta recept true.
Laddad JS SHA-256 `17311d27a3a50ec9e75415316ca8cc90d10c94ac85380b36a75a3541d1b7114e`.
`/health` 200, `/ready` 503; grocery och plan_store svarar ok efter frigörelsen.
216/216 revisionsrader och 61/61 privata tillståndsrader matchar tidigare
hashvärden. Inga gamla databaser återställda över nytt arbete.

Publik/personlig ny meny, inköpslista/audit, sparad GET och omräkning kunde
inte slutkvalificeras med användbart aktuellt underlag: obligatorisk federation
är spärrad. Inga lyckade menyprov påstås. Ingen sänkning av användarkrav eller
historisk replay som acceptans. Aktuell kontostatus är gästflöde/DATA_BLOCKED;
signerade kontosessioner har inte verifierats.

## Scheman och återförsök

Windows Ready/Enabled, nästa 8 oktober **17:30 svensk tid**, fortsatt
01:30/09:30/17:30. Serverns cron återläst: behovskontroll var 15:e minut,
backup 02:47 svensk tid. Inga pauser lämnade av oss, inga aktiva lås brutna.
12:45-ticken gav not_due, noll prisanrop: **på grund av befintlig backoff**,
inte därför att alla baser blivit färska. Global retry_at är 18:37:43 UTC,
vilket ger nästa möjliga cronåterhämtning omkring **20:45 svensk tid**.
Hemköps lokala retry_at 12:52:43 UTC överskrids av global backoff. Windows
17:30 kan separat pröva väntande leverans enligt befintligt kontrakt/lås.
Framtida utfall är inte verifierade; nästa lätta serverkontroll 15:00 svensk tid.

Ingen måltids-/sökaktivering, källkodrelease, Git-push eller policyändring.
Maskinläsbar slutstatus: [FINAL.json](FINAL.json). Privata stora råbevis finns
utanför Git i `.local/drift-restoration-20261008/` på D:.
