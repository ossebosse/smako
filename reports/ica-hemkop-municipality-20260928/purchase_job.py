import json, threading, time
from pathlib import Path
from datetime import UTC, datetime
from job import configure, save
configure()
from app.main import app
import uvicorn
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
from app.models.ingredient import NormalizedIngredient
from app.services.product_matcher import ProductMatcher
from app.services.basket_calculator import BasketCalculator
from app.services.basket_auditor import BasketAuditor
from app.services.user_pricing import price_candidate_for_context
from grocery_data.app.domain.promotion_pricing import UserPricingContext
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=8000,log_level='error',access_log=False))
thread=threading.Thread(target=server.run,daemon=True);thread.start();start=time.monotonic()
while not server.started:
    if not thread.is_alive() or time.monotonic()-start>180: raise RuntimeError('startup failed')
    time.sleep(.1)
try:
    current=GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request('22350',{})
    report={'at':datetime.now(UTC).isoformat(),'universe_id':current.universe.universe_id,'cases':[],'rejections':[]}
    targets=['1003452','1004016','1004268','4517']
    for target in targets:
        products=[p for p in current.universe.products if p.source_provenance and p.source_provenance.provider_store_id==target]
        for p in products:
            if not p.canonical_name or not p.package_quantity or p.package_unit not in {'g','ml'}:continue
            try:
                need=NormalizedIngredient(canonical_name=p.canonical_name,required_quantity=p.package_quantity*1.5,unit=p.package_unit)
                matches=ProductMatcher().match(need,[p])
                if len(matches)!=1:continue
                context=UserPricingContext.from_chain_flags({'ica':True,'hemkop':True})
                priced=price_candidate_for_context(matches[0],context)
                item=BasketCalculator().calculate_item(need,priced)
                quoted=BasketCalculator.quote_group_basket([item])
                audit=BasketAuditor(pantry_items=frozenset()).audit([need],quoted,user_pricing_context=context)
                if not audit.passed:raise ValueError(str(audit))
                report['cases'].append({'account':target,'product':p.model_dump(mode='json'),'need':need.model_dump(mode='json'),
                    'checkout':[x.model_dump(mode='json') for x in quoted],'audit':audit.model_dump(mode='json')})
                break
            except Exception as exc:
                report['rejections'].append({'account':target,'product_id':p.product_id,'reason':str(exc)[:400]})
    save('representative-purchases',report)
    print('representative successful accounts',[x['account'] for x in report['cases']],flush=True)
finally:
    server.should_exit=True;thread.join(30)
