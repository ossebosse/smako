import ast
import importlib.util
import json
import sys
import types
from datetime import UTC, datetime
from pathlib import Path

import pytest


def test_portable_retention_supplies_validator_missing_on_installed_scheduler(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        'target_storage_axfood_test', Path(__file__).parents[2] / 'scripts/target_storage.py')
    target = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(target)
    captured = []

    def remote(*args, **kwargs):
        captured.append(kwargs['input'].decode())
        return json.dumps({'status': 'complete'}).encode()

    monkeypatch.setattr(target.subprocess, 'check_output', remote)
    assert target.maintain_target('test')['status'] == 'complete'
    tree = ast.parse(captured[0])
    sources = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'sources' for t in node.targets))
    module = types.ModuleType('portable_storage_test')
    exec(sources['deploy.scripts.storage_maintenance'], module.__dict__)  # noqa: S102 - checked-in bundle under test
    name = 'grocery_data.app.services.axfood_detail_archive'
    monkeypatch.setitem(sys.modules, name, None)
    archive = tmp_path / 'archive'
    archive.mkdir()
    with pytest.raises(ModuleNotFoundError):
        module.maintain_axfood_archives(archive, now=datetime.now(UTC))
    validator = types.ModuleType(name)
    monkeypatch.setitem(sys.modules, name, validator)
    exec(sources[name], validator.__dict__)  # noqa: S102 - checked-in bundle under test
    assert module.maintain_axfood_archives(archive, now=datetime.now(UTC))['status'] == 'complete'
