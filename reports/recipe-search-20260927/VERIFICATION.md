# Smako: receptsökning och källbunden mängd — 27 september 2026

Inaktiv implementation, ingen produktionsaktivering. Historisk prisreplay för 24 september 2026; nya leverantörsuppgifter hämtade 27 september redovisas separat. Recept, portioner, 40/30/20-mål och högst två inköpsställen är oförändrade.

## Faktiskt resultat

**33 av 84 godkänns före och efter: 32 tidigare godkännanden består, ett nytt tillkommer och ett tidigare felaktigt godkännande återkallas. Målet om ett högre netto och alla 33 bevarade är inte uppfyllt.** Alla originalrecept, källimporter och tidigare releasefiler finns kvar.

| Mått | Före | Efter |
|---|---:|---:|
| Beredningsprövningsbara oförändrade v1-recept | 84 | 84 |
| Recept med kvalificerade numeriska ingrediensvärden | 84 | 84 |
| Näringsmål + hel varukorg + audit | 33 | 33 |
| Kvarvarande första stopp: sökbudget | 29 | 0 |
| Kvarvarande första stopp: näringsbrist | 22 prövade kombinationer | 51 styrkta övre gränser inom aktuella kandidatdomäner |
| Tidsumma för individuella receptprov, utan initial återställning/faktaladdning | 16.977 s | 11.046 s |

84 numeriska ingrediensunderlag betyder inte 84 uppnådda varukorgar. Efterkörningen har 33 faktiskt godkända varukorgar och 51 konservativa näringsgränser. Gränserna är inga köpbevis. Samtliga 84 recept/ID, mängder, mål, föregående beräknade proteinexempel, prövade kombinationer och eftergränser finns i [RECIPE-RESULTS.md](RECIPE-RESULTS.md); fulla kandidat-ID, butik, snapshot och näringsursprung finns i [recipe-first-stops.json](recipe-first-stops.json).

**Nytt:** Tacos med tofu och gul lök, v1, 40,2125 g protein/portion mot 40 g. Den befintliga 13-procentiga Skånemejerier-varianten hade 2,9 g protein/100 g i det frysta underlaget men saknade belagd massa för 200 ml-förpackningen. Dabas anger både 200 g och 200 ml för exakt GTIN 07310867003841. Föregränsen med den tidigare gramkvalificerade 32-procentiga varianten var 39,9 g. Samma recept får nu använda den korrekt identifierade 13-procentiga varianten. Ingen generell densitet, receptändring, prisändring eller ny kampanj har införts.

**Återkallat:** Stekt ris med lax och vitkål räknade tidigare 15 g torkad finhackad vitlök som 15 g rå ätbar vitlök. Det gav 40,345 g protein/portion. Santa Maria beskriver produkten som torkad; ingen rå/torkad mängdomräkning finns. Med korrekt rå form ligger övre gränsen på 39,58 g, 0,42 g under målet. Det tidigare godkännandet kan inte bevaras utan ett annat kvalificerat underlag eller en separat receptändring. Inget sådant har hittats eller fabricerats.

## Oförändrad fri 15/20-profil

| Medlemskap | Köpplanering | Kostnad före → efter | Tid före → efter | Köpstatus | Exakta / uppskattade / villkorade rader |
|---|---|---:|---:|---|---|
| Original | exact | 484.73 → 484.73 kr | 146.965 → 102.989 s | VERIFIED | 16 / 0 / 0 |
| Original | estimated | 484.73 → 484.73 kr | 166.500 → 117.835 s | VERIFIED | 16 / 0 / 0 |
| Willys Plus + Lidl Plus, separat kopia | exact | 484.73 → 484.73 kr | 145.039 → 104.718 s | VERIFIED | 16 / 0 / 0 |
| Willys Plus + Lidl Plus, separat kopia | estimated | 484.73 → 484.73 kr | 170.830 → 119.052 s | VERIFIED | 16 / 0 / 0 |

Alla fyra väljer Coop Online Syd (`online_fulfillment`) och Willys Lund (`online_store`). Näring redovisas separat: 10 måltider VERIFIED och 5 ESTIMATED. Uppskattat köpplaneringsläge gör inte automatiskt köpraderna uppskattade. Två av 84-recepten ingår i den fria planen; tacoreceptet behöver inte väljas för att dess eget godkända köp ska vara giltigt. Ingen ekonomisk bortvalsorsak har härletts enbart från frånvaro i menyn.

