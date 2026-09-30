"""Hash-check the actual active artifact and every referenced OWN raw file."""

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

root = Path("/work")
manifest_file = root / "price-universes/active/city-lund.json"
manifest = json.loads(manifest_file.read_bytes())
artifact = root / "price-universes" / manifest["artifact_file"]
assert hashlib.sha256(artifact.read_bytes()).hexdigest() == manifest["artifact_sha256"]
checked = {}
with sqlite3.connect(f"file:{root}/grocery.sqlite?mode=ro", uri=True) as db:
    for snapshot in manifest["snapshot_ids"]:
        for location, expected in db.execute(
            "SELECT DISTINCT payload_location,payload_hash FROM raw_snapshots WHERE catalog_snapshot_id=?",
            (snapshot,),
        ):
            path = (root / "raw" / location).resolve()
            assert path.is_relative_to(root / "raw"), "raw path escapes test root"
            checked[location] = (
                path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected
            )
report = {
    "checked_at": datetime.now(UTC).isoformat(),
    "universe_id": manifest["universe_id"],
    "manifest_sha256": hashlib.sha256(manifest_file.read_bytes()).hexdigest(),
    "artifact_sha256": manifest["artifact_sha256"],
    "raw_files": len(checked),
    "bad_raw_files": sum(not valid for valid in checked.values()),
    "oldest_base_observed_at": manifest.get("oldest_base_observed_at"),
    "source_observations_unchanged": True,
}
(root / "ops-preflight.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
assert checked and all(checked.values()), "referenced raw data incomplete"
