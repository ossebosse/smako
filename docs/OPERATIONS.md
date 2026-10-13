# Gemensam driftstatus och avgränsad reparation

Kör i `D:\Projects\Smako`. Kräver befintlig SSH-administratörsåtkomst till
`smako`; ingen publik diagnostikendpoint, ny notifieringstjänst eller timer.

```powershell
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py municipalities
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py incidents
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py app-incident --request-id 9e96c548-6414-467b-ab7e-3d5e4fe6d779
```

Status läser aktuell Windowsuppgift, senaste relähändelser, kö/kvitto, C:/D:,
serverkapacitet, aktuella baskällor, publicerat/laddat manifest och readiness.
`municipalities` visar samma kedja per registrerad kommun, dess butiksplanering,
väntande laddning och exakt motsvarande lokala reläkvitto. Kommunernas
turordningsjournal redovisas separat; saknad observation är fortfarande unknown.
Inga pris- eller menyanrop, imagebyggen, tester eller full arkivgenomsökning.
Status inkluderar nu även appens senaste 20 HTTP 5xx-metriker inom ett dygn.
`app-incident --request-id ...` läser en exakt referens även utanför detta fönster.
Det lokala verktyget skickar en granskad läsare över befintlig administratörs-SSH;
ingen installation, schemastart eller publik endpoint behövs. SQL är läsande.
Metrikens `created_at` är lagringstid, inte garanterad svarstid. Jämför klientens
`reference` i transportloggen med metrikens `request_id`, inte bara närliggande tider.

Historiska dd12 saknade beständiga exceptionkedjor. Saknat underlag visas som
`unavailable`, även när HTTP-metriken finns. Sedan 2026-10-08 17:02 UTC är
[app-incident-293fc6c49400 aktiverad](releases/app-status-incident-20261008/ACTIVATED.md).
Den versionen
skriver `app-incidents.json` bredvid privat PlanStore, högst 64 incidenter/512 kB,
atomiskt och med skyddat filmode. Där finns start-/statusreferens, ägarkontrollerat
jobb, steg, jobbutfall, kodställen och exceptionkedja utan meddelanden eller lokaler.
Upprepade läsningar räknas som felanrop, **inte** som flera beräkningar.
Pris-ID anges uttryckligen vid HTTP-anropets början; det påstås inte bevisa
beräkningsunderlaget för ett äldre jobb om ett manifest har bytts däremellan.
Indexet är bounded evidence, inte full historik: senaste åtta requestreferenser
och första referensen per incident bevaras. Frånvaro är inte bevis för noll fel.
Skrivfel ger `app_incident_write_failed` med enbart feltyp i skyddad applogg;
ursprungligt HTTP-fel ändras inte. Oavlästa bakgrundsfel har inte fått en ny
jobbjournal i denna etapp. Kontrollerade felprov är inte historisk orsaksbevisning.
Otillgängliga delar är **unknown** med observationstid; senaste framgång är
inte bevis för aktuell drift. Ett importerat Willys-paket kan uttryckligen
vänta på andra obligatoriska källor före publicering och kvittens.

På servern är samma ingång `python -m grocery_data.ops`. Det lokala verktyget
kör den som UID/GID 10001 genom befintlig SSH/Docker-väg. Windowskontrollen
är läsande; inga uppgifter registreras eller startas av statuskommandot.
Använd `--host`, `--workspace` och `--pwsh` före underkommandot för andra
redan auktoriserade miljöer. Ingen ny rättighet följer av ett CLI-kommando.

## Belägg och reproduktion

```powershell
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py reproduce --snapshot-id b662192bf600405e9b70476f8d44f667
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py reproduce --snapshot-id 927a801e126847a184f0515cffc36283
```

Reproduce verifierar ursprungliga råhashar/tider och extraherar Hemköps
butiksfält eller faktiska motstridiga kommersiella poster. Det hämtar inget
och promoverar inget. Högst 32 MB råmaterial läses per reproduktion. Större
fall stoppas tydligt för avgränsad separat granskning, inte som lyckade prov.
Alla kedjor använder samma snapshot-/råreferensväg; källspecifik extraktion
finns där ett konkret kontrakt är känt. Saknade fakta är okända.

Reducerade autentiska regressioner:

```powershell
.venv\Scripts\python.exe -m pytest grocery_data\tests\test_hemkop_picking_contract.py grocery_data\tests\test_operations_diagnostics.py -q
```

Schemafälten heter båda `hasPickingBaseStore`, på två JSON-sökvägar. Parsern
accepterar endast belagd explicit false, bevarar saknat fält och stoppar true,
null eller fel typ. Kampanjkonflikten är källevidens, inte ett trasigt
medlemspris-ID. Två stabilt återgivna skilda erbjudanden tillåts redan.

## Aktuellt incidentindex och varningar

