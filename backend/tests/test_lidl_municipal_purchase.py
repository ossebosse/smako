"""Real 23 September offers; explicit purchase day and adverse scope changes."""
import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.lidl_product_facts import declaration_matches_product, reviewed_facts
from app.services.personal_planner import PersonalPlanner
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def products():
    return [Product.model_validate(p) for p in json.loads((Path(__file__).parent /
        "fixtures/lidl-municipality-20260923.json").read_bytes())["products"]]


def item(product, packages=1, member=True):
    need = NormalizedIngredient(canonical_name=product.name.casefold(),
        required_quantity=product.package_quantity * packages, unit="g")
    matches = ProductMatcher().match(need, [product])
    assert len(matches) == 1
    candidate = price_candidate_for_context(matches[0], UserPricingContext.from_chain_flags({"lidl": member}),
                                            on_date=date(2026, 9, 23))
    return need, BasketCalculator().calculate_item(need, candidate)


def test_member_price_unknown_ordinary_checkout_and_audit():
    context = UserPricingContext.from_chain_flags({"lidl": True})
    for p in products():
        assert p.price is None
        if p.name not in {"Lingongrova", "Hamburgare"}:
            continue
        need, bought = item(p)
        assert bought.total_price == (17.9 if p.name == "Lingongrova" else 159)
        assert BasketAuditor(pantry_items=frozenset()).audit([need], [bought], user_pricing_context=context).passed
        with pytest.raises(ValueError):
            item(p, member=False)


def test_household_cap_across_recipes_and_distinct_stores():
    a, b = [p for p in products() if p.name == "Hamburgare"]
    assert a.store_id != b.store_id
    assert a.offers[0].price_contract_id == b.offers[0].price_contract_id
    accepted = [item(a)[1], item(b)[1]]
    assert sum(i.total_price for i in BasketCalculator.quote_group_basket(accepted)) == 318
    rejected = [item(a, 2)[1], item(b)[1]]
    with pytest.raises(GroupPricingError, match="household"):
        BasketCalculator.quote_group_basket(rejected)
    need = NormalizedIngredient(canonical_name="hamburgare", required_quantity=5400, unit="g")
    assert not BasketAuditor(pantry_items=frozenset()).audit([need], rejected,
        user_pricing_context=UserPricingContext.from_chain_flags({"lidl": True})).passed


def test_product_declaration_and_nutrition_qualification_are_separate_from_price():
    rows = products()
    facts = reviewed_facts(rows)
    assert len(facts) == 2
    for p in rows:
        fact = facts.get((p.store_id, p.product_id))
        planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=False), source_facts=lambda _, retained=fact: retained)
        result = PersonalPlanner._nutrition_evidence(planner, p, p.name.casefold(), "g", {"kcal", "protein_g"}, None)
        if p.name == "Lingongrova":
            assert result.nutrition["protein_g"] == 8.8 and result.nutrition["kcal"] == 266
            assert declaration_matches_product(p, fact)
            assert not declaration_matches_product(p.model_copy(update={"gtin": "0000000000000"}), fact)
            assert not declaration_matches_product(p.model_copy(update={"package_quantity": 600}), fact)
        else:
            assert result is None


def test_processed_products_never_become_raw_recipe_ingredients():
    for product in products():
        if product.name == "Hamburgare":
            assert not ProductMatcher().match(NormalizedIngredient(canonical_name="nötfärs", required_quantity=500, unit="g"), [product])
        if product.name.startswith("Majssnacks"):
            assert not ProductMatcher().match(NormalizedIngredient(canonical_name="ost", required_quantity=100, unit="g"), [product])


def test_expired_campaign_cannot_fall_back_to_unknown_ordinary_price():
    for product in products():
        if product.name not in {"Lingongrova", "Hamburgare"}:
            continue
        need = NormalizedIngredient(canonical_name=product.name.casefold(), required_quantity=100, unit="g")
        candidate = ProductMatcher().match(need, [product])[0]
        with pytest.raises(ValueError):
            price_candidate_for_context(candidate, UserPricingContext.from_chain_flags({"lidl": True}),
                                        on_date=date(2026, 9, 28))
