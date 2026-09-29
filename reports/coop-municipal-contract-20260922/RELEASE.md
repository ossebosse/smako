# Separat kommunverifiering – ingen aktivering

**Tekniskt verifierat lokalt:** samma kommunstyrda kod för inventering, butiksspecifik transport, befintlig radvalidering, OWN, isolerat PriceUniverse och persistent uppdateringsurval för Lund och Malmö. X:-tras två faktiska butikskällor har upptäckts och hämtats på nytt; befintlig textparser ger nio aktuella köppriskandidater per lyckad butik. Representativa ingrediensköp klarar checkout/audit. Alla misslyckade och geografiskt osäkra butiker redovisas.

**Partiellt:** Malmö har sex blockerade verifierade kommunbutiker samt en geografiskt okänd X:-tra-butik. X:-tra har både annonskarantän och obestyrkt bildtäckning. Ingen garanti ges för framtida avvikande PDF-layout. Inga nya näringsgodkända helmenyer eller besparingar påstås genom denna verifiering.

**Faktiskt aktiverat: inget.** Ingen serverkonfiguration, aktiv databas/PriceUniverse, användarprofil, Windows-uppgift eller schema har ändrats. Primat, Coop Online och väntande ICA-release har lämnats orörda.

## Bevara den tidigare avgränsade Coop-releasen

Det befintliga paketet i `../coop-nutrition-20260922` behåller sina fakta, 15/20-resultat och serverbevis. Den tidigare verkliga jämförelsen var 536,27 kr i båda armarna med samma produktfaktaversion. Den observationen är inte en ny jämförelse med Malmö eller X:-tra.

De nio fungerande Coop/Stora Coop-butikerna i Lund behöver inte invänta X:-tra eller Malmös blockerade källor. Den befintliga produktionsorienterade Coop-providergränsen fortsätter att utesluta X:-tra. Den nya gemensamma kommun-CLI:n bygger endast isolerade kandidater med explicit kommunidentitet; den aktiverar ingenting.

## Inför ett separat beslut om detta tillägg

1. Granska `incremental.patch` mot den bevarade smutsiga arbetskopian, inte som en ersättning av tidigare arbete. Källbindning, uppdateringsurval och tester är den avgränsade förändringen. Binär PDF-fixture finns i `review-files.tar.gz` och hashmanifestet.
2. Om denna nya kommunorkestrering ska köras på servern: paketera just slutkoden i en ny separat kandidatimage och verifiera dess start, browser/PDF-beroenden, produktionsoperationernas gemensamma lås och begränsad insamling under avsedd användare. Den äldre verifierade Coop-imagen innehåller inte dessa nya ändringar; lokal verifiering ersätter inte serverprovet.
3. Bind till ett uttryckligt godkänt kommun-/butiksurval. En bredare datainventering får inte ändra användarnas befintliga områden, val eller max två inköpsställen. X:-tra och utvidgning till Malmö kräver egna omfattningsbeslut och relevant produkt-/näringsprövning.
4. Före eventuell aktivering: kontrollera dåvarande källålder, kampanjdag, medlems-/köpvillkor, validerad komplett bas och kodkompatibelt fortfarande giltigt rollbackunderlag. Denna rapport är ingen framtida färskhetsgaranti. Prisobservationerna ligger kvar på 22 september; återspelningen förnyar dem inte.
5. Återanvänd befintlig publicering, atomic activation, reload och health/ready samt separat testidentitet för planering/sparning/återläsning. Inga sådana ändringar har gjorts i denna etapp. Aktivera inte felande eller okända butiker som bieffekt av ett kommunval.
6. Uppdateringsfilen är ett granskningsbart urval, ingen installerad scheduler. Om driftkoppling senare godkänns ska befintlig driftloop använda denna policy och operationernas gemensamma lås, bevara giltigt LKG vid fel och hålla insamling skild från kampanjernas lokala tillämplighet.

Rollback för denna **oaktiverade** ändring är att fortsätta använda det tidigare separata paketet; inget aktivt underlag behöver återställas. Vid en framtida release får endast då fortfarande giltiga snapshots användas. Ingen återställning, rensning eller överskrivning av tidigare arbete har utförts.
