# Beta backup, restore and PriceUniverse rollback

The scheduler creates one bundle daily at 02:47 Europe/Stockholm, before the
potentially long 03:17 source refresh. It first
acquires the same cross-process lock as refresh, so database and manifest state
cannot advance while the bundle is captured. Default retention is 14 days. A
bundle contains:

- an online, transactionally consistent backup of the grocery SQLite database;
- an online backup of the WAL-enabled consumer-plan database;
- every active municipal PriceUniverse manifest and its exact content-addressed blob;
- each corresponding active closed external-provider manifest and its exact blob;
- the municipality registry, current source pointers, hash-bound source databases,
  source configuration and protected operations journals for registered scopes;
- a SHA-256/size manifest for every file.

Recovery scope version 2 is additive to the existing bundle format. Restore uses
the same configured container data paths, preserving immutable source hashes and
observation times. Historical source attempt trees are not copied. Adding a
municipality changes the registry hash and makes a new complete backup due.
The existing demand worker retries a missed daily backup under the same operation
lock; a failed backup has a 30-minute retry delay and does not prevent source work.
The protected `reports/operations/backup-status.json` records complete, deferred
or failed outcomes and is included in the operations status response.

The bundle manifest also contains content-free semantic fingerprints for the
following persisted state:

- `collector_runs`, `catalog_snapshots`, raw-snapshot metadata,
  `connector_health` and `store_context_links` (source freshness and LKG);
- community observations/moderation, receipt ingestions, beta feedback,
  first-party analytics, frontend errors and request metrics;
- saved-plan revisions;
- the exact active PriceUniverse and external-provider LKG pointers, snapshot
  set, artifact hashes and their existing source timestamps.

Only row counts and SHA-256 values enter this inventory; report text, email,
actor hashes and other row values are not copied into `manifest.json`. The
restore recomputes every available fingerprint after the atomic file swaps and
fails if any differ. Bundles created before this additive inventory remain
restorable, but are reported as `legacy_bundle_file_hash` rather than claiming
the stronger semantic check.

Raw snapshots and refresh reports already live on durable bind mounts. They are
not recopied into every daily SQLite bundle because their volume is materially
larger; take a daily provider/block-storage snapshot of `deploy/runtime` in
addition to these portable bundles if the host supports it. Raw receipt images
are not retained by product policy.

## Manual backup

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm backup-once
```

The script uses SQLite's online backup API and runs `PRAGMA quick_check` on both
destinations before atomically publishing the bundle. The private backup copies
are finalized in DELETE journal mode before hashing, so a live WAL source yields
a self-contained bundle without WAL/SHM sidecars. The source journal mode and
committed source rows remain unchanged. Copy completed bundles to
encrypted storage outside the server. A backup stored only on the same disk is
not disaster recovery. Backup directories are forced to mode 0700 and bundle
files to 0600 on POSIX; Windows runs the same restriction best-effort.

## Non-destructive restore rehearsal

Run this at least once before inviting beta users. It restores into a scratch
directory inside the backup volume, not the live paths:

```bash
BUNDLE=/srv/app/var/backups/20260901T024700Z
LEDGER=/srv/app/var/backups/privacy-ledgers/current.json

docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm -T --entrypoint python backup-once \
  deploy/scripts/privacy_erasure_ledger.py export \
  --database /srv/app/var/grocery/grocery_data.sqlite --output "$LEDGER"

docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm \
  -e GROCERY_DATABASE_URL=sqlite+pysqlite:////srv/app/var/backups/restore-test/grocery.sqlite \
  -e PLAN_STORE_PATH=/srv/app/var/backups/restore-test/plans.sqlite3 \
  -e PRICE_UNIVERSE_CACHE_ROOT=/srv/app/var/backups/restore-test/price_universes \
  --entrypoint python backup-once \
  deploy/scripts/restore_sqlite.py --bundle "$BUNDLE" \
  --deletion-ledger "$LEDGER" --confirm
```

Then verify both databases:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm --entrypoint python backup-once -c \
  "import sqlite3; assert sqlite3.connect('/srv/app/var/backups/restore-test/grocery.sqlite').execute('pragma quick_check').fetchone()[0] == 'ok'; assert sqlite3.connect('/srv/app/var/backups/restore-test/plans.sqlite3').execute('pragma quick_check').fetchone()[0] == 'ok'; print('restore test: PASS')"
```

Record the rehearsal date and result in the operator log. Do not call a backup
tested merely because files exist.

The restore command itself must finish with `verification.status=verified`.
New bundles report `semantic_and_file_hash` for grocery data, plans and
PriceUniverse. The command does not run migrations, touch source rows or
replace any source clock with the restore time. `created_at` in the outer
backup manifest is only the time at which the backup was captured; it is never
used as a price observation time.

After the scratch restore, compare these values with the bundle's
`state_integrity` section before deleting the scratch directory:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm -T --entrypoint python backup-once - <<'PY'
import json
from pathlib import Path

