"""Exact pure-computation reuse; synthetic pricing is not market acceptance."""

from dataclasses import replace
from unittest.mock import patch

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, MealSlot, PersonalPlanning, PortionLimits
from app.models.recipe import Recipe, RecipePreparation
from app.models.recipe_preferences import RecipePreferences
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.menu_optimizer import DiversityConstraints, MenuOptimizer
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, protein_category
from app.services.recipe_candidate_validator import recipe_id
from app.services.recipe_computation_cache import RecipeComputationCache, recipe_value
from app.services.recipe_library import candidates

from backend.tests.test_combined_profile import products
from backend.tests.test_personal_planning_v2 import NOW, prepared, run, state


def authored():
    return candidates(RecipePreferences(mode="complete"), 2)[0]


def test_value_key_covers_the_whole_current_recipe_contract():
    # A future field must be deliberately included, never silently omitted.
    assert set(Recipe.model_fields) == {
        "name", "servings", "ingredients", "instructions", "preparation", "design"}
    assert set(RecipePreparation.model_fields) == {
        "version", "origin", "parent_sha256", "family", "input_forms"}
    recipe = authored()
    assert recipe_value(recipe) == recipe_value(recipe.model_copy(deep=True))
    assert hash(recipe_value(recipe)) == hash(recipe_value(recipe.model_copy(deep=True)))


@pytest.mark.parametrize("change", ["quantity", "instructions", "form", "form_order", "design", "servings", "name"])
def test_changed_nested_recipe_values_cannot_reuse_old_computation(change):
    recipe = authored()
    cache = RecipeComputationCache()
    calls = []

    def compute(value):
        calls.append(value.model_dump_json())
        return recipe_id(value)

    old = cache.get(recipe, compute)
    assert cache.get(recipe.model_copy(deep=True), compute) == old
    assert len(calls) == 1
    if change == "quantity":
        first = recipe.ingredients[0]
        recipe.ingredients[0] = first.model_copy(update={"quantity": first.quantity + 1e-10})
    elif change == "instructions":
        recipe.instructions.append("En uttryckligt ändrad instruktion.")
    elif change == "form":
        recipe.preparation.input_forms[next(iter(recipe.preparation.input_forms))] = "as_sold"
    elif change == "form_order":
        forms = recipe.preparation.input_forms
        ordered = tuple(reversed(tuple(forms.items())))
        forms.clear()
        forms.update(ordered)
    elif change == "design":
        recipe = recipe.model_copy(update={"design": recipe.design.model_copy(update={"equipment": ("annat",)})})
    elif change == "servings":
        recipe = recipe.model_copy(update={"servings": 4})
    else:
        recipe = recipe.model_copy(update={"name": recipe.name + " ändrad"})
    assert cache.get(recipe, compute) == recipe_id(recipe)
    assert len(calls) == 2  # Including changes hidden by recipe_id's legacy rounding.


def test_bound_profiles_and_pure_ids_equal_uncached_for_all_issued_candidates():
    recipes = candidates(RecipePreferences(mode="complete"), 2)
    assert len(recipes) >= 152  # every issued dinner; grows with content packs
    cache = RecipeComputationCache()
    optimizer = MenuOptimizer()
    constraints = DiversityConstraints(target_recipe_count=5)
    with patch.object(optimizer, "_profile", wraps=optimizer._profile) as profile:
        for offset in range(len(recipes)):
            chosen = [recipes[(offset + step * 13) % len(recipes)] for step in range(5)]
            plain = optimizer.accepts_recipes(chosen, constraints)
            assert optimizer.accepts_recipes(chosen, constraints, profile_cache=cache) == plain
        assert profile.call_count == 6 * len(recipes)  # 5 uncached profiles + 1 per exact recipe.
    for recipe in recipes:
        assert cache.get(recipe, recipe_id) == recipe_id(recipe)
        assert cache.get(recipe, protein_category) == protein_category(recipe)


def test_profile_cache_keeps_current_constraints_and_rejects_edited_seal():
    recipes = candidates(RecipePreferences(mode="complete", adaptation="products"), 2)[:2]
    optimizer, cache = MenuOptimizer(), RecipeComputationCache()
    constraints = DiversityConstraints(max_same_recipe_family=2,
        recipe_families={r.name: "same" for r in recipes})
    assert optimizer.accepts_recipes(recipes, constraints, profile_cache=cache)
    assert not optimizer.accepts_recipes(recipes, replace(constraints, max_same_recipe_family=1), profile_cache=cache)
    recipes[0].instructions[0] += " Ändrat utan ny innehållsgranskning."
    with pytest.raises(ValueError, match="instruktioner"):
        optimizer.accepts_recipes(recipes, constraints, profile_cache=cache)


