# Lund Phase-C benchmark

`backend/scripts/benchmark_lund_phase_c.py` is the reproducible, offline runner
for the Lund coverage milestone. It executes two checks against promoted local
snapshots:

1. the fixed 13-ingredient representative basket with `max_stores=1`, `2` and
   `3`;
2. five recipes, four servings, the complete `CHEAPEST`, `BALANCED` and
   `VARIED` matrix with `max_stores=1` and `2` through the normal
   `MealPlanService` quality pipeline.

The representative quantities are versioned in the runner. Every candidate is
accepted by `ProductMatcher` before price comparison. Checkout then uses the
strict `BasketOptimizer`, `PurchaseQuantityResolver` and `BasketAuditor`. The
menu scenario additionally requires nutrition and diversity `PASS`.

## Immutable transport

SQLite is opened with `mode=ro&immutable=1`. The runner never imports the
default grocery-data application (whose startup may create a schema); it builds
a small in-process ASGI read surface over the supplied read-only session
factory. Socket connection and DNS functions are disabled for the whole
benchmark.

The result records SHA-256, size, mtime and SQLite sidecar state before and
after execution. `immutable_unchanged` must be true and `network_attempts` must
be zero. A pre-migration baseline receives two missing store-context fields
through a connection-local `TEMP VIEW`; the source file remains immutable and
its legacy provenance gaps remain visible.

## Readiness gate

The candidate run stops with `NOT_READY` unless all of these facts exist:

- promoted full Willys snapshot with active Lund contexts `2176` and `2354`;
- every active physical Hemköp Lund store has one active, exact OWN online
  context link and is either eligible or a proven terminal context gap;
- at least one Hemköp Lund context remains promoted, fresh, full-online and
  basket-capable;
- in federated mode, a credential-free frozen external cache for every exact,
  basket-capable persisted Primat context that is admitted to the benchmark;
- every physical ICA, Coop and Lidl store has a persisted closed identity
  explanation. A verified full context is eligible, while `OFFERS_ONLY`,
  unresolved and drift states remain explicitly excluded rather than guessed.

An eligible Hemköp context must link to the matching active local store and
its active promoted snapshot. A terminal context gap is narrower than a failed
full crawl: its latest exact-scope, full-online candidate must be persisted as
`REJECTED` or `BROKEN`, inactive, tied to a failed collector run, and retain raw
payloads plus complete reconciliation evidence. That evidence must account for
all declared categories, pages and rows and reconcile duplicate counts exactly. Missing,
unattempted, ambiguously mapped or weakly evidenced contexts remain unresolved
and therefore `NOT_READY`.

Terminal gaps are emitted separately as `terminal_context_gaps` and as explicit
warnings. They are never treated as basket-capable and are filtered from both
the representative-basket and five-recipe provider request scopes. This allows
the final benchmark to run without `--allow-incomplete-phase-c` when, for
example, one exact context has conclusively failed while another fresh promoted
Hemköp Lund context remains eligible. It does not silently relax the expected
physical-store set.

The same `--max-price-age-hours` value is enforced by this preflight and by the
providers. For every active full-catalog OWN Lund context, preflight reads only
price rows belonging to active promoted snapshots and uses the oldest
observation as the conservative store timestamp. A missing observation, any
future newest observation, or an oldest observation over the threshold fails
closed before provider startup. It never substitutes snapshot creation or
promotion time for missing price evidence.

Every admitted exact Primat context link is evaluated against its persisted
`observed_at` using the same time and threshold. Missing snapshot provenance,
missing/invalid observation time, future time or stale time makes that link
ineligible. A physical store without an admitted full context must still have
a closed persisted explanation (`verified` non-basket coverage, `unresolved`
or `mapping_drift`); an unknown state stops the run. `_exact_external_contexts`
applies the same eligibility filter, so an unsafe link cannot subsequently
enter either the frozen or bounded-live provider.

