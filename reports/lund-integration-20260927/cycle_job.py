"""Ordinary local rebuild from freshly collected sources; no forced price refetch."""
import os,sys,json,time,threading,subprocess,socket
from pathlib import Path
from datetime import datetime,UTC
from unittest.mock import patch
from job import configure,save
configure();P=Path('/work');label=sys.argv[1]
if label=='cycle-restart':
 for k in ['COOP_MUNICIPAL_OFFERS_ENABLED','COOP_MUNICIPALITY_CODE','COOP_XTRA_OFFERS_ENABLED','CITYGROSS_MUNICIPAL_ENABLED','CITYGROSS_MUNICIPALITY_CODE','LIDL_MUNICIPAL_ENABLED','LIDL_MUNICIPALITY_CODE','WILLYS_FLYER_ENABLED','WILLYS_FLYER_MUNICIPALITY_CODE']:os.environ.pop(k,None)
from deploy.scripts import run_daily_refresh as runner
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
store=PreparedUniverseArtifactStore(P/'price-universes');f=store.resolve_active_artifact('Lund',verify_hash=True)
server=None;thread=None
if f is not None:
 import uvicorn
 from app.main import app
 server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8000,log_level='error',access_log=False))
 thread=threading.Thread(target=server.run,daemon=True);thread.start();end=time.monotonic()+180
 while not server.started:
  if not thread.is_alive() or time.monotonic()>end:raise RuntimeError('private ordinary app startup failed')
  time.sleep(.1)
try:
 start=time.monotonic();command=runner.build_refresh_command()+['--chain','citygross','--no-external-refresh']
 with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')) as lock:
  code=runner._run_locked(lock,started_at=datetime.now(UTC),command=command)
 report={'exit':code,'seconds':time.monotonic()-start,'command':command,'runner':json.loads((P/'runner.json').read_bytes()),'collection':'new source relay artifact import and ordinary source jobs; not forced full recrawl','test_clock':False}
 # Ordinary demand wrapper makes only its real due decision; no invented success.
 os.environ['DEMAND_REFRESH_ENABLED']='true'
 if server and label=='cycle-second':report['ordinary_demand_tick_exit']=runner.main()
 try:plan=runner.demand_refresh_plan(now=datetime.now(UTC))
 except (ValueError,FileNotFoundError,AttributeError) as exc:plan={'work_due':True,'reason':'no complete published artifact','error_type':type(exc).__name__}
 report['demand_plan']=plan
 if not plan['work_due']:
  def forbidden(*a,**kw):raise AssertionError('price network during not_due check')
  with patch.object(socket,'getaddrinfo',forbidden):report['not_due_exit']=runner.main()
 else:report['not_due']='not asserted: current state has work due'
 if server:
  from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
  p=GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request('22350',{})
  report['served_universe_id']=p.universe.universe_id;report['served_products']=len(p.universe.products)
 save(label,report);print(label,code,report['seconds'])
finally:
 if server:server.should_exit=True;thread.join(30)
