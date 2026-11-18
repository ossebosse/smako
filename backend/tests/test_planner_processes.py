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
    monkeypatch.setattr(pp, "free_threaded", lambda: False)
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
    monkeypatch.setattr(pp, "_own_anon_bytes", lambda: 2 * 2**30)
    monkeypatch.setattr(pp, "_observed_peak", {"plan": 0, "worker": 0})
    monkeypatch.setattr(pp, "_observed_per_item", 0.0)
    assert pp.memory_slots() == 3  # 75 % of 4 GB; a child: half of 2 GB
    assert pp.reserve_processes(5) == 3
    # The three are counted as not yet grown: nothing more fits now.
    assert pp.reserve_processes(5) == 0
    pp.release_processes(3)
    assert pp._worker_bytes == 0
    monkeypatch.setattr(pp, "_observed_peak", {"plan": 0, "worker": int(1.6 * 2**30)})
    assert pp.memory_slots() == 1  # a large worker was seen: 2 GB each
    # A large app process does not make its children large: an unseen worker
    # counts as at most 1 GB, a seen one as what it copied (2026-11-18).
    monkeypatch.setattr(pp, "_own_anon_bytes", lambda: 6 * 2**30)
    monkeypatch.setattr(pp, "_available_bytes", lambda: int(3.5 * 2**30))
    monkeypatch.setattr(pp, "_observed_peak", {"plan": 0, "worker": 0})
    assert pp.memory_slots() == 2
    monkeypatch.setattr(pp, "_observed_peak", {"plan": int(2.7 * 2**30), "worker": int(0.4 * 2**30)})
    assert pp.memory_slots() == 5
    monkeypatch.setattr(pp, "_own_anon_bytes", lambda: None)
    assert pp.reserve_processes(2) == 0  # unknown memory: no extra process
    assert pp._slots_in_use == 0


def test_a_plan_process_holds_back_only_what_it_may_still_copy(monkeypatch):
    """A plan's 2.7 GB process no longer stands for every worker (2026-11-18)."""
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "7")
    monkeypatch.setattr(pp, "_available_bytes", lambda: 8 * 2**30)
    monkeypatch.setattr(pp, "_own_anon_bytes", lambda: 4 * 2**30)
    monkeypatch.setattr(pp, "_observed_peak", {"plan": int(2.4 * 2**30), "worker": int(0.4 * 2**30)})
    monkeypatch.setattr(pp, "_observed_per_item", 0.0)
    slot = pp.reserve_plan_process()
    assert slot is not None and pp._slots_in_use == 1
    # Before it has copied anything its whole estimate (3 GB) is held back:
    # 6 GB usable - 3 GB = 3 GB, 0.5 GB per worker.
    assert pp.memory_slots() == 6
    monkeypatch.setattr(pp, "_private_dirty", lambda pid: int(2.5 * 2**30))
    monkeypatch.setattr(pp, "_available_bytes", lambda: int(5.5 * 2**30))
    pp.observe_plan_process(slot, 123)
    # It copied 2.5 GB, which left the free memory; 0.5 GB more may follow.
    assert pp._observed_peak["plan"] == int(2.5 * 2**30)
    assert pp.memory_slots() == 7
    assert pp.reserve_processes(9) == 6  # the cores decide now
    pp.release_processes(6)
    pp.release_plan_process(slot)
    assert pp._slots_in_use == 0 and not pp._plan_children
    monkeypatch.setattr(pp, "_available_bytes", lambda: 2 * 2**30)
    assert pp.reserve_plan_process() is None  # a plan's process does not fit


