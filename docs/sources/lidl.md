# Lidl Sverige — source discovery

**Chain:** Lidl  
**Country/locale:** Sverige, `sv_SE` / `SE`  
**Last verified:** 2026-08-23  
**Recommended `CoverageLevel`:** `OFFERS_ONLY`  
**Discovery confidence:** high for the sources and response fields described as verified; low/unknown for store-specific price resolution and full-catalog coverage.
**Source policy:** `ALLOW` for the unauthenticated public store pages and product-search endpoint used by this connector.

## Executive summary

Lidls official Swedish site exposes three useful public source surfaces:

1. server-rendered store-locator pages and an official store sitemap;
2. a public product-search JSON endpoint used by Lidl's own frontend;
3. product detail pages containing JSON-LD and Nuxt hydration JSON.

The public product surface is **not a complete local store catalog**. At verification time, the unfiltered public product search exposed 421 current-or-upcoming published product/offer rows, while the product sitemap exposed 520 product-detail URLs in the earlier discovery. The latter also contains products that are not necessarily currently active. Public product cards consistently exposed in-store campaign windows in the inspected samples. A normal Lidl store carries materially more products than this public publishing set, and no public full per-store assortment was found.

The priced dataset must therefore be reported as `OFFERS_ONLY`, not `FULL_CATALOG`. The product sitemap can supplement identity and descriptive metadata, but it must not be treated as proof that a product is currently available or priced in a selected store.

No login, CAPTCHA, access-control bypass, private mobile API, or personalized Lidl Plus data was used. Public personalized coupons behind login are out of scope.

### Policy review

`robots.txt` and the public pages relevant to this connector were reviewed on 2026-08-23. No rule disallowing `/q/api/search` was found; the only related rule observed was the narrower `/q/search?id=*` pattern, which this connector does not use. No separate general website term applicable to this unauthenticated offer/search collection was found in the reviewed public navigation. Account and Lidl Plus membership terms do not grant or govern this connector because it never logs in or consumes personalized coupons. The policy decision is therefore `ALLOW`, subject to the technical stop rules below. This is an engineering policy classification, not legal advice.

## Implemented connector and operational result

`connectors/lidl/` implements a raw-first `OFFERS_ONLY` connector with separate transport and parser. The operational collection identity is deliberately a single source-truthful context:

- external ID: `public-default-region`;
- label: `Lidl Sverige – publika erbjudanden (standardregion)`;
- context type: `REGIONAL`;
- price region: public default region `1`;
- physical-store price verified: `false`.

Lund and Malmö canaries discover physical stores, but the public offer prices are never assigned to those physical identities. The daily collector runs the single national context once, so two city-scoped runs cannot overwrite one another under the same source identity.

The low-rate live collection on 2026-08-23 produced:

| Metric | Result |
|---|---:|
| Declared public rows | 421 |
| Raw rows / unique IDs / duplicates | 421 / 421 / 0 |
| Pages | 9 / 9 |
| Requests | 10: one context probe plus nine offer pages |
| HTTP errors / 429 / access challenges | 0 / 0 / 0 |
| Runtime | 13.235 s |
| Raw payloads / bytes | 10 / 3,044,486 |
| Parsed / quarantined | 421 / 0 |
| Price observations | 421 |
| Source rows with an unconditional sale price | 408 / 421 |
| Public Lidl Plus member-price rows | 37 |
| Comparison-price coverage | 220 / 421 |
| Explicit `gridbox.meta.ean` values | 277 / 421 |
| Checksum-valid GTIN coverage | 260 / 421 = 61.76% |
| Source package-quantity coverage | 233 / 421 = 55.34% |
| Resolved purchase models | 266 / 421 = 63.18% |
| Unknown purchase model | 155 / 421 = 36.82% |

The 421 promotion-lineage rows were classified as 37 member prices, 16 multibuys (three member-only), 51 percent discounts, 35 typed sale prices and 282 `OTHER`. `OTHER` is intentional: publication in the public product surface without an old price, discount or member signal is not fabricated into a sale-price claim.

Offline replay reproduced 421 products, 421 price observations and the same promotion distribution with zero network requests and zero browser launches. A parser-local v2 replay then added only checksum-valid identities from the explicitly named `gridbox.meta.ean` field: 277 raw values yielded 260 valid GTINs (49 GTIN-8 and 211 GTIN-13). The internal `productId` and `erpNumber` were never used as GTIN. Product, price and promotion projections otherwise remained identical as multisets. The healthy v2 replay was promoted and records the original live v1 snapshot as its previous active snapshot. The connector-local acceptance fixture also proves schema-break rejection, preservation of last-known-good and repair by replay without network.

