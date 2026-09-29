"""Actual HTTP planner on the isolated published artifact, no replay clock."""
import json,os,subprocess,sys,time,hashlib
from pathlib import Path
from datetime import datetime,UTC
from job import configure,save
if '--serve' not in sys.argv:configure()
os.environ['PLAN_PREWARM_ENABLED']='false';P=Path('/work')
final_probe='final-http' in sys.argv
physical_probe=final_probe or 'physical-http' in sys.argv or os.getenv('SMAKO_TEST_SCOPE')=='physical-only'
result_name='http-results-final' if final_probe else 'http-results'
if physical_probe:
 P=P/'physical-probe';os.environ.update(SMAKO_TEST_SCOPE='physical-only',PRICE_UNIVERSE_CACHE_ROOT=str(P/'price-universes'),OWN_SOURCES_ONLY='true',PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS=','.join(json.loads((P/'scope-settings.json').read_bytes())['required_context_ids']))
 if '--serve' not in sys.argv:os.environ['PLAN_STORE_PATH']=str(P/'plans.sqlite')
 import job;job.P=P
if '--serve' in sys.argv:
 import uvicorn
 from contextlib import asynccontextmanager
 from collections import Counter
 from app.main import app
 from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
 from app.services.planning_diagnostics import PlanningDiagnostics
 original_snapshot=PlanningDiagnostics.snapshot
 def observed_snapshot(self):
  result=original_snapshot(self)
  save('planner-diagnostic-'+str(time.time_ns()),result)
  return result
 PlanningDiagnostics.snapshot=observed_snapshot
 original_lifespan=app.router.lifespan_context
 @asynccontextmanager
 async def observed_lifespan(application):
  async with original_lifespan(application):
   current=GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request('22350',{})
   products=[x.model_dump(mode='json') for x in current.universe.products]
   rows={}
   today=datetime.now(UTC).date()
   for x in current.universe.products:
    row=rows.setdefault(x.store_id,{'chain':x.chain,'store':x.store_name,'channel':str(x.price_context_type),'products':0,'date_valid_products':0,'purchase_terms':{},'source_observations':[],'source_snapshots':[],'active_offer_rows':0,'future_offer_rows':0,'expired_offer_rows':0})
    row['products']+=1
    for offer in x.offers:
     key='active_offer_rows' if offer.is_active(today) else ('future_offer_rows' if offer.valid_from and offer.valid_from>today else 'expired_offer_rows')
     row[key]+=1
    snapshot=x.source_provenance.source_snapshot_id if x.source_provenance else None
    if snapshot and snapshot not in row['source_snapshots']:row['source_snapshots'].append(snapshot)
    if x.price is not None or any(o.is_active(today) for o in x.offers):row['date_valid_products']+=1
    use=x.purchase_terms.usage if x.purchase_terms else 'legacy_contract_requires_quantity_resolution'
    row['purchase_terms'][use]=row['purchase_terms'].get(use,0)+1
    obs=x.source_provenance.source_observed_at if x.source_provenance else None
    if obs and obs.isoformat() not in row['source_observations']:row['source_observations'].append(obs.isoformat())
   import app.services.personal_planner as planner_module
   save('actual-serving-'+str(time.time_ns()),{'runtime_planner_file':planner_module.__file__,'runtime_planner_sha256':hashlib.sha256(Path(planner_module.__file__).read_bytes()).hexdigest(),'plan_store_path':os.environ['PLAN_STORE_PATH'],'universe_id':current.universe.universe_id,'products':len(products),'products_sha256':hashlib.sha256(json.dumps(products,sort_keys=True).encode()).hexdigest(),'stores':rows,'note':'Read from actual in-process serving manager after ordinary lifespan; purchase_terms usage is capability, not recipe or nutrition approval'})
   yield
 app.router.lifespan_context=observed_lifespan
 uvicorn.run(app,host='127.0.0.1',port=8000,log_level='warning',access_log=False)
 raise SystemExit
import httpx
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
f=PreparedUniverseArtifactStore(P/'price-universes').resolve_active_artifact('Lund',verify_hash=True)
if f is None:
 save('http-results',{'status':'blocked_before_startup','reason':'required active PriceUniverse artifact is unavailable','requests_not_run':['original-exact','original-estimated','plus-exact','plus-estimated','physical-only'],'price_clock':'actual current time, no historical substitution'})
 raise SystemExit
