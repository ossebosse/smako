# Källvalidering, importmarginal och återkomstfix — 2026-10-10

**DRIFT ÅTERSTÄLLD OCH ÅTERKOMSTFIX AKTIVERAD.**

Slutkontroll 2026-10-10 10:04 UTC (12:04 svensk tid): `/ready` 200,
alla fem obligatoriska baser FRESH, publicerat och faktiskt laddat manifest lika.
Beta kör `return-session-205cd8ca0f31`; källprocessen `source-ops-04e47c691e0c`.
[Utförd aktivering och återgång](ACTIVATED.md). Ingen Git-push.

## Avgränsad källrättning

Runtime `04e47c691e0c6521f790422eaa8f0b836f21acbd`. Två schemafiler
transplanterade ovanpå den faktiska källimagen `ce326c1d7fcf`; ingen
konsument-/måltidskod ingår i källpaketet. Parserns kommersiella kontrakt
är oförändrat. Paketets fullständiga identiteter finns i SOURCE-PACKAGE.json.

- Willys: sex exakta image/thumbnail-textfält kan växla mellan string och
  null|string i katalogens aggregerade schema. Inga nya struktur-/prisfält
  undantas. Dessa bildfält läses inte av pris-/produktparsern.
- Hemköp: det redan semantiskt valfria hasPickingBaseStore får åter saknas på
  de två verifierade vägarna. Gruppen och storeId måste finnas. Ingen false
  fabriceras; true/null/fel typ och ändrad butiksbindning stoppas fortsatt.
- 71 riktade tester PASS, Ruff och compileall PASS. Tre autentiska
  schemafall FAIL före rättningen. Kompletta förekodsreplay återskapar stoppen
  för 19 108 Willys-, 5 132 Brunnshög- och 6 294 Karhögstorgsprodukter.
  Noll källanrop; råhashar och observationstider oförändrade.
- Samtliga tre kompletta replay passerar i leveransimagen (två CPU, 3 GiB,
  nätverk av). 30 534 produkters kommersiella och normaliserade data matchar
  förekoden fält för fält, bortsett från nya databas-ID:n/råreferens-ID:n.
  REPLAY-AFTER.json och SEMANTICS.json redovisar omfattningen.
- Källprocessen bytt under befintligt operationslås efter att pågående jobb
  avslutats. Endast scheduler.image och BUILD_ID ändrade. Appcontainer,
  mounts och övrig miljö bevarade. SOURCE-ACTIVATION.json binder utfallet.
- Båda Hemköpssnapshoten återspelade och promoverade på servern genom ordinarie
  CLI under lås, med oförändrade råhashar/tider och noll nätanrop. Ingen
  accept_schema_change eller global backoffradering. Kodversion/hash kontrollerad;
  parserkontraktets versionssträng oförändrad eftersom endast granskningen ändrats.
  Det generella repair-kommandots parsersträngsgate användes därför inte som
  bevis; den avgränsade körningen kontrollerade incident/signatur och leveranshash.

## Utrymme

Fyra uttryckligt inventerade inaktiva testkataloger arkiverades direkt till
skyddad D:-lagring. 15 687 poster, alla filhashar, mode/uid/gid/länkar och
återläsningsprov kontrollerade; aktiva mounts och öppna filreferenser
kontrollerades igen före borttagning. Stoppade historiska testcontainrar
behöver återställda testfiler om de ska återstartas.

Serverns lediga utrymme steg från 5 202 079 744 till 16 521 736 192 byte:
11 319 656 448 byte faktiskt frigjorda. Arkivet är 2 409 307 076 byte.
Detaljer och SHA-256 finns i ARCHIVE.json. Aktiv mottagare, databaser,
prisråfiler, användardata, köer, kvitton och releasebilder bevarades.
Ingen Docker-prune, ingen schema-/färskhetsändring.

Det befintliga kapacitetsskyddet behålls: två gånger DB/WAL/SHM, två gånger
aktiv prisartefakt och 512 MiB reserv. Vid start krävdes cirka 8,69 GB.
Den riktiga mottagarkontrollen (UID 10001) passerade efter arkivering:
8 511 371 010 byte arbetsutrymme + 536 870 912 byte reserv, mot
16 520 695 808 byte ledigt. Den inkluderar även kö och rådatamarginal.
Ledigt utrymme kontrolleras igen efter import/publicering och appbackup.

