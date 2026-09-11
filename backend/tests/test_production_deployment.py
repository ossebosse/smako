from __future__ import annotations

import errno
import hashlib
import json
import os
import sqlite3
import stat
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import deploy.scripts.backup_sqlite as backup_module
import deploy.scripts.run_daily_refresh as refresh_runner
import deploy.scripts.run_source_retry as source_retry_runner
from deploy.scripts.backup_sqlite import _chmod_private, create_backup
from deploy.scripts.privacy_erasure_ledger import export_deletion_ledger
from deploy.scripts.production_smoke import _safe_origin, _validate_plan
from deploy.scripts.restore_sqlite import restore
from deploy.scripts.run_daily_refresh import build_refresh_command
from deploy.scripts.seed_runtime import seed_runtime
from deploy.scripts.start_cron import _schedule
from grocery_data.app.services import durable_files
from grocery_data.app.services.durable_files import (
    InsufficientStorageError,
    StoragePreflight,
)
from grocery_data.app.services.manual_refresh_operations import (
    RefreshAlreadyRunningError,
    RefreshRunLock,
    production_refresh_lock_path,
)

ROOT = Path(__file__).resolve().parents[2]


def _assert_private_tree(root: Path) -> None:
    if os.name == "nt":
        return
    for path in (root, *root.rglob("*")):
        expected = 0o700 if path.is_dir() else 0o600
        assert stat.S_IMODE(path.stat().st_mode) == expected, path


def _database(path: Path, value: str) -> None:
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("CREATE TABLE evidence (value TEXT NOT NULL)")
        connection.execute("INSERT INTO evidence VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def _active_artifact(root: Path, *, marker: str) -> None:
    payload = json.dumps({"marker": marker}).encode()
    digest = hashlib.sha256(payload).hexdigest()
    artifact = root / "artifacts" / f"{digest}.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(payload)
    manifest = {
        "artifact_file": f"artifacts/{digest}.json",
        "artifact_sha256": digest,
        "artifact_bytes": len(payload),
        "universe_id": f"price-universe:{marker}",
        "snapshot_ids": [f"snapshot-{marker}"],
        "oldest_observed_at": "2026-08-30T10:16:31.972452Z",
        "built_at": "2026-09-01T09:37:33.103109Z",
        "activated_at": "2026-09-01T09:41:31.514583Z",
    }
    active = root / "active/city-lund.json"
    active.parent.mkdir(parents=True, exist_ok=True)
    active.write_text(json.dumps(manifest), encoding="utf-8")


def _configure_backup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Path]:
    grocery = tmp_path / "runtime/grocery/grocery_data.sqlite"
    plans = tmp_path / "runtime/plans/consumer_plans.sqlite3"
    universe = tmp_path / "runtime/price_universes"
    backups = tmp_path / "runtime/backups"
    grocery.parent.mkdir(parents=True)
    plans.parent.mkdir(parents=True)
    _database(grocery, "grocery-before")
    connection = sqlite3.connect(grocery)
    try:
        connection.execute(
            """
            CREATE TABLE privacy_erasure_suppressions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_record_id TEXT NOT NULL,
                action TEXT NOT NULL,
                UNIQUE (target_kind, target_record_id)
            )
            """
        )
        connection.commit()
    finally:
        connection.close()
    _database(plans, "plan-before")
    _active_artifact(universe, marker="universe-before")
    _active_artifact(universe / "external-provider-cache", marker="external-before")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{grocery.as_posix()}",
    )
    monkeypatch.setenv("PLAN_STORE_PATH", str(plans))
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", str(universe))
    monkeypatch.setenv("PRICE_UNIVERSE_CITY", "Lund")
    monkeypatch.setenv("BACKUP_ROOT", str(backups))
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "14")
    monkeypatch.setenv("BACKUP_FREE_SPACE_RESERVE_BYTES", "0")
    return {
        "grocery": grocery,
        "plans": plans,
        "universe": universe,
        "backups": backups,
    }


