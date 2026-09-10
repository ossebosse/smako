# Coop source discovery

Last verified: **2026-08-25**

## Result

| Area | Result |
| --- | --- |
| Store discovery | Public store locator and public store detail pages |
| Browser/API discovery result | Deterministically enumerable and accepted online catalogue in a selected fulfilment context |
| Online price granularity | Regional/online context; it is not verified physical shelf pricing |
| Online context model | Price/assortment context `730400` is separate from physical stores and pickup points; Stora Coop Lund uses pickup point `257611` |
| Operational own source | Public physical-store offer pages |
| Online candidate identity | Stable `id` plus separately validated `ean`; the verified product model exposes both |
| Package metadata | Structured size/unit, sales unit, comparison price/unit, piece weight, and source package text |
| Availability | Online fulfilment signal; physical shelf reliability not verified |
| Accepted OWN coverage | Result A — `FULL_ONLINE_CATALOG` |
| Promoted catalogue snapshot | `851d317e88ce422b90d80d26ca1ebb2b` |
| Optimizer catalogue source | OWN primary; Primat/licensed data is an explicit fallback only |

The physical-store offer feed and the regional online catalogue remain separate source
channels. On 2026-08-25 the reviewed catalogue collector completed all 748 accepted
terminal categories and 822 product pages for online context `730400`. It reconciled
12,380 raw category rows to 11,175 unique purchasable products, replayed the same raw
data with zero network requests, passed the full quality and basket gates, and promoted
snapshot `851d317e88ce422b90d80d26ca1ebb2b` atomically. The production source strategy
therefore uses OWN as Coop's basket primary and keeps Primat/licensed data only as an
explicit, provenance-preserving fallback.

## Final discovery classification

**Result A — COOP OWN = `FULL_ONLINE_CATALOG`; basket source = OWN.**

Normal anonymous public requests verified the structured product, product-by-id,
category-tree, category-product, promotion-list, promotion-detail, and fulfilment
contracts for online context `730400`. A full `mjölk` search reconciled 290/290 unique
rows, root category `Mejeri & ägg` reconciled 786/786, and the reviewed full run
completed 748/748 accepted terminal categories and 822/822 pages. Cross-category
overlap accounted for 1,205 of 12,380 raw rows; the accepted union contains 11,175
unique products, with zero unresolved within-category conflicts or pagination loops.

The physical-offer connector continues to use ordinary public store pages as a separate
OWN offers channel. The regional catalogue is represented by one addressless online
fulfilment context, **Coop Online Syd** (`730400`), not by cloning it into physical
stores. The active Lund relation is physical Stora Coop Lund (`2696`) -> pickup point
`257611` -> online context `730400`; Mårtenstorget has no verified pickup link. Prices
from `730400` are labelled **online price**, never verified physical shelf price.

### Accepted full-catalogue quality

| Metric | Result |
| --- | ---: |
| Accepted terminal categories / pages | 748 / 822 |
| Raw category rows / unique products | 12,380 / 11,175 |
| Safe cross-category overlaps / unresolved conflicts | 1,205 / 0 |
| Price / regular-price coverage | 100.00% / 100.00% |
| Checksum-valid GTIN | 11,119 / 11,175 (99.50%) |
| Package quantity | 11,086 / 11,175 (99.20%) |
| Resolved purchase model | 11,094 / 11,175 (99.28%) |
| Comparison-price / availability coverage | 96.17% / 100.00% |
| Recipe coverage >=1 / >=3 / >=5 | 48/48 / 45/48 / 39/48 |
| Representative basket | 13/13 complete |
| Offline replay | Exact catalogue reconstruction, 0 network requests |

The accepted union persisted 1,003 normalized promotions across 979 products: 240
public sale-price rows, 10 member-price rows, 748 multibuy rows, and 5 percentage
discounts. Sixty-seven promotions are explicitly member-only. Promotion validity was
present for all 1,003 rows. `CUSTOMER_PRIVATE` remains a B2C customer-group marker and
never establishes membership by itself.

The separate [official API and partner-path report](coop_official_api.md) records the
formal-access research. Coop operates an official API portal, but its anonymous API
and product catalogues were empty at verification time. Azure AD sign-in was visible
and a generic signup route required CAPTCHA; neither was attempted. A negotiated
partner enquiry appears plausible, but external eligibility, catalogue products,
terms, and an onboarding route remain **unknown**.

## Twelve mandatory discovery answers

1. **Can Lund/Malmö physical stores be found publicly?** Yes: 7 Lund and 13 Malmö
   store pages were verified. Store-coverage discovery has a bounded dynamic locator
   transport. The separate offers connector retains reviewed bootstrap paths.
2. **Can an anonymous user see Coop's online catalogue?** Yes. A normal browser can
   select a delivery/pickup context and view searches, categories, products, and
   prices without login.
3. **What is the structured product transport?** Coop's public bundle constructs a
   REST `POST` to `/personalization/search/products`; it is not GraphQL.
4. **What selects price and assortment?** The public product requests use online
   context `730400` for the verified Coop Syd flow. `deliveryMode` and pickup identity
   remain separate. The public point-of-service response links Stora Coop Lund pickup
   point `257611` to online context `730400`.
