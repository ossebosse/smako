"""Explicit deposit contract arithmetic; fixtures are not real product evidence."""
from datetime import date
from decimal import Decimal

import pytest
from app.models.product import OfferMetadata, ProductCandidate
from app.services.basket_calculator import resolve_fixed_checkout_price
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import DepositContract, UserPricingContext


def offer(inclusion='additional'):
    return OfferMetadata(kind='multipack',price=30,description='Fixture: two six-packs',required_packages=2,
        max_quantity=1,valid_from=date(2026,9,19),valid_to=date(2026,9,20),
        deposit=DepositContract(gtin='7350086160659',per_container=Decimal(2),containers_per_package=6,
                                inclusion=inclusion,evidence='Fixture explicit 2 kr/container, 6/package'))


@pytest.mark.parametrize('inclusion,total',[('additional',54),('included',30)])
def test_known_deposit_counts_all_containers_exactly_once(inclusion,total):
    item=offer(inclusion)
    result=resolve_fixed_checkout_price(package_count=2,base_unit_price=15,regular_unit_price=None,
        offers=[item],on_date=date(2026,9,19))
    assert result[0]==total and item.price==30
    with pytest.raises(ValueError,match='complete purchase'):
        resolve_fixed_checkout_price(package_count=1,base_unit_price=15,regular_unit_price=None,offers=[item],on_date=date(2026,9,19))
    with pytest.raises(ValueError,match='complete purchase'):
        resolve_fixed_checkout_price(package_count=4,base_unit_price=15,regular_unit_price=None,offers=[item],on_date=date(2026,9,19))


def test_unknown_deposit_or_cross_variant_cannot_price():
    with pytest.raises(ValueError):DepositContract(gtin='7350086160659',per_container=None,containers_per_package=6,inclusion='additional',evidence='unknown')
    with pytest.raises(ValueError):DepositContract(gtin='7350086160659',per_container=2,containers_per_package=6,inclusion='unknown',evidence='unknown')
    from backend.tests.test_ica_conditional_checkout import real_product
    p=real_product();c=ProductCandidate.from_product(p.model_copy(update={'offers':[offer()]}),0)
    with pytest.raises(ValueError,match='another product variant'):
        price_candidate_for_context(c,UserPricingContext(),on_date=date(2026,9,19))


def test_deposit_not_silently_assigned_to_unverified_ordinary_remainder():
    with pytest.raises(ValueError,match='base deposit scope unknown'):
        resolve_fixed_checkout_price(package_count=3,base_unit_price=20,regular_unit_price=20,offers=[offer()],on_date=date(2026,9,19))