def test_production_compose_has_tls_readiness_and_durable_mounts() -> None:
    compose = (ROOT / "deploy/compose.yaml").read_text(encoding="utf-8")
    caddy = (ROOT / "deploy/Caddyfile").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")

    assert "http://127.0.0.1:8000/ready" in compose
    assert "80:80" in compose and "443:443" in compose
    assert "${RUNTIME_ROOT:-./runtime}/grocery:/srv/app/var/grocery" in compose
    assert "${RUNTIME_ROOT:-./runtime}/plans:/srv/app/var/plans" in compose
    assert ("${RUNTIME_ROOT:-./runtime}/price_universes:/srv/app/var/price_universes") in compose
    assert "${RUNTIME_ROOT:-./runtime}/raw_snapshots:/srv/app/var/raw_snapshots" in compose
    assert compose.count("${RUNTIME_ROOT:-./runtime}/") == 11
    app_section = compose.split("  app:\n", 1)[1].split("  scheduler:\n", 1)[0]
    assert "raw_snapshots:/srv/app/var/raw_snapshots:ro" in app_section
    assert "deploy/scripts/start_cron.py" in compose
    assert "response_header_timeout 60s" in caddy
    assert "max_size 2MB" in caddy
    assert 'Permissions-Policy "camera=(self)' in caddy
    assert "Content-Security-Policy" in caddy
    assert "frame-ancestors 'none'" in caddy
    assert 'X-Frame-Options "DENY"' in caddy
    assert "script-src 'self'" in caddy
    assert "log {" not in caddy
    assert "--no-access-log" in compose
    assert "--no-access-log" in dockerfile
    assert "PLANNER_MAX_CONCURRENT_REQUESTS: ${PLANNER_MAX_CONCURRENT_REQUESTS:-1}" in compose
    assert "PLANNER_MAX_QUEUED_REQUESTS: ${PLANNER_MAX_QUEUED_REQUESTS:-4}" in compose
    assert "x-json-logging: &json-logging" in compose
    assert 'max-size: "10m"' in compose
    assert 'max-file: "5"' in compose
    assert compose.count("logging: *json-logging") == 6
    scheduler = compose.split("  scheduler:", maxsplit=1)[1].split("  caddy:", maxsplit=1)[0]
    assert "migrate:" in scheduler
    assert "condition: service_completed_successfully" in scheduler
    assert "      app:\n" not in scheduler
    assert "caddy:2.10.2-alpine@sha256:" in compose
    assert "python:3.12.13-slim-bookworm@sha256:" in dockerfile
    assert "backend /srv/app/backend" in dockerfile
    assert "COPY . " not in dockerfile
    assert ".env\n" in dockerignore
    assert ".env.*\n" in dockerignore
    assert "deploy/.env.production*\n" in dockerignore
    assert "deploy/runtime/\n" in dockerignore
    assert "backups/\n" in dockerignore
    assert "raw_snapshots/\n" in dockerignore


def test_production_environment_template_has_no_committed_secret() -> None:
    template = (ROOT / "deploy/.env.production.example").read_text(encoding="utf-8")
    assert "PUBLIC_BASE_URL=https://beta.example.se" in template
    assert "PRICE_UNIVERSE_REQUIRED=true" in template
    assert "SECRET_KEY=replace-with-at-least-32-random-bytes" in template
    assert "BETA_ADMIN_TOKEN=replace-with-a-different-32-byte-value" in template
    assert "PRIMAT_API_KEY=\n" in template
    assert "PLANNER_MAX_CONCURRENT_REQUESTS=1" in template
    assert "PLANNER_MAX_QUEUED_REQUESTS=4" in template
    assert "RUNTIME_ROOT=./runtime" in template
    assert "password" not in template.casefold()


