# Lund Phase-C: Primat context and frozen-cache runbook

This flow is an explicit, bounded operator operation. Normal meal generation
continues to use promoted local snapshots and never performs a live chain or
Primat request.

## Security and request boundary

- The bootstrap resolves postal code `22350` exactly once.
- The transport permits only HTTPS on `primat.nu`, with concurrency 1, no
  retries, and only the explicitly enabled endpoint paths.
- `401`, `403`, `429`, CAPTCHA, WAF, Access Denied, or human verification stops
  the operation. There is no bypass or retry path.
- Context and product exports contain parsed domain objects only. Headers,
  cookies, URL parameters, credentials, raw responses, and session state are
  rejected or never enter the export boundary.
- No live operation should be run before explicit operator approval.

## Exact physical-store identity

Every customer-facing ICA, Coop, or Lidl context proposed for basket eligibility
must map to exactly one active official Lund `PhysicalStore`. A returned row
that cannot satisfy this contract remains unresolved/non-basket in v3 and does
not force a guessed link or prevent an independently proven store from being
accepted. Accepted evidence, in priority order:

1. provider-native ID equals the official primary ID or an official alias;
2. exact normalized official address plus exact five-digit postal code;
3. exact latitude and longitude.

Display-name similarity is never used. An unmatched or ambiguous context stops
the complete export. Staff/internal contexts are filtered by the normal Primat
adapter before reconciliation.

The output is a closed `grocery-context-evidence-bundle-v1` envelope whose
`items` are individually validated `grocery-context-evidence-v1` records.
Basket eligibility is derived later from healthy, fresh, full-catalog evidence;
it is not accepted as an export claim.

## Price-context completion flow (v3)

The store-identity milestone no longer requires every provider row to match in
one all-or-nothing export. It captures the complete public customer-context list
returned for the bounded Lund resolve, then explains every official store
independently. The operation still makes exactly one resolve request:

```powershell
py -3.12 backend/scripts/capture_lund_primat_stores.py `
  --allow-bounded-primat-store-discovery `
  --city Lund `
  --postal-code 22350 `
  --database .lund_phase_c_20260823.sqlite `
  --output <new-store-discovery-file.json>
```

The output is the closed `primat-store-discovery-bundle-v1` projection. It
contains the response SHA-256 and allowlisted public identity fields, including
selected and unselected customer contexts, but no raw response body, query
parameters, headers, cookies, API key, browser state or session data. The file
is replayed with zero network requests:

```powershell
py -3.12 -m grocery_data map-primat-stores `
  --city Lund `
  --database .lund_phase_c_20260823.sqlite `
  --input <store-discovery-file.json>
```

Automatic mappings require, in order, an exact official primary/alias ID, exact
normalized address, exact normalized name plus postal code, or a unique
coordinate match within 75 metres. Fuzzy names are emitted only as suggestions.
Ambiguous and unmatched stores persist as `unresolved`. A changed provider
context or identity fingerprint becomes `mapping_drift`; the last verified
context/link remains as LKG and is never silently replaced.

Identity alone creates a non-basket link. After reviewing the strong mappings,
an independently approved smoke re-resolves once and performs one shared,
bounded multi-context product query:

```powershell
py -3.12 backend/scripts/smoke_lund_primat_contexts.py `
  --allow-bounded-primat-context-smoke `
  --city Lund `
  --postal-code 22350 `
  --database .lund_phase_c_20260823.sqlite `
  --store-discovery <store-discovery-file.json> `
  --context-id <verified-primat-context> `
  --output <new-context-smoke-file.json>

py -3.12 -m grocery_data verify-primat-context-smoke `
  --city Lund `
  --database .lund_phase_c_20260823.sqlite `
  --input <context-smoke-file.json>
```

The closed `primat-context-smoke-bundle-v1` records per-context product and
priced-row counts, a few public product samples and request-scoped provenance.
Only a currently `verified` identity whose fingerprint has not drifted and
which returns at least one priced row with complete-catalog coverage can become
basket eligible. The replay/import command performs zero provider requests.

