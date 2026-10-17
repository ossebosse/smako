import threading
from types import SimpleNamespace

from app.services.source_facts_prewarm import schedule_source_facts_prewarm


def _settings(complete=True, enabled=True):
    return SimpleNamespace(complete_recipes_enabled=complete, source_facts_prewarm_enabled=enabled)


def _universe(name):
    return SimpleNamespace(universe=SimpleNamespace(universe_id=name))


def test_loads_each_active_universe_with_the_shared_loader():
    seen = []
    report = schedule_source_facts_prewarm(
        _settings(), [_universe("lund"), _universe("malmo")],
        loader=lambda prepared: seen.append(prepared.universe.universe_id) or {"k": 1}, start=False,
        library_warmer=lambda: seen.append("library"))

    assert seen == ["library", "lund", "malmo"]
    assert report["status"] == "ready"
    assert [r["fact_rows"] for r in report["universes"]] == [1, 1]


def test_failure_is_recorded_and_never_raised():
    def broken(prepared):
        raise OSError("missing raw snapshot")

    report = schedule_source_facts_prewarm(_settings(), [_universe("lund")], loader=broken, start=False,
                                           library_warmer=lambda: None)

    assert report["status"] == "partial"
    assert report["universes"][0] == {"universe_id": "lund", "status": "failed",
                                      "error_type": "OSError", "seconds": report["universes"][0]["seconds"]}


def test_not_run_without_complete_recipes_or_when_disabled():
    def loader(prepared):
        raise AssertionError("must not load")

    assert schedule_source_facts_prewarm(_settings(complete=False), [_universe("x")], loader=loader)["status"] == "not_run"
    assert schedule_source_facts_prewarm(_settings(enabled=False), [_universe("x")], loader=loader)["status"] == "not_run"


def test_runs_in_a_background_thread_without_blocking_startup():
    release, done = threading.Event(), threading.Event()

    def slow(prepared):
        release.wait(5)
        done.set()
        return {}

    report = schedule_source_facts_prewarm(_settings(), [_universe("lund")], loader=slow,
                                           library_warmer=lambda: None)
    assert report["status"] in {"scheduled", "running"}
    release.set()
    assert done.wait(5)


def test_library_warm_failure_is_recorded_and_facts_still_load():
    def broken_library():
        raise RuntimeError("manifest")

    report = schedule_source_facts_prewarm(_settings(), [_universe("lund")], loader=lambda p: {},
                                           start=False, library_warmer=broken_library)

    assert report["library"]["status"] == "failed"
    assert report["universes"][0]["status"] == "ready"
    assert report["status"] == "partial"
