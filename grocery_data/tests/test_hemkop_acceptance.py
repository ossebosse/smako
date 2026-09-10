from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ConnectorStatus,
    GeographicArea,
    RawBatch,
    RawFetch,
    SourceStore,
    TransportMetrics,
)
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import ProductModel, RawSnapshotModel

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "hemkop" / "fixtures"


class FullFixtureHemkopClient:
    connector_version = "hemkop-v1"
    allow_full_crawl = True
    max_categories = None
    max_pages_per_category = None
    allowed_store_ids = frozenset({"4224"})
    requests_per_second = 0.1
    max_concurrency = 1

    def __init__(self) -> None:
        self.fetch_calls = 0
        self.closed = False

    def store_allowed(self, store_external_id: str) -> bool:
        return store_external_id in self.allowed_store_ids

    async def fetch_stores(self) -> RawBatch:
        self.fetch_calls += 1
        return RawBatch(
            chain=Chain.HEMKOP,
            documents=(
                RawFetch(
                    chain=Chain.HEMKOP,
                    kind="stores",
                    method="GET",
                    url="https://www.hemkop.se/axfood/rest/store",
                    query={"online": "false"},
                    http_status=200,
                    content_type="application/json",
                    payload=(FIXTURES / "stores.json").read_bytes(),
                    connector_version=self.connector_version,
                ),
            ),
            transport=TransportMetrics(request_count=1),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        self.fetch_calls += 1
        assert store.external_id == "4224"
        return RawBatch(
            chain=Chain.HEMKOP,
            documents=(
                RawFetch(
                    chain=Chain.HEMKOP,
                    store_external_id="4224",
                    kind="store_activation",
                    method="POST",
                    url="https://www.hemkop.se/axfood/rest/store/activate",
                    query={"storeId": "4224"},
                    http_status=200,
                    content_type="application/json",
                    payload=b"{}",
                    connector_version=self.connector_version,
                ),
                RawFetch(
                    chain=Chain.HEMKOP,
                    store_external_id="4224",
                    kind="store_context",
                    method="GET",
                    url="https://www.hemkop.se/axfood/rest/store/active",
                    http_status=200,
                    content_type="application/json",
                    payload=b'{"pickingStore":{"storeId":"4224"}}',
                    connector_version=self.connector_version,
                ),
                RawFetch(
                    chain=Chain.HEMKOP,
                    store_external_id="4224",
                    kind="category_tree",
                    method="GET",
                    url="https://www.hemkop.se/leftMenu/categorytree",
                    query={"storeId": "4224"},
                    http_status=200,
                    content_type="application/json",
                    payload=(FIXTURES / "category_tree_20.json").read_bytes(),
                    connector_version=self.connector_version,
                ),
                RawFetch(
                    chain=Chain.HEMKOP,
                    store_external_id="4224",
                    kind="catalog_page",
                    method="GET",
                    url="https://www.hemkop.se/c/skafferi",
                    query={"page": "0", "size": "30"},
                    http_status=200,
                    content_type="application/json",
                    payload=(FIXTURES / "fixed_package.json").read_bytes(),
                    connector_version=self.connector_version,
                    page_number=0,
                ),
                RawFetch(
                    chain=Chain.HEMKOP,
                    store_external_id="4224",
                    kind="catalog_page",
                    method="GET",
                    url="https://www.hemkop.se/c/kott-fagel-och-chark",
                    query={"page": "0", "size": "30"},
                    http_status=200,
                    content_type="application/json",
                    payload=(FIXTURES / "member_price.json").read_bytes(),
                    connector_version=self.connector_version,
                    page_number=0,
                ),
            ),
            transport=TransportMetrics(request_count=6),
            catalog_completion=CatalogCompletion(
                complete=True,
                limited=False,
                expected_categories=2,
                completed_categories=2,
                pages_fetched=2,
                products_observed=2,
                expected_products=2,
                raw_rows=2,
                unique_products=2,
                duplicate_products=0,
                expected_pages=2,
            ),
        )

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_full_snapshot_replays_without_transport_or_session_secrets(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw_store, full_catalog_min_products=1)
    client = FullFixtureHemkopClient()
    connector = HemkopConnector.for_full_collection(client=client)  # type: ignore[arg-type]
    connector.minimum_full_catalog_products = 2

    try:
        candidate = await collector.collect_area(
            connector,
            GeographicArea(city="Lund"),
            auto_promote=False,
        )

        assert candidate.status is ConnectorStatus.HEALTHY
        assert candidate.promoted is False
        assert candidate.metrics.products_parsed == 2
        assert client.fetch_calls == 2
        assert client.closed is True
        assert candidate.source_policy_audit is not None
        assert candidate.source_policy_audit.operator_opt_in is True
        assert candidate.source_policy_audit.store_allowlist == ("4224",)

        with session_scope(factory) as session:
            source_products = tuple(
                session.execute(
                    select(
                        ProductModel.external_product_id,
                        ProductModel.name,
                        ProductModel.sale_price,
                    )
                    .where(ProductModel.catalog_snapshot_id == candidate.snapshot_id)
                    .order_by(ProductModel.external_product_id)
                )
            )
            assert session.scalar(
                select(func.count(RawSnapshotModel.id)).where(
                    RawSnapshotModel.catalog_snapshot_id == candidate.snapshot_id
                )
            ) == 6

        replay_connector = HemkopConnector.for_replay(store_external_ids=("4224",))
        replay_connector.minimum_full_catalog_products = 2
        replay_connector.client.fetch_stores = AsyncMock(side_effect=AssertionError("network"))
        replay_connector.client.fetch_catalog = AsyncMock(side_effect=AssertionError("network"))
        replayed = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(replay_connector, candidate.snapshot_id)

        assert replayed.network_requests == 0
        assert replayed.status is ConnectorStatus.HEALTHY
        assert replayed.products_parsed == 2
        replay_connector.client.fetch_stores.assert_not_awaited()
        replay_connector.client.fetch_catalog.assert_not_awaited()
        with session_scope(factory) as session:
            replay_products = tuple(
                session.execute(
                    select(
                        ProductModel.external_product_id,
                        ProductModel.name,
                        ProductModel.sale_price,
                    )
                    .where(ProductModel.catalog_snapshot_id == replayed.replay_snapshot_id)
                    .order_by(ProductModel.external_product_id)
                )
            )
            assert replay_products == source_products
    finally:
        engine.dispose()
