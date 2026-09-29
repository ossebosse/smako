# Äldre kedjeimporter → gemensamt PurchaseTerms, 2026-09-29

Avgränsad adapterleverans i isolerad kandidat. Ingen produktionsaktivering, schemaändring, användarinställning, recept-, närings- eller prismotorändring. Coop-v4:s käll-/versionsrättning och ICA/Hemköps kommunurval ingår fortsatt. Alternativpolicyn `lund-own-five-base-20260928-v1` är oförändrad.

## Fryst jämförelse

Utgångspunkt är det faktiska opublicerade slutpaketet och image `smako-ica-hemkop-municipality:20260928-v8` (`0790b31…`), inte ren Git HEAD. [baseline.json](baseline.json) fryser appfiler, tidigare bevis, policy och 15/20-input; `before/` innehåller föregående implementation. Nya imagen byggs ovanpå exakt denna tidigare image.

Samma sparade källsvar från 28 september, råhashar, observationstider, köpdag **2026-09-28**, projektionstid **20:00 UTC**, medlemsmatris offentlig/medlem och köpmodeller exakt/uppskattad används före/efter. Hela rånämnaren finns kvar. `import_replay.py` fryser både providerprojektion och checkout i separata processer. De tidiga `*-current-day-probe.json` är diagnostik och används inte som slutjämförelse.

**Noll nya återförsäljarhämtningar.** Retained replay separeras från verklig publicering och HTTP-prov på den aktuella klockan 29 september. Historiska priser påstås inte vara nyinsamlade. Importdatum och nya radgodkännanden föryngrar inte källobservationerna.

## Var termerna tappades och rättningen

| Led | Före | Nu |
|---|---|---|
| ICA `parser.py:526–595` | Ingen bunden köpform för vikt/öppen variant; normaliserad annons kunde inte tillämpas | Källbunden fast/styck, hela explicit angivna cirka-paket, uttrycklig lösvikt och öppna kampanjval. Inga nya GTIN eller restpriser. Parser v8. |
| Coop `structured_offers.py:235–330` | Bland annat flervariants-flerköp krävde ordinarie pris; vikt krävde exakt paket | Identifierade barn får egna kompletta köp; blandning kräver uttryckligt stöd. Explicit cirka-vikt och lösvikt separeras. Parser v5 bevarar v4:s schemaspärr. |
| Hemköp `physical_offers.py:93–169` | Bara singleton och enkel styckkampanj; beskrivning, klubbpris, maxantal och flerköp spärrades före gemensam modell | Explicit `productCodes`, `qualifyingCount`, `realMixAndMatch`, klubbpris, samstämmig cap och källbeskrivning binds till kontraktet. Flera produkter utan variantmängder blir öppet villkorat val. Parser v2. |
| X:-tra `xtra_pdf.py:399–483` | Befintliga kvalificerade PDF-rader saknade termer; variantannons stoppades som ingrediens | Samma text-/layout-/prisbevis, kompletta paketgrupper och uttryckligt villkorat kampanjval. Eget dokument, parser och felstatus; ingen bildmodell. Parser v2. |
| Radgodkännande `offer_rows.py`, `source_purchase_terms.py` | Äldre fastpaket-/singletonkrav före gemensamt kontrakt | Termer måste stämma mellan produkt och SourceOffer, råreferens, mängd och prisbas. Saknad eller motstridig bindning spärras. |
| OWN `api/catalog.py:491` → `providers/own.py:1027` | ICA/Hemköps kg-bas/kontrakts-ID kunde tappas; erbjudande utan ordinarie pris kunde felklassas | Bevarar bunden prisbas/ID och villkorad prissignal. Ingen kampanj blir ordinarie restpris. |
| Kommunproviders → PriceUniverse | Äldre exakt-paketspärr även efter godkänd import | Accepterar giltigt befintligt köpstöd, med oförändrad kommun-, fysisk butiks-, kanal-, datum- och källbindning. |

