# Releasekandidat: Willys/Lidl pris- och faktakvalificering

Kandidaten finns i befintlig arbetskopia. **Inte produktionsaktiverad.** Tidigare kedjors implementation och releaseunderlag kvarstår; inga Windows-uppgifter, aktiva scheman eller användarval har ändrats.

## Innehåll

Återanvändbar import av officiella Garant-deklarationer, entydig faktabindning från bevarade katalogsvar, utökad Willys variant-/kg-kvalificering och Lidl dokument-/styckköpsbindning. Prisgodkännande kräver inte näringsgodkännande. Kg-priser utan exakt paketmängd bevaras men tillåts inte i exakt paketplanering. Kycklingvingar tillåts inte som generella gram kycklingkött.

`PACKAGE.json` anger slutkod, data, tester och kontrollunderlag med SHA-256. Paketet är ett ändringsmanifest ovanpå tidigare kandidater, inte en fristående ersättning för hela den smutsiga arbetskopian. Ingen gammal dokumentgranskning ärvs av nya utgåvor.

## Verifierat

- Samma frysta källor, köpdag och medlemskontext: Willys 77→87 unika godkända erbjudanden, varav ökningen två exakta livsmedelsköp och åtta kg-priser. Lidl 23→26, tre exakta livsmedelsköp. Butikskopior och Gyros namnbyte är inte nettotillskott.
- Willys gram-kompatibla näringsunderlag 6→10 unika produkter. Lidl 2→2; mango har därutöver generisk SLV-näring per 100 g ätbar del, utan påhittad styckvikt. Pågenlimpan har ett nytt separat godkänt receptprov.
- 453 unika riktade tester passerar enligt senaste körning per testfall, noll skip. Ruff och compileall passerar för manifestets kod och de nya testmodulerna.
- Oförändrad ordinarie 15/20-profil med samma kompletta giltiga bas: VERIFIED, 535,25 kr i båda armarna, två butiker. Slutkodens backend-hashar stämmer med körmiljön. Basen var AGING, inte STALE, vid gemensam testklocka. Inga externa prisanrop under planeringen.
- Kommunurval Lund/Malmö, import, publicering/reload, andra rebuild, omstart, datumspärr samt fel/LKG/återhämtning verifierade i isolering. Nya prisobservationer har inte skapats av replay.

## Öppna kontroller och beroenden

1. Hela målet är inte uppnått. 38 av de 46 granskade Willys variant-/intervallfallen återstår; Lidl har 81 kvarvarande regionalt aktuella livsmedelskandidater utan kvalificerad nationell fysisk produktbindning. Hela ursprungliga nämnaren och övriga orsaksgrupper finns i README och JSON-registren.
2. Fullständig Malmö-publicering med aktuell komplett bas är fortfarande separat. Det begränsade Malmö-driftprovet ersätter inte den.
3. Hela driftprovets `not_due`-assertion passerade inte: bevarad City Gross-bas hade nått ordinarie refreshgräns. Willys/Lidl var inte förfallna; ingen färskhetsgräns ändrades. `runtime-summary.json` är uttryckligen PARTIAL.
4. En tidigare ogranskad verklig kampanjutgåva saknas för oberoende generaliseringsprov. Kända dokument/revisioner och syntetiska negativa fall ersätter inte detta.
5. Historiska `backend/tests/test_reviewed_lidl_nutrition.py` saknar sin adapterfixture och är fortsatt olöst, utanför de 453 testerna. Dess hela historiska berednings-/ost-/lårfilékedja har inte ersatts av nya tester.
6. Fullständiga deklarationer, belagd ätbar vikt, densitet och variant–mängdbindning saknas för angivna produkter. Prisposter kvarstår där priset är verifierat. Saknade värden fylls inte med noll eller gissningar.

Aktivering kräver nytt aktuellt komplett basunderlag och ordinarie releasekontroller. Rapportens frysta provklocka och godkända bas är ingen garanti för färskhet vid en senare aktivering.