def test_workers_are_sized_by_the_recipes_they_get(monkeypatch):
    """1.3 MB per recipe: two workers of 1,148 recipes looked like one (2026-11-18)."""
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "7")
    monkeypatch.setattr(pp, "_available_bytes", lambda: int(7.4 * 2**30))
    monkeypatch.setattr(pp, "_own_anon_bytes", lambda: 4 * 2**30)
    monkeypatch.setattr(pp, "_observed_peak", {"plan": 0, "worker": 0})
    monkeypatch.setattr(pp, "_observed_per_item", 0.0)
    pp.note_child_peak("worker", int(1.5 * 2**30), 1148)
    pp.note_child_peak("worker", 2**30, 24)  # a small slice says little per recipe
    assert pp._observed_per_item == int(1.5 * 2**30) / 1148
    # Sized as one 1.9 GB worker each, two would fit in 5.5 GB; sized by
    # slice, six workers of 328 recipes each (0.5 GB) fit.
    assert pp.reserve_processes(6, items=2297) == 6
    held = pp._worker_bytes
    assert 6 * 0.5 * 2**30 < held < 6 * 0.6 * 2**30
    pp.release_processes(6)
    assert pp._worker_bytes == 0 and pp._slots_in_use == 0
    pp.note_per_item(3 * 2**20)  # a plan's process saw larger workers
    assert pp._observed_per_item == 3 * 2**20
    # 3 MB per recipe: all workers together would copy 8.6 GB x k/(k+1).
    assert pp.reserve_processes(6, items=2297) == 1
    pp.release_processes(1)
    assert pp._slots_in_use == 0


def test_a_running_child_is_measured(monkeypatch):
    import signal as signals

    monkeypatch.setattr(pp, "_observed_peak", {"plan": 0, "worker": 0})

    pid = os.fork()
    if pid == 0:
        data = bytearray(32 * 2**20)  # a child that copies 32 MB
        data[::4096] = b"x" * len(data[::4096])
        time.sleep(30)
        os._exit(0)
    try:
        time.sleep(0.5)
        pp.observe_child(pid)
        assert pp._observed_peak["worker"] >= 30 * 2**20 and pp._observed_peak["plan"] == 0
    finally:
        os.kill(pid, signals.SIGKILL)
        os.waitpid(pid, 0)


# --- One plan per process (several people at once) ---------------------------

def _plan_env(monkeypatch):
    monkeypatch.setattr(pp, "free_threaded", lambda: False)  # the process path, also without the GIL
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


def test_a_plan_without_a_free_slot_runs_here(monkeypatch):
    _plan_env(monkeypatch)
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "0")
    assert pp.run_plan_in_process(os.getpid) == os.getpid()
    assert pp._running_plans == 0 and pp._slots_in_use == 0


def test_a_plan_process_asks_the_app_process_for_its_workers(monkeypatch):
    _plan_env(monkeypatch)
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "4")

    def work():
        with pp.qualification_workers() as granted:
            during = granted
        with pp.qualification_workers() as again:  # given back, so granted again
            return during, again, os.getpid()

    during, again, pid = pp.run_plan_in_process(work)
    # Four cores: the plan's own process is one, so three workers.
    assert (during, again) == (3, 3) and pid != os.getpid()
    assert pp._slots_in_use == 0


def test_a_cpu_quota_limits_the_cores(monkeypatch):
    import builtins
    import io

    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda path, *a, **k: io.StringIO("250000 100000\n")
                        if path == "/sys/fs/cgroup/cpu.max" else real_open(path, *a, **k))
    monkeypatch.setattr(pp.os, "cpu_count", lambda: 8)
    assert pp._cores() == 3


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


def test_free_threaded_qualification_uses_planner_copies_in_threads(monkeypatch):
    """Without the GIL: threads on planner copies, the first slice on the planner itself."""
    import threading
    from types import SimpleNamespace

    from app.services.personal_planner import PersonalPlanner
    from app.services.planner_context import content_digest

    recipes = [{"recipe": i} for i in range(60)]
    seen = {}

    class Fake(SimpleNamespace):
        def _qualify_slice(self, meal, fixed_slots, *, here=False):
            def work(part):
                seen.setdefault(self.name, set()).add(threading.get_ident())
                return {content_digest(r): {"status": "rejected", "reason": self.name, "stage": "s", "code": "C"}
                        for r in part}
            return work

        def _thread_copy(self):
            return Fake(name="copy", diagnostics=self.diagnostics)

    planner = Fake(name="self", diagnostics=SimpleNamespace(pools=[{}]))
    monkeypatch.setattr(pp, "free_threaded", lambda: True)
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "2")
    monkeypatch.setattr(pp, "_MIN_ITEMS_PER_WORKER", 10)
    rows = PersonalPlanner._qualify_in_processes(planner, None, recipes, {}, ())
    assert len(rows) == 60
    assert sum(r["reason"] == "self" for r in rows.values()) == 20  # a third on the planner itself
    assert seen["self"] == {threading.get_ident()} and threading.get_ident() not in seen["copy"]
    diagnostics = planner.diagnostics.pools[-1]["parallel_qualification"]
    assert diagnostics["threads"] and diagnostics["workers"] == 2 and diagnostics["slices_redone"] == 0
    assert not pp.plan_processes_enabled()  # plans are threads already


