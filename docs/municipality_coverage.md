# Explicit municipality area mode

## Additive operation and consumer selection, activated 2026-10-10

App and scheduler were activated at **19:34 UTC / 21:34 Swedish time**, runtime
`f5b6aedc851d28ab6fb77e7c656bd10db63c1d62`. Malmö (`1280`, build key `21120`)
and preserved Lund (`1281`, `22350`) are registered in the shared operation.
Lund's live readiness is 200 with loaded manifest `65dee955…`; its 20 contexts
remain available. Malmö is honestly `pending`, with readiness 503 until its
first qualified artifact has been published and loaded. An ordinary refresh
was started through the existing runner at approximately 19:35 UTC; this does
not prove completed Malmö collection.

**Remaining operational blocker:** Windows returned `Access denied` when
updating `Smako Willys Local Relay`. Its original action still uses release
`fe795e5b04f5` and the Lund child workspace. The new immutable release
`D:\smako-local-relay\releases\f5b6aedc851d` is installed and its 681-file
integrity/import/dependency checks pass, but it is not used by the task yet.
Do not describe Malmö's recurring Willys collection as enabled until this step
succeeds. Run the following in **PowerShell as administrator** on this Windows
machine; it changes only the existing task action and verifies unchanged
principal, triggers and settings. The evidence directory must be new.

```powershell
& 'D:\Projects\Smako\deploy\scripts\enable_municipal_relay.ps1' `
  -ReleaseRoot 'D:\smako-local-relay\releases\f5b6aedc851d' `
  -Workspace 'D:\smako-local-relay\scopes' `
  -Config 'D:\smako-local-relay\config\relay.json' `
  -EvidenceDirectory 'D:\smako-local-relay\municipal-task-activation-f5b6aed'
```

Then use the existing task's next run (or start that same task once) and verify
Malmö collection → qualified source → import → publication → runtime reload →
receipt. Do not create another scheduler or relax retailer/freshness gates.
The relay's existing SSH route already returns both registered municipalities.

The activation held the shared lease, checked idle planning traffic and CPU,
verified image/package hashes and a consistent PlanStore backup, and preserved
the complete Compose configuration except app/scheduler image and BUILD_ID.
All 252 existing plan revisions and 82 private states were checked unchanged by
row hashes afterward. The idle old cron process ignored termination; after a
fresh process check proved it had no jobs, that old container was terminated
to complete the controlled replacement. No collecting process was killed.

Qualified local packages are in `.local/municipal-rollout/qualified-packages/`,
Windows ZIP in `final-relay/`, and the image archive is
`municipal-images-qualified.tar` (SHA-256
`830b85709c4bc7fb71ac899734c5e2583d099b3c4adb31703f6c65e511826163`).
Only the qualified source package is accepted: an earlier combined package
failed because the older source runtime lacks consumer recipe dependencies.
Builder `b00bcd6` applies the reviewed source hunks against that runtime and
keeps its consumer dependency tree. The app package is byte-identical to the
previously tested candidate. Final container tests: **17 app, 16 source PASS**,
network disabled; source tests cover collection orchestration and actual
artifact building, not the app-only consumer controls. Local evidence is in
`.local/municipal-rollout/`; remote private activation/backup evidence is under
`/opt/smako/evidence/municipal-activation-f5b6aedc851d`.

The municipal rollout extends the existing `municipal-collection-scopes-v1`
registry with `refresh_scopes`. It does not add another scheduler. The ordinary
refresh runner holds one operation lease and processes each enabled municipality
sequentially, prioritizing the existing operation. Each new municipality has its
own demand/backoff journal, source state, immutable artifact and runtime reload.
A missing first manifest initiates bootstrap with durable retry backoff.

After installing the matching app, scheduler and Windows relay releases, register
Malmö on the scheduler through the existing operational environment:

```sh
python -m grocery_data.municipal_cli add --municipality 1280 --postal-code 21120 --dry-run
python -m grocery_data.municipal_cli add --municipality 1280 --postal-code 21120
python -m grocery_data.municipal_cli list
```

The non-dry command acquires the shared operation lease and writes atomically.
Repeated identical registration is harmless; conflicting/overlapping keys fail.
The first addition retains Lund, its required contexts and sources enabled in
both environment and persisted job configuration. `21120` is an internal build
key, not evidence of a municipality boundary or the consumer's position.
The same command accepts other official SCB municipalities, for example `1480`
with a distinct build key; retailer coverage must still qualify independently.

The existing Windows launcher gains `-Municipalities`. Its workspace must then
be the existing parent `D:\smako-local-relay\scopes`; the server registry selects
enabled Willys scopes. Existing `municipality-1281` queues and receipts are
retained; `municipality-1280` gets separate state. Do not point multi-municipality
mode at the old child workspace. It requires a new immutable relay installation
and updating the existing task action while idle, preserving its identity,
schedule, S4U account and transport. No additional timer is needed.

The app loads the enabled municipalities and accepts scoped authenticated
`POST /api/admin/reload-price-universe?city=Malm%C3%B6`. `/api/municipalities`
exposes only configured municipalities with honest pending/available status.
The public and personal forms select an available municipality and keep store
choices separately per area. Explicit store selections also constrain ordinary
optimized menus and standalone personal shopping lists. Missing/stale chosen
stores fail rather than silently expanding the basket. Request-local candidate
and price caches include the selection; the shared artifact is unchanged.

