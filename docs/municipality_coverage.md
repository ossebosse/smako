# Explicit municipality area mode

## Current repair acceptance, 2026-10-11 07:13 UTC

Source runtime `municipal-source-0e2bacd95c03` is active; app `2b83475f5e68`,
proxy and existing schedules are preserved. Malmö now has **2542 products and
61 selectable contexts**, including 13 physical Coop stores. Lund has 2263
products and 29 contexts, including 9 additional physical Coop stores and the
repaired Hemköp Brunnshög catalog. Published and loaded IDs agree for each
municipality; readiness 200 for both. Malmö is FRESH; Lund is AGING due to Willys.
Contexts are separate price channels, not a count of distinct supermarkets.

The Coop blocker was an obsolete provider parser allowlist. Authentic retained
sources now qualify: Malmö 13 stores/1,752 rows, Lund 9 stores/1,200 rows. Three
Malmö Coop pages still produced no qualified offers during fresh live attempts;
Central's public offer response was HTTP 200 with an empty JSON object. The two
X:-tra publication gaps remain. No missing feed is treated as confirmed no-offers.

Hemköp 4199/4212 now have reviewed store floors 6,300/5,800 and retain full category,
page and duplicate validation. Complete retained 7,171/6,475-product captures pass.
Their **new ordinary live collection and production promotion remain pending**
until after the preserved 08:02:19 UTC retry deadline. Historical snapshots keep
their stored 8,000 floor. Lund 4224 was safely replayed and published with 5,103
products and its original source observation time.

Four live public/personal Chromium/WebKit control checks pass with 61 contexts.
A real two-store selection (Willys Emporia and Stora Coop Stadion) produces an
audited menu and identical saved reload; the winning basket uses Willys alone.
All 255 prior plan revisions and 82 private states are preserved; one public test
revision was added. Municipal diagnostics now use their scoped journal, city
status and postal readiness. The common source DB reader still cannot qualify
City Gross 3211's separate source DB; this remains explicitly unknown there.

See [release evidence](releases/municipal-source-repair-20261011/ACTIVATED.json)
and the [measured scale-up plan](municipal_scaling.md). Freshness 36/48 h, exact
store binding, LKG and Coop full-crawl allowlist 730400 remain in force.

## Earlier runtime and acceptance, 2026-10-11 00:33 UTC

Malmö (1280 / build key 21120) is published, loaded and available in production.
The first Willys source delivery was receipted by the existing Windows task at
22:44 UTC on 10 October. The subsequent ordinary server run has separate evidence;
its newer manifest need not equal that historical delivery receipt.
Lund (1281 / 22350) remains ready. Current verification: 2026-10-11T00:33:37.621089+00:00.

Current Malmö PriceUniverse has **2529 products and 48 selectable
store/price contexts** (Hemköp: 6, ICA: 23, Lidl: 8, City Gross: 1, Willys: 10).
Contexts include separate online catalog and
physical offer channels; this is not a count of distinct physical supermarkets
or a claim of complete retailer coverage. Current published/loaded manifest:
`price-universe:ef27708e376313ffad291ffb23d70ccec7f803b2e97e7a412f8a8235ae3e0b30`.

App runtime remains `2b83475f5e68`. Source runtime is `f6a38b849035`:
Hemköp catalogs are now scheduled per store, and one failed store retains its own
durable retry backoff even when another store succeeds. Fresh peers are excluded
from its retries. The constructor rechecks verified municipal authority and only
narrows it with the scheduled IDs. Freshness and qualification gates are unchanged.
The existing cron configuration, Windows task account and schedule are preserved.
The automatic Windows run at 23:30 UTC checked both municipalities successfully
and made zero retailer requests because neither was due.

Caddy fix `1fc4b6c` is active: `geolocation=(self)`. Only the proxy was recreated;
its image, actual environment, TLS volumes and ports were preserved. The new bound
configuration is pinned to `/opt/smako/overrides/Caddyfile.geolocation-1fc4b6c`.
The old bound file differed from the current symlink target: do not overwrite the
proxy from an unreviewed `/opt/smako/current/deploy/Caddyfile`.

