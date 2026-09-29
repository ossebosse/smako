"""Normal snapshot replay/promotion of today's captured schema-rejected full bases."""
import asyncio,sqlite3,sys,time,socket
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from job import configure,save
configure();P=Path('/work');probe=sys.argv[1]=='hemkop-probe'
database=P/('hemkop-probe.sqlite' if probe else 'grocery.sqlite')
if probe:
 assert not database.exists()
 with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as src,sqlite3.connect(database) as dst:src.backup(dst)
from grocery_data.app.storage import create_database_engine,create_session_factory
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.connectors.coop.online_catalog_connector import CoopOnlineCatalogConnector
from grocery_data.app.connectors.hemkop.connector import HemkopConnector
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
factory=create_session_factory(create_database_engine('sqlite:///'+str(database)))
service=DatabaseReplayService(factory,FilesystemRawSnapshotStore(P/'raw'))
with sqlite3.connect(database) as db:
 rows=db.execute("select id,chain,scope_key from catalog_snapshots where created_at>='2026-09-27' and state='rejected' and (scope_key like 'coop:online:%' or scope_key like 'lund:hemkop:%')").fetchall()
def forbidden(*args,**kwargs):raise AssertionError('network during replay')
reports=[]
with RefreshRunLock(production_refresh_lock_path(database,P/'price-universes')):
 for identity,chain,scope in rows:
  if probe and chain!='hemkop':continue
  store=scope.rsplit(':',1)[1]
  connector=CoopOnlineCatalogConnector.for_replay(context_ids=(store,)) if chain=='coop' else HemkopConnector.for_replay(store_external_ids=(store,))
  start=time.monotonic()
  with patch.object(socket,'getaddrinfo',forbidden):result=asyncio.run(service.replay_snapshot(connector,identity,promote=True))
  with sqlite3.connect(database) as db:
   times={sid:db.execute('select min(fetched_at),max(fetched_at),count(*) from raw_snapshots where catalog_snapshot_id=?',(sid,)).fetchone() for sid in [identity,result.replay_snapshot_id]}
  reports.append({'chain':chain,'store':store,'result':asdict(result),'seconds':time.monotonic()-start,'raw_observation_ranges':times,'same_observations':len(set(times.values()))==1,'new_network_requests':0,'source':'actual 2026-09-27 collection reparsed; never re-observed','isolated_copy':probe})
  save('hemkop-probe' if probe else 'base-replay',reports);print(chain,store,result.status,result.products_parsed,flush=True)
