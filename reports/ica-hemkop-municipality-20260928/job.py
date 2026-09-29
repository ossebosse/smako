import os,sys,json,secrets,sqlite3,subprocess,time
from pathlib import Path
from datetime import datetime,UTC
P=Path('/work')
def configure():
 os.environ.pop('OPENAI_API_KEY',None)
 os.environ.update(APP_ENV='development',BUILD_ID='ica-hemkop-municipality-20260928-v8',PUBLIC_BASE_URL='http://127.0.0.1:8000',SECRET_KEY=secrets.token_hex(32),BETA_ADMIN_TOKEN=secrets.token_hex(32),GROCERY_DATABASE_URL='sqlite:////work/grocery.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw',PLAN_STORE_PATH='/work/plans.sqlite',PRICE_UNIVERSE_CACHE_ROOT='/work/price-universes',PRICE_UNIVERSE_REQUIRED='true',PRICE_UNIVERSE_PREWARM_ENABLED='false',REFRESH_CITY='Lund',REFRESH_POSTAL_CODE='22350',REFRESH_REPORT_DIR='/work/reports',REFRESH_RUNNER_STATUS_PATH='/work/runner.json',DEMAND_REFRESH_STATE_PATH='/work/demand.json',DEMAND_REFRESH_ENABLED='false',INTERNAL_APP_BASE_URL='http://127.0.0.1:8000',COOP_ALLOW_FULL_CRAWL='true',COOP_ONLINE_CONTEXT_IDS='730400',COOP_MUNICIPAL_OFFERS_ENABLED='true',COOP_MUNICIPALITY_CODE='1281',COOP_MUNICIPAL_OFFERS_ROOT='/work/coop-municipal',COOP_XTRA_OFFERS_ENABLED='true',CITYGROSS_MUNICIPAL_ENABLED='true',CITYGROSS_MUNICIPALITY_CODE='1281',CITYGROSS_MUNICIPAL_ROOT='/work/citygross-municipal',LIDL_MUNICIPAL_ENABLED='true',LIDL_MUNICIPALITY_CODE='1281',LIDL_MUNICIPAL_ROOT='/work/lidl-municipal',WILLYS_FLYER_ENABLED='true',WILLYS_FLYER_MUNICIPALITY_CODE='1281',WILLYS_FLYER_ROOT='/work/willys-flyer',WILLYS_MUNICIPAL_CONFIG='/work/willys-config.json',WILLYS_COLLECTION_LOCATION='LOCAL_RELAY',SOURCE_RELAY_INBOX='/work/raw/source-inbox/willys',REFRESH_MUNICIPALITY_CODE='1281',HEMKOP_MUNICIPAL_OFFERS_ENABLED='true',HEMKOP_MUNICIPAL_ROOT='/work/hemkop-municipal',ICA_STRUCTURED_OFFERS_ENABLED='true',ICA_STRUCTURED_OFFERS_ROOT='/work/ica-structured',ICA_AREA_OFFER_CANDIDATES_ENABLED='false',ICA_FLYER_PAID_ENABLED='false',ICA_FLYER_VISUAL_COMMAND_JSON='',OWN_SOURCES_ONLY='false',ALLOW_PROVIDER_FALLBACK='false',ALLOW_MOCK_FALLBACK='false',MAX_PRICE_AGE_HOURS='48',PRICE_AGE_WARNING_HOURS='36')
 policy=json.loads((P/'policy.json').read_bytes());assert policy['id']=='lund-own-five-base-20260928-v1'
 os.environ.update(OWN_SOURCES_ONLY='true',PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS=','.join(policy['required_context_ids']))
 # Credentials are inherited; all mutable runtime destinations above are private.
 for k in ['COOP_MUNICIPAL_INVENTORY','CITYGROSS_MUNICIPAL_INVENTORY','LIDL_MUNICIPAL_INVENTORY']:os.environ.pop(k,None)
def save(name,data):(P/(name+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2,default=str))
def main():
 configure();mode=sys.argv[1]
 if mode=='config':
  save('effective-config',{k:os.getenv(k) for k in ['HEMKOP_ALLOW_FULL_CRAWL','HEMKOP_STORE_EXTERNAL_IDS','COOP_ALLOW_FULL_CRAWL','COOP_ONLINE_CONTEXT_IDS','PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS','WILLYS_COLLECTION_LOCATION','MAX_PRICE_AGE_HOURS','PRICE_AGE_WARNING_HOURS','ICA_STRUCTURED_OFFERS_ENABLED','DEMAND_REFRESH_ENABLED']});print('sanitized private configuration saved')
 elif mode=='initialize':
  assert not (P/'grocery.sqlite').exists()
  with sqlite3.connect('file:/seed/refreshed.sqlite?mode=ro',uri=True) as src,sqlite3.connect(P/'grocery.sqlite') as dst:src.backup(dst)
  (P/'willys-config.json').write_text(json.dumps({'schema':'willys-municipal-build-v1','build_scopes':{'22350':'1281'}}))
  (P/'raw/source-inbox/willys').mkdir(parents=True)
  result=subprocess.run([sys.executable,'-m','pip','check'],capture_output=True,text=True)
  save('dependencies',{'exit':result.returncode,'output':result.stdout,'versions':subprocess.check_output([sys.executable,'-m','pip','list','--format=json'],text=True),'seed':'historical source context mappings and snapshots only; no active PriceUniverse copied','initialized_at':datetime.now(UTC)})
  from deploy.scripts.run_daily_refresh import build_refresh_command
  result=subprocess.run(build_refresh_command()+['--dry-run'],capture_output=True,text=True);save('dry-run',{'exit':result.returncode,'output':result.stdout,'error':result.stderr[-1000:]});print('initialized',result.returncode)
 elif mode=='refresh':
  started=time.monotonic()
  with (P/'refresh.log').open('w') as log:r=subprocess.run([sys.executable,'deploy/scripts/run_daily_refresh.py'],stdout=log,stderr=log,timeout=7200)
  save('refresh-result',{'exit':r.returncode,'seconds':time.monotonic()-started,'finished_at':datetime.now(UTC),'network':'actual network collection, no replay or test clock'});print('refresh exit',r.returncode)
 elif mode=='status':
  from deploy.scripts.run_daily_refresh import demand_refresh_plan
  save('demand-status',demand_refresh_plan(now=datetime.now(UTC)));print('status saved')
if __name__=='__main__':main()
