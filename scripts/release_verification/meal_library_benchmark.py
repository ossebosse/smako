"""Real isolated fresh planner computations; not completed-menu cache reads."""
import hashlib
import json
import resource
import sys
import time
from datetime import datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

label,case,cache_mode=sys.argv[1:4]
root=Path('/results')/label;root.mkdir(exist_ok=True)
freeze=json.loads(Path('/inputs/freeze.json').read_text())
clock=datetime.fromisoformat(freeze['frozen_at_utc'])
raw=Path('/inputs/universe.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==freeze['artifact_sha256']
t0=time.perf_counter();prepared=PreparedPriceUniverseArtifact.model_validate_json(raw).restore();universe_seconds=time.perf_counter()-t0
del raw
request_data=json.loads(Path('/evaluation/requests.json').read_text())[case]
request=PlanRequest.model_validate(request_data)
settings=Settings(price_provider='own',complete_recipes_enabled=True)
state={'revision':0,'items':[],'reservations':{},'events':{}}
rows=[]
for i in range(4 if cache_mode=='warm' else 1):
 start=time.perf_counter();facts=load_retained_facts(prepared);fact_seconds=time.perf_counter()-start
 planning_start=time.perf_counter()
 planner=PersonalPlanner(request,settings,prepared,state,facts=facts,now=clock)
 try:
  result=planner.create()
  payload=result.model_dump(mode='json')
  (root/f'{case}-{cache_mode}-{i}-plan.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
  row={'outcome':'PASS','paid':result.optimized_basket.total,'portions':result.portions,'recipes':[r.name for r in result.recipes],'check_timings':result.personal.checks.get('timings_seconds')}
 except ValueError as e:
  row={'outcome':'FAIL','reason':str(e),'diagnostics':getattr(e,'diagnostics',None)}
 row.update(case=case,cache_mode=cache_mode,iteration=i,facts_seconds=fact_seconds,planner_seconds=time.perf_counter()-planning_start,wall_seconds=time.perf_counter()-start,universe_seconds=universe_seconds,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
 try:
  from app.services.meal_prepared_artifacts import STATS
  row['preparation_stats']=dict(STATS)
 except ImportError:pass
 rows.append(row);print(json.dumps({k:v for k,v in row.items() if k not in {'diagnostics','check_timings','recipes'} }),flush=True)
 (root/f'{case}-{cache_mode}-timings.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
 if row['outcome']=='FAIL':break
