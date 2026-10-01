"""Read-only serving/freshness gate; emits evidence, never starts the Windows task."""

import hashlib
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

root = Path("/work")
assert os.environ["BUILD_ID"] == "bdc9f7df417084641d0a712e3dad188dad1ad7d4"
now = datetime.now(UTC)
manifest_path = root / "price-universes/active/city-lund.json"
manifest = json.loads(manifest_path.read_bytes())
artifact = root / "price-universes" / manifest["artifact_file"]
assert hashlib.sha256(artifact.read_bytes()).hexdigest() == manifest["artifact_sha256"]
prepared = json.loads(artifact.read_bytes())
required = json.loads((root / "policy.json").read_bytes())["required_context_ids"]
assert len(required) == 5
observations = {}
for context in required:
    rows = [p for p in prepared["universe"]["products"] if p["store_id"] == context]
    assert rows and all(p.get("source_provenance") for p in rows)
    times = [datetime.fromisoformat(p["source_provenance"]["source_observed_at"]) for p in rows]
    oldest = min(times)
    age = (now - oldest).total_seconds() / 3600
    assert 0 <= age < 48, f"mandatory base stale: {context}"
    observations[context] = {
        "rows": len(rows),
        "oldest_observed_at": oldest.isoformat(),
        "age_hours": round(age, 3),
        "state": "AGING" if age >= 36 else "FRESH",
    }
with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
    ready = client.get("/ready")
    response = client.get("/api/price-universe/status")
    response.raise_for_status()
    serving = response.json()
assert ready.status_code == 200
assert serving["universe_id"] == manifest["universe_id"]
assert serving["raw_product_count"] == len(prepared["universe"]["products"])
assert sorted(serving["snapshot_ids"]) == sorted(manifest["snapshot_ids"])
preflight = json.loads((root / "ops-preflight.json").read_bytes())
assert preflight["manifest_sha256"] == hashlib.sha256(manifest_path.read_bytes()).hexdigest()
assert preflight["bad_raw_files"] == 0 and preflight["raw_files"] > 0
raw_checked = datetime.fromisoformat(preflight["checked_at"])
assert timedelta(0) <= now - raw_checked < timedelta(minutes=15), "repeat raw-file verification"
expiry = min(
    now + timedelta(hours=2),
    min(datetime.fromisoformat(v["oldest_observed_at"]) for v in observations.values())
    + timedelta(hours=46),
)
assert expiry > now
report = {
    "checked_utc": now.isoformat(),
    "expires_utc": expiry.isoformat(),
    "image": "sha256:2f81344208e05cbc57d16fa74a73c97b26bc729859936ca5d96ab150579fe221",
    "universe_id": serving["universe_id"],
    "raw_product_count": serving["raw_product_count"],
    "manifest_sha256": preflight["manifest_sha256"],
    "raw_files_verified": preflight["raw_files"],
    "mandatory_contexts": observations,
    "ready_http": ready.status_code,
    "task_start_authorized": False,
}
(root / "receiver-preflight-oct01.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
