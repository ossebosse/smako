# ICA/Hemköp: kommunval genom befintlig driftkedja

Utgångspunkten var det faktiska, opublicerade Coop-v4-paketet, inte ren Git HEAD. Alla 589 appfiler och 420 bevisfiler verifierades före ändringar. Slutpaketet bygger på samma image och innehåller 592 verifierade appfiler. Coops parser-/versionsrättning, Primat och tidigare releaser bevaras.

## Varför kommunen inte nådde driften

ICA:s `collect_area_offers` och gemensam kommunvalidering fanns redan. Det ordinarie jobbet skapade däremot ett lokalitetsområde och läste en källa under ortnamnet. Providern krävde dessutom att butikens adressort var byggstadens namn. Kommunstödet i inventeringen räckte därför inte för Södra Sandby, Genarp och Veberöd. Den tidigare kompletta-inventeringsgrinden var inte heller ett korrekt villkor för individuellt verifierade, frivilliga erbjudandebutiker.

Hemköps parser filtrerade på adressort och katalogplaneringen utgick från redan registrerade kontexter. Det officiella rikstäckande butiksregistret och den gemensamma positions-/kommungeometrin återanvänds nu före kontexturvalet. Dalby upptäcks trots att butiken inte har onlinekatalog. Befintlig Hemköp-transport används för den offentliga butikssidans strukturerade offline-erbjudanden; ingen ICA-baskatalog återupptas.

## Kodväg och källbindning

- `area_membership.collection_area`: samma `REFRESH_MUNICIPALITY_CODE` kontrolleras mot officiellt kommunnamn och sparas per byggstad i `municipal-collection-scopes.json`. Omstart utan parametern återläser samma val. Lunds val kan inte användas som Malmös val. Detta är ett insamlingsval, inte en ändring av användarens butiker eller inköpsområde.
- `ica_offer_job` och `ica_area_offers`: kommunnycklad källa, verifiering av varje officiell butik och fortsatt individuellt radgodkännande. En misslyckad inventering behåller tidigare källdatabas, godkända butiker och observationstider samt sparar felet och en begränsad återförsökstid. En tidigare verifierad erbjudandelänk på samma officiella butikssida återanvänds för en butik som ännu inte förfallit, även om lokatorsvaret saknar länken.
- `hemkop_municipal_job`, befintlig Hemköp-parser och `willys.municipality_inventory.build_inventory`: officiellt register → bunden SCB RegSO 2025-geometri → verifierade kommunbutiker → befintligt register för fysisk butik/kontext. Inga nya butikskontexter görs obligatoriska. Katalogurvalet respekterar även fortsatt operatörens crawl-allowlist.
- `hemkop.physical_offers`: liten adapter över befintlig Hemköp-connector/transport, OWN-collector och radkontrakt. Endast en explicit produktvariant, fast förpackning och stödda enkla styckepriser godkänns. Villkor, multipla varianter och okänt schema förblir spärrade. Ett åtkomst-/429-stopp avbryter återstående butiksanrop och ger begränsat återförsök.
- `IcaAreaOfferProvider` och dess Hemköp-adapter kopplas in i den ordinarie `production_price_universe_build`. Både officiellt externt butiks-ID och OWN:s interna butiks-ID kontrolleras i respektive namnrymd, tillsammans med adress, postnummer, ort, kedja, snapshot och `:offer-rows`-scope. Produktens interna källbutik måste vara den hämtade OWN-butiken; den får inte jämföras direkt med kedjans externa ID.
- Ordinarie CLI import/build/publicering/reload och `run_daily_refresh` använder samma källval, beständiga förfallotider och befintliga operationslås. Frivilliga källfel rapporteras utan att göra en giltig obligatorisk bas oanvändbar.

Hemköps butikskälla är `https://www.hemkop.se/erbjudanden/{id}`. Den officiella sidans publicerade klientkod använder `GET /search/campaigns/offline?q={id}`. Råsvaren saknar ett separat svarseko av butiks-ID; bindningen bygger därför uttryckligen på den observerade officiella routen, dess q-parameter, registret och den butiksspecifika hämtningen, inte på ett påstått svarsfält. Fel q, URL, kedja, butiks-ID eller HTTP-status spärras. Samma sex kvalificerade varor i flera butiker kommer från separata hämtningar och snapshots, inte kopiering. [Sparad officiell sid-/klientevidens](results/hemkop-public-probe.json).

## Avgränsning av bevisen

Lund har gått hela vägen till faktisk serving, nästa rebuild, reload och omstart. Malmö använder samma kommun- och källkod, men provet har endast ett erbjudandeunderlag och ingen beslutad obligatorisk baspolicy. Dess två identiska kandidater med 580 produkter avslås av den ordinarie kontrollkorgen. Ingen validering har försvagats och ingen Malmö-serving har aktiverats.

Ny faktisk ICA/Hemköp-insamling gjordes 28/9. Replay av samma sparade Hemköp-svar med slutparsern ger samma 42 godkända rader. Ett syntetiskt byte av Hemköp-utgåva, även med återanvänt kampanj-ID, får annat källhash och annat godkännandebevis; detta är ett regressionstest, inte en verkligt observerad andra Hemköp-utgåva. Coops tidigare verkliga kampanjbytesbevis och dess regression återanvänds oförändrade.

Den separata femkällorspolicyn behåller exakt samma fem obligatoriska onlinekontexter och samma filhash. Kommuninsamlingen innebär varken fler tillåtna användarbutiker, annan priskanal eller höjt butikstak. Originalpolicy, sparade användarval, Windows-uppgifter och aktiva scheman är oförändrade. Ingen produktion har aktiverats.

Äldre PurchaseTerms-kopplingar, nya komplexa kampanjvillkor, Lidl/Willys-täckning, full Malmö-publicering och historisk Lidl-fixture är fortsatt separata uppgifter. Kvarvarande dataluckor och nästa källuppgifter redovisas [butiksvis](STORES.md).
