# Smako VPS operations

Public origin: https://beta.smako.nu. SSH: `ssh smako`.
Release source: `/opt/smako/current` (symlink to `releases/local-relay-20260909b`).
The `/opt/smako/compose` wrapper invokes the existing deployment Compose file,
the host-path/TCP-only VPS override, and server-only `production.env`.

Runtime state is `/srv/smako/data`, backups `/srv/smako/backups`, restore scratch
`/srv/smako/restore`. Application data belongs to UID/GID 10001, with directories
0700 and files 0600. Environment file is administrator-owned, mode 0600.
Secrets were generated on the server; do not print or copy that file locally.

## Routine commands (run through ssh smako)

```sh
/opt/smako/compose ps -a
curl --fail --silent https://beta.smako.nu/health
curl --fail --silent https://beta.smako.nu/ready
/opt/smako/compose logs --tail 50 app
/opt/smako/compose --profile ops run --rm -T --no-deps backup-once
/opt/smako/compose up -d --no-build --no-deps --force-recreate app
```

For a new release, transfer only the required source files to a new directory
under `/opt/smako/releases`, validate hashes and `.dockerignore`, build an
immutable image tag with the existing Dockerfile, then update `current` and the
non-secret APP_VERSION/BUILD_ID fields in the server environment. Preserve the
previous image, source and data. Use the application-only rollback below to retain the corrected scheduler;
it does not alter prices or restore historical user data.
For PriceUniverse/source rollback use `production-backup-restore.md`.

## Verified restore with current deletion suppression

Export current deletion requests independently of the historical bundle:

```sh
/opt/smako/compose --profile ops run --rm -T --no-deps backup-once \
  python deploy/scripts/privacy_erasure_ledger.py export \
  --database /srv/app/var/grocery/grocery_data.sqlite \
  --output /srv/app/var/backups/privacy-ledgers/current.json

# The following is an isolated scratch restore. Substitute an existing valid
# bundle and unused scratch target; it does not activate restored production data.
BUNDLE=20260908T171716Z
/opt/smako/compose --profile ops run --rm -T --no-deps \
  -e GROCERY_DATABASE_URL=sqlite+pysqlite:////srv/app/var/restore/rehearsal2/grocery.sqlite \
  -e PLAN_STORE_PATH=/srv/app/var/restore/rehearsal2/plans.sqlite3 \
  -e PRICE_UNIVERSE_CACHE_ROOT=/srv/app/var/restore/rehearsal2/price_universes \
  backup-once python deploy/scripts/restore_sqlite.py \
  --bundle /srv/app/var/backups/$BUNDLE \
  --deletion-ledger /srv/app/var/backups/privacy-ledgers/current.json --confirm
```

A real restore requires stopping app/scheduler and following the existing
`production-backup-restore.md`. Never reopen historical user data without current
ledger replay. Missing/corrupt deletion information fails closed.

## Scheduler and source-data boundary

The scheduler is running. Stockholm schedules: backup 02:47, daily refresh 03:17,
Coop retry 06:17. Source jobs use the existing 7200-second bound, shared operation
lock, validation, atomic activation and LKG retention. Backups are independent:
DAILY_REFRESH_ENABLED=false and/or COOP_RETRY_ENABLED=false disable only those
price jobs. Do not stop the whole scheduler to disable a source job.

Cron opens its Docker log pipe as root, then runs Python as app through runuser.
A real isolated scheduled backup was created and validated on 2026-09-08; the
minute-by-minute rehearsal scheduler was stopped immediately afterwards.

The VPS now has the approved source-only store/context/identity registry and
original ICA external LKG cache. No historical user database was transferred.
A single normal managed refresh in smako-refresh-variation-20260908 completed
at 2026-09-08 20:27 UTC: DEGRADED, new validated universe 215f7d6905f9... active.
Coop 730400 and Hemkop 4123/4224 are newly collected; ICA uses unchanged Sep 7
LKG. Willys and Coop physical offers failed with ConnectorFetchError. Latest
pre-release backup 20260908T202737Z is complete and bundle-validated.
Use the following read-only commands for actual status; never infer observation
freshness from image/build time:

