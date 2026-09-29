# Separat aktiveringsunderlag – Lund 1281

**Status: INTE REDO.** Primat 1004409 saknar den obligatoriska full_catalog-täckningen. Komplett federation och fyra fria profilprov måste genomföras när beroendet är återställt. Den separata OWN-only-publiceringen är inte en ersättande Lund-release.

Ingen aktivering är utförd eller beslutad. Kandidatens faktiska provstatus och
eventuella blockerare finns i VERIFICATION.md. Detta dokument är inte ett
godkännande att ändra produktion, scheman eller användarval.

## Paket och gränser

Använd det innehållsidentifierade paketet i final-image.json och samtliga
källhashar i source-manifest.json. Arbetskopians tidigare opublicerade ändringar
ingår; en ren Git HEAD är inte samma paket. App, collector och refresh ska använda
samma verifierade bild. Paketkontrollen och beroendekontrollen finns i
results/final-image-verification.json. Prisinsamling från lokal Willys-relay
måste även fortsättningsvis valideras som källartefakt före import.

Kommunvalet avser datainsamling. Det ändrar inte en användares butiksval.
Gemensamma kommunjobb använder 1281. Befintliga ICA- och Hemköpsavgränsningar
redovisas i verifieringsrapporten och får inte beskrivas som full kommuninventering.

## Kontroller som måste upprepas vid ett senare beslut

- Läs aktuellt effektivt källval och de sex obligatoriska baskontexterna från
  konfigurationen. Kontrollera officiella butikskopplingar, kanaler och kommunstatus.
- Kör ordinarie behovsstyrd uppdatering för de källor som då är förfallna.
  Kontrollerna är oförändrade: varning vid 36 timmar, hård gräns vid 48 timmar.
  Bedöm äldsta verkliga basobservation; byggtid och replaytid är inte observationer.
- Kontrollera varje kampanjs start, slut, dagsvillkor, medlemskap och butiksgiltighet.
  Denna söndags provdata får inte återanvändas som giltiga måndagserbjudanden.
  Dokumentbundna granskningar gäller endast det verifierade dokumentet.
- Verifiera komplett baskontexttäckning efter federation. Validera den atomiskt
  publicerade artefaktens hash och det manifest serving-processen faktiskt laddat.
  En frivillig källas fel får inte avlägsna fungerande bas eller förlänga en kampanj.
- Kontrollera ordinarie reload, sparade planers läsbarhet, pris-/näringsmärkning och
  separata instruktioner för ungefärlig vikt och hela förpackningar.
- Behåll en verifierad återställningspunkt. Läskompatibilitet i äldre kod är inte
  bevis för att äldre kod kan räkna om den nya planens berednings-/köpmetod.

## Separata öppna releasekontroller

Fullständigt aktuellt Malmö-publiceringsprov genomförs inte här. Den historiska
Lidl-fixturen för 2026-09-15 saknas fortfarande; detta prov återskapar inte dess
deklarations-, identitets- eller beredningsbevis. Se verifieringsrapporten för
den bedömda påverkan på den aktuella Lund-kandidaten.
