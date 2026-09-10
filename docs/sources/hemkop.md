# Hemköp — source discovery

Senast verifierad: **2026-08-24**  
Kedja: **Hemköp**  
Nuvarande säkra `CoverageLevel`: **`FULL_ONLINE_CATALOG`**  
Teknisk fullkatalogskapacitet: **verifierad för Malmö Triangeln `4247`, Lund Brunnshög `4224` och Lund Karhögstorg `4123`**  
`SourcePolicy`: **`REVIEW`**

Hemköps publika webbshop har en deterministisk kategoristruktur och ett
paginerat JSON-flöde med priser och kampanjer. Ett normalt publikt butiksval
kunde aktiveras och läsas tillbaka för både Lund och Malmö. Malmö Triangeln
reconcilerades till 9 002 unika produkt-ID:n över 113/113 sidor. Lund Brunnshög
reconcilerades separat till 5 086 unika produkt-ID:n över 67/67 sidor och Lund
Karhögstorg till 6 092 över 78/78 sidor. Alla tre contexten har egna promoterade
snapshots; den senaste Karhögstorg-crawlen har noll dubbletter inom en kategori.

Live-snapshot `4d572317b00049268f8ee1d3b3060c87` lämnades avsiktligt
`HEALTH_CHECKED` och inaktiv. Dess raw-data replayades helt offline till
snapshot `00db33803746408796d118c91270fccc`, som efter separat validation och
acceptance blev atomiskt **`PROMOTED`**, aktiv och `HEALTHY`. Replay gjorde
noll nätverksanrop och startade ingen browser.

Lund Brunnshögs source-snapshot `a579353ef6844296a03d75b69fedbf53`
reproducerades också offline med noll nätanrop och är separat **`PROMOTED`**,
aktiv och `HEALTHY`. Karhögstorg `4123` har verifierad onlineaktivering, exakt
contextlänk och den separat promoterade, aktiva source-snapshoten
`2d669d3dd375462fbb5fb8cf5a5ec934`. Dess offline replay
`1398f77ad6654c668375122b9adae178` gjorde noll nätanrop och reproducerade samma
6 092 produkter.

Policyn är `REVIEW`, inte `BLOCK`. `robots.txt` anger både begränsningar och
requestbudget, och de aktuella e-handelsvillkoren begränsar användningen av
webbplatsens innehåll. Den breda collectorn är därför avstängd som standard
och kräver explicit operator-/policybeslut. Ingen login, CAPTCHA,
anti-bot-utmaning eller annan teknisk accesskontroll observerades i discovery
eller fullkörning.

## Hur evidensen ska läsas

- **Verifierat live:** requesterna kördes mot Hemköps officiella publika
  webbplats den 2026-08-23; den rena Karhögstorg-fullcrawlen kördes och
  inspekterades separat den 2026-08-24.
- **Verifierat i normal publik session:** Hemköps vanliga sessionsflöde valde
  butik och `/store/active` bekräftade exakt begärd butik. Kortlivad
  sessions-/CSRF-data sparades inte.
- **Verifierat frontendkontrakt:** route och parametrar finns i den officiella
  JavaScript-klient som Hemköp levererade 2026-08-23.
- **Infererat:** slutsatsen stöds av frontend och live-data men måste bekräftas
  av connector-canary eller full traversal innan den får bli
  produktionskontrakt.

Routarna är storefront-interna och inte ett dokumenterat externt API. De måste
schemaövervakas och kan ändras utan versionsgaranti.

## Sammanfattning

| Område | Källa | Resultat |
|---|---|---|
| Butiker | `GET /axfood/rest/store?online=false` | **Verifierat live.** 205 publika butiker med stabila `storeId`. |
| Aktiv butik | publik CSRF + `POST /axfood/rest/store/activate`, därefter `GET /axfood/rest/store/active` | **Verifierat live** för Lund `4123`/`4224` och Malmö `4247`. |
| Kategorier | `GET /leftMenu/categorytree?storeId={storeId}` | **Verifierat live.** 534 noder, 414 löv, 20 förstakategorier. |
| Katalog | `GET /c/{categoryPath}?page={page}&size={size}` | **Verifierat full traversal** för Malmö `4247` och Lund `4224`/`4123`, med exakt klassificerat category-overlap. Den historiska `4123`-kandidaten underkändes fail-closed; sparad replay bevisade en identisk pagination-overlap och en senare ren fullcrawl promoterades. |
| Kategorisida | `GET /sortiment/{categoryPath}` | **Verifierat live.** Next.js-SSR med kategori-/fallbackkontrakt; produkter hämtas client-side efter butiksval. |
| Sökning | `GET /search?q={query}&page={page}&size={size}` | **Verifierat live**, men `?q=` är `Disallow` i robots och ska inte användas för katalogtraversering. |
| Produktdetalj | `GET /axfood/rest/p/{productCode}?isEanCode=false` | **Verifierat live.** EAN, pris, jämförpris och rik produktmetadata. |
| Kampanjer | `GET /search/campaigns?page={page}&size={size}` | **Verifierat live.** Promotionobjekt, inklusive Klubbpris och multipack. |
| Embedded state | Next.js `__NEXT_DATA__`, `/api/config`, `/api/flags` | **Verifierat live.** Användbart för discovery/versionering; inga klientvärden eller sessionsvärden lagras. |