All four live Chromium/WebKit public/personal control checks pass against the
real deployed policy and distance API. They verify exact manual selections,
choices retained separately when switching municipality, separate mobile rows,
and nearby selection using a simulated Malmö position. Coordinates are not saved
in browser preferences. This is browser automation, not a physical-phone GPS test.
A real five-dinner/two-serving menu constrained to Willys Malmö Emporia passes
basket, nutrition, exact-store and identical-reload checks. Previously stored
plans and private states remain hash-preserved: all 252 prior plan revisions and
82 private-state rows are unchanged. Three isolated menu tests added three revisions.

The first Willys capture contained 39,594 store/product rows and 11,422 distinct
retailer products from Emporia, Katrinelund, Limhamn and Mobilia. It completed
2,572 HTTP requests without HTTP errors or access challenges in about 86 minutes.
Its first PriceUniverse publication took about 17 minutes, including about
15 minutes of preparation/build work. Captured source rows are not the same
measure as usable products in PriceUniverse.

The ordinary Hemköp run promoted Kronprinsen 4114 (8,837 products) and Triangeln
4247 (9,269 products); both snapshots are in the published and loaded universe.
The run is honestly reported as degraded because two other catalogs were rejected.
The resulting PriceUniverse is fresh and usable.
Värnhem 4199 (7,066 unique products) and Elinegård 4212 (6,459) have reconciled
full traversals but fail the existing 8,000-product minimum. Their independently
qualified physical offers remain separate. Review evidence-backed per-store
baselines before enabling their full catalogs; do not lower the chain-wide gate.
Lund 4224's existing schema hold also remains.

Coop/Stora Coop/X:-tra still lack qualified selectable Malmö contexts. Söderkulla's
official publication URL redirects to a missing-publication page; Nydala's official
`weeklyOffersLink` is empty. Three Coop stores have public-offer fetch failures;
the retained evidence does not establish a more specific transport cause. Keep
each failed store visible in coverage and collect sanitized exception-chain
evidence on a normal future attempt. Coop full crawling remains limited to 730400.

The same deployed registration code passes a Göteborg 1480 / 41110 dry-run;
the existing registry is byte-unchanged and Göteborg is **not enabled**. Before
larger additions, budget disk space and sequential collection duration. The
Windows task has a three-hour limit and each capture a two-hour limit. Larger
scopes may require resumable per-store capture through the existing artifact
pipeline and more storage. Per-store retry filtering does not remove those limits.
At 00:33 UTC the server had 13.85 GB free against a 9.61 GB operational estimate;
this check passed but does not guarantee room for additional municipalities.

Verification: 17 app-image cases, 33 original source-image cases, 15 local
scheduling cases and 33 updated source-image cases pass. These runs overlap;
they are not a sum of unique tests. The prior 216 focused offline cases remain
supporting evidence, not a whole-repository test-suite claim. Ruff and compileall
pass. Reusable live checks are `scripts/release_verification/municipal_live_browser.py`
and `public_menu_browser.py` (with `--postal-code` and `--store-context`).

Sanitized release evidence: [ACTIVATED.json](releases/municipal-rollout-20261011/ACTIVATED.json).
Protected operation evidence is under `/opt/smako/evidence/` in
`municipal-recovery-activation-2b83475f5e68`, `municipal-geolocation-1fc4b6c`,
and `municipal-schedule-f6a38b849035`. Local detailed evidence is retained in
`.local/municipal-rollout/`. No new recurring scheduler was created.

The municipal rollout extends the existing `municipal-collection-scopes-v1`
registry with `refresh_scopes`. It does not add another scheduler. The ordinary
refresh runner holds one operation lease and processes each enabled municipality
sequentially, prioritizing the existing operation. Each new municipality has its
own demand/backoff journal, source state, immutable artifact and runtime reload.
A missing first manifest initiates bootstrap with durable retry backoff.

The matching app, scheduler and Windows relay are already installed for Lund
and Malmö. These are the reusable registration commands in the scheduler
operational environment; Malmö is already registered:

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
receipt chain is verified. Nearby-store browser acceptance now passes with the active proxy policy. Blocked retailers remain explicit coverage gaps.

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
