"""Frozen actual-catalog acceptance of all three personal dinner modes."""
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning
from app.services.inter_plan_distance import compare_plans
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

p = PreparedPriceUniverseArtifact.model_validate_json(Path("reports/private/price-fixture.json").read_bytes()).restore()
state = {"id": "synthetic-mode-probe", "revision": 0, "profile": None, "items": [], "events": {}, "reservations": {}}
results, plans = [], {}
for mode in ("cheapest", "balanced", "varied"):
    started = time.perf_counter()
    req = PlanRequest(recipes=3, diversity_mode=mode, max_stores=2, personal=PersonalPlanning(meals=[MealSettings(count=3, servings=4)]))
    plan = PersonalPlanner(req, Settings(price_provider="mock"), p, state, now=datetime(2026, 9, 10, 17, 30, tzinfo=UTC)).create()
    assert len({r.name for r in plan.recipes}) == 3
    plans[mode] = plan
    row = {"mode": mode, "status": "PASS", "seconds": round(time.perf_counter()-started, 3), "total": plan.optimized_basket.total, "recipes": [r.name for r in plan.recipes]}
    results.append(row)
    print(json.dumps(row), flush=True)
comparison = compare_plans(plans["balanced"].recipes, plans["varied"].recipes)
assert sum(d["structurally_changed"] for d in comparison["dinners"]) >= 2
assert plans["varied"].optimized_basket.total <= plans["balanced"].optimized_basket.total * 1.25 + 0.01
results.append({"comparison": comparison})
Path("reports/personal-v2/personal-modes-final.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
