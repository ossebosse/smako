"""Pure recipe reuse must not cache product or source qualification decisions."""

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


def test_all_104_authored_recipes_reuse_validation_with_identical_input_evidence():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    assert len(recipes) == 104
    cache = RecipeComputationCache()
    cases = []
    for recipe in recipes:
        # Different ingredients/products/units still go through normal evidence
        # checks. Synthetic declarations here prove equivalence, not coverage.
        for ingredient in (recipe.ingredients[0], next(i for i in recipe.ingredients if i.unit == "ml")):
            item = product(ingredient.name, 500, ingredient.unit, 20)
            evidence = fact(ingredient.unit)
            args = (recipe, item, ingredient.name, ingredient.unit, True, evidence)
            cases.append((args, recipe_preparation.input_evidence(*args)))
    with patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify:
        for args, expected in cases:
            assert recipe_preparation.input_evidence(*args, recipe_cache=cache) == expected
        assert verify.call_count == 104


def test_all_104_candidates_fit_with_all_four_actual_pure_computations():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    cache, optimizer = RecipeComputationCache(), MenuOptimizer()
    computations = (recipe_id, protein_category, optimizer._profile, recipe_preparation.validate)
    for recipe in recipes:
        for compute in computations:
            cache.get(recipe, compute)
    assert len(cache.values) == 416 < cache.limit == 512
    # A full second pass over separately loaded values fits without eviction.
    for recipe in candidates(RecipePreferences(mode="complete"), 2):
        for compute in computations:
            cache.get(recipe, compute)
    assert len(cache.values) == 416


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
        assert verify.call_count == 2  # One normal cached validation + explicit uncached comparison.


def test_non_prepared_recipe_false_is_reused_without_promoting_it():
    cache = RecipeComputationCache()
    recipe = original()
    item = product("Tofu", 300, "g", 20)
    with patch.object(recipe_preparation, "validate", wraps=recipe_preparation.validate) as verify:
        for _ in range(2):
            assert recipe_preparation.input_evidence(recipe, item, "tofu", "g", True,
                                                     fact(), recipe_cache=cache) is None
        assert verify.call_count == 1
