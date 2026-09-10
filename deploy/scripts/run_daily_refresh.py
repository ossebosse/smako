"""Run the existing managed refresh once, then hot-swap the serving runtime.

This file is orchestration only.  Collection, candidate validation, content-
addressed storage and atomic/LKG activation remain owned by ``daily-refresh``.
The serving process is asked to load the already activated, hash-verified
manifest only after the CLI returned a usable result (exit 0 or degraded 2).
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import make_url

from grocery_data.app.services.coop_refresh_configuration import (
    assess_coop_refresh_configuration,
)
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.manual_refresh_operations import (
    REFRESH_PARENT_LOCK_NONCE_ENV,
    RefreshAlreadyRunningError,
    RefreshRunLock,
    production_refresh_lock_path,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)


class RuntimeReloadUnavailable(RuntimeError):
    """The serving process could not be reached after disk activation."""


class RuntimeReloadRejected(RuntimeError):
    """The serving process reached the endpoint but rejected the candidate."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"required production setting is missing: {name}")
    return value


def build_refresh_command() -> list[str]:
    city = os.getenv("REFRESH_CITY", "Lund").strip() or "Lund"
    postal_code = os.getenv("REFRESH_POSTAL_CODE", "22350").strip()
    if len(postal_code) != 5 or not postal_code.isdigit():
        raise ValueError("REFRESH_POSTAL_CODE must contain five digits")
    report_dir = os.getenv(
        "REFRESH_REPORT_DIR",
        "/srv/app/var/reports/refresh",
    ).strip()
    universe_root = _required("PRICE_UNIVERSE_CACHE_ROOT")
    return [
        sys.executable,
        "-m",
        "grocery_data",
        "daily-refresh",
        "--city",
        city,
        "--postal-code",
        f"{city}={postal_code}",
        "--price-universe-cache-root",
        universe_root,
        "--report-dir",
        report_dir,
        "--format",
        "json",
    ]