```sh
/opt/smako/compose ps
docker logs --tail 10 smako-refresh-variation-20260908
curl --fail https://beta.smako.nu/ready
/opt/smako/compose exec scheduler cat /etc/cron.d/grocery-beta
```

PRIMAT_API_KEY must be supplied by the operator directly in
/opt/smako/production.env using a secure SSH editor; keep chmod 600 and never
paste the value into chat, source control or logs. After setting it, recreate
only scheduler so subsequent scheduled jobs receive it:

The VPS wrapper does **not** read `/opt/smako/.env.production`. Verify only
whether the key is non-empty in the actual scheduler/cron environment; never
print the key or a full Compose configuration/environment dump.

```sh
/opt/smako/compose up -d --no-build --no-deps --force-recreate scheduler
```

A currently running refresh retains its original environment. Missing Primat
credentials preserve ICA LKG only while its ORIGINAL observation times remain
usable. No credential, source gate or freshness threshold is invented. Coop
remains the single approved ONLINE context 730400; physical offers stay separate.


## TLS and security

Caddy serves TCP 80/443 with public ACME TLS and durable certificate state under
`/srv/smako/data/caddy`. HTTP redirects to HTTPS. ACME contact is currently omitted;
the server Caddyfile removes only the optional email line, and its Compose email
variable accepts empty. To add a real operator contact, set ACME_EMAIL privately,
restore `email {$ACME_EMAIL}` in the global Caddy block, validate and recreate Caddy.
No secret value belongs in image layers or repository files.

UFW and SSH configuration are unchanged. Only Caddy publishes web ports; UDP 443
is deliberately not published. Uvicorn, Caddy admin and database ports are not
public. No container mounts the Docker socket. Docker is enabled at boot;
app/Caddy restart policies and exact saved-plan persistence were verified across
a real Docker service restart. Physical-phone camera acceptance and legal/privacy
approval remain external operator tasks.

Evidence is under `/opt/smako/evidence` and locally `D:/codex-smako-vps-20260908`.

## Structural menu v2 release and application-only rollback

Release source: /opt/smako/releases/variation-20260908. Image:
billigaste-veckomenyn:0.1.0-smako-variation-20260908,
sha256:34ed06d1c1f84040de8e8a0037b5be43b570a144376d06e615a9995e35209405.
No database migration or price refresh is part of this application image change.
Backups and source activation retain their independent operation lock and ledger.

After a release fault, the tested application-only rollback uses the previous
retained image and leaves the fixed scheduler, Caddy, prices and user data intact:

```sh
APP_VERSION=0.1.0-smako-beta-20260908 BUILD_ID=smako-rc-20260908-78a8df06 \
  /opt/smako/compose up -d --no-build --no-deps --force-recreate app
curl --fail https://beta.smako.nu/health
curl --fail https://beta.smako.nu/ready
```

This command pins that running container to the old image. Keep these overrides
on subsequent app recreation until the release fault is resolved; an unqualified
compose up uses the version in production.env. Roll forward with the new version:

```sh
APP_VERSION=0.1.0-smako-variation-20260908 BUILD_ID=structural-menu-v2-20260908 \
  /opt/smako/compose up -d --no-build --no-deps --force-recreate app
```

Do not restore an old database for this image-only rollback. If a data restore
is separately required, use the verified current-deletion-ledger procedure above.
The old and new images were exercised in isolation with the exact saved revision
and readiness preserved across both switches.

## Previous loading hotfix — 2026-09-09

Current app/UI: loading-hotfix-20260909, image
billigaste-veckomenyn:0.1.0-smako-loading-20260909,
sha256:aaa5fa342a4237e7f6f6510bb164438263393c78a174d802fe0d171e5f5e8415.
Only four static frontend files changed. Backup 20260909T072017Z is validated;
all 25 prior saved revisions retained exact row hashes. No data migration/refresh.
Existing users reload normally; shell-v5/versioned JS preserves sessions and plans.
Use this rollback for the CURRENT release (the earlier section is historical):

```sh
APP_VERSION=0.1.0-smako-variation-20260908 BUILD_ID=structural-menu-v2-20260908 \
  /opt/smako/compose up -d --no-build --no-deps --force-recreate app
curl --fail https://beta.smako.nu/ready
```

