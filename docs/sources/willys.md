# Willys — source discovery

Senast verifierad: **2026-08-23**  
Kedja: **Willys**  
Rekommenderad `CoverageLevel`: **`FULL_CATALOG` för onlinebutiker**  
Discovery confidence: **hög** för de verifierade publika frontendkällorna nedan.

## Sammanfattning

Willys officiella Next.js-frontend använder ett publikt Axfood-API med ett
sessionsbundet butiksval. Store locator, kategoriträd, paginerade kategorisidor,
sökning och produktdetaljer verifierades direkt. En komplett butikskatalog kan
byggas genom att traversera kategoriträdets lövnoder och deduplicera produktkod.

Butiksaktivering använder den publika frontendens CSRF-flöde. Tokenen är
kortlivad och hålls endast i HTTP-klientens minne; den sparas aldrig i raw data,
metadata, loggar eller fixtures. Ingen login, CAPTCHA, åtkomstkontroll eller
anti-botmekanism kringgicks.

## Full Lund-verifiering

Den aktiva, komplett rate-limitade Lund-körningen 2026-08-23 traverserade de
två katalogberättigade onlinebutikerna och gav 18 434 butik-produktrader:

| Butik | Produkter | Katalogsidor | Recipe coverage ≥1/≥3/≥5 |
| --- | ---: | ---: | ---: |
| Willys Lund `2176` | 10 069 | 653 | 48/48 / 47/48 / 39/48 |
| Willys Lund Nova `2354` | 8 365 | 585 | 48/48 / 45/48 / 39/48 |

Source-snapshot `65a83015146d4c7d989ad6e58210b147` är aktiv och
`PROMOTED`. Snapshot `9981f09460924fda8a138d3554467d28` replayade samma
18 434 produkter helt offline med noll nätanrop. Completion-, parser-,
freshness- och quality-grindarna passerade. Den tredje upptäckta Lund-butiken,
Willys Hemma Stortorget `2863`, saknar fortfarande verifierad full
onlinekatalog och fabriceras inte som basket-context.

## Coverage

| Egenskap | Coverage | Kommentar |
|---|---|---|
| Store discovery | Ja | Publik fullständig butikslista |
| Lund/Malmö | Ja | Filtreras från officiell lista med externa `storeId` |
| Full butikskatalog | Ja, onlinebutiker | Kategoriträd + alla paginerade lövkategorier |
| Lokal butikskontext | Ja | Publik frontendaktivering per session |
| Produkt-ID | Ja | `code`, ofta med `_ST`/`_KG` suffix |
| GTIN/EAN | Ja på detaljnivå | `ean`; enrichment kräver produktdetaljanrop |
| Pris/jämförpris | Ja | Separata fält; jämförpris är aldrig paketstorlek |
| Fast paket | Ja | `productLine2`, pris/st och basket metadata |
| Lösvikt | Ja | `priceUnit=kr/kg`, `productBasketType.code=VIKT` |
| Variabelt viktpaket | Ja | kg-pris + ST-korg + `averageWeight`/`ca:` |
| Medlemspris | Ja | `campaignType=LOYALTY`; hålls villkorat |
| Multipack | Ja | `qualifyingCount` + grupppris; plattas inte ut |
| Kampanjperiod | Ja för inspekterade kampanjer | `validUntil`; startdatum inte alltid synligt |
| Lagerstatus | Delvis | `outOfStock`; inte en garanti om fysisk hyllstatus |
| Historik | Nej från källan | Byggs av våra tidsstämplade observationer |

Coverage ska degraderas till `PARTIAL_CATALOG` om en butik inte kan aktiveras
som online-/plockbutik eller om full kategoritraversering inte valideras.

## Officiella källor

- Webbplats: <https://www.willys.se/>
- Publik runtime-konfiguration: <https://www.willys.se/api/config>
- Butikssök: <https://www.willys.se/butik>
- Varusök: <https://www.willys.se/sok?q=pasta>

Runtime-konfigurationen pekade vid verifieringen på:

```text
https://www.willys.prod.axcsfprod.aws.axfoodapp.cloud
```

Detta hostnamn är ett upptäckt frontendkontrakt, inte ett utlovat externt API,
och ska därför canary-testas och versionsövervakas.

## Store discovery

```text
GET /axfood/rest/v1/store
```

Responsen är en JSON-lista. Viktiga fält:

- `storeId`
- `name`
- `onlineStore`
- `address.line1`
- `address.postalCode`
- `address.town`
- koordinater när de finns

Verifierade Lund-ID:n inkluderade `2176`, `2354` (Willys Lund Nova) och
`2863`. Seed-ID:n får användas i canary, men normal discovery filtrerar alltid
den aktuella officiella listan och deduplicerar på `willys + storeId`.

## Store context

Den officiella frontendens publika flöde är:

```text
GET  /axfood/rest/v1/csrf-token
POST /axfood/rest/v1/store/activate
     ?storeId={id}
     &activelySelected=true
     &forceAsPickingStore=true
GET  /axfood/rest/v1/store/active
```

