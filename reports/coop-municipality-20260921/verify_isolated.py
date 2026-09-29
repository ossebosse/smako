"""Isolated actual source -> collector/OWN API -> PriceUniverse -> checkout/audit.
No retailer network calls: consume the separately freshly fetched batch unchanged.
"""
import argparse,asyncio,json,time
from pathlib import Path
from collections import Counter
import httpx
from fastapi import FastAPI
from app.providers.own import OwnGroceryPriceProvider
from app.services.product_matcher import ProductMatcher
from app.models.ingredient import NormalizedIngredient
from app.services.price_universe import PriceUniverseBuilder,PriceUniverseKey
from app.services.basket_calculator import BasketCalculator
from app.services.basket_auditor import BasketAuditor
from app.services.user_pricing import price_candidate_for_context
from grocery_data.app.domain import SourceStore,RawBatch,GeographicArea
from grocery_data.app.domain.promotion_pricing import UserPricingContext
from grocery_data.app.api import catalog_router,health_router
from grocery_data.app.connectors.coop.connector import CoopRowApprovedOfferConnector
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock,production_refresh_lock_path
from grocery_data.app.storage import create_database_engine,create_schema,create_session_factory

async def run(inputs,output):
 output.mkdir(exist_ok=False);db=output/'own.sqlite'
 engine=create_database_engine('sqlite:///'+db.resolve().as_posix());create_schema(engine);factory=create_session_factory(engine)
 started=time.perf_counter();report={'production_activation':False,'network_calls':0,'source':'retained fresh actual batches; timestamps unchanged','stores':[]};products=[];snapshots=[]
 with RefreshRunLock(production_refresh_lock_path(db,output/'price-universes')):
  collector=GroceryCollector(factory,FilesystemRawSnapshotStore(output/'raw'))
  for path in sorted(inputs.glob('*-store.json')):
   account=path.name.split('-')[0];store=SourceStore.model_validate_json(path.read_bytes())
   batch=RawBatch.model_validate_json((inputs/(account+'-batch.json')).read_bytes());locator=RawBatch.model_validate_json((inputs/(account+'-locator.json')).read_bytes())
   connector=CoopRowApprovedOfferConnector(store=store,locator=locator,offers=batch)
   result=await collector.collect_area(connector,GeographicArea(city=store.city),scope_key=store.city.casefold()+':coop:'+account+':offer-rows')
   snapshots.append(result.snapshot_id)
   envelope=json.loads(batch.documents[0].payload);source_groups=envelope.get('structured_offers',{}).get('data',{}).get('sortingGroups',[])
   row={'store':account,'name':store.name,'official_url':batch.documents[0].url,'observed_at':batch.documents[0].fetched_at.isoformat(),'source_hash':batch.documents[0].payload_hash,'ads':next((g['offerAmount'] for g in source_groups if g['id']=='alla'),None),'dom_price_cards':envelope['captured_total'],'extracted_variants':len(connector.extracted.products),'parser_failures':[x.model_dump(mode='json') for x in connector.extracted.failures],'accepted':result.metrics.products_parsed,'rejected':result.metrics.products_quarantined,'published_isolated_own':result.promoted,'snapshot':result.snapshot_id,'status':result.status.value,'metrics':result.metrics.model_dump(mode='json'),'qualification':connector.row_acceptance,'reasons':dict(Counter(b for d in connector.row_acceptance['decisions'] for b in d['blockers']))}
   report['stores'].append(row)
   (output/(account+'-extracted.json')).write_text(connector.extracted.model_dump_json(indent=2),encoding='utf-8')
  app=FastAPI();app.state.session_factory=factory;app.include_router(catalog_router);app.include_router(health_router)
  async with httpx.AsyncClient(base_url='http://isolated-own.test',transport=httpx.ASGITransport(app=app)) as client:
   own=OwnGroceryPriceProvider('http://isolated-own.test',client=client,include_offers_only=True,include_conditional_offer_products=True)
   for source_path in sorted(inputs.glob('*-store.json')):
    store=SourceStore.model_validate_json(source_path.read_bytes())
    response=await client.get('/stores',params={'chain':'coop','city':store.city,'limit':500})
    response.raise_for_status()
    target=next(s for s in response.json()['stores'] if s['external_id']==store.external_id)
    assert target['price_context_type']=='physical_store' and target['coverage']=='offers_only'
    offers=await own.get_offers(target['id']);products.extend(offers)
    row=next(s for s in report['stores'] if s['store']==store.external_id)
    row['own_projected']=len(offers);row['projection']=own.offer_projection_diagnostics[target['id']]
   key=PriceUniverseKey.create(city='isolated-coop-municipality-1281',snapshot_ids=snapshots,source_strategy_version='coop-physical-v1',normalizer_version='product-normalizer-v3-recipe-taxonomy',taxonomy_version='existing-taxonomy-v1')
   universe=PriceUniverseBuilder().build(key,products)
   (output/'price-universe.json').write_text(universe.model_dump_json(indent=2),encoding='utf-8')
   report['price_universe_id']=universe.universe_id;report['price_universe_count']=len(universe.products);report['proofs']=[]
   for row in report['stores']:
    rows=[p for p in universe.products if p.source_provenance.provider_store_id==row['store']]
    row['price_universe']=len(rows);row['semantic_taxonomy_candidates']=sum(p.semantic_confidence.value=='high' for p in rows)
    # Representative PUBLIC group purchase and MEMBER fixed-price product.
    selected=[next((p for p in rows if p.name==name),None) for name in ['Kärnvetemjöl','Nötfärs 20%','Färsk Pasta Fettuccine']]
    selected=[p for p in selected if p is not None]
    row['nutrition_restricted_planning']='not_verified; no new product-bound nutrition imported'
    row['verified_ingredient_checkout_products']=len(selected)
    for product in selected:
     context=UserPricingContext.from_chain_flags({'coop':True})
     offer=product.offers[0];day=__import__('datetime').datetime.now(__import__('zoneinfo').ZoneInfo('Europe/Stockholm')).date()
     need=NormalizedIngredient(canonical_name='vetemjöl' if product.name=='Kärnvetemjöl' else product.canonical_name,required_quantity=product.package_quantity*offer.required_packages,unit=product.package_unit)
     matches=ProductMatcher().match(need,[product])
     assert len(matches)==1
     candidate=price_candidate_for_context(matches[0],context,on_date=day)
     item=BasketCalculator().calculate_item(need,candidate)
     audit=BasketAuditor(pantry_items=frozenset()).audit([need],[item],user_pricing_context=context)
     proof={'store':row['store'],'name':product.name,'source_product_id':product.product_id,'source_observed_at':product.source_provenance.source_observed_at.isoformat(),'price':product.price,'package_quantity':product.package_quantity,'package_unit':product.package_unit,'matcher':{'target':need.canonical_name,'confidence':matches[0].semantic_confidence.value,'evidence':matches[0].semantic_evidence},'offer':offer.model_dump(mode='json'),'item':item.model_dump(mode='json'),'audit':audit.model_dump(mode='json')}
     report['proofs'].append(proof)
     (output/('proof-'+row['store']+'-'+str(len(report['proofs']))+'.json')).write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
     print(product.name,'audit',audit.passed,flush=True)
     assert product.price is None and item.regular_total_price is None 
     assert item.total_price==offer.price
     assert audit.passed
   assert all(any(p['store']==r['store'] and p['audit']['passed'] for p in report['proofs']) for r in report['stores'])
   report['runtime_seconds']=round(time.perf_counter()-started,3)
   (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps({'stores':[{k:r[k] for k in ['store','ads','extracted_variants','accepted','rejected','published_isolated_own','own_projected','price_universe']} for r in report['stores']],'universe':len(universe.products),'proofs':len(report['proofs']),'seconds':report['runtime_seconds']}),flush=True)
 engine.dispose()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();asyncio.run(run(a.input,a.output))
