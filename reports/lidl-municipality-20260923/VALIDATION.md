# Lidl-verifiering

- `tests-final-runnable.xml`: 232 tester, 0 fel, 0 överhoppade, 459,920 s. Lidl-parser/nationell äldre bevismetod/kommuninventering, radkontrakt, City Gross, Coop/X:-tra, Willys, gemensam behovsrunner, medlemskap, hushållsgränser och produktfakta ingår.
- `lidl-final-tests.xml`: 16 fokuserade prov, 0 fel, 43,006 s. Överlappar regressionerna men omfattar också kortare dagsvillkor/intradagskarantän och kampanjutgång utan påhittat ordinarie pris.
- `wiring-lidl-final.xml`: 8 driftkopplingsprov efter den sista skärpningen av byggstad/kommunkod, 0 fel. Ingen kommun får tyst matas in i en annan byggstad.
- `wiring-tests.xml`: 22 gemensamma Lidl/City Gross/Coop-kopplingsprov, 0 fel.
- Ruff för ändrad kod och nya tester: PASS (`ruff-final.log`). Python 3.12 compileall: PASS.

Dessa antal är överlappande körningar och ska inte summeras till ett antal unika tester. Testklockor och ändrade testfält är uttryckliga injektioner, inte aktuella källpriser.

## Äldre test som inte kunde köras

Det första breda testkommandot stoppades vid insamlingen av `backend/tests/test_reviewed_lidl_nutrition.py`: den oförändrade äldre testfilen hänvisar till den saknade filen `reports/source-implementation-20260915/lidl_offer_adapter.py`. Logg och XML finns kvar som `tests-final.log` och `tests-final.xml`. Detta räknas inte som ett godkänt eller överhoppat test. Den körbara sviten ovan kördes därefter separat. Den nya exakta Pågen-deklarationen och dess bindnings-/näringsprövning har egna körda tester. Ingen äldre deklaration, test eller fixture ersattes med påhittade data.

## Verkligt nät och replay

Den officiella inventeringen gjorde en nationell sitemap-hämtning och 212 butiksdetaljhämtningar. SCB-geometrin hämtades separat för två kommuner. Utredningsanrop för aktuell publikation, offentligt produktflöde, visningsklientens publika API-kontrakt och Dabas-deklaration är sparade separat i rapportmappen.

`package-live-verification/verification.json` avser en separat begränsad faktisk insamling från den hashkontrollerade extraherade slutkoden: **10 externa anrop**, varav **7 produktflödessidor**, samt publikationslistning, publikationsmetadata och PDF. Ett nationellt underlag delas mellan belagt omfattade butiker. Det är inte tio gånger tio butiksanrop. Samma kod gav 6 OWN-poster i Lund och 24 i Malmö. Inga gamla kampanjposter användes som dagens priser.

Den sista paketerade nätobservationen är ett separat verifieringsunderlag. Driftproven behåller de tidigare verkliga observationerna från cirka 15:28Z den 23 september; de föryngras inte till tiden för paketprovet. De aktuella priserna, förpackningarna och villkoren överensstämmer.

Collector-måttet `request_count=8` per återspelad butik räknar sparade dokument (sitemap och sju produktflödessidor). Det är inte nya nätanrop. Driftens nätmätning och källrapportens `external_price_requests` skiljer dessa tal åt. Fullkällans låga täckningshälsa ligger kvar; endast de tre självständigt godkända raderna publiceras genom befintligt partiellt kontrakt.

Ordinarie runner-/publiceringsprov tillåter endast loopback. Verklig app, childprocess, lås, databasvalidering, byggare, artefaktvalidering och HTTP-reload körs; källhämtning är märkt replay eller felinjektion. Se RUNTIME.md och respektive maskinkvittenser.

Ingen bildanalys, betald modell-API, produktionsaktivering, Windows-konfiguration eller schemaläggningsändring utfördes.
