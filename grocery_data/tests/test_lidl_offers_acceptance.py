from __future__ import annotations

from pathlib import Path

import pytest

from grocery_data.app.connectors.lidl import LidlClient, LidlParser
from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    ProductParseResult,
    RawBatch,
    RawFetch,
    SourceStore,
)
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import (
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "lidl" / "fixtures"


class _FixtureLidlConnector:
    chain = Chain.LIDL
    coverage = CoverageLevel.OFFERS_ONLY
    connector_version = "lidl-fixture-v1"

    def __init__(self, fixture: str, *, parser: LidlParser | None = None) -> None:
        self.fixture = fixture
        self.parser = parser or LidlParser()
        self.parser_version = self.parser.parser_version
        self.fetch_calls = 0
        self.closed = False

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        self.fetch_calls += 1
        assert area.city == "Sverige"
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    kind="offer_context_probe",
                    method="GET",
                    url="https://www.lidl.se/q/api/search",
                    query={"fetchsize": "1", "offset": "0"},
                    http_status=200,
                    content_type="application/mindshift.search+json;version=2",
                    payload=(FIXTURES / "offer_samples.json").read_bytes(),
                    connector_version=self.connector_version,
                ),
            ),
        )

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        return self.parser.parse_stores(raw, references, area)

    def catalog_eligible(self, store: SourceStore) -> bool:
        return store.external_id == LidlClient.public_offer_context_id

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        self.fetch_calls += 1
        payload = (FIXTURES / self.fixture).read_bytes()
        if self.fixture == "schema_changed.json":
            # Mutate the complete five-row golden response so the repaired
            # replay can be compared at equal product cardinality.
            payload = (FIXTURES / "offer_samples.json").read_bytes().replace(
                b'"items": [',
                b'"products": [',
                1,
            )
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    kind="offer_page",
                    method="GET",
                    url="https://www.lidl.se/q/api/search",
                    query={"offset": "0"},
                    http_status=200,
                    content_type="application/mindshift.search+json;version=2",
                    payload=payload,
                    connector_version=self.connector_version,
                ),
            ),
        )

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        return await self.fetch_catalog(store)

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        return self.parser.parse_catalog(raw, references, store)

    async def aclose(self) -> None:
        self.closed = True


class _RepairedLidlParser(LidlParser):
    """Connector-local test repair for a renamed top-level collection field."""

    parser_version = "lidl-parser-v2-local-repair"

    def parse_catalog(
        self,
        raw: RawBatch,
        references: list[str],
        store: SourceStore,
    ) -> ProductParseResult:
        repaired = tuple(
            document.model_copy(
                update={"payload": document.payload.replace(b'"products"', b'"items"')}
            )
            for document in raw.documents
        )
        return super().parse_catalog(
            raw.model_copy(update={"documents": repaired}),
            references,
            store,
        )


@pytest.mark.asyncio
async def test_lidl_offers_lkg_replay_schema_break_and_local_repair(tmp_path: Path) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw_store)

    good_connector = _FixtureLidlConnector("offer_samples.json")
    good = await collector.collect_area(good_connector, GeographicArea(city="Sverige"))
    assert good.status == ConnectorStatus.HEALTHY
    assert good.promoted is True
    assert good.metrics.products_parsed == 5
    assert good.metrics.products_quarantined == 0
    assert good.raw_documents == 2
    assert good_connector.fetch_calls == 2
    assert good_connector.closed is True

    offline_connector = _FixtureLidlConnector("offer_samples.json")
    replay = await DatabaseReplayService(factory, raw_store).replay_snapshot(
        offline_connector,
        good.snapshot_id,
        promote=False,
    )
    assert replay.network_requests == 0
    assert replay.products_parsed == 5
    assert replay.products_quarantined == 0
    assert replay.status == ConnectorStatus.HEALTHY
    assert offline_connector.fetch_calls == 0

    broken_connector = _FixtureLidlConnector("schema_changed.json")
    broken = await collector.collect_area(broken_connector, GeographicArea(city="Sverige"))
    assert broken.status == ConnectorStatus.BROKEN
    assert broken.promoted is False
    assert broken.active_snapshot_id == good.snapshot_id
    assert broken.metrics.products_parsed == 0
    assert broken.metrics.products_quarantined == 1
    with session_scope(factory) as session:
        snapshots = SnapshotRepository(session)
        active = snapshots.active(Chain.LIDL, scope_key="sverige")
        rejected = snapshots.get(broken.snapshot_id)
        assert active is not None and active.id == good.snapshot_id
        assert rejected is not None
        assert rejected.state == "rejected"
        assert rejected.is_active is False

    repaired_connector = _FixtureLidlConnector(
        "schema_changed.json",
        parser=_RepairedLidlParser(),
    )
    repaired = await DatabaseReplayService(factory, raw_store).replay_snapshot(
        repaired_connector,
        broken.snapshot_id,
        promote=True,
        accept_schema_change=True,
    )
    assert repaired.network_requests == 0
    assert repaired_connector.fetch_calls == 0
    assert repaired.products_parsed == 5
    assert repaired.products_quarantined == 0
    assert repaired.status == ConnectorStatus.HEALTHY
    assert repaired.promoted is True
    with session_scope(factory) as session:
        active = SnapshotRepository(session).active(Chain.LIDL, scope_key="sverige")
        assert active is not None and active.id == repaired.replay_snapshot_id

    engine.dispose()
