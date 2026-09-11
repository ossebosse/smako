"""Read-only compatibility check, including synthetic immutable purchase history."""
import hashlib
import json
import sqlite3
from pathlib import Path

from app.services.plan_store import PlanStore

counts = []
for path in (Path("/restore/plans/plans.sqlite3"), Path("/evidence/gaps-synthetic-plans.sqlite")):
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{path.as_posix()}?mode=ro&immutable=1", uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute("SELECT * FROM consumer_plan_revisions").fetchall()
        saved = [PlanStore._materialize(row) for row in rows]
        payloads = [json.loads(r[0]) for r in db.execute("SELECT payload FROM personal_private_state")]
        if "synthetic" in path.name:
            assert len(saved) == 2 and saved[0].plan.personal.version == "personal-v2-2"
            assert [e["total"] for e in payloads[0]["ledger"]] == [70, 15]
            assert [s.plan.optimized_basket.total for s in saved] == [70, 15]
        counts.append({"kind": "synthetic" if "synthetic" in path.name else "isolated_backup", "revisions": len(saved), "private_records": len(payloads)})
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before

from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)
assert client.post("/api/personal/plans/synthetic/change", json={}).status_code == 503
assert client.post("/api/plans", json={}).status_code == 503
assert "Tillfälligt" in client.post("/api/account/migrate-guest", json={}).json()["detail"]
print(json.dumps({"status": "PASS", "counts": counts, "writes_blocked": True, "database_hashes_unchanged": True}))