def test_production_smoke_requires_clean_https_origin_and_audited_plan() -> None:
    assert _safe_origin("https://beta.example.se/") == "https://beta.example.se"
    with pytest.raises(ValueError, match="HTTPS"):
        _safe_origin("http://beta.example.se")
    with pytest.raises(ValueError, match="credentials"):
        _safe_origin("https://user:secret@beta.example.se")

    facts = _validate_plan(
        {
            "plan_id": "plan-1",
            "plan": {
                "recipes": [
                    {
                        "title": f"Recipe {index}",
                        "ingredients": [{"name": "potatis"}],
                        "instructions": ["Tillaga."],
                    }
                    for index in range(5)
                ],
                "optimized_basket": {
                    "total": 273.11,
                    "stores": [
                        {
                            "store_id": "own:coop:730400",
                            "items": [
                                {
                                    "product_name": "Potatis 1 kg",
                                    "price_context_type": "online_fulfillment",
                                    "store_name": "Coop Online Syd",
                                }
                            ],
                        }
                    ],
                },
                "quality": {"basket_audit": {"status": "PASS"}},
                "data": {
                    "price_universe_id": "price-universe:verified",
                    "status": "fresh",
                    "live_chain_requests": 0,
                },
            },
        },
        max_stores=2,
    )
    assert facts == {
        "plan_id": "plan-1",
        "price_universe_id": "price-universe:verified",
        "recipes": 5,
        "recipe_details_checked": 5,
        "stores": 1,
        "shopping_groups_checked": 1,
        "shopping_lines_checked": 1,
        "total_sek": 273.11,
        "online_price_items": 1,
    }


def test_beta_go_runbooks_keep_external_acceptance_and_restore_truthful() -> None:
    checklist = (ROOT / "docs/beta-go-checklist.md").read_text(encoding="utf-8")
    backup = (ROOT / "docs/production-backup-restore.md").read_text(encoding="utf-8")
    deployment = (ROOT / "docs/public-beta-deployment.md").read_text(encoding="utf-8")

    assert "deploy/scripts/production_smoke.py" in checklist
    assert "desktop fake-camera" in checklist
    assert "publicly deployed" in checklist
    assert "semantic_and_file_hash" in backup
    assert "a restore must make old data appear\nold, never fresh" in backup
    assert "raw_snapshots/" in backup and "reports/" in backup
    assert "beta-go-checklist.md" in deployment


def test_managed_refresh_entrypoint_uses_full_city_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("REFRESH_CITY", "Lund")
    monkeypatch.setenv("REFRESH_POSTAL_CODE", "22350")
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", "/var/price-universes")
    command = build_refresh_command()
    assert command[1:4] == ["-m", "grocery_data", "daily-refresh"]
    assert command[command.index("--city") + 1] == "Lund"
    assert command[command.index("--postal-code") + 1] == "Lund=22350"
    assert "--chain" not in command
    assert "--context-store-id" not in command
    assert "--no-external-refresh" not in command


def test_production_refresh_has_bounded_timeout() -> None:
    compose = (ROOT / "deploy/compose.yaml").read_text(encoding="utf-8")
    template = (ROOT / "deploy/.env.production.example").read_text(encoding="utf-8")

    assert "REFRESH_TIMEOUT_SECONDS: ${REFRESH_TIMEOUT_SECONDS:-7200}" in compose
    assert "REFRESH_TIMEOUT_SECONDS=7200" in template


def test_production_dependencies_are_exactly_pinned() -> None:
    requirements = (ROOT / "deploy/requirements.txt").read_text(encoding="utf-8")
    dependencies = [line for line in requirements.splitlines() if line and not line.startswith("#")]

    assert dependencies
    assert all("==" in dependency for dependency in dependencies)
    assert not any(">=" in dependency or "~=" in dependency for dependency in dependencies)


def test_cron_expression_rejects_command_injection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DAILY_REFRESH_CRON", "17 3 * * *; curl attacker")
    with pytest.raises(ValueError, match="five safe cron fields"):
        _schedule("DAILY_REFRESH_CRON", "17 3 * * *")


