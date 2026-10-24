"""Resume only closed evidence; an SSH reader is not the log's lifetime."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def pilot(monkeypatch):
    scripts = Path(__file__).resolve().parents[2]/'docs/reviews/preparation-memory-20261024'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('pilot_resume_probe',scripts/'run_pilot.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('case',['valid','missing_footer','exceeded_peak'])
def test_resume_requires_actual_closed_process_resources(pilot,tmp_path,case):
    receipt = {'source_commit':pilot.SOURCE,'image':pilot.IMAGE,'user':'10001:10001',
        'state':{'ExitCode':0,'OOMKilled':False},'resources':{'Memory':3221225472,
        'MemorySwap':3221225472,'NanoCpus':2000000000,'NetworkMode':'none','ReadonlyRootfs':True}}
    (tmp_path/'receipt.json').write_text(json.dumps(receipt),encoding='utf8')
    if case != 'missing_footer':
        footer = {'method_signature':'frozen-method','target_enforced_for_current_runtime':True,
            'memory_target_passed':True,'memory':{'peak':pilot.LIMIT+1 if case=='exceeded_peak' else 1024,
                                                'swap_current':0}}
        (tmp_path/'final-resource.json').write_text(json.dumps(footer),encoding='utf8')
    if case == 'valid':
        pilot.validate_closed_resources(tmp_path,'frozen-method')
    else:
        with pytest.raises(FileNotFoundError if case=='missing_footer' else AssertionError):
            pilot.validate_closed_resources(tmp_path,'frozen-method')


def test_resume_preserves_unfinished_nonempty_group(pilot,tmp_path):
    folder = tmp_path/'group'
    folder.mkdir()
    sentinel = folder/'counterexample.json'
    sentinel.write_text('original evidence',encoding='utf8')
    with pytest.raises(AssertionError,match='Preserve incomplete evidence'):
        pilot.make_empty_group(folder)
    assert sentinel.read_text(encoding='utf8') == 'original evidence'


def test_resume_rejects_a_nonprefix_summary(pilot,tmp_path):
    path = tmp_path/'summary.json'
    path.write_text(json.dumps([{'facts_arm':'original','city':'lund','size':262}]),encoding='utf8')
    with pytest.raises(AssertionError,match='exact ordered prefix'):
        pilot.resume_summary(tmp_path)


def test_disk_log_survives_a_closed_transport_and_captures_child_output(tmp_path):
    scripts = Path(__file__).resolve().parents[2]/'docs/reviews/preparation-memory-20261024'
    log = tmp_path/'foreground.log'
    snippet = '''import subprocess,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from resume_current_pipeline import redirect_output
redirect_output(Path(sys.argv[2]))
print('parent continues')
subprocess.run([sys.executable,'-c',"print('child continues')"],check=True)
'''
    with subprocess.Popen([sys.executable,'-c',snippet,str(scripts),str(log)],
                          stdout=subprocess.PIPE,stderr=subprocess.PIPE) as process:
        process.stdout.close()
        process.stderr.close()
        assert process.wait(timeout=15) == 0
    assert log.read_text(encoding='utf8').splitlines() == ['parent continues','child continues']
