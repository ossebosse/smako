# Kedjestatus, kontrollerad 22 september 2026

Ingen aktivering. ICA/Coop/X:-tra, Primat och användarval har bevarats.

| Kedja | Kommuninventering | Butiksspecifik insamling/validering | OWN / PriceUniverse | Ordinarie refresh/rebuild | Nästa avgränsade steg |
|---|---|---|---|---|---|
| Willys | Implementerad, samma kod och färsk register-/SCB-kontroll för Lund 1281 och Malmö 1280. Alla registerrader behålls. | Befintlig full onlinekatalog, exakt aktiverad och återläst butik, samtliga kategorier/sidor; oberoende verifiering av kommunurvalet i källartefakten. | Kommunreferenser följer vanlig collector, SnapshotManager, OWN-provider och produktionsbyggare. | Lund verifierat genom upprepade ordinarie privata rebuilds och omstart. Malmöresultat och avgränsning i README. | Operatörsbeslut, persistent explicit konfiguration, färskhetskontroll. Separat transport/bevis krävs för butiker utan verifierad onlinekatalog. |
| City Gross | Befintlig discovery använder adressort, inte kommunbevis. | **Befintlig full onlinekatalog finns redan.** Historiskt verifierad Hyllie: 13 642/13 642 produkter, 137/137 sidor. Begränsad kedjekontroll 20/9: 100 källrader. Ingen ny City Gross-hämtning i denna körning. | Full OWN-/provider-/PriceUniverse-väg finns; den saknade delen är inte en ny connector. Historiska kampanjer och medlemsflerköp har parsats. | Generisk full refresh, snapshotvalidering och byggare finns; kommunstyrt urval och fortsatt kommunbevis ännu inte verifierat. | Återanvänd hela butikssideregistret + site-mappning, bind officiell position till samma SCB-kommunläge, generera granskningsbart `storeNumber`↔`siteId`-urval. Behåll befintligt uttryckligt fullinsamlingstillstånd; verifiera därefter färsk full katalog och två rebuilds. |
| Lidl | Befintlig locator/adressort; ännu inte motsvarande kommunurval. | Paginerat publikt regionalt erbjudandeflöde finns (`public-default-region`, `offers_only`). Ingen full baspriskatalog. | OWN och generisk provider/evalueringsväg finns. En virtuell region är inte belagt hyllpris i varje fysisk butik. | Fysisk kommunkoppling kan inte aktiveras generellt med dagens regionala bevis. | Kommuninventering plus aktuell nationell eller regional butiksgiltighet **för de konkreta erbjudandena**; återanvänd tidigare nationella reklambladsbevis och produkt/variantkontroller. Generalisera dagens uttryckliga diagnostiska Lund-gate först när giltigheten är verifierad. |

## Prisroller och kanaler

Willys-källan är en butiksknuten **onlinekatalog** med ordinarie köppriser och eventuella separata kampanj-/medlemsavtal. Det är inte bevis för samma fysiska hyllpris. Kommunrättningen ändrar inte prisparsern eller medlems-/gruppköpskontrollerna. Råa `potentialPromotions` är inte liktydigt med villkorslöst godkända köp: prisroller, förpackning, datum och befintlig checkout avgör användningen. Lunds råunderlag innehåller 1 344 GENERAL- och 82 LOYALTY-kopplingar till butik–produkt; dessa är inte antal unika eller planeringsgodkända kampanjer.

City Gross är motsvarande verifierad **online_price** per kontext; inga priser har tilldelats alla kommunens fysiska butiker. Historiska fullkatalog-/kampanjresultat är bevis för återanvändbar kod, inte dagens prisgiltighet. Tidigare kontroll noterade även en BOB-förpackningsoklarhet; den har inte gissats bort.

Lidls tidigare nationella bevisväg kontrollerar bland annat `countryCode=SE`, uttrycklig text om alla butiker i Sverige, specifikt produkt-ID/GTIN där belagt, variant/förpackning, källhash, observation och kampanjdatum. Ett gammalt godkännande eller dagens regionala defaultflöde får inte ersätta ett aktuellt nationellt bevis. Personliga/okända medlemsvillkor ska fortsatt inte göras globala.

## Återanvänd evidens, utan nya kedjeanrop

- `../municipality-offers-20260920/SOURCES.md`, `NEXT.md` och sparade kedjeprober.
- `../../docs/sources/citygross.md`: fullinsamling 23 augusti, snapshot `80b792e5029b4f348478550609ceff10`, samt senare källpolicy.
- Befintliga `citygross`/`lidl` connectors, `lidl_national_offer_evaluation.py`, OWN-provider och produktionsbyggare lästa i aktuell arbetskopia.
- Denna etapp gör inga City Gross-/Lidl-ombyggnader och gör inga nya försök mot tidigare blockerad transport.