## Officiella källor

- Butikssök: <https://www.hemkop.se/butik-sok>
- Sortiment: <https://www.hemkop.se/handla>
- Verifierad kategorisida: <https://www.hemkop.se/sortiment/mejeri-ost-och-agg>
- Erbjudanden: <https://www.hemkop.se/erbjudanden>
- Prissättningsinformation: <https://www.hemkop.se/artikel/prissattning>
- E-handelsvillkor: <https://www.hemkop.se/artikel/anvandarvillkor>
- Robots: <https://www.hemkop.se/robots.txt>
- Sitemap: <https://www.hemkop.se/sitemap.xml>
- Publik butikskälla: <https://www.hemkop.se/axfood/rest/store?online=false>
- Kategoriträd, exempel: <https://www.hemkop.se/leftMenu/categorytree?storeId=4224>
- Katalog-JSON, exempel: <https://www.hemkop.se/c/mejeri-ost-och-agg?page=0&size=30>
- Sök, diagnostiskt exempel: <https://www.hemkop.se/search?q=pasta&page=0&size=12>
- Produktdetalj, exempel: <https://www.hemkop.se/axfood/rest/p/101548687_ST?isEanCode=false>
- Kampanjer, exempel: <https://www.hemkop.se/search/campaigns?page=0&size=12>

Frontendens chunkfilnamn är innehållshashade och ska inte hårdkodas. Aktuella
script-URL:er och build-id ska upptäckas från den publika sidan.

## Store discovery

### Request och identity

```text
GET https://www.hemkop.se/axfood/rest/store?online=false
Accept: application/json
```

**Verifierat live:** HTTP 200, JSON-array med 205 poster.

Viktiga fält:

- `storeId`
- `name`
- `open`, `external`
- `onlineStore`, `clickAndCollect`
- `geoPoint.latitude`, `geoPoint.longitude`
- `address.line1`, `address.town`, `address.postalCode`
- leverans-, plock- och servicefält

Identity är `hemkop + storeId`.

### Lund och Malmö

Alla sex poster nedan var `open=true`, `onlineStore=true` och
`clickAndCollect=true` i den verifierade responsen.

| `storeId` | Namn | Postnummer/ort | Adress |
|---|---|---|---|
| `4224` | Hemköp Lund Brunnshög | 224 81 Lund | Solbjersvägen 32 |
| `4123` | Hemköp Lund Karhögstorg | 223 58 Lund | Karhögstorg 2a |
| `4212` | Hemköp Malmö Elinegård | 216 33 Limhamn | Tröskgatan 8 |
| `4114` | Hemköp Malmö Kronprinsen | 217 48 Malmö | Regementsgatan 52 |
| `4247` | Hemköp Malmö Triangeln | 211 43 Malmö | Södra Förstadsgatan 58 |
| `4199` | Hemköp Malmö Värnhem | 212 12 Malmö | Fredsgatan 12b |

Geografisk filtrering ska använda adress, postnummer och koordinater. En
delsträngsmatchning på butiksnamn gav tidigare falska träffar som Göteborg
Lundby och Mjölby Lundby.

## Butiks-, sortiments- och priskontext

Hemköps frontend använder en aktiv butik i en cookie-bunden, anonym session:

```text
GET  /axfood/rest/csrf-token
POST /axfood/rest/store/activate
     ?storeId={id}
     &activelySelected=true
     &forceAsPickingStore=true
GET  /axfood/rest/store/active
```

Detta flöde verifierade `4123` Lund Karhögstorg, `4224` Lund Brunnshög och
`4247` Malmö Triangeln med exakt readback av vald `storeId`. Token och cookies var kortlivade
transportdetaljer och sparades inte i rådata, loggar eller dokumentation.

Ett nytt anonymt anrop utan uttryckligt butiksval fick i stället Hemköps
standardkontext `4003` i Bålsta från `/store/active`. Sådana produkt- och
prisresultat får aldrig märkas som Lund eller Malmö.

Fail-closed-kontraktet kräver två oberoende contextbevis i samma raw batch:

1. sparat HTTP-200-readback från `/store/active` vars `storeId` exakt är den
   begärda butiken; och
2. varje katalogsidas strukturerade facet-query måste innehålla exakt samma
   `salableOnlineInStore_string_mv:{storeId}` och ingen annan butik.

Saknat/mismatchat readback eller facet ger noll parsade katalogprodukter,
`price_context_unverified`/schemafel och en `BROKEN` kandidat. En sådan kandidat
kan inte promotas och påverkar inte last-known-good.

Den officiella prissättningssidan säger uttryckligen att priserna på
`hemkop.se` gäller e-handeln och att priser i fysiska butiker kan skilja sig
mellan butik och ort. Den säkra contextmodellen är därför:

