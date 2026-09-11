"""Freeze public retained product evidence only; never reads private plan data."""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from app.services.personal_source_facts import load_retained_facts, raw_product
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
manifest = json.loads((root / "active/city-lund.json").read_bytes())
artifact = (root / manifest["artifact_file"]).read_bytes()
prepared = PreparedPriceUniverseArtifact.model_validate_json(artifact).restore()
facts = load_retained_facts(prepared)
raw_root = Path("/srv/app/var/raw_snapshots")
metadata = {}
last, doc = None, None
with sqlite3.connect("file:/srv/app/var/grocery/grocery_data.sqlite?mode=ro", uri=True) as db:
    db.row_factory = sqlite3.Row
    for snapshot in sorted(
        {
            p.source_provenance.source_snapshot_id
            for p in prepared.universe.products
            if p.source_provenance
        }
    ):
        for row in db.execute(
            "SELECT p.id, p.raw_reference, r.payload_location, r.payload_hash FROM products p JOIN raw_snapshots r ON p.raw_snapshot_id=r.id WHERE p.catalog_snapshot_id=? ORDER BY r.payload_location",
            (snapshot,),
        ):
            path = (raw_root / row["payload_location"]).resolve()
            assert path.is_relative_to(raw_root)
            if last != path:
                content = path.read_bytes()
                assert hashlib.sha256(content).hexdigest() == row["payload_hash"]
                doc, last = json.loads(content), path
            raw = raw_product(doc, row["raw_reference"])
            # Existing public catalog fields only. No source transport/session metadata.
            keys = (
                "id",
                "code",
                "ean",
                "gtin",
                "name",
                "variety",
                "manufacturerName",
                "accreditedTags",
                "labels",
                "allergyInfo",
                "listOfIngredients",
                "nutrientInformation",
                "nutrientLinks",
                "nonEkoProduct",
                "countryOfOrigin",
            )
            metadata[row["id"]] = {k: raw[k] for k in keys if k in raw}
out = Path("/tmp/personal-v2-qualified-facts.json")
out.write_text(
    json.dumps(
        {
            "universe_id": manifest["universe_id"],
            "price_sha256": hashlib.sha256(artifact).hexdigest(),
            "facts": [[list(k), asdict(v)] for k, v in sorted(facts.items())],
            "raw": metadata,
        },
        ensure_ascii=False,
    )
)
Path("/tmp/personal-v2-qualified-prices.json").write_bytes(artifact)
print(
    json.dumps(
        {
            "universe_id": manifest["universe_id"],
            "price_sha256": hashlib.sha256(artifact).hexdigest(),
            "facts_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
            "facts": len(facts),
            "detail_requests": 0,
        }
    )
)
