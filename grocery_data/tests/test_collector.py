from hashlib import sha256
from pathlib import Path

import pytest
from sqlalchemy import func, select

from grocery_data.app.connectors.base import ConnectorFetchError, SourcePolicyError
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    RawBatch,
    RawFetch,
    SnapshotState,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
)
from grocery_data.app.monitoring import CollectorEventType
from grocery_data.app.services.collector import CatalogCompletenessError, GroceryCollector
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
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    RawSnapshotModel,
    SourceProductModel,
)


class ListAlertSink:
    def __init__(self) -> None:
        self.alerts = []

    def send(self, alert) -> None:  # type: ignore[no-untyped-def]
        self.alerts.append(alert)


class ListCollectorEventSink:
    def __init__(self) -> None:
        self.events = []

    def emit(self, event) -> None:  # type: ignore[no-untyped-def]
        self.events.append(event)


class FixtureWillysConnector:
    chain = Chain.WILLYS
    coverage = CoverageLevel.FULL_CATALOG
    connector_version = "willys-fixture-v1"

    def __init__(
        self,
        catalog_payload: bytes,
        *,
        parser: WillysParser | None = None,
        catalog_completion: CatalogCompletion | None = None,
    ) -> None:
        self.catalog_payload = catalog_payload
        self.parser = parser or WillysParser()
        self.parser_version = self.parser.parser_version
        self.catalog_completion = catalog_completion
        self.closed = False
        self.fetch_calls = 0

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        self.fetch_calls += 1
        del area
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    kind="stores",
                    method="GET",
                    url="https://public.example/stores",
                    http_status=200,
                    content_type="application/json",
                    payload=(
                        b'[{"storeId":"2354","name":"Willys Lund Nova",'
                        b'"onlineStore":true,"address":{"town":"Lund"}}]'
                    ),
                    connector_version=self.connector_version,
                ),
            ),
        )

    def parse_stores(self, raw, references, area):  # type: ignore[no-untyped-def]
        return self.parser.parse_stores(raw, references, area)

    def catalog_eligible(self, store) -> bool:  # type: ignore[no-untyped-def]
        return store.online_shopping is True

    async def fetch_catalog(self, store) -> RawBatch:  # type: ignore[no-untyped-def]
        self.fetch_calls += 1
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    kind="catalog_page",
                    method="GET",
                    url="https://public.example/catalog",
                    http_status=200,
                    content_type="application/json",
                    payload=self.catalog_payload,
                    connector_version=self.connector_version,
                    page_number=0,
                ),
            ),
            catalog_completion=self.catalog_completion
            or CatalogCompletion(
                complete=True,
                expected_categories=1,
                completed_categories=1,
                pages_fetched=1,
                products_observed=1,
            ),
        )

    def parse_catalog(self, raw, references, store):  # type: ignore[no-untyped-def]
        return self.parser.parse_catalog(raw, references, store)

    async def fetch_offers(self, store) -> RawBatch:  # type: ignore[no-untyped-def]
        del store
        return RawBatch(chain=self.chain, documents=())

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_collector_enforces_source_policy_before_run_or_fetch(tmp_path: Path) -> None:
    class DeniedConnector(FixtureWillysConnector):
        source_policy = SourcePolicy.REVIEW

        def collection_policy_audit(self) -> SourceCollectionAudit:
            return SourceCollectionAudit(
                source_policy=self.source_policy,
                operator_opt_in=False,
            )

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    connector = DeniedConnector(b"{}")
    collector = GroceryCollector(factory, FilesystemRawSnapshotStore(tmp_path / "raw"))

    with pytest.raises(SourcePolicyError, match="explicit operator opt-in"):
        await collector.collect_area(connector, GeographicArea(city="Lund"))

    assert connector.fetch_calls == 0
    with session_scope(factory) as session:
        assert session.scalars(select(CollectorRunModel)).all() == []
        assert session.scalars(select(CatalogSnapshotModel)).all() == []
        assert session.scalars(select(RawSnapshotModel)).all() == []
    engine.dispose()


GOOD_CATALOG = b"""{"results":[
  {"code":"pasta-1","name":"Fusilli","priceValue":19.9,"priceUnit":"kr/st",
   "comparePrice":39.8,"comparePriceUnit":"kr/kg","productLine2":"500g",
   "productBasketType":{"code":"ST"}}
],"pagination":{"currentPage":0,"numberOfPages":1}}"""

