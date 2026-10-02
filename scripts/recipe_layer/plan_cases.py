"""Free ordinary five-dinner searches; no locks or patched products."""
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
    label = sys.argv[1] if len(sys.argv) > 1 else 'menus'
    case = sys.argv[2] if len(sys.argv) > 2 else 'greek'
    root = Path('/results') / label
    root.mkdir(parents=True, exist_ok=True)
    clock = install_clock()
    manager = PreparedPriceUniverseManager()
    manager.load_file_and_activate(Path('/inputs/universe.json'))
    service = MealPlanService(Settings(price_provider='own', meal_plan_strategy='optimized',
        price_universe_required=True, complete_recipes_enabled=True), price_universe_manager=manager)
    cuisines = ['greek', 'mexican'] if case == 'mixed-protein40' else [case]
    preferences = {'mode': 'complete', 'cuisines': cuisines, 'min_ingredients': 10, 'max_ingredients': 15}
    if case == 'mixed-protein40':
        preferences.update(min_protein_g=40, max_minutes=40)
    request = PlanRequest(postal_code='22350', recipes=5, servings=2, max_stores=2,
        diversity_mode='balanced', purchase_planning_mode='estimated', allow_nutrition_estimates=True,
        recipe_preferences=preferences,
        personal={'allow_nutrition_estimates': True, 'meals': [{'count': 5, 'servings': 2,
            'limits': {'min_protein_g': 0, 'min_carbs_g': 0, 'min_fat_g': 0, 'max_kcal': 4000}}]})
    record = {'clock': clock.isoformat(), 'case': case, 'request': request.model_dump(mode='json'),
              'resources': {'cpus': 2, 'memory_gib': 3}}
    started, cpu = time.perf_counter(), time.process_time()
    with activate_performance_trace() as trace:
        try:
            plan = await service.create_plan(request)
            (root / (case + '-plan.json')).write_text(plan.model_dump_json(indent=2))
            record.update(status='qualified', total=plan.optimized_basket.total,
                          recipes=[r.name for r in plan.recipes], checks=plan.personal.checks)
        except ValueError as exc:
            record.update(status='stopped', reason=str(exc), stage=getattr(exc, 'stage', None), code=getattr(exc, 'code', None))
    record.update(seconds=time.perf_counter()-started, cpu_seconds=time.process_time()-cpu,
                  peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  trace=dataclasses.asdict(trace.snapshot()))
    (root / (case + '.json')).write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({k: v for k, v in record.items() if k not in {'checks', 'trace', 'request'}}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
