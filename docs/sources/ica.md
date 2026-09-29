## Områdeserbjudanden 16 september 2026 – inaktiv utvärdering

[Inventering, nätbevis, täckning och blockerare](../../reports/ica-area-20260916/README.md). Ny manuell CLI `python -m grocery_data.scripts.collect_ica_area_offers --city Lund --output <ny-katalog>` återanvänder officiell discovery, connector och collector med separat offers_only-scope per butik. Befintlig adressortsgräns används utan postnummerlikhet. Malmö fungerar med samma områdesparameter. Parser v6 bevarar kampanjvillkor, karantänsätter oklar pant/dagsgiltighet och behåller paket även utan ordinarie pris. Opt-in ICA-provider kräver samma parser, exakt ensam variant och paket; Primat/defaultkällor ändras inte. Reklambladens sidor finns bevarade men bildbaserad kampanjextraktion är ännu ofullständig. Se [releaseförslaget](../../reports/ica-area-20260916/RELEASE.md) före eventuell aktivering. Ingen baspriskatalogretry eller produktionsaktivering gjordes.

## Uppföljning 15 september 2026

[Gunnesbos aktuella browserprisbevis, Primat-jämförelse och Clemenstorgets källbegränsning](../../reports/ica-gunnesbo-clemenstorget-20260915.md). 50 publika SSR-köppriser återverifierade via normal anonym Gunnesbo-webbläsare; 232 sök-ID:n betyder inte 232 hämtade prisposter. Den isolerade projektionen återanvänder onlineparsern och är inte registrerad för drift. Vanlig HTTP nekas på sökdokumentet, medan normalt browserflöde fungerar. Ingen automatiserad prisinsamling eller flerdagarsacceptans är ännu belagd. Primat och aktiva källor är oförändrade. Clemenstorget saknar verifierad egen baspriskatalog via de angivna officiella vägarna; Caroli/Mobilia ersätter den inte.

# ICA source discovery

Last verified: **2026-09-14**

## Direct-source replacement evaluation (2026-09-14)

[Current evaluation](../../reports/ica-direct-evaluation-20260914.md) keeps Primat
active and the six existing beta contexts unchanged. Public store offers worked
both locally and in the actual scheduler user/environment: Gunnesbo 138 groups,
Clemenstorget 73, zero parser failures. These are offer groups, not complete
catalogues or automatically qualified baseline prices.

The official full Lund locator confirms Gunnesbo BMS/web ID `17883`, account
`1088004`, with exact online URL `/stores/1088004`; Clemenstorget BMS/web ID `2771`,
account `1004409`, has no online URL. Clemenstorget's online region mapping remains
unverified. Repeated historical `/stores/1004409/api/...` attempts returning 403 do
not verify that mapping. The isolated diagnostic now requires the exact official
online URL before an API probe and skips Clemenstorget without it.

Gunnesbo's verified historical v6 search route returned 403/HTML from local Windows
and the actual scheduler runtime. No retry, continuation or decoration followed.
No browser was available through the current CUA environment for new passive
capture. The historical Fäladstorget `collect` reference had no retained request or
response body in the reviewed material and remains unclassified.

There are zero qualified complete direct-catalogue runs across multiple scheduled
calendar days. No candidate, source strategy or PriceUniverse was activated.
The older observations below remain historical evidence and do not refresh prices.

## Current authoritative contract (2026-08-26)

The old catalogue experiment described later in this document is retained as
historical diagnostics. It is **not** the authoritative request contract for the
current ICA frontend. A fresh, ordinary public-browser observation established a
newer v6 flow and an exact Gunnesbo online context, but the run then reached an
access-challenge stop before continuation and decoration could be replayed live.

Current safe classification:

| Scope | OWN discovery coverage | Production basket source |
| --- | --- | --- |
| Gunnesbo region `92198f17-b02f-4fae-ad41-228bcc725420` | `PARTIAL_CATALOG` | Primat/licensed |
| Other Lund ICA contexts | Not reclassified without exact context evidence | Existing per-context strategy |
| ICA offers | `OFFERS_ONLY` | OWN offers |

No ICA OWN full snapshot was promoted, no active PriceUniverse was changed, and
meal generation still makes zero ICA network calls. The context-aware resolver can
accept an exact verified OWN override later, but the active ICA default remains
Primat and fallback remains explicit.

### Strict ephemeral-browser transport attempt

A production-shaped browser transport now exists behind a small common collection
interface shared with the HTTP transport. It starts a new anonymous Playwright
Chromium context for one exact allowlisted region, activates the ordinary public
store route, and uses only the same-origin JSON resources used by the storefront.
It has no persistent profile or storage state and sets no proxy, custom headers,
user agent, locale, browser channel, executable override, stealth script or
fingerprint override. Cookies and browser storage are neither read nor serialized.
The page, context, browser and Playwright runtime are closed after capture.

