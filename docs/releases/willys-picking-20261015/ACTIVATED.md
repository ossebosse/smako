# Willys picking-store contract, 2026-10-15

**Later update:** the Windows task change below was completed at 09:26:11 UTC
and its actual action was independently verified to use release `5b344ca3b50e`.
No further Windows action is pending. A subsequent source-only fix restores
Stortorget's retained physical flyer inventory; see the
[follow-up release](../willys-flyer-inventory-20261015/REPORT.md).
The activation evidence below records the earlier 08:40 verification state.

## Cause and reviewed change

Willys added `hasPickingBaseStore` to its store list and active-store responses.
The retained Lund responses from 2026-10-14 explicitly contain `false` for
contexts 2176 and 2354. Parser v5 rejected the resulting schema difference,
so newer source data was not published. This is separate from ordinary-price
retention, which remains active for every chain.

Commits `98eadc2b114c` and `5b344ca3b50e` introduce
`willys-parser-v6-picking-contract`. Transport, parser and independent artifact
qualification require exact store bindings and accept only absent or explicit
false picking metadata. True, null, wrong types, conflicting nested stores and
unrelated schema changes remain blocked. Original raw hashes and observation
times are preserved. Previously approved v3/v4/v5 relay artifacts remain
eligible for independent requalification by the current parser.

Incident: `source-28f02640d493c57dc843b0e5`.
Signature: `28f02640d493c57dc843b0e5adac77c8f91776a31680f33d6dd267aa2948ff7f`.
Rejected source: `6e5ed8fd7b8e414c8f0a244a4ad418e9`.
The reduced authentic fixture is
`grocery_data/tests/fixtures/willys-picking-store-20261014.json`.

## Verification and runtime

145 distinct focused test cases passed across Willys picking, parser, client,
nullable price, artifact, municipal, schema and Hemkop picking regressions.
Ruff and compileall passed. The exact retained relay artifact was independently
requalified both inside the final server image with networking disabled and
inside the installed Windows release: 19,294 price rows, 10,659 products and
1,267 raw files. No source timestamps were renewed.

Artifact SHA-256:
`5b2495fe3d2af7a2f312266f035bc461fabf90e0cffd4471fd387b9df27eb65b`.
Source observations: 2026-10-14 15:41:33–16:11:02 UTC.

The scheduler was activated at 2026-10-15 08:07:12 UTC under the shared
operations lock, after verified SQLite backups:

- Build: `willys-picking-scheduler-5b344ca3b50e`.
- Image: `sha256:58d27cb6e10dfbbf79aca7334d1596bbb3df281f6ac38b11bf70f9f1e8754390`.
- Prior image: `sha256:13057faa6cdbdeb67e73345c1f6f2324c7ff084e25796d1f16febb91afa8935e`.
- Original backup: `/opt/smako/evidence/willys-picking-5b344ca3b50e/backup-20261015T080331Z/`.
  Losslessly archived on 2026-10-18 to the adjacent
  `backup-20261015T080331Z.tar.gz`, after verifying all file hashes,
  ownership and permissions. The private inventory, receipt and `.ARCHIVED.txt`
  remain beside it. See [restoration and SHA-256](../../storage-maintenance.md).

Only six reviewed scheduler runtime files changed; 624 others were identical.
Only its image and BUILD_ID changed in Compose. The serving app container,
mounts, environment and price manifests were unchanged during activation.
The app remains `base-price-retention-app-0f54e51`.

The Windows package is installed and verified at
`D:\smako-local-relay\releases\5b344ca3b50e` (six changed files, 679 unchanged).
Its overlay was made against the actual prior Windows runtime, including the
reviewed nullable-price dependency; unrelated collector changes were excluded.
Changing the scheduled task action requires Windows administration. The UAC
launch was cancelled, so the task still references `7b7fe72472dd`; the running
Malmö collection was not interrupted. The prepared action-only change is
`.local/willys-picking-repair/activate_windows_admin.ps1`.

## Recovery and operational evidence

