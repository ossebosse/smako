"""Create a consistent, integrity-checked daily beta backup bundle."""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import shutil
import sqlite3
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import make_url

from grocery_data.app.services.durable_files import (
    InsufficientStorageError,
    atomic_write_bytes,
    require_free_space,
)
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)

_SAFE_SCOPE_PART = re.compile(r"[^0-9a-zåäö]+")
_BACKUP_ESTIMATE_OVERHEAD_BYTES = 16 * 1024 * 1024
_DEFAULT_BACKUP_FREE_SPACE_RESERVE_BYTES = 512 * 1024 * 1024

# These projections are deliberately limited to operational metadata and
# beta-user records.  Product/price payload integrity is already covered by
# the exact database-file SHA-256.  The additional table fingerprints make a
# restore rehearsal able to prove, without exposing row contents, that source
# observation times, LKG links and user-report records did not change.
_GROCERY_STATE_TABLE_GROUPS: dict[str, tuple[str, ...]] = {
    "source_freshness_and_lkg": (
        "collector_runs",
        "catalog_snapshots",
        "raw_snapshots",
        "connector_health",
        "store_context_links",
    ),
    "community_and_beta_reports": (
        "community_evidence_observations",
        "community_evidence_moderation_events",
        "community_receipt_ingestions",
        "beta_feedback",
        "product_analytics_events",
        "frontend_errors",
        "beta_request_metrics",
        "privacy_erasure_suppressions",
    ),
}
_PLAN_STATE_TABLE_GROUPS: dict[str, tuple[str, ...]] = {
    "saved_plan_revisions": ("consumer_plan_revisions",),
    "private_personal_state": ("personal_private_state",),
}


def _chmod_private(path: Path, *, directory: bool) -> None:
    """Apply owner-only mode on POSIX and best-effort readonly bits on Windows."""

    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        if os.name != "nt":
            raise


def _private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _chmod_private(path, directory=True)


def _secure_tree(root: Path) -> None:
    if not root.exists():
        return
    for path in root.rglob("*"):
        _chmod_private(path, directory=path.is_dir())
    _chmod_private(root, directory=True)


def _sqlite_path(database_url: str) -> Path:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database:
        raise ValueError("beta SQLite backup requires a file-backed SQLite URL")
    return Path(url.database).expanduser().resolve()


