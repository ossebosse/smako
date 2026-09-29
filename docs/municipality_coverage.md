# Explicit municipality area mode

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
