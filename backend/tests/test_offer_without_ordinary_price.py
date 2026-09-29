"""Explicit SYNTHETIC prices; never evidence of retailer savings."""
from datetime import date

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import OfferMetadata, ProductCandidate
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.basket_optimizer import BasketOptimizer
from app.services.user_pricing import price_candidate_for_context, price_contracts_for_candidate

from backend.tests.test_personal_planning_v2 import prepared, product
from grocery_data.app.domain.promotion_pricing import UserPricingContext

DAY = date(2026, 9, 15)


def offer_product(price=10, cap=3):
    return product(
        "mjölk", 1000, "ml", None, store="lidl", sale_price=price,
        offers=[OfferMetadata(kind="campaign", description="SYNTHETIC bounded offer",
            price=price, max_quantity=cap, valid_from=date(2026, 9, 14),
            valid_to=date(2026, 9, 20), price_contract_id="synthetic-week38-product-v1")],
    )


def candidate(p=None, day=DAY):
    return price_candidate_for_context(ProductCandidate.from_product(p or offer_product(), 1),
        UserPricingContext(), on_date=day)


def need(quantity=1200, name="mjölk"):
    return NormalizedIngredient(canonical_name=name, required_quantity=quantity, unit="ml")


def test_no_ordinary_contract_and_whole_packages_survive_presentation():
    p = offer_product()
    assert p.price is None
    c = candidate(p)
    assert all(str(x.mechanism) != "regular" for x in price_contracts_for_candidate(c))
    item = BasketCalculator().calculate_item(need(), c)
    assert (item.packages_needed, item.total_price) == (2, 20)
    assert item.regular_unit_price is None and item.regular_total_price is None
    assert not item.ordinary_price_known
    assert item.purchase_date == DAY
    assert item.applied_offer.max_quantity == 3
    assert item.model_dump(mode="json")["regular_unit_price"] is None
    assert BasketAuditor(pantry_items=frozenset()).audit([need()], [item]).passed


@pytest.mark.parametrize("day", [date(2026, 9, 13), date(2026, 9, 21)])
def test_before_and_after_campaign_have_no_price(day):
    with pytest.raises(ValueError, match="active eligible"):
        candidate(day=day)


def test_checkout_uses_explicit_purchase_day_not_wall_clock():
    c = candidate()
    assert BasketCalculator().calculate_item(need(), c).total_price == 20
    with pytest.raises(ValueError, match="complete purchase"):
        BasketCalculator().calculate_item(need(), c.model_copy(update={"purchase_date": date(2027, 1, 1)}))


def test_combined_requirements_cannot_get_regular_remainder():
    with pytest.raises(ValueError, match="complete purchase"):
        BasketCalculator().calculate_item(need(3001), candidate())


@pytest.mark.parametrize("offer_price,expected_store,expected_total", [(10, "lidl", 20), (30, "coop", 40)])
def test_optimizer_positive_and_no_improvement(offer_price, expected_store, expected_total):
    p = offer_product(offer_price)
    ordinary = product("mjölk", 1000, "ml", 20)
    catalog = prepared(p, ordinary)
    rows = {"mjölk": [candidate(p), ProductCandidate.from_product(ordinary, 1)]}
    result = BasketOptimizer().optimize([need()], rows, catalog.stores, max_stores=2)
    assert result.total == expected_total
    assert result.stores[0].store_id == expected_store


def test_cap_is_shared_across_distinct_recipe_lines_and_alternative_remains():
    p = offer_product(cap=3)
    ordinary = product("mjölk", 1000, "ml", 20)
    catalog = prepared(p, ordinary)
    # Two recipe aliases deliberately retain separate lines, same product ID.
    a, b = need(1500, "mjölk"), need(1500, "mjölk till sås")
    rows = {n.canonical_name: [candidate(p), ProductCandidate.from_product(ordinary, 1)] for n in (a,b)}
    result = BasketOptimizer().optimize([a,b], rows, catalog.stores, max_stores=2)
    bought = sum(i.packages_needed for s in result.stores for i in s.items if i.store_id == "lidl")
    assert bought <= 3
    assert result.total == 60
    assert len(result.stores) == 2
    one = BasketOptimizer().optimize([a,b], rows, catalog.stores, max_stores=1)
    assert one.total == 80 and one.stores[0].store_id == "coop"


