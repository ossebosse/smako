"""Read-only audit of the completed 2026-10-01 S4U delivery; no import or collection."""

import hashlib
import json
import sqlite3
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx

from grocery_data.app.services.source_artifact import verify_source_artifact

root = Path("/work")
digest = "5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a"
snapshot_id = "293e153376ae45bbbf114c0cbb5790d3"
artifact = root / "raw/source-inbox/willys" / (digest + ".smako-source")
verified = verify_source_artifact(artifact)
assert verified.artifact_sha256 == digest
manifest = verified.manifest.model_dump(mode="json")


def stamp(value):
    return datetime.fromisoformat(value).astimezone(UTC).isoformat()


db = sqlite3.connect("file:/work/grocery.sqlite?mode=ro", uri=True)
db.row_factory = sqlite3.Row
snapshot = dict(db.execute("SELECT * FROM catalog_snapshots WHERE id=?", (snapshot_id,)).fetchone())
metrics = json.loads(snapshot.pop("metrics"))
assert metrics["source_artifact"]["sha256"] == digest
assert metrics["source_artifact"]["source_snapshot_id"] == manifest["source_snapshot_id"]
assert snapshot["state"] == "promoted" and snapshot["is_active"] == 1
matches = db.execute(
    "SELECT count(*) FROM catalog_snapshots WHERE instr(metrics,?)>0", (digest,)
).fetchone()[0]
assert matches == 1
raw = list(db.execute("SELECT * FROM raw_snapshots WHERE catalog_snapshot_id=?", (snapshot_id,)))
expected = Counter(
    (
        p["sha256"],
        stamp(p["metadata"]["fetched_at"]),
        p["metadata"]["store_external_id"],
        p["metadata"]["kind"],
    )
    for p in manifest["payloads"]
)
actual = Counter(
    (p["payload_hash"], stamp(p["fetched_at"]), p["store_external_id"], p["kind"]) for p in raw
)
assert expected == actual
for item in raw:
    path = (root / "raw" / item["payload_location"]).resolve()
    assert path.is_relative_to(root / "raw")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == item["payload_hash"]
rows = [
    dict(r)
    for r in db.execute(
        "SELECT store_external_id,count(*) AS rows,min(fetched_at) AS observed_from,max(fetched_at) AS observed_to FROM source_products WHERE catalog_snapshot_id=? GROUP BY store_external_id",
        (snapshot_id,),
    )
]
assert sum(r["rows"] for r in rows) == manifest["row_count"]
run = dict(
    db.execute(
        "SELECT id,status,successful,started_at,finished_at,error_summary FROM collector_runs WHERE id=?",
        (snapshot["collector_run_id"],),
    ).fetchone()
)
assert run["successful"] == 1 and run["error_summary"] is None
db.close()

active_path = root / "price-universes/active/city-lund.json"
active_bytes = active_path.read_bytes()
active = json.loads(active_bytes)
prepared_bytes = (root / "price-universes" / active["artifact_file"]).read_bytes()
assert hashlib.sha256(prepared_bytes).hexdigest() == active["artifact_sha256"]
prepared = json.loads(prepared_bytes)
products = prepared["universe"]["products"]
selected = [
    p for p in products if p.get("source_provenance", {}).get("source_snapshot_id") == snapshot_id
]
assert selected
raw_times = {(r["store_external_id"], stamp(r["fetched_at"])) for r in raw}
for product in selected:
    source = product["source_provenance"]
    assert source["source_provider"] == "own" and source["source_channel"] == "catalog"
    assert (
        source["price_context"] == "online_store" and source["collection_location"] == "LOCAL_RELAY"
    )
    assert (source["provider_store_id"], stamp(source["source_observed_at"])) in raw_times
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
    ready = client.get("/ready")
    response = client.get("/api/price-universe/status")
    response.raise_for_status()
    serving = response.json()
assert ready.status_code == 200
assert serving["universe_id"] == active["universe_id"]
assert serving["raw_product_count"] == len(products)
assert sorted(serving["snapshot_ids"]) == sorted(active["snapshot_ids"])
assert snapshot_id in serving["snapshot_ids"]
runner = json.loads((root / "runner.json").read_bytes())
assert runner["run_kind"] == "source_relay_import" and runner["exit_code"] == 0
assert runner["runtime_reload"]["changed"] is True
assert runner["runtime_reload"]["new_price_universe_id"] == serving["universe_id"]
report = {
    "checked_utc": datetime.now(UTC).isoformat(),
    "read_only": True,
    "retailer_requests_during_audit": 0,
    "artifact_sha256": digest,
    "source_manifest": {
        k: manifest[k]
        for k in (
            "schema_version",
            "source_snapshot_id",
            "collection_started_at",
            "collection_finished_at",
            "observed_from",
            "observed_to",
            "row_count",
            "product_count",
            "request_count",
            "context_ids",
            "parser_version",
            "normalizer_version",
        )
    },
    "completion": {k: v.model_dump(mode="json") for k, v in verified.completion.items()},
    "matching_import_snapshots": matches,
    "imported_snapshot": snapshot,
    "import_run": run,
    "import_source_metadata": metrics["source_artifact"],
    "imported_source_rows": rows,
    "raw_payloads_verified": len(raw),
    "raw_hashes_times_contexts_equal_source": True,
    "source_validation": "PASS",
    "runner": runner,
    "active_manifest_sha256": hashlib.sha256(active_bytes).hexdigest(),
    "prepared_artifact_sha256": active["artifact_sha256"],
    "serving": {
        k: serving[k]
        for k in ("universe_id", "built_at", "raw_product_count", "product_count", "snapshot_ids")
    },
    "served_rows_from_this_import": len(selected),
    "served_rows_by_store": dict(
        Counter(p["source_provenance"]["provider_store_id"] for p in selected)
    ),
    "served_source_times_preserved": True,
    "ready_http": ready.status_code,
}
print(json.dumps(report, indent=2))
