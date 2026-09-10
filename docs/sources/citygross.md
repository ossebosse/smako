# City Gross — source discovery

Senast verifierad: **2026-08-23**  
Kedja: **City Gross**  
Teknisk source-potential: **verifierad `FULL_ONLINE_CATALOG` för Malmö Hyllie**  
Säkert implementerad `CoverageLevel`: **`FULL_ONLINE_CATALOG` för `storeNumber=3211`**  
Basketkälla: **OWN; Primat finns endast som explicit fallback**  
Source policy: **`REVIEW`; full crawl kräver uttrycklig operator-opt-in och exakt store-allowlist**

## Hur evidensen ska läsas

- **Verifierat (live 2026-08-23):** full Hyllie-traversal kördes mot City Gross officiella publika webbplats utan cookies, login eller privat sessionskontext; raw sparades före parsing och replayades offline.
- **Tidigare verifierat (live 2026-08-22/21):** avgränsad discovery för store-, category-, search-, price- och promotionkontraktet.
- **Verifierat (frontendkontrakt):** route och parametrar finns i den officiella frontendkod som City Gross levererade den 2026-08-21, men just den routen provades inte fullständigt i discovery.
- **Infererat:** en slutsats som måste bekräftas i en connector-canary innan den blir produktionskontrakt.

De strukturerade routarna är storefront-interna och inte ett dokumenterat externt API. Teknisk coverage ska hållas skild från rätt/beredskap att köra en full daglig collector.

## Sammanfattning

| Område | Källa | Resultat |
|---|---|---|
| Butiker | `GET /api/v1/PageData/stores` | **Verifierat live 2026-08-22.** Publik JSON med 38 visade butikssidor och externa site-ID:n. |
| Butiksnummer | `GET /api/v1/sites/{siteId}/storeNumber` | **Verifierat live.** Kopplar CMS-site till katalogens butikskontext. |
| Bred katalog | `GET /api/v1/Loop54/products?store={storeNo}&skip={offset}&take={size}` | **Verifierat live 2026-08-23.** Hela Malmö Hyllie traverserades: 13 642 deklarerade/råa/unika produkter, 137/137 sidor och 0 dubbletter. |
| Sök | `GET /api/v1/Loop54/search?SearchQuery={q}&skip={offset}&store={storeNo}&take={size}&type=product` | **Verifierat live.** 226 träffar för `pasta` i Malmö Hyllie. |
| Kategorikatalog | `GET /api/v1/Loop54/category/{categoryId}/products?...` | **Verifierat live.** Mejeri (`1503`) gav exakt 1 282 råa och unika produkt-ID:n över 13 sidor, utan dubbletter. |
| Kampanjer | Prisobjekt i varje produkt samt `GET /api/v1/offers?...` | Produktpromotioner **verifierade live**; offers-routen svarade men gav noll poster i provet. |
| Embedded JSON | `window.SERVER_DATA` | **Verifierat live.** Initial app-state; katalog och butik är tomma tills en butik valts. |

## Officiella källor

- Butiker: <https://www.citygross.se/butiker>
- Matvaror: <https://www.citygross.se/matvaror>
- Veckans erbjudande: <https://www.citygross.se/matvaror/veckans-erbjudande>
- Robots: <https://www.citygross.se/robots.txt>
- Sitemap: <https://www.citygross.se/sitemap.xml>
- Så fungerar e-handeln: <https://www.citygross.se/kundservice/sahar-fungerar-det>
- Leveransinformation: <https://www.citygross.se/kundservice/leverans>
- Allmänna villkor: <https://www.citygross.se/kundservice/allmanna-villkor>
- Publik butikskälla: <https://www.citygross.se/api/v1/PageData/stores>
- Publik site-källa: <https://www.citygross.se/api/v1/sites?siteTypeId=3>
- Publik postnummerrekommendation: <https://www.citygross.se/api/v1/postalCode/GetRecommendedStoresByZip?zip=22350&count=5>
- Verifierat butiksexempel: <https://www.citygross.se/api/v1/sites/169/storeNumber>
- Verifierad katalogroute: <https://www.citygross.se/api/v1/Loop54/products?store=3211&skip=0&take=20>
- Verifierad sökroute: <https://www.citygross.se/api/v1/Loop54/search?SearchQuery=pasta&skip=0&store=3211&take=20&type=product>

