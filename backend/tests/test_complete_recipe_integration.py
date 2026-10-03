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


def test_distinct_content_shortage_precedes_product_search_and_suggests_actual_time(monkeypatch):
    from app.models.personal import TasteProfile
    from app.services.complete_recipes import validate_content_capacity
    from app.services.personal_planner import PersonalPlanner
    from app.services.recipe_library import candidates

    from backend.tests.test_personal_planning_v2 import NOW, prepared, state

    prefs = RecipePreferences(mode="complete", cuisines=["greek", "mexican"], max_minutes=40)
    meal = MealSettings(count=5, servings=4)
    recipes = candidates(prefs, 4)
    assert len(recipes) >= 5  # A variant count would falsely admit this request.
    with pytest.raises(PolicyConflict) as stopped:
        validate_content_capacity(prefs, meal, TasteProfile(), recipes)
    assert stopped.value.code == "RECIPE_CHOICES_CONFLICT"
    assert "4 distinkta grundrätter" in str(stopped.value)
    assert "43 minuter" in str(stopped.value)
    assert "garanterar inte" in str(stopped.value)
    request = PlanRequest(recipes=5, servings=4, recipe_preferences=prefs)
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(), state(), facts={}, now=NOW)
    def products_must_not_run(*args):
        raise AssertionError("Content shortage must stop before product qualification")
    monkeypatch.setattr(planner, "clean_recipe", products_must_not_run)
    with pytest.raises(PolicyConflict, match="4 distinkta grundrätter"):
        planner._candidates(planner.spec.meals[0])
    # Same choices with an explicit larger time allowance pass content checks.
    wider = prefs.model_copy(update={"max_minutes": 45})
    validate_content_capacity(wider, meal, TasteProfile(), candidates(wider, 4))


def test_content_capacity_honors_merged_diet_and_hard_exclusions():
    from app.models.personal import TasteProfile
    from app.services.complete_recipes import validate_content_capacity
    from app.services.personal_policy import merged_profile
    from app.services.recipe_library import candidates

    prefs = RecipePreferences(mode="complete", cuisines=["indian"])
    recipes = candidates(prefs, 2)
    with pytest.raises(PolicyConflict, match="4 distinkta grundrätter"):
        validate_content_capacity(prefs, MealSettings(count=5, diet="vegetarian"), TasteProfile(), recipes)
    merged = merged_profile(TasteProfile(exclusions=["lök"]), TasteProfile(allergies=["mjölk"]))
    with pytest.raises(PolicyConflict) as stopped:
        validate_content_capacity(prefs, MealSettings(count=5), merged, recipes)
    assert stopped.value.stage == "policy_taste"
    assert "Dina krav har inte ändrats" in str(stopped.value)


def test_valid_solution_reports_nutrition_budget_separately_from_checkout_validity():
    from app.services.complete_recipes import completed_search_outcome
    result = completed_search_outcome({"nutrition_searches": [
        {"budget_exhausted": True, "evaluated": 256, "qualifying_basket_found": True},
        {"budget_exhausted": False, "evaluated": 12}],
        "search": [{"beam_pruned": 9, "equivalent_pruned": 3}]})
    assert result["status"] == "VALID_SOLUTION"
    assert result["global_optimum_proven"] is False
    assert result["search_budget"]["nutrition_status"] == "REACHED"
    assert result["search_budget"]["nutrition_budget_exhausted_recorded"] == 1
    assert result["search_budget"]["distinct_week_proposals_pruned"] == 6
    assert "En giltig meny hittades" in result["budget_message"]


def test_omitted_nutrition_details_do_not_claim_no_search_limit_was_reached():
    from app.services.complete_recipes import completed_search_outcome
    result = completed_search_outcome({"omitted_nutrition_searches": 1})
    assert result["search_budget"]["nutrition_status"] == "UNKNOWN"
    assert completed_search_outcome({})["search_budget"]["nutrition_status"] == "NOT_REACHED"


