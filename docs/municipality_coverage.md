# Explicit municipality area mode

## Current runtime and acceptance, 2026-10-11

App/source runtime **2b83475f5e68** is active. Malmö1280/21120 has a published,
loaded, receipted PriceUniverse and responds ready200. Lund1281/22350 remains
ready200. First Malmö artifact `8d1199ee…` contains2376 products and46 selectable
store/price contexts: ICA23, Willys10, Lidl8, Hemköp4 and City Gross1. These are
not46 distinct physical stores or complete retailer coverage. Coop/Stora Coop/
X:-tra remain absent from the selectable Malmö contexts because their municipal
publications have not qualified. First publication22:37 UTC10 October; relay
receipt22:44:12. Exact evidence: `.local/municipal-rollout/malmo-chain-acceptance.json`.

A genuine five-dinner, two-serving public menu restricted to Willys Malmö
Emporia passed all basket, nutrition, store-filter and identical-reload checks
in10.172 seconds. All252 previous plan revisions and82 private states are
hash-preserved; this isolated test added one plan revision. Evidence:
`malmo-public-menu/clean-balanced.json` and `preservation.json` in the same folder.

**Remaining live-control blocker:** the deployed proxy sends
`Permissions-Policy: camera=(self), geolocation=(), microphone=()`.
Repository fix1fc4b6c allows only same-origin geolocation. The corresponding
change to the actually bound Caddy configuration validates successfully and is
waiting for the shared operation lease after the ordinary Hemköp collection.
The bound runtime config differs from the file currently reached through
`/opt/smako/current`; the prepared activation pins an exact copy of the real
runtime config with only the geolocation change and preserves actual environment,
image, TLS volumes and ports. Never replace it using the unreviewed host-path file.

New reusable live probe4194ce3 is `scripts/release_verification/municipal_live_browser.py`.
It takes municipality, postal scope, simulated latitude/longitude and output path;
it checks public/personal Chromium/WebKit controls against the genuine API.
The current deployed denial is reproduced explicitly in `geo-policy-negative`.
Ruff/compileall pass. Full Malmö nearby-store browser acceptance is still pending.

The two Hemköp fixes are deployed: transport authority now re-reads verified
municipal inventory (03f0691), and verified full catalogs absent from the first
artifact remain due (2b83475). Actual constructors accept IDs4114,4199,4212,4247.
The ordinary22:45 UTC tick selected Malmö/Hemköp, beginning4114 at22:46:59.
Full catalogs have not yet qualified. The retained traffic limit is0.1 requests/s
with one connection; the runner timeout is7200 seconds. Measure this work before
adding larger municipalities, rather than assuming arbitrary scopes fit.

App/source activation evidence/backup:
`/opt/smako/evidence/municipal-recovery-activation-2b83475f5e68`.
17 appimage and33 sourceimage tests passed; earlier216 distinct focused offline
cases remain evidence for unchanged behavior, not a whole-repository-suite claim.
Four live Lund checks passed after activation. Windows continues using the
verified f5b6aed relay release with `-Municipalities` and the existing account,
triggers and task settings. The first Malmö upload encountered the active Lund
lease; the same qualified packet was subsequently imported without refetching.
The existing Windows task then confirmed the already-active version and receipted
it. No new recurring scheduler was created.

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
activation is recorded above. The Windows action update is now verified;
the complete first Malmö collection → import → publication → loaded universe →
receipt chain is verified. Nearby-store browser acceptance still awaits the proxy
policy correction. Blocked retailers remain explicit coverage gaps.

Before expanding to the largest municipalities, measure collection duration and
storage using each genuine source run. The current Willys relay is bounded to
`min(5900, 1000 * verified_online_stores + 100)` requests, 6000 raw documents per
artifact, and a two-hour collection request window. The existing Windows task
has a three-hour execution limit and processes municipalities sequentially.
These are retained guards, not evidence that any size of municipality fits.
The first Malmö relay run completed four catalogs with39,594 store/product rows
(11,422 distinct retailer products),2572 HTTP200 responses and zero challenges
in5168.609 seconds (about86 minutes). Parsing/storage and package validation
contribute material runtime beyond network requests. Its first upload succeeded
but import met the ordinary Lund operation lease; the exact qualified8,162,127-
byte artifact was retained and reused through the existing import command once
idle. Server replay reached matching complete row counts and health_checked at
22:19 UTC. Publication and the relay receipt are separate later checks. Larger scopes may require resumable
per-store work and fair ordering using the existing snapshot/relay pipeline;
do not simply increase caps or weaken completeness. Check server space before
each addition: current builds make a consistent copy of the shared database.

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
