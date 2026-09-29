# Separat releaseunderlag: Willys automatisk textkvalificering

**Ingen produktionsaktivering.** De sju officiellt kommunvalda reklambladsbutikerna och tidigare källor/releaseunderlag behålls.

Leveransen innehåller generella dokumentregler, SourceOffer/radvalidering, fortsatt standardinsamling och stöd för belagda styckavtal via den befintliga prisberäkningen. Den har ingen ny produktlista per PDF, generell godkännandeflagga, databas, refreshmekanism eller ändring av aktiva scheman. Uppdatera app och grocery_data som en kompatibel versionsuppsättning vid ett eventuellt senare separat releasebeslut.

253 unika riktade tester passerar: ny dokumentkvalificering, äldre Willys-flöde, styck- och gruppköp, audit, hushållsgränser, OWN, ICA, City Gross och Primat. Ruff och compileall redovisas i paketet. Lidl-pilotens saknade historiska fixture/testskydd förblir olöst; dessa tester påstås inte reparera det.

Faktiskt hämtade v39-data går genom OWN och PriceUniverse. Utan granskningsregister: 7 Hemma- och 29 Willys-poster. Med tidigare exakta granskningar: 24 per Hemma-butik och 64 Rosengård, totalt 208. Alla slutligt kvalificerade källrader har jämförts exakt med importerade priser, produkt/mängd, villkor och datum. Representativa matköp är verifierade; produktdeklarationer/näring har inte fabricerats.

Malmös isolerade ordinarie rebuild/publicering/reload, omstart, no-work-kontroll, hämtfel och återhämtning passerar med 184 reklambladsposter och oförändrad giltig City Gross-/Lidl-bas. Första efterfrågestyrda kontrollens lokala publiceringsregistrering redovisas separat. Nätverk, replay och injektion är åtskilda.

Den sista parserändringen spärrar panttext även under en prisruta. Den är verifierad med riktat motprov och oförändrade slutliga SourceOffer-rader för samtliga 208 importerade poster. Driftprovets körda provider-, checkout-, publicerings- och refreshkomponenter är hashidentiska med leveransen; själva parserfilen ändrades efter driftprovets start och kördes därför om separat. Paketet gör inte anspråk på en ytterligare verklig nätinsamling eller full driftkörning av just den sista parserändringen. Exakt komponentbevis finns i `FINAL-VERIFICATION.json`.

Kvar före ett bredare releasebeslut:

1. Ett verkligt kampanjbyte och en verklig tidigare ogranskad utgåva. Två regionala v39-PDF:er samt syntetiskt okänd hash/nya datum är inte detta bevis.
2. Färsk komplett Lund-bas och fullständigt Lund-publiceringsprov. Gammal bas var förfallen; ett erbjudandeflöde ensamt klarade inte den ordinarie kompletta provkassen. Den inaktiva prisartefakten har 24 poster.
3. Fullständigt Malmö-publiceringsprov med aktuell komplett federerad bas/Primat kvarstår separat.
4. Vid ny layout eller otillräcklig text: behåll berörda poster utanför köpimporten och redovisa granskningsbehovet. Säkerhetsspärrarna ska inte kringgås.

Följ befintligt kommunval och behovsstyrning. De privata proven anger nästa reklambladshämtning 25 september cirka 20:40–20:41 svensk tid och kampanjövergång 28 september 00:00. Kontrollera alltid aktuell basfärskhet vid senare release; dessa observationer är inte förnyade av rebuild.
