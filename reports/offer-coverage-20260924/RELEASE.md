# Separat releaseunderlag – automatisk Willys-/Lidl-kvalificering

Status: verifierad isolerad kandidat, inte produktionsaktiverad. Tidigare kedjepaket och Primat är bevarade. `PACKAGE.json` anger exakt slutkod och dokumentation; `baseline-manifest.json` låser jämförelsens råunderlag. Läs [mätresultat och begränsningar](README.md) före releasebedömning.

Ändringen ersätter manuellt arbete för fler slutna textfall i Willys och kvalificerar 14 nya Lidl-livsmedel genom sammansatt dokumentidentitet. Ingen ny connector, prisdatabas, prissättare eller refreshmekanism införs. Befintliga policies/snapshots stöds fortsatt; Lidl v2 får ett uttryckligt nytt policynamn.

Validering: 189 unika passerade tester, Ruff, compileall, samtliga kvalificerade rader genom collector/OWN och isolerat PriceUniverse i Lund/Malmö, matcher/checkout/audit, verklig separat v40-text med framtida datumstopp. Två faktiska Lidl-hämtningssekvenser omfattar totalt 14 externa anrop. Willys-jämförelsen använder oförändrat tidigare råunderlag. Inga modell- eller bildanrop.

Privat ordinarie runner/CLI/serving-start har godkända omstarts-, no-work-, fel/LKG- och återhämtningsfaser med slutkod. Första/andra publiceringskörningarna är märkta mellanliggande kod; slutkodens fel- och återhämtningsprov gör också fulla normala rebuilds och reload. Källjobbets separata Lidl-återhämtning tar emot den faktiska nya PDF-revisionen med originaltider. Se `runtime-1280/ACCEPTANCE.json`, `lidl-recovery-verification.json` och `current-expiry-verification.json`.

Kvarstående releasekontroller och begränsningar:

- Fullständig aktuell Malmö-bas och federerat publiceringsprov inklusive övriga baskällor/Primat. Den privata City Gross-basen är färsk; Lunds kvarhållna Willys-onlinebas är stale och ger inte full publiceringsrätt.
- Willys automatiktäckning ökar, men totalantalet unika kvalificerade priser är oförändrat i jämförelsen. Nettotillskottet får inte påstås färdigt. Annan verklig Willys-kampanjvecka saknas fortfarande som generaliseringsprov.
- Lidl v40 ger fyra automatiska bindningar men inga köp före 28 september. Det är inte ett redan genomfört framtida driftbyte.
- Osäkra villkor, prisrutor, variantgrupper, pant och okänd dokumenttext kräver fortfarande granskning. Manuella godkännanden får inte ärvas av en ny PDF; därför har dagens nya Lidl-revision 14 automatiska och 0 ärvda manuella poster, jämfört med 14 + 3 i den frysta gamla revisionen.
- Ingen ny näringsbehörighet. Det historiska Lidl-testet med saknad adapter-fixture är fortfarande en öppen testlucka, inte ett passerat test.
- Första no-work-försöket behövde lokal statusinitiering och är sparat som `demand_bootstrap`; det andra försöket bevisar verkligt not_due utan child eller externa prisanrop.

Återställning ska följa befintlig snapshot-/LKG-policy och verklig giltighet. Detta paket ger inte tillstånd att återaktivera förfallna observationer, flytta användares inköpsområde eller ändra aktiva scheman. Ingen produktionsändring har genomförts.