Befintlig `run_daily_refresh.py` uppdaterar under operationslåset
`reports/operations/source-incidents.json` och `drift-indicators.json`.
Den senaste skyddade `refresh-runner-status.json` visar eventuellt indexfel.
Max 128 incidenter och 2 MB index, atomisk ersättning; stora råfiler refereras.
Indexformat v2 skiljer kommersiella incidenter efter verklig produkt och
motstridiga villkor. Vid övergång bevaras ett litet v1-index, varefter aktuellt
index byggs om från oförändrade snapshots. Inga råarkiv dupliceras.
Första körningen granskar högst senaste 100 snapshots; äldre historik är inte
automatiskt återräknad. Därefter inkrementellt med återbesök av pågående jobb.
Samma signatur slås samman och räknar nya jobb, inte statuspollningar.
Källåterhämtning markeras separat från lyckad publicering/laddning/kvittens.
Historisk runtime utan bevis visas som unknown; parserversion kommer från DB.

Varningar omfattar obligatorisk felkälla, försenad publicering, diskmarginal
och färskhetsrisk. 75 minuter är en konservativ behandlingsuppskattning från
den uppmätta återhämtningen på cirka 65 minuter, ingen garanti eller ny
giltighetstid. Fördröjd publicering varnas efter samma 75 minuter. Reläaktivitet
varnas lokalt efter 10 timmar (ordinarie åtta timmars intervall plus marginal).
Servern kan inte bevisa Windowsaktivitet när datorn inte är nåbar.

Ingen extern notifiering är konfigurerad av verktyget. Statusfilerna är
skyddade driftindikatorer; inget mejl/larm påstås skickat. Repetition uppdaterar
last_seen, återhämtning och återkomst är separata övergångar.

## Tillåtna åtgärdsklasser

Vid utrymmesbrist: läs [lagringsrapport och säker arkivering](storage-maintenance.md).
Den skiljer aktiv data från kalla testkopior och delad Dockerlagring, dokumenterar
backupens rättade åtkomstfel och innehåller återställningsanvisningar. Följ samma
driftlås; en historisk cleanup-plan får inte köras om utan ny referensgranskning.

| Klass | Åtgärd |
| --- | --- |
| A, rutin | Giltig artefakt återlevereras genom ordinarie relä; publicering återupptas; transport återförsöks begränsat. |
| B, kod | Reproduktion, avgränsad granskad diff, negativa prov, versionsbundet källpaket och kontrollerad aktivering. |
| C, extern motsägelse | Behåll spärren; ett nytt helt sammanhängande försök, aldrig välja första/sista/billigaste raden. |
| D, operatör | Nya rättigheter, kapacitet eller policybeslut; verktyget kringgår inget. |

`repair` kräver incident-ID och full signatur från aktuell diagnos samt exakt
granskad `--runtime`. Förhandskontrollen är standard; `--apply` krävs för
skrivning. Den tar befintligt kernel-lås, kontrollerar tillstånd igen och
vägrar om källan, incidenten eller runtime ändrats. Exakta argument finns i:

```powershell
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py repair --help
```

Välj `--action replay` för färska sparade schemafel efter verifierat ändrad
parser, `retry` för understött avgränsat Hemköp-kontextförsök eller `publish`
när samtliga obligatoriska källor är kvalificerade och färska. Ingen generell
retry-adapter fabriceras för andra kedjor: deras befintliga driftjobb används.
Resultatet journalförs; samma incident/snapshot/åtgärd/runtime startas högst en
gång. Ett avbrott med kvarstående running-post ska granskas mot verkligt jobb,
inte repareras genom att radera journalen. Globala backoffhistoriken raderas
inte. Källans retry-deadline och hastighetsgränser gäller fortsatt.

Den levande gemensamma källdatabasen ska använda SQLite WAL med FULL-durabilitet.
Managed refresh och guarded replay säkerställer läget under operationslåset,
även efter återställning. Detta låter konsumenterna läsa committade produktfakta
under insamling/import. Ändra aldrig journalformatet på slutna hashbundna arkiv,
godkända kommunala källdatabaser eller byggkopior. Använd befintlig SQLite-backup
för en konsistent kopia inklusive committad WAL, inte en filkopiering av enbart
huvudfilen. SQLite beskriver beteendet i [WAL-dokumentationen](https://sqlite.org/wal.html).
Diagnostikens rågränser är 32 MB per fil och 128 MB per katalog; varje hash och
ursprunglig observationstid måste fortfarande verifieras före replay.

Öppna deterministiska schemafel begränsar berörda onlinekontexter i de verifierade
Hemköp-/Coop-adaptrarna tills granskad reparation/återhämtning. Andra tillåtna
butiker i samma kedja bevaras. Fysiska erbjudandefel blockerar inte onlinebasen.
Övriga adaptrar behåller sina befintliga återförsök och tydlig incidentrapport;
inget nytt generellt hämtkontrakt antas. Ett hold är aldrig ett
färskhetsgodkännande; 36/48 timmar gäller.

Efter varje åtgärd: status → alla fem verkliga observationer → samma aktiva och
laddade manifest → `/ready` → beständigt reläkvitto → publik/personlig meny,
audit och sparad GET under separata verifieringsidentiteter. Bevara gamla
revisioner; byt aldrig tillbaka till en äldre databas.