Ingen default-approximation läggs på baskataloger. En kg-annons utan paketuppgift bevisar inte fri lösvikt: Royal Gala/Purjolök och andra oklara former hålls kvar som `weight_purchase_form_unproven`. Den tidigare mellanversionens generösare antagande används inte i slutkandidaten. Råa annonser och avslag finns kvar.

## Full nämnare och mätbar förbättring

Godkända rader betyder käll-/köpkontrakt, inte automatiskt recept- eller näringsgodkännande. Antalen nedan inkluderar butikskopior. Hemköp omfattar tre Lund- och fyra Malmöbutiker i lokal replay; endast Lund ingår i publicerad femkällorskandidat.

| Kedja | Butiker | Rånämnare | Godkända före → efter | PU före → efter | Exakt / uppskattad / villkorad i PU efter | Unika kampanjer före → efter | Unika erbjudandevarianter före → efter |
|---|---:|---:|---:|---:|---|---:|---:|
| ica | 12 | 1035 | 277 → 824 | 275 → 824 | 277 / 41 / 506 | 152 → 484 | 152 → 484 |
| coop | 9 | 2179 | 254 → 1614 | 254 → 1614 | 1595 / 19 / 0 | 44 → 101 | 107 → 545 |
| hemkop | 7 | 485 | 42 → 333 | 42 → 333 | 152 / 0 / 181 | 6 → 48 | 6 → 48 |
| xtra | 1 | 50 | 7 → 11 | 6 → 9 | 6 / 0 / 3 | 7 → 11 | 7 → 11 |

Unikhet räknas med källans kampanj-ID, variant-ID där sådant finns, pris, antal, period, medlemskap och cap. Coops butiksspecifika prefix slås inte ihop som produktbevis; jämförelsestatistiken använder källans `eagId` och variant-ID. ICA:s öppna annons räknas som ett kampanjval, inte som fabricerade produktvarianter. Priser kopieras aldrig mellan butiker.

Alla efterprovets PU-rader klarar pris- och mängdreconciliation i minst ett av de fyra prövade lägena. Full ingrediens-/semantikaudit är en ytterligare spärr:

| Kedja | Fungerande pris/mängd före → efter | Full audit före → efter |
|---|---:|---:|
| ica | 151 → 824 | 140 → 808 |
| coop | 216 → 1614 | 194 → 1401 |
| hemkop | 42 → 333 | 35 → 326 |
| xtra | 5 → 9 | 5 → 8 |

Köpprovet begär en dokumenterad paketmängd, 200 g för uppskattat paket/viktköp och ett öppet kampanjval. Den befintliga motorn får köpa hela grupper när ordinarie restpris saknas. Företalets misslyckade enpaketsköp betyder inte att annonsen saknade alla möjliga köp. Öppna kampanjval kan passera audit med **UNVERIFIED** och särskild varning; det är inte verifierat slutkvitto. Låga semantikträffar (t.ex. Pågenlimpan som generisk ingrediens) redovisas separat från korrekt pris/mängd.

[comparison.json](comparison.json) redovisar samtliga fyra medlems-/köplägen, rånämnare, avvisningsorsaker och butiker. [before-import/checkout.json](before-import/checkout.json) och [after-import-v5/checkout.json](after-import-v5/checkout.json) innehåller alla beräkningar/audits, även misslyckade.

## Butiksvis