prepared=PreparedPriceUniverseArtifact.model_validate_json(f.read_bytes()).restore()
# Fixture completeness precedes any verdict about the base policy.
import sqlite3
snapshots={p.source_provenance.source_snapshot_id for p in prepared.universe.products
           if p.source_provenance and p.source_provenance.source_provider=='own'}
raw_checks={}
with sqlite3.connect('file:/work/grocery.sqlite?mode=ro',uri=True) as db:
 for snapshot in snapshots:
  for location,digest in db.execute('select distinct payload_location,payload_hash from raw_snapshots where catalog_snapshot_id=?',(snapshot,)):
   path=(Path('/work/raw')/location).resolve()
   assert path.is_relative_to(Path('/work/raw'))
   if location not in raw_checks:raw_checks[location]=path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==digest
save('http-raw-preflight',{'referenced_files':len(raw_checks),'all_valid':all(raw_checks.values()),'invalid':[k for k,v in raw_checks.items() if not v],'source_observations_unchanged':True})
assert raw_checks and all(raw_checks.values()), 'Incomplete retained source fixture; policy comparison must not start'
report={'started_at':datetime.now(UTC),'source_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'cases':[],'restarts':[]}
def start(rollback=False):
 env=dict(os.environ)
 if rollback:env.update(PYTHONPATH="/rollback/backend:/rollback:/srv/app/backend:/srv/app:/evaluation",PLAN_STORE_PATH=str(P/'rollback-plans.sqlite'))
 process=subprocess.Popen([sys.executable,__file__,'--serve'],env=env,stdout=(P/'app.log').open('a'),stderr=subprocess.STDOUT)
 for _ in range(1800):
  if process.poll() is not None:raise RuntimeError('isolated app startup failed; see app.log')
  try:
   if httpx.get('http://127.0.0.1:8000/ready',timeout=1).status_code==200:return process
  except httpx.TransportError:pass
  time.sleep(.1)
 process.terminate();process.wait(30);raise RuntimeError('startup timeout')
def stop(p):p.terminate();p.wait(30)
server=start()
try:
 with httpx.Client(base_url='http://127.0.0.1:8000',timeout=600) as client:
  from deploy.scripts.run_daily_refresh import _reload_runtime
  report['serving_reload']=_reload_runtime()
  request=json.loads(Path('/evaluation/original-request.json').read_bytes())
  physical=[s.store_id for s in prepared.stores if s.price_context_type=='physical_store' and s.price_semantics!='online_price' and any(p.store_id==s.store_id for p in prepared.universe.products) and all(p.price_context_type=='physical_store' and p.source_provenance and p.source_provenance.source_provider=='own' and p.source_provenance.source_channel=='offers' for p in prepared.universe.products if p.store_id==s.store_id)]
  report['physical_scope']={'store_ids':physical,'basis':'Only contexts whose actual products are verified OWN physical_store offers; excludes online_price and catalog-channel prices.'}
  matrix=[('physical','exact') ] if physical_probe else [('original','exact'),('original','estimated'),('plus','exact'),('plus','estimated') ]
  report['scope']='independent OWN-only physical-channel probe; not complete Lund base' if physical_probe else 'explicit alternative lund-own-five-base-20260928-v1; not original policy'
  for member,mode in ([] if final_probe else matrix):
   value=json.loads(json.dumps(request));value['purchase_planning_mode']=mode
   if member in {'plus','physical'}:value['memberships']={'willys':True,'lidl':True}
   if member=='physical':
    if not physical:
     report['cases'].append({'case':'physical','status':'blocked','reason':'no verified physical_store contexts in published artifact'});continue
    value['allowed_store_ids']=physical
   value['personal']['pantry_revision']=client.get('/api/personal/state').json()['revision']
   began=time.monotonic();response=client.post('/api/plans',json=value)
   row={'case':member+'-'+mode,'seconds':time.monotonic()-began,'http_status':response.status_code,'request':value,'response':response.json()}
   if response.status_code==201:
    identity=response.json().get('id',response.json().get('plan_id'));row['plan_id']=identity
    row['roundtrip_identical']=client.get('/api/plans/'+identity).json()==response.json()
   report['cases'].append(row);save(result_name,report);print(row['case'],row['http_status'],row['seconds'],flush=True)
  stop(server);server=start()
  for row in report['cases']:
   if row.get('plan_id'):report['restarts'].append({'id':row['plan_id'],'unchanged':client.get('/api/plans/'+row['plan_id']).json()==row['response']})
  save(result_name,report)
finally:stop(server)
