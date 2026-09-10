# Public beta deployment (Lund)

This runbook is the reproducible production path for the first 5â€“20 anonymous
beta users. It does not create a hostname or a server. The operator must supply
a Linux host, DNS and the provider credentials already approved by the project.

## Architecture

```text
public phone
    â”‚ HTTPS :443 (HTTP/3 where available)
    â–¼
Caddy 2 â”€â”€ automatic ACME TLS, security headers, access log disabled
    â”‚ private Compose network; 60 s bounded burst response-header timeout
    â–¼
one Uvicorn/FastAPI worker
    â”œâ”€â”€ immutable PriceUniverse loaded once, then atomically hot-swapped
    â”œâ”€â”€ /var/grocery/grocery_data.sqlite (community/physical/source metadata)
    â””â”€â”€ /var/plans/consumer_plans.sqlite3 (append-only saved plan revisions)

separate cron container
    â”œâ”€â”€ 02:47 Europe/Stockholm: SQLite + active-artifact backup
    â”œâ”€â”€ 03:17 Europe/Stockholm: existing managed daily-refresh
    â”œâ”€â”€ internal authenticated runtime reload after usable activation
    â””â”€â”€ rejected reload restores LKG; unreachable app defers to restart
```

The application port is not published. Only Caddy exposes ports 80/443. Both
Caddy request access logs and Uvicorn access logs are deliberately disabled;
the backend keeps only allowlisted structured operational events. No ingress
access-log record of client IP addresses or URL query strings is persisted.
Plan share IDs use URL fragments, which browsers do not send with the document
request. Camera and
barcode access therefore use a normal secure origin; no localhost or quick
tunnel is part of the production path.

Every Compose service uses Docker's bounded `json-file` driver with five
10 MiB segments. This caps retained container stdout/stderr near 50 MiB per
service while preserving the backend's allowlisted operational records. Log
rotation does not re-enable Caddy or Uvicorn request access logging. Export
longer-lived operational aggregates explicitly rather than increasing local
container logs without a disk-capacity review.

One application worker is intentional for the small beta: it keeps one loaded
PriceUniverse/cache, avoids multiplying its memory footprint and keeps SQLite
writes simple. Do not scale the worker count horizontally while using these
single-host SQLite files.

## Persistent state

All mutable paths are bind-mounted below `deploy/runtime` by default. Set the
host-only Compose variable `RUNTIME_ROOT` to an absolute directory to keep an
isolated rehearsal on another filesystem; container paths and the deployment
architecture remain unchanged.

| Host directory | Container path | Contents |
| --- | --- | --- |
| `grocery/` | `/srv/app/var/grocery` | community reports, physical observations, source/snapshot metadata |
| `plans/` | `/srv/app/var/plans` | immutable saved-plan revisions |
| `price_universes/` | `/srv/app/var/price_universes` | content-addressed artifacts, active manifests, external LKG cache |
| `raw_snapshots/` | `/srv/app/var/raw_snapshots` | source snapshots created by refresh |
| `reports/` | `/srv/app/var/reports` | credential-safe refresh/operations reports |
| `backups/` | `/srv/app/var/backups` | daily verified backup bundles |

Caddy certificate state uses the named volumes `caddy_data` and
`caddy_config`. `docker compose down` does not remove any of these. Never run
`docker compose down -v` during normal operations.

## Environment and storage preflight

Do this before any build. A failed `docker info` means the daemon is not
available: stop there and repair/start Docker rather than treating Compose
configuration validation as a build. These checks are read-only; do not run a
prune as part of preflight.

```powershell
docker version
docker compose version
docker context show
docker info
docker system df
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
wsl.exe --version
wsl.exe --list --verbose
Get-PSDrive -Name C,D | Select-Object Name,Used,Free
[System.IO.Path]::GetTempPath()
(Get-Location).Path
Get-Process -Name '*docker*' -ErrorAction SilentlyContinue |
  Select-Object ProcessName,Id,Path
```