def test_backup_of_live_wal_database_is_self_contained(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    writer = sqlite3.connect(paths["plans"])
    try:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        writer.execute("PRAGMA wal_autocheckpoint=0")
        writer.execute("INSERT INTO evidence VALUES ('committed-in-wal')")
        writer.commit()
        assert Path(f"{paths['plans']}-wal").stat().st_size > 0
        bundle = create_backup(now=datetime(2026, 9, 8, 4, 47, tzinfo=UTC))
        copied = bundle / "plans/consumer_plans.sqlite3"
        reader = sqlite3.connect(f"file:{copied.as_posix()}?mode=ro", uri=True)
        try:
            assert reader.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
            assert reader.execute("SELECT value FROM evidence ORDER BY value").fetchall() == [
                ("committed-in-wal",),
                ("plan-before",),
            ]
        finally:
            reader.close()
        assert not list(bundle.rglob("*-wal"))
        assert not list(bundle.rglob("*-shm"))
        assert writer.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        backup_module._validate_complete_backup_bundle(bundle)
    finally:
        writer.close()


def test_backup_restore_round_trip_includes_wal_visible_rows_and_active_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 1, 4, 47, tzinfo=UTC))
    _assert_private_tree(bundle)

    connection = sqlite3.connect(paths["grocery"])
    try:
        connection.execute("UPDATE evidence SET value = 'grocery-after'")
        connection.commit()
    finally:
        connection.close()
    connection = sqlite3.connect(paths["plans"])
    try:
        connection.execute("UPDATE evidence SET value = 'plan-after'")
        connection.commit()
    finally:
        connection.close()
    _active_artifact(paths["universe"], marker="universe-after")

    restore(bundle, confirm=True)

    with sqlite3.connect(paths["grocery"]) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone()[0] == ("grocery-before")
    with sqlite3.connect(paths["plans"]) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone()[0] == ("plan-before")
    active = json.loads((paths["universe"] / "active/city-lund.json").read_text(encoding="utf-8"))
    artifact = paths["universe"] / active["artifact_file"]
    assert json.loads(artifact.read_text(encoding="utf-8"))["marker"] == ("universe-before")
    assert (bundle / "manifest.json").is_file()