bundle = Path("/srv/app/var/backups/20260901T024700Z")
manifest = json.loads((bundle / "manifest.json").read_text())
state = manifest["state_integrity"]
print("PriceUniverse:", state["price_universe"]["universe_id"])
print("Source timestamps:", state["price_universe"]["timestamps"])
print(
    "Source/LKG fingerprint:",
    state["grocery_database"]["source_freshness_and_lkg"]["sha256"],
)
print(
    "Community/report fingerprint:",
    state["grocery_database"]["community_and_beta_reports"]["sha256"],
)
PY
```

## Full database restore

### Privacy erasure gate before reopening

Self-service erasure affects the active databases immediately, but a backup
captured before the erasure can still contain the former rows for up to the
configured 14-day retention period. The application writes actor-free
`privacy_erasure_suppressions` rows containing only opaque target record IDs so
the restore can identify what must stay suppressed if an older bundle is used.

Database restore now fails closed and performs this sequence automatically:

1. validate every historical bundle hash and active artifact pair;
2. atomically export and read back the current suppression ledger to an
   independent file before replacing anything, or validate the operator's
   explicit ledger export;
3. copy both historical databases to isolated files beside their targets and
   verify their hashes, SQLite integrity and semantic inventory;
4. replay the current ledger idempotently against those isolated copies;
5. verify every suppression plus unchanged source-freshness/LKG state;
6. only then atomically replace the stopped deployment's database files.

Feedback, product analytics, frontend errors, request metrics and saved plans
named by the ledger are hard-deleted. Community observations and parsed receipt
facts remain under the existing evidence policy, but their actor links are
replaced with distinct row-specific unlinking markers. These retained factual
rows are **unlinked, not claimed to be anonymous**; their content and legal
status still require the documented privacy review.

For a normal restore the command captures the current ledger directly from the
active grocery database. Before planned maintenance, also create an independent
portable export (and copy it to the same encrypted off-host storage as the
backup) so a disk-loss restore does not depend on that database file:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm -T --entrypoint python backup-once \
  deploy/scripts/privacy_erasure_ledger.py export \
  --database /srv/app/var/grocery/grocery_data.sqlite \
  --output /srv/app/var/backups/privacy-ledgers/current.json
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm -T --entrypoint python backup-once \
  deploy/scripts/privacy_erasure_ledger.py verify \
  --ledger /srv/app/var/backups/privacy-ledgers/current.json
```

The export writes a same-filesystem temporary file, flushes it, validates its
entry digest, and atomically replaces `current.json`. Never copy a partial/temp
file. After any known erasure, refresh the independent export before rotating
the off-host copy.

If the current database is absent, pass the current independent export:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm -T --entrypoint python backup-once \
  deploy/scripts/restore_sqlite.py \
  --bundle /srv/app/var/backups/20260901T024700Z \
  --deletion-ledger /srv/app/var/backups/privacy-ledgers/current.json \
  --confirm
```

If current deletion information is missing, corrupt, has an unsupported target
or fails its digest, restore stops before target activation. Do not start the
application: keep the historical copy isolated until a current valid ledger is
available or every backup that might contain the deleted data has expired and
been purged under the approved retention process.

This is intentionally explicit and requires downtime:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production stop app scheduler

docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm --entrypoint python backup-once \
  deploy/scripts/restore_sqlite.py \
  --bundle /srv/app/var/backups/20260901T024700Z --confirm

docker compose -f deploy/compose.yaml --env-file deploy/.env.production up -d
```

The restore acquires the same cross-process lock as refresh/backup even though
the operator must stop both writers first. A running refresh therefore makes
restore fail instead of racing an active-manifest or database swap. It verifies
every bundle hash and each SQLite database before staging
files beside the targets. It keeps a timestamped `before-restore` copy and uses
`os.replace` for the final swap, with restored/rollback files at mode 0600 and
parent directories at 0700. Stop both writers first; restoring a live WAL
database is unsupported.

The lock key can be derived safely before the exact SQLite target exists, so a
verified bundle can restore into a new/scratch runtime after a disk-loss event.
Its nearest existing parent and the configured PriceUniverse root still define
the canonical data plane; an absent target does not disable serialization.

After startup, require `/ready` to pass and confirm that recent community
reports, one saved plan and the expected PriceUniverse ID are visible.
Also compare `/ready.price_universe` and `/admin` source ages with the restored
manifest's original `oldest_observed_at`; a restore must make old data appear
old, never fresh. If raw snapshot replay or historical refresh reports are
needed after full disk loss, restore the matching provider/block-storage copy
of `runtime/raw_snapshots` and `runtime/reports` as well. Their payload files
are deliberately not duplicated in every portable SQLite bundle.

## PriceUniverse-only rollback

Price rollback does not require rolling back user reports or plans:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production stop scheduler

docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm --entrypoint python backup-once \
  deploy/scripts/restore_sqlite.py \
  --bundle /srv/app/var/backups/20260901T024700Z \
  --only-price-universe --confirm

docker compose -f deploy/compose.yaml --env-file deploy/.env.production restart app
docker compose -f deploy/compose.yaml --env-file deploy/.env.production start scheduler
```

The immutable blobs are copied first and the backed-up active manifest is
replaced last. The shown controlled app restart loads and hash-validates the
restored artifact; an authenticated internal reload is an equivalent operator
action when the app remains running. Verify `/ready` and the expected
PriceUniverse ID after either path. If reload validation fails,
the serving process retains its previous in-memory LKG; investigate rather than
forcing an unvalidated artifact.

Source freshness and LKG metadata live in the grocery database and deliberately
have no independent source-only rollback command. Use the verified full restore
when those records must be rolled back; that also restores the paired user and
plan databases and reapplies the current deletion ledger. `--only-price-universe`
changes only immutable pricing artifacts and must not be described as a source
metadata rollback.

## Retention and constraints

- Default: 14 daily portable bundles; configurable from 1â€“365 days.
- Keep at least one off-host encrypted copy.
- Never store `.env.production`, provider credentials or Caddy private key data
  inside the application backup bundle.
- A portable bundle alone restores active pricing, source/LKG metadata,
  community/report database rows and saved plans. Full forensic history also
  requires the separately encrypted host snapshot of `raw_snapshots/` and
  `reports/`; do not claim otherwise.
- SQLite is for one application worker on one server. PostgreSQL is the next
  step before multiple replicas, not a requirement for 5â€“20 low-write beta
  users.
