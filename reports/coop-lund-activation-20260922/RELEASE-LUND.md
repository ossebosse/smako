# Samlat aktiveringsunderlag – Lund, 22 september 2026

**Beslut vid kontrollen cirka 11:44 Europe/Stockholm: priskandidaten är tekniskt verifierad; återkommande betaaktivering är inte redo.** Det finns en konkret kvarstående koppling i driftkedjan, beskriven nedan. Inga priser, användarprofiler, Windows-uppgifter, produktionsscheman eller serverkonfigurationer har ändrats. Ingen ny butiksinventering gjordes.

## Verifierad leverans

- Slutimage: `smako-coop-candidate:lund-activation-20260922`, **`sha256:00fd55cc75d824dfcfb1aa2c6abbee882c0af95a574ad190c2a6932db0064622`**. Samtliga paketerade app-/connector-/scriptmoduler är hashkontrollerade mot arbetskopian; CLI:n ingår nu också. Pris-, variant-, närings-, medlems-, datum-, hushållsgräns- och karantänmoduler är oförändrade sedan deras tidigare verifiering, förutom tidigare redovisad striktare kommunbindning.
- Serverpaketet kompletterades med samma versionsbundna text-/HTML-beroenden som lokal verifiering: BeautifulSoup 4.15.0, soupsieve 2.9.1, PyMuPDF 1.28.2. Playwright 1.58.0/Chromium behålls. Bygg utan nätverk från hashregistrerade wheels; inga installationer i aktiva containrar. Python 3.12, UID/GID 10001, skrivskyddad rot, 2 CPU/5 GiB. Bildmodell och betald API-väg avstängda.
- **Nio Coop/Stora Coop-butiker, 493 kvalificerade butik–variantposter, 1 937 i karantän.** Ny faktisk begränsad serverinsamling 11:28:29–11:29:09, 44,492 sekunder. Alla nio har tom lista över gemensamma kritiska blockerare. Sex tidigare utgångna Stora-erbjudanden återkommer inte. Namn/ID/observationer finns i `server-results/coop-live/coverage.json`.
- Kommunparametern och inventeringens butikskoppling används av urval/provider. Ursprunglig Lundsinventering 1281 återanvändes. Coop Online är fortsatt separat. Användarnas adress-/butiksval och max två inköpsställen ändrades inte.
- **X:-tra Skansvägen är separat:** ny faktisk PDF-textinsamling i paketet 11:34:53; 8 sidor, 57 identifierade textannonser, 10 godkända i OWN, 9 aktuella i eget isolerat PU, 47 karantän. Tre ingrediensköp klarar checkout/audit; honung kvarstår med matchningsspärr. PDF-länken upptäcktes från butikens officiella sida. Texttäckningen är partiell. X:-tra ingår inte i den fulla Coop-kandidaten nedan och kan helt utelämnas utan att stoppa de nio Coop-butikerna.

## Publicering och riktig planering

Godkända Coop-poster byggdes med den **befintliga produktionsbyggaren**, komplett läsbar baskälldatabas och fryst Primat-cache. Basen togs som en ny konsekvent SQLite-backup under operationslåset; dess bytes och Primat-underlag är identiska med tidigare jämförelse. Det är inte en lokal sökprojektion och observationstiderna har inte ändrats. Den tidigare basartefakten återanvändes därför som jämförelse- och rollbackunderlag.

Coop-kandidat: `price-universe:b893fb0448ca2e70d6a7e5a980dbf740fb3b8727ed8fb1b6b9d8b63eccdd2888`. Samtliga 493 poster nådde byggaren och kunde följas i det laddade underlaget. Både bas och kandidat passerade `PreparedUniverseArtifactStore.activate` med samma validator/färskhetskontroller som publiceringskedjan, **endast mot privat manifest**. Felaktig kandidat, saknad snapshotkoppling och för gammal rollback avvisades. Misslyckad aktivering behöll privat LKG; giltig rollback och återstart/återläsning passerade. Det bevisar att artefakten kan publiceras med befintligt kontrakt, inte att den har aktiverats i betan.

