"""Every retained blocked recipe through actual candidate/basket qualification."""
import os
os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite',GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
import json
import time
from pathlib import Path
from datetime import datetime
from app.models import PlanRequest
from app.models.personal import MealSlot
from app.config import get_settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_nutrition import calculation_basis
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_candidate_generator import DeterministicRecipeCandidateGenerator
from app.services.recipe_preparation import content_hash

prepared=PreparedPriceUniverseArtifact.model_validate_json(Path('/work/universe.json').read_bytes()).restore()
request=PlanRequest.model_validate_json(Path('/evaluation/original-request.json').read_bytes())
request.purchase_planning_mode='estimated'
request.memberships={'willys':True,'lidl':True}
planner=PersonalPlanner(request,get_settings(),prepared,{'revision':0,'items':[],'reservations':{},'events':{}},now=datetime.fromisoformat('2026-09-24T21:16:35.494010+00:00'))
out=Path('/work/profile');out.mkdir(exist_ok=True)
import signal
from app.models.recipe import Recipe
baseline=json.loads(Path('/evaluation/search-baseline-cases.json').read_bytes())
baseline_diagnostics=json.loads(Path('/evaluation/search-baseline-diagnostics.json').read_bytes())
old_budget={s['recipes'][0]['name'] for s in baseline_diagnostics['nutrition_searches'] if s['budget_exhausted'] and not s['qualifying_basket_found']}
assert len(old_budget)==29
selected=[r for r in baseline if r['adapted']['name'] in old_budget]
result=[]
def deadline(*_): raise TimeoutError('reference search exceeded 30 seconds; no impossibility claim')
signal.signal(signal.SIGALRM,deadline)
for row in selected:
 planner.nutrition_search_limit=4096
 recipe=Recipe.model_validate(row['adapted']);meal=planner.meals[row['meal_type']]
 start=time.perf_counter();before=len(planner.diagnostics.nutrition_searches)
 record={'recipe':recipe.name,'version':recipe.preparation.version,'limit':4096,'deadline_seconds':30,
         'scope':'all 29 previous budget cases, final code and supplemented facts; not the old 20-case reference'}
 signal.alarm(30)
 try:
  cleaned=planner.clean_recipe(recipe,meal)
  b=planner.basket([MealSlot(id=row['meal_type']+'-1',day=1,meal_type=row['meal_type'],recipe=cleaned)],final=True)
  record.update(passed=True,cost=b['basket'].total,checks=b['checks'],audit=b['audit'].model_dump(mode='json'))
 except (ValueError,TimeoutError) as e:
  record.update(passed=False,stage=getattr(e,'stage',None),reason=str(e))
 finally:signal.alarm(0)
 record['seconds']=time.perf_counter()-start
 record['searches']=planner.diagnostics.nutrition_searches[before:]
 result.append(record)
 (out/'reference-current-29.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
 print(recipe.name,record['passed'],record['seconds'],flush=True)
