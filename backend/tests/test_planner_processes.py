"""Planner work split over cores: same answer, and safe fallbacks."""
import os
import time

import pytest
from app.services import planner_processes as pp

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="needs fork")


def square_all(part):
    return {item: item * item for item in part}


def test_slices_cover_everything_once_and_small_work_stays_here():
    assert pp._slices(10, 8) == [(0, 10)]
    bounds = pp._slices(100, 3)
    assert bounds[0][0] == 0 and bounds[-1][1] == 100 and len(bounds) == 3
    assert all(a[1] == b[0] for a, b in zip(bounds, bounds[1:], strict=False))


def test_workers_return_the_same_answers():
    items = list(range(120))
    answers, missing = pp.run_in_processes(items, square_all, timeout=30, workers=4)
    assert answers == {i: i * i for i in items} and missing == []


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
    assert missing == [0, 3] and set(answers) == set(range(30, 90))


def test_worker_count_follows_the_setting(monkeypatch):
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "3")
    assert pp.worker_count() == 3
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "x")
    assert pp.worker_count() == 0
    monkeypatch.delenv("SMAKO_PLANNER_PROCESSES")
    assert pp.worker_count() == max(0, min(8, (os.cpu_count() or 1) - 1))


def test_qualification_asks_workers_only_for_unknown_recipes_and_merges_their_rows(monkeypatch):
    from types import SimpleNamespace

    from app.services.personal_planner import PersonalPlanner
    from app.services.planner_context import content_digest

    recipes = [{"recipe": i} for i in range(60)]
    known = {content_digest(recipes[0]): {"status": "passed", "evidence": None}}
    asked = []

    def candidates(meal, *, fixed_slots=(), _rows_only=None):
        asked.extend(r["recipe"] for r in _rows_only)
        return {content_digest(r): {"status": "rejected", "reason": "x", "stage": "s", "code": "C"} for r in _rows_only}

    planner = SimpleNamespace(_candidates=candidates, diagnostics=SimpleNamespace(pools=[{}]))
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "3")
    monkeypatch.setattr(pp, "_MIN_ITEMS_PER_WORKER", 10)
    rows = PersonalPlanner._qualify_in_processes(planner, None, recipes, known, ())
    assert len(rows) == 60 and rows[content_digest(recipes[0])]["status"] == "passed"
    assert planner.diagnostics.pools[-1]["parallel_qualification"] == {
        "workers": 3, "recipes": 59, "rows": 59, "slices_redone": 0}
    # The parent asked nothing itself: the workers did (their list is theirs).
    assert asked == []
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "0")
    assert PersonalPlanner._qualify_in_processes(planner, None, recipes, known, ()) is known
