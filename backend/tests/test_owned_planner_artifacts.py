from copy import deepcopy
from dataclasses import replace

import pytest
from app.services.plan_store import PlanStore
from app.services.planner_artifacts import OwnedPlannerArtifacts
from app.services.planner_context import planner_context

from backend.tests.test_complete_scope_incumbents import fixture, planner
from backend.tests.test_personal_planning_v2 import NOW


def test_owned_artifact_survives_restart_and_cannot_cross_owner(tmp_path):
    store = PlanStore(tmp_path / "plans.sqlite")
    cache = OwnedPlannerArtifacts(store, "a" * 64)
    assert cache.save("view", "context", {"rows": [1, 2]})
    assert OwnedPlannerArtifacts(PlanStore(store.path), "a" * 64).load("view", "context") == {"rows": [1, 2]}
    assert OwnedPlannerArtifacts(store, "b" * 64).load("view", "context") is None
    store.erase_owned(owner_actor_hash="a" * 64)
    assert cache.load("view", "context") is None


def test_corrupt_and_uncommitted_rows_are_misses(tmp_path):
    store = PlanStore(tmp_path / "plans.sqlite")
    cache = OwnedPlannerArtifacts(store, "a" * 64)
    cache.save("view", "x", {"complete": True})
    with store._connect() as connection:
        connection.execute("UPDATE planner_owned_artifacts SET payload=?", (b"broken",))
    assert cache.load("view", "x") is None
    with pytest.raises(RuntimeError), store._connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("DELETE FROM planner_owned_artifacts")
        raise RuntimeError("crash before commit")
    with store._connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM planner_owned_artifacts").fetchone()[0] == 1


def test_existing_private_state_restore_suppression_cascades_to_cache_only_owner(tmp_path):
    store = PlanStore(tmp_path / "plans.sqlite")
    cache = OwnedPlannerArtifacts(store, "a" * 64)
    assert cache.save("view", "x", {})
    with store._connect() as connection:
        private_id = connection.execute("SELECT id FROM personal_private_state").fetchone()[0]
        # Same operation and FK mode as privacy_erasure_ledger on restore.
        connection.execute("DELETE FROM personal_private_state WHERE id=?", (private_id,))
        assert connection.execute("SELECT COUNT(*) FROM planner_owned_artifacts").fetchone()[0] == 0


def test_budget_refuses_growth_without_deleting_certificates(tmp_path, monkeypatch):
    from app.services import planner_artifacts

    store = PlanStore(tmp_path / "plans.sqlite")
    cache = OwnedPlannerArtifacts(store, "a" * 64)
    monkeypatch.setattr(planner_artifacts, "MAX_ROWS", 1)
    assert cache.save("certificate", "x", {})
    assert not cache.save("view", "y", {})
    assert cache.load("certificate", "x") == {}


def test_qualification_and_verified_menu_survive_new_planner_instances(tmp_path):
    from app.services.personal_planner import PersonalPlanner

    request, universe, facts, pantry = fixture()
    settings = replace(planner(request, universe, facts, pantry).settings,
                       library_search_policy="smako-verified-reference-v1")
    store = PlanStore(tmp_path / "plans.sqlite")
    cache = OwnedPlannerArtifacts(store, "a" * 64)

    def run():
        subject = PersonalPlanner(request, settings, universe, deepcopy(pantry), facts=facts,
            now=NOW,
            artifacts=cache)
        return subject, subject.create()

    _, first = run()
    second, result = run()
    assert result.optimized_basket == first.optimized_basket
    assert result.personal.slots == first.personal.slots
    report = result.personal.checks["verified_reference"]
    assert report["loaded_publications"] == 1 and report["replayed_publications"] == 0
    assert sum(p.get("qualification_cache_hits", 0) for p in second.diagnostics.pools) > 0
    # Erase durable cache, then reproduce with ordinary qualification/search.
    with store._connect() as connection:
        connection.execute("DELETE FROM planner_owned_artifacts")
    _, cold = run()
    assert cold.optimized_basket == first.optimized_basket
    assert cold.personal.slots == first.personal.slots


@pytest.mark.parametrize("change", ["pantry", "facts", "date", "settings", "locks", "view"])
def test_context_invalidation(change):
    from datetime import timedelta

    request, universe, facts, pantry = fixture()
    subject = planner(request, universe, facts, pantry)
    old = planner_context(subject)
    if change == "pantry":
        subject.state = deepcopy(subject.state)
        subject.state["revision"] += 1
    elif change == "facts":
        subject.facts_version += "changed"
    elif change == "date":
        subject.pricing_date += timedelta(days=1)
    elif change == "view":
        from types import SimpleNamespace
        subject.view = SimpleNamespace(cache_identity="changed campaign/freshness partition")
    elif change == "settings":
        subject.settings = replace(subject.settings, library_seed_pool_limit=1)
    elif change == "locks":
        subject.request = subject.request.model_copy(update={"max_stores": 2})
    assert planner_context(subject) != old


def test_same_effective_clock_reuses_context_but_final_ages_are_request_owned():
    from datetime import timedelta

    request, universe, facts, pantry = fixture()
    subject = planner(request, universe, facts, pantry)
    old = planner_context(subject)
    subject.now += timedelta(seconds=1)
    assert planner_context(subject) == old