@pytest.mark.parametrize("label,expected", [
    ("Oliver Kalamata Urkärnade Eko", True),
    ("Oliver Kalamata Urkärnade Ekologiska", True),
    ("Oliver Kalamata Urkärnade Eko Fyllda Med Ost", False),
    ("Oliver Kalamata Urkärnade Eko Vitlök", False),
    ("Oliver Kalamata Urkärnade Eko Tapenade", False),
    ("Oliver Kalamata Urkärnade Eko Marinerade", False),
])
def test_organic_olive_label_remains_whole_identity_not_a_flavor_substitution(label, expected):
    from app.services.complete_recipes import _whole_food_identity
    assert _whole_food_identity("oliver", "preserved_drained", SimpleNamespace(name=label), None) is expected


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


def test_source_nutrition_bound_rejections_are_in_visible_totals():
    from app.services.planning_diagnostics import PlanningDiagnostics
    diagnostics = PlanningDiagnostics()
    diagnostics.pools.append({"meal_type": "dinner", "raw": 2})
    diagnostics.singleton_passed = 1
    diagnostics.reject("nutrition_bound", SimpleNamespace(name="Kvalificerad rätt"), "Högsta möjliga protein understiger målet.")
    result = diagnostics.snapshot()
    assert sum(r["rejected"] for r in result["candidate_rejections"]) + result["singleton_passed"] == 2
    assert result["not_singleton_evaluated"] == 0


def test_authored_complete_recipe_uses_real_basket_and_survives_storage(tmp_path, monkeypatch):
    from app.models.personal import MealSlot
    from app.services.performance_trace import activate_performance_trace
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import ProductFacts
    from app.services.plan_store import PlanStore
    from app.services.recipe_library import candidates

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")
    recipe = candidates(prefs, 2)[0]
    products = [product(i.name, max(100, i.quantity), i.unit, 10).model_copy(update={
        "category": "Kryddor" if i.form == "dry" else "Frukt & grönsaker" if i.form == "raw_edible" else "Mat",
        "name": "Grekisk Yoghurt Naturell 10%" if i.name == "yoghurt naturell" else i.name + " Malen" if i.name == "spiskummin" else i.name,
    }) for i in recipe.ingredients]
    universe = prepared(*products)
    request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs,
        personal=PersonalPlanning(meals=[MealSettings(count=1, servings=2)],
            slots=[MealSlot(id="dinner-1", day=1, meal_type="dinner", recipe=recipe)]))
    facts = {(p.store_id, p.product_id): ProductFacts(source="synthetic_test_declaration", source_product_id=p.product_id,
        source_snapshot_id="v2-frozen", ingredients=(p.name,), ingredients_complete=True) for p in products}
    with activate_performance_trace() as trace:
        result = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(), facts=facts, now=NOW).create()
    assert {'personal_product_facts', 'personal_package_calculation', 'personal_audit', 'personal_week_search', 'personal_nutrition'} <= trace.snapshot().span_statistics.keys()
    assert result.personal.checks["checkout_audit"]["passed"]
    assert result.optimized_basket.total == 10 * len(recipe.ingredients)
    assert result.recipes[0] == recipe
    store = PlanStore(tmp_path / "plans.sqlite3")
    saved = store.create(request, result, owner_actor_hash="a" * 64)
    reopened = PlanStore(tmp_path / "plans.sqlite3").get_owned(saved.plan_id, owner_actor_hash="a" * 64)
    assert reopened.plan.recipes == result.recipes
    assert reopened.request.recipe_preferences == prefs
    assert reopened.plan.personal.checks["search_outcome"]["global_optimum_proven"] is False
    approved = prefs.model_copy(update={"adaptation": "approved"})
    variant = next(r for r in candidates(approved, 2) if r.design.base_id == recipe.design.base_id and r.design.variant_id != recipe.design.variant_id)
    request.recipe_preferences = approved
    automatic = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(), facts=facts, now=NOW)
    monkeypatch.setattr(automatic, "_candidates", lambda meal: [recipe, variant])
    with pytest.raises(PolicyConflict) as stopped:
        automatic.create(replace_slot="dinner-1")
    assert stopped.value.code == "RECIPE_ALTERNATIVE_NOT_FOUND"
    # Explicitly selected approved variants keep their meaning and are fully
    # qualified, even though automatic 'replace recipe' needs another base.
    request.personal.slots[0].recipe = variant
    explicit = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(), facts=facts, now=NOW).create()
    assert explicit.recipes[0] == variant


