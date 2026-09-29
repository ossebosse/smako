"""Ordinary private job, durable sources/configuration, no external network."""
import hashlib,json,os,secrets,shutil,sqlite3,subprocess,sys,threading,time
from datetime import UTC,datetime,timedelta
from pathlib import Path
ROOT=Path('/work/lifecycle')
def save(mode,value):
 Path('/work/result-'+mode+'.json').write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
def copy_active(source,target):
 m=json.loads((source/'active/city-lund.json').read_bytes());data=(source/m['artifact_file']).read_bytes()
 assert hashlib.sha256(data).hexdigest()==m['artifact_sha256']
 p=target/m['artifact_file'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 (target/'active').mkdir(exist_ok=True);shutil.copyfile(source/'active/city-lund.json',target/'active/city-lund.json')
def configure():
 os.environ.update(APP_ENV='development',PUBLIC_BASE_URL='http://127.0.0.1:8000',SECRET_KEY=secrets.token_hex(32),BETA_ADMIN_TOKEN=secrets.token_hex(32),
  PLAN_STORE_PATH=str(ROOT/'plans.sqlite'),GROCERY_DATABASE_URL='sqlite+pysqlite:///'+str(ROOT/'grocery.sqlite'),GROCERY_RAW_SNAPSHOT_ROOT=str(ROOT/'raw'),
  PRICE_UNIVERSE_CACHE_ROOT=str(ROOT/'price-universes'),PRICE_UNIVERSE_PREWARM_ENABLED='false',INTERNAL_APP_BASE_URL='http://127.0.0.1:8000',
  REFRESH_CITY='Lund',REFRESH_POSTAL_CODE='22350',REFRESH_REPORT_DIR=str(ROOT/'reports'),REFRESH_RUNNER_STATUS_PATH=str(ROOT/'runner-status.json'),
  DEMAND_REFRESH_STATE_PATH=str(ROOT/'demand.json'),DEMAND_REFRESH_ENABLED='true',COOP_MUNICIPAL_OFFERS_ROOT=str(ROOT/'municipal'),
  COOP_MUNICIPAL_OFFERS_ENABLED='true',COOP_XTRA_OFFERS_ENABLED='false',COOP_ALLOW_FULL_CRAWL='true',COOP_ONLINE_CONTEXT_IDS='730400',ICA_AREA_OFFER_CANDIDATES_ENABLED='false',ICA_STRUCTURED_OFFERS_ENABLED='false',
  ICA_FLYER_PAID_ENABLED='false',ICA_FLYER_VISUAL_COMMAND_JSON='',WILLYS_COLLECTION_LOCATION='LOCAL_RELAY',WILLYS_MUNICIPAL_CONFIG=str(ROOT/'willys-config.json'),
  SOURCE_RELAY_INBOX=str(ROOT/'raw/source-inbox/willys'))
def initialize():
 ROOT.mkdir(exist_ok=False)
 previous=Path('/previous/lifecycle')
 with sqlite3.connect(previous.joinpath('grocery.sqlite').as_uri()+'?mode=ro',uri=True) as src:
  with sqlite3.connect(ROOT/'grocery.sqlite') as dst:src.backup(dst)
 copy_active(previous/'price-universes',ROOT/'price-universes')
 copy_active(previous/'price-universes/external-provider-cache',ROOT/'price-universes/external-provider-cache')
 shutil.copytree(previous/'municipal',ROOT/'municipal')
 (ROOT/'willys-config.json').write_text(json.dumps({'schema':'willys-municipal-build-v1','build_scopes':{'22350':'1281','21120':'1280'}}))
 incoming=ROOT/'raw/source-inbox/willys';incoming.mkdir(parents=True)
 for p in Path('/incoming').glob('*.smako-source'):shutil.copyfile(p,incoming/p.name)
 save('initialize',{'time':datetime.now(UTC),'base_source':'hash-stable previous complete test database; no search projection','production_activation':False})
def run(mode):
 if mode=='initialize':initialize();return
 configure()
 if mode.startswith('malmo-build'):
  import asyncio
  from grocery_data import __main__ as cli
  from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
  from grocery_data.app.services.source_artifact import import_source_inbox
  from grocery_data.app.storage import create_database_engine,create_session_factory
  from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
  incoming=ROOT/'raw/source-inbox/willys'
  for p in Path('/incoming').glob('*.smako-source'):
   if not (incoming/'processed'/p.name).exists():shutil.copyfile(p,incoming/p.name)
  engine=create_database_engine(os.environ['GROCERY_DATABASE_URL'])
  with RefreshRunLock(production_refresh_lock_path(ROOT/'grocery.sqlite',ROOT/'price-universes')):
   imported=asyncio.run(import_source_inbox(create_session_factory(engine),FilesystemRawSnapshotStore(ROOT/'raw'),incoming))
   started=time.monotonic()
   result=asyncio.run(cli._build_production_price_universe(database=ROOT/'grocery.sqlite',city='Malmö',postal_code='21120',external_cache=None,output=ROOT/'malmo.json',max_price_age_hours=48))
   from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
   prepared=PreparedPriceUniverseArtifact.model_validate_json((ROOT/'malmo.json').read_bytes()).restore()
   products=[p.model_dump(mode='json') for p in prepared.universe.products if p.chain=='willys']
   from collections import Counter
   with sqlite3.connect(ROOT/'grocery.sqlite') as db:
    own=db.execute("SELECT p.store_external_id,count(*),min(p.observed_at),max(p.observed_at) FROM products p JOIN catalog_snapshots s ON s.id=p.catalog_snapshot_id WHERE s.is_active=1 AND s.chain='willys' GROUP BY 1").fetchall()
   save(mode,{'imports':imported,'build':result,'runtime_seconds':time.monotonic()-started,'scope':'OWN-only municipality candidate; no Malmö Primat baseline asserted',
    'willys_products':len(products),'product_signature':hashlib.sha256(json.dumps(products,sort_keys=True).encode()).hexdigest(),
    'product_store_counts':dict(Counter(str(p.get('store_id')) for p in products)),'own':own,'stores':[s.model_dump(mode='json') for s in prepared.stores],
    'config':json.loads((ROOT/'willys-config.json').read_bytes()),'sample_products':products[:2]})
  engine.dispose();return
 from deploy.scripts import run_daily_refresh as runner
 from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
 from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
 from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
 if mode=='not-due':
  plan=runner.demand_refresh_plan(now=datetime.now(UTC))
  save(mode,{'plan':plan});return
 import httpx,uvicorn
 from app import main as application
 server=uvicorn.Server(uvicorn.Config(application.app,host='127.0.0.1',port=8000,log_level='error',access_log=False))
 thread=threading.Thread(target=server.run,daemon=True);thread.start();deadline=time.monotonic()+180
 while not server.started:
  if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('private app startup failed')
  time.sleep(.1)
 try:
  started=time.monotonic()
  command=runner.build_refresh_command()+['--chain','citygross','--no-external-refresh']
  if mode=='cycle-final-a':
   for p in Path('/incoming').glob('*.smako-source'):shutil.copyfile(p,ROOT/'raw/source-inbox/willys'/p.name)
  original=subprocess.run
  def quiet(command,**kwargs):
   if 'grocery_data' in command:kwargs.update(stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   return original(command,**kwargs)
  subprocess.run=quiet
  with RefreshRunLock(production_refresh_lock_path(ROOT/'grocery.sqlite',ROOT/'price-universes')) as lock:
   code=runner._run_locked(lock,started_at=datetime.now(UTC),command=command,run_kind='daily_refresh')
  store=PreparedUniverseArtifactStore(ROOT/'price-universes');path=store.resolve_active_artifact('Lund',verify_hash=True)
  prepared=PreparedPriceUniverseArtifact.model_validate_json(path.read_bytes()).restore()
  products=[p.model_dump(mode='json') for p in prepared.universe.products if p.chain=='willys']
  signature=hashlib.sha256(json.dumps(products,sort_keys=True).encode()).hexdigest()
  result={'exit':code,'runtime_seconds':time.monotonic()-started,'universe_id':prepared.universe.universe_id,'willys_products':len(products),'product_signature':signature,
   'coop_products':sum(p.chain=='coop' and p.coverage=='offers_only' for p in prepared.universe.products),'runner':json.loads((ROOT/'runner-status.json').read_bytes()),
   'config':json.loads((ROOT/'willys-config.json').read_bytes()),'network':'Docker network none; loopback private app only','production_activation':False}
  with sqlite3.connect(ROOT/'grocery.sqlite') as db:
   result['own']=db.execute("SELECT p.store_external_id,count(*),min(p.observed_at),max(p.observed_at) FROM products p JOIN catalog_snapshots s ON s.id=p.catalog_snapshot_id WHERE s.is_active=1 AND s.chain='willys' GROUP BY 1").fetchall()
  with httpx.Client(base_url='http://127.0.0.1:8000') as c:result.update(health=c.get('/health').status_code,ready=c.get('/ready').status_code)
  future=datetime.now(UTC)+timedelta(hours=49)
  report_files=sorted((ROOT/'reports').rglob('*.json'),key=lambda p:p.stat().st_mtime)
  result['aggregate_report_files']=[str(p) for p in report_files[-3:]]
  if report_files:result['aggregate_report']=json.loads(report_files[-1].read_bytes())
  result['explicit_future_test_clock']=future
  result['status_after_49h']=prepared.status(now=future).model_dump(mode='json')
  save(mode,result)
  print(json.dumps({k:result[k] for k in ['exit','runtime_seconds','universe_id','willys_products','coop_products','product_signature','health','ready']}))
 finally:
  server.should_exit=True;thread.join(timeout=30)
if __name__=='__main__':
 try:run(sys.argv[1])
 except Exception as e:
  import traceback
  save('error-'+sys.argv[1],{'error':type(e).__name__,'trace':traceback.format_exc()});raise
