"""Export, validate, replay, and verify the privacy-erasure restore ledger.

The application database contains an append-only list of actor-free suppression
directives.  A historical restore must copy that current list out of the file
being replaced, validate it, and replay it against isolated database copies
before those copies can become active.  An operator may also provide a
previously exported ledger when the current database is unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

LEDGER_SCHEMA_VERSION = "privacy-erasure-ledger-v1"
SUPPRESSION_ACTION = "SUPPRESS_ON_RESTORE"

_HARD_DELETE_TARGETS = {
    "beta_feedback": "beta_feedback",
    "analytics_event": "product_analytics_events",
    "frontend_error": "frontend_errors",
    "request_metric": "beta_request_metrics",
}
_UNLINK_TARGETS = {
    "community_observation": "community_evidence_observations",
    "receipt_ingestion": "community_receipt_ingestions",
}
_SAVED_PLAN_TARGET = "saved_plan"
_ALLOWED_TARGET_KINDS = frozenset((*_HARD_DELETE_TARGETS, *_UNLINK_TARGETS, _SAVED_PLAN_TARGET))
_LEDGER_COLUMNS = {
    "id",
    "created_at",
    "target_kind",
    "target_record_id",
    "action",
}


class DeletionLedgerError(ValueError):
    """The supplied ledger cannot safely govern a restore."""


class DeletionLedgerUnavailableError(FileNotFoundError):
    """No independently usable current deletion information is available."""


@dataclass(frozen=True, slots=True)
class SuppressionDirective:
    id: str
    created_at: str
    target_kind: str
    target_record_id: str
    action: str = SUPPRESSION_ACTION

    @property
    def replacement_actor_hash(self) -> str | None:
        if self.target_kind not in _UNLINK_TARGETS:
            return None
        # This value is derived only from the already-opaque row ID.  It cannot
        # recover or correlate the erased browser/session identity, and is
        # deliberately different for every retained factual row.
        material = f"privacy-erasure-restored-row:v1:{self.target_kind}:{self.target_record_id}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def as_dict(self) -> dict[str, str]:
        return {
            "action": self.action,
            "created_at": self.created_at,
            "id": self.id,
            "target_kind": self.target_kind,
            "target_record_id": self.target_record_id,
        }


def _canonical_entries(entries: Iterable[SuppressionDirective]) -> bytes:
    rows = [entry.as_dict() for entry in entries]
    rows.sort(key=lambda row: (row["target_kind"], row["target_record_id"], row["id"]))
    return json.dumps(
        rows,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def ledger_digest(entries: Iterable[SuppressionDirective]) -> str:
    return hashlib.sha256(_canonical_entries(entries)).hexdigest()


def _validate_text(value: object, *, name: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise DeletionLedgerError(f"invalid deletion ledger {name}")
    if any(ord(character) < 32 for character in value):
        raise DeletionLedgerError(f"invalid deletion ledger {name}")
    return value


def _directive(value: object) -> SuppressionDirective:
    if not isinstance(value, dict):
        raise DeletionLedgerError("invalid deletion ledger entry")
    directive = SuppressionDirective(
        id=_validate_text(value.get("id"), name="id", maximum=64),
        created_at=_validate_text(value.get("created_at"), name="created_at", maximum=64),
        target_kind=_validate_text(value.get("target_kind"), name="target_kind", maximum=32),
        target_record_id=_validate_text(
            value.get("target_record_id"),
            name="target_record_id",
            maximum=128,
        ),
        action=_validate_text(value.get("action"), name="action", maximum=32),
    )
    if directive.target_kind not in _ALLOWED_TARGET_KINDS:
        raise DeletionLedgerError(f"unsupported deletion ledger target: {directive.target_kind}")
    if directive.action != SUPPRESSION_ACTION:
        raise DeletionLedgerError("unsupported deletion ledger action")
    return directive


def _validate_directives(values: Iterable[object]) -> tuple[SuppressionDirective, ...]:
    directives = tuple(_directive(value) for value in values)
    ids: set[str] = set()
    targets: set[tuple[str, str]] = set()
    for directive in directives:
        target = (directive.target_kind, directive.target_record_id)
        if directive.id in ids:
            raise DeletionLedgerError("duplicate deletion ledger id")
        if target in targets:
            raise DeletionLedgerError("duplicate deletion ledger target")
        ids.add(directive.id)
        targets.add(target)
    return tuple(
        sorted(
            directives,
            key=lambda row: (row.target_kind, row.target_record_id, row.id),
        )
    )


def _database_integrity(connection: sqlite3.Connection, *, label: str) -> None:
    result = connection.execute("PRAGMA quick_check").fetchone()
    if result is None or result[0] != "ok":
        raise DeletionLedgerError(f"{label} failed SQLite integrity validation")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise DeletionLedgerError(f"{label} failed SQLite foreign-key validation")


def capture_current_deletion_ledger(database: Path) -> tuple[SuppressionDirective, ...]:
    """Read and validate the current append-only ledger without modifying it."""

    database = database.expanduser().resolve()
    if not database.is_file():
        raise DeletionLedgerUnavailableError(
            "current privacy-erasure ledger database is unavailable"
        )
    try:
        connection = sqlite3.connect(
            f"file:{database.as_posix()}?mode=ro",
            uri=True,
        )
    except sqlite3.Error as exc:
        raise DeletionLedgerUnavailableError(
            "current privacy-erasure ledger database cannot be opened"
        ) from exc
    try:
        _database_integrity(connection, label="current privacy-erasure ledger database")
        table = connection.execute(
            """
            SELECT 1 FROM sqlite_master
            WHERE type = 'table' AND name = 'privacy_erasure_suppressions'
            """
        ).fetchone()
        if table is None:
            raise DeletionLedgerUnavailableError(
                "current privacy-erasure suppression table is unavailable"
            )
        columns = {
            str(row[1])
            for row in connection.execute('PRAGMA table_info("privacy_erasure_suppressions")')
        }
        if not _LEDGER_COLUMNS.issubset(columns):
            raise DeletionLedgerError(
                "current privacy-erasure suppression table has an invalid schema"
            )
        rows = connection.execute(
            """
            SELECT id, created_at, target_kind, target_record_id, action
            FROM privacy_erasure_suppressions
            ORDER BY target_kind, target_record_id, id
            """
        ).fetchall()
        return _validate_directives(
            {
                "id": row[0],
                "created_at": row[1],
                "target_kind": row[2],
                "target_record_id": row[3],
                "action": row[4],
            }
            for row in rows
        )
    except sqlite3.DatabaseError as exc:
        raise DeletionLedgerError("current privacy-erasure ledger failed validation") from exc
    finally:
        connection.close()


def _ledger_payload(
    entries: tuple[SuppressionDirective, ...],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    timestamp = (generated_at or datetime.now(UTC)).astimezone(UTC)
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "generated_at": timestamp.isoformat(),
        "entries_sha256": ledger_digest(entries),
        "entries": [entry.as_dict() for entry in entries],
    }


def _load_payload(payload: object) -> tuple[SuppressionDirective, ...]:
    if not isinstance(payload, dict):
        raise DeletionLedgerError("deletion ledger must be a JSON object")
    if payload.get("schema_version") != LEDGER_SCHEMA_VERSION:
        raise DeletionLedgerError("unsupported deletion ledger schema")
    generated_at = payload.get("generated_at")
    _validate_text(generated_at, name="generated_at", maximum=64)
    values = payload.get("entries")
    if not isinstance(values, list):
        raise DeletionLedgerError("deletion ledger entries must be a list")
    entries = _validate_directives(values)
    expected = payload.get("entries_sha256")
    if not isinstance(expected, str) or not hmac.compare_digest(
        expected,
        ledger_digest(entries),
    ):
        raise DeletionLedgerError("deletion ledger integrity hash does not match")
    return entries


def load_deletion_ledger(path: Path) -> tuple[SuppressionDirective, ...]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise DeletionLedgerUnavailableError("privacy-erasure ledger file is unavailable")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeletionLedgerError("privacy-erasure ledger file is corrupt") from exc
    return _load_payload(payload)


def _chmod_private(path: Path, *, directory: bool) -> None:
    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        if os.name != "nt":
            raise


def export_deletion_ledger(
    database: Path,
    destination: Path,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Atomically export current suppression directives to an independent file."""

    entries = capture_current_deletion_ledger(database)
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _chmod_private(destination.parent, directory=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    payload = _ledger_payload(entries, generated_at=generated_at)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    try:
        with temporary.open("xb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _chmod_private(temporary, directory=False)
        # Read back and validate the exact temporary file before publication.
        verified = load_deletion_ledger(temporary)
        if verified != entries:
            raise DeletionLedgerError("deletion ledger readback differs from export")
        os.replace(temporary, destination)
        _chmod_private(destination, directory=False)
        try:
            directory = os.open(destination.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            # Windows developer filesystems commonly do not support directory
            # fsync. The file itself was flushed and is always hash-validated.
            pass
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "status": "verified",
        "schema_version": LEDGER_SCHEMA_VERSION,
        "entries": len(entries),
        "entries_sha256": ledger_digest(entries),
        "bytes": destination.stat().st_size,
    }


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        is not None
    )


def _ensure_suppression_table(connection: sqlite3.Connection) -> None:
    already_exists = _table_exists(connection, "privacy_erasure_suppressions")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS privacy_erasure_suppressions (
            id VARCHAR(32) NOT NULL PRIMARY KEY,
            created_at DATETIME NOT NULL,
            target_kind VARCHAR(32) NOT NULL,
            target_record_id VARCHAR(128) NOT NULL,
            action VARCHAR(32) NOT NULL DEFAULT 'SUPPRESS_ON_RESTORE',
            CONSTRAINT uq_privacy_erasure_suppression_target
                UNIQUE (target_kind, target_record_id)
        )
        """
    )
    if not already_exists:
        connection.execute(
            """
            CREATE INDEX ix_privacy_erasure_suppressions_created
            ON privacy_erasure_suppressions (created_at)
            """
        )


def _apply_grocery_directives(
    database: Path,
    entries: tuple[SuppressionDirective, ...],
) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        _database_integrity(connection, label="staged grocery database before suppression")
        connection.execute("BEGIN IMMEDIATE")
        _ensure_suppression_table(connection)
        for entry in entries:
            table = _HARD_DELETE_TARGETS.get(entry.target_kind)
            if table is not None and _table_exists(connection, table):
                connection.execute(
                    f'DELETE FROM "{table}" WHERE id = ?',
                    (entry.target_record_id,),
                )
            unlink_table = _UNLINK_TARGETS.get(entry.target_kind)
            if unlink_table is not None and _table_exists(connection, unlink_table):
                replacement = entry.replacement_actor_hash
                connection.execute(
                    f'UPDATE "{unlink_table}" SET actor_hash = ? WHERE id = ? AND actor_hash <> ?',
                    (replacement, entry.target_record_id, replacement),
                )
            connection.execute(
                """
                INSERT INTO privacy_erasure_suppressions (
                    id, created_at, target_kind, target_record_id, action
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(target_kind, target_record_id) DO NOTHING
                """,
                (
                    entry.id,
                    entry.created_at,
                    entry.target_kind,
                    entry.target_record_id,
                    entry.action,
                ),
            )
        connection.commit()
        _database_integrity(connection, label="staged grocery database after suppression")
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def _apply_plan_directives(
    database: Path,
    entries: tuple[SuppressionDirective, ...],
) -> None:
    connection = sqlite3.connect(database)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        _database_integrity(connection, label="staged plan database before suppression")
        connection.execute("BEGIN IMMEDIATE")
        if _table_exists(connection, "consumer_plan_revisions"):
            for entry in entries:
                if entry.target_kind == _SAVED_PLAN_TARGET:
                    connection.execute(
                        "DELETE FROM consumer_plan_revisions WHERE plan_id = ?",
                        (entry.target_record_id,),
                    )
        connection.commit()
        _database_integrity(connection, label="staged plan database after suppression")
    except BaseException:
        connection.rollback()
        raise
    finally:
        connection.close()


def apply_deletion_ledger(
    grocery_database: Path,
    plan_database: Path,
    entries: Iterable[SuppressionDirective],
) -> dict[str, Any]:
    """Apply directives idempotently to isolated database copies."""

    validated = _validate_directives(entry.as_dict() for entry in entries)
    _apply_grocery_directives(grocery_database, validated)
    _apply_plan_directives(plan_database, validated)
    result = verify_deletion_ledger(grocery_database, plan_database, validated)
    return {
        "status": "applied",
        "entries": len(validated),
        "entries_sha256": ledger_digest(validated),
        "verification": result,
    }


def verify_deletion_ledger(
    grocery_database: Path,
    plan_database: Path,
    entries: Iterable[SuppressionDirective],
) -> dict[str, Any]:
    """Fail unless every directive is persisted and its target is suppressed."""

    validated = _validate_directives(entry.as_dict() for entry in entries)
    grocery_checks = 0
    connection = sqlite3.connect(
        f"file:{grocery_database.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        _database_integrity(connection, label="suppressed grocery database")
        if not _table_exists(connection, "privacy_erasure_suppressions"):
            raise DeletionLedgerError("restored suppression ledger table is missing")
        for entry in validated:
            persisted = connection.execute(
                """
                SELECT action FROM privacy_erasure_suppressions
                WHERE target_kind = ? AND target_record_id = ?
                """,
                (entry.target_kind, entry.target_record_id),
            ).fetchone()
            if persisted is None or persisted[0] != SUPPRESSION_ACTION:
                raise DeletionLedgerError("restored suppression directive is missing")
            table = _HARD_DELETE_TARGETS.get(entry.target_kind)
            if (
                table is not None
                and _table_exists(connection, table)
                and connection.execute(
                    f'SELECT 1 FROM "{table}" WHERE id = ?',
                    (entry.target_record_id,),
                ).fetchone()
                is not None
            ):
                raise DeletionLedgerError("deleted user-linked row reappeared")
            unlink_table = _UNLINK_TARGETS.get(entry.target_kind)
            if unlink_table is not None and _table_exists(connection, unlink_table):
                row = connection.execute(
                    f'SELECT actor_hash FROM "{unlink_table}" WHERE id = ?',
                    (entry.target_record_id,),
                ).fetchone()
                if row is not None and row[0] != entry.replacement_actor_hash:
                    raise DeletionLedgerError("retained factual row remains user-linkable")
            grocery_checks += 1
    finally:
        connection.close()

    plan_checks = 0
    connection = sqlite3.connect(
        f"file:{plan_database.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        _database_integrity(connection, label="suppressed plan database")
        if _table_exists(connection, "consumer_plan_revisions"):
            for entry in validated:
                if entry.target_kind != _SAVED_PLAN_TARGET:
                    continue
                if (
                    connection.execute(
                        "SELECT 1 FROM consumer_plan_revisions WHERE plan_id = ?",
                        (entry.target_record_id,),
                    ).fetchone()
                    is not None
                ):
                    raise DeletionLedgerError("deleted saved plan reappeared")
                plan_checks += 1
    finally:
        connection.close()
    return {
        "status": "verified",
        "entries": len(validated),
        "entries_sha256": ledger_digest(validated),
        "grocery_directives_verified": grocery_checks,
        "saved_plan_directives_verified": plan_checks,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--database", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--ledger", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "export":
        result = export_deletion_ledger(args.database, args.output)
    else:
        entries = load_deletion_ledger(args.ledger)
        result = {
            "status": "verified",
            "schema_version": LEDGER_SCHEMA_VERSION,
            "entries": len(entries),
            "entries_sha256": ledger_digest(entries),
        }
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
