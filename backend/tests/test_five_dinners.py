"""New real meal structures, strict identity, accounting and observable failures."""

from copy import deepcopy
from itertools import combinations
from unittest.mock import patch

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import MealSettings, MealSlot, PantryItem, PersonalPlanning, PortionLimits
from app.models.recipe import RecipeIngredient
from app.services.meal_plan_optimizer import MealPlanService
from app.services.nutrition_reference import product_reference, reference_evidence
from app.services.personal_nutrition import calculation_basis, is_couscous_preparation
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, run, state
from backend.tests.test_personal_qualified_facts import facts


def recipes():
    return DeterministicRecipeCandidateGenerator().generate_reference_candidates()


def five_request():
    return PlanRequest(
        recipes=5, servings=4, diversity_mode="balanced", max_stores=2,
        personal=PersonalPlanning(allow_nutrition_estimates=True, meals=[MealSettings(
            count=5, servings=4, limits=PortionLimits(min_protein_g=20, max_kcal=800),
        )]),
    )


def pool():
    return prepared(*[product(n, q, "g", price).model_copy(
        update={"canonical_name": "fisk", "canonical_food": "fish_meat", "food_family": "fish",
                "product_role": "white_fish", "product_form": "fillet"} if n == "Torskfilé" else {}
    ) for n, q, price in [
        ("Kycklingbröstfilé", 800, 80), ("Torskfilé", 400, 40), ("Laxfilé", 400, 50),
        ("Långkornigt Ris", 1000, 20), ("Äggnudlar", 250, 10), ("Morötter", 1000, 10),
        ("Vitkål", 1000, 10), ("Couscous", 500, 20), ("Naturell Tofu Fast", 200, 15),
        ("Tomater", 500, 20),
    ]])


def test_new_families_unlock_five_without_relaxed_similarity_or_repetition():
    s = MealPlanService(Settings(price_provider="mock"))
    req = five_request()
    policy = s._diversity_policy_for(req, req.diversity_mode)
    rs = recipes()
    constraints = s._culinary_constraints(rs, policy)
    assert policy.max_pairwise_culinary_similarity == 0.85
    assert policy.max_same_carbohydrate_meals == policy.max_same_cooking_method_meals == 2
    assert not any(s.menu_optimizer.accepts_recipes(c, constraints) for c in combinations(rs[:8], 5))
    assert any(s.menu_optimizer.accepts_recipes(c, constraints) for c in combinations(rs, 5))
    assert not s.menu_optimizer.accepts_recipes(rs[6:8], constraints)  # Same salmon core.


def test_five_and_pantry_never_use_package_surplus_or_mutate_inventory(monkeypatch):
    monkeypatch.setattr(DeterministicRecipeCandidateGenerator, "generate_for_meal_type", lambda *a, **k: [])
    stock = state([PantryItem(name="ris", quantity=500, unit="g", nutrition_reference="slv:2481:dry")])
    before = deepcopy(stock)
    products = pool()
    evidence = {(p.store_id, p.product_id): facts(p) for p in products.universe.products}
    with patch("socket.socket.connect", side_effect=AssertionError("external call forbidden")):
        result = run(products, five_request(), stock, facts=evidence)
    assert len(result.recipes) == 5
    assert stock == before
    assert sum(a["quantity"] for a in result.personal.allocations) == 500
    assert result.data.live_chain_requests == 0
    for recipe, n in zip(result.recipes, result.personal.checks["nutrition"], strict=True):
        assert n["values"]["protein_g"] >= 20 and n["values"]["kcal"] <= 800
        assert sum(s["quantity"] for s in n["sources"]) == sum(i.quantity for i in recipe.ingredients)
    assert all(i.packages_needed == int(i.packages_needed)
               for store in result.optimized_basket.stores for i in store.items)


