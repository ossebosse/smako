"""Real retained Coop data, explicit test clock; never fresh-source acceptance."""
import importlib
from datetime import UTC, date, datetime

import httpx
import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.providers.own import OwnGroceryPriceProvider
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context
from fastapi import FastAPI

from grocery_data.app.api import catalog_router
from grocery_data.app.connectors.coop.connector import CoopRowApprovedOfferConnector
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.tests.test_coop_physical_structured import FIXTURES, source


class ReplayClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = datetime(2026,9,21,8,tzinfo=UTC)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


@pytest.mark.parametrize("account,accepted", [("3839",44),("3815",77)])
async def test_real_own_universe_checkout_and_audit(tmp_path,monkeypatch,account,accepted):
    for name in ["grocery_data.app.api.common", "grocery_data.app.api.catalog", "grocery_data.app.services.freshness",
                 "app.providers.own", "app.models.product", "grocery_data.app.domain.promotion_pricing",
                 "grocery_data.app.services.fixed_checkout_price"]:
        monkeypatch.setattr(importlib.import_module(name),"datetime",ReplayClock)
    store,batch=source(account)
    locator=RawBatch.model_validate_json((FIXTURES/f"{account}-locator.json").read_bytes())
    engine=create_database_engine("sqlite:///:memory:");create_schema(engine)
    factory=create_session_factory(engine)
    collector=GroceryCollector(factory,FilesystemRawSnapshotStore(tmp_path/'raw'))
    connector=CoopRowApprovedOfferConnector(store=store,locator=locator,offers=batch)
    result=await collector.collect_area(connector,GeographicArea(city=store.city),
                                       scope_key=f"{store.city.casefold()}:coop:{account}:offer-rows")
    assert result.promoted and result.metrics.products_parsed==accepted
    assert result.status.value=='broken'  # full snapshot health remains visible
    assert connector.row_acceptance['complete'] is False
    app=FastAPI();app.state.session_factory=factory;app.include_router(catalog_router)
    async with httpx.AsyncClient(base_url='http://isolated.test',transport=httpx.ASGITransport(app=app)) as client:
        own=OwnGroceryPriceProvider('http://isolated.test',client=client,include_offers_only=True,
                                   include_conditional_offer_products=True)
        stores=await own.find_offer_stores(store.postal_code)
        assert len(stores)==1 and stores[0].physical_store_external_id==account
        products=await own.get_offers(stores[0].store_id)
        assert len(products)==accepted
        key=PriceUniverseKey.create(city=store.city,snapshot_ids=[result.snapshot_id],
            source_strategy_version='test-coop-v1',normalizer_version='v3',taxonomy_version='v1')
        universe=PriceUniverseBuilder().build(key,products,built_at=ReplayClock.now(UTC))
        assert len(universe.products)==accepted
        for product in products:
            assert product.price is None and product.conditional_price_signal
            assert product.source_provenance.provider_store_id==account
            assert product.source_provenance.price_context=='physical_store'
            assert product.source_provenance.source_observed_at==batch.documents[0].fetched_at
            assert product.gtin is None
        pasta=next(p for p in universe.products if p.name=='Färsk Pasta Fettuccine')
        need=NormalizedIngredient(canonical_name='pasta',required_quantity=200,unit='g')
        matched=ProductMatcher().match(need,[pasta])
        assert len(matched)==1
        public=UserPricingContext();member=UserPricingContext.from_chain_flags({'coop':True})
        candidate=price_candidate_for_context(matched[0],public,on_date=date(2026,9,21))
        item=BasketCalculator().calculate_item(need,candidate)
        assert item.total_price==15 and item.packages_needed==1
        assert item.regular_total_price is None
        assert BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=public).passed
        mince=next(p for p in products if p.name=='Nötfärs 20%')
        raw=ProductCandidate.from_product(mince,1)
        with pytest.raises(ValueError):price_candidate_for_context(raw,public,on_date=date(2026,9,21))
        for day in [date(2026,9,20),date(2026,9,28)]:
            with pytest.raises(ValueError):price_candidate_for_context(raw,member,on_date=day)
        candidate=price_candidate_for_context(raw,member,on_date=date(2026,9,21))
        need=NormalizedIngredient(canonical_name=mince.canonical_name,required_quantity=1000,unit='g')
        item=BasketCalculator().calculate_item(need,candidate)
        assert item.total_price==119.8
        auditor=BasketAuditor(pantry_items=frozenset())
        assert auditor.audit([need],[item],user_pricing_context=member).passed
        alias=need.model_copy(update={'canonical_name':'test alias'})
        assert not auditor.audit([need,alias],[item,item.model_copy(update={'ingredient':'test alias'})],user_pricing_context=member).passed
        with pytest.raises(ValueError):BasketCalculator().calculate_item(need.model_copy(update={'required_quantity':2000}),candidate)
        flour=next(p for p in products if p.name=='Kärnvetemjöl')
        need=NormalizedIngredient(canonical_name='vetemjöl',required_quantity=4000,unit='g')
        flour_matches=ProductMatcher().match(need,[flour])
        assert len(flour_matches)==1
        candidate=price_candidate_for_context(flour_matches[0],public,on_date=date(2026,9,21))
        item=BasketCalculator().calculate_item(need,candidate)
        assert item.total_price==26 and item.packages_needed==2
        assert item.regular_total_price is None
        assert auditor.audit([need],[item],user_pricing_context=public).passed
        with pytest.raises(ValueError):BasketCalculator().calculate_item(need.model_copy(update={'required_quantity':2000}),candidate)
    engine.dispose()
