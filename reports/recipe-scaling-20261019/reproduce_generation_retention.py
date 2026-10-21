"""Small deterministic regression for completed-generation retention.

Synthetic prices isolate the search; they are not retailer or timing evidence.
Run with PYTHONPATH=backend;. on Windows, backend:. on Linux.
"""
import json

from app.models.personal import MealSlot
from app.models.recipe import Recipe, RecipeIngredient
from app.services.menu_optimizer import MenuOptimizer


def options(names):
    recipes = [Recipe(name=name, servings=1,
                      ingredients=[RecipeIngredient(name=name, quantity=1, unit="g")],
                      instructions=["Synthetic search reproduction"]) for name in names]
    return [[MealSlot(id=f"dinner-{day}", day=day, meal_type="dinner", recipe=recipe)
             for recipe in recipes] for day in (1, 2)]


def evaluate(slots, *, final):
    names = tuple(slot.recipe.name for slot in slots)
    return {
        ("A",): 1, ("B",): 3, ("C",): 2,
        ("A", "A"): 10, ("A", "B"): 15, ("B", "A"): 15, ("B", "B"): 2,
        ("C", "A"): 8, ("A", "C"): 8, ("C", "C"): 6,
        ("B", "C"): 12, ("C", "B"): 12,
    }[names]


def plan(cohorts):
    # Model a bounded refinement pool whose ranking changes with library growth.
    def refinement(groups):
        return [[slot for slot in group if len(group) <= 2 or slot.recipe.name != "B"]
                for group in groups]

    trace = []
    slots, paid = MenuOptimizer().optimize_library_slots(
        cohorts, evaluate=evaluate, accepts=lambda slots, final: True,
        score=lambda slots, price: price, retention_score=lambda slots, price: price,
        refinement_selector=refinement, search_trace=trace)
    return slots, paid, trace


def main():
    old_slots, old_paid, old_trace = plan([(1, options("A")), (2, options("AB"))])
    new_slots, new_paid, new_trace = plan([
        (1, options("A")), (2, options("AB")), (3, options("ABC"))])
    rechecked = evaluate(old_slots, final=True)
    assert old_paid == rechecked == 2
    assert new_paid == old_paid == 2
    print(json.dumps({
        "synthetic": True, "prior_paid": old_paid, "expanded_paid": new_paid,
        "prior_repriced_in_expanded_scope": rechecked,
        "prior_menu": [slot.recipe.name for slot in old_slots],
        "expanded_menu": [slot.recipe.name for slot in new_slots],
        "prior_final_phases": sorted({row["library_generation"] for row in old_trace
                                     if row["library_phase"] == "refinement"}),
        "expanded_final_phases": sorted({row["library_generation"] for row in new_trace
                                        if row["library_phase"] == "refinement"}),
    }, indent=2))


if __name__ == "__main__":
    main()