Minimal historical unit-test schemas that predate the observation columns keep
their compatibility role and report
`legacy_schema_not_evaluated/enforced=false`. This is explicitly not freshness
evidence. A production-schema database never receives that exemption.

An "exact" external link means an allowlisted structured identity decision:
official primary/alias ID (`EXACT`), exact address plus postal code (`HIGH`),
or exact coordinates (`HIGH`). It must also have the exact-store relation,
catalog coverage, snapshot evidence and observation time. Fuzzy or name-only
evidence is rejected regardless of confidence label.

`--allow-incomplete-phase-c` exists only for unresolved-context diagnostics. A
proven terminal context gap does not require it, and the flag must not be used
for the final result.

Willys rows have an extra provenance invariant: `price_context` must be
`online_store`. Physical shelf price is never inferred from the online
catalogue.

## Modes

OWN-only uses only the OWN catalogue binding and excludes ICA, Coop and Lidl:

```powershell
$env:PYTHON_DOTENV_DISABLED = "1"
py -3.12 backend/scripts/benchmark_lund_phase_c.py --mode own-only
```

Federated mode normally makes no live Primat request. It requires a sanitized
frozen export whose stores and products contain ordinary public
`SourceProvenance`, but no request headers, cookies, tokens, credentials or
session state:

```powershell
$env:PYTHON_DOTENV_DISABLED = "1"
py -3.12 backend/scripts/benchmark_lund_phase_c.py `
  --mode federated `
  --external-cache path/to/lund-frozen-external-v1.json
```

The cache root has `schema_version=lund-frozen-external-v1`, `postal_code`,
`stores` and `products`. Every store must match an exact active persisted Lund
`StoreContextLink`; merely supplying a correctly shaped product row cannot make
an external context eligible.

For the one explicitly authorized live acceptance run, the frozen cache may be
replaced by `--allow-bounded-primat-live`. The key is read only from normal
environment configuration and is never accepted as a command-line argument or
included in output. Its transport permits serial `GET` requests only to the
configured HTTPS `primat.nu` `/stores/resolve` and `/products` paths, rejects
all other hosts/endpoints, and has a hard request ceiling (64 by default):

```powershell
$env:PYTHON_DOTENV_DISABLED = "1"
py -3.12 backend/scripts/benchmark_lund_phase_c.py `
  --mode federated `
  --allow-bounded-primat-live `
  --primat-max-requests 64
```

This opt-in is intentionally mutually exclusive with `--external-cache`.
Returned Primat contexts are filtered through the same persisted exact Lund
links before the optimizer sees them. HTTP status counts and closed endpoint
counts are reported without query strings, headers or credentials.

`/stores/resolve` is cached for the complete provider request scope, so the
representative basket, menu flow and closed exporter together spend at most one
store-resolution request. A store-only bootstrap factory mode exists for the
initial exact context-evidence export: it requires a hard request cap of one,
permits only `/stores/resolve`, needs no already-persisted links, and refuses
all product and offer methods.

The authorized candidate acceptance run may also materialize its already
parsed, request-local product cache as a replay artifact. The destination must
not already exist:

```powershell
$env:PYTHON_DOTENV_DISABLED = "1"
py -3.12 backend/scripts/benchmark_lund_phase_c.py `
  --mode federated `
  --database candidate `
  --allow-bounded-primat-live `
  --primat-max-requests 64 `
  --frozen-cache-output path/to/lund-frozen-external-v1.json
```

The export is built by `BoundedPrimatPhaseCExporter` from domain `Store` and
`Product` rows only. It cannot contain headers, cookies, credentials, request
parameters or raw responses. The result records product/store counts, hash and
that the export spent zero additional requests.

## Old/new comparison

The recorded OLD Lund run was incomplete because `yellow_onion` had no usable
candidate. Its total therefore remains `null`; the runner never fabricates a
numeric old/new price delta. A replay of `grocery_data_live.sqlite` with current
matcher code can be requested with `--database both` and is reported separately
as `current_code_immutable_replay`. This
distinguishes a software-recall improvement from a genuine store/snapshot
coverage change.

