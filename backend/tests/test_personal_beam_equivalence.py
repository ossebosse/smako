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


def test_replacement_does_not_fill_beam_with_a_dish_in_the_fixed_suffix(monkeypatch):
    """Synthetic prices expose the actual replacement constraint callback."""
    from app.config import Settings
    from app.models.personal import MealSettings
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import (
        NOW,
        prepared,
        product,
        recipe,
        request,
        state,
    )

    dishes = [recipe(name) for name in ("A", "B", "C")]
    slots = [MealSlot(id=f"d{i}", day=i, meal_type="dinner", recipe=r)
             for i, r in enumerate(dishes[:2], 1)]
    planner = PersonalPlanner(request(slots=slots, meals=[MealSettings(count=2, servings=1)]),
        Settings(price_provider="mock"), prepared(product("mjölk", 1000, "ml", 20)), state(), now=NOW)
    monkeypatch.setattr(planner, "_candidates", lambda meal: dishes[1:])
    monkeypatch.setattr(planner.service.menu_optimizer, "accepts_recipes", lambda *a, **k: True)
    optimize = planner.service.menu_optimizer.optimize_slots

    class SearchChecked(Exception):
        pass

    def check_search(options, *, accepts, **kwargs):
        chosen, _ = optimize(options, accepts=accepts,
            evaluate=lambda slots, final: sum(1 if s.recipe.name == "B" else 10 for s in slots),
            score=lambda slots, total: total, beam_width=1)
        assert [s.recipe.name for s in chosen] == ["C", "B"]
        assert chosen[1] == slots[1]  # Fixed slot/order survives; no allocation permutation.
        raise SearchChecked

    monkeypatch.setattr(planner.service.menu_optimizer, "optimize_slots", check_search)
    with pytest.raises(SearchChecked):
        planner.create(replace_slot="d1")


def test_streaming_slot_beam_bounds_live_baskets_without_pruning_candidates():
    import weakref
    class Result:
        def __init__(self,cost):self.cost=cost
    refs=[];peak=0
    recipes=[Recipe(name=f"Load {n:04d}",servings=1,
        ingredients=[RecipeIngredient(name="ris",quantity=n+1,unit="g")],instructions=["synthetic"])
        for n in range(600)]
    options=[[MealSlot(id=f"breakfast-{day}",day=day,meal_type="breakfast",recipe=r)
        for r in recipes] for day in (1,2)]
    def evaluate(slots,*,final):
        nonlocal peak
        value=Result(sum(600-int(s.recipe.name.split()[-1]) for s in slots))
        refs.append(weakref.ref(value));peak=max(peak,sum(r() is not None for r in refs))
        return value
    trace=[]
    chosen,result=MenuOptimizer().optimize_slots(options,evaluate=evaluate,
        accepts=lambda slots,final:True,score=lambda slots,r:r.cost,beam_width=8,
        search_trace=trace,state_identity=lambda slots:tuple(sorted(s.recipe.name for s in slots)))
    assert [s.recipe.name for s in chosen]==["Load 0599","Load 0599"] and result.cost==2
    assert sum(r["proposals"] for r in trace)==600+8*600
    assert peak<=290, f"Complete partial baskets retained: {peak}"
    assert all(r["retained"]==8 and r["priced"]==r["retained"]+r["beam_pruned"] for r in trace)