| Kedja | Butik | Rånämnare | Godkända före → efter | PU före → efter |
|---|---|---:|---:|---:|
| ica | ICA Kvantum Brunnshög (1086002) | 73 | 21 → 66 | 21 → 66 |
| ica | ICA Kvantum Malmborgs Clemenstorget (1004409) | 125 | 33 → 111 | 33 → 111 |
| ica | ICA Kvantum Malmborgs Tuna (1003391) | 122 | 33 → 101 | 33 → 101 |
| ica | ICA Kvantum Södra Sandby (1003452) | 97 | 27 → 90 | 27 → 90 |
| ica | ICA Nära Genarp (1004016) | 38 | 16 → 35 | 16 → 35 |
| ica | ICA Nära Jägaren, Lund (1004475) | 45 | 16 → 41 | 16 → 41 |
| ica | ICA Nära Satelliten (1003508) | 43 | 17 → 39 | 17 → 39 |
| ica | ICA Nära Söderlivs, Lund (1004339) | 55 | 20 → 49 | 20 → 49 |
| ica | ICA Nära Veberöd (1004268) | 44 | 17 → 40 | 17 → 40 |
| ica | ICA Supermarket Fäladstorget (1004223) | 89 | 24 → 70 | 24 → 70 |
| ica | ICA Supermarket Linero Torg (1004598) | 69 | 24 → 54 | 24 → 54 |
| ica | Maxi ICA Stormarknad Gunnesbo, Lund (1088004) | 235 | 29 → 128 | 27 → 128 |
| coop | Coop Veberöd (1158) | 397 | 39 → 271 | 39 → 271 |
| coop | Stora Coop Lund (2696) | 363 | 68 → 274 | 68 → 274 |
| coop | Coop Vildgåsen Lund (3656) | 98 | 11 → 71 | 11 → 71 |
| coop | Coop Värpinge Lund (3659) | 315 | 32 → 257 | 32 → 257 |
| coop | Coop Mårtenstorget (3813) | 397 | 39 → 271 | 39 → 271 |
| coop | Coop Klostergården (3820) | 315 | 32 → 257 | 32 → 257 |
| coop | Coop Trollebergsvägen (3837) | 98 | 11 → 71 | 11 → 71 |
| coop | Coop Flöjtvägen (3839) | 98 | 11 → 71 | 11 → 71 |
| coop | Coop Genarp (3841) | 98 | 11 → 71 | 11 → 71 |
| hemkop | Hemköp Dalby (4517) | 73 | 6 → 48 | 6 → 48 |
| hemkop | Hemköp Lund Brunnshög (4224) | 66 | 6 → 46 | 6 → 46 |
| hemkop | Hemköp Lund Karhögstorg (4123) | 69 | 6 → 47 | 6 → 47 |
| hemkop | Hemköp Malmö Elinegård (4212) | 70 | 6 → 48 | 6 → 48 |
| hemkop | Hemköp Malmö Kronprinsen (4114) | 69 | 6 → 48 | 6 → 48 |
| hemkop | Hemköp Malmö Triangeln (4247) | 70 | 6 → 48 | 6 → 48 |
| hemkop | Hemköp Malmö Värnhem (4199) | 68 | 6 → 48 | 6 → 48 |
| xtra | X:-Tra Skansvägen (3658) | 50 | 7 → 11 | 6 → 9 |

ICA:s Västkustchips `2005577158` i Brunnshög gäller till 28 september: den ingår i den frysta köpdagens 824 ICA-rader men försvinner korrekt ur aktuell servering 29 september (823 ICA-rader). X:-tra har två annonser som börjar 1 oktober (kycklingdelar och äggnudlar). De ingår i godkänd OWN/rånämnare men inte i köpdagens eller dagens aktiva servering. Inga rader döljs i redovisningen.

Aktuellt serverat Lund: **42 085 → 44 119 produkter**. De fem obligatoriska onlinebaserna är fortsatt 41 512. Fysiska ICA 275 → 823, Coop 254 → 1 614, Hemköp 18 → 141 och X:-tra 6 → 9. De övriga 20 redan godkända Lidl/Willys-raderna är oförändrade. Alla 33 tidigare kontexter finns kvar; inga nya obligatoriska beroenden eller användarbutiker skapas.

## Hemköps sex och kvarvarande spärrar

De sex äldre kvalificerade annonserna per butik var Pågenlimpan 900 g/22 kr, teriyakisås 250 ml/29,95 kr, chiliolja 210 g/39,95 kr, gochujang 170 g/15 kr, panko 200 g/15 kr och pärlsocker 500 g/15,95 kr. Deras singleton-/paketfält passade den gamla förkontrollen. Före/efter är samma 485 råannonser; 42 godkända butikskopior blir 333, varav 152 exakta och 181 öppna villkorade.