def test_restore_preserves_source_lkg_timestamps_reports_and_plan_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    source_observed_at = "2026-08-30T10:16:31.972452+00:00"
    source_promoted_at = "2026-08-30T11:00:00.000000+00:00"
    report_created_at = "2026-08-30T12:00:00.000000+00:00"
    plan_created_at = "2026-08-30T13:00:00.000000+00:00"
    with sqlite3.connect(paths["grocery"]) as connection:
        connection.executescript(
            """
            CREATE TABLE catalog_snapshots (
                id TEXT PRIMARY KEY,
                previous_active_snapshot_id TEXT,
                is_active INTEGER NOT NULL,
                promoted_at TEXT
            );
            CREATE TABLE connector_health (
                chain TEXT PRIMARY KEY,
                active_snapshot_id TEXT,
                last_success_at TEXT
            );
            CREATE TABLE store_context_links (
                id TEXT PRIMARY KEY,
                snapshot_id TEXT,
                observed_at TEXT
            );
            CREATE TABLE community_evidence_observations (
                id TEXT PRIMARY KEY,
                observed_at TEXT NOT NULL,
                payload_sha256 TEXT NOT NULL
            );
            CREATE TABLE beta_feedback (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                category TEXT NOT NULL
            );
            """
        )
        connection.execute(
            "INSERT INTO catalog_snapshots VALUES (?, ?, ?, ?)",
            ("snapshot-active", "snapshot-lkg", 1, source_promoted_at),
        )
        connection.execute(
            "INSERT INTO connector_health VALUES (?, ?, ?)",
            ("coop", "snapshot-active", source_observed_at),
        )
        connection.execute(
            "INSERT INTO store_context_links VALUES (?, ?, ?)",
            ("context-link", "snapshot-active", source_observed_at),
        )
        connection.execute(
            "INSERT INTO community_evidence_observations VALUES (?, ?, ?)",
            ("community-row", report_created_at, "a" * 64),
        )
        connection.execute(
            "INSERT INTO beta_feedback VALUES (?, ?, ?)",
            ("feedback-row", report_created_at, "OTHER"),
        )
    connection.close()
    with sqlite3.connect(paths["plans"]) as connection:
        connection.execute(
            """
            CREATE TABLE consumer_plan_revisions (
                plan_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                price_universe_id TEXT,
                PRIMARY KEY (plan_id, revision)
            )
            """
        )
        connection.execute(
            "INSERT INTO consumer_plan_revisions VALUES (?, ?, ?, ?)",
            ("plan-row", 1, plan_created_at, "price-universe:universe-before"),
        )
    connection.close()

    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    state = manifest["state_integrity"]
    assert (
        state["grocery_database"]["source_freshness_and_lkg"]["tables"]["catalog_snapshots"]["rows"]
        == 1
    )
    assert (
        state["grocery_database"]["community_and_beta_reports"]["tables"][
            "community_evidence_observations"
        ]["rows"]
        == 1
    )
    assert (
        state["plan_database"]["saved_plan_revisions"]["tables"]["consumer_plan_revisions"]["rows"]
        == 1
    )
    assert state["price_universe"]["timestamps"]["oldest_observed_at"] == (
        "2026-08-30T10:16:31.972452Z"
    )

    with sqlite3.connect(paths["grocery"]) as connection:
        connection.execute(
            "UPDATE connector_health SET last_success_at = ?",
            ("2099-01-01T00:00:00+00:00",),
        )
        connection.execute("DELETE FROM community_evidence_observations")
        connection.execute("DELETE FROM beta_feedback")
    connection.close()
    with sqlite3.connect(paths["plans"]) as connection:
        connection.execute("DELETE FROM consumer_plan_revisions")
    connection.close()
    _active_artifact(paths["universe"], marker="universe-after")

    verification = restore(bundle, confirm=True)

    assert verification["status"] == "verified"
    assert verification["checks"]["grocery_database"] == {
        "status": "verified",
        "mode": "bundle_hash_then_deletion_reapplication",
    }
    assert verification["checks"]["plan_database"] == {
        "status": "verified",
        "mode": "bundle_hash_then_deletion_reapplication",
    }
    assert verification["checks"]["price_universe"] == {
        "status": "verified",
        "mode": "semantic_and_file_hash",
    }
    assert verification["checks"]["privacy_deletion_ledger"]["status"] == "verified"
    assert verification["checks"]["privacy_deletion_ledger"]["entries"] == 0
    assert verification["deletion_ledger"]["source"] == "captured_current_database"
    assert verification["deletion_ledger"]["entries"] == 0
    with sqlite3.connect(paths["grocery"]) as connection:
        assert (
            connection.execute(
                "SELECT last_success_at FROM connector_health WHERE chain = 'coop'"
            ).fetchone()[0]
            == source_observed_at
        )
        assert (
            connection.execute(
                "SELECT promoted_at FROM catalog_snapshots WHERE id = 'snapshot-active'"
            ).fetchone()[0]
            == source_promoted_at
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM community_evidence_observations").fetchone()[0]
            == 1
        )
        assert connection.execute("SELECT COUNT(*) FROM beta_feedback").fetchone()[0] == 1
    with sqlite3.connect(paths["plans"]) as connection:
        assert (
            connection.execute(
                "SELECT created_at FROM consumer_plan_revisions WHERE plan_id = 'plan-row'"
            ).fetchone()[0]
            == plan_created_at
        )
    restored_active = json.loads(
        (paths["universe"] / "active/city-lund.json").read_text(encoding="utf-8")
    )
    assert restored_active["oldest_observed_at"] == ("2026-08-30T10:16:31.972452Z")
    assert restored_active["universe_id"] == "price-universe:universe-before"


