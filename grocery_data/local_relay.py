"""Daily local orchestration of the existing validated source relay contract."""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic, sleep
from types import SimpleNamespace
from uuid import uuid4
from zoneinfo import ZoneInfo

from grocery_data import source_cli
from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.manual_refresh_operations import (
    RefreshAlreadyRunningError,
    RefreshRunLock,
)
from grocery_data.app.services.source_artifact import verify_source_artifact


def remote_activate(digest: str):
    result = subprocess.run(
        [
            "ssh",
            "-oBatchMode=yes",
            "-oConnectTimeout=15",
            "-oServerAliveInterval=30",
            "-oServerAliveCountMax=3",
            "smako",
            "docker",
            "exec",
            "--user",
            "10001:10001",
            "smako-scheduler-1",
            "python",
            "-m",
            "grocery_data.source_cli",
            "import",
            f"/srv/app/var/raw_snapshots/source-inbox/willys/{digest}.smako-source",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=1800,
    )
    value = json.loads(result.stdout.strip().splitlines()[-1])
    if value.get("activation") not in {"normal_managed_refresh", "already_active"}:
        raise ValueError("server did not confirm active source")
    return {k: value[k] for k in ("activation", "snapshot_id", "universe_id") if k in value}


def transient_retry(action, log, *, delay=sleep):
    for attempt in range(3):
        try:
            return action()
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
            transient = isinstance(exc, subprocess.TimeoutExpired) or exc.returncode == 255
            log(
                "transport_failure",
                attempt=attempt + 1,
                error_type=type(exc).__name__,
                exit_code=exc.returncode
                if isinstance(exc, subprocess.CalledProcessError)
                else None,
                transient=transient,
            )
            if not transient or attempt == 2:
                raise
            delay((30, 120)[attempt])


def run(
    workspace: Path,
    *,
    collect=source_cli.collect,
    push=source_cli.push,
    activate=remote_activate,
    now=None,
    delay=sleep,
):
    now = now or datetime.now(UTC)
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    logs = workspace / "logs"
    logs.mkdir(exist_ok=True)
    log_path = logs / f"{now:%Y%m%dT%H%M%SZ}-{uuid4().hex}.jsonl"
    started = monotonic()

    def log(event, **fields):
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"at": datetime.now(UTC).isoformat(), "event": event, **fields}, default=str
                )
                + "\n"
            )

    log(
        "task_start",
        expected_daily_time="01:30",
        schedule_timezone="Europe/Stockholm",
        invocation_kind="scheduled_or_manual_not_inferred",
    )
    try:
        with RefreshRunLock(workspace / "local-workflow.lock"):
            for old in sorted(logs.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)[
                29:
            ]:
                if old != log_path and old.is_file() and not old.is_symlink():
                    old.unlink()
            receipt_path = workspace / "last-success.json"
            receipt = json.loads(receipt_path.read_bytes()) if receipt_path.exists() else {}
            day = now.astimezone(ZoneInfo("Europe/Stockholm")).date().isoformat()
            if receipt.get("collection_day") == day:
                log("already_delivered", sha256_prefix=receipt["sha256"][:12])
                return 0
            candidate = None
            # Resume complete unpublished runs; never restamp old observations.
            for path in sorted(
                (workspace / "completed").glob("*.smako-source"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            ):
                try:
                    verified = verify_source_artifact(path, now=now)
                except (ValueError, OSError):
                    log("pending_validation_rejected", artifact_file=path.name)
                    continue
                observed = verified.manifest.observed_from
                if verified.artifact_sha256 != receipt.get("sha256") and now - observed < timedelta(
                    hours=24
                ):
                    candidate = path
                    break
            if candidate is None:
                log("collection_start")
                result = asyncio.run(collect(SimpleNamespace(workspace=workspace)))
                if result["status"] != "complete":
                    raise ValueError("collection did not complete")
                candidate = Path(result["artifact"])
                log(
                    "collection_complete",
                    requests=result["requests"],
                    rows=result["rows"],
                    runtime_seconds=result.get("runtime_seconds"),
                )
            verified = verify_source_artifact(candidate)
            digest = verified.artifact_sha256
            log(
                "validation_pass",
                sha256_prefix=digest[:12],
                artifact_file=candidate.name,
                observed_from=verified.manifest.observed_from,
                bytes=candidate.stat().st_size,
            )
            transfer_start = monotonic()
            transient_retry(
                lambda: push(SimpleNamespace(artifact=candidate, host="smako")), log, delay=delay
            )
            log("upload_pass", seconds=round(monotonic() - transfer_start, 3))
            import_start = monotonic()
            log("server_import_start")
            server = transient_retry(lambda: activate(digest), log, delay=delay)
            log("server_activation_pass", seconds=round(monotonic() - import_start, 3), **server)
            observed = verified.manifest.observed_from
            receipt = {
                "sha256": digest,
                "artifact": str(candidate),
                "collection_day": observed.astimezone(ZoneInfo("Europe/Stockholm"))
                .date()
                .isoformat(),
                "observed_from": observed.isoformat(),
                "completed_at": datetime.now(UTC).isoformat(),
                "server": server,
            }
            atomic_write_bytes(
                receipt_path,
                json.dumps(receipt).encode(),
                validator=lambda p: json.loads(p.read_bytes()),
            )
            log("task_success", sha256_prefix=digest[:12])
            return 0
    except RefreshAlreadyRunningError:
        log("already_running")
        return 0
    except Exception as exc:  # noqa: BLE001 - redact at the operator boundary
        log("task_failed", error_type=type(exc).__name__)
        return 1
    finally:
        log("task_end", seconds=round(monotonic() - started, 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    return run(parser.parse_args().workspace)


if __name__ == "__main__":
    raise SystemExit(main())
