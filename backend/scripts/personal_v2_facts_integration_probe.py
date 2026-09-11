"""Read-only runtime adapter verification against retained production snapshots."""
import json
import sys
import time
from collections import Counter
from pathlib import Path

from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
manifest = json.loads((root / "active/city-lund.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((root / manifest["artifact_file"]).read_bytes()).restore()
start = time.perf_counter()
facts = load_retained_facts(prepared)
counts = {}
for p in prepared.universe.products:
    row = counts.setdefault(p.chain, Counter())
    row["products"] += 1
    f = facts.get((p.store_id, p.product_id))
    if f:
        row["joined"] += 1
        row["organic_true"] += f.organic is True
        row["ingredient_declaration"] += bool(f.ingredients)
        row["nutrition_complete"] += {"kcal", "protein_g", "carbs_g", "fat_g"} <= f.nutrition.keys()
        assert f.source_product_id == p.product_id
        assert f.source_snapshot_id == p.source_provenance.source_snapshot_id
        assert not f.ingredients_complete
assert counts["coop"]["nutrition_complete"] > 6000
result = {"status": "PASS", "universe": manifest["universe_id"], "counts": counts, "seconds": round(time.perf_counter() - start, 3), "live_requests": 0, "private_data_read": False}
Path(sys.argv[1]).write_text(json.dumps(result, indent=2))
print(json.dumps(result))
