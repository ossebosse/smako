"""Isolated optional-source fault injection and recovery from actual saved source bytes."""
import asyncio,json,shutil,socket,hashlib
from pathlib import Path
from datetime import datetime,UTC,timedelta
from unittest.mock import patch
from job import configure,save
configure()
from grocery_data.app.services import willys_flyer_job as job
from grocery_data.scripts.collect_willys_flyers import collect
from grocery_data.app.domain import RawBatch
P=Path('/work'); source=P/'willys-flyer'; target=P/'fault-probe-willys'
manifest=P/'price-universes/active/city-lund.json'
manifest_before=hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None
async def main():
 if not (source/'1281/source-state.json').exists():
  save('optional-lifecycle',{'status':'blocked','reason':'no current Willys flyer source state'});return
 state=json.loads((source/'1281/source-state.json').read_bytes())
 if not state.get('approved'):
  save('optional-lifecycle',{'status':'blocked','reason':'no currently qualified Willys flyer snapshot','inventory_status':state.get('inventory_status')});return
 shutil.copytree(source,target)
 env={'GROCERY_DATABASE_URL':'sqlite:////work/grocery.sqlite','WILLYS_FLYER_ROOT':str(target)}
 root,config=job.configuration(env);path=job.location(root,config);state=job.read(path)
 before=state['approved'];now=datetime.now(UTC)
 # Read saved municipality choice without code/enabled environment values.
 persisted=job.configuration(env)[1]
 idle=await job.run_source_job(environment=env,now=now)
 for row in state['selection']['stores']:
  if row['selected']:row['next_fetch_at']=(now-timedelta(seconds=1)).isoformat()
 job.write(path,state)
 calls=[]
 async def failure(*args,**kwargs):calls.append('injected_collect_failure');raise ConnectionError('explicit isolated fault injection')
 with patch('grocery_data.scripts.collect_willys_flyers.collect',failure):failed=await job.run_source_job(environment=env,now=now)
 retained=job.read(path)['approved']==before
 batches={}
 for identity in before:
  found=list(source.glob('1281/attempts/*/collection/'+identity+'/source.json'))
  if found:batches[identity]=RawBatch.model_validate_json(found[-1].read_bytes())
 async def replay(inventory,chosen,output):return await collect(inventory,chosen,output,raw_by_store=batches)
 with patch('grocery_data.scripts.collect_willys_flyers.collect',replay):
  recovered=await job.run_source_job(environment=env,now=now+timedelta(minutes=16))
 after=job.read(path)['approved']
 observations={k:[x['observed_at'] for x in v] for k,v in before.items()}
 after_observations={k:[x['observed_at'] for x in v] for k,v in after.items()}
 checks={}
 def denied(*args,**kwargs):raise AssertionError('network forbidden for local expiry inspection')
 with patch.object(socket,'getaddrinfo',denied):
  for label,clock in [('now',now),('campaign_day_after',now+timedelta(days=1)),('48h_expiry',now+timedelta(hours=49))]:checks[label]=job.source_plan(environment=env,now=clock)
 save('optional-lifecycle',{'main_publication_unchanged':manifest_before==(hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None),'scope':'separate copied source tree, real captured bytes; injected fetch failure and replay recovery, explicit future test clocks; not a new live collection','persisted_selection':persisted,'initial_run':idle,'failure':failed,'calls':calls,'approved_retained_after_failure':retained,'recovery':recovered,'observations_unchanged_by_replay':observations==after_observations,'before_observations':observations,'after_observations':after_observations,'plans':checks})
 print('optional lifecycle completed; observations unchanged',observations==after_observations)
asyncio.run(main())
