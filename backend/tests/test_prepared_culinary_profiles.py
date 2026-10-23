"""A prepared menu must preserve full-pool resolution of duplicate display names."""
from app.config import Settings
from app.models import PlanRequest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.meal_plan_optimizer import MealPlanService


def recipe(name, rice):
    return Recipe(name=name, servings=2, instructions=["Koka och servera."], ingredients=[
        RecipeIngredient(name="ris", quantity=rice, unit="g"),
        RecipeIngredient(name="broccoli", quantity=100, unit="g")])


def test_prepared_profiles_retain_the_full_pool_variant_and_pair_order():
    service = MealPlanService(Settings())
    first, other, variant = recipe("A", 100), recipe("B", 200), recipe("A", 1000)
    request = PlanRequest(recipes=2)
    policy = service._diversity_policy_for(request, request.diversity_mode)
    full = service._culinary_constraints([first, other, variant], policy)
    profiles = service._culinary_profiles([first, other, variant])
    subset = service._culinary_constraints([first, other], policy, profiles=profiles)
    naive = service._culinary_constraints([first, other], policy)
    assert subset.pairwise_recipe_similarities["a", "b"] == full.pairwise_recipe_similarities["a", "b"]
    assert naive.pairwise_recipe_similarities["a", "b"] != full.pairwise_recipe_similarities["a", "b"]
    assert [name for name, row in full.pairwise_recipe_similarities.profile_rows({"b", "a"})] == ["a", "b"]
