# Separat releasebeslut: Coop-näring och browserpaket

**a) Redo för separat aktiveringsbeslut om den verifierade partiella kandidaten, vid slutprovet 22 september 2026. Ingen aktivering utförd.** Oförändrad menybudget är inte en blockerare: 14 tidigare spärrade rader kan nu prövas korrekt, och två konkreta ostalternativ har klarat receptets näringskrav, checkout och audit. Det finns fortfarande inget belägg för besparing i den aktuella menyn.

## Verifierat innehåll

- Nio redan kommunverifierade Coop/Stora Coop-butiker; 493 godkända butik–variantposter, 1 937 i karantän. Befintlig partiell radimport, butikskoppling och källbevis bevarade. De sex utgångna Stora-raderna återkommer inte.
- Faktamodellen återanvänder kvarhållna, verifierbara katalogfakta med strikt identitets-, variant-, förpacknings- och versionsbindning. Ingen prisöverföring från Coop Online. Saknad näring, exakt kolhydratvärde eller GTIN hittas inte på. Produktdeklaration och tillåten uppskattning skiljs åt.
- Samma verkliga 15/20 i båda armarna: 536,27 kr, samma 12 valda produktposter och två inköpskontexter, inga valda fysiska Coop-priser. Identiska kompletta baskällor, recept och näringsfaktaversion. Produktbundna näringsprövningar 0 → 14 godkända av 22. Medlemskontext, 40/30/20-krav och butikstak oförändrade.
- Slutkodens körbara separata browserimage testad på avsedd server som användare 10001, utan utvecklarkod monterad. Faktisk publikhämtning, operationslås, synlig karantän och felreturkoder. Dokumenterad och exporterad image i [PACKAGE.md](PACKAGE.md).
- 125 fokuserade tester samt Ruff/compileall PASS. HTTP-planering, sparning/återläsning, checkout, audit, health/ready och privat publicering/rollback verifierade. Kodhasharna för hela backend/grocery-app är samma i slutlig A/B och i paketet. Publiceringskod och prisartefakter är oförändrade mellan privat publiceringsprov och slutlig A/B.

## Kvarstående avgränsningar, inte blockerare för den partiella releasen

Åtta fettuccinerader saknar kvalificerad näringsdeklaration och passar inte de prövade recepten som kräver torr pasta. Tomaternas produktreferens fungerar, men det aktuella couscousreceptets sökning når inte proteinkravet. Övriga oprövade produkter, låg semantisk säkerhet och karantäntyper är inte generellt näringsgodkända. För profiler som behöver ett exakt näringsvärde där deklarationen bara anger en gräns återstår det fältet som spärr. Full reklambladstäckning, X:-tra, bildtolkning, nya kedjor och medlemsaktivering ingår inte.

## Kontroller vid ett senare uttryckligt aktiveringsbeslut

1. Kontrollera samma granskade imagehash och inkrementella kodpaket mot driftens gemensamma priskontrakt. Detta är ett separat Coop-paket; kopiera inte hela den ärvda smutsiga arbetskopian och skriv inte över den väntande ICA-releasen. Framtida inkoppling/uppdateringsschema kräver separat beslut och ingår inte i denna körning.
2. Kontrollera aktuella källor/kampanjer och 36/48-timmarsregeln igen. Rollbackbasens äldsta observation är **21 september 03:17:55 Europe/Stockholm**; varning **22 september 15:17:55**, absolut stopp **23 september 03:17:55**. Dessa tider förlängs inte av rebuild, export eller beslut. Efter stopp krävs ny faktisk basinsamling och nytt parat prov. Ost-/tomatkampanjerna i bevisen gäller 21–27 september, men detta förlänger inte baskatalogens färskhet.
3. Använd samma kanoniska operationslås, validering, atomiska manifestbyte och processreload. Spara kodkompatibel, fortfarande giltig A-bas. Privat rollback är testad både positivt och mot för gammalt underlag; använd aldrig ett utgånget LKG som prisrollback.
4. Efter ett framtida godkänt byte: kontrollera aktivt manifest, körande process, live health/ready och separat testidentitet med sparning/återläsning. Kontrollera explicit att Coop faktiskt finns i aktivt PU; enbart lyckat basbygge eller latest-candidate räcker inte.

Vid slutprovet finns inget kvarstående externt API-/browser-/näringshinder för den avgränsade kandidaten. De återstående aktiveringskontrollerna ovan är tids- och driftbundna och har avsiktligt inte utförts som produktionsåtgärder.

## Faktiskt aktiverat

**Ingenting.** Primat, aktiv app/scheduler, användarprofiler, planer, priser, Windows-uppgift, scheman och den väntande ICA-releasen är bevarade. Produktions-health/ready är 200/200 med tidigare image `billigaste-veckomenyn:0.1.0-smako-price-recovery-lund-20260914a`. Aktivt prismanifest är oförändrat: `price-universe:8cfb4f26664c18415b606d55f3075b4ee0d36b5f8f6d8f175e6fe26b2e1127ed`. Ingen observerad flerdagarsstabilitet påstås.
