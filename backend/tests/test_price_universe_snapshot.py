"""A price universe from its binary snapshot is the one from its JSON artifact."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from app.services import price_universe_snapshot as snapshots
from app.services.price_universe_runtime import PreparedPriceUniverseManager

from backend.tests.test_price_universe_runtime import POSTAL_CODE, _build_prepared


def _artifact(prepared, folder: Path) -> Path:
    draft = folder / "draft.json"
    PreparedPriceUniverseManager.write_artifact(prepared, draft)
    named = folder / f"{hashlib.sha256(draft.read_bytes()).hexdigest()}.json"
    draft.rename(named)  # content-addressed, as the artifact store names them
    return named


@pytest.mark.asyncio
async def test_snapshot_load_equals_json_load_with_empty_caches(tmp_path, monkeypatch):
    _, prepared, _, _ = await _build_prepared()
    artifact = _artifact(prepared, tmp_path)
    monkeypatch.setenv("SMAKO_PREPARED_SNAPSHOT_ROOT", str(tmp_path / "snapshots"))

    first = PreparedPriceUniverseManager()
    from_json = first.load_file_and_activate(artifact)
    written = list((tmp_path / "snapshots").glob("*.pickle"))
    assert len(written) == 1 and written[0] in first.loaded_snapshots
    from_json.package_cache._cache.get_or_compute("warm", lambda: 1)  # must not travel

    second = PreparedPriceUniverseManager()
    from_snapshot = second.load_file_and_activate(artifact)
    assert from_snapshot is not from_json
    assert from_snapshot.universe == from_json.universe
    assert from_snapshot.economic_pool == from_json.economic_pool
    assert from_snapshot.stores == from_json.stores
    assert from_snapshot._context_oldest_observed_at == from_json._context_oldest_observed_at
    assert from_snapshot._base_context_ids == from_json._base_context_ids
    index, original = from_snapshot.product_search_index, from_json.product_search_index
    assert index.prepared is from_snapshot
    assert dict(index.postings) == dict(original.postings) and dict(index.groups) == dict(original.groups)
    assert from_snapshot.universe.indexes.positions("canonical", next(iter(
        from_json.universe.indexes._lookups["canonical"]))) is not None
    assert from_snapshot.package_cache.stats.entries == 0
    assert second.get_for_request(POSTAL_CODE, {}) is from_snapshot


@pytest.mark.asyncio
async def test_another_code_version_or_a_damaged_snapshot_loads_the_json(tmp_path, monkeypatch):
    _, prepared, _, _ = await _build_prepared()
    artifact = _artifact(prepared, tmp_path)
    monkeypatch.setenv("SMAKO_PREPARED_SNAPSHOT_ROOT", str(tmp_path / "snapshots"))
    PreparedPriceUniverseManager().load_file_and_activate(artifact)
    path = next((tmp_path / "snapshots").glob("*.pickle"))

    data = bytearray(path.read_bytes())
    data[-10] ^= 0xFF
    path.write_bytes(bytes(data))
    assert snapshots.read(path, source_sha256=artifact.stem) is None  # digest rejects it
    again = PreparedPriceUniverseManager()
    assert again.load_file_and_activate(artifact).universe == prepared.universe  # JSON, then rewritten
    assert snapshots.read(path, source_sha256=artifact.stem) is not None

    monkeypatch.setattr(snapshots, "_fingerprint", "another-code-version")
    assert snapshots.read(path, source_sha256=artifact.stem) is None
    assert snapshots.read(path, source_sha256="0" * 64) is None


@pytest.mark.asyncio
async def test_without_a_snapshot_folder_nothing_is_written(tmp_path, monkeypatch):
    _, prepared, _, _ = await _build_prepared()
    artifact = _artifact(prepared, tmp_path)
    monkeypatch.delenv("SMAKO_PREPARED_SNAPSHOT_ROOT", raising=False)
    manager = PreparedPriceUniverseManager()
    manager.load_file_and_activate(artifact)
    assert not manager.loaded_snapshots and not list(tmp_path.rglob("*.pickle"))


def test_facts_come_from_their_snapshot_until_the_sources_change(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from app.services import personal_source_facts as module

    monkeypatch.setenv("SMAKO_PREPARED_SNAPSHOT_ROOT", str(tmp_path))
    loads = []
    monkeypatch.setattr(module, "load_retained_facts", lambda prepared: loads.append(1) or {"k": ("fact", 1)})
    stamp = [("raw", 1, 2)]
    monkeypatch.setattr(module, "_source_fingerprint", lambda: tuple(stamp))
    prepared = SimpleNamespace(universe=SimpleNamespace(products_digest="a" * 64))

    assert module._facts_from_snapshot_or_sources(prepared) == {"k": ("fact", 1)} and loads == [1]
    assert module._facts_from_snapshot_or_sources(prepared) == {"k": ("fact", 1)} and loads == [1]
    stamp[0] = ("raw", 2, 2)  # a source folder changed: loaded again
    module._facts_from_snapshot_or_sources(prepared)
    assert loads == [1, 1] and len(list(tmp_path.glob("facts-*.pickle"))) == 2
    other = SimpleNamespace(universe=SimpleNamespace(products_digest="b" * 64))
    module._facts_from_snapshot_or_sources(other)
    assert loads == [1, 1, 1]