On Linux also record the daemon's reported root and space on every actual
target filesystem:

```bash
docker info --format '{{.DockerRootDir}}'
docker system df
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
df -h . /tmp "$(docker info --format '{{.DockerRootDir}}')"
```

Docker Desktop's Linux `Docker Root Dir` is inside its disk image. Record the
physical disk-image location from Docker Desktop **Settings â†’ Resources â†’
Advanced** as well as free space on that Windows drive. If the image is on a
nearly full drive, move it only through that operator UI while Docker is
stopped; do not move its VHDX or WSL files by hand. Leave a capacity margin for
both the final image and transient build layers.

For a Windows Docker Desktop rehearsal, keep the project name and mutable data
separate from any active deployment. Forward slashes avoid drive-letter parsing
ambiguity in Compose. These commands only validate configuration and start the
`migrate`/`app` subset; they do not start Caddy, the scheduler, or a live source
refresh:

```powershell
$runtime = 'D:\codex-rc\billigaste-veckomenyn\runtime'
$runtimeDirs = 'grocery','plans','price_universes/active',
  'price_universes/artifacts','raw_snapshots','reports','backups'
$runtimeDirs | ForEach-Object {
  New-Item -ItemType Directory -Path (Join-Path $runtime $_) -Force | Out-Null
}
$env:RUNTIME_ROOT = $runtime.Replace('\', '/')
$env:COMPOSE_PROJECT_NAME = 'billigaste-veckomenyn-rc'
$env:APP_VERSION = '0.1.0-rc-local'
$env:BUILD_ID = 'rc-local-20260907'
$env:PUBLIC_BASE_URL = 'https://rc.local.invalid'
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$secretBytes = New-Object byte[] 32
$tokenBytes = New-Object byte[] 32
$rng.GetBytes($secretBytes)
$rng.GetBytes($tokenBytes)
$rng.Dispose()
$env:SECRET_KEY = [Convert]::ToBase64String($secretBytes)
$env:BETA_ADMIN_TOKEN = [Convert]::ToBase64String($tokenBytes)
$env:PLANNER_RATE_LIMIT_REQUESTS = '1000'
$env:PLANNER_NETWORK_RATE_LIMIT_REQUESTS = '1001'

# Seed only the hash-verified canonical PriceUniverse. Migrations create a new,
# small grocery database and the app creates a new plan database on D:.
$sourceRoot = (Resolve-Path 'price_universes').Path
$sourceManifest = Join-Path $sourceRoot 'active\city-lund.json'
$manifest = Get-Content -Raw -LiteralPath $sourceManifest | ConvertFrom-Json
$sourceArtifact = Join-Path $sourceRoot ($manifest.artifact_file -replace '/', '\')
$targetUniverse = Join-Path $runtime 'price_universes'
$targetArtifact = Join-Path $targetUniverse ($manifest.artifact_file -replace '/', '\')
New-Item -ItemType Directory -Path (Split-Path $targetArtifact) -Force | Out-Null
Copy-Item -LiteralPath $sourceArtifact -Destination $targetArtifact
Copy-Item -LiteralPath $sourceManifest `
  -Destination (Join-Path $targetUniverse 'active\city-lund.json')
$copiedArtifact = Get-Item -LiteralPath $targetArtifact
$copiedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $targetArtifact).Hash.ToLowerInvariant()
if ($copiedArtifact.Length -ne [int64]$manifest.artifact_bytes -or
    $copiedHash -ne ([string]$manifest.artifact_sha256).ToLowerInvariant()) {
  throw 'isolated PriceUniverse copy failed hash/size validation'
}

