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

before=json.loads((out/'before-edible-input-v1-public-exact-restored-original-plan.json').read_bytes())
original=json.loads(Path('/evaluation/original-request.json').read_bytes())
original['personal']['slots']=before['personal']['slots']
original['purchase_planning_mode']='exact'
request=PlanRequest.model_validate(original)
planner=PersonalPlanner(request,get_settings(),prepared,{'revision':0,'items':[],'reservations':{},'events':{}},now=datetime.fromisoformat('2026-09-24T21:16:35.494010+00:00'))
start=time.perf_counter()
result=planner.create()
value={'kind':'fixed previous complete menu through ordinary PersonalPlanner; diagnostic comparison, not free-search result',
 'request':request.model_dump(mode='json'),'seconds':time.perf_counter()-start,'plan':result.model_dump(mode='json'),
 'diagnostics':planner.diagnostics.snapshot()}
(out/'same-previous-menu.json').write_text(json.dumps(value,ensure_ascii=False,indent=2,default=str))
print('previous menu cost',result.optimized_basket.total)
