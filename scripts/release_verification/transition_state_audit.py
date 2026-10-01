"""Read-only final transition inventory and actual HTTP serving audit."""

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

import httpx

root = Path("/work")
digest = "5b1a2b6b01ba65338f224cdd6af432c8178f214b1612d5d54ec400ffe8f9362a"
with sqlite3.connect("file:/work/grocery.sqlite?mode=ro", uri=True) as db:
    snapshots = db.execute(
        "SELECT id,metrics FROM catalog_snapshots WHERE instr(metrics,?)>0", (digest,)
    ).fetchall()
    assert len(snapshots) == 1
    sid = snapshots[0][0]
    sources = db.execute(
        "SELECT store_external_id,count(*),min(fetched_at),max(fetched_at) FROM source_products WHERE catalog_snapshot_id=? GROUP BY store_external_id",
        (sid,),
    ).fetchall()
with sqlite3.connect("file:/work/plans.sqlite?mode=ro", uri=True) as db:
    revisions = db.execute(
        "SELECT plan_id,revision,response_json FROM consumer_plan_revisions ORDER BY plan_id,revision"
    ).fetchall()
active = json.loads((root / "price-universes/active/city-lund.json").read_bytes())
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as c:
    serving = c.get("/api/price-universe/status").json()
assert serving["universe_id"] == active["universe_id"]
archive = Path("/archive")
inventory = json.loads((archive / "latest.json").read_bytes())
for f in inventory["files"].values():
    assert (
        hashlib.sha256((archive / "objects" / f["sha256"]).read_bytes()).hexdigest() == f["sha256"]
    )
report = {
    "matching_live_imports": len(snapshots),
    "live_snapshot_id": sid,
    "source_rows_and_times": sources,
    "plan_revisions": len(revisions),
    "plan_content_sha256": hashlib.sha256(json.dumps(revisions).encode()).hexdigest(),
    "active_manifest_sha256": hashlib.sha256(
        (root / "price-universes/active/city-lund.json").read_bytes()
    ).hexdigest(),
    "serving": {k: serving[k] for k in ["universe_id", "raw_product_count", "snapshot_ids"]},
    "old_inventory_sha256": hashlib.sha256((archive / "latest.json").read_bytes()).hexdigest(),
    "old_artifact_status_counts": dict(
        Counter(f["status"] for f in inventory["files"].values() if f["kind"] == "artifact")
    ),
    "old_unique_artifacts": len(
        {f["sha256"] for f in inventory["files"].values() if f["kind"] == "artifact"}
    ),
    "old_receipt_files": sum(f["kind"] == "receipt" for f in inventory["files"].values()),
    "preserved_archive_hashes_valid": True,
}
print(json.dumps(report, indent=2))