## Verified 2026-08-24 price-context completion, OWN-only and federated acceptance

The completed candidate database now explains every official physical Lund
store with exactly one state. With the 48-hour freshness policy, the audit is
`physical=23`, `explained=23`, `unknown=0`, `basket=6`, `offers=0`, `stale=14`,
`mapping_unresolved=2` and `no_price_context=1`:

| Chain | Physical | Exact audit outcome | Basket contexts |
| --- | ---: | --- | ---: |
| Willys | 3 | 2 `OWN_FULL_CONTEXT`, 1 `NO_PRICE_CONTEXT` | 2 |
| Hemköp | 2 | 2 `OWN_FULL_CONTEXT` | 2 |
| ICA | 9 | 2 `EXTERNAL_FULL_CONTEXT`, 7 `STALE_CONTEXT` | 2 |
| Coop | 7 | 7 `STALE_CONTEXT` | 0 |
| Lidl | 2 | 2 `MAPPING_UNRESOLVED` | 0 |
| City Gross | 0 | `NO_LUND_CONTEXT` | 0 |
| **Total physical stores** | **23** | 4 own full + 2 external full + 14 stale + 2 unresolved + 1 no context | **6** |

Hemköp Karhögstorg is no longer a terminal gap. The historical rejected raw
candidate contained one byte-identical `101882749_ST` row across pages 5 and 6:
`EXACT_ROW_DUPLICATE` plus `PAGINATION_OVERLAP`, with no field conflict. Strict
offline reconstruction removed exactly that one row, reported zero conflicts
and made zero network requests; it did not retroactively promote the rejected
source. Fresh source-snapshot `2d669d3dd375462fbb5fb8cf5a5ec934`
subsequently completed 20/20 categories and 78/78 pages with 6,797 raw / 6,092
unique priced rows and zero within-category duplicate, conflict or overlap. It
is promoted, active, healthy and basket eligible. Replay
`1398f77ad6654c668375122b9adae178` reproduced all 6,092 rows offline.

Against Brunnshög, Karhögstorg had 4,169 common external product IDs: 4,017
(96.35%) had the same price and 152 differed; 3,864 (92.68%) had the same
promotion semantics. There were 1,923 Karhögstorg-only and 917 Brunnshög-only
IDs. The absolute-difference buckets were 4,017 at 0 kr, 8 within 0.50 kr, 86
from 0.50 through 1 kr, 51 from 1 through 5 kr and 7 above 5 kr. The snapshots
were observed about 14.5 hours apart, so this is context-and-time diagnostics,
not a pure causal store effect.

The accepted OWN-only representative basket used promoted local snapshots and
made zero live chain/provider requests during optimization:

| Scenario | Complete | Selected contexts | Total |
| --- | ---: | --- | ---: |
| 13 items, `max_stores=1` | 13/13 | Willys Lund | 340.30 kr |
| 13 items, `max_stores=2` | 13/13 | Hemköp Karhögstorg + Willys Lund | 329.30 kr |
| 13 items, `max_stores=3` | 13/13 | Hemköp Brunnshög + Hemköp Karhögstorg + Willys Lund | 326.36 kr |

The exact five-recipe sets were:

- **CHEAPEST:** Stekt ris med tofu och morot; Stekt ris med falukorv och morot;
  Stekt ris med korv och morot; Mustig gryta på korv med nudlar och morot;
  Mustig gryta på tofu med nudlar och morot.
- **BALANCED:** Korvpanna med bröd och morot; Stekt korv med potatis och morot;
  Stekt ris med tofu och morot; Bowl med tofu, ris och gul lök; Tacos med ägg
  och morot.
- **VARIED:** Korvpanna med bröd och morot; Stekt ris med korv och morot;
  Mustig gryta på tofu med nudlar och morot; Bowl med tofu, ris och gul lök;
  Tacos med ägg och morot.

