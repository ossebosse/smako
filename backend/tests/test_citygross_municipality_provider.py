"""Actual retained City Gross rows; explicit replay clock and injected bad IDs."""
import importlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from app.models import Store
from app.providers.citygross_municipality import CityGrossMunicipalityProvider
from app.providers.own import OwnGroceryPriceProvider
from app.services.price_universe import PriceUniverse, PriceUniverseBuilder, PriceUniverseKey
from fastapi import FastAPI

from grocery_data.app.api import catalog_router
from grocery_data.app.connectors.citygross.municipality_inventory import approved_citygross_stores
from grocery_data.app.connectors.citygross.row_approved_offers import (
    CityGrossRowApprovedOfferConnector,
)
from grocery_data.app.domain import GeographicArea, RawBatch, RawFetch
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.scripts.collect_citygross_municipality import MunicipalCityGrossConnector
from grocery_data.tests.test_citygross_full_acceptance import (
    FullFixtureCityGrossClient,
    _exact_completion,
)
from grocery_data.tests.test_citygross_municipality import RAW, inventory


class ReplayClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = datetime(2026, 9, 23, 10, tzinfo=UTC)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


class Base:
    def __init__(self):
        self.stores = [Store(store_id="own:willys:keep", name="Preserved baseline", chain="willys", city="Malmö"),
                       Store(store_id="legacy-neighbour", name="Staffanstorp", chain="citygross", city="Staffanstorp")]

    async def find_stores(self, postal):
        return self.stores

    def report(self):
        return {}


@pytest.fixture(autouse=True)
def replay_clock(monkeypatch):
    for name in ["grocery_data.app.api.common", "grocery_data.app.api.catalog",
                 "grocery_data.app.services.freshness", "app.providers.own", "app.models.product",
                 "grocery_data.app.domain.promotion_pricing", "grocery_data.app.services.fixed_checkout_price",
                 "app.providers.citygross_municipality"]:
        monkeypatch.setattr(importlib.import_module(name), "datetime", ReplayClock)


async def retained_source(tmp_path, *, full_catalog=False):
    inv = inventory()
    store = approved_citygross_stores(inv)["3211"]
    fixture = Path(__file__).parents[2] / "grocery_data/tests/fixtures/citygross/municipal-promotion-evidence-20260923.json"
    evidence = json.loads(fixture.read_bytes())["items"]
    documents = []
    for position, entry in enumerate(evidence.values()):
        original_observation = datetime.strptime(entry["source_document"].split("_")[0], "%Y%m%dT%H%M%S%fZ").replace(tzinfo=UTC)
        # Explicit fixture envelope for one captured source row; source prices,
        # package identity, conditions and observation remain byte-value equal.
        payload = {"items": [entry["row"]], "pageSize": 1, "currentPage": position,
                   "totalCount": len(evidence), "totalPages": len(evidence)}
        documents.append(RawFetch(chain="citygross", store_external_id="3211", kind="catalog_page",
            method="GET", url="https://www.citygross.se/api/v1/Loop54/products",
            query={"store": "3211", "skip": str(position), "take": "1"}, fetched_at=original_observation,
            http_status=200, content_type="application/json", payload=json.dumps(payload).encode(),
            connector_version="citygross-v1", page_number=position))
    catalog = RawBatch(chain="citygross", documents=tuple(documents))
    if full_catalog:
        class RetainedCatalogClient(FullFixtureCityGrossClient):
            async def fetch_catalog(self, source_store):
                assert source_store.external_id == "3211"
                return catalog.model_copy(update={"catalog_completion": _exact_completion(
                    expected=len(evidence), expected_pages=len(documents))})

        adapter = MunicipalCityGrossConnector(inv, "3211", client=RetainedCatalogClient(()))
        # Reduced completeness floor only for this three-row search fixture;
        # production floor and exact source observations remain untouched.
        adapter.minimum_full_catalog_products = len(evidence)
    else:
        adapter = CityGrossRowApprovedOfferConnector(store=store, locator=RAW, catalog=catalog)
    database = tmp_path / "own.sqlite"
    engine = create_database_engine("sqlite:///" + database.as_posix())
    create_schema(engine)
    factory = create_session_factory(engine)
    result = await GroceryCollector(factory, FilesystemRawSnapshotStore(tmp_path / "raw"),
                                   full_catalog_min_products=1).collect_area(
        adapter, GeographicArea.model_validate(inv["area"]), scope_key="municipality:1280:citygross:3211:offer-rows")
    assert result.promoted and result.metrics.products_parsed == (3 if full_catalog else 2)
    application = FastAPI()
    application.state.session_factory = factory
    application.include_router(catalog_router)
    return engine, application, {"database": database, "inventory": inv, "store_ids": ["3211"],
                                 "snapshot_ids": [result.snapshot_id]}


