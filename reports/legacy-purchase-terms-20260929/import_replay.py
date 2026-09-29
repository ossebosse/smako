"""Retained real rows through ordinary collector, OWN, PU, checkout and audit."""
import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from types import SimpleNamespace
import replay

O=replay.O
mode=replay.mode
sys.path.insert(0,str((O/'before' if mode=='before' else replay.ROOT)/'backend'))
import httpx
from grocery_data.app.domain import GeographicArea, RawBatch
from grocery_data.app.connectors.ica import IcaConnector
from grocery_data.app.connectors.coop.connector import CoopRowApprovedOfferConnector
from grocery_data.app.connectors.coop.xtra_pdf import XtraTextOfferConnector
from grocery_data.app.connectors.hemkop.physical_offers import RetainedPhysicalOffers
from grocery_data.app.connectors.hemkop.parser import HemkopParser
from grocery_data.app.services.ica_area_offers import RowApprovedOfferConnector
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.storage import create_database_engine,create_schema,create_session_factory
from app.providers.own import OwnGroceryPriceProvider
from app.providers.ica_area_offers import IcaAreaOfferProvider
from app.providers.hemkop_municipality_offers import HemkopMunicipalityOfferProvider
from app.providers.coop_municipality_offers import CoopMunicipalityOfferProvider
from app.services.production_price_universe_build import _read_only_app
from app.services.price_universe import PriceUniverseBuilder,PriceUniverseKey
from app.models.product import ProductCandidate
from app.models.ingredient import NormalizedIngredient
from app.services.user_pricing import price_candidate_for_context
from app.services.basket_calculator import BasketCalculator
from app.services.basket_auditor import BasketAuditor
from app.services.product_matcher import ProductMatcher
from grocery_data.app.domain.promotion_pricing import UserPricingContext

DAY=date(2026,9,28)

class EmptyBase:
    async def find_stores(self,postal):return []
    async def get_store_products(self,store):return []
    async def get_offers(self,store):return []
    def report(self):return {}

def provider_for(chain,own,db,source):
    if chain in {'ica','hemkop'}:
        cls=IcaAreaOfferProvider if chain=='ica' else HemkopMunicipalityOfferProvider
        return cls(EmptyBase(),own,database=db,city='Lund',account_ids=frozenset({source.external_id}),municipal_stores={source.external_id:source})
    state=replay.read(replay.PRIOR/'coop-municipal/1281/source-state.json')
    inventory={**state['inventory'],'selected_store_ids':[source.external_id]}
    return CoopMunicipalityOfferProvider(EmptyBase(),own,database=db,inventory=inventory,include_xtra=chain=='xtra')

def connector_for(chain,store,batch,locator):
    if chain=='ica':
        return RowApprovedOfferConnector(IcaConnector(client=SimpleNamespace()),store,locator,batch)
    if chain=='hemkop':
        return RetainedPhysicalOffers(SimpleNamespace(client=SimpleNamespace(requests_per_second=1),parser=HemkopParser()),store,locator,batch)
    cls=XtraTextOfferConnector if chain=='xtra' else CoopRowApprovedOfferConnector
    return cls(store=store,locator=locator,offers=batch)

def purchases(products):
    output=[]
    for p in products:
        row={'id':p.product_id,'name':p.name,'source':p.source_provenance.model_dump(mode='json'),'terms':p.purchase_terms.model_dump(mode='json') if p.purchase_terms else None,'cases':[]}
        terms=p.purchase_terms
        group=bool(terms and terms.usage=='variant_selection_required')
        estimated=bool(terms and terms.usage=='estimated')
        qty=1 if group else 200 if estimated else p.usable_quantity or p.package_quantity
        unit='st' if group else 'g' if estimated else p.usable_unit or p.package_unit
        for member in [False,True]:
            for planning_mode in ['exact','estimated']:
                case={'member':member,'mode':planning_mode}
                try:
                    need=NormalizedIngredient(canonical_name=p.canonical_name or p.name.casefold(),required_quantity=qty,unit=unit)
                    matched=ProductMatcher().match(need,[p])
                    if group:assert not matched
                    context=UserPricingContext.from_chain_flags({p.chain:member})
                    candidate=price_candidate_for_context(matched[0] if matched else ProductCandidate.from_product(p,1),context,on_date=DAY,planning_mode=planning_mode,allow_campaign_choice=group)
                    item=BasketCalculator().calculate_item(need,candidate)
                    quoted=BasketCalculator.quote_group_basket([item])
                    restored=[type(i).model_validate_json(i.model_dump_json()) for i in quoted]
                    audit=BasketAuditor(pantry_items=frozenset()).audit([need],restored,user_pricing_context=context)
                    case['audit']=audit.model_dump(mode='json')
                    assert audit.passed,audit
                    assert all(not i.ordinary_price_known for i in quoted)
                    case.update(status='PASS',total=sum(i.total_price for i in quoted),verification=quoted[0].verification_status,
                        matched=bool(matched),checkout=[i.model_dump(mode='json') for i in quoted],audit=audit.model_dump(mode='json'))
                except Exception as exc:
                    case.update(status='BLOCKED',reason=f'{type(exc).__name__}: {exc}'[:500])
                row['cases'].append(case)
        output.append(row)
    return output

