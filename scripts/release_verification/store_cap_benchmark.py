"""Time real personal plans for several store caps in an isolated container.

Run inside a release image with the app's data volumes mounted read-only and
no network. Each case is one full ``PersonalPlanner.create()`` on the active
price universe for the postcode: real recipes, products, facts and checkout.
Nothing is saved; the state is an empty guest state. Prints one JSON line per
case: seconds, total, stores used and a digest of the chosen basket, so two
images can be compared case by case.

    python store_cap_benchmark.py CASES.json
"""
import hashlib
import json
import sys
import time
from pathlib import Path


def basket_digest(plan):
    rows = sorted(
        (group.store_id, item.product_id, item.packages_needed)
        for group in plan.optimized_basket.stores for item in group.items)
    recipes = sorted(recipe.name for recipe in plan.recipes)
    return hashlib.sha256(json.dumps([rows, recipes]).encode()).hexdigest()[:16]


def main():
    from app.config import get_settings
    from app.models import PlanRequest
    from app.services.personal_planner import PersonalPlanner
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    cases = json.loads(Path(sys.argv[1]).read_text())
    settings = get_settings()
    root = Path(settings.price_universe_cache_root)
    loaded = {}
    for case in cases:
        city = case["city"]
        if city not in loaded:
            pointer = json.loads((root / "active" / f"city-{city}.json").read_text())
            started = time.perf_counter()
            raw = (root / pointer["artifact_file"]).read_bytes()
            loaded[city] = PreparedPriceUniverseArtifact.model_validate_json(raw).restore()
            print(json.dumps({"loaded": city, "seconds": round(time.perf_counter() - started, 3)}), flush=True)
        state = {"revision": 0, "items": [], "reservations": {}, "events": {}}
        started = time.perf_counter()
        try:
            request = PlanRequest.model_validate(case["request"])
            plan = PersonalPlanner(request, settings, loaded[city], state).create()
            row = {"outcome": "PASS", "total": plan.optimized_basket.total,
                   "stores_used": plan.optimized_basket.store_count,
                   "status": str(plan.optimized_basket.verification_status),
                   "digest": basket_digest(plan)}
        except Exception as exc:  # report every outcome; nothing is retried
            row = {"outcome": type(exc).__name__, "message": str(exc)[:300]}
        row.update(case=case["name"], seconds=round(time.perf_counter() - started, 3))
        print(json.dumps(row, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