async def test_real_own_uuid_maps_to_official_external_identity_and_price_universe(tmp_path):
    engine, application, source = await retained_source(tmp_path)
    try:
        with sqlite3.connect(source["database"]) as db:
            internal_id, external_id = db.execute("SELECT id,external_id FROM stores").fetchone()
        assert internal_id != external_id == "3211"
        async with httpx.AsyncClient(base_url="http://isolated", transport=httpx.ASGITransport(app=application)) as client:
            own = OwnGroceryPriceProvider("http://isolated", client=client, include_offers_only=True,
                                          include_conditional_offer_products=True)
            provider = CityGrossMunicipalityProvider(Base(), [{**source, "own": own}])
            stores = await provider.find_stores("21534")
            context = next(s.store_id for s in stores if s.chain == "citygross")
            assert context.startswith("context:citygross:")
            assert {s.store_id for s in stores} == {"own:willys:keep", context}
            products = await provider.get_store_products(context)
            assert len(products) == 2
            assert provider.diagnostics["3211"]["accepted"] == 2
            key = PriceUniverseKey.create(city="Malmö", snapshot_ids=source["snapshot_ids"],
                source_strategy_version="municipal-citygross-test", normalizer_version="existing", taxonomy_version="existing")
            original = PriceUniverseBuilder().build(key, products, built_at=ReplayClock.now(UTC))
            restored = PriceUniverse.model_validate_json(original.model_dump_json())
            assert len(restored.products) == 2
            for product in restored.products:
                assert product.store_id == context
                assert product.price_context_type == "online_store" and product.coverage == "offers_only"
                assert product.price is None and product.offers
                assert product.source_provenance.provider_store_id == "3211"
                assert product.source_provenance.source_snapshot_id in source["snapshot_ids"]
                assert product.source_provenance.maximum_purchase_units == 25
                assert product.source_provenance.official_product_url.startswith("https://www.citygross.se/")
                assert product.source_provenance.source_observed_at.date().isoformat() == "2026-09-23"
    finally:
        engine.dispose()


@pytest.mark.parametrize("failure", ["wrong_product_store", "wrong_snapshot", "neighbour_selection"])
async def test_source_mismatch_cannot_borrow_another_store_price(tmp_path, failure):
    engine, application, source = await retained_source(tmp_path)
    try:
        if failure == "wrong_product_store":
            with sqlite3.connect(source["database"]) as db:
                db.execute("UPDATE source_products SET store_external_id='3229' WHERE external_product_id='100058571_ST'")
        elif failure == "wrong_snapshot":
            source["snapshot_ids"] = ["not-an-active-snapshot"]
        else:
            source["store_ids"] = ["3229"]
        async with httpx.AsyncClient(base_url="http://isolated", transport=httpx.ASGITransport(app=application)) as client:
            own = OwnGroceryPriceProvider("http://isolated", client=client, include_offers_only=True,
                                          include_conditional_offer_products=True)
            provider = CityGrossMunicipalityProvider(Base(), [{**source, "own": own}])
            stores = await provider.find_stores("21534")
            assert not any(s.store_id == "legacy-neighbour" for s in stores)
            assert any(s.store_id == "own:willys:keep" for s in stores)
            products = [p for values in provider.products.values() for p in values]
            assert len(products) == (1 if failure == "wrong_product_store" else 0)
            assert all(p.source_provenance.provider_store_id == "3211" for p in products)
            if failure == "wrong_product_store":
                assert provider.diagnostics["3211"]["rejected"] == {"source_identity_mismatch": 1}
    finally:
        engine.dispose()


