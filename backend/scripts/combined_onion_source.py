"""Narrow read of the three retained onion catalog records; no collection."""

import hashlib
import json
import sqlite3
from pathlib import Path

from app.services.personal_source_facts import raw_product

ids = (
    "2cc06cc5ed1149a29f14ad34f29c0216",
    "48a79aaac1754f4aa527d6528270f107",
    "d08d91e0cc5043e29a674d065e0bf62b",
)
root = Path("/srv/app/var/raw_snapshots")
result = []
with sqlite3.connect("file:/srv/app/var/grocery/grocery_data.sqlite?mode=ro", uri=True) as db:
    db.row_factory = sqlite3.Row
    for identity in ids:
        row = db.execute(
            "SELECT p.id, p.raw_reference, r.payload_location, r.payload_hash FROM products p JOIN raw_snapshots r ON p.raw_snapshot_id=r.id WHERE p.id=?",
            (identity,),
        ).fetchone()
        path = (root / row["payload_location"]).resolve()
        assert path.is_relative_to(root)
        content = path.read_bytes()
        assert hashlib.sha256(content).hexdigest() == row["payload_hash"]
        raw = raw_product(json.loads(content), row["raw_reference"])
        result.append(
            {
                "product_id": identity,
                "payload_hash_verified": True,
                "fields": {
                    k: raw.get(k) for k in ("id", "name", "nutrientInformation", "nutrientLinks")
                },
            }
        )
print(json.dumps(result, ensure_ascii=False, indent=2))
