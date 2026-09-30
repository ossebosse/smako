"""Read actual serving and snapshot fingerprints for comparison with the source copy."""

import hashlib
import json
import sqlite3
from pathlib import Path

import httpx


def snapshots(path):
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT id,state,is_active FROM catalog_snapshots ORDER BY id").fetchall()
    return {"count": len(rows), "sha256": hashlib.sha256(json.dumps(rows).encode()).hexdigest()}


root = Path("/work")
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=10) as client:
    ready = client.get("/ready")
    response = client.get("/api/price-universe/status")
    response.raise_for_status()
    status = response.json()
report = {
    "ready_http": ready.status_code,
    "serving": {
        key: status.get(key)
        for key in (
            "universe_id",
            "raw_product_count",
            "freshness",
            "oldest_usable_price_age_hours",
        )
    },
    "snapshots": snapshots(root / "grocery.sqlite"),
    "manifest_sha256": hashlib.sha256(
        (root / "price-universes/active/city-lund.json").read_bytes()
    ).hexdigest(),
    "inbox_sha256": hashlib.sha256(
        (
            root
            / "raw/source-inbox/willys/76eabee073a1f0b5dfe08f51b65eb1154c991ec0207ffaa032c0e30c955b5325.smako-source"
        ).read_bytes()
    ).hexdigest(),
}
(root / "receiver-replay-evidence.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
