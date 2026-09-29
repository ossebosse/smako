"""Actual imported products, max two physical stores; no live price writes."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.models.store import Store
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, GroupPricingError
from app.services.basket_optimizer import BasketOptimizer
from app.services.product_matcher import ProductMatcher
from app.services.user_pricing import price_candidate_for_context
from grocery_data.app.domain.promotion_pricing import UserPricingContext

ROOT=Path(__file__).parent
rows=[Product.model_validate(p) for p in json.loads((ROOT/'verified-final/price-universe.json').read_bytes())['products']]
day=datetime.now(ZoneInfo('Europe/Stockholm')).date()
member=UserPricingContext.from_chain_flags({'coop':True})

def choose(sid,name):
    return next(p for p in rows if p.source_provenance.provider_store_id==sid and p.name==name)

def match(p,quantity):
    need=NormalizedIngredient(canonical_name=p.canonical_name,required_quantity=quantity,unit=p.package_unit)
    matches=ProductMatcher().match(need,[p]);assert len(matches)==1
    return need,price_candidate_for_context(matches[0],member,on_date=day)

selected=[choose('3841','Kärnvetemjöl'),choose('1158','Färsk Pasta Fettuccine')]
needs=[];candidates={};stores=[]
for p in selected:
    need,candidate=match(p,p.package_quantity*p.offers[0].required_packages)
    needs.append(need);candidates[need.canonical_name]=[candidate]
    source_store=json.loads((ROOT/'final-sources'/(p.source_provenance.provider_store_id+'-store.json')).read_bytes())
    stores.append(Store(store_id=p.store_id,name=p.store_name,chain=p.chain,city=source_store['city'],source_store_id=p.source_provenance.provider_store_id,price_context_type='physical_store',physical_store_external_id=p.source_provenance.provider_store_id))
basket=BasketOptimizer().optimize(needs,candidates,stores,max_stores=2,calculate_savings=False)
audit=BasketAuditor(pantry_items=frozenset()).audit(needs,basket,user_pricing_context=member)
assert audit.passed and len(basket.stores)==2 and basket.total==41
# Same campaign cap in Genarp and Veberöd; do not multiply three into six.
items=[]
for sid in ['3841','1158']:
    need,candidate=match(choose(sid,'Nötfärs 20%'),1000)
    items.append(BasketCalculator().calculate_item(need,candidate))
try:
    BasketCalculator.quote_group_basket(items)
    raise AssertionError('household cap bypassed')
except GroupPricingError as exc:
    cap_error=str(exc)
extra=[]
for name in ['Morötter','Tomater Plommon']:
    p=choose('2696',name);need,candidate=match(p,p.package_quantity*p.offers[0].required_packages)
    item=BasketCalculator().calculate_item(need,candidate)
    a=BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=member)
    assert a.passed
    extra.append({'name':name,'product_id':p.product_id,'item':item.model_dump(mode='json'),'audit':a.model_dump(mode='json')})
report={'purchase_day':str(day),'max_stores':2,'basket':basket.model_dump(mode='json'),'audit':audit.model_dump(mode='json'),'shared_household_excess':'blocked: '+cap_error,'stora_additional_proofs':extra,'menu_or_nutrition_acceptance':False,'production_activation':False}
(ROOT/'two-store-checkout.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'total':basket.total,'stores':len(basket.stores),'audit':audit.passed,'cap_excess':'blocked','stora_proofs':len(extra)}))
