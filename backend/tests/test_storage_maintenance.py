"""Retention must release space without invalidating recovery or active prices."""
import hashlib
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from deploy.scripts import storage_maintenance as maintenance

NOW = datetime(2026, 10, 20, tzinfo=UTC)


def old(path, days=20):
    stamp = (NOW - timedelta(days=days)).timestamp()
    for item in [*path.rglob("*"), path] if path.is_dir() else [path]:
        os.utime(item, (stamp, stamp))


def bundle(root, number):
    path = root / f"202610{number:02d}T000000Z"
    path.mkdir(parents=True)
    content = b"closed immutable recovery payload"
    (path / "database").write_bytes(content)
    (path / "manifest.json").write_text(json.dumps({
        "schema_version": "grocery-beta-backup-v1",
        "files": [{"path": "database", "bytes": len(content),
                   "sha256": hashlib.sha256(content).hexdigest()}],
    }))
    return path


def artifact(root, content, *, active=False, city="lund"):
    digest = hashlib.sha256(content).hexdigest()
    path = root / "artifacts" / (digest + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    old(path)
    if active:
        pointer = root / "active" / f"city-{city}.json"
        pointer.parent.mkdir(exist_ok=True)
        pointer.write_text(json.dumps({
            "artifact_file": f"artifacts/{path.name}", "artifact_sha256": digest,
            "artifact_bytes": len(content),
        }))
    return path


def test_count_rotation_dry_run_then_apply_keeps_recovery_and_unknowns(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_MAX_COUNT", "3")
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "365")
    paths = [bundle(tmp_path, i) for i in range(1, 6)]
    unknown = tmp_path / "manual-release"
    unknown.mkdir()
    (unknown / "private").write_text("keep")
    privacy = tmp_path / "privacy-ledgers"
    privacy.mkdir()
    before = maintenance.maintain_backups(tmp_path, now=NOW)
    assert before["removed"] == [paths[1].name, paths[0].name]
    assert all(p.exists() for p in paths)
    after = maintenance.maintain_backups(tmp_path, now=NOW, apply=True)
    assert before["reclaimable_bytes"] == after["reclaimable_bytes"] > 0
    assert all(p.exists() for p in paths[2:])
    assert not any(p.exists() for p in paths[:2])
    assert unknown.exists() and privacy.exists()
    assert maintenance.maintain_backups(tmp_path, now=NOW, apply=True)["removed"] == []


def test_byte_and_age_limits_never_delete_last_two_verified_backups(tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUP_MAX_BYTES", "1")
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "1")
    paths = [bundle(tmp_path, i) for i in range(1, 5)]
    result = maintenance.maintain_backups(tmp_path, now=NOW, apply=True)
    assert result["minimum_exceeds_budget"]
    assert [p.exists() for p in paths] == [False, False, True, True]


def test_corrupt_recovery_floor_prevents_rotation(tmp_path):
    paths = [bundle(tmp_path, i) for i in range(1, 5)]
    (paths[-1] / "database").write_bytes(b"x" * (paths[-1] / "database").stat().st_size)
    with pytest.raises(ValueError, match="checksum"):
        maintenance.maintain_backups(tmp_path, now=NOW, apply=True)
    assert all(p.exists() for p in paths)


def test_incomplete_and_unknown_bundles_never_count_as_recovery(tmp_path):
    only = bundle(tmp_path, 1)
    bad = bundle(tmp_path, 3)
    (bad / "database").unlink()
    result = maintenance.maintain_backups(tmp_path, now=NOW, apply=True)
    assert result["unknown"] == [bad.name]
    assert result["protected"] == [only.name] and only.exists() and bad.exists()


def test_abandoned_backup_staging_reclaimed_but_recent_staging_kept(tmp_path):
    stale = tmp_path / (".20261001T000000Z." + "a" * 32 + ".tmp")
    stale.mkdir()
    (stale / "partial").write_bytes(b"partial backup")
    old(stale)
    recent = tmp_path / (".20261020T000000Z." + "b" * 32 + ".tmp")
    recent.mkdir()
    result = maintenance.maintain_backups(tmp_path, now=NOW, apply=True)
    assert result["removed"] == [stale.name] and recent.exists()


def test_all_active_cities_and_reader_grace_survive_blob_retention(tmp_path):
    lund = artifact(tmp_path, b"lund", active=True)
    malmo = artifact(tmp_path, b"malmo", active=True, city="malmo")
    retired = artifact(tmp_path, b"retired")
    recent = artifact(tmp_path, b"in-flight reader")
    stamp = (NOW - timedelta(hours=1)).timestamp()
    os.utime(recent, (stamp, stamp))
    unknown = tmp_path / "artifacts" / "operator-evidence.json"
    unknown.write_text("keep")
    result = maintenance.maintain_artifacts(tmp_path, now=NOW, apply=True)
    assert result["removed"] == [retired.name]
    assert all(p.exists() for p in [lund, malmo, recent, unknown])


def test_missing_or_invalid_manifest_never_permits_blob_sweep(tmp_path):
    retired = artifact(tmp_path, b"keep without authority")
    assert maintenance.maintain_artifacts(tmp_path, now=NOW, apply=True)["status"] == "no_active_manifest"
    current = artifact(tmp_path, b"current", active=True)
    current.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="verification"):
        maintenance.maintain_artifacts(tmp_path, now=NOW, apply=True)
    assert retired.exists()


