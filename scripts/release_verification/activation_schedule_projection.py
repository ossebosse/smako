"""Pure schedule projection: no clocks, receipts, tasks or observations are changed."""

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[2]
live = json.loads(
    (root / "docs/releases/lund-20260929/S4U-LIVE-EVIDENCE.json").read_text(encoding="utf-8")
)
observed = datetime.fromisoformat(live["receipt"]["observed_from"])
start = datetime.fromisoformat(live["started_utc"])
end = datetime.fromisoformat(live["finished_utc"])
duration = end - start
lag = observed - start
zone = ZoneInfo("Europe/Stockholm")


def forecast(hours):
    virtual_observation = observed
    rows = []
    for day in range(2, 7):
        for hour in hours:
            attempt = datetime.combine(date(2026, 10, day), time(hour, 30), zone)
            age = attempt - virtual_observation
            due = age >= timedelta(hours=35)
            row = {
                "start_local": attempt.isoformat(),
                "start_utc": attempt.astimezone(UTC).isoformat(),
                "projected_source_age_hours": age.total_seconds() / 3600,
                "decision": "would_collect" if due else "not_due",
            }
            if due:
                hard_stop = virtual_observation + timedelta(hours=48)
                row.update(
                    hard_stop_local=hard_stop.astimezone(zone).isoformat(),
                    margin_after_measured_delivery_minutes=(
                        hard_stop - attempt - duration
                    ).total_seconds()
                    / 60,
                    margin_after_3h_budget_minutes=(
                        hard_stop - attempt - timedelta(hours=3)
                    ).total_seconds()
                    / 60,
                )
                virtual_observation = attempt + lag
            rows.append(row)
    return rows


report = {
    "kind": "calculation, not actual future task runs or fabricated source fixtures",
    "authentic_initial_observed_from": observed.isoformat(),
    "measured_delivery_seconds": duration.total_seconds(),
    "measured_observation_start_offset_seconds": lag.total_seconds(),
    "due_hours": 35,
    "warning_hours": 36,
    "hard_stop_hours": 48,
    "registered_daily_0130_projection": forecast([1]),
    "proposed_only_8h_projection": forecast([1, 9, 17]),
    "phase_independent_budget_hours": {
        "due": 35,
        "max_poll_gap": 8,
        "execution_budget": 3,
        "total": 46,
        "hard_stop_margin": 2,
    },
    "any_trigger_changed": False,
    "any_source_request": False,
}
assert any(
    r.get("margin_after_measured_delivery_minutes", 0) < 0
    for r in report["registered_daily_0130_projection"]
)
assert all(
    r.get("margin_after_3h_budget_minutes", 1) > 0 for r in report["proposed_only_8h_projection"]
)
print(json.dumps(report, indent=2))