```text
active Hemköp store/picking context
    -> store-backed online assortment
    -> Hemköp e-commerce price
```

Det är inte verifierat att webbpriset är identiskt med fysisk hyllpris.
Butiksvalet påverkar sortimentet: huvudkategorin Mejeri, ost & ägg rapporterade
563 produkter för Lund `4224` och 887 för Malmö `4247`. Bland 82 produkt-ID:n
som fanns i båda kontexternas första 100 resultat var pris och observerad
promotion lika i stickprovet. Det bevisar butiksspecifikt sortiment, men varken
motbevisar eller bevisar butiksspecifik prisvariation. Prisobservationer ska
ändå bindas till den bekräftade aktiva kontexten.

## Kategori, katalog och pagination

### Kategoriträd

```text
GET /leftMenu/categorytree?storeId=4224
```

Live-resultat:

- en syntetisk rot `N00` / Alla varor,
- 20 förstakategorier,
- 534 noder totalt,
- 414 terminala löv,
- samtliga 534 noder markerade giltiga,
- maximalt djup 4.

Noderna har `id`, `title`, `url`, `valid` och `children`. Exempel på rötter är
`N01` Kött, fågel & chark, `N04` Frukt & grönt, `N06` Mejeri, ost & ägg och
`N10` Skafferi.

### Publik kategorisida och runtime-JSON

```text
GET /sortiment/mejeri-ost-och-agg
GET /c/mejeri-ost-och-agg?page=0&size=30
```

Kategorisidan svarade HTTP 200 och Next.js `__NEXT_DATA__` deklarerade det
runtime-flöde som frontend använder: `fn=/c/mejeri-ost-och-agg`, nollbaserad
`page` och `size=30`. Offentlig source map för sidkomponenten säger också att
produktdata hämtas client-side eftersom aktiv butik inte är känd vid build.

Det direkta JSON-svaret innehöll bland annat:

- `results`
- `pagination`
- `categoryInfo`, `superCategories`, `categoryBreadcrumbs`
- `subCategories`, `facets`, `sorts`
- produktkort med pris-, paket-, lager- och promotionfält.

### Pagination-proof och full traversal

För aktiverad Malmö Triangeln-kontext `4247` traverserades Mejeri, ost & ägg
först som ett separat exakt bevis:

```text
reported / raw / unique: 887 / 887 / 887
pages: 9 / 9
duplicates: 0
price rows: 887
```

Den efterföljande fullkörningen använde de 20 förstakategorierna som source-
partitioner. De är inte disjunkta navigationsmängder, vilket live-evidensen
gjorde synligt. Fullständighet räknas därför med två separata dubblettmått:

```text
categories: 20 / 20
pages: 113 / 113
declared category rows: 10 016
raw rows: 10 016
unique product IDs: 9 002
within-category duplicates: 0
cross-category duplicates: 1 014
```

Varje cross-category-dubblett hade samma stabila produkt-ID och samma
semantiska produktfingerprint. En ändrad dubblettrad, en dubblett inom samma
partition, en saknad sida eller en oförklarad differens gör completion ogiltig.
Det generiska `CatalogCompletion`-kontraktet kräver exakt:
`raw = unique + cross`, `within = 0`, alla deklarerade sidor och att varje
dubblett är klassificerad.

Axfood-protokollet deklarerar dessutom en extra terminal sentinel-sida när
`totalNumberOfResults` är exakt delbart med `pageSize`; Hemköps verifierade
form är `results: null`. Paginationvalidatorn accepterar endast denna exakta
terminalform och stoppar vid `[]`, saknat fält eller avvikande sidaritmetik.

### Textsökning är inte traversal

```text
GET /search?q=pasta&page=0&size=12
```

Svaret gav 12 rader av 254 och:

```text
pageSize: 12
currentPage: 0
numberOfPages: 22
totalNumberOfResults: 254
```

Sökningen är användbar för canary och användarsökning men ska inte bygga full
katalog. `robots.txt` markerar dessutom `?q=` som `Disallow`.

## Produkt-, pris- och kvantitetsfält

Verifierade katalog-/sökresultat innehöll bland annat:

- `code` — stabilt externt produkt-ID, exempel `101548687_ST`
- `name`, `manufacturer`
- `price`, `priceValue`, `priceUnit`
- `comparePrice`, `comparePriceUnit`
- `productLine2`, `displayVolume`, `averageWeight`
- `productBasketType`, `incrementValue`
- `online`, `outOfStock`
- `potentialPromotions`
- kategori-, etikett- och bildfält.

Produktdetaljen:

```text
GET /axfood/rest/p/101548687_ST?isEanCode=false
```

gav `ean: 7311043008346` för Garant Fusilli 500 g och bland annat:

```text
priceValue: 15.09
priceUnit: kr/st
comparePrice: 30,18 kr
comparePriceUnit: kg
productLine2: GARANT, 500g
displayVolume: 500g
online: true
outOfStock: false
```

EAN fanns i detaljresponsen men inte i katalogkorten. Fullkörningens uppmätta
GTIN-coverage är därför 0 %. GTIN-enrichment kräver extra, separat budgeterade
detaljanrop och ingår inte i standardtraversalen.

