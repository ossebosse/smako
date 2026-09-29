# Willys: preciserade butiksluckor och kvarstående prov

Kontrollerat 23 september 2026 kl. 10:00 Europe/Stockholm. Willys kommunimplementation, tester och [releaseunderlag från 22–23 september](../willys-municipality-20260922/RELEASE.md) är bevarade. Denna avgränsade kontroll ändrar ingen kod, prispost, driftkonfiguration eller aktivering.

## Varför sju butiker inte gav onlineprisunderlag

Alla sju är identifierade i det officiella registret, har `open=true`, `onlineStore=false` och `clickAndCollect=false`. Både det sparade registret från 22 september och ett nytt verkligt registeranrop 23 september visar dessa flaggor. Deras officiella positioner är i respektive kommun enligt det befintliga SCB-underlaget. De saknas därför inte genom ett felaktigt kommunurval eller en saknad butiksidentitet.

| Kommun | Butik | Butiks-ID | Konkret dokumenterad orsak | Officiell publik erbjudandekälla, kontrollerad separat |
|---|---|---|---|---|
| Lund 1281 | Willys Hemma Lund Stortorget | 2863 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts av katalogurvalet före prishämtning. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2863/), HTTP 200, publikation `p001-004_WH_V39_ED1.pdf`. |
| Malmö 1280 | Willys Hemma Malmö Lindängen | 2843 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts före prishämtning. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2843/), HTTP 200, publikation `p001-004_WH_V39_ED1.pdf`. |
| Malmö 1280 | Willys Hemma Malmö Lugnet | 2851 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts före prishämtning. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2851/), HTTP 200, publikation `p001-004_WH_V39_ED1.pdf`. |
| Malmö 1280 | Willys Hemma Malmö Möllevången | 2870 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts före prishämtning. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2870/), HTTP 200, publikation `p001-004_WH_V39_ED1.pdf`. |
| Malmö 1280 | Willys Hemma Malmö Söderkulla | 2865 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts före prishämtning. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2865/), HTTP 200, publikation `p001-004_WH_V39_ED1.pdf`. |
| Malmö 1280 | Willys Hemma Oxie Centrum | 2879 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts före prishämtning. Oxie ligger enligt positionsbeviset inom Malmö kommun. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2879/), HTTP 200, publikation `p001-004_WH_V39_ED1.pdf`. |
| Malmö 1280 | Willys Malmö Rosengård | 2352 | Ingen verifierad butiksspecifik onlinekatalog: källans `onlineStore=false`; utesluts före prishämtning. | [Butikens reklamblad](https://reklamblad.willys.se/willys/2352/), HTTP 200, publikation `ED1_0001-0012_WIL V39.pdf`. |

**Klassificering:** sju fall av *ingen verifierad butiksspecifik onlinekatalog*. Inget av dessa bortval är dokumenterat som åtkomst-/konfigurationsfel, saknad/felaktig butikskoppling eller annan driftorsak. Det betyder inte att möjligheten till katalogåtkomst har motbevisats genom ett nytt katalogförsök: sådana försök har inte gjorts. Ett tidigare postnummerformatfel i OWN-provider rättades och rörde verifierade onlinebutikers import; det är inte orsaken till de här sju butiksluckorna. Den okända nationella registerraden `2002` är ett separat identitetsfel och är inte någon av dessa sju butiker.

Kodens faktiska beslut finns i [municipality_inventory.py](../../grocery_data/app/connectors/willys/municipality_inventory.py): `collection_selected` kräver kommunstatus `inside` och `online_shopping is True`; övriga innanför får `no_verified_online_catalog`. [connector.py](../../grocery_data/app/connectors/willys/connector.py) kräver också `online_shopping is True` för katalogen. Den tidigare [butiksrapporten](../willys-municipality-20260922/COVERAGE.md) använder samma underlag.

## Erbjudandekällorna finns, men är ännu inte anslutna

Det aktuella [officiella butiksregistret](https://www.willys.prod.axcsfprod.aws.axfoodapp.cloud/axfood/rest/v1/store) publicerar varje butiksspecifik `flyerURL` ovan. Alla sju länkar har hämtats var för sig och returnerar verkliga reklamblad med erbjudandetext i HTML. De sex Hemma-butikerna pekar vid kontrollen på samma publicerings-ID `b41cbfdd-679c-42dc-a87a-6911734c8a8d`; Rosengårds publicerings-ID är `51714d69-989d-4a0d-be80-4365684b295d`. Kopplingen är belagd separat från varje butiks egen registerpost och sida; inga priser kopieras mellan butiker.

En publik erbjudandekälla finns alltså för **var och en av de sju butikerna utan att full onlinekatalog behövs**. Däremot kan den nuvarande Willys-connectorn inte använda dessa blad oförändrad: `fetch_offers()` returnerar avsiktligt en tom batch och återanvänder bara `potentialPromotions` från fullkatalogens produktrader. Ingen Willys-transport/parser för `flyerURL` eller iPaper finns i den granskade koden. Den konkreta återstående luckan är därför anslutning och radkvalificering av den redan publicerade erbjudandekällan, inte belägg för att butiken saknar erbjudanden.

Ett senare avgränsat Willys-tillägg kan föra kvalificerade butikserbjudanden genom befintlig `offers_only`-validering, OWN och PriceUniverse. Det behöver belägga produkt/variant, förpackning, exakt prisroll, datum, medlemsvillkor, maxantal och fysisk butiksgiltighet från respektive källa. Ett publiceringsnamn med vecka 39 eller HTTP 200 ensamt godkänner inga prisavtal. Här kontrolleras endast källornas existens och koppling; inga erbjudanderader normaliseras, importeras eller godkänns, och ingen bildanalys görs.

## Malmös fullständiga publiceringsprov återstår

Det bevarade Willys-resultatet är verklig insamling av fyra Malmö-kataloger, **39 274 OWN-poster och 38 950 PriceUniverse-poster**, samt vanlig produktionsbyggare och ombyggnad efter omstart med identisk prispostsignatur. Kandidaten är uttryckligen OWN-only. Den verifierar inte en full federerad Malmö-publicering/reload med aktuell komplett Malmö-bas inklusive Primat.

Inför ett separat sådant prov återstår att:

1. Tillhandahålla aktuell komplett bas för rätt Malmö-omfattning via den ordinarie behovsstyrda vägen och kontrollera varje källas ålder. Ingen Lund-bas, begränsad sökprojektion eller föryngrad observation får ersätta detta.
2. Genom avsedd isolerad driftstart köra ordinarie låst refresh/rebuild, validering, atomisk publicering och reload; verifiera aktiv manifestreferens, faktiska Malmö-butiker och prisroller samt health/ready.
3. Köra andra ordinarie rebuild och processomstart med beständigt kommunval/status; jämföra prispostsignaturer och originaltider samt verifiera 0 externa prisanrop när inget är förfallet. Dokumentera verklig hämtning, replay och injicerade fel var för sig.
4. Verifiera representativa produkt-/receptköp genom matcher, checkout och audit i den kompletta federerade omfattningen, plus förfall, hämtfel, LKG och återhämtning med oförändrade pris- och färskhetsregler.

Det tidigare [beslutsunderlaget](../willys-municipality-20260922/decision-current.json) är en tidsstämplad observation, inte dagens aktiveringsbesked. Den gamla federerade Lund-basen hade redan passerat en baskällas 48-timmarsgräns den 23 september kl. 03:17:55 Europe/Stockholm. Den får inte återanvändas som aktuellt Malmö-underlag eller giltigt rollbackunderlag. Willys-källornas och andra baskällors ålder ska bedömas separat vid ett senare prov/beslut. Ingen aktivering görs här.

## Lidls nästa konkreta steg

Återanvänd befintlig locator, `offers_only`-connector och nationell erbjudandebevisning. Nästa avgränsade arbete är att binda hela officiella butiksinventeringen till samma kommunfunktion och verifiera Lund/Malmö, med utanför/okänd/misslyckad butik bevarad. Koppla därefter ett **aktuellt** officiellt regionalt eller nationellt erbjudandeunderlag till exakt de butiker där det gäller och kvalificera konkreta produkt-/variant-/förpackningsrader genom befintlig OWN/PriceUniverse-väg. Standardregion 1 eller ett utgånget historiskt nationellt blad räcker inte som allmän fysisk butiksgiltighet. Medlemsmålgrupp och villkor måste förbli explicita. Ingen Lidl-ombyggnad eller ny Lidl-hämtning görs i denna kontroll.

## Evidens och omfattning

[Sanerad nät- och butiksevidens](willys-gaps-public-evidence.json) innehåller URL, observationstid, HTTP-status, hash, publicerings-ID, källa/flagga per butik samt hänvisning till återanvänt kommunbevis. Nätkontrollen gjorde **8 explicita offentliga hämtningar**: ett register och sju butiksblad (klienten följde källornas URL-kanonisering till avslutande snedstreck; transportanrop inklusive redirects har inte räknats separat). Registret innehöll 258 rader. Sökindex gav inga träffar och används inte som frånvarobevis. Ingen inloggning, sessiondata, fullkataloginsamling, bildtolkning, modell-API, Windows-/schemaändring eller produktionsaktivering användes. Kommungeometrin är återanvänt verifierat underlag från 22 september; inga nya SCB-anrop gjordes. Endast denna rapport och dess sanerade JSON-evidens har skapats av denna deluppgift.
