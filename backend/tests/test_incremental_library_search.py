"""Synthetic topology/price tests; authentic frozen data is checked separately."""
from collections import Counter

import pytest
from app.errors import IncompleteBasketError
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import MenuOptimizer


def options(names, days=2):
    recipes = [Recipe(name=name, servings=1,
        ingredients=[RecipeIngredient(name=name, quantity=1, unit="g")],
        instructions=["Synthetic test"]) for name in names]
    return [[MealSlot(id=f"d{day}", day=day, meal_type="dinner", recipe=r)
             for r in recipes] for day in range(1, days+1)]


def run(cohorts, *, evaluate, accepts=lambda slots, final: True, **kwargs):
    return MenuOptimizer().optimize_library_slots(
        cohorts, evaluate=evaluate, accepts=accepts, score=lambda slots, cost: cost,
        retention_score=lambda slots, cost: cost, **kwargs)


def test_seed_once_and_future_packs_compete_without_new_full_search():
    trace, calls = [], Counter()
    def evaluate(slots, *, final):
        calls[len(slots)] += 1
        return sum({"A": 10, "B": 8, "C": 6, "D": 4}[s.recipe.name] for s in slots)
    chosen, cost = run([(1, options("AB")), (2, options("ABC")),
                        (3, options("ABC")), (4, options("ABCD"))],
                       evaluate=evaluate, search_trace=trace)
    assert cost == 8 and [s.recipe.name for s in chosen] == ["D", "D"]
    assert calls[1] == 2  # only the initial two prefixes, not every generation
    assert {r["library_generation"] for r in trace if r["library_phase"] == "seed"} == {1}
    assert {r["library_generation"] for r in trace if r["library_phase"] == "substitution"} == {2, 4}
    assert all(r["sweep"] <= 2 for r in trace if r["library_phase"] == "substitution")


def test_expensive_invalid_and_unpriceable_additions_preserve_valid_seed():
    seen = []
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        seen.append(names)
        if "C" in names:
            raise IncompleteBasketError("Synthetic missing qualification")
        return sum({"A": 2, "B": 10}[name] for name in names)
    chosen, cost = run([(1, options("A")), (2, options("ABCD"))], evaluate=evaluate,
        accepts=lambda slots, final: all(s.recipe.name != "D" for s in slots))
    assert cost == 4 and all(s.recipe.name == "A" for s in chosen)
    assert not any("D" in names for names in seen)


def test_failed_seed_retries_larger_pool_and_reuses_exact_prefix():
    calls, trace = Counter(), []
    def evaluate(slots, *, final):
        calls[(tuple(s.recipe.name for s in slots), final)] += 1
        return len(slots)
    chosen, _ = run([(1, options("A")), (2, options("AB"))], evaluate=evaluate,
        accepts=lambda slots, final: not final or any(s.recipe.name == "B" for s in slots),
        search_trace=trace)
    assert any(s.recipe.name == "B" for s in chosen)
    assert calls[(("A",), False)] == 1
    assert sum(r.get("library_shared_basket_cache_hits", 0) for r in trace) == 1
    assert sum(r["evaluations_executed"] for r in trace) == sum(calls.values())
    seed_attempts = {r["library_generation"]: r["attempt"] for r in trace if r["library_phase"] == "seed"}
    assert seed_attempts[1] != seed_attempts[2]  # branch diagnostics stay separate


def test_empty_early_meal_type_uses_first_complete_pool():
    early = options("A")
    early[1] = []
    trace = []
    chosen, _ = run([(1, early), (2, options("AB"))],
                    evaluate=lambda slots, final: len(slots), search_trace=trace)
    assert len(chosen) == 2
    assert {r["library_generation"] for r in trace} == {2}


