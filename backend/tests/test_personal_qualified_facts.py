"""Frozen independent requirements and exact facts-only reuse regressions."""

from dataclasses import replace

import pytest
from app.models.personal import (
    ExtraNeed,
    MealSettings,
    MealSlot,
    PantryItem,
    PortionLimits,
    TasteProfile,
)
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_source_facts import complete_identity_facts, facts_version
from app.services.recipe_candidate_validator import recipe_id

from backend.tests.test_personal_planning_v2 import (
    key_for,
    prepared,
    product,
    recipe,
    request,
    run,
    state,
)

GTIN = "7310865004703"


def facts(p, **kwargs):
    return ProductFacts(
        source="frozen source",
        source_product_id=p.product_id,
        source_snapshot_id="v2-frozen",
        **kwargs,
    )


def milk_recipe():
    from app.models.recipe import RecipeIngredient

    return recipe(ingredients=[RecipeIngredient(name="mjölk", quantity=200, unit="ml")])


def test_weight_only_needs_no_nutrition_and_eco_needs_neither():
    p = prepared(product("mjölk", 1000, "ml", 20))
    r = milk_recipe()
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=r)],
        meals=[
            MealSettings(
                meal_type="breakfast", count=1, servings=1, limits=PortionLimits(min_weight_g=150)
            )
        ],
    )
    result = run(
        p,
        req,
        facts={},
        cooked_weights={
            recipe_id(r): {
                "source": "synthetic measured edible batch",
                "servings": 1,
                "total_g": 200,
            }
        },
    )
    assert result.personal.checks["nutrition"][0]["values"] == {"weight_g": 200}
    req.personal.meals[0].limits = PortionLimits()
    req.personal.organic_percent = 100
    result = run(p, req, facts={("coop", "mjölk"): facts(p.universe.products[0], organic=True)})
    assert result.personal.checks["organic_cost_percent"] == 100
    assert result.personal.checks["allergy"] == "NOT_REQUESTED"


def test_animal_unknown_is_allowed_only_if_product_itself_verified_organic():
    p = prepared(product("mjölk", 1000, "ml", 20))
    req = request(
        extras=[ExtraNeed(query="mjölk", quantity=100, unit="ml", confirmed=True)],
        organic_animals=True,
    )
    f = facts(p.universe.products[0], organic=True)
    assert run(p, req, facts={("coop", "mjölk"): f}).optimized_basket.total == 20
    with pytest.raises(PolicyConflict):
        run(p, req, facts={("coop", "mjölk"): replace(f, organic=None)})
    req.personal.profile = TasteProfile(allergies=["jordnötter"])
    with pytest.raises(PolicyConflict, match="allergeninformation"):
        run(p, req, facts={("coop", "mjölk"): f})


def test_exact_facts_fill_without_changing_any_price_or_product_fields():
    a = product("mjölk", 1000, "ml", 20, gtin=GTIN)
    b = product("mjölk", 1000, "ml", 11, store="willys", gtin=GTIN)
    p = prepared(a, b)
    snapshots = [x.model_dump_json() for x in p.universe.products]
    f = facts(
        a,
        organic=True,
        nutrition_unit="ml",
        nutrition_basis="per 100 ml as sold",
        nutrition={"protein_g": 3.5},
    )
    result = complete_identity_facts(p, {("coop", "mjölk"): f})
    joined = result[("willys", "mjölk")]
    assert joined.organic and joined.nutrition["protein_g"] == 3.5
    assert joined.field_sources["organic"][0]["source"] == "frozen source"
    assert [x.model_dump_json() for x in p.universe.products] == snapshots
    assert joined.source_product_id == b.product_id and joined.source_snapshot_id == "v2-frozen"
    assert not joined.ingredients_complete and not joined.allergens_checked


@pytest.mark.parametrize(
    "change",
    [
        {"package_quantity": 500, "usable_quantity": 500},
        {"name": "mjölk 3 %"},
        {"gtin": "1234567890123"},
        {"brand": "Other"},
        {"product_form": "prepared"},
    ],
)
def test_variant_package_invalid_gtin_or_brand_cannot_inherit(change):
    a = product("mjölk 1,5 %", 1000, "ml", 20, gtin=GTIN, brand="Brand", product_form="raw")
    b = product(
        "mjölk 1,5 %", 1000, "ml", 11, store="willys", gtin=GTIN, brand="Brand", product_form="raw"
    ).model_copy(update=change)
    result = complete_identity_facts(
        prepared(a, b), {("coop", a.product_id): facts(a, organic=True)}
    )
    assert ("willys", b.product_id) not in result


def test_conflicting_fields_block_only_their_own_claims_and_keep_all_provenance():
    a = product("mjölk", 1000, "ml", 20, gtin=GTIN)
    b = product("mjölk", 1000, "ml", 11, store="willys", gtin=GTIN)
    f = facts(
        a,
        organic=True,
        nutrition_unit="ml",
        nutrition_basis="per 100 ml as sold",
        nutrition={"protein_g": 3.5, "kcal": 45},
    )
    other = replace(f, source="other source", organic=False, nutrition={"protein_g": 4, "kcal": 45})
    result = complete_identity_facts(
        prepared(a, b), {("coop", "mjölk"): f, ("willys", "mjölk"): other}
    )
    for v in result.values():
        assert v.organic is None and v.nutrition == {"kcal": 45}
        assert {"organic", "nutrition.protein_g"} <= set(v.conflicts)
        assert len(v.field_sources["organic"]) == 2