Frontendens aktuella hashade JavaScript-fil verifierades endast som discovery-evidens. Hashen ska inte hårdkodas i connectorn; script-URL:er ska upptäckas från HTML när frontendkontraktet behöver undersökas igen.

## Store discovery

### Alla butikssidor

```text
GET https://www.citygross.se/api/v1/PageData/stores
Accept: application/json
```

**Verifierat live 2026-08-22:** HTTP 200, 38 poster. `GET /api/v1/sites?siteTypeId=3` gav samtidigt 39 site-poster. Skillnaden är en observability-signal: butiksväljaren ska utgå från `PageData/stores`, medan site-källan får användas för ID-koppling och avvikelsen ska mätas. Varje butikspost hade en `data`-del med bland annat:

- `id` — CMS-/sid-ID
- `siteId`
- `url`
- `storeName`
- `storeLocation.coordinates`
- `address.streetAddress`, `address.zipCode`, `address.city`
- `contactInformation`
- `openingHours`
- `services`
- `displayInSiteStoreSelector`, `displayInAppStoreSelector`

### Site-ID till butikens sortiments-ID

```text
GET /api/v1/sites/{siteId}/storeNumber
```

Verifierade exempel:

| Område | Butik | CMS `id` | `siteId` | `storeNumber` | Adressort |
|---|---|---:|---:|---:|---|
| Malmö | Malmö Hyllie | 13481 | 169 | 3211 | Malmö |
| Malmöregionen | Malmö Stora Bernstorp | 2666 | 59 | 3203 | Arlöv |
| närmast Lund i verifierat urval | Staffanstorp | 3123 | 11 | 3229 | Staffanstorp |

Responsen från de tre butiknummeranropen angav även `provider: Axfood`. Det är ett observerat källfält och får inte användas för att slå ihop City Gross- och Axfood-connectorer utan ett uttryckligt, testat kontrakt.

Den officiella butikskällan hade **ingen butik med Lund som namn eller adressort**. Lund-scope måste därför ha en dokumenterad radie-/kommunpolicy och kan till exempel inkludera Staffanstorp som närliggande butik. Systemet får inte fabricera en “City Gross Lund”.

### Lund/Malmö och postnummerkontext — verifierat 2026-08-22

City Gross offentliga kundguide beskriver matvarue-handeln som **välj butik → beställ → hämta i vald butik**. Under rubriken “Våra leveransalternativ” anges upphämtning i butik för varor, recept och catering; den publika leveranssidan beskriver också butiksspecifika upphämtningstider. Det fanns i denna verifiering ingen offentlig uppgift om hemleverans av matvaror från Malmö Hyllie till Lund.

Den säkra kontextmodellen är därför:

```text
PriceContextType = ONLINE_STORE
price_and_assortment_context_id = storeNumber
physical_store_external_id = siteId
catalog_response_fulfillment_type = UNKNOWN
customer_ordering_flow = PICKUP_AT_SELECTED_STORE
```

Detta betyder **inte** att e-handelspriset är bevisat identiskt med fysisk hyllkant. Det betyder att sortimentet och e-handelspriset väljs med den valda butikens `storeNumber`. Kundguiden beskriver upphämtning i vald butik, men Loop54-responsen innehåller inget separat verifierat fulfillmentfält; connectorn lämnar därför just det fältet okänt.

Store-context är funktionell, inte bara kosmetisk. Samma produkt-ID `101253206_KG` kostade 169 kr/kg i Hyllie `3211` och Bernstorp `3203`, men 175 kr/kg i Trelleborg `3232` och Staffanstorp `3229`. Samtidigt skilde deklarerat sortiment: Hyllie 13 614, Bernstorp 13 730, Staffanstorp 13 903 och Trelleborg 13 604. Källan är alltså minst butikskontext-/regionberoende; connectorn får aldrig blanda observationer mellan `storeNumber`.

Offentliga postnummeranrop gav följande exempel:

| Postnummer | Första rekommenderade `storeNumber` | Mappad site | Bedömning |
|---|---:|---|---|
| 22350, Lund | 3232 | City Gross Trelleborg | rankingens semantik är **UNKNOWN** |
| 22660, Lund | 3232 | City Gross Trelleborg | rankingens semantik är **UNKNOWN** |
| 22761, Lund | 3232 | City Gross Trelleborg | rankingens semantik är **UNKNOWN** |
| 21120, Malmö | 3211 | Malmö Hyllie | rekommendationssignal, inte leveransbevis |
| 21532, Malmö | 3211 | Malmö Hyllie | rekommendationssignal, inte leveransbevis |