Den ordinarie 07:45-processens temporära source.sqlite3 tog 3 995 328 512
byte under byggsteget och frigjordes när jobbet avslutades. Detta var aktivt
arbetsutrymme och raderades inte manuellt.

## Återställd priskedja

Inga nya fullhämtningar behövdes. Coop behöll sitt godkända underlag från
9 oktober. Båda Hemköpsunderlagen återspelades från sina autentiska sparade
råsvar. Willys-paketet `05f37497fd1d…` återlevererades från kommunarbetsytans
completed-katalog på D:, med ursprungliga observationstider.

Manuell, kontrollerad Scheduler-start 07:56:55 UTC, inte bevis för flera dagars
framtida automatisk drift. Lokalt validerat 07:58:19, uppladdat 07:58:56,
importerat/promoverat 08:03:19, publicerat/laddat och kvitterat 08:15:33.
Task success 08:15:34. Samma artefakthash har **exakt en** promoverad import.
Den tidigare verkliga kapacitetsförlusten och misslyckade försöken bevaras.

Aktivt manifest:
`price-universe:50c0bb0e83de94803b9eb6d06576cbe653e29a5f5d7a43abc5af9117c721cd5a`.
Beständigt last-success binder samma hash, snapshot och manifest. IMPORT.json,
FINAL-STATUS.json och DEMAND-CHECK.json visar de olika stegen.

### Fem obligatoriska baser vid slutkontrollen

Alla tider nedan UTC; observationen är äldsta verkliga produktobservation i
respektive serverad baskontext, inte tid för replay eller rebuild.

| Bas | Observation | Ålder, timmar | Snapshot | Serving |
| --- | --- | ---: | --- | --- |
| Coop Online Syd | 2026-10-09T13:30:54.726697+00:00 | 20.553 | `8d1dba204e45414e96be4501fad38b2a` | FRESH, publicerad/laddad |
| Hemköp Brunnshög | 2026-10-09T14:16:48.180280+00:00 | 19.788 | `4f5bcff3f29845cea4a38298350d7597` | FRESH, publicerad/laddad |
| Hemköp Karhögstorg | 2026-10-09T14:01:23.074953+00:00 | 20.045 | `4ae441e96dba422db2b838ed86ac4d00` | FRESH, publicerad/laddad |
| Willys Lund | 2026-10-09T14:02:03.571083+00:00 | 20.034 | `432ae077c8354fd694539a8a88b6e5a9` | FRESH, publicerad/laddad |
| Willys Lund Nova | 2026-10-09T14:20:49.022948+00:00 | 19.721 | `432ae077c8354fd694539a8a88b6e5a9` | FRESH, publicerad/laddad |

Coop är online_fulfillment; Hemköp och Willys är respektive exakta online_store.
Kommun 1281, femkällorspolicy och 36/48 h-gränser är oförändrade. Readiness
anger fortfarande requires_attention för bredare underlag; det är inte ett
påstående att alla frivilliga källor är lika färska. De fem obligatoriska
baserna är verifierat färska och användbara.

### D:-relä och scheman

Relä fe795e5b04f5 är oförändrat. Befintliga rådata, SQLite/WAL, tmp, completed,
kö, kvitton och loggar ligger kvar under
`D:\smako-local-relay\scopes\municipality-1281`. Processpecifika TEMP/TMP,
TMPDIR och SQLITE_TMPDIR samt tidigare huvud-/barnprocessprov på D: behålls.
Denna återhämtning återanvände en färdig artefakt; den påstås inte bevisa en
ny råinsamling. Nytt slutkvitto och nya körloggar skrevs på D:.

Uppgiften är Ready/Enabled, LastTaskResult=0, ossia S4U/Limited, IgnoreNew,
3 h körgräns, StartWhenAvailable/WakeToRun=true. Triggers 01:30/09:30/17:30
lokal tid och pinnad PowerShell är oförändrade. Nästa registrerade start
10 oktober 17:30 svensk tid. Inga dolda pauser finns kvar.
Den direkt efterföljande manuella behovskontrollen 09:56:20 UTC gav **not_due,
0 externa prisanrop**, 0,078 s i reläets loggmått. Nästa behovstid
11 oktober 01:01:56 UTC är inte samma sak som nästa schemalagda kontroll.
Serverns ordinarie 10:00-kontroll gav också not_due.

