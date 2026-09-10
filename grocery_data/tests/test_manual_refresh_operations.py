from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from grocery_data.app.services.manual_refresh_operations import (
    RefreshAlreadyRunningError,
    RefreshLockError,
    RefreshRunLock,
    credential_safe_report,
    process_identity,
    process_is_alive,
    production_refresh_lock_path,
    refresh_lock_owned_by_process,
    render_daily_refresh_report,
    render_refresh_status,
    write_refresh_report,
)

NOW = datetime(2026, 8, 29, 8, 30, tzinfo=UTC)


def test_production_lock_path_is_stable_across_cwd_and_path_aliases(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    state = tmp_path / "state"
    state.mkdir()
    database = state / "prices.sqlite"
    database.write_bytes(b"sqlite-placeholder")
    universe_root = tmp_path / "cache" / "price-universes"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()

    monkeypatch.chdir(tmp_path)
    first = production_refresh_lock_path(
        state / "." / "prices.sqlite",
        tmp_path / "cache" / "nested" / ".." / "price-universes",
    )
    monkeypatch.chdir(elsewhere)
    second = production_refresh_lock_path(database, universe_root)

    assert first == second
    assert first.parent == universe_root.resolve() / ".refresh-locks"
    assert first.name.startswith("daily-refresh-")
    assert first.suffix == ".lock"
    assert str(database) not in first.name


def test_production_lock_identity_changes_with_database_or_universe_root(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first_database = tmp_path / "first.sqlite"
    second_database = tmp_path / "second.sqlite"
    first_database.write_bytes(b"first")
    second_database.write_bytes(b"second")
    first_root = tmp_path / "first-universe"
    second_root = tmp_path / "second-universe"

    baseline = production_refresh_lock_path(first_database, first_root)

    assert production_refresh_lock_path(second_database, first_root) != baseline
    assert production_refresh_lock_path(first_database, second_root) != baseline


def test_production_lock_path_drives_one_shared_cross_process_lock(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "prices.sqlite"
    database.write_bytes(b"sqlite-placeholder")
    path = production_refresh_lock_path(database, tmp_path / "universe")
    owner = RefreshRunLock(path, pid=111, clock=lambda: NOW, pid_is_alive=lambda _pid: True)
    contender = RefreshRunLock(
        production_refresh_lock_path(database, tmp_path / "universe"),
        pid=222,
        clock=lambda: NOW,
        pid_is_alive=lambda pid: pid == 111,
    )

    owner.acquire()
    try:
        with pytest.raises(RefreshAlreadyRunningError, match="already held"):
            contender.acquire()
    finally:
        owner.release()


def test_production_lock_path_requires_existing_regular_database(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(FileNotFoundError):
        production_refresh_lock_path(tmp_path / "missing.sqlite", tmp_path / "universe")

    database_directory = tmp_path / "database-directory"
    database_directory.mkdir()
    with pytest.raises(ValueError, match="regular file"):
        production_refresh_lock_path(database_directory, tmp_path / "universe")


def test_production_lock_path_can_scope_an_exact_missing_restore_target(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database = tmp_path / "scratch" / "grocery" / "prices.sqlite"
    universe = tmp_path / "scratch" / "price-universes"

    before_restore = production_refresh_lock_path(
        database,
        universe,
        allow_missing_database=True,
    )
    database.parent.mkdir(parents=True)
    database.write_bytes(b"sqlite-placeholder")
    after_restore = production_refresh_lock_path(database, universe)

    assert before_restore == after_restore
    assert before_restore.parent == universe.resolve() / ".refresh-locks"


def test_lock_context_persists_diagnostic_file_and_releases_kernel_lease(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "refresh.lock"
    lock = RefreshRunLock(path, pid=1234, clock=lambda: NOW, pid_is_alive=lambda _pid: True)

    with lock:
        assert lock.acquired is True

    assert lock.acquired is False
    assert path.exists()
    payload = json.loads(path.read_bytes()[1:])
    assert payload["schema_version"] == "manual-refresh-lock-v2"
    assert payload["pid"] == 1234
    assert payload["acquired_at"] == "2026-08-29T08:30:00Z"
    assert payload["owner_nonce"]

    successor = RefreshRunLock(path, pid=5678, clock=lambda: NOW)
    successor.acquire()
    successor.release()


def test_live_pid_lock_is_denied_even_when_old(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "refresh.lock"
    identity = lambda _pid: "boot-a:start-111"
    owner = RefreshRunLock(
        path,
        pid=111,
        clock=lambda: NOW,
        pid_is_alive=lambda _pid: True,
        pid_identity=identity,
    )
    owner.acquire()
    contender = RefreshRunLock(
        path,
        pid=222,
        clock=lambda: NOW + timedelta(days=2),
        stale_after=timedelta(hours=1),
        pid_is_alive=lambda pid: pid == 111,
        pid_identity=identity,
    )

    with pytest.raises(RefreshAlreadyRunningError, match="already held"):
        contender.acquire()

    owner.release()


def test_reused_live_pid_from_previous_process_identity_is_reclaimed(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "refresh.lock"
    owner = RefreshRunLock(
        path,
        pid=1,
        clock=lambda: NOW,
        pid_is_alive=lambda _pid: True,
        pid_identity=lambda _pid: "boot-a:start-old-container",
    )
    owner.acquire()
    owner.release()  # Kernel releases the lease when the old container exits.

    successor = RefreshRunLock(
        path,
        pid=1,
        clock=lambda: NOW + timedelta(minutes=1),
        pid_is_alive=lambda _pid: True,
        pid_identity=lambda _pid: "boot-a:start-new-container",
    )
    replacement = successor.acquire()

    assert replacement.pid == 1
    assert replacement.process_identity == "boot-a:start-new-container"
    assert path.exists()
    successor.release()


def test_identityless_kernel_lock_never_expires_while_owner_is_active(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "refresh.lock"
    owner = RefreshRunLock(
        path,
        pid=1,
        clock=lambda: NOW,
        pid_is_alive=lambda _pid: True,
        pid_identity=lambda _pid: None,
    )
    owner.acquire()

    within_refresh_bound = RefreshRunLock(
        path,
        pid=2,
        clock=lambda: NOW + timedelta(hours=2, minutes=1),
        pid_is_alive=lambda _pid: True,
        pid_identity=lambda _pid: None,
    )
    with pytest.raises(RefreshAlreadyRunningError, match="already held"):
        within_refresh_bound.acquire()

    much_later = RefreshRunLock(
        path,
        pid=2,
        clock=lambda: NOW + timedelta(hours=6, seconds=1),
        pid_is_alive=lambda _pid: True,
        pid_identity=lambda _pid: None,
    )
    with pytest.raises(RefreshAlreadyRunningError, match="already held"):
        much_later.acquire()

    owner.release()
    much_later.acquire()
    much_later.release()


def test_dead_pid_lock_is_reclaimed_immediately(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "refresh.lock"
    abandoned = RefreshRunLock(path, pid=111, clock=lambda: NOW, pid_is_alive=lambda _pid: False)
    abandoned.acquire()
    abandoned.release()  # A crashed process releases its OS lock automatically.
    successor = RefreshRunLock(
        path,
        pid=222,
        clock=lambda: NOW + timedelta(seconds=1),
        pid_is_alive=lambda _pid: False,
    )

    info = successor.acquire()

    assert info.pid == 222
    successor.release()
    assert json.loads(path.read_bytes()[1:])["pid"] == 222
    assert path.exists()


def test_unlocked_malformed_metadata_does_not_block_recovery(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "refresh.lock"
    path.write_bytes(b"\0partial")
    recent = RefreshRunLock(
        path,
        pid=222,
        clock=lambda: datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        stale_after=timedelta(hours=1),
        pid_is_alive=lambda _pid: False,
    )
    recent.acquire()
    recent.release()
    assert json.loads(path.read_bytes()[1:])["pid"] == 222


def test_same_lock_object_cannot_acquire_twice(tmp_path) -> None:  # type: ignore[no-untyped-def]
    lock = RefreshRunLock(
        tmp_path / "refresh.lock",
        pid=123,
        clock=lambda: NOW,
        pid_is_alive=lambda _pid: True,
    )
    lock.acquire()
    with pytest.raises(RefreshLockError, match="already acquired"):
        lock.acquire()
    lock.release()


def test_current_process_is_alive_and_invalid_pids_are_not() -> None:
    assert process_is_alive(os.getpid()) is True
    assert process_is_alive(0) is False
    assert process_is_alive(-1) is False


def test_current_process_identity_is_boot_and_start_scoped_when_supported() -> None:
    identity = process_identity(os.getpid())

    if os.name == "nt" or os.path.isdir("/proc"):
        assert isinstance(identity, str)
        assert identity.startswith(("windows:", "linux:"))
        assert len(identity) > 20
    else:
        assert identity is None


def test_parent_lock_handoff_requires_exact_live_pid_and_nonce(tmp_path) -> None:  # type: ignore[no-untyped-def]
    lock = RefreshRunLock(tmp_path / "refresh.lock")
    info = lock.acquire()
    try:
        assert refresh_lock_owned_by_process(
            lock.path,
            nonce=info.owner_nonce,
            pid=os.getpid(),
        )
        assert not refresh_lock_owned_by_process(
            lock.path,
            nonce="wrong",
            pid=os.getpid(),
        )
        assert not refresh_lock_owned_by_process(
            lock.path,
            nonce=info.owner_nonce,
            pid=os.getpid() + 1,
        )
    finally:
        lock.release()
    assert not refresh_lock_owned_by_process(
        lock.path,
        nonce=info.owner_nonce,
        pid=os.getpid(),
    )


def test_credential_safe_report_removes_sensitive_values_and_unknown_objects() -> None:
    safe = credential_safe_report(
        {
            "status": "failed: Authorization=Bearer abc.secret",
            "headers": {"X": "private"},
            "nested": {"csrfToken": "csrf-value", "count": 2},
            "exception": RuntimeError("password=hunter2"),
            "path": __file__,
            "opaque": object(),
        }
    )
    encoded = json.dumps(safe)
    assert "abc.secret" not in encoded
    assert "private" not in encoded
    assert "csrf-value" not in encoded
    assert "hunter2" not in encoded
    assert safe["headers"] == "[REDACTED]"
    assert safe["nested"]["csrfToken"] == "[REDACTED]"
    assert safe["exception"] == {"error_type": "RuntimeError"}
    assert safe["opaque"] == {"value_type": "object"}


def test_report_writer_is_atomic_timestamped_and_credential_safe(tmp_path) -> None:  # type: ignore[no-untyped-def]
    report_dir = tmp_path / "reports"
    destination = write_refresh_report(
        {
            "run_type": "daily_refresh",
            "status": "fresh",
            "api_key": "never-write-me",
            "detail": "Bearer also-never-write-me",
        },
        report_dir,
        now=NOW,
    )

    assert destination.parent == report_dir.resolve()
    assert destination.name.startswith("daily-refresh-20260829T083000.000000Z-")
    assert destination.suffix == ".json"
    assert not list(report_dir.glob("*.tmp"))
    content = destination.read_text(encoding="utf-8")
    assert "never-write-me" not in content
    assert json.loads(content)["api_key"] == "[REDACTED]"


def test_report_writer_never_overwrites_same_timestamp(tmp_path) -> None:  # type: ignore[no-untyped-def]
    first = write_refresh_report({"status": "fresh"}, tmp_path, now=NOW)
    second = write_refresh_report({"status": "fresh"}, tmp_path, now=NOW)
    assert first != second
    assert first.exists() and second.exists()


def test_report_writer_rejects_unsafe_prefix(tmp_path) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError, match="safe lowercase"):
        write_refresh_report({}, tmp_path, prefix="../escape", now=NOW)


def test_daily_refresh_renderer_handles_cli_envelope() -> None:
    rendered = render_daily_refresh_report(
        {
            "reports": [
                {
                    "city": "Lund",
                    "items": [
                        {
                            "chain": "hemkop",
                            "context_name": "Karhögstorg",
                            "status": "fresh",
                            "products": 6100,
                            "age_hours": 1.25,
                            "lkg_used": False,
                        }
                    ],
                    "universe": {
                        "status": "active",
                        "universe_id": "price-universe:test",
                    },
                    "summary": {"fresh": 1, "broken": 0, "promoted": 1},
                }
            ]
        }
    )
    assert "LUND DAILY REFRESH" in rendered
    assert "Karhögstorg" in rendered
    assert "6100" in rendered
    assert "PriceUniverse: active" in rendered
    assert "fresh=1" in rendered


def test_status_renderer_shows_chain_freshness() -> None:
    rendered = render_refresh_status(
        {
            "city": "Lund",
            "status": "aging",
            "basket_capable": 7,
            "oldest_basket_price_age_hours": 37.5,
            "chains": {
                "hemkop": {
                    "fresh_full_basket_contexts": 1,
                    "aging_full_basket_contexts": 1,
                    "stale_or_broken": 0,
                }
            },
        }
    )
    assert "LUND REFRESH STATUS: AGING" in rendered
    assert "Basket contexts: 7" in rendered
    assert "HEMKOP" in rendered
    assert "aging=1" in rendered
