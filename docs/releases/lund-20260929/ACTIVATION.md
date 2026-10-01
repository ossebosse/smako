# Separat besluts- och aktiveringsordning för Lund

Detta är en **förberedd ordning**, inte ett utfört produktionsbyte. Tre skilda
beslut krävs: (1) `lund-own-five-base-20260928-v1` som produktionsomfattning,
(2) serveraktivering och (3) ändring av den aktiva Windows-uppgiften. Inget av
dem följer av att ett isolerat test passerar. Fullständigt Malmö-underlag och
dess baspolicy är ett annat beslut.

**Teknisk status: INTE REDO.** [Kompletterande driftprov](OPERATIONS.md)
visar ännu oprövad S4U-livekedja, otömd gammal kö på originalpolicyn och
inkompatibel planläsning i faktisk produktionsbild. Nedanstående är en
villkorad ordning, inte ett godkänt körschema. Korsversionerna är
inkompatibla: ett kort samordnat avbrott är obligatoriskt.

Testregistreringen är utförd av operatören. Aktuella förkontroller och
gränsen före start finns i [S4U-PREFLIGHT.md](S4U-PREFLIGHT.md).

## Utgåva och exakta ändringar

Källcommit för båda driftpaketen är `bdc9f7df417084641d0a712e3dad188dad1ad7d4`.
Serverpaketet är `smako-server-bdc9f7df4170.zip`; reläpaketet är
`smako-windows-relay-bdc9f7df4170.zip`. Kontrollera SHA-256 mot
[resultatrapporten](RESULTS.md) innan någon installation eller bildstart.
Serverns `app`, `migrate` och `scheduler` ska alla få samma verifierade
innehållsadresserade bild via `deploy/compose.release.yaml`, utan värdbygge.
Separat versionsbundet relä finns förberett under
`D:\smako-local-relay\releases\bdc9f7df4170`; tillstånd och lokal konfiguration
ska vara kvar utanför denna katalog.

Nuvarande produktionsbild är `sha256:54dde8382599ac30beee8bffd05d8cefff232e1ea5c81f1fd7f302db0d591c1f`
och `BUILD_ID=price-recovery-lund-20260914a`. Nuvarande serverpolicy har
`OWN_SOURCES_ONLY=false` och sex obligatoriska kontexter, inklusive två
ICA/Primat-baser. Ett **separat godkänt** Lund-byte skulle sätta
`OWN_SOURCES_ONLY=true` och exakt fem `PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS`
från `deploy/policies/lund-own-five-base-20260928-v1.json`: Coop Online Syd,
Hemköp Brunnshög, Hemköp Karhögstorg, Willys Lund och Willys Lund Nova.
`WILLYS_COLLECTION_LOCATION=LOCAL_RELAY`, 36/48-timmarsgränserna,
`offers_only`, valda kommunflöden och användarens tillåtna butiker får inte
förändras som bieffekt. Originalpolicyn ska arkiveras separat och återställbar.
Det föreslagna värdet för `PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS` är exakt
`context:coop:23eaae11c9661e68,context:hemkop:3288e04edd97e349,context:hemkop:756955d0e6e05f23,context:willys:383650ec6ff5a636,context:willys:4a671428fc484e43`.

Nuvarande Windows-uppgift `Smako Willys Local Relay` kör befintlig PS7 med
`ossia`/S4U/Limited, dagligen 01:30, `IgnoreNew`, PT3H,
`StartWhenAvailable` och `WakeToRun`. Förslaget i
den nya privata mallen
`D:\Projects\Smako\.local\drift-verification\task-proposed-municipal\task-proposed.xml`
ändrar **endast**
`Actions/Exec/Arguments` till `start_packaged_relay.ps1` med versionsbunden
`-File`, separat `-Workspace D:\smako-local-relay\scopes\municipality-1281` och
`-Config D:\smako-local-relay\config\relay.json`, samt
`Actions/Exec/WorkingDirectory` till den versionsbundna katalogen. `Command`,
körkonto, rättigheter, triggers och övriga inställningar är kvar. Den privata
konfigurationsfilen skapas först i samband med ett godkänt byte och ska aldrig
läggas i Git. Uppgiften är ännu inte ändrad eller registrerad från mallen.
Nuvarande `Arguments` är
`-NoProfile -NonInteractive -File "C:\Users\ossia\Documents\Codex\2026-08-20\jag-vill-att-du-bygger-en\deploy\scripts\collect_willys_local.ps1" -Repository "C:\Users\ossia\Documents\Codex\2026-08-20\jag-vill-att-du-bygger-en" -Workspace "D:\smako-local-relay"`.
Föreslagen `Arguments` är
`-NoProfile -NonInteractive -File "D:\smako-local-relay\releases\bdc9f7df4170\deploy\scripts\start_packaged_relay.ps1" -Workspace "D:\smako-local-relay\scopes\municipality-1281" -Config "D:\smako-local-relay\config\relay.json"`.
Programmet förblir den nuvarande pinnade `pwsh.exe`-sökvägen.

Den nya arbetsytan är ett uttryckligt tillägg till Windows-förslaget: gamla
city-scope-köer/kvitton ska ligga kvar oförändrade i den gamla arbetsytan,
nya kommunartefakter ska ha eget aktuellt tillstånd. Tidigare XML med samma
arbetsyta för båda versionerna är bevarad historik, inte aktuell instruktion.
Varken katalogen eller produktionskonfigurationen har installerats här.
Ändringen ingår i det separata Windows-beslutet. Ingen gammal artefakt får
konverteras, kvitteras som publicerad eller raderas för att flytta kön.

## Kontroller före varje byte

