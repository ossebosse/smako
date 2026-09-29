"""One controlled resume after the proven legacy two-store request-budget stop.
Uses only complete original store batches; incomplete pages are never promoted.
Calls the ordinary source_cli.collect with the final implementation and policy.
"""
import asyncio,json,time
from pathlib import Path
from types import SimpleNamespace
from grocery_data import source_cli
from grocery_data.app.domain import RawBatch,RawFetch,GeographicArea,TransportMetrics
from grocery_data.app.services.source_artifact import _source_stores,_willys_completion
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine,create_session_factory,session_scope
from grocery_data.app.storage.models import RawSnapshotModel
from sqlalchemy import select
ROOT=Path(__file__).parent
async def main():
 old=next((ROOT/'malmo-relay/runs').iterdir());metrics_path=old/'collection-metrics.json'
 # This background evidence job never retries an access/schema/quality failure.
 while not metrics_path.exists():await asyncio.sleep(5)
 metrics=json.loads(metrics_path.read_bytes())
 if metrics['status']=='complete':return
 assert metrics['requests']==1500 and metrics['http_errors']==0 and metrics['challenges']==0, 'only proven legacy budget exhaustion authorizes this resume'
 engine=create_database_engine('sqlite+pysqlite:///'+(old/'candidate.sqlite3').resolve().as_posix())
 factory=create_session_factory(engine);raw=FilesystemRawSnapshotStore(old/'raw')
 with session_scope(factory) as session:
  rows=list(session.scalars(select(RawSnapshotModel).order_by(RawSnapshotModel.fetched_at,RawSnapshotModel.id)))
  docs=tuple(RawFetch(chain=r.chain,store_external_id=r.store_external_id,kind=r.kind,method=r.method,url=r.url,query=r.query,
   fetched_at=r.fetched_at,http_status=r.http_status,content_type=r.content_type,payload=raw.load(DatabaseReplayService._stored(r)),
   connector_version=r.connector_version,page_number=r.page_number) for r in rows)
 engine.dispose()
 boundary=json.loads((ROOT/'boundary-1280.json').read_bytes());area=GeographicArea(city='Malmö',mode='municipality',municipality_code='1280')
 discovery=tuple(d for d in docs if d.kind=='stores');stores=_source_stores(discovery,area,boundary);cached={};statuses={}
 for store in stores:
  scoped=tuple(d for d in docs if d.store_external_id==store.external_id)
  try:completion=_willys_completion(discovery+scoped,area=area,boundary=boundary,contexts=(store.external_id,))[store.external_id]
  except ValueError:
   statuses[store.external_id]='incomplete_or_not_yet_collected';continue
  cached[store.external_id]=(store,RawBatch(chain='willys',documents=scoped,catalog_completion=completion,transport=TransportMetrics()))
  statuses[store.external_id]='reused_complete_original_observations'
 assert cached, 'nothing qualified to resume'
 original=source_cli.WillysClient
 class ResumeClient(original):
  async def fetch_catalog(self,store):
   if store.external_id in cached:
    prior,batch=cached[store.external_id]
    fields=['external_id','address','postal_code','city','latitude','longitude','online_shopping']
    assert all(getattr(store,f)==getattr(prior,f) for f in fields), 'store evidence changed; do not reuse'
    return batch
   return await super().fetch_catalog(store)
 source_cli.WillysClient=ResumeClient
 original_export=source_cli.export_source_artifact
 def export(*args,**kwargs):
  kwargs['original_request_count']+=metrics['requests']
  kwargs['collection_started_at']=min(d.fetched_at for d in docs)
  return original_export(*args,**kwargs)
 source_cli.export_source_artifact=export
 result=await source_cli.collect(SimpleNamespace(workspace=ROOT/'malmo-final-relay',municipality='1280'))
 (ROOT/'malmo-resume-result.json').write_text(json.dumps({'trigger':'legacy two-store request budget; final code computes municipal budget','reused':statuses,'original_requests':metrics['requests'],'result':result},default=str,ensure_ascii=False,indent=2),encoding='utf-8')
asyncio.run(main())
