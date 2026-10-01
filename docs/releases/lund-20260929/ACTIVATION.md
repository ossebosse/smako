# Lund: samordnat byte och begränsad återgång

Detta är instruktionen för ett senare godkänt byte, **inte utförd produktion**.
Tre separata beslut krävs: femkällorspolicyn, serveraktivering och ändring av
den aktiva Windows-uppgiften. Serverbeslutet måste uttryckligen omfatta att
återgångsmålet erbjuder **läsning av sparade planer, inte full drift**.
Se [TRANSITION.md](TRANSITION.md) för provad sekvens och teknisk slutstatus.
Teknisk status: **REDO FÖR SEPARAT AKTIVERINGSBESLUT** för denna begränsade
återgång. Det är inget godkännande att ändra drift.
Malmö, utökad erbjudandetäckning och städning ingår inte.

## Versionsbundna mål

Server, migration, collector och refresh/scheduler ska använda den slutliga
bilden och runtime-commiten i [TRANSITION-EVIDENCE.json](TRANSITION-EVIDENCE.json).
Använd `deploy/compose.release.yaml`: samma bild för app, migrate, scheduler,
refresh-once och backup-once, utan lokalt bygge. Ange både
`SMAKO_RELEASE_IMAGE` och `SMAKO_RELEASE_ENV_FILE` till granskade privata värden.
Rendera med samma skyddade env som interpolationskälla. `env_file` gör även
de fullständiga kommun-/källinställningarna tillgängliga; befintliga explicita
Compose-miljövärden har företräde och ska stämmas av mot den granskade filen.

Windows använder det liveprovade **oförändrade** paketet
`D:\smako-local-relay\releases\bdc9f7df4170`. Dess kontrakt provas mot den nya
servern genom autentisk replay. Det nya Windows-ZIP:et är byggt från samma
slutcommit som servern men inte installerat/S4U-liveprovat; ersätt inte bdc9
automatiskt. Ursprungligt [S4U-bevis](S4U-LIVE.md) gäller exakt bdc9 och dess
provade konfiguration. Ett annat konto, transport, nyckelskydd, startargument
eller körpolicy kräver uttryckligt godkänd kompletterande kontroll.

Återgångsmålet är den slutliga pinnade serverbilden med entrypoint
`app.recovery:app`, genom `deploy/compose.recovery.yaml`. Den läser den senaste
plandatakatalogen read-only med befintliga autentiseringsnycklar och
åtkomstkontroller. Ingen prisrot krävs. Nyplanering, omräkning och API-import
svarar kontrollerat 503; source_cli/refresh vägrar med exit 3 i återgångsläget.
Gammal produktionsbild `54dde8382599ac30beee8bffd05d8cefff232e1ea5c81f1fd7f302db0d591c1f`
är bevarad historik, **inte ett fungerande återgångsmål för nya planer**.

## Exakta föreslagna inställningsändringar

Efter separat policybeslut används `lund-own-five-base-20260928-v1`,
`OWN_SOURCES_ONLY=true` och exakt följande `PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS`:

```text
context:coop:23eaae11c9661e68,context:hemkop:3288e04edd97e349,context:hemkop:756955d0e6e05f23,context:willys:383650ec6ff5a636,context:willys:4a671428fc484e43
```

Det är Coop Online Syd, Hemköp Brunnshög/Karhögstorg och Willys Lund/Lund Nova.
Originalpolicyn med obligatoriska Primat-baser sparas separat.
`WILLYS_COLLECTION_LOCATION=LOCAL_RELAY`, 36/48 timmar, `offers_only`,
kommunflöden och användarens butiksval ändras inte.

Ny mottagarinbox är `/srv/app/var/raw_snapshots/source-inbox/municipality-1281`,
på värden `/srv/smako/data/raw_snapshots/source-inbox/municipality-1281`.
Sätt `SOURCE_RELAY_INBOX` och privat `relay.json` till samma containersökväg.
Transporten ska rikta sig till den nya **scheduler/receiver-containern** med
skrivbara grocery/raw/prisvolymer och `INTERNAL_APP_BASE_URL=http://app:8000`.
Vanlig app har read-only raw/prisvolymer och ska inte göras skrivbar som genväg.
Renderad Compose ska bekräfta dessa bindningar före byte. Gamla inboxen får inte
pollas av det nya kommunflödet. Befintligt operationslås serialiserar alla
refresh-/importvägar även efter att normala jobb återupptas.

Windows-förslaget ändrar endast Arguments och WorkingDirectory för
`Smako Willys Local Relay`:

```text
-NoProfile -NonInteractive -File "D:\smako-local-relay\releases\bdc9f7df4170\deploy\scripts\start_packaged_relay.ps1" -Workspace "D:\smako-local-relay\scopes\municipality-1281" -Config "D:\smako-local-relay\config\relay.json"
WorkingDirectory: D:\smako-local-relay\releases\bdc9f7df4170
```

Behåll befintlig pinnad pwsh.exe, ossia/S4U/Limited, 01:30-trigger, IgnoreNew,
PT3H, StartWhenAvailable och WakeToRun. Kontrollera effektiv körpolicy och
signering enligt provat startförfarande; tillfällig Bypass vid registrering
bevisar inte schemalagd laddning. Ingen permanent säkerhetspolicy ändras.
Privat uppgiftsmall: `.local/drift-verification/task-proposed-municipal/task-proposed.xml`.
Gamla skript, arbetsytor och uppgiftexport bevaras.