BROKEN_CATALOG = b"""{"results":[
  {"code":"pasta-1","name":"Fusilli","salesPrice":{"amount":19.9},
   "priceUnit":{"code":"ST"},"productLine2":{"amount":500,"unit":"g"}}
],"pagination":{"currentPage":0,"numberOfPages":1}}"""


def _exact_completion() -> CatalogCompletion:
    return CatalogCompletion(
        complete=True,
        expected_categories=1,
        completed_categories=1,
        pages_fetched=1,
        products_observed=1,
        expected_products=1,
        raw_rows=1,
        unique_products=1,
        duplicate_products=0,
        expected_pages=1,
    )


def test_collector_full_gate_rechecks_unvalidated_exact_evidence(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    collector = GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    )
    # `model_construct` represents an untrusted/in-memory connector object
    # that bypassed ordinary Pydantic construction. The collector boundary
    # must still fail closed.
    inconsistent = CatalogCompletion.model_construct(
        complete=True,
        limited=False,
        expected_categories=None,
        completed_categories=0,
        pages_fetched=1,
        products_observed=1,
        expected_products=2,
        raw_rows=1,
        unique_products=1,
        duplicate_products=0,
        expected_pages=1,
        reason=None,
    )

    with pytest.raises(CatalogCompletenessError, match="exact product/page counts"):
        collector._validate_catalog_completion(
            FixtureWillysConnector(GOOD_CATALOG),
            RawBatch.model_construct(
                chain=Chain.WILLYS,
                documents=(),
                catalog_completion=inconsistent,
            ),
        )
    engine.dispose()


@pytest.mark.parametrize(
    "partition_counts",
    [
        {},
        {
            "within_partition_duplicates": 1,
            "cross_partition_duplicates": 0,
        },
    ],
    ids=("unexplained-cross-partition", "within-partition-repeat"),
)
def test_collector_full_gate_rejects_unexplained_or_within_partition_duplicates(
    tmp_path: Path,
    partition_counts: dict[str, int],
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    collector = GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    )
    evidence = CatalogCompletion.model_construct(
        complete=True,
        limited=False,
        expected_categories=2,
        completed_categories=2,
        pages_fetched=2,
        products_observed=1,
        expected_products=2,
        raw_rows=2,
        unique_products=1,
        duplicate_products=1,
        expected_pages=2,
        reason=None,
        **partition_counts,
    )

    with pytest.raises(CatalogCompletenessError, match="exact product/page counts"):
        collector._validate_catalog_completion(
            FixtureWillysConnector(GOOD_CATALOG),
            RawBatch.model_construct(
                chain=Chain.WILLYS,
                documents=(),
                catalog_completion=evidence,
            ),
        )
    engine.dispose()


