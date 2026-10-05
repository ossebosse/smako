# Förberett app-only-byte – inte aktiverat

Betan, driftkonfigurationen, reläerna, insamlingsjobben, databasen och användarrevisionerna har lämnats orörda. Denna instruktion gäller ett separat framtida beslut om **endast appen**. Den tidigare 2816-imagen ska inte installeras som ett dolt mellansteg, och en äldre databas får aldrig återställas över senare användardata.

| Identitet | Värde |
| --- | --- |
| Runtime-commit | `82de80e1ae898e2ab005c16c8d95e6670898be93` |
| Serverpaket | `smako-server-82de80e1ae89.zip` |
| Paketstorlek | 2 836 739 byte |
| Paketets SHA-256 | `1dedad3f09443fe7fcc09ed79427932f0c612f08b83314991f52f016a44e1708` |
| Verifierad testimage-ID | `sha256:30de1272e6d2896714f9e815f7d6537019fc43548c4a55767a812c379ebb1b0a` |
| Avsett BUILD_ID | `package-variation-82de80e1ae89` |

Paketet är lokalt i `.local/releases/package-variation-r6-20261005/`. Det byggdes från committad källkod, manifestets samtliga filer verifierades med SHA-256 och den isolerade testimagen byggdes från just paketet. En separat imageöverföring till drifthost krävs vid ett senare godkännande. Inget Windows-reläpaket ska installeras för detta appbyte.

## Före ett separat aktiveringsbeslut

1. Läs [RESULTS.md](RESULTS.md) och de öppna begränsningarna. De redovisade beloppen är historisk replay och styrker inte dagens köpbarhet.
2. Kontrollera paketfil, SHA-256, `RELEASE.json`-commit och samtliga filhashar. Kontrollera att överförd image-ID är exakt den som valts för aktivering; en ombyggnad får egen identitet och behöver egen verifiering.
3. Läs den **faktiskt använda** Compose-wrappern, dess ordnade `-f`-filer, miljöfiler och projekt-ID. Skapa en administratörsägd kopia av [app-only.override.example.yaml](app-only.override.example.yaml). Lägg den som sista Compose-fil utan att byta övriga filer eller global imagevariabel.
4. Spara privat bevis av upplöst Compose-konfiguration före/efter. Diffen ska bara omfatta `services.app.image`, `services.app.environment.BUILD_ID` och `services.app.environment.COMPLETE_RECIPES_ENABLED`. Bevara scheman, kommuner, femkällorspolicy, 36/48-timmarsgränser, kanaler, reläer, volymer och övriga tjänster.
5. Ta en konsistent backup av **aktuell** användar-/planlagring. Spara privata hashvärden för befintliga planrevisioner, skafferi och ägarbindning. Kontrollera före start att appens mounts inte skuggar kandidatens runtimekod med äldre filer.
6. Starta endast `app` med befintlig wrapper, validerad sista override samt `--no-build --pull never`. Låt andra tjänster och aktuella data ligga kvar. Kontrollera `/ready`, build-ID, faktisk containerimage, skapa/läs en ny plan och läs äldre planrevisioner med rätt ägare. Testa dubbelstart, jobbförlopp, receptbyte och uttrycklig omräkning mot det nya valet.

Den isolerat **testade funktionsåtergången** behåller samma runtime och stänger av skapandekontrollerna för kompletta recept; gamla och nya planrevisioner förblir läsbara. Vid en eventuell senare **binär** återgång får endast den image som faktiskt kördes före bytet användas, med aktuell databas och alla senare revisioner kvar. Den äldre binärens läsning av planer som skapats med nya variationsfält har inte kvalificerats i detta prov och måste kontrolleras med kopia av aktuell lagring innan ett sådant imagebyte. Sätt aldrig tillbaka den äldre frysta testdatabasen eller ett gammalt användarlager. Det isolerade funktionsåtergångsprovet och WebKit-anmärkningen redovisas i [TESTS.md](TESTS.md).

Den historiska [app-only-anvisningen](../recipe-usability-20261005/ACTIVATION.md) beskriver hur man granskar en Compose-diff och ägarisolerade revisioner i mer detalj. Dess paket-, image- och BUILD_ID-värden gäller **inte** denna kandidat.
