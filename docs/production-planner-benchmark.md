# Production planner benchmark

The production benchmark uses the active, integrity-checked PriceUniverse and
requires exact equality with an immutable economic golden. Grocery providers
are replaced by a fail-closed sentinel.

Run the standard dedicated benchmark:

```powershell
py -3.12 -m grocery_data benchmark-planner `
  --golden production `
  --cold `
  --warm `
  --runs 3
```

Add `--enforce-targets` in release acceptance. The default targets are:

- request-cold median below 10 seconds;
- warm median below 1 second.

Timing thresholds are deliberately not normal unit-test assertions. Economic
golden equality and zero provider calls remain hard failures in every run.

Latency definitions:

- **PROCESS COLD:** orchestration wall time for a new Python worker, verified
  PriceUniverse load and first plan;
- **REQUEST COLD:** first unseen plan after the PriceUniverse has become
  resident in an isolated worker;
- **WARM:** repeated identical requests after an unmeasured seed plan in the
  same worker.

Each process/request-cold sample uses a new worker process. The warm samples
share only their worker's immutable PriceUniverse and planner caches. Reports
include median and nearest-rank p95, per-span call/wall/CPU/average/max data,
PriceUniverse loading stages, search depth, operation counters and exact
economic fingerprints.

Every invocation writes an immutable pair:

```text
reports/planner-performance/benchmarks/benchmark-planner-<timestamp>.json
reports/planner-performance/benchmarks/benchmark-planner-<timestamp>.md
```

Use an explicit repository-local golden instead of `production` when replaying
an older artifact. `production` resolves only a golden whose PriceUniverse ID
matches the currently active manifest.
