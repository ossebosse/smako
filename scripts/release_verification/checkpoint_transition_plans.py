"""Checkpoint the isolated latest store after every writer has stopped."""

import hashlib
import json
import sqlite3
from pathlib import Path

path = Path("/work/plans.sqlite")
with sqlite3.connect(path) as db:
    before = db.execute(
        "SELECT * FROM consumer_plan_revisions ORDER BY plan_id,revision"
    ).fetchall()
    result = db.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
    assert result == (0, 0, 0), result
    assert (
        db.execute("SELECT * FROM consumer_plan_revisions ORDER BY plan_id,revision").fetchall()
        == before
    )
db.close()
assert not Path(str(path) + "-wal").exists() or Path(str(path) + "-wal").stat().st_size == 0
print(
    json.dumps(
        {
            "checkpoint": list(result),
            "revisions": len(before),
            "all_rows_preserved": True,
            "database_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
    )
)