def _reload_runtime() -> dict[str, Any]:
    try:
        base_url = _required("INTERNAL_APP_BASE_URL").rstrip("/")
        token = _required("BETA_ADMIN_TOKEN")
    except RuntimeError as exc:
        raise RuntimeReloadUnavailable("RuntimeReloadConfigurationMissing") from exc
    request = urllib.request.Request(
        f"{base_url}/api/admin/reload-price-universe",
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Request-ID": f"scheduled-refresh-{uuid4().hex}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeReloadRejected(type(exc).__name__) from None
    except (OSError, urllib.error.URLError) as exc:
        raise RuntimeReloadUnavailable(type(exc).__name__) from None
    except (UnicodeError, ValueError) as exc:
        raise RuntimeReloadRejected(type(exc).__name__) from None
    if not isinstance(payload, dict):
        raise RuntimeReloadRejected("NonObjectResponse")
    required = {"old_price_universe_id", "new_price_universe_id", "changed"}
    if not required.issubset(payload):
        raise RuntimeReloadRejected("IncompleteResponse")
    return {
        key: payload.get(key)
        for key in (
            "status",
            "old_price_universe_id",
            "new_price_universe_id",
            "changed",
            "pricing_projection",
            "plan_prewarm",
        )
        if key in payload
    }


def _write_status(payload: dict[str, Any]) -> None:
    destination = Path(
        os.getenv(
            "REFRESH_RUNNER_STATUS_PATH",
            "/srv/app/var/reports/operations/refresh-runner-status.json",
        )
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    atomic_write_bytes(
        destination,
        encoded,
        validator=lambda candidate: json.loads(candidate.read_bytes()),
    )


def _artifact_store() -> PreparedUniverseArtifactStore:
    return PreparedUniverseArtifactStore(Path(_required("PRICE_UNIVERSE_CACHE_ROOT")))


def _operations_lock() -> RefreshRunLock:
    database_url = make_url(_required("GROCERY_DATABASE_URL"))
    if database_url.get_backend_name() != "sqlite" or not database_url.database:
        raise RuntimeError("production refresh serialization requires file-backed SQLite")
    database = Path(database_url.database).expanduser().resolve(strict=True)
    universe_root = Path(_required("PRICE_UNIVERSE_CACHE_ROOT"))
    return RefreshRunLock(production_refresh_lock_path(database, universe_root))


def _active_disk_universe_id(
    store: PreparedUniverseArtifactStore,
    *,
    city: str,
) -> str | None:
    """Return only the validated active manifest identity when available."""

    reader = getattr(store, "read_active", None)
    if not callable(reader):
        return None
    try:
        manifest = reader(city)
    except (OSError, ValueError):
        return None
    value = getattr(manifest, "universe_id", None)
    return value if isinstance(value, str) and value else None


def _restore_restart_lkg(
    store: PreparedUniverseArtifactStore,
    *,
    city: str,
    previous: bytes | None,
    promoted: bytes | None,
) -> dict[str, Any]:
    """Restore the pre-refresh restart pointer, leaving candidate bytes intact."""

    store.restore_active_manifest(
        city,
        previous,
        expected_current=promoted,
    )
    return {
        "status": "restored_previous" if previous is not None else "removed_first_candidate",
        "candidate_artifact_retained": True,
    }


def _run_locked(
    operations_lock: RefreshRunLock,
    *,
    started_at: datetime,
    command: list[str] | None = None,
    run_kind: str = "daily_refresh",
    status_writer: Callable[[dict[str, Any]], None] | None = None,
) -> int:
    command = command or build_refresh_command()
    timeout_seconds = int(os.getenv("REFRESH_TIMEOUT_SECONDS", "7200"))
    if not 300 <= timeout_seconds <= 7200:
        raise ValueError("REFRESH_TIMEOUT_SECONDS must be between 300 and 7200")
    city = command[command.index("--city") + 1]
    artifact_store = _artifact_store()
    previous_manifest = artifact_store.active_manifest_bytes(city)
    previous_manifest_state = "missing"
    if previous_manifest is not None:
        # A corrupt pointer is not an LKG, but it must not block refresh from
        # repairing first boot. Never restore it after a later reload rejection.
        try:
            artifact_store.resolve_active_artifact(city, verify_hash=True)
            previous_manifest_state = "verified"
        except (OSError, ValueError):
            previous_manifest = None
            previous_manifest_state = "invalid"
    status: dict[str, Any] = {
        "schema_version": (
            "source-retry-runner-v1"
            if run_kind == "coop_source_retry"
            else "production-refresh-runner-v1"
        ),
        "started_at": started_at.isoformat(),
        "city": city,
        "run_kind": run_kind,
        "coop_source_configuration": assess_coop_refresh_configuration(
            os.environ
        ).sanitized_report(),
        "previous_restart_manifest": previous_manifest_state,
    }
    try:
        if operations_lock.info is None:
            raise RuntimeError("outer refresh operation lock is not held")
        if run_kind == "daily_refresh" and os.getenv("WILLYS_COLLECTION_LOCATION") == "LOCAL_RELAY":
            from grocery_data.app.config import GroceryDataSettings
            from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
            from grocery_data.app.services.source_artifact import import_source_inbox
            from grocery_data.app.storage import create_database_engine, create_session_factory

            relay_settings = GroceryDataSettings.from_env()
            relay_engine = create_database_engine(relay_settings.database_url)
            try:
                status["source_relay_imports"] = asyncio.run(
                    import_source_inbox(
                        create_session_factory(relay_engine),
                        FilesystemRawSnapshotStore(relay_settings.raw_snapshot_root),
                        Path(
                            os.getenv(
                                "SOURCE_RELAY_INBOX",
                                "/srv/app/var/raw_snapshots/source-inbox/willys",
                            )
                        ),
                    )
                )
            except Exception as exc:  # noqa: BLE001 - isolate asynchronous source arrivals
                status["source_relay_imports"] = [
                    {"status": "failed", "error_type": type(exc).__name__}
                ]
            finally:
                relay_engine.dispose()
        child_environment = dict(os.environ)
        child_environment[REFRESH_PARENT_LOCK_NONCE_ENV] = operations_lock.info.owner_nonce
        completed = subprocess.run(
            command,
            check=False,
            timeout=timeout_seconds,
            env=child_environment,
        )
        status["refresh_exit_code"] = completed.returncode
        exit_code = completed.returncode
        if completed.returncode in {0, 2}:
            promoted_manifest = artifact_store.active_manifest_bytes(city)
            try:
                status["runtime_reload"] = _reload_runtime()
            except RuntimeReloadUnavailable as exc:
                # Disk activation is valid and may be the only way a crash-looping
                # app can recover on restart. Do not restore the older pointer.
                status["runtime_reload"] = {
                    "status": "deferred",
                    "reason": "app_unavailable",
                    "error_type": type(exc).__name__,
                }
                disk_universe_id = _active_disk_universe_id(
                    artifact_store,
                    city=city,
                )
                if disk_universe_id is not None:
                    status["runtime_reload"]["disk_price_universe_id"] = disk_universe_id
                status["disk_manifest_rollback"] = {
                    "status": "not_attempted",
                    "reason": "candidate_retained_for_restart",
                }
                exit_code = 2
            except RuntimeReloadRejected as exc:
                status["runtime_reload"] = {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                }
                try:
                    status["disk_manifest_rollback"] = _restore_restart_lkg(
                        artifact_store,
                        city=city,
                        previous=previous_manifest,
                        promoted=promoted_manifest,
                    )
                except Exception as rollback_exc:  # noqa: BLE001 - report class only
                    status["disk_manifest_rollback"] = {
                        "status": "failed",
                        "error_type": type(rollback_exc).__name__,
                    }
                exit_code = 1
        else:
            status["runtime_reload"] = {
                "status": "not_attempted",
                "reason": "refresh_not_usable",
            }
    except Exception as exc:  # noqa: BLE001 - outer operational boundary
        # Preserve the server's in-memory LKG and publish only an allowlisted
        # error class. No exception text is retained.
        exit_code = 1
        status.update(
            {
                "refresh_exit_code": None,
                "runtime_reload": {"status": "not_attempted"},
                "error_type": type(exc).__name__,
            }
        )
    status["completed_at"] = datetime.now(UTC).isoformat()
    status["exit_code"] = exit_code
    status["status"] = "complete" if exit_code == 0 else "degraded" if exit_code == 2 else "failed"
    (status_writer or _write_status)(status)
    return exit_code


def main() -> int:
    started_at = datetime.now(UTC)
    city = os.getenv("REFRESH_CITY", "Lund").strip() or "Lund"
    operations_lock = _operations_lock()
    try:
        operations_lock.acquire()
    except RefreshAlreadyRunningError:
        completed_at = datetime.now(UTC)
        _write_status(
            {
                "schema_version": "production-refresh-runner-v1",
                "started_at": started_at.isoformat(),
                "completed_at": completed_at.isoformat(),
                "city": city,
                "refresh_exit_code": None,
                "runtime_reload": {
                    "status": "not_attempted",
                    "reason": "operation_lock_held",
                },
                "status": "degraded",
                "exit_code": 2,
            }
        )
        return 2
    try:
        return _run_locked(operations_lock, started_at=started_at)
    finally:
        operations_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
