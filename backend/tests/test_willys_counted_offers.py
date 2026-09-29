"""Explicit sales units use the existing counted-contract resolver, not a new pricer."""
import json
from datetime import date
from pathlib import Path

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.connectors.willys.flyer_contract import household_contract
from grocery_data.app.domain.promotion_pricing import UserPricingContext


def products():
    return [Product.model_validate(p) for p in json.loads((Path(__file__).parent/'fixtures/willys-counted-offers-20260924.json').read_bytes())['products']]


def purchase(product,n,*,day=date(2026,9,24),matcher=False):
    need=NormalizedIngredient(canonical_name=product.canonical_name,required_quantity=n,unit='st')
    candidate=ProductMatcher().match(need,[product])[0] if matcher else ProductCandidate.from_product(product,1)
    candidate=price_candidate_for_context(candidate,UserPricingContext(),on_date=day)
    item=BasketCalculator().calculate_item(need,candidate)
    audit=BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=UserPricingContext())
    assert audit.totals_reconciled and all(i.cost_reconciled and i.quantity_reconciled for i in audit.items)
    if matcher:assert audit.passed
    if product.name=='Knoppljung':assert not audit.passed  # a price is not recipe-food approval
    return item


def test_explicit_piece_campaign_unknown_regular_matcher_checkout_and_audit():
    p=next(p for p in products() if p.name=='Gurka')
    assert p.price is None and p.package_quantity==p.usable_quantity==1
    assert purchase(p,3,matcher=True).total_price==pytest.approx(29.7)
    with pytest.raises(ValueError):purchase(p,4)
    with pytest.raises(ValueError):purchase(p,1,day=date(2026,9,20))
    with pytest.raises(ValueError):purchase(p,1,day=date(2026,9,28))
    # Count is not a guessed cucumber mass.
    assert p.estimated_piece_weight is None and p.gtin is None


def test_complete_piece_multibuy_has_no_invented_residual_price():
    p=next(p for p in products() if p.name=='Knoppljung')
    assert p.price is p.sale_price is p.piece_price is None
    bought=purchase(p,3)
    assert bought.total_price==79 and bought.sale_price is bought.piece_price is None
    assert purchase(p,6).total_price==158
    for quantity in (1,2,4):
        with pytest.raises(ValueError):purchase(p,quantity)


def test_piece_household_limit_is_shared_over_recipes_and_stores():
    p=next(p for p in products() if p.name=='Gurka')
    other=p.model_copy(update={'store_id':'another-verified-store'})
    bought=[purchase(p,2),purchase(other,1)]
    assert sum(i.total_price for i in BasketCalculator.quote_group_basket(bought))==pytest.approx(29.7)
    with pytest.raises(GroupPricingError,match='household'):
        BasketCalculator.quote_group_basket([*bought,purchase(other,1)])


def test_unverified_piece_cannot_use_counted_campaign_exception():
    p=next(p for p in products() if p.name=='Gurka').model_dump()
    p['source_provenance']['retailer_id_namespace']=None
    with pytest.raises(ValueError):Product.model_validate(p)


def test_household_identity_survives_auto_manual_case_and_number_representation():
    a={'title': 'PÅGENLIMPAN','brand': 'Pågen','package_quantity': 900,'package_unit': 'g','valid_from': '2026-09-21','valid_to': '2026-09-27'}
    b={**a,'brand':'PÅGEN','package_quantity':900.0}
    assert household_contract(a)==household_contract(b)
    assert household_contract(a)!=household_contract({**b,'valid_to':'2026-09-28'})
