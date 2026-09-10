from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from deploy.scripts.backup_sqlite import create_backup
from deploy.scripts.privacy_erasure_ledger import (
    DeletionLedgerError,
    DeletionLedgerUnavailableError,
    apply_deletion_ledger,
    export_deletion_ledger,
    load_deletion_ledger,
)
from deploy.scripts.restore_sqlite import restore

_OBSERVED_AT = "2026-08-30T10:16:31.972452+00:00"
_PROMOTED_AT = "2026-08-30T11:00:00.000000+00:00"
_PLAN_CREATED_AT = "2026-08-30T13:00:00.000000+00:00"
_OLD_ACTOR = "a" * 64
_OTHER_ACTOR = "b" * 64


def _active_artifact(root: Path, *, marker: str) -> None:
    payload = json.dumps({"marker": marker}, sort_keys=True).encode()
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


def _create_grocery_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            CREATE TABLE privacy_erasure_suppressions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                target_kind TEXT NOT NULL,
                target_record_id TEXT NOT NULL,
                action TEXT NOT NULL,
                UNIQUE (target_kind, target_record_id)
            );
            CREATE TABLE beta_feedback (
                id TEXT PRIMARY KEY, actor_hash TEXT, message TEXT NOT NULL
            );
            CREATE TABLE product_analytics_events (
                id TEXT PRIMARY KEY, actor_hash TEXT
            );
            CREATE TABLE frontend_errors (
                id TEXT PRIMARY KEY, actor_hash TEXT
            );
            CREATE TABLE beta_request_metrics (
                id TEXT PRIMARY KEY, plan_id TEXT
            );
            CREATE TABLE community_evidence_observations (
                id TEXT PRIMARY KEY,
                actor_hash TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                factual_value TEXT NOT NULL
            );
            CREATE TABLE community_receipt_ingestions (
                id TEXT PRIMARY KEY,
                actor_hash TEXT NOT NULL,
                purchase_observed_at TEXT NOT NULL,
                factual_value TEXT NOT NULL
            );
            CREATE TABLE catalog_snapshots (
                id TEXT PRIMARY KEY, promoted_at TEXT NOT NULL
            );
            CREATE TABLE connector_health (
                chain TEXT PRIMARY KEY, last_success_at TEXT NOT NULL
            );
            CREATE TABLE store_context_links (
                id TEXT PRIMARY KEY, observed_at TEXT NOT NULL
            );
            """
        )
        connection.executemany(
            "INSERT INTO beta_feedback VALUES (?, ?, ?)",
            (
                ("feedback-user", _OLD_ACTOR, "delete me"),
                ("feedback-other", _OTHER_ACTOR, "keep me"),
            ),
        )
        connection.execute(
            "INSERT INTO product_analytics_events VALUES (?, ?)",
            ("analytics-user", _OLD_ACTOR),
        )
        connection.execute(
            "INSERT INTO frontend_errors VALUES (?, ?)",
            ("frontend-user", _OLD_ACTOR),
        )
        connection.execute(
            "INSERT INTO beta_request_metrics VALUES (?, ?)",
            ("metric-user", "plan-user"),
        )
        connection.execute(
            "INSERT INTO community_evidence_observations VALUES (?, ?, ?, ?)",
            (
                "observation-user",
                _OLD_ACTOR,
                _OBSERVED_AT,
                "factual shelf observation",
            ),
        )
        connection.execute(
            "INSERT INTO community_receipt_ingestions VALUES (?, ?, ?, ?)",
            (
                "receipt-user",
                _OLD_ACTOR,
                _OBSERVED_AT,
                "parsed factual receipt lines",
            ),
        )
        connection.execute(
            "INSERT INTO catalog_snapshots VALUES (?, ?)",
            ("snapshot-original", _PROMOTED_AT),
        )
        connection.execute(
            "INSERT INTO connector_health VALUES (?, ?)",
            ("coop", _OBSERVED_AT),
        )
        connection.execute(
            "INSERT INTO store_context_links VALUES (?, ?)",
            ("context-original", _OBSERVED_AT),
        )
        connection.commit()


def _create_plan_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute(
            """
            CREATE TABLE consumer_plan_revisions (
                plan_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                owner_actor_hash TEXT,
                created_at TEXT NOT NULL,
                price_universe_id TEXT NOT NULL,
                PRIMARY KEY (plan_id, revision)
            )
            """
        )
        connection.executemany(
            "INSERT INTO consumer_plan_revisions VALUES (?, ?, ?, ?, ?)",
            (
                (
                    "plan-user",
                    1,
                    _OLD_ACTOR,
                    _PLAN_CREATED_AT,
                    "price-universe:original",
                ),
                (
                    "plan-other",
                    1,
                    _OTHER_ACTOR,
                    _PLAN_CREATED_AT,
                    "price-universe:original",
                ),
            ),
        )
        connection.commit()


def _configure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, Path]:
    grocery = tmp_path / "runtime/grocery/grocery.sqlite"
    plans = tmp_path / "runtime/plans/plans.sqlite3"
    universe = tmp_path / "runtime/price_universes"
    backups = tmp_path / "runtime/backups"
    _create_grocery_database(grocery)
    _create_plan_database(plans)
    _active_artifact(universe, marker="original")
    monkeypatch.setenv(
        "GROCERY_DATABASE_URL",
        f"sqlite+pysqlite:///{grocery.resolve().as_posix()}",
    )
    monkeypatch.setenv("PLAN_STORE_PATH", str(plans))
    monkeypatch.setenv("PRICE_UNIVERSE_CACHE_ROOT", str(universe))
    monkeypatch.setenv("PRICE_UNIVERSE_CITY", "Lund")
    monkeypatch.setenv("BACKUP_ROOT", str(backups))
    monkeypatch.setenv("BACKUP_RETENTION_DAYS", "14")
    return {
        "grocery": grocery,
        "plans": plans,
        "universe": universe,
        "backups": backups,
    }


def _record_current_deletion(paths: dict[str, Path]) -> None:
    directives = (
        ("01" * 16, "beta_feedback", "feedback-user"),
        ("02" * 16, "analytics_event", "analytics-user"),
        ("03" * 16, "frontend_error", "frontend-user"),
        ("04" * 16, "request_metric", "metric-user"),
        ("05" * 16, "community_observation", "observation-user"),
        ("06" * 16, "receipt_ingestion", "receipt-user"),
        ("07" * 16, "saved_plan", "plan-user"),
    )
    with closing(sqlite3.connect(paths["grocery"])) as connection:
        connection.executemany(
            """
            INSERT INTO privacy_erasure_suppressions
                (id, created_at, target_kind, target_record_id, action)
            VALUES (?, ?, ?, ?, 'SUPPRESS_ON_RESTORE')
            """,
            (
                (identifier, "2026-09-02T10:00:00+00:00", kind, target)
                for identifier, kind, target in directives
            ),
        )
        connection.execute("DELETE FROM beta_feedback WHERE id = 'feedback-user'")
        connection.execute("DELETE FROM product_analytics_events WHERE id = 'analytics-user'")
        connection.execute("DELETE FROM frontend_errors WHERE id = 'frontend-user'")
        connection.execute("DELETE FROM beta_request_metrics WHERE id = 'metric-user'")
        connection.execute(
            """
            UPDATE community_evidence_observations
            SET actor_hash = ? WHERE id = 'observation-user'
            """,
            ("c" * 64,),
        )
        connection.execute(
            """
            UPDATE community_receipt_ingestions
            SET actor_hash = ? WHERE id = 'receipt-user'
            """,
            ("d" * 64,),
        )
        connection.commit()
    with closing(sqlite3.connect(paths["plans"])) as connection:
        connection.execute("DELETE FROM consumer_plan_revisions WHERE plan_id = 'plan-user'")
        connection.commit()


def test_old_backup_reapplies_current_deletions_idempotently_and_preserves_truth(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    _record_current_deletion(paths)
    ledger = tmp_path / "independent/privacy-erasure-ledger.json"
    export = export_deletion_ledger(paths["grocery"], ledger)
    assert export["status"] == "verified"
    assert export["entries"] == 7

    verification = restore(bundle, confirm=True, deletion_ledger=ledger)

    assert verification["status"] == "verified"
    assert verification["deletion_ledger"] == {
        "status": "verified_and_applied",
        "source": "operator_export",
        "entries": 7,
        "entries_sha256": export["entries_sha256"],
    }
    assert verification["checks"]["grocery_database"]["mode"] == (
        "bundle_hash_then_deletion_reapplication"
    )
    with closing(sqlite3.connect(paths["grocery"])) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM beta_feedback WHERE id = 'feedback-user'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT message FROM beta_feedback WHERE id = 'feedback-other'"
            ).fetchone()[0]
            == "keep me"
        )
        observation = connection.execute(
            """
            SELECT actor_hash, observed_at, factual_value
            FROM community_evidence_observations
            WHERE id = 'observation-user'
            """
        ).fetchone()
        receipt = connection.execute(
            """
            SELECT actor_hash, purchase_observed_at, factual_value
            FROM community_receipt_ingestions
            WHERE id = 'receipt-user'
            """
        ).fetchone()
        assert observation[0] != _OLD_ACTOR
        assert observation[1:] == (_OBSERVED_AT, "factual shelf observation")
        assert receipt[0] != _OLD_ACTOR
        assert receipt[1:] == (_OBSERVED_AT, "parsed factual receipt lines")
        assert observation[0] != receipt[0]
        assert (
            connection.execute(
                "SELECT last_success_at FROM connector_health WHERE chain = 'coop'"
            ).fetchone()[0]
            == _OBSERVED_AT
        )
        assert (
            connection.execute(
                "SELECT promoted_at FROM catalog_snapshots WHERE id = 'snapshot-original'"
            ).fetchone()[0]
            == _PROMOTED_AT
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM privacy_erasure_suppressions").fetchone()[0]
            == 7
        )
    with closing(sqlite3.connect(paths["plans"])) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM consumer_plan_revisions WHERE plan_id = 'plan-user'"
            ).fetchone()[0]
            == 0
        )
        assert connection.execute(
            """
            SELECT created_at, price_universe_id
            FROM consumer_plan_revisions WHERE plan_id = 'plan-other'
            """
        ).fetchone() == (_PLAN_CREATED_AT, "price-universe:original")
    active = json.loads((paths["universe"] / "active/city-lund.json").read_text(encoding="utf-8"))
    assert active["universe_id"] == "price-universe:original"
    assert active["snapshot_ids"] == ["snapshot-original"]
    assert active["oldest_observed_at"] == "2026-08-30T10:16:31.972452Z"

    entries = load_deletion_ledger(ledger)
    first = apply_deletion_ledger(paths["grocery"], paths["plans"], entries)
    second = apply_deletion_ledger(paths["grocery"], paths["plans"], entries)
    assert first["verification"] == second["verification"]
    assert first["verification"]["status"] == "verified"


def test_empty_valid_ledger_restores_legacy_backup_without_suppression_table(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure(monkeypatch, tmp_path)
    with closing(sqlite3.connect(paths["grocery"])) as connection:
        connection.execute("DROP TABLE privacy_erasure_suppressions")
        connection.commit()
    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    with closing(sqlite3.connect(paths["grocery"])) as connection:
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
    ledger = tmp_path / "independent/empty-privacy-erasure-ledger.json"
    export = export_deletion_ledger(paths["grocery"], ledger)
    assert export["entries"] == 0

    verification = restore(bundle, confirm=True, deletion_ledger=ledger)

    assert verification["checks"]["grocery_database"]["mode"] == (
        "bundle_hash_then_deletion_reapplication"
    )
    assert verification["deletion_ledger"]["entries"] == 0
    with closing(sqlite3.connect(paths["grocery"])) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM privacy_erasure_suppressions"
            ).fetchone()[0]
            == 0
        )


def test_missing_current_deletion_ledger_fails_before_restore_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    paths["grocery"].unlink()

    with pytest.raises(DeletionLedgerUnavailableError, match="unavailable"):
        restore(bundle, confirm=True)

    assert not paths["grocery"].exists()
    with closing(sqlite3.connect(paths["plans"])) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM consumer_plan_revisions WHERE plan_id = 'plan-user'"
            ).fetchone()[0]
            == 1
        )


def test_corrupt_external_deletion_ledger_fails_before_restore_activation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    _record_current_deletion(paths)
    ledger = tmp_path / "independent/privacy-erasure-ledger.json"
    export_deletion_ledger(paths["grocery"], ledger)
    payload = json.loads(ledger.read_text(encoding="utf-8"))
    payload["entries"][0]["target_record_id"] = "tampered-target"
    ledger.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(DeletionLedgerError, match="integrity hash"):
        restore(bundle, confirm=True, deletion_ledger=ledger)

    with closing(sqlite3.connect(paths["grocery"])) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM beta_feedback WHERE id = 'feedback-user'"
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute("SELECT COUNT(*) FROM privacy_erasure_suppressions").fetchone()[0]
            == 7
        )
    with closing(sqlite3.connect(paths["plans"])) as connection:
        assert (
            connection.execute(
                "SELECT COUNT(*) FROM consumer_plan_revisions WHERE plan_id = 'plan-user'"
            ).fetchone()[0]
            == 0
        )


def test_restore_rejects_hidden_temporary_bundle_even_with_complete_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    paths = _configure(monkeypatch, tmp_path)
    bundle = create_backup(now=datetime(2026, 9, 1, 2, 47, tzinfo=UTC))
    temporary_bundle = bundle.with_name(f".{bundle.name}.interrupted.tmp")
    bundle.rename(temporary_bundle)

    with pytest.raises(ValueError, match="temporary/incomplete"):
        restore(temporary_bundle, confirm=True)

    with closing(sqlite3.connect(paths["grocery"])) as connection:
        assert (
            connection.execute(
                "SELECT message FROM beta_feedback WHERE id = 'feedback-user'"
            ).fetchone()[0]
            == "delete me"
        )
