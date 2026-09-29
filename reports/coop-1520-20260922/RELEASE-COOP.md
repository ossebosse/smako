# Separat beslutsunderlag: kommun-Coop efter riktig 15/20-prövning

**Beslut: inte redo för aktivering i betan. Ingen aktivering utförd.**

Den tekniska kandidaten och den kontrollerade planeringsjämförelsen är körda.
Coop-tillskottet ger ingen belagd förbättring i denna profil: 536,27 kr med och
utan tillskottet, samma valda produkter och samma inköpskontexter. Ingen ny fysisk
Coop-rad väljs. Resultatet motiverar inte ett besparingspåstående.

## Tekniskt verifierat

- Ny insamling på servern från samtliga nio verifierade kommunbutiker; 493
  radgodkända butik–variantposter, 1 937 i karantän. Sex utgångna Stora-poster
  från 21 september är fortsatt borta. X:-tra ingår inte.
- Kommun-ID-inventering → befintlig collector/OWN → vanlig fullständig
  PriceUniverse-byggare med explicit frivilligt kommun-Coop-tillskott.
  Genarp/Veberöd försvinner inte genom postnummerurval. Okänd kommun tas inte med.
- Två isolerade byggen från samma kompletta källdatabas/Primat-cache, identiska
  basprodukter och näringsfakta. Primat kvar; ICA-baspaus och väntande release kvar.
- Verklig HTTP-planering, 15 måltider/20 portioner, 40/30/20 g protein,
  medlemskap av, max två inköpskontexter. Identisk fryst receptpool för jämförelsen.
  Separat testidentitet, privat plandatabas, sparning/identisk återläsning.
- Fel i frivillig Coop-databas stoppar inte giltig bas. Butiksidentitet,
  köpgränser över butiker/alias, flerköp och 36/48 timmar regressionstestade.
- Privat publiceringsprov av validering, felaktig kandidat, saknad lineage,
  giltig rollback, nekad för gammal rollback och återläsning efter omstart.
  Exakt utfall i server-results/publication-result.json.

## Affärsmässigt verifierat

Oförändrad total kostnad och oförändrad meny. 493 importerade priser är inte
493 näringsgodkända produkter. Ingen av tillskottets produkter har verifierat
produktbundet näringsunderlag i de tillgängliga kompletta baskällorna.
Detaljerad matchning och faktiskt prövade produkter finns i COVERAGE.md och
product-qualification.json. De tidigare ingrediensköpen förblir prisbevis,
inte bevis för en näringsgodkänd helmeny.

Originalprofilens allow_nutrition_estimates=true är oförändrat. Vi har inte
lagt till näringsvärden eller flyttat deklarationer genom namnlikhet/siffer-ID.
Coop Online Syd är fortfarande en onlinekanal. Dess befintliga priser får inte
beskrivas som fysiska priser i kommunbutikerna.

## Exakta kvarstående hinder före den avsedda releasen

1. **Produktbunden näring/identitet saknas för tillskottet.** För att verifiera
   faktisk användning i den näringsbegränsade profilen behövs belagd länk från
   en relevant fysisk erbjudandevariant till produktdeklaration, eller annan
   redan tillåten verifierbar produktbunden näringskälla. Ingen uppskattad
   GTIN-mappning. Kör sedan om samma parade profil; en förbättring är inte garanterad.
2. **Separat driftsatt Coop-paket återstår.** Den testade förberedda
   schedulerbilden 0.1.0-smako-ica-structured-lund-20260920a saknar Playwright. Serverns redan installerade browserbild
   smako-ica-shadow:20260915 klarade däremot alla nio hämtningar. En framtida
   Coop-release måste binda den verifierade browsertransporten, godkänd
   kommuninventering och de två explicita byggargumenten till en separat
   publiceringskörning. Ingen sådan produktionskoppling eller återkommande
   körning har installerats. Hela denna smutsiga arbetskopia eller det väntande
   ICA-paketet får inte deployas som en genväg.
3. **Tidsbundet underlag måste omprövas vid beslut.** Rollbackens exakta sista
   användningstid finns i publication-result.json. Vid senare beslut ska nya
   basobservationer samlas där 36/48 timmar kräver det, aktuella kampanjer
   kontrolleras och båda armarna byggas på samma nya frysta underlag. Rebuild
   eller denna rapport förlänger inte prisernas giltighet.

Punkt 1 blockerar ett påstående om användbar förbättring av den aktuella
15/20-profilen; priserna är tekniskt radgodkända även utan näring. Punkt 2 är
ett faktiskt driftpaketeringsberoende, inte en blockerad offentlig källa.
Punkt 3 är en tidsstyrd aktiveringskontroll. X:-tra, övriga karantäntyper och
Windows-administratörssteget för ICA är inte beroenden för Coop-kandidaten.

## Aktivering och rollback – endast framtida separat beslut

Efter separat beslut: bygg/granska ett eget Coop-paket mot kompatibla gemensamma
priskontrakt, använd befintligt gemensamt lås, färska källor, validering och
atomisk aktivering/reload. Verifiera då live health/ready och separat plan.
Spara kodkompatibelt giltigt A-underlag. Rollback tar bort det frivilliga
Coop-tillskottet genom samma publiceringsväg; återaktivera inte gamla priser.

## Faktiskt aktiverat

**Ingenting från denna etapp.** Betans tidigare app och scheduler,
prismanifest, profiler, Windows-uppgift och scheman har inte ändrats.
Den ordinarie tidigare insamlingen hade redan förnyat betans underlag till
22 september före testet. Ingen flerdagarsstabilitet påstås.

Slutligt privat publiceringsprov: samtliga sju kontroller PASS, 140,08 s.
Slutlig live health/ready: 200/200. Detaljer i PUBLICATION.md.
