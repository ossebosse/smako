# 2026-10-31: Menytimeout utredd, mindre faktarbete aktiverat

[PR 55](https://github.com/ossebosse/smako/pull/55), main `c5fdd5f91172`.
App `app-cd15469e50f9-fa1f8fd2`; scheduler source-ops-8a53beb80e43.
[Utredning](reviews/menu-timeout-20261031/REPORT.md) och
[aktiveringsjournal](releases/menu-facts-deadline-20261031/ACTIVATED.md).
Två bortkastade faktahashningar tas bort; samtliga 54 515 faktaposter och
slutversionen identiska. Varmt isolerat prov 33,372 → 25,910 s, samma verifierade
110,55 kr. Kallt prov fortfarande timeout 60,017 s; kallstart är inte löst.
De två äldre felreferensernas exakta steg är okända. Första publika provet: **63,032 s**,
110,55 kr, passerad checkout och identisk sparad återläsning. Ny gäst, samma typ av menyval;
ingen omkörning. Inga JavaScriptfel. **Tidsmålet 60 s missades**, även om menyn levererades
och funktionskontrollerna passerade.
140 riktade fall, Ruff/compileall, PR- och main-CI gröna (4 402 pass, 63 skip).
En runtimefil ändrad, 1010 andra oförändrade. Full releasebackup
/srv/smako/backups/20261031T152015Z, tidigare användarrader, mountar och prismanifest verifierade.
Retention complete; ingen schema-/schedulerändring.

---

# Gemensam driftstatus och avgränsad reparation

Senaste appaktivering: [läsbar planinformation](releases/plan-notice-contrast-20261031/ACTIVATED.md).
App `app-2d2181aabfb4-a98bfc56`; scheduler source-ops-8a53beb80e43.
Tre statiska filer; Lund/Malmö ready, användarrader och prismanifest bevarade.
Ny verifierad backup, retention complete. Den tidigare kapacitetsvarningen är borta vid efterkontrollen.

Föregående appaktivering: [förloppspanel, planvy och inköpslista](releases/plan-shopping-ui-20261031/ACTIVATED.md).
App `app-56caf4ab5f6e-d90dabe8`; scheduler `source-ops-8a53beb80e43`.
Lund/Malmö ready; användarrader, mountar och prismanifest verifierade.
Ny verifierad releasebackup; retention complete. Kapacitetsvarningen och
ordinarie backupens tidigare lagringsfel kvarstår. Backend och scheman består.

Föregående appaktivering: [mobilmeny och Översikt, 31 oktober](releases/mobile-overview-20261031/ACTIVATED.md).
App `app-bbf62d741a99-320a0495`; scheduler `source-ops-8a53beb80e43`.
Lund/Malmö ready, tidigare användarrader och prismanifest verifierade.
Ny verifierad releasebackup; retention complete. Den konservativa
kapacitetsvarningen kvarstår. Backend och scheman består.

Föregående appaktivering: [mobilkonfigurator och egna varor, 30 oktober](releases/mobile-configurator-20261030/ACTIVATED.md).
App `app-562afbb53344-92f00d23`; scheduler `source-ops-8a53beb80e43`.
Båda kommunernas readiness, tidigare användarrader och oförändrade
prismanifest verifierades. Retention complete; installerad backup-/schema-
policy består. Den konservativa kapacitetsvarningen och prisernas
åldersvarningar ska fortsatt följas. Nedan följer källaktiveringens belägg.

Se [aktiveringen](releases/stora-coop-syd-base-20261029/ACTIVATED.md).
Stora Coop Lund (2696), Forum Jägersro (3850) och Stadion (3853) har vardera
11237 baspriser från Online Syd och 454 egna kampanjposter. Mindre Coop/X:-tra
är oförändrade. Butiksvalens källmärkning och verklig varusökning är verifierade.
App och scheduler `source-ops-8a53beb80e43`; PR47–49 och slutlig main-CI gröna.
Faktaläsaren följer samma exakta källprodukt för ingredienser och näring.
Versionspolicyn ger distinkta laddade pris-ID:n i båda kommunerna.
Backup `20261029T211156Z`, tidigare användarrader och mountar verifierade.
Recept-/checkoutregler och tvånattspolicy består. Äldre journaler är historiska.

[Senaste Coop-källrättning](releases/coop-remaining-sources-20261029/ACTIVATED.md)
verifierar fyra tomma Malmö-källor och ny kvalificerad/laddad Online Syd-katalog i Lund.
Malmös befintliga butiksscope består. Okända kampanjvillkor ger baspris. Äldre rapporter
nedan är historiska; Windowsregistreringen återstår fortsatt med administratör.

[Coops insamlingsfält rättat 29 oktober](releases/coop-environmental-code-20261029/ACTIVATED.md)
bekräftar de tio tidigare uppdaterade butikerna. De separata Coop-fel som
återstod då är åtgärdade i den senaste källrättningen ovan.

Senaste [samlade betaaktivering](releases/beta-ica-recipes-20261028/ACTIVATED.md)
omfattar ICA-baspriser, hela recept-/beräkningsarbetet och serverhämtning
måndag/torsdag 03:17 svensk tid. Windowsreläets befintliga uppgiftsregistrering
kräver fortfarande administratör; serverstatus bevisar inte dess veckoschema.

[Driftkontroll och dashboardrättning 28 oktober](releases/dashboard-operations-20261028/ACTIVATED.md)
bekräftar ICA-baspriser, återställd Malmö-Willyskvittens och Willys reklamblads-
historik. Journalen skiljer de dåvarande Coop-felen från användbara äldre
priser och från Windowsuppgiftens registrering.

## Prispolicy från 2026-10-15

Kvalificerade baspriser behålls tills en validerad ersättning finns, för alla
kedjor och kommuner. Ålder 36/48 timmar är fortsatt en driftvarning och grund
för återförsök, men spärrar inte i sig butikssökning, beräkning eller publicering.
Kampanjer gäller enbart inom sina källbelagda datum, inklusive sista dagen i
Europe/Stockholm. Vid utgång används produktens baspris om det finns; annars
utesluts erbjudandet. Ordinarie kampanjhämtning och dess återförsök fortsätter.
Rabatter utan slutdatum får inte ärva basprisernas obegränsade giltighet: deras
tidigare 48-timmarsgräns behålls konservativt på inköpsdagsnivå.
Alla källtider, identitetskontroller, kvalitetskrav och insamlingsfel bevaras.
`base_prices_usable` skiljs från `freshness`; STALE betyder inte raderad data.
Se [implementation och verifiering](reports/base-price-retention-20261015.md)
för aktuell aktiveringsstatus.

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

Hemköps `hemkop-parser-v1.4-delegated-context` bevarar från 2026-10-18 de
ursprungliga butikskontextdokumenten även när en katalogsida delegeras till
den gemensamma Axfood-parsern. Komplett hämtning följd av noll parsade produkter
och `price_context_unverified` kan annars vara adapterfelet från v1.3, trots
att både katalog och butik har korrekt bindning. Kontrollera de faktiska
parserfelen; det generella incidentnamnet `SOURCE_QUALIFICATION_FAILED` räcker
inte för att fastställa orsaken. Se [rättning och driftbevis](releases/source-recovery-20261018/REPORT.md).

Willys har sedan 2026-10-15 en separat verifierad motsvarighet:
`willys-parser-v6-picking-contract` granskar exakt butik och explicit false i
både butikskatalog och aktiv butikskontext. Serverns parserrättning är aktiv;
installerat Windows-paket och faktisk schemaversion redovisas separat i
[aktiveringsrapporten](releases/willys-picking-20261015/ACTIVATED.md).
Gamla godkända v3/v4/v5-paket kan omkvalificeras utan nya observationstider.
Använd ordinarie reläåterleverans för ett komplett väntande paket så att även
kommunal inventering och slutligt publiceringskvitto följer med.

Ett 422-fel för en vald priskontext kan gälla en separat fysisk erbjudandekanal
trots readiness 200 för de obligatoriska baskällorna. Kontrollera därför just
den valda kontexten och dess adapter mot aktuellt manifest. Vid källbyte provas
också ett tidigare sparat, godkänt butiksurval; byt inte automatiskt till en
annan butik eller priskanal. Stortorgets följdfel berodde på äldre härledda
registermetadata, inte utgångna kampanjer. Se
[rättningen för sparade reklambladsregister](releases/willys-flyer-inventory-20261015/REPORT.md).

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

Willys checkpoints från `84b2de8` använder verifierad gränsgeometri och
källmetadata som identitet. SCB:s WFS-`timeStamp` och yttre `observed_at`
ändrar inte identiteten; originalets råhash kontrolleras ändå och bevaras.
Identitetsschema 1 återanvänds inte av schema 2. Ett första försök efter
uppgradering kan därför behöva hämta butiker igen. En checkpoint är enbart
hämtstöd: ordinarie insamling, artefaktvalidering, import, publicering och
beständig kvittens krävs fortfarande. Se [verifieringen](releases/source-recovery-20261018/REPORT.md).

Från `2464596` reserverar reläet 45 minuter för import/publicering och använder
samma gräns för SSH-svaret, inom oförändrat totalt körfönster. En förlorad
transportrespons är fortfarande ett okänt utfall: kontrollera serverjobbet och
driftlåset innan återleverans. Den befintliga importvägen kan kvittera en exakt
redan publicerad och laddad artefakt utan att bygga om eller förnya källtider.

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
när samtliga obligatoriska baskällor är kvalificerade och användbara. Ingen generell
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
färskhetsgodkännande; åldersvarningarna vid 36/48 timmar gäller fortfarande.

Efter varje åtgärd: status → alla fem verkliga observationer → samma aktiva och
laddade manifest → `/ready` → beständigt reläkvitto → publik/personlig meny,
audit och sparad GET under separata verifieringsidentiteter. Bevara gamla
revisioner; byt aldrig tillbaka till en äldre databas.
