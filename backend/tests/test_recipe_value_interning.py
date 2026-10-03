"""Exact, bounded pure keys/signatures; no source or product decision is cached."""

from unittest.mock import patch

import pytest
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.models.recipe import RecipeDesign, RecipeIngredient
from app.models.recipe_preferences import RecipePreferences
from app.services.ingredient_normalizer import canonicalize_ingredient_name
from app.services.recipe_computation_cache import (
    ExactRecipeKey,
    RecipeComputationCache,
    recipe_value,
)
from app.services.recipe_library import candidates

from backend.tests.test_combined_profile import products
from backend.tests.test_personal_planning_v2 import run, state


def authored():
    return candidates(RecipePreferences(mode="complete"), 2)[0]


def old_forms(recipe, canonical):
    return tuple((i.form, tuple(i.product_requirements or ())) for i in recipe.ingredients
                 if canonicalize_ingredient_name(i.name) == canonical)


def test_same_object_is_snapshotted_but_recursive_hash_is_not_repeated():
    cache, recipe = RecipeComputationCache(), authored()
    with patch("app.services.recipe_computation_cache.hash", wraps=hash, create=True) as recursive_hash:
        key = cache.key(recipe)
        for _ in range(100):
            assert cache.key(recipe) is key
            assert hash(cache.key(recipe)) == hash(key)
        assert recursive_hash.call_count == 1
        assert cache.key(recipe.model_copy(deep=True)) is key  # Exact value interning.
        assert recursive_hash.call_count == 2
        recipe.instructions.append("Ändrat steg")
        assert cache.key(recipe) != key
        assert recursive_hash.call_count == 3
        assert len(key.value[3]) + 1 == len(recipe.instructions)


@pytest.mark.parametrize("field", tuple(RecipeIngredient.model_fields))
def test_every_ingredient_field_changes_exact_key_without_rounding(field):
    recipe, cache = authored(), RecipeComputationCache()
    original = cache.key(recipe)
    ingredient = recipe.ingredients[0]
    updates = {"name": ingredient.name + " ändrad", "quantity": ingredient.quantity + 1e-10,
        "unit": "kg", "canonical_name": "ändrad", "form": "as_sold", "component": "annan",
        "required": not ingredient.required, "role": "cooking", "quantity_min": .125,
        "quantity_max": 99999, "quantity_step": .125, "product_requirements": ("annan",)}
    assert set(updates) == set(RecipeIngredient.model_fields)
    assert updates[field] != getattr(ingredient, field)
    recipe.ingredients[0] = ingredient.model_copy(update={field: updates[field]})
    assert cache.key(recipe) != original
    assert cache.key(recipe).value == recipe_value(recipe)


@pytest.mark.parametrize("field", tuple(RecipeDesign.model_fields))
def test_every_frozen_design_field_changes_key_even_with_reused_content_sha(field):
    recipe, cache = authored(), RecipeComputationCache()
    original = cache.key(recipe)
    design = recipe.design
    updates = {"base_id": design.base_id + "-changed", "version": "99.0.0", "variant_id": "changed",
        "cuisines": ("thai",), "family": "changed", "primary_ingredient": "changed", "method": "changed",
        "side": "changed", "flavor_profile": (*design.flavor_profile, "changed"),
        "components": (design.components[0].model_copy(update={"name": "changed"}), *design.components[1:]),
        "steps": (design.steps[0].model_copy(update={"duration_minutes": 179}), *design.steps[1:]),
        "estimated_minutes": 179, "equipment": (*design.equipment, "changed"),
        "vegetarian": not design.vegetarian, "fish": not design.fish,
        "ingredient_count": 39, "provenance": design.provenance.model_copy(update={"notes": "changed"}),
        "content_sha256": "0" * 64}
    assert set(updates) == set(RecipeDesign.model_fields)
    assert updates[field] != getattr(design, field)
    changed = recipe.model_copy(update={"design": design.model_copy(update={field: updates[field]})})
    if field != "content_sha256":
        assert changed.design.content_sha256 == recipe.design.content_sha256
    assert cache.key(changed) != original
    assert cache.key(changed).value == recipe_value(changed)


def test_recipe_keys_compare_exact_values_even_with_hash_collision():
    first, second = ExactRecipeKey(("first",)), ExactRecipeKey(("second",))
    # Deliberately force a collision in the test; hashes are an index, not proof.
    object.__setattr__(second, "_hash", hash(first))
    assert hash(first) == hash(second) and first != second
    assert len({first: 1, second: 2}) == 2


def test_forms_equal_original_comprehension_for_all_104_recipes_and_missing_names():
    cache = RecipeComputationCache()
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    for recipe in recipes:
        for name in [i.name for i in recipe.ingredients] + ["unknown"]:
            canonical = canonicalize_ingredient_name(name)
            assert cache.forms_for(recipe, canonical) == old_forms(recipe, canonical)
    assert len(cache._forms) == 104
    assert not cache.values  # Does not consume the four computations' 416 slots.


def test_forms_keep_alias_order_and_recheck_changed_mutable_recipe_inputs():
    recipe, cache = authored(), RecipeComputationCache()
    recipe.ingredients[:] = [
        RecipeIngredient(name="vitlök", quantity=10, unit="g", form="raw_edible", product_requirements=("fresh",)),
        RecipeIngredient(name="vitlöksklyfta", canonical_name="misleading", quantity=3, unit="g", form="dry"),
    ]
    assert cache.forms_for(recipe, "vitlök") == old_forms(recipe, "vitlök")
    recipe.ingredients.reverse()
    assert cache.forms_for(recipe, "vitlök") == old_forms(recipe, "vitlök")
    old = cache.forms_for(recipe, "vitlök")
    ingredient = recipe.ingredients[0]
    recipe.ingredients[0] = ingredient.model_copy(update={"product_requirements": ("changed",)})
    assert cache.forms_for(recipe, "vitlök") != old
    assert cache.forms_for(recipe, "vitlök") == old_forms(recipe, "vitlök")


def test_all_new_pure_cache_structures_are_bounded_and_request_local():
    first, second = RecipeComputationCache(limit=2), RecipeComputationCache(limit=2)
    recipe = authored()
    for index in range(8):
        changed = recipe.model_copy(update={"name": str(index)})
        first.forms_for(changed, "vitlök")
        first.get(changed, lambda r: r.name)
        assert len(first._identities) <= 2
        assert len(first._interned) <= 2
        assert len(first._forms) <= 2
        assert len(first.values) <= 2
    assert not second._identities and not second._forms and not second.values
    assert first.key(None).value is None


@pytest.mark.parametrize("servings", [1, 2])
def test_complete_synthetic_plan_and_audit_equal_before_interning(servings):
    universe, facts = products()
    request = PlanRequest(recipes=0, max_stores=2, personal=PersonalPlanning(meals=[
        MealSettings(meal_type="breakfast", count=3, servings=servings,
            limits=PortionLimits(min_protein_g=30)),
        MealSettings(meal_type="snack", count=2, servings=1,
            limits=PortionLimits(min_protein_g=20)),
    ]))
    cached = run(universe, request, state(), facts=facts)
    with patch.object(RecipeComputationCache, "key", lambda self, recipe: recipe_value(recipe)), \
         patch.object(RecipeComputationCache, "forms_for", lambda self, recipe, name: old_forms(recipe, name)):
        plain = run(universe, request, state(), facts=facts)
    for field in ("optimized_basket", "ingredients", "recipes", "personal"):
        assert getattr(cached, field) == getattr(plain, field)
