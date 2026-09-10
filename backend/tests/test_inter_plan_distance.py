from dataclasses import replace

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.diversity import DiversityMode
from app.services.inter_plan_distance import (
    compare_plans,
    reference_identity,
    required_changes,
    search_conditioned_varied,
)
from app.services.meal_plan_optimizer import MealPlanService
from app.services.menu_optimizer import MenuOptimizer

from backend.tests.test_price_universe_runtime import _build_prepared, _product
from backend.tests.test_structural_variation_v2 import meal


@pytest.mark.parametrize("count,changed", [(3, 2), (4, 2), (5, 3), (6, 3), (7, 4)])
def test_versioned_overlap_policy(count, changed):
    assert required_changes(count) == changed


def test_rename_reorder_minor_vegetable_and_protein_swaps_do_not_count():
    baseline = [meal(), meal(carb="potatis", steps=["Rosta i ugn vid 225 grader."])]
    assert compare_plans(baseline, list(reversed(baseline)))["structurally_different_dinners"] == 0
    renamed = baseline[0].model_copy(update={"name": "Ett helt annat namn"})
    report = compare_plans(baseline, [renamed, baseline[1]])
    assert report["exact_overlap_count"] == 2
    assert report["structurally_different_dinners"] == 0
    for minor in [meal(veg="rödlök"), meal(protein="tofu")]:
        report = compare_plans(baseline, [minor])
        assert report["structurally_different_dinners"] == 0
        assert report["dinners"][0]["comparisons"][0]["components"]["cooking"] == 1
    assert reference_identity(baseline) == reference_identity(list(reversed(baseline)))
    assert reference_identity(baseline) != reference_identity([meal(steps=["Låt sjuda till soppa."])])


def test_shared_ingredients_with_different_preparation_count():
    baseline = meal(carb="potatis", steps=["Låt sjuda till en tjock gryta."])
    alternative = baseline.model_copy(update={"instructions": ["Rosta på plåt i ugn vid 225 grader."]})
    report = compare_plans([baseline], [alternative])
    assert report["structurally_different_dinners"] == 1
    assert report["dinners"][0]["comparisons"][0]["components"]["ingredient"] == 1


@pytest.fixture
async def frozen_search():
    baseline = [
        meal(name="Ris", protein="tofu", carb="ris", steps=["Koka ris. Stek tofu och morot."]),
        meal(name="Pasta", protein="linser", carb="pasta", steps=["Koka pasta och vänd i sås."]),
        meal(name="Gryta", protein="kikärtor", carb="potatis", steps=["Låt sjuda till en gryta."]),
        meal(name="Wrap", protein="ägg", carb="tortillas", steps=["Stek fyllningen och vik tortillas."]),
        meal(name="Plåt", protein="kyckling", carb="couscous", steps=["Rosta i ugn vid 225 grader."]),
    ]
    alternatives = [r.model_copy(update={"name": name, "instructions": [step]}) for r, name, step in zip(
        baseline, ["Soppa", "Gratäng", "Potatispanna"],
        ["Koka med vatten och låt sjuda till soppa.", "Gratinera pasta i ugn.", "Stek potatis och kikärtor."],
    )]
    canonicals = sorted({i.canonical_name for r in baseline for i in r.ingredients})
    products = [_product(str(i), canonical, price=10, quantity=100000, index=i)
                for i, canonical in enumerate(canonicals)]
    products.append(_product("extra", "broccoli", price=100, quantity=100000, index=99))
    _, prepared, _, _ = await _build_prepared(products=products)
    service = MealPlanService(Settings())
    recipes = baseline + alternatives
    policy = service._diversity_policy_for(PlanRequest(recipes=5), DiversityMode.VARIED)
    # Require one of each major role in this controlled fixture: all qualifying
    # menus buy exactly the same packages, allowing a true same-price assertion.
    constraints = replace(service._culinary_constraints(recipes, policy),
                          max_same_primary_ingredient_meals=1, max_same_carbohydrate_meals=1)
    optimizer = MenuOptimizer()
    options = {"recipe_count": 5, "max_stores": 1, "beam_width": 120,
               "price_universe": prepared.universe, "package_cost_cache": prepared.package_cache,
               "basket_result_cache": prepared.basket_cache, "search_reuse_enabled": True,
               "admissible_lower_bound_enabled": True}
    products = prepared.economic_pool.candidates_by_name
    stores = prepared.stores
    balanced = optimizer.optimize(baseline, products, stores, diversity_constraints=constraints, **options)
    return optimizer, products, stores, recipes, constraints, balanced, options


async def test_identical_rejected_three_genuine_changes_and_same_price_accepted(frozen_search):
    optimizer, products, stores, recipes, constraints, balanced, options = frozen_search
    found = search_conditioned_varied(optimizer, recipes, products, stores,
                                     balanced_result=balanced, target_constraints=constraints,
                                     fallback_constraints=constraints, **options)
    report = compare_plans(balanced.recipes, found.result.recipes)
    assert report["target_met"]
    assert report["structurally_different_dinners"] == 3
    assert report["exact_overlap_count"] == 2
    assert found.result.basket.total == balanced.basket.total
    assert found.result.basket_audit.passed
    assert found.result.basket.store_count <= 1
    assert found.internal_targets_relaxed is False


async def test_cheapest_qualifying_plan_beats_unnecessary_expense(frozen_search):
    optimizer, products, stores, recipes, constraints, balanced, options = frozen_search
    expensive = recipes[-1].model_copy(update={"name": "A dyr panna",
        "ingredients": [*recipes[-1].ingredients, meal(veg="broccoli").ingredients[-1]]})
    service = MealPlanService(Settings())
    all_recipes = [expensive, *recipes]
    policy = service._diversity_policy_for(PlanRequest(recipes=5), DiversityMode.VARIED)
    constraints = replace(service._culinary_constraints(all_recipes, policy),
                          max_same_primary_ingredient_meals=1, max_same_carbohydrate_meals=1)
    found = search_conditioned_varied(optimizer, all_recipes, products, stores,
                                     balanced_result=balanced, target_constraints=constraints,
                                     fallback_constraints=constraints, **options)
    assert found.result.basket.total == balanced.basket.total
    assert expensive.name not in {r.name for r in found.result.recipes}


async def test_over_25_percent_rejected_and_infeasible_target_reported(frozen_search):
    optimizer, products, stores, recipes, constraints, balanced, options = frozen_search
    expensive = [r.model_copy(update={"ingredients": [*r.ingredients, meal(veg="broccoli").ingredients[-1]]})
                 for r in recipes[5:]]
    found = search_conditioned_varied(optimizer, [*recipes[:5], *expensive], products, stores,
                                     balanced_result=balanced, target_constraints=constraints,
                                     fallback_constraints=constraints, **options)
    assert found.result.basket.total <= balanced.basket.total * 1.25
    assert not compare_plans(balanced.recipes, found.result.recipes)["target_met"]
    assert any(a["reason"] == "lowest_found_plan_over_budget" for a in found.attempts)
    assert found.result.basket_audit.passed


async def test_best_partial_distance_is_returned_when_target_impossible(frozen_search):
    optimizer, products, stores, recipes, constraints, balanced, options = frozen_search
    found = search_conditioned_varied(optimizer, recipes[:7], products, stores,
                                     balanced_result=balanced, target_constraints=constraints,
                                     fallback_constraints=constraints, **options)
    report = compare_plans(balanced.recipes, found.result.recipes)
    assert report["structurally_different_dinners"] == 2
    assert report["target_met"] is False
    assert found.attempts[0]["reason"] == "insufficient_structurally_distinct_candidates"
