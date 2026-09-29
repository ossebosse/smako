# Aktiveringsunderlag – gemensam köpplanering

**Inaktiv kandidat. Ingen produktionsaktivering har genomförts.** Detta underlag kompletterar tidigare ICA-, Coop/Stora Coop/X:-tra-, Willys-, Hemköp-, City Gross-, Lidl- och Primat-arbete. Det ersätter inte deras väntande releasekontroller.

## Vad kandidaten innehåller

Gemensamma källbundna köptermer genom collector, OWN och PriceUniverse; valbart uppskattningsläge genom API/UI och sparade planer; hela cirka-förpackningar och lösvikt; villkorade kampanjval; identifierade blandgrupper genom befintlig gruppmotor; separat pant-/kvalitetsstatus; uppmätt mängd vid lagerbokning; officiell Arla-deklaration och märkt SLV-persikoreferens.

`purchase_planning_mode=exact` är standard för gamla och nya anrop där fältet saknas. Befintligt närings-opt-in, proteinmål, allergispärrar, medlemsval, butiksval och område behålls. Kommuninsamling ändrar inte användarens val. `estimated` väljs uttryckligt. En villkorad grupp är ett extra inköpsval, inte en automatisk specifik receptingrediens.

Ingen ny prismotor, databas, schemaändring eller parallell refreshmekanism ingår. Nya köptermer lagras i befintliga JSON-payloads och serialiserade artefakter. Bakåtkompatibla defaultfält lämnas utanför äldre representationer så att befintliga artefakthashar går att läsa. Prisberäkningscachens versionsnyckel är uppdaterad så att gammal semantik inte återanvänds som nytt beräkningsresultat.

## Verifierat kandidatpaket

[PACKAGE.json](PACKAGE.json) innehåller käll-/datahashar, tidigare paketreferens, ursprunglig arbetskopiebaslinje och evidenshashar. Kodlistan är den bevarade arbetskopians beroendemängd; den är **inte** ett påstående om att all kod där skrevs i denna etapp. Arbetskopian innehöll tidigare opublicerat kedjearbete och får inte ersättas med en ren HEAD-version vid paketering.

Se [VERIFICATION.md](VERIFICATION.md) för 768 unika passerade regressioner, kompilering/statisk kontroll, kommun-/rebuild-/reload-/omstartsprov, felinjektion och den riktiga oförändrade 15/20-profilen. Uppskattad radstatus och villkorade varianter hålls separata från exakta kvittopåståenden.

## Förutsättningar före framtida aktivering

1. Ett aktuellt komplett basunderlag måste finnas inom **oförändrade** färskhetsgränser. Använd ordinarie källhämtning och godkända snapshotreferenser. Historiska testklockor eller rebuildtid får inte föryngra observationer.
2. Kör ordinarie kandidatbyggnad, validering, atomisk publicering och serving-reload mot dessa aktuella referenser. Kontrollera att alla obligatoriska baskontexter finns kvar. Ett frivilligt erbjudandefel får behålla giltig LKG men ska inte stoppa fungerande bas.
3. Det fullständiga Malmö-publiceringsprovet med aktuell komplett bas kvarstår. Etappens isolerade Malmöprov med bevarad City Gross-bas och Willys-/Lidl-tillskott är inte samma integrationsbevis.
4. Den historiska Lidl-fixtureluckan är fortsatt öppen. Återställ underlaget eller verifiera uttryckligen motsvarande historiska skydd innan denna punkt kan stängas. Ny oberoende verklig kampanjutgåva är också en kvarstående generaliseringskontroll.
5. Kontrollera användarval, märkning, lagerbokning och representativa köp efter framtida aktivering. En osäker variant eller pantuppgift ska fortfarande synas som sådan; generell godkännandeflagga får inte användas för att göra allt grönt.

Detta är en checklista för en separat framtida aktivering, inte genomförda produktionsåtgärder. Windows-uppgift och aktiva scheman har inte ändrats.

## Återgång

Behåll föregående kodpaket, godkända bas-/erbjudandesnapshotreferenser och föregående aktiva PriceUniverse-manifest vid en eventuell framtida aktivering. Återgång sker med ordinarie atomisk artefakt-/kodhantering; gör ingen destruktiv återställning av arbetskopian eller användardata. Gamla exakta användarval och planer är bakåtkompatibla. Nya uppskattade/variantvillkorade planer ska inte öppnas i äldre kod och presenteras som exakta; bevara dem och deras lägesfält tills kompatibel kod används.

Källblockerare i [BLOCKERS.md](BLOCKERS.md) är avsiktliga begränsningar av en partiell import. Källkonflikt, okänd pant eller saknad variant-/allergi-/näringsgrund ska inte kringgås under release.