“Nära mig” requests position only on a user click, uses verified coordinates and
straight-line distance, and leaves previous choices intact when no matching
positions exist. A fulfillment context uses verified pickup destinations; its
warehouse is never treated as a nearby physical store. Coordinates are not
saved in the browser's preferences. Coop Online remains restricted to `730400`;
physical Coop/Stora Coop/X:-tra sources remain separate.

Willys parser v4 is now consistently identified by the connector and portable
artifact qualifier, with retained v3 source-container compatibility. Scope-only
migration still requires identical raw observations and identical parser and
normalizer versions; changed prices at the same timestamp remain rejected.
Import receipts require the corresponding universe to be confirmed loaded.

Verification evidence is in `.local/verification/municipal-*.xml` and
`municipal-test-summary.json`: 216 distinct focused test cases passed across
the recorded runs after targeted repairs. Earlier failed runs are retained;
this is not a claim of a green complete repository suite. Ruff and compileall
passed. `scripts/release_verification/municipal_browser.py` passed four mobile
Chromium/WebKit control cases using explicit fixture responses. Offline tests
cover Lund/Malmö isolation, a third municipality, real local menu calculation,
store selection/cache separation, restart, source qualification and LKG behavior.
They do not prove live Malmö prices or retailer availability.

The initial 19:02 UTC check was blocked by an ordinary Lund refresh. That job
completed, published and loaded `65dee955…`; the subsequent controlled code
activation is recorded above. Remaining live acceptance is the privileged
Windows action update and authentic collection → import → publication → loaded
universe → receipt for Malmö. City Gross or any blocked retailer must remain a
reported coverage gap, never fabricated catalog coverage.

The sections below describe the earlier geographic evidence contract; their
historical activation statements do not describe this candidate's capabilities.

`GeographicArea` retains `mode="locality"` by default. Opt-in `mode="municipality"` requires a valid Swedish SCB code and matching official municipality name (`city` remains the discovery label). `area_key` distinguishes `municipality:SE:1281` from legacy `Lund`. This does not migrate plans, runtime PriceUniverse keys, geographic stores, source scope ownership or user preferences.

The shared `services/area_membership.py` evaluates SourceStore facts for every chain. It never infers municipal membership from address locality, store name, postal-code equality, a search URL or a regional price context. Missing evidence returns unknown, not outside. Version 1 supports explicit authoritative retailer administrative address fields; coordinates remain available but there is no approximate fallback.

`address_municipality_evidence` must bind chain, exact retailer store ID, exact address, administrative field path, HTTPS source URL, response SHA-256 and timezone-aware source observation. ICA's parser constructs these directly from the sanitized official `address.municipality`, not from user/model input. Official names map through all 290 SCB codes in the versioned `scb_municipalities_2026.json` register. The file records source URL, 2026 version and source hash. Unknown or conflicting codes/names fail closed.

`reuse_municipality_evidence` only reuses matching chain/ID/address/postcode observations across discovery queries, preserves original evidence/time, and quarantines conflicting municipalities. No fuzzy name join. ICA's optional address enrichment discovers missing localities from official store links, then fetches full public address cards through the existing connector. The URL is only a discovery hint; exact ID/address/postcode and explicit municipal field are still required. Budget 8 locality queries, sequential, stop on error; errors and unqueried localities remain visible. Unknown/failed primary map cards remain in the denominator.

`collect_area_offers` supports this explicit area mode, retains geographic evidence per store and separates locator reconciliation (`inventory.complete`) from municipal inventory proof (`municipality_complete=false` without independent enumeration evidence). The activation proposal cannot mistake one for the other. Existing locality provenance and inclusion logic remain unchanged. Previous reports from a different mode, municipality or named area cannot silently expand retained collection scope. Legacy locality reports lacking an area envelope remain replay-compatible.

Other existing chain collectors/registry reconciliation are still locality-scoped; the new shared evaluator is reusable, but municipal operational collection has NOT been silently enabled there. Their parsers need administratively verified facts or approved geometry before municipal membership can be established. User store choice, distance and max purchase locations remain independent.

## Source and uncertainty

- SCB official 2026 code register: https://www.scb.se/en/finding-statistics/regional-statistics/regional-divisions/counties-and-municipalities/counties-and-municipalities-in-numerical-order/
- ICA official locator and address cards: https://www.ica.se/butiker/
- SCB says its simplified municipality boundaries are not suitable for analysis; they are not used: https://www.scb.se/hitta-statistik/regional-statistik-och-kartor/regionala-indelningar/digitala-granser/
- Lantmäteriet official geometry service metadata/OpenAPI: https://api.lantmateriet.se/ogc-features/v1/administrativ-indelning . Metadata 200, actual filtered `collections/kommuner/items?kommunkod=1281` 401 on 2026-09-20. Geometric verification needs legitimate service entitlement/credentials configured outside chat. No access workaround or new account was attempted.

Administrative retailer addresses may themselves be wrong; results explicitly identify this uncertainty and do not claim cadastral verification. The SCB register must be refreshed with an explicit new version when municipal codes/names change; no yearly schedule was installed. Report `reports/municipality-offers-20260920` preserves the exact current evidence and unknowns.

No runtime dependency was added: existing Python/Pydantic/httpx and connectors are used. No GPU, OCR, model, paid API, server configuration, Windows task, source activation or production schedule changed.
