import errno
import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from grocery_data import local_relay, relay_storage
from grocery_data.app.services import durable_files, source_artifact
from grocery_data.tests.test_local_relay import forbidden, pending


@pytest.fixture(autouse=True)
def restore_temp(monkeypatch):
    for key in ("TEMP", "TMP", "TMPDIR", "SQLITE_TMPDIR"):
        if key in os.environ:
            monkeypatch.setenv(key, os.environ[key])
        else:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)


def test_actual_parent_and_child_temp_files_use_workspace(tmp_path):
    result = relay_storage.storage_probe(tmp_path)
    assert result["status"] == "PASS"
    for field in ("parent_temp_file", "child_temp_file"):
        path = Path(result[field])
        assert path.parent == tmp_path / "tmp"
        assert not path.exists()
    assert all(os.environ[k] == str(tmp_path / "tmp") for k in ("TEMP", "TMP", "TMPDIR", "SQLITE_TMPDIR"))


def test_unavailable_volume_does_not_create_or_fallback(tmp_path):
    missing = tmp_path / "unmounted" / "workspace"
    with pytest.raises(FileNotFoundError):
        relay_storage.configure_storage(missing)
    assert not missing.parent.exists()


def test_unwritable_temp_does_not_fallback(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise OSError(errno.ENOSPC, "injected write failure")
    monkeypatch.setattr(tempfile, "TemporaryFile", fail)
    with pytest.raises(OSError):
        relay_storage.configure_storage(tmp_path)
    assert tempfile.tempdir == str(tmp_path / "tmp")


def test_capacity_counts_runs_and_queue_but_charges_new_growth(tmp_path, monkeypatch):
    run = tmp_path / "runs" / "one"
    run.mkdir(parents=True)
    (run / "candidate.sqlite3").write_bytes(b"db" * 100)
    (run / "raw.json").write_bytes(b"raw" * 100)
    (tmp_path / "completed").mkdir()
    (tmp_path / "completed" / "pending.smako-source").write_bytes(b"zip")
    report = relay_storage.collection_capacity(tmp_path)
    assert report["largest_run_bytes"] == 500 and report["queue_bytes"] == 3
    assert report["required_bytes"] == 512 * 1024**2
    monkeypatch.setattr(durable_files.shutil, "disk_usage", lambda p: SimpleNamespace(free=1024))
    with pytest.raises(durable_files.InsufficientStorageError):
        relay_storage.collection_capacity(tmp_path)


def test_server_capacity_stop_preserves_queue_and_receipt(tmp_path):
    artifact = pending(tmp_path)
    before = artifact.read_bytes()
    receipt = tmp_path / "last-success.json"
    receipt.write_text(json.dumps({"sha256": "old", "observed_from": "2020-01-01T00:00:00+00:00"}))
    original = receipt.read_bytes()
    def fail():
        raise OSError(errno.ENOSPC, "injected receiver full")
    assert local_relay.run(tmp_path, collect=forbidden, push=forbidden, activate=forbidden, capacity_check=fail) == 1
    assert receipt.read_bytes() == original and artifact.read_bytes() == before


def test_failed_packaging_does_not_publish_partial_or_replace_previous(tmp_path, monkeypatch):
    good = pending(tmp_path)
    original = good.read_bytes()
    verified = source_artifact.verify_source_artifact(good)
    target = good.parent / "new.smako-source"
    def fail(*args, **kwargs):
        raise OSError(errno.ENOSPC, "injected full disk during archive write")
    monkeypatch.setattr(source_artifact.zipfile.ZipFile, "writestr", fail)
    with pytest.raises(OSError):
        source_artifact.write_source_artifact(verified.manifest, verified.documents, target)
    assert not target.exists() and good.read_bytes() == original
    assert list(good.parent.glob(".*.smako-source")) == []


def test_receiver_capacity_checks_actual_paths_without_server_writes(tmp_path, monkeypatch):
    raw = tmp_path / "raw"; raw.mkdir()
    inbox = raw / "inbox"; inbox.mkdir()
    prices = tmp_path / "prices"; prices.mkdir()
    db = tmp_path / "source.sqlite"; db.write_bytes(b"x" * 100)
    monkeypatch.setenv("GROCERY_RAW_SNAPSHOT_ROOT", str(raw))
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", str(prices))
    monkeypatch.setenv("GROCERY_DATABASE_URL", "sqlite:///" + str(db))
    # Windows has no getuid; only the actual Linux receiver uses this field.
    source = relay_storage.RECEIVER_CAPACITY_SCRIPT.replace("os.getuid()", "10001")
    args = json.dumps({"inbox": str(inbox), "artifact_bytes": 10, "run_bytes": 100})
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    result = json.loads(subprocess.check_output([os.sys.executable, "-c", source, args], text=True))
    assert result["status"] == "PASS"
    assert sum(v["required_bytes"] for v in result["volumes"]) == 310
    assert before == sorted(str(p) for p in tmp_path.rglob("*"))