def configured_database_paths() -> dict[str, Path]:
    database_url = os.getenv("GROCERY_DATABASE_URL", "").strip()
    plan_path = os.getenv("PLAN_STORE_PATH", "").strip()
    if not database_url or not plan_path:
        raise RuntimeError("GROCERY_DATABASE_URL and PLAN_STORE_PATH are required")
    return {
        "grocery/grocery_data.sqlite": _sqlite_path(database_url),
        "plans/consumer_plans.sqlite3": Path(plan_path).expanduser().resolve(),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fsync_file(path: Path) -> None:
    # Windows requires a writable descriptor for ``os.fsync`` even though no
    # bytes are changed here. All callers own private files in the temp bundle.
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def _fsync_tree(root: Path) -> None:
    """Flush completed bundle files and directory entries before publication."""

    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        _fsync_file(path)
    if os.name == "nt":
        return
    directories = [root, *(item for item in root.rglob("*") if item.is_dir())]
    for path in sorted(directories, key=lambda item: len(item.parts), reverse=True):
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _sqlite_backup_size_upper_bound(source: Path) -> int:
    if not source.is_file():
        raise FileNotFoundError(f"required SQLite database is missing: {source.name}")
    connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    try:
        page_size = int(connection.execute("PRAGMA page_size").fetchone()[0])
        page_count = int(connection.execute("PRAGMA page_count").fetchone()[0])
    finally:
        connection.close()
    return max(source.stat().st_size, page_size * page_count)


def _active_artifact_pair_bytes(root: Path, relative_manifest: Path) -> int:
    manifest_path = root / relative_manifest
    if not manifest_path.is_file():
        return 0
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("active artifact manifest must be an object")
    artifact_value = payload.get("artifact_file")
    if not isinstance(artifact_value, str):
        raise TypeError("active artifact manifest lacks artifact_file")
    relative_artifact = PurePosixPath(artifact_value)
    if relative_artifact.is_absolute() or ".." in relative_artifact.parts:
        raise ValueError("active artifact path escapes its root")
    artifact_path = root / Path(*relative_artifact.parts)
    if not artifact_path.is_file():
        raise FileNotFoundError("active artifact referenced by manifest is missing")
    return manifest_path.stat().st_size + artifact_path.stat().st_size


def _backup_free_space_reserve_bytes() -> int:
    raw = os.getenv(
        "BACKUP_FREE_SPACE_RESERVE_BYTES",
        str(_DEFAULT_BACKUP_FREE_SPACE_RESERVE_BYTES),
    )
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("BACKUP_FREE_SPACE_RESERVE_BYTES must be an integer") from exc
    if not 0 <= value <= 1024**4:
        raise ValueError("BACKUP_FREE_SPACE_RESERVE_BYTES is outside its safe range")
    return value


def _preflight_backup_space(backup_root: Path, relative_manifest: Path) -> None:
    databases = configured_database_paths()
    universe_root = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).resolve()
    required = _BACKUP_ESTIMATE_OVERHEAD_BYTES + sum(
        _sqlite_backup_size_upper_bound(source) for source in databases.values()
    )
    for scoped_manifest in _active_manifests(universe_root, relative_manifest):
        required += _active_artifact_pair_bytes(universe_root, scoped_manifest)
        required += _active_artifact_pair_bytes(universe_root / "external-provider-cache", scoped_manifest)
    from deploy.scripts.municipal_backup import current_files
    required += sum(path.stat().st_size for path in current_files().values())
    # SQLite page accounting and copied file sizes are exact at observation
    # time; a small proportional allowance covers manifest and metadata growth.
    required += max(1024 * 1024, required // 20)
    require_free_space(
        backup_root,
        required_bytes=required,
        reserve_bytes=_backup_free_space_reserve_bytes(),
    )


def _active_manifests(root: Path, primary: Path) -> list[Path]:
    return sorted({primary, *(p.relative_to(root) for p in (root / 'active').glob('city-*.json'))})


def _validate_complete_backup_bundle(bundle: Path) -> None:
    """Re-read every declared byte before a temporary bundle becomes visible."""

    manifest_path = bundle / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        "grocery-beta-backup-v1"
    ):
        raise ValueError("backup completion manifest is invalid")
    rows = payload.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("backup completion manifest has no files")
    declared: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("backup completion manifest file entry is invalid")
        value = row.get("path")
        if not isinstance(value, str):
            raise TypeError("backup completion manifest file path is invalid")
        relative = Path(value)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("backup completion manifest path escapes its bundle")
        normalized = relative.as_posix()
        if normalized in declared:
            raise ValueError("backup completion manifest contains a duplicate path")
        declared.add(normalized)
        candidate = bundle / relative
        expected_bytes = row.get("bytes")
        expected_hash = row.get("sha256")
        if (
            not candidate.is_file()
            or isinstance(expected_bytes, bool)
            or not isinstance(expected_bytes, int)
            or candidate.stat().st_size != expected_bytes
            or not isinstance(expected_hash, str)
            or _sha256(candidate) != expected_hash
        ):
            raise ValueError(f"backup completion verification failed: {normalized}")
    actual = {
        path.relative_to(bundle).as_posix()
        for path in bundle.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual != declared:
        raise ValueError("backup completion manifest does not declare the exact bundle")


def _fingerprint_value(value: object) -> object:
    """Return a deterministic, non-secret representation for hashing only."""

    if isinstance(value, bytes):
        return {
            "blob_bytes": len(value),
            "blob_sha256": hashlib.sha256(value).hexdigest(),
        }
    if value is None or isinstance(value, (str, int, float)):
        return value
    raise TypeError(f"unsupported SQLite value type: {type(value).__name__}")


def _table_state(connection: sqlite3.Connection, table: str) -> dict[str, Any]:
    """Fingerprint one SQLite table without placing its values in the bundle manifest."""

    existing = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    if existing is None:
        return {"present": False, "rows": 0, "sha256": None}

    # ``table`` comes exclusively from the static allowlists above. Quoting it
    # still keeps this helper correct for future names containing punctuation.
    quoted_table = '"' + table.replace('"', '""') + '"'
    columns = connection.execute(f"PRAGMA table_info({quoted_table})").fetchall()
    if not columns:
        raise RuntimeError(f"unable to inspect SQLite table: {table}")
    column_names = [str(row[1]) for row in columns]
    primary_key = [
        str(row[1])
        for row in sorted(columns, key=lambda row: int(row[5]) or 2**31)
        if int(row[5]) > 0
    ]
    quoted_columns = [
        '"' + column.replace('"', '""') + '"' for column in column_names
    ]
    order_columns = primary_key or column_names
    quoted_order = [
        '"' + column.replace('"', '""') + '"' for column in order_columns
    ]
    query = (
        f"SELECT {', '.join(quoted_columns)} FROM {quoted_table} "
        f"ORDER BY {', '.join(quoted_order)}"
    )
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {"table": table, "columns": column_names},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    rows = 0
    for row in connection.execute(query):
        rows += 1
        digest.update(b"\n")
        digest.update(
            json.dumps(
                [_fingerprint_value(value) for value in row],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
    return {"present": True, "rows": rows, "sha256": digest.hexdigest()}


def database_state_inventory(
    database: Path,
    groups: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    """Create a content-free inventory for restore integrity verification."""

    connection = sqlite3.connect(
        f"file:{database.resolve().as_posix()}?mode=ro",
        uri=True,
    )
    try:
        result: dict[str, Any] = {}
        for group_name, table_names in groups.items():
            table_states = {
                table: _table_state(connection, table) for table in table_names
            }
            aggregate = hashlib.sha256(
                json.dumps(
                    table_states,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            result[group_name] = {
                "sha256": aggregate,
                "tables": table_states,
            }
        return result
    finally:
        connection.close()


def _active_artifact_state(root: Path, relative_manifest: Path) -> dict[str, Any] | None:
    """Describe one active pointer without changing any source timestamp."""

    manifest_path = root / relative_manifest
    if not manifest_path.is_file():
        return None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("active artifact manifest must be an object")
    artifact_value = payload.get("artifact_file")
    if not isinstance(artifact_value, str):
        raise TypeError("active artifact manifest lacks artifact_file")
    relative_artifact = PurePosixPath(artifact_value)
    if relative_artifact.is_absolute() or ".." in relative_artifact.parts:
        raise ValueError("active artifact path escapes its root")
    artifact_path = root / Path(*relative_artifact.parts)
    timestamps = {
        key: payload[key]
        for key in (
            "activated_at",
            "built_at",
            "captured_at",
            "oldest_observed_at",
        )
        if isinstance(payload.get(key), str)
    }
    snapshot_ids = payload.get("snapshot_ids")
    return {
        "manifest_path": relative_manifest.as_posix(),
        "manifest_sha256": _sha256(manifest_path),
        "artifact_path": artifact_value,
        "artifact_sha256": _sha256(artifact_path),
        "universe_id": payload.get("universe_id"),
        "snapshot_ids_sha256": hashlib.sha256(
            json.dumps(
                snapshot_ids if isinstance(snapshot_ids, list) else [],
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
        # Exact source timestamps are safe operational metadata. Keeping them
        # here makes timestamp fabrication detectable during a restore drill.
        "timestamps": timestamps,
    }


def _backup_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(f"required SQLite database is missing: {source.name}")
    _private_directory(destination.parent)
    source_connection = sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection, pages=2048, sleep=0.05)
        # SQLite backup copies the source journal mode too. A later read-only
        # inventory of a WAL-mode copy can leave undeclared -wal/-shm files in
        # the bundle. Finalize only this private destination as one file before
        # hashing it; never checkpoint or change the live source's journal mode.
        journal_mode = destination_connection.execute("PRAGMA journal_mode=DELETE").fetchone()
        if journal_mode is None or journal_mode[0] != "delete":
            raise RuntimeError("SQLite backup could not finalize a self-contained database")
        result = destination_connection.execute("PRAGMA integrity_check").fetchone()
        if result is None or result[0] != "ok":
            raise RuntimeError(f"SQLite backup integrity failed: {source.name}")
        if destination_connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
            raise RuntimeError(f"SQLite backup foreign-key check failed: {source.name}")
    finally:
        destination_connection.close()
        source_connection.close()
    _chmod_private(destination, directory=False)
    _fsync_file(destination)


def _copy_active_artifact(
    *,
    source_root: Path,
    relative_manifest: Path,
    destination_root: Path,
    bundle_prefix: Path,
) -> list[dict[str, Any]]:
    manifest_path = source_root / relative_manifest
    if not manifest_path.is_file():
        return []
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError("active artifact manifest must be an object")
    artifact_value = payload.get("artifact_file")
    if not isinstance(artifact_value, str):
        raise TypeError("active artifact manifest lacks artifact_file")
    relative_artifact = PurePosixPath(artifact_value)
    if relative_artifact.is_absolute() or ".." in relative_artifact.parts:
        raise ValueError("active artifact path escapes its root")
    artifact_path = source_root / Path(*relative_artifact.parts)
    if not artifact_path.is_file():
        raise FileNotFoundError("active artifact referenced by manifest is missing")
    expected = payload.get("artifact_sha256")
    actual = _sha256(artifact_path)
    if isinstance(expected, str) and expected != actual:
        raise ValueError("active artifact hash does not match its manifest")
    expected_bytes = payload.get("artifact_bytes")
    if isinstance(expected_bytes, int) and expected_bytes != artifact_path.stat().st_size:
        raise ValueError("active artifact size does not match its manifest")

    manifest_destination = destination_root / relative_manifest
    artifact_destination = destination_root / Path(*relative_artifact.parts)
    _private_directory(manifest_destination.parent)
    _private_directory(artifact_destination.parent)
    shutil.copy2(manifest_path, manifest_destination)
    shutil.copy2(artifact_path, artifact_destination)
    _chmod_private(manifest_destination, directory=False)
    _chmod_private(artifact_destination, directory=False)
    _fsync_file(manifest_destination)
    _fsync_file(artifact_destination)
    return [
        {
            "path": (bundle_prefix / relative_manifest).as_posix(),
            "sha256": _sha256(manifest_destination),
            "bytes": manifest_destination.stat().st_size,
        },
        {
            "path": (bundle_prefix / Path(*relative_artifact.parts)).as_posix(),
            "sha256": actual,
            "bytes": artifact_destination.stat().st_size,
        },
    ]


def _create_backup_locked(*, now: datetime | None = None) -> Path:
    timestamp = (now or datetime.now(UTC)).astimezone(UTC)
    backup_root = Path(os.getenv("BACKUP_ROOT", "/srv/app/var/backups")).resolve()
    retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))
    if not 1 <= retention_days <= 365:
        raise ValueError("BACKUP_RETENTION_DAYS must be between 1 and 365")
    bundle_name = timestamp.strftime("%Y%m%dT%H%M%SZ")
    final = backup_root / bundle_name
    temporary = backup_root / f".{bundle_name}.{uuid4().hex}.tmp"
    if final.exists():
        raise FileExistsError(f"backup bundle already exists: {bundle_name}")
    _private_directory(backup_root)
    universe_root = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).resolve()
    city = " ".join(os.getenv("PRICE_UNIVERSE_CITY", "Lund").casefold().split())
    city_slug = _SAFE_SCOPE_PART.sub("-", city).strip("-")
    if not city_slug:
        raise ValueError("PRICE_UNIVERSE_CITY cannot form a safe backup scope")
    relative_manifest = Path(f"active/city-{city_slug}.json")
    # Rotation must not depend on being able to allocate another full copy.
    # The maintenance routine preserves two checksum-verified recovery bundles.
    from deploy.scripts.storage_maintenance import run_locked
    run_locked(now=timestamp, apply=True)
    _preflight_backup_space(backup_root, relative_manifest)
    temporary.mkdir(mode=0o700, exist_ok=False)
    _chmod_private(temporary, directory=True)
    files: list[dict[str, Any]] = []
    try:
        for relative, source in configured_database_paths().items():
            destination = temporary / relative
            _backup_database(source, destination)
            files.append(
                {
                    "path": relative,
                    "sha256": _sha256(destination),
                    "bytes": destination.stat().st_size,
                }
            )

        manifests = _active_manifests(universe_root, relative_manifest)
        for scoped_manifest in manifests:
            primary_files = _copy_active_artifact(
                source_root=universe_root,
                relative_manifest=scoped_manifest,
                destination_root=temporary / "price_universes",
                bundle_prefix=Path("price_universes"),
            )
            if not primary_files:
                raise FileNotFoundError("required active PriceUniverse manifest is missing")
            files.extend(primary_files)
            files.extend(_copy_active_artifact(
                source_root=universe_root / "external-provider-cache",
                relative_manifest=scoped_manifest,
                destination_root=temporary / "price_universes/external-provider-cache",
                bundle_prefix=Path("price_universes/external-provider-cache")))
        from deploy.scripts.municipal_backup import current_files
        for relative, source in current_files().items():
            destination = temporary / relative
            _private_directory(destination.parent)
            shutil.copy2(source, destination)
            _chmod_private(destination, directory=False)
            _fsync_file(destination)
            digest = _sha256(destination)
            if digest != _sha256(source):
                raise ValueError('municipal recovery file changed during locked backup')
            files.append({'path': relative, 'sha256': digest, 'bytes': destination.stat().st_size})
        # Two scopes may refer to the same immutable content-addressed blob.
        files = list({row['path']: row for row in files}.values())
        active_manifest_path = universe_root / relative_manifest
        active_manifest = (
            json.loads(active_manifest_path.read_text(encoding="utf-8"))
            if active_manifest_path.is_file()
            else {}
        )
        grocery_backup = temporary / "grocery/grocery_data.sqlite"
        connection = sqlite3.connect(grocery_backup)
        try:
            try:
                revision_row = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()
            except sqlite3.OperationalError:
                revision_row = None
        finally:
            connection.close()
        state_integrity = {
            "grocery_database": database_state_inventory(
                grocery_backup,
                _GROCERY_STATE_TABLE_GROUPS,
            ),
            "plan_database": database_state_inventory(
                temporary / "plans/consumer_plans.sqlite3",
                _PLAN_STATE_TABLE_GROUPS,
            ),
            "price_universe": _active_artifact_state(
                temporary / "price_universes",
                relative_manifest,
            ),
            "external_provider_lkg": _active_artifact_state(
                temporary / "price_universes/external-provider-cache",
                relative_manifest,
            ),
        }
        state_integrity['municipal_price_universes'] = {
            p.as_posix(): _active_artifact_state(temporary / 'price_universes', p)
            for p in manifests}
        manifest = {
            "schema_version": "grocery-beta-backup-v1",
            "recovery_scope_version": 2,
            "created_at": timestamp.isoformat(),
            "app_version": os.getenv("APP_VERSION", "unknown"),
            "build_id": os.getenv("BUILD_ID", "unknown"),
            "alembic_revision": revision_row[0] if revision_row else None,
            "price_universe_id": (
                active_manifest.get("universe_id")
                if isinstance(active_manifest, dict)
                else None
            ),
            "state_integrity": state_integrity,
            "files": sorted(files, key=lambda row: str(row["path"])),
        }
        from grocery_data.app.services.municipal_rollout import registry_path
        registry = registry_path()
        manifest['municipal_registry_sha256'] = _sha256(registry) if registry.exists() else None
        bundle_manifest = temporary / "manifest.json"
        atomic_write_bytes(
            bundle_manifest,
            json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            ),
            validator=lambda candidate: json.loads(candidate.read_bytes()),
        )
        _chmod_private(bundle_manifest, directory=False)
        _validate_complete_backup_bundle(temporary)
        _secure_tree(temporary)
        _fsync_tree(temporary)
        os.replace(temporary, final)
        try:
            directory = os.open(backup_root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except OSError:
            # Directory fsync is unavailable on some developer platforms. The
            # production Linux path supports it; file hashes still catch a
            # torn/non-durable rehearsal copy elsewhere.
            pass
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise

    from deploy.scripts.storage_maintenance import maintain_backups
    maintain_backups(backup_root, now=timestamp, apply=True)
    return final


def create_backup(*, now: datetime | None = None) -> Path:
    databases = configured_database_paths()
    universe_root = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).resolve()
    lock = RefreshRunLock(
        production_refresh_lock_path(
            databases["grocery/grocery_data.sqlite"],
            universe_root,
        )
    )
    lock.acquire()
    try:
        return _create_backup_locked(now=now)
    finally:
        lock.release()


def main() -> int:
    from deploy.scripts.backup_schedule import record
    try:
        bundle = create_backup()
    except Exception as exc:  # noqa: BLE001 - sanitized operational boundary
        failure: dict[str, Any] = {
            "status": "failed",
            "error_type": type(exc).__name__,
        }
        if isinstance(exc, InsufficientStorageError):
            failure.update(exc.status())
        elif isinstance(exc, OSError) and exc.errno == errno.ENOSPC:
            failure["reason"] = "storage_write_failed"
        from grocery_data.app.services.manual_refresh_operations import RefreshAlreadyRunningError
        if isinstance(exc, RefreshAlreadyRunningError):
            failure.update(status='deferred', reason='operation_lock_held')
        record(**failure)
        print(json.dumps(failure, sort_keys=True))
        return 1
    record('complete', bundle=bundle.name, completed_at=datetime.now(UTC).isoformat())
    print(json.dumps({"status": "complete", "bundle": bundle.name}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