def test_refinement_revisits_older_recipes_after_new_ingredient_changes_basket():
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        if len(names) == 1:
            return {"A": 1, "B": 5, "C": 6}[names[0]]
        # B was uncompetitive in the seed; after C replaces one slot, B shares
        # a package with it and improves the WHOLE basket. No per-dish prices.
        return {("A", "A"): 10, ("A", "C"): 8, ("C", "A"): 8,
                ("B", "C"): 3, ("C", "B"): 3}.get(names, 20)
    chosen, cost = run([(1, options("AB")), (2, options("ABC"))], evaluate=evaluate)
    assert cost == 3 and {s.recipe.name for s in chosen} == {"B", "C"}


def test_bounded_pair_can_improve_when_neither_single_swap_does():
    trace = []
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        return {("A",): 1, ("A", "A"): 10, ("B", "C"): 3}.get(names, 15)
    chosen, cost = run([(1, options("A")), (2, options("ABC"))], evaluate=evaluate, search_trace=trace)
    assert cost == 3 and [s.recipe.name for s in chosen] == ["B", "C"]
    paired = [r for r in trace if r["library_phase"] == "paired_refinement"]
    assert len(paired) == 1 and paired[0]["proposals"] <= 128


def test_pair_budget_stays_fixed_when_many_recipes_qualify():
    trace = []
    _, cost = run([(1, options("A", days=5)), (2, options("ABCDEFGHIJKLM", days=5))],
        evaluate=lambda slots, final: sum(ord(s.recipe.name)-64 for s in slots), search_trace=trace)
    paired = next(r for r in trace if r["library_phase"] == "paired_refinement")
    assert cost == 5 and paired["pairs_available"] == 640 and paired["proposals"] == 128


def test_cache_is_call_local_and_keys_include_exact_recipe_and_slot_values():
    first, second = options("A"), options("A")
    # Same recipe ID/name but different authoritative preparation inputs must
    # not inherit a basket. Slot day and meal type are private allocation inputs.
    second[0][0].recipe.instructions.append("Changed instructions")
    second[0][0] = second[0][0].model_copy(update={"day": 3, "meal_type": "breakfast"})
    calls = []
    def evaluate(slots, *, final):
        calls.append((slots[0].day, slots[0].meal_type, len(slots[0].recipe.instructions), final))
        return 1
    kwargs = {"evaluate": evaluate, "accepts": lambda slots, final: not final}
    for _ in range(2):
        with pytest.raises(IncompleteBasketError):
            run([(1, first), (2, second)], **kwargs)
    assert calls.count((1, "dinner", 1, False)) == 2
    assert calls.count((3, "breakfast", 2, False)) == 2


def test_single_meal_runs_final_checks_and_all_failed_pools_still_fail():
    calls = []
    def evaluate(slots, *, final):
        calls.append(final)
        raise IncompleteBasketError("No qualified complete basket")
    with pytest.raises(IncompleteBasketError, match="No qualified complete basket"):
        run([(1, options("A", days=1)), (2, options("AB", days=1))], evaluate=evaluate)
    assert calls and all(calls)


def test_restricted_variant_seed_retries_full_pool_when_joint_constraints_need_omitted_variant():
    trace = []
    chosen, cost = run([(1, options("ABC"))],
        seed_selector=lambda groups: [group[:1] for group in groups],
        evaluate=lambda slots, final: len(slots),
        accepts=lambda slots, final: not final or any(s.recipe.name == "C" for s in slots),
        search_trace=trace)
    assert cost == 2 and any(s.recipe.name == "C" for s in chosen)
    assert any(row.get("seed_full_pool_retry") for row in trace)
    assert any(row.get("seed_variants_retained") == 2 for row in trace)


def test_omitted_seed_variants_still_improve_the_complete_week():
    chosen, cost = run([(1, options("ABC"))],
        seed_selector=lambda groups: [group[:1] for group in groups],
        evaluate=lambda slots, final: sum({"A": 10, "B": 5, "C": 1}[s.recipe.name] for s in slots))
    assert cost == 2 and all(s.recipe.name == "C" for s in chosen)