`GET /api/v1/zipCodes/{zip}/storeNumber` svarade för både 22350 och 21532 med `storeNumber: 0`, `siteId: 0`, `grocery: true`. Semantiken är inte dokumenterad offentligt och får inte användas som e-handels-/leveransbevis. `GetRecommendedStoresByZip` får endast användas som en upptäcktssignal tills frontendkontraktet eller City Gross dokumentation förklarar rankingen. Att Trelleborg rankas först för flera Lund-postnummer visar varför den inte får likställas med “närmsta butik”.

Konsekvens för första scope:

- **Malmö:** Malmö Hyllie är en verifierad fysisk upphämtningsbutik med separat onlinekatalogkontext `3211`. Malmö Stora Bernstorp är en separat närliggande kontext `3203` med adressort Arlöv.
- **Lund:** ingen fysisk City Gross-butik och ingen verifierad hemleveranskontext. Staffanstorp (`siteId=11`, `storeNumber=3229`) kan erbjudas som en uttryckligt närliggande upphämtningsbutik om produktens geografipolicy tillåter det; den får inte märkas “City Gross Lund”.

Primär katalog-/priskontextidentitet: `citygross + storeNumber`. Fysisk butikslänk: `siteId`. Båda bevaras i lineage men får inte byta semantik eller användas omväxlande som samma externa ID.

Frontendkontraktet innehöll också:

```text
GET /api/v1/sites?siteTypeId=3
GET /api/v1/postalCode/GetRecommendedStoresByZip?zip={zip}&count=5
GET /api/v1/zipCodes/{zip}/storeNumber
```

Dessa är bra kandidater för geografisk discovery men ska live-canary-testas innan de blir connector-kontrakt.

## Butikskontext

City Gross frontend kan spara valt sortiment i en vanlig klientcookie och skickar dessutom `store` explicit i katalog- och sökrequests. Den implementerade transporten läser, skickar eller sparar inga cookies; katalog-, kategori-, navigation- och store-anropen verifierades med explicit publik `store`-parameter utan auth/sessiondata.

**Verifierat frontendkontrakt:**

- frontendkontraktet kan lägga valt `storeNumber` i en vanlig store-cookie,
- `assortment_values` innehåller leveranstyp, site-ID och postnummer,
- produktlista och sök använder query-parametern `store`,
- offers-routen är separat och butikskontextberoende; produktpromotionerna i katalogresponsen är den verifierade connectorvägen.

Detta är storefront-/sortimentskontext, inte en inloggningscredential. Connectorn använder endast det publika `storeNumber` som explicit query/context-ID. Inga cookies, sessions- eller autentiseringsvärden sparas i fixtures eller raw metadata.

## Full katalog och pagination

### Verifierad katalogrequest

```text
GET /api/v1/Loop54/products?store=3211&skip=0&take=20
```

**Verifierat live för Malmö Hyllie 2026-08-23:**

```text
totalCount: 13642
pageSize: 100
currentPage: 0
totalPages: 137
items: 100
```

`take=24`, `48`, `96` och `100` respekterades i discovery. Den accepterade fullkörningen använde `take=100`, hämtade samtliga offsets `0..13600`, och terminalsidan hade 42 poster. Varje sida behöll `productStoreDetails.id=3211`. Collector-kontraktet verifierade totalantal, sidantal, förväntat offset, stabil kontext, sid-hash, produkt-ID och termination fail-closed.

### Komplett Hyllie-traversal

```text
reported total:       13 642
expected pages:          137
pages fetched:           137
raw rows:              13 642
unique product IDs:    13 642
duplicates:                 0
missing pages:              0
context switches:           0
HTTP errors / 429:       0 / 0
```

Detta är komplett traversal för den explicit deklarerade **onlinekatalogen för
Malmö Hyllie**, inte ett påstående om varje fysisk hyllprodukt eller andra City
Gross-butiker. Produktantalet ökade från 13 614 i discovery 2026-08-22 till
13 642 vid fullkörningen 2026-08-23; snapshotens eget deklarerade totalantal är
alltid det count som reconcileras.