## Coverage matrix

| Capability | Coverage | Evidence / limitation |
|---|---|---|
| Store discovery | Yes | Official sitemap, city pages and store detail pages |
| Lund stores | Yes | 2 stores on the official Lund page |
| Malmö stores | Yes, with geographic caveat | 7 stores under the Malmö slug; Limhamn is a separate official city slug and must be included by the Lund/Malmö geography policy when appropriate |
| Full local catalog | No | No complete per-store assortment found |
| Public active product/offers set | Yes | `/q/search` and `/q/api/search` |
| Product details | Partial | Public product pages; only products with public pages |
| Product ID | Yes | `productId`, `erpNumber`, URL suffix `p<ID>` |
| GTIN/EAN | Partial | Public search has explicit `gridbox.meta.ean`: 277 / 421 raw, 260 checksum-valid; product detail JSON can additionally expose `eans`/JSON-LD `gtin13`. Numeric product IDs are never guessed as GTIN |
| Brand | Sometimes | `brand.name`; may be empty |
| Category | Yes for inspected products | `category`, `keyfacts.analyticsCategory`, `wonCategoryPrimaryPath` |
| Package metadata | Partial | Structured/textual fields exist, but parsing must remain conservative |
| Price | Yes for published active products | National/region-context response; exact store-level semantics not proven |
| Regular/old price | Sometimes | `price.oldPrice`, visible crossed-out value |
| Public Lidl Plus price | Sometimes | Public Lidl Plus campaign fields/labels; not personalized coupons |
| Multipack | Sometimes | `multipack` indicator plus display text such as `2 for`; retain the original rule rather than flattening blindly |
| Comparison price | Sometimes | Visible comparison-price text; not consistently observed as a dedicated numeric field |
| Campaign period | Yes for inspected published products | `storeStartDate`, `storeEndDate`, badges; product detail region price contains start/end timestamps |
| Reliable stock availability | No | Campaign/in-store window is not a stock-on-hand guarantee |
| Historical prices | Not supplied as history | Must be built from daily observations |

## Store discovery source

### Recommended primary source

**Request:** `GET https://www.lidl.se/s/sv-SE/butiker/sitemap.xml`  
**Response:** XML sitemap  
**Authentication:** none  
**Pagination:** none

The sitemap contains official city-index and store-detail URLs. It is preferable for rediscovery because it avoids maintaining a hand-written seed list.

Relevant verified pages:

