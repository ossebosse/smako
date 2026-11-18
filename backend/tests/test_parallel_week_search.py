"""Workers price predicted menus; the search finds the same weeks (2026-11-18)."""
import os

import pytest
from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services import planner_processes as pp
from app.services.menu_optimizer import MenuBoundPruned, MenuOptimizer

pytestmark = pytest.mark.skipif(not hasattr(os, "fork"), reason="fork")


def groups(count=20, days=3):
    recipes = [Recipe(name=f"R{i:02d}", servings=1, ingredients=[RecipeIngredient(name="ris", quantity=i + 1, unit="g")],
                      instructions=["synthetic"]) for i in range(count)]
    return [[MealSlot(id=f"dinner-{d}", day=d, meal_type="dinner", recipe=r) for r in recipes]
            for d in range(1, days + 1)]


def price(names):
    # Shared "packages": recipes with the same last digit share a cost.
    singles = sum((int(n[1:]) * 37) % 23 + 10 for n in names)
    return singles - 6 * (len(names) - len({n[-1] for n in names}))


def search(monkeypatch, workers):
    monkeypatch.setenv("SMAKO_MENU_SEARCH_STALL_SECONDS", "0")
    monkeypatch.setenv("SMAKO_PLANNER_MEMORY_CHECK", "0")
    monkeypatch.setenv("SMAKO_PLANNER_PROCESSES", "4")
    priced = []

    def evaluate(slots, final):
        names = tuple(s.recipe.name for s in slots)
        priced.append(names)
        if names[0] == names[1]:
            raise ValueError("synthetic joint rejection")
        return price(names)

    def bounded(slots, bound):
        if sum((int(s.recipe.name[1:]) * 37) % 23 + 10 for s in slots) - 12 > bound:
            raise MenuBoundPruned
        return evaluate(slots, final=True)

    trace = []
    chosen, cost = MenuOptimizer().optimize_slots(
        groups(), complete_first=True, accepts=lambda slots, final: len({s.recipe.name for s in slots}) >= len(slots) - 1,
        evaluate=evaluate, bounded_evaluate=bounded, score=lambda slots, cost: cost, search_trace=trace,
        candidate_priority=lambda slot: (int(slot.recipe.name[1:]) * 37) % 23,
        evaluation_workers=pp.speculative_workers if workers else None)
    return [s.recipe.name for s in chosen], cost, trace[-1]


def test_parallel_pricing_finds_the_same_weeks_in_the_same_order(monkeypatch):
    names, cost, alone = search(monkeypatch, workers=False)
    names_parallel, cost_parallel, parallel = search(monkeypatch, workers=True)
    assert (names_parallel, cost_parallel) == (names, cost)
    for field in ("improvements", "improvement_evaluations", "evaluations_executed", "anchors_considered",
                  "exchange_restarts", "evaluation_rejected", "constraints_rejected"):
        assert parallel[field] == alone[field], field
    assert parallel["parallel_pricing"]["workers"] >= 1
    assert parallel["parallel_pricing"]["used"] > 0


def test_a_worker_that_cannot_answer_leaves_the_menu_to_the_search():
    pool = pp.SpeculativeWorkers(lambda payload: 1 // payload, 2, (ValueError,))
    try:
        assert pool.submit("a", 0) and pool.submit("b", 2)
        assert pool.take("a", timeout=10) is None  # ZeroDivisionError: not the caller's error
        assert pool.take("b", timeout=10) == ("ok", 0)
        assert pool.take("never", timeout=0.1) is None
    finally:
        pool.close()