## Kapacitet efter avslutat arbete

GB är decimalmått; exakta byte finns i FINAL-STATUS.json och ARCHIVE.json.

| Volym | Före | Efter |
| --- | ---: | ---: |
| Windows C: | 4.14 GB | 4.07 GB |
| Windows D: | 657.26 GB | 651.85 GB |
| Server /dev/vda1, berörda data-/Docker-/inboxvolymer | 5,20 GB | 16.19 GB |

Servern hade 12,31 GB kvar under den riktiga publiceringens temporära kopia.
Slutlig beräknad importmarginal är 8,87 GB inklusive befintlig reserv, mot
16,19 GB ledigt (cirka 7,32 GB utöver kontrollens krav). Ingen kapacitetsgräns
sänktes. D: rymmer arkiv, källbasimage och isolerade testfiler. Ingen C:-rensning
eller global TEMP-/Docker-flytt gjordes. C:-förändringen tillskrivs inte säkert
Smako. Detta är uppmätt aktuell marginal, inte en garanti för framtida tillväxt.

## App- och användarprov

- App aktiverad efter fungerande priser, väntan på vila, konsistent backup
  och full Compose-diff. Fyra serverade filhashar matchar leveransimagen.
- Riktiga personliga inköpsflöden i mobil Chromium och WebKit PASS:
  generisk/exakt vara, redigering, sparat utkast, dubbelklick ett POST,
  checkout/audit, sparad GET, omladdning och ny flik utan ny beräkning,
  uttrycklig omräkning revision 2, oförändrad revision 1, annan ägare 403.
- Publik mobil Chromium: fem enkla middagar för två, aktuella priser,
  dubbelklick ett POST/ett jobb, omladdning under körning, fem öppnade recept,
  inköpslista, checkout/audit, sparad GET och ägarskydd PASS. Klick till
  renderat resultat **140,312 s**; jobb-/transportmått 140,187 s. Ingen
  prestandaförbättring eller 60-sekundersuppfyllelse påstås i denna etapp.
  Resultat 251,95 kr, använd mängd 125,26 kr, tre butiker; uppskattat köp
  uttryckligen tillåtet. Proteinmål/allergenkrav var inte begärda.
- Noll oväntade pageerror/unhandledrejection i slutproven. Offentlig omladdning
  gav ett bevarat net::ERR_ABORTED för exakt den GET som klienten uttryckligen
  avbröt vid beforeunload. Requestreferens, dokument/generation och samma jobbs
  terminal201 efter omladdning är korrelerade i BROWSER-EVIDENCE.json.
  Detta är ett hanterat navigationsavbrott, inte noll inträffade nätfel.
- Första personliga Chromiumförsöket kvarstår FAIL: testet väntade på synlig
  inköpspanel efter en #plan-länk, fast sparad Min plan korrekt visades.
  Endast testets navigationsantagande rättades; applikationen ändrades inte
  för omkörningen. Råfelet och hash finns kvar, inga fellyssnare togs bort.
- Alla **240 äldre revisioner och 74 privata tillstånd** är oförändrade på
  radnivå efter bytet/proven. 246 revisioner och 78 privata tillstånd efter
  nya verifieringssessioner. Samtliga 246 revisioner materialiseras av aktuell
  app, inklusive gamla byggversioner. Ingen skafferi-/köpbekräftelse utfördes.
- Gästsessioner med separata verifieringsidentiteter; OIDC är inte konfigurerat.
  Mobil WebKit är inte fysisk iPhone. Inga produktionsfel injicerades och ingen
  flera timmar lång väntan simulerades som verklig användartid. Isolerade
  tids-/utgångs-/prisgateprov från 205cd8 återanvänds med versionsbindning.

## Kvarstående begränsningar

Inga blockerare för denna aktivering återstår. Planberäkningens väntetid och
långsiktig retention är separata frågor. Recept, mängder, fakta, inköpsmotor,
näring, audit, sökbudget och dagens användardata ändrades inte av appfixen.
71 källtester och fulla replay är nykörda i denna etapp; 28+28 app/backendtester
samt isolerade felinjektionsprov från return-session-leveransen är **återanvända**,
inte omräknade som nya. TESTS.json binder råbevis och kodhashar.
