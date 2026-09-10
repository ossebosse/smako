# Store coverage and optional physical validation

## Separate identities

`PhysicalStore` is an official real-world shop. `StoreContextLink` relates that
shop to zero or more price contexts. A price context can be an OWN online store,
a licensed provider context, an offer feed, a delivery context, or a regional
context. The relationship is many-to-many and is never inferred from a similar
display name alone.

An online price is labelled as an online context; it is not presented as a
verified shelf price. Lidl's national/default offer feed is deliberately not
assigned to either physical Lidl shop. Malmö Hyllie is deliberately not
assigned to Lund, where City Gross currently has no verified physical or
fulfilment context.

Accepted link evidence is one of:

- an exact official external store ID (including an explicitly preserved
  official alias);
- exact address plus postal code;
- exact official coordinates.

Basket eligibility additionally requires a healthy, fresh, full promoted
snapshot for that exact context. Offer capability never implies basket
capability.

## Bounded official discovery

Run all six official locators without collecting any product catalogue:

```text
python -m grocery_data audit-store-coverage --city Lund
```

Refresh one locator cheaply while retaining every other chain's persisted LKG
registry, for example ICA and its official secondary store aliases:

```text
python -m grocery_data audit-store-coverage --city Lund --chain ica
```

For deterministic offline regression:

```text
python -m grocery_data audit-store-coverage --city Lund \
  --fixture grocery_data/app/services/fixtures/official_stores_lund.json
```

An optional credential-free provider context export can be reconciled with
`--context-export`. Import requires the closed
`grocery-context-evidence-bundle-v1` envelope and rejects loose legacy lists,
unknown fields, duplicate JSON keys, credential-shaped values and files over
100 MB. Missing links are deactivated only when the operator explicitly marks
a non-empty export authoritative.

After a separately reviewed official discovery, import only the closed context
evidence without calling any locator or catalogue:

```text
python -m grocery_data audit-store-coverage --city Lund \
  --context-export <closed-context-export.json> \
  --skip-official-discovery
```

This mode requires `--context-export`, uses the persisted active physical-store
LKG, reports `discovery_skipped` and `context_import_only`, and leaves official
discovery-health timestamps/evidence unchanged. Locator options such as
`--fixture`, `--chain`, and `--confirm-store-removals` cannot be combined with
it.

Store discovery has its own drift guard. An empty result, or an unexplained
count reduction, is degraded and retains the last-known registry. A reviewed
non-empty removal can be confirmed explicitly; removed rows become `NOT_SEEN`
and remain in history.

The 2026-08-23 strict-address-locality Lund fixture contains 23 physical shops:
Willys 3, Hemköp 2, ICA 9, Coop 7, Lidl 2 and City Gross 0. The broader ICA
municipality result also contains Södra Sandby, Genarp and Veberöd; those are
not relabelled as city Lund. Hemköp Lund Karhögstorg is preserved as official
identity `4123`, Karhögstorg 2A, 22358 Lund.

Coop's physical-store adapter uses the bounded public rendered locator and
reconciles its declared city total; this is independent of Coop's seeded OWN
offer connector. In the verified Lund run the locator returned 7/7 detail
pages, and both `storeID` and the separate `ledgerAccountNumber` alias were
preserved for exact provider reconciliation.

Hemköp illustrates why physical identity and price context are not 1:1.
Brunnshög `4224` links to promoted full-online snapshot
`a579353ef6844296a03d75b69fedbf53` and is basket-capable. Karhögstorg `4123`
is physically discovered, online-capable and exactly linked, but two complete
catalogue attempts failed the same within-category pagination invariant. It has
no promoted snapshot and is therefore not basket-capable; the physical store is
not removed or misreported as missing.

The final Lund candidate also has two fresh full OWN Willys price contexts:
`2176` and `2354`, backed by active promoted snapshot
`65a83015146d4c7d989ad6e58210b147`. Its offline replay
`9981f09460924fda8a138d3554467d28` reproduced 18,434 store-product rows with
zero network calls. Willys Hemma Stortorget `2863` remains a discovered
physical store without a verified full online catalogue and is not presented
as basket-capable.

The bounded Primat v2 context bootstrap stopped fail-closed on
`identity_no_exact_match_coop`. Offline reconciliation found no safe closed
bundle and no exact Primat Lund context links to import. In particular, Coop's
physical stores and OWN offers remain visible, while the broad Primat basket
role is `NO_PRICE_CONTEXT`; no physical store identity was guessed from a
name. This also means the current run has no accepted federated numeric
benchmark, without changing the 23-store physical discovery result.

## Optional physical observations

Manual shelf-price observations are validation evidence only. They never
overwrite catalog prices and never gate normal shopping or meal planning.
The final 2026-08-23 Lund acceptance run had **0 physical observations**; the
OWN-only basket and menu benchmarks still completed. This is the expected
optional-workflow behaviour, not missing eligibility evidence.

Fast CLI entry:

```text
python -m grocery_data record-physical-price \
  --store physical:hemkop:4123 \
  --gtin 7310000000000 \
  --price 29.90
```

Sampled accuracy report:

```text
python -m grocery_data physical-price-report --store physical:hemkop:4123
```

The internal mobile page is `/physical-check`. It supports manual barcode entry
and an optional browser `BarcodeDetector` camera helper. No camera image,
precise user location, user identity or payment information is stored.

For the bounded Windows + iPhone proof-of-concept workflow, including the
fail-closed field-mode settings and ephemeral Cloudflare Quick Tunnel, see
[Physical price field deployment](physical_field_deployment.md). The tunnel is
optional and does not change basket eligibility or digital-price semantics.

Comparisons report exact difference, percentage difference, exact/0.50/1.00
SEK tolerances, promotion/member/multibuy agreement, staleness and likely input
anomalies. Reports always say that results describe sampled observations in the
named store/city, never national source accuracy.
