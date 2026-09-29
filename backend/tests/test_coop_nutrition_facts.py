"""Actual saved Coop declarations and physical offers; no new price assertions."""
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from app.models import Product, SourceProvenance
from app.services.nutrition_reference import product_reference
from app.services.personal_source_facts import complete_coop_retailer_facts, project_raw_facts

F=Path(__file__).parent/'fixtures/coop-nutrition-20260922'

def pair():
    record=json.loads((F/'catalog.json').read_bytes())[0]
    raw=record['raw'];ev=record['evidence']
    offer=next(p for p in json.loads((F/'offers.json').read_bytes()) if p['name']==raw['name'].strip())
    source=SourceProvenance(source_provider='own',source_channel='catalog',
        source_snapshot_id=ev['catalog_snapshot_id'],source_observed_at=ev['fetched_at'],provider_store_id='730400')
    donor=Product(product_id=ev['id'],name=raw['name'].strip(),canonical_name='ost',category='ost',
        store_id='online',store_name='Coop Online',chain='coop',brand=raw['manufacturerName'],
        gtin=raw['ean'],price=raw['salesPriceData']['b2cPrice'],package_quantity=raw['packageSize'],
        package_unit='g',sale_model='fixed_package',source_provenance=source)
    target=donor.model_copy(update={'product_id':offer['external_product_id'],'store_id':'physical',
        'store_name':'Värpinge','brand':offer['brand'],'gtin':None,'price':None,
        'coverage':'offers_only','price_context_type':'physical_store',
        'source_provenance':source.model_copy(update={'source_channel':'offers','source_snapshot_id':'physical-snapshot',
            'provider_store_id':'3659','source_observed_at':datetime.fromisoformat(offer['fetched_at']),
            'retailer_product_id':offer['source_fields']['source_variant_id'],
            'retailer_id_namespace':'coop:public-product',
            'retailer_identity_source_sha256':offer['source_fields']['source_sha256']})})
    fact=project_raw_facts(raw,chain='coop',product_id=donor.product_id,snapshot_id=source.source_snapshot_id,
        source_reference=ev['raw_reference']+':'+ev['payload_hash'],observed_at=ev['fetched_at'])
    return donor,target,fact

def connect(donor,target,fact,extra=()):
    original={(donor.store_id,donor.product_id):fact}
    original.update({(p.store_id,p.product_id):f for p,f in extra})
    pool=SimpleNamespace(universe=SimpleNamespace(products=[donor,target,*[p for p,f in extra]]))
    return complete_coop_retailer_facts(pool,original)

def test_real_catalog_facts_reused_without_price_gtin_or_observation_transfer():
    d,t,f=pair();before=deepcopy(t.model_dump())
    result=connect(d,t,f);new=result[(t.store_id,t.product_id)]
    assert new.nutrition['protein_g']==25
    assert new.nutrition_unit=='g' and new.nutrition_preparation=='as_sold'
    assert new.source_product_id==t.product_id and new.source_snapshot_id=='physical-snapshot'
    assert new.observed_at==f.observed_at
    assert new.field_sources['retailer_identity'][0]['catalog_ean']=='5000246727094'
    assert t.model_dump()==before and t.gtin is None and t.price is None
    assert result[(d.store_id,d.product_id)]==f

@pytest.mark.parametrize('fault',['namespace','id','pack','brand','variant','time','scope','hash','conflicting_donor'])
def test_ambiguous_or_incompatible_join_does_not_propagate(fault):
    d,t,f=pair();p=t.source_provenance;extra=()
    if fault=='namespace':p=p.model_copy(update={'retailer_id_namespace':'other:product'})
    if fault=='id':p=p.model_copy(update={'retailer_product_id':'other-id'})
    if fault=='hash':p=p.model_copy(update={'retailer_identity_source_sha256':None})
    if fault=='time':p=p.model_copy(update={'source_observed_at':p.source_observed_at+timedelta(days=8)})
    t=t.model_copy(update={'source_provenance':p})
    if fault=='pack':t=t.model_copy(update={'package_quantity':450})
    if fault=='brand':t=t.model_copy(update={'brand':'other'})
    if fault=='variant':t=t.model_copy(update={'name':'Cheddar Mature 26%'})
    if fault=='scope':t=t.model_copy(update={'price_context_type':'online_fulfillment'})
    if fault=='conflicting_donor':
        alt=d.model_copy(update={'store_id':'other-catalog'})
        extra=((alt,replace(f,nutrition={'protein_g':20})),)
    assert (t.store_id,t.product_id) not in connect(d,t,f,extra)