Semantiska invariants:

- `priceValue`/`priceUnit` är försäljningspris och försäljningsenhet.
- `comparePrice`/`comparePriceUnit` är jämförpris, aldrig förpackningsstorlek.
- kg-jämförpris får inte skapa ett påhittat 1 kg-paket.
- `productLine2`, `displayVolume` och `averageWeight` sparas raw-first.
- tvetydig mängd blir `UNKNOWN`, inte en fabricerad kvantitet.
- `outOfStock` får endast kopplas till en bekräftad aktiv onlinekontext.

## Kampanjer och medlemspris

```text
GET /search/campaigns?page=0&size=12
```

Det verifierade anonyma svaret hade 12 resultat av 412 och 35 sidor.
Strukturerade promotionfält omfattade:

- `code`, `promotionType`, `campaignType`
- `price.value`, `qualifyingCount`
- `conditionLabel`, `rewardLabel`, `realMixAndMatch`
- `validUntil`, `productCodes`, `applied`
- `lowestHistoricalPrice`, `promotionTheme`, `comparePrice`.

Verifierade former omfattade `GENERAL`, `LOYALTY`/Klubbpris och
mix-and-match. “3 för 39 kr” ska sparas med kvalificerande antal 3 och
totalpris 39; det får inte bli ovillkorligt 13 kr/st. Klubbpris ska vara
`member_only=true` och aldrig presenteras som allmänt pris.

Frontendkontraktet visar även läsroutes för kampanjgrupper och
promotionprodukter, men de är inte fullständigt liveprovade. Kampanjer hämtade
utan verifierad aktiv butik får inte märkas som lokala.

## WILLYS → HEMKÖP REUSE ANALYSIS

Hemköp och Willys delar tydligt Axfood-domän och många källfält, men de är inte
samma transportkontrakt.

| Lager | Återanvändning | Evidens/konsekvens |
|---|---|---|
| HTTP-transport | **partial** | Willys använder versionerad separat API-host (`/axfood/rest/v1/...`); Hemköp använder webbplatsens BFF med blandade `/axfood/rest/...`, `/c/...` och `/search/...`. |
| Butiksaktivering | **partial** | Samma CSRF-/sessionsidé och närliggande parametrar, men olika host/path/version. Separat Hemköp-adapter krävs. |
| Store discovery | **partial** | Liknande store schema, annan route och Hemköp-specifika leveransfält. |
| Kategoriträd | **strong partial** | Samma `id/url/children`-modell; Hemköp skickar explicit `storeId`. |
| Pagination | **reusable core** | Samma nollbaserade `page`, `size`, `numberOfPages`, `totalNumberOfResults`; fail-closed validator bör delas endast om schemat bevisas identiskt i fixtures. |
| Product parser | **strong partial** | Samma centrala `code`, pris-, jämförpris-, paket- och basketfält; separata fixtures/fingerprint behövs. |
| Price parser | **strong partial** | Samma grundfält, men Hemköps e-handels-/butikskontext måste bevaras separat. |
| Promotion parser | **strong partial** | `campaignType`, `qualifyingCount`, loyalty och mix-and-match är närliggande. Kedjespecifika avvikelser ska stanna lokalt. |
| Package resolver | **reusable shared core** | Shared `PurchaseQuantityResolver` och invariants ska användas utan Hemköp-specialfall. |
| Raw/replay/snapshot/API | **reusable shared core** | Befintlig operational contract ska återanvändas oförändrad. |

Om gemensam Axfood-logik extraheras ska den ligga under ett litet delat lager
med regressionstester för båda kedjorna. `connectors/hemkop/` ska fortsatt vara
en separat adapter; `HemkopConnector = WillysConnector` är inte korrekt.

## Source policy, robots och requestbudget

Aktuell `robots.txt` svarade HTTP 200 och innehöll:

```text
User-agent: *
Disallow: /kassa/
Disallow: /varukorg
Disallow: /mina-sidor/
Disallow: /min-order/
Disallow: /o/
Disallow: /*?sort=
Disallow: /*?q=
Disallow: /dev-info
Disallow: /beta/
Crawl-delay: 10
Visit-time: 0400-0845
Sitemap: https://www.hemkop.se/sitemap.xml
```

Hemköps e-handelsvillkor var märkta uppdaterade 2026-06-17. Avsnittet om
immateriella rättigheter anger i sak att webbplatsen och innehållet är för
personligt bruk och att annat användande kräver Hemköps tillåtelse. Detta är en
viktig policy-/avtalsrisk och inte ett tekniskt accesshinder.

Projektets klassificering är därför:

```text
technical access: public, no challenge observed
source policy: REVIEW
full crawl default: disabled
operator opt-in: required
```

