from __future__ import annotations

import copy
import json
from collections.abc import Callable
from math import ceil
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select

from grocery_data.__main__ import _parser as cli_parser
from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.citygross.parser import CityGrossParser
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SnapshotState,
    SourceStore,
    TransportMetrics,
)
from grocery_data.app.services.collector import CatalogCompletenessError, GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.services.snapshot_manager import SnapshotManager
from grocery_data.app.storage import (
    ConnectorHealthRepository,
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
)

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "citygross" / "fixtures"


def _fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_bytes())


def _hyllie_stores_payload() -> bytes:
    rows = _fixture_json("stores.json")
    hyllie = next(row for row in rows if row.get("data", {}).get("siteId") == 169)
    return json.dumps([hyllie], ensure_ascii=False, separators=(",", ":")).encode()


def _catalog_pages(
    count: int,
    *,
    page_size: int,
    transform: Callable[[dict[str, Any], int], None] | None = None,
) -> tuple[bytes, ...]:
    """Generate deterministic pages by cloning observed, sanitised row shapes.

    Only the source identity is varied so persistence can exercise exact
    traversal at the production 10,000-row floor.  No new source field or
    undocumented semantic is invented by the acceptance fixture.
    """

    templates = _fixture_json("catalog_samples.json")["items"]
    rows: list[dict[str, Any]] = []
    for position in range(count):
        row = copy.deepcopy(templates[position % len(templates)])
        row["id"] = f"{row['id']}_ACCEPTANCE_{position:05d}"
        if transform is not None:
            transform(row, position)
        rows.append(row)

    total_pages = ceil(count / page_size)
    return tuple(
        json.dumps(
            {
                "items": rows[page * page_size : (page + 1) * page_size],
                "totalCount": count,
                "pageSize": page_size,
                "currentPage": page,
                "totalPages": total_pages,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        for page in range(total_pages)
    )


def _exact_completion(
    *,
    expected: int,
    rows: int | None = None,
    unique: int | None = None,
    duplicates: int = 0,
    expected_pages: int = 1,
    pages_fetched: int | None = None,
    complete: bool = True,
) -> CatalogCompletion:
    rows = expected if rows is None else rows
    unique = expected if unique is None else unique
    pages_fetched = expected_pages if pages_fetched is None else pages_fetched
    return CatalogCompletion(
        complete=complete,
        limited=not complete,
        expected_categories=1,
        completed_categories=1 if complete else 0,
        pages_fetched=pages_fetched,
        products_observed=unique,
        expected_products=expected,
        raw_rows=rows,
        unique_products=unique,
        duplicate_products=duplicates,
        expected_pages=expected_pages,
        reason=None if complete else "acceptance failure evidence",
    )


class FullFixtureCityGrossClient:
    """Explicitly allowlisted, no-network stand-in for the public REST transport."""

    connector_version = "citygross-v1"
    allow_full_crawl = True
    max_pages = None
    allowed_store_ids = frozenset({"3211"})
    requests_per_second = 1.0
    max_concurrency = 1

    def __init__(
        self,
        pages: tuple[bytes, ...],
        *,
        completion: CatalogCompletion | None = None,
    ) -> None:
        self.pages = pages
        self.completion = completion
        self.fetch_calls = 0
        self.closed = False

    def store_allowed(self, store_external_id: str) -> bool:
        return store_external_id in self.allowed_store_ids

    async def fetch_stores(self) -> RawBatch:
        self.fetch_calls += 1
        return RawBatch(
            chain=Chain.CITY_GROSS,
            documents=(
                RawFetch(
                    chain=Chain.CITY_GROSS,
                    kind="stores",
                    method="GET",
                    url="https://www.citygross.se/api/v1/PageData/stores",
                    http_status=200,
                    content_type="application/json",
                    payload=_hyllie_stores_payload(),
                    connector_version=self.connector_version,
                ),
                RawFetch(
                    chain=Chain.CITY_GROSS,
                    kind="store_number_map",
                    method="GET",
                    url="https://www.citygross.se/api/v1/sites",
                    query={"siteTypeId": "3"},
                    http_status=200,
                    content_type="application/json",
                    payload=(FIXTURES / "sites.json").read_bytes(),
                    connector_version=self.connector_version,
                ),
            ),
            transport=TransportMetrics(request_count=2),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        self.fetch_calls += 1
        assert store.external_id == "3211"
        documents: list[RawFetch] = []
        for page, payload in enumerate(self.pages):
            metadata = json.loads(payload)
            page_size = int(metadata["pageSize"])
            current_page = int(metadata["currentPage"])
            documents.append(
                RawFetch(
                    chain=Chain.CITY_GROSS,
                    store_external_id=store.external_id,
                    kind="catalog_page",
                    method="GET",
                    url="https://www.citygross.se/api/v1/Loop54/products",
                    query={
                        "store": store.external_id,
                        "skip": str(current_page * page_size),
                        "take": str(page_size),
                    },
                    http_status=200,
                    content_type="application/json",
                    payload=payload,
                    connector_version=self.connector_version,
                    page_number=page,
                )
            )
        declared = json.loads(self.pages[0])
        completion = self.completion or _exact_completion(
            expected=declared["totalCount"],
            expected_pages=declared["totalPages"],
        )
        return RawBatch(
            chain=Chain.CITY_GROSS,
            documents=tuple(documents),
            transport=TransportMetrics(request_count=len(documents)),
            catalog_completion=completion,
        )

    async def aclose(self) -> None:
        self.closed = True


class CurrentPriceRepairParser(CityGrossParser):
    """Connector-local parser repair for a simulated currentPrice rename."""

    parser_version = "citygross-parser-v2-current-price-repair"

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        repaired: list[RawFetch] = []
        for document in raw.documents:
            if document.kind != "catalog_page":
                repaired.append(document)
                continue
            payload = document.json_payload()
            for row in payload["items"]:
                prices = row["productStoreDetails"]["prices"]
                if "currentPrice" not in prices and "salesPrice" in prices:
                    prices["currentPrice"] = prices["salesPrice"]
            repaired.append(
                document.model_copy(
                    update={
                        "payload": json.dumps(
                            payload,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ).encode()
                    }
                )
            )
        return super().parse_catalog(
            raw.model_copy(update={"documents": tuple(repaired)}),
            references,
            store,
        )


def _full_connector(
    client: FullFixtureCityGrossClient,
    *,
    minimum: int,
    parser: CityGrossParser | None = None,
) -> CityGrossConnector:
    connector = CityGrossConnector.for_full_collection(
        client=client,  # type: ignore[arg-type]
        parser=parser,
    )
    connector.minimum_full_catalog_products = minimum
    return connector


def _projection(session, snapshot_id: str) -> tuple[tuple[Any, ...], ...]:  # type: ignore[no-untyped-def]
    products = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                ProductModel.name,
                ProductModel.sale_price,
                ProductModel.sale_model,
                ProductModel.package_quantity,
                ProductModel.package_unit,
            )
            .where(ProductModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id)
        )
    )
    prices = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                PriceObservationModel.sale_price,
                PriceObservationModel.regular_price,
                PriceObservationModel.member_price,
                PriceObservationModel.comparison_price,
                PriceObservationModel.comparison_unit,
            )
            .join(PriceObservationModel, PriceObservationModel.product_id == ProductModel.id)
            .where(PriceObservationModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id)
        )
    )
    promotions = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                PromotionModel.external_id,
                PromotionModel.type,
                PromotionModel.price,
                PromotionModel.quantity,
                PromotionModel.member_only,
            )
            .join(PromotionModel, PromotionModel.product_id == ProductModel.id)
            .where(PromotionModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id, PromotionModel.external_id)
        )
    )
    return products, prices, promotions


