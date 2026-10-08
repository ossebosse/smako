# Gemensam driftstatus och avgränsad reparation

Kör i `D:\Projects\Smako`. Kräver befintlig SSH-administratörsåtkomst till
`smako`; ingen publik diagnostikendpoint, ny notifieringstjänst eller timer.

```powershell
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py status
.venv\Scripts\python.exe -X utf8 scripts\smako_ops.py incidents
```

Status läser aktuell Windowsuppgift, senaste relähändelser, kö/kvitto, C:/D:,
serverkapacitet, aktuella baskällor, publicerat/laddat manifest och readiness.
Inga pris- eller menyanrop, imagebyggen, tester eller full arkivgenomsökning.
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

Öppna deterministiska schemafel hålls från nya identiska fullhämtningar i
behovsvägen tills granskad reparation/återhämtning. Andra kedjor filtreras inte
bort. Ett hold är aldrig ett färskhetsgodkännande; 36/48 timmar gäller.

Efter varje åtgärd: status → alla fem verkliga observationer → samma aktiva och
laddade manifest → `/ready` → beständigt reläkvitto → publik/personlig meny,
audit och sparad GET under separata verifieringsidentiteter. Bevara gamla
revisioner; byt aldrig tillbaka till en äldre databas.