Implementationen använder `HEMKOP_ALLOW_FULL_CRAWL=false` som default. Registry,
store discovery och canary skapar alltid en inert en-kategori/en-sida-transport,
även om processmiljön råkar innehålla en full-crawl-flagga. Endast den explicita
CLI collection-fabriken får skapa full transport, och då krävs både
`HEMKOP_ALLOW_FULL_CRAWL=true` och en icke-tom exakt
`HEMKOP_STORE_EXTERNAL_IDS`-allowlist. Standardbudgeten är minst tio sekunder
mellan requests (`<=0.1 req/s`),
concurrency 1 och angivet `Visit-time`, om inte ansvarig beslutar om en ännu
striktare budget. `429` ska respektera `Retry-After`. `401`, `403`, CAPTCHA,
WAF/Human Verification eller oväntad login ska sätta `SourcePolicy.BLOCK` för
körningen och stoppa utan retry-loop eller bypass.

`REVIEW` betyder inte att användningen är juridiskt godkänd. Det betyder endast
att projektets nya policy tillåter en teknisk körning efter ett explicit,
loggat operator-/policybeslut.

## Lund-contexts: separat promotion och fail-close

Karhögstorg (`4123`) är en officiellt upptäckt fysisk butik med verifierad
onlinekapacitet, exakt activation/readback och en
`EXACT_STORE_ONLINE_CONTEXT`-länk.

### Historisk duplicate: root cause och säker policy

Kandidat `f0c46d421d514757912c1883cdecde0b` avvisades först korrekt fail-closed.
Den sparade rådatans exakta rotorsak var:

| Fält | Verifierat värde |
| --- | --- |
| Kategori | `godis-snacks-och-glass` |
| Produkt | `101882749_ST`, Cream Cheese & Rödlök Chips, Redhead 150 g |
| Pris / jämförpris | 32,13 kr / 214,20 kr/kg |
| Första förekomst | sida 5, index 82; raw row `e968011e2db84f43b30e5788eaeb3767` |
| Andra förekomst | sida 6, index 0; raw row `705c8c18e89d4a259b4022a46bffcc0c` |
| Första payload | `20260823T150829835157Z_0039_catalog_page_7c85bd80.json`, SHA-256 `23d9a99f864544cd68757ecfb8c792ca1160a023842a1f82bb06b86a1884158d` |
| Andra payload | `20260823T150839866402Z_0040_catalog_page_ee6f4095.json`, SHA-256 `c69e70ef5eeaa9b93bca5f9116cb6c21e59981550b33140a4cfd4d3a7b450994` |
| Skillnader mellan köpraderna | 0 |
| Klassificering | `EXACT_ROW_DUPLICATE` + `PAGINATION_OVERLAP` |

Raderna hade samma produkt-ID, pris, jämförpris, paket, promotioner,
`online=true` och `outOfStock=false`. Motsvarande full-row-repeat syntes även i
30-raderskörningen från sida 19 index 13 till sida 20 index 0. Detta var varken
`VARIANT_COLLISION` eller `SOURCE_ID_COLLISION`.

Dedup-policyn är avsiktligt smal: samma externa produkt-ID får bara räknas en
gång när pris, ordinarie pris, paketmetadata, promotionssemantik och availability
är identiska. Den borttagna raden loggas som anomali och pagination-overlap.
Minsta konflikt i något av dessa köpsemantiska fält gör kandidaten fortsatt
`REJECTED`/`BROKEN` och stoppar promotion.

Offline reconstruction `0ab1769e92c94243a379509b4517d3df` replayade hela den
sparade kandidaten med **0 nätanrop**: 20/20 kategorier, 78/78 sidor, 6 766 råa
rader, 6 068 unika/prissatta produkter, 697 förklarade cross-category-overlap,
exakt 1 borttagen identisk within-category-rad, 1 pagination-overlap och 0
konflikter/quarantine. Den historiska source-kandidaten förblev avvisad;
Brunnshögs LKG ändrades inte.

### Ny ren Karhögstorg-crawl 2026-08-24

Först efter att offline replay passerat kördes en ny full traversal. Den behövde
inte deduplicera någon within-category-rad och promoterades separat:

| Mätvärde | Resultat |
| --- | ---: |
| Source-snapshot | `2d669d3dd375462fbb5fb8cf5a5ec934` |
| Kategorier / sidor | 20/20 / 78/78 |
| Deklarerade / råa / unika produkter | 6 797 / 6 797 / 6 092 |
| Cross-category-overlap | 705 |
| Within / conflict / pagination-overlap | 0 / 0 / 0 |
| Pris / ordinarie pris / availability | 100 % / 100 % / 100 % |
| Package quantity | 5 963/6 092, 97,88 % |
| Löst purchase model | 5 978/6 092, 98,13 % |
| Recipe-relevant package / model | 99,47 % / 99,69 % |
| Promotioner | 1 222: 188 sale, 94 member, 940 multibuy |
| Member-only / explicit max quantity | 121 / 4 |
| Requests / HTTP-fel / 429 | 83 / 0 / 0 |
| Sanerade raw-dokument | 82 / 15 550 968 byte |
| Recipe coverage ≥1 / ≥3 / ≥5 | 48/48 / 46/48 / 34/48 |
| Representative basket | 13/13, complete |
| Offline replay | `1398f77ad6654c668375122b9adae178`, 0 nätanrop, 6 092 produkter |

