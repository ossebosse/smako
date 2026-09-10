from pathlib import Path

import pytest
from sqlalchemy import select

from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    SnapshotState,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import OWN_CATALOG, source_strategy_for
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.connector_acceptance import (
    AcceptanceCheck,
    ConnectorAcceptanceContract,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.services.snapshot_manager import SnapshotManager, SnapshotValidationError
from grocery_data.app.storage import (
    ConnectorHealthRepository,
    SnapshotRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import CatalogSnapshotModel, CollectorRunModel
from grocery_data.tests.test_collector import (
    GOOD_CATALOG,
    FixtureWillysConnector,
    _exact_completion,
)


class FullOnlineFixtureConnector(FixtureWillysConnector):
    coverage = CoverageLevel.FULL_ONLINE_CATALOG

    def parse_stores(self, raw, references, area):  # type: ignore[no-untyped-def]
        stores = super().parse_stores(raw, references, area)
        return [store.model_copy(update={"coverage": self.coverage}) for store in stores]


def _connector(*, minimum: int | None = None) -> FullOnlineFixtureConnector:
    connector = FullOnlineFixtureConnector(
        GOOD_CATALOG,
        catalog_completion=_exact_completion(),
    )
    if minimum is not None:
        connector.minimum_full_catalog_products = minimum
    return connector


def test_complete_catalog_predicate_drives_acceptance_and_source_strategy() -> None:
    assert is_complete_catalog_coverage(CoverageLevel.FULL_CATALOG) is True
    assert is_complete_catalog_coverage(CoverageLevel.FULL_ONLINE_CATALOG) is True
    assert is_complete_catalog_coverage(CoverageLevel.PARTIAL_CATALOG) is False
    assert is_complete_catalog_coverage("future_unknown_coverage") is False

    contract = ConnectorAcceptanceContract(
        chain=Chain.CITY_GROSS,
        declared_coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        source_supports_promotions=False,
    )
    assert AcceptanceCheck.CATALOG_FETCH in contract.required_checks()
    assert AcceptanceCheck.PAGINATION_COMPLETE in contract.required_checks()

    accepted = source_strategy_for(Chain.CITY_GROSS).with_verified_own_catalog(
        CoverageLevel.FULL_ONLINE_CATALOG
    )
    assert accepted.primary_source == OWN_CATALOG


@pytest.mark.asyncio
async def test_full_online_collection_uses_complete_catalog_gate(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    result = await GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    ).collect_area(_connector(), GeographicArea(city="Lund"))

    assert result.status == ConnectorStatus.HEALTHY
    assert result.promoted is True
    with session_scope(factory) as session:
        snapshot = SnapshotRepository(session).get(result.snapshot_id)
        assert snapshot is not None
        assert snapshot.coverage == CoverageLevel.FULL_ONLINE_CATALOG.value
        assert snapshot.metrics["minimum_products_for_full_catalog"] == 1
        assert snapshot.metrics["catalog_completion"]["2354"]["expected_products"] == 1
    engine.dispose()


@pytest.mark.asyncio
async def test_connector_specific_complete_catalog_minimum_is_persisted_and_enforced(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    with pytest.raises(RuntimeError, match="absolute minimum"):
        await GroceryCollector(
            factory,
            FilesystemRawSnapshotStore(tmp_path / "raw"),
            full_catalog_min_products=1,
        ).collect_area(
            _connector(minimum=2),
            GeographicArea(city="Lund"),
        )

    with session_scope(factory) as session:
        snapshot = session.scalar(select(CatalogSnapshotModel))
        assert snapshot is not None
        assert snapshot.state == SnapshotState.REJECTED.value
        assert snapshot.metrics["minimum_products_for_full_catalog"] == 2
    engine.dispose()


@pytest.mark.asyncio
async def test_replay_preserves_stronger_connector_complete_catalog_minimum(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    source = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(_connector(), GeographicArea(city="Lund"))
    replay_connector = _connector(minimum=2)

    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(replay_connector, source.snapshot_id, promote=True)

    assert replay_connector.fetch_calls == 0
    assert replayed.status == ConnectorStatus.BROKEN
    assert replayed.promoted is False
    with session_scope(factory) as session:
        snapshot = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert snapshot is not None
        assert snapshot.metrics["minimum_products_for_full_catalog"] == 2
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == source.snapshot_id
    engine.dispose()


@pytest.mark.asyncio
async def test_healthy_review_candidate_preserves_active_snapshot_and_health_until_promoted(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    collector = GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    )
    baseline = await collector.collect_area(_connector(), GeographicArea(city="Lund"))
    with session_scope(factory) as session:
        original_health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert original_health is not None
        original_checked_at = original_health.checked_at
        original_last_success_at = original_health.last_success_at

    candidate = await collector.collect_area(
        _connector(),
        GeographicArea(city="Lund"),
        auto_promote=False,
    )

    assert candidate.status == ConnectorStatus.HEALTHY
    assert candidate.promoted is False
    assert candidate.active_snapshot_id == baseline.snapshot_id
    with session_scope(factory) as session:
        snapshot = SnapshotRepository(session).get(candidate.snapshot_id)
        assert snapshot is not None
        assert snapshot.state == SnapshotState.HEALTH_CHECKED.value
        assert snapshot.is_active is False
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == baseline.snapshot_id
        health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert health is not None
        assert health.active_snapshot_id == baseline.snapshot_id
        assert health.checked_at == original_checked_at
        assert health.last_success_at == original_last_success_at
        run = session.get(CollectorRunModel, snapshot.collector_run_id)
        assert run is not None and run.successful is True

    promoted = SnapshotManager(factory, full_catalog_min_products=1).promote(candidate.snapshot_id)
    assert promoted.state == SnapshotState.PROMOTED.value
    with session_scope(factory) as session:
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == candidate.snapshot_id
        assert active.previous_active_snapshot_id == baseline.snapshot_id
        health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert health is not None
        assert health.active_snapshot_id == candidate.snapshot_id
        store = StoreRepository(session).get(Chain.WILLYS, "2354")
        assert store is not None and store.is_active is True
    engine.dispose()


@pytest.mark.asyncio
async def test_manual_promotion_rechecks_full_online_completion_evidence(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    candidate = await GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    ).collect_area(
        _connector(),
        GeographicArea(city="Lund"),
        auto_promote=False,
    )

    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(candidate.snapshot_id)
        assert row is not None
        payload = dict(row.metrics)
        completion = dict(payload["catalog_completion"])
        evidence = dict(completion["2354"])
        evidence.update({"complete": False, "limited": True})
        completion["2354"] = evidence
        payload["catalog_completion"] = completion
        row.metrics = payload

    with pytest.raises(SnapshotValidationError, match="traversal is incomplete"):
        SnapshotManager(factory, full_catalog_min_products=1).promote(candidate.snapshot_id)

    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(candidate.snapshot_id)
        assert row is not None and row.state == SnapshotState.REJECTED.value
        assert SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund") is None
    engine.dispose()