def test_edited_unregistered_recipe_cannot_enter_complete_mode():
    from app.services.complete_recipes import matches_preferences
    from app.services.recipe_library import candidates
    prefs = RecipePreferences(mode="complete", cuisines=["greek"])
    recipe = candidates(prefs, 2)[0]
    edited = recipe.model_copy(update={"instructions": ["Använd olja efter eget tycke."]})
    with pytest.raises(ValueError):
        matches_preferences(edited, prefs)


def test_complete_candidates_use_actual_product_nutrition_not_legacy_coverage(monkeypatch):
    from app.services import recipe_library
    from app.services.personal_planner import PersonalPlanner
    from app.services.personal_policy import ProductFacts

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products", min_protein_g=1)
    recipe = recipe_library.candidates(prefs, 2)[0]
    monkeypatch.setattr(recipe_library, "candidates", lambda *args: [recipe])
    products = [product(i.name, max(100, i.quantity), i.unit, 10).model_copy(update={
        "category": "Kryddor" if i.form == "dry" else "Frukt & grönsaker" if i.form == "raw_edible" else "Mat",
        "name": "Grekisk Yoghurt Naturell 10%" if i.name == "yoghurt naturell" else i.name + " Malen" if i.name == "spiskummin" else i.name,
    }) for i in recipe.ingredients]
    facts = {(p.store_id, p.product_id): ProductFacts(source="synthetic_test_declaration", source_product_id=p.product_id,
        source_snapshot_id="v2-frozen", ingredients=(p.name,), ingredients_complete=True, nutrition={"protein_g": 1},
        nutrition_unit=p.usable_unit, nutrition_basis="Synthetic test per 100 input units") for p in products}
    request = PlanRequest(recipes=1, servings=2, max_stores=1, recipe_preferences=prefs,
        personal=PersonalPlanning(allow_nutrition_estimates=True, meals=[MealSettings(count=1, servings=2)]))
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(*products), state(), facts=facts, now=NOW)
    def legacy_estimate_must_not_run(*args):
        raise AssertionError("Legacy coarse coverage cannot override sealed complete design/source nutrition")
    monkeypatch.setattr(planner.service, "_nutrition_for", legacy_estimate_must_not_run)
    assert planner._candidates(planner.spec.meals[0]) == [recipe]
    assert planner.diagnostics.singleton_passed == 1
    request.recipe_preferences = prefs.model_copy(update={"min_protein_g": 300})
    strict = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(*products), state(), facts=facts, now=NOW)
    with pytest.raises(PolicyConflict) as stopped:
        strict._candidates(strict.spec.meals[0])
    assert stopped.value.code == "NUTRITION_TARGET_NOT_MET"
    # Complete candidates also have singleton qualification with no optional
    # target. Subsequent week-search evaluation must not count them twice.
    request.recipe_preferences = prefs.model_copy(update={"min_protein_g": None})
    unrestricted = PersonalPlanner(request, Settings(complete_recipes_enabled=True), prepared(*products), state(), facts=facts, now=NOW)
    unrestricted.create()
    assert unrestricted.diagnostics.singleton_passed == 1


