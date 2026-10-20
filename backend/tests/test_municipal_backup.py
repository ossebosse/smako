import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest

from backend.tests.test_production_deployment import _active_artifact, _configure_backup, _database
from deploy.scripts import backup_schedule, backup_sqlite, restore_sqlite
from deploy.scripts.municipal_backup import current_files, restored_target
from grocery_data.app.services.municipal_rollout import add_municipality


@pytest.mark.parametrize("references", ["approved", "partial_approved"])
def test_new_municipalities_and_current_source_graph_restore_without_changing_age(monkeypatch, tmp_path, references):
    paths = _configure_backup(monkeypatch, tmp_path)
    root = paths['grocery'].parent
    monkeypatch.setenv('REFRESH_CITY', 'Lund')
    monkeypatch.setenv('REFRESH_POSTAL_CODE', '22350')
    add_municipality('1280', '21120', persist=True)
    add_municipality('1480', '41110', persist=True)
    for city in ('malmö', 'göteborg'):
        isolated = tmp_path / city
        _active_artifact(isolated, marker=city)
        import shutil
        for source in isolated.rglob('*'):
            if source.is_file():
                relative = source.relative_to(isolated)
                if relative.as_posix() == 'active/city-lund.json':
                    relative = relative.with_name('city-' + city + '.json')
                target = paths['universe'] / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    source_root = root / 'citygross-municipal'
    source = source_root / '1480/attempts/current.sqlite'
    source.parent.mkdir(parents=True)
    _database(source, 'göteborg-offers')
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    state = source_root / '1480/source-state.json'
    state.write_text(json.dumps({'last_outcomes': {'database': 'diagnostic/path/only.sqlite'},
        references: {'store': [{'database': '1480/attempts/current.sqlite',
        'sha256': digest, 'observed_at': '2026-09-01T00:00:00+00:00'}]}}))
    now = datetime(2026, 9, 3, 2, 47, tzinfo=UTC)
    bundle = backup_sqlite.create_backup(now=now)
    metadata = json.loads((bundle / 'manifest.json').read_bytes())
    assert len(metadata['state_integrity']['municipal_price_universes']) == 3
    assert any(row['path'].endswith('current.sqlite') for row in metadata['files'])
    assert not backup_schedule.due(now=now + timedelta(minutes=15))
    source.write_bytes(b'broken')
    state.write_text('{}')
    registry = root / 'municipal-collection-scopes.json'
    original_registry = registry.read_bytes()
    registry.write_text('{}')
    result = restore_sqlite.restore(bundle, confirm=True)
    assert result['status'] == 'verified'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    assert registry.read_bytes() == original_registry
    assert json.loads(state.read_bytes())[references]['store'][0]['observed_at'] == '2026-09-01T00:00:00+00:00'
    assert backup_schedule.due(now=now + timedelta(days=1))
    add_municipality('1283', '25441', persist=True)
    assert backup_schedule.due(now=now + timedelta(minutes=15))


@pytest.mark.parametrize('bad', ['../../escape.sqlite', '/outside/data.sqlite'])
def test_reference_escape_cannot_create_a_complete_backup(monkeypatch, tmp_path, bad):
    paths = _configure_backup(monkeypatch, tmp_path)
    add_municipality('1280', '21120', persist=True)
    root = paths['grocery'].parent / 'citygross-municipal/1280'
    root.mkdir(parents=True)
    (root / 'source-state.json').write_text(json.dumps({'database': bad}))
    with pytest.raises((ValueError, FileNotFoundError)):
        current_files()
    with pytest.raises(ValueError):
        restored_target('runtime/grocery/../../escape')


def test_failed_due_backup_retries_without_advancing_success(monkeypatch, tmp_path):
    _configure_backup(monkeypatch, tmp_path)
    now = datetime(2026, 10, 13, 7, tzinfo=UTC)
    monkeypatch.setattr(backup_sqlite, '_create_backup_locked', lambda **kw: (_ for _ in ()).throw(OSError()))
    assert backup_schedule.run_due_locked(now=now)['status'] == 'failed'
    assert not backup_schedule.due(now=now + timedelta(minutes=29))
    assert backup_schedule.due(now=now + timedelta(minutes=30))


def test_busy_daily_backup_is_deferred_and_next_worker_can_retry(monkeypatch, tmp_path, capsys):
    from grocery_data.app.services.manual_refresh_operations import RefreshAlreadyRunningError
    _configure_backup(monkeypatch, tmp_path)
    monkeypatch.setattr(backup_sqlite, 'create_backup', lambda: (_ for _ in ()).throw(RefreshAlreadyRunningError()))
    assert backup_sqlite.main() == 1
    assert json.loads(capsys.readouterr().out)['status'] == 'deferred'
    assert backup_schedule.due(now=datetime(2026, 10, 13, 7, tzinfo=UTC))
