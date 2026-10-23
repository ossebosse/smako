"""Qualified recipes and menu per profile on a frozen data folder.

qualify_probe.py <data-dir> <out.json> <case> [<case> ...]
"""
import json
import socket
import sys
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request

data, out, cases = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
manifest = json.loads((data / "matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "combined-prices.json").read_bytes()).restore()
raw = json.loads((data / "combined-facts.json").read_bytes())
facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
base = json.loads((data / "combined-request.json").read_bytes())
result = {}
for case in cases:
    request = matrix_request(base, case)
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True, price_provider="own"), prepared,
                              {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=facts,
                              now=datetime.fromisoformat(manifest["now"]))
    started = time.perf_counter()
    row = {}
    with patch.object(socket.socket, "connect", side_effect=AssertionError("net")):
        try:
            plan = planner.create()
            row.update(outcome="PASS", paid=plan.optimized_basket.total,
                       recipes=[s.recipe.name for s in plan.personal.slots if s.recipe])
        except PolicyConflict as exc:
            row.update(outcome="BLOCKED", code=exc.code, reason=str(exc)[:300])
    row["wall_seconds"] = round(time.perf_counter() - started, 1)
    row["qualified"] = planner.diagnostics.singleton_passed
    row["qualified_by_meal_type"] = {}
    for meal_type, _recipe_id in planner.variant_search_evidence:
        row["qualified_by_meal_type"][meal_type] = row["qualified_by_meal_type"].get(meal_type, 0) + 1
    result[case] = row
    print(case, json.dumps(row, ensure_ascii=False)[:400], flush=True)
out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
