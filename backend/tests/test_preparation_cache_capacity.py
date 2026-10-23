"""A full disk cache must not rescan every retained artifact per missed recipe."""
from pathlib import Path

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
