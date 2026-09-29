# Municipality geometry: optional SCB RegSO 2025 position evidence

The shared area evaluator accepts separately bound official coordinates plus
SCB RegSO 2025 polygons. This is an explicit municipality-mode proof, not a
change to default address-locality selection or users' distance/store limits.

SCB documents that this nationwide division follows municipality boundaries
as of 2025-01-01: https://www.scb.se/vara-tjanster/oppna-data/oppna-geodata/regso/
Official WFS: https://geodata.scb.se/geoserver/stat/wfs (stat:RegSO_2025).
This is not the simplified municipality overview map previously rejected.
Municipality code/name still use the existing official code registry.

Fetch complete feature counts for the requested code, explicit EPSG:4326,
store original payload and hash/version/observation, validate every feature's
municipality code. Retain source store ID, coordinate source/hash/time and
coordinates. Missing/conflicting evidence stays unknown. Point-in-polygon
supports holes/multipolygons. A conservative 10 m margin around every RegSO
edge (including internal edges) produces unknown instead of guessing inclusion.
It is an uncertainty exclusion, not an area expansion or search radius.

Retailer coordinate accuracy and boundary changes since 2025 remain limitations.
Do not infer route distance or cadastral accuracy. Refresh with separately
verified geometry when its version changes. No production schedule installed.

Coop collection opts in via `python -m grocery_data.scripts.collect_coop_municipality
--municipality-code 1281 --output <new-dir>`. National Coop and X:-tra arrays are
processed independently of existing price coverage, with precise ID/account/
address alias reconciliation. Conflicts block collection. All discovered rows
remain in the report. No independent total of all businesses is asserted.

Existing locality/prefix-based consumer discovery is unchanged. Explicit
municipal ingestion uses the inventory-generated IDs; it must not silently
expand a saved user's store scope. See reports/coop-municipality-20260921.
