"""Acceptance evidence must stop on a lost delivered outcome, not just price."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def evidence_collector(monkeypatch,tmp_path):
    scripts = Path(__file__).resolve().parents[2]/'docs/reviews/preparation-memory-20261024'
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location('frozen_full_matrix_probe',scripts/'run_full_matrix.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    root = tmp_path/'evidence'
    root.mkdir()
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(module,'ORIGINAL',root/'inputs')
    monkeypatch.setattr(module,'LIBRARIES',root/'libraries')
    primary = root/f'candidate-{module.REVISION}-plain'
    primary.mkdir()
    (primary/'L5000-verified-distribution.json').write_text(json.dumps({'method_signature':'frozen-method'}),encoding='utf8')
    inputs = root/'inputs/malmo'
    inputs.mkdir(parents=True)
    (inputs/'matrix-inputs.json').write_text(json.dumps({'sha256':{'fixture':'exact-input'}}),encoding='utf8')
    library = root/'libraries/262'
    library.mkdir(parents=True)
    (library/'library-manifest.json').write_text('{}',encoding='utf8')
    folder = root/f'pilot-{module.REVISION}/original/malmo/262'
    folder.mkdir(parents=True)
    destination = root/'full'
    destination.mkdir()
    return module,folder,destination


def save_report(folder,arm,outcome,*,code='DATA_BLOCKED'):
    rows = [{'outcome':outcome,'cgroup_peak_bytes':100,'code':code,'stage':'qualification'} for _ in range(4)]
    if outcome == 'PASS':
        for row in rows:
            row.update(audit_passed=True,paid=100,semantic_sha256='same-menu',wall_seconds=1)
    data = {'schema':'smako-planner-acceptance-v1','method_signature':'frozen-method',
        'label':f'L262-{arm}','case':'standard','library_version':'fixture-library',
        'inputs':{'sha256':{'fixture':'exact-input'}},'records':rows}
    (folder/f'L262-{arm}-standard.json').write_text(json.dumps(data),encoding='utf8')


@pytest.mark.parametrize('legacy,verified,code,expected',[
    ('PASS','BLOCKED','DATA_BLOCKED','OUTCOME_REGRESSION'),
    ('BLOCKED','BLOCKED','DIFFERENT_BLOCK','UNEXPLAINED_BLOCKED_OUTCOME_CHANGE'),
    ('BLOCKED','BLOCKED','DATA_BLOCKED',None),
])
def test_blocked_evidence_is_not_silently_accepted_against_a_delivered_menu(evidence_collector,legacy,verified,code,expected):
    collector,folder,destination = evidence_collector
    save_report(folder,'main',legacy)
    save_report(folder,'verified',verified,code=code)
    if expected:
        with pytest.raises(RuntimeError,match=expected):
            collector.collect(destination)
    else:
        collector.collect(destination)
    saved = json.loads((destination/'cells.json').read_bytes())
    assert saved['required_cells'] == 252 and saved['measured_cells'] == 2
    assert saved['full_matrix_qualified'] is False
    assert bool(saved['failures']) is bool(expected)
    if expected:
        assert saved['failures'][0]['gate'] == expected
    else:
        assert saved['status'] == 'IN_PROGRESS' and saved['observed_blocked_cells'] == 2
