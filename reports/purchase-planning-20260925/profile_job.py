"""Private complete-base build and unchanged ordinary 15/20 planning."""
import asyncio,json,subprocess,sys,os,sqlite3,shutil,hashlib
from pathlib import Path
from datetime import datetime,UTC
from unittest.mock import patch
from contextlib import ExitStack
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
 clock='2026-09-24T21:16:35.494010+00:00'
 class FrozenDatetime(datetime):
  @classmethod
  def now(cls,tz=None):
   value=datetime.fromisoformat(clock)
   return value.astimezone(tz) if tz else value.replace(tzinfo=None)
 for arm in ('before', 'after'):
  root=R/arm
  artifact=out/(arm+'-universe.json')
  with ExitStack() as stack:
   for module in ('app.services.production_price_universe_build','app.providers.federated','app.providers.own','grocery_data.app.api.common','grocery_data.app.api.catalog','app.providers.willys_flyers','app.providers.lidl_municipality'):
    stack.enter_context(patch(module+'.datetime',FrozenDatetime))
   stack.enter_context(RefreshRunLock(production_refresh_lock_path(db,pu)))
   result=await build_city_price_universe(database=db,city='Lund',postal_code='22350',external_cache=cache,
     output=artifact,max_price_age_hours=48,willys_flyer_enabled=True,willys_flyer_sources=sources(root/'willys'),lidl_municipal_enabled=True,lidl_sources=sources(root/'lidl'))
  (out/(arm+'-build.json')).write_text(json.dumps(result,default=str,ensure_ascii=False,indent=2))
  required=set(json.loads(Path('/evaluation/required-contexts.json').read_bytes()))
  built=json.loads(artifact.read_bytes())
  actual={s['store_id'] for s in built['stores']}
  assert required <= actual, {'missing_required_base_contexts':sorted(required-actual)}
  print(arm,'BUILT',flush=True)
  for mode in ('exact','estimated'):
   request=json.loads(Path('/evaluation/request.json').read_bytes());request['purchase_planning_mode']=mode
   label=arm+'-'+mode
   requestfile=out/(label+'-request.json');requestfile.write_text(json.dumps(request))
   args=[sys.executable,'/evaluation/evaluate_1520_profile.py','--artifact',str(artifact),'--request',str(requestfile),'--output',str(out),'--label',label,'--clock',clock,'--cases','restored-original','--universes',str(pu)]
   subprocess.run(args,check=True)
if __name__=='__main__':asyncio.run(main())