1. Läs [resultatrapporten](RESULTS.md) och verifiera att både gammal/ny
   mottagar- och reläversion har passerat den faktiska kompatibilitetsordningen.
   Kontrollera att fem obligatoriska källor är under 48 timmar gamla, att
   kampanjer gäller på plandagen och att faktiskt laddat manifest innehåller
   dem. Degradationskod eller HTTP 200 ensam är inte godkännande.
2. Vänta tills pågående Windows-jobb och serverns refresh/import är färdiga.
   Ta operationslåset för en kort kontrollerad cutover. Kör inte gamla och nya
   reläet samtidigt. Säkerhetskopiera **konsistent**, utan skrivare, den aktuella
   serverreleasen och bild-ID:t, Compose-filer och skyddad `.env`,
   `/srv/smako/data/grocery`, `/srv/smako/data/plans`, aktivt manifest och
   PriceUniverse under `/srv/smako/data/price_universes`, refererade
   `/srv/smako/data/raw_snapshots` inklusive inbox, samt rapporter/uppdateringsstatus.
   Använd SQLite online-backup eller stoppade skrivare, verifiera hash och
   återläsbarhet. Spara sekretesskyddade kopior utanför Git och rapporter.
3. Exportera den aktiva Windows-uppgiften och dess hash igen. Ta en konsistent
   kopia av `D:\smako-local-relay` till skyddat backupmål, inklusive köer,
   `last-success.json`, lås-/uppdateringsstatus och lokal konfiguration.
   Bevara rättigheter. Inga gamla datumkataloger raderas.
4. Verifiera releasebildens OCI-revision, server-ZIP:ens filhashar och
   `docker compose -f compose.yaml -f /opt/smako/compose.vps.yaml -f
   compose.release.yaml config` med skyddad produktionskonfiguration. Bild-ID
   måste vara identiskt för `app`, `migrate`, `scheduler` och användas av
   collector/refresh. Genomför databas- och läsbarhetsprov innan trafik byts.

## Samordnad cutover: ett enda kontrollerat avbrott

Får utföras först när tekniska spärrar stängts och **alla tre** separata
beslut fattats. Gamla/nya relä- och mottagarversioner får inte köras i kors.

1. Blockera nya berörda schemastarter på både server och Windows inom det
   godkända avbrottet. Vänta ut pågående jobb, barnprocesser och operationer;
   kontrollera låsägarna, bryt inte lås. Behåll gamla paret tills det är tyst.
2. Inventera/hashförteckna gamla/nya köer, inboxar och senaste kvitton.
   Med gamla paret ska giltiga gamla väntande artefakter importeras och
   faktiskt publiceras före bytet, eller hållas separat under ett uttryckligen
   granskat förfarande. **Nu blockerad:** originalpolicyn kan inte publicera
   utan Primat-baser. En redan importerad men opublicerad artefakt får inte
   bli ett framgångskvitto. Valideringsavvisade äldre filer bevaras separat
   med felorsak; de får inte tyst tappas eller bindas om till kommun.
3. Ta konsistenta skyddade backuper och låset enligt kontrollerna ovan.
   Bevara gamla prisroten som separat återgångskandidat, men återställ aldrig
   äldre planer, köer eller kvitton över nytillkommet tillstånd.
4. Under samma avbrott, med **båda jobbsidor fortsatt pausade**, byt app,
   migrate, collector/refresh/scheduler till verifierad ny bild och godkänd
   femkällorspolicy. Byt den enda Windows-uppgiftens Arguments/WorkingDirectory
   enligt aktuell XML, inklusive separat kommunarbetsyta. Behåll konto,
   S4U/Limited, triggers, IgnoreNew, tidsgräns och övriga inställningar.
   Den gamla arbetsytan/uppgiftexporten bevaras. Inget obevakat
   server-först-fönster tillåts.
5. Tillåt endast en kontrollerad körning av det nya paret. Använd giltiga
   nya artefakter för replay där det är relevant; gör ny verklig hämtning
   när behovsstyrningen kräver det. Verifiera hash, scope, observation,
   inbox, operationslås, import, atomisk publicering, laddat manifest,
   beständigt kvitto och idempotens. Planläsning och kvalitetsstatus måste
   passera. Återuppta båda sidors normala scheman först därefter.

## Återgång: stoppa vid konstaterad läsinkompatibilitet

Vid fel hålls **båda** sidors nya jobb pausade och pågående operationer väntas
ut. Nya artefakter/kvitton stannar i nya kommunarbetsytan/inboxen, gamla i
gamla. Inga nya artefakter skickas till gamla mottagaren. Återanvänd senaste
kvittot inom rätt scope; återställ inte en äldre backup över kön. Upprepad
import ska kontrolleras mot artefakthash/snapshot, inte filnamn eller körtid.

Ett rent bildbyte tillbaka är **inte verifierat säkert**: faktisk gammal
bild avvisar nya manifestfält och tappar planfält; kampanjplanens GET ger
500 även med det gamla manifestet. Återställ därför inte den äldre bilden
som enda användarserver med nya planer. Innan godkänd aktivering behövs en
verifierad kompatibilitetsåtergång, eller en separat granskad lösning som
behåller nya bildens läsning av den senaste plandatabasen under avbrottet.
Att ny bild kan läsa planerna efter vårt test är inte bevis på att en sådan
trafik-/driftlösning är installerad. Denna spärr är öppen.

När en säker återgång väl verifierats ska tidigare serverbild/konfiguration,
separat kompatibel prisrot och ursprunglig Windows-XML bytas tillsammans
innan scheman återupptas. Originalpolicyn med obligatoriska Primat-baser är
fortfarande separat och saknar giltigt underlag; återställd planläsning får
inte betecknas som återställd nyplanering/full drift. Omräkning provas
separat. Gamla mappar och backuper bevaras; inga städspärrar kringgås.