async def main():
    dest=O/(mode+'-import'+__import__('os').getenv('REPLAY_OUTPUT_SUFFIX',''))
    reuse=dest.exists() and (dest/'collections.json').exists()
    if dest.exists() and not reuse:raise ValueError('incomplete output requires a new directory')
    dest.mkdir(exist_ok=True)
    db=dest/'own.sqlite'
    engine=create_database_engine('sqlite:///'+db.resolve().as_posix());create_schema(engine)
    factory=create_session_factory(engine)
    collector=GroceryCollector(factory,FilesystemRawSnapshotStore(dest/'raw'))
    collected=json.loads((dest/'collections.json').read_text(encoding='utf-8')) if reuse else []
    for chain,store,batch,_ in ([] if reuse else replay.inputs()):
        # Locator is retained separately where available. parse_stores uses the
        # already verified immutable store evidence, never a guessed city list.
        locator=RawBatch(chain=store.chain,documents=())
        connector=connector_for(chain,store,batch,locator)
        result=await collector.collect_area(connector,GeographicArea(city=store.city),
            scope_key=f'{store.city.lower()}:{store.chain.value}:{store.external_id}:offer-rows')
        print('import',chain,store.external_id,result.promoted,result.metrics.products_parsed,flush=True)
        collected.append({'chain':chain,'store':store.model_dump(mode='json'),'snapshot':result.snapshot_id,
            'promoted':result.promoted,'evidence':connector.row_acceptance})
    (dest/'collections.json').write_text(json.dumps(collected,ensure_ascii=False,indent=2),encoding='utf-8')
    # Freeze projection as well as checkout; no actual source observation is rewritten.
    from datetime import datetime, UTC
    import importlib
    class ReplayClock(datetime):
        @classmethod
        def now(cls, tz=None):
            value=cls(2026,9,28,20,tzinfo=UTC)
            return value.astimezone(tz) if tz else value.replace(tzinfo=None)
    for module in ['grocery_data.app.api.common','grocery_data.app.api.catalog',
                   'grocery_data.app.services.freshness','app.providers.own',
                   'app.models.product','grocery_data.app.domain.promotion_pricing',
                   'grocery_data.app.services.fixed_checkout_price',
                   'app.providers.coop_municipality_offers','app.providers.ica_area_offers']:
        setattr(importlib.import_module(module),'datetime',ReplayClock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_read_only_app(factory)),base_url='http://test') as client:
        own=OwnGroceryPriceProvider('http://test',client=client,include_offers_only=True,include_conditional_offer_products=True)
        result=[]
        for row in collected:
            source=row['store']
            provider=provider_for(row['chain'],own,db,replay.SourceStore.model_validate(source))
            stores=await provider.find_stores('22350')
            store=next((s for s in stores if s.source_store_id==source['external_id'] and s.chain==source['chain']),None)
            products=await provider.get_store_products(store.store_id) if store else []
            key=PriceUniverseKey.create(city=source['city'],postal_codes=(source['postal_code'].replace(' ',''),),snapshot_ids=(row['snapshot'],),memberships={},source_strategy_version='frozen-real-replay',normalizer_version='same-pipeline',taxonomy_version='unchanged')
            universe=PriceUniverseBuilder().build(key,products)
            checks=purchases(universe.products)
            result.append({**row,'own':len(products),'pu':len(universe.products),'checks':checks,'provider':provider.diagnostics,
                'projection':getattr(own,'offer_projection_diagnostics',{}).get(store.store_id,{}) if store else {}})
            passed=sum(any(c['status']=='PASS' for c in p['cases']) for p in checks)
            print('checkout',row['chain'],source['external_id'],len(products),len(universe.products),passed,
                Counter(c.get('reason') for p in checks for c in p['cases'] if c['status']!='PASS').most_common(3),flush=True)
        (dest/'checkout.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    engine.dispose()

if __name__=='__main__':asyncio.run(main())