Source-snapshoten är `PROMOTED`, aktiv och `HEALTHY`; contextlänken är exakt,
`full_online_catalog`, `online_store` och `basket_eligible=true`. Replay-
snapshoten är verifierad `HEALTHY` evidens men inaktiv, så den konkurrerar inte
med den aktiva source-snapshoten.

Brunnshög (`4224`) verifierades separat med 5 642 deklarerade/råa rader,
5 086 unika ID:n, 556 förklarade cross-category-overlap och noll
within-category-dubbletter över 67/67 sidor. Samtliga 5 086 produkter hade
pris och availability; package quantity täckte 5 009 produkter (98,49 %) och
purchase model löstes för 98,55 %. Katalogen innehöll 995 promotioner: 186
sale, 78 member och 731 multibuy; 87 var member-only och 10 bar explicit
maximum quantity. Recipe-relevant package/model coverage var 99,67/99,77 %.

Liveinsamlingen gjorde 72 requests med noll HTTP-fel och noll 429, och sparade
71 sanerade raw-dokument / 12 757 212 byte. Offline replay
`d0706e17b6b5421d8dc6c7dcabf72b63` gjorde noll nätanrop och reproducerade
alla 5 086 produkter. Source-snapshot
`a579353ef6844296a03d75b69fedbf53` är separat promoterad, aktiv och
`HEALTHY`. Recipe benchmark gav ≥1/≥3/≥5 kandidater för 48/43/30 av 48
ingredienser och den representativa korgen var komplett 13/13. Brunnshögs
butiksspecifika kollapsgrind är 4 500 produkter; den är bara ett absolut
ras-skydd och ersätter inte exact completion-kontraktet.

### Karhögstorg jämfört med Brunnshög

Den nätfria jämförelsen använde stabilt externt produkt-ID. Standardkatalogen
har 0 GTIN, men alla join-ID:n var unika och inga matchningar var ambigua:

| Mätvärde | Resultat |
| --- | ---: |
| Karhögstorg / Brunnshög produkter | 6 092 / 5 086 |
| Gemensamma produkter | 4 169 |
| Samma pris | 4 017, 96,35 % |
| Olika pris | 152, 3,65 % |
| Samma / olika promotionssemantik | 3 864 (92,68 %) / 305 (7,32 %) |
| Endast Karhögstorg / endast Brunnshög | 1 923 / 917 |

Absolut prisdifferens för de 4 169 gemensamma var: 0 kr för 4 017 produkter,
`(0; 0,50]` för 8, `(0,50; 1]` för 86, `(1; 5]` för 51 och över 5 kr för 7.
Exempel är Propplösare 89/99 kr, färsk potatis 17,95/24,95 kr, Mollbergs
mörkrost bönor 86,15/91,80 kr och bifftomat 61,95/56,95 kr (Karhögstorg först).
`88an` hade samma baspris 54,84 kr men Brunnshög hade sale 42,95 kr, vilket
visar varför promotionssemantik jämförs separat. Observationerna ligger cirka
14,5 timmar isär; resultatet är diagnostik för både context och tid och ska inte
tolkas som en ren kausal butikseffekt.

## Coveragebedömning

### Nuvarande: `FULL_ONLINE_CATALOG`

Verifierat för Malmö Triangeln `4247`:

- explicit `REVIEW`-opt-in, allowlist och sanerat audit trail,
- aktiv butik/readback plus exakt store-facet på varje katalogsida,
- 20/20 source-partitioner och 113/113 sidor,
- 10 016 deklarerade/råa rader, 9 002 unika produkter,
- 1 014 semantiskt identiska cross-category-overlap och 0 within-category-
  dubbletter,
- 9 002/9 002 produkter med pris,
- 8 793/9 002 med package quantity,
- 159 med okänd purchase model,
- 1 422 promotions,
- 118 requests, 0 HTTP-fel och 0 × 429,
- 117 sanerade raw-dokument, 22 812 892 byte,
- full offline replay med samma 9 002 produkter och noll nät/browser,
- schema-break, context-break, incomplete traversal och LKG fail-closed,
- atomiskt promoterad och aktiv replay-snapshot.

Verifierat separat för Lund Brunnshög `4224`:

- explicit `REVIEW`-opt-in och exakt one-store allowlist,
- aktiv butik/readback plus exakt store-facet på varje katalogsida,
- 20/20 source-partitioner och 67/67 sidor,
- 5 642 deklarerade/råa rader, 5 086 unika produkter,
- 556 semantiskt identiska cross-category-overlap och 0 within-category-
  dubbletter,
- 5 086/5 086 produkter med pris och availability,
- 5 009/5 086 med package quantity och 98,55 % löst purchase model,
- 995 promotions,
- 72 requests, 0 HTTP-fel och 0 × 429,
- 71 sanerade raw-dokument, 12 757 212 byte,
- full offline replay med samma 5 086 produkter och noll nät,
- 13/13 representative basket,
- atomiskt promoterad, aktiv och `HEALTHY` source-snapshot.