def test_personal_planner_two_recipe_slots_aggregate_offer_cap():
    from app.models.personal import MealSettings, MealSlot
    from app.models.recipe import RecipeIngredient

    from backend.tests.test_personal_planning_v2 import recipe, request, run

    p = offer_product(cap=3)
    # Separate historical SYNTHETIC fixture for the existing frozen planner clock.
    p = p.model_copy(update={"offers": [p.offers[0].model_copy(update={"valid_from": date(2026, 9, 9)})]})
    catalog = prepared(p, product("mjölk", 1000, "ml", 20))
    slots = [MealSlot(id=f"dinner-{i}", day=i, meal_type="dinner",
                     recipe=recipe(name=f"SYNTHETIC milk recipe {i}",
                         ingredients=[RecipeIngredient(name="mjölk", quantity=1800, unit="ml")]))
             for i in (1, 2)]
    result = run(catalog, request(slots=slots, meals=[MealSettings(meal_type="dinner", count=2, servings=1)]))
    assert result.portions == 2
    assert len(result.personal.slots) == 2
    assert sum(i.packages_needed for s in result.optimized_basket.stores for i in s.items if s.store_id == "lidl") <= 3
    assert result.optimized_basket.total == 80
    assert result.optimized_basket.stores[0].store_id == "coop"


def test_own_normalization_keeps_missing_ordinary_price():
    from app.providers.own import OwnGroceryPriceProvider

    from backend.tests.test_own_provider import _fixed_product

    provider = OwnGroceryPriceProvider("https://synthetic.invalid")
    raw = _fixed_product(regular_price=None, coverage="offers_only", promotions=[{
        "kind": "campaign", "description": "SYNTHETIC source contract", "price": 18.9,
        "valid_from": "2026-09-14", "valid_to": "2026-09-20", "max_quantity": 3,
    }])
    result = provider._product_from_row(raw)
    assert result is not None and result.price is None
    assert result.sale_price == 18.9
    assert result.offers[0].max_quantity == 3


def test_auditor_rejects_separately_valid_lines_exceeding_combined_cap():
    item = BasketCalculator().calculate_item(need(1800), candidate())
    duplicate = item.model_copy(update={"ingredient": "mjölk till sås"})
    audit = BasketAuditor(pantry_items=frozenset()).audit(
        [need(1800), need(1800, "mjölk till sås")], [item, duplicate])
    assert not audit.passed


def test_optional_offer_does_not_force_cartesian_search_of_unrelated_products():
    from app.models.store import Store

    stores = [Store(store_id=f"store-{i}", name=f"Store {i}", chain="synthetic", city="Lund") for i in range(5)]
    stores.append(Store(store_id="lidl", name="Lidl synthetic", chain="lidl", city="Lund"))
    needs = [need(1, "mjölk" if i == 0 else f"synthetic-{i}") for i in range(12)]
    rows = {n.canonical_name: [ProductCandidate.from_product(product(n.canonical_name, 1000, "ml", 20, store=s.store_id), 1)
                             for s in stores[:-1]] for n in needs}
    rows["mjölk"].append(candidate())
    # More than 5**12 product combinations; only bounded store subsets matter.
    result = BasketOptimizer().optimize(needs, rows, stores, max_stores=2)
    assert result.total == 230
    assert len(result.stores) == 2