### Komplett pagineringsbevis för en stor kategori

Mejeri (`categoryId=1503`) traverserades med samma publika route och `take=100`:

```text
reported total:       1282
expected pages:         13
pages fetched:          13
raw rows:             1282
unique product IDs:   1282
duplicates:              0
terminal page rows:      82
price/context rows:    1282 / 1282
```

Detta kategoriresultat var det första pagineringsbeviset. Samma invariants har
nu även passerat för hela Hyllie-katalogen enligt föregående avsnitt.

Ett tomt `SearchQuery` på sökrouten gav korrekt HTTP 400 (“SearchQuery should not be empty”); full katalog ska därför hämtas via `/Loop54/products`, inte genom fabricerade wildcard-sökningar.

### Verifierad textsökning

```text
GET /api/v1/Loop54/search?SearchQuery=pasta&skip=0&store=3211&take=20&type=product
```

**Verifierat live:** `searchResults` innehöll 20 produktposter av totalt 226, 12 sidor. Toppfält var:

- `products`
- `cateredMeals`
- `recipes`
- `pages`
- `categories`
- `stores`
- `facets`
- `totalCount`, `pageSize`, `currentPage`, `totalPages`

### Kategorier

`GET /api/v1/navigation` gav 895 `ProductCategoryPage`-noder: 641 synliga, 763 terminala, 524 synliga terminala och 36 synliga root-produktkategorier. Full katalog ska fortfarande använda den platta `/products`-routen; kategoriträdet är navigerings- och diff-evidens, inte en alternativ sökords-crawl.

Frontendkontraktet bygger kategori-URL:er som:

```text
GET /api/v1/Loop54/category/{categoryId}/products
    ?skip={24 * page}
    &take=24
    &categoryName={name}
    &store={storeNumber}
    [&SortField=...&SortOrder=...&filters...]
```

Kategorirouten är användbar för navigering och diff per kategori, men full collector kan enklare använda den verifierade `/Loop54/products`-routen.

Frontendkontraktet visade även batchläsning:

```text
GET /api/v1/Loop54/products/{comma-separated-product-ids}?SortField=...&take=...&SortOrder=...
```

Batchrouten ska provas separat innan den används för enrichment.

## Produkt-, paket- och tillgänglighetsfält

Verifierade produktposter innehöll bland annat:

- `id` — externt produkt-ID, exempel `101548710_ST`
- `gtin`
- `name`, `subtitle`, `description`, `brand`
- `url`
- `superCategory`, `category`, `bfCategory`, `bfCategoryCode`
- `descriptiveSize`
- `netContent.value`, `netContent.unitOfMeasure`
- `grossWeight.value`, `grossWeight.unitOfMeasure`
- `sellingUnitOfMeasure`
- `sellable`, `maximumQuantity`
- `productStoreDetails.id`
- `productStoreDetails.stockStatus`
- `productStoreDetails.p_availablefrom`, `p_availableto`
- ingrediens-, allergen-, närings-, ursprungs-, märkning- och bildfält

I fullkatalogen hade 13 642/13 642 rader ett rått `gtin`-fält. 13 521
(99,11 %) var checksumgiltiga GTIN-8/12/13/14 och lagrades som `gtin`; övriga
källkoder bevarades endast i raw lineage. Paketmängd kunde fastställas för
12 563/13 642 (92,09 %) och köpmodell för 13 008/13 642 (95,35 %).

### Viktig kvantitetsvarning

En verifierad burkpost hade:

```text
descriptiveSize: 415/230G
netContent.value: 1000
grossWeight.value: 500
```

Källfälten är alltså inte alltid direkt förenliga. Förpacknings- och avrunnen mängd får inte tas från ett enda numeriskt fält. Parsern accepterar `415/230G` som 415 g brutto/230 g användbar mängd **endast** när observerat paketpris och jämförpris oberoende bevisar 230 g, exempelvis `12,25 / 0,230 = 53,26 kr/kg`. Annars lämnas slash-formen konfliktfylld/okänd. Generiska `netContent` och `grossWeight` får inte skriva över den säkrare regeln.

Tillgänglighetsfälten är en stark signal för det valda e-handelssortimentet, men fysisk hylltillgänglighet och uppdateringslatens verifierades inte.

