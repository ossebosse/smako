"""Price/hash of one matrix profile for several LIBRARY_SUBSTITUTION_POOL_LIMIT values.

Runs every limit in ONE process, in the given order: later limits reuse
in-process caches, so wall times are NOT comparable (use the acceptance matrix
for timing). Prices, result hashes and recipes are. Same request, inputs,
quality checks and semantic hash as backend/scripts/planner_acceptance_matrix.py.

usage (repo root of a library worktree, PYTHONPATH=backend:.):
  limit_sweep.py <inputs-dir> <matrix-case> 120,160,0 > out.log
"""
import json
import os
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

os.environ.setdefault("RECIPE_PREPARATION_CACHE_ROOT", ".local/limit-sweep-cache")  # own cache root
from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request, quality

d = Path(sys.argv[1]); case = sys.argv[2]; caps = [int(x) for x in sys.argv[3].split(",")]
m = json.loads((d/"matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((d/"combined-prices.json").read_bytes()).restore()
raw = json.loads((d/"combined-facts.json").read_bytes())
facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
req = matrix_request(json.loads((d/"combined-request.json").read_bytes()), case)
for cap in caps:
    s = replace(Settings(complete_recipes_enabled=True, price_provider="own"), library_substitution_pool_limit=cap)
    t = time.perf_counter()
    p = PersonalPlanner(req, s, prepared, {"revision": 0, "items": [], "reservations": {}, "events": {}}, facts=facts, now=datetime.fromisoformat(m["now"]))
    try:
        plan = p.create(); q = quality(plan, req)
        out = {"cap": cap, "paid": q["paid"], "sha": q["semantic_sha256"][:12], "recipes": q["recipes"]}
    except Exception as e:  # noqa: BLE001 - a failed profile is a recorded result
        out = {"cap": cap, "error": type(e).__name__, "code": getattr(e, "code", None)}
    out.update(wall=round(time.perf_counter()-t, 1),
               subst=[(r.get("substitution_variants_available"), r.get("substitution_variants_retained"), r["proposals"])
                      for r in p.diagnostics.search if r.get("library_phase") == "substitution"])
    print(json.dumps(out, ensure_ascii=False), flush=True)