@pytest.mark.parametrize("name,need", [
    ("Hela Tomater Skalade", "tomat"), ("Soltorkade Tomater", "tomat"),
    ("Körsbärstomater hela", "tomat"),
    ("Tomatpuré", "tomat"), ("Tomatsoppa", "tomat"),
    ("Pärlcouscous", "couscous"), ("Couscous Fullkorn", "couscous"),
    ("Glutenfri Couscous", "couscous"), ("Take away Couscous", "couscous"),
    ("Silkestofu Naturell", "tofu"), ("Tofu Naturell Fast i Lag", "tofu"),
])
def test_better_metadata_cannot_qualify_the_wrong_form(name, need):
    p = product(name, 500, "g", 1)
    f = facts(p, nutrition={"protein_g": 30, "kcal": 100}, nutrition_unit="g",
              nutrition_basis="per 100 g", nutrition_preparation="as_sold")
    assert product_reference(p, need, f) is None


def test_normal_fresh_tomato_wins_over_cheaper_canned_with_complete_metadata():
    canned = product("Hela Tomater Skalade", 1000, "g", 1)
    products = prepared(*pool().universe.products, canned)
    req = five_request()
    req.personal.slots = [MealSlot(id="d", day=1, meal_type="dinner", recipe=recipes()[-1])]
    f = facts(canned, nutrition={"protein_g": 30, "kcal": 100}, nutrition_unit="g",
              nutrition_basis="per 100 g", nutrition_preparation="as_sold")
    plan = run(products, req, facts={(canned.store_id, canned.product_id): f})
    names = [i.product_name for g in plan.optimized_basket.stores for i in g.items]
    assert "Tomater" in names and canned.name not in names


def test_cod_uses_fried_component_and_not_poached_or_invented_yield():
    fry = reference_evidence(1246, cooked=True, method="fry")
    boil = reference_evidence(1246, cooked=True)
    history = fry.field_sources["nutrition.kcal"][0]["transformations"][0]
    assert history["cooked_food_id"] == 1337
    assert history["raw_input_g"] == 550
    assert history["documented_final_batch_g"] == pytest.approx(396.875)
    assert fry.nutrition != boil.nutrition
    assert reference_evidence(1173, cooked=True, method="fry") is None


def test_no_discard_assembly_is_explicit_and_edited_preparation_stays_blocked():
    recipe = recipes()[-1]
    assert is_couscous_preparation(recipe)
    with pytest.raises(PolicyConflict):
        calculation_basis(recipe)
    for edit in [
        recipe.model_copy(update={"instructions": recipe.instructions + ["Häll av vattnet."]}),
        recipe.model_copy(update={"ingredients": [
            RecipeIngredient(name="pasta", quantity=320, unit="g"), *recipe.ingredients[:2],
        ]}),
    ]:
        with pytest.raises(PolicyConflict):
            calculation_basis(edit, allow_estimates=True)
    assert calculation_basis(recipe, allow_estimates=True)["cooked_weight"] == "NOT_VERIFIED"


def test_failure_counts_expose_candidates_separately_from_search_pruning(monkeypatch):
    monkeypatch.setattr(DeterministicRecipeCandidateGenerator, "generate_for_meal_type", lambda *a, **k: [])
    req = five_request().model_copy(update={"max_same_cooking_method_meals": 1})
    products = pool()
    evidence = {(p.store_id, p.product_id): facts(p) for p in products.universe.products}
    planner = PersonalPlanner(req, Settings(price_provider="mock"), products, state(), facts=evidence, now=NOW)
    with pytest.raises(PolicyConflict) as error:
        planner.create()
    d = error.value.diagnostics
    assert d["raw_recipe_pool"] > 0
    assert d["raw_recipe_pool"] == (
        sum(r["rejected"] for r in d["candidate_rejections"])
        + d["singleton_passed"] + d["not_singleton_evaluated"]
    )
    assert any(r["rejections"]["variation"] for r in d["search"])
    for step in d["search"]:
        assert step["proposals"] == step["constraints_rejected"] + step["evaluation_rejected"] + step["priced"]
        assert step["priced"] == step["retained"] + step["beam_pruned"]
        assert sum(step["rejections"].values()) == step["constraints_rejected"] + step["evaluation_rejected"]