@pytest.mark.asyncio
async def test_review_sourceoffer_collector_own_preserves_deposit_contract(tmp_path, monkeypatch):
    # Historical fixture, explicit clock. Never shift the source observation or
    # campaign dates merely because the calendar advanced past this regression.
    import importlib
    from datetime import UTC, datetime

    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            instant = datetime(2026,9,20,8,tzinfo=UTC)
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    for module in ["app.models.product", "app.providers.own", "grocery_data.app.api.common", "grocery_data.app.api.catalog",
                   "grocery_data.app.services.freshness", "grocery_data.app.domain.promotion_pricing",
                   "grocery_data.app.services.fixed_checkout_price"]:
        monkeypatch.setattr(importlib.import_module(module), "datetime", ReplayClock)
    import httpx
    from app.providers.own import OwnGroceryPriceProvider
    from app.services.production_price_universe_build import _read_only_app

    from grocery_data.app.connectors.ica import IcaConnector
    from grocery_data.app.domain import GeographicArea, SourceStore
    from grocery_data.app.services.collector import GroceryCollector
    from grocery_data.app.services.ica_area_offers import RowApprovedOfferConnector
    from grocery_data.app.services.ica_flyer_review import review_key, reviewed_flyer_batch
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )
    from grocery_data.tests.test_ica_flyer_review import fixture

    evidence,review=fixture();terms=review['terms']
    terms.update(gtin='7350086160659',name='Fixture drink',package='250 ml',brand='Fixture',
        eligibility='public',valid_from='2026-09-19',valid_to='2026-09-20',
        deposit_status='known',deposit_contract=offer().deposit.model_dump(mode='json'))
    evidence['observed_at']='2026-09-19T16:00:00+00:00'
    review.update(evidence_sha256=review_key(evidence),terms_sha256=review_key(terms))
    raw=reviewed_flyer_batch(evidence,review,account_id='fixture-store')
    store=SourceStore(chain='ica',external_id='fixture-store',name='Fixture',city='Lund',
        address='Fixture 1',postal_code='22350',coverage='offers_only',raw_reference='fixture:official',
        source_fields={'official_store_url':'https://example.test/store','offers_url':'https://example.test/offers'})
    engine=create_database_engine('sqlite:///'+str(tmp_path/'test.sqlite'));create_schema(engine)
    sessions=create_session_factory(engine);connector=IcaConnector()
    collector=GroceryCollector(sessions,FilesystemRawSnapshotStore(tmp_path/'raw'))
    result=await collector.collect_area(RowApprovedOfferConnector(connector,store,raw,raw),
        GeographicArea(city='Lund'),scope_key='fixture:ica:fixture-store:offer-rows')
    assert result.promoted
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_read_only_app(sessions)),base_url='http://test') as client:
        own=OwnGroceryPriceProvider('http://test',client=client,include_offers_only=True,include_conditional_offer_products=True)
        stores=await own.find_offer_stores('22350')
        products=await own.get_offers(stores[0].store_id)
        assert len(products)==1 and products[0].price is None
        assert products[0].offers[0].deposit==offer().deposit
        c=price_candidate_for_context(ProductCandidate.from_product(products[0],0),UserPricingContext(),on_date=date(2026,9,19))
        total,*_=resolve_fixed_checkout_price(package_count=2,base_unit_price=c.effective_price,
            regular_unit_price=c.price,offers=c.offers,on_date=date(2026,9,19))
        assert total==54
    await connector.aclose();engine.dispose()


def test_deposit_membership_dates_and_aggregate_alias_cap_use_existing_audit():
    from app.models.ingredient import NormalizedIngredient
    from app.services.basket_auditor import BasketAuditor
    from app.services.basket_calculator import BasketCalculator

    member=OfferMetadata.model_validate({**offer().model_dump(),'eligibility':'member','membership_program':'ICA_STAMMIS','member_program':'ica medlem'})
    from backend.tests.test_personal_planning_v2 import product
    p=product('synthetic drink',250,'ml',None,store='ica',gtin=member.deposit.gtin,sale_price=15,offers=[member])
    context=UserPricingContext.from_chain_flags({'ica':True})
    raw=ProductCandidate.from_product(p,1)
    with pytest.raises(ValueError):price_candidate_for_context(raw,UserPricingContext(),on_date=date(2026,9,19))
    for day in [date(2026,9,18),date(2026,9,21)]:
        with pytest.raises(ValueError):price_candidate_for_context(raw,context,on_date=day)
    candidate=price_candidate_for_context(raw,context,on_date=date(2026,9,19))
    need=NormalizedIngredient(canonical_name=p.canonical_name,required_quantity=p.package_quantity*2,unit=p.package_unit)
    item=BasketCalculator().calculate_item(need,candidate)
    assert item.total_price==54
    auditor=BasketAuditor(pantry_items=frozenset())
    assert auditor.audit([need],[item],user_pricing_context=context).passed
    alias=need.model_copy(update={'canonical_name':'fixture alias'})
    duplicate=item.model_copy(update={'ingredient':'fixture alias'})
    assert not auditor.audit([need,alias],[item,duplicate],user_pricing_context=context).passed


@pytest.mark.parametrize('inclusion,total',[('additional',54),('included',30)])
def test_public_basket_separates_known_deposit_from_merchandise(inclusion,total):
    from app.models.ingredient import NormalizedIngredient
    from app.services.basket_calculator import BasketCalculator

    from backend.tests.test_personal_planning_v2 import product
    p=product('läsk',6000,'ml',None,effective_price=15,sale_price=None,gtin='7350086160659',offers=[offer(inclusion)])
    candidate=price_candidate_for_context(ProductCandidate.from_product(p,1),UserPricingContext(),on_date=date(2026,9,19))
    item=BasketCalculator().calculate_item(NormalizedIngredient(canonical_name='läsk',required_quantity=12000,unit='ml'),candidate)
    assert item.total_price==total and item.deposit_total==24 and item.merchandise_total==total-24
