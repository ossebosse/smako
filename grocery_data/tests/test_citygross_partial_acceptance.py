from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.citygross.parser import CityGrossParser
from grocery_data.app.connectors.registry import SOURCE_COVERAGE, ConnectorRegistry
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
)
from grocery_data.app.domain.source_strategy import (
    OWN_CATALOG,
    PRIMAT_CATALOG,
    SourceUnavailableError,
    source_strategy_for,
)
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import (
    ConnectorHealthRepository,
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
)

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "citygross" / "fixtures"


def _fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def _single_hyllie_store_payload() -> bytes:
    """Keep the real sanitized Hyllie row while limiting this test to one context."""

    rows = json.loads(_fixture_bytes("stores.json"))
    return json.dumps([rows[0]], ensure_ascii=False, separators=(",", ":")).encode()


def _renamed_current_price_payload() -> bytes:
    """Simulate one connector-local City Gross price-schema change on every row."""

    payload = json.loads(_fixture_bytes("catalog_samples.json"))
    for row in payload["items"]:
        prices = row["productStoreDetails"]["prices"]
        prices["salesPrice"] = prices.pop("currentPrice")
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()


class FixtureCityGrossClient:
    """No-network transport over sanitized responses captured from the public source."""

    connector_version = "citygross-v1"

    def __init__(self, catalog_payload: bytes) -> None:
        self.catalog_payload = catalog_payload
        self.fetch_calls = 0
        self.closed = False

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
                    payload=_single_hyllie_store_payload(),
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
                    payload=_fixture_bytes("sites.json"),
                    connector_version=self.connector_version,
                ),
            ),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        self.fetch_calls += 1
        payload = json.loads(self.catalog_payload)
        rows = payload.get("items") or payload.get("products") or []
        total = int(payload["totalCount"])
        pages = int(payload["totalPages"])
        page_size = int(payload["pageSize"])
        return RawBatch(
            chain=Chain.CITY_GROSS,
            documents=(
                RawFetch(
                    chain=Chain.CITY_GROSS,
                    store_external_id=store.external_id,
                    kind="catalog_page",
                    method="GET",
                    url="https://www.citygross.se/api/v1/Loop54/products",
                    query={
                        "store": store.external_id,
                        "skip": "0",
                        "take": str(page_size),
                    },
                    http_status=200,
                    content_type="application/json",
                    payload=self.catalog_payload,
                    connector_version=self.connector_version,
                    page_number=0,
                ),
            ),
            # This proves the fixture page itself is reconciled. The connector
            # deliberately remains PARTIAL_CATALOG because the live source's
            # complete operational traversal has not passed acceptance.
            catalog_completion=CatalogCompletion(
                complete=True,
                expected_categories=1,
                completed_categories=1,
                pages_fetched=pages,
                products_observed=len(rows),
                expected_products=total,
                raw_rows=len(rows),
                unique_products=len({str(row["id"]) for row in rows}),
                duplicate_products=len(rows) - len({str(row["id"]) for row in rows}),
                expected_pages=pages,
            ),
        )

    async def aclose(self) -> None:
        self.closed = True


class OptedInPartialCityGrossConnector(CityGrossConnector):
    """Synthetic partial fixture with an explicit REVIEW operator decision."""

    def collection_policy_audit(self) -> SourceCollectionAudit:
        return SourceCollectionAudit(
            source_policy=SourcePolicy.REVIEW,
            operator_opt_in=True,
            store_allowlist=("3211",),
        )


class RepairedCityGrossParser(CityGrossParser):
    """Example connector-local repair for currentPrice -> salesPrice."""

    parser_version = "citygross-parser-v2-schema-repair-test"

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        adapted_documents: list[RawFetch] = []
        for document in raw.documents:
            if document.kind != "catalog_page" or document.http_status != 200:
                adapted_documents.append(document)
                continue
            payload: dict[str, Any] = document.json_payload()
            for row in payload.get("items", []):
                prices = row.get("productStoreDetails", {}).get("prices", {})
                if "currentPrice" not in prices and "salesPrice" in prices:
                    prices["currentPrice"] = prices["salesPrice"]
            adapted_documents.append(
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
            raw.model_copy(update={"documents": tuple(adapted_documents)}),
            references,
            store,
        )


