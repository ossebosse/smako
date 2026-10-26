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


def test_content_batch_enforces_limits_and_rescans_after_restart_or_removal(tmp_path, monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path))
    monkeypatch.setattr(artifacts, 'CONTENT_LIMIT', 2)
    with artifacts._content_write_batch() as budget:
        for index in range(5):
            assert artifacts.prepared('content', index, lambda index=index: {'value': index},
                                      _write_budget=budget) == {'value': index}
    paths = sorted((tmp_path / 'content').glob('*.json'))
    assert len(paths) == 2
    retained = paths[1].read_bytes()
    paths[0].unlink()
    with artifacts._content_write_batch() as budget:
        assert artifacts.prepared('content', 'after removal', lambda: {'value': 42},
                                  _write_budget=budget) == {'value': 42}
    assert len(list((tmp_path / 'content').glob('*.json'))) == 2
    assert paths[1].read_bytes() == retained


def test_content_batch_competing_writer_computes_without_writing(tmp_path, monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path))
    with artifacts._content_write_batch() as writer:
        assert writer.writable
        with artifacts._content_write_batch() as contender:
            assert not contender.writable
            assert artifacts.prepared('content', 'contender', lambda: {'value': 42},
                                      _write_budget=contender) == {'value': 42}
            assert not list((tmp_path / 'content').glob('*.json'))
        artifacts.prepared('content', 'writer', lambda: {'value': 43}, _write_budget=writer)
    assert len(list((tmp_path / 'content').glob('*.json'))) == 1


def test_content_batch_enforces_total_bytes_across_entries(tmp_path, monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path))
    monkeypatch.setattr(artifacts, 'MAX_BYTES', 600)
    values = [{'value': 'x' * 120, 'index': index} for index in range(4)]
    with artifacts._content_write_batch() as budget:
        for index, value in enumerate(values):
            assert artifacts.prepared('content', index, lambda value=value: value, _write_budget=budget) == value
    paths = list((tmp_path / 'content').glob('*.json'))
    assert paths and len(paths) < len(values)
    assert sum(p.stat().st_size for p in paths) <= 600


def test_version_change_at_full_content_cache_recomputes_without_stale_reuse(tmp_path, monkeypatch):
    monkeypatch.setenv('RECIPE_PREPARATION_CACHE_ROOT', str(tmp_path))
    monkeypatch.setattr(artifacts, 'CONTENT_LIMIT', 1)
    version = ['first-source-version']
    monkeypatch.setattr(artifacts, 'method_signature', lambda: version[0])
    assert artifacts.prepared('content', 'same-content', lambda: {'source': 'first'}) == {'source': 'first'}
    retained = {p.name: p.read_bytes() for p in (tmp_path / 'content').glob('*.json')}
    version[0] = 'replacement-source-version'
    assert artifacts.prepared('content', 'same-content', lambda: {'source': 'replacement'}) == {'source': 'replacement'}
    assert {p.name: p.read_bytes() for p in (tmp_path / 'content').glob('*.json')} == retained
    version[0] = 'first-source-version'
    assert artifacts.prepared('content', 'same-content', lambda: pytest.fail('valid old version remains readable')) == {'source': 'first'}
