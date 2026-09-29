"""Synthetic prices only: nutrient alternatives must respect the shop budget."""
from copy import deepcopy

from app.models.personal import MealSettings, MealSlot, PortionLimits
from app.models.recipe import Recipe, RecipeIngredient

from backend.tests.test_personal_planning_v2 import prepared, product, request, run
from backend.tests.test_personal_qualified_facts import facts


def test_joint_extrema_within_shop_budget_survive_bounded_nearby_search():
    products, evidence, slots = [], {}, []
    for index, (name, unit, outside) in enumerate(
        [("mjölk", "ml", "ica"), ("bröd", "g", "willys"), ("ost", "g", "hemkop")]
    ):
        # Each product is independently identified. All-global maxima need
        # three shops; the viable common-shop choice is far from cheap origin.
        variants = [("coop", n, n) for n in range(1, 13)]
        variants += [("coop", 20, 30), (outside, 100, 40)]
        for store, protein, price in variants:
            p = product(name, 100, unit, price, store=store,
                        identity=f"synthetic-{index}-{store}-{protein}")
            products.append(p)
            evidence[(p.store_id, p.product_id)] = facts(
                p, nutrition={"protein_g": protein}, nutrition_unit=unit,
                nutrition_basis=f"per 100 {unit} as sold",
            )
        slots.append(MealSlot(
            id=f"breakfast-{index+1}", day=index+1, meal_type="breakfast",
            recipe=Recipe(name=f"Synthetic cold {name}", servings=1,
                          ingredients=[RecipeIngredient(name=name, quantity=100, unit=unit)],
                          instructions=["Servera tillsammans."]),
        ))
    req = request(slots=slots, meals=[MealSettings(
        meal_type="breakfast", count=3, servings=1, limits=PortionLimits(min_protein_g=20),
    )])
    req.max_stores = 2
    before = deepcopy(req)
    result = run(prepared(*products), req, facts=evidence)
    assert req == before
    assert result.optimized_basket.store_count <= 2
    assert result.optimized_basket.total == 90
    assert [x['values']['protein_g'] for x in result.personal.checks['nutrition']] == [20, 20, 20]
    assert all(i.product_id.endswith('-coop-20') for s in result.optimized_basket.stores for i in s.items)