| Mode | `max_stores` | Selected contexts | Total | Price/portion |
| --- | ---: | --- | ---: | ---: |
| CHEAPEST | 1 | Willys Lund | 225.74 kr | 11.29 kr |
| CHEAPEST | 2 | Hemköp Karhögstorg + Willys Lund | 194.04 kr | 9.70 kr |
| BALANCED | 1 | Hemköp Karhögstorg | 270.87 kr | 13.54 kr |
| BALANCED | 2 | Hemköp Karhögstorg + Willys Lund | 236.68 kr | 11.83 kr |
| VARIED | 1 | Hemköp Karhögstorg | 271.73 kr | 13.59 kr |
| VARIED | 2 | Hemköp Karhögstorg + Willys Lund | 238.72 kr | 11.94 kr |

All six menu runs passed basket audit, nutrition, diversity and end-to-end
provenance. No physical shelf-price observation was required or fabricated.

Two external ICA contexts are now strongly mapped and smoke-verified:
`physical:ica:1004409` → `primat:ica:1004409` (Clemenstorget, `EXACT_ID`, 4/4
priced smoke rows) and `physical:ica:1088004` → `primat:ica:1088004`
(Gunnesbo, `EXACT_ID`, 90/90). Coop's seven exact provider identities expose
only non-basket `OFFERS_ONLY`; Lidl's two Primat physical mappings remain
unresolved and its OWN offers remain regional rather than store-specific.

The separate two-context frozen Primat artifact was the only external input to
the offline federated benchmark. Its collection proof is closed and exact:

| Frozen-cache invariant | Verified result |
| --- | ---: |
| Provider scope | `primat:ica:1004409`, `primat:ica:1088004` |
| Requests | 49: 1 resolve + 48 product |
| HTTP / denied / retry | 49 × 200 / 0 / 0 |
| Non-empty declared queries | 48/48 |
| Products | 1,863 |
| SHA-256 | `399944820a33a875ad7b15a5bbf676c64400b1d223537602b92ccf9c0a51d508` |
| Candidate database after collection | unchanged |

The socket-blocked federated run then passed the full scenario matrix. Its
runtime was 1,063.0382 seconds, network attempts were zero and the immutable
database remained unchanged:

| Scenario | OWN | Federated | Delta | Federated selected contexts |
| --- | ---: | ---: | ---: | --- |
| 13 items, `max_stores=1` | 340.30 kr | 340.30 kr | 0.00 kr | Willys Lund |
| 13 items, `max_stores=2` | 329.30 kr | 329.30 kr | 0.00 kr | Hemköp Karhögstorg + Willys Lund |
| 13 items, `max_stores=3` | 326.36 kr | 326.36 kr | 0.00 kr | Hemköp Brunnshög + Hemköp Karhögstorg + Willys Lund |
| CHEAPEST 5 × 4, `max_stores=1` | 225.74 kr | 225.74 kr | 0.00 kr | Willys Lund |
| CHEAPEST 5 × 4, `max_stores=2` | 194.04 kr | 194.04 kr | 0.00 kr | Hemköp Karhögstorg + Willys Lund |
| BALANCED 5 × 4, `max_stores=1` | 270.87 kr | 270.87 kr | 0.00 kr | Hemköp Karhögstorg |
| BALANCED 5 × 4, `max_stores=2` | 236.68 kr | 236.68 kr | 0.00 kr | Hemköp Karhögstorg + Willys Lund |
| VARIED 5 × 4, `max_stores=1` | 271.73 kr | 271.73 kr | 0.00 kr | Hemköp Karhögstorg |
| VARIED 5 × 4, `max_stores=2` | 238.72 kr | 238.72 kr | 0.00 kr | Hemköp Karhögstorg + Willys Lund |

The federated menus used the exact recipe sets listed above. The store gate
represented Hemköp, ICA and Willys. Both exact ICA contexts were eligible and
considered, but the optimizer selected no ICA row; provider preference did not
change basket economics. Coop and Lidl were fully explained but ineligible and
City Gross remained `NO_LUND_CONTEXT`. BasketAuditor, nutrition, diversity,
total reconciliation and complete price/store/provider/snapshot provenance all
passed. Member-only rows and fallback rows were both zero.

