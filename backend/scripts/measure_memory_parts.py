"""Which loaded data holds the memory and the Python objects? (server check)

Loads an area step by step and prints, after each step, the process's private
memory and the number of objects the garbage collector tracks: the price
universe, the area's product facts, the recipe library and one plan.
Usage inside the app image: ``python measure_memory_parts.py malmö``.
"""
import dataclasses
import gc
import json
import sys
import time
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]


def private_mb():
    with open("/proc/self/status") as status:
        for line in status:
            if line.startswith("RssAnon:"):
                return round(int(line.split()[1]) / 1024)
    return None


def step(name, started):
    gc.collect()
    print(json.dumps({"step": name, "seconds": round(time.perf_counter() - started, 1),
                      "private_mb": private_mb(), "objects": len(gc.get_objects())}), flush=True)


started = time.perf_counter()
step("python and imports", started)
from app.config import Settings
from app.services import personal_planner as pp
from app.services.nutrition_prewarm import plain_request
from app.services.personal_source_facts import cached_retained_facts
from app.services.plan_jobs import planning_deadline
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

step("app modules", started)
root = Path("/srv/app/var/price_universes")
pointer = json.loads((root / "active" / f"city-{sys.argv[1]}.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.from_file(root / pointer["artifact_file"]).restore()
print(json.dumps({"products": len(prepared.universe.products)}), flush=True)
step("price universe", started)
_ = prepared.economic_pool
step("economic pool", started)
cached_retained_facts(prepared)
step("product facts", started)
from app.services.recipe_library import meal_candidates

req = plain_request(prepared)
meal_candidates(req.personal.meals[0], req.recipe_preferences, include_supplement=True, generation=None)
step("recipe library", started)
settings = dataclasses.replace(Settings(price_provider="mock"), complete_recipes_enabled=True,
                               library_search_policy="smako-current-library-v2")
state = {"id": "m", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}
with planning_deadline(240):
    plan = pp.PersonalPlanner(req, settings, prepared, state).create()
step("one plan (caches kept)", started)