@pytest.mark.parametrize("ingredient,form,label,category,expected", [
    ("dill", "raw_edible", "Dill & Gräslök Chips", "Snacks", False),
    ("dill", "raw_edible", "Dill Påse", "Kryddor", False),
    ("dill", "raw_edible", "Dill", "Frukt & grönt", True),
    ("dill", "raw_edible", "Dill Finhackad Fryst", "Fryst", True),
    ("oregano", "dry", "Oregano Klass 1", "Frukt & grönt", False),
    ("oregano", "dry", "Oregano Burk", "Kryddor", True),
    ("spiskummin", "dry", "Kryddost Spiskummin & Nejlika 31%", "Ost", False),
    ("tofu", "as_sold", "Tofu Naturell Fast Vegansk", "Vegetariskt", True),
    ("tofu", "as_sold", "Tofu Alspånsrökt Ekologisk", "Vegetariskt", False),
    ("tofu", "as_sold", "Tofu Silkesmjuk Ekologisk", "Vegetariskt", False),
    ("yoghurt naturell", "as_sold", "Grekisk Yoghurt Jordgubb 0,2%", "Mejeri", False),
    ("yoghurt naturell", "as_sold", "Grekisk Yoghurt Naturell 10%", "Mejeri", True),
    ("kyckling", "raw_edible", "Kyckling Nuggets", "Fågel", False),
    ("kyckling", "raw_edible", "Kyckling Bröstfilé", "Fågel", True),
    ("rapsolja", "as_sold", "Smör- & Rapsolja Flytande", "Matfett", False),
    ("jordnötssmör", "as_sold", "Jordnötssmör Kakao Granola Nötsmörsbakad", "Skafferi", False),
    ("sojasås", "as_sold", "Sojasås Sweet", "Soja", False),
    ("sojasås", "as_sold", "Sojasås Japansk", "Soja", True),
    ("keso", "as_sold", "Keso Cottage Cheese Naturell Mini 1,5%", "Mejeri", True),
    ("selleri", "raw_edible", "Bladselleri", "Frukt & grönt", True),
    ("rödbeta", "raw_edible", "Rödbetor Kokta", "Grönsaker", False),
    ("rödbeta", "raw_edible", "Rödbetor Klass 1", "Frukt & grönt", True),
    ("cayennepeppar", "dry", "Cayennepeppar", "Kryddor", True),
    ("mjölk", "as_sold", "Mellanmjölk 1,5%", "Mejeri", True),
    ("tortillas", "as_sold", "Street Tortillas", "Bröd", True),
    ("tortillas", "as_sold", "Glutenfria Corn Tortillas", "Bröd", True),
    ("tortillas", "as_sold", "Tortillas Nacho Cheese Chips", "Snacks", False),
    ("bönor", "cooked_drained", "Vita Bönor Stora Eko", "Konserver", True),
    ("bönor", "cooked_drained", "Vita Bönor i Tomatsås", "Konserver", False),
])
def test_whole_food_identity_never_substring_matches(ingredient, form, label, category, expected):
    from app.services.complete_recipes import _whole_food_identity
    assert _whole_food_identity(ingredient, form, SimpleNamespace(name=label, category=category), None) == expected


def test_compound_chili_and_unknown_pantry_form_do_not_qualify():
    from app.services.complete_recipes import _whole_food_identity, pantry_form_compatible
    product = SimpleNamespace(name="Chilipulver", category="Kryddor")
    mixture = SimpleNamespace(ingredients=["Chilipeppar 84%, spiskummin, salt, oregano, vitlök."], ingredients_complete=True)
    assert not _whole_food_identity("chilipulver", "dry", product, mixture)
    row = {"name": "vitlök", "input_form": "raw_edible"}
    assert not pantry_form_compatible({"name": "vitlök", "unit": "g"}, row)
    assert not pantry_form_compatible({"name": "Torkad vitlök", "unit": "g", "form": "raw_edible"}, row)
    assert pantry_form_compatible({"name": "vitlök", "unit": "g", "form": "raw_edible"}, row)


@pytest.mark.parametrize("name,form,requirement,good,bad", [
    ("linser", "dry", "red_split", "Röda Linser Delade", "Röda Linser Hela"),
    ("spiskummin", "dry", "ground", "Spiskummin Malen", "Spiskummin Hel"),
    ("ris", "dry", "white_rice", "Basmatiris", "Ris Fullkorn"),
    ("spenat", "as_sold", "frozen", "Spenat Fryst", "Spenat"),
])
def test_generic_pantry_cannot_bypass_reviewed_product_requirements(name, form, requirement, good, bad):
    from app.services.complete_recipes import pantry_form_compatible
    row = {"name": name, "input_form": form, "product_requirements": [requirement]}
    assert pantry_form_compatible({"name": good, "unit": "g", "form": form}, row)
    assert not pantry_form_compatible({"name": bad, "unit": "g", "form": form}, row)


