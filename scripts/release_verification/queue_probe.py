"""Ordinary receiver replay on copied data; no queue rewriting or fabricated scope."""

import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

root = Path("/work")
artifact = Path(sys.argv[1])
label = sys.argv[2]


def inventory():
    with sqlite3.connect(f"file:{root}/grocery.sqlite?mode=ro", uri=True) as db:
        snapshots = db.execute(
            "SELECT id, state, is_active FROM catalog_snapshots ORDER BY id"
        ).fetchall()
    manifest = root / "price-universes/active/city-lund.json"
    return {
        "snapshot_count": len(snapshots),
        "snapshots_sha256": hashlib.sha256(json.dumps(snapshots).encode()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
    }


before = inventory()
artifact_hash = hashlib.sha256(artifact.read_bytes()).hexdigest()
result = subprocess.run(
    [sys.executable, "-m", "grocery_data.source_cli", "import", str(artifact)],
    capture_output=True,
    text=True,
    timeout=1800,
    check=False,
)
(root / (label + ".stdout")).write_text(result.stdout)
(root / (label + ".stderr")).write_text(result.stderr)
try:
    output = json.loads(result.stdout.strip().splitlines()[-1])
except (ValueError, IndexError):
    output = {"structured_result_unavailable": True, "private_logs": True}
report = {
    "network": "Docker network none; authentic artifact replay",
    "exit_code": result.returncode,
    "artifact_sha256": artifact_hash,
    "artifact_unchanged": hashlib.sha256(artifact.read_bytes()).hexdigest() == artifact_hash,
    "before": before,
    "after": inventory(),
    "receiver": output,
}
(root / (label + ".json")).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
