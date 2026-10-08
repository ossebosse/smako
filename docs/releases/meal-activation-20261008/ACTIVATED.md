# Måltidsbibliotek aktiverat – 8 oktober 2026

Användarens uttryckliga appgodkännande genomfört 20:04:26 UTC.
Beta kör `meal-library-42fab888ffd7`, image
`sha256:d17a4c077ad68ec70f5b821cc2ffbee69bc2f9012fa44ba240bce2fc2203908a`.
Runtimepaketcommit `42fab888ffd7` sammanför exakt 54cb:s måltids-/sökmotor,
de åtta receptens data-only-image 9784eb87 och senare granskade status-/incident-
och nullable-erbjudandesorteringsrättningar. Inget av den nya inköpslistekoden ingår.

Paket `smako-meal-library-42fab888ffd7.zip`, SHA-256
`a96f663bd9130db910c1a5aec70b588997c1a518da5de5a60549cdd640cd77fe`.
Paketet är ett fyra-filers delta ovanpå den identifierade receptimagen; inte
ett fristående källpaket. Basmanifest och exakt imageexport i EVIDENCE.json.
Ingen ombyggnad på servern.

## Kontroller

- Befintligt operationslås. Ingen plantrafik på 15 minuter samt två lugna
  CPU-prov före byte; detta är ingen direkt räknare över processminnesjobb.
- Aktuell konsistent PlanStore-backup, 105 529 344 byte, full integrity/FK PASS.
  Alla 228 gamla revisioner och 65 privata tillståndsrader bevarade. Alla gamla
  revisioner materialiserade med nya modellen. Grocerys användar-/kvitto-/sessionstabeller tomma.
- Upplöst Compose ändrade endast app.image och app.BUILD_ID. Receptflaggan
  förblev true. Mounts, övriga containrar, scheman, källor och proxy oförändrade.
- `/ready` 200, oförändrat prismanifest bc39552c…, fem obligatoriska baser färska.
  Laddat JavaScript matchar c5d7a4e2… / meal-library-1.
- 47 riktade tester lokalt och 47 mot imagekod PASS. Tidiga testmiljöfel
  (saknade testberoenden/fel testmount) bevarade, inga runtimeundantag införda.
- Isolerad Chromium kombinationsvecka PASS. Tidigare oförändrade bibliotekets
  innehålls-/sökbevis återanvända från all-meal-classes och willys-storage-search.
- Riktiga beta-knappar: Chromium publik fem enkla middagar (cirka 54,5 s till
  resultat); WebKit personlig 15 tillfällen/30 portioner, byte, omräkning,
  revisionsläsning och ägarskydd PASS. Dubbelstart/omladdning ingår.
  Inga oväntade pageerror/network failures. Mobil viewport, inte fysisk iPhone.
  OIDC saknas fortfarande: gästsessionsprov, inte verifiering av signerad kontoinloggning.

## Kapacitet och säkerhetskopiering

Server 9 324 527 616 byte före imageinläsning, 7 382 798 336 före arkivåtgärd,
11 031 560 192 efter åtgärd, 10 925 735 936 efter ny backup och aktivering.
Det tidigare godkännandet för säker arkivering användes enbart för den inaktiva
17:02-backupens `grocery.sqlite3` (3 648 765 952 byte), inga aktiva data.
Arkiv strömmat direkt till skyddat `D:/Smako-backups/meal-activation-20261008/`.
Full återställningskopia hashmatchar originalet; 43 tabeller läsbara. Originalets
fulla integrity-resultat återanvändes för exakt samma hash; ett nytt långsamt
fullprov avbröts och redovisas inte som PASS. Tar bevarar mode/uid/gid.
Serverkopian togs bort först efter kontroller av hash, mounts och öppna filer.
Arkiv SHA-256 `ac37f2baa999c44c38bfa3e19d0f3053cbbb7564521efd807623471a5559598a`.
Ingen annan rensning och inga tidigare images togs bort.

## Driftväg och funktionsåtergång

Den verkliga `/opt/smako/compose` avslutas nu med
`/opt/smako/overrides/meal-library-42fab888ffd7.yaml`.
Vid separat motiverad funktionsåtergång: ändra bara COMPLETE_RECIPES_ENABLED
 till false i samma image, kontrollera upplöst diff och använd befintligt lås
 och app-only up --no-deps --no-build --pull never. Behåll senaste data.
Detta bevisar inte äldre binärkompatibilitet. Återställ aldrig äldre databas.

Privata backuper, råa webbläsarsvar och konfigurationer ligger utanför Git.
Maskinläsbar sanerad sammanfattning: EVIDENCE.json.
