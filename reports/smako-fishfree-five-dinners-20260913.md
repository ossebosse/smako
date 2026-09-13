# Fem middagar utan fiskingredienser — acceptans 13 september 2026

**Fryst funktionell acceptans A–E: PASS.** Ordinarie formulär väljer fem middagar × fyra portioner, Balanserad, högst två inköpsställen, minst 20 g protein och högst 800 kcal per portion. Spårbara näringsuppskattningar är uttryckligen påslagna. Ingen förvald meny eller dolda produktlås i A. Detta är ett matvalstest; allergifrihet påstås inte.

## Versioner och jämförbarhet

Före ändring verifierades faktisk symlänk, `/health`, image och källhashar: `personal-v2-cost-fish-20260912`, app `e5a3787`, image `sha256:4226869fc258d0ad96c1c4b1f79ce71b3d89749fbf89c01e2d815f7bf888e769`. Den tidigare kostnadsanalysen har inte upprepats.

Fryst prisversion för före/efter: `price-universe:9ab6c58a4934c0a253e037c724d58fdcc8c84b484d26a87d2027be087e17b929`, byggd 2026-09-11 07:15:56.668911 UTC. Samma indata/profil och samma underliggande råsvar; de uttryckligt granskade kompletteringarna är faktadeltat. Efter: `retained-catalog-facts-v3:5da97c85b2217dc8992ffdcbdc48c253e722b0c13ab90b094281f3bdaa9873c5`. Näringsversion: `slv-component-input-v3:62a78f3b718fb932c524c1692eb1e290909d808ec0ca660bf99a01c18f2e6a93`. Den frysta testklockan gäller endast acceptansharnessen, aldrig produktionskoden.

[Komplett UI/API-acceptans](fishfree-20260913/acceptance.json) · [Formulär och resultat](fishfree-20260913/form-menu.png) · [Före: produktvis diagnostik](fishfree-20260913/before-qualification.json) · [Efter: produktvis diagnostik](fishfree-20260913/qualification.json). Före-diagnostiken använder även de fyra nya kandidaternas behov för att isolera dataluckorna; dessa recept fanns inte i den gamla generatorn. Ursprungligt DATA_BLOCKED är dokumenterat i [föregående rapport](smako-affordable-five-dinners-20260912.md).

## Kravets betydelse och hela kontrollkedjan

Befintliga `TasteProfile.exclusions` är hårda ingrediensuteslutningar, inte enbart ogillade huvudråvaror. `allergies` är redan ett separat fält. Nya formulärval säger nu uttryckligen **Uteslut ingredienser – hårt matval** respektive **Allergier – även deklarerade spår**. Inga sparade hårda uteslutningar eller allergier migreras/omklassificeras.

1. Formuläret i `personal.html`/`personal.js` skickar `personal.profile.exclusions=["fisk"]`, `allergies=[]`; uppskattningar är av tills användaren väljer dem.
2. `PersonalPlanner` slår ihop profil, måltidsprofil och äldre `avoid_ingredients` som hårda uteslutningar. Kandidatfiltret behåller lax/tonfisk och fiskfamiljen.
3. `check_product` kontrollerar faktisk ingrediensdeklaration före fullständighetskravet; känd fisk blir CONFLICT även om övriga fält saknas. Sammansatta produkter måste ha granskad ingrediensdeklaration.
4. Slutkorgens valda produkter och identitetsbundna skafferibidrag kontrolleras igen, med `checks.ingredient_exclusions` och källor i API/UI.
5. Byte och redigering går genom samma hårda regler. Ett redigeringsförsök med lax avslås utan att ändra sparad revision.

Okänd ingrediensinformation förblir okänd. Namn och generisk näringsreferens bevisar aldrig frånvaro. `ingredients_complete`, `ingredients`, `ingredient_evidence_kind`, `field_sources.ingredients`, `retailer_product_id` och konflikterna `ingredients`/`identity_variant` avgör ingrediensgranskningen. Saknad näring, ekostatus eller tillagad vikt avgör inte fiskinnehåll. Separata aktiva närings-/ekokrav kontrolleras fortsatt.

