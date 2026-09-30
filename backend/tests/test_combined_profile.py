"""Independent thresholds, new ordinary cold meals and preserved data gates."""

from copy import deepcopy
from dataclasses import replace

import pytest
from app.models.personal import MealSettings, MealSlot, PortionLimits
from app.models.recipe import Recipe, RecipeIngredient
from app.services.diet_policy import recipe_respects_diet
from app.services.personal_nutrition import calculation_basis
from app.services.personal_policy import PolicyConflict
from app.services.reviewed_cold_meals import candidates, plain_quark

from backend.tests.test_personal_planning_v2 import prepared, product, request, run
from backend.tests.test_personal_qualified_facts import facts


def products():
    p = prepared(
        product("Kvarg Naturell 0,2%", 500, "g", 20).model_copy(
            update={"semantic_confidence": "low"}
        ),
        product("bröd", 500, "g", 25),
        product("Hushållsost", 500, "g", 40),
    )
    values = {"Kvarg Naturell 0,2%": 11, "bröd": 9, "Hushållsost": 26}
    evidence = {
        (x.store_id, x.product_id): facts(
            x,
            animal=x.name != "bröd",
            ingredients=("Pastöriserad MJÖLK, mjölksyrakultur",) if "Kvarg" in x.name else (),
            nutrition={"protein_g": values[x.name]},
            nutrition_unit="g",
            nutrition_basis="per 100 g as sold",
        )
        for x in p.universe.products
    }
    return p, evidence


@pytest.mark.parametrize("servings", [1, 2, 4])
def test_per_portion_protein_does_not_change_with_servings_or_require_final_weight(servings):
    p, evidence = products()
    meal = candidates("breakfast", servings)[0]
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=meal)],
        meals=[
            MealSettings(
                meal_type="breakfast",
                count=1,
                servings=servings,
                limits=PortionLimits(min_protein_g=30),
            )
        ],
    )
    result = run(p, req, facts=evidence)
    assert result.personal.checks["nutrition"][0]["values"] == {"protein_g": 34.7}
    assert result.portions == servings
    assert not req.personal.allow_nutrition_estimates
    req.personal.meals[0].limits.min_weight_g = 100
    with pytest.raises(PolicyConflict, match="tillagningsutbyte"):
        run(p, req, facts=evidence)


def test_each_meal_keeps_own_minimum_and_zero_count_has_no_effect():
    p, evidence = products()
    req = request(
        slots=[
            MealSlot(id="b", day=1, meal_type="breakfast", recipe=candidates("breakfast", 1)[0]),
            MealSlot(id="s", day=1, meal_type="snack", recipe=candidates("snack", 1)[0]),
        ],
        meals=[
            MealSettings(count=0, servings=2, limits=PortionLimits(min_protein_g=300, max_kcal=0)),
            MealSettings(
                meal_type="breakfast", count=1, servings=1, limits=PortionLimits(min_protein_g=30)
            ),
            MealSettings(
                meal_type="snack", count=1, servings=1, limits=PortionLimits(min_protein_g=20)
            ),
        ],
    )
    before = deepcopy(req)
    result = run(p, req, facts=evidence)
    assert [r["values"]["protein_g"] for r in result.personal.checks["nutrition"]] == [34.7, 22]
    assert req == before
    req.personal.meals[1].limits.min_protein_g = 40
    with pytest.raises(PolicyConflict, match="protein_g.*minimum 40"):
        run(p, req, facts=evidence)


@pytest.mark.parametrize(
    "change", [{"nutrition": {}}, {"nutrition_unit": "ml"}, {"nutrition_basis": None}]
)
def test_cold_quark_does_not_turn_missing_data_into_zero_or_assume_density(change):
    p, evidence = products()
    key = next(k for k in evidence if "Kvarg" in k[1])
    evidence[key] = replace(evidence[key], **change)
    req = request(
        slots=[MealSlot(id="s", day=1, meal_type="snack", recipe=candidates("snack", 1)[0])],
        meals=[
            MealSettings(
                meal_type="snack", count=1, servings=1, limits=PortionLimits(min_protein_g=20)
            )
        ],
    )
    with pytest.raises(PolicyConflict) as error:
        run(p, req, facts=evidence)
    assert error.value.code == "DATA_BLOCKED"


@pytest.mark.parametrize(
    "name",
    [
        "Kvarg Vanilj",
        "Kvarg Naturell Dessert",
        "Kvarg Naturell Proteinpudding",
        "Kvargdryck Naturell",
    ],
)
def test_review_never_promotes_unreviewed_variants(name):
    _p, evidence = products()
    f = next(v for k, v in evidence.items() if "Kvarg" in k[1])
    assert not plain_quark(product(name, 500, "g", 20), f)


def test_cold_review_rejects_heating_and_vegan():
    meal = candidates("snack", 1)[0]
    assert not recipe_respects_diet(meal, preference="vegan")
    assert recipe_respects_diet(meal, preference="vegetarian")
    meal.instructions.append("Koka och häll av.")
    with pytest.raises(PolicyConflict, match="beredningsgrund"):
        calculation_basis(meal, allow_estimates=True)


def test_joint_nutrition_choices_retain_package_prices_for_the_whole_basket():
    items = []
    evidence = {}
    for name, unit in (("bröd", "g"), ("ost", "g"), ("mjölk", "ml")):
        for suffix, amount, price, protein in (
            ("low", 1000, 1, 1),
            ("small", 500, 5, 15),
            ("large", 1000, 9, 15),
        ):
            item = product(name, amount, unit, price, identity=f"{name}-{suffix}")
            items.append(item)
            evidence[(item.store_id, item.product_id)] = facts(
                item,
                nutrition={"protein_g": protein},
                nutrition_unit=unit,
                nutrition_basis=f"per 100 {unit}",
            )
    meal = Recipe(
        name="Sex portioner med bröd, ost och mjölk",
        servings=6,
        ingredients=[
            RecipeIngredient(name=n, quantity=600, unit=u)
            for n, u in (("bröd", "g"), ("ost", "g"), ("mjölk", "ml"))
        ],
        instructions=["Servera tillsammans."],
    )
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=meal)],
        meals=[
            MealSettings(
                meal_type="breakfast", count=1, servings=6, limits=PortionLimits(min_protein_g=44)
            )
        ],
    )
    result = run(prepared(*items), req, facts=evidence)
    assert result.personal.checks["nutrition"][0]["values"]["protein_g"] == 45
    assert result.optimized_basket.total == 27
    assert all(
        i.product_id.endswith("large")
        for store in result.optimized_basket.stores
        for i in store.items
    )
