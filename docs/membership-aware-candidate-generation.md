# Membership-aware candidate generation

Last audited: **2026-08-31**

The application keeps one shared, membership-independent `PriceUniverse`.
`UserPricingContext` is applied to an immutable request-scoped economic view;
changing memberships neither rebuilds the universe nor calls a grocery
provider.

## Economic pipeline

| Stage | Price-sensitive decision | Membership handling |
| --- | --- | --- |
| Shared artifact | Retains products and every verified public or generic-member contract | No user eligibility is applied |
| Product matching | Builds `matched_candidates_by_name` before economic top-K limits | Keeps member-priced SKUs available for request-time ranking |
| Semantic preparation | Applies taxonomy, product-role and quantity-confidence gates once | Price-independent; cached by selector/policy identity |
| Request projection | Resolves eligible contracts for the Stockholm pricing date | `UserPricingContext` is applied before any economic pruning |
| Store/product shortlist | Ranks package economics for representative demand quantities | Uses eligible unit prices and exact multibuy threshold/residual/cap math |
| Canonical/category shortlist | Ranks economic ingredient signals and applies category caps | Member economics can change which canonical ingredients reach recipe generation |
| Recipe generation/ranking | Consumes the request-projected economic ingredient signals | No public-only shortlist is reused for a member request |
| Menu and store search | Prices ingredient aggregates while pruning menu/store combinations | Uses the same pricing-context identity and projected candidate map |
| Checkout | Solves package counts and promotion contracts | Uses the same authoritative contract resolver and exact quantity semantics |
| Basket audit | Reconciles totals and contract provenance | Rejects a member contract unless its exact programme is enabled |

Member multibuy prices are never flattened to an unconditional unit price.
For example, a member contract `3 for 30` is evaluated at the actual demand:
two packages do not qualify, three cost 30, and a residual fourth package uses
the best eligible residual contract.

## Fixed-menu monotonicity

Adding a membership expands the eligible contract set for an otherwise fixed
request. The projected candidate map therefore retains:

1. every request-context canonical/store winner; and
2. the exact public winners projected back onto the current pricing context.

The chain/program invariant prevents a membership for one chain from changing
eligibility at another chain. The tested invariant is:

`fixed basket cost(with additional memberships) <= fixed basket cost(without)`

This invariant concerns the same recipes, products/ingredient demand and store
limit. A newly generated menu may legitimately have different composition and
must not be used to attribute membership savings. Consumer membership savings
are consequently calculated by repricing the final basket's same exact product
identities and quantities with memberships disabled.

## Cache isolation

- Semantic preparation: selector/taxonomy/verification-policy digest.
- Pricing projection: full `UserPricingContext`, `Europe/Stockholm` date and
  selector/policy digest.
- Effective menu search: pricing-context identity plus a SHA-256 fingerprint of
  every eligible normalized contract.
- Basket result cache: pricing-context identity is part of the key.
- Request-local package quote cache: the candidate fingerprint includes
  contract ID, eligibility, mechanism, membership programme, discount,
  quantity/cap, validity/confidence and selected-contract provenance.
- Saved/full plans: the request and saved result preserve stable membership
  programme IDs.

A public-price projection or menu result is therefore not reusable as a member
projection merely because all non-membership request fields are equal.

## Exact identity and scope boundary

Offers-only member rows may enter shared optimizer pricing only when an exact,
unique identity exists in the same chain and exact price context, using:

1. validated GTIN;
2. exact retailer product ID; or
3. explicit high-confidence identifier-registry evidence.

Duplicate/conflicting identifiers are `AMBIGUOUS`; missing identifiers are
`UNMAPPED`. Product names are never an automatic bridge. Physical Coop offers
remain separate from online context `730400`, and regional Lidl offers do not
become store-specific prices. Coupon/personal/unknown Lidl semantics remain
outside the shared universe. Historical source snapshots are never mutated by
the bridge.

Personalized offers remain a per-user overlay boundary. No retailer password
or unsupported account-login automation is part of this implementation.
