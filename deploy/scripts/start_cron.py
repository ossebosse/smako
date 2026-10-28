"""Configure Debian cron from validated deployment settings and exec it.

Scheduling lives in a dedicated container.  The web process contains no timer,
loop or provider code.  Cron receives an ephemeral, shell-escaped copy of the
container environment so Docker secrets are never written to a durable volume.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from grocery_data.app.services.coop_refresh_configuration import (
    assess_coop_refresh_configuration,
)

_CRON_FIELD = re.compile(r"^[0-9*/?,\-]+$")


def _coop_preflight_event(environment: dict[str, str]) -> dict[str, object] | None:
    configuration = assess_coop_refresh_configuration(environment)
    if configuration.valid:
        return None
    return {
        "event": "scheduler_configuration_warning",
        "severity": "error",
        **configuration.sanitized_report(),
    }


def _schedule(name: str, default: str) -> str:
    value = os.getenv(name, default).strip()
    fields = value.split()
    if len(fields) != 5 or any(not _CRON_FIELD.fullmatch(field) for field in fields):
        raise ValueError(f"{name} must contain exactly five safe cron fields")
    return " ".join(fields)


def _validate_display_schedule(
    cron: str,
    display_schedule: str,
    *,
    name: str,
) -> None:
    """Prevent admin freshness projection from drifting from actual cron."""

    fields = cron.split()
    if (
        len(fields) != 5
        or not fields[0].isdigit()
        or not fields[1].isdigit()
        or fields[2:4] != ["*", "*"]
        or fields[4] not in {"*", "1,4"}
    ):
        raise ValueError(f"{name} must correspond to one fixed daily clock time")
    parts = display_schedule.strip().split()
    expected_days = [] if fields[4] == "*" else ["Mon,Thu"]
    if len(parts) != 2 + len(expected_days) or parts[1] != "Europe/Stockholm" or parts[2:] != expected_days:
        raise ValueError(f"{name} must use HH:MM Europe/Stockholm")
    clock = parts[0].split(":")
    if len(clock) != 2 or not all(value.isdigit() for value in clock):
        raise ValueError(f"{name} must use HH:MM Europe/Stockholm")
    hour, minute = (int(value) for value in clock)
    if hour > 23 or minute > 59:
        raise ValueError(f"{name} must contain a valid clock time")
    cron_minute, cron_hour = (int(value) for value in fields[:2])
    if cron_minute != minute or cron_hour != hour:
        raise ValueError(f"{name} must match the configured cron expression")


def scheduled_jobs() -> tuple[tuple[str, str], ...]:
    """Backups remain scheduled even when source collection is blocked."""
    jobs = [("DAILY_BACKUP_CRON", "backup_sqlite.py")]
    if os.getenv("DEMAND_REFRESH_ENABLED", "false").casefold() == "true":
        return tuple(jobs + [("DEMAND_REFRESH_CRON", "run_daily_refresh.py")])
    for setting, schedule, script in (
        ("DAILY_REFRESH_ENABLED", "DAILY_REFRESH_CRON", "run_daily_refresh.py"),
        ("COOP_RETRY_ENABLED", "COOP_RETRY_CRON", "run_source_retry.py"),
    ):
        value = os.getenv(setting, "true").strip().lower()
        if value not in {"true", "false"}:
            raise ValueError(f"{setting} must be true or false")
        if value == "true":
            jobs.append((schedule, script))
    return tuple(jobs)


def _write_environment(path: Path) -> None:
    excluded = {"PWD", "OLDPWD", "SHLVL", "_"}
    lines = [
        f"export {name}={shlex.quote(value)}"
        for name, value in sorted(os.environ.items())
        if name not in excluded and name.isidentifier()
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chown(path, 0, 10001)
    path.chmod(0o640)


def main() -> None:
    # Configuration mistakes must be conspicuous, but must not stop backups or
    # healthy providers from running.  The managed refresh will classify Coop
    # against its persisted LKG and return DEGRADED or FAILED as appropriate.
    coop_warning = _coop_preflight_event(dict(os.environ))
    if coop_warning is not None:
        print(
            json.dumps(
                coop_warning,
                ensure_ascii=False,
                sort_keys=True,
            ),
            flush=True,
        )
    refresh = _schedule("DAILY_REFRESH_CRON", "17 03 * * *")
    coop_retry = _schedule("COOP_RETRY_CRON", "17 06 * * *")
    backup = _schedule("DAILY_BACKUP_CRON", "47 02 * * *")
    _validate_display_schedule(
        refresh,
        os.getenv("DAILY_REFRESH_SCHEDULE", "03:17 Europe/Stockholm"),
        name="DAILY_REFRESH_SCHEDULE",
    )
    jobs = scheduled_jobs()
    if any(name == 'COOP_RETRY_CRON' for name, _ in jobs):
        _validate_display_schedule(
            coop_retry,
            os.getenv("COOP_RETRY_SCHEDULE", "06:17 Europe/Stockholm"),
            name="COOP_RETRY_SCHEDULE",
        )
    environment_path = Path("/run/grocery-beta-environment")
    _write_environment(environment_path)

    cron_file = Path("/etc/cron.d/grocery-beta")
    command_prefix = (
        ". /run/grocery-beta-environment && cd /srv/app && "
    )
    schedules = {"DAILY_REFRESH_CRON": refresh, "COOP_RETRY_CRON": coop_retry,
                 "DAILY_BACKUP_CRON": backup,
                 "DEMAND_REFRESH_CRON": _schedule("DEMAND_REFRESH_CRON", "*/15 * * * *")}
    cron_file.write_text(
        "SHELL=/bin/sh\n"
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\n"
        + "".join(
            # Cron opens Docker's root-owned output pipe before dropping to
            # app. Otherwise shell redirection fails before the job can run.
            f"{schedules[name]} root {command_prefix}runuser -u app -- "
            f"python deploy/scripts/{script} "
            ">> /proc/1/fd/1 2>> /proc/1/fd/2\n"
            for name, script in jobs
        ), encoding="utf-8",
    )
    cron_file.chmod(0o644)
    # Installation/update starts the scheduler through this same entry point.
    # Use the ordinary operation lease and UID; a busy lease defers cleanup to
    # the existing backup/refresh job, never a competing timer or root deletion.
    maintenance = subprocess.run(
        ["runuser", "-u", "app", "--", "python", "-m",
         "deploy.scripts.storage_maintenance", "--apply"], check=False)
    if maintenance.returncode:
        print(json.dumps({"event": "storage_maintenance_deferred",
                          "exit_code": maintenance.returncode}), flush=True)
    os.execv("/usr/sbin/cron", ["cron", "-f"])


if __name__ == "__main__":
    main()