Verifierat separat för Lund Karhögstorg `4123`:

- explicit `REVIEW`-opt-in och exakt one-store allowlist,
- aktiv butik/readback plus exakt store-facet på varje katalogsida,
- 20/20 source-partitioner och 78/78 sidor,
- 6 797 deklarerade/råa rader, 6 092 unika produkter,
- 705 förklarade cross-category-overlap och 0 within-category-dubbletter eller
  konflikter,
- 6 092/6 092 produkter med pris, ordinarie pris och availability,
- 5 963/6 092 med package quantity och 98,13 % löst purchase model,
- 1 222 promotions,
- 83 requests, 0 HTTP-fel och 0 × 429,
- 82 sanerade raw-dokument, 15 550 968 byte,
- full offline replay med samma 6 092 produkter och noll nät,
- 13/13 representative basket,
- atomiskt promoterad, aktiv och `HEALTHY` source-snapshot.

Katalogkorten gav ingen GTIN: GTIN-coverage är sanningsenligt 0 % i denna
standardinsamling. En bounded produktdetalj kan ge EAN, men en 9 002-sidors
detaljcrawl ingår inte i fullkatalogkontraktet.

Det äldre stickprovet som inte såg prisvariation är bevarad historik. Den större
2026-08-24-jämförelsen fann 152 olika current prices bland 4 169 gemensamma
produkter och 305 skillnader i promotionssemantik. Det ändrar inte coverage:
varje pris är bundet till den exakt aktiverade online-store-kontexten och påstås
inte vara fysiskt hyllpris.

## Kända begränsningar och risker

- Storefront-routarna saknar externt versionslöfte.
- Villkor och robots kräver `REVIEW` och explicit operatörsbeslut.
- Oaktiverad session använder en icke-lokal standardbutik.
- Kategoriantal skiljer sig kraftigt mellan aktiverade butiker.
- GTIN kräver produktdetalj; standardkatalogens GTIN-coverage är 0 %.
- Paketstorlek ligger ofta i mänsklig text och kräver fail-closed parser.
- `outOfStock` är onlinekontext, inte verifierad fysisk hyllstatus.
- Sökparametern `?q=` ska inte användas för full traversal.
- Full coverage är verifierad separat för `4247`, `4224` och `4123`; andra butiker måste
  få egna kompletta snapshots innan de kan påstå samma store-level coverage.
- Identiska pagination-overlap får endast dedupliceras under det strikta
  köpsemantiska likhetskontraktet. ID-, pris-, paket-, promotion- eller
  availability-konflikt ska fortsatt stoppa traversalen fail-closed.

## Connector-canary och operativa kommandon

Canaryn är alltid bounded och behöver ingen full-crawl-authority:

```powershell
python -m grocery_data canary hemkop --city Lund
python -m grocery_data canary hemkop --city Malmö
```

Den ska:

1. läsa och logga `SourcePolicy.REVIEW` samt operator-opt-in,
2. hämta store discovery och finna vald Lund-/Malmö-butik,
3. aktivera butiken i en ny anonym session och verifiera `/store/active`,
4. hämta kategoriträdet och exakt en förstakategori/produktsida med högst fem
   rader,
5. verifiera store-facet, `currentPage`, `numberOfPages`, total och att
   completion sanningsenligt är `limited`,
6. kräva ett plausibelt resultat över noll med parsade priser,
7. spara sanerad raw response och schemafingerprint,
8. aldrig spara CSRF, Cookie, auth-header eller personlig data,
9. stoppa omedelbart vid access challenge eller trasig pagination.

Canaryn garanterar inte att just de första fem raderna innehåller viktvara,
promotion eller alla purchase models. De semantiska fallen täcks separat av
golden fixtures och den fulla offline-acceptance-sviten.

Golden fixtures bör minst omfatta fast paket, lösvikt, styckvara, variabel
vikt, vätska, avrunnen vikt, kampanj, klubbpris, multipack, saknad EAN och
okänd pakettext.

Full collection är ett separat, explicit `REVIEW`-beslut:

```powershell
$env:HEMKOP_ALLOW_FULL_CRAWL="true"
$env:HEMKOP_STORE_EXTERNAL_IDS="4247"
$env:HEMKOP_REQUESTS_PER_SECOND="0.1"
$env:HEMKOP_MAX_CONCURRENCY="1"
python -m grocery_data collect --chain hemkop --city Malmö --no-promote
```

### Flera Lund-contexts

Lund körs inte som ett enda godtyckligt Hemköp-context. Efter en bounded
officiell store-discovery läser `collect-all --city Lund` de aktiva fysiska
Hemköp-butikerna och deras exakta, source-proven
`EXACT_STORE_ONLINE_CONTEXT`-länkar ur det lokala registret. En fysisk butik
utan sådan online-evidens skapar aldrig ett crawl-target.

Varje tillåten butik körs seriellt med:

- en connector vars audit-allowlist innehåller exakt ett store-ID,
- ett eget scope, exempelvis `lund:hemkop:4123`,
- en egen kandidat/aktiv snapshot och last-known-good,
- felisolering så att ett trasigt context inte stoppar eller deaktiverar ett
  annat Lund-context.

