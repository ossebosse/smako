"""Same-input cold/warm baseline through the ordinary public planner; offline."""
import asyncio
import cProfile
import dataclasses
import json
import os
import pstats
import resource
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import Settings
from app.models import PlanRequest
from app.services import meal_plan_optimizer, price_universe_runtime, user_pricing
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import activate_performance_trace
from app.services.price_universe_runtime import PreparedPriceUniverseManager


async def main():
    label = sys.argv[1] if len(sys.argv) > 1 else 'baseline'
    root = Path('/results') / label
    root.mkdir(parents=True, exist_ok=True)
    freeze = json.loads(Path('/inputs/freeze.json').read_text())
    clock = datetime.fromisoformat(freeze['frozen_at_utc'])

    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz) if tz else clock.replace(tzinfo=None)

    meal_plan_optimizer.datetime = price_universe_runtime.datetime = ReplayClock
    meal_plan_optimizer.current_pricing_date = user_pricing.current_pricing_date = lambda: clock.astimezone(ZoneInfo('Europe/Stockholm')).date()
    settings = Settings(price_provider='own', meal_plan_strategy='optimized', price_universe_required=True,
                        stable_candidate_search_enabled=True, allow_provider_fallback=False, openai_api_key=None)
    started = time.perf_counter()
    manager = PreparedPriceUniverseManager()
    prepared = manager.load_file_and_activate(Path('/inputs/universe.json'))
    load_seconds = time.perf_counter() - started
    service = MealPlanService(settings, price_universe_manager=manager)
    request = PlanRequest(postal_code='22350', recipes=5, servings=2, max_stores=3,
                          diversity_mode='balanced', purchase_planning_mode='exact', diet_preference='mixed',
                          memberships={k: True for k in ('coop', 'ica', 'hemkop', 'willys', 'lidl', 'citygross')})
    summary = {'label': label, 'artifact_sha256': freeze['artifact_sha256'], 'clock': clock.isoformat(),
               'universe_id': prepared.universe.universe_id, 'load_seconds': load_seconds,
               'resources': {'cpus': 2, 'memory_gib': 3}, 'request': request.model_dump(mode='json'), 'runs': []}
    for phase in ('cold', 'warm'):
        profiler = cProfile.Profile()
        started, cpu = time.perf_counter(), time.process_time()
        with activate_performance_trace() as trace:
            if os.getenv('PROFILE') == '1':
                profiler.enable()
            plan = await service.create_plan(request)
            profiler.disable()
        report = {'phase': phase, 'wall_seconds': time.perf_counter() - started, 'cpu_seconds': time.process_time() - cpu,
                  'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'trace': dataclasses.asdict(trace.snapshot()), 'total': plan.optimized_basket.total,
                  'recipes': [r.name for r in plan.recipes], 'profiled': os.getenv('PROFILE') == '1'}
        summary['runs'].append(report)
        (root / (phase + '-plan.json')).write_text(plan.model_dump_json(indent=2))
        (root / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        if report['profiled']:
            profiler.dump_stats(str(root / (phase + '.prof')))
            with (root / (phase + '-profile.txt')).open('w') as stream:
                pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(70)
        print(json.dumps({k: v for k, v in report.items() if k != 'trace'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
