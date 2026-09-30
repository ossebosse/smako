# Willys OWN LOCAL_RELAY operations

## Releasekandidat 2026-09-30 (ännu inte aktiv)

Den repobaserade koden och dess hjälpskript/tester ligger i
`D:\Projects\Smako` på `release/lund-relay-20260929`. Kandidatens
runtime-commit är `bdc9f7df417084641d0a712e3dad188dad1ad7d4`.
Det versionsbundna reläpaketet är installerat för **isolerade prov** under
`D:\smako-local-relay\releases\bdc9f7df4170`; aktiv schemalagd uppgift
`Smako Willys Local Relay` fortsätter oförändrad från den gamla
`C:\Users\ossia\Documents\Codex\2026-08-20\jag-vill-att-du-bygger-en`.
Aktuell kandidatverifiering, mottagarkompatibilitet, råhash, behovsstyrning
och blockerare finns i [releaseutfallet](releases/lund-20260929/RESULTS.md).
Den exakta föreslagna uppgiftsändringen, backup och återgång finns i
[aktiveringsordningen](releases/lund-20260929/ACTIVATION.md). Den äldre
driftinstruktionen nedan är historik för den **aktiva** versionen, inte
verifiering av kandidatens obevakade S4U-körning. Registrering av en separat
S4U-testuppgift nekades av Windows; ändra inte den aktiva uppgiften som
testgenväg.

---

Verified 10 September 2026: **Smako Willys Local Relay**, ossia, **S4U / Limited**,
daily **01:30 Europe/Stockholm**. Interactive desktop login is not required.
Actual session-0 filesystem/DNS/HTTPS/SSH/inbox probes and a genuine full task run
passed. WakeToRun=true, StartWhenAvailable=true, IgnoreNew, PT3H, no scheduler
restart loop. Battery start is allowed and battery transition does not stop it.

Current live Willys: **18,209 FRESH OWN / LOCAL_RELAY rows**, product observations
10 September 16:28:57–16:57:12 UTC. New collection 35m41s; logged workflow 46m33s.
Nominal 01:30 completion around 02:17 leaves about 30 minutes before backup 02:47
and 60 before refresh 03:17. Source/global locks remain authoritative if late.
Coop retry remains 06:17. [Full verification report](../reports/smako-willys-unattended-verification-20260910.md).

**MULTI_DAY_RELIABILITY = UNOBSERVED.** A controlled daytime session-0 run is not
evidence of reliability across actual nights. No desktop logout/sleep was forced.
Power policy was not changed: AC allows only important wake timers, battery timers
are disabled. WakeToRun alone does not establish reliable waking. A powered-off
computer cannot run; StartWhenAvailable permits delayed eligible execution when
Windows becomes available. Further power/BIOS changes require operator approval.

## Tomorrow morning: inspect once

```powershell
$relayRepo = 'C:\Users\ossia\Documents\Codex\2026-08-20\jag-vill-att-du-bygger-en'
$relayWorkspace = 'D:\smako-local-relay'
pwsh -NoProfile -NonInteractive -File "$relayRepo\deploy\scripts\inspect_willys_relay.ps1"
# Offline task/local-receipt view:
pwsh -NoProfile -NonInteractive -File "$relayRepo\deploy\scripts\inspect_willys_relay.ps1" -LocalOnly
```

Check last task result, actual last run, last successful Willys observation,
artifact ID/hash prefix, live VPS freshness and next task time together. A probe
or lock skip returning 0 is not a new collection. The receipt and full-run phase
log must confirm the successful observation. The command is read-only and makes
no provider calls. VPS errors are redacted, not treated as FRESH.

## Task inspection, manual run, disable, enable and removal

```powershell
Get-ScheduledTask -TaskName 'Smako Willys Local Relay'
Get-ScheduledTaskInfo -TaskName 'Smako Willys Local Relay'
(Get-ScheduledTask -TaskName 'Smako Willys Local Relay').Principal
(Get-ScheduledTask -TaskName 'Smako Willys Local Relay').Actions
(Get-ScheduledTask -TaskName 'Smako Willys Local Relay').Settings
Start-ScheduledTask -TaskName 'Smako Willys Local Relay'
Disable-ScheduledTask -TaskName 'Smako Willys Local Relay'
Enable-ScheduledTask -TaskName 'Smako Willys Local Relay'
# Intentional cancellation now also terminates local Python/SSH descendants:
Stop-ScheduledTask -TaskName 'Smako Willys Local Relay'
# Safe removal when intentionally decommissioning:
Disable-ScheduledTask -TaskName 'Smako Willys Local Relay'
if ((Get-ScheduledTask -TaskName 'Smako Willys Local Relay').State -eq 'Running') {
    throw 'Wait for completion or intentionally cancel before removal.'
}
Unregister-ScheduledTask -TaskName 'Smako Willys Local Relay' -Confirm:$false
```

Windows may require operator authorization to edit a task registered through its
native dialog. Do not replace it with SYSTEM or highest privileges. Current task
actions remain the original PS7 collector script and repository working directory.
The pinned PS7 path must remain present if the runtime/repository is moved.

## Reproduce initial installation and unattended configuration

```powershell
pwsh -NoProfile -NonInteractive -File "$relayRepo\deploy\scripts\install_willys_task.ps1" -Repository $relayRepo -Workspace $relayWorkspace -DailyAt '01:30'
```

