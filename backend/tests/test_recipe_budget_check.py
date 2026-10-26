"""Budget receipts cannot discard prior work when a check fails or resumes."""
import json
import runpy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("exit_code", [0, 2])
def test_serial_check_keeps_shared_charges_after_interruption_and_failure(tmp_path, monkeypatch, exit_code):
    code = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer/budgeted_check.py"))
    execute = code["run"]
    monkeypatch.setitem(execute.__globals__, "windows_limits",
                        lambda: (lambda _: None, lambda: 512, lambda _: (384, 512), lambda: None))

    def target(_, **kwargs):
        raise SystemExit(exit_code)

    monkeypatch.setattr(code["runpy"], "run_path", target)
    monkeypatch.setattr(code["sys"], "argv", list(code["sys"].argv))
    path = tmp_path / "budget.json"
    path.write_text(json.dumps({"limit_seconds": 7200, "prior_v2_seconds": 40,
        "used_seconds": 0, "remaining_seconds": 7200, "entries": [
            {"label": "earlier", "status": "complete", "wall_seconds": 20},
            {"label": "interrupted", "status": "running", "wall_seconds": 0,
             "started_at": (datetime.now(UTC) - timedelta(seconds=30)).isoformat()}]}))
    args = SimpleNamespace(budget=path, label="current", max_seconds=5, command=["unit-only.py"])
    assert execute(args) == exit_code
    saved = json.loads(path.read_bytes())
    assert saved["entries"][1]["status"] == "interrupted_charged"
    assert saved["entries"][1]["wall_seconds"] >= 30
    assert saved["entries"][-1]["status"] == ("complete" if exit_code == 0 else "stopped")
    assert saved["used_seconds"] == 40 + sum(r["wall_seconds"] for r in saved["entries"])
    assert saved["used_seconds"] >= 90
    assert saved["remaining_seconds"] == 7200 - saved["used_seconds"]
    assert all(r["status"] != "running" for r in saved["entries"])


def test_shared_limit_includes_prior_v2_before_starting_any_worker(tmp_path, monkeypatch):
    code = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer/budgeted_check.py"))
    execute = code["run"]

    def unexpected_worker():
        pytest.fail("An exhausted shared budget must not start a worker")

    monkeypatch.setitem(execute.__globals__, "windows_limits", unexpected_worker)
    path = tmp_path / "budget.json"
    path.write_text(json.dumps({"limit_seconds": 7200, "prior_v2_seconds": 200,
                               "entries": [{"label": "intake", "status": "complete", "wall_seconds": 7000}]}))
    with pytest.raises(RuntimeError, match="exhausted"):
        execute(SimpleNamespace(budget=path, label="refused", max_seconds=75, command=["unit-only.py"]))
    assert len(json.loads(path.read_bytes())["entries"]) == 1


def test_live_worker_lease_rejects_second_run_without_charging_or_replacing_its_journal(tmp_path):
    code = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer/budgeted_check.py"))
    path = tmp_path / "budget.json"
    original = b'{"limit_seconds":7200,"entries":[{"status":"running"}]}'
    path.write_bytes(original)
    with code["budget_lease"](path):
        with pytest.raises(RuntimeError, match="already active"):
            code["run"](SimpleNamespace(budget=path, label="refused", max_seconds=75, command=["never.py"]))
        assert path.read_bytes() == original
    # Closing the handle, including process exit, releases the lease.
    with code["budget_lease"](path):
        assert path.read_bytes() == original


def test_phase_deadline_cannot_extend_shared_deadline_and_timer_is_cleaned(tmp_path, monkeypatch):
    import sys

    code = runpy.run_path(str(Path(__file__).resolve().parents[2] / "scripts/recipe_layer/budgeted_check.py"))
    execute = code["run"]
    monkeypatch.setitem(execute.__globals__, "windows_limits",
                        lambda: (lambda _: None, lambda: 512, lambda _: (384, 512), lambda: None))
    observed = []

    def timer(seconds, callback):
        value = SimpleNamespace(seconds=seconds, cancelled=False, start=lambda: None)
        value.cancel = lambda: setattr(value, "cancelled", True)
        observed.append(value)
        return value

    def target(_, **kwargs):
        context = sys.modules["smako_budget_context"]
        with pytest.raises(ValueError, match="positive"):
            context.arm_phase(0)
        context.arm_phase(100)
        raise SystemExit(0)

    monkeypatch.setattr(code["threading"], "Timer", timer)
    monkeypatch.setattr(code["runpy"], "run_path", target)
    monkeypatch.setattr(code["sys"], "argv", list(code["sys"].argv))
    path = tmp_path / "budget.json"
    path.write_text(json.dumps({"limit_seconds": 7200, "entries": []}))
    assert execute(SimpleNamespace(budget=path, label="phase", max_seconds=5, command=["unit-only.py"])) == 0
    assert len(observed) == 1 and 0 < observed[0].seconds <= 5 and observed[0].cancelled
    assert "smako_budget_context" not in sys.modules
