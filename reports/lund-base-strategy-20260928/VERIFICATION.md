# Lund 1281: separat basstrategi, 28 september 2026

**Ingen produktionsaktivering. Originalpolicyn är fortsatt blockerad.** Alternativets namngivna testpolicy är `lund-own-five-base-20260928-v1`. Denna rapport ändrar inte gamla releasekrav.

## Primat

Ett verkligt resolve-anrop visar Clemenstorget 1004409 med tier=offers_only. Identiteten stämmer. Coverage är normaliserad lokal tolkning av tier när källfältet coverage saknas. Selected kommer från källans urval och är inte skälet till revalideringsfelet. Bevarade augustiexporter visar tidigare tier=full, men inget fullständigt historiskt HTTP-råsvar har återfunnits. Den tidigare full_catalog-klassningen stöddes av källans deklaration och begränsade produktprov, inte oberoende sortimentsinventering. Ingen belagd mappningsdefekt motiverar omklassning. Se PRIMAT-CONTRACT.md.

Originalets sex obligatoriska kontexter bevaras. Alternativet utesluter båda Primat-baserna, behåller Coop Online Syd, Hemköp Brunnshög och Willys Lund/Nova och gör även Hemköp Karhögstorg obligatorisk. Clemenstorgets 34 egna kvalificerade erbjudanden är offers_only, inte full katalog.

## Faktiska HTTP-resultat med komplett fryst underlag

| Profil | HTTP | Kostnad kr | Tid s | Köpstatus | Exakta / uppskattade / villkorade rader | Butiker och kanaler |
|---|---:|---:|---:|---|---|---|
| original-exact | 201 | 445.29 | 159.07 | VERIFIED | 15 / 0 / 0 | Coop Online Syd (online_fulfillment); Willys Lund (online_store) |
| original-estimated | 201 | 445.29 | 180.31 | VERIFIED | 15 / 0 / 0 | Coop Online Syd (online_fulfillment); Willys Lund (online_store) |
| plus-exact | 201 | 445.29 | 154.05 | VERIFIED | 15 / 0 / 0 | Coop Online Syd (online_fulfillment); Willys Lund (online_store) |
| plus-estimated | 201 | 445.29 | 182.97 | VERIFIED | 15 / 0 / 0 | Coop Online Syd (online_fulfillment); Willys Lund (online_store) |

Fyra anrop via ordinarie /api/plans, oförändrat originalunderlag för 15 måltider/20 portioner, 40/30/20 g protein och högst två inköpsställen. Endast köpplaneringsläge och den uttryckliga Willys Plus/Lidl Plus-testkopians medlemskap varierar. Inga produktlås, extraköp, handpatchade kandidater eller förändrade sparade användarval. Alla ursprungligen tillåtna kanaler är tillåtna. Historiska 484,73 kr är inte ett förväntat aktuellt utfall.

Körtiderna är HTTP-väggtid i samma privata instans (2 CPU, 5 GiB). Första anropet börjar utan uppvärmd faktacache, senare anrop kan återanvända cache; tiderna är inga fristående prestandabenchmarks. Ingen annan byggning körs samtidigt.

Valda produkt-ID:n, hela paketkostnader, använda och köpta mängder, butik/kanal, nutrition, audit och sparningsjämförelser finns i profile-summary.json och oförkortade results/http-results.json. Näringsstatus hålls separat från köpstatus. Alla fyra slutkorgar har 15 exakta rader och noll uppskattade/villkorade; detta är inte ett prov på ett valt uppskattat köp. Plus-flaggorna är aktiverade i medlemskopian, men ingen slutlig köprad använder medlemspris. API-fältet membership_programs_used återger här programvalen och ska inte tolkas som bevis på utnyttjad rabatt. Avsaknad av val innebär inte bevis för att ett erbjudande är dyrare.

### original-exact

Näringsstatus: {'ESTIMATED': 5, 'VERIFIED': 10}. Audit: {'passed': True, 'verification_status': 'VERIFIED', 'totals_reconciled': True, 'ingredients_checked': 15, 'unknown_quantities': 0}. Sparning/GET oförändrat: True.

### original-estimated

Näringsstatus: {'ESTIMATED': 5, 'VERIFIED': 10}. Audit: {'passed': True, 'verification_status': 'VERIFIED', 'totals_reconciled': True, 'ingredients_checked': 15, 'unknown_quantities': 0}. Sparning/GET oförändrat: True.

### plus-exact

Näringsstatus: {'ESTIMATED': 5, 'VERIFIED': 10}. Audit: {'passed': True, 'verification_status': 'VERIFIED', 'totals_reconciled': True, 'ingredients_checked': 15, 'unknown_quantities': 0}. Sparning/GET oförändrat: True.

### plus-estimated

Näringsstatus: {'ESTIMATED': 5, 'VERIFIED': 10}. Audit: {'passed': True, 'verification_status': 'VERIFIED', 'totals_reconciled': True, 'ingredients_checked': 15, 'unknown_quantities': 0}. Sparning/GET oförändrat: True.

## Underlag och korrigerat isoleringsfel