def test_only_current_versions_enter_publication_cohorts():
    from app.services.meal_library_content import identity, manifest_entries
    from app.services.recipe_library import current_recipe_generations, current_recipes
    generations = current_recipe_generations()
    assert set(generations) == {identity(r) for r in current_recipes()}
    assert not set(generations).intersection(manifest_entries().get("revocations", {}))
    for generation in set(generations.values()):
        older = {identity(r) for r in current_recipes(generation-1)}
        published = {identity(r) for r in current_recipes(generation)}
        new = {key for key, number in generations.items() if number == generation}
        assert new <= published and not new.intersection(older)


def test_shared_baskets_remain_bounded_as_library_grows():
    import weakref
    class Result:
        def __init__(self, cost):
            self.cost = cost
    references, peak = [], 0
    def evaluate(slots, *, final):
        nonlocal peak
        result = Result(sum(int(s.recipe.name) for s in slots))
        references.append(weakref.ref(result))
        peak = max(peak, sum(r() is not None for r in references))
        return result
    old = options([str(i) for i in range(300)], days=1)
    grown = options([str(i) for i in range(600)], days=1)
    _, result = MenuOptimizer().optimize_library_slots([(1, old), (2, grown)],
        evaluate=evaluate, accepts=lambda slots, final: True,
        score=lambda slots, result: result.cost, retention_score=lambda slots, result: result.cost)
    assert result.cost == 0
    # Each cache is bounded at 256; a few active proposal/beam objects may live
    # outside it. More recipes must not retain all complete checkout objects.
    assert peak <= 530


@pytest.mark.parametrize("reject_final", [False, True])
def test_real_planner_qualifies_once_and_audits_winner_independently(monkeypatch, reject_final):
    from app.services.personal_policy import PolicyConflict

    from backend.tests.test_complete_scope_incumbents import fixture, planner
    request, universe, facts, pantry = fixture()
    subject = planner(request, universe, facts, pantry)
    calls, original = [], subject.basket
    search_done = False
    original_search = subject.service.menu_optimizer.optimize_library_slots
    def search(*args, **kwargs):
        nonlocal search_done
        result = original_search(*args, **kwargs)
        search_done = True
        return result
    def basket(slots, **kwargs):
        calls.append((tuple(s.recipe.name for s in slots), kwargs.get("final", True)))
        if search_done and reject_final:
            raise PolicyConflict("Synthetic independent final audit rejection")
        return original(slots, **kwargs)
    monkeypatch.setattr(subject, "basket", basket)
    monkeypatch.setattr(subject.service.menu_optimizer, "optimize_library_slots", search)
    if reject_final:
        with pytest.raises(PolicyConflict, match="Synthetic independent final audit rejection"):
            subject.create()
        assert search_done and calls[-1][1]
        return
    result = subject.create()
    assert subject._library_search_handled
    assert len(subject.diagnostics.pools) == 1
    chosen = tuple(r.name for r in result.recipes)
    assert calls[-1] == (chosen, True)
    assert calls.count((chosen, True)) >= 2  # search cannot replace final audit
    assert result.personal.checks["checkout_audit"]["passed"]
    assert result.personal.allocations


def test_legacy_breakfast_can_accompany_complete_mode_without_library_identity():
    from types import SimpleNamespace

    from app.models.personal import MealSettings

    from backend.tests.test_complete_scope_incumbents import fixture, planner
    request, universe, facts, pantry = fixture()
    request.personal.meals = [MealSettings(meal_type="breakfast", count=1, servings=2)]
    subject = planner(request, universe, facts, pantry)
    breakfast = Recipe(name="Synthetic legacy yoghurt", servings=2,
        ingredients=[RecipeIngredient(name="yoghurt naturell", quantity=200, unit="g")],
        instructions=["Servera yoghurten."])
    subject.service.candidate_generator = SimpleNamespace(generate_for_meal_type=lambda *a, **k: [breakfast])
    result = subject.create()
    assert subject._library_search_handled
    assert result.recipes[0].name == breakfast.name and result.recipes[0].design is None
    assert result.personal.checks["checkout_audit"]["passed"]


