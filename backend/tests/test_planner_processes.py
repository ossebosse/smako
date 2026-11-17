"""Planner work split over cores: same answer, and safe fallbacks."""
import os
import time
from itertools import pairwise

import pytest
from app.services import planner_processes as pp

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")


def square_all(part):
    return {item: item * item for item in part}


def test_slices_cover_everything_once_and_small_work_stays_here():
    assert pp._slices(10, 8) == [(0, 10)]
    bounds = pp._slices(100, 3)
    assert bounds[0][0] == 0 and bounds[-1][1] == 100 and len(bounds) == 3
    assert all(a[1] == b[0] for a, b in pairwise(bounds))


def test_workers_return_the_same_answers():
    items = list(range(120))
    answers, missing = pp.run_in_processes(items, square_all, timeout=30, workers=4)
    merged = {k: v for answer in answers for k, v in answer.items()}
    assert len(answers) == 4 and merged == {i: i * i for i in items} and missing == []


def test_a_failing_or_late_worker_leaves_its_slice_to_the_caller():
    def work(part):
        if 0 in part:
            raise RuntimeError("boom")
        if 119 in part:
            time.sleep(30)
        return square_all(part)

    started = time.monotonic()
    answers, missing = pp.run_in_processes(list(range(120)), work, timeout=3, workers=4)
    assert time.monotonic() - started < 10
    assert missing == [0, 3] and {k for a in answers for k in a} == set(range(30, 90))


def test_cpu_budget_follows_the_setting(monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "3")
    assert pp.cpu_budget() == 3
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "x")
    assert pp.cpu_budget() == 0
    monkeypatch.delenv("SMAKO_PLANNER_PROCESSES")
    assert pp.cpu_budget() == max(0, min(8, (os.cpu_count() or 1) - 1))


def test_the_parent_does_one_slice_itself():
    parent = os.getpid()
    answers, missing = pp.run_in_processes(list(range(120)), lambda part: {"pid": os.getpid(), "n": len(part)},
                                           timeout=30, workers=2, here=True)
    assert missing == [] and len(answers) == 3
    assert answers[0]["pid"] == parent and {a["pid"] for a in answers[1:]}.isdisjoint({parent})
    assert sum(a["n"] for a in answers) == 120


def test_qualification_asks_workers_only_for_unknown_recipes_and_merges_their_rows(monkeypatch):
    from types import SimpleNamespace

    from app.services import planner_shared_cache
    from app.services.personal_planner import PersonalPlanner
    from app.services.planner_context import content_digest
    from app.services.price_universe import PackageCostCache

    recipes = [{"recipe": i} for i in range(60)]
    known = {content_digest(recipes[0]): {"status": "passed", "evidence": None}}
    asked = []
    cache = PackageCostCache(max_entries=1000)

    def candidates(meal, *, fixed_slots=(), _rows_only=None):
        asked.extend(r["recipe"] for r in _rows_only)
        for r in _rows_only:  # a worker prices packages into its copy of the cache
            cache._cache.get_or_compute(("quote", r["recipe"]), lambda r=r: r["recipe"] * 10)
        return {content_digest(r): {"status": "rejected", "reason": "x", "stage": "s", "code": "C"} for r in _rows_only}

    planner = SimpleNamespace(_candidates=candidates, diagnostics=SimpleNamespace(pools=[{}]),
                              prepared=SimpleNamespace(package_cache=cache))
    monkeypatch.setattr(planner_shared_cache, "planner_scope", lambda planner: None)
    monkeypatch.setattr(planner_shared_cache, "nutrition_scope", lambda planner: None)
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "2")
    monkeypatch.setenv("SMAKO_PLANNER_MEMORY_CHECK", "0")
    monkeypatch.setattr(pp, "_MIN_ITEMS_PER_WORKER", 10)
    rows = PersonalPlanner._qualify_in_processes(planner, None, recipes, known, ())
    assert len(rows) == 60 and rows[content_digest(recipes[0])]["status"] == "passed"
    diagnostics = planner.diagnostics.pools[-1]["parallel_qualification"]
    assert diagnostics["workers"] == 2 and diagnostics["recipes"] == 59 and diagnostics["rows"] == 59
    assert diagnostics["slices_redone"] == 0
    # This process did one slice (a third), two workers the rest; their quotes
    # are now in this process's cache too.
    assert len(asked) == 20 and set(asked) <= set(range(1, 21))
    assert diagnostics["kept_entries"] == 39 and cache.stats.entries == 59
    assert pp._slots_in_use == 0  # the slots were given back
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "0")
    assert PersonalPlanner._qualify_in_processes(planner, None, recipes, known, ()) is known


def test_slots_follow_cores_and_free_memory(monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "6")
    monkeypatch.setattr(pp, "_available_bytes", lambda: 4 * 2**30)
    monkeypatch.setattr(pp, "_child_bytes", lambda: 1 * 2**30)
    assert pp.memory_slots() == 3  # 75 % of 4 GB for 1 GB children
    first = pp.reserve_processes(5)
    assert first == 3
    assert pp.reserve_processes(5) == 3  # memory is measured anew, cores still free
    assert pp.reserve_processes(5) == 0  # all six cores taken
    pp.release_processes(6)
    assert pp._slots_in_use == 0
    monkeypatch.setattr(pp, "_child_bytes", lambda: None)
    assert pp.reserve_processes(2) == 0  # unknown memory: no extra process


# --- One plan per process (several people at once) ---------------------------