Tiderna kommer från nya processer med kalla planner-cacher, samma frysta 37 031 produkter, samma kompletta bas, originalreceptpool, köpdag, inställningar och medlemskontext inom respektive jämförelse. Initial artifact-återställning ligger utanför den redovisade planeringstiden. Detta är en körning per kombination, inte ett statistiskt prestandaintervall. Tidigare giltiga körresultat återanvänds som förebevis.

## Vad som ändrats

- Gemensamma konservativa näringsgränser använder redan kvalificerade produktfakta och faktisk använd ingrediensmängd per portion. De relaxerar butikskombinationer och kan endast avslå en omöjlig näringsdomän, aldrig godkänna en varukorg. Okända fakta, oförenlig enhet, lagerhistorik eller behov av färdiglagad vikt faller tillbaka till befintlig beräkning.
- Sammanfattningar per näringsklass beräknas före sökloopen. Kandidaternas fakta återanvänds mellan extrema och klassindelning. Näringsmässigt omöjliga klasser går inte vidare till dyr varukorgsberäkning. Slutlig näringskontroll, köpberäkning och audit kvarstår.
- Förpackningsberäkningens befintliga cache kan uttryckligen återanvändas inom en enda planeringsbegäran. Den rensas mellan begäranden och begränsas mellan varukorgsförsök. Produktfingeravtryck, behov/mängd/enhet och aktuellt pris-/köpkontrakt ingår; näringscache använder fortsatt receptinnehåll och versionsbundna fakta. Medlemskap, planeringsläge och källurval är begäransbundna. Olika cachekonfigurationer delar inte session.
- Dabasimport stöder uttryckliga nettomängder i flera enheter för samma bas-GTIN. Logistiska enheter, motstridiga mängder, fel marknad/identitet/förpackning spärras. Leverantörens konsumentflagga kan vara Nej, men då krävs fortfarande en redan existerande detaljhandelsidentitet med exakt GTIN, varumärke och förpackning. Dessa deklarationer kan inte bindas genom enbart namn. Pris, allergener och konfliktspärrar ändras inte.
- Rå potatis och rå vitlök använder granskad formkontroll även när en produkt har en näringstabell. Kryddor, sammansatta livsmedel och tillsatt olja får inte ärva råvarans gramgrund. Redan sparade SLV-referenser 4457 och 371 återanvänds med ursprunglig version/observation och befintligt opt-in. Vitlökskryddad salladsost har fått korrekt primär produktidentitet.

Kodfilerna listas i [changed-application-files.json](changed-application-files.json). Inga ändringar i generator, receptdefinitioner, produktionsschema, kommuninventering eller användarprofil.

## Kodens effekt och nya källuppgifter hålls isär

Första sök-/cacheändringen med helt frysta fakta behöll 33/84 och 484,73 kr, med tider 135,826 / 158,959 / 133,830 / 159,616 s. Underlag i `code-only/`. Slutlig kod inklusive korrekt råvaruform men med ursprungligt deklarationsregister ger **32/84** (`profile/final-code-only-all-84.json`). Slutlig kod plus det importerade mängdunderlaget ger **33/84**. Den nya tacokvalificeringen beror på belagd mängdkoppling, inte på höjd sökbudget. Inga receptinnehåll har ändrats.

## Profilering och referenssökning

cProfile kördes först på oförändrad förekod: cirka 16 000 varukorgsoptimeringar och 215 000 anrop till näringskontroll. Profileringen påverkar tiden; dess 285,735 s används inte som före-/eftertidsjämförelse. `profile/before-cprofile.json` innehåller mätningen.

Jämförbar public/exact-körning: varukorgsoptimeringens inkluderande tid 47,40 → 22,94 s; faktiskt omräknad näring 32 192 → 1 673 anrop, 7,77 → 0,35 s; kandidatgenerering 13,54 → 10,10 s; audit 1,81 → 1,77 s. Mätområdena överlappar och får inte summeras. Hela planeringen förbättras 28–30 % över de fyra profilerna.

Referenssökningen omfattar uttryckligen alla 29 tidigare budgetfall, 4 096 som lokalt tak och 30 sekunders separat tidsgräns per recept. 28 stoppas av näringsgränsen utan att 4 096 kombinationer påstås vara provade. Tacoreceptets samtliga 832 näringsklasser prövas: 828 avslås tidigt, fyra klarar numerisk näring, bästa godkända varukorg är fortfarande 117,05 kr. Ordinarie 256-prov hittade samma köp. Den gamla 20-receptsreferensen finns oförändrad i `baseline/search-reference.json` och räknas inte som bevis för alla 29.