Exempel på verklig kopplingsrättning: kampanj `2500324385`, produkt `101428349_ST`, svensk nötfärs 800 g/119 kr, klubbpris och max 2 köp. Beskrivningen “fetthalt max 12%” är produktuppgift; den betyder inte inköpsgräns. Samstämmiga `redeemLimit`, `promotionRedeemLimit` och etiketten ger den verkliga gränsen. Pizza `2500317459`, sex explicit listade produktkoder, `realMixAndMatch=true`, 2 för 79 kr får öppet variantval; bildens huvudprodukt ger inte rätt att anta paketvikt för alla varianter.

Hemköp kvar: 59 annonser saknar explicit variantmedlemskap, 79 har ytterligare köp-/pant-/datumvillkor som kräver granskning, 14 saknar stöd för paketformen (sju Bakpotatis med cirka-vikt/styckpris och sju Helgbukett utan verifierad paketenhet). Det befintliga viktkontraktet kräver belagt kg-pris; styckpriset omvandlas inte till ett påhittat kg-pris. Varken huvudbildens kod eller jämförpris får fylla luckorna. Kg-annons utan identifierad variantmängd blir inte ny lösvikt bara för att beloppet går att läsa.

Coop kvar: pantbelopp, extra köpkrav, prissteg, `isPil`, åldersvillkor och oklara viktformer. Gemensam kampanj och “Välj mellan” bevisar inte fri blandning. Verifierade varianter kan köpas var för sig i kompletta grupper. Regressionen för explicit “Välj och blanda” är tydligt syntetisk; inget sådant bevis fabriceras för dagens annonser.

ICA kvar: oklara paket/viktformer, saknad entydig variant, pant och ej tillämpbara villkor. X:-tra kvar: paket-/layout-/oberoende priskontroll, pant, medlemskapsplacering och kampanjbindning. Dessa kräver konkret kompletterande källuppgift eller nytt köpstöd; ingen ny generell parserutredning görs här.

## Faktiska API-köp i publicerad kandidat

| Fall | Fullt köp | Märkning |
|---|---|---|
| ICA Kvantum Brunnshög: färsk laxsida ASC | 1 helt cirka-paket 1 200 g × 139 kr/kg = **ca 166,80 kr** för behov 200 g | VERIFIED_WITH_ESTIMATES; exakt läge DATA_BLOCKED |
| Stora Coop Lund: röd paprika, explicit lösvikt | 350 g × 39 kr/kg = **ca 13,65 kr** | VERIFIED_WITH_ESTIMATES; uppvägning kvarstår |
| Coop Genarp: fläskfilé | 1 helt cirka-paket 590 g × 79,90 kr/kg = **ca 47,14 kr** för behov 200 g | VERIFIED_WITH_ESTIMATES, medlemsvillkor kvar |
| Coop Genarp: Pizza X-Tra Allt Vesuvio | **3 × 350 g = 99 kr**, behov ett paket | VERIFIED; två paket överskott, inget påhittat restpris |
| Hemköp Dalby: svensk nötfärs | **2 × 800 g = 238 kr**, behov 1 200 g | VERIFIED; 400 g överskott. 2 400 g spärras av cap. |
| Hemköp Dalby: Pizza, öppet variantval | **2 kampanjmärkta val = 79 kr** | UNVERIFIED; variant/näring/allergen kvar öppna |
| X:-tra Skansvägen: Marmelad, öppet variantval | **1 kampanjmärkt val = 20 kr** | UNVERIFIED; ingen falsk gram- eller näringsmängd |

