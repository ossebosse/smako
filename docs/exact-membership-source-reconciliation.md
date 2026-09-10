# Exact membership-source reconciliation

## Safety boundary

An authoritative member-price join requires two independent approvals:

1. exact product identity through a checksum-valid GTIN/EAN, an exact retailer
   product ID in the same identifier namespace, or an explicit verified
   registry fact; and
2. exact compatible price context.

The current automatic scope rule is deliberately narrow: source and target
must have the same chain and exact context ID. A matching identifier in a
different physical, online, regional, or national context is reported as
`exact_identity_scope_incompatible` and is never attached.

Names, brands, package descriptions and search similarity are absent from the
authoritative reconciliation model. They may support an admin suggestion, but
cannot create a `SourceProductIdentityLink`.

Every successful decision contains an immutable audit value with source and
target provider, source and target record IDs, both context IDs, exact evidence
types, scope evidence, verification time, and `confidence=exact`. There are no
new cross-source links in the 2026-08-31 Lund audit, so nothing new was
persisted or promoted.

## Current Lund audit, 2026-08-31

| Chain/source channel | Semantic rows active | Exact product mapped | Scope compatible | Retained active | Remaining reason |
|---|---:|---:|---:|---:|---|
| ICA OWN offers | 15 | 0 | 0 | 0 | All 62 discovered rows have no exact target identity in a compatible active full-catalog context. Thirteen expose GTIN and all 62 expose a retailer ID, but none equals a target identifier. |
| Coop Online 730400 | 11 | 82 total | 82 total | 11 | Source-local online product identity and online scope are preserved. |
| Coop physical offers | 121 | 0 | 0 | 0 | All 121 lack GTIN and retailer product ID. Physical contexts remain separate from online 730400. |
| Hemköp full contexts | 92 | 208 total | 208 total | 92 | Karhögstorg 4123 and Brunnshög 4224 remain separate exact contexts. |
| Lidl regional offers | 22 | 0 | 0 | 0 | Thirty-nine generic rows lack a compatible full-catalog target; two additional coupon-shaped rows remain `UNKNOWN`. |
| Willys full contexts | 116 | 116 | 116 | 114 | Two exact products are explicitly unavailable and remain outside the purchasable artifact. |
| City Gross | 0 | 0 | 0 | 0 | No generic Prio evidence exists in the current production snapshots. |

The machine-readable matrix is
`reports/membership-coverage/member-coverage-matrix-20260831.json`.

## Decision reasons

- `exact_gtin`
- `exact_retailer_product_id`
- `explicit_registry_gtin`
- `multiple_exact_evidence`
- `no_exact_identifier`
- `exact_identifier_not_found`
- `exact_identity_scope_incompatible`
- `duplicate_exact_identity`
- `conflicting_exact_identifiers`
- `unknown_eligibility`
- `user_specific_excluded`

No decision has an arbitrary first-match fallback. Duplicate or conflicting
exact identifiers are `ambiguous`; personal and unclear coupon semantics stay
outside the shared PriceUniverse.
