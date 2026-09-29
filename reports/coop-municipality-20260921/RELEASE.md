# Separat releaseförslag: Coop kommunurval och partiella fysiska erbjudanden

**Förberett och lokalt verifierat, inte aktiverat.** Bevara den väntande
ICA-releasen och tidigare Coop-underlag. Denna utökning är ett separat paket.

Verifierat för Lund 1281: nio egna Coop/Stora Coop-flöden, 499 kvalificerade
butik–variantposter, befintligt partiellt offers_only-kontrakt samt karantän.
Alla priser har exakt fysisk butikskoppling; Coop Online har inte utvidgats.
Inventering tar också med X:-tra Skansvägen, men dess PDF ger inga importerade
priser i detta paket. Det är 9/10 prisinsamling, inte full kommuntäckning.

Innehåll: kommuninventering från nationell Coop-karta och X:-tra-register,
positionsbevis mot SCB RegSO 2025, parametriserad isolerad collector, strikt
konto-ID-jämförelse, bevarade åldersvillkor och konservativ gemensam hushållsgräns.
SCB:s 2025-referens och registerkoordinater är uttryckliga osäkerheter.

## Före ett separat aktiveringsbeslut

1. Granska tilläggspatchen mot dess sparade smutsiga bas och integrera mot då
   aktuell kod. Det är inte en patch direkt mot ren HEAD. Koordinera releaseordning
   med väntande ICA-arbete; kopiera inte detta paket in i dess aktivering.
2. Verifiera samma tillåtna vanliga Chromium-/Coop-transport i avsedd servermiljö.
   Samla då färska baskällor och butiksvisa erbjudanden, behåll max 36/48h och
   kampanjutgång. Dagens sparade observationer får inte föryngras genom rebuild.
3. Koppla explicit kommuninventering till granskat område/butiksval i befintlig
   publiceringskedja. Ändra inte tyst befintliga planer, profiler eller deras
   adressortsval. Befintlig postnummerbaserad OWN-discovery ensam täcker inte
   Genarp/Veberöd; använd kommunens verifierade käll-ID:n och officiella adresser.
4. Behåll frivilligt tillskott: 1 937 karantänvarianter och X:-tra får inte stoppa
   giltiga baser eller de 499 godkända posterna. Gemensamt schema-/butiksfel ska
   fortfarande blockera hela berört källunderlag. Hushållstak delas konservativt
   för samma källkampanj och period; lokala pris-/medlemsavvikelser bevaras.
5. Kör då giltig oförändrad riktig 15/20-profil med jämförbara baser, 40/30/20-krav
   och max två verkliga butiker. Dagens 27 köpprov ersätter inte näringsprövning,
   menyresultat eller betans sparning/återläsning. Inga besparingar är belagda här.
6. Efter separat uttryckligt godkännande: använd befintlig backup, lås, validering,
   atomisk aktivering och processreload; kontrollera health/ready och en separat
   testidentitets checkout/audit. Ingen sådan åtgärd har genomförts nu.

## Avgränsningar och rollback

X:-tras åtta textsidor är hämtade; annons–pris–variant–villkor saknar ett verifierat
importavtal. Det är inte ett tomt erbjudandeflöde och inte bevisat enbart bildmaterial.
Blandade gruppköp, obelagd pant, isPil och övrig kvarvarande karantän är oförändrade.
Inga GTIN, paketvikter, referenspriser som ordinarie köppris eller näringsvärden
har skapats. 95%-snapshotgränsen är oförändrad och skiljs från partiell radimport.

Rollback vid en framtida release ska återgå till kodkompatibelt, fortfarande
giltigt basunderlag utan detta tillskott. Behåll råbevis och karantän. Återaktivera
inte en utgången eller för gammal snapshot. Arbetskopians tillägg kan granskas
mot `prework.tar.gz`; återställ aldrig hela arbetskopian över annat ocommittat arbete.

Ingen produktions-, Windows-, schema- eller serverändring i denna leverans.
Inga nya kedjor, bildmodeller, betalda anrop eller ändring av Primat/ICA-baspausen.