The separately authorized category proof has a narrower transport contract than a
general browser API client. It must navigate an explicit public ICA category UI route
and observe requests emitted by ICA's own frontend. It must **not** construct a
`product-pages` or `/products` request with `page.evaluate`, injected `fetch`, copied
headers, or copied cookies. For an allowlisted catalogue response it may retain only
the request method and sanitized URL, an observed `/products` JSON UUID array needed
for replay lineage, the response status/content type, and sanitized public JSON.
Request headers, response headers beyond content type, cookies, storage state, and
other runtime/session state are outside the capture boundary and are never inspected.

The frontend's observed `/products` UUID-array length is the category proof's batch
size evidence. `ICA_PRODUCT_BATCH_SIZE` is therefore not an input to category proof.
That setting remains mandatory for a later explicit full crawl, after the ordinary
frontend behavior has actually established a safe value.

The transport diagnosis distinguishes the two request origins. The discarded path
used the correct Gunnesbo URL, `PUT` method and JSON UUID-array body, and the browser
could supply ordinary same-origin `Origin`/`Referer`; however, it directly called
`fetch` with only `Content-Type` and neither established nor verified ICA's current
VISITOR request wrapper, application request-source metadata, CSRF value or page
runtime identity. The replacement path never fabricates those values and never
reads them. ICA's own page JavaScript must issue the request from its current
ephemeral anonymous context; the collector observes only its public response and
the minimum UUID-array lineage needed for replay.

The earlier **HTTP 405** was produced by a hand-constructed browser `fetch` that did
not prove ICA's own anonymous frontend runtime had initialized. It is therefore no
longer used as evidence that normal Chromium cannot access the catalogue.

On **2026-08-26**, the replacement transport made one bounded run in a fresh,
headed, anonymous Playwright Chromium context. It navigated the exact verified
Gunnesbo Mejeri/Ost UI route, registered observers before navigation, and made no
synthetic API request. During initial storefront/runtime initialization, a relevant
response was HTTP 200 `text/html` and was classified by the strict challenge
markers before any sanitizable `product-pages` or `/products` JSON response was
captured. The browser, context, page and Playwright runtime were then closed. The
saved partial evidence contains one sanitized transport-stop document only:

```json
{
  "classification": "access_challenge",
  "http_status": 200,
  "observed_content_type": "text/html",
  "schema": "ica-online-transport-stop-v1"
}
```

There was no retry, alternate browser mode, modified fingerprint/header, copied
cookie/session, CAPTCHA handling or challenge bypass. Because the public UI itself
did not establish a capturable normal catalogue runtime in this fresh context, the
frontend's effective `/products` batch size remains unobserved and is not guessed.

This stop is decisive for the current milestone:

- the one-category proof stopped before its first JSON page and did not reconcile;
- no full Gunnesbo traversal was attempted;
- no other Lund region was probed;
- no ICA snapshot was promoted;
- no PriceUniverse artifact or source strategy changed;
- Gunnesbo remains `PARTIAL_CATALOG` and Primat remains its basket source.

The separately gated category-proof path is retained for a future operator-reviewed
run if the ordinary public runtime becomes accessible. It writes only sanitized raw,
closes the browser before replay, reconciles continuation and batch lineage entirely
offline, and always reports `promotable=false`:

```powershell
$env:ICA_ALLOW_BROWSER_CATEGORY_PROOF = "true"
$env:ICA_ONLINE_CONTEXT_IDS = "92198f17-b02f-4fae-ad41-228bcc725420"
py -3.12 -m grocery_data ica-category-proof `
  --city Lund `
  --store 92198f17-b02f-4fae-ad41-228bcc725420 `
  --category-id ea243faf-2eca-47d7-af07-1dc61dd7693a `
  --ica-transport browser
```

The command derives the actual UUID-array size from ICA's frontend request and must
not be given an assumed batch size. Full collection remains a different authority
(`ICA_ALLOW_FULL_CRAWL=true`) and still requires setting `ICA_PRODUCT_BATCH_SIZE` to
the verified observation. It is unavailable until the one-category proof and all
existing quality gates pass.

### Exact context readback

Normal store selection opened `/stores/1088004`. The public SSR bootstrap safely
proved this allowlisted relation:

```text
retailerRegionId = 1088004
regionId         = 92198f17-b02f-4fae-ad41-228bcc725420
regionName       = Maxi ICA Stormarknad Gunnesbo Lund
```