async def test_zero_municipality_preserves_other_chains_without_neighbour_fallback():
    provider = CityGrossMunicipalityProvider(Base(), [])
    assert [s.store_id for s in await provider.find_stores("22350")] == ["own:willys:keep"]


async def test_full_catalog_search_delegates_exact_native_store_and_preserves_validated_projection(tmp_path):
    engine, application, source = await retained_source(tmp_path, full_catalog=True)
    try:
        with sqlite3.connect(source["database"]) as db:
            native_id = db.execute("SELECT id FROM stores WHERE external_id='3211'").fetchone()[0]
        async with httpx.AsyncClient(base_url="http://isolated", transport=httpx.ASGITransport(app=application)) as client:
            own = OwnGroceryPriceProvider("http://isolated", client=client)
            base = Base()
            base.search_products = AsyncMock(return_value=[])
            provider = CityGrossMunicipalityProvider(base, [{**source, "own": own}])
            stores = await provider.find_stores("21534")
            context = next(s.store_id for s in stores if s.chain == "citygross")
            catalog = await provider.get_store_products(context)
            assert len(catalog) == 3
            assert all(p.coverage == "full_online_catalog" for p in catalog)
            native_search = own.search_products
            own.search_products = AsyncMock(wraps=native_search)
            hits = await provider.search_products("grillkorv", [context, "own:willys:keep"])
            own.search_products.assert_awaited_once_with("grillkorv", [native_id])
            base.search_products.assert_awaited_once_with("grillkorv", ["own:willys:keep"])
            assert len(hits) == 1
            expected = next(p for p in catalog if p.source_provenance.retailer_product_id == "100308301_ST")
            assert hits[0] is expected
            assert hits[0].store_id == context
            assert hits[0].source_provenance.provider_store_id == "3211"
            assert hits[0].source_provenance.maximum_purchase_units == 25
            assert hits[0].source_provenance.source_observed_at == expected.source_provenance.source_observed_at

            native_hits = await native_search("grillkorv", [native_id])
            # Explicit hostile search responses must never bypass initial source
            # validation, even if an unapproved row matches the ingredient.
            own.search_products = AsyncMock(return_value=[
                native_hits[0].model_copy(update={"store_id": "another-native-store"}),
                native_hits[0].model_copy(update={"product_id": "unvalidated-product"}),
            ])
            assert await provider.search_products("grillkorv", [context]) == []
            assert await provider.get_store_products(context) == catalog
    finally:
        engine.dispose()


async def test_offers_only_search_keeps_all_rows_for_existing_matcher(tmp_path):
    engine, application, source = await retained_source(tmp_path)
    try:
        async with httpx.AsyncClient(base_url="http://isolated", transport=httpx.ASGITransport(app=application)) as client:
            own = OwnGroceryPriceProvider("http://isolated", client=client, include_offers_only=True,
                                          include_conditional_offer_products=True)
            provider = CityGrossMunicipalityProvider(Base(), [{**source, "own": own}])
            stores = await provider.find_stores("21534")
            context = next(s.store_id for s in stores if s.chain == "citygross")
            own.search_products = AsyncMock(side_effect=AssertionError("offer rows use the shared matcher"))
            assert await provider.search_products("unrelated", [context]) == await provider.get_store_products(context)
            own.search_products.assert_not_awaited()
    finally:
        engine.dispose()
