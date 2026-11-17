import dataclasses
import json
import os
import sys
import time
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]
from app.config import Settings
from app.services import personal_planner as pp
from app.services.nutrition_prewarm import plain_request
from app.services.personal_source_facts import cached_retained_facts
from app.services.plan_jobs import planning_deadline
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
city = sys.argv[1]
pointer = json.loads((root / "active" / f"city-{city}.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.from_file(root / pointer["artifact_file"]).restore()
t = time.time(); facts = cached_retained_facts(prepared); print("facts", round(time.time()-t, 1), flush=True)
# Settings() alone checks production URLs; the measurement needs only the planner.
settings = dataclasses.replace(Settings(price_provider="mock"), complete_recipes_enabled=True,
                               library_search_policy="smako-current-library-v2")
req = plain_request(prepared)
state = {"id": "m", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}
def once(workers):
    os.environ["SMAKO_PLANNER_PROCESSES"] = str(workers)
    pp._QUALIFICATION_MEMORY.rows.clear()
    prepared.package_cache.clear()
    t = time.perf_counter()
    profile = None
    if os.environ.get("MEASURE_PROFILE"):
        import cProfile
        profile = cProfile.Profile()
        profile.enable()
    with planning_deadline(240):
        plan = pp.PersonalPlanner(req, settings, prepared, state).create()
    if profile is not None:
        import io
        import pstats
        profile.disable()
        out = io.StringIO()
        pstats.Stats(profile, stream=out).sort_stats("tottime").print_stats(30)
        print(f"--- profile workers={workers}\n" + out.getvalue()[-9000:], flush=True)
    ch = plan.model_dump(mode="json")["personal"]["checks"]
    tm = ch.get("timings_seconds") or {}
    print(json.dumps({"workers": workers, "seconds": round(time.perf_counter()-t, 1), "total": str(plan.optimized_basket.total),
        "qualification": round(tm.get("candidate_generation_and_qualification", 0), 1), "search": round(tm.get("week_search", 0), 1),
        "packages": round(tm.get("package_calculation", 0), 1), "recipes": [r.name for r in plan.recipes]}, ensure_ascii=False), flush=True)
once(0)            # also warms the library once
for w in [int(x) for x in os.environ.get("MEASURE_WORKERS", "0,6,0,6").split(",")]:
    once(w)
