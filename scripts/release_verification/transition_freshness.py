"""Report real current base ages; never authorize a task or alter observations."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

root = Path("/work")
now = datetime.now(UTC)
manifest = json.loads((root / "price-universes/active/city-lund.json").read_bytes())
artifact = (root / "price-universes" / manifest["artifact_file"]).read_bytes()
assert hashlib.sha256(artifact).hexdigest() == manifest["artifact_sha256"]
products = json.loads(artifact)["universe"]["products"]
required = json.loads((root / "policy.json").read_bytes())["required_context_ids"]
observations = {}
for context in required:
    rows = [p for p in products if p["store_id"] == context]
    assert rows
    oldest = min(datetime.fromisoformat(p["source_provenance"]["source_observed_at"]) for p in rows)
    age = (now - oldest).total_seconds() / 3600
    assert 0 <= age < 48
    observations[context] = {
        "rows": len(rows),
        "oldest_observed_at": oldest.isoformat(),
        "age_hours": round(age, 3),
        "state": "AGING" if age >= 36 else "FRESH",
    }
print(
    json.dumps(
        {
            "checked_utc": now.isoformat(),
            "universe_id": manifest["universe_id"],
            "raw_rows": len(products),
            "mandatory_contexts": observations,
            "test_clock_used": False,
        },
        indent=2,
    )
)
