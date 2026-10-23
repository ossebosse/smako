"""Why did a profile get dearer with more facts? Old basket products under the new facts.

diff_probe.py <old-data> <new-data> <case>
"""
import json
import socket
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request

old, new, case = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]


def load(data):
    raw = json.loads((data / "combined-facts.json").read_bytes())
    return FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})


manifest = json.loads((old / "matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((old / "combined-prices.json").read_bytes()).restore()
request = matrix_request(json.loads((old / "combined-request.json").read_bytes()), case)
old_facts, new_facts = load(old), load(new)
with patch.object(socket.socket, "connect", side_effect=AssertionError("net")):
    plan = PersonalPlanner(request, Settings(complete_recipes_enabled=True, price_provider="own"), prepared,
                           {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=old_facts,
                           now=datetime.fromisoformat(manifest["now"])).create()
print("old menu", plan.optimized_basket.total, [s.recipe.name for s in plan.personal.slots if s.recipe])
for store in plan.optimized_basket.stores:
    for item in store.items:
        key = (item.store_id, item.product_id)
        a, b = old_facts.get(key), new_facts.get(key)
        if a == b:
            continue
        print(f"- {item.ingredient}: {item.product_name} ({item.total_price} kr)")
        for field in ("ingredients", "animal", "organic", "nutrition", "nutrition_unit", "conflicts"):
            va, vb = getattr(a, field, None), getattr(b, field, None)
            if va != vb:
                print(f"    {field}: {str(va)[:90]} -> {str(vb)[:160]}")

with patch.object(socket.socket, "connect", side_effect=AssertionError("net")):
    replanner = PersonalPlanner(request, Settings(complete_recipes_enabled=True, price_provider="own"), prepared,
                                {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=new_facts,
                                now=datetime.fromisoformat(manifest["now"]))
    replanner.create()  # same request setup; then price the OLD menu exactly
    try:
        again = replanner.basket(plan.personal.slots, final=True)
        print("old menu under new facts:", again["basket"].total,
              "accepted:", replanner._search_accepts(plan.personal.slots) if hasattr(replanner, "_search_accepts") else "n/a")
    except Exception as exc:  # noqa: BLE001 - diagnostic probe
        print("old menu under new facts rejected:", type(exc).__name__, str(exc)[:300])