This creates the base task without overwriting an existing one. Its initial mode
is Interactive; creation alone does not establish unattended operation. In Task
Scheduler (`taskschd.msc`) → task Properties → General, retain ossia and Limited
(highest privileges unchecked), select Run whether user is logged on or not.
The tested final configuration is **S4U**, corresponding to Do not store password.
Inspect the actual Principal afterwards and run the small probe before a full crawl.

The existing explicit SSH key worked under S4U in session 0 with ssh-agent disabled.
Do not assume Windows-integrated network credentials or encrypted profile files
will work; retest after key/profile/runtime changes. If a future Password-mode
registration is necessary, enter credentials only in Windows' local dialog,
never in repository files, shell arguments, logs or messages. Preserve normal
administrator SSH separately; no key material or global sshd settings changed here.

## Explicit one-shot preflight

Use after a task identity/runtime/path change, while no relay is running:

```powershell
if ((Get-ScheduledTask -TaskName 'Smako Willys Local Relay').State -eq 'Running') {
    throw 'Wait for the running relay.'
}
New-Item -ItemType File -Path "$relayWorkspace\preflight.request"
Start-ScheduledTask -TaskName 'Smako Willys Local Relay'
# After Task Scheduler returns to Ready, inspect the new probe timestamp/result:
Get-ScheduledTaskInfo -TaskName 'Smako Willys Local Relay'
Get-Content "$relayWorkspace\preflight-status.json"
```

The launcher consumes the request before executing the probe. PASS must include
session 0, correct user, dependencies/filesystem/DNS/HTTPS/SSH and VPS inbox/import
checks. It creates/removes a small temporary inbox file; no product collection,
source import, activation or retailer API request. Verify the probe timestamp is
new; a stale preflight-status.json is not current proof. Normal next invocation
collects unless the ordinary same-day delivery/lock safeguards apply. The bounded
hold marker is reserved for cancellation tests and must not be left pending.

## Local files, locking and truthful failures

- `D:\smako-local-relay\logs`: bounded JSONL logs, most recent 30 after normal lock
  acquisition. Start, nominal schedule, collection, validation, upload, server
  import/activation acknowledgement and final success/failure use actual times.
- `completed`: immutable `.smako-source` artifacts. `runs`: isolated candidate
  databases, raw evidence and collection metrics; incomplete runs do not publish.
- `last-success.json`: atomic receipt with original observation time, artifact
  hash and normal server activation result. Same observation day repeats skip
  another full crawl. No existing observation is restamped.
- `preflight-status.json` and `preflight.consumed`: bounded one-shot diagnostics.

The PowerShell launcher owns a KILL_ON_JOB_CLOSE job covering its descendants;
cancel/timeout kills local workers. Binding failure stops before collection.
Kernel workflow/collection locks still prevent overlap; do not delete lock files
to bypass ownership. Aborted tasks retain the previous valid artifact. Already
validated remote work continues to obey server locks and normal qualification.

Only transient SSH exit 255/timeouts receive at most three attempts, with
30/120-second backoff. Provider blocks, incomplete/invalid artifacts and server
validation errors are not tightly retried. An undelivered complete artifact under
24h may resume with its real original observations. A server lock conflict leaves
a staged artifact for a later normal/manual import. Upload alone cannot activate.

Local and VPS validators enforce hashes, schema, exact approved contexts,
category/pagination completeness, counts, timestamps and normal source quality.
Partial/tampered/future/stale artifacts fail. Duplicate import is idempotent and
older data cannot replace newer observations. Missed runs never become fresh:
FRESH <36h, AGING 36–48h, STALE at 48h; stale prices are excluded by existing
planner/search rules. A genuinely fresh qualified import restores Willys normally.

## VPS inspection and safe retry

All data commands use UID/GID 10001. Existing global/source locks serialize
backup, refresh, relay import and activation; sources retain independent LKG.

```powershell
ssh smako /opt/smako/compose exec -T -u 10001:10001 scheduler ls -l /srv/app/var/raw_snapshots/source-inbox/willys
ssh smako /opt/smako/compose exec -T -u 10001:10001 scheduler python -m grocery_data status --city Lund --postal-code Lund=22350 --format json
ssh smako /opt/smako/compose exec -T -u 10001:10001 scheduler cat /srv/app/var/price_universes/active/city-lund.json
ssh smako /opt/smako/compose exec -T -u 10001:10001 scheduler cat /srv/app/var/price_universes/external-provider-cache/active/city-lund.json
ssh smako /opt/smako/compose exec -T scheduler cat /etc/cron.d/grocery-beta
# Replace the placeholder with the exact existing verified inbox/processed path:
ssh smako /opt/smako/compose exec -T -u 10001:10001 scheduler python -m grocery_data.source_cli import /srv/app/var/raw_snapshots/source-inbox/willys/<sha256>.smako-source
Invoke-RestMethod https://beta.smako.nu/ready
Invoke-RestMethod https://beta.smako.nu/api/product-search -Method Post -ContentType 'application/json' -Body '{"query":"kaffe"}'
```

Host inbox: `/srv/smako/data/raw_snapshots/source-inbox/willys/`; the normal 03:17
runner handles staged arrivals, with processed/rejected results retained. The task
also requests immediate normal activation, safe after the morning window. Index
reload follows successful normal activation, never upload alone. Consumer requests
make zero provider calls. Willys remains OWN/LOCAL_RELAY, approved 2176/2354 only;
ICA remains Primat. [Deferred ICA research](sources/ica-own-deferred-research.md) is
saved for a separately scoped future milestone and has not been executed.