Källor: [ICA:s officiella Brunnshög-erbjudanden](https://www.ica.se/erbjudanden/ica-kvantum-brunnshog-1086002/), [Stora Coop Lund](https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-lund/) och [Coop Genarp](https://www.coop.se/butiker-erbjudanden/coop/coop-genarp/) med respektive bundet strukturerat svar; [Hemköps butikserbjudanden](https://www.hemkop.se/erbjudanden/4517) med `/search/campaigns/offline?q=4517`; [X:-tras butik](https://x-tra.se/butiker/skansvaegen) med sitt separat bundna PDF-dokument. Exakt vald butik, source snapshot, råreferens, datum, cap och medlemskap finns i [purchases-results.json](results/purchases-results.json) och [representative-products.json](results/representative-products.json).

Sju positiva HTTP 201, två negativa 422 av rätt orsak, exakt sparning/återläsning före och efter faktisk processomstart. Lagerposter, köpledger och sparad profil är oförändrade. Generering skapar planreservationer/revisioner enligt befintlig modell och bokför inte ett köp. Sök-API rapporterar `live_provider_calls=0`; containrarna saknar extern nätanslutning. `purchase_usage`, kg-bas, uppskattningsvarning, medlemskap och villkorat val följer befintlig UI-kod. UI-/runtime-regressionen verifierar samma renderingskontrakt.

Näringsvägen: det befintliga provet **Koriander med vitlök** körs med nykvalificerad Hemköp-koriander och Coop Online-vitlök, två inköpsställen. Fullt inköp 15 kr; 20 g koriander + 5 g vitlök används. Den oförändrade råa, uppmätta beredningen och generiska SLV-mappningen ger ca 6,9 kcal och 0,52 g protein per portion (2 portioner), separat från inköpta paket/rester. Detta är ett berednings-/ingrediensprov, inte ett påstående om komplett middag. [nutrition-result.json](results/nutrition-result.json). Ingen allergensäkerhet påstås.

## Drift, regression och avgränsning

Samtliga fyra oförändrade 15/20-profiler ger HTTP 201, 445,29 kr och samma meny i Coop Online Syd + Willys Lund; 15 verifierade köprader, 10 VERIFIED och 5 ESTIMATED näringsresultat. Andra rebuilden med explicit frivilligt Hemköp-fel behåller 44 119 produkter och hash `cdb81a5a2055986fc67e64ae18a767489bdd4fe94008b044351670be813faa2e`. Sju prissökningar och ett sparat cirka-köp är identiska efter faktisk omstart efter andra publiceringen. Fem baser är byte-identiska (41 512 produkter); alla 12 tidigare planrevisioner och 3 privata tillstånd är oförändrade. Full slutstatus finns i [ACCEPTANCE.json](ACCEPTANCE.json). Slutimagen är `smako-legacy-purchase-terms:20260929-v5`, digest `sha256:eee77ff22794b02c80d20457a33d7fc4aacf11fd4a3f277860e93fb12f7c0eba`. Isolerat dataområde: `/var/tmp/smako-legacy-purchase-terms-20260929`; föregående paket/databaser finns kvar för rollback. Ingen aktivering av originalpolicyn eller produktion.

Ordinarie CLI/providerimport → rebuild → atomisk publicering → serving-reload används under befintligt operationslås. Externa insamlingshooks är uttryckligen avgränsade bort i replayprovet; inga förfallna observationer föryngras. Andra rebuilden injicerar ett frivilligt Hemköp-insamlingsfel och prövar att giltigt LKG och samtliga fem baser består. Serving-status får vara AGING/degraded enligt befintliga 36/48-timmarsgränser; den kallas inte FRESH.

Regression: 457 berörda fall verifierade över slutkoden (455 i bred körning; två gamla singleton-assertioner korrigerade och hela deras femfallssvit omkörd), plus 31 UI/runtime-fall. Fokuserade vikt-, blandnings-, cap-, källkonflikt-, fullkatalog-, Willys/Lidl-, PurchaseTerms-, normaliserings- och sparningsprov ingår. Ruff och compileall körs. Inga opåverkade dyra liveinsamlingar upprepas.

Separat öppet: Malmös baspolicy/fullständiga publicering, ICA:s okända kommunträffar, Bunkeflostrands källväg, nya komplexa kampanjvillkor, Lidl/Willys-täckning och historisk Lidl-fixture. Den tidigare lyckade femmiddagsmilstolpen bevaras. Inget i denna leverans markerar dessa sidouppgifter lösta.
