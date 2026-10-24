"""Measure the ordinary frozen facts projection; no menu or audit qualification."""
from __future__ import annotations

import json
import runpy
import sys
import time
from pathlib import Path

index = sys.argv.index('--memory-report')
report_path = Path(sys.argv[index+1])
del sys.argv[index:index+2]
started = time.perf_counter()
try:
    runpy.run_path('/review/backend/scripts/augment_review_facts.py', run_name='__main__')
except SystemExit as error:
    if error.code not in (None, 0):
        raise
memory = {}
for line in Path('/proc/self/status').read_text().splitlines():
    if line.startswith(('VmRSS:', 'VmHWM:')):
        key,value,_ = line.split()
        memory[key.rstrip(':')] = int(value)*1024
for key in ('current','peak'):
    memory['cgroup_'+key] = int(Path('/sys/fs/cgroup/memory.'+key).read_text())
memory['swap_current'] = Path('/sys/fs/cgroup/memory.swap.current').read_text().strip()
report_path.write_text(json.dumps({'status':'DIAGNOSTIC_ONLY_NO_PLAN_OR_AUDIT',
    'elapsed_seconds':time.perf_counter()-started, 'memory':memory,
    'memory_target_passed':memory['cgroup_peak'] <= 2684354560},indent=2)+'\n')
