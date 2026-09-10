from dataclasses import replace

import pytest
from app.models import PlanRequest
from app.models.diversity import DiversityMode
from app.models.recipe import Recipe, RecipeIngredient
from app.services.culinary_similarity import CulinarySimilarity
from app.services.ingredient_taxonomy import INGREDIENT_TAXONOMY
from app.services.meal_plan_optimizer import MealPlanService
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
from app.services.recipe_candidate_validator import recipe_id
from app.services.recipe_profile import RecipeProfileBuilder

from deploy.scripts.start_cron import scheduled_jobs


def meal(protein="korv", veg="morot", steps=None, name="Middag", carb="nudlar"):
    return Recipe(name=name, servings=4, ingredients=[
        RecipeIngredient(name=protein, canonical_name=protein, quantity=500, unit="g"),
        RecipeIngredient(name=carb, canonical_name=carb, quantity=400, unit="g"),
        RecipeIngredient(name=veg, canonical_name=veg, quantity=500, unit="g"),
    ], instructions=steps or ["Koka nudlar. Stek protein och grönsaker och vänd ihop."])


def test_renaming_does_not_create_structure_or_fake_oven():
    builder = RecipeProfileBuilder()
    a = meal()
    b = a.model_copy(update={"name": "Ugnsbakad exotisk bowl"})
    assert replace(builder.build(a), recipe_name="") == replace(builder.build(b), recipe_name="")
    assert builder.build(b).cooking_method == "pan_cook"


@pytest.mark.parametrize("other", [meal(veg="rödlök"), meal(protein="tofu"), meal(name="Bowl")])
def test_small_swaps_cannot_pass_near_duplicate_guard(other):
    assert CulinarySimilarity().compare_recipes(meal(), other).score >= .85


def test_potatoes_and_onions_may_repeat_in_actually_different_dishes():
    stew = meal(carb="potatis", veg="gul lök", steps=["Låt sjuda till en tjock gryta."])
    roast = meal(carb="potatis", veg="gul lök", steps=["Rosta på plåt i ugn vid 225 grader."])
    assert CulinarySimilarity().compare_recipes(stew, roast).score < .85
    assert recipe_id(stew) != recipe_id(roast)


def test_generated_techniques_have_executable_evidence_and_explicit_pantry():
    recipes = DeterministicRecipeCandidateGenerator().generate_candidates(INGREDIENT_TAXONOMY,120,4)
    profiles = [RecipeProfileBuilder().build(r) for r in recipes]
    assert len({p.recipe_family for p in profiles}) >= 5
    for recipe, profile in zip(recipes, profiles, strict=True):
        steps = " ".join(recipe.instructions).lower()
        assert "basvaror: vatten, salt, peppar" in steps
        assert "alla ingredienser" in steps
        if profile.cooking_method == "oven":
            assert "ugnen" in steps and "minuter" in steps
        if profile.recipe_family == "wrap":
            assert "vik ihop tortillas" in steps
            assert any(i.canonical_name == "tortillas" for i in recipe.ingredients)
        if profile.recipe_family == "soppa":
            assert "häll på vatten" in steps and "soppa" in steps


@pytest.mark.parametrize("count,families,methods", [(3,3,2),(5,4,3),(7,5,3)])
def test_targets_scale_and_cache_separates_budget(count, families, methods):
    request = PlanRequest(recipes=count, diversity_mode="varied")
    policy = MealPlanService._diversity_policy_for(request, DiversityMode.VARIED)
    assert policy.min_recipe_families == families
    assert policy.min_cooking_methods == methods
    policies = {m: MealPlanService._diversity_policy_for(request,m) for m in DiversityMode}
    a = MealPlanService._menu_search_cache_payload(request,policies,120,pricing_context_id="member-a")
    b = MealPlanService._menu_search_cache_payload(request.model_copy(update={"varied_budget_percent":0}),policies,120,pricing_context_id="member-a")
    c = MealPlanService._menu_search_cache_payload(request,policies,120,pricing_context_id="member-b")
    assert a != b and a != c


def test_backups_independent_of_disabled_price_jobs(monkeypatch):
    monkeypatch.setenv("DAILY_REFRESH_ENABLED","false")
    monkeypatch.setenv("COOP_RETRY_ENABLED","false")
    assert scheduled_jobs() == (("DAILY_BACKUP_CRON","backup_sqlite.py"),)


def test_same_stew_with_a_different_side_is_still_near_duplicate():
    a = meal(protein="linser", carb="ris", steps=["Låt linser sjuda till en gryta."])
    b = meal(protein="linser", carb="potatis", steps=["Låt linser sjuda till en gryta."])
    assert CulinarySimilarity().compare_recipes(a,b).score >= .85


def test_sausage_noodle_bowl_does_not_escape_guard_with_cream_and_carrot():
    noodles = meal(veg="rödlök")
    bowl = meal(steps=["Stek protein och grönsaker. Håll komponenterna åtskilda i skålen."])
    bowl = bowl.model_copy(update={"ingredients": [*bowl.ingredients,
        RecipeIngredient(name="crème fraiche",canonical_name="crème fraiche",quantity=250,unit="ml")]})
    assert CulinarySimilarity().compare_recipes(noodles,bowl).score >= .85


def test_missing_historical_policy_version_does_not_claim_new_assessment():
    from app.models.plan import DiversityPlanOption
    assert DiversityPlanOption.model_fields["variation_policy_version"].default == "legacy"
