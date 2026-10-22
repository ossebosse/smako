"""List every egg-named product and whether the recipe egg identity accepts it.

Usage: egg_check.py <data-dir> <output.json>; run with the checkout's PYTHONPATH.
"""
import json
import sys
from pathlib import Path

from app.services.complete_recipes import _whole_food_identity
from app.services.personal_policy import ProductFacts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

data, out = Path(sys.argv[1]), Path(sys.argv[2])
prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "combined-prices.json").read_bytes()).restore()
raw = json.loads((data / "product-facts.json").read_bytes())
facts = {(r["store_id"], r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]}
rows = []
for p in prepared.universe.products:
    if "ägg" not in p.name.casefold():
        continue
    fact = facts.get((p.store_id, p.product_id))
    rows.append({"chain": p.chain, "store_id": p.store_id, "name": p.name, "brand": getattr(p, "brand", None),
                 "ingredients": list(fact.ingredients) if fact else None,
                 "accepted": bool(_whole_food_identity("ägg", "raw_edible", p, fact))})
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(rows), sum(r["accepted"] for r in rows))
