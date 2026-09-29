"""Official retained declarations: exact identity, corrupt source, no price borrowing."""
import copy
import json
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest
from app.services import offer_catalog_facts as service
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

R=Path(__file__).parents[2]/'reports/offer-expansion-20260924'
SELECT=service.candidates


@pytest.fixture
def evidence(monkeypatch):
    prepared=PreparedPriceUniverseArtifact.model_validate_json((R/'prepared-1280-second.json').read_bytes()).restore()
    p=next(p for p in prepared.universe.products if p.chain=='willys' and p.name=='Pågenlimpan')
    records=json.loads((R/'catalog-fact-candidates.json').read_bytes())
    rows=next(rs for rs in records.values() if rs[0]['name']=='Pågenlimpan')
    monkeypatch.setattr(service,'candidates',lambda *_: {(p.store_id,p.product_id):rows})
    return p,rows


def test_verified_catalog_declaration_is_rebound_but_never_its_price(evidence):
    p,rows=evidence
    before=p.model_dump_json()
    f=service.complete([p],R/'base/grocery.sqlite',R/'base/raw')[(p.store_id,p.product_id)]
    assert f.nutrition=={'kcal':275,'fat_g':1.9,'carbs_g':52,'protein_g':9.6}
    assert f.observed_at==rows[0]['fetched_at']
    assert p.model_dump_json()==before and p.gtin is None
    assert service.matches_product(p,f)
    assert not service.matches_product(p.model_copy(update={'package_quantity':500}),f)
    assert not service.matches_product(p,replace(f,source_snapshot_id='other'))


@pytest.mark.parametrize('field,value', [('name','Pagen other'),('brand','Other'),
    ('package_quantity',500),('gtin','7310865004703')])
def test_raw_declaration_does_not_follow_changed_product(evidence,field,value):
    p,_=evidence
    # The raw recheck remains necessary even if a database candidate is corrupted.
    assert not service.complete([p.model_copy(update={field:value})],R/'base/grocery.sqlite',R/'base/raw')


def test_missing_or_replaced_raw_source_never_uses_cached_nutrition(evidence,tmp_path):
    p,rows=evidence
    assert not service.complete([p],R/'base/grocery.sqlite',tmp_path)
    for r in rows:
        dest=tmp_path/r['payload_location'];dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text('{}',encoding='utf8')
    assert not service.complete([p],R/'base/grocery.sqlite',tmp_path)


def test_ambiguous_supplier_gtin_cannot_attach_to_unknown_gtin_offer(evidence,tmp_path):
    p,rows=evidence
    r=copy.deepcopy(rows[0])
    path=tmp_path/'catalog.sqlite'
    sp={k:v for k,v in r.items() if k not in {'payload_hash','payload_location','http_status','declaration_url'}}
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE source_products ('+','.join(sp)+')')
        db.execute('CREATE TABLE catalog_snapshots (id,is_active,state,coverage)')
        db.execute('CREATE TABLE raw_snapshots (id,payload_hash,payload_location,http_status,url)')
        db.execute('INSERT INTO catalog_snapshots VALUES (?,1,?,?)',(r['catalog_snapshot_id'],'promoted','full_online_catalog'))
        db.execute('INSERT INTO raw_snapshots VALUES (?,?,?,?,?)',(r['raw_snapshot_id'],r['payload_hash'],r['payload_location'],200,r['declaration_url']))
        insert='INSERT INTO source_products VALUES ('+','.join('?' for _ in sp)+')'
        db.execute(insert,tuple(sp.values()))
        db.commit()
        assert SELECT([p],path)
        sp.update(id='different-supplier-variant',gtin='7310865004703')
        db.execute(insert,tuple(sp.values()));db.commit()
        assert not SELECT([p],path)

def test_declared_loaf_reaches_existing_cold_recipe_without_repricing(evidence):
    from datetime import date
    from types import SimpleNamespace

    from app.models.ingredient import NormalizedIngredient
    from app.models.recipe import Recipe, RecipeIngredient
    from app.services.basket_auditor import BasketAuditor
    from app.services.basket_calculator import BasketCalculator
    from app.services.personal_nutrition import calculation_basis
    from app.services.personal_planner import PersonalPlanner
    from app.services.product_matcher import ProductMatcher
    from app.services.user_pricing import price_candidate_for_context

    from grocery_data.app.domain.promotion_pricing import UserPricingContext
    p,_=evidence
    fact=service.complete([p],R/'base/grocery.sqlite',R/'base/raw')[(p.store_id,p.product_id)]
    recipe=Recipe(name='Uppmätt bröd som sålt',servings=1,
        ingredients=[RecipeIngredient(name='bröd',quantity=100,unit='g')],instructions=['Servera tillsammans.'])
    planner=SimpleNamespace(request=SimpleNamespace(purchase_planning_mode="exact"), spec=SimpleNamespace(allow_nutrition_estimates=True),source_facts=lambda _:fact)
    assert calculation_basis(recipe,allow_estimates=True)['method']=='sum_declared_edible_as_sold'
    nutrition=PersonalPlanner._nutrition_evidence(planner,p,'bröd','g',{'kcal','protein_g','carbs_g','fat_g'},recipe)
    assert nutrition and nutrition.nutrition['protein_g']==9.6
    need=NormalizedIngredient(canonical_name='bröd',required_quantity=100,unit='g')
    match=ProductMatcher().match(need,[p]);assert len(match)==1
    ctx=UserPricingContext.from_chain_flags({'willys':True})
    priced=price_candidate_for_context(match[0],ctx,on_date=date(2026,9,24))
    bought=BasketCalculator().calculate_item(need,priced)
    assert bought.packages_needed>=1
    assert BasketAuditor(pantry_items=frozenset()).audit([need],[bought],user_pricing_context=ctx).passed
    for name in ('Köttfärslimpa','Kycklinglimpa','Fisklimpa','Bananlimpa','Bakmix limpa'):
        assert not ProductMatcher().match(need,[p.model_copy(update={'name':name})])
