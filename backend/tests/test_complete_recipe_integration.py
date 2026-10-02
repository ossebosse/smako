"""Integration contracts with synthetic products; not authentic-market acceptance."""
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, PersonalPlanning, PortionLimits
from app.models.recipe_preferences import RecipePreferences
from app.services.complete_recipes import prepare_request, product_form_compatible
from app.services.personal_policy import PolicyConflict
from pydantic import ValidationError


def test_old_request_has_no_new_serialized_defaults():
    old = PlanRequest()
    dumped = old.model_dump(mode="json")
    assert "recipe_preferences" not in dumped
    assert "allow_nutrition_estimates" not in dumped
    assert "use_pantry" not in dumped
    assert prepare_request(old, Settings()) is old


def test_public_complete_translates_preserving_constraints_and_consent():
    request = PlanRequest(recipes=5, servings=2, max_stores=2, diet_preference="vegetarian",
        purchase_planning_mode="estimated", memberships=["coop_member"],
        recipe_preferences=RecipePreferences(mode="complete", cuisines=["greek", "mexican"],
            min_protein_g=40, max_minutes=40), use_pantry=False)
    translated = prepare_request(request, Settings(complete_recipes_enabled=True), pantry_revision=7)
    assert translated.recipe_preferences == request.recipe_preferences
    assert translated.personal.pantry_revision == 7
    assert not translated.personal.allow_nutrition_estimates  # Purchase opt-in is separate.
    assert not translated.personal.use_pantry
    meal = translated.personal.meals[0]
    assert (meal.count, meal.servings, meal.diet, meal.limits.min_protein_g) == (5, 2, "vegetarian", 40)
    assert translated.membership_programs == request.membership_programs
    assert translated.max_stores == 2
    assert translated.purchase_planning_mode == "estimated"
    assert PlanRequest.model_validate(translated.model_dump()).recipe_preferences == request.recipe_preferences


def test_feature_gate_and_contradictions_are_explicit():
    request = PlanRequest(recipe_preferences=RecipePreferences(mode="complete"))
    with pytest.raises(PolicyConflict, match="inte aktiverade"):
        prepare_request(request, Settings())
    settings = replace(Settings(), complete_recipes_enabled=True)
    request.personal = PersonalPlanning(meals=[MealSettings(limits=PortionLimits(max_protein_g=30))])
    request.recipe_preferences = RecipePreferences(mode="complete", min_protein_g=40)
    with pytest.raises(PolicyConflict, match="maxgräns"):
        prepare_request(request, settings)
    request.personal = PersonalPlanning(meals=[MealSettings(distribution={"fish": 2})])
    request.recipe_preferences = RecipePreferences(mode="complete", allow_fish=False)
    with pytest.raises(PolicyConflict, match="Fisk är avstängd"):
        prepare_request(request, settings)


def test_existing_personal_limits_are_not_lowered_or_opted_in():
    request = PlanRequest(recipe_preferences=RecipePreferences(mode="complete", min_protein_g=30),
        personal=PersonalPlanning(meals=[MealSettings(limits=PortionLimits(min_protein_g=40))]))
    converted = prepare_request(request, Settings(complete_recipes_enabled=True))
    assert converted.personal.meals[0].limits.min_protein_g == 40
    assert not converted.personal.allow_nutrition_estimates
    assert request.personal.meals[0].limits.min_protein_g == 40


@pytest.mark.parametrize("name", ["Vitlök pulver", "Torkad vitlök", "Kycklingnuggets", "Marinerad kyckling"])
def test_raw_product_form_is_guarded_without_requested_nutrition(name):
    ingredient = "vitlök" if "vitlök" in name.casefold() else "kyckling"
    recipe = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={ingredient: "raw_edible"}))
    product = SimpleNamespace(name=name, purchase_terms=None)
    assert not product_form_compatible(recipe, ingredient, product, None)


def test_feedback_accepts_partial_and_binds_nonempty_ratings():
    from app.api.beta_ops import RecipeFeedback
    assert RecipeFeedback(revision=2, recipe_index=0, actual_minutes=55).actual_minutes == 55
    with pytest.raises(ValidationError):
        RecipeFeedback(revision=2, recipe_index=0)


def test_authored_complete_recipe_uses_real_basket_and_survives_storage(tmp_path):
    from app.models.personal import MealSlot
    from app.services.personal_planner import PersonalPlanner
    from app.services.plan_store import PlanStore
    from app.services.recipe_library import candidates

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")
    recipe = candidates(prefs, 2)[0]
    universe = prepared(*[product(i.name, max(100, i.quantity), i.unit, 10) for i in recipe.ingredients])
    request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs,
        personal=PersonalPlanning(meals=[MealSettings(count=1, servings=2)],
            slots=[MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=recipe)]))
    result = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(), facts={}, now=NOW).create()
    assert result.personal.checks["checkout_audit"]["passed"]
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)
    assert result.recipes[0] == recipe
    store = PlanStore(tmp_path / "plans.sqlite3")
    saved = store.create(request, result, owner_actor_hash="a" * 64)
    reopened = PlanStore(tmp_path / "plans.sqlite3").get_owned(saved.plan_id, owner_actor_hash="a" * 64)
    assert reopened.plan.recipes == result.recipes
    assert reopened.request.recipe_preferences == prefs
    assert reopened.plan.personal.checks["search_outcome"]["global_optimum_proven"] is False


def test_edited_unregistered_recipe_cannot_enter_complete_mode():
    from app.services.complete_recipes import matches_preferences
    from app.services.recipe_library import candidates
    prefs = RecipePreferences(mode="complete", cuisines=["greek"])
    recipe = candidates(prefs, 2)[0]
    edited = recipe.model_copy(update={"instructions": ["Använd olja efter eget tycke."]})
    with pytest.raises(ValueError):
        matches_preferences(edited, prefs)


@pytest.mark.asyncio
async def test_job_progress_and_successful_retry_reuse():
    from app.services.plan_jobs import PlanJobs, report_stage
    jobs = PlanJobs(max_pending=1)
    calls = []
    async def work():
        calls.append(1)
        report_stage("candidate_qualification")
        return {"saved": "revision"}
    first = jobs.start("owner", "input+pantry-v1", "request", work)
    await first.task
    assert first.stage == "candidate_qualification"
    assert jobs.start("owner", "input+pantry-v1", "retry", work) is first
    second = jobs.start("owner", "input+pantry-v2", "new-pantry", work)
    await second.task
    assert second is not first and len(calls) == 2
    assert jobs.get(first.job_id, "other") is None
    await jobs.close()
