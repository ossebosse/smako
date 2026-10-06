# Etapp A – dd12 aktiverad på beta

Godkänd image `sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7` aktiverades 2026-10-06 cirka 11:42 UTC på beta.smako.nu. BUILD_ID `status-reconnect-dd12cc80e98c`; kompletta recept är på. Paketets 658 manifestfiler och imagen med 651 faktiskt kopierade runtimefiler verifierades före bytet. Laddad complete-recipes.js matchar `17311d27a3a50ec9e75415316ca8cc90d10c94ac85380b36a75a3541d1b7114e`.

Wrapper `/opt/smako/compose` behöll alla befintliga Compose-filer och fick sista override `/opt/smako/overrides/status-reconnect-dd12cc80e98c.yaml`. Hela upplösta konfigurationsdiffen omfattar enbart appimage, BUILD_ID och COMPLETE_RECIPES_ENABLED. Scheduler, ops/collector, proxy och mounts behöll sina identiteter/konfigurationer. Ingen ändring av scheman, kommuner, källpolicy, prisdata eller säkerhet. Produktionsresurskonfigurationen är oförändrad och saknade redan explicita CPU-/RAM-gränser; etapp B provas separat med två CPU och 3 GiB.

Befintligt operation lock användes. Appprocessen var stilla (0,04 CPU-sekunder under tio sekunder) före ersättning; detta är en OS-observation, inte en direkt avläsning av minnesjobb. Integritets- och foreign-key-kontrollerade SQLite-backuper av aktuella plan-/grocerylager finns privat i `/opt/smako/evidence/status-activation-20261006/current-state-backup/`. Alla tidigare 209 revisionsrader och 58 privata tillståndsrader behöll sina radfingeravtryck efter bytet. Ingen databas återställdes.

## Riktiga knappflöden

Publikt Chromium och personligt WebKit i mobil layout klarade generering, dubbelklick, omladdning under jobb, fem sekunders klientoffline, återanslutning, receptbyte, uttrycklig omräkning och sparade revisions-GET. Varje generation hade en POST och en jobbreferens. Komplett resultat, audit, layout och faktiska laddade filer kontrollerades. Separata nya verifieringsgäster användes.

**Första WebKit-försöket är fortfarande FAIL:** färdig meny 201 utan sidfel, men ett status-GET tog 16 123,785 ms och klarade inte verktygets ti sekundersgräns. Samma request-id `6e4518bd-bf5b-4d8a-ad59-16b1ae191149` finns i servermetriken: 202, 159,367 ms, registrerat 11:49:57,441277 UTC. Mätgränserna skiljer sig; exakt proxy-/ankomstkorrelation saknas och grundorsaken är obelagd. Rått FAIL och tidsunderlag bevaras. Separat omkörning med samma val passerade hela flödet. Detta är inte en appfix eller bevis för att latensavvikelsen aldrig återkommer.

Priserna kom från faktiskt publicerad PriceUniverse `price-universe:387cc368662cc45b3ee4714aaf57ed42e4a6ff1123a814d7fb62e25f5ead80e9`, 2 234 produkter, utan testklocka. Underlaget var aging men användbart enligt oförändrade 36/48-timmarsgränser. Ingen insamling kördes. Faktisk `/api/account/status` är DATA_BLOCKED för kontoinloggning: drift använder gästägarsession. Signerad OIDC-inloggning är inte aktiverad och har inte kvalificerats genom gästproven.

## Återgång och utvecklingsgräns

Funktionsåtergång är flagga av på samma image enligt [dd12-anvisningen](../status-reconnect-20261006/ACTIVATION.md), med senaste data kvar. Den har inte aktiverats eftersom inget kvarstående funktionsfel kräver den. Ingen äldre binäråtergång eller databasåterställning ingår. Etapp B är separat utveckling och har inte installerats.

[Maskinbevis](EVIDENCE.json). Fulla prov, skärmbilder och råa fel bevaras privat under `.local/meal-library-20261006/activation/`; Compose/env/backup finns privat på servern. Inga cookies, token eller privata planer committas. Ingen Git-push.

## Senare driftobservation – separat från aktiveringsprovet

Den 6 oktober blev serverdisken full och `/ready` rapporterade att planlagringen
inte kunde nås. Utvecklingens nya byggmappar bidrog till utrymmesbehovet;
exakt fördelning av diskökningen över andra skrivare har inte belagts.
Ingen ny app installerades och ingen databas återställdes.

Efter ett separat uttryckligt godkännande arkiverades endast denna etapps tolv
nya `build-*`-mappar till D:. Samtliga 7 362 filer verifierades mot sina hashvärden
innan serverkopiorna frigjordes. Arkivet behålls; äldre underlag, imagen och
användarlagringen bevarades. Cirka 253 MB blev tillgängliga. Därefter svarar
planlagringen åter `ok`. [Arkiv- och omfattningsbevis](STORAGE-RECOVERY.json).

Beta är ändå **inte ready**: två obligatoriska Willys-kontexter är nu stale
enligt oförändrad 48-timmarsgräns. Den aktiva imagen, BUILD_ID och receptflaggan
är fortsatt dd12 enligt ovan. Detta är senaste läget, inte en återkallelse av
de tidigare knappflödesproven. Ingen ny insamling, schemauppdatering eller
försvagad färskhetskontroll har gjorts. [Tidsstämplad observation](LATEST-STATE.json).