För matval separeras deklarerade ingredienser från försiktighetsfrasen ”kan innehålla spår av”. Allergiläget behåller hela deklarationen och kräver dessutom verifierade allergen-/spårfält. Granskningen fyller aldrig `allergens_checked` med påhittad frånvaro.

## Konkreta blockerare och åtgärder

| Kategori/recept | Faktiskt hinder före eller vid granskning | Åtgärd och status |
|---|---|---|
| Fisk faktiskt identifierad | Fiskrätterna har lax/torsk. Sparade sammansatta produkter innehåller fisksåspulver, ansjovis/sardeller eller ansjovisextrakt trots andra produktnamn. | Fiskrätterna utesluts. Fem verkliga sammansatta deklarationer ger FISH_IDENTIFIED, inklusive BBQ-sås, Worcestershire, Tapenade Chili, Tom Kha-krydda och Caesardressing; se separat källbevis nedan. |
| Alla tre tidigare fiskfria recept | `ingredients_complete=False` för relevanta produkter; tomma Willys-deklarationer i det lagrade katalogsvaret. | 25 exakta produktgranskningar. Produktidentitet, mängd/enhet och källor framgår i registret och den kompletta produktdiagnostiken. |
| Kokt kyckling med ris och morötter | Eldorado `101337918_ST` innehåller kyckling 80 % + saltlake; Garant `101222270_ST` 87 % + saltlake. Den gamla rå/kokt-mappningen är inte kompatibel. Coop `2307116100005` anger 100 % kyckling men 0,5 g kolhydrat mot referensens nollgrund. Strimlade produkter passar inte den gamla hela filéberedningen. | Detta recept förblir blockerat med nya fakta. Ingen utspädning eller nollkvot gissas. Ugnskyckling har egen faktisk beredning och använder en kompatibel produktdeklaration. |
| Kycklingsoppa med äggnudlar och vitkål | Kyckling, nudlar och vitkål saknade komplett granskning; Spicefield `101498815_ST` anger även vatten och passar inte den snäva befintliga torrnudelmappningen. | Ren strimlad Garant `101258401_ST`, Coop-nudlar `7311312008794` och vitkål `101286120_ST` fungerar med befintlig soppberedning. Receptet kvalificeras och används vid UI-byte. |
| Couscoussallad med tofu och tomat | Tofu `101358420_ST`, couscous och tomat saknade granskning. Garant `101547036_ST` visar fullkorn i detaljunderlaget trots kort ingredienstext och får därför `nutrition_reference_form_fullgrain`. | Naturell Eldorado-tofu, vanlig Coop-couscous `7340011321767` och den redan lagrade tomatvarianten `101880323_ST` kvalificeras. Ingen specialprodukt har tillförts för att fylla en plats. |
| Nya recept saknades helt | Ingen färdig beredningskedja för linspasta, linsgryta, tofupanna eller ugnskyckling. | Fyra konkreta generatorrecept tillagda med proportioner, instruktioner, mängdgrund och produkt-/referensmappningar. Samtliga kvalificeras. |
| Saknad/fel näringsgrund | Gogreen `101289938_ST` är kokta linser med vatten/salt och avrunnen grund; Eldorado `101234820_ST` är parboiledris. | De används inte som torra röda linser eller vanligt vitt ris. Kompatibla Coop-linser `7331217016854` och ris `7340011340522` används. |
| Näringsgräns | Varje rätt måste faktiskt nå 20 g/800 kcal. Övriga kandidater kan avslås separat vid beredning eller produktval. | Alla fem sluträtter passerar; ingen tröskel har sänkts. Normal morotsmängd ingår i linsrätterna och uppfyller det befintliga grönsakskravet. |
| Variation/butikskombination | Tre gamla familjer räckte inte för fem varierade middagar. En enda butik ger inte full korg med kvalificerade produkter. | Sex fiskfria recept kvalificeras, fem väljs. Pasta, ris, nudlar och couscous samt sås, gryta, panna, ugn och sallad ger godkänd befintlig variation; två inköpsställen. |
| Sökning hittar ingen kombination | Ett begränsat misslyckat sökresultat bevisar inte global omöjlighet. | A och B hittar faktiskt godkända femkombinationer. Ingen global optimalitets-/omöjlighetsutsaga görs. |

