"""The phase report may raise memory.peak after the plan's own sample."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize('peak,valid_phase',[(1024,True),(2684354561,True),(1024,False)])
def test_phase_memory_receipt_runs_after_report_serialization(tmp_path,peak,valid_phase):
    wrapper = Path(__file__).resolve().parents[2]/'docs/reviews/preparation-memory-20261024/profile_memory_entry.py'
    group = tmp_path/'cgroup'
    group.mkdir()
    for name in ('current','peak','swap.current'):
        (group/f'memory.{name}').write_text('0',encoding='utf8')
    (tmp_path/'L5000-verified-distribution.json').write_text(
        json.dumps({'method_signature':'fixture-method'}),encoding='utf8')
    phase = tmp_path/'phase-profile.json'
    instrumentation = tmp_path/'profiler.py'
    instrumentation.write_text('''import atexit,json,os
from pathlib import Path
def save():
    root=Path(os.environ['SMAKO_PROFILE_CGROUP_ROOT'])
    (root/'memory.peak').write_text(os.environ['FIXTURE_PEAK'],encoding='utf8')
    value=json.dumps({'schema':'smako-preparation-profile-v1'})
    if os.environ['FIXTURE_VALID_PHASE']=='False':value='truncated {'
    Path(os.environ['SMAKO_PROFILE_REPORT']).write_text(value,encoding='utf8')
atexit.register(save)
''',encoding='utf8')
    env = {**os.environ,'SMAKO_PROFILE_REPORT':str(phase),
        'SMAKO_PROFILE_CGROUP_ROOT':str(group),'SMAKO_PROFILE_INSTRUMENTATION_ENTRY':str(instrumentation),
        'SMAKO_MEMORY_TARGET_METHOD':'fixture-method','FIXTURE_PEAK':str(peak),
        'FIXTURE_VALID_PHASE':str(valid_phase)}
    completed = subprocess.run([sys.executable,str(wrapper)],env=env,check=True,capture_output=True)
    receipt = tmp_path/'final-resource.json'
    if not valid_phase:
        assert not receipt.exists()  # The caller must reject the missing footer.
        return
    assert receipt.exists(), completed.stderr.decode('utf8',errors='replace')
    data = json.loads(receipt.read_bytes())
    assert data['measurement_complete'] and data['phase_report_serialized']
    assert data['memory']['peak'] == peak  # Not the zero sampled during the plan.
    assert data['memory_target_passed'] is (peak <= 2684354560)
    assert data['target_enforced_for_current_runtime']
    assert data['entry_sha256'] == hashlib.sha256(wrapper.read_bytes()).hexdigest()
    assert data['phase_report_sha256'] == hashlib.sha256(phase.read_bytes()).hexdigest()
    assert data['instrumentation_entry_sha256'] == hashlib.sha256(instrumentation.read_bytes()).hexdigest()
