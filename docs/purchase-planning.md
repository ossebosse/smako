# Source-bound purchase planning

The implementation extends the existing offer, quantity resolver and promotion-group engine. It does not add a retailer-specific pricing engine. The contract lives in `grocery_data/app/domain/purchase_terms.py`.

## Source → checkout

`SourceOffer.payload.purchase_terms` is validated at the source boundary. The catalog API keeps it in `OfferMetadata.purchase_terms`; OWN preserves it on offers and consistent product semantics. Prices, dates, audience, store/channel evidence and caps remain in the existing offer contract. Quantity and identity evidence never substitute for them.

The ordinary municipality providers rekey the same verified physical context without moving prices between stores. Prepared PriceUniverse artifacts retain the terms. `user_pricing`, `purchase_quantity_resolver`, matching, the existing basket optimizer/calculator and audit use the same terms. New optional defaults are excluded from serialized legacy objects to preserve old artifact digests.

The terms distinguish:

* `purchase_form`: fixed package, loose weight, variable package, piece, unresolved.
* `identity_scope` and `variant_selection`: identified product versus a campaign group requiring a choice.
* Source approximate package grams versus an actual documented min/max package interval.
* An interval of **different variant sizes**, which is not an average or a variable-weight distribution.
* Source exclusions, deposit evidence, critical blockers and cap scope.

An official, unambiguous document advertisement can establish price evidence without a GTIN or invented ordinary price. A source product ID remains in its retailer namespace. An offers-only unit price that only describes a comparison price cannot establish a loose-weight purchase.

## Planning choice and quality

`PlanRequest.purchase_planning_mode` is `exact` by default or `estimated` by explicit choice. The personal UI sends and persists this field. `estimated` permits evidenced approximate quantities, not uncertain membership, campaign identity, prices or source scope.

Loose weight is purchased at the planned amount. Variable-weight packages are counted and charged as whole packages at the documented approximate weight. Shared recipe requirements are aggregated before purchase. The row states the minimum usable amount needed and the fact that weighing changes final cost/surplus. No source interval or budget buffer is invented.

Confirmed open campaign choices enter as explicit personal extras of kind `campaign` and whole `st`, not as generic recipe ingredients. The confirmation is private request state; imported source products cannot set it. Whole multibuy groups are charged when there is no separate residual price. An unresolved variant never becomes a nutrition/allergen declaration. `UNVERIFIED` remains visible even when the arithmetic audit passes. Estimated quantities produce `ESTIMATED`; selecting estimated mode alone does not make an otherwise exact basket estimated.

Known merchandise and deposit amounts are separate. An unknown deposit prevents a complete total, but does not delete otherwise evidenced merchandise price information. Purchase booking into pantry requires actual measured usable quantities for approximate lines. The stored measurement remains separate from the planning estimate.

## Verified mixed variants

Sources may set `mixing_allowed`, `campaign_group_id`, `eligible_variant_ids` and `complete_group_size` only from explicit source evidence. `source_promotion_groups.attach_source_groups` joins the exact retailer source identity to OWN product UUID with store and snapshot scope. Identical price, period, membership and limit contracts are required. A safely identified subset is sufficient; unobserved variants are not created.

The existing `PromotionGroup` engine handles the result. Fixed-total groups need no invented ordinary price. Groups that describe a discount from ordinary prices still need those prices. A single unambiguous incomplete fixed-total group may be completed with whole packages of an already selected eligible variant. Ambiguous overlapping completion stays blocked. Household caps across stores require an explicit shared source key and cap; similarity of names/prices never establishes this scope. Unresolved deposit inclusion blocks mixed checkout.

The intermediate deferred group calculation is marked pending and cannot be presented as a verified standalone purchase. Final group reconciliation sets the actual cost and quantities, clears pending state and is independently audited.

## Nutrition

Nutrition is computed on the recipe's used edible amount, not the whole purchased package. Existing exact-product declarations take precedence. SLV references preserve ID/version/observation and require the existing generic-estimate opt-in. Per-100-ml values remain ml-based. Grams, pieces, edible yield, density and raw/cooked amounts cannot be interchanged without evidence or an explicitly permitted documented estimate. Generic reference values never prove allergen safety or the composition of an unspecified prepared food.

The Arla declaration importer accepts the official Product/label evidence and binds its actual brand/name/fat/weight variant. This does not copy prices across stores and does not turn a supplier barcode into a missing retailer GTIN. Open campaign groups cannot borrow declarations from one named variant.

## Tests and evidence

`backend/tests/test_purchase_planning_modes.py` covers the mode, whole packages, loose weight, UI/API request persistence, conditional choices, membership/date/cap failures and measured pantry booking. `test_source_promotion_groups.py` exercises SourceOffer → real collector → SQLite/catalog → OWN → PriceUniverse → mixed-group optimizer → audit/roundtrip, including wrong identity/store/conflict and legacy serialization. `test_variable_purchase_nutrition.py` checks the real saved Lidl Arla case against its separately acquired official declaration. Existing chain, source parser, price, nutrition, API and promotion regressions remain in the verification set.

See `reports/purchase-planning-20260925/README.md` for measured source coverage and the inactive release package. Synthetic contract tests are not counted as newly collected offers or independent campaign holdout evidence.
