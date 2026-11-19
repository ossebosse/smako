"""Warm plan processes keep their pages and caches between plans (2026-11-19)."""
import os

import pytest
from app.services import plan_jobs
from app.services import planner_processes as pp

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="fork")

_COUNT = {"n": 0}


def _runner(payload):
    _COUNT["n"] += 1  # lives in the warm process: counts its plans
    if payload == "stale":
        raise pp.WarmStale("other universe")
    if payload == "fail":
        raise ValueError("planned failure")
    plan_jobs.report_stage("week_search")
    return {"pid": os.getpid(), "plans_here": _COUNT["n"], "payload": payload}


pp.register_warm_runner("test_runner", _runner)


@pytest.fixture
def warm(monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_MEMORY_CHECK", "0")
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "4")
    monkeypatch.setenv("SMAKO_WARM_PLAN_PROCESSES", "1")
    monkeypatch.setenv("SMAKO_PLAN_PROCESSES", "1")
    monkeypatch.setattr(pp, "free_threaded", lambda: False)
    yield
    for worker in list(pp._warm_all):
        pp._warm_retire(worker)


def test_a_warm_process_takes_the_next_plan(warm):
    stages = []
    token = plan_jobs._stage_reporter.set(lambda stage, progress: stages.append(stage))
    try:
        first = pp.run_plan_warm("test_runner", "a", lambda: "here")
        second = pp.run_plan_warm("test_runner", "b", lambda: "here")
    finally:
        plan_jobs._stage_reporter.reset(token)
    assert first["pid"] == second["pid"] != os.getpid()
    assert (first["plans_here"], second["plans_here"]) == (1, 2)
    assert stages == ["week_search", "week_search"]
    assert pp._slots_in_use == 0 and pp._running_plans == 0


def test_errors_are_raised_here_and_a_stale_process_is_retired(warm):
    with pytest.raises(ValueError, match="planned failure"):
        pp.run_plan_warm("test_runner", "fail", lambda: "here")
    pid = pp.run_plan_warm("test_runner", "a", lambda: "here")["pid"]
    # A process holding another price universe: the plan runs as before and
    # that process is not used again.
    assert pp.run_plan_warm("test_runner", "stale", lambda: "fallback") == "fallback"
    assert pp.run_plan_warm("test_runner", "c", lambda: "here")["pid"] != pid


def test_without_warm_processes_plans_run_as_before(warm, monkeypatch):
    monkeypatch.setenv("SMAKO_WARM_PLAN_PROCESSES", "0")
    monkeypatch.setenv("SMAKO_PLAN_PROCESSES", "0")
    assert pp.run_plan_warm("test_runner", "a", lambda: "here") == "here"
    assert pp.run_plan_warm("unknown", "a", lambda: "here") == "here"


def test_a_process_over_its_size_is_not_kept(warm, monkeypatch):
    monkeypatch.setenv("SMAKO_WARM_PROCESS_LIMIT_MB", "1")
    first = pp.run_plan_warm("test_runner", "a", lambda: "here")
    second = pp.run_plan_warm("test_runner", "b", lambda: "here")
    assert first["pid"] != second["pid"] and second["plans_here"] == 1
