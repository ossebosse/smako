"""Run one bounded Coop Online Syd recovery through the managed refresh path."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from grocery_data.app.config import load_repository_dotenv
from grocery_data.app.services.coop_refresh_configuration import (
    COOP_VERIFIED_ONLINE_CONTEXT_ID,
    assess_coop_refresh_configuration,
    require_coop_refresh_configuration,
)
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.freshness import (
    FreshnessPolicy,
    FreshnessState,
    assess_freshness,
)
from grocery_data.app.services.manual_refresh_operations import (
    RefreshAlreadyRunningError,
)

try:
    from deploy.scripts import run_daily_refresh as daily_runner
except ImportError:  # Direct execution inside the production image.
    import run_daily_refresh as daily_runner  # type: ignore[no-redef]


def build_source_retry_command() -> list[str]:
    city = os.getenv("REFRESH_CITY", "Lund").strip() or "Lund"
    if city.casefold() != "lund":
        raise ValueError("the verified Coop 730400 recovery scope is Lund only")
    postal_code = os.getenv("REFRESH_POSTAL_CODE", "22350").strip()
    if len(postal_code) != 5 or not postal_code.isdigit():
        raise ValueError("REFRESH_POSTAL_CODE must contain five digits")
    universe_root = daily_runner._required("PRICE_UNIVERSE_CACHE_ROOT")
    report_dir = os.getenv(
        "REFRESH_REPORT_DIR", "/srv/app/var/reports/refresh"
    ).strip()
    return [
        sys.executable,
        "-m",
        "grocery_data",
        "daily-refresh",
        "--city",
        city,
        "--postal-code",
        f"{city}={postal_code}",
        "--chain",
        "coop",
        "--context-store-id",
        COOP_VERIFIED_ONLINE_CONTEXT_ID,
        "--no-external-refresh",
        "--price-universe-cache-root",
        universe_root,
        "--report-dir",
        report_dir,
        "--format",
        "json",
    ]


def _write_status(payload: dict[str, Any]) -> None:
    destination = Path(
        os.getenv(
            "SOURCE_RETRY_STATUS_PATH",
            "/srv/app/var/reports/operations/source-retry-status.json",
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


def _latest_full_report() -> dict[str, Any] | None:
    directory = Path(
        os.getenv("REFRESH_REPORT_DIR", "/srv/app/var/reports/refresh")
    )
    for path in sorted(directory.glob("refresh-report-*.json"), reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("run_type") == "daily_refresh":
            return payload
    return None


def _coop_full_row(report: dict[str, Any] | None) -> dict[str, Any] | None:
    collection = report.get("own_collection") if report else None
    rows = collection.get("results") if isinstance(collection, dict) else None
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, dict):
            continue
        if (
            row.get("chain") == "coop"
            and str(row.get("context_store_id") or "")
            == COOP_VERIFIED_ONLINE_CONTEXT_ID
            and "basket" in {str(role).casefold() for role in row.get("roles") or ()}
        ):
            return row
    return None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _row_observed_at(
    row: dict[str, Any],
    report: dict[str, Any],
) -> datetime | None:
    observed = _timestamp(
        row.get("active_snapshot_observed_at") or row.get("observed_at")
    )
    if observed is not None:
        return observed
    age = row.get("active_snapshot_age_hours")
    completed = _timestamp(report.get("completed_at") or report.get("started_at"))
    if (
        completed is not None
        and isinstance(age, (int, float))
        and not isinstance(age, bool)
        and age >= 0
    ):
        return completed - timedelta(hours=float(age))
    return None


def retry_needed(
    report: dict[str, Any] | None,
    *,
    now: datetime | None = None,
) -> tuple[bool, str]:
    row = _coop_full_row(report)
    if row is None:
        return True, "coop_full_catalog_status_missing"
    if row.get("status") != "healthy" or not bool(row.get("promoted")):
        return True, "coop_full_catalog_not_refreshed"
    universes = report.get("price_universes") if report else None
    if isinstance(universes, dict):
        universes = [universes]
    if isinstance(universes, list) and any(
        isinstance(universe, dict)
        and bool(universe.get("build_error"))
        and bool(universe.get("active_unchanged"))
        for universe in universes
    ):
        return True, "price_universe_rebuild_required"
    summary = report.get("summary") if report else None
    if isinstance(summary, dict) and summary.get("exit_code") == 1:
        return True, "daily_refresh_failed"
    evaluated_at = now or datetime.now(tz=UTC)
    warning = float(os.getenv("PRICE_AGE_WARNING_HOURS", "36"))
    stale = float(os.getenv("MAX_PRICE_AGE_HOURS", "48"))
    freshness = assess_freshness(
        _row_observed_at(row, report or {}),
        now=evaluated_at,
        policy=FreshnessPolicy(
            warning_age_hours=warning,
            stale_age_hours=stale,
        ),
    )
    if freshness.state in {
        FreshnessState.AGING,
        FreshnessState.STALE,
        FreshnessState.BROKEN,
    }:
        return True, f"coop_full_catalog_{freshness.state.value}"
    if bool(row.get("retry_required")):
        return True, "daily_refresh_requested_early_retry"
    return False, "coop_full_catalog_fresh"


def _read_status(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def full_runner_failed_after_report(report: dict[str, Any] | None) -> bool:
    status = _read_status(
        Path(
            os.getenv(
                "REFRESH_RUNNER_STATUS_PATH",
                "/srv/app/var/reports/operations/refresh-runner-status.json",
            )
        )
    )
    if not status or status.get("schema_version") != "production-refresh-runner-v1":
        return False
    exit_code = status.get("exit_code")
    if exit_code in {0, 2}:
        return False
    runner_at = _timestamp(status.get("started_at"))
    report_at = _timestamp(
        (report or {}).get("completed_at") or (report or {}).get("started_at")
    )
    return bool(runner_at is not None and (report_at is None or runner_at > report_at))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="operator acceptance only: execute one independent collection even if fresh",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    # Local operator runs reuse the repository's existing uncommitted runtime
    # configuration. Production sets PYTHON_DOTENV_DISABLED=true and receives
    # the same names from Compose.
    load_repository_dotenv()
    started_at = datetime.now(tz=UTC)
    configuration = assess_coop_refresh_configuration(os.environ)
    try:
        require_coop_refresh_configuration(os.environ)
    except Exception as exc:  # noqa: BLE001 - sanitized operational boundary
        _write_status(
            {
                "schema_version": "source-retry-runner-v1",
                "run_kind": "coop_source_retry",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(tz=UTC).isoformat(),
                "status": "configuration_error",
                "reason": configuration.diagnostic_code,
                "configuration": configuration.sanitized_report(),
                "error_type": type(exc).__name__,
                "exit_code": 1,
            }
        )
        return 1
    latest_report = _latest_full_report()
    needed, reason = retry_needed(latest_report)
    if full_runner_failed_after_report(latest_report):
        needed, reason = True, "latest_daily_refresh_aborted"
    if not args.force and not needed:
        _write_status(
            {
                "schema_version": "source-retry-runner-v1",
                "run_kind": "coop_source_retry",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(tz=UTC).isoformat(),
                "status": "not_required",
                "reason": reason,
                "configuration": configuration.sanitized_report(),
                "exit_code": 0,
            }
        )
        return 0
    operations_lock = daily_runner._operations_lock()
    try:
        operations_lock.acquire()
    except RefreshAlreadyRunningError:
        _write_status(
            {
                "schema_version": "source-retry-runner-v1",
                "run_kind": "coop_source_retry",
                "started_at": started_at.isoformat(),
                "completed_at": datetime.now(tz=UTC).isoformat(),
                "status": "skipped_operation_lock_held",
                "reason": "operation_lock_held",
                "configuration": configuration.sanitized_report(),
                "exit_code": 2,
            }
        )
        return 2
    try:
        return daily_runner._run_locked(
            operations_lock,
            started_at=started_at,
            command=build_source_retry_command(),
            run_kind="coop_source_retry",
            status_writer=_write_status,
        )
    finally:
        operations_lock.release()


if __name__ == "__main__":
    raise SystemExit(main())
