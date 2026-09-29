"""Inspect retained real products and facts, without price or nutrition requests."""
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

os.environ.update(GROCERY_DATABASE_URL='sqlite:////work/base/refreshed.sqlite', GROCERY_RAW_SNAPSHOT_ROOT='/work/raw')
from app.config import get_settings
from app.models import PlanRequest
from app.services.personal_planner import PersonalPlanner
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

prepared=PreparedPriceUniverseArtifact.model_validate_json(Path('/work/universe.json').read_bytes()).restore()
request=PlanRequest.model_validate_json(Path('/evaluation/original-request.json').read_bytes())
request.purchase_planning_mode='estimated';request.memberships={'willys':True,'lidl':True}
planner=PersonalPlanner(request,get_settings(),prepared,{'revision':0,'items':[],'reservations':{},'events':{}},now=datetime.fromisoformat('2026-09-24T21:16:35.494010+00:00'))
rows=[]
for p in prepared.universe.products:
    if any(t in p.name.casefold() for t in ('tofu','lax','vitlök','protein','tortilla')):
        fact=planner.source_facts(p)
        rows.append({'product':p.model_dump(mode='json'),'facts':asdict(fact) if fact else None})
Path('/work/profile/source-candidates.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str),encoding='utf8')
print('inspected',len(rows),'retained products')
