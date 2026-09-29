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

import dataclasses,re,sqlite3,hashlib,sys
from app.models.personal import TasteProfile
from app.services.personal_source_facts import raw_product
terms=('rödlök','röd lök','crème','creme','kikärt','bönor','bön','ägg','blandfärs')
selected={p.product_id:p for p in prepared.universe.products if any(t in p.name.casefold() for t in terms)}
rows=[]
with sqlite3.connect('file:/work/base/refreshed.sqlite?mode=ro',uri=True) as db:
 db.row_factory=sqlite3.Row
 rawrows={}
 for row in db.execute('SELECT p.id,p.raw_reference,r.payload_location,r.payload_hash FROM products p JOIN raw_snapshots r ON r.id=p.raw_snapshot_id'):
  if row['id'] not in selected:continue
  path=Path('/work/raw')/row['payload_location'];b=path.read_bytes();assert hashlib.sha256(b).hexdigest()==row['payload_hash']
  rawrows[row['id']]={'snapshot_hash':row['payload_hash'],'raw':raw_product(json.loads(b),row['raw_reference'])}
 for p in selected.values():
  fact=planner.source_facts(p)
  rows.append({'product':p.model_dump(mode='json'),'facts':dataclasses.asdict(fact) if fact else None,'retained':rawrows.get(p.product_id)})
queries=[]
for name in ('rödlök','crème fraiche','svarta bönor','bönor','kikärtor','kidneybönor','ägg','blandfärs'):
 for unit in (('g','ml') if name=='crème fraiche' else ('g',)):
  result={'name':name,'unit':unit}
  try:result['accepted']=[c.model_dump(mode='json') for i,c in planner.resolve(name,100,unit,profile=TasteProfile())]
  except ValueError as e:result['error']=str(e)
  result['trace']=[{'product':prepared.universe.products[i].name,'id':prepared.universe.products[i].product_id,'store':prepared.universe.products[i].store_id,'stage':stage,'outcome':outcome,'reason':reason} for key,trace in planner._resolution_trace.items() if key[0]==name and key[1]==unit for i,stage,outcome,reason in trace]
  queries.append(result)
(out/('diagnose-'+sys.argv[1]+'.json')).write_text(json.dumps({'products':rows,'queries':queries},ensure_ascii=False,indent=2,default=str))
print('diagnosed',len(rows),'products')