def test_collector_full_gate_accepts_exact_explained_cross_partition_overlap(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    collector = GroceryCollector(
        create_session_factory(engine),
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    )
    evidence = CatalogCompletion(
        complete=True,
        expected_categories=2,
        completed_categories=2,
        pages_fetched=2,
        products_observed=1,
        expected_products=2,
        raw_rows=2,
        unique_products=1,
        duplicate_products=1,
        within_partition_duplicates=0,
        cross_partition_duplicates=1,
        expected_pages=2,
    )

    collector._validate_catalog_completion(
        FixtureWillysConnector(GOOD_CATALOG),
        RawBatch(
            chain=Chain.WILLYS,
            documents=(),
            catalog_completion=evidence,
        ),
    )
    engine.dispose()


@pytest.mark.asyncio
async def test_collection_emits_started_and_finished_events(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    events = ListCollectorEventSink()

    result = await GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        event_sink=events,
        full_catalog_min_products=1,
    ).collect_area(FixtureWillysConnector(GOOD_CATALOG), GeographicArea(city="Lund"))

    assert [event.event for event in events.events] == [
        CollectorEventType.STARTED,
        CollectorEventType.FINISHED,
    ]
    started, finished = events.events
    assert started.snapshot_id == result.snapshot_id == finished.snapshot_id
    assert started.scope == "lund"
    assert finished.products == 1
    assert finished.errors == 0
    assert finished.request_count == 2
    assert finished.status == ConnectorStatus.HEALTHY
    engine.dispose()


@pytest.mark.asyncio
async def test_explicit_context_scope_does_not_replace_city_identity(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    events = ListCollectorEventSink()
    with session_scope(factory) as session:
        StoreRepository(session).upsert(
            SourceStore(
                chain=Chain.WILLYS,
                external_id="2176",
                name="Willys Lund",
                city="Lund",
                online_shopping=True,
                coverage=CoverageLevel.FULL_CATALOG,
                raw_reference="raw:existing-context",
            )
        )

    result = await GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        event_sink=events,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
        scope_key="Lund:Willys:2354",
    )

    assert result.scope_key == "lund:willys:2354"
    assert events.events[0].scope == "lund:willys:2354"
    with session_scope(factory) as session:
        snapshot = SnapshotRepository(session).active(
            Chain.WILLYS,
            scope_key="lund:willys:2354",
        )
        store = StoreRepository(session).get(Chain.WILLYS, "2354")
        other_store = StoreRepository(session).get(Chain.WILLYS, "2176")
        assert snapshot is not None
        assert snapshot.id == result.snapshot_id
        assert store is not None
        assert store.city == "Lund"
        assert other_store is not None
        assert other_store.is_active is True

        expected_scope = {
            "scope_key": "lund:willys:2354",
            "geographic_area": {
                "city": "Lund",
                "postal_codes": [],
                "latitude": None,
                "longitude": None,
            },
        }
        assert snapshot.metrics["source_scope"] == expected_scope
        run = session.get(CollectorRunModel, snapshot.collector_run_id)
        assert run is not None
        assert run.scope["source_scope"] == expected_scope
        source_products = tuple(
            session.scalars(
                select(SourceProductModel.external_product_id).where(
                    SourceProductModel.catalog_snapshot_id == snapshot.id
                )
            )
        )

        # Simulate a scoped pre-descriptor snapshot. Replay must recover the
        # real city generically from its persisted contextual store, never by
        # passing the compound ownership key to the store parser.
        source_metrics = dict(snapshot.metrics)
        source_metrics.pop("source_scope")
        snapshot.metrics = source_metrics
        legacy_run_scope = dict(run.scope)
        legacy_run_scope.pop("source_scope")
        run.scope = legacy_run_scope

    replay_connector = FixtureWillysConnector(GOOD_CATALOG)
    replayed = await DatabaseReplayService(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    ).replay_snapshot(replay_connector, result.snapshot_id, promote=True)

    assert replay_connector.fetch_calls == 0
    assert replayed.network_requests == 0
    assert replayed.products_parsed == len(source_products) == 1
    assert replayed.status is ConnectorStatus.HEALTHY
    assert replayed.promoted is True
    with session_scope(factory) as session:
        replay_snapshot = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        replay_store = StoreRepository(session).get(Chain.WILLYS, "2354")
        untouched_store = StoreRepository(session).get(Chain.WILLYS, "2176")
        assert replay_snapshot is not None
        assert replay_snapshot.scope_key == "lund:willys:2354"
        assert replay_snapshot.metrics["source_scope"] == expected_scope
        assert (
            tuple(
                session.scalars(
                    select(SourceProductModel.external_product_id).where(
                        SourceProductModel.catalog_snapshot_id == replay_snapshot.id
                    )
                )
            )
            == source_products
        )
        assert replay_store is not None and replay_store.is_active is True
        assert untouched_store is not None and untouched_store.is_active is True
    engine.dispose()


@pytest.mark.asyncio
async def test_exact_completion_evidence_persists_and_replays_without_network(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collected = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(
            GOOD_CATALOG,
            catalog_completion=_exact_completion(),
        ),
        GeographicArea(city="Lund"),
    )

    assert collected.promoted is True
    with session_scope(factory) as session:
        source = SnapshotRepository(session).get(collected.snapshot_id)
        assert source is not None
        persisted = source.metrics["catalog_completion"]["2354"]
        assert persisted["expected_products"] == 1
        assert persisted["raw_rows"] == 1
        assert persisted["unique_products"] == 1
        assert persisted["duplicate_products"] == 0
        assert persisted["expected_pages"] == 1

    replay_connector = FixtureWillysConnector(GOOD_CATALOG)
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(replay_connector, collected.snapshot_id)

    assert replay_connector.fetch_calls == 0
    assert replayed.network_requests == 0
    assert replayed.products_parsed == 1
    assert replayed.status == ConnectorStatus.HEALTHY
    with session_scope(factory) as session:
        candidate = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert candidate is not None
        assert candidate.metrics["catalog_completion"]["2354"] == persisted
        assert candidate.metrics["network_requests"] == 0
    engine.dispose()


@pytest.mark.asyncio
async def test_collection_failure_emits_metrics_without_exception_details(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    events = ListCollectorEventSink()

    with pytest.raises(ConnectorFetchError):
        await GroceryCollector(
            factory,
            FilesystemRawSnapshotStore(tmp_path / "raw"),
            event_sink=events,
            full_catalog_min_products=1,
        ).collect_area(
            PartialFailureConnector(GOOD_CATALOG),
            GeographicArea(city="Lund"),
        )

    assert [event.event for event in events.events] == [
        CollectorEventType.STARTED,
        CollectorEventType.FAILED,
    ]
    failed = events.events[-1]
    assert failed.products == 0
    assert failed.errors == 2  # one failed store plus one HTTP response
    assert failed.request_count == 3
    assert failed.status == ConnectorStatus.BROKEN
    assert set(failed.model_dump()) == {
        "event",
        "chain",
        "scope",
        "snapshot_id",
        "products",
        "errors",
        "request_count",
        "runtime_ms",
        "status",
        "created_at",
    }
    engine.dispose()


class RepairedWillysParser(WillysParser):
    parser_version = "willys-parser-v2-test"

    def _parse_product(  # type: ignore[no-untyped-def]
        self,
        row,
        store,
        raw_reference,
        fetched_at,
        *,
        page_category_path=(),
    ):
        adapted = dict(row)
        sales_price = adapted.get("salesPrice")
        if isinstance(sales_price, dict) and sales_price.get("amount") is not None:
            adapted["priceValue"] = sales_price["amount"]
        price_unit = adapted.get("priceUnit")
        if isinstance(price_unit, dict):
            adapted["priceUnit"] = f"kr/{str(price_unit.get('code') or '').casefold()}"
        package = adapted.get("productLine2")
        if isinstance(package, dict):
            adapted["productLine2"] = f"{package.get('amount')}{package.get('unit')}"
        return super()._parse_product(
            adapted,
            store,
            raw_reference,
            fetched_at,
            page_category_path=page_category_path,
        )


class ExplodingWillysParser(WillysParser):
    parser_version = "willys-parser-exploding-test"

    def parse_catalog(self, raw, references, store):  # type: ignore[no-untyped-def]
        del raw, references, store
        raise RuntimeError("fixture parser failed")


class MixedStoreFixtureConnector(FixtureWillysConnector):
    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        self.fetch_calls += 1
        del area
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    kind="stores",
                    method="GET",
                    url="https://public.example/stores",
                    http_status=200,
                    content_type="application/json",
                    payload=(
                        b'[{"storeId":"offline","name":"Willys Hemma Lund",'
                        b'"onlineStore":false,"address":{"town":"Lund"}},'
                        b'{"storeId":"2354","name":"Willys Lund Nova",'
                        b'"onlineStore":true,"address":{"town":"Lund"}}]'
                    ),
                    connector_version=self.connector_version,
                ),
            ),
        )


