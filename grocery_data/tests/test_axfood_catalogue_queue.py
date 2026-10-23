import pytest
from sqlalchemy import select

from grocery_data.app.domain import GeographicArea
from grocery_data.app.services.axfood_catalogue_queue import approved_catalogue_codes
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.app.storage.models import CatalogSnapshotModel
from grocery_data.tests.test_collector import GOOD_CATALOG, FixtureWillysConnector


@pytest.mark.asyncio
async def test_catalogue_promotion_updates_exact_detail_queue_without_new_queue_or_requests(tmp_path):
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    collector = GroceryCollector(factory, FilesystemRawSnapshotStore(tmp_path/'raw'), full_catalog_min_products=1)
    first = await collector.collect_area(FixtureWillysConnector(GOOD_CATALOG), GeographicArea(city="Lund"))
    with factory() as session:
        codes, proof = approved_catalogue_codes(session, first.snapshot_id, chain="willys", store_id="2354")
        assert codes == ["pasta-1"]
        assert proof['catalogs'][0]['snapshot_id'] == first.snapshot_id
        for chain, store in [('hemkop', '2354'), ('willys', 'other')]:
            with pytest.raises(ValueError):
                approved_catalogue_codes(session, first.snapshot_id, chain=chain, store_id=store)
    second = await collector.collect_area(FixtureWillysConnector(GOOD_CATALOG.replace(b'pasta-1', b'pasta-2')),
                                         GeographicArea(city="Lund"))
    with factory() as session:
        assert approved_catalogue_codes(session, second.snapshot_id, chain='willys', store_id='2354')[0] == ['pasta-2']
        with pytest.raises(ValueError):
            approved_catalogue_codes(session, first.snapshot_id, chain='willys', store_id='2354')
        row = session.scalar(select(CatalogSnapshotModel).where(CatalogSnapshotModel.id == second.snapshot_id))
        row.is_active = False
        with pytest.raises(ValueError):
            approved_catalogue_codes(session, second.snapshot_id, chain='willys', store_id='2354')
    engine.dispose()