Detta ger inte automatisk crawl-authority. Om flaggan är falsk eller om exakt
store-ID saknas i operatorns allowlist blir contextet `skipped` med noll
nätanrop. Ett allowlistat ID som inte motsvarar en aktiv, exakt officiell
online-länk rapporteras men används aldrig.

```powershell
$env:HEMKOP_ALLOW_FULL_CRAWL="true"
$env:HEMKOP_STORE_EXTERNAL_IDS="4123,4224"
$env:HEMKOP_REQUESTS_PER_SECOND="0.1"
$env:HEMKOP_MAX_CONCURRENCY="1"
python -m grocery_data collect-all --city Lund --no-promote
```

Även när flera ID:n är operator-godkända skapas en separat one-ID-transport
för varje run. Direktkörning kan använda samma säkra path:

```powershell
python -m grocery_data collect --chain hemkop --city Lund `
  --context-store-id 4123 --no-promote
```

Replay använder de fångade store-identiteterna men en inert transport utan
crawl-authority:

```powershell
python -m grocery_data replay `
  --chain hemkop `
  --snapshot-id 4d572317b00049268f8ee1d3b3060c87
```

Den aktiva auktoritativa Malmö-replay-snapshoten är
`00db33803746408796d118c91270fccc`; Lund Brunnshögs aktiva source-snapshot är
`a579353ef6844296a03d75b69fedbf53` och Karhögstorgs aktiva source-snapshot är
`2d669d3dd375462fbb5fb8cf5a5ec934`. En ny livekörning ska alltid lämnas staged
med `--no-promote`, replayas och granskas innan separat promotion.

## Federerad Lund-acceptance 2026-08-24

Båda Hemköp-contexten var färska, promoterade och basketberättigade i såväl
OWN-only som federerad körning. Den federerade providergrinden representerade
Hemköp, ICA och Willys; två exakta ICA-contexts var eligible och övervägdes men
valdes i noll resultatrader. Därför reproducerade federationen exakt samma
Hemköp-/Willys-contexts, recept och priser som OWN-only:

| Scenario | Valda contexts | OWN = federerat | Delta |
| --- | --- | ---: | ---: |
| 13 varor, `max_stores=1` | Willys Lund | 340,30 kr | 0,00 kr |
| 13 varor, `max_stores=2` | Karhögstorg + Willys Lund | 329,30 kr | 0,00 kr |
| 13 varor, `max_stores=3` | Brunnshög + Karhögstorg + Willys Lund | 326,36 kr | 0,00 kr |
| CHEAPEST 5 × 4, `max_stores=1` | Willys Lund | 225,74 kr / 11,29 kr per portion | 0,00 kr |
| CHEAPEST 5 × 4, `max_stores=2` | Karhögstorg + Willys Lund | 194,04 kr / 9,70 kr per portion | 0,00 kr |
| BALANCED 5 × 4, `max_stores=1` | Karhögstorg | 270,87 kr / 13,54 kr per portion | 0,00 kr |
| BALANCED 5 × 4, `max_stores=2` | Karhögstorg + Willys Lund | 236,68 kr / 11,83 kr per portion | 0,00 kr |
| VARIED 5 × 4, `max_stores=1` | Karhögstorg | 271,73 kr / 13,59 kr per portion | 0,00 kr |
| VARIED 5 × 4, `max_stores=2` | Karhögstorg + Willys Lund | 238,72 kr / 11,94 kr per portion | 0,00 kr |

Frozen-cachen innehöll 1 863 produkter för exakt två ICA-contexts. Den samlades
med 49 requests (1 resolve + 48 produkt), 49 × HTTP 200, 0 denied/retry och
48/48 icke-tomma frågor; SHA-256 är
`399944820a33a875ad7b15a5bbf676c64400b1d223537602b92ccf9c0a51d508` och
kandidatdatabasen var oförändrad. Hela socket-blockerade acceptansmatrisen
passerade på 1 063,0382 sekunder med 0 nätförsök och oförändrad immutable
databas. Basket-, nutrition-, diversity-, reconciliation- och provenance-
audits passerade; inga member-only- eller fallbackrader användes. Coop och Lidl
var förklarade men ej eligible, och City Gross var `NO_LUND_CONTEXT`.

## Nuvarande beslut

```text
PUBLIC SOURCE POTENTIAL: FULL_ONLINE_CATALOG
SAFELY VERIFIED COVERAGE: FULL_ONLINE_CATALOG (Malmö Triangeln 4247; Lund Brunnshög 4224; Lund Karhögstorg 4123)
SOURCE POLICY: REVIEW
IMPLEMENTED CONNECTOR: YES
ACTIVE SNAPSHOTS: 00db33803746408796d118c91270fccc; a579353ef6844296a03d75b69fedbf53; 2d669d3dd375462fbb5fb8cf5a5ec934 (PROMOTED/HEALTHY)
FULL BASKET SOURCE: YES, per active verified context, including both Lund stores 4224 and 4123
```