class PartialFailureConnector(FixtureWillysConnector):
    async def fetch_catalog(self, store) -> RawBatch:  # type: ignore[no-untyped-def]
        self.fetch_calls += 1
        partial = RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    kind="catalog_page",
                    method="GET",
                    url="https://public.example/catalog",
                    query={"page": "0"},
                    http_status=200,
                    content_type="application/json",
                    payload=self.catalog_payload,
                    connector_version=self.connector_version,
                    page_number=0,
                ),
                RawFetch(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    kind="catalog_page",
                    method="GET",
                    url="https://public.example/catalog",
                    query={"page": "1"},
                    http_status=503,
                    content_type="application/json",
                    payload=b'{"error":"temporary"}',
                    connector_version=self.connector_version,
                    page_number=1,
                ),
            ),
            catalog_completion=CatalogCompletion(
                complete=False,
                expected_categories=1,
                completed_categories=0,
                pages_fetched=2,
                products_observed=1,
                reason="WillysHttpError",
            ),
        )
        raise ConnectorFetchError("fixture aborted", partial_batch=partial)


@pytest.mark.asyncio
async def test_collection_skips_store_without_verified_catalog_context(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    connector = MixedStoreFixtureConnector(GOOD_CATALOG)

    result = await GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    ).collect_area(connector, GeographicArea(city="Lund"))

    assert result.promoted is True
    assert len(result.stores) == 2
    assert result.metrics.stores_successful == 1
    assert result.metrics.stores_failed == 0
    assert result.metrics.products_parsed == 1
    assert connector.fetch_calls == 2
    assert any("lacked a verified catalog context" in warning for warning in result.warnings)
    engine.dispose()