Slutimagen körde den riktiga oförändrade profilen: **15 platser, 20 portioner, 40/30/20, medlemskap av, max två inköpsställen**. Resultat **536,27 kr**, HTTP **201**, planering **43,949 s**, totalt prov **91,272 s**. Sparad plan motsvarar återläst plan, health/ready 200/200, 332 varukorgsaudits. Inga fysiska Coop-rader valdes i slutmenyn. Den tidigare hashbundna jämförelsen var också 536,27 kr utan tillskott; detta är ett nytt kandidatprov, inte en ny parvis körning eller ett nytt besparingspåstående. Tidigare produkt-/näringsrättningarnas kvalificerade alternativ och kvarstående pastaspärrar bevaras.

Publiceringsprovet tog 141,644 s. Efter dess körning ändrades endast uppdateringspolicyn och paketberoenden; publicering, byggare, pris-/näringskod och artefakter är hashoförändrade. Den berörda policyändringen verifierades på slutimagen och med nya regressioner. **78 unika tester passerade** (76 i första körningen, därefter 12 berörda varav två nya); Ruff och compileall PASS. Tidigare oförändrad ICA-/Coop-pris- och näringsevidens återanvänds med hashkontroll.

## Färskhet och uppdatering

Vid beslutskontrollen var äldsta baskällan **32,44 timmar** gammal, observerad **21 september 03:17:55**. Föreslagen basuppdatering vid 35 timmar är **22 september 14:17:55**; varning **15:17:55**, absolut stopp och rollbackgräns **23 september 03:17:55**. Beslut, rebuild och export förlänger inga tider. Aktivering efter stopp kräver nytt giltigt bas- och rollbackunderlag.

En faktisk schemalucka rättades i kommunpolicyn: Coop/X:-tra omfattas ännu inte av ICA:s undantag för datumstyrda kampanjer. Nästa kontroll begränsas därför till **35 timmar efter observation**, även om kampanjbytet ligger senare. För dagens Coop-källor föreslås **23 september cirka 22:28–22:29**, för X:-tra **22:34**; nästa korta kampanjstart är **24 september 00:00**. Detta är **beräknade förfallotider, inte installerade jobb**. Alla butikstider finns i [UPDATES.md](UPDATES.md).

Det befintliga produktionsschemat lästes oförändrat: nästa dagliga refresh **23 september 03:17** och källretry **06:17**. Daglig start ligger bara cirka 55 sekunder före den nuvarande basens 48 h-stopp och är ingen säker marginal för en insamling. Behovsstyrningen från den väntande ICA-releasen är inte aktiverad. Ett senare aktiveringsbeslut måste hantera detta utan att implicit aktivera ICA-paketet eller ändra Windows-uppgiften.

Policyprovet bevarar senaste lyckade observation vid fel, ger första återförsök efter 15 minuter och begränsad fortsatt backoff, och bevarar tidsplan vid omstart. Inga externa prisanrop sker vid enbart policykontroll. Kampanjens slut och 48 h-stopp gäller även efter ett misslyckat anrop. Karantänposter blir inte tillåtna genom LKG. Den **beständiga källpekaren och driftkopplingen för Coop** återstår enligt nästa avsnitt; metadata om senaste lyckade hämtning är inte ensam en färdig LKG-integration.

## Verklig återstående blockerare

**Ordinarie återkommande rebuild tar ännu inte med Coop-kandidaten.** `grocery_data.__main__._build_production_price_universe` vidarebefordrar ICA:s valfria källargument men inte `coop_offer_database` / `coop_municipality_inventory`. `deploy/scripts/run_daily_refresh.py` läser inte den kommunala Coop-kandidatens beständiga källpekare och uppdateringsurval. Ett separat offlineprov av argumentöverföringen bekräftar de tomma Coop-argumenten (`publication-wiring-gap.json`). Den vanliga browserentrypointen producerar fortfarande en kandidat, inte full produktion.

En engångsaktivering av den verifierade artefakten är tekniskt möjlig, men följande ordinarie rebuild kan tappa tillskottet. Därför är **automatisk återkommande release inte godkänd enbart för att publiceringsprovet passerade**.