## Prissemantik

Priser låg under:

```text
productStoreDetails.prices.currentPrice
productStoreDetails.prices.ordinaryPrice
productStoreDetails.prices.memberPrice
productStoreDetails.prices.promotions
productStoreDetails.prices.activePromotion
productStoreDetails.prices.lowestPriceLast30Days
```

Verifierade prisfält omfattade:

- `price`
- `unit`, exempel `PCE`
- `comparativePrice`
- `comparativePriceUnit`, exempel `KGM`
- `hasDiscount`, `hasPromotion`
- flaggor för medlemspris och aktuell/långvarig rabatt

Invariant: `comparativePrice` är jämförpris och får aldrig automatiskt bli paketpris eller paketstorlek. `sellingUnitOfMeasure`, `unit`, paketmetadata och pris måste tolkas tillsammans; konflikter blir `UNKNOWN`.

## Kampanjer och medlemspris

Produktposter innehöll strukturerade promotion-objekt med bland annat:

- `id`, `type`, `campaignTypeId`, `name`
- `effectType`
- `membersOnly`
- `from`, `to`
- `minAmount`, `minQuantity`
- `value`
- `maxAppliedPerReceipt`
- `displayLowestPriceLast30Days`
- `priceDetails.price`, `unit`, `comparativePrice`, `comparativePriceUnit`

Verifierade livesvar omfattade publik `2 för 49`, publikt enkelt kampanjpris, medlemspris och medlemsexklusiv `4 för 99`. En promotion blir `MULTIBUY` endast när källan samtidigt anger `type=1`, `effectType=ItemsTotal` och en heltalskvantitet större än ett. `maxAppliedPerReceipt` bevaras som maximalt antal rabatterade grupper för multibuy. Endast ett objekt som exakt matchar `activePromotion` får ändra aktuellt kampanj-/medlemspris; framtida eller inaktiva poster i `promotions[]` bevaras som villkor men skriver inte över current price.

Frontendkontraktet använder:

```text
GET /api/v1/offers?size=999&currentweekoffer=true
GET /api/v1/offers?size=999&nextweekoffer=true
GET /api/v1/offers/{comma-separated-offer-ids}?ignoreStore=true
```

Offers-routen kräver vald butik. Ett tidigare, avgränsat browserprov svarade HTTP 200 med fälten `offers`, `aggregations`, `total`, men totalen var 0 vid verifieringstillfället. Den implementerade HTTP-transporten återanvänder inte browsercookies eller sessiondata. Separata offerposter och kategorier är därför **inte schemafixture-verifierade**; kampanjstödet byggs från de rikare, verifierade produktpromotionerna.

## Coveragebedömning

### Resultat A: `FULL_ONLINE_CATALOG` för Malmö Hyllie

Den publika källans 13 642 deklarerade Hyllie-produkter har traverserats och
reconcilerats exakt. Full snapshot `80b792e5029b4f348478550609ceff10`
reproducerades från immutable raw med noll nätverksanrop, passerade parser-,
schema-, pagination-, pris-, quantity-, recipe- och basketgrindarna och
promotades atomiskt. City Gross är därför en Own-basketkälla för den explicit
verifierade onlinebutikskontexten `3211`.

Detta ändrar inte säkerhetsgränsen:

- `ConnectorRegistry.create(citygross)` ger en inert, en-sides bounded adapter,
- full live collection skapas endast med `CityGrossConnector.for_full_collection()`,
- `CITYGROSS_ALLOW_FULL_CRAWL=true` och exakt
  `CITYGROSS_STORE_EXTERNAL_IDS=3211` krävs,
- standardvärdet för full-crawl-flaggan är `false`,
- canary, store discovery och replay behöver aldrig full-crawl-authority,
- Primat är konfigurerad fallback men väljs aldrig tyst.

Varje run har ett sanerat policy-auditspår i både `collector_runs.scope` och
`collector_runs.metrics`, och full-collect CLI-utdata visar samma fält:
`source_policy=review`, `operator_opt_in`, sorterad `store_allowlist`,
`requests_per_second` och `max_concurrency`. Schemat är stängt (`extra=forbid`)
och kan därför inte bära cookies, headers, tokens eller sessionsdata. Bounded
store discovery/canary rapporterar `operator_opt_in=false` även om full-crawl-
miljövariabler finns i operatorns process.

