"""One planner run on frozen matrix inputs; aggregate week-search trace by phase.

usage (repo root, PYTHONPATH=backend:.): search_phases.py --inputs DIR --case standard --output out.json
Uses the acceptance matrix's own input validation and request construction.
"""
import argparse
import json
import os
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--inputs", type=Path, required=True)
parser.add_argument("--case", default="standard")
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--uncapped", action="store_true")
args = parser.parse_args()
os.environ.setdefault("RECIPE_PREPARATION_CACHE_ROOT", str(args.output.with_suffix(".cache")))

from app.config import Settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import ProductFacts
from app.services.personal_source_facts import FactsCollection
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

from backend.scripts.planner_acceptance_matrix import matrix_request

manifest = json.loads((args.inputs / "matrix-inputs.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.model_validate_json((args.inputs / "combined-prices.json").read_bytes()).restore()
raw = json.loads((args.inputs / "combined-facts.json").read_bytes())
facts = FactsCollection({tuple(k): ProductFacts(**v) for k, v in raw["facts"]})
request = matrix_request(json.loads((args.inputs / "combined-request.json").read_bytes()), args.case)
settings = Settings(complete_recipes_enabled=True, price_provider="own")
from dataclasses import replace as _r

settings = _r(settings, library_substitution_slot_limit=int(os.environ.get("SLOT", "0")), library_substitution_screen_margin=float(os.environ.get("SCREEN", "0.10")), library_merge_generations=os.environ.get("MERGE") == "1", library_substitution_pool_limit=int(os.environ.get("POOL", "160")))
if args.uncapped:
    from dataclasses import replace
    settings = replace(settings, library_seed_pool_limit=0, library_refinement_pool_limit=0,
                       library_seed_variant_shortlist=False, library_substitution_pool_limit=0)
state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
started = time.perf_counter()
planner = PersonalPlanner(request, settings, prepared, state, facts=facts,
                          now=datetime.fromisoformat(manifest["now"]))
plan = planner.create()
wall = time.perf_counter() - started
phases = defaultdict(lambda: defaultdict(int))
for row in planner.diagnostics.search:
    key = (row.get("library_phase", "beam"), row.get("library_generation"), row.get("attempt"))
    for field in ("proposals", "constraints_rejected", "priced", "evaluations_executed", "evaluation_cache_hits",
                  "evaluation_rejected"):
        phases[key][field] += row.get(field, 0)
    phases[key]["rows"] += 1
    for field in ("seed_variants_available", "seed_variants_retained",
                  "substitution_variants_available", "substitution_variants_retained"):
        if field in row:
            phases[key][field] = row[field]
pools = planner.diagnostics.pools
out = {"wall_seconds": wall, "paid": plan.optimized_basket.total, "timings": dict(planner.timings),
       "pools": pools, "generation": planner._generation,
       "phases": [{"phase": k[0], "generation": k[1], "attempt": k[2], **v} for k, v in phases.items()]}
args.output.write_text(json.dumps(out, indent=1, default=str), encoding="utf8")
print(json.dumps(out, indent=1, default=str))