def test_disaster_restore_recreates_missing_database_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    deletion_ledger = tmp_path / "independent/privacy-erasure-ledger.json"
    export_deletion_ledger(paths["grocery"], deletion_ledger)
    paths["grocery"].unlink()
    paths["plans"].unlink()
    paths["grocery"].parent.rmdir()
    paths["plans"].parent.rmdir()

    verification = restore(bundle, confirm=True, deletion_ledger=deletion_ledger)

    assert verification["deletion_ledger"]["source"] == "operator_export"

    with sqlite3.connect(paths["grocery"]) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone()[0] == ("grocery-before")
    with sqlite3.connect(paths["plans"]) as connection:
        assert connection.execute("SELECT value FROM evidence").fetchone()[0] == ("plan-before")


def test_backup_refuses_to_overlap_managed_refresh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    lock = RefreshRunLock(production_refresh_lock_path(paths["grocery"], paths["universe"]))
    lock.acquire()
    try:
        with pytest.raises(RefreshAlreadyRunningError):
            create_backup(now=datetime(2026, 9, 2, 4, 47, tzinfo=UTC))
    finally:
        lock.release()


def test_backup_space_preflight_preserves_prior_bundle_and_creates_no_scratch(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    prior = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    prior_manifest = (prior / "manifest.json").read_bytes()

    def no_space(*_args: object, **_kwargs: object) -> StoragePreflight:
        raise InsufficientStorageError(StoragePreflight(100, 200, 300))

    monkeypatch.setattr(backup_module, "require_free_space", no_space)

    with pytest.raises(InsufficientStorageError):
        create_backup(now=datetime(2026, 9, 2, 2, 47, tzinfo=UTC))

    assert (prior / "manifest.json").read_bytes() == prior_manifest
    assert not (paths["backups"] / "20260902T024700Z").exists()
    assert not list(paths["backups"].glob(".*.tmp"))


def test_backup_enospc_during_completion_manifest_never_publishes_partial_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    prior = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    prior_manifest = (prior / "manifest.json").read_bytes()

    def disk_full(*_args: object, **_kwargs: object) -> None:
        raise OSError(errno.ENOSPC, "fault injection")

    monkeypatch.setattr(backup_module, "atomic_write_bytes", disk_full)

    with pytest.raises(OSError) as error:
        create_backup(now=datetime(2026, 9, 2, 2, 47, tzinfo=UTC))

    assert error.value.errno == errno.ENOSPC
    assert (prior / "manifest.json").read_bytes() == prior_manifest
    assert not (paths["backups"] / "20260902T024700Z").exists()
    assert not list(paths["backups"].glob(".*.tmp"))


def test_backup_cli_reports_sanitized_structured_storage_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failure = InsufficientStorageError(StoragePreflight(100, 200, 300))
    monkeypatch.setattr(backup_module, "create_backup", lambda: (_ for _ in ()).throw(failure))

    assert backup_module.main() == 1

    assert json.loads(capsys.readouterr().out) == {
        "status": "failed",
        "reason": "insufficient_storage",
        "error_type": "InsufficientStorageError",
        "free_bytes": 100,
        "required_bytes": 200,
        "reserve_bytes": 300,
    }


@pytest.mark.parametrize(
    ("writer", "environment_name"),
    (
        (refresh_runner._write_status, "REFRESH_RUNNER_STATUS_PATH"),
        (source_retry_runner._write_status, "SOURCE_RETRY_STATUS_PATH"),
    ),
)
def test_runner_status_enospc_preserves_previous_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    writer: object,
    environment_name: str,
) -> None:
    destination = tmp_path / "operations/status.json"
    destination.parent.mkdir(parents=True)
    previous = b'{"status":"last_good"}'
    destination.write_bytes(previous)
    monkeypatch.setenv(environment_name, str(destination))

    def disk_full(_descriptor: int) -> None:
        raise OSError(errno.ENOSPC, "fault injection")

    monkeypatch.setattr(durable_files.os, "fsync", disk_full)

    with pytest.raises(OSError) as error:
        writer({"status": "replacement"})  # type: ignore[operator]

    assert error.value.errno == errno.ENOSPC
    assert destination.read_bytes() == previous
    assert not list(destination.parent.glob(".*.tmp"))