## Enda övergångsordningen efter besluten

1. Kontrollera paket-/bildhashar, faktiskt laddat manifest, refererade råfiler
   och äldsta verkliga observation i var och en av de fem baserna. Varning vid
   36 timmar, stopp vid 48; kampanjens faktiska slut gäller. Återanvänd giltiga
   underlag. Kopiering/rebuild får aldrig föryngra observationer.
2. Pausa nya starter på **båda** jobbsidor under ett kort planerat avbrott.
   Vänta ut jobb, barnprocesser och befintliga operationslås; bryt inte lås.
   Inget obevakat server-först-fönster och inga dubbla importerare tillåts.
3. Ta konsistenta skyddade backuper av Windows-XML/hash, serverbild/Compose/env,
   senaste plan- och grocery-databaser, manifest/prisrot, råfiler, köer, kvitton
   och uppdateringsstatus. Använd SQLite online-backup eller stoppade skrivare.
   Bevara rättigheter och hemligheter utanför Git och rapporter.
4. Kör `python -m grocery_data.relay_transition` från slutpaketet på respektive
   värd med `--workspace` och/eller `--inbox --database --price-root`, samt
   separat `--archive`. Verktyget använder befintliga lås, väntar högst 300 s
   som standard och vägrar vid kvarvarande operation. Det bevarar original,
   innehållsadresserade kopior, kvitton och klassificering. Upprepning med
   oförändrat tillstånd ger samma inventeringshash. Kvitterade, mottagna utan
   belagd publicering, väntande och oläsbara filer hålls synligt åtskilda.
   **Ingen gammal publicering krävs före bytet.** Ingen falsk kvittens,
   påhittad kommunbindning eller ändrad observation tillåts.
5. Behåll gamla arbetsytan/inboxen separat. Under samma paus installeras nya
   servermålet och Windows-förslaget med separat kommunarbetsyta/inbox.
   Verifiera att samtliga serverjobb använder samma bild. Återuppta redan
   påbörjad övergång från senaste köer; skriv inte tomt tillstånd över dem.
6. Prova en kontrollerad leverans med kompatibla paret: hash, scope/tider,
   autentiserad transport, validering, exakt en import, atomisk publicering,
   **faktiskt laddat** manifest och beständigt kvitto. Förlorat lokalt kvitto
   efter publicering ska ge återleverans/already_active utan dubbelimport.
   Kontrollera planläsning. Återuppta scheman först när detta passerat.

## Begränsad återgång och återstart

1. Pausa båda jobbsidor, vänta ut operationer och stoppa vanlig app/importörer.
   Behåll **senaste** planer, revisioner, köer och kvitton. Ta ny backup;
   återställ aldrig tidigare databas- eller kökopia över nytillkommet tillstånd.
2. Med samtliga skrivare stoppade: kör SQLite `PRAGMA wal_checkpoint(TRUNCATE)`
   mot senaste planfilen och kontrollera resultatet, revisionsantal och att WAL
   är tom/saknas. Behåll skrivarna stoppade hela läsdriften. Läsaren använder
   SQLite immutable/read-only för att inte skapa sidofiler på read-only-volymen
   och vägrar med 503 om en icke-tom WAL finns; den får inte ignorera nya revisioner.
   Starta pinnad återgångsbild med `deploy/compose.recovery.yaml`, befintlig
   `SMAKO_ENV_FILE`, `SMAKO_LATEST_PLAN_DIRECTORY=/srv/smako/data/plans` och
   `SMAKO_PLAN_FILENAME=consumer_plans.sqlite3` (verifierat produktionsfilnamn).
   Containerflaggan är `SMAKO_RECOVERY_READ_ONLY=true`. Katalog och
   containerfilsystem är read-only; endast `/tmp` är skrivbart. Ingen
   scheduler, collector eller reläleverans startas i detta läge.
3. Verifiera `/ready` med `mode=recovery_read_only`, ägarens GET av gamla/nya
   planer och 403 för fel användare. Kontrollera full sparad JSON, revision
   och källreferenser. Läsningen räknar aldrig om resultat. Nyplanering,
   omräkning/import ska ge `503 recovery_read_only`, inte 500 eller PASS.
   Byt därefter trafik till lästjänstens localhost-port via granskad proxy.
   Detta är läsdrift; komplett planerings-UI/full drift utlovas inte.
4. Ingen gammal prisrot/originalpolicy aktiveras för nyplanering. Primat-hindret
   kvarstår i originalpolicyn; det påverkar inte prisoberoende planläsning.
5. Återstart: stoppa lästjänsten, starta nya normala paret med **samma senaste
   data**, kontrollera aktuella 36/48-timmarsgränser/kampanjer, serving och
   idempotens. Återuppta därefter scheman. Skicka inga nya artefakter till
   gamla paret, radera inga gamla mappar och återställ inga äldre köer.

Köarkiv är bevarandebevis, inte publiceringskvitton. Inkompatibla/oläsbara gamla
leveranser kvarstår synligt ej publicerade för separat granskning.
