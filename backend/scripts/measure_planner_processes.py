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
settings = Settings.from_env() if hasattr(Settings, "from_env") else Settings()
settings = settings.model_copy(update={"complete_recipes_enabled": True, "library_search_policy": "smako-current-library-v2"})
req = plain_request(prepared)
state = {"id": "m", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}
def once(workers):
    os.environ["SMAKO_PLANNER_PROCESSES"] = str(workers)
    pp._QUALIFICATION_MEMORY.rows.clear()
    prepared.package_cache.clear()
    t = time.perf_counter()
    with planning_deadline(240):
        plan = pp.PersonalPlanner(req, settings, prepared, state).create()
    ch = plan.model_dump(mode="json")["personal"]["checks"]
    tm = ch.get("timings_seconds") or {}
    print(json.dumps({"workers": workers, "seconds": round(time.perf_counter()-t, 1), "total": str(plan.optimized_basket.total),
        "qualification": round(tm.get("candidate_generation_and_qualification", 0), 1), "search": round(tm.get("week_search", 0), 1),
        "packages": round(tm.get("package_calculation", 0), 1), "recipes": [r.name for r in plan.recipes]}, ensure_ascii=False), flush=True)
once(0)            # also warms the library once
for w in (0, 6, 0, 6):
    once(w)