Keep the overrides on further recreation during rollback. Roll forward with
APP_VERSION=0.1.0-smako-loading-20260909 BUILD_ID=loading-hotfix-20260909 and the
same app-only command. No historical database restore is needed. Caddy/scheduler
stay running. The old release also restores the known saved-plan loading bug.
Full evidence: /opt/smako/evidence/smako-loading-hotfix-20260909.md and .json.

## Previous Balanced-conditioned Varied — 2026-09-09

Current app: `0.1.0-smako-conditioned-20260909`, build
`balanced-conditioned-v1-20260909`, source `releases/conditioned-varied-20260909`.
Image sha256:580749d6e44b9d90a156ca193300f243b1d05a6020615812bbb7b3f913ab74ab.
Existing Dockerfile/Compose used; only app recreated. Scheduler and Caddy were
not restarted. No source refresh, database migration or price activation.
Backup `20260909T120104Z` completed and passed the existing bundle validator.
All 36 pre-release plan revision rows remained byte-identical. Historical API
responses add only `plans.*.inter_plan_distance=null`; existing values are unchanged.

Public 22350/5 dinners/4 portions/max 2/no memberships: Balanced 275.52 SEK,
Varied 293.50 SEK, one exact overlap and three genuinely different dinners.
Four families/three methods; +17.98 SEK (6.53 %), ceiling 344.40 SEK.
Both public browser engines passed saved reload and repeated planning. The
loading hotfix remains included. Isolated/public HTTP smoke passed functional
checks but took 11.06/10.75 s, missing the existing 10-second target.

Application-only rollback retains the loading hotfix and all current data:

```sh
APP_VERSION=0.1.0-smako-loading-20260909 BUILD_ID=loading-hotfix-20260909 \
  /opt/smako/compose up -d --no-build --no-deps --force-recreate app
curl --fail https://beta.smako.nu/ready
```

Keep those overrides on subsequent recreation during rollback. Roll forward
with `APP_VERSION=0.1.0-smako-conditioned-20260909` and
`BUILD_ID=balanced-conditioned-v1-20260909` using the same app-only command.
Do not restore historical databases for this code-only change. Evidence:
`reports/smako-balanced-conditioned-20260909.md` and `.json`, plus VPS
`/opt/smako/evidence/conditioned-*`. The isolated test app is stopped.

## Current product search — 2026-09-09

Version `0.1.0-smako-search-20260909b`, build `product-search-v1.1-20260909`,
source `releases/product-search-20260909b`. Image:
`sha256:f40b2ed919a1f3384970e0eb9596d7662c304e5750b89657b2cfad10a3c198c3`.
Application-only release: no schema/source/PriceUniverse change. Index 24,132
products / 24,497 rows; requests exclude two stale ICA contexts. Backup
`20260909T132857Z` passed readback. 51 prior revisions are byte-identical;
one public smoke plan brought the count to 52. Scheduler/Caddy were not
recreated; `smako-search-candidate` is stopped. Evidence:
`reports/smako-product-search-20260909.md` and `.json`.

Public HTTPS and Chromium/WebKit mobile search passed with zero provider
egress. Planner cold timing still misses its pre-existing 10-second target
(11.18 s), with functional smoke PASS. Application-only rollback:

```sh
APP_VERSION=0.1.0-smako-conditioned-20260909 BUILD_ID=balanced-conditioned-v1-20260909 \
  /opt/smako/compose up -d --no-build --no-deps --force-recreate app
curl --fail https://beta.smako.nu/ready
```

Retain these overrides during rollback. Roll forward with
`APP_VERSION=0.1.0-smako-search-20260909b` and `BUILD_ID=product-search-v1.1-20260909`.
Keep current user data and prices; do not restore a historical database for
this image-only rollback or weaken freshness to re-enable ICA.

## Current: search coverage and ICA recovery, 9 September 2026

Release `search-coverage-20260909`, APP_VERSION `0.1.0-smako-coverage-20260909`,
BUILD_ID `search-coverage-v1-20260909`. Image
`sha256:1333cfa33d3fae6186494978efff2df1ea9e45afec334f3a01b75a362c96c416`.
Both app and scheduler were recreated. The canonical production.env now has
the operator-supplied Primat key; the actual cron environment was checked.
The serving app still receives no Primat key. Caddy is unchanged.

