"""Actual newly qualified Lidl food offers, no prices invented by tests."""
import json
from datetime import date
from pathlib import Path

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def products():
    return [Product.model_validate(p) for p in json.loads((Path(__file__).parent/'fixtures/lidl-new-purchases-20260924.json').read_bytes())['products']]

def test_new_foods_checkout_audit_no_unknown_base_price():
    expected={'Mango':11.9,'Kycklingvingar':49.9,'Madalenas med apelsin':27.9}
    assert len(products())==6
    for p in products():
        assert p.price is None
        need=NormalizedIngredient(canonical_name=p.name.casefold(),required_quantity=p.package_quantity,unit=p.package_unit)
        match=ProductMatcher().match(need,[p]);assert len(match)==1
        for member in (False,True):
            ctx=UserPricingContext.from_chain_flags({'lidl':member})
            candidate=price_candidate_for_context(match[0],ctx,on_date=date(2026,9,24))
            bought=BasketCalculator().calculate_item(need,candidate)
            assert bought.total_price==expected[p.name]
            assert BasketAuditor(pantry_items=frozenset()).audit([need],[bought],user_pricing_context=ctx).passed
        for day in (date(2026,9,20),date(2026,9,28)):
            with pytest.raises(ValueError):price_candidate_for_context(match[0],ctx,on_date=day)

def test_exact_new_purchase_does_not_authorize_wrong_recipe_or_grams_per_piece():
    for p in products():
        if p.name=='Mango':
            need=NormalizedIngredient(canonical_name='mango',required_quantity=100,unit='g')
            assert not ProductMatcher().match(need,[p])
        if p.name=='Kycklingvingar':
            need=NormalizedIngredient(canonical_name='kyckling',required_quantity=500,unit='g')
            assert not ProductMatcher().match(need,[p])