Coverage gäller **Malmö Hyllie `storeNumber=3211` / fysisk `siteId=169`**.
Bernstorp `3203/59` och Staffanstorp `3229/11` är verifierade separata
pris-/sortimentskontexter men har inte fulltraverserade snapshots. Okända par är
discovery-only och kataloginaktiva. Ingen City Gross-butik eller hemleveranskälla
är verifierad för Lund; Staffanstorp får bara exponeras som närliggande
upphämtningsbutik, aldrig som “City Gross Lund”.

### Verifierad canary, fullkörning och offline acceptance

Den färdiga koden kördes live med `python -m grocery_data canary citygross --city Malmö`:

```text
stores:                  2
sample context:          Malmö Hyllie / 3211
requests:                3
products parsed:         5 / 5
quarantine:              0
parse success:           100 %
declared catalog total:  13 614
captured in canary:      5
schema fingerprint:      present
completion:              incomplete/limited (expected)
runtime:                 4,3 s
```

Rålagret för canaryn innehöll tre payloads (897 159 byte) och inga cookie-,
auth-, token-, API-key- eller sessionfält. Lund-canaryn stoppade fail-closed efter
butikssökning eftersom ingen katalogberättigad Lund-butik hittades.

Fullkörningen sparade 139 payloads / 74 036 248 byte: två butikssvar och 137
katalogsidor. Transporten gjorde 139 requests på cirka 3 minuter 18 sekunder,
med 0 HTTP-fel, 0 svar med 429 och ingen access challenge. Parser v2 +
normalizer v3 gav 13 642/13 642 produkter och priser, 1 574 promotionrader och
0 quarantine. Replay av exakt samma raw startade varken nätverk eller browser
och producerade samma produkt-, pris- och promotionresultat.

En simulerad `currentPrice` → `salesPrice`-förändring ger `BROKEN`, avvisad
kandidat och bibehållen last-known-good. Connector-lokal parserreparation och
replay av samma raw återställer ett godkänt resultat utan ny collection.

### Quality och optimizer-acceptance

| Mått | Full katalog | Broad recipe-relevant diagnostic |
|---|---:|---:|
| Priscoverage | 100,00 % | 100,00 % |
| Ordinarie pris | 100,00 % | 100,00 % |
| Giltig GTIN | 99,11 % | 98,62 % |
| Paketmängd | 92,09 % | 91,70 % |
| Löst purchase model | 95,35 % | 97,35 % |

Quantity confidence för hela katalogen: 12 267 exact, 696 derived, 45
estimated och 634 unknown. `stockStatus` exponeras ännu inte som availability,
så availability coverage är sanningsenligt 0 % tills semantiken har verifierats.

Promotioner: 1 574 totalt; 1 239 multibuy, 62 member-only, 39 member-multibuy,
35 med maxkvantitet och samtliga med komplett `valid_from`/`valid_to`.

Den centrala benchmarken med 48 canonical receptingredienser gav:

```text
>= 1 usable candidate: 48 / 48 = 100,00 %
>= 3 usable candidates: 45 / 48 = 93,75 %
>= 5 usable candidates: 40 / 48 = 83,33 %
representative basket:  13 / 13, complete_for_request=true
```

City Gross Hyllie är därmed `full_basket_capable=true`. Dessa mått gäller den
promoterade snapshoten, inte andra City Gross-kontexter.

## Robots, villkor och requestbudget

**Verifierat live från City Gross officiella `robots.txt`:**

```text
User-agent: *
Disallow: /mina-sidor/
Disallow: /loop54/
```

Den observerade API-routen ligger under `/api/v1/Loop54/`, alltså med prefix och
annan versalisering. Regeln behandlas som en tydlig **policy signal**, inte som
en teknisk accesskontroll eller ett versaliseringskryphål. Källpolicyn är därför
`REVIEW`, inte `ALLOW`: operatorn måste uttryckligen sätta både crawl-flagga och
exakt store-allowlist. `BLOCK` gäller fortsatt för login, CAPTCHA, WAF/access
challenge eller ett manuellt källbeslut, och stoppar körningen direkt utan
bypass.