Avgränsat återstående kodsteg är en uttryckligt avstängd koppling i befintlig driftväg: verifierad kommuninventering och senaste godkända butikskällor → beständig källa/versionspekare → byggargument → validering/publicering/reload. Den ska bevara giltigt underlag vid frivilligt Coop-fel, synligt redovisa bortfall, respektera 35/36/48 timmar samt klara restart och följande rebuild. Inget nytt scheduler- eller prissystem behövs. Ett operatörsflaggbyte ensamt kan inte ersätta den kopplingen.

**X:-tras ytterligare avgränsning:** den befintliga fullständiga Coop-providerimporten tar avsiktligt endast Coop/Stora Coop. Textparsern fungerar nu på servern, men X:-tras isolerade PDF-databas är inte ansluten till den fulla publiceringsbyggaren. Det är ett separat valfritt tillägg; låt det vara avstängt vid en första Coop-release.

**Malmö hålls utanför beslutet.** Tre hämtfel, två källbundna parserfel och Nydalas saknade PDF-länk samt geografiskt osäker Kirseberg redovisas i föregående kommunrapport. Inget av dessa gav gemensamt kritiskt fel i de nio faktiskt hämtade Lundsflödena. De blockerar därför inte Lunds avgränsade kandidat.

## Nästa steg och operatörsgräns

1. Slutför och isolerat verifiera driftkopplingen ovan, inklusive en andra ordinarie rebuild som behåller Coop och ett misslyckat anrop som behåller fortfarande giltigt underlag. X:-tra avstängt. Detta är det kvarstående implementationssteget före ett samlat aktiveringsbeslut.
2. Ta därefter ett separat uttryckligt beslut om Lunds nio Coop/Stora Coop-butiker, aktuell image och giltigt underlag. Kontrollera källålder, verkliga kampanjdatum och kodkompatibel rollback precis då. Bekräfta hur basuppdateringen ska ske med marginal; den väntande ICA-/Windows-releasen får inte aktiveras som bieffekt.
3. Först efter det beslutet gör operatören deploy av godkänt paket och publicering genom befintliga operationslås, kandidatvalidator, atomiskt manifestbyte och processreload. Kontrollera faktiskt laddat PU-ID och Coop-rader, health/ready och separat testidentitet med sparning/återläsning. Återställ bara en fortfarande giltig kodkompatibel bas vid fel. Ändra inga användarval.

**Nu faktiskt aktiverat: ingenting.** Betan kör fortfarande `billigaste-veckomenyn:0.1.0-smako-price-recovery-lund-20260914a` och PU `price-universe:8cfb4f26664c18415b606d55f3075b4ee0d36b5f8f6d8f175e6fe26b2e1127ed`. Health/ready åter 200/200 efter provet. Produktionsmanifestets hash var oförändrad. Primat och den blockerade direkta ICA-baspriskatalogens paus är oförändrade.

## Reproducerbar paketering och prov

Denna etapps serverdata finns under `/var/tmp/smako-coop-lund-activation-20260922`, inte produktionsrötterna. Första SQLite-backupen fyllde testutrymmet på `/tmp` (tmpfs), inte datadisken. Endast denna körnings data flyttades intakta till diskbaserad `/var/tmp`; den ofullständiga kopian ligger separat i `data/failed-base-disk-full`. Äldre arbete rensades inte. Ny fullständig backup lyckades; cirka 319 GiB var ledigt på datadisken vid kontrollen. Det är ingen kvarstående diskblockerare för det avgränsade testpaketet.

Byggstegen finns i `remote.py stage`, `prepare_wheels.py` och `remote.py build`; versionsbundna wheelhashar i `wheel-manifest.json`, image-/kodhashar i `package-result.json` och `code-closure.json`. De använder endast separat kandidatimage. Genomförda prov: `freeze`, `collect-package`, `build-coop`, `xtra-smoke`, `policy`, `publication`, `coop-acceptance`, `retrieve`. Basartefakten återanvändes först efter byteidentisk full bas/cache. Välj nya privata körkataloger vid omprov; skriv inte över tidigare resultat och använd inte material efter dess färskhetsstopp.