def test_runtime_seeder_is_consistent_and_refuses_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    grocery = source / "grocery.sqlite"
    plans = source / "plans.sqlite3"
    universe = source / "price_universes"
    raw = source / "raw_snapshots"
    raw.mkdir()
    (raw / "evidence.json").write_text("{}", encoding="utf-8")
    _database(grocery, "grocery")
    _database(plans, "plan")
    _active_artifact(universe, marker="active")

    runtime = tmp_path / "runtime"
    result = seed_runtime(
        runtime_root=runtime,
        grocery_database=grocery,
        plan_database=plans,
        universe_root=universe,
        raw_snapshot_root=raw,
    )
    assert result["status"] == "seeded"
    assert (runtime / "grocery/grocery_data.sqlite").is_file()
    assert (runtime / "plans/consumer_plans.sqlite3").is_file()
    assert (runtime / "price_universes/active/city-lund.json").is_file()
    assert (runtime / "raw_snapshots/evidence.json").is_file()
    _assert_private_tree(runtime)

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        seed_runtime(
            runtime_root=runtime,
            grocery_database=grocery,
            plan_database=plans,
            universe_root=universe,
        )


class _FakeArtifactStore:
    def __init__(self) -> None:
        self.active: bytes | None = b"old-manifest"
        self.rollback_calls: list[tuple[bytes | None, bytes | None]] = []

    def active_manifest_bytes(self, _city: str) -> bytes | None:
        return self.active

    def resolve_active_artifact(self, _city: str, *, verify_hash: bool) -> Path:
        assert verify_hash is True
        return Path("old-artifact.json")

    def restore_active_manifest(
        self,
        _city: str,
        previous: bytes | None,
        *,
        expected_current: bytes | None,
    ) -> None:
        assert self.active == expected_current
        self.rollback_calls.append((previous, expected_current))
        self.active = previous


def _configure_refresh_runner(
    monkeypatch: pytest.MonkeyPatch,
    store: _FakeArtifactStore,
    tmp_path: Path,
) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    database = tmp_path / "grocery.sqlite"
    database.touch()
    universe = tmp_path / "price-universes"
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{database.as_posix()}",
    )
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", str(universe))
    monkeypatch.setenv("REFRESH_CITY", "Lund")
    monkeypatch.setenv("REFRESH_POSTAL_CODE", "22350")
    monkeypatch.setattr(refresh_runner, "_artifact_store", lambda: store)
    monkeypatch.setattr(refresh_runner, "_write_status", statuses.append)

    def complete_refresh(*_args: object, **kwargs: object) -> SimpleNamespace:
        child_environment = kwargs.get("env")
        assert isinstance(child_environment, dict)
        assert child_environment.get("GROCERY_DATA_REFRESH_PARENT_LOCK_NONCE")
        store.active = b"promoted-manifest"
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(refresh_runner.subprocess, "run", complete_refresh)
    return statuses


def test_reload_rejection_restores_previous_restart_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _FakeArtifactStore()
    statuses = _configure_refresh_runner(monkeypatch, store, tmp_path)

    def reject() -> dict[str, object]:
        raise refresh_runner.RuntimeReloadRejected("HTTPError")

    monkeypatch.setattr(refresh_runner, "_reload_runtime", reject)

    assert refresh_runner.main() == 1
    assert store.active == b"old-manifest"
    assert store.rollback_calls == [(b"old-manifest", b"promoted-manifest")]
    assert statuses[0]["disk_manifest_rollback"] == {
        "status": "restored_previous",
        "candidate_artifact_retained": True,
    }


def test_unavailable_app_retains_promoted_restart_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _FakeArtifactStore()
    statuses = _configure_refresh_runner(monkeypatch, store, tmp_path)

    def unavailable() -> dict[str, object]:
        raise refresh_runner.RuntimeReloadUnavailable("URLError")

    monkeypatch.setattr(refresh_runner, "_reload_runtime", unavailable)
    monkeypatch.setattr(
        refresh_runner,
        "_active_disk_universe_id",
        lambda *_args, **_kwargs: "price-universe:new",
    )

    assert refresh_runner.main() == 2
    assert store.active == b"promoted-manifest"
    assert store.rollback_calls == []
    assert statuses[0]["runtime_reload"] == {
        "status": "deferred",
        "reason": "app_unavailable",
        "error_type": "RuntimeReloadUnavailable",
        "disk_price_universe_id": "price-universe:new",
    }


