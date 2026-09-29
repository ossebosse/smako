"""Requalify genuine fresh relay evidence in municipal mode; zero retailer requests."""
import asyncio,json,sqlite3,time
from pathlib import Path
from grocery_data.app.domain import GeographicArea
from grocery_data.app.connectors.willys.connector import WillysConnector
from grocery_data.app.services.source_artifact import verify_source_artifact,OfflineWillysClient,export_source_artifact
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock
from grocery_data.app.storage import create_database_engine,create_schema,create_session_factory
ROOT=Path(__file__).parent
async def main():
    started=time.monotonic()
    receipt=json.loads(Path('D:/smako-local-relay/last-success.json').read_bytes())
    verified=verify_source_artifact(Path(receipt['artifact']))
    assert verified.artifact_sha256==receipt['sha256']
    target=ROOT/'lund-requalified';target.mkdir(exist_ok=False)
    db=target/'own.sqlite'
    with sqlite3.connect(db) as conn: conn.execute('pragma journal_mode=WAL')
    engine=create_database_engine('sqlite+pysqlite:///'+db.resolve().as_posix());create_schema(engine)
    factory=create_session_factory(engine);raw=FilesystemRawSnapshotStore(target/'raw')
    boundary=json.loads((ROOT/'boundary-1281.json').read_bytes())
    connector=WillysConnector(client=OfflineWillysClient(verified),municipality_boundary=boundary)
    area=GeographicArea(city='Lund',mode='municipality',municipality_code='1281')
    stores=connector.parse_stores(await connector.fetch_stores(area),['original:registry'],area)
    connector.allowed_store_ids=frozenset(s.external_id for s in stores)
    with RefreshRunLock(target/'operations.lock'):
        result=await GroceryCollector(factory,raw).collect_area(connector,area,auto_promote=False,scope_key=area.city.casefold())
        path=export_source_artifact(factory,raw,result.snapshot_id,target/'lund.smako-source',municipality_boundary=boundary,
            collection_started_at=verified.manifest.collection_started_at,collection_finished_at=verified.manifest.collection_finished_at,
            original_request_count=verified.manifest.request_count)
        v=verify_source_artifact(path)
    (target/'inventory.json').write_text(json.dumps(connector.municipality_inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    (target/'result.json').write_text(json.dumps({'reused_original_artifact_sha256':verified.artifact_sha256,'artifact':str(path),'sha256':v.artifact_sha256,
        'row_count':v.manifest.row_count,'product_count':v.manifest.product_count,'contexts':v.manifest.context_ids,
        'observed_from':v.manifest.observed_from.isoformat(),'observed_to':v.manifest.observed_to.isoformat(),
        'new_retailer_requests':0,'runtime_seconds':time.monotonic()-started,'source_observations_preserved':True},indent=2),encoding='utf-8')
    engine.dispose()
asyncio.run(main())
