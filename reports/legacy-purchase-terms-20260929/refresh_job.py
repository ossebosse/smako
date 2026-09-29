"""Ordinary import/build/publication/reload under lock; municipal sources use their ordinary due state."""
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from job import configure, save
configure()
P=Path('/work');mode=sys.argv[1]
from deploy.scripts import run_daily_refresh as runner
from grocery_data.app.services import coop_offer_job
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path
from serving import snapshot
import uvicorn
from app.main import app
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8000,log_level='error',access_log=False))
thread=threading.Thread(target=server.run,daemon=True);thread.start();start=time.monotonic()
while not server.started:
    if not thread.is_alive() or time.monotonic()-start>180:raise RuntimeError('private startup failed')
    time.sleep(.1)
try:
    save(mode+'-serving-before',snapshot())
    before=runner.demand_refresh_plan(now=datetime.now(UTC));save(mode+'-before',before)
    root,cfg=coop_offer_job.configuration();statepath=coop_offer_job.location(root,cfg)
    state_before=coop_offer_job.read(statepath)
    if mode == 'retry':
        # Explicit user-requested retry in this isolated copy only; preserve observations/history.
        with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')):
            retry_state=coop_offer_job.read(statepath);requested=[]
            for row in retry_state['selection']['stores']:
                if row['selected'] and row['concept'] != 'X:-tra':
                    requested.append({'store_id':row['store_id'],'prior_next_fetch_at':row.get('next_fetch_at')})
                    row['next_fetch_at']=datetime.now(UTC).isoformat()
            coop_offer_job.write(statepath,retry_state)
            save('explicit-private-retry',{'reason':'user-authorized bounded new collection after corrected schema review','stores':requested,'source_observations_unchanged':True,'production_or_scheduler_changes':False})
    if mode in {'refresh','retry'}:
        plan=coop_offer_job.source_plan()
        assert not plan['inventory_due'], 'bounded collection requires valid retained municipal inventory'
        expected={r['store_id'] for r in state_before['selection']['stores'] if r['selected'] and r['concept'] != 'X:-tra'}
        assert set(plan['due_store_ids']) == expected, plan['due_store_ids']
    if mode in {'fault','fault-final','second'}:os.environ['HEMKOP_MUNICIPAL_PROBE']='fault'
    command=runner.build_refresh_command()+['--chain','citygross','--no-external-refresh']
    command=[sys.executable,'/evaluation/scoped_cli.py',*command[3:]]
    started=time.monotonic()
    with RefreshRunLock(production_refresh_lock_path(P/'grocery.sqlite',P/'price-universes')) as lock:
        code=runner._run_locked(lock,started_at=datetime.now(UTC),command=command)
    result={'exit':code,'seconds':time.monotonic()-started,'command':command,
        'runner':json.loads((P/'runner.json').read_bytes()),'test_clock':False,
        'scope':'ordinary CLI with unrelated optional collection hooks explicitly deferred; same provider imports and policy',
        'coop_state_before':{'approved':state_before.get('approved'),'selection':state_before.get('selection')},
        'coop_state_after':coop_offer_job.read(statepath)}
    save(mode+'-result',result);save(mode+'-serving-after',snapshot())
    save(mode+'-after',runner.demand_refresh_plan(now=datetime.now(UTC)))
    print(mode,'exit',code,'seconds',result['seconds'],flush=True)
    assert code in (0,2)
finally:
    server.should_exit=True;thread.join(30)
