"""Load an area's price universe as the app does, with snapshots (server check).

Run twice in fresh processes with ``SMAKO_PREPARED_SNAPSHOT_ROOT`` on a
persistent folder: the first loads the JSON and writes the snapshot, the
second loads the snapshot. Each then makes one plain plan, so the result can be
compared. Usage inside the app image: ``python measure_snapshot_load.py malmö``.
"""
import dataclasses
import json
import sys
import time
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]
from app.config import Settings
from app.services import personal_planner as pp
from app.services.nutrition_prewarm import plain_request
from app.services.personal_source_facts import cached_retained_facts
from app.services.plan_jobs import planning_deadline
from app.services.price_universe_runtime import PreparedPriceUniverseManager


def private_mb():
    with open("/proc/self/status") as status:
        for line in status:
            if line.startswith("RssAnon:"):
                return round(int(line.split()[1]) / 1024)
    return None


root = Path("/srv/app/var/price_universes")
pointer = json.loads((root / "active" / f"city-{sys.argv[1]}.json").read_bytes())
manager = PreparedPriceUniverseManager()
started = time.perf_counter()
prepared = manager.load_file_and_activate(root / pointer["artifact_file"])
loaded = time.perf_counter() - started
facts_started = time.perf_counter()
cached_retained_facts(prepared)
facts_seconds = time.perf_counter() - facts_started
settings = dataclasses.replace(Settings(price_provider="mock"), complete_recipes_enabled=True,
                               library_search_policy="smako-current-library-v2")
state = {"id": "m", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}
began = time.perf_counter()
with planning_deadline(240):
    plan = pp.PersonalPlanner(plain_request(prepared), settings, prepared, state).create()
print(json.dumps({"load_seconds": round(loaded, 1), "facts_seconds": round(facts_seconds, 1), "snapshots": sorted(p.name[:20] for p in manager.loaded_snapshots),
                  "plan_seconds": round(time.perf_counter() - began, 1), "total": str(plan.optimized_basket.total),
                  "recipes": [r.name[:30] for r in plan.recipes], "private_mb": private_mb()}, ensure_ascii=False),
      flush=True)
