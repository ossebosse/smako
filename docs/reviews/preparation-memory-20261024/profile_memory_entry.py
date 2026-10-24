"""Measure the instrumented process after its atexit phase-report writer.

The original profiler and plan timing boundaries remain unchanged. Register
first so Python runs this receipt last; a missing receipt fails the caller.
The two path overrides support local subprocess checks without Linux cgroups.
"""
from __future__ import annotations

import atexit
import hashlib
import json
import os
import runpy
from pathlib import Path

LIMIT = 2684354560
ENTRY_SHA = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def finish():
    phase = Path(os.environ['SMAKO_PROFILE_REPORT'])
    phase_bytes = phase.read_bytes()
    assert json.loads(phase_bytes)['schema'] == 'smako-preparation-profile-v1'
    output = phase.parent
    report = json.loads((output/'L5000-verified-distribution.json').read_bytes())
    method = report['method_signature']
    group = Path(os.environ.get('SMAKO_PROFILE_CGROUP_ROOT','/sys/fs/cgroup'))
    memory = {key:int((group/f'memory.{key}').read_text()) for key in ('current','peak')}
    memory['swap_current'] = int((group/'memory.swap.current').read_text())
    entry = Path(os.environ.get('SMAKO_PROFILE_INSTRUMENTATION_ENTRY','/profile_instrumentation.py'))
    target = os.environ.get('SMAKO_MEMORY_TARGET_METHOD')
    result = {'scope':'after plan calls and atexit phase-report serialization; before tiny receipt write',
        'measurement_complete':True,'phase_report_serialized':True,
        'phase_report_sha256':hashlib.sha256(phase_bytes).hexdigest(),
        'entry_sha256':ENTRY_SHA,
        'instrumentation_entry_sha256':hashlib.sha256(entry.read_bytes()).hexdigest(),
        'method_signature':method,'target_method_signature':target,'memory':memory,
        'target_enforced_for_current_runtime':bool(target and method == target),
        'memory_target_passed':memory['peak'] <= LIMIT and memory['swap_current'] == 0}
    (output/'final-resource.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')


if __name__ == '__main__':
    atexit.register(finish)
    runpy.run_path(os.environ.get('SMAKO_PROFILE_INSTRUMENTATION_ENTRY','/profile_instrumentation.py'),
                   run_name='__main__')
