"""Quota pruning must avoid work without hiding a feasible completion."""
from collections import Counter
from itertools import product

import pytest
from app.models.personal import MealSettings, MealSlot, PersonalPlanning
from app.services.personal_policy import (
    distribution_ok,
    protein_category,
    remaining_category_capacity,
)
from app.services.stable_candidate_pool import VariantSearchEvidence, category_seed_cap

from backend.tests.test_personal_planning_v2 import NOW, prepared, recipe, state

KINDS = ("vegetarian", "chicken", "fish", "meat")


@pytest.mark.parametrize("distribution", [{}, {"fish": 0}, {"chicken": 1, "vegetarian": 2},
    {"chicken": 1, "vegetarian": 2, "meat": 2}, {"vegetarian": 5}])
def test_capacity_matches_exhaustive_feasible_completions(distribution):
    meal = MealSettings(meal_type="snack", count=5, distribution=distribution)
    for fixed in ((), ("chicken",), ("vegetarian", "meat"), ("fish", "fish")):
        slots = [MealSlot(id=str(i), day=i+1, meal_type="snack", recipe=recipe(name=k)) for i, k in enumerate(fixed)]
        capacity = remaining_category_capacity(meal, slots, classify=lambda r: r.name)
        possible = set()
        for tail in product(KINDS, repeat=5-len(fixed)):
            counts = Counter((*fixed, *tail))
            if all(counts[k] == n for k, n in distribution.items()):
                possible.update(tail)
        assert {k for k, n in capacity.items() if n > 0} == possible


def test_rejected_category_never_reaches_product_resolution(monkeypatch):
    from app.config import Settings
    from app.models import PlanRequest
    from app.models.recipe import RecipeIngredient
    from app.services.personal_planner import PersonalPlanner
    from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator

    options = [recipe(name=k, ingredients=[RecipeIngredient(name=food, quantity=100, unit="g")])
               for k, food in zip(KINDS, ("bröd", "kyckling", "lax", "nötfärs"), strict=True)]
    monkeypatch.setattr(DeterministicRecipeCandidateGenerator, "generate_for_meal_type", lambda *a, **kw: options)
    meal = MealSettings(meal_type="snack", count=5, distribution={"chicken": 1, "vegetarian": 2, "meat": 2})
    planner = PersonalPlanner(PlanRequest(recipes=0, diversity_mode="cheapest", personal=PersonalPlanning(meals=[meal])), Settings(price_provider="mock"), prepared(), state(), now=NOW)
    resolved = []
    monkeypatch.setattr(planner, "clean_recipe", lambda r, m: resolved.append(r.name) or r)
    assert [r.name for r in planner._candidates(meal)] == ["vegetarian", "chicken", "meat"]
    assert resolved == ["vegetarian", "chicken", "meat"]
    # Swap after the other four dishes have exhausted both veg and meat quotas.
    fixed = [MealSlot(id=str(i), day=i+1, meal_type="snack", recipe=options[k]) for i, k in enumerate((0, 0, 3, 3))]
    resolved.clear()
    assert [r.name for r in planner._candidates(meal, fixed_slots=fixed)] == ["chicken"]
    assert resolved == ["chicken"]


def test_category_selection_reserves_distinct_bases_and_keeps_unknown_evidence():
    from app.services.recipe_candidate_validator import recipe_id
    from app.services.recipe_library import current_recipes

    recipes = list(current_recipes())
    # Cost alone favours plants; requested animal categories must survive.
    evidence = {recipe_id(r): VariantSearchEvidence(
        1 if protein_category(r) == "vegetarian" else 100, (), frozenset()) for r in recipes}
    capacity = {"vegetarian": 2, "chicken": 1, "meat": 2, "fish": 0}
    unknown = next(r for r in recipes if protein_category(r) == "chicken")
    del evidence[recipe_id(unknown)]
    kept = category_seed_cap(recipes, evidence, capacity=capacity, classify=protein_category, limit=24)
    assert unknown in kept
    assert kept == category_seed_cap(recipes, evidence, capacity=capacity, classify=protein_category, limit=24)
    assert len(kept) < len(recipes)
    assert not any(protein_category(r) == "fish" for r in kept)
    for kind, number in capacity.items():
        assert len({r.design.base_id for r in kept if protein_category(r) == kind}) >= number
    assert kept == [r for r in recipes if r in kept]


def test_final_distribution_validation_still_rejects_wrong_quota():
    meal = MealSettings(count=2, distribution={"chicken": 1, "vegetarian": 1})
    slots = [MealSlot(id=str(i), day=i+1, meal_type="dinner", recipe=recipe(name="chicken")) for i in range(2)]
    assert not distribution_ok(slots, [meal], classify=lambda r: r.name)