CSRF-värdet skickas som `X-CSRF-Token` och sparas inte. En connector ska
faila tydligt om aktivering inte fungerar; den får inte låtsas att priser är
butikslokala.

## Catalog and pagination

```text
GET /axfood/rest/v1/leftMenu/categorytree
GET /axfood/rest/v1/c/{leaf-category-path}?page={zero_based}&size={size}
```

Kategoriresponsen innehåller `results`, `pagination`, `categoryInfo`,
`categoryBreadcrumbs` och `superCategories`. I den verifierade liveformen ligger
kategorikontexten på själva katalogsidan, inte på varje produktpost:
`superCategories` är ordnad från den syntetiska roten `N00` (`Alla varor`) till
föräldern och `categoryInfo` är lövet. Parsern tar bort `N00`, deduplicerar namn
och ger exempelvis `Skafferi > Pasta, ris & matgryn > Ris`.
`pagination.currentPage` och `pagination.numberOfPages` styr fortsättningen.
Produkten dedupliceras på `code`, eftersom samma produkt kan förekomma i fler än
en kategori.

Sökning finns också:

```text
GET /axfood/rest/v1/search?q={query}&page={page}&size={size}
```

Sökning är bra för canary och användarsökning men ska inte likställas med full
katalog. Full coverage kräver kategoritraversering.

## Product detail and important fields

```text
GET /axfood/rest/v1/p/{code}
```

Verifierade fält:

- `code`, `ean`, `name`, `manufacturer`
- `priceValue`, `priceUnit`
- `comparePrice`, `comparePriceUnit`
- `productLine2`
- `averageWeight`, `incrementValue`
- `productBasketType.code`
- `outOfStock`
- `potentialPromotions`
- sidnivåkategori via `superCategories`, `categoryInfo` och
  `categoryBreadcrumbs` (produktdetaljer kan ha `breadcrumbs`)

Listvyerna saknade EAN i vissa stickprov medan detaljvyn innehöll den. Full
GTIN-enrichment innebär därför extra requests och ska vara konfigurerbar.

## Price and purchase semantics

Verifierade exempel:

- Fusilli 500 g: pris/st, fast paket, separat jämförpris/kg.
- Potatis: pris/kg och `productBasketType=VIKT`, alltså fraktionell lösvikt.
- Kycklingfilé ca 850 g: pris/kg men köps som en ungefärlig ST-förpackning,
  alltså `VARIABLE_WEIGHT_PACKAGE`.
- Paprika mix 400 g: pris/st, alltså fast paket trots produktkategori frukt/grönt.

Explicit invariant: `comparePrice=49.90` och `comparePriceUnit=kr/kg` får aldrig
skapa ett paket om 1 kg. Om pris-/basket-/paketevidens inte räcker blir
`sale_model=UNKNOWN` och raden får inte användas som verifierad exakt checkout.

## Promotions

`potentialPromotions` innehöll två viktiga strukturer:

- medlemspris: `campaignType=LOYALTY`, promotion price, villkor och maxantal;
- multipack: `qualifyingCount`, `rewardLabel` (grupppris), `realMixAndMatch` och
  `validUntil`.

Exempelvis "3 för 32 kr" bevaras som quantity `3` och grupppris `32`. Källans
eventuella beräknade `10.666...` får inte bli ett ovillkorligt styckpris.

## Request policy

- Metod: publik HTTPS/JSON som den officiella frontendens egen klient använder.
- Auth: ingen login; sessionsbundet publikt butiksval.
- Standard rate: 1 request/sekund, konfigurerbar konservativt.
- Retries: begränsade, exponentiell backoff, `Retry-After` respekteras.
- User-Agent: stabilt identifierbar, ingen rotation eller maskering.
- Daily ingestion: en gång per dygn är tillräckligt.

## Golden fixtures and repair signals

Sanerade responseutdrag finns under
`grocery_data/app/connectors/willys/fixtures/` för fast paket, lösvikt,
styckvara, variabel vikt, medlemspris, multipack, saknad GTIN och schemaändring.

Högvärdiga health-signaler:

- `/store` eller `/categorytree` är inte längre JSON/200;
- kategoriantal eller produktantal faller kraftigt;
- `results`/`pagination` flyttas eller ändrar typ;
- `priceValue`, `priceUnit` eller `productLine2` byter namn/typ;
- andelen okänd försäljningsmodell eller saknade priser ökar;
- butiksaktiveringen bekräftar inte vald butik.

## Known limitations

- API:t är frontendinternt och kan ändras utan versionsgaranti.
- Full katalog har endast bevisats för aktiverbar onlinebutik.
- EAN-enrichment per produkt är request-tungt.
- `outOfStock` är inte säker realtidsstatus i fysisk butik.
- Kampanjernas startdatum var inte konsekvent tillgängligt i stickproven.
- Villkors-/robotsgranskning ska göras innan bred kontinuerlig produktion; PoC:n
  använder konservativ takt och en liten opt-in-canary.
