"""Candidate image with real mounted source data and disabled networking."""
import json,time
from collections import Counter
from pathlib import Path
from app.config import get_settings
from app.models import PlanRequest,PlanResponse
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
root=Path('/srv/app/var/price_universes')
manifest=json.loads((root/'active/city-lund.json').read_bytes())
prepared=PreparedPriceUniverseArtifact.model_validate_json((root/manifest['artifact_file']).read_bytes()).restore()
frozen=json.loads(Path('/evidence/verified-frozen.json').read_bytes())
output={'network':'none','price_version':manifest['universe_id'],'products':len(prepared.universe.products),'chains':dict(Counter(p.chain for p in prepared.universe.products)), 'cases':{}}
for key in ['B5','A3_original','D_strict','E3_original','C5']:
 req=PlanRequest.model_validate(frozen['cases'][key]['settings'])
 inventory={'revision':0,'items':frozen['cases'][key]['stock_before'],'reservations':{},'events':{}}
 p=PersonalPlanner(req,get_settings(),prepared,inventory)
 start=time.perf_counter()
 try:
  plan=p.create()
  output['cases'][key]={'status':'PASS','plan':plan.model_dump(mode='json')}
 except PolicyConflict as e:output['cases'][key]={'status':e.code,'message':str(e),'diagnostics':e.diagnostics}
 output['cases'][key]['seconds']=time.perf_counter()-start
 Path('/evidence/runtime.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
 print(json.dumps({'case':key,'status':output['cases'][key]['status'],'cost':output['cases'][key].get('plan',{}).get('optimized_basket',{}).get('total'),'price_version':manifest['universe_id'],'products':output['products'],'chains':output['chains']}),flush=True)
