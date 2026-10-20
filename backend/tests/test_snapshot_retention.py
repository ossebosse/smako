import json
import sqlite3
from datetime import UTC, datetime

import pytest

from grocery_data.app.services.snapshot_retention import TOMBSTONE, maintain
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.app.storage.models import CatalogSnapshotModel, CollectorRunModel
from grocery_data.app.storage.repositories import RawSnapshotRepository
from grocery_data.tests.test_storage_core import _product, _raw, _source_product

NOW = datetime(2026, 10, 20, tzinfo=UTC)


@pytest.fixture
def history(tmp_path):
    database = tmp_path / "grocery.sqlite"
    engine = create_database_engine("sqlite:///" + database.as_posix())
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_root = tmp_path / "raw"
    with factory() as session:
        for number in range(1, 9):
            stamp = datetime(2026, 8, number, tzinfo=UTC)
            run = CollectorRunModel(id=f"run-{number}", chain="willys", scope={},
                                    status="completed", connector_version="test",
                                    started_at=stamp, finished_at=stamp, successful=True)
            session.add(run)
            session.flush()
            snapshot = CatalogSnapshotModel(
                id=f"snapshot-{number}", chain="willys", scope_key="lund",
                coverage="full_catalog", state="promoted", is_active=number == 3,
                collector_run_id=run.id, connector_version="test", created_at=stamp,
                previous_active_snapshot_id=f"snapshot-{number-1}" if number in (3, 7, 8) else None)
            session.add(snapshot)
            session.flush()
            raw = _raw(RawSnapshotRepository(session), snapshot_id=snapshot.id,
                       fetched_at=stamp, suffix=str(number))
            source = _source_product(session, snapshot_id=snapshot.id, raw_id=raw.id,
                                     store_id=None, observed_at=stamp, suffix=str(number))
            _product(session, source_product=source, observed_at=stamp)
            path = raw_root / f"raw/willys/{snapshot.id}/{number}.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(f'{{"page":"{number}"}}'.encode())
        session.commit()
    engine.dispose()
    with sqlite3.connect(database) as db:
        # A future subsystem must not lose its evidence through a cascade.
        db.execute("CREATE TABLE future_evidence (product TEXT REFERENCES products(id))")
        db.execute("INSERT INTO future_evidence SELECT id FROM products WHERE catalog_snapshot_id='snapshot-4'")
    universe = tmp_path / "universe"
    (universe / "active").mkdir(parents=True)
    (universe / "active/city-lund.json").write_text(json.dumps({"snapshot_ids": ["snapshot-5"]}))
    operations = tmp_path / "operations"
    operations.mkdir()
    return database, raw_root, {"universe": universe, "operations": operations, "now": NOW}


def test_retire_only_unused_payloads_preserves_lkg_lineage_receipts_and_evidence(history):
    database, raw, kwargs = history
    with sqlite3.connect(database) as db:
        before = db.execute(
            "SELECT id,created_at,is_active,previous_active_snapshot_id FROM catalog_snapshots ORDER BY id").fetchall()
    preview = maintain(database, raw, **kwargs)
    assert preview["retired"] == ["snapshot-1"]
    assert preview["raw_files_removed"] == 1 and preview["reclaimable_bytes"] > 0
    assert (raw / "raw/willys/snapshot-1/1.json").exists()
    result = maintain(database, raw, apply=True, **kwargs)
    assert result["retired"] == ["snapshot-1"]
    with sqlite3.connect(database) as db:
        assert db.execute(
            "SELECT id,created_at,is_active,previous_active_snapshot_id FROM catalog_snapshots ORDER BY id").fetchall() == before
        assert db.execute("SELECT count(*) FROM products").fetchone()[0] == 7
        assert db.execute("SELECT count(*) FROM raw_snapshots").fetchone()[0] == 8
        assert db.execute("SELECT count(*) FROM future_evidence").fetchone()[0] == 1
        assert not db.execute("PRAGMA foreign_key_check").fetchall()
        metadata = json.loads(db.execute(
            "SELECT metrics FROM catalog_snapshots WHERE id='snapshot-1'").fetchone()[0])
        assert metadata[TOMBSTONE] == NOW.isoformat()
    assert not (raw / "raw/willys/snapshot-1").exists()
    assert (raw / "raw/willys/snapshot-3/3.json").exists()
    assert maintain(database, raw, apply=True, **kwargs)["retired"] == []


def test_open_incident_and_running_collector_keep_their_evidence(history):
    database, raw, kwargs = history
    pointer = kwargs["operations"] / "source-incidents.json"
    pointer.write_text(json.dumps({"snapshot_id": "snapshot-1"}))
    assert maintain(database, raw, apply=True, **kwargs)["retired"] == []
    pointer.unlink()
    with sqlite3.connect(database) as db:
        db.execute("UPDATE collector_runs SET finished_at=NULL WHERE id='run-1'")
    assert maintain(database, raw, apply=True, **kwargs)["retired"] == []


def test_invalid_operational_pointer_aborts_before_database_changes(history):
    database, raw, kwargs = history
    (kwargs["operations"] / "unknown.json").write_text("{invalid")
    with pytest.raises(ValueError):
        maintain(database, raw, apply=True, **kwargs)
    with sqlite3.connect(database) as db:
        assert db.execute("SELECT count(*) FROM products").fetchone()[0] == 8


def test_raw_file_changed_after_collection_is_never_deleted(history):
    database, raw, kwargs = history
    path = raw / "raw/willys/snapshot-1/1.json"
    path.write_text("unexpected contents")
    with pytest.raises(ValueError, match="changed"):
        maintain(database, raw, apply=True, **kwargs)
    assert path.exists()


def test_retired_raw_body_is_retried_after_interrupted_cleanup(history, monkeypatch):
    from pathlib import Path

    database, raw, kwargs = history
    original = Path.unlink
    def fail_once(path, *args, **kw):
        if path.name == "1.json":
            raise OSError("controlled deletion failure")
        return original(path, *args, **kw)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", fail_once)
        with pytest.raises(OSError):
            maintain(database, raw, apply=True, **kwargs)
    result = maintain(database, raw, apply=True, **kwargs)
    assert result["retired"] == [] and result["raw_files_removed"] == 1


def test_municipal_copy_compacts_without_changing_its_immutable_source(history, monkeypatch):
    from deploy.scripts.storage_maintenance import sha256
    from grocery_data.app.services.snapshot_retention import compact_candidate_copy

    database, raw, kwargs = history
    before = sha256(database)
    candidate = database.with_name("next-attempt.sqlite")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(candidate) as dst:
        src.backup(dst)
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", str(kwargs["universe"]))
    result = compact_candidate_copy(candidate, raw.parent / "new-empty-raw", now=NOW)
    assert result["retired"] == ["snapshot-1"]
    assert sha256(database) == before
    with sqlite3.connect(candidate) as db:
        assert db.execute("SELECT count(*) FROM products").fetchone()[0] == 7