def test_real_less_than_carbs_is_retained_as_limit_not_exact_nutrition():
    _,_,f=pair()
    assert 'carbs_g' not in f.nutrition and not f.conflicts
    assert f.field_sources['nutrition_limits'][0]['accuracy']=='LESS_THAN'
    assert f.field_sources['nutrition_limits'][0]['amount']==['0.5']
    assert f.nutrition['protein_g']==25

@pytest.mark.parametrize('name',['Plommontomat','Tomater Plommon','Plommontomater'])
def test_fresh_tomato_aliases_keep_existing_364_reference(name):
    _,t,_=pair();t=t.model_copy(update={'name':name})
    assert product_reference(t,'tomat',None)==364

@pytest.mark.parametrize('name',['Tomater Plommon Torkade','Plommontomat inlagd','Plommontomat sås'])
def test_prepared_tomato_not_raw_reference(name):
    _,t,_=pair();t=t.model_copy(update={'name':name})
    assert product_reference(t,'tomat',None) is None

def test_fresh_fettuccine_cannot_become_reviewed_dry_pasta():
    _,t,_=pair();t=t.model_copy(update={'name':'Färsk Pasta Fettuccine'})
    assert product_reference(t,'pasta',None) is None


def test_tomato_alias_does_not_enable_estimates_without_existing_opt_in():
    from app.services.personal_planner import PersonalPlanner

    _, product, _ = pair()
    product = product.model_copy(update={'name': 'Plommontomat'})
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=False),
                              source_facts=lambda p: None)
    assert PersonalPlanner._nutrition_evidence(planner, product, 'tomat', 'g', {'protein_g'}, None) is None
    planner.spec.allow_nutrition_estimates = True
    result = PersonalPlanner._nutrition_evidence(planner, product, 'tomat', 'g', {'protein_g'}, None)
    assert result is not None
    assert result.source != 'product_declaration'


def test_retained_cache_cannot_bless_a_changed_target_identity(tmp_path):
    import hashlib
    import sqlite3

    from app.services.personal_source_facts import load_retained_facts

    donor, target, _ = pair()
    raw = json.loads((F/'catalog.json').read_bytes())[0]['raw']
    payload = json.dumps({'results': {'items': [raw]}}).encode()
    (tmp_path/'catalog.json').write_bytes(payload)
    db = tmp_path/'source.sqlite'
    with sqlite3.connect(db) as con:
        con.execute('CREATE TABLE products (id, chain, external_product_id, store_external_id, raw_reference, raw_snapshot_id, catalog_snapshot_id)')
        con.execute('CREATE TABLE raw_snapshots (id, payload_hash, payload_location, catalog_snapshot_id)')
        snapshot = donor.source_provenance.source_snapshot_id
        con.execute('INSERT INTO products VALUES (?,?,?,?,?,?,?)',
            (donor.product_id,'coop',raw['id'],'730400','raw:fixture#results.items[0]','raw',snapshot))
        con.execute('INSERT INTO raw_snapshots VALUES (?,?,?,?)',
            ('raw',hashlib.sha256(payload).hexdigest(),'catalog.json',snapshot))
    pool = SimpleNamespace(universe=SimpleNamespace(products=[donor,target],universe_id='same-source-version'),
                           product_search_index=SimpleNamespace(groups={}))
    before = load_retained_facts(pool,database=db,raw_root=tmp_path)
    assert (target.store_id,target.product_id) in before
    pool.universe.products = [donor,target.model_copy(update={'package_quantity':450})]
    after = load_retained_facts(pool,database=db,raw_root=tmp_path)
    assert (target.store_id,target.product_id) not in after


def test_real_declared_upper_bound_cannot_satisfy_exact_carbohydrate_requirement():
    from app.services.personal_planner import PersonalPlanner

    donor, target, fact = pair()
    mapped = connect(donor,target,fact)[(target.store_id,target.product_id)]
    planner = SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=True),
                              source_facts=lambda p: mapped)
    assert PersonalPlanner._nutrition_evidence(planner,target,'ost','g',{'protein_g'},None) is not None
    assert PersonalPlanner._nutrition_evidence(planner,target,'ost','g',{'carbs_g'},None) is None