@pytest.mark.parametrize("unit,basis", [("g", "per 100 ml as sold"), ("ml", "per 100 ml prepared")])
def test_nutrition_units_and_preparation_basis_do_not_mix(unit, basis):
    a = product("mjölk", 1000, "ml", 20, gtin=GTIN)
    b = product("mjölk", 1000, "ml", 11, store="willys", gtin=GTIN)
    f = facts(
        a,
        organic=True,
        nutrition_unit="ml",
        nutrition_basis="per 100 ml as sold",
        nutrition={"protein_g": 3.5},
    )
    result = complete_identity_facts(
        prepared(a, b),
        {
            ("coop", "mjölk"): f,
            ("willys", "mjölk"): replace(f, nutrition_unit=unit, nutrition_basis=basis),
        },
    )
    assert all(
        not v.nutrition and v.organic is True and "nutrition_basis" in v.conflicts
        for v in result.values()
    )


def test_nutritionally_qualified_more_expensive_alternative_and_fact_cache_version():
    a = product("mjölk", 1000, "ml", 10)
    b = product("mjölk", 1000, "ml", 20, identity="more-protein")
    p = prepared(a, b)
    f = facts(a, nutrition_unit="ml", nutrition_basis="per_100_as_sold", nutrition={"protein_g": 1})
    evidence = {
        ("coop", "mjölk"): f,
        ("coop", "more-protein"): replace(
            f, source_product_id="more-protein", nutrition={"protein_g": 4}
        ),
    }
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=milk_recipe())],
        meals=[
            MealSettings(
                meal_type="breakfast", count=1, servings=1, limits=PortionLimits(min_protein_g=7)
            )
        ],
    )
    result = run(p, req, facts=evidence)
    assert result.optimized_basket.total == 20
    old = result.model_dump_json()
    changed = {
        **evidence,
        ("coop", "more-protein"): replace(
            evidence[("coop", "more-protein")], nutrition={"protein_g": 4.5}
        ),
    }
    newer = run(p, req, facts=changed)
    assert newer.personal.cache_identity != result.personal.cache_identity
    assert facts_version(changed) != facts_version(evidence)
    assert result.model_dump_json() == old


def test_exact_pantry_and_explicit_extra_share_packages_but_all_nutrition_is_counted():
    a = product("mjölk", 1000, "ml", 20)
    p = prepared(a)
    inventory = state(
        [PantryItem(name="mjölk", quantity=100, unit="ml", product_key=key_for(p, "mjölk"))]
    )
    f = facts(
        a,
        organic=True,
        nutrition_unit="ml",
        nutrition_basis="per_100_as_sold",
        nutrition={"protein_g": 4},
    )
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=milk_recipe())],
        meals=[
            MealSettings(
                meal_type="breakfast", count=1, servings=1, limits=PortionLimits(min_protein_g=7)
            )
        ],
        extras=[ExtraNeed(query="mjölk", quantity=500, unit="ml", confirmed=True)],
        organic_percent=100,
    )
    before = repr(inventory)
    result = run(p, req, inventory, facts={("coop", "mjölk"): f})
    assert result.optimized_basket.total == 20
    assert result.personal.checks["nutrition"][0]["values"]["protein_g"] == 8
    assert sum(a["quantity"] for a in result.personal.allocations) == 100
    assert result.personal.checks["organic_evidence"]["food_cost"] == 20
    assert repr(inventory) == before
    inventory["items"][0]["product_key"] = None
    with pytest.raises(PolicyConflict, match="exakta produkt"):
        run(p, req, inventory, facts={("coop", "mjölk"): f})


def test_no_new_food_purchase_is_explicit_not_one_hundred_percent():
    a = product("mjölk", 1000, "ml", 20)
    p = prepared(a)
    inventory = state([PantryItem(name="mjölk", quantity=1000, unit="ml")])
    req = request(
        extras=[ExtraNeed(query="mjölk", quantity=500, unit="ml", use_pantry=True, confirmed=True)],
        organic_percent=70,
    )
    result = run(p, req, inventory, facts={("coop", "mjölk"): facts(a)})
    assert result.personal.checks["organic_cost_percent"] is None
    assert result.personal.checks["organic_evidence"]["status"] == "NO_NEW_FOOD_PURCHASES"


def test_cooked_method_cannot_assume_raw_macronutrient_retention():
    a = product("mjölk", 1000, "ml", 20)
    r = milk_recipe().model_copy(update={"instructions": ["Koka och häll bort hälften."]})
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=r)],
        meals=[MealSettings(meal_type="breakfast", count=1, limits=PortionLimits(min_protein_g=1))],
    )
    with pytest.raises(PolicyConflict, match="beredningsgrund"):
        run(
            prepared(a),
            req,
            facts={
                ("coop", "mjölk"): facts(
                    a,
                    nutrition_unit="ml",
                    nutrition_basis="per_100_as_sold",
                    nutrition={"protein_g": 4},
                )
            },
        )


