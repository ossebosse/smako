# City Gross kommunstöd – separat, inte aktiverat

City Gross använder den gemensamma kommunfunktionen och befintlig katalog,
GroceryCollector, SnapshotManager, OWN, PriceUniverse, matcher och checkout.
Ingen ny prissättare, handskriven kommunbutikslista eller scheduler införs.

## Inventering och källor

`python -m grocery_data.scripts.collect_citygross_municipality
--municipality-code 1280 --output <ny-isolerad-katalog>` är den avgränsade
insamlingens CLI. Samma kod accepterar alla officiella svenska kommunkoder.
`--inventory-only` hämtar endast inventering/geografi.

Hela officiella City Gross PageData-registret kopplas till det officiella
sites-registret via exakt siteId. storeNumber, siteId, adress och position
behåller sina egna betydelser. SCB RegSO-geometrin och `area_membership`
avgör kommunurval. Vid import räknas både butikskoppling och geografi om från
bevarad officiell evidens; sparat `inside` eller en godtycklig ID-lista räcker
inte. Alla utanför, okända och misslyckade poster redovisas.

Lund 1281 gav noll, Malmö 1280 Hyllie 3211/site169 och Staffanstorp 1230
3229/site11 den 23 september 2026. Malmö Stora Bernstorp är utanför Malmö.
Namnet används aldrig som kommunbevis. Ett tomt verifierat urval är giltigt
och får inte låna en grannbutik.

Kommunadaptern återanvänder den fullständiga onlineconnectorn med exakt
genererad butiksallowlist, sekventiella sidor och befintliga transportgränser.
Priserna tillhör butikens onlinekontext. De belägger inte fysiska hyllpriser.
Katalograder måste innehålla samma storeNumber. Avbruten helkatalog kan ge
`offers_only` genom befintlig radkvalificering av faktiskt hämtade sidor;
ordinarie katalogpris avlägsnas då, originaltider och transportfelet behålls.
Detta är partiell erbjudandetäckning, inte en fullständig separat fysisk feed.

## Ordinarie, beständig driftväg

Avstängt som standard. Den vanliga `deploy/scripts/run_daily_refresh.py`
äger operationslåset och startar `python -m grocery_data daily-refresh`.
City Gross-jobbet körs där före vanlig builder/publicering/reload. Varje senare
rebuild läser samma godkända källreferenser även när inga City Gross-priser
behöver hämtas. Den äldre ortsbaserade City Gross-insamlingen ersätts endast
för den konfigurerade kommunens build.

| Inställning | Betydelse |
|---|---|
| `CITYGROSS_MUNICIPAL_ENABLED=true` | Uttryckligt opt-in, annars av. |
| `CITYGROSS_MUNICIPALITY_CODE` | Officiell kommunkod; ingen reservkommun. |
| `CITYGROSS_MUNICIPAL_ROOT` | Beständig datakatalog; standard bredvid grocery-DB under `citygross-municipal`. |
| `CITYGROSS_MUNICIPAL_BUILD_CITY` | Befintligt build som använder kommunurvalet; standard REFRESH_CITY eller kommunnamn. Väljer inga användarbutiker. |
| `CITYGROSS_MUNICIPAL_INVENTORY` | Valfri verifierad bootstrapinventering; bevaras i state och behövs inte efter omstart. |
| `DEMAND_REFRESH_ENABLED=true` | Använder befintlig lokal behovskontroll, ingen ny tick/scheduler. |

`config.json` sparar enabled, kommunkod och build. Kommunens `source-state.json`
sparar hela inventeringen, alla butikars status, uppdateringstider och relativa
hashkontrollerade referenser till oföränderliga OWN-databaser i `attempts/`.
Varje butik har egen databas och kan behålla sin senaste godkända källa när
en annan butik misslyckas. Ändrad/okänd butikskoppling får inte ärva priser.
Roten ska följa med normal backup; körkontot behöver dess skrivbehörighet.

Ett offers-only-resultat från en avbruten helkatalog sparas separat i
`partial_approved`. Det ersätter inte en fortfarande giltig full katalog.
När fullkatalogen passerar 48 timmar kan den kvalificerade partiella källan
användas med sina egna oförändrade observationer och samma färskhetsgrind.
Fullkatalogfelet och dess retry kvarstår. En lyckad helkatalog tömmer den
partiella reservreferensen; källorna fogas aldrig ihop till en låtsaskatalog.

`source_plan` gör inga nätanrop. Kampanjgränser använder befintlig policy,
baspriser hämtas senast efter 35 timmar, varnar efter 36 och stoppas efter 48.
Misslyckad hämtning behåller endast giltigt underlag med originaltider och
ger befintlig 15 minuters exponentiell retry, maximalt sex timmar. Inventeringen
kontrolleras normalt efter 72 timmar, vid fel efter 15 minuter.
Publicering och reload har separata kvitton; ett lyckat fetch kvitterar aldrig
ett misslyckat reload. Samma kvittomekanism används av Coop.

Den sedan tidigare befintliga `OWN_SOURCES_ONLY=true` används nu även av
ordinarie daily-refresh. Den är ett uttryckligt separat driftläge, inte en
automatisk följd av saknade Primat-kontexter. Standardlägets fullständiga
externa bas, validering och färskhetsgrindar kvarstår. En extern cache accepteras
inte samtidigt med OWN-only. Ingen användarprofil eller skarp inställning ändras.

## Prisavtal och begränsningar

Parser v4 behåller ordinarie pris, publikt kampanjpris och medlemspris separat.
`ItemsTotal` med minQuantity=1 är ett enkelkampanjavtal, inte OTHER. Flerköp
behåller grupppris och antal. Kampanjer med ej stödda villkor, exempelvis
minsta köpbelopp eller kupong, kan inte bli köpbara genom medlemsflaggan.

`maxAppliedPerReceipt` begränsar rabatterade paket/grupper. Källans separata
`maximumQuantity` begränsar antal försäljningsenheter i varukorgen och följer
som `maximum_purchase_units` i SourceProvenance till PU, checkout och audit.
Flera ingrediensrader med samma produkt delar taket. Kg omtolkas inte som
antal: viktköp utan belagt enhetsantal kvalificeras inte med ett sådant tak.
Officiell produktlänk, variant-ID, butik, kanal, förpackning, datum och källtid
behålls; personliga eller villkorslösa gissade rabattpriser införs inte.

## Releasegräns

Se `reports/citygross-municipality-20260923/RELEASE-CITYGROSS.md` för faktisk
testomfattning, källor och kvarstående federerad bas. Testdata innehåller märkta
replay/felinjektioner och ska inte kopieras som skarpt uppdateringsstate.
Ingen produktionsaktivering eller ändring av Windows, aktiva scheman, server-
konfiguration, Primat, väntande ICA-/Coop-/X:-tra-/Willys-releaser ingår.