@pytest.mark.asyncio
async def test_aborted_catalog_persists_all_partial_raw_before_reject(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    connector = PartialFailureConnector(GOOD_CATALOG)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")

    with pytest.raises(ConnectorFetchError):
        await GroceryCollector(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).collect_area(connector, GeographicArea(city="Lund"))

    with session_scope(factory) as session:
        snapshot = session.scalar(
            select(CatalogSnapshotModel).order_by(CatalogSnapshotModel.created_at.desc())
        )
        assert snapshot is not None
        assert snapshot.state == "rejected"
        raw_rows = list(
            session.scalars(
                select(RawSnapshotModel)
                .where(RawSnapshotModel.catalog_snapshot_id == snapshot.id)
                .order_by(RawSnapshotModel.created_at, RawSnapshotModel.id)
            )
        )
        assert [row.http_status for row in raw_rows] == [200, 200, 503]
        evidence = snapshot.metrics["catalog_completion"]["2354"]
        assert evidence["complete"] is False
        assert evidence["products_observed"] == 1
        assert snapshot.metrics["run_metrics"]["request_count"] == 3
        assert snapshot.metrics["run_metrics"]["http_error_count"] == 1
        snapshot_id = snapshot.id

    replayed_connector = FixtureWillysConnector(GOOD_CATALOG)
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(replayed_connector, snapshot_id, promote=True)
    assert replayed_connector.fetch_calls == 0
    assert replayed.products_parsed == 1
    assert replayed.status == ConnectorStatus.BROKEN
    assert replayed.promoted is False
    engine.dispose()


@pytest.mark.parametrize(
    ("completion", "minimum", "error_match"),
    [
        (
            CatalogCompletion(
                complete=False,
                expected_categories=1,
                completed_categories=0,
                pages_fetched=1,
                products_observed=1,
                expected_products=1,
                raw_rows=1,
                unique_products=1,
                duplicate_products=0,
                expected_pages=1,
                reason="missing_page",
            ),
            1,
            "incomplete or explicitly limited",
        ),
        (_exact_completion(), 2, "absolute minimum"),
    ],
    ids=("completion-rejection", "product-floor-rejection"),
)
@pytest.mark.asyncio
async def test_completion_gate_rejection_keeps_raw_db_lineage_replayable(
    tmp_path: Path,
    completion: CatalogCompletion,
    minimum: int,
    error_match: str,
) -> None:
    """Raw-first evidence survives a gate rollback without contaminating the LKG."""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    baseline = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG, catalog_completion=_exact_completion()),
        GeographicArea(city="Lund"),
    )

    rejected_connector = FixtureWillysConnector(
        GOOD_CATALOG,
        catalog_completion=completion,
    )
    with pytest.raises(CatalogCompletenessError, match=error_match):
        await GroceryCollector(
            factory,
            raw_store,
            full_catalog_min_products=minimum,
        ).collect_area(rejected_connector, GeographicArea(city="Lund"))

    with session_scope(factory) as session:
        rejected = session.scalar(
            select(CatalogSnapshotModel)
            .where(CatalogSnapshotModel.id != baseline.snapshot_id)
            .order_by(CatalogSnapshotModel.created_at.desc())
        )
        assert rejected is not None
        assert rejected.state == SnapshotState.REJECTED.value
        assert rejected.is_active is False
        assert rejected.metrics["catalog_completion"]["2354"] == {
            key: value
            for key, value in completion.model_dump(mode="json").items()
            if key
            not in {
                "within_partition_duplicates",
                "cross_partition_duplicates",
                "exact_duplicates_removed",
                "conflicting_duplicates",
                "pagination_overlaps",
            }
        }
        raw_rows = list(
            session.scalars(
                select(RawSnapshotModel)
                .where(RawSnapshotModel.catalog_snapshot_id == rejected.id)
                .order_by(RawSnapshotModel.created_at, RawSnapshotModel.id)
            )
        )
        assert len(raw_rows) == 2
        for row in raw_rows:
            payload = (raw_store.root / row.payload_location).read_bytes()
            assert sha256(payload).hexdigest() == row.payload_hash
        assert (
            session.scalar(
                select(func.count(SourceProductModel.id)).where(
                    SourceProductModel.catalog_snapshot_id == rejected.id
                )
            )
            == 0
        )
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == baseline.snapshot_id
        rejected_id = rejected.id
        persisted_completion = rejected.metrics["catalog_completion"]["2354"]

    replay_connector = FixtureWillysConnector(GOOD_CATALOG)
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(replay_connector, rejected_id, promote=True)

    assert replay_connector.fetch_calls == 0
    assert replayed.network_requests == 0
    assert replayed.status == ConnectorStatus.BROKEN
    assert replayed.promoted is False
    with session_scope(factory) as session:
        replay = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert replay is not None and replay.state == SnapshotState.REJECTED.value
        assert replay.metrics["catalog_completion"]["2354"] == persisted_completion
        assert replay.metrics["network_requests"] == 0
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == baseline.snapshot_id

    engine.dispose()