def test_custom_normalizer_retains_its_original_call_behavior():
    class StatefulNormalizer(IngredientNormalizer):
        calls = 0

        def normalize_and_aggregate(self, recipes):
            self.calls += 1
            return super().normalize_and_aggregate(recipes)

    normalizer = StatefulNormalizer()
    optimizer = MenuOptimizer(normalizer=normalizer)
    recipe = authored()
    constraints = DiversityConstraints(recipe_families={recipe.name: "family"},
        primary_ingredients={recipe.name: "primary"}, carbohydrates={recipe.name: "carb"})
    cache = RecipeComputationCache()
    optimizer.accepts_recipes([recipe], constraints, profile_cache=cache)
    optimizer.accepts_recipes([recipe], constraints, profile_cache=cache)
    assert normalizer.calls == 2
    assert not cache.values


def test_recipe_reuse_is_bounded_and_separate_between_planners():
    recipe = authored()
    first, second = RecipeComputationCache(limit=2), RecipeComputationCache(limit=2)
    assert first.get(recipe, recipe_id) == second.get(recipe, recipe_id)
    assert first.values is not second.values
    for index in range(5):
        first.get(recipe.model_copy(update={"name": str(index)}), recipe_id)
        assert len(first.values) <= 2
    assert len(second.values) == 1


def test_expanding_library_keeps_hot_prefix_without_raising_cache_bounds():
    recipe = authored()
    cache = RecipeComputationCache(limit=4)
    calls = []

    def compute(value):
        calls.append(value.name)
        return recipe_id(value)

    expected = recipe_id(recipe)
    for index in range(30):
        assert cache.get(recipe, compute) == expected
        candidate = recipe.model_copy(update={"name": f"independent-base-{index}"})
        assert cache.get(candidate, compute) == recipe_id(candidate)
        cache.forms_for(recipe, recipe.ingredients[0].canonical_name)
        cache.forms_for(candidate, recipe.ingredients[0].canonical_name)
        for mapping in (cache.values, cache._identities, cache._interned, cache._forms):
            assert len(mapping) <= 4
    assert calls.count(recipe.name) == 1
    # Reusing the hot prefix still compares its entire mutable current value.
    recipe.instructions.append("Explicit instruction change, new computation required.")
    assert cache.get(recipe, compute) == recipe_id(recipe)
    assert calls.count(recipe.name) == 2


def test_clean_cache_reuses_only_validated_content_and_current_preferences(monkeypatch):
    prefs = RecipePreferences(mode="complete", cuisines=["greek"])
    request = PlanRequest(recipes=1, recipe_preferences=prefs)
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(), state(), facts={}, now=NOW)
    # This is a content-boundary test, not a claim of product qualification.
    monkeypatch.setattr(planner, "resolve", lambda *args, **kwargs: [])
    recipe = candidates(prefs, 2)[0]
    meal = planner.spec.meals[0]
    from app.services.complete_recipes import matches_preferences
    with patch("app.services.complete_recipes.matches_preferences", wraps=matches_preferences) as verify:
        assert planner.clean_recipe(recipe, meal) == planner.clean_recipe(recipe, meal)
        assert verify.call_count == 1
        planner.request.recipe_preferences = prefs.model_copy(update={"cuisines": ("thai",)})
        with pytest.raises(PolicyConflict, match="matkök"):
            planner.clean_recipe(recipe, meal)
        assert verify.call_count == 2
        planner.request.recipe_preferences = prefs
        recipe.preparation.input_forms[recipe.ingredients[0].canonical_name] = "unknown"
        with pytest.raises(ValueError):
            planner.clean_recipe(recipe, meal)


@pytest.mark.parametrize("servings,minimum", [(1, 30), (2, 32)])
def test_real_planner_search_and_audit_equal_uncached_for_private_nutrition_choices(servings, minimum):
    universe, facts = products()
    request = PlanRequest(recipes=0, max_stores=2, personal=PersonalPlanning(meals=[
        MealSettings(meal_type="breakfast", count=3, servings=servings,
            limits=PortionLimits(min_protein_g=minimum)),
        MealSettings(meal_type="snack", count=2, servings=1,
            limits=PortionLimits(min_protein_g=20)),
    ]))
    cached = run(universe, request, state(), facts=facts)
    with patch.object(RecipeComputationCache, "get", lambda self, recipe, compute: compute(recipe)):
        plain = run(universe, request, state(), facts=facts)
    for field in ("optimized_basket", "ingredients", "recipes", "personal"):
        assert getattr(cached, field) == getattr(plain, field)


def test_slot_search_keeps_exact_order_ties_and_trace_with_or_without_id_cache():
    recipes = candidates(RecipePreferences(mode="complete", adaptation="products"), 2)[:6]
    options = [[MealSlot(id=f"d{day}", day=day, meal_type="dinner", recipe=r) for r in recipes]
               for day in range(1, 4)]

    def search():
        trace = []
        result = MenuOptimizer().optimize_slots(options,
            accepts=lambda slots, final: len({s.recipe.name for s in slots}) == len(slots),
            evaluate=lambda slots, final: len(slots) * 10,
            score=lambda slots, total: (total, tuple(s.recipe.name for s in slots)),
            beam_width=3, fallback_beam_width=8, search_trace=trace,
            state_identity=lambda slots: tuple(sorted(recipe_id(s.recipe) for s in slots)))
        return result, trace

    cached = search()
    with patch.object(RecipeComputationCache, "get", lambda self, recipe, compute: compute(recipe)):
        assert search() == cached