The managed build seam now takes an integrity-checked private SQLite copy
using the existing backup routine before invoking the immutable builder.
The shared refresh lock, source gates, observation times and atomic activation
remain unchanged. A live managed rebuild under HTTPS traffic passed with no
additional provider calls, reusing the fresh Primat cache. The private copy is
removed on success or error. Do not remove the builder's mutation guard.

ICA's 49-request bounded refresh succeeded; Willys' complete collection still
fails at HTTP 403 and remains excluded. Do not change source allowlists or
accept partial raw pages to restore Willys. See
`reports/smako-search-coverage-20260909.md` for the coverage matrix and evidence.
Backup `20260909T144544Z` validated; 52 prior plan revisions preserved.

Application-only rollback to the previous product-search release:

```sh
APP_VERSION=0.1.0-smako-search-20260909b BUILD_ID=product-search-v1.1-20260909 \
  /opt/smako/compose up -d --no-build --no-deps --force-recreate app
```

Keep these overrides for subsequent app recreation during rollback. Retain
the corrected scheduler and production.env credential; do not restore the
old environment backup or database for an app rollback. Roll forward using
APP_VERSION `0.1.0-smako-coverage-20260909`, BUILD_ID `search-coverage-v1-20260909`.
The previous release sections above are historical.


## Willys LOCAL_RELAY release — 2026-09-09

Current image tag: `billigaste-veckomenyn:0.1.0-smako-relay-20260909b`,
BUILD_ID `local-relay-v1.1-20260909`. Source is the reviewed overlay under
`releases/local-relay-20260909b`. See [relay runbook](willys-local-relay.md) and
[collection/import/ICA report](../reports/smako-local-relay-ica-20260909.md).

Willys remains OWN, with `WILLYS_COLLECTION_LOCATION=LOCAL_RELAY`. The existing
03:17 daily refresh independently validates inbox arrivals before normal source
promotion/build/activation. Direct Willys collection is disabled. Coop retry,
backup schedules, original observations, Primat credentials and other source
policies remain unchanged. No Windows task was installed. Daily local operation
requires the explicit operator commands/runbook; a successful pilot is not proof
of multi-day reliability.

Use UID/GID 10001 for all Python source/data operations. The host
`production.env` retains administrator UID/GID 1000 and mode 0600. Deployment
must preserve that file's existing owner/mode and unrelated lines. Validate the
new Compose configuration quietly before moving the current symlink. The VPS's
base Compose ACME_EMAIL fallback is intentionally optional, unlike the local
checkout; preserve that server setting when applying an overlay. Never copy
credentials to the local machine or print rendered Compose environment values.

Do not restore an old database or plans to roll back code. Both prior source
releases and images remain available. A pre-relay app can reject a relay-bearing
immutable artifact's product digest: it does not know the transport field.
Rollback across that schema addition requires the normal validated previous
PriceUniverse/LKG activation boundary, preserving current source observations
and saved-plan data; do not merely point an old app at the newest artifact.
The earlier relay-v1 image understands the optional provenance field, so it can
load the final artifact, though its search response omits the relay location.


## 2026-09-09 scheduled relay / ICA quality release

Current runtime release: `/opt/smako/releases/automation-ica-20260909`, build
`automation-ica-v1-20260909`, image
`sha256:277ac8601acf02831d22534d101ef91797e3298655e3d24b96a3d1353cf63761`.
Existing backup succeeded before app/scheduler deployment. Production environment
ownership/mode and existing TLS/Compose configuration were preserved. Normal ICA
and Willys activations and final HTTPS acceptance passed. Previous relay releases
are retained; do not restore databases/saved plans for a code rollback or point a
pre-relay image at a relay-bearing artifact. The final Windows-only PS7 installer
runs locally and does not affect server runtime code.
See [current milestone evidence](../reports/smako-automation-ica-20260909.md) and
[relay operations](willys-local-relay.md). Server evidence copies are kept under
`/opt/smako/evidence/automation-ica-20260909/`, outside the immutable release.
