"""SYNTHETIC search topology; no retailer prices or modified user requirements."""
import pytest
from app.errors import IncompleteBasketError
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import MenuOptimizer


def test_equivalent_day_permutations_do_not_exhaust_meal_beam():
    recipes = [Recipe(name=name, servings=1,
        ingredients=[RecipeIngredient(name=name, quantity=1, unit="g")], instructions=["synthetic"])
        for name in ("A", "B", "C", "D")]
    options = [[MealSlot(id=f"d{i}", day=i, meal_type="dinner", recipe=r) for r in recipes] for i in (1,2,3)]
    def accepts(slots, *, final):
        names = [s.recipe.name for s in slots]
        return len(set(names)) == len(names) and (not final or set(names) == {"A", "C", "D"})
    def evaluate(slots, *, final):
        return sum(ord(s.recipe.name) - ord("A") for s in slots)
    optimizer = MenuOptimizer()
    # Same width and hard rules. Two permutations of AB consume the old beam.
    with pytest.raises(IncompleteBasketError):
        optimizer.optimize_slots(options, accepts=accepts, evaluate=evaluate, score=lambda s,r:r, beam_width=2)
    trace = []
    chosen, total = optimizer.optimize_slots(options, accepts=accepts, evaluate=evaluate,
        score=lambda s,r:r, beam_width=2, search_trace=trace,
        state_identity=lambda slots: tuple(sorted(s.recipe.name for s in slots)))
    assert {s.recipe.name for s in chosen} == {"A", "C", "D"}
    assert total == 5
    assert trace[1]["equivalent_pruned"] == 1
    assert all(step["retained"] <= 2 for step in trace)
    assert all(step["priced"] == step["retained"] + step["beam_pruned"] for step in trace)


def retry_options():
    recipes = [Recipe(name=name, servings=1,
        ingredients=[RecipeIngredient(name=name, quantity=1, unit="g")], instructions=["synthetic"])
        for name in ("A", "B", "C")]
    return [[MealSlot(id=f"d{i}", day=i, meal_type="dinner", recipe=r) for r in recipes] for i in (1,2)]


def test_bounded_retry_only_after_distinct_prefix_was_lost():
    options = retry_options()
    trace = []
    def accepts(slots, *, final):
        return not final or {s.recipe.name for s in slots} == {"B", "C"}
    calls = []
    def evaluate(slots, *, final):
        calls.append(tuple(s.recipe.name for s in slots))
        return sum(ord(s.recipe.name)-ord("A") for s in slots)
    chosen, cost = MenuOptimizer().optimize_slots(options, evaluate=evaluate, accepts=accepts,
        score=lambda s,r:r, beam_width=1, fallback_beam_width=3, search_trace=trace,
        state_identity=lambda slots: tuple(sorted(s.recipe.name for s in slots)))
    assert {s.recipe.name for s in chosen} == {"B", "C"} and cost == 3
    assert {r["attempt"] for r in trace} == {1,2}
    assert {r["beam_width"] for r in trace} == {1,3}
    assert next(r for r in trace if r.get("retry_reason"))["exhausted"]
    assert calls.count(("A",)) == 1  # unchanged exact prefix reuses request-local result
    assert sum(r["evaluation_cache_hits"] for r in trace if r["attempt"] == 2) >= 1
    assert all(r["priced"] + r["evaluation_rejected"] == r["evaluations_executed"] + r["evaluation_cache_hits"] for r in trace)


@pytest.mark.parametrize("unsafe", [False, True])
def test_no_retry_without_pruning_or_without_safe_identity(unsafe):
    trace = []
    options = retry_options()
    with pytest.raises(IncompleteBasketError):
        MenuOptimizer().optimize_slots(options, evaluate=lambda *a,**k:0,
            accepts=(lambda slots,final: not final) if unsafe else (lambda slots,final:False),
            score=lambda s,r:r, beam_width=1, fallback_beam_width=3, search_trace=trace,
            state_identity=None if unsafe else lambda slots:tuple(s.recipe.name for s in slots))
    assert {r["attempt"] for r in trace} == {1}


def test_retry_branch_diagnostics_do_not_mix_attempts():
    from app.services.planning_diagnostics import PlanningDiagnostics
    diagnostics = PlanningDiagnostics()
    diagnostics.search.append({"depth":1,"attempt":1})
    diagnostics.branch(1,"nutrition")
    diagnostics.search.append({"depth":1,"attempt":2})
    diagnostics.branch(1,"variation")
    rows = diagnostics.snapshot()["search"]
    assert rows[0]["rejections"]["nutrition"] == 1 and rows[0]["rejections"]["variation"] == 0
    assert rows[1]["rejections"]["nutrition"] == 0 and rows[1]["rejections"]["variation"] == 1
