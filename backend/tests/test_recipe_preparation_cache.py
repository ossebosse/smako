"""Reuse exact recipe work and request-local input evidence without sharing approval."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from app.config import Settings
from app.models.recipe_preferences import RecipePreferences
from app.services import recipe_preparation
from app.services.menu_optimizer import MenuOptimizer
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import protein_category
from app.services.recipe_candidate_validator import recipe_id
from app.services.recipe_computation_cache import RecipeComputationCache
from app.services.recipe_library import candidates

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, state
from backend.tests.test_personal_qualified_facts import facts
from backend.tests.test_recipe_preparation import fact, original


def test_all_authored_recipes_reuse_validation_with_identical_input_evidence():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    assert len(recipes) >= 152
    cache = RecipeComputationCache()
    cases = []
    for recipe in recipes:
        # Different ingredients/products/units still go through normal evidence
        # checks. Synthetic declarations here prove equivalence, not coverage.
        # The expanded library includes complete dishes without volume inputs.
        # Exercise every unit actually present, including their real rejections.
        by_unit = {i.unit: i for i in recipe.ingredients}
        for ingredient in (recipe.ingredients[0], *by_unit.values()):
            item = product(ingredient.name, 500, ingredient.unit, 20)
            evidence = fact(ingredient.unit)
            args = (recipe, item, ingredient.name, ingredient.unit, True, evidence)
            cases.append((args, recipe_preparation.input_evidence(*args)))
    with patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify:
        for args, expected in cases:
            assert recipe_preparation.input_evidence(*args, recipe_cache=cache) == expected
        assert verify.call_count == len(recipes)


def test_all_candidates_fit_with_all_four_actual_pure_computations():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    cache, optimizer = RecipeComputationCache(), MenuOptimizer()
    computations = (recipe_id, protein_category, optimizer._profile, recipe_preparation.validate)
    for recipe in recipes:
        for compute in computations:
            cache.get(recipe, compute)
    assert len(cache.values) == len(recipes) * len(computations) < cache.limit == 16384
    # A full second pass over separately loaded values fits without eviction.
    for recipe in candidates(RecipePreferences(mode="complete"), 2):
        for compute in computations:
            cache.get(recipe, compute)
    assert len(cache.values) == len(recipes) * len(computations)


@pytest.mark.parametrize("change", ["quantity", "instructions", "form", "form_order", "design", "version", "provenance"])
def test_changed_recipe_cannot_borrow_cached_validation_even_with_same_content_hash(change):
    recipe = candidates(RecipePreferences(mode="complete"), 2)[0]
    cache = RecipeComputationCache()
    item = product("Rapsolja", 500, "ml", 20)

    def evidence():
        return recipe_preparation.input_evidence(recipe, item, "rapsolja", "ml", True,
                                                  fact("ml"), recipe_cache=cache)

    with patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify:
        evidence()
        evidence()
        assert verify.call_count == 1
        original_hash = recipe.design.content_sha256
        if change == "quantity":
            ingredient = recipe.ingredients[0]
            recipe.ingredients[0] = ingredient.model_copy(update={"quantity": ingredient.quantity + 1e-10})
        elif change == "instructions":
            recipe.instructions[0] += " Ändrat utan ny granskning."
        elif change == "form":
            recipe.preparation.input_forms[next(iter(recipe.preparation.input_forms))] = "unknown"
        elif change == "form_order":
            forms = recipe.preparation.input_forms
            ordered = tuple(reversed(tuple(forms.items())))
            forms.clear()
            forms.update(ordered)
        elif change == "design":
            recipe = recipe.model_copy(update={"design": recipe.design.model_copy(update={"equipment": ("annat",)})})
        elif change == "version":
            recipe = recipe.model_copy(update={"design": recipe.design.model_copy(update={"version": "99.0.0"})})
        else:
            provenance = recipe.design.provenance.model_copy(update={"notes": "Ändrad proveniens"})
            recipe = recipe.model_copy(update={"design": recipe.design.model_copy(update={"provenance": provenance})})
        assert recipe.design.content_sha256 == original_hash
        if change == "form_order":
            # Reordering a mapping is still a valid method. It must nevertheless
            # cause a new exact-key computation (legacy recipe IDs retain order).
            evidence()
            assert verify.call_count == 2
        else:
            for _ in range(2):
                with pytest.raises(ValueError):
                    evidence()
            assert verify.call_count == 3  # Failed validations are never stored.


def test_planner_recipe_cache_preserves_each_product_source_unit_form_and_opt_in_check():
    recipe = recipe_preparation.adapt(original(), "panna")
    first = product("Tofu naturell Fast", 300, "g", 20, identity="first")
    second = product("Tofu naturell Fast", 500, "g", 25, identity="second")
    universe = prepared(first, second)
    evidence = {
        (p.store_id, p.product_id): facts(p, nutrition={"protein_g": amount},
            nutrition_unit="g", nutrition_basis="per 100 g")
        for p, amount in ((first, 15), (second, 21))
    }
    planner = PersonalPlanner(request(allow_nutrition_estimates=True), Settings(),
        universe, state(), facts=evidence, now=NOW)

    def value(item=first, unit="g", fields=frozenset({"protein_g"}), name="tofu"):
        # Force existing evidence-cache misses/evictions without changing the
        # request, so only the new pure-validation reuse is under test.
        planner.nutrition_cache.clear()
        return planner.nutrition_evidence(item, name, unit, fields, recipe)

    with patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify:
        assert value().nutrition["protein_g"] == 15
        assert value(second).nutrition["protein_g"] == 21
        assert value(unit="ml") is None  # No inferred density.
        assert value(name="not a recipe input") is None
        assert value(fields=frozenset({"salt_g"})) is None
        original_fact = planner.facts[(first.store_id, first.product_id)]
        planner.facts[(first.store_id, first.product_id)] = replace(original_fact, conflicts=("nutrition",))
        assert value() is None
        planner.facts[(first.store_id, first.product_id)] = replace(original_fact, nutrition={"protein_g": 17})
        assert value().nutrition["protein_g"] == 17
        # A mismatching snapshot must have exactly the ordinary uncached result;
        # it cannot inherit the qualified product's previous nutrients/source.
        planner.facts[(first.store_id, first.product_id)] = replace(original_fact, source_snapshot_id="other")
        cached = value()
        with patch.object(RecipeComputationCache, "get", lambda self, r, compute: compute(r)):
            uncached = value()
        assert cached == uncached
        assert cached is None or cached.source != original_fact.source
        planner.spec.allow_nutrition_estimates = False
        assert value(second) is None
        # One ordinary validation; bypassing the pure cache validates both
        # the shared identity and the uncached evidence path independently.
        assert verify.call_count == 3


def test_non_prepared_recipe_false_is_reused_without_promoting_it():
    cache = RecipeComputationCache()
    recipe = original()
    item = product("Tofu", 300, "g", 20)
    with patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify:
        for _ in range(2):
            assert recipe_preparation.input_evidence(recipe, item, "tofu", "g", True,
                                                     fact(), recipe_cache=cache) is None
        assert verify.call_count == 1


def test_distinct_recipes_share_input_work_but_keep_exact_validation_and_provenance():
    all_recipes = candidates(RecipePreferences(mode="complete"), 2)
    recipes = [r for r in all_recipes if "rapsolja" in r.preparation.input_forms]
    item = product("Rapsolja", 500, "ml", 20)
    evidence = {(item.store_id, item.product_id): facts(item,
        nutrition={"protein_g": 0, "fat_g": 92, "carbs_g": 0, "kcal": 828},
        nutrition_unit="ml", nutrition_basis="per 100 ml",
        field_sources={"nutrition.protein_g": ({"source": "test declaration"},)})}
    planner = PersonalPlanner(request(allow_nutrition_estimates=True), Settings(),
        prepared(item), state(), facts=evidence, now=NOW)
    fields = frozenset({"protein_g", "fat_g", "carbs_g", "kcal"})
    # Synthetic oil evidence cannot introduce oil into a recipe without it.
    absent = [r for r in all_recipes if "rapsolja" not in r.preparation.input_forms]
    assert absent
    assert all(planner.nutrition_evidence(item, "rapsolja", "ml", fields, r) is None for r in absent)
    expected = [planner._nutrition_evidence(item, "rapsolja", "ml", fields, r) for r in recipes]
    # Reviewed losses have unknown served nutrition even with declared oil.
    # They still participate in the cache-equivalence check below.
    assert any(expected)
    assert all((value is None) == bool(r.design.unmeasured_processes)
               for r, value in zip(recipes, expected, strict=True))
    planner.recipe_computations = RecipeComputationCache()
    with (
        patch.object(planner, "_nutrition_evidence", wraps=planner._nutrition_evidence) as compute,
        patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify,
    ):
        actual = [planner.nutrition_evidence(item, "rapsolja", "ml", fields, r) for r in recipes]
        assert actual == expected  # Includes family, method and original source provenance.
        assert verify.call_count == len(recipes)  # Never borrow another recipe's approval.
        distinct = {(r.preparation.version, r.preparation.family,
                     r.preparation.input_forms["rapsolja"]) for r in recipes
                    if not r.design.unmeasured_processes}
        assert compute.call_count == len(distinct) < len(recipes)
        # A cache hit must not conceal even a tiny amount change or broken seal.
        recipe = recipes[0].model_copy(deep=True)
        ingredient = recipe.ingredients[0]
        recipe.ingredients[0] = ingredient.model_copy(update={"quantity": ingredient.quantity + 1e-10})
        with pytest.raises(ValueError):
            planner.nutrition_evidence(item, "rapsolja", "ml", fields, recipe)
        assert compute.call_count == len(distinct)


def test_input_sharing_preserves_different_preparation_families():
    first = recipe_preparation.adapt(original(), "panna")
    second = recipe_preparation.adapt(original().model_copy(update={"name": "En annan rätt"}), "gryta")
    item = product("Tofu naturell Fast", 300, "g", 20)
    evidence = {(item.store_id, item.product_id): facts(item, nutrition={"protein_g": 15},
        nutrition_unit="g", nutrition_basis="per 100 g",
        field_sources={"nutrition.protein_g": ({"source": "test declaration"},)})}
    planner = PersonalPlanner(request(allow_nutrition_estimates=True), Settings(),
        prepared(item), state(), facts=evidence, now=NOW)
    for recipe in (first, second):
        actual = planner.nutrition_evidence(item, "tofu", "g", {"protein_g"}, recipe)
        assert actual == planner._nutrition_evidence(item, "tofu", "g", {"protein_g"}, recipe)
        assert actual.field_sources["nutrition.protein_g"][-1]["family"] == recipe.preparation.family
    assert len(planner.nutrition_cache) == 2