De fem obligatoriska baskatalogerna hämtades på riktigt 27 september 15:13–16:14 UTC och var fortfarande FRESH under slutprovet. Ingen ny fullhämtning eller föryngring görs av en färsk bas. Aktuella frivilliga flöden hämtades på riktigt 28 september cirka 07:02–07:04 UTC. App, collector och refresh använder samma oförändrade bild och källkod.

Första testkopian innehöll databasen men saknade katalogernas råfiler. Därför fick de första fyra HTTP-anropen DATA_BLOCKED (21,91 / 21,50 / 21,28 / 22,37 s). Detta var ett fel i isoleringspaketet, inte ett bevis mot OWN-basen. initialize_job.py kopierar nu råträdet; restore_raw_job.py kompletterade 2 232 faktiskt refererade filer med hashkontroll, utan nätanrop och utan ändrade observationer. HTTP-provet har en obligatorisk råfilskontroll före start. De felaktigt ofullständiga proven är sparade separat i results/http-results-incomplete-raw.json och räknas inte som den alternativa strategins slutresultat. Ingen gemensam pris-, närings- eller identitetskontroll ändrades.

## Täckning

41 704 importerade baskatalograder, varav 41 512 tillgängliga; 243 giltiga fysiska erbjudandeposter. Serving-instansen innehåller 41 755 poster i 19 kontexter. Butikskopior räknas inte som nya unika erbjudanden. Onlinebasen och de partiella fysiska erbjudandena är olika kanaler. Full tabell och konkreta bortfall: STORE-RESULTS.md.

Coops nya fysiska strukturerade hämtning avvisades på butik-/källbeviskonflikt. Tolv fortfarande giltiga äldre godkända poster från Stora Coop Lund och X:-tra är kvar. Lidl har tre kvalificerade produkt-ID:n i vardera två butiker, 399 karantänrader per butik. Willys Hemma Stortorget ger 14 produkt-/grupprader, 20 karantänrader ur 34 annonskandidater. City Gross har verifierat noll Lund-butiker. Detta är partiell erbjudandetäckning, inte fulla fysiska sortiment.

## Driftprov och negativa kontroller

- Första ordinarie insamling/byggning/validering/atomisk publicering/reload: exit 0; faktisk serving-manifestkontroll. 569,96 s totalt i runner.
- Andra ordinarie behovsstyrda rebuilden: exit 0, 443,76 s inklusive reload; uttryckligt injicerat Willys-jobbfel hindrar inte de fem baserna. Container utan extern nätåtkomst. Senast godkända giltiga erbjudanden bevaras.
- Efter denna byggning hade Coops vanliga retry förfallit. Ett separat, uttryckligen injicerat transportfel kördes genom ordinarie optional-jobb och befintlig backoff; godkända referenser ändrades inte. Det är inte en lyckad ny Coop-hämtning.
- Ny process läser beständig policy och kommunval även när kommunkoder tas bort ur miljön. Vanlig demand-tick ger not_due. Upprepad not_due med DNS spärrad ger exit 0 utan prisanrop.
- Tom separat publiceringsrot utan LKG: kopia av aktuell kandidat med uttryckligen injicerade 49 h gamla obligatoriska Coop-observationer avvisas med required usable contexts: context:coop:23eaae11c9661e68. Huvudmanifestet förblir oförändrat. Ett inledande felkandidatprov stoppades redan av produkthashskyddet; slutprovet använder en sammanhängande omhashad testkandidat så att just obligatorisk färskhet prövas. Detta är publisher-/admissionsprov, inte simulerad lyckad nätinsamling.
- Willys fel/återhämtning testas dessutom i separat källkopia: injicerat hämtningsfel, därefter replay av verkliga sparade bytes. Observationstider och huvudpublicering oförändrade.
- Explicit framtidsklocka: 49 h ger noll användbara baspriser; kampanjer med senare faktiskt slutdatum får fortsätta. Efter sista kända kampanjs slut återstår noll kandidater. Inga utgångna kampanjköp godkänns i något prov.
- Sparning/GET och faktisk serveromstart prövas för alla skapade slutplaner; resultaten finns separat per plan.

## Paket, regressioner och beslut

Oförändrad bild: sha256:32e838155b0ef2b4b4eb9944cb7d1b31324b37e7ea56eb6d840fc70fc9e1ff87. Källträd: 3e9cf6f3656bb20298560d44bbca079690834946ee3a773ddbe8126bd71b9899. Samtliga 589 källfilshashar och 238 tidigare rapportbevis är bevarade. Policyhash och denna etapps bevis finns i PACKAGE.json. 37 riktade Primat-/driftregressioner godkända; tidigare hashstabila tester återanvänds utan att dubbelräknas som nya tester.

Alternativet har fungerande fulla HTTP-planer i samtliga fyra profiler. Det är fortfarande ett separat policyalternativ, inte en godkänd release enligt originalkraven. Se ACTIVATION.md för beslut som återstår och färskhetskontroller vid beslutstillfället.

ICA-/Hemköpsluckan i kommuninventeringen, äldre köptermer, fullständigt Malmö-publiceringsprov och historisk Lidl-fixture förblir separata öppna uppgifter. Detta prov löser dem inte. Ingen produktion, Windows-uppgift, aktiv schemaläggning, sparad användarprofil, bildmodell eller betald modell-API har ändrats/använts.