def _snapshot_projection(session: Session, snapshot_id: str) -> tuple[tuple[object, ...], ...]:
    products = tuple(
        tuple(row)
        for row in session.execute(
            select(
                ProductModel.external_product_id,
                ProductModel.name,
                ProductModel.sale_model,
                ProductModel.package_quantity,
                ProductModel.package_unit,
                ProductModel.sale_price,
                ProductModel.comparison_price,
                ProductModel.comparison_unit,
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
                PriceObservationModel.sale_unit,
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
                PromotionModel.max_quantity,
            )
            .join(PromotionModel, PromotionModel.product_id == ProductModel.id)
            .where(PromotionModel.catalog_snapshot_id == snapshot_id)
            .order_by(ProductModel.external_product_id, PromotionModel.external_id)
        )
    )
    return products, prices, promotions


@pytest.mark.asyncio
async def test_citygross_partial_snapshot_replay_break_lkg_and_local_repair(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw_store, full_catalog_min_products=1)

    try:
        good_client = FixtureCityGrossClient(_fixture_bytes("catalog_samples.json"))
        good = await collector.collect_area(
            OptedInPartialCityGrossConnector(client=good_client),  # type: ignore[arg-type]
            GeographicArea(city="Malmö"),
        )

        assert good.status is ConnectorStatus.HEALTHY
        assert good.promoted is True
        assert good.metrics.products_parsed == 8
        assert good.metrics.products_with_price == 8
        assert good.metrics.products_quarantined == 0
        assert good.raw_documents == 3
        assert good_client.fetch_calls == 2
        assert good_client.closed is True

        with session_scope(factory) as session:
            snapshots = SnapshotRepository(session)
            good_row = snapshots.get(good.snapshot_id)
            assert good_row is not None
            assert good_row.state == "promoted"
            assert good_row.coverage == CoverageLevel.PARTIAL_CATALOG.value
            assert snapshots.active(Chain.CITY_GROSS, scope_key="malmö").id == good.snapshot_id
            completion = good_row.metrics["catalog_completion"]["3211"]
            assert completion["expected_products"] == 8
            assert completion["unique_products"] == 8
            assert completion["duplicate_products"] == 0
            raw_rows = list(
                session.scalars(
                    select(RawSnapshotModel).where(
                        RawSnapshotModel.catalog_snapshot_id == good.snapshot_id
                    )
                )
            )
            assert len(raw_rows) == 3
            assert all((raw_store.root / row.payload_location).is_file() for row in raw_rows)
            assert all(row.payload_hash and row.schema_fingerprint for row in raw_rows)
            good_projection = _snapshot_projection(session, good.snapshot_id)

        products, prices, promotions = good_projection
        assert len(products) == 8
        assert len(prices) == 8
        assert len(promotions) == 4

        replay_client = FixtureCityGrossClient(b"replay must not inspect client payload")
        replayed = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(
            OptedInPartialCityGrossConnector(client=replay_client),  # type: ignore[arg-type]
            good.snapshot_id,
        )

        assert replayed.network_requests == 0
        assert replayed.status is ConnectorStatus.HEALTHY
        assert replayed.products_parsed == 8
        assert replayed.products_quarantined == 0
        assert replay_client.fetch_calls == 0
        assert replay_client.closed is True
        with session_scope(factory) as session:
            replay_row = SnapshotRepository(session).get(replayed.replay_snapshot_id)
            assert replay_row is not None and replay_row.state == "health_checked"
            assert replay_row.coverage == CoverageLevel.PARTIAL_CATALOG.value
            assert replay_row.metrics["network_requests"] == 0
            assert _snapshot_projection(session, replayed.replay_snapshot_id) == good_projection

        broken_client = FixtureCityGrossClient(_renamed_current_price_payload())
        broken = await collector.collect_area(
            OptedInPartialCityGrossConnector(client=broken_client),  # type: ignore[arg-type]
            GeographicArea(city="Malmö"),
        )

        assert broken.status is ConnectorStatus.BROKEN
        assert broken.promoted is False
        assert broken.metrics.products_parsed == 0
        assert broken.metrics.products_quarantined == 8
        assert broken.active_snapshot_id == good.snapshot_id
        assert broken_client.closed is True
        with session_scope(factory) as session:
            snapshots = SnapshotRepository(session)
            broken_row = snapshots.get(broken.snapshot_id)
            assert broken_row is not None and broken_row.state == "rejected"
            assert broken_row.metrics["schema_diff"] is not None
            assert snapshots.active(Chain.CITY_GROSS, scope_key="malmö").id == good.snapshot_id
            health = ConnectorHealthRepository(session).get(Chain.CITY_GROSS)
            assert health is not None
            assert health.status == ConnectorStatus.BROKEN.value
            assert health.active_snapshot_id == good.snapshot_id

        repair_client = FixtureCityGrossClient(b"repair replay must remain offline")
        repaired = await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(
            OptedInPartialCityGrossConnector(  # type: ignore[arg-type]
                client=repair_client,
                parser=RepairedCityGrossParser(),
            ),
            broken.snapshot_id,
            promote=True,
            accept_schema_change=True,
        )

        assert repaired.network_requests == 0
        assert repaired.status is ConnectorStatus.HEALTHY
        assert repaired.promoted is True
        assert repaired.products_parsed == 8
        assert repaired.products_quarantined == 0
        assert repair_client.fetch_calls == 0
        assert repair_client.closed is True
        with session_scope(factory) as session:
            snapshots = SnapshotRepository(session)
            repaired_row = snapshots.get(repaired.replay_snapshot_id)
            assert repaired_row is not None and repaired_row.state == "promoted"
            assert repaired_row.coverage == CoverageLevel.PARTIAL_CATALOG.value
            assert repaired_row.metrics["network_requests"] == 0
            assert repaired_row.metrics["replayed_from"] == broken.snapshot_id
            assert _snapshot_projection(session, repaired.replay_snapshot_id) == good_projection
            assert (
                snapshots.active(Chain.CITY_GROSS, scope_key="malmö").id
                == repaired.replay_snapshot_id
            )
            health = ConnectorHealthRepository(session).get(Chain.CITY_GROSS)
            assert health is not None
            assert health.status == ConnectorStatus.HEALTHY.value
            assert health.active_snapshot_id == repaired.replay_snapshot_id
    finally:
        engine.dispose()