`regionId` is modelled as an ICA online price-context identity, not assumed to be a
physical-store ID. `PhysicalStore` and `GroceryContext` remain separate. The full
bootstrap is never retained: it contains ephemeral visitor/session/request tracking
fields. Only the two verified public identities and an allowlisted category tree may
enter replay raw data. Cookies and an anonymous in-memory HTTP cookie jar, if ever
required by the public flow, are discarded after one run and are never serialized.

### Verified current endpoints and shapes

The first anonymous Gunnesbo request succeeded with HTTP 200 and JSON:

```text
GET /stores/1088004/api/webproductpagews/v6/product-pages/search
    ?includeAdditionalPageInfo=true
    &maxPageSize=300
    &maxProductsToDecorate=50
    &q=Mjölk
    &tag=web
```

Top-level keys were `productGroups`, `metadata`, `additionalPageInfo`, and
`missedPromotions` (the current source spells this `missed`, not `missing`). The
result exposed 240 ordered product IDs: 50 inline `decoratedProducts` and 190
`otherProductIds`. A currently observed product retained:

- `productId = f4ec81a4-4fff-4696-92dc-4a3e7bf06c31`;
- `retailerProductId = 2052770`;
- a valid Gunnesbo price of 20.55 SEK;
- `packSizeDescription = 1.5L`;
- a separately nested 13.70 SEK/litre unit price;
- `available = true` and `isInCurrentCatalog = true`.

Prices are observations in the exact online context. They are labelled **ICA
online price**, never verified shelf price. `productId` is the primary source
identity and `retailerProductId` is a secondary ICA identity. No GTIN field was
proved in the catalogue response, so GTIN coverage is reported as zero/unknown and
is never derived from `retailerProductId`.

The public SSR category projection contained 218 category nodes, 25 roots, 193
terminal nodes and 25 non-terminal nodes. The Mejeri root
`ea243faf-2eca-47d7-af07-1dc61dd7693a` had 13 children. The current category request
contract is:

```text
GET /stores/1088004/api/webproductpagews/v6/product-pages
    ?categoryId=<uuid>
    &includeAdditionalPageInfo=true        # first page only
    &maxPageSize=300
    &maxProductsToDecorate=50
    &sortOptionId=favorite
    &tag=web&tag=category-item
```

The observed Mejeri root declared 1,700 products. Its first page exposed 292 raw
group positions and 291 unique IDs (one exact cross-group overlap), consisting of 50
decorated products and 242 undecorated IDs. `metadata.nextPageToken` was present.
The current public JavaScript establishes the continuation request as the same GET
with `pageToken=<previous token>` and without `includeAdditionalPageInfo`; a missing
token terminates traversal. Runtime implementation hashes tokens before raw storage,
tracks every seen token, and fails closed with `PAGINATION_LOOP` if a token repeats.

The browser also showed the current bulk decoration boundary:

```text
PUT /stores/1088004/api/webproductpagews/v6/products
Content-Type: application/json

["<product UUID>", "<product UUID>", ...]
```

The response shape is `products`, `missedPromotions`, and `restrictedGroups`.
Decoration is batched; a one-request-per-product implementation is prohibited. The
exact normal browser batch size was not proved in the completed safe observation, so
a full collector requires an explicit browser-verified `ICA_PRODUCT_BATCH_SIZE`
instead of guessing it.

### Promotion evidence

The current search surface supports `filters=boolean=onOffer` and returns
`missedPromotions` with `promoId`, `retailerPromotionId`, product counters and
`requiredProductQuantity`. The public frontend bundle references promotion resolution
by promotion ID and retailer promotion ID. An explicit rendered promotion example
proved `description = "2 för 59 kr"`, `type = "OFFER"`, and
`requiredProductQuantity = 2`.

Counters alone do not prove total price or membership. The parser therefore keeps
unresolved evidence fail-closed and creates `MULTIBUY`, `MEMBER_PRICE`, validity or
maximum-quantity semantics only when the resolved source explicitly supplies them.
Anonymous/private-customer context is never interpreted as ICA Stammis membership.

### Mandatory stop and what remains unproved

Immediately after the successful JSON search, the next ordinary anonymous API
request returned HTTP 202 with `text/html` challenge content. Collection stopped at
once under the crawler policy. There was no retry with a new identity, no copied
cookie/header, no CAPTCHA handling and no WAF bypass.

Consequently the following remain unproved live in this iteration:

- replacement-token continuation to a terminal category;
- exact reconciliation of one large category;
- a successful current `/products` batch made by the collector;
- full Gunnesbo category-union traversal;
- current promotion-detail resolution;
- Gunnesbo/Burlöv live cross-context control;
- package/purchase-model quality, 48-ingredient coverage and 13/13 basket quality;
- zero-network replay of a complete candidate, and failure/LKG/repair promotion.

The implementation supports strict sanitized raw, deterministic offline parser and
replay contracts, exact context allowlists, bounded canary operation, token-loop and
duplicate conflict rejection, and context-aware source strategy. Full crawl remains
off by default and requires all of:

```text
ICA_ALLOW_FULL_CRAWL=true
ICA_ONLINE_CONTEXT_IDS=92198f17-b02f-4fae-ad41-228bcc725420
ICA_PRODUCT_BATCH_SIZE=<browser-verified size>
concurrency=1
request rate 0.5–1.0/s
```

Any 401, 403, 405, 429, non-JSON response, CAPTCHA or Human Verification aborts the
context run. Until a fresh run completes every acceptance gate, ICA OWN must not be
made basket eligible and must not trigger a PriceUniverse activation.

## Historical assessment (2026-08-21)

## Result

| Area | Result |
| --- | --- |
| Store discovery | Public, structured SSR data on `ica.se` |
| Store-specific catalogue | Initial SSR catalogue works in headed Chromium; continuation is blocked by AWS WAF |
| Store-specific prices | Yes, in the selected online store context |
| Offers | Public store-specific SSR data; collected |
| GTIN/EAN | Available per offer variant; group GTIN only when exactly one variant exists |
| Package metadata | Yes, as source text such as `0.4kg`; parsing is still required |
| Availability | Online-catalogue signal only; not verified as physical shelf stock |
| Coverage level | `OFFERS_ONLY` |

`OFFERS_ONLY` is deliberate. ICA's visual online catalogue is public in a browser,
but a plain collector request receives an AWS WAF challenge. The project does not
execute or bypass that challenge. Official store-specific offer pages are available
as ordinary public HTML with structured SSR data and are the connector's only
operational product surface.

The connector therefore must not be used as a complete-basket ICA catalogue. It may
enrich optimization with the products and conditional promotions that were actually
observed.

## Evidence convention

- **Verified** means observed on an official ICA page or in structured data embedded
  by that page on 2026-08-21.
- **Frontend contract** means the request shape was found in ICA's official current
  JavaScript bundle, but was not replayed as an independent API request.
- **Not verified** means the collector must not rely on the behaviour yet.

No login, CAPTCHA, access-control bypass, copied bearer token, or captured credential
was used.

## Store discovery

### Public source

Verified `GET` pages:

