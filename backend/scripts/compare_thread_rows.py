"""Qualification rows on one core against threads (server-only check).

Runs the same plain plan twice from cold caches, once with
``SMAKO_PLANNER_PROCESSES=0`` and once with the given number of workers, and
prints every recipe whose qualification row differs, with both reasons.
Usage inside the app image: ``python compare_thread_rows.py malmö 5``.
"""
import dataclasses
import json
import os
import sys
from pathlib import Path

sys.path[:0] = ["/srv/app/backend", "/srv/app"]
from app.config import Settings
from app.services import personal_planner as pp
from app.services.nutrition_prewarm import plain_request
from app.services.personal_source_facts import cached_retained_facts
from app.services.plan_jobs import planning_deadline
from app.services.planner_shared_cache import SHARED_NUTRITION, SHARED_RESOLUTION
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

root = Path("/srv/app/var/price_universes")
city, workers = sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "5"
pointer = json.loads((root / "active" / f"city-{city}.json").read_bytes())
prepared = PreparedPriceUniverseArtifact.from_file(root / pointer["artifact_file"]).restore()
cached_retained_facts(prepared)
settings = dataclasses.replace(Settings(price_provider="mock"), complete_recipes_enabled=True,
                               library_search_policy="smako-current-library-v2")
req = plain_request(prepared)
state = {"id": "m", "revision": 0, "profile": None, "items": [], "reservations": {}, "events": {}}


def rows(count):
    os.environ["SMAKO_PLANNER_PROCESSES"] = count
    pp._QUALIFICATION_MEMORY.rows.clear()
    prepared.package_cache.clear()
    SHARED_RESOLUTION.clear()
    SHARED_NUTRITION.clear()
    with planning_deadline(300):
        plan = pp.PersonalPlanner(req, settings, prepared, state).create()
    merged = {}
    for value in pp._QUALIFICATION_MEMORY.rows.values():
        merged.update(value["rows"])
    return plan.optimized_basket.total, merged


serial_total, serial = rows("0")
thread_total, threaded = rows(workers)
differ = [key for key in serial.keys() | threaded.keys() if serial.get(key) != threaded.get(key)]
print(json.dumps({"serial_total": str(serial_total), "thread_total": str(thread_total),
                  "rows": [len(serial), len(threaded)], "differ": len(differ)}), flush=True)
for key in differ[:15]:
    a, b = serial.get(key) or {}, threaded.get(key) or {}
    print(json.dumps({"serial": [a.get("status"), a.get("code"), (a.get("reason") or "")[:160]],
                      "thread": [b.get("status"), b.get("code"), (b.get("reason") or "")[:160]],
                      "evidence_equal": a.get("evidence") == b.get("evidence")}, ensure_ascii=False), flush=True)
