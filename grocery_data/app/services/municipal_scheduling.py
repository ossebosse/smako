"""Deadline ordering and durable fair turns inside existing sequential workers."""
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path

from grocery_data.app.services.durable_files import atomic_write_bytes


def read_state(path):
    path = Path(path)
    return json.loads(path.read_bytes()) if path.exists() else {}


def order_work(items, state, *, now):
    """Age waiting jobs to avoid an endlessly failing municipality starving peers.

    Deadlines are scheduling priorities only; no source expiry is extended.
    """
    jobs = state.setdefault("jobs", {})
    for item in items:
        job = jobs.setdefault(item["municipality_code"], {})
        if item.get("work_due", True):
            job.setdefault("waiting_since", now.isoformat())
        else:
            job.pop("waiting_since", None)

    def priority(item):
        job = jobs[item["municipality_code"]]
        waiting = datetime.fromisoformat(job.get("waiting_since", now.isoformat()))
        deadline = datetime.fromisoformat(item["deadline"]) if item.get("deadline") else now
        seconds = estimate_seconds(job)
        # A served failing scope gets a new waiting time; never an older priority
        # than a peer that has waited a full day without service.
        deadline = max(deadline, datetime.fromisoformat(job.get("last_attempt_at", "1970-01-01T00:00:00+00:00")))
        return (not item.get("work_due", True), min(deadline - timedelta(seconds=seconds),
                waiting + timedelta(hours=24)), job.get("last_attempt_at", ""))

    return sorted(items, key=priority)


def estimate_seconds(job, default=1800):
    measured = job.get("duration_seconds")
    if isinstance(measured, (int, float)) and math.isfinite(measured) and measured > 0:
        return max(60, measured * 1.25)
    return default


def record_attempt(state, code, *, started, seconds, result):
    job = state.setdefault("jobs", {}).setdefault(code, {})
    job.update(last_attempt_at=started.isoformat(), waiting_since=datetime.now(UTC).isoformat(),
               exit_code=result)
    # Failed/deferred short runs must not replace the full-work estimate.
    if result == 0:
        job["duration_seconds"] = max(seconds, job.get("duration_seconds", 0))


def save_state(path, state):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    atomic_write_bytes(Path(path), json.dumps(state, ensure_ascii=False).encode())


def plan_deadline(plan):
    times = [s["hard_stop_at"] for s in plan.get("sources", {}).values() if s.get("hard_stop_at")]
    return min(times) if times else None
