"""Contract examples, not historical market reproductions or optimality proofs."""
from decimal import Decimal

import pytest
from app.errors import IncompleteBasketError
from app.services.verified_menu_search import SearchBudget, verified_search


@pytest.mark.parametrize("reference, improvement", [("761.45", "783.42"), ("480.97", "487.85"), ("340.64", "361.81")])
def test_more_expensive_independent_track_cannot_replace_reference(reference, improvement):
    calls = []

    def search(track, emit):
        calls.append(track)
        emit((track,), Decimal(reference if track == "reference" else improvement))

    chosen, result, report = verified_search(
        search, audit=lambda slots: Decimal(reference if slots == ("reference",) else improvement),
        accepts=lambda slots: True, rank=lambda slots, value: (value,),
        budget=SearchBudget(10, 10),
    )
    assert chosen == ("reference",) and result == Decimal(reference)
    assert calls == ["reference", "improvement"]
    assert report["global_optimum_proven"] is False


def test_audit_failure_tries_next_candidate_and_uses_current_checkout():
    def search(track, emit):
        emit((track,), Decimal("1" if track == "improvement" else "4"))

    def audit(slots):
        if slots == ("improvement",):
            raise IncompleteBasketError("Rejected checkout")
        return Decimal(5)  # Cached/old price 4 must never be copied.

    chosen, value, report = verified_search(search, audit=audit, accepts=lambda s: True,
        rank=lambda s, v: (v,), budget=SearchBudget(10, 10))
    assert chosen == ("reference",) and value == Decimal(5)
    assert report["audit_rejected"] == 1


def test_budget_stop_retains_completed_candidates_even_before_track_returns():
    budget = SearchBudget(2, 2)

    def search(track, emit):
        if track == "reference":
            emit(("base",), 10)
        else:
            budget.proposal()
            budget.evaluation()
            emit(("better",), 8)
            budget.proposal()
            budget.evaluation()
            budget.evaluation()

    assert verified_search(search, audit=lambda s: 8 if s == ("better",) else 10,
        accepts=lambda s: True, rank=lambda s, v: (v,), budget=budget)[1] == 8
    assert budget.reason == "evaluations"


def test_budget_without_a_complete_candidate_is_incomplete_not_impossible():
    budget = SearchBudget(1, 1)

    def search(track, emit):
        if track == "reference":
            raise IncompleteBasketError("Search miss")
        budget.proposal()
        budget.proposal()

    with pytest.raises(IncompleteBasketError, match="ofullständig"):
        verified_search(search, audit=lambda s: None, accepts=lambda s: True,
                        rank=lambda s, v: (v,), budget=budget)


def test_equal_price_keeps_previous_winner_and_revoked_candidate_is_rejected():
    def search(track, emit):
        emit((track,), 10)

    chosen, _, report = verified_search(search, audit=lambda s: 10, accepts=lambda s: s != ("revoked",),
        rank=lambda s, v: (v,), budget=SearchBudget(2, 2),
        previous=[(("previous",), 100), (("revoked",), 0)])
    assert chosen == ("previous",)
    assert report["constraint_rejected"] == 1


def test_reaudited_price_can_increase_under_changed_facts():
    chosen, value, _ = verified_search(lambda track, emit: emit((track,), 20),
        audit=lambda s: 30 if s == ("previous",) else 20,
        accepts=lambda s: True, rank=lambda s, v: (v,), budget=SearchBudget(2, 2),
        previous=[(("previous",), 1)])
    assert chosen != ("previous",) and value == 20


def test_pinned_reference_keeps_publication_order_and_exact_values():
    from app.services.meal_library_content import identity
    from app.services.planner_context import content_digest
    from app.services.recipe_library import current_recipes
    from app.services.reference_library import reference_manifest

    pin = reference_manifest()["manifest"]
    assert pin["recipes"] == [[identity(r), content_digest(r)] for r in current_recipes()]
    assert len(pin["recipes"]) == 262


def test_real_planner_reference_is_audited_and_policy_stays_opt_in():
    from dataclasses import replace

    from backend.tests.test_complete_scope_incumbents import fixture, planner

    request, universe, facts, pantry = fixture()
    original = planner(request, universe, facts, pantry)
    baseline = original.create()
    subject = planner(request, universe, facts, pantry)
    subject.settings = replace(subject.settings, library_search_policy="smako-verified-reference-v1")
    result = subject.create()
    assert original.settings.library_search_policy == "legacy"
    assert result.optimized_basket.total <= baseline.optimized_basket.total
    assert result.personal.checks["checkout_audit"]["passed"]
    assert result.personal.checks["verified_reference"]["verified_candidates"] > 0


def test_exhaustive_prefix_does_not_label_later_bounded_search_exhaustive():
    from app.services.complete_recipes import completed_search_outcome

    result = completed_search_outcome({"search": [
        {"library_phase": "exhaustive", "library_prefix_recipes": 262},
        {"library_phase": "substitution", "library_prefix_recipes": 1000}]})
    assert result["search_budget"]["week_search_method"] == "bounded_search_with_exhaustive_prefixes"


def test_synthetic_enrichment_search_miss_keeps_old_valid_menu_without_copying_its_price():
    from backend.tests.test_incremental_library_search import options, run

    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        if len(names) < 3:
            return sum(1 if name == "A" else 2 for name in names)
        return {("A",) * 3: Decimal("340.64"), ("B",) * 3: Decimal("361.81")}.get(names, Decimal(500))

    old = run([(1, options("AB", days=3))], evaluate=evaluate)
    widened = [(1, options("ABC", days=3))]
    missed = run(widened, evaluate=evaluate,
        seed_selector=lambda groups: [[s for s in group if s.recipe.name == "B"] for group in groups],
        refinement_selector=lambda groups: [[s for s in group if s.recipe.name != "A"] for group in groups])
    assert old[1] == Decimal("340.64") and missed[1] == Decimal("361.81")
    chosen, cost, _ = verified_search(lambda track, emit: emit(*(old if track == "reference" else missed)),
        audit=lambda slots: evaluate(slots, final=True), accepts=lambda slots: True,
        rank=lambda slots, value: value, budget=SearchBudget(10, 10))
    assert cost == Decimal("340.64") and all(s.recipe.name == "A" for s in chosen)


def test_previous_menu_is_reaudited_even_when_ordinary_search_misses(monkeypatch):
    from app.errors import IncompleteBasketError
    from app.services.library_publications import slots_record

    from backend.tests.test_complete_scope_incumbents import fixture, planner

    request, universe, facts, pantry = fixture()
    old = planner(request, universe, facts, pantry).create()
    subject = planner(request, universe, facts, pantry)
    subject.previous_menus = (slots_record(old.personal.slots),)

    def miss(*args, **kwargs):
        raise IncompleteBasketError("Synthetic heuristic miss after adding qualified recipes")

    monkeypatch.setattr(subject.service.menu_optimizer, "optimize_library_slots", miss)
    result = subject.create()
    assert result.optimized_basket == old.optimized_basket
    assert result.personal.checks["reaudited_previous_menu"]["selected_track"] == "previous"
    assert result.personal.checks["checkout_audit"]["passed"]
