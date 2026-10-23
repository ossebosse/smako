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
    assert not cache.save("view", "after-erasure", {})
    replacement = OwnedPlannerArtifacts(store, "a" * 64)
    assert replacement.save("view", "context", {"new": True})
    assert cache.load("view", "context") is None
    assert not cache.save("view", "context", {"stale": True})


def test_owner_migration_transfers_artifacts_and_invalidates_old_worker(tmp_path):
    store = PlanStore(tmp_path / "plans.sqlite")
    cache = OwnedPlannerArtifacts(store, "a" * 64)
    assert cache.save("view", "context", {"rows": [1]})
    with store._connect() as connection:
        connection.execute("UPDATE personal_private_state SET owner_actor_hash=? WHERE id=?",
                           ("b" * 64, cache.private_id))
    assert cache.load("view", "context") is None
    assert not cache.save("view", "context", {"stale": True})
    assert OwnedPlannerArtifacts(store, "b" * 64).load("view", "context") == {"rows": [1]}


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
    assert report["prepared_menu_hit"] is True
    assert sum(p.get("qualification_cache_hits", 0) for p in second.diagnostics.pools) > 0
    # Erase durable cache, then reproduce with ordinary qualification/search.
    with store._connect() as connection:
        connection.execute("DELETE FROM planner_owned_artifacts")
    _, cold = run()
    assert cold.optimized_basket == first.optimized_basket
    assert cold.personal.slots == first.personal.slots


def test_failed_prepared_checkout_returns_to_ordinary_search(tmp_path):
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import PolicyConflict

    request, universe, facts, pantry = fixture()
    settings = replace(planner(request, universe, facts, pantry).settings,
                       library_search_policy="smako-verified-reference-v1")
    cache = OwnedPlannerArtifacts(PlanStore(tmp_path / "plans.sqlite"), "a" * 64)
    old = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache).create()
    subject = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache)
    original, calls = subject.auditor.audit, []

    def audit(*args, **kwargs):
        calls.append(True)
        if len(calls) == 1:
            raise PolicyConflict("Synthetic prepared checkout rejection")
        return original(*args, **kwargs)

    subject.auditor.audit = audit
    result = subject.create()
    assert result.optimized_basket == old.optimized_basket
    assert not result.personal.checks["verified_reference"].get("prepared_menu_hit")
    assert result.personal.checks["checkout_audit"]["passed"] and len(calls) >= 2


@pytest.mark.parametrize("change", ["pantry", "facts", "date", "settings", "locks", "view"])
def test_context_invalidation(change):
    from datetime import timedelta

    request, universe, facts, pantry = fixture()
    subject = planner(request, universe, facts, pantry)
    old = planner_context(subject)
    if change == "pantry":
        subject.items = [{**item, "quantity": item["quantity"] + 1} for item in subject.items]
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


def test_unrelated_revision_is_not_a_cached_basket_input_but_consumption_is():
    request, universe, facts, pantry = fixture()
    subject = planner(request, universe, facts, pantry)
    old = planner_context(subject)
    subject.state = deepcopy(subject.state)
    subject.state["revision"] += 1
    subject.state["id"] = "materialized-private-record"
    subject.request.personal.pantry_revision += 1
    assert planner_context(subject) == old
    subject.state["ledger"] = [{"plan_id": subject.plan_id, "action": "consume", "rows": []}]
    assert planner_context(subject) != old


def test_frozen_axfood_manifest_invalidates_even_identical_projected_facts():
    from app.services.personal_source_facts import FactsCollection

    request, universe, facts, pantry = fixture()
    subject = planner(request, universe, FactsCollection(facts, source_manifests=("a" * 64,)), pantry)
    old = planner_context(subject)
    subject.facts.source_manifests = ("b" * 64,)
    assert planner_context(subject) != old


def test_capacity_cache_requires_current_full_qualification_views(tmp_path):
    from app.services.personal_planner import PersonalPlanner

    request, universe, facts, pantry = fixture()
    request = request.model_copy(deep=True)
    request.recipes = 3
    request.personal.meals[0].count = 3
    settings = replace(planner(request, universe, facts, pantry).settings,
                       library_search_policy="smako-verified-reference-v1")
    cache = OwnedPlannerArtifacts(PlanStore(tmp_path / "plans.sqlite"), "a" * 64)
    subject = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache)
    view = {"qualified": 3, "rows": {str(n): {"status": "passed"} for n in range(3)}}
    assert cache.save("qualification", "view-key", view)
    subject._qualification_views = {"dinner": "view-key"}
    subject.diagnostics.pools = [{"meal_type": "dinner", "raw": 3, "qualified": 3}]
    subject._retain_capacity_proof({"depth": 3, "attempt": 1, "beam_pruned": 0,
        "scope": "qualified_dinner_pool", "status": "PROVEN_INFEASIBLE", "dimension": "dish_form",
        "maximum_slots": 2, "required_slots": 3})
    fresh = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache)
    assert fresh._reuse_capacity_proof()
    with cache.store._connect() as connection:
        connection.execute("DELETE FROM planner_owned_artifacts WHERE kind='qualification'")
    fresh = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache)
    assert not fresh._reuse_capacity_proof()


def test_new_facts_requalify_owned_old_menu_and_never_reuse_old_nutrition(tmp_path):
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_source_facts import FactsCollection

    request, universe, facts, pantry = fixture()
    settings = replace(planner(request, universe, facts, pantry).settings,
                       library_search_policy="smako-verified-reference-v1")
    cache = OwnedPlannerArtifacts(PlanStore(tmp_path / "plans.sqlite"), "a" * 64)
    facts = FactsCollection(facts)
    first_subject = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache)
    first = first_subject.create()
    # Deliberately leave FactsCollection.version stale to verify content binding.
    for key, value in list(facts.items()):
        facts[key] = replace(value, nutrition={k: v * 2 for k, v in value.nutrition.items()})
    second = PersonalPlanner(request, settings, universe, pantry, facts=facts, now=NOW, artifacts=cache)
    assert second.facts_version != first_subject.facts_version
    result = second.create()
    assert result.optimized_basket.total <= first.optimized_basket.total
    assert result.personal.checks["nutrition"] != first.personal.checks["nutrition"]
    assert result.personal.checks["verified_reference"]["publications"][0]["selected_track"] == "previous"
