"""Final code, retained actual observations, no review register and no network."""
import asyncio,json
from pathlib import Path
from types import SimpleNamespace
from app.models.ingredient import NormalizedIngredient
from app.services.production_price_universe_build import build_city_price_universe
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_matcher import ProductMatcher
from app.services.basket_calculator import BasketCalculator
from app.services.basket_auditor import BasketAuditor
from app.services.user_pricing import price_candidate_for_context
from app.services.personal_planner import PersonalPlanner
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.services.campaign_refresh_policy import STOCKHOLM
from datetime import datetime
R=Path(__file__).parent

def purchases(prepared):
 context=UserPricingContext.from_chain_flags({'willys':True});results=[]
 for p in prepared.universe.products:
  if p.chain!='willys' or p.source_provenance.source_channel!='offers':continue
  if p.name not in {'Gurka','Brie','Kycklingbröstfilé','Kycklingbröstfilé Sverige','Pizzadeg','Pågenlimpan'}:continue
  need=NormalizedIngredient(canonical_name='chicken_breast' if p.name.startswith('Kycklingbröstfilé') else p.name.casefold(),required_quantity=p.package_quantity*p.offers[0].required_packages,unit=p.package_unit)
  matches=ProductMatcher().match(need,[p])
  if not matches:
   results.append({'name':p.name,'store':p.source_provenance.provider_store_id,'matcher':'no_eligible_recipe_match','audit_passed':False})
   continue
  assert len(matches)==1
  c=price_candidate_for_context(matches[0],context,on_date=datetime.now(STOCKHOLM).date())
  bought=BasketCalculator().calculate_item(need,c)
  audit=BasketAuditor(pantry_items=frozenset()).audit([need],[bought],user_pricing_context=context)
  assert audit.passed,(p.name,audit)
  assert p.price is p.gtin is None
  planner=SimpleNamespace(spec=SimpleNamespace(allow_nutrition_estimates=False),source_facts=lambda _:None)
  assert PersonalPlanner._nutrition_evidence(planner,p,p.canonical_name,p.package_unit,{'kcal','protein_g'},None) is None
  results.append({'name':p.name,'store':p.source_provenance.provider_store_id,'package':[p.package_quantity,p.package_unit],
   'price':bought.total_price,'packages':bought.packages_needed,'source_observed':p.source_provenance.source_observed_at.isoformat(),
   'offer':p.offers[0].model_dump(mode='json'),'audit_passed':True,'nutrition':'no_exact_approved_product_declaration',
   'ordinary_price':p.price,'checkout':bought.model_dump(mode='json')})
 assert results
 return results

async def main():
 for code,city,postal in [('1281','Lund','22223'),('1280','Malmö','21120')]:
  root=R/f'automatic-only-{code}';inv=json.loads((root/'inventory.json').read_bytes());report=json.loads((root/'coverage.json').read_bytes())
  sources=[dict(database=root/s['database'],store_ids=[s['store_id']],snapshot_ids=[s['snapshot_id']],inventory=inv) for s in report['stores']]
  output=root/'prepared.json'
  build=await build_city_price_universe(database=R/'runtime-1281/grocery.sqlite',city=city,postal_code=postal,external_cache=None,
     output=output,max_price_age_hours=48,willys_flyer_enabled=True,willys_flyer_sources=sources)
  prepared=PreparedPriceUniverseArtifact.model_validate_json(output.read_bytes()).restore()
  rows=purchases(prepared)
  proof={'scope':'isolated inactive automatic-only PriceUniverse, no complete base or publication claim',
    'review_registry_used':False,'network_requests':0,'build':build,'price_universe_products':len(prepared.universe.products),
    'purchases':rows}
  (root/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
  print(code,len(prepared.universe.products),'PU',len(rows),'audits',flush=True)
if __name__=='__main__':asyncio.run(main())