## Historical final candidate OWN-only acceptance — 2026-08-23 (preserved)

The completed candidate run used active Willys source-snapshot
`65a83015146d4c7d989ad6e58210b147`, together with the eligible promoted Hemköp
Lund context. Willys contributed 18,434 store-product rows. Its bounded offline
replay `9981f09460924fda8a138d3554467d28` reproduced all 18,434 rows with zero
network calls:

| Willys context | Products | Pages | Recipe coverage ≥1/≥3/≥5 |
| --- | ---: | ---: | ---: |
| Lund `2176` | 10,069 | 653 | 48/48 / 47/48 / 39/48 |
| Lund Nova `2354` | 8,365 | 585 | 48/48 / 45/48 / 39/48 |

The candidate OWN-only benchmark completed with:

| Scenario | Complete | Total |
| --- | ---: | ---: |
| 13 items, `max_stores=1` | 13/13 | 331.30 kr |
| 13 items, `max_stores=2` | 13/13 | 323.76 kr |
| 13 items, `max_stores=3` | 13/13 | 323.76 kr |
| 5 recipes × 4, BALANCED, `max_stores=2` | PASS | 251.58 kr |

Readiness, terminal-context exclusion, semantic and quantity validation,
basket audit, provenance, total reconciliation, nutrition/diversity,
no-network and immutable-database gates all passed. No manual shelf-price
observation was required; the physical-observation count was zero.

## Historical federated acceptance outcome — fail-closed, no numeric result

The second bounded Primat context bootstrap stopped on the closed invariant
`identity_no_exact_match_coop`. The subsequent offline audit found neither a
safe closed context bundle nor exact persisted Primat Lund links that could
satisfy the federated readiness gate. No external context was guessed from a
similar name and no partial bundle was imported.

Consequently there is no accepted federated 13-item or five-recipe numeric
result for this run. Coop remains a discovered physical-store chain with its
separate OWN `OFFERS_ONLY` channel, but its Lund Primat basket role is
`NO_PRICE_CONTEXT` until an exact structured identity can be verified. The
same failed bundle supplies no accepted Primat basket links for ICA or Lidl.
This is a missing verified context result, not evidence that the physical
stores or their offer pages are unavailable.

The historical OLD result remains incomplete because `yellow_onion` had no
usable candidate, so its total is `null`. Neither the final OWN-only totals nor
the preserved current-code diagnostic below are used to invent an OLD→NEW
numeric delta.

## Preserved historical baseline current-code diagnostic

The socket-blocked immutable replay performed on 2026-08-23 is retained as a
diagnostic, not relabelled as the historical OLD run:

| Scenario | Complete | Total | Selected context |
| --- | ---: | ---: | --- |
| 13 items, `max_stores=1` | 13/13 | 341.96 kr | Willys Lund / 2176 |
| 13 items, `max_stores=2` | 13/13 | 341.96 kr | Willys Lund / 2176 |
| 13 items, `max_stores=3` | 13/13 | 341.96 kr | Willys Lund / 2176 |
| 5 recipes × 4, BALANCED, `max_stores=2` | PASS | 271.06 kr | Willys Lund / 2176 |

Both Willys Lund contexts (2176 and 2354) were considered and explicitly
labelled `online_store/full_catalog`; optimization selected stable context
`context:willys:383650ec6ff5a636` (2176). Each representative scenario had
13/13 complete provenance rows (`OWN`, Willys, one context), zero fallback,
zero member prices and snapshot
`01f4d4694b2a4691a8f716296976fe6a`. The menu had 12/12 complete provenance
rows on the same context/snapshot. Basket audit, total reconciliation,
nutrition and diversity all passed; SQLite was unchanged and network attempts
were zero.

The historical OLD result remains incomplete for `yellow_onion` with a null
total. The 341.96 kr value is therefore never used as an OLD total or as the
basis for a fabricated old/new delta.