def test_equal_keys_compute_once_and_different_keys_at_the_same_time():
    import threading

    from app.services.price_universe import _ThreadSafeLru

    cache = _ThreadSafeLru(max_entries=100, metric_prefix="t")
    inside, release, calls = threading.Barrier(2, timeout=5), threading.Event(), []

    def slow(name):
        def factory():
            calls.append(name)
            inside.wait()  # both different keys are computing at once
            release.wait(5)
            return name
        return factory

    threads = [threading.Thread(target=cache.get_or_compute, args=(k, slow(k))) for k in ("a", "b")]
    same = threading.Thread(target=cache.get_or_compute, args=("a", slow("a-again")))
    for thread in threads:
        thread.start()
    time.sleep(0.2)
    same.start()  # waits for "a" instead of computing it again
    time.sleep(0.2)
    release.set()
    for thread in [*threads, same]:
        thread.join(5)
    assert sorted(calls) == ["a", "b"]
    assert cache.get_or_compute("a", lambda: "x") == "a"
    # A factory that needs another key of the same cache computes it directly.
    assert cache.get_or_compute("outer", lambda: cache.get_or_compute("inner", lambda: 1) + 1) == 2


def test_a_qualification_thread_does_not_share_the_request_quote_session(monkeypatch):
    import contextvars
    from types import SimpleNamespace

    from app.services import basket_optimizer
    from app.services.personal_planner import PersonalPlanner

    session = contextvars.ContextVar("quote_session", default=None)
    session.set("the request's session")
    scope = {"keys": {}}
    monkeypatch.setattr(basket_optimizer, "_REQUIREMENT_KEY_SCOPE", contextvars.ContextVar("scope", default=None))
    basket_optimizer._REQUIREMENT_KEY_SCOPE.set(scope)
    seen = []
    planner = SimpleNamespace(
        optimizer=SimpleNamespace(_quote_cache_context=session),
        _candidates=lambda meal, fixed_slots, _rows_only: seen.append(
            (session.get(), basket_optimizer._REQUIREMENT_KEY_SCOPE.get())) or {})
    thread_work = PersonalPlanner._qualify_slice(planner, None, ())
    contextvars.copy_context().run(thread_work, [1])
    PersonalPlanner._qualify_slice(planner, None, (), here=True)([1])
    assert seen[0][0] is None and seen[0][1] == {} and seen[0][1] is not scope
    assert seen[1] == ("the request's session", scope)
    assert session.get() == "the request's session"


def test_a_thread_copy_has_its_own_optimizer_settings():
    from app.config import Settings
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, state

    planner = PersonalPlanner(request(), Settings(price_provider="mock"), prepared(product("mjölk", 1000, "ml", 10)),
                              state(), now=NOW)
    other = planner._thread_copy()
    assert other.optimizer is not planner.optimizer
    assert other.optimizer._store_subsets is planner.optimizer._store_subsets  # the pure memo is shared
    other.optimizer.verification_policy = "changed in the thread"
    assert planner.optimizer.verification_policy != "changed in the thread"
    assert other.lookup_cache is not planner.lookup_cache and other.prepared is planner.prepared


def test_background_work_runs_at_low_priority_with_at_most_one_worker(monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "6")
    monkeypatch.setenv("SMAKO_PLANNER_MEMORY_CHECK", "0")
    monkeypatch.setattr(pp, "free_threaded", lambda: False)

    def work():
        import threading as threads
        with pp.qualification_workers() as granted:
            return granted, os.getpriority(os.PRIO_PROCESS, threads.get_native_id())

    granted, nice = pp.run_in_background_thread(work).result(timeout=10)
    assert granted == 1 and nice == pp._BACKGROUND_NICE
    with pp.qualification_workers() as granted:  # people's plans: the full share
        assert granted == 6
    assert os.getpriority(os.PRIO_PROCESS, 0) < pp._BACKGROUND_NICE  # this thread is untouched
    assert pp._slots_in_use == 0


def test_background_errors_reach_the_caller():
    def work():
        raise ValueError("stopped")

    with pytest.raises(ValueError, match="stopped"):
        pp.run_in_background_thread(work).result(timeout=10)
