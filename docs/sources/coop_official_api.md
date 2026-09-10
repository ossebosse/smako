# Coop official API and partner-path discovery

Last verified: **2026-08-25**

## Scope and safety boundary

This report covers only information exposed anonymously by official Coop-owned public
pages, their public frontend assets, and anonymous responses used by the normal public
shopping flow. No account was created, no sign-in or CAPTCHA was attempted, and no
credential, cookie, authorization value, CSRF value, browser/session state, or tracking
identity was copied or retained. Public frontend runtime configuration used to
reproduce anonymous requests was resolved transiently and was not logged, documented,
persisted, or written to fixtures/raw data.

The goal was to answer three questions:

1. Does Coop operate an official API catalogue?
2. Are API products, descriptions, and external/partner onboarding publicly documented?
3. Do Coop's public ecommerce assets confirm structured catalogue and fulfilment APIs?

## Executive conclusion

| Question | Result | Confidence |
| --- | --- | --- |
| Official Coop API portal exists | Yes: `portal.api.coop.se` identifies itself as **Coop API Catalog** | Verified |
| Platform type | Microsoft Azure API Management developer portal | Verified from public page metadata/runtime |
| Anonymous API catalogue | Empty: the public portal management endpoint returned `count = 0` | Verified |
| Anonymous API products | Empty: the public portal management endpoint returned `count = 0` | Verified |
| Public API/product descriptions | None found anonymously | Verified for the anonymous view; authenticated content unknown |
| Public sign-in | Azure Active Directory sign-in is shown | Verified |
| Public signup route | A generic signup page exists and requires a CAPTCHA | Verified; signup was not attempted |
| External API-partner onboarding | No API-specific eligibility, approval, entitlement, or application process was found | Unknown/not publicly documented |
| Public supplier onboarding | Yes, through Coop Supplier Network | Verified, but this is supplier onboarding rather than API-consumer onboarding |
| Dedicated API-platform contact | None found on the public API portal | Unknown |
| Public ecommerce uses structured APIs | Yes: product search/by-id, category tree/category products, promotions, and point-of-service paths | Verified from anonymous public responses and Coop's frontend assets |
| Those frontend APIs are an approved external contract | No such permission or contract was found | Not verified |

The official portal is therefore a **promising formal-contact lead**, not a currently
usable public grocery-data API. Separately, the normal anonymous shopping frontend has
now passed the project's reviewed full-catalogue acceptance: 748 terminal categories,
822 pages, 12,380 raw category rows, and 11,175 unique products were collected for
online context `730400`, replayed with zero network requests, quality-scored, and
atomically promoted as snapshot `851d317e88ce422b90d80d26ca1ebb2b`. This changes the
operational classification to Result A, OWN `FULL_ONLINE_CATALOG`, while
Primat/licensed data remains an explicit fallback. It does **not** turn the frontend
routes into a supported external-partner API or prove physical shelf prices.

## Official Coop API Catalog

Public entry points:

```text
GET https://portal.api.coop.se/
GET https://portal.api.coop.se/apis
GET https://portal.api.coop.se/products
GET https://portal.api.coop.se/signin
GET https://portal.api.coop.se/signup
```

The public HTML identifies the site as **Coop API Catalog**, describes it as a place to
discover APIs, and names the author as `Coop API Platform Team`. The implementation is
the Azure API Management developer portal: the public API and product pages use the
standard APIM API/product-list runtime components.

### Anonymous catalogue result

The same-origin endpoints used by the public portal were called anonymously, without
cookies or authorization:

```text
GET /mapi/products?api-version=2023-03-01-preview&$top=50&$skip=0
=> HTTP 200, { "value": [], "count": 0 }

GET /mapi/apis?api-version=2023-03-01-preview&$top=50&$skip=0&skipWorkspaces=true
=> HTTP 200, { "value": [], "count": 0 }
```

This proves only that **no API products or APIs are published to the anonymous portal
audience at verification time**. It does not prove that the authenticated catalogue is
empty.

No public product name, description, API operation, schema, scope, quota, price,
subscription policy, SLA, or usage terms could therefore be recorded.

### Sign-in and signup

The public sign-in page offers Azure Active Directory sign-in. The separate public
`/signup` route contains the standard APIM signup runtime and declares CAPTCHA as
required. The signup flow was deliberately not executed.

The existence of that generic page is **not** evidence that an arbitrary external
company will be approved, receive a subscription, or see Coop's authenticated products.
No API-specific onboarding instructions, approval criteria, external-partner terms, or
API-platform contact details were found on the portal.