The guarded replay preview passed against the exact incident, signature and
active runtime. Recovery uses ordinary relay redelivery of the immutable
artifact, preserving municipal inventory, publication and receipt lineage.
No database replay was applied and no new Lund collection was requested.
Import, publication, load and durable receipt are verified separately below.

The first redelivery reached catalog persistence but stopped with SQLite
`SQLITE_BUSY`; the prior qualified source and published universe remained
active. The live database was confirmed to use WAL and the source operation
lease had been held. One bounded normal redelivery retry was started after
the failed process had exited. No lock was deleted and no quality gate changed.
A separate file-backed WAL probe passed import, duplicate detection and
normal promotion. The transient production lock's root cause is not
established by that probe.

The retry qualified and promoted snapshot `af0754d54da34321a66abf1b79168c8a`
with all 19,294 product rows. Normal publication, application load and durable
relay receipt completed at **08:36:37 UTC**. The receipt retains the exact
artifact hash and original 2026-10-14 observation times. Published and loaded
universe IDs both equal
`price-universe:632e1923465a2f0de140dd64fbea8d98e9e23a84755207c34577da9a4a5ddf42`.

Post-recovery status: Lund readiness HTTP 200; all five required source
contexts qualified, usable, published and loaded, without pending source
incidents or delayed publication for those contexts:

| Source context | Original observation (UTC) | State |
| --- | --- | --- |
| Coop Online Syd 730400 | 2026-10-14 12:45:18 | FRESH, loaded |
| Hemkop 4224 | 2026-10-15 02:46:04 | FRESH, loaded |
| Hemkop 4123 | 2026-10-14 22:01:03 | FRESH, loaded |
| Willys 2176 | 2026-10-14 15:41:42 | FRESH, loaded and receipted |
| Willys 2354 | 2026-10-14 16:00:57 | FRESH, loaded and receipted |

The incident index confirms `source_recovered` at 08:21:56 UTC with the new
qualified snapshot. Source recovery precedes the separate final receipt above.

Customer postcode **22225** was verified through the actual personal UI in
Chromium and WebKit. A new personal Lund plan with dinner, breakfast and snack
completed in **118.8 seconds**, used Willys products, passed checkout audit and
total reconciliation, and returned the identical saved plan on GET/reload.
Both municipalities returned readiness 200. Malmö still truthfully reports
older retained Willys base observations; its running collection is not claimed
as completed. Source-age warnings for other data are not cleared artificially.

At 08:40:02 UTC every pre-existing plan row was hash-verified against the
activation backup: **280 plan revisions and 93 private states preserved**.
After the isolated live tests, counts are 282/94. The serving app container is
unchanged and all three service containers are running with zero restarts.

An isolated real browser session in Malmö produced five dinners for two
people in 13.5 seconds (HTTP 201), passed all 17 acceptance checks, including
checkout audit and reconciled total, and preserved the exact plan on saved
GET/reload. No browser errors were observed. This verifies the existing
Malmö published universe while its normal source collection continues; it
does not claim that collection has finished or its new prices are published.

Private evidence is in `.local/willys-picking-repair/` and the server directory
above. It includes the runtime file reviews, package hashes, offline artifact
proofs, activation record and redelivery logs. Credentials, raw customer plans
and unrestricted task XML are not committed.

## Rollback

Under the shared operations lock, restore the saved Compose wrapper
`compose-wrapper.before` and recreate only the scheduler from the prior image.
Do not restore an older live database or overwrite saved customer plans.
The app and ordinary-price retention need no rollback. The Windows task still
uses its prior release until the pending administrator action is completed.

## Windows action recorded at 08:40 UTC (completed at 09:26 UTC)

The server repair and Lund recovery are complete. The scheduled Windows task
still uses `7b7fe72472dd`, as confirmed again at the final verification. Do not
describe the installed `5b344ca3b50e` package as the active scheduled runtime.
After Windows administrator approval, the prepared script changes only the
task's program arguments and working directory, preserves its complete XML
otherwise, and does not restart the running municipal collection. Read and
verify its `windows-activation.json` result and actual task action afterward.
No Git push or merge was performed.
