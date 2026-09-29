"""Scoped municipal offers proof. No Lund base policy and no federated Malmö claim."""
import asyncio
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from job import configure, save

configure()
os.environ.update(REFRESH_MUNICIPALITY_CODE='1280',REFRESH_CITY='Malmö',PRICE_UNIVERSE_CITY='Malmö',
    REFRESH_POSTAL_CODE='21120',PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS='',PRICE_UNIVERSE_CACHE_ROOT='/work/malmo-probe/price-universes',
    PLAN_STORE_PATH='/work/malmo-probe/plans.sqlite')

from grocery_data.app.services import ica_offer_job, hemkop_municipal_job
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock, production_refresh_lock_path
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore, validate_backend_prepared_universe_artifact
from app.services.production_price_universe_build import _read_only_engine, _read_only_app, _CountingASGITransport, _network_disabled, _build_settings
from app.providers.own import OwnGroceryPriceProvider
from app.providers.ica_area_offers import IcaAreaOfferProvider
from app.providers.hemkop_municipality_offers import HemkopMunicipalityOfferProvider
from app.services.price_universe_runtime import PreparedPriceUniverseManager
from app.services.meal_plan_optimizer import MealPlanService
import httpx

class ScopedEmptyBase:
    async def find_stores(self, postal): return []
    async def search_products(self, query, stores): return []
    async def get_store_products(self, store): return []
    async def get_offers(self, store): return []
    async def aclose(self): pass
    def report(self): return {'scope':'ICA/Hemkop municipal offers only; no mandatory online base policy'}

async def main():
    result={'scope':'bounded municipal offers, not full federated Malmö publication', 'lund_policy_used':False,'rebuilds':[]}
    with RefreshRunLock(production_refresh_lock_path(Path('/work/grocery.sqlite'),Path('/work/price-universes'))):
        pointer=Path('/work/ica-structured/1280/structured-source.json')
        previous=json.loads(pointer.read_bytes())
        if not previous['ica_offer_store_ids'] and previous['coverage'].get('inventory_error'):
            from grocery_data.app.services.durable_files import atomic_write_bytes
            saved=json.loads(Path('/work/ica-job-1280.json').read_bytes())
            assert saved['ica_offer_store_ids'] and saved['coverage']['area']['municipality_code']=='1280'
            save('malmo-failed-inventory-before-fix',previous)
            atomic_write_bytes(pointer,json.dumps(saved,ensure_ascii=False).encode())
            result['recovery']='Restored exact successful source pointer in private stage; no price observation changed'
        result['ica_status']=(await ica_offer_job.run_structured_offer_job(city='Malmö',root=Path('/work/ica-structured')))['status']
        result['hemkop_status']=(await hemkop_municipal_job.run_source_job(city='Malmö'))['status']
        for turn in range(2):
            provider=ScopedEmptyBase();resources=[]
            for chain,options,cls in [
                ('ica',ica_offer_job.structured_source_inputs(city='Malmö',root=Path('/work/ica-structured')),IcaAreaOfferProvider),
                ('hemkop',hemkop_municipal_job.source_inputs(city='Malmö'),HemkopMunicipalityOfferProvider)]:
                database=options[chain+'_offer_database'];selected=options[chain+'_municipal_stores']
                engine,sessions,_=_read_only_engine(database)
                client=httpx.AsyncClient(transport=_CountingASGITransport(_read_only_app(sessions)),base_url='http://municipal-source.local/')
                own=OwnGroceryPriceProvider('http://municipal-source.local',client=client,include_offers_only=True,include_conditional_offer_products=True)
                resources.append((client,engine))
                provider=cls(provider,own,database=database,city='Malmö',account_ids=frozenset(selected),municipal_stores=selected)
                locality=next(iter(selected.values())).city
                sample_stores=await own.find_offer_stores_in_locality(locality)
                sample= (await own.get_offers(sample_stores[0].store_id))[0]
                save('malmo-identity-'+chain,{'store':sample_stores[0].model_dump(mode='json'),'product':sample.model_dump(mode='json'),'evidence':provider.evidence.get(sample.product_id)})
            try:
                await provider.find_stores('21120')
                save('malmo-provider-diagnostic',provider.report())
                with _network_disabled() as attempts:
                    prepared=await PreparedPriceUniverseManager().build_and_activate(city='Malmö',postal_codes=('21120',),
                        provider=provider,memberships={},selector=MealPlanService(_build_settings()).economic_selector)
                target=Path('/work/malmo-probe/candidate-'+str(turn)+'.json');target.parent.mkdir(exist_ok=True)
                PreparedPriceUniverseManager.write_artifact(prepared,target)
                rows=[p.model_dump(mode='json') for p in prepared.universe.products]
                entry={'products':len(rows),'products_sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest(),
                    'stores':[s.model_dump(mode='json') for s in prepared.stores],'network_attempts':attempts['count'], 'provider':provider.report()}
                try:
                    publication=PreparedUniverseArtifactStore(Path(os.environ['PRICE_UNIVERSE_CACHE_ROOT'])).activate(target,city='Malmö',validator=validate_backend_prepared_universe_artifact)
                    entry['publication']=publication.model_dump(mode='json')
                except (ValueError, __import__("app.errors",fromlist=["IncompleteBasketError"]).IncompleteBasketError) as exc:
                    entry['publication_blocker']=str(exc)
                entry['published_serving_products']=len(rows) if 'publication' in entry else 0
                entry['per_store_counts']={s.store_id:sum(p.store_id==s.store_id for p in prepared.universe.products) for s in prepared.stores}
                result['rebuilds'].append(entry)
            finally:
                for client,engine in resources:await client.aclose();engine.dispose()
        save('malmo-scoped-result',result)
        print('Malmö',[(r['products'],r.get('publication_blocker')) for r in result['rebuilds']],flush=True)

asyncio.run(main())
