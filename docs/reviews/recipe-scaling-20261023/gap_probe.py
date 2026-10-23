"""How far above the incumbent are priced week proposals? (prunability estimate)

Wraps the week-search observer; run like the matrix: gap_probe.py <data-dir> <case> <out.json>
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
from app.services.product_planning_trace import ProductPlanningTrace

from backend.scripts.planner_acceptance_matrix import matrix_request

data, case, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
manifest = json.loads((data / "matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "combined-prices.json").read_bytes()).restore()
raw = json.loads((data / "combined-facts.json").read_bytes())
facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
request = matrix_request(json.loads((data / "combined-request.json").read_bytes()), case)
events = []
original = ProductPlanningTrace.search_decision


def observe(self, slots, outcome, *, result=None, reason=None, depth=None):
    if result is not None and outcome in {"priced", "retained"}:
        events.append((outcome, depth, float(result["basket"].total)))
    return original(self, slots, outcome, result=result, reason=reason, depth=depth)


with patch.object(ProductPlanningTrace, "search_decision", observe), \
        patch.object(socket.socket, "connect", side_effect=AssertionError("net")):
    plan = PersonalPlanner(request, Settings(complete_recipes_enabled=True, price_provider="own"), prepared,
                           {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=facts,
                           now=datetime.fromisoformat(manifest["now"])).create()
best, gaps = None, []
for outcome, depth, total in events:
    if outcome == "retained":
        best = total if best is None else min(best, total)
        continue
    if best is not None:
        gaps.append(total / best - 1)
    best = total if best is None else min(best, total)
gaps.sort()
n = len(gaps)
summary = {"final": plan.optimized_basket.total, "priced": n,
           **{f"share_above_{p}pct": round(sum(g > p / 100 for g in gaps) / n, 3) for p in (0, 2, 5, 10, 20, 30)}}
out.write_text(json.dumps({"summary": summary, "gaps": gaps}), encoding="utf-8")
print(json.dumps(summary))