@pytest.mark.parametrize("name,requirement,good,bad", [
    ("yoghurt naturell", "thick", "Grekisk Yoghurt Naturell 10%", "Mild Naturell Yoghurt 0,5%"),
    ("tofu", "firm", "Tofu Naturell Extra Fast", "Tofu Naturell"),
    ("spiskummin", "ground", "Spiskummin Malen", "Spiskummin Hel"),
    ("linser", "red_split", "Röda Linser Delade", "Röda Linser Hela"),
    ("ris", "white_rice", "Basmatiris", "Ris Fullkorn"),
])
def test_reviewed_texture_and_cooking_time_properties_are_binding(name, requirement, good, bad):
    form = "as_sold" if requirement in {"thick", "firm"} else "dry"
    recipe = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={name: form}),
        ingredients=[SimpleNamespace(name=name, product_requirements=[requirement])])
    def item(label):
        return SimpleNamespace(name=label, category="Kryddor", purchase_terms=None)
    assert product_form_compatible(recipe, name, item(good), None)
    assert not product_form_compatible(recipe, name, item(bad), None)


def test_supplier_classification_is_bound_to_product_snapshot_and_package():
    from app.services.complete_recipes import _requirements_compatible
    product = SimpleNamespace(name="Röda linser", product_id="source-product", store_id="source-store",
        package_quantity=400, package_unit="g", source_provenance=SimpleNamespace(source_snapshot_id="snapshot"))
    source = {"identity_method": "unique_exact_complete_brand_variant_fixed_pack", "bound_product_id": "source-product",
        "bound_store_id": "source-store", "bound_snapshot_id": "snapshot", "source_package_quantity": 400,
        "source_package_unit": "g", "url": "https://manufacturer.example/roda-linser", "sha256": "digest"}
    fact = SimpleNamespace(ingredients=["Röda linser"], product_classification=("red_split",),
        field_sources={"product_classification": [source]})
    assert _requirements_compatible("linser", ["red_split"], product, fact)
    product.package_quantity = 800
    assert not _requirements_compatible("linser", ["red_split"], product, fact)
    product.package_quantity = 400
    product.source_provenance.source_snapshot_id = "other"
    assert not _requirements_compatible("linser", ["red_split"], product, fact)


def test_white_bean_variant_requires_positive_named_white_beans():
    from app.services.complete_recipes import _requirements_compatible
    assert _requirements_compatible("bönor", ["white_beans"], SimpleNamespace(name="Vita Bönor Stora Eko"), None)
    assert not _requirements_compatible("bönor", ["white_beans"], SimpleNamespace(name="Bönor"), None)
    assert _requirements_compatible("bönor", ["white_beans"], SimpleNamespace(name="Bönor"), SimpleNamespace(ingredients=["Vita bönor, vatten, salt."]))
    assert not _requirements_compatible("bönor", ["future_unknown_requirement"], SimpleNamespace(name="Vita Bönor"), None)


def test_source_frozen_corn_qualifies_without_category_guess_and_rejects_mixed_food():
    from app.services.personal_source_facts import project_raw_facts
    f = project_raw_facts({"id": "gtin", "consumerInformationText": ["Fryst"],
            "listOfIngredients": "INGREDIENSER: Majskorn (Ungern)."}, chain="coop", product_id="corn",
        snapshot_id="snapshot", source_reference="coop:raw:verified-hash")
    recipe = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={"majs": "as_sold"}),
        ingredients=[SimpleNamespace(name="majs", product_requirements=("frozen", "plain"))])
    product = SimpleNamespace(name="Majs", product_id="corn", category="Grönsaker", purchase_terms=None,
        source_provenance=SimpleNamespace(source_snapshot_id="snapshot"))
    assert product_form_compatible(recipe, "majs", product, f)
    product.name = "Ärtor Majs Paprika"
    assert not product_form_compatible(recipe, "majs", product, f)
    product.name = "Majs"
    product.source_provenance.source_snapshot_id = "different-snapshot"
    assert not product_form_compatible(recipe, "majs", product, f)


