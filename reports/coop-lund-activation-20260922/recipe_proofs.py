"""Separate explicit-product checkout probes, never the winning A/B menu."""
import json,time
from pathlib import Path
from datetime import datetime,UTC
from app.models.plan import PlanRequest
from app.models.personal import MealSlot
from app.models.recipe import Recipe
from app.config import get_settings
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import load_retained_facts
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.personal_policy import PolicyConflict
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path


def run():
 root=Path('/work');out=root/'profile';start=time.perf_counter()
 with RefreshRunLock(production_refresh_lock_path(Path('/srv/app/var/grocery/grocery_data.sqlite'),Path('/srv/app/var/price_universes'))):
  prepared=PreparedPriceUniverseArtifact.model_validate_json((out/'coop-acceptance-source-universe.json').read_bytes()).restore()
  facts=load_retained_facts(prepared,database=root/'base-final/frozen-base.sqlite')
  request=PlanRequest.model_validate_json(Path('/evaluation/request.json').read_bytes())
  data=json.loads((out/'coop-acceptance.json').read_bytes())
  trace={r['product_id']:r for r in data['request_candidate_trace']}
  recipes=json.loads(Path('/evaluation/request-recipes.json').read_bytes())
  from app.services.user_pricing import price_candidate_for_context
  from app.models.product import ProductCandidate
  from grocery_data.app.domain.promotion_pricing import UserPricingContext
  diagnostic=[]
  for product in prepared.universe.products:
   if product.product_id not in trace:continue
   row={'product_id':product.product_id,'name':product.name,'semantic_confidence':str(product.semantic_confidence),'role':product.product_role,'form':product.product_form,'unit':product.usable_unit,'offers':[o.model_dump(mode='json') for o in product.offers]}
   try:price_candidate_for_context(ProductCandidate.from_product(product,1),UserPricingContext(),on_date=datetime.now(__import__('zoneinfo').ZoneInfo('Europe/Stockholm')).date());row['eligible_price']=True
   except ValueError as e:row.update(eligible_price=False,price_rejection=str(e))
   diagnostic.append(row)
  (root/'candidate-diagnostics.json').write_text(json.dumps(diagnostic,ensure_ascii=False,indent=2),encoding='utf8')
  wanted=[('3659','Cheddar Medium Mature 35%'),('3659','Gouda Medium Mature 30%'),('2696','Plommontomat')]
  results=[]
  for store,name in wanted:
   product=next(p for p in prepared.universe.products if p.source_provenance and p.source_provenance.provider_store_id==store and p.name==name)
   canonical='ost' if 'Mature' in name else 'tomat';record={'store':store,'name':name,'product_id':product.product_id,'source_observed_at':product.source_provenance.source_observed_at.isoformat(),'attempts':[]}
   for n,block in enumerate(recipes):
    meal='dinner' if n<2 else 'breakfast' if n==2 else 'snack'
    for raw in block['recipes']:
     if raw['name'] not in trace[product.product_id]['individual_nutrition_supported_recipes']:continue
     recipe=Recipe.model_validate(raw);slot=MealSlot(id='probe',day=1,meal_type=meal,recipe=recipe)
     planner=PersonalPlanner(request,get_settings(),prepared,{'items':[],'reservations':{},'revision':0},facts=facts)
     try:
      unlocked=planner.basket([slot])
      group=next(g for g in unlocked['groups'] if g['name']==canonical)
      position=planner.by_identity[(product.store_id,product.product_id)]
      planner.spec.product_locks[group['key']]=planner.product_keys[position]
      locked=planner.basket([slot])
      assert locked['audit'].passed and locked['basket'].store_count<=2
      assert any(i.product_id==product.product_id for s in locked['basket'].stores for i in s.items)
      record.update(result='PASS',recipe=recipe.model_dump(mode='json'),meal_type=meal,
          constraints=planner.meals[meal].limits.model_dump(mode='json'),unlocked_cost=unlocked['basket'].total,
          basket=locked['basket'].model_dump(mode='json'),checks=locked['checks'],audit=locked['audit'].model_dump(mode='json'))
      break
     except PolicyConflict as e:record['attempts'].append({'recipe':raw['name'],'stage':getattr(e,'stage',None),'reason':str(e)})
    if record.get('result')=='PASS':break
   if 'result' not in record:record['result']='BLOCKED'
   results.append(record)
  result={'production_activation':False,'winning_menu_changed':False,'purpose':'Existing explicit product lock for a separate single-recipe feasibility test; same meal constraints, memberships, maximum stores and source facts. Not the unrestricted A/B menu.','results':results,'seconds':round(time.perf_counter()-start,3)}
  (root/'recipe-proofs.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
  print(json.dumps([{'name':r['name'],'result':r['result'],'cost':r.get('basket',{}).get('total'),'attempts':r['attempts']} for r in results],ensure_ascii=False))
