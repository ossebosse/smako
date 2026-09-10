# Production planner economic golden

`backend/scripts/benchmark_planner_golden.py` freezes and verifies exact
economic planner results against one active, hash-verified PriceUniverse. The
runner is offline and fails immediately if planning attempts a provider call.

Freeze a new immutable baseline:

```powershell
py -3.12 backend/scripts/benchmark_planner_golden.py freeze --city Lund
```

Verify an implementation against the frozen 2026-08-31 baseline:

```powershell
py -3.12 backend/scripts/benchmark_planner_golden.py verify `
  --golden reports/planner-performance/golden/production-planner-golden-2026-08-31-04b709a55e66.json
```

Verification requires the same active PriceUniverse ID and replays the frozen
Europe/Stockholm pricing date. It compares all seven scenario fingerprints.
The file is never overwritten.

The semantic fingerprint includes:

- request constraints and membership programs;
- selected recipe identities and exact ingredient quantities;
- normalized canonical ingredient demands;
- product IDs, package counts, stores/contexts and normalized price-contract
  identities;
- exact totals and price per portion;
- nutrition, diversity and basket-audit results;
- source snapshot provenance and PriceUniverse identity.

Wall-clock timings, generation timestamps, recipe instruction prose and
display-only ordering are deliberately excluded from economic identity.

The historical fixed-menu membership fixture remains a pricing/eligibility
diagnostic. Its actual nutrition and diversity statuses are frozen rather than
being presented as passing: one recipe is below the current vegetable minimum,
and the menu exceeds the current balanced cooking-method repetition policy.
