"""Diagnostic reuse must preserve exact IDs across copies and mutable inputs."""
from types import SimpleNamespace

import pytest
from app.services import product_planning_trace as trace_module
from app.services.recipe_computation_cache import RecipeComputationCache
from app.services.recipe_library import current_recipes


def trace():
    prepared = SimpleNamespace(economic_pool=SimpleNamespace(candidates_by_name={}, matched_candidates_by_name={}),
                               universe=SimpleNamespace(products=[]))
    return trace_module.ProductPlanningTrace(prepared, recipe_cache=RecipeComputationCache())


def test_copies_reuse_identical_full_trace_hash_and_return_isolated_values(monkeypatch):
    subject = trace()
    recipe = current_recipes()[0]
    original = trace_module.recipe_identity
    calls = []

    def measured(r):
        calls.append(r)
        return original(r)

    monkeypatch.setattr(trace_module, "recipe_identity", measured)
    first = subject.identity(recipe)
    assert first == subject.identity(recipe.model_copy(deep=True)) == original(recipe)
    assert len(calls) == 1
    first["id"] = "edited response"
    assert subject.identity(recipe) == original(recipe)


@pytest.mark.parametrize("change", ["instructions", "ingredients", "forms"])
def test_trace_id_tracks_changed_nested_recipe_values(change):
    subject = trace()
    recipe = current_recipes()[0].model_copy(deep=True)
    before = subject.identity(recipe)
    if change == "instructions":
        recipe.instructions.append("Ny uttrycklig beredningsinstruktion.")
    elif change == "ingredients":
        recipe.ingredients[0] = recipe.ingredients[0].model_copy(update={"quantity": recipe.ingredients[0].quantity + 1})
    else:
        recipe.preparation.input_forms[recipe.ingredients[0].canonical_name] = "as_sold"
    assert subject.identity(recipe) == trace_module.recipe_identity(recipe)
    assert subject.identity(recipe) != before
