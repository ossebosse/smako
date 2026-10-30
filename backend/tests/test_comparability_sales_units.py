import json
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest, Product, Store
from app.models.personal import ExtraNeed, GenericRef, PersonalPlanning
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, interpretation
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import PreparedPriceUniverse
from app.services.shopping_list import price_free_products
from pydantic import ValidationError

from backend.tests.test_weight_offers import NOW


def prepare(*products, now=NOW):
    key=PriceUniverseKey.create(city="Lund",postal_codes=["22350"],snapshot_ids=sorted({p.source_provenance.source_snapshot_id for p in products}),source_strategy_version="retained",normalizer_version="v1",taxonomy_version="v1")
    return PreparedPriceUniverse(universe=PriceUniverseBuilder().build(key,products,built_at=now),stores=tuple(Store(store_id=p.store_id,name=p.store_name,chain=p.chain,city="Lund",price_context_type=p.price_context_type,price_semantics="online_price" if "online" in (p.price_context_type or "").lower() else None) for p in {p.store_id:p for p in products}.values()),economic_pool=EconomicIngredientPool(),source_name="retained")
from backend.tests.test_product_search import search

ROWS=json.loads((Path(__file__).parent/'fixtures/comparability-products-20261010.json').read_text(encoding='utf8'))

@pytest.mark.parametrize('name,cost', [('Krispsallat',23.61),('Shi-take',46.9),('Aluminiumfolie',29.95)])
def test_actual_unknown_content_can_be_bought_as_explicit_packs(name,cost):
    product=next(Product.model_validate(p) for p in ROWS if name.casefold() in p['name'].casefold())
    prepared=prepare(product)
    rows=search(prepared,name,now=NOW)
    row=rows['results'][0]
    assert row['display_price']==cost
    choice=price_free_products(rows)[0]
    assert choice['selectable'] and choice['purchase_units']
    assert 'prices' not in choice
    assert product.package_quantity is None
    extra=ExtraNeed(kind='exact',query=product.name,quantity=2,unit='st',purchase_units=True,product_key=choice['product_key'],properties=interpretation(product.name),confirmed=True)
    request=PlanRequest(recipes=0,personal=PersonalPlanning(extras=[extra]))
    result=PersonalPlanner(request,Settings(price_provider='mock'),prepared,{'id':'sales-test','revision':0,'items':[],'reservations':{},'events':{}},now=NOW).create()
    assert result.optimized_basket.total==round(cost*2,2)
    item=result.optimized_basket.stores[0].items[0]
    assert item.purchase_units and item.packages_needed==2 and item.unit=='st'
    assert 'okänd innehållsmängd' in item.purchase_warning
    assert result.personal.checks['checkout_audit']['passed']
    assert product.package_quantity is None
    extra=extra.model_copy(update={'purchase_units':False,'unit':'g','quantity':150})
    request.personal.extras=[extra]
    with pytest.raises(PolicyConflict):
        PersonalPlanner(request,Settings(price_provider='mock'),prepared,{'id':'sales-test','revision':0,'items':[],'reservations':{},'events':{}},now=NOW).create()

@pytest.mark.parametrize('update',[{'quantity':1.5},{'unit':'g'},{'use_pantry':True},{'kind':'generic','product_key':None}])
def test_sales_unit_request_rejects_invalid_scope(update):
    with pytest.raises(ValidationError):
        ExtraNeed.model_validate({'kind':'exact','query':'Sallad','quantity':1,'unit':'st','purchase_units':True,'product_key':'a'*32,'confirmed':True}|update)

def test_old_request_json_unchanged():
    assert 'purchase_units' not in ExtraNeed(query='Kaffe',quantity=500,unit='g',confirmed=True).model_dump(mode='json')

from app.services.personal_store import PersonalStore
from app.services.plan_store import PlanOwnerMismatchError, PlanStore


def test_new_purchase_units_saved_restart_and_private_owner(tmp_path):
    extra=ExtraNeed(kind='exact',query='Aluminiumfolie',quantity=2,unit='st',purchase_units=True,product_key='a'*32,confirmed=True,generic=GenericRef(query='aluminiumfolie'))
    store=PersonalStore(PlanStore(tmp_path/'plans.sqlite'))
    state=store.update_shopping('a'*64,0,[extra])
    assert state['shopping_items'][0]['purchase_units']
    reopened=PersonalStore(PlanStore(tmp_path/'plans.sqlite'))
    assert reopened.read('a'*64)==state
    assert not reopened.read('b'*64).get('shopping_items')

@pytest.mark.parametrize('name',['Chips','Sverige-/Fullkornspasta','Crunchy','Porchetta'])
def test_actual_open_campaigns_and_lidl_weight_use_ordinary_planner(name,tmp_path):
    data=json.loads((Path(__file__).parent/'fixtures/comparability-campaigns-20261010.json').read_text(encoding='utf8'))
    p=next(Product.model_validate(row) for row in data if row['name']==name)
    prepared=prepare(p)
    result=search(prepared,name,now=NOW,memberships=['WILLYS_PLUS','ICA_STAMMIS','LIDL_PLUS'])
    row=price_free_products(result)[0]
    assert row['selectable']
    campaign=p.purchase_terms.variant_selection=='required'
    assert row['campaign_choice']==campaign
    amount=1 if campaign else 1000
    req=PlanRequest(recipes=0,purchase_planning_mode='estimated',membership_price_policy='all_advertised',personal=PersonalPlanning(extras=[ExtraNeed(kind='campaign' if campaign else 'exact',query=p.name,quantity=amount,unit='st' if campaign else 'g',product_key=row['product_key'],properties=interpretation(p.name),confirmed=True)]))
    plan=PersonalPlanner(req,Settings(price_provider='mock'),prepared,{'id':'campaign-test','revision':0,'items':[],'reservations':{},'events':{}},now=NOW).create()
    item=plan.optimized_basket.stores[0].items[0]
    assert plan.personal.checks['checkout_audit']['passed']
    if campaign:
        assert item.conditional_variant_choice and item.packages_needed==p.offers[0].required_packages
        assert item.total_price==p.offers[0].price and p.package_quantity is None
    else:
        assert item.quantity_confidence=='estimated'
    store=PlanStore(tmp_path/'plans.sqlite')
    saved=store.create(req,plan,owner_actor_hash='a'*64)
    reopened=PlanStore(tmp_path/'plans.sqlite').get_owned(saved.plan_id,owner_actor_hash='a'*64)
    assert reopened.plan.model_dump()==saved.plan.model_dump()
    with pytest.raises(PlanOwnerMismatchError):store.get_owned(saved.plan_id,owner_actor_hash='b'*64)


def test_missing_chain_is_coverage_gap_not_zero_defects():
    p=Product.model_validate(ROWS[0]);data=search(prepare(p),'kaffe',now=NOW)
    city=next(c for c in data['chain_coverage'] if c['chain']=='citygross')
    assert city['status']=='INELIGIBLE' and 'underlag' in city['next_step']
    assert data['live_provider_calls']==0