## Ordinarie HTTP, köp och återläsning

Tacoreceptet skickades genom `/api/plans` med oförändrad v1-definition som ett normalt valt recept. Ingen produktlåsning, inga extraköp och inga handpatchade kandidater. Två portioner, 40 g protein/portion, högst två butiker och befintligt närings-opt-in. Exakt och uppskattat läge gav HTTP 201. Varukorgen kostar 117,05 kr, samtliga sex köprader är VERIFIED, näringen ESTIMATED och audit passerar.

Köpen omfattar en hel 200 ml/200 g crème-fraicheförpackning (125 g används), 540 g tofu (200 g används), 370 g tortillas (200 g används), 500 ml rapsolja (10 ml används), 1 kg gul lök (150 g används) och 400 g vitkål (250 g används). Förpackningsrester räknas inte som använd receptnäring. Butiker: Coop Online Syd och Willys Lund, respektive ursprunglig nätkanal.

Båda planer sparades och lästes tillbaka identiskt, även efter omstart. Vid rollback till förekoden gick sparade planer att läsa identiskt; omräkning av det då ännu okvalificerade tacoreceptet svarade säkert 422 och bevarade sparad plan. Underlag: `profile/http-rescued-after-integration.json`. HTTP-tider 12,116 s respektive 4,840 s är sekventiella kall/varm-fall och används inte för en rättvis lägesjämförelse.

## Källor, tester och kvarvarande beroenden

Ny verklig hämtning: Dabas HTML för GTIN 07310867003841 och 07310867523868 samt PDF-text för den förstnämnda. HTML och aktuell PDF överensstämmer om 13 % fett, näring och mängd. Den laktosfria varianten saknar massuppgift och får inte ärva den andra variantens 200 g. Två deklarationer importerades genom befintligt importverktyg; endast den belagda masskopplingen räddar ett nytt recept här. `sources/`, `declaration-import.json` och `imported-declarations.json` innehåller underlaget.

Officiella länkar: [Skånemejerier 13 % / Dabas](https://www.dabas.com/productsheet/07310867003841), [aktuell PDF](https://www.dabas.com/productsheet/07310867003841/pdf), [laktosfri variant](https://www.dabas.com/productsheet/07310867523868), [Santa Maria finhackad vitlök](https://www.santamariaworld.com/se/produkter/vitlok-finhackad/). Direkt råhämtning av Santa Maria stoppades av certifikatvalidering; den officiella webbsidans text kontrollerades genom webbläsverktyget. Ingen spärr kringgicks. [Scans fläskfilé](https://www.scan.se/vara-produkter/412921/flaskfile/) kontrollerades också: deklarerade 21 g protein förbättrar inte den befintliga övre gränsen. Ingen fördelaktigare näring har gissats.

700 regressioner passerade. Därefter 32 riktade slutprov för importens extra konfliktspärr, källbindning och näringsgränser; båda importerade deklarationerna reproduceras oförändrat. Ruff och compileall passerade. Slutspärren ändrar inte den sparade import som användes av de native planeringskörningarna. Befintliga tester omfattar berörda kedjor, kommunstöd, köpformer, protein-/enhets-/allergispärrar, cacheisolering och priser.

Kvarvarande 51 recept har proteinövre gräns under respektive mål inom kvalificerat, tillämpligt underlag. För godkännande krävs ytterligare belagda kompatibla produktalternativ eller separata receptändringar; större sökbudget ensam kan inte lösa dessa domäner. Vi har inte visat att recepten är globalt omöjliga eller dyrare. GoGreens motstridiga deklaration förblir spärrad. Alla 720 föregående releasebevis är byteidentiska.

Färsk komplett produktionsbas, fullständigt Malmö-publiceringsprov och historisk Lidl-fixture kvarstår som separata kontroller. Inga nya livsmedelspriser hämtades; historiska observationer har inte föryngrats. Ingen produktionsaktivering, aktiv schemaläggning, användarprofiländring, bildanalys eller betald modell-API.

Se [RELEASE.md](RELEASE.md) för separat aktiverings- och återställningsunderlag.