- [Lund stores](https://www.ica.se/butiker/oppettider/lund/)
- [Malmö stores](https://www.ica.se/butiker/oppettider/malmo/)

The implemented connector uses the public online-filtered variants, which fit in one
SSR response and expose an official offers URL per store:

- `/butiker/oppettider/handla-online/lund/` (2 Lund-municipality stores)
- `/butiker/oppettider/handla-online/malmo/` (4 Malmö-municipality stores after
  filtering the 15 regional results by `address.municipality`)

This does not claim complete discovery of physical/offline ICA stores. It is the
correct discovery surface for the connector's store-specific `OFFERS_ONLY` coverage.

Both pages render without login and embed a JavaScript object named
`window.__INITIAL_DATA__`. It is a JavaScript literal rather than strict JSON because
some values can be `undefined`; raw capture should preserve the original page before
any tolerant parsing.

Verified Lund result:

- `resultStore.totalNrOfStores = 12`
- `resultStore.storeCards` contained 12 records
- `resultStore.paginationIndex = 1`
- `SlimStores.slimStores` contained 12 records

Verified Malmö result:

- `resultStore.totalNrOfStores = 69`
- the initial SSR page contained 20 records
- all 20 initial records had `address.municipality = "Malmö"`
- `resultStore.paginationIndex = 1`

The Malmö observation proves that a connector must paginate. It must also retain the
source municipality/urban-area fields and apply the project's Lund/Malmö geographic
policy explicitly rather than relying only on free-text query matching.

Verified `storeCards` fields include:

- `storeName`, `profile`, `phoneNumber`, `emailAddress`
- `storeId` and `accountNumber` (distinct identifier namespaces)
- `services`, `openingHours`, `mdsaFilters`
- `onlineUrl`, `bhsUrl`, `highlightUrls`
- `distanceInMeters`
- `address.street`, `city`, `postalCode`, `municipality`, `urbanArea`, `county`,
  `region`
- `address.coordinates.coordinateX` and `coordinateY`

For example, one Lund record had `storeId = "2771"` and
`accountNumber = "1004409"`. Store deduplication should use the stable ICA identifier
namespace explicitly, not the display name.

### Frontend request contract

The official store page declares this production base URL in `__INITIAL_DATA__`:

```text
https://apim-pub.gw.ica.se/sverige/digx/mdsastoresearch/v1
```

ICA's official current store bundle constructs these calls:

```text
GET /searchbyquery
    ?query={query}
    &take={take}
    &offset={offset}
    &onlyOnline={boolean}
    &onlyOnlineB2B={boolean}

GET /searchbylocation
    ?query={query}
    &take={take}
    &offset={offset}
    &onlyOnline={boolean}
    &onlyOnlineB2B={boolean}
    &maxdistance={metres}

GET /searchbyquery
    ?query=*
    &lon={longitude}
    &lat={latitude}
    &take={take}
    &offset={offset}
    &maxdistance={metres}

GET /stores/search?storeIds={ids}
GET /stores/search?accountNumbers={ids}

POST /ministores/search
{
  "storeIds": ["..."],
  "take": 100,
  "includeBhsUrl": true,
  "includeB2BFlag": true,
  "mustServices": ["Handla online"]
}
```

The bundle obtains an authorization header before these calls. Discovery therefore
did **not** replay the gateway calls independently and did not capture or persist that
header. The supported PoC source is the public SSR page until ICA provides an approved
API contract or the project's legal/security review explicitly approves another
transport.

Official bundle inspected:

```text
https://assets.icanet.se/raw/upload/v1/customer-solutions-apps/mdsa-store-vue3/assets/src-BX8MsYy3.js
```

## Store-specific catalogue and prices

### Ordinary Chromium investigation (2026-08-21)

This investigation used unmodified Playwright Chromium: no stealth plugin, proxy,
fingerprint override, copied credential, CAPTCHA solver, or request-header replay.
Only response method/host/path/status/content type and sanitized JSON structure were
recorded. Cookies, authorization data, and browser storage were neither inspected nor
persisted.

What worked:

- headed Chromium loaded Maxi ICA Stormarknad Gunnesbo (`1088004`) with HTTP 200;
- the page visibly confirmed the selected store and displayed product prices;
- `/search?q=pasta` embedded valid `window.__INITIAL_STATE__` with 50 decorated
  product entities and `totalProducts = 223`;
- `/categories` exposed the official store category tree and product counts;
- a terminal Formpasta category declared 57 products, contained all 57 stable product
  IDs in its product groups, decorated 50 entities in SSR, and had no next cursor;
- a normal browser response exposed the structured same-origin endpoint
  `PUT /stores/{accountNumber}/api/webproductpagews/v6/products`;
- one observed successful JSON response contained product ID, retailer product ID,
  name, brand, package description, price, unit price/unit, availability, promotions
  and category path;
- the same retailer product (`Spirali 500g ICA`, `1007759`) proved store specificity:
  Gunnesbo showed 12.20 SEK and 24.40 SEK/kg plus a 3-for-30 campaign, while ICA
  Kvantum Södra Sandby (`1003452`) showed 13.20 SEK and 26.40 SEK/kg without it.

What failed:

- headless Chromium received HTTP 403 for the document;
- in ordinary headed Chromium, scrolling caused ICA's own frontend to request the
  next product-decoration batch, but that same-origin request returned HTTP 405,
  `text/html`, 2,605 bytes, with an AWS-WAF CAPTCHA marker;
- the frontend retried the failed request, but no additional structured product batch
  became available;
- therefore all IDs can be observed for small terminal categories, but all products
  cannot be decorated with price/package data and complete cross-category traversal
  cannot be proven end-to-end.

Classification: **Result C — `OFFERS_ONLY` remains the highest safe operational
coverage.** A normal browser can read the initial store-specific catalogue surface,
but cannot produce a complete replayable catalogue under the approved constraints.
No browser transport or full-catalog snapshot is promoted.

The bounded diagnostic can be rerun explicitly after installing Playwright and its
ordinary Chromium binary:

```powershell
py -3.12 grocery_data/scripts/discover_ica_browser.py `
  --store 1088004 `
  --path "categories/skafferi/pasta-ris-mos/torkad-pasta/formpasta/7f4cc98a-2e78-41aa-bf65-a7e69ebd36a7" `
  --scrolls 1
```

It exits non-zero when the document or a product-batch response is classified as an
access challenge. It stores no raw browser session state and is not a daily collector.

### Public source and store context

An ICA store page links to its online catalogue by `accountNumber`. Verified example:

```text
GET https://handlaprivatkund.ica.se/stores/1088004
GET https://handlaprivatkund.ica.se/stores/1088004/search?q=pasta
GET https://handlaprivatkund.ica.se/stores/1088004/promotions
GET https://handlaprivatkund.ica.se/stores/1088004/products/spirali-500g-ica/1007759
```

Here `1088004` is the selected store's ICA account number. The pages rendered in a
normal public browser without login. Prices and product results changed in this store
context.

The catalogue pages embed a valid JSON object in `window.__INITIAL_STATE__`. Product
details also expose JSON-LD `Product` and `BreadcrumbList` records. These structured
blocks are preferable to scraping visual CSS classes.

A plain identifiable collector `GET` to the shopping search page returned HTTP 403
during discovery, while the normal public browser page rendered and referenced AWS
WAF challenge assets. No attempt was made to vary identity, solve a challenge, or
bypass the response. Consequences:

- normal `httpx` transport is **not verified** for this source;
- browser-assisted raw capture may be required if it is allowed by ICA's terms;
- a 403 must produce an explicit coverage/health failure, not a stealth workaround;
- the connector must never rotate identities or automate a CAPTCHA.

### Verified search payload

For `GET /stores/1088004/search?q=pasta`, the initial state contained:

- 50 entries in `data.products.productEntities`
- `data.search.catalogue.data.totalProducts = 223`
- `productGroups`, `breadcrumbs`, `sortOptions`, `categories`, `filters`
- `fullURLPath`, `query`, `currentCategory`, `totalProducts`

Verified product fields include:

- `productId`: ICA shopping-platform UUID
- `retailerProductId`: ICA retailer product number
- `name`, `brand`, `categoryPath`
- `available`, `isInCurrentCatalog`
- `size.value`, for example `"0.4kg"`
- `price.current.amount` and `price.current.currency`
- `price.unit.current.amount`, currency, and a unit label such as
  `fop.price.per.kg`
- image identifiers and URLs

The observed `retailerProductId` is not evidence of GTIN. The inspected product
detail JSON-LD exposed `sku`, but no `gtin`, `gtin13`, `ean`, or `barcode` field.
Therefore GTIN is **not available/verified** from this source today.

### Pagination

The initial search page gave 50 entities for 223 products. Additional products became
visible after client-side loading, but the exact search cursor request was not captured.
The official shopping bundle contains implementation paths such as:

```text
/api/search
/api/search/products
/api/product-listing-pages
/v6/product-pages/search
/v6/products
```

These strings are frontend-contract evidence only. Their request schema and support
status were not verified, so a connector must not invent a cursor contract from them.

## Operational offers source

The implemented connector uses each official store card's public `highlightUrls.offers.url`,
for example:

```text
GET https://www.ica.se/erbjudanden/maxi-ica-stormarknad-gunnesbo-lund-1088004/
```

This ordinary HTTP page returns structured `window.__INITIAL_DATA__` with
`offers.weeklyOffers`. On 2026-08-21 the Gunnesbo page declared 294 offer groups.
Important verified fields include:

- `id`, `details.name`, `details.brand`, `details.packageInformation`;
- `category.articleGroupName`, `validTo`, `comparisonPrice`, `restriction`;
- `parsedMechanics.benefitType`, `quantity`, `value1..value4`, `unitSign`;
- store-specific `regularPrice` and `referencePriceText`;
- `eans` variants and `traits`, including explicit `Stammis`;
- multibuy, fixed price, percent discount and other mechanics.

The parser retains a multibuy such as `3 för 25` as quantity 3 and total price 25.
It never flattens that condition to a one-item price. A `Stammis` trait produces
`member_only=true`. An offer group receives a GTIN only when exactly one valid EAN is
present; groups with multiple variants remain GTIN-unknown.

Regular-price or comparison-price ranges remain unknown rather than being collapsed
to one invented value. The offers source has no reliable stock signal. It also does
not expose a verified drained quantity in the inspected records; drained quantity is
therefore `None` rather than inferred from text such as “utan spad”.

## Price and quantity semantics

Verified representation separates:

- sale/current price (`price.current`)
- comparison/unit price (`price.unit.current` plus its label)
- package text (`size.value`)
- promotion terms (`offer`/`offers`)

Required invariants for the ICA parser:

1. Never derive package quantity from the comparison price.
2. Parse `size.value` independently and retain the original text.
3. Treat an unknown or ambiguous package string as unknown, not as 1 kg.
4. Keep regular/current price and multibuy/member promotion separate.
5. Treat `available`/JSON-LD `InStock` as online-catalogue availability only; it is not
   verified physical shelf inventory.

## Recommended raw capture boundary

The ICA connector sanitizes before constructing a `RawFetch`. It saves only:

- an `ica-public-ssr-v1` JSON envelope containing the parser-required public
  `resultStore` store-card fields; or
- an `ica-public-ssr-v1` JSON envelope containing the parser-required public
  `offers.weeklyOffers` fields;
- URL, status, content type, fetch time, payload hash, and connector version.

The allowlist structurally excludes page/runtime configuration. Access challenges,
HTTP errors and sanitization failures become closed inert JSON diagnostics; response
bodies, response/request headers, cookies, authorization data, browser storage and
session material are never included in a `RawFetch`.

### Historical raw-snapshot remediation (2026-08-23)

A bounded workspace audit found 29 legacy ICA HTML files containing runtime- or
session-shaped fields. No values were printed or copied. The exact closed target
manifest and idempotent migration are retained in
`grocery_data/scripts/remediate_ica_raw_snapshots.py`.

The migration:

- proved parser-equivalent output for all 29 files (11 store pages and 18 offer pages);
- atomically replaced only those 29 files with the same `ica-public-ssr-v1` allowlist;
- updated all 43 linked `raw_snapshots` rows, including payload hash/size, content type,
  request fingerprint, per-batch schema fingerprint and connector remediation version;
- updated 11 affected catalog snapshots' schema evidence/fingerprint and matching active
  connector-health fingerprints in one transaction per database;
- covered `.ica_recipe_benchmark.sqlite` (3 raw rows), `cross_chain_phase2.sqlite`
  (8 raw rows), and `ica_phase2.sqlite` (32 raw rows); and
- handled ten unreferenced canary raw files without inventing database lineage.

Post-migration validation reported parser parity 29/29, database integrity 43/43 and
zero files containing any of the denied ICA runtime/session key families across the
workspace raw roots. No unsanitized backup was retained.

## Coverage limitations and risks

- Operational coverage is `OFFERS_ONLY`; no full catalogue is claimed.
- An ICA account number and an internal `storeId` are different namespaces.
- The browser-visible full catalogue is not collected: plain/headless HTTP is blocked,
  and ordinary headed Chromium reaches a CAPTCHA response on product-batch continuation.
- Offer-group GTIN is available only for a single unambiguous EAN variant.
- `validTo` is available; `validFrom` remains unknown in this source.
- Anonymous availability is not proven to equal physical shelf stock.
- Plain collector HTTP was rejected once with 403; this is a material operational risk.
- All internal endpoint names and response shapes are unversioned frontend contracts.
- ICA can change asset filenames, state shape, WAF policy, or online-store availability
  without notice.

## Incremental product registry

ICA remains `OFFERS_ONLY` for consumer catalogue behavior. A separate, explicitly
incomplete registry accumulates product identities from ordinary public SSR pages and
the existing offers collector. It never upgrades coverage to `FULL_CATALOG` based on
accumulation or an estimated saturation percentage.

The identity observed in both Gunnesbo and Södra Sandby is the ICA retailer product ID;
it is stored once globally. Store price, comparison price, availability and promotion
are separate historical observations. Every discovery event retains its source kind,
page identifier, observation time and optional opaque raw-snapshot lineage.

Safe discovery uses fresh ordinary browser sessions with small deterministic page
budgets. A 403, 405/HTML WAF response, CAPTCHA, Human Verification or access-denied page
ends the run immediately without retries. Cookies, browser storage, request headers and
challenge state are never persisted. The structured `window.__INITIAL_STATE__` subset
can be replayed offline by `connectors/ica/registry_parser.py`; discovery and enrichment
are deliberately separate, so an ID may remain `DISCOVERED_ID_ONLY`.

Internal diagnostics:

- `GET /registry/ica/stores/{store_id}/stats`
- `GET /registry/ica/products/{external_product_id}`
- `POST /registry/ica/stores/{store_id}/basket-coverage`

The last endpoint is a query-level safety check. It reports complete only when every
requested canonical ingredient has a recent priced observation with acceptable
semantic and quantity confidence. It does not claim that ICA's whole catalogue is
complete.

## Initial canary assertions

A low-volume canary should verify, without a full crawl:

1. the Lund or Malmö locator page returns HTTP 200;
2. `__INITIAL_DATA__` exists and converts to the closed replayable SSR allowlist;
3. `totalNrOfStores > 0`, and the first page has municipality/address identifiers;
4. one offers page returns `weeklyOffers` with a plausible non-zero count;
5. name, promotion mechanics and store price evidence parse;
6. comparison price never becomes package quantity;
7. a missing/renamed `weeklyOffers` field marks the run broken and leaves LKG active.

## Live Phase 2 result

One isolated collection on 2026-08-21 produced:

| Scope | Stores | Offer rows | Price evidence | GTIN | Package quantity | Requests |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Lund municipality | 2 | 381 | 365 (95.8%) | 180 (47.2%) | 117 (30.7%) | 3 |
| Malmö municipality | 4 | 771 | 740 (96.0%) | 369 (47.9%) | 242 (31.4%) | 5 |

Both snapshots were promoted `HEALTHY`, with zero HTTP errors, zero 429 responses and
zero quarantine records. Offline replay reproduced 381/771 records with zero network
requests and unchanged raw files. High `UNKNOWN` purchase-model rates (72.7% Lund,
69.1% Malmö) are expected for offer groups whose public source does not state an
unambiguous package/sale model; these rows are not fabricated into fixed packages.

## How to fix this connector

1. Run `python -m grocery_data canary ica --city Lund` (and Malmö).
2. Inspect `/health/connectors/ica`, schema diff and bounded failure samples.
3. Locate the affected immutable `stores_page` or `offers_page` raw document.
4. Sanitize a representative snippet and add/update an ICA fixture.
5. Change only `connectors/ica/client.py`, `models.py` or `parser.py` where possible.
6. Run ICA parser, normalization, promotion and quantity tests offline.
7. Replay the affected snapshot; confirm `network_requests=0`.
8. Diff old/new normalized snapshots and inspect coverage changes.
9. Validate health and ensure an incomplete/broken result is not promoted.
10. Promote atomically, then verify stores, catalog/offers API and freshness metadata.

## Final recipe-relevant enrichment experiment (2026-08-21)

ICA remains `OFFERS_ONLY`. A persistent registry and query-level coverage diagnostics
are useful, but ordinary-browser SSR enrichment is not reliable enough to make ICA a
general basket store. No CAPTCHA, WAF, login or access-control bypass was attempted.

One fresh ordinary headed-Chromium session, capped at ten navigations, observed:

| Safe route | Pages | Declared total | SSR product IDs | Priced | Package metadata | GTIN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Gunnesbo search `pasta` | 1 | 223 | 50 | 50 | 50 | 0 |
| Gunnesbo search `mjölk` | 1 | 240 | 50 | 50 | 50 | 0 |
| Gunnesbo category `Mejeri & Ost` | 1 | 291 | 50 | 50 | 50 | 0 |
| Product detail | 5 | n/a | 5 | 5 | name-only | 0 |
| Recipe index/detail | 2 | n/a | 0 | 0 | 0 | 0 |

Search/category SSR therefore yielded 50 priced products per page, but only the first
50 fully decorated records for result sets of 223--291. It did not provide a complete
termination proof. Product detail yielded one price per navigation and no GTIN;
recipe pages exposed no retailer-product mapping. ICA's public sitemap indexes cover
content, stores and recipes, but no online-product catalogue sitemap was found.

This run reached its hard navigation budget without a challenge. A separate earlier
ordinary headed session reached Human Verification on its third search navigation and
stopped immediately. The variable challenge point makes SSR enrichment unsuitable as
a production completeness mechanism. Enrichment-run health is persisted separately
from the stable offers-source health; a challenge marks enrichment `degraded` without
invalidating the offers snapshot.

A fresh Lund offers collection populated 381 registry observations. With the same
semantic, quantity and seven-day freshness gates used by the consumer, the 48-item
recipe benchmark measured:

| Store | >=1 usable | >=3 usable | >=5 usable |
| --- | ---: | ---: | ---: |
| Maxi ICA Gunnesbo | 4/48 (8.33%) | 0/48 | 0/48 |
| ICA Nära Södra Sandby | 2/48 (4.17%) | 0/48 | 0/48 |

The representative ten-ingredient basket was safely covered 2/10 at Gunnesbo and 1/10
at Södra Sandby, so `complete_for_request=false` for both. One-, three- and seven-day
thresholds were identical because the offers observations were new. Missing rows are
reported as `NO_PRODUCT_IDS`, `STALE_PRICE`, `UNKNOWN_QUANTITY`,
`SEMANTIC_REJECTION`, or `NO_STORE_PRICE`; stale and fresh data are never silently
mixed into a complete result.

Operational recommendation: **C -- retain ICA OFFERS_ONLY and the opportunistic,
replayable registry, but stop investing in automated ICA basket enrichment. Use Primat
or another licensed/provider source where broad current ICA prices are required.**
The evidence is far below the predeclared 95% ingredient and 90--95% basket thresholds,
while safe browser collection has an unstable challenge boundary. This conclusion does
not make any claim about how Primat obtains ICA data.

Deferred research backlog (not executed): [ICA OWN acquisition research](ica-own-deferred-research.md).