[Fem sparade sammansatta produkter med faktiska fiskingredienser, fält, källor och hash](fishfree-20260913/compound-fish.json). `qualification.json` listar varje matchad produkt per receptingrediens med identitet, mängd/enhet, `ingredients`, `sources`, `conflicts`, ingrediensbeslut och näringsresultat; ingen allmän DATA_BLOCKED-rad ersätter dessa detaljer.

## Verkliga data- och receptkompletteringar

[Produktregister med källpayload, fält och SHA-256](../backend/app/data/ingredients/reviewed-20260913.json): 13 tidigare lagrade Coop-deklarationer granskade och 12 distinkta Willys-produkter hämtade via befintlig godkänd detaljklient. Sparade katalogråsvar granskades först offline. Inga nya Coop-/ICA-anrop, inga nya prisrader, ingen full kataloginsamling, ingen ändring av Willys-task/relay, ingen lättad parsergrind och ingen åtkomstblockering. Antalet externa detaljprodukter är 12 av högst 30, helt före konsumentplaneringen.

Exakt artikel-ID, produktnamn/variant, förpackning och tillgängligt varumärke måste stämma. Coop-deklarationen måste fortfarande vara identisk med den granskade; Willys-fakta måste ha kompatibel observationstid inom sju dagar. Avvikande deklarationer eller identitetskonflikter kvalificeras inte. Inga deklarationer kopieras mellan fabrikat och inga GTIN fabriceras.

Två individuella eningrediensgranskningar har annan evidensgrund: morot `100794464_ST` och tomat `101880323_ST`. Produktdetaljens uttryckliga grödbeskrivning, relevant grönsakskategori (`N050402` respektive `N050309`), artikelidentitet och förpackning stöder en oförädlad gröda. Rationale och faktisk beskrivning finns i registret. Tom deklaration, kategori eller namn ensamt räcker aldrig; detta är ingen generell namnbaserad regel. Övriga 23 granskningar bygger på produktspecifik deklaration.

[Fyra tillagningar i vanliga generatorn](../backend/app/services/reviewed_warm_meals.py) använder uppmätt ätbar insats, all sås/kokvätska serverad, ingen avrinning och inga olistade kaloribärande ingredienser. Linspasta kokas i såsen; linsgryta serveras med separat absorberat ris; tofupanna tillagas med nudlar och kål; strimlad kyckling ugnsbakas med morötter och serverad sky. Det är olika faktiska beredningar, inte namnbyten.

Nya explicita produktmappningar aktiverar redan lagrade SLV-poster **884 torra röda linser**, **845 torr durumvetepasta**, **422 konserverad tomat med vätska**. Befintliga rå/torr/ätfärdig-referenser för kyckling, ris, tofu, nudlar, kål och morot återanvänds. Produktdeklarationen används i första hand där kompatibel. För nya beredningar är beräkningen `näring per 100 g × använd ätbar insats / 100 / portioner`; rå/torr mängd får inte bytas till kokt/avrunnen mängd.

