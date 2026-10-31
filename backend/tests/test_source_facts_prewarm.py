import threading
from types import SimpleNamespace

import pytest
from app.services.source_facts_prewarm import schedule_source_facts_prewarm


def _settings(complete=True, enabled=True, policy="smako-current-library-v2"):
    return SimpleNamespace(complete_recipes_enabled=complete, source_facts_prewarm_enabled=enabled,
                           library_search_policy=policy)


def _universe(name):
    return SimpleNamespace(universe=SimpleNamespace(universe_id=name))


def _prepare(prepared, facts, *, portions):
    assert portions == (1, 2, 3, 4)
    return {"ready": True, "persistence_failures": 0, "content_variants": 2462,
            "portion_views": {str(n): 2462 for n in portions}}


@pytest.mark.parametrize("policy, historical", [
    ("smako-current-library-v2", False), ("smako-verified-reference-v1", True), ("legacy", True),
])
def test_policy_prepares_required_indexes_without_eager_history(monkeypatch, policy, historical):
    from app.services import recipe_library

    calls = []
    for name in ("_registered", "_registered_history", "_current_issued_index",
                 "_issued_index", "_registered_portions"):
        monkeypatch.setattr(recipe_library, name,
                            lambda *args, name=name: calls.append((name, args)))
    result = schedule_source_facts_prewarm(_settings(policy=policy), [_universe("u")],
        loader=lambda p: {}, preparer=_prepare, start=False)
    assert result["status"] == "ready"
    assert (("_registered_history", ()) in calls) is historical
    index = "_issued_index" if historical else "_current_issued_index"
    other = "_current_issued_index" if historical else "_issued_index"
    assert [(name, args) for name, args in calls if name == index] == [
        (index, (n,)) for n in (1, 2, 3, 4)]
    assert not any(name == other for name, _ in calls)


def test_loads_each_active_universe_with_the_shared_loader():
    seen = []
    report = schedule_source_facts_prewarm(
        _settings(), [_universe("lund"), _universe("malmo")],
        loader=lambda prepared: seen.append(prepared.universe.universe_id) or {"k": 1}, start=False,
        library_warmer=lambda: seen.append("library"), preparer=_prepare)

    assert seen == ["library", "lund", "malmo"]
    assert report["status"] == "ready"
    assert [r["fact_rows"] for r in report["universes"]] == [1, 1]
    assert all(r["shared_preparation"]["portion_views"] ==
               {str(n): 2462 for n in (1, 2, 3, 4)} for r in report["universes"])


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
                                           library_warmer=lambda: None, preparer=_prepare)
    assert report["status"] in {"scheduled", "running"}
    release.set()
    assert done.wait(5)


def test_library_warm_failure_is_recorded_and_facts_still_load():
    def broken_library():
        raise RuntimeError("manifest")

    report = schedule_source_facts_prewarm(_settings(), [_universe("lund")], loader=lambda p: {},
                                           start=False, library_warmer=broken_library, preparer=_prepare)

    assert report["library"]["status"] == "failed"
    assert report["universes"][0]["status"] == "ready"
    assert report["status"] == "partial"


def test_prepares_the_same_universe_and_facts_without_changing_them(monkeypatch):
    from app.services import meal_prepared_artifacts

    prepared = _universe("new-price-generation")
    facts = {("store", "product"): object()}
    seen = []

    def prepare(actual, loaded, *, portions):
        assert actual is prepared and loaded is facts
        seen.append((actual.universe.universe_id, portions))
        return _prepare(actual, loaded, portions=portions)

    monkeypatch.setattr(meal_prepared_artifacts, "prepare_current_sources", prepare)
    report = schedule_source_facts_prewarm(_settings(), [prepared], loader=lambda p: facts,
                                          library_warmer=lambda: None, start=False)

    assert seen == [("new-price-generation", (1, 2, 3, 4))]
    assert report["status"] == "ready" and len(facts) == 1


def test_partial_persistence_is_reported_without_rejecting_the_universe():
    prepared = _universe("retained-valid-prices")
    report = schedule_source_facts_prewarm(_settings(), [prepared], loader=lambda p: {},
        library_warmer=lambda: None, start=False,
        preparer=lambda *args, **kwargs: {"ready": False, "persistence_failures": 1})

    assert report["status"] == "partial"
    assert report["universes"][0]["error_type"] == "RuntimeError"
    assert prepared.universe.universe_id == "retained-valid-prices"


def test_legacy_keeps_the_existing_fact_load_without_current_library_preparation():
    seen = []
    def forbidden(*args, **kwargs):
        raise AssertionError("legacy must not prepare the current library")
    report = schedule_source_facts_prewarm(_settings(policy="legacy"), [_universe("legacy")],
        loader=lambda p: seen.append(p) or {}, library_warmer=lambda: None,
        start=False, preparer=forbidden)
    assert len(seen) == 1 and report["status"] == "ready"
    assert "shared_preparation" not in report["universes"][0]


def test_only_one_heavy_preparation_runs_at_a_time():
    entered, release, second_entered = threading.Event(), threading.Event(), threading.Event()

    def first(prepared, facts, *, portions):
        entered.set()
        assert release.wait(5)
        return _prepare(prepared, facts, portions=portions)

    def second(prepared, facts, *, portions):
        second_entered.set()
        return _prepare(prepared, facts, portions=portions)

    schedule_source_facts_prewarm(_settings(), [_universe("first")], loader=lambda p: {},
                                 library_warmer=lambda: None, preparer=first)
    assert entered.wait(5)
    try:
        schedule_source_facts_prewarm(_settings(), [_universe("second")], loader=lambda p: {},
                                     library_warmer=lambda: None, preparer=second)
        assert not second_entered.wait(0.1)
    finally:
        release.set()
    assert second_entered.wait(5)
