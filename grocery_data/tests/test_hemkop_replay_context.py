import pytest

from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.domain import Chain, GeographicArea
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.hemkop_context_collection import HemkopContextActivationError
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.storage import (
    SnapshotRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import StoreContextLinkModel
from grocery_data.tests.test_hemkop_context_orchestration import _seed_context
from grocery_data.tests.test_hemkop_full_acceptance import FullFixtureHemkopClient, _full_connector


@pytest.mark.asyncio
async def test_exact_replay_updates_link_atomically_and_missing_relation_preserves_lkg(tmp_path):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    _seed_context(factory, "4224")
    raw = FilesystemRawSnapshotStore(tmp_path / "raw")
    collector = GroceryCollector(factory, raw, full_catalog_min_products=1)
    source = await collector.collect_area(_full_connector(FullFixtureHemkopClient()),
        GeographicArea(city="Lund"), scope_key="lund:hemkop:4224")
    assert source.promoted
    connector = HemkopConnector.for_replay(store_external_ids=("4224",))
    connector.minimum_full_catalog_products = 8
    service = DatabaseReplayService(factory, raw, full_catalog_min_products=1)
    result = await service.replay_snapshot(connector, source.snapshot_id, promote=True)
    assert result.promoted and result.network_requests == 0
    with session_scope(factory) as session:
        link = session.query(StoreContextLinkModel).one()
        assert link.snapshot_id == result.replay_snapshot_id and link.basket_eligible
        link.is_active = False
    with pytest.raises(HemkopContextActivationError, match="exact official online-context evidence"):
        await service.replay_snapshot(connector, source.snapshot_id, promote=True)
    with session_scope(factory) as session:
        active = SnapshotRepository(session).active(Chain.HEMKOP, scope_key="lund:hemkop:4224")
        assert active.id == result.replay_snapshot_id
    engine.dispose()
