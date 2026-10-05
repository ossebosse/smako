"""Offline, same-input new-generation benchmark (never a completed-plan cache hit)."""
import asyncio
import cProfile
import dataclasses
import json
import os
import pstats
import resource
import sys
import time
from contextlib import nullcontext
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PROCESS_STARTED = time.perf_counter()

from app.config import Settings
from app.models import PlanRequest
from app.services import meal_plan_optimizer, personal_planner, price_universe_runtime, user_pricing
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import activate_performance_trace
from app.services.price_universe_runtime import PreparedPriceUniverseManager


async def main():
    label = sys.argv[1]
    root = Path('/results') / label
    root.mkdir(parents=True, exist_ok=False)
    freeze = json.loads(Path('/inputs/freeze.json').read_text())
    clock = datetime.fromisoformat(freeze['frozen_at_utc'])

    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.astimezone(tz) if tz else clock.replace(tzinfo=None)

    meal_plan_optimizer.datetime = personal_planner.datetime = price_universe_runtime.datetime = ReplayClock
    meal_plan_optimizer.current_pricing_date = user_pricing.current_pricing_date = lambda: clock.astimezone(ZoneInfo('Europe/Stockholm')).date()
    settings = Settings(price_provider='own', meal_plan_strategy='optimized', price_universe_required=True,
                        stable_candidate_search_enabled=True, allow_provider_fallback=False,
                        complete_recipes_enabled=True, openai_api_key=None)
    started = time.perf_counter()
    manager = PreparedPriceUniverseManager()
    prepared = manager.load_file_and_activate(Path('/inputs/universe.json'))
    load_seconds = time.perf_counter() - started
    service = MealPlanService(settings, price_universe_manager=manager)
    request_data = json.loads(Path('/inputs/request.json').read_text())
    request_data.update(json.loads(os.getenv('REQUEST_OVERRIDES', '{}')))
    request = PlanRequest.model_validate(request_data)
    summary = {'label': label, 'artifact_sha256': freeze['artifact_sha256'], 'clock': clock.isoformat(),
               'universe_id': prepared.universe.universe_id, 'load_seconds': load_seconds,
               'resources': {'cpus': 2, 'memory_gib': 3}, 'request': request.model_dump(mode='json'), 'runs': []}
    for phase in os.getenv('PHASES', 'cold,warm').split(','):
        profiler = cProfile.Profile()
        profiled = os.getenv('PROFILE') == '1'
        # cProfile must run inside the ordinary worker thread, not just its awaiting event loop.
        original = personal_planner.PersonalPlanner.create
        def measured_create(planner, *args, profiled=profiled, profiler=profiler, original=original, **kwargs):
            if profiled:
                return profiler.runcall(original, planner, *args, **kwargs)
            return original(planner, *args, **kwargs)
        personal_planner.PersonalPlanner.create = measured_create
        started, cpu = time.perf_counter(), time.process_time()
        with activate_performance_trace() if profiled else nullcontext() as trace:
            plan = await service.create_plan(request)
        calculation_wall = time.perf_counter() - started
        personal_planner.PersonalPlanner.create = original
        serialized_at = time.perf_counter()
        payload = plan.model_dump_json(indent=2)
        serialization_seconds = time.perf_counter() - serialized_at
        report = {'phase': phase, 'wall_seconds': calculation_wall, 'cpu_seconds': time.process_time() - cpu,
                  'cold_process_to_serialized_seconds': time.perf_counter() - PROCESS_STARTED if phase == 'cold' else None,
                  'serialization_seconds': serialization_seconds,
                  'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                  'trace': dataclasses.asdict(trace.snapshot()) if trace else None,
                  'planner_timings': plan.personal.checks.get('timings_seconds'),
                  'facts_version': plan.personal.checks.get('facts_version'),
                  'total': plan.optimized_basket.total,
                  'recipes': [r.name for r in plan.recipes], 'profiled': profiled}
        if os.getenv('FACTS_COMPARISON_MODE') == 'enriched_historical':
            report['facts_comparison'] = 'enriched_historical; source retrieval dates preserved'
        else:
            assert report['facts_version'] == freeze['expected_facts_version'], 'Historical facts differ from original request'
        summary['runs'].append(report)
        (root / (phase + '-plan.json')).write_text(payload)
        (root / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        if profiled:
            profiler.dump_stats(str(root / (phase + '.prof')))
            with (root / (phase + '-profile.txt')).open('w') as stream:
                pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats('cumulative').print_stats(100)
        print(json.dumps({k: v for k, v in report.items() if k != 'trace'}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
