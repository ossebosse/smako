"""Controlled source/content mutations against retained real data and baskets.

Injected numeric facts and price changes are test operands, never published facts
or claimed consumer menus. Every modified universe is rebuilt, not overlaid on
old indexes. Ordinary purchase/audit/nutrition code is used for every basket.
"""
import json
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest, ProductCandidate
from app.models.personal import MealSlot
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.meal_library_content import encoded, import_pack
from app.services.meal_prepared_artifacts import STATS, prepare_content
from app.services.personal_planner import PersonalPlanner
from app.services.personal_source_facts import FactsCollection, load_retained_facts
from app.services.price_universe import PriceUniverseBuilder
from app.services.price_universe_runtime import PreparedPriceUniverse, PreparedPriceUniverseArtifact
from app.services.recipe_library import current_recipes
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext

freeze=json.loads(Path('/inputs/freeze.json').read_text());clock=datetime.fromisoformat(freeze['frozen_at_utc'])
prepared=PreparedPriceUniverseArtifact.model_validate_json(Path('/inputs/universe.json').read_bytes()).restore()
facts=load_retained_facts(prepared);content=prepare_content(current_recipes())
recipe=next(r for r in current_recipes() if r.design.base_id=='smako-snack-carrot-quark-dip')
request=PlanRequest(recipes=0,max_stores=3,purchase_planning_mode='estimated',recipe_preferences={'mode':'complete'},
    personal={'use_pantry':False,'allow_nutrition_estimates':True,'meals':[{'meal_type':'snack','count':1,'servings':1,
        'recipe_choices':{},'limits':{'min_protein_g':0,'min_carbs_g':0,'min_fat_g':0,'max_kcal':4000}}]})
rows=[]
def basket(label,underlying,fact_values= facts):
    before=dict(STATS);started=time.perf_counter()
    planner=PersonalPlanner(request,Settings(price_provider='mock',complete_recipes_enabled=True),underlying,
        {'revision':0,'items':[],'reservations':{},'events':{}},facts=fact_values,now=clock)
    try:
        checked=planner.clean_recipe(recipe,planner.meals['snack'])
        result=planner.basket([MealSlot(id='snack-1',day=1,meal_type='snack',recipe=checked)])
        row={'status':'PASS','basket':result['basket'].model_dump(mode='json'),
             'audit':result['audit'].model_dump(mode='json'),'checks':result['checks']}
    except ValueError as error:row={'status':'STOPPED','reason':str(error)}
    row.update(label=label,universe_id=underlying.universe.universe_id,
        facts_version=getattr(fact_values,'version',None),seconds=time.perf_counter()-started,
        preparation_delta={k:STATS[k]-before[k] for k in STATS})
    rows.append(row);Path('/results/incremental.json').write_bytes(encoded({'injected':True,'rows':rows,'dependencies':content['dependencies']}))
    return row
def rebuild(products):
    universe=PriceUniverseBuilder().build(prepared.universe.key,products,built_at=prepared.universe.built_at)
    return PreparedPriceUniverse(universe=universe,stores=prepared.stores,economic_pool=EconomicIngredientPool(),
        source_name='controlled-incremental-retained-data',oldest_observed_at=prepared.oldest_observed_at)
baseline=basket('baseline',prepared);assert baseline['status']=='PASS'
basket('identical-source-reuse',prepared)
# Real fixed dishes demonstrate one compatible purchase across meal categories.
# This is an integration probe, not a free economic selection or savings claim.
shared_recipes=[next(r for r in current_recipes() if r.design.base_id==base) for base in
    ['smako-dinner-bean-couscous-salad','smako-breakfast-overnight-apple-oats']]
shared_request=request.model_copy(deep=True)
shared_request.personal.meals=[request.personal.meals[0].model_copy(update={
    'meal_type':r.design.meal_types[0],'servings':r.servings}) for r in shared_recipes]
shared_planner=PersonalPlanner(shared_request,Settings(price_provider='mock',complete_recipes_enabled=True),prepared,
    {'revision':0,'items':[],'reservations':{},'events':{}},facts=facts,now=clock)
shared_slots=[MealSlot(id=r.design.meal_types[0]+'-1',day=1,meal_type=r.design.meal_types[0],
    recipe=shared_planner.clean_recipe(r,shared_planner.meals[r.design.meal_types[0]])) for r in shared_recipes]
joint=shared_planner.basket(shared_slots)
Path('/results/shared-meal-purchase.json').write_bytes(encoded({'selection':'fixed real recipes, not free selection',
    'slots':[s.model_dump(mode='json') for s in shared_slots],
    'basket':joint['basket'].model_dump(mode='json'),'checks':joint['checks'],
    'audit':joint['audit'].model_dump(mode='json')}))
item=next(i for s in baseline['basket']['stores'] for i in s['items'] if i['ingredient'].startswith('kvarg'))
target=next(p for p in prepared.universe.products if p.product_id==item['product_id'] and p.store_id==item['store_id'])
key=(target.store_id,target.product_id);fact=facts[key]
mutated=dict(facts);mutated[key]=replace(fact,nutrition={**fact.nutrition,'protein_g':fact.nutrition['protein_g']+1})
changed=basket('one-fact-controlled-protein-delta',prepared,FactsCollection(mutated))
assert changed['status']=='PASS' and changed['checks']['nutrition']!=baseline['checks']['nutrition']
# Remove all verified quark products, then restore one actual retained identity.
remaining=[p for p in prepared.universe.products if p.product_id not in {
    p.product_id for p in prepared.universe.products if 'kvarg' in p.name.lower()}]
missing=basket('previously-missing-product',rebuild(remaining));assert missing['status']=='STOPPED'
restored=basket('one-retained-product-added',rebuild([*remaining,target]));assert restored['status']=='PASS'
price_products=[p.model_copy(update={'price':p.price+1})
    if p.product_id==target.product_id and p.store_id==target.store_id else p for p in prepared.universe.products]
priced=basket('one-controlled-price-change',rebuild(price_products));assert priced['status']=='PASS'
# Campaign expiry is an ordinary datetime gate, not a permanent source approval.
campaign=next(p for p in prepared.universe.products if p.offers and p.offers[0].valid_to)
offer=campaign.offers[0]
candidate=ProductCandidate.from_product(campaign,1)
before=price_candidate_for_context(candidate,UserPricingContext(),on_date=offer.valid_to,planning_mode='estimated')
after=price_candidate_for_context(candidate,UserPricingContext(),on_date=offer.valid_to+timedelta(days=1),planning_mode='estimated')
rows.append({'label':'campaign-expiry','injected_clock_only':True,'product_id':campaign.product_id,
             'valid_to':str(offer.valid_to),'before':before.model_dump(mode='json'),'after':after.model_dump(mode='json')})
# A new content version rebuilds only its own static row; issued v1 is retained.
row=recipe.model_dump(mode='json');row['design']['version']='1.2.0';row['name']+=' (tekniskt versionsprov)'
path=Path('/tmp/changed-content.json');path.write_bytes(encoded({'schema_version':'smako-meal-pack-v1',
    'pack_id':'controlled-incremental-content','recipes':[row]}))
before=dict(STATS);import_pack(path);updated=prepare_content(current_recipes())
rows.append({'label':'one-recipe-version','preparation_delta':{k:STATS[k]-before[k] for k in STATS},
             'affected_ingredient_keys':[k for k,v in updated['dependencies'].items() if any(recipe.design.base_id in i for i in v)]})
Path('/results/incremental.json').write_bytes(encoded({'injected':True,'rows':rows,'dependencies':content['dependencies']}))