@pytest.mark.parametrize("start,end,offer_protein,expected_store,expected_cost", [
    (date(2026,9,11), date(2026,9,12), 3.4, "coop", 20),  # purchase before campaign
    (date(2026,9,9), date(2026,9,11), 3.4, "lidl", 10),   # purchase during campaign
    (date(2026,9,8), date(2026,9,9), 3.4, "coop", 20),    # purchase after campaign
    (date(2026,9,9), date(2026,9,11), 1.0, "coop", 20),   # active, nutrition-ineligible offer
])
def test_optional_offer_validity_cannot_block_personal_planner(
    start, end, offer_protein, expected_store, expected_cost,
):
    from app.models.personal import MealSettings, MealSlot, PortionLimits
    from app.models.recipe import RecipeIngredient
    from app.services.personal_policy import ProductFacts

    from backend.tests.test_personal_planning_v2 import NOW, recipe, request, run

    # Only SYNTHETIC campaign dates vary around the existing frozen Sep10 clock.
    # Neither observations nor clock are rewritten to make a price look fresh.
    assert NOW.date() == date(2026,9,10)
    offer = offer_product()
    offer = offer.model_copy(update={"offers": [offer.offers[0].model_copy(
        update={"valid_from": start, "valid_to": end})]})
    ordinary = product("mjölk", 1000, "ml", 20)
    catalog = prepared(offer, ordinary)
    facts = {(p.store_id,p.product_id): ProductFacts(
        source="synthetic-test-declaration", source_product_id=p.product_id,
        source_snapshot_id="v2-frozen", nutrition_unit="ml", nutrition_basis="per_100_as_sold",
        nutrition={"protein_g": offer_protein if p.store_id == "lidl" else 3.4},
    ) for p in (offer, ordinary)}
    slot = MealSlot(id="b", day=1, meal_type="breakfast", recipe=recipe(
        name="SYNTHETIC milk breakfast", ingredients=[RecipeIngredient(name="mjölk", quantity=200, unit="ml")]))
    req = request(slots=[slot], meals=[MealSettings(meal_type="breakfast", count=1, servings=1,
                  limits=PortionLimits(min_protein_g=6))])
    result = run(catalog, req, facts=facts)
    assert result.optimized_basket.total == expected_cost
    assert result.optimized_basket.stores[0].store_id == expected_store
    assert result.personal.checks["nutrition"][0]["values"]["protein_g"] >= 6
    assert BasketAuditor(pantry_items=frozenset()).audit(result.ingredients, result.optimized_basket).passed


def test_optional_search_budget_preserves_verified_base_and_warns(monkeypatch):
    import app.services.basket_optimizer as module
    monkeypatch.setattr(module, "_MAX_GROUP_COMBINATIONS", 1)
    offer = candidate().model_copy(update={"coverage": "offers_only"})
    ordinary = product("mjölk", 1000, "ml", 20)
    catalog = prepared(offer_product(), ordinary)
    needs = [need(), need(name="milk sauce")]
    rows = {n.canonical_name: [offer, ProductCandidate.from_product(ordinary, 1)] for n in needs}
    basket = BasketOptimizer().optimize(needs, rows, catalog.stores, max_stores=2)
    assert basket.total == 80 and basket.stores[0].store_id == "coop"
    assert basket.max_stores == 2 and len(basket.stores) == 1
    assert basket.savings_vs_single_store is None
    assert basket.verification_warnings
    assert all(i.ordinary_price_known for s in basket.stores for i in s.items)
    assert BasketAuditor(pantry_items=frozenset()).audit(needs, basket).passed


def test_search_budget_does_not_fabricate_missing_base_or_relax_group_gate(monkeypatch):
    import app.services.basket_optimizer as module
    from app.services.basket_calculator import GroupPricingError
    from app.services.basket_optimizer import IncompleteBasketError
    monkeypatch.setattr(module, "_MAX_GROUP_COMBINATIONS", 0)
    offer = candidate().model_copy(update={"coverage": "offers_only"})
    catalog = prepared(offer_product())
    needs = [need(), need(name="milk sauce")]
    with pytest.raises(IncompleteBasketError):
        BasketOptimizer().optimize(needs, {n.canonical_name: [offer] for n in needs}, catalog.stores, max_stores=2)
    # A non-optional contract still fails closed at the exact-search limit.
    with pytest.raises(GroupPricingError, match="stor"):
        BasketOptimizer().optimize(needs, {n.canonical_name: [candidate()] for n in needs}, catalog.stores, max_stores=2)
