# Lidl: frivilliga kommunerbjudanden

Kommunval → officiell nationell sitemap och butiksdetaljer → gemensam SCB-geometri → aktuell nationell publikation och kvalificerad produktkoppling → befintlig Lidl-parser → partiell radvalidering → collector/OWN → PriceUniverse → ordinarie behovsstyrda runner.

Detta är `offers_only` för fysiska butiker. Ingen full baspriskatalog, ingen automatisk nationell giltighet för standardregionens produktflöde och ingen ändring av sparade användarval. Regionala eller lokala publikationer kräver egna bevis. Personliga och aktiveringsberoende priser kvalificerar inte för delad import.

## Källbevis och prisavtal

`municipality_inventory.py` läser alla butiksadresser i Lidls officiella sitemap. Namn och adressort används inte som kommunfilter. Saknade detaljer/koordinater och identitetskonflikter bevaras med orsak. Officiella TNC-ID:n har en uttryckligen härledd, inte avtalsgaranterad, stabilitet; exakt officiell URL, adress, postnummer och position kontrolleras också.

`municipal_offers.py` återanvänder `LidlParser`. `document_qualification.py` kvalificerar en exakt kombination av komplett varumärkesrubrik, namngiven variant och bokstavlig förpackning mot en unik strukturerad produkt. Separata kontroller gäller prisruta, dokumentpris, jämförpris där det finns, kampanjdatum och villkor. Dessa binds till en unik strukturerad produkt med explicit kontrollsiffergiltig EAN. PDF:en innehåller inte dessa EAN-koder: produktkopplingen är kontrollerad sammansatt dokumentidentitet, inte en GTIN-join i reklambladet. Pris är kontrolluppgift, aldrig identitetsnyckel.

Publikationer upptäcks från den aktuella officiella listningen. Nya dokument får prövas med samma slutna textregler utan en manuell produktlista. Osäkra produktbindningar, okända villkor, pant, variantgrupper och tvetydiga prisrutor kräver fortsatt granskning. Tidigare manuella godkännanden gäller endast samma dokumenthash och kontrollerade text. Varken regionala flöden eller gamla granskningar ärver nationell giltighet. Inga bilder analyseras.

Policyn `lidl-national-qualified-document-text-v2` bevarar läsning av tidigare v1-snapshots. Oprövade prislegendfält har uttryckligt textstöd och deras butiksundantag behålls; de ger inte automatiskt butiksgiltighet.

Ordinarie köppris är null. Publikt erbjudande och allmänt Lidl Plus-pris ligger i befintliga `SourceOffer`-avtal. Köpgräns i produktbeskrivningen bevaras. Gemensam `lidl:household:<publication>:<product>`-identitet gör att befintlig gruppcheckout räknar samma hushållsgräns över recept och butiker. Kortare hela dagar behålls; intradagsvillkor som befintligt köpavtal inte uttrycker säkert går till karantän. Pant gissas inte.

Den separata Pågen-deklarationen kan ge produktfakta för exakt GTIN/variant/500 g och granskad kampanjidentitet. Korrekt pris gör inte hamburgare till rå nötfärs och ger inte produkter utan deklaration godkända näringsvärden.

## Frivilligt driftläge

Ingen inställning nedan är aktiverad i produktion av denna leverans.

- `LIDL_MUNICIPAL_ENABLED=true` är uttryckligt första tillval.
- `LIDL_MUNICIPALITY_CODE` är officiell fyrsiffrig kommunkod.
- `LIDL_MUNICIPAL_ROOT` pekar på en separat beständig datamapp.
- Byggstad måste motsvara kommunen. Felkonfiguration är ett synligt frivilligt källfel.
- `LIDL_MUNICIPAL_INVENTORY` kan ge första hashbevarade officiella inventeringen; kommande inventeringar sker via samma officiella väg.

Första körningen sparar konfigurationen. Senare processer kan läsa kod och enabled-läge från disk. `grocery_data daily-refresh` anropar källadaptern under befintligt operationslås. Godkända relativa SQLite-referenser och snapshot-ID:n återanvänds vid varje normal rebuild; publicering och HTTP-reload kvitteras separat. Ingen separat scheduler eller ny prissättare finns.

En kommunhämtning delar samma nationella källsvar mellan endast belagt omfattade butiker. Uppdateringen följer befintlig kampanjstyrning och 35-timmarskontroll för att respektera 36/48-timmarsgränserna. Hämtfel får befintlig begränsad återförsökstid och bevarar fortfarande giltig LKG med originalobservation. Förfallna priser spärras av befintliga kontroller. Kontroller utan förfall gör inga externa prisanrop.

## Isolerad insamling

Python 3.12 och `grocery_data/requirements-lidl-candidate.txt` krävs. PyMuPDF används enbart för dokumenttext, samma version som det verifierade X:-tra-underlaget.

```powershell
py -3.12 -m grocery_data.scripts.collect_lidl_municipality --municipality-code 1281 --output <ny-isolerad-mapp>
py -3.12 -m grocery_data.scripts.collect_lidl_municipality --municipality-code 1280 --output <annan-ny-isolerad-mapp>
```

`--inventory` återanvänder och omvaliderar en officiell inventering. `--replay` är uttryckligt offlineunderlag, bevarar originaltider och rapporterar noll nya prisanrop. Båda argumenten är verifierings-/insamlingstillval, inte produktionstillstånd.

Se historiskt underlag i `reports/lidl-municipality-20260923` och aktuell jämförelse i [pristäckningsrapporten](../reports/offer-coverage-20260924/README.md). Fullständigt federerat Malmö-publiceringsprov med färsk komplett bas och Lidls dokumenterade historiska nutritionstestlucka är fortsatt öppna.