The portal sitemap also lists generic APIM routes such as `/product`, `/api-details`,
`/signup-oauth`, `/profile`, and `/reports`. Route presence is template evidence, not
evidence that Coop publishes a particular API product.

## Public Coop ecommerce frontend evidence

The current public online-shopping page loaded this Coop-owned, content-hashed asset
during the 2026-08-25 verification:

```text
https://www.coop.se/Assets/apps/coopse/dist/coopse.script.ecommerceApp.cca0bf7d.js
```

The public `/handla/` configuration and that asset expose host/path/version names for
structured services. Only host/path/version and sanitized response evidence was
retained. No public client runtime value was written to documentation, logs, fixtures,
or raw data.

### Verified service references

| Surface | Public host/base reference | Observed public path references |
| --- | --- | --- |
| Ecommerce | `https://external.api.coop.se/ecommerce` | `/coop/users/anonymous/categories/tree/{context}`, `/coop/pointofservice/{pickupPointId}`, delivery/fulfilment paths |
| Personalization/search | `https://external.api.coop.se/personalization`, API version `v1` | `/search/products`, `/search/entities/by-id`, `/search/entities/by-attribute`, `/search/products/promotion`, `/search/products/promotions` |
| Physical-store discovery | `https://proxy.api.coop.se/external/store/` | store lookup used by the public store frontend |

The asset also contains explicit pickup, delivery, store, product, category, and
promotion logic. It does not expose a single literal `catalog` endpoint; the public
catalogue surface is assembled from search/category/product services and a selected
delivery or pickup context.

These references are consistent with the browser findings in `docs/sources/coop.md`:
catalogue membership changes with fulfilment context, and structured product searches
require a selected online context. They are now backed by bounded anonymous response
verification rather than bundle strings alone.

This evidence does **not** establish that:

- the frontend services are licensed for independent collection;
- frontend client configuration may be reused outside Coop's site;
- an API Catalog account grants access to these particular services;
- a partner API offers full catalogue enumeration or physical-store prices;
- frontend paths are stable, supported partner contracts.

The accepted collector uses these normal public shopping requests under the project's
review policy. This does not turn the paths into a supported partner API; production
activation still requires every full-catalogue acceptance gate for each candidate.

### Bounded anonymous response verification

The 2026-08-25 verification established these source facts without login or user
session state:

- Online price/assortment context `730400` is distinct from physical-store identity.
  The public point-of-service response links Stora Coop Lund pickup point `257611` to
  `730400`.
- Coop Hjärup and verified Malmö pickup points also use `730400`; a Stockholm control
  uses distinct context `256600`. The safe interpretation is a regional/online context,
  not a shelf-price identity for any one physical store.
- A `mjölk` search using normal offset pagination reconciled 290/290 products over 13
  pages, with zero duplicates, conflicts, or missing rows.
- The raw context-specific category tree contained 24 roots. Exact fail-closed
  handling excludes two non-category root sentinels and collapses one exact duplicate
  leaf, leaving 748 accepted terminal categories.
- Root category `Mejeri & ägg` reconciled 786/786 products over 17 pages with no
  duplicates, conflicts, or missing rows.
- Ten product-by-id samples had exact basket-relevant parity with their search rows.
- Stable product `id` and separately exposed `ean`, structured package/sales units,
  normal/promotion/comparison prices, availability, ingredients, and nutrition are
  present in the rich product response.
- The accepted catalogue union persisted 1,003 normalized promotions across 979
  products: 748 multibuy, 240 public sale-price, 10 member-price, and 5 percentage-
  discount rows. Explicit `medMeraRequired`, not `CUSTOMER_PRIVATE`, determines
  membership.

The reviewed full traversal completed all 748 accepted terminal categories and 822
pages. It reconciled 12,380 raw rows to 11,175 unique products with 1,205 safe cross-
category overlaps and zero unresolved conflicts. Price coverage was 100.00%, valid
GTIN 99.50%, package quantity 99.20%, and resolved purchase model 99.28%. Recipe
coverage >=1/>=3/>=5 was 48/48, 45/48, and 39/48; the representative basket was 13/13.
Exact replay made zero network requests, and failure/LKG/repair plus atomic promotion
passed before Result A was activated.

## Public supplier and partner routes

### Coop Supplier Network

Coop publicly documents a supplier application through
`https://suppliernetwork.coop.se/`. It states that approved suppliers can manage
article/price notifications and campaigns and access assortment and store lists.
Public support routes include:

- the supplier application/support site;
- `cooplevsupport@coop.se`;
- the public supplier support telephone and service portal listed in its guidelines.

