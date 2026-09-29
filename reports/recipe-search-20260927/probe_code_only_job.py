"""Every retained blocked recipe through actual candidate/basket qualification."""
import os
from grocery_data.app.services import product_declarations
product_declarations.PATH = __import__("pathlib").Path("/rollback/grocery_data/app/data/product_declarations.json")
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
facts=[]
for p in prepared.universe.products:
 if any(x in p.name.lower() for x in ('rapsol','kikärt','hushållsost','fläskytter')):
  f=planner.source_facts(p)
  facts.append({'product':p.model_dump(mode='json'),'facts':f.__dict__ if f else None})
(out/'final-code-only-relevant-facts.json').write_text(json.dumps(facts,ensure_ascii=False,indent=2,default=str))
rows=[]
originals={r['name']:r for r in json.loads(Path('/evaluation/original-rejections.json').read_bytes())['rejections']}
for meal in request.personal.meals:
 before=DeterministicRecipeCandidateGenerator(recipe_version='legacy').generate_for_meal_type(planner.view.economic_pool,meal.meal_type,count=80,servings=meal.servings)
 after=DeterministicRecipeCandidateGenerator().generate_for_meal_type(planner.view.economic_pool,meal.meal_type,count=80,servings=meal.servings)
 for old,new in zip(before,after,strict=True):
  try: calculation_basis(old,allow_estimates=True);continue
  except ValueError: pass
  source=originals[old.name]
  assert old.instructions==source['instructions'] and [i.model_dump() for i in old.ingredients]==source['ingredient_amounts'], old.name
  row={'original':old.model_dump(mode='json'),'adapted':new.model_dump(mode='json'),'original_hash':content_hash(old),'meal_type':meal.meal_type}
  start=time.perf_counter();stage='preparation'
  try:
   row['basis']=calculation_basis(new,allow_estimates=True);row['preparation_passed']=True
   stage='product_qualification'
   clean=planner.clean_recipe(new,meal)
   row['product_match_passed']=True
   stage='nutrition_basket'
   row['nutrition_attempted']=True
   slot=MealSlot(id=meal.meal_type+'-1',day=1,meal_type=meal.meal_type,recipe=clean)
   result=planner.basket([slot],final=True)
   row['nutrition_basket_passed']=True
   row['basket']=result['basket'].model_dump(mode='json')
   row['checks']=result['checks']
   row['audit']=result['audit'].model_dump(mode='json')
  except ValueError as e:
   row['stop']={'stage':getattr(e,'stage',None) or stage,'reason':str(e),'code':getattr(e,'code',None)}
  row['ingredient_evidence']=[]
  from app.models.personal import TasteProfile
  from dataclasses import asdict
  for ingredient in new.ingredients:
   item={'name':ingredient.name,'unit':ingredient.unit,'quantity':ingredient.quantity,'qualified':[]}
   try:
    for index,candidate in planner.resolve(ingredient.name,ingredient.quantity,ingredient.unit,profile=TasteProfile(),recipe=new):
     product=prepared.universe.products[index]
     evidence=planner.nutrition_evidence(product,ingredient.name,ingredient.unit,{'protein_g'},new)
     if evidence:
      item['qualified'].append({'product_id':product.product_id,'store_id':product.store_id,'name':product.name,
        'package_quantity':candidate.package_quantity,'usable_quantity':candidate.usable_quantity,
        'source_snapshot_id':product.source_provenance.source_snapshot_id,'facts':asdict(evidence)})
   except ValueError as e:item['reason']=str(e)
   row['ingredient_evidence'].append(item)
  row['seconds']=round(time.perf_counter()-start,3);rows.append(row)
  (out/'final-code-only-all-84.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2,default=str))
  print(json.dumps({'n':len(rows),'name':new.name,'pass':row.get('nutrition_basket_passed',False),'stop':row.get('stop')},ensure_ascii=False),flush=True)
(out/'final-code-only-all-84-diagnostics.json').write_text(json.dumps(planner.diagnostics.snapshot(),ensure_ascii=False,indent=2,default=str))
assert len(rows)==84,len(rows)
