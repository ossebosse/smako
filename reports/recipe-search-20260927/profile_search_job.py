"""Profile unchanged planner against the frozen native price universe."""
import cProfile
import json
import os
import pstats
import runpy
import sys
from pathlib import Path

os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite', GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
out = Path('/work/profile'); out.mkdir(exist_ok=True)
request = json.loads(Path('/evaluation/original-request.json').read_bytes())
request['purchase_planning_mode'] = 'exact'
p = out/'before-profiled-request.json'; p.write_text(json.dumps(request))
sys.argv = ['evaluate_profile.py', '--recipe-version', 'edible-input-v1', '--artifact', '/work/universe.json',
            '--request', str(p), '--output', str(out), '--label', 'before-profiled',
            '--clock', '2026-09-24T21:16:35.494010+00:00', '--cases', 'restored-original',
            '--universes', '/work/base/price-universes']
profiler = cProfile.Profile(); profiler.enable()
runpy.run_path('/evaluation/evaluate_profile.py', run_name='__main__')
profiler.disable()
stats = pstats.Stats(profiler)
rows = [{'file': k[0], 'line': k[1], 'function': k[2], 'primitive_calls': v[0], 'calls': v[1],
         'self_seconds': v[2], 'inclusive_seconds': v[3]} for k, v in stats.stats.items()]
(out/'before-cprofile.json').write_text(json.dumps(sorted(rows,key=lambda r:r['inclusive_seconds'],reverse=True)[:120],indent=2))