Den publika `sitemap.xml` svarade 2026-08-22 med HTTP 200 och 1 468 URL:er: 930 under `/matvaror`, 44 under `/butiker`, 20 under `/kundservice` och inga `/api/`-URL:er. Sitemapen är användbar för kategori-/butikskontroll men är inte katalog- eller produktcount-bevis.

Full collection använder som default högst en samtidig request och 1 request/s
(`CITYGROSS_MAX_CONCURRENCY=1`, `CITYGROSS_REQUESTS_PER_SECOND=1`), bounded
retries och omedelbart stopp vid 401, 403, challenge eller 429. Ingen login,
CAPTCHA, dold autentisering eller access-control-bypass användes.

## Kända begränsningar och risker

- Routarna är interna storefront-kontrakt utan versionsgaranti.
- Robots signalerar disallow för Loop54; detta håller source-policy i `REVIEW` och kräver explicit operator-opt-in för varje bred collection.
- Hashade frontendbundles byts vid deploy.
- `netContent`, `grossWeight` och `descriptiveSize` kan motsäga varandra.
- Enumererade kodvärden för vikt- och försäljningsenhet måste fixture-kartläggas; de får inte gissas.
- `stockStatus` är inte verifierat mot fysisk hylla.
- Separata `/offers`-poster var tomma i liveprovet; promotioner i katalogprodukterna är bättre bevisade.
- Full coverage är verifierad endast för Hyllies onlinekontext `3211`; andra contexts kräver egna traversals och snapshots.
- City Gross hade ingen Lund-butik i officiell discovery.
- City Gross publika e-handelsguide beskriver upphämtning i vald butik; Malmö-till-Lund-hemleverans är inte verifierad.
- Postnummerrekommendationernas ranking är odokumenterad och geografiskt oväntad för flera Lund-postnummer.
- Storefältet `provider: Axfood` kan spegla en delad teknisk backend men ändrar inte connectorgränsen; City Gross ska fortsätta vara isolerad.

## Implementerad connector-canary

Den implementerade opt-in-canaryn:

1. hämtar `/PageData/stores` och den publika site-mappningen,
2. verifierar `siteId=169` ↔ `storeNumber=3211`,
3. hämtar endast en katalogsida med fem poster,
4. kontrollerar total/page/context och minst ett stabilt produkt-ID,
5. parservaliderar pris-, comparison- och paketfält fail-closed,
6. sparar rårespons och schemafingerprint,
7. rapporterar explicit `complete=false`, `limited=true`,
8. avbryter vid HTTP-/schemafel, 429 eller ändrad kontext.

Golden fixtures bör minst omfatta fast paket, lösvikt, styckvara, variabel vikt, `415/230G`/drained weight, ordinarie pris, medlemserbjudande, multipack, saknad GTIN och konflikt mellan paketfält.

## HOW TO FIX A BROKEN CITY GROSS CONNECTOR

1. Kör en liten City Gross-canary för exakt `siteId` och `storeNumber`; gör ingen full crawl för att diagnostisera parsern.
2. Kontrollera connector health, HTTP-status, deklarerat `totalCount`, hämtade sidor, unika produkt-ID:n och price/package coverage.
3. Läs schema-fingerprintdiffen och bekräfta om ändringen ligger i store discovery, Loop54-envelope, produkt, pris eller promotion.
4. Inspektera ett begränsat sample från `parser_failures`; logga inte hela payloads.
5. Leta upp den berörda sparade råresponsen via lineage och kontrollera att den inte innehåller cookies, tokens eller persondata.
6. Lägg till eller uppdatera en sanitiserad verklig fixture under `connectors/citygross/fixtures/`.
7. Ändra City Gross-klienten eller parsern lokalt under `connectors/citygross/`; ändra shared core endast med ett reproducerande regressionstest.
8. Kör City Gross parser-, quantity-, promotion-, pagination- och schemafingerprinttester helt offline.
9. Replaya den sparade snapshoten med nätverk och browser avstängda och verifiera noll externa requests.
10. Validera count, dubbletter, priscoverage, quantity confidence och promotions mot senaste goda baseline.
11. Promota endast om hela declared-coverage-kontraktet passerar; annars behåll last-known-good och märk den nya kandidaten `BROKEN`/`DEGRADED`.
12. Verifiera generiska stores/catalog/search/prices/offers-endpoints och `OwnGroceryPriceProvider` innan connectorn åter sätts `HEALTHY`.
