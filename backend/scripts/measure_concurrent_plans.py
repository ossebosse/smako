"""Several people planning at once, on a retained city universe (server-only tool).

Starts N different plain dinner weeks at the same moment, each in its own
request thread as the web app does (``run_plan_in_process``), first with every
plan in the app process (``SMAKO_PLAN_PROCESSES=0``, plans take turns on one
core) and then with one process per plan. Prints each plan's time, its total
and the container's peak memory. Nothing is written; no network is needed.

Usage inside the app image: ``python3 measure_concurrent_plans.py malmö 3``.
"""
import dataclasses
import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]
from app.config import Settings
from app.services import personal_planner as pp
from app.services.nutrition_prewarm import plain_request
from app.services.personal_source_facts import cached_retained_facts
from app.services.plan_jobs import planning_deadline
from app.services.planner_processes import run_plan_in_process
from app.services.planner_shared_cache import SHARED_NUTRITION, SHARED_RESOLUTION
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
city, people = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 3
pointer = json.loads((root / "active" / f"city-{city}.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.from_file(root / pointer["artifact_file"]).restore()
started = time.time()
cached_retained_facts(prepared)
print("facts", round(time.time() - started, 1), flush=True)
settings = dataclasses.replace(Settings(price_provider="mock"), complete_recipes_enabled=True,
                               library_search_policy="smako-current-library-v2")
state = {"id": "m", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}


def request(person):
    # Different people: other servings and dinner counts, so no plan is a copy.
    base = plain_request(prepared).model_dump(mode="json")
    meal = base["personal"]["meals"][0]
    meal["servings"] = base["servings"] = 2 + person % 3
    meal["count"] = base["recipes"] = 3 + person // 3
    return type(plain_request(prepared)).model_validate(base)


def peak_memory():
    for path in ("/sys/fs/cgroup/memory.peak", "/sys/fs/cgroup/memory/memory.max_usage_in_bytes"):
        try:
            return round(int(Path(path).read_text()) / 2**30, 2)
        except (OSError, ValueError):
            continue
    return None


def round_of(mode):
    os.environ["SMAKO_PLAN_PROCESSES"] = mode
    pp._QUALIFICATION_MEMORY.rows.clear()
    prepared.package_cache.clear()
    SHARED_RESOLUTION.clear()
    SHARED_NUTRITION.clear()
    results, gate = [None] * people, threading.Barrier(people)

    def one(person):
        req = request(person)
        gate.wait()
        begun = time.perf_counter()
        try:
            with planning_deadline(300):
                plan = run_plan_in_process(lambda: pp.PersonalPlanner(req, settings, prepared, state).create())
            results[person] = {"seconds": round(time.perf_counter() - begun, 1),
                               "total": str(plan.optimized_basket.total)}
        except Exception as error:  # noqa: BLE001 - reported, not hidden
            results[person] = {"seconds": round(time.perf_counter() - begun, 1), "error": repr(error)[:200]}

    begun = time.perf_counter()
    threads = [threading.Thread(target=one, args=(i,)) for i in range(people)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    print(json.dumps({"plan_processes": mode, "people": people, "wall": round(time.perf_counter() - begun, 1),
                      "plans": results, "peak_gb": peak_memory()}), flush=True)


for mode in os.environ.get("MEASURE_MODES", "0,1").split(","):
    round_of(mode)