@pytest.mark.asyncio
async def test_full_catalog_requires_absolute_minimum_on_first_run(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)

    with pytest.raises(RuntimeError, match="absolute minimum"):
        await GroceryCollector(
            factory,
            FilesystemRawSnapshotStore(tmp_path / "raw"),
            full_catalog_min_products=2,
        ).collect_area(
            FixtureWillysConnector(GOOD_CATALOG),
            GeographicArea(city="Lund"),
        )

    with session_scope(factory) as session:
        snapshot = session.scalar(select(CatalogSnapshotModel))
        assert snapshot is not None and snapshot.state == "rejected"
        assert snapshot.metrics["minimum_products_for_full_catalog"] == 2
        assert SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund") is None
    engine.dispose()


@pytest.mark.asyncio
async def test_store_reconciliation_runs_only_after_healthy_promotion(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    stale = SourceStore(
        chain=Chain.WILLYS,
        external_id="stale",
        name="Willys Lund Stale",
        city="Lund",
        online_shopping=True,
        coverage=CoverageLevel.FULL_CATALOG,
        raw_reference="raw:seed",
    )
    with session_scope(factory) as session:
        StoreRepository(session).upsert(stale)

    collector = GroceryCollector(factory, raw_store, full_catalog_min_products=1)
    good = await collector.collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
    )
    assert good.promoted is True
    with session_scope(factory) as session:
        assert StoreRepository(session).get(Chain.WILLYS, "stale").is_active is False
        StoreRepository(session).upsert(stale)

    broken = await collector.collect_area(
        FixtureWillysConnector(BROKEN_CATALOG),
        GeographicArea(city="Lund"),
    )
    assert broken.promoted is False
    with session_scope(factory) as session:
        assert StoreRepository(session).get(Chain.WILLYS, "stale").is_active is True
    engine.dispose()


