"""Replay current captured raw data through normal parser and promotion gates."""
import asyncio,sqlite3,sys,time,socket
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from job import configure,save
configure();P=Path('/work');probe=sys.argv[1]=='coop-probe'
database=P/('coop-probe.sqlite' if probe else 'grocery.sqlite')
if probe:
 assert not database.exists()
 with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as src,sqlite3.connect(database) as dst:src.backup(dst)
from grocery_data.app.storage import create_database_engine,create_session_factory
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import DatabaseReplayService
from grocery_data.app.connectors.coop.online_catalog_connector import CoopOnlineCatalogConnector
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
factory=create_session_factory(create_database_engine('sqlite:///'+str(database)))
service=DatabaseReplayService(factory,FilesystemRawSnapshotStore(P/'raw'))
identity='467c7656ad314cc5accd7833c8f90c9c'
def forbidden(*args,**kwargs):raise AssertionError('network during replay')
start=time.monotonic()
with RefreshRunLock(production_refresh_lock_path(database,P/'price-universes')):
 with patch.object(socket,'getaddrinfo',forbidden):
  result=asyncio.run(service.replay_snapshot(CoopOnlineCatalogConnector.for_replay(context_ids=('730400',)),identity,promote=True))
with sqlite3.connect(database) as db:
 times={sid:db.execute('select min(fetched_at),max(fetched_at),count(*) from raw_snapshots where catalog_snapshot_id=?',(sid,)).fetchone() for sid in [identity,result.replay_snapshot_id]}
 report={'result':asdict(result),'seconds':time.monotonic()-start,'raw_observation_ranges':times,'same_observations':len(set(times.values()))==1,'new_network_requests':0,'source':'actual 2026-09-27 collection reparsed; never re-observed','isolated_copy':probe}
 save('coop-probe' if probe else 'coop-replay',report);print(report)
