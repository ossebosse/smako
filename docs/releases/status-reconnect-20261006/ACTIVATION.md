# Förberett app-only-byte – inte aktiverat

Betan, driftkonfigurationen, reläerna, insamlingsjobben, databasen och användarrevisionerna har lämnats orörda. Denna instruktion gäller ett separat framtida beslut om **endast appen**. Den tidigare 2816-imagen ska inte installeras som ett dolt mellansteg, och en äldre databas får aldrig återställas över senare användardata.

| Identitet | Värde |
| --- | --- |
| Runtime-commit | `dd12cc80e98c79aa32c159223c8bc1ceeaaa7580` |
| Serverpaket | `smako-server-dd12cc80e98c.zip` |
| Paketstorlek | 2 839 700 byte |
| Paketets SHA-256 | `bc1ec3f2b03c228348bb63bcf3bba0f84f300b56aa375cdbe877f0dc8838484c` |
| Verifierad testimage-ID | `sha256:c8362751b13a6e649beadad2a3c27b9b5df8bfd1e2fa177ff68e01e1d7b8b2c7` |
| Avsett BUILD_ID | `status-reconnect-dd12cc80e98c` |

Paketet är lokalt i `.local/releases/status-reconnect-r7-20261006/`. Det byggdes från committad källkod, manifestets samtliga filer verifierades med SHA-256 och den isolerade testimagen byggdes från just paketet. Vid godkännande ska just denna image finnas på den faktiska apphosten; överför den vid behov och verifiera identiteten. Ingen ombyggnad eller installation ingår i denna leverans. Inget Windows-reläpaket ska installeras för detta appbyte.

## Före ett separat aktiveringsbeslut

1. Läs [RESULTS.md](RESULTS.md) och de öppna begränsningarna. De redovisade beloppen är historisk replay och styrker inte dagens köpbarhet.
2. Kontrollera paketfil, SHA-256, `RELEASE.json`-commit och samtliga filhashar. Kontrollera att överförd image-ID är exakt den som valts för aktivering; en ombyggnad får egen identitet och behöver egen verifiering.
3. Läs den **faktiskt använda** Compose-wrappern, dess ordnade `-f`-filer, miljöfiler och projekt-ID. Skapa en administratörsägd kopia av [app-only.override.example.yaml](app-only.override.example.yaml). Lägg den som sista Compose-fil utan att byta övriga filer eller global imagevariabel.
4. Spara privat bevis av upplöst Compose-konfiguration före/efter. Diffen ska bara omfatta `services.app.image`, `services.app.environment.BUILD_ID` och `services.app.environment.COMPLETE_RECIPES_ENABLED`. Bevara scheman, kommuner, femkällorspolicy, 36/48-timmarsgränser, kanaler, reläer, volymer och övriga tjänster.
5. Kontrollera befintliga pågående jobb före ett godkänt appbyte; processminnesjobb ska få avslutas innan processen ersätts. Ta en konsistent backup av **aktuell** användar-/planlagring. Spara privata hashvärden för befintliga planrevisioner, skafferi och ägarbindning. Kontrollera före start att appens mounts inte skuggar kandidatens runtimekod med äldre filer.
6. Starta endast `app` med befintlig wrapper, validerad sista override samt `--no-build --pull never`. Låt andra tjänster och aktuella data ligga kvar. Kontrollera `/ready`, build-ID, faktisk containerimage, skapa/läs en ny plan och läs äldre planrevisioner med rätt ägare. Kontrollera de laddade filerna mot RELEASE.json: complete-recipes.js ska ha SHA-256 17311d27a3a50ec9e75415316ca8cc90d10c94ac85380b36a75a3541d1b7114e och URL-parametern status-reconnect-1. Testa dubbelstart, omladdning, återupptagen status, receptbyte och uttrycklig omräkning. Ofärdiga processminnesjobb överlever inte en appomstart; färdiga sparade revisioner ska fortfarande läsas med rätt ägare.

Den isolerat **testade funktionsåtergången** behåller samma runtime och stänger av skapandekontrollerna för kompletta recept; gamla och nya planrevisioner förblir läsbara. Vid en eventuell senare **binär** återgång får endast den image som faktiskt kördes före bytet användas, med aktuell databas och alla senare revisioner kvar. Den äldre binärens läsning av planer som skapats med nya variationsfält har inte kvalificerats i detta prov och måste kontrolleras med kopia av aktuell lagring innan ett sådant imagebyte. Sätt aldrig tillbaka den äldre frysta testdatabasen eller ett gammalt användarlager. Det isolerade funktionsåtergångsprovet och den historiska WebKit-anmärkningen redovisas i [TESTS.md](TESTS.md).

Den tidigare [app-only-anvisningen](../package-variation-20261005/ACTIVATION.md) beskriver hur man granskar en Compose-diff och ägarisolerade revisioner i mer detalj. Dess paket-, image- och BUILD_ID-värden gäller **inte** denna kandidat.
