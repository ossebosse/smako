# Meal-plan performance profiling

`backend.scripts.profile_meal_plan` runs one optimized plan against explicit,
immutable snapshot inputs. It disables sockets for the complete provider/plan
operation, verifies the SQLite file before and after, and prints:

- a short human-readable summary to stderr;
- a versioned JSON report to stdout;
- an optional JSON artifact through `--json-output` (existing files are never
  overwritten).

Example Lund replay:

```powershell
py -3.12 -m backend.scripts.profile_meal_plan `
  --database .lund_phase_c_20260823.sqlite `
  --external-cache .lund-frozen-external-v1-20260824.json `
  --postal-code 22350 `
  --recipes 5 `
  --servings 4 `
  --max-stores 2 `
  --diversity balanced `
  --candidate-count 80 `
  --beam-width 30
```

For reproducible comparisons, pass the same `--freshness-now`, database,
external-cache, membership defaults, candidate count, candidate search limit,
and beam width. Both input SHA-256 values are retained in the JSON report.

Timings are cumulative wall time for named work scopes. A parent phase such as
`economic_ingredient_pool` intentionally includes child phases such as
`source_reconciliation` and `canonical_matching`; do not add those numbers
together. Operation counters are exact for the traced request. Depth counters
are aggregated over the CHEAPEST, BALANCED and VARIED searches that share the
same immutable candidate snapshot.

The profiler never accepts a live Primat mode. External products must already
be present in the credential-free frozen cache, and a network attempt fails the
profile.

## Initial Lund baseline (2026-08-24)

The first bounded profile used 10 generated/search candidates, beam width 5,
five recipes, four servings, max two stores, and BALANCED. This deliberately
small search isolates construction cost before production caching:

| Measurement | Result |
|---|---:|
| Wall clock | 130.705 s |
| Economic ingredient pool (inclusive) | 127.899 s |
| Canonical product matching | 108.544 s |
| Local snapshot/provider reconciliation | 18.531 s |
| Menu search | 0.829 s |
| Basket optimization | 0.852 s |
| Response serialization | 4.1 ms |
| Product rows / semantic comparisons | 81,622 |
| Eligible product candidates | 665 |
| Package calculations | 23,887 |
| Basket calculations | 162 |
| Store combinations | 3,365 |

The run made zero network attempts and left both immutable inputs unchanged.
Database SHA-256 was
`b629a21b104e3959ddec58d8762e3368dd52fdfeccfffc84113504c33d36b77e`;
external-cache SHA-256 was
`399944820a33a875ad7b15a5bbf676c64400b1d223537602b92ccf9c0a51d508`.
The measured top-level conclusion is that rebuilding and semantically matching
the local product universe dominates this request; the reduced beam search is
below one second.

## Production PriceUniverse result (2026-08-24)

The production path now performs the authoritative provider search and
`ProductMatcher` work once during refresh. The result is stored in a validated
`prepared-price-universe-v1` artifact and loaded at process startup. A meal
request never rebuilds the universe and a sentinel provider confirmed zero
provider/chain calls in every benchmark below.

One important equivalence guard changed the implementation decision. A raw
canonical/top-K prefilter was about 51 times faster than the legacy matcher, but
only 12 of 42 canonical candidate-ID sets were identical (1,748 valid legacy
candidates were absent). It remains a useful diagnostic/index surface, but is
not the production semantic authority. The active artifact instead contains the
exact established matcher output; safe top-K and dominance pruning affect only
the separate debug index until economic golden equivalence has been proven.

| Universe measurement | Result |
|---|---:|
| Refresh-time build | 189.697 s |
| Atomic artifact serialization | 1.967 s |
| Restart load | 2.50–2.78 s |
| Artifact size | 56,914,087 bytes |
| Raw eligible context products | 30,867 |
| Structured canonical mappings before pruning | 5,736 |
| Diagnostic mappings after safe pruning/top-K | 2,057 |
| Canonical indexes | 57 |
| Exact menu purchasing candidates | 672 |
| Full validated pre-pruning menu candidates | 2,691 |
| Exact pre-taxonomy candidates (53 keys) | 3,403 |

Artifact SHA-256 is
`e2ed4d6863d0c38f4528e4265dd583ad92c17d377a07e81e27546b9e11219b72`.
Its snapshot lineage contains both promoted Hemköp snapshots, the promoted
Willys snapshot and the frozen Primat request snapshot. Activation validates
schema, city, lineage, credential-free content and the stored copy before an
atomic manifest swap.

### Correctness and request runtimes

The exact snapshot-bound representative-candidate cache reduced candidate
construction from 40.406 seconds to a startup/refresh concern. Once loaded, the
13-item baskets run as follows:

| Max stores | Runtime | Total | Selected contexts |
|---:|---:|---:|---|
| 1 | 0.063 s | 340.30 kr | Willys Lund |
| 2 | 0.071 s | 329.30 kr | Hemköp Karhögstorg + Willys Lund |
| 3 | 0.091 s | 326.36 kr | Hemköp Brunnshög + Hemköp Karhögstorg + Willys Lund |

All totals, products, store contexts, verification and provenance match the
accepted frozen golden result.

For 80 generated candidates, beam width 30, five recipes, four portions and
max two stores, BALANCED measured:

| State | Runtime | Menu search | Basket work | Result |
|---|---:|---:|---:|---:|
| Cold after artifact load | 46.847 s | 46.172 s | 30.742 s cumulative | 236.68 kr |
| Warm identical request | 0.512 s | 0.002 s | 0.153 s cumulative | 236.68 kr |

The whole cold six-scenario matrix (three modes × max one/two stores) took about
82.7 seconds after artifact load, compared with the preserved 1,063.0-second
full-matrix run. Once the two store-limit search results were cached, each
selected diversity response took 0.49–0.52 seconds. The shared variant-search
cache deliberately ignores the selected projection when resolved constraints
are identical; a real diversity override receives a separate key.

The full matrix remains exactly:

| Mode | Max 1 | Max 2 |
|---|---:|---:|
| CHEAPEST | 225.74 kr | 194.04 kr |
| BALANCED | 270.87 kr | 236.68 kr |
| VARIED | 271.73 kr | 238.72 kr |

No selected store or recipe changed. Every basket audit, nutrition gate,
diversity gate and provenance gate passed. The federated winners use OWN rows,
so they remain feasible in the preserved OWN-only golden universe; the
OWN-only and federated economic delta is 0.00 kr in all six scenarios.

### Cache and search diagnostics

On a cold+warm BALANCED/max-two pair the persistent caches reported:

- package-cost cache: 1,357 hits / 1,325 misses (50.6% hit rate);
- basket-result cache: 2,854 hits / 7,603 misses (27.3% hit rate);
- complete menu-result cache: 1 hit / 1 miss (the warm request is a direct hit);
- store combinations: 159,983 cold, of which 35,226 were proven infeasible by
  ingredient/store bitsets before product selection.

The semantic work is persisted in the artifact rather than repeated through a
lazy request LRU. Consequently the separate diagnostic `SemanticCandidateCache`
has no request misses; all 672 production menu candidates and the broader exact
matcher caches are already materialized when the process starts.

Cold beam search remains the largest residual hotspot and does not yet meet the
20-second stretch target. Normal weekly use does meet the requested warm target
comfortably (about 0.5 seconds), and exact 13-item basket calculation is below
0.1 seconds. A future iteration can persist/prewarm common full menu-search
results or improve the beam lower bound without weakening semantic or quantity
gates.

### Freshness and operations

The active Lund manifest reported `FRESH`, oldest basket price age 26.0 hours,
warning at 36 hours and stale at 48 hours. Daily status reported 23/23 physical
stores explained and six fresh full basket contexts. Coop remains explicitly
visible as seven physical stores and zero fresh full basket contexts.

`daily-refresh` isolates connector failures and retains an explicitly marked
LKG. It can invoke an injected in-process universe builder after promotion or
atomically activate an explicitly prebuilt local candidate. A cross-process
startup verifies the content-addressed artifact hash and loads it once; request
handling never rebuilds it. See `docs/production-operations.md` for commands and
the fail-closed handoff contract.
