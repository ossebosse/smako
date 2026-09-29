"""Retained public document prices; real matcher and checkout contracts."""
import json
from datetime import date
from pathlib import Path

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate, SaleModel
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def products():
    return [Product.model_validate(p) for p in json.loads((Path(__file__).parent /
        'fixtures/willys-flyers-20260923.json').read_bytes())['products']]


def item(product, packages=1, member=True, day=date(2026, 9, 23)):
    need = NormalizedIngredient(
        canonical_name='chicken_breast' if product.name == 'Kycklingbröstfilé Sverige' else product.name.casefold(),
        required_quantity=product.package_quantity * packages, unit=product.package_unit)
    matches = ProductMatcher().match(need, [product])
    assert len(matches) == 1
    candidate = price_candidate_for_context(matches[0], UserPricingContext.from_chain_flags({'willys': member}), on_date=day)
    return need, BasketCalculator().calculate_item(need, candidate)


def test_verified_prices_membership_and_audit_without_invented_ordinary_price():
    for p in products():
        assert p.gtin is p.price is None
        need, bought = item(p, p.offers[0].required_packages)
        assert bought.total_price == p.offers[0].price
        assert BasketAuditor(pantry_items=frozenset()).audit([need], [bought],
            user_pricing_context=UserPricingContext.from_chain_flags({'willys': True})).passed
        with pytest.raises(ValueError):
            item(p, member=False)
        with pytest.raises(ValueError):
            item(p, day=date(2026, 9, 28))


def test_shared_household_cap_does_not_multiply_across_stores_and_recipes():
    a, b = [p for p in products() if p.name == 'Pågenlimpan']
    assert a.store_id != b.store_id
    assert a.offers[0].price_contract_id == b.offers[0].price_contract_id
    accepted = [item(a, 2)[1], item(b)[1]]
    assert sum(i.total_price for i in BasketCalculator.quote_group_basket(accepted)) == pytest.approx(74.7)
    with pytest.raises(GroupPricingError, match='household'):
        BasketCalculator.quote_group_basket([*accepted, item(b)[1]])


@pytest.mark.parametrize('sale_model,unit,quantity,price', [
    (SaleModel.SOLD_BY_WEIGHT, 'g', 400, 100),
    (SaleModel.SOLD_BY_PIECE, 'st', 3, 10),
])
def test_mixed_base_and_offers_only_basket_preserves_non_package_quotes(sale_model, unit, quantity, price):
    p = next(p for p in products() if p.name == 'Pågenlimpan')
    offered = item(p)[1]
    candidate = ProductCandidate(product_id='baseline', product_name='Baseline', canonical_name='baseline',
        store_id='base-store', store_name='Base', price=price, effective_price=price,
        sale_model=sale_model, sale_price=price, sale_unit='kg' if unit == 'g' else 'st',
        comparison_price=price if unit == 'g' else None, comparison_unit='kg' if unit == 'g' else None,
        piece_price=price if unit == 'st' else None, variable_weight=unit == 'g', match_score=1)
    baseline = BasketCalculator().calculate_item(
        NormalizedIngredient(canonical_name='baseline', required_quantity=quantity, unit=unit), candidate)
    quoted = BasketCalculator.quote_group_basket([baseline, offered])
    assert quoted[0] == baseline
    assert quoted[0].total_price == (40 if unit == 'g' else 30)
    assert quoted[1].total_price == 24.9


def test_multibuy_odd_residual_cannot_use_unknown_ordinary_price():
    p = next(p for p in products() if p.name == 'Pizzadeg' and p.offers[0].required_packages == 2)
    assert item(p, 2)[1].total_price == 25
    with pytest.raises(ValueError):
        item(p, 3)
