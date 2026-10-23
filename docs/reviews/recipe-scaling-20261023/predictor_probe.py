"""Does a cheap single-recipe predictor separate improving week proposals?

predictor_probe.py <data-dir> <case> <out.json> [merge]
For every priced proposal that differs from the incumbent in one slot:
P = incumbent - paid(old recipe) + paid(new recipe), from qualification evidence.
"""
import json
import socket
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request

data, case, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
merge = len(sys.argv) > 4 and sys.argv[4] == "merge"
manifest = json.loads((data / "matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((data / "combined-prices.json").read_bytes()).restore()
raw = json.loads((data / "combined-facts.json").read_bytes())
facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
request = matrix_request(json.loads((data / "combined-request.json").read_bytes()), case)
settings = replace(Settings(complete_recipes_enabled=True, price_provider="own"), library_merge_generations=merge, library_substitution_screen_margin=-1.0)
planner = PersonalPlanner(request, settings, prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}},
                          facts=facts, now=datetime.fromisoformat(manifest["now"]))
rows, state = [], {"slots": None, "total": None, "epoch": 0}
original = planner.product_trace.search_decision


def paid(slot):
    ev = planner.variant_search_evidence.get((slot.meal_type, planner._recipe_id(slot.recipe))) if slot.recipe else None
    return float(ev.paid) if ev else None


def observe(slots, outcome, *, result=None, reason=None, depth=None):
    if result is not None and outcome in {"priced", "retained"}:
        total = float(result["basket"].total)
        inc = state["slots"]
        if outcome == "priced" and inc is not None and len(inc) == len(slots):
            diff = [i for i, (a, b) in enumerate(zip(inc, slots, strict=True)) if a != b]
            if len(diff) == 1:
                i = diff[0]
                old, new = paid(inc[i]), paid(slots[i])
                if old is not None and new is not None:
                    rows.append({"inc": state["total"], "actual": total, "P": state["total"] - old + new, "slot": i, "epoch": state["epoch"]})
        if outcome == "retained" or state["total"] is None or total < state["total"]:
            state["slots"], state["total"] = list(slots), total
            state["epoch"] += 1
    return original(slots, outcome, result=result, reason=reason, depth=depth)


planner.product_trace.search_decision = observe
with patch.object(socket.socket, "connect", side_effect=AssertionError("net")):
    plan = planner.create()
improving = [r for r in rows if r["actual"] < r["inc"]]
summary = {"final": plan.optimized_basket.total, "single_slot_priced": len(rows), "improving": len(improving),
           "max_P_ratio_of_improving": max((r["P"] / r["inc"] for r in improving), default=None)}
for m in (0.0, 0.02, 0.05, 0.1, 0.15, 0.2):
    kept = [r for r in rows if r["P"] <= r["inc"] * (1 + m)]
    summary[f"margin_{m}"] = {"kept_share": round(len(kept) / max(1, len(rows)), 3),
                              "improving_lost": sum(1 for r in improving if r["P"] > r["inc"] * (1 + m))}
from collections import defaultdict

groups = defaultdict(list)
for r in rows:
    groups[(r["epoch"], r["slot"])].append(r)
ranks = []
for g in groups.values():
    g.sort(key=lambda r: r["P"])
    ranks += [k for k, r in enumerate(g) if r["actual"] < r["inc"]]
summary["improving_rank_in_slot"] = sorted(ranks)
summary["slot_groups"] = len(groups)
summary["max_group"] = max((len(g) for g in groups.values()), default=0)
out.write_text(json.dumps({"summary": summary, "rows": rows}), encoding="utf-8")
print(json.dumps(summary))
