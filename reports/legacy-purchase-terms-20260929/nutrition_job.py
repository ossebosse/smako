"""Existing measured raw salad test, with newly imported real coriander."""
import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,UTC
from job import configure,save
configure()
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.models.ingredient import NormalizedIngredient
from app.models.recipe import Recipe,RecipeIngredient
from app.services.product_matcher import ProductMatcher
from app.services.personal_planner import PersonalPlanner
from app.services.personal_nutrition import raw_salad_instructions,calculation_basis
from app.services.user_pricing import price_candidate_for_context
from app.services.basket_calculator import BasketCalculator
from app.services.basket_auditor import BasketAuditor
p=PreparedPriceUniverseArtifact.model_validate_json(PreparedUniverseArtifactStore(Path('/work/price-universes')).resolve_active_artifact('Lund',verify_hash=True).read_bytes()).restore()
recipe=Recipe(name='Koriander med vitlök',servings=2,ingredients=[RecipeIngredient(name='koriander',quantity=20,unit='g'),RecipeIngredient(name='vitlök',quantity=5,unit='g')],instructions=raw_salad_instructions())
planner=SimpleNamespace(request=SimpleNamespace(purchase_planning_mode='exact'),spec=SimpleNamespace(allow_nutrition_estimates=True),source_facts=lambda _:None)
report={'basis':calculation_basis(recipe,allow_estimates=True),'recipe':recipe.model_dump(mode='json'),'components':[],'allergen_approval':False,'new_application_recipe':False}
needs=[];items=[];macros={'kcal':0,'protein_g':0,'carbs_g':0,'fat_g':0}
for ing in recipe.ingredients:
 need=NormalizedIngredient(canonical_name=ing.name,required_quantity=ing.quantity,unit=ing.unit)
 selected=[]
 for product in p.universe.products:
  if ing.name=='koriander' and not (product.chain=='hemkop' and product.price_context_type=='physical_store' and product.name=='Koriander'):continue
  matches=ProductMatcher().match(need,[product])
  if not matches:continue
  fact=PersonalPlanner._nutrition_evidence(planner,product,ing.name,'g',set(macros),recipe)
  if fact is None:continue
  try:
   item=BasketCalculator().calculate_item(need,price_candidate_for_context(matches[0],UserPricingContext.from_chain_flags({'hemkop':True}),on_date=datetime.now(UTC).date()))
  except ValueError:continue
  selected.append((item.total_price,product,item,fact))
 assert selected,ing.name
 _,product,item,fact=min(selected,key=lambda row:row[0])
 needs.append(need);items.append(item)
 report['components'].append({'product':product.model_dump(mode='json'),'used_g':ing.quantity,'evidence':__import__('dataclasses').asdict(fact)})
 for k in macros:macros[k]+=fact.nutrition[k]*ing.quantity/100
items=BasketCalculator.quote_group_basket(items)
audit=BasketAuditor(pantry_items=frozenset()).audit(needs,items,user_pricing_context=UserPricingContext.from_chain_flags({'hemkop':True}))
assert audit.passed,audit
report.update(checkout=[i.model_dump(mode='json') for i in items],audit=audit.model_dump(mode='json'),estimated_total_macros=macros,estimated_per_portion={k:v/2 for k,v in macros.items()})
save('nutrition-result',report)
print('existing raw preparation, actual newly imported coriander, checkout and nutrient evidence passed')
