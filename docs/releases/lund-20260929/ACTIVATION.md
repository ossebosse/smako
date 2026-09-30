# Separat besluts- och aktiveringsordning för Lund

Detta är en **förberedd ordning**, inte ett utfört produktionsbyte. Tre skilda
beslut krävs: (1) `lund-own-five-base-20260928-v1` som produktionsomfattning,
(2) serveraktivering och (3) ändring av den aktiva Windows-uppgiften. Inget av
dem följer av att ett isolerat test passerar. Fullständigt Malmö-underlag och
dess baspolicy är ett annat beslut.

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
`D:\Smako-release-work\task-proposed-bdc9\task-proposed.xml` ändrar **endast**
`Actions/Exec/Arguments` till `start_packaged_relay.ps1` med versionsbunden
`-File`, oförändrat `-Workspace D:\smako-local-relay` och separat
`-Config D:\smako-local-relay\config\relay.json`, samt
`Actions/Exec/WorkingDirectory` till den versionsbundna katalogen. `Command`,
körkonto, rättigheter, triggers och övriga inställningar är kvar. Den privata
konfigurationsfilen skapas först i samband med ett godkänt byte och ska aldrig
läggas i Git. Uppgiften är ännu inte ändrad eller registrerad från mallen.
Nuvarande `Arguments` är
`-NoProfile -NonInteractive -File "C:\Users\ossia\Documents\Codex\2026-08-20\jag-vill-att-du-bygger-en\deploy\scripts\collect_willys_local.ps1" -Repository "C:\Users\ossia\Documents\Codex\2026-08-20\jag-vill-att-du-bygger-en" -Workspace "D:\smako-local-relay"`.
Föreslagen `Arguments` är
`-NoProfile -NonInteractive -File "D:\smako-local-relay\releases\bdc9f7df4170\deploy\scripts\start_packaged_relay.ps1" -Workspace "D:\smako-local-relay" -Config "D:\smako-local-relay\config\relay.json"`.
Programmet förblir den nuvarande pinnade `pwsh.exe`-sökvägen.

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

## Godkänd cutover och återgång

Efter **alla tre** separata besluten: frys endast relevant schemalagd körning,
vänta ut operationer och verifiera backup; växla serverbild och först därefter
den enda Windows-uppgiftens kodreferenser enligt granskad XML. Starta inte en
parallell uppgift. Kör mottagarvalidering och ett enda reläjobb när det är
förfallet; kontrollera källhash, ordinarie inbox/import, OWN, atomiskt manifest,
serving-reload och beständigt kvitto. Återuppta ordinarie scheman först när
observationer och faktisk serving är verifierade. Om den äldre reläversionen
inte kan leverera mot den nya mottagaren krävs ett planerat kort avbrott för
just denna övergång, inte ett obevakat server-först-fönster.

Vid fel: stoppa nya jobb och vänta ut operationslåset; återställ tidigare
serverbild/symlink och uppgifts-XML med samma körkonto/triggers. Behåll alltid
den **senaste** plan-databasen och reläets köer/kvitton samt nya råartefakter.
Byt aldrig tillbaka till en äldre kopia av dessa tillstånd: det skulle radera
nya användarplaner eller tappa leveranser. Kontrollera äldre kods läsning av
nya planer separat från förmågan att räkna om dem. Om läskompatibiliteten inte
är bevisad, behåll ny serverbild för planläsning eller använd en särskilt
verifierad kompatibilitetsåtergång. Den äldre mottagaren får inte skriva över
ett nytt aktivt manifest eller importera samma kö igen utan idempotensprov.
Gamla releaser och kodmappar bevaras tills ingen aktiv drift använder dem;
tidigare policyspärrar för städning gäller fortfarande.
