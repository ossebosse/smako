# Separat aktiveringsunderlag — recept och mängd, 26 september 2026

Detta är en inaktiv kandidat. Ingen produktion, schemaläggning, Windows-uppgift eller sparad användarprofil har ändrats.

## Omfattning

Gemensam PersonalPlanner-/matchningskod, dokumenterad mängdprojektion, befintlig deklarationsimport och SLV-referensregister. Inga kedjespecifika undantag för aktuella produkter eller kampanjer. Produktens butik, kanal, pris och prisobservation lämnas oförändrade. GTIN-bunden produktfakta får återanvändas; kampanjmedlemskap får det inte.

Publicera applikationskod och dess datafiler atomiskt enligt befintlig releaseväg. Nya obligatoriska datafiler är `backend/app/data/nutrition/slv-20260926.json` och `edible-yield-references.json`; kompletteringen i `grocery_data/app/data/product_declarations.json` måste följa med. Ofullständig filkopiering är inte ett verifierat paket. `PACKAGE.json` anger slutliga hashar och bevarat tidigare underlag.

## Verifiering

Läs den genererade `VERIFICATION.md` och `summary.json`, inte sammanställningsskriptet som bevis. Alla 84 v1-recept jämförs med identiskt receptinnehåll. Legacy-recept, ordinarie 15/20-profiler, mer omfattande referenssökning och en kontroll utan receptcache redovisas separat. Närings- och mängdbevis per faktiskt kvalificerad kandidat finns i `profile/all-84.json`.

Nya Dabas-/SLV-/dokumenthämtningar har sina verkliga observationstider den 26 september. Prisunderlaget är historisk replay från den 24 september och blir inte färskt av körningen. Nätet är avstängt i den isolerade native-behållaren under planering och HTTP-test. Testklockan är uttrycklig. Källfel/rollback simuleras inte som verklig insamling.

SLV-posternas individuella `retrieved_at` kommer från respektive arkiverat närings-API-svar. Den äldre basfilens datum får inte ärvas av nytillagda livsmedel. De nya referensernas observation gör aldrig historiska priser aktuella.

Matchningskontrollen omfattar även att gravad fisk, burek och soppgrönsaksblandningar inte används som rena råingredienser. Efter den sista blandningsspärren körs samtliga 84, fyra fria profiler, referenssökning, HTTP/omstart/rollback och rebuild om. Ersatta mellankörningar bevaras under `profile/intermediate-*` och räknas inte som slutbevis.

Slutlig källklasskontroll prövar även Ostkex & Tilltugg, Blötmat och gula ärtor med omvänd ordning i produktnamnet. Smakord eller grov katalogkanonisering får inte övertrumfa dessa precisa produktklasser. Ingen regel nämner varumärket Tuc, Poésie, aktuell butik eller kampanj. `profile/identity-guard-verification.json` anger omkörningen efter dessa rättningar. Den isolerade rebuildens automatiska VERIFIED räcker inte ensam som bevis för livsmedelsidentitet; de faktiskt valda produkterna granskas också mot källklass och beredningsgrund.

Textmatchningens reservväg får inte kringgå ett uttryckligt identitets- eller beredningsavslag i den gemensamma matcharen. Den sista rättningen verifieras i `profile/fallback-guard-verification.json`, inklusive omkörning av legacy-regressionen. `rebuild-source-decisions.json` binder de negativa acceptansfallen till verkliga sparade produkter och källkategorier. Äldre mellankörningars lägre kostnader är inte godkända resultat.

Efter native-slutprovet korrigerades endast radbrytningen i ett importblock för Ruff. `format-only-proof.json` visar identiskt Python-syntaxträd före/efter och binder de två filhasharna; exakt native-prövad fil bevaras under `verification-code/`. Inget körbeteende ändrades. Slutpaketets övriga syntax- och formatkontroller kördes därefter.

Rebuild återberäknar den ekonomiska kandidatpoolen och kan därmed ändra receptutbudet. Dess kostnad är inte en jämförbar besparing mot den gamla frysta kandidatpoolen. `profile/rebuild-evidence.json` kontrollerar oförändrade produktfält/prisobservationer, två likadana rebuilds och artefaktens återläsning.

HTTP-proven använder ordinarie `/api/plans`, PersonalPlanner, checkout, audit och PlanStore, följt av GET, processomstart och GET. Inga produktlås, extraköp eller ersatta kandidatlistor. HTTP-tider är funktionella kontrolltider: första anropet kallare, efterföljande anrop delar serverprocess. De ska inte tolkas som ett rättvist prestandamått mellan lägen; de fria profilerna startar i nya processer.

## Visuell kontroll

`visual-check.json` dokumenterar faktiskt granskade webbläsarvyer av sparade, oförändrade HTTP-resultat. Den lokala visningsservern är läsbar och gör inga mutationer. Pris-/mängduppskattning, receptversion och näringsuppskattning visas separat. Inköpslistan skiljer användbar mängd från receptbehov och kräver uppmätt mängd före bokföring av uppskattade inköp. Rå beredningsmetadata översätts för visning; gamla lagrade instruktioner skrivs inte om. Kontroll gjord i desktopvy; ingen separat mobilgranskning påstås.

## Rollbackprov och gräns

Rollbackmålet är den frysta, närmast föregående beredningsleveransen i `baseline-code/`, med stöd för `smako-edible-input-v1`. Samma isolerade PlanStore och oförändrad prisartefakt används. De nya sparade planerna ska återläsas identiskt med äldre kod. Omräkning av de nyupplösta ingrediensfallen ska avslås säkert (HTTP 422) och lämna sparad plan oförändrad. Process, svar och likhetskontroller finns i `profile/http-new-recipes-after-integration.json` och `profile/http-cream-after-integration.json`.

Provet gäller detta explicita rollbackmål. Nedgradering till en ännu äldre version som saknar receptfältet `preparation` är inte verifierad och får inte antas säker. Bevara PlanStore/sparade planer vid rollback; återställ aldrig databasen över nya användarplaner som genväg. Återgång till denna kandidats kod och kompletta faktapaket återger de nya beräkningsmöjligheterna.

## Återstående releasekontroller

- Färsk komplett produktionsbas med oförändrade 36/48-timmarsgränser; historisk replay räcker inte för aktuell aktivering.
- Fullständigt Malmö-publiceringsprov med aktuell komplett bas, fortsatt separat uppgift.
- Den tidigare dokumenterade historiska Lidl-fixturen är fortfarande en separat olöst testlucka; denna etapp reparerar eller döljer den inte.
- Sökningen är begränsad. Kvarvarande budgetavslag och faktiskt numeriska målmissar redovisas separat. Varken de importerade källfakta eller förbättrad täckning ger global optimalitetsgaranti.
- Motstridiga leverantörs-/katalogdeklarationer behålls som konflikter. Generisk referens får inte sudda ut en deklarationskonflikt eller bevisa allergisäkerhet.

Ingen aktivering är utförd eller beställd genom detta underlag.
