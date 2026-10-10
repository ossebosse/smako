"""Count limits derive from ordering evidence, never a kg-price quotient."""
import json
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest, Product
from app.models.personal import ExtraNeed, PersonalPlanning
from app.models.product import ProductCandidate
from app.services.personal_planner import PersonalPlanner
from app.services.user_pricing import price_candidate_for_context

from backend.tests.test_comparability_sales_units import NOW, ROWS, prepare
from backend.tests.test_product_search import search
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain.promotion_pricing import UserPricingContext

PATH=Path(__file__).parents[2]/'grocery_data/tests/fixtures/comparability-20261010/product-0eeef76b41194e05bb3d14d2722c453d.json'

def product():
    row=json.loads(PATH.read_bytes())['record']
    parsed=WillysParser._offers(row,raw_reference='raw:retained-count-limit')[0]
    assert parsed.source_payload['limit_unit']=='purchase_packages'
    p=Product.model_validate(ROWS[-1])
    # Only the parser-proven fields are enriched; historical prices/times intact.
    offer=p.offers[0].model_copy(update={k:parsed.source_payload[k] for k in ('limit_unit','price_basis_unit','price_contract_id')})
    return p.model_copy(update={'offers':[offer]})

@pytest.mark.parametrize('grams,total,packages',[(400,69.5,1),(1000,139,2),(1500,208.5,3),(2000,293,4)])
def test_actual_capped_weight_full_basket_and_audit(grams,total,packages):
    p=product();prepared=prepare(p)
    req=PlanRequest(recipes=0,purchase_planning_mode='estimated',memberships=['WILLYS_PLUS'],personal=PersonalPlanning(extras=[ExtraNeed(query=p.name,kind='exact',product_key=search(prepared,'Fläskfilé',now=NOW)['results'][0]['product_key'],quantity=grams,unit='g',confirmed=True)]))
    result=PersonalPlanner(req,Settings(price_provider='mock'),prepared,{'id':'cap-test','revision':0,'items':[],'reservations':{},'events':{}},now=NOW).create()
    assert result.optimized_basket.total==total
    item=result.optimized_basket.stores[0].items[0]
    assert item.packages_needed==packages and item.membership_required
    assert item.applied_offer.price==139 and item.applied_offer.price_basis_unit=='kg'
    assert result.personal.checks['checkout_audit']['passed']

@pytest.mark.parametrize('changed',[{'productBasketType':{'code':'KG'}},{'averageWeight':None}])
def test_count_limit_requires_ordering_evidence(changed):
    row=json.loads(PATH.read_bytes())['record']|changed
    assert not WillysParser._offers(row)[0].source_payload.get('limit_unit')

def test_member_and_date_still_apply():
    from datetime import date
    p=product()
    for context,day in [(UserPricingContext(),NOW.date()),(UserPricingContext.from_chain_flags({'willys':True}),date(2026,10,12))]:
        c=price_candidate_for_context(ProductCandidate.from_product(p,1),context,on_date=day,planning_mode='estimated')
        assert c.sale_price==169 and not c.offers

def test_shared_cap_and_independent_audit_reject_tampered_total():
    from app.models.ingredient import NormalizedIngredient
    from app.services.basket_auditor import BasketAuditor
    from app.services.basket_calculator import BasketCalculator, GroupPricingError
    p=product();ctx=UserPricingContext.from_chain_flags({'willys':True})
    need=NormalizedIngredient(canonical_name=p.name,required_quantity=1000,unit='g')
    c=price_candidate_for_context(ProductCandidate.from_product(p,1),ctx,on_date=NOW.date(),planning_mode='estimated')
    item=BasketCalculator().calculate_item(need,c)
    bad=item.model_copy(update={'total_price':1})
    assert not BasketAuditor(pantry_items=[]).audit([need],[bad],user_pricing_context=ctx).passed
    alias=item.model_copy(update={'store_id':'other-store','ingredient':'other-need'})
    with pytest.raises(GroupPricingError):BasketCalculator.quote_group_basket([item,alias])
    assert not BasketAuditor(pantry_items=[]).audit([need],[item,alias],user_pricing_context=ctx).passed


def test_search_rate_is_member_labelled():
    row=search(prepare(product()),'fläskfilé',now=NOW,memberships=['WILLYS_PLUS'])['results'][0]
    assert row['display_price']==139 and row['display_price_unit']=='kg'
    assert row['prices'][0]['membership_required']