def test_resolution_cache_separates_texture_requirements():
    from app.models.personal import TasteProfile
    from app.services.personal_planner import PersonalPlanner
    from app.services.recipe_library import candidates

    from backend.tests.test_personal_planning_v2 import NOW, prepared, product, state

    prefs = RecipePreferences(mode="complete", cuisines=["greek"], adaptation="products")
    recipe = candidates(prefs, 2)[0]
    plain = recipe.model_copy(update={"ingredients": [i.model_copy(update={"product_requirements": ()}) for i in recipe.ingredients]})
    thin = product("Mild Naturell Yoghurt 0,5%", 1000, "g", 10, identity="thin")
    thick = product("Grekisk Yoghurt Naturell 10%", 1000, "g", 20, identity="thick")
    universe = prepared(thin, thick)
    request = PlanRequest(recipe_preferences=prefs, personal=PersonalPlanning(meals=[MealSettings(count=1)]))
    planner = PersonalPlanner(request, Settings(complete_recipes_enabled=True), universe, state(), facts={}, now=NOW)
    # Lower-level cache only: clean_recipe separately rejects the unregistered
    # modified content, while resolve must still never conflate its constraints.
    ordinary = planner.resolve("yoghurt naturell", 100, "g", profile=TasteProfile(), recipe=plain)
    qualified = planner.resolve("yoghurt naturell", 100, "g", profile=TasteProfile(), recipe=recipe)
    assert {c.product_id for _, c in ordinary} == {"thin", "thick"}
    assert {c.product_id for _, c in qualified} == {"thick"}


def test_culinary_formula_is_separate_from_allergen_completeness():
    from app.services.complete_recipes import plain_juice_composition, plain_peanut_composition
    assert plain_juice_composition("citronjuice", "INGREDIENSER: Citronjuice från koncentrat, antioxidationsmedel (KALIUMMETABISULFIT).")
    assert not plain_juice_composition("citronjuice", "Citronjuice 10%, vatten, socker.")
    assert not plain_juice_composition("citronjuice", "Citronjuice, limejuice.")
    assert plain_juice_composition("citronjuice", "INGREDIENSER: Citronjuice (citron: EU (Italien och/eller Spanien)), konserveringsmedel (E 224 KALIUMDISULFIT).")
    assert plain_juice_composition("citronjuice", "INGREDIENSER: Citronjuice från koncentrat (citron: Argentina), konserveringsmedel (E 224 SULFIT).")
    assert plain_juice_composition("limejuice", "INGREDIENSER: Ekologisk limejuice** (lime: Brasilien). **KRAV-ekologisk ingrediens. KRAV-märkningen verifieras av Kiwa.")
    assert not plain_juice_composition("citronjuice", "Citronjuice, vatten.")
    assert not plain_juice_composition("citronjuice", "Citronjuice (citron: Italien), socker.")
    assert plain_peanut_composition("INGREDIENSER: Rostade och malda ekologiska JORDNÖTTER 99,4% (Kina), havssalt. Kan innehålla spår av mandel, hasselnötter och cashewnötter.")
    assert not plain_peanut_composition("JORDNÖTTER 90%, rörsocker, vegetabiliskt fett, salt.")
    recipe = SimpleNamespace(design=True, preparation=SimpleNamespace(input_forms={"citronjuice": "as_sold"}),
        ingredients=[SimpleNamespace(name="citronjuice", product_requirements=["pure_juice"])])
    fact = SimpleNamespace(ingredients=["Citronjuice från koncentrat."], ingredients_complete=False, conflicts=[])
    assert product_form_compatible(recipe, "citronjuice", SimpleNamespace(name="Citronjuice", category="Juice", purchase_terms=None), fact)
    assert fact.ingredients_complete is False


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