def _plan_env(monkeypatch):
    monkeypatch.setenv("SMAKO_PLAN_PROCESSES", "1")
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "2")
    monkeypatch.setenv("SMAKO_PLANNER_MEMORY_CHECK", "0")


def test_a_plan_in_its_own_process_reports_stages_and_returns_its_result(monkeypatch):
    from app.services import plan_jobs

    _plan_env(monkeypatch)
    seen = []
    token = plan_jobs._stage_reporter.set(lambda stage, progress: seen.append((stage, progress, os.getpid())))

    def work():
        plan_jobs.report_stage("searching")
        return {"pid": os.getpid()}

    try:
        result = pp.run_plan_in_process(work)
    finally:
        plan_jobs._stage_reporter.reset(token)
    assert result["pid"] != os.getpid()
    # Reported in the parent, so the job the browser polls sees them.
    assert seen == [("searching", None, os.getpid())]


def test_a_plan_error_is_raised_in_the_parent_with_its_details(monkeypatch):
    from app.services.personal_policy import PolicyConflict

    _plan_env(monkeypatch)

    def work():
        raise PolicyConflict("Inga recept", code="RECIPE_CHOICES_CONFLICT", stage="search",
                             diagnostics={"pid": os.getpid()})

    with pytest.raises(PolicyConflict) as caught:
        pp.run_plan_in_process(work)
    assert caught.value.code == "RECIPE_CHOICES_CONFLICT" and caught.value.diagnostics["pid"] != os.getpid()


def test_what_a_plan_process_learned_is_kept_for_later_plans(monkeypatch):
    from app.services.personal_planner import _QualificationMemory
    from app.services.price_universe import PackageCostCache

    _plan_env(monkeypatch)
    memory, cache = _QualificationMemory(), PackageCostCache(max_entries=100)
    memory.put("old", {"rows": {}})

    def work():
        memory.put("view", {"rows": {"r": 1}})
        cache._cache.get_or_compute("quote", lambda: 42)
        return "ok"

    assert pp.run_plan_in_process(work) == "ok"
    assert memory.get("view") == {"rows": {"r": 1}} and memory.get("old") == {"rows": {}}
    assert cache._cache.get_or_compute("quote", lambda: -1) == 42


def test_a_dead_plan_process_is_planned_here_instead(monkeypatch):
    _plan_env(monkeypatch)
    parent = os.getpid()

    def work():
        if os.getpid() != parent:
            os._exit(3)
        return "here"

    assert pp.run_plan_in_process(work) == "here"


def test_a_cancelled_plan_stops_its_process(monkeypatch):
    import asyncio
    import threading

    from app.services import plan_jobs

    _plan_env(monkeypatch)
    stop = threading.Event()
    token = plan_jobs._work_cancellation.set(stop)
    threading.Timer(0.5, stop.set).start()
    started = time.monotonic()
    try:
        with pytest.raises(asyncio.CancelledError):
            pp.run_plan_in_process(lambda: time.sleep(30))
    finally:
        plan_jobs._work_cancellation.reset(token)
    assert time.monotonic() - started < 5


def test_plans_running_at_once_share_the_cores(monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "6")
    monkeypatch.setattr(pp, "_running_plans", 3)
    assert pp.worker_count() == 2
    monkeypatch.setattr(pp, "_child_allotment", 1)  # in a plan's own process
    assert pp.worker_count() == 1


def test_a_plan_without_a_free_slot_runs_here(monkeypatch):
    _plan_env(monkeypatch)
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "0")
    assert pp.run_plan_in_process(os.getpid) == os.getpid()
    assert pp._running_plans == 0 and pp._slots_in_use == 0


def test_a_plan_process_gets_its_workers_from_the_parent(monkeypatch):
    _plan_env(monkeypatch)
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "4")
    assert pp.run_plan_in_process(lambda: (os.getpid(), pp.worker_count()))[1] == 3
    assert pp._slots_in_use == 0


def test_a_lock_held_in_another_thread_at_fork_is_free_in_the_plan_process(monkeypatch):
    import threading

    from app.services.price_universe import PackageCostCache

    _plan_env(monkeypatch)
    cache = PackageCostCache(max_entries=10)
    held, release = threading.Event(), threading.Event()

    def hold():
        with cache._cache._lock:
            held.set()
            release.wait(10)

    thread = threading.Thread(target=hold)
    thread.start()
    held.wait(5)
    try:
        assert pp.run_plan_in_process(lambda: cache._cache.get_or_compute("k", lambda: 7)) == 7
    finally:
        release.set()
        thread.join()


def test_shared_resolution_entries_from_a_plan_process_are_kept(monkeypatch):
    from app.services.planner_shared_cache import SharedResolution

    _plan_env(monkeypatch)

    class Prepared:
        pass

    prepared, shared = Prepared(), SharedResolution()
    scope = shared.scope(("universe", 1), prepared)

    def work():
        shared.put(shared.scope(("universe", 1), prepared), "mjölk", ("ok", [1, 2], ()))
        shared.put(shared.scope(("other", 2), prepared), "x", ("ok", [], ()))
        return "done"

    assert pp.run_plan_in_process(work) == "done"
    assert shared.get(scope, "mjölk") == ("ok", [1, 2], ())
    # A scope only the child had is not recreated here.
    assert len(shared.stats()) == 1


def test_plans_in_this_process_are_counted_too(monkeypatch):
    monkeypatch.setenv("SMAKO_PLAN_PROCESSES", "0")
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "6")
    monkeypatch.setattr(pp, "_running_plans", 1)  # another plan is running
    assert pp.run_plan_in_process(pp.worker_count) == 3
    assert pp._running_plans == 1
