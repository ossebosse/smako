"""Measure real planner work in a resource-limited, isolated release container.

The previous scale generator logic is unchanged (LF/CRLF is recorded separately).
Its handoff to benchmark.py
is routed here only to add CPU/cgroup metrics and separate trial output names.
No products, recipe definitions, requests, planner results or clocks are mocked.
"""
import hashlib
import json
import os
import resource
import runpy
import sys
import time
from datetime import datetime
from pathlib import Path


def measure(label, case, mode):
    from app.config import Settings
    from app.models import PlanRequest
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_source_facts import load_retained_facts
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    root = Path('/results') / label
    root.mkdir(exist_ok=True)
    freeze = json.loads(Path('/inputs/freeze.json').read_bytes())
    raw = Path('/inputs/universe.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == freeze['artifact_sha256']
    started = time.perf_counter()
    prepared = PreparedPriceUniverseArtifact.model_validate_json(raw).restore()
    universe_seconds = time.perf_counter() - started
    del raw
    request = PlanRequest.model_validate(json.loads(Path('/evaluation/requests.json').read_bytes())[case])
    settings = Settings(price_provider='own', complete_recipes_enabled=True)
    state = {'revision': 0, 'items': [], 'reservations': {}, 'events': {}}
    rows = []
    for iteration in range(4 if mode == 'warm' else 1):
        started = time.perf_counter()
        cpu = resource.getrusage(resource.RUSAGE_SELF)
        facts = load_retained_facts(prepared)
        fact_seconds = time.perf_counter() - started
        planning_started = time.perf_counter()
        planner = PersonalPlanner(request, settings, prepared, state, facts=facts,
                                  now=datetime.fromisoformat(freeze['frozen_at_utc']))
        result = planner.create()
        planner_seconds = time.perf_counter() - planning_started
        cpu_after = resource.getrusage(resource.RUSAGE_SELF)
        (root / f'{case}-{mode}-{iteration}-plan.json').write_text(
            json.dumps(result.model_dump(mode='json'), ensure_ascii=False, indent=2))
        from app.services.meal_prepared_artifacts import STATS
        row = {'outcome': 'PASS', 'iteration': iteration, 'mode': mode, 'case': case,
               'facts_seconds': fact_seconds, 'planner_seconds': planner_seconds,
               'serialization_seconds': time.perf_counter() - planning_started - planner_seconds,
               'wall_seconds': time.perf_counter() - started,
               'universe_seconds': universe_seconds,
               'cpu_user_seconds': cpu_after.ru_utime - cpu.ru_utime,
               'cpu_system_seconds': cpu_after.ru_stime - cpu.ru_stime,
               'maxrss_kib': cpu_after.ru_maxrss,
               'cgroup_memory_peak_bytes': int(Path('/sys/fs/cgroup/memory.peak').read_text()),
               'cpu_stat': Path('/sys/fs/cgroup/cpu.stat').read_text(),
               'preparation_stats': dict(STATS), 'facts_version': facts.version,
               'paid': result.optimized_basket.total,
               'check_timings': result.personal.checks.get('timings_seconds')}
        rows.append(row)
        (root / f'{case}-{mode}-timings.json').write_text(json.dumps(rows, indent=2))
        print(json.dumps(row), flush=True)


if __name__ == '__main__':
    label, case, mode, factor = sys.argv[1:5]
    assert mode in {'cold', 'persistent', 'warm'} and factor in {'0', '1', '2', '5'}
    # Zero is the actual 182-recipe P3 library. 1/2/5 use the earlier issued
    # 176-recipe P2 corpus and the exact previous synthetic generator.
    if factor == '0':
        measure(label, case, mode)
    else:
        original = runpy.run_path

        def dispatch(path, *args, **kwargs):
            if path == '/evaluation/benchmark.py':
                return measure(label, case, mode)
            return original(path, *args, **kwargs)

        runpy.run_path = dispatch
        sys.argv = ['scale', factor, case]
        original('/evaluation/scale.py', run_name='__main__')
        for suffix in ('preparation', 'validation'):
            source = Path(f'/results/scale-{factor}-{case}-{suffix}.json')
            if source.exists():
                os.replace(source, Path('/results') / label / source.name)