## Separate frozen-cache collection

The Phase-D external cache is collected separately from the meal and basket
optimizer. The collector reads the complete eligible ICA scope from one
explicit SQLite database through `mode=ro&immutable=1`; eligibility requires an
active physical store, active `verified` strong Primat mapping, active exact
catalog link, full coverage, `basket_eligible=true`, a snapshot ID and data no
older than the configured threshold. The two expected context IDs must equal
that database-derived scope exactly before the provider is constructed.

```powershell
py -3.12 backend/scripts/collect_lund_primat_frozen_cache.py `
  --allow-bounded-primat-frozen-cache-collection `
  --city Lund `
  --postal-code 22350 `
  --database .lund_phase_c_20260823.sqlite `
  --context-id primat:ica:1004409 `
  --context-id primat:ica:1088004 `
  --max-age-hours 48 `
  --output <new-lund-frozen-external-v1.json>
```

The collector spends exactly one `/stores/resolve` request followed by exactly
48 sequential `/products` requests. Every product request contains both
eligible contexts. The 48-row query surface is derived directly from
`CatalogRecipeCoverageBenchmark.ingredient_set`; one unique declared alias is
selected per canonical ingredient so the provider cache cannot collapse two
rows into one request. This includes the shared 13-item representative basket.
It deliberately does not claim that all 67 optional aliases or an enumerated
full catalogue were collected: the artifact is a query-bounded candidate
universe for the offline benchmark.

The transport permits only HTTPS GET requests to Primat `/stores/resolve` and
`/products`, with request limit 49, concurrency one and retries zero. Current
identity fingerprints, full coverage and request-scoped provenance are checked
before the existing closed `lund-frozen-external-v1` schema is written. The
output refuses overwrite and contains no headers, cookies, credentials, URL
parameters or raw response bodies. No optimizer runs and the SQLite file plus
sidecars must remain byte-for-byte unchanged.

## Verified 2026-08-24 outcome

The v3 store-by-store flow completed without weakening identity rules. The
sanitized discovery artifact `.lund-primat-store-discovery-20260824.json`
contains 30 raw resolver rows from exactly one `GET /api/v3/stores/resolve`
request. It contains no API key, headers, cookies, query parameters, browser
state or session material.

Two physical ICA stores have accepted full external price contexts:

| Official physical store | Primat context | Identity | Discovery | Price smoke | Audit state |
| --- | --- | --- | --- | ---: | --- |
| `physical:ica:1004409` — ICA Kvantum Malmborgs Clemenstorget | `primat:ica:1004409` | `VERIFIED` / `EXACT_ID` | `FULL_CATALOG` | 4/4 priced | `EXTERNAL_FULL_CONTEXT` |
| `physical:ica:1088004` — Maxi ICA Stormarknad Gunnesbo, Lund | `primat:ica:1088004` | `VERIFIED` / `EXACT_ID` | `FULL_CATALOG` | 90/90 priced | `EXTERNAL_FULL_CONTEXT` |

Both IDs are official primary IDs, both mappings were revalidated without
identity drift, and both fresh links are active and `basket_eligible=true`.
The shared bounded smoke made one resolve and one product request. Its response
projection is preserved in `.lund-primat-context-smoke-20260824.json`; every
priced sample carries a Primat request snapshot and valid source provenance.

The independently approved 48-query frozen collector revalidated the same
closed two-context scope and produced 32 unique Clemenstorget products and
1,831 unique Gunnesbo products. This is a declared ingredient-query candidate
universe (1,863 products), not an enumerated provider catalogue. Collection
used exactly 49 requests: one resolve plus 48 product requests. All 49 returned
HTTP 200; denied responses and retries were zero, and every one of the 48
declared ingredient queries returned a non-empty result. The artifact SHA-256
is `399944820a33a875ad7b15a5bbf676c64400b1d223537602b92ccf9c0a51d508`.
The candidate SQLite database was byte-for-byte unchanged after collection.

The subsequent socket-blocked frozen replay passed the complete federated
acceptance matrix in 1,063.0382 seconds. Network attempts were zero and the
immutable database remained unchanged. The exact outcomes were:

| Scenario | Federated result | Selected contexts | OWN delta |
| --- | ---: | --- | ---: |
| 13 items, `max_stores=1` | 340.30 kr | Willys Lund | 0.00 kr |
| 13 items, `max_stores=2` | 329.30 kr | Hemköp Karhögstorg + Willys Lund | 0.00 kr |
| 13 items, `max_stores=3` | 326.36 kr | Hemköp Brunnshög + Hemköp Karhögstorg + Willys Lund | 0.00 kr |
| CHEAPEST 5 × 4, `max_stores=1` | 225.74 kr / 11.29 kr per portion | Willys Lund | 0.00 kr |
| CHEAPEST 5 × 4, `max_stores=2` | 194.04 kr / 9.70 kr per portion | Hemköp Karhögstorg + Willys Lund | 0.00 kr |
| BALANCED 5 × 4, `max_stores=1` | 270.87 kr / 13.54 kr per portion | Hemköp Karhögstorg | 0.00 kr |
| BALANCED 5 × 4, `max_stores=2` | 236.68 kr / 11.83 kr per portion | Hemköp Karhögstorg + Willys Lund | 0.00 kr |
| VARIED 5 × 4, `max_stores=1` | 271.73 kr / 13.59 kr per portion | Hemköp Karhögstorg | 0.00 kr |
| VARIED 5 × 4, `max_stores=2` | 238.72 kr / 11.94 kr per portion | Hemköp Karhögstorg + Willys Lund | 0.00 kr |

The federated store gate represented Hemköp, ICA and Willys. Both exact ICA
contexts were eligible and considered but selected zero times, so all prices,
stores and recipe sets reproduced the OWN-only matrix exactly. Coop and Lidl
were explained but ineligible; City Gross remained `NO_LUND_CONTEXT`. Basket,
nutrition, diversity, reconciliation and provenance audits passed, with no
member-price or fallback rows.

Coop is truthfully non-basket. All seven official physical stores have a
`VERIFIED` / `EXACT_ID` provider identity (`105760`, `106430`, `106435`,
`106444`, `106445`, `216523`, `216526`), but every corresponding Primat context
is only `OFFERS_ONLY` and `basket_eligible=false`. These identities do not turn
the external offer feed into a full basket source. In the 48-hour Lund audit,
their separate persisted price evidence was stale, so all seven stores were
`STALE_CONTEXT`.

Lidl also remains truthfully non-basket. `physical:lidl:0163` is `UNRESOLVED` /
`NONE`; `physical:lidl:0303` is `UNRESOLVED` / `PROBABLE`, and its similar name
is suggestion-only rather than production identity evidence. No Primat full
candidate was linked to either physical store. The public OWN offer feed remains
regional and must never be assigned as a store-specific shelf/catalogue price;
the verified audit therefore reports both stores as `MAPPING_UNRESOLVED`.

The complete price-context audit explains 23/23 physical stores with zero
unknown state: 4 `OWN_FULL_CONTEXT`, 2 `EXTERNAL_FULL_CONTEXT`, 14
`STALE_CONTEXT`, 2 `MAPPING_UNRESOLVED` and 1 `NO_PRICE_CONTEXT`. Six contexts
are basket eligible. City Gross remains `NO_LUND_CONTEXT`; Malmö Hyllie is not
imported into Lund.

## Historical verified 2026-08-23 outcome — preserved

The v2 bounded bootstrap stopped fail-closed with contract invariant
`identity_no_exact_match_coop`. The offline follow-up audit found no safe closed
context bundle and no exact persisted Primat Lund links that could be imported.
No provider store was matched by display-name similarity and no partial output
was promoted into the context registry.

Steps 4–7 in the historical v2 sequence below were therefore not acceptance
steps for that run: there was no
frozen external cache and no federated numeric benchmark result. Coop remains
present as official physical stores plus its separate OWN `OFFERS_ONLY`
channel, while its Primat basket mapping is `NO_PRICE_CONTEXT`. ICA and Lidl
likewise received no accepted Primat link from the failed bundle. A future
retry must start again at the bounded bootstrap and satisfy the same exact
identity contract; this outcome does not authorize relaxed matching.

