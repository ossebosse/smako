# Willys Hemma Stortorget: retained flyer inventory, 2026-10-15

The customer reported HTTP 422 request
`3acc8226-628b-41a7-8fd4-a8340ca03e7c` at 09:49:26 UTC. The selected context
`context:willys:f3f63d6851275fcc` is the physical flyer context for Willys Hemma
Lund Stortorget, official store 2863. Both online Willys base catalogs were
qualified and loaded; this was a separate optional-source regression.

The prior picking-contract parser upgrade preserved the original explicit
`hasPickingBaseStore: false` in derived store metadata. Saved flyer inventories
from the previous parser already retained that flag in their original raw
register but omitted it from derived metadata. Exact inventory reconstruction
therefore differed at 258 metadata keys and rejected the approved flyer input.
The ordinary source builder reported `optional_configuration_error` and omitted
the context. The planner then correctly rejected the customer's selected
context rather than silently substituting another store.

A separate controlled live browser reproduction submitted the retained set of
29 contexts from the earlier Lund universe. It reproduced the same missing
Stortorget context in 25.8 seconds before this repair was activated. That
verification job is separate from the customer's request above.

Commit `ad285c415df4` keeps full raw reconstruction and strict picking validation.
It permits only the legacy omission of derived explicit-false metadata before
comparing every other inventory field exactly. The original saved evidence is
not edited. Changed identity, address, geography, selection and raw hash remain
blocked, as do true, null and non-boolean picking values.

75 focused tests passed: retained flyer inventory, physical flyer handling,
picking validation and municipal source artifacts. Positive selection is checked
for both Lund and Malmö. Ruff and compileall passed. A read-only proof against
the actual approved Lund databases inside the final image, with networking
disabled, loaded exactly the missing context and accepted all 16 source rows
with zero rejections. Their original source times and campaign dates are kept.

The activated scheduler changes only
`grocery_data/app/connectors/willys/flyer_inventory.py`; 629 other runtime files
are byte-identical to the actual active source image. The consumer app and
Windows relay require no code change for this repair.

- Build: `willys-flyer-retained-scheduler-ad285c415df4`.
- Image: `sha256:8f25b16ea86cf5cd93d385f87db7d20b73a2543bdc70cb9c08b7beb52ec15a10`.
- Runtime base: `sha256:58d27cb6e10dfbbf79aca7334d1596bbb3df281f6ac38b11bf70f9f1e8754390`.
- Private evidence: `.local/willys-flyer-inventory/` and
  `/opt/smako/evidence/willys-flyer-retained-20261015/`.

The earlier Windows task action change is now independently confirmed as
activated at 09:26:11 UTC, pointing to release `5b344ca3b50e`, with its schedule
and running task preserved. It is no longer a pending action.

## Activation and publication

Activated at **11:02:24 UTC** under the shared operations lease. The existing
09:45 scheduled refresh was allowed to complete before the lease was acquired.
Its Malmö Hemkop attempt failed before this release was activated; qualified
older base observations remained usable and both municipalities returned
readiness 200. That independent source warning is not cleared by this repair.

Current SQLite backups were verified at
`/opt/smako/evidence/willys-flyer-retained-20261015/backup-20261015T105559Z/`.
Only scheduler image and BUILD_ID changed in Compose. Source mounts,
environment and published price pointers were preserved during activation;
the consumer app container was not restarted.

The normal guarded publication passed preflight against the active reviewed
runtime. It uses the recovered original picking incident and full signature
as its existing publication anchor; no new source incident is fabricated from
the customer's 422. Action `publish` resumes the normal locked build/reload
pipeline without requesting a new base collection. Original source hashes,
observations and campaign windows are retained.

## Final load and customer-path verification

Publication and application reload were acknowledged at **11:19:36 UTC**;
the guarded publication completed with exit code 0 at 11:20:12 UTC. Disk,
loaded application and the durable physical-flyer publication receipt all name
`price-universe:5539233425d7b341ad9e0785adad69e461893356e71eedd3b5a9bb6ab3642aed`.
The published and reloaded source fingerprints match. This is the physical
flyer adapter's receipt; the earlier base-catalog relay receipt is a separate
source record and was not fabricated or rewritten for this publication.

Postcode **22225** now returns 29 usable contexts, including Stortorget at
`Stortorget 6`, still tied to source snapshot
`0441382043f343f0a1569f60368939b8`. All five mandatory Lund base contexts remain
qualified, published and loaded; readiness is 200.

The final real-browser test seeds the same older set of 29 specific contexts
and keeps Stortorget selected. Both Chromium and WebKit accept that retained
selection. One personal plan with dinner, breakfast and snack completed in
**87.5 seconds**, preserved every selected context, passed checkout audit and
total reconciliation, and returned the identical saved plan on GET/reload.
There were no page errors. Final evidence is `live/evidence.json` and
`live-check-final.log` in the private evidence directory. The initial browser
harness was corrected to seed tab-local `sessionStorage`; the production UI
was unchanged and publication was not repeated.

A separate public browser session produced five dinners for two people in
**10.031 seconds**, HTTP 201, with all 17 acceptance checks passing, including
checkout audit, nutrition quality and identical saved GET/reload. Evidence is
`public-lund/clean-balanced.json`.

At **11:24:17 UTC**, row hashes prove preservation of all **282 existing plan
revisions and 94 private states** from the activation backup. Counts after the
isolated successful tests are 284/95. The consumer app container is unchanged;
all three service containers are running with zero restarts.

## Rollback

Use the shared operation lease and restore this release's
`compose-wrapper.before`, then recreate only the scheduler from the runtime
base above. Keep customer plans and the current live database. Rolling the
source image back also restores the old inventory incompatibility, so review
the optional physical campaign source before another publication.
