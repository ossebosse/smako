"""Read selected retained source objects, never collect or mutate data."""

import hashlib
import json
import sqlite3
from pathlib import Path

from app.services.personal_source_facts import raw_product
from sqlalchemy.engine import make_url

from grocery_data.app.config import GroceryDataSettings

s = GroceryDataSettings.from_env()
selection = json.loads(Path("/tmp/fishfree-selection.json").read_bytes())
out = []
with sqlite3.connect(f"file:{make_url(s.database_url).database}?mode=ro", uri=True) as db:
    db.row_factory = sqlite3.Row
    for item in selection:
        rows = db.execute(
            """SELECT p.raw_reference, r.payload_hash, r.payload_location
            FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id
            WHERE p.chain='willys' AND p.external_product_id=?
            ORDER BY p.id""",
            (item["code"],),
        ).fetchall()
        if not rows:
            continue
        row = rows[0]
        path = (s.raw_snapshot_root / row["payload_location"]).resolve()
        assert path.is_relative_to(s.raw_snapshot_root.resolve())
        data = path.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["payload_hash"]
        raw = raw_product(json.loads(data), row["raw_reference"])
        assert raw["code"] == item["code"]
        out.append({"selection": item, "source": dict(row), "raw": raw})
Path("/tmp/fishfree-retained.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf8")
print(json.dumps([{"code": v["selection"]["code"], "fields": list(v["raw"])} for v in out]))
