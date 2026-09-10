# Membership pricing capability matrix

Last audited: **2026-08-31**

This document records only capabilities demonstrated by approved sources,
promoted snapshots and the active closed provider cache. The audit refreshed
Willys and Hemköp Brunnshög through their existing approved production
collectors. It made no endpoint-discovery, reverse-engineering or retailer
account-login calls and did not test or infer retailer credentials.

The terms below are deliberately distinct:

- **generic member price**: a price explicitly published for every member of a
  named retailer programme;
- **personal offer**: an offer tied to one person's account, coupon or voucher;
- **shared PriceUniverse eligibility**: sufficiently identified source evidence
  that may be retained in the shared artifact and evaluated against a user's
  membership at request time.

`UNKNOWN` means that repository evidence does not establish the capability.
`NOT_VERIFIED` means that no approved official authorization flow has been
verified. `NOT_IMPLEMENTED` means that the application has no such connection.

## Verified chain matrix

| Chain | Generic member-price evidence in current approved sources | Shared PriceUniverse state at audit | Personal-offer relevance | Official account authorization investigated | Personal-offer integration |
| --- | --- | --- | --- | --- | --- |
| ICA | **YES, offers-only.** The promoted OWN offers snapshot contains 62 explicit Stammis contracts, of which 15 were valid on the audit date (11 unit prices and 4 multibuy). The active Primat cache contains 0 member contracts. | **NOT RETAINED — NO EXACT FULL-CATALOG IDENTITY.** None of the 15 current OWN offers had an exact GTIN match in the active Primat Gunnesbo cache, so none could safely be merged into the basket universe. | **UNKNOWN.** No approved personal-offer source was verified. | **NOT_VERIFIED.** No current official OAuth, OIDC, partner API or authorization redirect is established. | **NOT_IMPLEMENTED** |
| Coop | **YES.** The current OWN online context `730400` contains 82 explicit `medMeraRequired=true` contracts, of which 11 were valid on the audit date (8 unit prices and 3 member multibuy). | **RETAINED.** All 82 source contracts are preserved in the active shared artifact; request-time validity makes 11 eligible on the audit date. A separate physical-offers snapshot has 121 member rows, but all have unresolved offer-group product identity and remain outside optimizer pricing. | **UNKNOWN.** No approved personal-offer source was verified. | **UNKNOWN** | **NOT_IMPLEMENTED** |
| Hemköp | **YES.** OWN exposes explicit `campaignType=LOYALTY` / Klubbpris contracts. The current promoted Karhögstorg `4123` and refreshed Brunnshög `4224` snapshots contain 208 explicit generic-member candidates: 92 current and 116 expired. | **RETAINED PER EXACT CONTEXT.** All 208 are retained: 142 Karhögstorg contracts (26 current) and 66 Brunnshög contracts (66 current). Prices and validity are never collapsed across contexts. Retailer-native comparison units such as `tvätt` remain opaque provenance and are not used in kg/l/st arithmetic. | **UNKNOWN.** No approved personal-offer source was verified. | **UNKNOWN** | **NOT_IMPLEMENTED** |
| Lidl | **YES, regional offers-only, with exclusions.** The promoted source contains 41 Lidl Plus rows and 23 were valid on the audit date. Two rows in the snapshot, one current, are labelled `Kupong`; their activation/personal scope is not proven. Excluding those leaves 39 generic candidates in the snapshot and 22 current candidates (19 unit prices and 3 multibuy). | **NOT RETAINED — NO ELIGIBLE FULL-CATALOG CONTEXT.** Lidl OWN is an offers-only regional source and the active PriceUniverse has no exact Lidl full-catalog context. Coupon-labelled rows must not enter the generic member layer without stronger evidence. | **UNKNOWN / POTENTIALLY RELEVANT.** Coupon wording exists, but the audit does not prove whether it is generic, activated or personal. | **UNKNOWN** | **NOT_IMPLEMENTED** |
| Willys | **YES.** The approved refresh discovered 116 current source-local generic-member contracts after source deduplication. | **RETAINED FROM FRESH EXACT CONTEXTS.** The active shared artifact contains 58 current Willys Lund and 56 current Willys Lund Nova contracts. Of these, 37 + 37 are current member multibuy contracts. Two additional exact context rows remain source evidence only because both products are explicitly `out_of_stock`. | **UNKNOWN.** No approved personal-offer source was verified. | **UNKNOWN** | **NOT_IMPLEMENTED** |
| City Gross | **UNKNOWN.** The production database has no City Gross catalog snapshot. Parser support for a `membersOnly` field is not evidence of a current production contract. | **NOT AVAILABLE** | **UNKNOWN** | **UNKNOWN** | **NOT_IMPLEMENTED** |

## Audit boundaries

After the approved Willys and Brunnshög refreshes, the one shared active
PriceUniverse contains **42,653** source product/context rows, **2,290**
optimizer products over seven exact contexts, and **47,360** unique normalized
price contracts. It retains **404** generic member contracts: 82 Coop, 208
Hemköp and 114 Willys. On the audit date **217** are current and 187 expired.
There are 182 retained member-multibuy contracts, of which 87 are current. No
`USER_SPECIFIC` contract is present. The artifact growth comes from adding the
fresh approved Willys catalogs and the separate Brunnshög context, not from
membership profiles or duplicated universes.

The request-time semantic candidate pool is intentionally smaller than the
full artifact. For the current planner taxonomy it exposes 19 active Hemköp
and 14 active Willys member contracts; the remaining retained contracts still
belong to the shared source artifact but do not match a currently generated
canonical ingredient. The matrix does not authorize fuzzy joins, stale data,
or offers-only rows as basket prices.

The old duplicate Coop snapshot scoped as `lund:coop:730400` represents the same
online context as the newer `coop:online:730400` snapshot and is not counted a
second time.

`CUSTOMER_PRIVATE` in the Coop online transport is an ordinary private-customer
B2C context. It is **not** membership evidence. Coop membership is accepted only
from the separate explicit `medMeraRequired=true` field.

## Personal-offer integration boundary

Generic membership preferences require no retailer login and belong in request
time eligibility over the shared PriceUniverse. Personal offers, activated
coupons, bonus vouchers and account tokens are user-specific overlays and must
never be stored in the shared artifact.

No current integration requests or stores ICA, Coop, Hemköp, Lidl, Willys or
City Gross passwords. A future account connection may be enabled only after an
officially approved authorization flow such as OAuth, OIDC, a documented partner
API or an explicit retailer authorization redirect has been verified.

The historical community reverse-engineering reference
`svendahlstrand/ica-api/api-referens.md` describes an undocumented ICA flow that
used HTTP Basic authentication. It is neither a current official authorization
contract nor an approved production integration. It must never be used to build
retailer-password collection, credential storage, automated login or a claimed
ICA account connection.
