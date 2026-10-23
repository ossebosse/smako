"""A full disk cache must not rescan every retained artifact per missed recipe."""
import os
from pathlib import Path

import pytest
from app.services import meal_prepared_artifacts as artifacts


def test_full_cache_returns_computed_value_without_statting_every_retained_file(tmp_path, monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path))
    monkeypatch.setattr(artifacts, 'MAX_GENERATIONS', 2)
    directory = tmp_path / 'test'
    directory.mkdir()
    old_paths = [directory / 'old-one.json', directory / 'old-two.json']
    for p in old_paths:
        p.write_text('retained evidence')
    observed = []
    original = Path.stat
    def stat(path, *args, **kwargs):
        if path in old_paths:
            observed.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, 'stat', stat)
    result = artifacts.prepared('test', ['new recipe'], lambda: {'value': 42})
    assert result == {'value': 42}
    assert observed == []
    assert sorted(p.name for p in directory.glob('*.json')) == sorted(p.name for p in old_paths)


def test_full_directory_snapshot_skips_repeated_scans_and_detects_removed_entry(tmp_path, monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path))
    monkeypatch.setattr(artifacts, 'MAX_GENERATIONS', 2)
    directory = tmp_path / 'test'
    directory.mkdir()
    for name in ('one', 'two'):
        (directory / f'{name}.json').write_text('retained')
    original = Path.glob
    scans = []
    def glob(path, pattern):
        if path == directory:
            scans.append(path)
        return original(path, pattern)
    monkeypatch.setattr(Path, 'glob', glob)
    for identity in ('first miss', 'second miss'):
        assert artifacts.prepared('test', identity, lambda: {'value': 42}) == {'value': 42}
    assert len(scans) == 1
    before = directory.stat()
    (directory / 'one.json').unlink()
    os.utime(directory, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    assert artifacts.prepared('test', 'new entry', lambda: {'value': 43}) == {'value': 43}
    assert len(list(original(directory, '*.json'))) == 2
    assert artifacts.prepared('test', 'new entry', lambda: pytest.fail('must read validated cache')) == {'value': 43}