## Historical v2 operator sequence — superseded, retained for audit history

The commands below describe the 2026-08-23 all-or-nothing flow. New operations
must use the v3 per-store capture, mapping, smoke and frozen-cache commands
above; this section is retained only so the historical closed stop remains
reproducible.

1. Refresh ICA and Coop official registry aliases independently, without
   touching the other chain locators or product catalogs:

   ```powershell
   py -3.12 -m grocery_data audit-store-coverage --city Lund --chain ica
   py -3.12 -m grocery_data audit-store-coverage --city Lund --chain coop
   ```

   The other chains remain in the persisted LKG registry. Verify, for example,
   that Clemenstorget retains official primary ID `1004409` and alias `2771`.
   Coop's secondary aliases come only from the independently verified public
   `StorePageType.ledgerAccountNumber` field; they are not inferred from Primat
   names or payloads.
2. Run the bounded context bootstrap against the completed candidate database:

   ```powershell
   py -3.12 backend/scripts/export_lund_primat_contexts.py `
     --allow-bounded-primat-context-bootstrap `
     --database .lund_phase_c_20260823.sqlite `
     --postal-code 22350 `
     --output .lund-primat-contexts.json
   ```
3. Inspect the report. It must show one resolve request, zero denied requests,
   all three required chains, and an exact structured identity for every row.
   A closed stop reports an allowlisted `contract_invariant` and, when relevant,
   only the affected chain (for example
   `identity_no_exact_match_coop`). It never emits provider
   store rows, context IDs, exception text, headers, cookies, or credentials.
4. Import and reconcile without credentials:

   ```powershell
   py -3.12 -m grocery_data audit-store-coverage `
     --city Lund `
     --context-export <closed-context-export.json> `
     --skip-official-discovery
   ```

   This context-import-only mode reads the persisted active `PhysicalStore`
   LKG, performs zero locator or catalogue requests, and does not replace the
   timestamp, evidence, or health result from the already reviewed official
   discovery run. Its JSON report explicitly sets `discovery_skipped=true` and
   `context_import_only=true`.

   Use `--authoritative-context-export` only after verifying that the export is
   complete for every chain/provider/channel it contains. The non-authoritative
   first import cannot retire last-known-good links.
5. Verify that each persisted Primat link is active, `coverage=full_catalog`,
   fresh, basket-capable, and points to the intended official physical-store
   ID. Official primary/alias identity is `confidence=EXACT`; exact normalized
   address+postal or exact coordinates are valid structured evidence stored as
   `confidence=HIGH`. Neither permits a name-only match.
6. Run the explicit bounded federated benchmark. Its single request-scoped
   Primat provider reuses the resolved store list and parsed product-search
   cache. `--frozen-cache-output <new-file>` writes
   `lund-frozen-external-v1` from that cache with zero additional provider
   requests. The command refuses to overwrite an existing file.
7. Replay the same benchmark with the frozen file. Socket access is disabled;
   store/product counts, prices, promotions, and provenance must reproduce.

## Required checks before accepting the files

- Original candidate SQLite hash and sidecar state are unchanged.
- `/stores/resolve` count is exactly 1.
- No access-control or rate-limit response occurred.
- No eligible selected customer-facing full context was dropped; every other
  official store has an explicit non-basket, stale, unresolved or no-context
  explanation.
- Each context matches a persisted Lund physical store through structured
  evidence; there are no name-only mappings.
- Frozen stores use `full_catalog`, `source_provider=primat`, catalog channel,
  request snapshot ID, observation timestamp, and explicit price-context type.
- Frozen products belong to the same request snapshot and mapped store set.
- Recursive forbidden-key and bearer-shaped-value scans pass.
- No `.env`, API key, authorization value, cookie, session, or raw payload is
  present in either output.

The physical-price observation feature is independent of this runbook. No
manual store visit or shelf-price observation is required for a context to be
basket eligible.