5. **Are physical store IDs interchangeable with online IDs?** No. Public
   `StorePageType.storeID` values `2696` (Stora Coop Lund) and `3853` (Stora Coop
   Stadion) are physical-store identities and must not be treated as production-unit
   or pickup-point IDs.
6. **Is catalogue membership context-specific?** Yes. Lund, Hjärup, and verified Malmö
   pickup points share `730400`, while a Stockholm control uses distinct context
   `256600`. This is regional/fulfilment context, not a physical-store ID.
7. **Are physical-store-specific prices proven?** No. A 97-product Lund/Stadion
   sample had identical visible prices. The prices are context-bound, but may be
   regional or central across the tested production units.
8. **Can bounded pagination be reconciled?** Yes. On 2026-08-25, `mjölk` reconciled
   290/290 as 12 pages of 24 plus 2 rows, with zero duplicates, conflicts, or missing
   rows. `Mejeri & ägg` reconciled 786/786 across 17 pages, also without duplicates,
   conflicts, or missing rows. Counts are observations and may change.
9. **Can complete catalogue traversal be proved?** Yes. Two exact non-category root
   sentinels and one exact duplicate leaf were excluded or collapsed under fail-closed
   rules, leaving 748 accepted terminal categories. All 748 categories and 822 pages
   completed, with 12,380 raw rows, 11,175 unique products, 1,205 safe cross-category
   overlaps, and zero unresolved conflicts or pagination loops.
10. **Did ordinary browsing hit a challenge?** No challenge appeared during more
    than 20 bounded, normal navigations used for this discovery. That observation is
    not a licence or stability proof for an unattended full-catalogue collector.
11. **Is the online-catalogue evidence replayable today?** Yes. The complete raw-first
    catalogue replay reconstructed all 11,175 products with network disabled. Critical
    schema failure, rejected candidate, retained last-known-good, local repair, replay,
    and atomic promotion are regression-tested.
12. **What coverage is defensible?** Result A, `FULL_ONLINE_CATALOG`. Coop Online Syd
    `730400` is an OWN basket context; physical store offers remain a separate OWN
    offers channel, and Primat/licensed data remains an explicit fallback only.

## Operational live verification

Two isolated collections on 2026-08-21/22 verified the current parser-v2
`OFFERS_ONLY` boundary. These numbers are rendered offer groups, **not** unique SKUs
or catalogue-product counts:

| Metric | Lund | Malmö |
| --- | ---: | ---: |
| Verified bootstrap store pages | 7 | 13 |
| Stores with verified offer context | 7 | 11 |
| Parsed offer rows | 322 | 494 |
| Rows with any price observation | 322 | 494 |
| Rows with explicit `sale_price` | 38 (11.80%) | 61 (12.35%) |
| Comparison price | 144 (44.72%) | 220 (44.53%) |
| Explicit package quantity | 172 (53.42%) | 263 (53.24%) |
| Resolved purchase model | 20 (6.21%) | 31 (6.28%) |
| Promotions | 287 | 437 |
| Member-only promotions | 109 | 164 |
| GTIN / stable external product ID | 0 / 0 | 0 / 0 |
| Parser failures / quarantine | 0 / 0 | 0 / 0 |
| Physical requests | 14 | 24 |
| HTTP errors / 429 | 0 / 0 | 0 / 0 |
| Raw files / bytes | 14 / 52,227 | 24 / 80,793 |
| Runtime | 45.657 s | 65.531 s |

Promoted live snapshot IDs are `d4694cc526db4aca84ca32fe9545773a` (Lund) and
`7669fb1950554fa6a2b6ea16b206c664` (Malmö). Their inactive replay candidates are
`83a6ee1990294108a3b1ffe74ed065fa` and `7fb1453c73df4298bc9c2e19d140e249`.

`products_with_price` includes a priced conditional promotion and must not be called
100% ordinary-price coverage. The high `UNKNOWN` purchase-model rate (302/322 Lund,
463/494 Malmö) is expected for grouped physical-store offers that do not identify one
purchasable SKU/package. They remain diagnostic offers rather than fabricated basket
products.

The live `StorePageType` records expose store identity but no address/postcode JSON-LD.
The connector therefore persists city from the explicitly verified bootstrap scope
with `city_evidence=verified_bootstrap_scope`, while address, postcode, coordinates,
and online-shopping status remain `None`. Catalogue stores still require stronger
location evidence; the nullable fields are accepted only on the separate offers
diagnostic path.

Both snapshots replayed from their 38 saved raw files with zero HTTP requests and zero
browser launches. Diff was exact (322/322 and 494/494 shared rows, no additions,
removals, price changes, failures, or warnings), and raw file counts/bytes did not
change.

## Evidence convention

- **Verified** means observed on an official Coop page, public response used by that
  page, or data embedded by it through 2026-08-25.
- **Frontend contract** means the method/path/schema belongs to Coop's current public
  frontend. Where a call was also reproduced, the surrounding section says so and
  reports its bounded reconciliation result.