function Wait-RcApp {
  for ($attempt = 0; $attempt -lt 60; $attempt++) {
    $container = docker compose -f deploy/compose.yaml `
      --env-file deploy/.env.production.example ps -q app
    if ($container -and
        (docker inspect --format '{{.State.Health.Status}}' $container) -eq 'healthy') {
      return
    }
    Start-Sleep -Seconds 2
  }
  throw 'isolated app did not become healthy'
}

docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example config --quiet
docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example build app
docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example up -d app
Wait-RcApp
docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example exec -T app `
  python deploy/scripts/production_smoke.py `
    --base-url http://127.0.0.1:8000 --allow-http `
    --output /srv/app/var/reports/release-candidate-smoke.json

$before = docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example exec -T app python -c `
  "import sqlite3; print(sqlite3.connect('/srv/app/var/plans/consumer_plans.sqlite3').execute('select count(*) from consumer_plan_revisions').fetchone()[0])"
docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example up -d --force-recreate --no-deps app
Wait-RcApp
docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example ps
$after = docker compose -f deploy/compose.yaml `
  --env-file deploy/.env.production.example exec -T app python -c `
  "import sqlite3; print(sqlite3.connect('/srv/app/var/plans/consumer_plans.sqlite3').execute('select count(*) from consumer_plan_revisions').fetchone()[0])"
if ([int]$before -lt 1 -or [int]$after -ne [int]$before) {
  throw 'saved-plan persistence check failed'
}
```

The example env plus process-local random values above is rehearsal-only; do
not reuse those values or a production env file. The default
`RUNTIME_ROOT=./runtime` remains the production layout. Do not point the
rehearsal at active databases, manifests, snapshots, or backups.

SQLite is proportionate for one process and 5â€“20 beta users. The plan database
already uses WAL. The larger grocery database is currently DELETE-journalled;
refresh is therefore scheduled during a low-traffic window, uses bounded
transactions and has a 30-second SQLite busy timeout. Reassess PostgreSQL before
multiple app replicas or materially higher write concurrency. The storage layer
already supports PostgreSQL, but this milestone deliberately does not migrate
for architectural fashion.

## Prerequisites

1. A small Linux server with Docker Engine and the Compose plugin.
2. A real DNS `A`/`AAAA` record pointing at it.
3. Inbound TCP 80/443 and UDP 443 allowed; application port 8000 remains closed.
4. At least 4 CPU cores, 8 GiB RAM and 20 GiB durable disk for the initial beta.
   Adjust after the measured concurrency report, not by assumption.
5. A verified active Lund database and PriceUniverse artifact transferred from
   the current trusted environment.

## First deployment

From the repository root:

```bash
umask 077
cp deploy/.env.production.example deploy/.env.production
chmod 600 deploy/.env.production
```

Set a real `PUBLIC_BASE_URL`, ACME email, immutable release/build ID, independent
minimum-32-byte `SECRET_KEY` and `BETA_ADMIN_TOKEN` values, and the existing
approved Primat credential. Do not commit the file. `APP_ENV` and
`PUBLIC_BASE_URL` are product/deployment metadata; retailer passwords are
neither requested nor supported.

Seed an empty runtime with an online SQLite backup rather than copying a live
WAL database byte-for-byte:

```bash
python3.12 -m deploy.scripts.seed_runtime \
  --grocery-db .lund_production_refresh_20260826_v2.sqlite \
  --plan-db data/consumer_plans.sqlite3 \
  --price-universe-root price_universes \
  --raw-snapshot-root raw_snapshots

sudo chown -R 10001:10001 deploy/runtime
sudo find deploy/runtime -type d -exec chmod 700 {} +
sudo find deploy/runtime -type f -exec chmod 600 {} +
```

The seeder refuses to overwrite an existing database or active manifest. Move
the source state through an encrypted operator channel; never bake it or a
provider key into the Docker image. The seeder and backup/restore scripts also
enforce owner-only directory/file modes (0700/0600); the explicit `umask`,
`chown` and `find` checks are deployment defense-in-depth and ensure container
UID 10001 can read the mounted state.

Validate and start:

```bash
docker compose \
  -f deploy/compose.yaml \
  --env-file deploy/.env.production \
  config --quiet

docker compose \
  -f deploy/compose.yaml \
  --env-file deploy/.env.production \
  build

# Preserve a verified pre-migration bundle, then bring the transferred database
# to the repository's exact Alembic head.
docker compose \
  -f deploy/compose.yaml \
  --env-file deploy/.env.production \
  --profile ops run --rm backup-once

docker compose \
  -f deploy/compose.yaml \
  --env-file deploy/.env.production \
  run --rm migrate

# The transferred artifact may be close to its freshness limit. Run one full
# preflight refresh before opening public ingress; this direct CLI invocation
# does not need the serving process or its hot-reload endpoint.
docker compose \
  -f deploy/compose.yaml \
  --env-file deploy/.env.production \
  --profile ops run --rm refresh-once \
  python -m grocery_data daily-refresh \
    --city Lund --postal-code Lund=22350 \
    --price-universe-cache-root /srv/app/var/price_universes \
    --report-dir /srv/app/var/reports/refresh --format json

docker compose \
  -f deploy/compose.yaml \
  --env-file deploy/.env.production \
  up -d
```

`migrate` runs Alembic to `head` before the app. The app then hash-validates the
active PriceUniverse and fails readiness rather than starting without it.

Verify from outside the server:

```bash
curl --fail --silent --show-error https://beta.example.se/health
curl --fail --silent --show-error https://beta.example.se/ready
curl --fail --silent --show-error https://beta.example.se/manifest.webmanifest
```

Open the same HTTPS URL on a phone and explicitly test camera permission and a
known EAN-13. TLS cannot be considered verified from Compose configuration
alone: ACME issuance requires working DNS and public ingress.

Then run the provider-free production acceptance command from another machine:

```bash
python deploy/scripts/production_smoke.py \
  --base-url https://beta.example.se \
  --output reports/public-beta/production-smoke.json
```

The exact external-host and real-phone evidence to record is listed in
[beta-go-checklist.md](beta-go-checklist.md). A local `--allow-http` rehearsal
must never be reported as public HTTPS acceptance.

## Daily refresh and runtime activation

The dedicated scheduler executes at `DAILY_REFRESH_CRON` (the machine-readable
five-field expression). `DAILY_REFRESH_SCHEDULE` is the matching human-readable
label exposed by the admin status; keep the two values aligned. It runs:

```bash
python -m grocery_data daily-refresh \
  --city Lund \
  --postal-code Lund=22350 \
  --price-universe-cache-root /srv/app/var/price_universes \
  --report-dir /srv/app/var/reports/refresh \
  --format json
```

It uses only the existing approved source strategies and the managed production
graph. It never runs from a meal-planning request. The managed command:

1. takes a cross-process refresh lock;
2. collects each OWN source behind an isolated failure boundary;
3. refreshes or explicitly retains the closed external cache;
4. builds an inactive candidate;
5. validates schema, representative basket, lineage, freshness and SHA-256;
6. stores a content-addressed immutable artifact;
7. atomically replaces only `active/city-lund.json` on success.

The shared data-plane lock is a kernel-managed advisory file lease (`flock` on
Linux; a byte-range lock on Windows), not a PID-only stale-file decision. It is
released automatically after a process/container crash and cannot be fooled by
PID 1 reuse or separate container PID namespaces. The persistent lock file
records an opaque boot/process-start identity, PID and nonce only as diagnostic
and handoff metadata. Backup and restore use the same lease.

The external wrapper has a bounded two-hour default timeout
(`REFRESH_TIMEOUT_SECONDS=7200`). The bound reflects a measured Willys-only
collection of roughly 25 minutes before the remaining Lund sources and universe
build. A timed-out collector is terminated, the runtime reload is skipped and
the existing disk/in-memory LKG remains active.

A failed candidate is never promoted. A usable previous manifest remains LKG.
Exit 0 means complete, 2 means degraded but usable, and 1 means no usable
result. After exit 0 or 2, the wrapper calls the authenticated internal
`POST /api/admin/reload-price-universe`; that endpoint repeats hash/schema
validation and swaps the process-local immutable runtime. Reload failure leaves
the previous in-memory universe serving, atomically restores the pre-refresh
active manifest as the restart target, keeps the immutable failed candidate for
diagnostics, and makes the wrapper fail.

The outer wrapper holds the data-plane lease continuously from before it reads
the previous manifest, through the managed CLI subprocess, and until hot reload
or rollback is complete. The child skips its nested lock only after validating
the parent's exact nonce, PID/process-start identity and still-held kernel
lease. This prevents backup, restore or a second refresh from racing runtime
activation or making rollback overwrite a newer manifest.

Manual dry run and one-shot execution:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  run --rm refresh-once \
  python -m grocery_data daily-refresh --city Lund --dry-run --format human

docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  --profile ops run --rm refresh-once
```

Operational evidence is written to `runtime/reports/refresh` and
`runtime/reports/operations/refresh-runner-status.json`; reports contain only
allowlisted state and exception classes, not response bodies, cookies or keys.

The scheduler depends only on a completed database migration, not on the app.
This is intentional: a missing PriceUniverse can make the app restart before
`/ready` exists, and the scheduled refresh must still be able to repair it.
When the app is unreachable after a successful disk activation, hot reload is
marked deferred and the valid candidate remains the restart target. An explicit
HTTP rejection instead restores the earlier LKG pointer. The backup runs before
refresh so a valid long collection does not systematically collide with the
cross-process backup lock.

Review-gated collectors stay disabled unless an operator supplies the exact
already-verified context allowlist. Do not turn a skipped REVIEW connector into
a broad crawl merely to make the dashboard green.

Freshness is enforced per retained price context at request time as well as at
build time. If one provider LKG crosses `MAX_PRICE_AGE_HOURS`, that context and
all of its product candidates are excluded before economic ranking; the other
current contexts remain available. `/ready` then stays green with PriceUniverse
status `degraded`, while admin/plan metadata reports the number and IDs of the
excluded contexts and the consumer sees a limited-coverage warning. If no
context remains current, status is `stale` and planning/readiness fail closed.
Never raise the global age limit simply to hide a repeatedly failing source.

## Deploy and application rollback

Build every release under an immutable `APP_VERSION`/`BUILD_ID`, retain the
previous local image (or push it to a private registry), then run:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production up -d
```

To roll back application code, restore the previous version in
`.env.production` and start without rebuilding:

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production \
  up -d --no-build
```

Application rollback does not alter prices or databases. PriceUniverse rollback
is separate and documented in [production-backup-restore.md](production-backup-restore.md).
The PWA uses network-first revalidation for navigation, `app.js`, `styles.css`
and the other mutable shell files, updating its offline cache after every
successful response. An online client therefore receives the rolled-back shell
without depending on a manually bumped cache name; the cached shell is used
only when the network is unavailable. The offline fallback is not itself a
release rollback mechanism.

## Reproducible image updates

The Python and Caddy base images are pinned by exact tag and multi-platform OCI
digest. Direct Python runtime dependencies are exact-version pinned in
`deploy/requirements.txt`. Update them only in a dedicated release change:

1. resolve and test the intended Python dependencies in a clean Python 3.12
   environment;
2. replace every exact version, run the complete test/build suite, and record
   the dependency diff;
3. inspect image indexes with `docker buildx imagetools inspect <image>` and
   replace both the human-readable tag and digest;
4. rebuild with `--pull --no-cache`, run readiness/mobile acceptance, then keep
   the prior immutable application image for rollback.

Never change a tag while retaining an old digest, or remove the digest merely
to pick up an update implicitly.

## Capacity benchmark

The benchmark client deadline defaults to 65 seconds, just above Caddy's
explicit 60-second cold-burst response SLA. It records an explicit SLA
PASS/FAIL. The app admits one CPU-heavy plan build and at most four distinct
waiters (`PLANNER_MAX_CONCURRENT_REQUESTS=1`,
`PLANNER_MAX_QUEUED_REQUESTS=4`); further requests receive a quick 503 with
`Retry-After` instead of accumulating an unbounded queue.
Optionally point it at the Uvicorn PID to sample CPU, RSS and peak RSS through
portable Windows/Linux process APIs:

```bash
APP_CID=$(docker compose -f deploy/compose.yaml \
  --env-file deploy/.env.production ps -q app)
APP_HOST_PID=$(docker inspect -f '{{.State.Pid}}' "$APP_CID")
python backend/scripts/benchmark_beta_capacity.py \
  --base-url https://beta.example.se --concurrency 5 \
  --target-pid "$APP_HOST_PID"
```

Use the host PID from `docker inspect`, not PID 1 from inside the container. The
command exits nonzero for either request errors or a 60-second burst-SLA miss.

Run concurrency 1 and 5 against separately restarted app processes when
measuring request-cold capacity. A fresh five-request burst completed 5/5 with
zero errors, p95 39.44 seconds, wave time 39.87 seconds, 99.6% sampled CPU and
825.7 MiB peak RSS. Concurrency 10 is an admission/overload test: at most five
requests are admitted (one active plus four queued) and the remainder should
receive a quick 503; it is not evidence of ten-user cold-planning scalability.
The individual request-cold target remains below 10 seconds and warm remains
below 1 second; burst queue latency is reported separately. The JSON report contains aggregates only: no
plan ID, request body, IP address, query string, cookie or error response body.

## Useful operations

```bash
docker compose -f deploy/compose.yaml --env-file deploy/.env.production ps
docker compose -f deploy/compose.yaml --env-file deploy/.env.production logs -f app caddy scheduler
docker compose -f deploy/compose.yaml --env-file deploy/.env.production exec app \
  python -m grocery_data status --city Lund --format human
docker compose -f deploy/compose.yaml --env-file deploy/.env.production exec -T scheduler \
  python -c "import json; from pathlib import Path; paths=(Path('/srv/app/var/reports/operations/refresh-runner-status.json'), Path('/srv/app/var/reports/operations/source-retry-status.json')); [(print(p), print(json.dumps(json.loads(p.read_text()), indent=2))) for p in paths if p.is_file()]"
```

Admin/readiness endpoints must remain cheap and local: they inspect database,
refresh reports and active artifact state but never call a grocery provider.

During the beta, a user can request review or deletion of server-held beta data
through **Skicka feedback** with category **Annat**. The app automatically adds
the current anonymous session/plan context; email remains optional and is used
only when a reply is requested. Handling is manual. A named operator/direct
contact and legal review remain explicit prerequisites for a broader launch;
the repository does not invent either.

## What this repository cannot do by itself

No public URL has been claimed or created by these files. A successful release
still requires an actual server, DNS control, ACME reachability, production
secrets and a real-phone HTTPS/camera acceptance run. Those are external
deployment facts, not values that can be fabricated in source code.

## Verified local Docker rehearsal (2026-09-08)

The real existing image and Compose services were executed on Windows/WSL2.
Evidence and isolated durable state are under `D:/codex-rc/docker-20260908`.
The daemon's `/var/lib/docker` is backed by
`D:\docker\DockerDesktopWSL\disk\docker_data.vhdx`; `main/ext4.vhdx` is the
small WSL system disk. Check both Windows host free space and the virtual data
filesystem; the latter can report more capacity than its host can supply:

```powershell
(Get-Content "$env:APPDATA\Docker\settings-store.json" -Raw |
  ConvertFrom-Json).CustomWslDistroDir
Get-ChildItem D:\docker\DockerDesktopWSL -Recurse -Filter *.vhdx |
  Select-Object FullName,Length
wsl -d docker-desktop -e df -h /mnt/docker-desktop-disk
Get-PSDrive C,D | Select-Object Name,Free
```

The `.dockerignore` excludes database/env/archive files recursively, including
SQLite files below Python packages. The executed build context was 8.02 MB;
scanning the built `/srv/app` found no databases, env files or raw snapshots.
Do not substitute a config-only check for the image build.

For the full local proxy rehearsal, use the existing Compose file plus this
small override, after the isolated directory/manifest seeding above. Save it
outside the image context. The app and scheduler retain an internal network;
Caddy alone joins an ingress bridge because Docker does not publish ports for
a container attached only to an internal network. The host binding is loopback.
No public domain, TLS issuance or live source refresh is part of this test.

```powershell
$rc = 'D:/codex-rc/docker-20260908'
# rehearsal.env is a TEST copy of the example with fresh random secrets,
# absolute RUNTIME_ROOT, unique APP_VERSION/BUILD_ID and high smoke rate limits.
# Never copy production secrets or print resolved Compose configuration.
$caddyFile = (Resolve-Path 'deploy/Caddyfile').Path.Replace('\','/')
@"
services:
  caddy:
    networks: [default, ingress]
    environment:
      PUBLIC_BASE_URL: 'http://:80'
    ports: !override
      - '127.0.0.1:18080:80'
    volumes: !override
      - '${caddyFile}:/etc/caddy/Caddyfile:ro'
      - '${rc}/runtime/caddy/data:/data'
      - '${rc}/runtime/caddy/config:/config'
networks:
  ingress: {}
  default:
    internal: true
"@ | Set-Content "$rc/compose.local.yaml"
$dc = @('compose','-p','billigaste-rc-20260908',
  '-f','deploy/compose.yaml','-f',"$rc/compose.local.yaml",
  '--env-file',"$rc/rehearsal.env")
$env:TEMP = 'D:/codex-rc/tmp'
$env:TMP = $env:TEMP
docker @dc config --quiet
docker @dc build app
docker @dc up -d --no-build migrate app caddy
py -3.12 deploy/scripts/production_smoke.py `
  --base-url http://127.0.0.1:18080 --allow-http --timeout-seconds 60 `
  --output "$rc/production-smoke.json"
docker @dc up -d --no-build --force-recreate --no-deps app
# After /ready returns 200, retrieve the SAME plan with its creating anonymous
# session capability and compare the exact saved revision/payload/provenance.
# A row-count-only check is weaker; persistence.json records exact equality.
# Windows-created bind directories initially belong to root inside Linux.
# Set ownership on ONLY this verified isolated backup mount, not active data.
docker @dc --profile ops run --rm -T --no-deps --user root backup-once `
  python -c "import os; os.chown('/srv/app/var/backups',10001,10001)"
docker @dc --profile ops run --rm -T --no-deps backup-once
```

A one-time scheduler startup was inspected in this rehearsal, then stopped
before any scheduled job. Keep it stopped for offline consumer benchmarks.
To reproduce cold concurrency, restart only app and await readiness before each
wave; do not run CPU-heavy suites simultaneously when evaluating latency:

```powershell
foreach ($n in 1,5,10) {
  docker @dc restart app
  for ($i=0; $i -lt 90; $i++) {
    try {
      if ((Invoke-WebRequest http://127.0.0.1:18080/ready).StatusCode -eq 200) { break }
    } catch { }
    Start-Sleep -Seconds 1
  }
  py -3.12 backend/scripts/benchmark_beta_capacity.py `
    --base-url http://127.0.0.1:18080 --concurrency $n `
    --report-dir "$rc/capacity"
}
# Stop only this project's services after verification; preserve state/evidence.
docker @dc stop
```

Concurrency 10 intentionally tests controlled overload and may exit 2. Inspect
accepted/completed, controlled rejection, timeout/error, Retry-After, total
latency and compute latency separately. A functionally passing smoke can also
exit 2 when its ten-second latency target is missed; preserve that result.
