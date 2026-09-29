# Willys och Lidl: större kvalificeringshinder, 24 september 2026

**Genomförd förbättring, inte full täckning.** Prisgodkända unika erbjudanden ökar från **77 till 87 för Willys** och **23 till 26 för Lidl**, efter deduplicering mellan butiker och motsvarande erbjudanden i båda Willys-formaten. Willysökningen består av **två nya exakta livsmedelsköp och åtta verifierade kg-priser**. Kg-priserna ligger kvar i OWN/PriceUniverse men är spärrade från exakt paketplanering. Lidl får tre nya exakta livsmedelsköp. Ingen produktionsaktivering, schemaändring, bildanalys eller betald modell-API.

## Jämförbar bas och mätning

Första kontrollen verifierade föregående PACKAGE-hash och samtliga nio deklarerade kodhashar (`baseline.json`). Prisjämförelsen använder samma bevarade källor, köpdag **2026-09-24**, WillysPlus/Lidl Plus aktiverade och samma kommuninventering för Lund 1281/Malmö 1280. Återspelning föryngrar inte observationer. Tillkommande deklarationshämtning och den isolerade Coop-bashämtningen redovisas separat.

| Fryst underlag | Nämnare | Automatiska annonser före → efter | Automatiska varianter före → efter | Manuella varianter före → efter | Datumgiltiga OWN/PU före → efter | Exakta livsmedelsköp/audit före → efter | Näring i kompatibel gram-enhet, opt-in, före → efter |
|---|---:|---:|---:|---:|---:|---:|---:|
| Willys Hemma, fyra sidor | 34 annonser | 17 → 20 | 22 → 26 | 2 → 2 | 24 → 28 | 22 → 22 | 3 → 4 |
| Willys, tolv sidor | 112 annonser | 51 → 57 | 56 → 63 | 8 → 7 | 64 → 70 | 59 → 61 | 5 → 9 |
| Lidl, 29 sidor | 380 käll-ID | 23 → 26 bundna annonser | 23 → 26 | 0 → 0 | 23 → 26 | 23 → 26 | 2 → 2 |

Tabellens Willys-rader är per dokument och får inte summeras som unika kedjeprodukter. Kedjededupliceringen finns i `unique-new-offers.json`: Willys 77→87, Lidl 23→26; unika exakta livsmedelsköp över båda kedjorna **95→100**. Gyros har samma stabila källannons-/variant-ID före/efter: rättat namn och automatisk kvalificering räknas inte som ett nytt erbjudande.

**Korrigerad tidigare redovisning:** Hemma har två nonfoodidentiteter, tolvsidiga bladet fem. Rengöring, kosmetik och växter ingick delvis i förra rapportens benämning ”livsmedelsköp”. Samma korrigerade klassning används nu i båda armarna. Ingenting har tagits bort ur nämnaren eller prislager. Endast SIA:s korta avslutade kampanj ligger utanför datumgiltig import vid denna köpdag, som tidigare. Okänt bildinnehåll är fortfarande okänt, inte noll.

## Genomförd kod

- **Tillverkardeklarationer:** återanvändbar Garant-import läser verklig strukturerad GS1-identitet, deklarerad förpackning, ingredienser och explicit näringsbas ur sparad officiell HTML. Garant Majskorvar 90 g och Gyros Örter Citron 400 g är färdigkopplade. GTIN används där erbjudandet faktiskt har det; annars krävs entydigt fullständigt namn/variant, varumärke och förpackning. Deklarationens GTIN blir aldrig ett gissat GTIN på erbjudandet.
- **Faktabrygga från bevarad katalog:** hela aktiva officiella Coop-katalogen genomsöks, utan kampanjlista. Full identitet och förpackning måste ge ett enda leverantörs-GTIN; råsvar, hash, råpost, GTIN, varumärke, namn, mängd, enhet och näringsbas kontrolleras igen. Motstridiga deklarationer spärras. Priser och butiksvillkor flyttas aldrig. Pågenlimpan, Pizzamjöl och Kokosmjölk får belagda fakta. Kokosmjölkens deklaration per gram ger ingen påhittad ml-densitet.
- **Willys:** prisetiketternas skiftläge normaliseras, så ”PER KG” och ”Per kg” inte blir två olika köpformer. Historiskt jämförpris `/kg` feltolkas inte som ett restvillkor. Uttryckliga alternativ som Fusilli/Penne Rigate och Royal Gala/Granny Smith kan delas när samma mängd/pris verkligen gäller. Ungefärlig vikt bevaras som osäker metadata; kg-priset får ett uttryckligt kontrakt och saknar exakt paketkostnad. Webbläsarvisare/PDF-konflikter spärras fortfarande.
- **Lidl:** entydig fullständig obrandad produktidentitet kan bindas utan att ett saknat varumärke hittas på. Fristående mängdetikett binds bara om geometri ger exakt en ägare, oberoende av önskat pris/mängd. Uttryckligt styckpris går genom befintligt styckköpskontrakt. Ingen nationell giltighet ges till resten av det regionala flödet.
- **Receptskydd:** benförsedda kycklingdelars paketmassa får inte bli generella gram kycklingkött. Exakt köp av kycklingvingar behålls. Brödlimpans fullständiga produktform kan identifieras som bröd, med negativa fall för kött-/fisklimpa, bakmix och kaka. Näring kräver fortfarande separat belägg och beredningsgrund.