- [all Swedish stores](https://www.lidl.se/s/sv-SE/butiker/)
- [Lund](https://www.lidl.se/s/sv-SE/butiker/lund/)
- [Malmö](https://www.lidl.se/s/sv-SE/butiker/malmoe/)
- [Limhamn](https://www.lidl.se/s/sv-SE/butiker/limhamn/hyllie-kyrkovaeg-45a/)

At verification time:

- Lund's official city page listed 2 stores.
- Malmö's official city page listed 7 stores.
- the official locator grouped the Hyllie Kyrkoväg 45A store under `limhamn`, not `malmoe`.

The sanitized 2026-08-23 canary evidence yielded these physical identities. `TNC` is retained with `id_stability=inferred`, and none of these identities receives the default-region offer price:

| City | External ID | Address | Postal code | Coordinates |
|---|---:|---|---:|---|
| Lund | 0163 | Magistratsvägen 6 | 22643 | 55.72050, 13.20542 |
| Lund | 0303 | Åkerlund och Rausings väg 1 | 22730 | 55.69938, 13.17783 |
| Malmö | 0167 | Delsjögatan 3 | 21765 | 55.57914, 12.97870 |
| Malmö | 0153 | Knivgatan 1B | 21228 | 55.60040, 13.03812 |
| Malmö | 0340 | Östergatan 12 | 21125 | 55.60710, 13.00632 |
| Malmö | 0145 | Södra Förstadsgatan 124 | 21428 | 55.58650, 13.00627 |
| Malmö | 0284 | Spångatan 11 | 21144 | 55.59632, 13.00554 |
| Malmö | 0314 | Torupsgatan 2 | 21773 | 55.59319, 12.96624 |
| Malmö | 0330 | Västra Varvsgatan 42 | 21115 | 55.61366, 12.97675 |

Consequently, municipality/urban-area scope must be applied using address, postal code and preferably coordinates, not only the locator's city slug.

### Store detail source

**Request:** `GET https://www.lidl.se/s/sv-SE/butiker/{city-slug}/{address-slug}/`  
**Response:** server-rendered HTML  
**Authentication:** none

Verified fields on a Lund store page:

- name/chain;
- street address, postal code and city;
- latitude/longitude in the official directions link;
- services;
- nearby stores;
- a store number in the official feedback URL's `TNC` parameter.

The `TNC` value is a strong candidate for `external_store_id`, but its stability is not publicly documented. Mark this interpretation as **inferred** until it has been compared across multiple runs or with another official Lidl field. The canonical detail URL is a useful lineage field, but a URL slug alone should not silently replace an external store ID.

### Store frontend JSON

The public store-search frontend references Lidl's structured stores service and obtains configuration with a client-side `x-apikey`. The credential value is intentionally **not copied into this repository or report**. The Phase 1 implementation should use the official sitemap/HTML path unless use of the structured store endpoint has been explicitly reviewed against Lidl's terms and credential-handling policy.

## Catalog and product discovery sources

### Current public product/offers set

**Page request:** `GET https://www.lidl.se/q/search`  
**Search request:** `GET https://www.lidl.se/q/search?q={query}`  
**Response:** server-rendered HTML with structured `#__NUXT_DATA__` JSON  
**Authentication:** none

The page can be parsed offline from the raw HTML. The Nuxt hydration payload contains the same product-grid model used by the UI, so HTML selectors should be a fallback rather than the primary parser.

An unfiltered request exposed 421 products at verification time. Product cards showed active or future in-store date windows in the inspected sample. This count must be monitored as a publishing/offers count, not as a store assortment count.

### Frontend JSON endpoint

**Verified request method:** `GET`  
**Endpoint:** `https://www.lidl.se/q/api/search`  
**Observed response content type:** `application/mindshift.search+json; version=2`  
**Authentication:** none observed for product search

Verified/reconstructed query parameters used by the frontend include:

- `q` — optional search query;
- `fetchsize` — frontend default 48;
- `offset` — zero-based result offset;
- `locale=sv_SE`;
- `assortment=SE`;
- `version=2.1.0` at verification time;
- filter/sort parameters from the route;
- optional campaign/category parameters.

The response contains:

- `numFound`, `offset`, `fetchsize`, `maxfetchsize`;
- `sort`, `sorts`, `facets`;
- `items`;
- breadcrumbs, teasers and advisors.

Each result item contains a `gridbox.data` product record. Important observed fields include:

- `productId`, `erpNumber`, `itemId`, `productType`;
- `gridbox.meta.ean`, an explicit EAN value that still requires checksum validation;
- `title`, `fullTitle`, `keyfacts`;
- `brand`;
- `canonicalPath`, `canonicalUrl`, `category`;
- `price`, `regionsPrices`;
- `lidlPlus`, `multipack`;
- `stockAvailability`, `storeStartDate`, `storeEndDate`;
- `productOrigin`, `gs1Attributes`, media and seals.

The endpoint performs media-type negotiation. A test that forced `Accept: application/json` returned HTTP 406, while a request preserving normal public-page negotiation returned HTTP 200 with the vendor JSON media type. The connector must capture the exact canary contract and must not assume generic JSON negotiation. A future 406 is a connector-health failure, not a signal to disguise the client or bypass a control.

### Supplemental product sitemap

**Request:** `GET https://www.lidl.se/p/export/SE/sv/product_sitemap.xml.gz`  
**Response:** gzip-compressed XML sitemap  
**Authentication:** none  
**Pagination:** none

The product sitemap contained 520 product-detail URLs at verification time. It is useful for discovering public product pages that may not be present in the current active search result, but it includes records that can be inactive or historical. Never infer current availability, current price or store coverage from sitemap presence.

### Product detail pages

**Request:** `GET https://www.lidl.se/p/{slug}/p{product_id}`  
**Response:** HTML plus JSON-LD and `#__NUXT_DATA__`  
**Authentication:** none

Verified structured fields include:

- JSON-LD: `sku`, sometimes `gtin13`, `name`, `description`, image, offer price/currency and broad `InStoreOnly` availability;
- Nuxt data: `erpNumber`, `eans`, category paths, descriptive fields, price model, region price model, campaign periods, package/base-price text and availability badges.

One inspected variable-weight chicken product represented `99 kr/kg (Ca 925 g)`. This is specifically **not** a fixed 925 g package price. Lidl parsing must preserve the source text and feed it through the shared sale-model/quantity-confidence rules.

## Additional frontend routes found in official code

The official storefront bundle defines these structured routes:

- `GET /q/api/search`
- `GET /q/api/category/{category-name}/{category-id}`
- `GET /q/api/brand/{brand}`
- `GET /q/api/query/{query-id}`
- `GET /q/api/gridboxes/...`

Only `/q/api/search` was called directly during this discovery. The other routes are **verified from Lidl's current public frontend code but not live-contract-tested** and must be covered by canaries before use.

## Pagination

The search frontend uses offset pagination:

- default `fetchsize`: 48;
- current offset: `offset`;
- total: `numFound`;
- continuation: increase `offset` until fetched records reach `numFound` or the response no longer advances.

The UI labels this as “Visa fler produkter”. The current broad public search showed 48 initially and 96 after one normal “Visa fler” interaction, with 421 declared in total. Direct traversal at the frontend's default page size reconciled all 421 unique IDs in nine pages. A separate safe page-size experiment also reconciled all 421 IDs as `108 + 108 + 108 + 97`.

Required safety checks:

- reject repeated offsets or duplicate pages;
- cap total pages and runtime;
- stop and degrade health when `numFound` collapses materially;
- preserve each raw page independently before parsing;
- do not transform comparison-price text into a package quantity.

## Store context and price locality

The official product frontend supports optional request headers:

- `x-ms-zone`
- `x-ms-warehouse`

They are sent when the selected store context supplies zone/warehouse values. Product data also contains `regions`, `regionsV2`, `zones` and `regionsPrices`.

What is verified:

- the fields and optional headers exist in Lidl's current public frontend code;
- a product can contain multiple region definitions and region-price records;
- the no-store-context page chooses a default region.

What is **not** verified:

- that every individual Lidl store has a distinct price;
- how every public store ID maps to zone/warehouse;
- whether Lund and Malmö resolve to the same or different price regions;
- whether the public response is complete for a selected store.

Until this mapping is verified end-to-end, prices must be labelled national/regional public offer prices, not exact store-specific prices. Do not claim “Lidl Lund full catalog” from the default response.

## Price and promotion semantics

Observed price-related fields/signals:

- `price.price` — displayed current/campaign amount;
- `price.oldPrice` and `discount` — regular/previous price signal when present;
- `price.packaging.text` or product-detail base-price text — package/sale-unit display;
- `regionsPrices[region].currentPrice` — region-scoped current price with start/end timestamps;
- `futureLidlPlusPrices` / `lidlPlus` — public member campaigns;
- `multipack` plus display text such as `2 for`;
- visible comparison-price text, for example `8,60 kr/l`.

Parsing rules:

- preserve regular, campaign, public-member and multibuy values separately;
- never divide a multibuy total into a unit sale price in the source model;
- never infer a package size from a comparison price;
- retain raw package/base-price text and attach parser confidence;
- treat a price with `/kg` plus an approximate weight as sold/variable by weight unless stronger source metadata proves a fixed package;
- parse public Lidl Plus campaign prices without login, but exclude personalized coupons;
- treat campaign-window availability as publication/offer availability, not inventory.

## Known limitations

1. The public priced product set is not a full store assortment.
2. Exact store-level price mapping is not yet proven.
3. Product sitemap presence does not imply current availability.
4. Some quantity and comparison-price information is display text rather than strongly typed numeric metadata.
5. GTIN/EAN is available on some detail pages, but coverage is unknown and may require an extra product-detail request.
6. `TNC` as store ID is plausible but not documented as a public stable contract.
7. The JSON endpoint's media-type/version contract can change independently of the HTML route.
8. Availability badges indicate campaign windows, not shelf stock.
9. Personalized Lidl Plus offers require login and are intentionally excluded.
10. Public search results can contain food and non-food products; category filtering is mandatory.

## Connector-health and repair signals

The Lidl connector should fingerprint and monitor these independently:

- store sitemap XML shape and count;
- city/store-detail HTML selectors and `TNC`/coordinate extraction rates;
- product sitemap URL count;
- `/q/api/search` content type and top-level keys;
- `gridbox.data` key/type fingerprint;
- `numFound` for unfiltered public search;
- ratio of items with `productId`, name and price;
- ratio with campaign start/end;
- ratio with package text and GTIN;
- distribution of region IDs;
- HTTP 406, 429 and 5xx counts.

Suggested Lidl-specific break conditions:

- vendor content type changes without a compatible parser;
- `items` or `gridbox.data` disappears;
- unfiltered count drops by more than 70% against last known good;
- price coverage drops below the configured threshold;
- store sitemap or both Lund/Malmö city pages disappear;
- default-region selection changes unexpectedly;
- package fields change from string to object (or vice versa) without fixture coverage.

## Recommended implementation boundary

Implement Lidl as an isolated connector with two sub-sources:

1. `LidlStoreSource`: sitemap + official store HTML;
2. `LidlOfferSource`: `/q/api/search`, product pages and product sitemap.

The connector should expose `coverage=OFFERS_ONLY` and never return a complete-catalog flag. Store discovery can be complete for the geographic scope while product coverage remains offers-only.

Implemented raw snapshots:

- a closed one-row public default-region context probe for the national operational scope;
- sanitized Lund and Malmö city/store evidence for canaries;
- each JSON search page;
- representative offline fixtures for fixed package, sold by weight, variable weight, Lidl Plus, multibuy, percentage discount, untyped price and schema change.

All raw records must retain URL, request parameters, content type, fetched time and hash. Do not store cookies, client keys, session values or personalized data.

## Source transparency labels for the API

For Lidl records, return at least:

- `coverage: offers_only`;
- `price_scope: national | region | unknown`;
- `store_price_verified: false` until zone/warehouse mapping is proven;
- `availability_scope: campaign_window`, not stock;
- `source_url`, `raw_snapshot_id`, `observed_at`;
- parser and normalizer versions;
- semantic and quantity confidence.

This prevents Lidl's useful public offer data from being mistaken for the full local catalog required to replace Primat on its own.

## Official sources checked

- [Lidl Sweden](https://www.lidl.se/)
- [Store locator](https://www.lidl.se/s/sv-SE/butiker/)
- [Store sitemap](https://www.lidl.se/s/sv-SE/butiker/sitemap.xml)
- [Public product search](https://www.lidl.se/q/search)
- [Weekly leaflet/offers](https://www.lidl.se/c/reklamblad/s10018018)
- [Product sitemap index](https://www.lidl.se/static/sitemap.xml)
- [Product sitemap](https://www.lidl.se/p/export/SE/sv/product_sitemap.xml.gz)
- representative official campaign and product-detail pages reached from the current Lidl homepage/search.

`robots.txt` was checked on 2026-08-23. It did not disallow the observed `q` search/API paths (apart from a specific `/q/search?id=*` pattern). Under the project policy, robots is a policy signal rather than technical access control; this source remains `ALLOW` because no applicable disallow or access-control requirement was identified for the connector paths. Production collection remains low-rate and identifiable.

## Canary, collection and replay

Canaries are bounded to five products and do not promote snapshots:

```console
python -m grocery_data canary lidl --city Lund
python -m grocery_data canary lidl --city Malmö
```

The verified canaries found two physical Lund stores plus the separate regional context (`3` contexts total) and seven physical Malmö stores plus that same regional context (`8` total). Both parsed `5 / 5`, quarantined zero and reported `HEALTHY`. They made four and nine requests respectively because the physical store evidence is individually sanitized.

Operational collection must run only the national context:

```console
python -m grocery_data collect --chain lidl --city Sverige
```

Defaults are `LIDL_REQUESTS_PER_SECOND=1` and `LIDL_MAX_CONCURRENCY=1`. The connector stops the current run immediately on 401, 403, 405, 429 or a recognized CAPTCHA/WAF/access-challenge signature. It does not retry those responses and persists only an inert allowlisted diagnostic object, never challenge HTML, cookies, headers or browser state.

Replay is browser- and network-free:

```console
python -m grocery_data replay --chain lidl --snapshot-id <snapshot-id>
```

## How to fix a broken Lidl connector

1. Keep the current promoted snapshot active and inspect the candidate's sanitized raw payloads, schema fingerprint and pagination completion evidence.
2. If the response is an access challenge, leave collection stopped. Do not alter identity, cookies, headers or sessions to bypass it.
3. For an ordinary public schema change, add/update a sanitized golden fixture and repair only `connectors/lidl/` where possible.
4. Replay the rejected raw snapshot with networking and browser transport disabled.
5. Require exact declared-row reconciliation, stable page size, no duplicate ID, adequate parse/price health and zero quarantine before accepting the change.
6. Promote only after the local repair and generic acceptance suite pass; otherwise retain last-known-good.

## Final classification

`LIDL = OFFERS_ONLY`, `full_basket_capable = false`.

The public publishing set is useful as an OWN offers channel with complete pagination over that set, public/member/multibuy semantics and offline replay. It does not prove a permanent full assortment, exact Lund/Malmö store pricing, sufficient package coverage or representative-basket completeness. The basket strategy must therefore remain a licensed broad provider where available; OWN Lidl offer rows must never be silently promoted into a basket catalog.