def test_links_and_changed_candidates_are_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = root / ("a" * 64 + ".json")
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    with pytest.raises(ValueError, match="link"):
        maintenance.inventory(linked)
    with pytest.raises(ValueError, match="link"):
        maintenance.safe_root(linked)
    file = root / "owned"
    file.write_text("before")
    tree = maintenance.inventory(file)[0]
    file.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        maintenance.remove_owned(root, file, tree, apply=True)
    assert outside.exists() and file.exists()


def test_staging_only_removes_exact_managed_namespace(tmp_path):
    root = tmp_path / "refresh-candidates"
    stale = root / ".price-universe-source-435s_s25"
    stale.mkdir(parents=True)
    (stale / "source.sqlite3").write_bytes(b"abandoned build copy")
    old(stale)
    unknown = root / "approved-candidate"
    unknown.mkdir()
    old(unknown)
    result = maintenance.maintain_build_staging(tmp_path, now=NOW, apply=True)
    assert result["removed"] == [stale.name]
    assert unknown.exists()


def test_backup_rotates_before_space_preflight_even_when_next_copy_fails(tmp_path, monkeypatch):
    from backend.tests.test_production_deployment import _configure_backup
    from deploy.scripts import backup_sqlite

    paths = _configure_backup(monkeypatch, tmp_path)
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "365")
    backups = [bundle(paths["backups"], i) for i in range(1, 5)]
    def full(*args):
        assert not backups[0].exists()
        raise OSError("controlled no space")
    monkeypatch.setattr(backup_sqlite, "_preflight_backup_space", full)
    with pytest.raises(OSError, match="controlled"):
        backup_sqlite.create_backup(now=NOW)
    assert all(p.exists() for p in backups[1:])


def test_busy_lease_blocks_standalone_maintenance(tmp_path, monkeypatch):
    import sys

    from backend.tests.test_production_deployment import _configure_backup
    from grocery_data.app.services.manual_refresh_operations import (
        RefreshAlreadyRunningError,
        RefreshRunLock,
        production_refresh_lock_path,
    )
    paths = _configure_backup(monkeypatch, tmp_path)
    monkeypatch.setattr(sys, "argv", ["storage_maintenance", "--apply"])
    lock = RefreshRunLock(production_refresh_lock_path(paths["grocery"], paths["universe"]))
    lock.acquire()
    try:
        with pytest.raises(RefreshAlreadyRunningError):
            maintenance.main()
    finally:
        lock.release()
