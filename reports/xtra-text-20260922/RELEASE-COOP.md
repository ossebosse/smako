# Separat releaseunderlag: nio Coop/Stora Coop-butiker

**Verifierat i isolerad testmiljö. Ingenting aktiverat. X:-tra är inte ett
beroende för detta releaseförslag.** Behåll väntande ICA-release som eget arbete.

## Verifierat innehåll

Kommuninventering för Lund 1281 och nio egna fysiska strukturerade flöden:
Veberöd 1158, Stora Coop Lund 2696, Vildgåsen 3656, Värpinge 3659,
Mårtenstorget 3813, Klostergården 3820, Trollebergsvägen 3837,
Flöjtvägen 3839 och Genarp 3841. Befintliga kommunbevis och osäkerheter är
oförändrade. Inga priser kopieras mellan butiker eller från Coop Online.

Samtliga **499 godkända butik–variantposter** och **1 937 karantänposter**
bevaras med ursprungliga källsvar, hash och observationer 21 september.
Ny isolerad import med aktuell kod gav samma 499 radgodkännanden.
**493** når PriceUniverse för inköpsdagen **22 september**. Sex färdigrätts-
varianter på Stora Coop, kampanj 1681-41962, gällde endast 21 september och
filtreras korrekt bort. Exakta namn, offer-ID:n, pris och datum finns i
`coop-regression/expired-difference.json`. De sex ska inte återaktiveras.

De tidigare 27 ingrediensköpen och källbevisen är bevarade. 25 av köpen har
återkörts med aktuellt datum och passerar matcher, checkout och audit på
21,077 s för hela nio-butiksimporten. De två ytterligare Stora-proven och
tvåbutiksprovet återanvänds som hashstabil tidigare verifiering, inte som ny
insamling. **Detta är inte en näringsgodkänd 15/20-helmeny.**

126 unika berörda testfall passerade under etappen: först 125 på 49,55 s,
därefter samtliga 20 berörda X:-tra/radkontraktstester efter sista tillägget,
inklusive ett nytt hushållstakstest, på 16,58 s. Ruff och compileall PASS.
Ingen ny genomgång/utvidgning av Coop-karantäntyper gjordes.

## Exakt kvar före 15/20 och aktivering

1. Färska validerade Primat- och övriga baskällor behöver samlas i avsedd
   test-/driftmiljö med befintlig tillåten transport. Samma frysta kompletta
   basunderlag ska användas i båda armarna; inte lokal begränsad sökprojektion.
   Bevara 36/48 timmar och verkliga observationer. Erbjudanden ska också vara
   giltiga på inköpsdagen; dagens artefakter blir inte nya av rebuild.
2. Bygg två isolerade kandidater utan respektive med kommunens då kvalificerade
   Coop-poster. Bind exakt fysisk butik och använd kommuninventeringens ID:n;
   befintlig postnummerprefix-discovery räcker inte ensam för Genarp/Veberöd.
   Ändra inte tidigare användarprofiler eller deras adressorts-/butiksval.
3. Kör produktbunden näringskvalificering och faktisk ingrediensmatchning för
   erbjudandetillskottet. Kartlägg vilka produkter som klarar näringskraven,
   inte bara hur många som finns i PriceUniverse. Inga näringsvärden får gissas.
4. Kör den befintliga riktiga, oförändrade 15/20-profilen med 40/30/20-krav,
   samma recept/indata, medlemskontext och **max två fysiska inköpsställen**.
   Redovisa kostnad, valda produkter, köpgränser över recept/butiker, checkout,
   audit och körtid. Den körningen är **inte utförd i denna avgränsade etapp**;
   varken helmenykvalitet eller besparing är därför belagd.
5. Verifiera frivilligt tillskott/felfall i den då aktuella publiceringskedjan,
   giltigt rollbackunderlag, servertransport, health/ready, isolerad testidentitets
   planering samt sparning/återläsning. Granska kodpatch mot sparad smutsig bas
   och samordna version med väntande ICA-arbete utan att blanda paketen.
6. Begär separat uttryckligt aktiveringsbeslut. Först därefter får befintliga
   lås-, backup-, validerings-, atomisk aktiverings- och reloadrutiner användas.

## Avgränsning och framtida rollback

Coop-tillskottet är partiellt. Alla 491/2 436 tidigare varianter behöver inte
godkännas innan de självständigt verifierade raderna kan släppas. Gemensamma
kritiska schema-/butiksfel stoppar dock berört underlag. Blandade gruppköp,
isPil, pant och övrig karantän är oförändrade; X:-tra behandlas separat.

Vid en framtida rollback: ta bort tillägget genom ordinarie publiceringsväg
och använd kodkompatibel, fortfarande giltig bas. Återaktivera inte gamla eller
utgångna priser. Återställ inte hela arbetskopian över andra ocommittade filer.

Primat, ICA-baspaus, ICA-release, aktiva priser, användarprofiler, Windows-uppgift,
serverkonfiguration och scheman har inte ändrats. Ingen bildanalys eller betald
API-tjänst användes. Ingen flerdagarsstabilitet eller full kommuntäckning påstås.
