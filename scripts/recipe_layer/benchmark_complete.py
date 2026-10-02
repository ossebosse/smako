"""Cold/warm complete dinner search on the same frozen ordinary planner path."""
import asyncio
import dataclasses
import json
import resource
import sys
import time
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import activate_performance_trace
from app.services.price_universe_runtime import PreparedPriceUniverseManager
from replay import install_clock


async def main():
    label = sys.argv[1] if len(sys.argv) > 1 else "complete-performance"
    root = Path("/results") / label
    root.mkdir(parents=True, exist_ok=True)
    clock = install_clock()
    manager = PreparedPriceUniverseManager()
    started = time.perf_counter()
    manager.load_file_and_activate(Path("/inputs/universe.json"))
    load_seconds = time.perf_counter() - started
    service = MealPlanService(Settings(price_provider="own", meal_plan_strategy="optimized",
        price_universe_required=True, complete_recipes_enabled=True), price_universe_manager=manager)
    request = PlanRequest(postal_code="22350", recipes=5, servings=2, max_stores=2,
        diversity_mode="cheapest", purchase_planning_mode="estimated", allow_nutrition_estimates=True,
        recipe_preferences={"mode": "complete", "cuisines": ["greek", "mexican"],
                            "min_ingredients": 10, "max_ingredients": 15,
                            "max_minutes": 40, "min_protein_g": 40})
    report = {"clock": clock.isoformat(), "stage": json.loads(Path("/evaluation/stage.json").read_text()),
              "request": request.model_dump(mode="json"), "resources": {"cpus": 2, "memory_gib": 3},
              "load_seconds": load_seconds, "runs": []}
    for phase in ("cold", "warm"):
        started, cpu = time.perf_counter(), time.process_time()
        with activate_performance_trace() as trace:
            plan = await service.create_plan(request)
        record = {"phase": phase, "wall_seconds": time.perf_counter()-started,
                  "cpu_seconds": time.process_time()-cpu,
                  "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  "total": plan.optimized_basket.total,
                  "recipes": [r.name for r in plan.recipes],
                  "trace": dataclasses.asdict(trace.snapshot())}
        (root / (phase + "-plan.json")).write_text(plan.model_dump_json(indent=2))
        report["runs"].append(record)
        (root / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(json.dumps({k: v for k, v in record.items() if k != "trace"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