- **Not verified** means the connector must not rely on the behaviour yet.

No login, CAPTCHA, access-control bypass, cookie, authorization value, or copied
session/tracking identity was used or retained. Public frontend runtime configuration
used to reproduce anonymous calls was transient and is deliberately absent from this
document, fixtures, logs, and raw data.

## Store discovery

### Public sources

Verified `GET` pages:

- [Coop store locator](https://www.coop.se/butiker-erbjudanden/)
- [Stora Coop Lund detail](https://www.coop.se/butiker-erbjudanden/stora-coop/stora-coop-lund/)
- [Coop Värpinge Lund detail](https://www.coop.se/butiker-erbjudanden/coop/coop-varpinge-lund/)

The locator renders without login. Searching for Lund in the public UI returned, among
other results, Stora Coop Lund, Coop Värpinge Lund, and Coop Vildgåsen Lund.

Store detail pages embed an `application/json` record of type `StorePageType`. The
verified Stora Coop Lund record contained:

- `storeID = 2696`
- `ledgerAccountNumber = 105760`
- `organizationUnitID = 114`
- `simpleAddressUrl = "105760"`
- `name`, `routeSegment`, `url`, and `disableStoreOffersFlyer`

These are distinct source identifier namespaces. A collector must label and store
them separately rather than assuming that an offer-page ID, ledger account, online
fulfilment-store ID, and content-page ID are interchangeable.

### Frontend request contract

The official page declares this store API base:

```text
https://proxy.api.coop.se/external/store/
```

Coop's official current store bundle constructs:

```text
GET /stores/map?conceptIds=12,6,95&invertFilter=true
    query: api-version=v2

GET /stores?storeIds={comma-separated ids}
    query: api-version=v1

GET /stores/{storeId}?includeFlyers=true
    query: api-version=v5&onlyVisibleOpeningHours=true

GET /sub-pages/{storeId}
    query: api-version=v5&onlyVisibleOpeningHours=true
```

The general search bundle also constructs:

```text
POST /search/stores
{
  "query": "Lund",
  "resultsOptions": {
    "skip": 0,
    "take": 20,
    "sortBy": [],
    "facets": []
  }
}
```

The frontend's store-result mapper expects source fields including `id`,
`ledger_account_number`, `name`, `address`, `city`, `zip`, `latitude`, `longitude`,
`services`, `url`, `hasDR`, and `opening_hours`.

The store API calls require a subscription header that the official page receives in
its browser runtime configuration. Discovery did **not** copy, log to a fixture, or
use that value. Direct API transport therefore remains unapproved/unverified. Until
an approved client contract exists, the safe source boundary is the public locator
and store-detail page (with browser assistance only if ordinary HTTP is insufficient).

Official store bundle inspected:

```text
https://www.coop.se/Assets/apps/coopse/dist/coopse.script.storesApp.fc698183.js
```

### Verified Lund and Malmö store results

Selecting the city result in the official public store finder returned **7 Lund
stores** and **13 Malmö stores**. Each detail page returned HTTP 200 and exposed the
`StorePageType` JSON described above. These are physical-store identities; online
fulfilment capability is listed separately below.

| City | Store | Address shown | `storeID` | Ledger | Seeded public `store_page_path` |
| --- | --- | --- | ---: | ---: | --- |
| Lund | Coop Värpinge Lund | Hildur Sandbergs Gata 22 | 3659 | 216526 | `/butiker-erbjudanden/coop/coop-varpinge-lund/` |
| Lund | Stora Coop Lund | Traktorvägen 2 | 2696 | 105760 | `/butiker-erbjudanden/stora-coop/stora-coop-lund/` |
| Lund | Coop Trollebergsvägen | Trollebergsvägen 14 | 3837 | 106444 | `/butiker-erbjudanden/coop/coop-trollebergsvagen/` |
| Lund | Coop Flöjtvägen | Flöjtvägen 44 | 3839 | 106445 | `/butiker-erbjudanden/coop/coop-flojtvagen/` |
| Lund | Coop Klostergården | Nordanvägen 7-9 | 3820 | 106435 | `/butiker-erbjudanden/coop/coop-klostergarden/` |
| Lund | Coop Mårtenstorget | Mårtenstorget 11 | 3813 | 106430 | `/butiker-erbjudanden/coop/coop-martenstorget/` |
| Lund | Coop Vildgåsen Lund | Vildgåsvägen 27 | 3656 | 216523 | `/butiker-erbjudanden/coop/coop-vildgasen-lund/` |
| Malmö | Coop Slottsstaden | Regementsgatan 70 | 3648 | 216535 | `/butiker-erbjudanden/coop/coop-slottsstaden/` |
| Malmö | Stora Coop Stadion | Stadiongatan 24 | 3853 | 105860 | `/butiker-erbjudanden/stora-coop/stora-coop-stadion/` |
| Malmö | Coop Forum Jägersro | Jägersrovägen 151 | 3850 | 105810 | `/butiker-erbjudanden/coop-forum/coop-forum-jagersro/` |
| Malmö | Coop Köpenhamnsvägen | Köpenhamnsvägen 2 | 3848 | 106420 | `/butiker-erbjudanden/coop/coop-kopenhamnsvagen/` |
| Malmö | Coop Värnhem | Föreningsgatan 72 | 3823 | 106412 | `/butiker-erbjudanden/coop/coop-varnhem/` |
| Malmö | Coop Nobeltorget | Amiralsgatan 68 | 3832 | 106414 | `/butiker-erbjudanden/coop/coop-nobeltorget/` |
| Malmö | Coop Malmö Central | Skeppsbron 1c, Centralplan | 3833 | 106415 | `/butiker-erbjudanden/coop/coop-malmo-central/` |
| Malmö | Coop Kornettsgatan | Kornettsgatan 13 | 3835 | 106417 | `/butiker-erbjudanden/coop/coop-kornettsgatan/` |
| Malmö | Coop Norra Parkgatan | Norra Parkgatan 1 | 3816 | 106411 | `/butiker-erbjudanden/coop/coop--norra-parkgatan/` |
| Malmö | Coop Karolingatan | Karolingatan 1 | 3838 | 106419 | `/butiker-erbjudanden/coop/coop-karolingatan/` |
| Malmö | Coop Kirseberg | Kirsebergstorg 7 | 3834 | 106416 | `/butiker-erbjudanden/coop/coop-kirseberg/` |
| Malmö | Coop Bulltofta | Ahrenbergsgatan 2 | 3815 | 106410 | `/butiker-erbjudanden/coop/coop-bulltofta/` |
| Malmö | Coop Västra Hamnen | Östra Varavsgatan 75 | 3653 | 216530 | `/butiker-erbjudanden/coop/coop-vastra-hamnen/` |

All 20 verified paths are present in the offer connector's bootstrap seed list.
`fetch_stores` on that connector performs ordinary public GETs against the allow-listed
paths and parses their current `StorePageType` evidence; this offer-specific path does
not discover a newly opened store until its bootstrap list is reviewed.

Physical-store coverage is deliberately separate. Its bounded adapter opens the
ordinary public locator, selects the exact city as a normal visitor, requires the
rendered declared total, captures only the visible name/address/postcode/detail links
in a closed sanitized envelope, and follows every returned detail page. Lund was
reconciled as exactly 7/7 current physical stores. Detail evidence preserves both
`storeID` and the distinct `ledgerAccountNumber` alias. The source identities remain
deduplicated by chain plus `storeID`; the two ID namespaces are never guessed to be
interchangeable.

The public online pickup selector verified **Stora Coop Lund** as a Lund fulfilment
store. A Malmö search offered **Stora Coop Stadion**, **Coop Forum Jägersro**, and
**Stora Coop Burlöv**; Burlöv is outside Malmö municipality and must not be silently
reported as a Malmö physical store. Other physical stores must be declared
`UNAVAILABLE` for a full online catalogue unless their online capability is separately
verified.

## Public online catalogue and accepted collector evidence

The structured routes in this section are collected only by the reviewed online
catalogue connector. The older physical-store offer connector remains a separate,
low-volume source channel and does not establish catalogue completeness.

### Public store-context flow

Verified public pages:

```text
GET https://www.coop.se/handla/
GET https://www.coop.se/handla/sok/?q=pasta
GET https://www.coop.se/handla/sok/?q=pasta&page=2
GET https://www.coop.se/handla/varor/skafferi/pasta-pastasas/formpasta/pasta-amorosi-7340191165588
```

No login was required. With no selection, the catalogue showed `Hemleverans i
Stockholm`. The public selector accepted postcode `22350`, offered delivery and pickup
options, and allowed selection of **Stora Coop Lund**. After selecting a public pickup
slot, the page showed `Hämtas på Stora Coop Lund` and the same pasta query changed from
375 results in the default context to 288 results in the Lund context. That is direct
evidence that catalogue membership is store/fulfilment-context specific.

The public ecommerce bundle distinguishes three online-context concepts:

- `productionUnit` supplies the price/assortment context used as the product-search
  `store` value;
- `deliveryMode` represents delivery versus pickup behaviour;
- `pickupPointId` identifies a selected pickup point where applicable.

Those concepts are separate from the physical-store `StorePageType.storeID`. The
public physical page identifies Stora Coop Lund as physical store `2696`; the verified
online price/assortment context is instead `730400`, and the pickup point is `257611`.
The public point-of-service response for `257611` identifies Stora Coop Lund and links
it to `storeId = 730400`. It is primary fulfilment evidence; an analytics observation
with the same relation is retained only as secondary discovery evidence and never as
runtime data.

The same public fulfilment source showed Coop Hjärup and verified Malmö pickup points
using `730400`. A Stockholm control used `256600`. This supports the conservative
label **Coop Online Syd** for `730400`: it is one regional/online purchasing context
that multiple pickup locations may serve, not Stora Coop Lund under another name.
Mårtenstorget was not selectable as pickup and must not inherit this link. Online
prices from `730400` must be labelled online prices, not verified shelf prices.

### Public catalogue indexes and pagination evidence

Coop's public `robots.txt` points to an index containing these official sources:

```text
GET https://www.coop.se/handla/sitemap_products.xml
GET https://www.coop.se/handla/sitemap_productsection.xml
```

Both returned HTTP 200 without special headers. On 2026-08-25:

- `sitemap_products.xml` contained **13,912 product URLs**;
- `sitemap_productsection.xml` contained **749 unique category URLs**;
- the direct parent category of **13,868 / 13,912** product URLs occurred in the
  category sitemap.

These sitemaps prove a deterministic, non-search-keyword product/category identity
universe. They do **not** prove that every listed product is orderable at a selected
store or that the sitemap equals every physical shelf assortment.

Pagination was checked end-to-end for structured responses in online context `730400`
as well as the earlier rendered examples:

| Route | Reported total | Page rows | Reconciled |
| --- | ---: | --- | --- |
| `/handla/sok/?q=pasta` | 288 | 12 pages × 24 | 288 |
| `/handla/varor/skafferi/pasta-pastasas/formpasta` | 77 | 48 + 29 | 77 unique, 0 duplicates |
| Product search `mjölk` | 290 | 12 × 24 + 2 | 290 unique, 0 duplicates/conflicts/missing |
| Category `Mejeri & ägg` | 786 | 16 × 48 + 18 | 786 unique, 0 duplicates/conflicts/missing |

This proves offset pagination for those examples. The count changed from the earlier
manual milk observation (288) to 290, which is expected for a live assortment and is
why completion reconciles each response's own declared total. The later reviewed full
run applied the same response-driven rule to all 748 accepted terminal categories and
all 822 pages before `FULL_ONLINE_CATALOG` was accepted.

The verified context-specific category transport is a recursive tree request for
`730400`, followed by category-product requests using the source category code and
`skip`/`take`. The raw tree contained 24 roots. Two exact nameless `/varor/` root
sentinels (`0001` and `0002`) are excluded only while their complete sentinel shape is
unchanged, and one exact duplicate terminal leaf is collapsed. Any changed sentinel,
nesting, URL, name, or children fails closed. The accepted traversal therefore contains
748 terminal categories; product overlap across different categories is reconciled
separately by stable product identity.

Adding or changing a public `pageSize` query parameter did not change the rendered
page size in the inspected route. A collector therefore cannot use that parameter as
a completeness control; it must follow the visible/returned pagination contract and
deduplicate source product identities.

### Public HTML and JSON-LD fields

The Lund-context search rendered 24 product links on the first page and a public
`aria-label="Sidnumrering"` navigation through page 12 for 288 results. Page URLs use
the one-based `page` query parameter shown above.

Product cards expose, in accessible HTML:

- product name and brand/manufacturer;
- package text, for example `500 g`;
- sale price and sale unit, for example `11,95 kr/st`;
- comparison price/unit, for example `23,90 kr/kg`;
- category path and a product detail URL;
- a 13-digit identifier in the verified product URL.

The product detail has JSON-LD `Product` containing:

- `name`, `brand`, `description`, and images;
- `sku`, `gtin`, and `gtin13` (all `7340191165588` for the verified sample);
- `category`;
- `size` as `QuantitativeValue`, e.g. `value = 500`, `unitCode = "GRM"`;
- `offers.price`, `priceCurrency`, and `availability`;
- `countryOfOrigin` and nutrition/ingredient `additionalProperty` values.

GTIN from JSON-LD is therefore a verified primary product key for this source. The
identifier embedded in a URL should still be cross-checked against JSON-LD rather than
accepted solely because it has 13 digits.

### Store-context and price-granularity sample

The normal public pickup selector was used to switch between **Stora Coop Lund** and
**Stora Coop Stadion**. No cookies, storage, request headers, or session identifiers
were inspected or persisted.

A same-route comparison covered 97 shared rendered product cards:

- form pasta: 48;
- potatoes: 9;
- eggs: 15;
- whole chicken/chicken fillet: 7;
- minced beef: 8;
- standard milk: 10.

Together with the reconciled pasta/formpasta routes and the verified Pasta Amorosi
detail, these checks cover representative recipe-relevant areas: dairy, eggs, pasta,
potatoes, chicken, minced meat, and an exact fixed-package grocery product. They are a
bounded quality sample, not a recipe-coverage or full-catalogue benchmark.

Membership and rendered price labels were identical for all 97 products. The verified
Pasta Amorosi detail price was `11.95 SEK` in both contexts. Consequently, this sample
does **not** prove per-physical-store price variation; the tested prices may be regional
or central across these fulfilment stores. The earlier default-Stockholm versus Lund
search-count difference (`375` versus `288`) still proves that catalogue membership is
fulfilment-context dependent.

The collector must therefore preserve the selected fulfilment context as lineage but
must not describe a price as proven physical-store-specific solely because a store was
selected.

More than 20 ordinary browser navigations across store-context selection, searches,
pagination, category pages, and product detail completed without CAPTCHA, WAF, or
access-challenge evidence. No retry, identity rotation, stealth, or challenge bypass
was used. This only establishes that the bounded manual discovery paths were publicly
browser-visible; it does not establish that a daily unattended full traversal is an
approved or durable transport.

### Replayable online diagnostic evidence

The earlier rendered-card and JSON-LD fixtures remain useful. The 2026-08-25 work adds
sanitized structured fixtures for a normal product, fixed-package liquid quantity,
fixed-price campaign, multibuy, percentage discount, variable-weight semantics,
category completion, and online-context/pickup identity. They contain response data
only: no cookie, authorization value, CSRF value, browser storage, client runtime
value, or tracking identifier.

The online parser requires matching context, request type, declared total, contiguous
offsets, exact raw/unique counts, and safe product identity. A repeated product within
one category may be removed only when price, regular price, package, promotion,
availability, and purchasing semantics are identical. The same product ID with any
conflicting purchasing semantics fails closed. Cross-category overlap is expected and
is reconciled by stable external product ID/EAN after each category has independently
completed.

Bounded fixtures and the complete saved `730400` category union replay with network
disabled. The full replay produced all 11,175 products with zero network requests.
Regression coverage also changes a critical price field, rejects the broken candidate,
keeps the previous last-known-good active, applies a connector-local repair, replays
offline, and permits promotion only after the full health gates pass.

### Frontend search contract

The page declares:

```text
personalization API: https://external.api.coop.se/personalization
api-version: v1
search UI: /handla/sok/
product UI: /handla/varor/
```

The official ecommerce bundle constructs this **REST** request (not GraphQL), and the
contract was reproduced with normal anonymous public requests for `730400`:

```text
POST https://external.api.coop.se/personalization/search/products
query parameters:
    api-version=v1
    store=730400
    groups=CUSTOMER_PRIVATE
    device=desktop
    direct=false

body:
{
  "query": "mjölk",
  "resultsOptions": {
    "skip": 0,
    "take": 24,
    "sortBy": [],
    "facets": []
  },
  "relatedResultsOptions": {
    "skip": 0,
    "take": 16
  },
  "customData": { "consent": true }
}
```

Normal result mode uses `direct=false` and derives `skip`/`take` from the UI page. The
verified milk traversal used `take=24` and `skip=0,24,48,...` until its declared
`results.count=290` was exactly consumed. A related first-request mode may use another
page size; completion must always follow the actual response contract rather than
assuming a global constant.

A manually supplied `pageSize` URL parameter was ignored by the rendered search page
in the bounded check. It is not a supported pagination control.

Any public frontend runtime configuration needed to make the same anonymous request is
resolved transiently in-process and is never logged, persisted, added to fixtures, or
included in raw metadata. Cookies, authorization, CSRF, route/session state, and
tracking identities are neither required evidence nor retained. The source remains a
public frontend implementation contract, not a supported external-partner API.

Additional verified routes are:

```text
POST /personalization/search/entities/by-id
GET  /ecommerce/coop/users/anonymous/categories/tree/730400
POST /personalization/search/entities/by-attribute
POST /personalization/search/products/promotions
POST /personalization/search/products/promotion
GET  /ecommerce/coop/pointofservice/{pickupPointId}
```

Ten sampled products had exact basket-relevant field/value parity between the search
row and product-by-id response. Normal collection must therefore use paginated search
or category responses and reserve by-id for bounded diagnostics or explicit detail
enrichment; a by-id request per catalogue product is unnecessary.

The official frontend's product mapper expects a rich source record, including:

- `id`, `ean`, `name`, `variety`, `manufacturerName`, and category trees;
- `piecePriceData`, `promotionPriceData`, `historicalPriceData`;
- `comparativePriceData`, `comparativePriceUnit`, `comparativePriceText`;
- `packageSize`, `packageSizeUnit`, `packageSizeInformation`, `salesUnit`-related data;
- `displayWeightPrice`, `pieceWeight`, and variant quantities;
- `onlinePromotions`, `promotionProductsEans`, deposits, origin, storage state, and
  ingredients/nutrition.

These fields were also observed in structured responses. A verified 1.5 litre milk
record exposed stable `id`/`ean`, `packageSize=1500`, millilitre unit, package text,
`salesPriceData.b2cPrice=16.27`, and comparison price `10.85 kr/lit`. This maps to one
fixed 1.5 litre package costing 16.27; the comparison price must never be mistaken for
the package price.

`groups=CUSTOMER_PRIVATE` denotes the anonymous/private B2C path and distinguishes
`b2cPrice` from `b2bPrice`. It is not membership evidence. Only explicit promotion
semantics such as `medMeraRequired` may set `member_only=true`.

Official ecommerce bundle inspected:

```text
https://www.coop.se/Assets/apps/coopse/dist/coopse.script.ecommerceApp.cca0bf7d.js
```

## Offers

### Physical-store offers

Manual discovery counted 89 rendered offer groups on the public Stora Coop Lund page
for week 34. That count was **not** exposed as an unambiguous, machine-readable source
total and is not used as a completeness contract by the live transport. The page
rendered:

- product/group name, brand and origin;
- package size or size range;
- fixed price, price per kg, or multibuy terms;
- `MEDLEMSPRIS` and ordinary offer labels;
- comparison price and unit;
- maximum quantity/uses per household where applicable;
- current and upcoming flyer links.

Examples included fixed-package, sold-by-weight, and multibuy offers. A `Se N varor`
dialog expands the named variants in a grouped offer. The expanded cards did not expose
GTIN links in the inspected DOM, so a grouped physical-store offer must not be promoted
to an exact SKU until it can be joined safely to catalogue products.

Official flyer sources verified include:

```text
https://dr.coop.se/Butik/Stora-Coop-Lund
https://dr.coop.se/Butik/216526/period/{period-id}/erbjudanden
```

The second pattern was observed for Coop Värpinge Lund. The numeric flyer ID must be
stored in its own namespace; it is not proven identical to `storeID` or
`ledgerAccountNumber`.

### Implemented `OFFERS_ONLY` browser capture

The operational transport launches one fresh ordinary headless Chromium process for
one requested physical-store page and closes it after capture. It:

1. stops on HTTP errors, CAPTCHA, Human Verification, access-denied, or WAF markers;
2. verifies that the final same-origin URL and visible `h1` still identify the
   requested seeded store;
3. extracts only public product links and accessible price labels from semantic
   product cards;
4. persists a sanitized JSON envelope containing the store ID/path, captured count,
   capture evidence, safe links, and labels — never cookies, browser storage, request
   headers, subscription values, or session identifiers.

The verified live offer page did not expose a usable source-declared total. Capture
therefore used `capture_evidence = "dom_stable"`: the same non-empty safe card set had
to remain unchanged over repeated observations before it could be accepted. If a
future page exposes one unambiguous declared total, the transport instead requires an
exact count match and fails closed on any short or excess capture. DOM stability is
evidence that the rendered offer surface stopped changing; it is not evidence of a
full store catalogue.

### Online promotions

The official ecommerce bundle constructs, and anonymous public requests verified:

```text
POST /search/products/promotions
POST /search/products/promotion
```

with online context and B2C customer-group context. The full current promotion-list
sample for `730400` reconciled **972/972 unique products** over 20 pages and contained
996 embedded promotions:

- 749 `MULTI_BUY_FIXED_PRICE` promotions, including 57 explicitly member-only;
- 242 `FIXED_PRICE` promotions, including 10 explicitly member-only;
- 5 `PERCENTAGE_DISCOUNT` promotions.

Expected structured fields include:

- `id`, `message`, `numberOfProductRequired`;
- `priceData`, `piecePriceData`, `comparativePrice`;
- `medMeraRequired`;
- `maxNumberOfUseWithUnit`;
- `startDate`, `endDate`;
- `higherThanHistoricalPrice`.

A verified fixed-price fixture is Sojasås Sesam (`7300156601421`, 250 ml): base price
28.35 and active promotion price 19.90. A verified public multibuy example has
quantity 2 and bundle price 29. Member-only multibuy rows are identified only by
explicit `medMeraRequired=true`; `CUSTOMER_PRIVATE` alone never marks membership.
Percentage rows preserve their explicit discount. Promotion start/end and maximum-use
fields are retained when present rather than inferred.

These routes were first verified as bounded discovery measurements and then included in
the accepted full catalogue. The promoted snapshot contains 1,003 normalized
promotions with explicit public/member/multibuy/percentage semantics and validity;
membership is never inferred from `CUSTOMER_PRIVATE`.

## Price and quantity semantics

Required invariants for the Coop parser:

1. `piecePriceData`/sale price, comparison price, promotion price, and historical price
   are distinct fields.
2. A comparison price can never create a package size.
3. `MULTI_BUY_FIXED_PRICE` must retain required quantity and bundle price.
4. `medMeraRequired` must be retained as member-only, not treated as a public effective
   price.
5. `displayWeightPrice`, sale unit, `pieceWeight`, and package size must determine
   `FIXED_PACKAGE`, `SOLD_BY_WEIGHT`, `SOLD_BY_PIECE`, or variable-weight behaviour.
6. Ambiguous offer ranges such as `500-2200 g` remain group metadata until an exact
   variant is selected.
7. JSON-LD `InStock` is an online fulfilment signal and is not verified physical shelf
   inventory.

## Implemented raw capture and replay boundary

The physical-offers connector saves before parsing:

- allow-listed, sanitized store-detail evidence containing the public
  `StorePageType`/store JSON needed for replay;
- the sanitized rendered-offer envelope described above;
- URL without query, status, content type, fetch time, payload hash, connector version,
  store identity, and parser version through the shared raw-first pipeline.

It does **not** save the complete browser page, cookies, request headers, browser
storage, public client runtime values, authorization values, route/session state, or
tracking identifiers. The online-catalogue candidate applies the same raw-first rule
to separate sanitized request types: category tree, product search, category page,
product by-id, promotion list/detail, and fulfilment mapping. Only response bodies and
non-sensitive lineage metadata may enter raw storage.

Offline tests save rendered offer and sanitized structured product/promotion/context
payloads and replay parser plus normalizer with `network_requests = 0`. Two
isolated live physical-offer collections were then replayed to parser v2 with exact
normalized equality and promoted atomically: Lund retained 322/322 rows and Malmö
494/494 rows, with no additions, removals, price changes, parser failures, or new raw
payloads. The full online run persisted separate sanitized category-tree,
category-page, fulfilment, product, and promotion evidence and replayed 11,175 products
exactly with zero network requests. Database acceptance tests verify broken candidate,
quarantine/rejection, unchanged last-known-good, connector-local parser repair,
zero-network replay, and subsequent atomic promotion for the full-catalogue path.

## Operational consumer strategy

The explicit chain strategy is:

```text
COOP catalogue primary:  OWN / CATALOG (Coop Online Syd 730400)
COOP own offer source:   OWN / OFFERS
COOP catalogue fallback: PRIMAT / licensed (explicit policy only)
```

There is no silent source mixing or fallback. The online context is eligible only while
its `FULL_ONLINE_CATALOG` snapshot is promoted, healthy, fresh, and linked through exact
geographic evidence. Every selected row retains provider, channel, context, snapshot,
observation time, coverage, and confidence. Physical-store offer observations remain
offers-only and never create duplicate basket contexts. Primat can be selected only by
the central explicit fallback policy and is then marked as fallback provenance.

## Coverage limitations and risks

- The offers connector enumerates a verified 7-Lund/13-Malmö bootstrap list; the
  independent physical-store coverage adapter uses the bounded public locator.
- Physical store pages expose offers, not a complete shelf catalogue.
- The online catalogue represents a fulfilment store/route selected through delivery
  context; it may not equal the nearest physical store.
- Multiple Coop store ID namespaces are present and must not be guessed across.
- The structured paths are public frontend implementation contracts, not documented
  partner APIs; runtime client values must remain transient and secret-free raw data
  is mandatory.
- Member, personalized, and logged-in-only offers are not fully visible anonymously.
- Offer groups may represent many SKUs and package ranges.
- Online availability is not proven to equal physical shelf stock.
- Frontend paths and raw field names are unversioned implementation contracts.
- The configured page size and rendered page size differed in discovery; pagination
  must be response-driven.
- Only context `730400` is accepted as full OWN online catalogue in this milestone;
  physical stores without an exact pickup relation do not inherit it.

## Implemented low-volume canary

Run explicitly; normal pytest remains offline:

```powershell
python -m grocery_data canary coop --city Lund
python -m grocery_data canary coop --city Malmö
```

The current canary performs the operational `OFFERS_ONLY` path:

1. GET every seeded public store-detail path for the requested city and save only the
   sanitized replay evidence;
2. parse and deduplicate the current `StorePageType` records;
3. select the first store whose public offer page is enabled;
4. launch a fresh ordinary Chromium session, verify store URL/heading, stop on access
   challenge, and wait for exact-total or DOM-stability evidence;
5. persist and offline-parse the sanitized offer-card envelope;
6. report stores, parsed/quarantined rows, request count, parse-success rate, the 95%
   parser threshold, and pass/fail. Empty output or parser health below 95% fails.

It does **not** execute the dynamic store locator, select an online fulfilment context,
fetch search/product-detail pages, prove GTIN coverage, traverse catalogue pagination,
or promote a production snapshot. Those checks belong to the separate reviewed online-
catalogue collector and must not be inferred from a green physical-offers canary.

## HOW TO FIX A BROKEN COOP CONNECTOR

1. Identify whether the failing channel is physical offers or online catalogue. Run the
   bounded `OFFERS_ONLY` canary only for a physical-offers failure; never use its green
   result as evidence that context `730400` is healthy.
2. Inspect connector health, request counts, HTTP status distribution, product counts,
   and the active snapshot age.
3. Compare the new sitemap/HTML/JSON-LD schema fingerprints with the latest known-good
   run.
4. Inspect a small sanitized failure sample. For catalogue failures compare category
   tree, category page, product, promotion, and fulfilment fingerprints; for offers
   compare seeded store pages, store-context validation, DOM stability, and offer cards.
5. Locate the saved raw payload by lineage ID; do not make a new live request merely
   to debug a parser.
6. Add the changed sanitized raw record as a Coop-local golden fixture.
7. Modify only `connectors/coop/` where possible. Do not add Coop field names to the
   shared normalizer or optimizer.
8. Run Coop store, offer-card, quantity, promotion, completeness-envelope, challenge,
   and schema-failure tests offline.
9. Replay the affected saved source evidence with network and browser disabled; confirm
   zero requests and unchanged normalized product, price, quantity, and promotion
   semantics.
10. For the full catalogue, require 748/748 accepted categories and response-driven
    pagination with zero unresolved conflicts, then re-run quality, 48-ingredient, and
    13-item basket gates. For physical offers, validate only the declared
    `OFFERS_ONLY` boundary.
11. Promote atomically only if health gates pass; otherwise retain last-known-good and
    expose degraded/stale status.
12. Verify generic API and `OwnGroceryPriceProvider` lineage. Activate the catalogue
    channel only for a healthy promoted `FULL_ONLINE_CATALOG` snapshot; otherwise retain
    its LKG or use only an explicitly configured fallback.