This is a real external onboarding path, but its stated purpose is onboarding companies
that supply products or services to Coop. It is **not publicly described as onboarding
an API consumer, price-data licensee, comparison service, or grocery-catalogue partner**.
It should be used only to ask Coop to route a formal enquiry to the correct API,
ecommerce/B2B, or data-partnership owner.

### Evidence that formal technical partnerships exist

Coop's official 2025 Wolt announcement says their framework agreement expands a
technical integration that automates product-price and availability updates. This
verifies that Coop supports at least some negotiated partner data integrations.

It does not identify the Coop API Catalog, publish an API schema, or provide a general
application route. The safe inference is only that a **formally agreed integration may
be possible**; self-service API access remains unverified.

### General contact fallback

Coop's public help centre provides a general request form. It can be used to ask for the
owner of API-platform, ecommerce/B2B, or product-data partnerships. It is not itself a
technical onboarding channel, and consumer support should not be treated as approval to
use an API.

## Verified, inferred, and unknown

### Verified

- Coop operates a public Azure APIM developer-portal shell.
- Anonymous `apis` and `products` queries return zero published records.
- The public portal exposes AAD sign-in and a CAPTCHA-protected generic signup route.
- Anonymous public responses verify product search/by-id, a context-specific category
  tree and category products, promotion pagination/semantics, and point-of-service
  identity.
- Online context `730400` is distinct from Stora Coop Lund pickup point `257611` and
  from the Stockholm control context `256600`.
- Coop Supplier Network has a public supplier application/support route.
- Coop has announced at least one negotiated partner integration for product prices and
  availability.

### Inferred, not proven

- The API portal is probably intended for provisioned internal or external identities,
  because it implements APIM products, subscriptions, profiles, and AAD authentication.
- A negotiated data partnership could plausibly expose product/price/availability data.
- Supplier support may be able to route a request to the relevant API/ecommerce owner.

These are inferences and must not be represented as access rights or technical
contracts.

### Unknown

- whether Coop accepts external API consumers that are not suppliers;
- who owns API/data-partner onboarding and how to contact that team directly;
- whether the authenticated portal publishes catalogue, store, price, promotion, or
  availability APIs;
- whether any partner API supports Lund/Malmö store-specific pricing;
- product/API descriptions, schemas, authentication method, entitlement scopes,
  licensing, rate limits, quotas, SLAs, cost, and test environment;
- whether partner product IDs/GTINs and fulfilment-store IDs align with the public
  ecommerce source.

## Recommended formal enquiry

Do not attempt to discover authenticated products by signing up automatically. A
human-reviewed enquiry should ask Coop to route it to the API Platform or
ecommerce/B2B data owner. The separate anonymous storefront collector must remain
bounded, raw-first, secret-free, and subject to its own source-policy and acceptance
gates.

The enquiry should ask:

1. Is external partner onboarding to Coop API Catalog available?
2. Is there a licensed API for product identity, GTIN, online assortment, store or
   fulfilment context, current price, comparison price, availability, and promotions?
3. Does it support store-specific Lund/Malmö data and complete pagination?
4. What authentication, approval, rate limits, data freshness, permitted storage,
   historical retention, redistribution, and commercial terms apply?
5. Is there a sandbox and a named technical/contract contact?

The API portal remains only a formal-access lead until Coop answers these questions.
The anonymous storefront source is separately accepted under the project's reviewed
public-source policy because the complete catalogue crawl, exact replay, quality
benchmark, health/LKG simulation, and atomic promotion all passed. Its accepted entity
is regional online context `730400` (**Coop Online Syd**), not a physical store. The
only activated Lund pickup relation is Stora Coop Lund physical store `2696` -> pickup
point `257611` -> context `730400`, and all prices are labelled online prices.

## Sources

- [Coop API Catalog home](https://portal.api.coop.se/)
- [Coop API Catalog APIs](https://portal.api.coop.se/apis)
- [Coop API Catalog products](https://portal.api.coop.se/products)
- [Coop API Catalog sign-in](https://portal.api.coop.se/signin)
- [Coop API Catalog signup](https://portal.api.coop.se/signup)
- [Coop online shopping](https://www.coop.se/handla/)
- [Coop Supplier Network](https://suppliernetwork.coop.se/)
- [Coop supplier guidelines](https://suppliernetwork.coop.se/knowledge-bank/guidelines-for-suppliers)
- [Coop general support request](https://kundservice.coop.se/hc/sv/requests/new)
- [Coop/Wolt technical-integration announcement](https://pressrum.coop.se/wolt-ny-partner-till-coop-sverige-ska-starka-lokala-samarbetet/)