def test_nutrition_qualification_precedes_intermediate_meal_beam_pruning():
    from app.config import Settings
    from app.services.personal_planner import PersonalPlanner

    from backend.tests.test_personal_planning_v2 import NOW

    a = product("mjölk", 1000, "ml", 20)
    from app.models import PlanRequest
    from app.models.personal import PersonalPlanning

    req = PlanRequest(
        recipes=0,
        diversity_mode="cheapest",
        max_stores=2,
        personal=PersonalPlanning(
            meals=[
                MealSettings(
                    meal_type="breakfast",
                    count=2,
                    servings=1,
                    limits=PortionLimits(min_protein_g=7),
                )
            ]
        ),
    )
    planner = PersonalPlanner(
        req,
        Settings(price_provider="mock"),
        prepared(a),
        state(),
        now=NOW,
        facts={
            ("coop", "mjölk"): facts(
                a,
                nutrition_unit="ml",
                nutrition_basis="per_100_as_sold",
                nutrition={"protein_g": 4},
            )
        },
    )
    good = milk_recipe().model_copy(update={"name": "Z datatäckt"})
    bad = [good.model_copy(update={"name": f"A billigt {i}", "servings": 2}) for i in range(10)]

    class Generator:
        def generate_for_meal_type(self, *args, **kwargs):
            return [*bad, good]

    planner.service.candidate_generator = Generator()
    result = planner.create()
    assert all(r.name == "Z datatäckt" for r in result.recipes)


def test_unrelated_missing_nutrient_does_not_block_selected_protein():
    a = product("mjölk", 1000, "ml", 20)
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=milk_recipe())],
        meals=[MealSettings(meal_type="breakfast", count=1, limits=PortionLimits(min_protein_g=7))],
    )
    f = facts(a, nutrition_unit="ml", nutrition_basis="per_100_as_sold", nutrition={"protein_g": 4})
    assert run(prepared(a), req, facts={("coop", "mjölk"): f}).personal.checks["nutrition"][0][
        "values"
    ] == {"protein_g": 8}


def test_discounted_food_denominator_excludes_nonfood():
    from app.models.product import OfferMetadata

    a = product(
        "mjölk",
        1000,
        "ml",
        20,
        offers=[
            OfferMetadata(
                kind="member",
                description="Member price",
                price=10,
                membership_program="COOP_MEMBER",
            )
        ],
    )
    b = product("bröd", 500, "g", 10)
    n = product("servetter", 50, "st", 100)
    req = request(
        extras=[
            ExtraNeed(query=p.name, quantity=1, unit=p.package_unit, confirmed=True)
            for p in (a, b, n)
        ],
        organic_percent=50,
    )
    req.memberships = {"coop": True}
    result = run(prepared(a, b, n), req, facts={("coop", "mjölk"): facts(a, organic=True)})
    assert result.optimized_basket.total == 120
    assert result.personal.checks["organic_evidence"]["food_cost"] == 20
    assert result.personal.checks["organic_cost_percent"] == 50


def test_other_market_or_source_revision_cannot_supply_facts():
    a = product("mjölk", 1000, "ml", 20, gtin=GTIN)
    b = product("mjölk", 1000, "ml", 11, store="willys", gtin=GTIN)
    f = facts(a, organic=True)
    for wrong in (
        replace(f, source_snapshot_id="wrong"),
        replace(f, field_sources={"organic": ({"market": "DE"},)}),
    ):
        result = complete_identity_facts(prepared(a, b), {("coop", "mjölk"): wrong})
        assert ("willys", "mjölk") not in result


def test_unrelated_extra_candidates_cannot_exhaust_nutrition_alternative_search():
    a = product("mjölk", 1000, "ml", 10)
    b = product("mjölk", 1000, "ml", 20, identity="protein")
    extras = [
        product("servetter", 50, "st", 10 + i / 100, identity=f"napkins-{i}") for i in range(270)
    ]
    p = prepared(a, b, *extras)
    f = facts(a, nutrition_unit="ml", nutrition_basis="per_100_as_sold", nutrition={"protein_g": 1})
    req = request(
        slots=[MealSlot(id="b", day=1, meal_type="breakfast", recipe=milk_recipe())],
        meals=[
            MealSettings(
                meal_type="breakfast", count=1, servings=1, limits=PortionLimits(min_protein_g=7)
            )
        ],
        extras=[ExtraNeed(query="servetter", quantity=50, unit="st", confirmed=True)],
    )
    result = run(
        p,
        req,
        facts={
            ("coop", "mjölk"): f,
            ("coop", "protein"): replace(
                f, source_product_id="protein", nutrition={"protein_g": 4}
            ),
        },
    )
    assert result.optimized_basket.total == 30
