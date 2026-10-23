"""List every egg-named product, whether the recipe egg identity accepts it and its usable mass.

Usage: egg_check.py <data-dir> <output.json>; run with the checkout's PYTHONPATH.
"""
import json
import sys
from pathlib import Path

from app.services.complete_recipes import _whole_food_identity
from app.services.official_product_facts import project_usable_quantity, shell_egg_quantity_proofs
from app.services.personal_policy import ProductFacts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

data, out = Path(sys.argv[1]), Path(sys.argv[2])
prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "combined-prices.json").read_bytes()).restore()
raw = json.loads((data / "product-facts.json").read_bytes())
facts = {(r["store_id"], r["product_id"]): ProductFacts(**r["facts"]) for r in raw["rows"]}
eggs = [p for p in prepared.universe.products if "ägg" in p.name.casefold()]
shell_egg_quantity_proofs(eggs, facts)
rows = []
for p in eggs:
    fact = facts.get((p.store_id, p.product_id))
    accepted = bool(_whole_food_identity("ägg", "raw_edible", p, fact))
    usable = project_usable_quantity(p, fact, allow_estimates=True, required_unit="g") if accepted else None
    rows.append({"chain": p.chain, "store_id": p.store_id, "name": p.name, "brand": getattr(p, "brand", None),
                 "ingredients": list(fact.ingredients) if fact else None, "accepted": accepted,
                 "package": [p.package_quantity, p.package_unit],
                 "usable_g": usable.usable_quantity if usable is not None and usable.usable_unit == "g" else None})
out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(rows), sum(r["accepted"] for r in rows), sum(r["usable_g"] is not None for r in rows))
