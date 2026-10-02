"""Read-only named retained public supplier documents for data preparation."""
import json
import sqlite3
import sys
from pathlib import Path

from app.services.personal_source_facts import raw_product
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_search import ProductSearchRequest

prepared = PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
index = prepared.product_search_index
db = sqlite3.connect('file:/inputs/grocery.sqlite?mode=ro', uri=True)
db.row_factory = sqlite3.Row
results = {}
for name in sys.argv[1:]:
    keys, _, _ = index.retrieve(ProductSearchRequest(query=name))
    rows, seen = [], set()
    for i in dict.fromkeys(i for k in keys for i in index.groups[k]):
        p = prepared.universe.products[i]
        if p.chain != 'coop' or (p.name, p.gtin, p.package_quantity) in seen:
            continue
        seen.add((p.name, p.gtin, p.package_quantity))
        row = db.execute('SELECT p.raw_reference,r.payload_location FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id WHERE p.id=?', (p.product_id,)).fetchone()
        if row:
            path = (Path('/inputs/raw') / row['payload_location']).resolve()
            assert path.is_relative_to('/inputs/raw')
            rows.append({'product': p.model_dump(mode='json'), 'raw': raw_product(json.loads(path.read_bytes()), row['raw_reference'])})
    results[name] = rows
Path('/results/retained-ingredient-documents.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
print({name: len(rows) for name, rows in results.items()})