def test_refresh_wrapper_holds_shared_lock_through_runtime_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = _FakeArtifactStore()
    _configure_refresh_runner(monkeypatch, store, tmp_path)
    database = tmp_path / "grocery.sqlite"
    universe = tmp_path / "price-universes"
    lock_path = production_refresh_lock_path(database, universe)
    lock_checks: list[str] = []

    def assert_locked(stage: str) -> None:
        contender = RefreshRunLock(lock_path)
        with pytest.raises(RefreshAlreadyRunningError):
            contender.acquire()
        lock_checks.append(stage)

    def complete_refresh(*_args: object, **kwargs: object) -> SimpleNamespace:
        child_environment = kwargs.get("env")
        assert isinstance(child_environment, dict)
        assert child_environment.get("GROCERY_DATA_REFRESH_PARENT_LOCK_NONCE")
        assert_locked("collection")
        store.active = b"promoted-manifest"
        return SimpleNamespace(returncode=0)

    def reload_runtime() -> dict[str, object]:
        assert_locked("runtime_activation")
        return {
            "old_price_universe_id": "old",
            "new_price_universe_id": "new",
            "changed": True,
        }

    monkeypatch.setattr(refresh_runner.subprocess, "run", complete_refresh)
    monkeypatch.setattr(refresh_runner, "_reload_runtime", reload_runtime)

    assert refresh_runner.main() == 0
    assert lock_checks == ["collection", "runtime_activation"]
    after = RefreshRunLock(lock_path)
    after.acquire()
    after.release()


def test_private_permission_helper_requests_owner_only_modes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    requested: list[int] = []
    monkeypatch.setattr(Path, "chmod", lambda _path, mode: requested.append(mode))

    _chmod_private(tmp_path, directory=True)
    _chmod_private(tmp_path / "record.sqlite", directory=False)

    assert requested == [0o700, 0o600]


def test_restore_refuses_to_overlap_managed_refresh(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure_backup(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 3, 2, 47, tzinfo=UTC))
    lock = RefreshRunLock(production_refresh_lock_path(paths["grocery"], paths["universe"]))
    lock.acquire()
    try:
        with pytest.raises(RefreshAlreadyRunningError):
            restore(bundle, confirm=True)
    finally:
        lock.release()


@pytest.mark.parametrize("arrival_failure", [False, True])
def test_relay_arrivals_hold_operation_lock_and_do_not_block_daily_refresh(
    monkeypatch, tmp_path, arrival_failure
):
    from grocery_data.app.services import source_artifact

    store = _FakeArtifactStore()
    statuses = _configure_refresh_runner(monkeypatch, store, tmp_path)
    monkeypatch.setenv("WILLYS_COLLECTION_LOCATION", "LOCAL_RELAY")
    monkeypatch.setenv("GROCERY_RAW_SNAPSHOT_ROOT", str(tmp_path / "raw"))
    calls = []

    async def arrivals(*args, **kwargs):
        contender = RefreshRunLock(
            production_refresh_lock_path(tmp_path / "grocery.sqlite", tmp_path / "price-universes")
        )
        with pytest.raises(RefreshAlreadyRunningError):
            contender.acquire()
        calls.append("inbox")
        if arrival_failure:
            raise OSError("synthetic inbox fault")
        return [{"status": "imported"}]

    monkeypatch.setattr(source_artifact, "import_source_inbox", arrivals)
    monkeypatch.setattr(refresh_runner, "_reload_runtime", lambda: {"changed": True})
    assert refresh_runner.main() == 0
    assert calls == ["inbox"]
    assert store.active == b"promoted-manifest"
    assert statuses[0]["source_relay_imports"][0]["status"] == (
        "failed" if arrival_failure else "imported"
    )