def test_partial_acceptance_does_not_weaken_accepted_full_citygross_source_roles() -> None:
    registry = ConnectorRegistry()
    citygross = SOURCE_COVERAGE[Chain.CITY_GROSS]

    assert citygross.source_coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert citygross.implemented is True
    assert citygross.acceptance_contract_passed is True
    bounded = registry.create(Chain.CITY_GROSS)
    assert bounded.coverage is CoverageLevel.PARTIAL_CATALOG
    assert bounded.client.max_pages == 1

    citygross_strategy = source_strategy_for(Chain.CITY_GROSS)
    assert citygross_strategy.primary_source == OWN_CATALOG
    with pytest.raises(SourceUnavailableError, match="explicit opt-in"):
        citygross_strategy.select_catalog_source({PRIMAT_CATALOG})
    fallback = citygross_strategy.select_catalog_source(
        {PRIMAT_CATALOG},
        allow_fallback=True,
    )
    assert fallback.source == PRIMAT_CATALOG

    assert SOURCE_COVERAGE[Chain.WILLYS].implemented is True
    assert SOURCE_COVERAGE[Chain.ICA].implemented is True
    assert SOURCE_COVERAGE[Chain.COOP].implemented is True
    assert source_strategy_for(Chain.WILLYS).primary_source == OWN_CATALOG
    assert source_strategy_for(Chain.ICA).primary_source == PRIMAT_CATALOG
    assert source_strategy_for(Chain.COOP).primary_source == OWN_CATALOG