@pytest.mark.asyncio
async def test_broken_collection_keeps_last_known_good_snapshot(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    alerts = ListAlertSink()
    collector = GroceryCollector(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        alert_sink=alerts,
        full_catalog_min_products=1,
    )

    good_connector = FixtureWillysConnector(GOOD_CATALOG)
    good = await collector.collect_area(good_connector, GeographicArea(city="Lund"))
    assert good.promoted is True
    assert good.status == ConnectorStatus.HEALTHY
    assert good.metrics.products_parsed == 1
    assert good_connector.closed is True

    broken_connector = FixtureWillysConnector(BROKEN_CATALOG)
    broken = await collector.collect_area(broken_connector, GeographicArea(city="Lund"))
    assert broken.promoted is False
    assert broken.status == ConnectorStatus.BROKEN
    assert broken.active_snapshot_id == good.snapshot_id
    assert broken_connector.closed is True
    assert any(alert.code == "schema_changed" for alert in alerts.alerts)

    with session_scope(factory) as session:
        snapshots = SnapshotRepository(session)
        assert snapshots.active(Chain.WILLYS, scope_key="lund").id == good.snapshot_id
        rejected = snapshots.get(broken.snapshot_id)
        assert rejected is not None and rejected.state == "rejected"
        health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert health is not None and health.status == "broken"

    repaired_connector = FixtureWillysConnector(
        BROKEN_CATALOG,
        parser=RepairedWillysParser(),
    )
    replayed = await DatabaseReplayService(
        factory,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        full_catalog_min_products=1,
    ).replay_snapshot(
        repaired_connector,
        broken.snapshot_id,
        promote=True,
        accept_schema_change=True,
    )
    assert replayed.network_requests == 0
    assert repaired_connector.fetch_calls == 0
    assert replayed.products_parsed == 1
    assert replayed.promoted is True
    with session_scope(factory) as session:
        assert (
            SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund").id
            == replayed.replay_snapshot_id
        )
        health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert health is not None
        assert health.status == ConnectorStatus.HEALTHY.value
        assert health.active_snapshot_id == replayed.replay_snapshot_id

    engine.dispose()


@pytest.mark.asyncio
async def test_replay_exception_rejects_candidate_and_finishes_run(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    good = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
    )
    exploding = FixtureWillysConnector(GOOD_CATALOG, parser=ExplodingWillysParser())

    with pytest.raises(RuntimeError, match="fixture parser failed"):
        await DatabaseReplayService(
            factory,
            raw_store,
            full_catalog_min_products=1,
        ).replay_snapshot(
            exploding,
            good.snapshot_id,
            promote=True,
        )

    assert exploding.closed is True
    assert exploding.fetch_calls == 0
    with session_scope(factory) as session:
        candidates = list(
            session.scalars(
                select(CatalogSnapshotModel)
                .where(CatalogSnapshotModel.id != good.snapshot_id)
                .order_by(CatalogSnapshotModel.created_at.desc())
            )
        )
        assert len(candidates) == 1
        assert candidates[0].state == "rejected"
        assert candidates[0].metrics["failure_type"] == "RuntimeError"
        assert candidates[0].metrics["network_requests"] == 0
        assert candidates[0].metrics["replayed_from"] == good.snapshot_id
        run = session.get(CollectorRunModel, candidates[0].collector_run_id)
        assert run is not None
        assert run.status == "failed"
        assert run.successful is False
        assert run.finished_at is not None
        health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert health is not None
        assert health.status == ConnectorStatus.BROKEN.value
        assert health.active_snapshot_id == good.snapshot_id
        assert (
            SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund").id
            == good.snapshot_id
        )
    engine.dispose()


@pytest.mark.asyncio
async def test_manual_promotion_rechecks_health_and_rejects_degraded_replay(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    good = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
    )
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(
        FixtureWillysConnector(GOOD_CATALOG),
        good.snapshot_id,
        promote=False,
    )
    assert replayed.status == ConnectorStatus.HEALTHY
    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert row is not None and row.state == "health_checked"
        payload = dict(row.metrics)
        run_metrics = dict(payload["run_metrics"])
        run_metrics["products_with_price"] = 0
        payload["run_metrics"] = run_metrics
        row.metrics = payload

    with pytest.raises(SnapshotValidationError, match="missing price rate"):
        SnapshotManager(factory, full_catalog_min_products=1).promote(replayed.replay_snapshot_id)

    with session_scope(factory) as session:
        rejected = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert rejected is not None and rejected.state == "rejected"
        assert (
            SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund").id
            == good.snapshot_id
        )
    engine.dispose()


@pytest.mark.asyncio
async def test_manual_promotion_accepts_healthy_replay_and_updates_health(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    good = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
    )
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(
        FixtureWillysConnector(GOOD_CATALOG),
        good.snapshot_id,
        promote=False,
    )

    promoted = SnapshotManager(factory, full_catalog_min_products=1).promote(
        replayed.replay_snapshot_id
    )

    assert promoted.state == "promoted"
    assert promoted.is_active is True
    with session_scope(factory) as session:
        health = ConnectorHealthRepository(session).get(Chain.WILLYS)
        assert health is not None
        assert health.status == ConnectorStatus.HEALTHY.value
        assert health.active_snapshot_id == replayed.replay_snapshot_id
    engine.dispose()


@pytest.mark.asyncio
async def test_manual_promotion_enforces_operator_minimum_over_persisted_candidate(
    tmp_path: Path,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    good = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
    )
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(
        FixtureWillysConnector(GOOD_CATALOG),
        good.snapshot_id,
        promote=False,
    )

    # The persisted candidate says that one product was sufficient, but the
    # manual/CLI policy defaults to 100. The candidate cannot lower that floor.
    with pytest.raises(SnapshotValidationError, match="below the configured minimum"):
        SnapshotManager(factory).promote(replayed.replay_snapshot_id)

    with session_scope(factory) as session:
        rejected = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert rejected is not None and rejected.state == "rejected"
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == good.snapshot_id
    engine.dispose()


@pytest.mark.parametrize(
    ("completion_update", "minimum", "message"),
    [
        ({"complete": False}, 1, "traversal is incomplete"),
        ({"products_observed": 1}, 2, "below the configured minimum"),
    ],
)
@pytest.mark.asyncio
async def test_manual_promotion_rejects_invalid_full_catalog_completion_evidence(
    tmp_path: Path,
    completion_update: dict[str, object],
    minimum: int,
    message: str,
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    good = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(GOOD_CATALOG),
        GeographicArea(city="Lund"),
    )
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(
        FixtureWillysConnector(GOOD_CATALOG),
        good.snapshot_id,
        promote=False,
    )
    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert row is not None
        payload = dict(row.metrics)
        completion = dict(payload["catalog_completion"])
        store_evidence = dict(completion["2354"])
        store_evidence.update(completion_update)
        completion["2354"] = store_evidence
        payload["catalog_completion"] = completion
        payload["minimum_products_for_full_catalog"] = minimum
        row.metrics = payload

    with pytest.raises(SnapshotValidationError, match=message):
        SnapshotManager(factory, full_catalog_min_products=1).promote(replayed.replay_snapshot_id)

    with session_scope(factory) as session:
        rejected = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert rejected is not None and rejected.state == "rejected"
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == good.snapshot_id
    engine.dispose()


@pytest.mark.parametrize(
    "partition_counts",
    [
        {},
        {
            "within_partition_duplicates": 1,
            "cross_partition_duplicates": 0,
        },
    ],
    ids=("unexplained-cross-partition", "within-partition-repeat"),
)
@pytest.mark.asyncio
async def test_manual_promotion_rejects_tampered_exact_completion_and_keeps_lkg(
    tmp_path: Path,
    partition_counts: dict[str, int],
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    good = await GroceryCollector(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).collect_area(
        FixtureWillysConnector(
            GOOD_CATALOG,
            catalog_completion=_exact_completion(),
        ),
        GeographicArea(city="Lund"),
    )
    replayed = await DatabaseReplayService(
        factory,
        raw_store,
        full_catalog_min_products=1,
    ).replay_snapshot(
        FixtureWillysConnector(GOOD_CATALOG),
        good.snapshot_id,
        promote=False,
    )

    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert row is not None
        payload = dict(row.metrics)
        completion = dict(payload["catalog_completion"])
        store_evidence = dict(completion["2354"])
        # Keep the row arithmetic internally plausible while introducing one
        # duplicate. It is either unexplained or explicitly within one source
        # partition, so exact full-catalog evidence must still reject it.
        store_evidence["expected_products"] = 2
        store_evidence["raw_rows"] = 2
        store_evidence["duplicate_products"] = 1
        store_evidence.update(partition_counts)
        completion["2354"] = store_evidence
        payload["catalog_completion"] = completion
        row.metrics = payload

    with pytest.raises(SnapshotValidationError, match="completion evidence is invalid"):
        SnapshotManager(factory, full_catalog_min_products=1).promote(replayed.replay_snapshot_id)

    with session_scope(factory) as session:
        rejected = SnapshotRepository(session).get(replayed.replay_snapshot_id)
        assert rejected is not None and rejected.state == "rejected"
        active = SnapshotRepository(session).active(Chain.WILLYS, scope_key="lund")
        assert active is not None and active.id == good.snapshot_id
    engine.dispose()


def test_manual_validation_rejects_metrics_without_persisted_rows() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    from grocery_data.app.monitoring import fingerprint_json

    empty_schema_fingerprint = fingerprint_json({}).digest
    with session_scope(factory) as session:
        snapshots = SnapshotRepository(session)
        row = snapshots.create(
            chain=Chain.WILLYS,
            coverage=CoverageLevel.FULL_CATALOG,
            connector_version="fixture-v1",
            parser_version="fixture-parser-v1",
            normalizer_version="fixture-normalizer-v1",
            scope_key="lund",
            schema_fingerprint=empty_schema_fingerprint,
            metrics={
                "run_metrics": {
                    "stores_found": 1,
                    "stores_successful": 1,
                    "products_fetched": 1,
                    "products_parsed": 1,
                    "products_with_price": 1,
                },
                "schemas": {},
                "schema_diff": None,
                "catalog_completion": {
                    "2354": {
                        "complete": True,
                        "limited": False,
                        "expected_categories": 1,
                        "completed_categories": 1,
                        "pages_fetched": 1,
                        "products_observed": 1,
                    }
                },
                "minimum_products_for_full_catalog": 1,
            },
        )
        snapshots.transition(row.id, "parsed")
        snapshot_id = row.id

    with pytest.raises(SnapshotValidationError, match="do not reconcile"):
        SnapshotManager(factory, full_catalog_min_products=1).validate(snapshot_id)

    with session_scope(factory) as session:
        row = SnapshotRepository(session).get(snapshot_id)
        assert row is not None and row.state == "rejected"
    engine.dispose()
