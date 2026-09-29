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

from app.models.recipe import Recipe
previous=json.loads(Path('/evaluation/prior-cases.json').read_bytes())
targets=[c for c in previous if c.get('stop',{}).get('code')=='NUTRITION_TARGET_NOT_MET']
result=[]
for budget in (256,4096):
 planner=PersonalPlanner(request,get_settings(),prepared,{"revision":0,"items":[],"reservations":{},"events":{}},now=datetime.fromisoformat("2026-09-24T21:16:35.494010+00:00"),nutrition_search_limit=budget)
 for case in targets:
  recipe=Recipe.model_validate(case['adapted'])
  slot=MealSlot(id=case['meal_type']+'-1',day=1,meal_type=case['meal_type'],recipe=recipe)
  start=time.perf_counter();mark=len(planner.diagnostics.nutrition_searches)
  row={'recipe':recipe.name,'budget':budget}
  try:
   value=planner.basket([slot],final=True);row.update(passed=True,cost=value['basket'].total)
  except ValueError as e:row.update(passed=False,reason=str(e),code=getattr(e,'code',None))
  row['seconds']=round(time.perf_counter()-start,4)
  row['searches']=planner.diagnostics.nutrition_searches[mark:]
  result.append(row)
  (out/'search-reference.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print('reference searches completed',len(result))