def test_citygross_cli_exposes_staged_collection_and_explicit_replay_promotion() -> None:
    collect = cli_parser().parse_args(
        ["collect", "--chain", "citygross", "--city", "Malmö", "--no-promote"]
    )
    replay = cli_parser().parse_args(
        [
            "replay",
            "--chain",
            "citygross",
            "--snapshot-id",
            "snapshot-id",
            "--promote",
        ]
    )

    assert collect.no_promote is True
    assert collect.chain == Chain.CITY_GROSS.value
    assert replay.promote is True
    assert replay.chain == Chain.CITY_GROSS.value


@pytest.mark.asyncio
async def test_citygross_full_online_staged_replay_failures_and_local_repair(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw_store, full_catalog_min_products=1)
    pages = _catalog_pages(8, page_size=4)

    try:
        good_client = FullFixtureCityGrossClient(pages)
        candidate = await collector.collect_area(
            _full_connector(good_client, minimum=1),
            GeographicArea(city="Malmö"),
            auto_promote=False,
        )

        assert candidate.status is ConnectorStatus.HEALTHY
        assert candidate.promoted is False
        assert candidate.active_snapshot_id is None
        assert candidate.metrics.products_parsed == 8
        assert candidate.metrics.products_with_price == 8
        assert candidate.source_policy_audit is not None
        expected_audit = {
            "source_policy": "review",
            "operator_opt_in": True,
            "store_allowlist": ["3211"],
            "requests_per_second": 1.0,
            "max_concurrency": 1,
        }
        assert candidate.source_policy_audit.model_dump(mode="json") == expected_audit
        assert good_client.fetch_calls == 2
        assert good_client.closed is True
        assert [
            store.external_id
            for store in candidate.stores
            if store.coverage == CoverageLevel.FULL_ONLINE_CATALOG
        ] == ["3211"]
        with session_scope(factory) as session:
            row = SnapshotRepository(session).get(candidate.snapshot_id)
            assert row is not None and row.state == SnapshotState.HEALTH_CHECKED.value
            assert row.coverage == CoverageLevel.FULL_ONLINE_CATALOG.value
            assert row.metrics["source_policy_audit"] == expected_audit
            run = session.get(CollectorRunModel, row.collector_run_id)
            assert run is not None
            assert run.scope == {
                "scope_key": "malmö",
                "source_scope": {
                    "scope_key": "malmö",
                    "geographic_area": {
                        "city": "Malmö",
                        "postal_codes": [],
                        "latitude": None,
                        "longitude": None,
                    },
                },
                **expected_audit,
            }
            assert {key: run.metrics[key] for key in expected_audit} == expected_audit
            assert row.metrics["catalog_completion"]["3211"] == {
                "complete": True,
                "limited": False,
                "expected_categories": 1,
                "completed_categories": 1,
                "pages_fetched": 2,
                "products_observed": 8,
                "expected_products": 8,
                "raw_rows": 8,
                "unique_products": 8,
                "duplicate_products": 0,
                "expected_pages": 2,
                "reason": None,
            }
            assert (
                session.scalar(
                    select(func.count(RawSnapshotModel.id)).where(
                        RawSnapshotModel.catalog_snapshot_id == candidate.snapshot_id
                    )
                )
                == 4
            )
            source_projection = _projection(session, candidate.snapshot_id)

        replay_connector = CityGrossConnector.for_replay(store_external_ids=("3211",))
        replay_connector.minimum_full_catalog_products = 1
        replay_connector.client.fetch_stores = AsyncMock(side_effect=AssertionError("network"))
        replay_connector.client.fetch_catalog = AsyncMock(side_effect=AssertionError("network"))
        replayed = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(replay_connector, candidate.snapshot_id)

        assert replayed.network_requests == 0
        assert replayed.status is ConnectorStatus.HEALTHY
        assert replayed.promoted is False
        assert replayed.products_parsed == 8
        replay_connector.client.fetch_stores.assert_not_awaited()
        replay_connector.client.fetch_catalog.assert_not_awaited()
        with session_scope(factory) as session:
            replay_row = SnapshotRepository(session).get(replayed.replay_snapshot_id)
            assert replay_row is not None
            assert replay_row.state == SnapshotState.HEALTH_CHECKED.value
            assert replay_row.metrics["network_requests"] == 0
            assert _projection(session, replayed.replay_snapshot_id) == source_projection

        promoted = SnapshotManager(factory, full_catalog_min_products=1).promote(
            candidate.snapshot_id
        )
        assert promoted.state == SnapshotState.PROMOTED.value

        incomplete_cases = (
            _exact_completion(
                expected=8,
                expected_pages=2,
                pages_fetched=1,
                rows=4,
                unique=4,
                complete=False,
            ),
            _exact_completion(
                expected=9,
                expected_pages=2,
                pages_fetched=2,
                rows=8,
                unique=8,
                complete=False,
            ),
            _exact_completion(
                expected=8,
                expected_pages=2,
                pages_fetched=2,
                rows=8,
                unique=7,
                duplicates=1,
                complete=False,
            ),
        )
        for completion in incomplete_cases:
            bad_client = FullFixtureCityGrossClient(pages, completion=completion)
            with pytest.raises(CatalogCompletenessError):
                await collector.collect_area(
                    _full_connector(bad_client, minimum=1),
                    GeographicArea(city="Malmö"),
                    auto_promote=False,
                )
            assert bad_client.closed is True
            with session_scope(factory) as session:
                active = SnapshotRepository(session).active(
                    Chain.CITY_GROSS,
                    scope_key="malmö",
                )
                assert active is not None and active.id == candidate.snapshot_id
                latest_rejected = session.scalar(
                    select(CatalogSnapshotModel)
                    .where(CatalogSnapshotModel.state == SnapshotState.REJECTED.value)
                    .order_by(CatalogSnapshotModel.created_at.desc())
                )
                assert latest_rejected is not None
                assert latest_rejected.metrics["failure_type"] == "CatalogCompletenessError"
                assert latest_rejected.metrics["source_policy_audit"] == expected_audit
                rejected_run = session.get(
                    CollectorRunModel,
                    latest_rejected.collector_run_id,
                )
                assert rejected_run is not None
                assert rejected_run.scope == {
                    "scope_key": "malmö",
                    "source_scope": {
                        "scope_key": "malmö",
                        "geographic_area": {
                            "city": "Malmö",
                            "postal_codes": [],
                            "latitude": None,
                            "longitude": None,
                        },
                    },
                    **expected_audit,
                }
                assert {
                    key: rejected_run.metrics[key] for key in expected_audit
                } == expected_audit
                health = ConnectorHealthRepository(session).get(Chain.CITY_GROSS)
                assert health is not None
                assert health.status == ConnectorStatus.BROKEN.value
                assert health.active_snapshot_id == candidate.snapshot_id

        def rename_current_price(row: dict[str, Any], _position: int) -> None:
            prices = row["productStoreDetails"]["prices"]
            prices["salesPrice"] = prices.pop("currentPrice")

        schema_client = FullFixtureCityGrossClient(
            _catalog_pages(8, page_size=4, transform=rename_current_price)
        )
        schema_broken = await collector.collect_area(
            _full_connector(schema_client, minimum=1),
            GeographicArea(city="Malmö"),
            auto_promote=False,
        )
        assert schema_broken.status is ConnectorStatus.BROKEN
        assert schema_broken.promoted is False
        assert schema_broken.metrics.products_parsed == 0
        assert schema_broken.metrics.products_quarantined == 8
        assert schema_broken.active_snapshot_id == candidate.snapshot_id
        with session_scope(factory) as session:
            row = SnapshotRepository(session).get(schema_broken.snapshot_id)
            assert row is not None and row.state == SnapshotState.REJECTED.value
            assert row.metrics["schema_diff"] is not None
            active = SnapshotRepository(session).active(Chain.CITY_GROSS, scope_key="malmö")
            assert active is not None and active.id == candidate.snapshot_id

        repaired_connector = CityGrossConnector.for_replay(
            store_external_ids=("3211",),
            parser=CurrentPriceRepairParser(),
        )
        repaired_connector.minimum_full_catalog_products = 1
        repaired_connector.client.fetch_stores = AsyncMock(side_effect=AssertionError("network"))
        repaired_connector.client.fetch_catalog = AsyncMock(side_effect=AssertionError("network"))
        repaired = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(
            repaired_connector,
            schema_broken.snapshot_id,
            promote=True,
            accept_schema_change=True,
        )

        assert repaired.network_requests == 0
        assert repaired.status is ConnectorStatus.HEALTHY
        assert repaired.promoted is True
        repaired_connector.client.fetch_stores.assert_not_awaited()
        repaired_connector.client.fetch_catalog.assert_not_awaited()
        with session_scope(factory) as session:
            repaired_row = SnapshotRepository(session).get(repaired.replay_snapshot_id)
            assert repaired_row is not None and repaired_row.state == SnapshotState.PROMOTED.value
            assert repaired_row.metrics["replayed_from"] == schema_broken.snapshot_id
            assert repaired_row.metrics["network_requests"] == 0
            assert _projection(session, repaired.replay_snapshot_id) == source_projection
            active = SnapshotRepository(session).active(Chain.CITY_GROSS, scope_key="malmö")
            assert active is not None and active.id == repaired.replay_snapshot_id
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_citygross_manual_promotion_rechecks_production_10000_product_floor(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    client = FullFixtureCityGrossClient(_catalog_pages(10_000, page_size=100))

    try:
        connector = CityGrossConnector.for_full_collection(client=client)  # type: ignore[arg-type]
        assert connector.minimum_full_catalog_products == 10_000
        candidate = await GroceryCollector(
            factory,
            raw_store,
            full_catalog_min_products=100,
        ).collect_area(
            connector,
            GeographicArea(city="Malmö"),
            auto_promote=False,
        )

        assert candidate.status is ConnectorStatus.HEALTHY
        assert candidate.promoted is False
        assert candidate.metrics.products_fetched == 10_000
        assert candidate.metrics.products_parsed == 10_000
        assert candidate.metrics.products_with_price == 10_000
        assert candidate.raw_documents == 102
        with session_scope(factory) as session:
            row = SnapshotRepository(session).get(candidate.snapshot_id)
            assert row is not None and row.state == SnapshotState.HEALTH_CHECKED.value
            assert row.metrics["minimum_products_for_full_catalog"] == 10_000
            completion = row.metrics["catalog_completion"]["3211"]
            assert completion["expected_products"] == 10_000
            assert completion["raw_rows"] == 10_000
            assert completion["unique_products"] == 10_000
            assert completion["duplicate_products"] == 0
            assert completion["expected_pages"] == 100
            assert completion["pages_fetched"] == 100

        promoted = SnapshotManager(
            factory,
            full_catalog_min_products=10_000,
        ).promote(candidate.snapshot_id)
        assert promoted.state == SnapshotState.PROMOTED.value
        with session_scope(factory) as session:
            active = SnapshotRepository(session).active(Chain.CITY_GROSS, scope_key="malmö")
            assert active is not None and active.id == candidate.snapshot_id
            assert (
                session.scalar(
                    select(func.count(ProductModel.id)).where(
                        ProductModel.catalog_snapshot_id == candidate.snapshot_id
                    )
                )
                == 10_000
            )
            assert (
                session.scalar(
                    select(func.count(PriceObservationModel.id)).where(
                        PriceObservationModel.catalog_snapshot_id == candidate.snapshot_id
                    )
                )
                == 10_000
            )
            health = ConnectorHealthRepository(session).get(Chain.CITY_GROSS)
            assert health is not None
            assert health.status == ConnectorStatus.HEALTHY.value
            assert health.active_snapshot_id == candidate.snapshot_id
    finally:
        engine.dispose()