def test_substitution_selector_bounds_only_the_newer_generation_sweep():
    """LIBRARY_SUBSTITUTION_POOL_LIMIT: tried additions are the selector's choice."""
    trace, seen = [], []
    prices = {"A": 10, "B": 9, "C": 3, "D": 1}

    def evaluate(slots, *, final):
        seen.append(tuple(s.recipe.name for s in slots))
        return sum(prices[s.recipe.name] for s in slots)

    def keep_c(groups):  # a selector that drops the cheapest addition, D
        return [[s for s in group if s.recipe.name != "D"] for group in groups]

    chosen, cost = run([(1, options("AB")), (2, options("ABCD"))], evaluate=evaluate,
                       search_trace=trace, substitution_selector=keep_c)
    substitution = [r for r in trace if r["library_phase"] == "substitution"]
    assert substitution[0]["substitution_variants_available"] == 4  # C and D in two slots
    assert substitution[0]["substitution_variants_retained"] == 2
    assert substitution[0]["proposals"] == 2  # only C, once per slot
    # D still reaches the week through the full-pool refinement after the sweep.
    assert cost == 2 and [s.recipe.name for s in chosen] == ["D", "D"]


def test_without_selector_every_addition_is_tried_as_before():
    trace = []
    run([(1, options("AB")), (2, options("ABCD"))],
        evaluate=lambda slots, final: len(slots), search_trace=trace)
    row = next(r for r in trace if r["library_phase"] == "substitution")
    assert "substitution_variants_available" not in row and row["proposals"] == 4


def test_completed_prefix_survives_a_later_shortlist_that_excludes_its_winner():
    prices = {
        ("A",): 1, ("B",): 3, ("C",): 2,
        ("A", "A"): 10, ("A", "B"): 15, ("B", "A"): 15, ("B", "B"): 2,
        ("C", "A"): 8, ("A", "C"): 8, ("C", "C"): 6,
        ("B", "C"): 12, ("C", "B"): 12,
    }
    def evaluate(slots, *, final):
        return prices[tuple(slot.recipe.name for slot in slots)]
    def refinement(groups):
        return [[slot for slot in group if len(group) <= 2 or slot.recipe.name != "B"]
                for group in groups]

    cohorts = [(1, options("A")), (2, options("AB")), (3, options("ABC"))]
    costs = [run(cohorts[:n], evaluate=evaluate, refinement_selector=refinement)[1]
             for n in (1, 2, 3)]
    assert costs == [10, 2, 2]  # Previously [10, 2, 6].
    # Retention is within this call, never a cached menu from stale prices.
    prices[("B", "B")] = 20
    chosen, cost = run(cohorts, evaluate=evaluate, refinement_selector=refinement)
    assert cost == 6 and all(s.recipe.name == "C" for s in chosen)


def test_retained_prefix_does_not_redirect_the_original_later_joint_anchor():
    def evaluate(slots, *, final):
        names = tuple(s.recipe.name for s in slots)
        if len(names) == 1:
            return ord(names[0]) - 64
        return {("A", "A"): 10, ("B", "B"): 8, ("A", "C"): 9.5,
                ("C", "A"): 9.5, ("C", "C"): 9, ("D", "D"): 1}.get(names, 15)
    def refinement(groups):
        return [[s for s in group if len(group) <= 2 or s.recipe.name in "AC"] for group in groups]
    anchors = []
    def joint(groups, anchor):
        names = tuple(s.recipe.name for s in anchor)
        anchors.append(names)
        if names == ("C", "C"):
            return [(0, 1, groups[0][-1], groups[1][-1])]
        return []
    chosen, cost = run([(1, options("A")), (2, options("AB")), (3, options("ABCD"))],
                      evaluate=evaluate, refinement_selector=refinement,
                      refinement_score=lambda slots, cost: cost, joint_proposals=joint)
    assert ("B", "B") in anchors and anchors[-1] == ("C", "C")
    assert cost == 1 and all(s.recipe.name == "D" for s in chosen)