Huvudkod: `product_declarations.py`, `official_product_facts.py`, `offer_catalog_facts.py`, befintliga `flyer_text.py`, `document_qualification.py`, `offer_rows.py`, `catalog.py`, OWN, prisavtalsmodellerna, `nutrition_reference.py`, `personal_source_facts.py` och `product_semantics.py`. Se `PACKAGE.json` för exakta filer/hashar.

## Näring, recept och verkliga köp

Willys får **fyra ytterligare unika produkter med användbar deklaration per gram**: Majskorvar, Gyros, Pågenlimpan och Pizzamjöl. Deduplicerad gram-kompatibel näring inklusive tidigare tillåtna SLV-referenser ökar **6→10**. Kokosmjölk tillkommer som verifierad deklaration per gram, men köp i ml saknar belagd densitet. Lidl har fortsatt två produkter med kompatibel gram-näring; mango får en separat generisk referens per 100 g ätbar del, inte näring per frukt.

Garantkällor: [Majskorvar](https://www.garantskafferiet.se/vara-produkter/choklad--snacks/chips-popcorn--salta-pinnar/majskorvar/), [Gyros](https://www.garantskafferiet.se/vara-produkter/svenskt-kott--fagel/langkok--ribs/pork-gyros/). Den befintliga majskorvsobservationen 24 september 16:15 UTC bevaras; Gyros har verklig ny hämtning med separat tid/hash i `sources/`. Mango hämtades från [SLV:s livsmedel 574](https://dataportal.livsmedelsverket.se/livsmedel/api/v1/livsmedel/574), med länkade näringsvärden och egen hämtningstid. Referensen avser färsk mango; fryst/torkad/sockerlagskonserv godtas inte. Opt-in kvarstår. Styck→gram, benandel, densitet och tillagningsutbyte gissas inte.

Pågenlimpan har separat positivt receptprov genom befintlig kall serveringsgrund, 100 g uppmätt bröd, dess produktdeklaration, hela inköpsförpackningar och audit. **En ny unik receptkvalificerad produkt**, återanvänd i sju butikskopior. Tidigare rapporters nollfält för recept betydde att detta särskilda prov inte körts, inte att samtliga äldre produkter visats omöjliga. Gyros, Pizzamjöl och Majskorvar blir inte automatiskt godkända i valfritt varmt recept. Pris, deklaration, recept och menyval är separata steg.

Alla nya exakta erbjudanden har körts genom collector → radvalidering → OWN → PriceUniverse → matcher → köp → audit i respektive kommuns faktiska butiker:

| Nytt exakt köp | Förpackning/pris | Villkor 21–27 september | Officiellt belägg |
|---|---|---|---|
| Barilla Fusilli | 1 kg, 25,90 kr | Offentligt styckkampanjpris; inget verifierat ordinarie köppris | [Willys Rosengårds blad](https://reklamblad.willys.se/willys/2352), sid 10; full annonsbindning i resultatfil |
| Barilla Penne Rigate | 1 kg, 25,90 kr | Samma uttryckliga annonsalternativ och offentliga villkor | [Willys Rosengårds blad](https://reklamblad.willys.se/willys/2352) |
| Matriket Kycklingvingar | 1,1 kg, 49,90 kr | Offentligt; benens andel är inte verifierad ätbar mängd | [Nationell PDF](https://assets.leaflets.schwarz/leaflets/pdfs/01a084f8-a64e-7579-bb70-0808f9278dbb/Galler-21-9-27-9-i-alla-butiker-ERBJUDANDEN-VECKA-39-00.pdf) + exakt strukturerad produkt 11217807 |
| Madalenas med apelsin | 500 g, 27,90 kr | Offentligt; fullständig deklaration återstår | [Lidls officiella bröd/bakverk](https://www.lidl.se/h/broed-bakverk/h10096086), exakt produkt 11219129 + nationell PDF |
| Mango | 1 st, 11,90 kr | Offentligt styckpris; ingen antagen fruktvikt | [Nationell PDF](https://assets.leaflets.schwarz/leaflets/pdfs/01a084f8-a64e-7579-bb70-0808f9278dbb/Galler-21-9-27-9-i-alla-butiker-ERBJUDANDEN-VECKA-39-00.pdf) + exakt produkt 11029883 |

Inga köpgränser har angetts i dessa fem annonser; det betyder inte garanterat lagersaldo. Varianter, datum, medlemskap och källans uttryckliga begränsningar bevaras på samtliga andra rader. De åtta kg-priserna och deras WillysPlus-/hushållsvillkor finns fullständigt i `unique-new-offers.json`; de räknas aldrig som exakta korgköp. `STORES.md` visar alla 17 butiker och deras officiella länkar.

## Hela nämnaren och kvarstående hinder

`willys-all-variant-cases.json` redovisar **alla 46 tidigare variant-/intervall-/ungefärlig-vikt-fall** med annons, källtext, före/efter och konkret saknat fält. Sju annonser har fått uttryckligt kg-prisstöd och en annons har säker variantuppdelning. Av kvarvarande fall har 22 mängdintervall/alternativ utan säker variant–mängdkoppling eller stödd köpform, 15 saknar sluten variantidentitet och en saknar entydig prisplacering. Dessa är inte samtliga ”oläsbar text”: vissa är kontrakts-/tolkningsluckor, andra saknar nödvändiga uppgifter. Ingen ungefärlig vikt görs exakt. Övriga grupper, inklusive åtta PDF/visarkonflikter, finns i hela annonsregistret i `comparison.json`.

Lidl: **380 unika käll-ID kvar**, ursprungliga 157 igenkända textblock redovisas tillsammans med 181 efter utökad textidentifiering. De extra 24 textblocken döljer ingen nämnare. 26 automatiskt bundna produkter, 354 utanför köpimport. Det regionala flödet innehåller 105 aktuella livsmedel, 68 aktuella nonfood och två okända; 132 framtida livsmedel, 64 framtida nonfood och tre okända; fem livsmedel och en nonfood med okänt datum. Av de 26 fysiskt datumverifierade köpen ligger **24 i den regionalt aktuella livsmedelsgruppen och två i dess grupp med okänt datum**. Därför är kvarstående regionalt aktuella livsmedel **81**, inte 79. Den tidigare förenklade divisionen 23/105 blandade datumgrunder.

Bland de 181 textblocken: 100 saknar entydig fullständig produktidentitet, 34 saknar unik livsmedelsidentitet, sju stödd fast mängd, fyra har kvarvarande villkor/variant, tre oklar sidövergripande giltighet, tre obelagd pant-/vätskeroll, två tvetydig fristående mängd, en motstridigt pris och en period utanför vald publikation. Detta är textblocksstatistik, inte en extra produktnämnare. Blåbär har verklig PDF-/webbpriskonflikt; den billigare siffran väljs inte.

Lidl-pilotens kvarvarande nutrition har konkreta beroenden: madalenas saknar säkert bunden fullständig produktdeklaration; kycklingvingar saknar verifierad ätbar mängd/beredningsgrund; mango saknar uppmätt ätbar gramvikt för ett styckköp. Närliggande Pärsons-deklaration avsåg en annan 2,5-kilosvariant och importerades inte till 180-gramsvaran. Barillas direkta hämtning gav HTTP 403; Dabas-träffarna avsåg 5 kg eller fullkorn, inte de kvalificerade 1-kilosvarianterna. Ingen sådan deklaration kopierades.

Ingen tidigare ogranskad verklig utgåva har verifierats: de sparade 28/29-sidiga Lidl-versionerna och v40-bladet var redan kända. V40:s fem bindningar är återprov, inte oberoende generaliseringsbevis. Willys två verkliga format hör till samma kampanjvecka. Bildexklusiva uppgifter förblir utanför den här etappen.

## Drift och 15/20

- Isolerad ordinarie runner/CLI, verklig lokal server, publicering/reload, andra rebuild och ny serverprocess verifierade med samma produkter/observationer. Malmöprovet behåller City Gross som begränsad bas; det är inte den separata kompletta Malmö-releasen.
- Willys hämtningsfel injicerades; giltig LKG fortsatte genom rebuild/reload. Återhämtning använde bevarad källa, aldrig ny observationstid. Lidl: separat verkligt source-job-fel, retry med annan sparad verklig hämtning, omstart och `not_due`. Framtida testklocka spärrade utgångna erbjudanden.
- Den övergripande `not_due`-assertionen **passerade inte**: den bevarade City Gross-basen var över sin ordinarie 35-timmarsgräns. Runner gjorde därför korrekt en ny rebuild. Willys/Lidl visade inget eget förfallet arbete. Noll externa prisanrop även där. Ingen gräns eller observation ändrades för att göra provet grönt. `runtime-summary.json` har status PARTIAL.
- Ny faktisk Coop 730400-hämtning till privat baskopia: 825 nätanrop, 11 309 unika produkter, 748/748 kategorier, 822/822 produktsidor, noll hämtfel, full katalog godkänd av ordinarie collector/promotion. Rapportserialiseringen kastade först ett `CollectionResult.model_dump`-fel **efter** färdig promotion; resultatet verifierades ur sparad databas/logg och hjälpskriptet rättades, utan ny fullhämtning.
- Riktig oförändrad **15/20**, 40/30/20 g protein, max två butiker, medlemskap av: samma kompletta bas, ordinarie generator med 96 middags-/5 frukost-/5 mellanmålskandidater, ingen receptlista som ersätter sökningen. Före/efter **535,25 kr**, 15 måltider/20 portioner, två butiker, VERIFIED. Slutkoden passerade åter efter receptskyddet. Noll externa prisanrop under planering, privat container med nätverk av. Inget nytt erbjudande behöver väljas; inga besparingar framtvingas.
- Basen hade nio giltiga kontexter och cirka 43,47 timmars äldsta observation vid gemensam provklocka: **AGING, ingen STALE-kontext**, inte ny/färsk genom omdatering. Före/efter har exakt samma basdatabas/Primatcache och köp-/medlemskontext. Menyprovet jämför gamla/nya erbjudandesnapshotar med gemensam deklarationsimport; den fullständiga näringskodens isolerade före/efter mäts separat ovan. Ingen produktionsmanifestfil eller användarinställning aktiverades.

Nästa ordinarie kontroll enligt de sparade tillstånden: Willys cirka **25 september 20:41 svensk tid**, Lidl **26 september 03:35 svensk tid**, eller tidigare om kampanj-/felregler kräver det. City Gross-baskontrollen i Malmöprovet är redan förfallen. De verkliga källtiderna, retrylägena och hard-stop finns i `runtime-summary.json`; detta ändrar inga aktiva scheman.

## Tester och kvarstående releasekontroller

**453 unika riktade testfall passerar**, noll skip, efter senaste körning per fall. `tests-final.json/xml` pekar på delkörningarna; gamla mellanloggar med felaktiga räkneförväntningar och den hittade kycklingvingeluckan bevaras. Negativa fall omfattar fel prisruta, annan mängd/variant, medlemskap, datum, butik, gemensamma köpgränser, deklarations-GTIN/hash och gram/styck. Ruff och compileall passerar för paketets 19 kodfiler och samtliga Python-testmoduler i testurvalet.

Den historiska Lidl-fixtureluckan är fortfarande **öppen**: `test_reviewed_lidl_nutrition.py` saknar `reports/source-implementation-20260915/lidl_offer_adapter.py`. Nya kontroller ersätter inte hela dess historiska ost-/lårfilé- och beredningsflöde. Testet ingår inte i de 453.

Release kräver fortsatt färskt komplett underlag vid faktisk aktivering, komplett separat Malmö-publiceringsprov, oberoende ny utgåva och beslut om kvarvarande manuella dokument-/produktbindningar. Bevara ICA, Coop/X:-tra, City Gross, Willys online, Lidl, Primat och samtliga tidigare releaseunderlag. Ingen del kallas 100 procent godkänd bara för att den är redovisad.
