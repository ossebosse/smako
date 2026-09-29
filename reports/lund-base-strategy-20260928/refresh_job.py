"""Existing runner/local rebuild, with a durable explicitly alternative policy."""
import os,sys,time,json,subprocess,threading,socket
from pathlib import Path
from datetime import datetime,UTC
from unittest.mock import patch
from job import configure,save
configure();P=Path('/work');mode=sys.argv[1]
from deploy.scripts import run_daily_refresh as runner
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
import uvicorn
from app.main import app
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8000,log_level='error',access_log=False))
thread=threading.Thread(target=server.run,daemon=True);thread.start();start=time.monotonic()
while not server.started:
 if not thread.is_alive() or time.monotonic()-start>180:raise RuntimeError('private startup failed')
 time.sleep(.1)
try:
 if mode=='restart':
  for k in ['COOP_MUNICIPALITY_CODE','LIDL_MUNICIPALITY_CODE','CITYGROSS_MUNICIPALITY_CODE','WILLYS_FLYER_MUNICIPALITY_CODE']:os.environ.pop(k,None)
 before=runner.demand_refresh_plan(now=datetime.now(UTC));save(mode+'-before',before)
 began=time.monotonic()
 if mode=='refresh':
  command=runner.build_refresh_command()+['--chain','citygross','--no-external-refresh']
  with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')) as lock:code=runner._run_locked(lock,started_at=datetime.now(UTC),command=command)
 else:code=None;command=None
 save(mode+'-result',{'code':code,'seconds':time.monotonic()-began,'command':command,'policy':json.loads((P/'policy.json').read_bytes()),'runner':json.loads((P/'runner.json').read_bytes()) if (P/'runner.json').exists() else None,'network':'actual due optional-source collection' if mode=='refresh' else 'network disabled at container boundary','test_clock':False})
 os.environ['DEMAND_REFRESH_ENABLED']='true'
 # Ordinary wrapper records published fingerprint; after successful first local rebuild,
 # first demand tick may itself rebuild on source-promotion pending state.
 plan=runner.demand_refresh_plan(now=datetime.now(UTC));save(mode+'-after',plan)
 if mode in {'second','restart'}:
  if mode=='second':
   original_command=runner.build_refresh_command
   runner.build_refresh_command=lambda: [sys.executable,'/evaluation/optional_fault_cli.py',*original_command()[3:]]
  tick_started=time.monotonic();result=runner.main();save(mode+'-demand-tick',{'exit':result,'seconds':time.monotonic()-tick_started,'status':json.loads((P/'runner.json').read_bytes())})
  plan=runner.demand_refresh_plan(now=datetime.now(UTC));save(mode+'-after-tick',plan)
  if not plan['work_due']:
   def denied(*a,**k):raise AssertionError('unexpected network on not_due')
   with patch.object(socket,'getaddrinfo',denied):result=runner.main()
   save(mode+'-not-due',{'exit':result,'status':json.loads((P/'runner.json').read_bytes()),'network_forbidden':True})
finally:server.should_exit=True;thread.join(30)
