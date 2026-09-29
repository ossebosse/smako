"""Real two-store offers; explicit fixture purchase day and adversarial deltas."""
import json
from datetime import date
from pathlib import Path

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def products():
    return [Product.model_validate(p) for p in json.loads((Path(__file__).parent /
        'fixtures/coop-municipality-household-20260921.json').read_bytes())]


def item(product, packages):
    need=NormalizedIngredient(canonical_name='nötfärs',required_quantity=packages*500,unit='g')
    matches=ProductMatcher().match(need,[product])
    assert len(matches)==1
    candidate=price_candidate_for_context(matches[0],UserPricingContext.from_chain_flags({'coop':True}),
                                          on_date=date(2026,9,21))
    return BasketCalculator().calculate_item(need,candidate)


def test_real_household_cap_does_not_multiply_by_physical_store():
    a,b=products()
    assert a.source_provenance.provider_store_id != b.source_provenance.provider_store_id
    assert a.offers[0].price_contract_id==b.offers[0].price_contract_id
    valid=[item(a,2),item(b,1)]
    assert sum(p.total_price for p in BasketCalculator.quote_group_basket(valid))==pytest.approx(179.7)
    need=NormalizedIngredient(canonical_name='nötfärs',required_quantity=1500,unit='g')
    audit=BasketAuditor(pantry_items=frozenset())
    context=UserPricingContext.from_chain_flags({'coop':True})
    assert audit.audit([need],valid,user_pricing_context=context).passed
    invalid=[item(a,2),item(b,2)]
    with pytest.raises(GroupPricingError,match='household'):BasketCalculator.quote_group_basket(invalid)
    assert not audit.audit([need.model_copy(update={'required_quantity':2000})],invalid,user_pricing_context=context).passed


def test_shared_limit_never_copies_local_price_or_member_eligibility():
    a,b=products()
    # Adversarial local price; the unmodified source fixture is retained.
    b=b.model_copy(update={'offers':[b.offers[0].model_copy(update={'price':61.9})]})
    result=BasketCalculator.quote_group_basket([item(a,1),item(b,1)])
    assert [i.total_price for i in result]==[59.9,61.9]
    assert result[0].store_id != result[1].store_id
    need=NormalizedIngredient(canonical_name='nötfärs',required_quantity=500,unit='g')
    for p in (a,b):
        match=ProductMatcher().match(need,[p])[0]
        with pytest.raises(ValueError):price_candidate_for_context(match,UserPricingContext(),on_date=date(2026,9,21))


def test_missing_source_campaign_id_quarantines_capped_rows():
    from grocery_data.tests.test_coop_physical_structured import parse
    def remove(root):
        for group in root['structured_offers']['data']['sortingGroups']:
            for row in group['offers']:
                row.pop('eagId',None)
    _,_,evidence=parse(mutate=remove)
    assert any('household_campaign_identity_unverified' in r['blockers'] for r in evidence['decisions'])
