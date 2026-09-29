"""Private complete-base build and unchanged ordinary 15/20 planning."""
import asyncio,json,subprocess,sys,os,sqlite3,shutil,hashlib
from pathlib import Path
from datetime import datetime,UTC
from app.services.production_price_universe_build import build_city_price_universe
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
R=Path('/work')
def sources(root):
 inv=json.loads((root/'inventory.json').read_bytes())
 return [dict(database=root/s['database'],store_ids=[s['store_id']],snapshot_ids=[s['snapshot_id']],inventory=inv) for s in json.loads((root/'coverage.json').read_bytes())['stores'] if s['status']=='success']
async def main():
 db=R/'base/refreshed.sqlite'; pu=R/'base/price-universes'
 manifest=json.loads((pu/'external-provider-cache/active/city-lund.json').read_bytes())
 cache=pu/'external-provider-cache'/manifest['artifact_file']
 out=R/'profile';out.mkdir(exist_ok=True)
 # Populate private raw evidence from the frozen active snapshot references.
 # Production evidence is read-only; newly collected pages already live here.
 raw=R/'raw';copied=0;missing=[]
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
  rows=conn.execute("SELECT DISTINCT r.payload_location,r.payload_hash FROM raw_snapshots r JOIN source_products sp ON sp.raw_snapshot_id=r.id JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id WHERE cs.is_active=1 AND cs.state='promoted'").fetchall()
 for relative,digest in rows:
  target=(raw/relative).resolve();assert target.is_relative_to(raw)
  if target.exists():continue
  original=(Path('/srv/app/var/raw_snapshots')/relative).resolve();assert original.is_relative_to('/srv/app/var/raw_snapshots')
  if not original.exists():missing.append(relative);continue
  body=original.read_bytes();assert hashlib.sha256(body).hexdigest()==digest
  target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body);copied+=1
 (out/'raw-copy.json').write_text(json.dumps({'copied':copied,'missing':missing,'observation_times_unchanged':True}))
 os.environ.update(GROCERY_DATABASE_URL='sqlite:///'+str(db),GROCERY_RAW_SNAPSHOT_ROOT=str(raw))
 clock=json.loads((out/'before-inputs.json').read_bytes())['frozen_test_clock']
 for arm in ('after',):
  root=R/arm
  artifact=out/(arm+'-universe.json')
  with RefreshRunLock(production_refresh_lock_path(db,pu)):
   result=await build_city_price_universe(database=db,city='Lund',postal_code='22350',external_cache=cache,
     output=artifact,max_price_age_hours=48,willys_flyer_enabled=True,willys_flyer_sources=sources(root/'willys'),lidl_municipal_enabled=True,lidl_sources=sources(root/'lidl'))
  (out/(arm+'-build.json')).write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
  print(arm,'BUILT',flush=True)
  args=[sys.executable,'/evaluation/evaluate_1520_profile.py','--artifact',str(artifact),'--request','/evaluation/request.json','--output',str(out),'--label',arm,'--clock',clock,'--cases','restored-original','--universes',str(pu)]
  subprocess.run(args,check=True)
if __name__=='__main__':asyncio.run(main())