Alla nya tillagningar är **ESTIMATED**, kräver aktivt medgivande och exakt granskad instruktion. Ingen exakt retentionsfaktor, tillagad vikt eller vitaminretention påstås. Den kvalitativa grunden kommer från [Livsmedelsverkets tillagningsinformation](https://www.livsmedelsverket.se/livsmedel-och-innehall/tillagning-forvaring-hallbarhet/tillagning/hur-paverkas-maten-vid-tillagning/) och [rapporten om näringsförändringar](https://www.livsmedelsverket.se/globalassets/publikationsdatabas/rapporter/2017/2017-nr-21-del-1-naringsforandringar-vid-tillagning-och-forvaring-riskhanteringsrapport.pdf). De stöder bedömningen av en uppskattning, inte en uppmätt numerisk tillagningsfaktor.

## A: hela menyn och inköpet

| Middag, fyra portioner | Protein/portion | kcal/portion | Status |
|---|---:|---:|---|
| Pasta med röd linssås och tomat | 30.38 g | 580.0 | ESTIMATED |
| Röd linsgryta med tomat och ris | 28.39 g | 554.3 | ESTIMATED |
| Tofupanna med äggnudlar och vitkål | 21.30 g | 449.0 | ESTIMATED |
| Ugnsbakad kyckling med morötter och ris | 41.47 g | 514.8 | ESTIMATED |
| Couscoussallad med tofu och tomat | 22.30 g | 416.0 | ESTIMATED |

Samtliga nedanstående priser är den frysta acceptansens priser, inte ett löfte om aktuella produktionspriser. Hela förpackningar betalas; endast receptens använda mängder räknas i näringen. Alla inköpsrader är offentligt tillgängliga utan medlemskap. Transport-/leveransavgifter saknar prisunderlag och ingår inte i varukostnaden.

| Inköpsställe / produkt | Hela förpackningar | Använd mängd | Förpackningsrest | Radkostnad |
|---|---:|---:|---:|---:|
| Coop Online Syd: Couscous | 1 × 500 g | 320 g | 180 g | 19.57 kr |
| Coop Online Syd: Tomater Krossade | 5 × 390 g | 1600 g | 350 g | 39.20 kr |
| Coop Online Syd: Kycklingbröstfilé Strimlad | 1 × 600 g | 600 g | 0 g | 79.00 kr |
| Coop Online Syd: Röda linser Hela | 1 × 900 g | 640 g | 260 g | 29.29 kr |
| Coop Online Syd: Äggnudlar | 2 × 250 g | 320 g | 180 g | 33.00 kr |
| Coop Online Syd: Ris Långkornigt | 1 × 1000 g | 560 g | 440 g | 22.67 kr |
| Willys Lund: Morötter Klass 1 | 3 × 500 g | 1400 g | 100 g | 29.70 kr |
| Willys Lund: Spaghetti | 1 × 1000 g | 300 g | 700 g | 16.90 kr |
| Willys Lund: Naturell Tofu Fast Vegansk | 6 × 200 g | 1200 g | 0 g | 71.40 kr |
| Willys Lund: Tomat Kumato Klass 1 | 2 × 300 g | 600 g | 0 g | 55.80 kr |
| Willys Lund: Vitkål Strimlad Klass 1 | 2 × 400 g | 600 g | 200 g | 27.80 kr |

**Total: 424,33 kr, 11 rader och 25 hela förpackningar.** Coop Online Syd 222,73 kr (online fulfillment, ingen fysisk hyllprisutsaga) + Willys Lund 201,60 kr. Kycklingens offentliga kampanjvillkor och datum följer prisraden i JSON; inga medlemsvillkor har flyttats till delad data.

| Produkt i slutkorgen | Artikel-ID / underlagsfält | Ingrediensevidens |
|---|---|---|
| Röda linser Hela | `7331217016854` / `listOfIngredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Spaghetti | `101548685_ST` / `ingredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Tomater Krossade | `7340191170407` / `listOfIngredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Morötter Klass 1 | `100794464_ST` / `description + breadcrumbs` | `reviewed_single_unprocessed_crop`; inga fiskingredienser identifierade i det granskade underlaget |
| Ris Långkornigt | `7340011340522` / `listOfIngredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Naturell Tofu Fast Vegansk | `101358420_ST` / `ingredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Äggnudlar | `7311312008794` / `listOfIngredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Vitkål Strimlad Klass 1 | `101286120_ST` / `ingredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Kycklingbröstfilé Strimlad | `7313940012679` / `listOfIngredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Couscous | `7340011321767` / `listOfIngredients` | `reviewed_declaration`; inga fiskingredienser identifierade i det granskade underlaget |
| Tomat Kumato Klass 1 | `101880323_ST` / `description + breadcrumbs` | `reviewed_single_unprocessed_crop`; inga fiskingredienser identifierade i det granskade underlaget |

Varje rad länkar vidare till full källa, observationstid och hash genom `field_sources.ingredients` i acceptansens API-svar. Allergistatus för A är **NOT_REQUESTED**, inte VERIFIED.

## B–E och regression

- **B PASS:** UI:s ”Byt recept” ersätter linspastan med kycklingsoppa med äggnudlar/vitkål. Hela femmenyn omräknas till 508,85 kr. Protein/kcal per portion i ordning: 46,04/501,2; 28,39/554,3; 21,30/449,0; 41,62/490,8; 22,30/416,0. Även övriga rätters faktiska produktval får ändras vid omoptimeringen. Full meny, alla paket och samtliga ingredienskällor finns i B.
- **C PASS:** 500 g identitetsbundet ris läggs via skafferi-API; 500 g allokeras/reserveras, faktisk lagermängd förblir 500 g. Inköp 424,33 kr eftersom resterande risbehov fortfarande kräver ett helt paket. Generering bekräftar varken köp eller konsumtion.
- **D PASS, historiskt regressionstest:** exakt tidigare godkända femmiddagsmeny med fisk och dess oförändrade gamla fakta ger 677,43 kr. Stekt torsk/nudlar/kål; torsk-/kålsoppa/nudlar; kokt kyckling/ris/morot; couscoussallad/tofu/tomat; stekt lax/ris/morot. Näring och alla paket finns i D. Nya uppgifter om saltlake/parboiled/fullkorn används i vanlig ny planering, inte för att retroaktivt skriva om detta frysta test eller användarhistorik.
- **E PASS konservativt:** separat `allergies=["fisk"]` ger 422/DATA_BLOCKED. Kandidatdetaljerna visar saknad fullständig ingrediens-/allergeninformation. Granskade ingredienser ersätter inte verifierad allergen-/spårkontroll.
- Redigering med lax ger 422 och sparad revision är oförändrad. Befintliga variation-, medlemspris-, fullförpacknings-, bokförda revisions- och lagerregressioner kvarstår.

**381 tester PASS**, Ruff och compileall PASS. [JUnit](fishfree-20260913/regression.xml). Noll externa konsumentanrop: lokalt UI/API tillåter endast loopback-socket, serverimagen körs med `--network none`, och planens `live_chain_requests=0`. De 12 produktdetaljanropen är en separat förberedande datakomplettering. [Serverimage med monterade verkliga rå-/prisdata](fishfree-20260913/runtime.json) passerar också med samma meny och 424,33 kr vid dess uttryckligt historiska prisklocka.
## Slutlig drift och faktisk HTTPS-användning

**Driftsatt och verifierad:** `personal-v2-fishfree-20260913b`, appkod `061afcf`, image `sha256:8b82c059517d7d8b2742c15ba672f4f97763d15e208588854778a9fe8a3562fe`. Ordinarie HTTPS/API gav **201**, fem godkända middagar och identisk sparad återläsning **2026-09-13 kl. 08:41:17 svensk tid**. [Fullt faktiskt svar](fishfree-20260913/https-final.json).

Priserna var **AGING**, inte nyinsamlade: äldsta användbara priskontext 47,770 h; tre äldre kontexter hade redan uteslutits, inklusive Willys Lund. Ordinarie generator använde då **Willys Lund Nova + Coop Online Syd**. Aktualitetsgränserna 36/48 h, butikstaket och övriga krav är oförändrade. Tidigare HTTPS-prov på första appreleasen kl. cirka 08:33 gav den frysta menyn för 424,33 kr; efter att en kontext åldrats ut ändrades både butik och meny. Detta är observerade resultat vid angiven tid, inga aktuella prisgarantier.

Faktisk slutlig HTTPS-meny (fyra portioner per rätt):

| Middag | Protein/portion | kcal/portion |
|---|---:|---:|
| Pasta med röd linssås och tomat | 30.38 g | 580.0 |
| Röd linsgryta med tomat och ris | 28.39 g | 554.3 |
| Tofupanna med äggnudlar och vitkål | 21.30 g | 449.0 |
| Ugnsbakad kyckling med morötter och ris | 41.62 g | 490.8 |
| Kycklingsoppa med äggnudlar och vitkål | 46.04 g | 501.2 |

Alla fem ESTIMATED, ingen allergi begärd, samtliga slutprodukter ingrediensgranskade. Full faktisk varukostnad **440,26 kr**: Coop Online Syd **140,66 kr** + Willys Lund Nova **299,60 kr**.

| Inköpsställe / produkt | Hela förpackningar | Använt | Rest | Radkostnad |
|---|---:|---:|---:|---:|
| Coop Online Syd: Tomater Krossade | 5 × 390 g | 1600 g | 350 g | 39.20 kr |
| Coop Online Syd: Röda linser Hela | 1 × 900 g | 640 g | 260 g | 29.29 kr |
| Coop Online Syd: Äggnudlar | 3 × 250 g | 640 g | 110 g | 49.50 kr |
| Coop Online Syd: Ris Långkornigt | 1 × 1000 g | 560 g | 440 g | 22.67 kr |
| Willys Lund Nova: Kycklingfilé Strimlad Sverige | 4 × 300 g | 1200 g | 0 g | 175.60 kr |
| Willys Lund Nova: Morötter Klass 1 | 3 × 500 g | 1400 g | 100 g | 29.70 kr |
| Willys Lund Nova: Spaghetti | 1 × 1000 g | 300 g | 700 g | 16.90 kr |
| Willys Lund Nova: Naturell Tofu Fast Vegansk | 3 × 200 g | 600 g | 0 g | 35.70 kr |
| Willys Lund Nova: Vitkål Strimlad Klass 1 | 3 × 400 g | 1200 g | 0 g | 41.70 kr |

Slutliga produktvalens källor, deklarationer och hash finns i HTTPS-svarets `checks.ingredient_exclusions`. Priser och produktfakta är inte livehämtade under planeringen.

Backup före sista appbyte: **20260913T063730Z** (dessförinnan 20260913T063125Z). Aktivering använder befintligt gemensamt driftlås och byter bara app; inga databaser/prismanifest återställs. **147 befintliga planrevisioner bevarade**, databas-integritet ok, scheduler och prismanifest oförändrade under bytet. [Driftverifikation](fishfree-20260913/deployment-final.json). Inga historiska köp, lagerreservationer eller medlemsvillkor migreras.

Befintlig läskompatibel nödrollback `personal-v2-dinners-20260911c-rollback` kan läsa samtliga nya sparade planmodeller, blockerar skrivning och kräver ingen databasrestore: [rollbackbevis](fishfree-20260913/rollback.json). Aktivering/rollback använder den befintliga wrappern och `fishfree_activate.py`; hemliga env-/rollbackkopior ligger endast på servern.

Kvar utanför denna acceptans: konservativt allergiläge behöver fortfarande komplett allergen-/spårunderlag; gamla kokta kycklingrätten saknar kompatibel närings-/beredningsmappning med nya fakta. Det hindrar inte de nu verifierade femmiddagskombinationerna. Priskontexter behöver ordinarie godkänd uppdatering när de når 48 h; ingen fullinsamling startades inom denna milstolpe.
