"""An authorized unlimited total retains history and per-operation accounting."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def subject(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'scripts/recipe_layer'))
    import budgeted_check
    previous = sys.modules.get('smako_budget_context')
    monkeypatch.setattr(sys, 'argv', list(sys.argv))
    yield budgeted_check
    if previous is not None:
        sys.modules['smako_budget_context'] = previous
    else:
        sys.modules.pop('smako_budget_context', None)


def test_unlimited_total_keeps_history_and_charges_the_new_operation(tmp_path, monkeypatch, subject):
    path = tmp_path / 'budget.json'
    old = {'label': 'previous work', 'wall_seconds': 4501, 'status': 'complete'}
    path.write_text(json.dumps({'limit_seconds': None, 'entries': [old]}))
    monkeypatch.setattr(subject, 'windows_limits', lambda: (lambda _p: None, lambda: 123,
                        lambda _p: (45, 67), lambda: None))
    calls = []

    def run_script(path, **kwargs):
        import smako_budget_context
        calls.append(path)
        smako_budget_context.arm_phase(5)()

    monkeypatch.setattr(subject.runpy, 'run_path', run_script)
    assert subject.run(SimpleNamespace(budget=path, label='new work', max_seconds=5,
                                      command=['synthetic.py'])) == 0
    result = json.loads(path.read_bytes())
    assert calls == ['synthetic.py'] and result['entries'][0] == old
    assert result['entries'][1]['status'] == 'complete'
    assert result['used_seconds'] >= 4501 and result['remaining_seconds'] is None


def test_bounded_exhausted_journal_still_refuses_to_start_work(tmp_path, subject):
    path = tmp_path / 'budget.json'
    before = json.dumps({'limit_seconds': 100, 'entries': [{'wall_seconds': 100, 'status': 'complete'}]})
    path.write_text(before)
    with pytest.raises(RuntimeError, match='exhausted'):
        subject.run(SimpleNamespace(budget=path))
    assert path.read_text() == before
