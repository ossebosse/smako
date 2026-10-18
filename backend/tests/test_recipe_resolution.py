"""Real supplier imports and synthetic negative contract boundaries."""
import json
from dataclasses import replace
from pathlib import Path

import pytest
from app.config import Settings
from app.models import Product
from app.models.personal import MealSettings, TasteProfile
from app.models.recipe import Recipe, RecipeIngredient
from app.services.nutrition_reference import reference_evidence
from app.services.official_product_facts import project_usable_quantity, supplement_catalog_facts
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.product_semantics import evaluate_product_semantics
from app.services.recipe_preparation import adapt, input_evidence

from backend.tests.test_personal_planning_v2 import NOW, prepared, product, request, state
from grocery_data.app.services.product_declarations import parse_declaration

ROOT=Path(__file__).parents[2]
REPORT=ROOT/'reports/recipe-resolution-20260926'

@pytest.fixture(scope='module')
def retained():
    return json.loads((REPORT/'profile/diagnose-before.json').read_text(encoding='utf-8'))['products']

def sourced(retained, gtin):
    row=next(r for r in retained if r['product']['gtin']==gtin and r['product']['chain']=='coop')
    p=Product.model_validate(row['product']);f=ProductFacts(**row['facts'])
    return p,supplement_catalog_facts([p],{(p.store_id,p.product_id):f})[(p.store_id,p.product_id)]

@pytest.mark.parametrize('gtin', ['07310867003803','07350002402955','07310130009785','07310130009822','07350002402979','07350002402962','07350027796824'])
def test_real_supplier_parser_scopes_consumer_not_transport(gtin):
    source=REPORT/'sources'/gtin
    row=parse_declaration(source.with_suffix('.html').read_bytes(),json.loads(source.with_suffix('.json').read_text()))
    assert row['gtin']==gtin
    assert row['net_quantity']<1000
    assert row['source']['observed_at']
    with pytest.raises(ValueError):parse_declaration(b'changed',row['source'])

def test_source_mass_and_volume_are_not_a_generic_density(retained):
    p,f=sourced(retained,'7310867003803')
    converted=project_usable_quantity(p,f)
    assert (p.package_quantity,p.package_unit,p.usable_unit)==(200,'ml','ml')
    assert (converted.package_unit,converted.usable_quantity,converted.usable_unit)==('ml',200,'g')
    assert p.price==converted.price and p.source_provenance==converted.source_provenance
    proof=f.field_sources['nutrition.protein_g'][-1]
    assert proof['operation']=='declared_per_100_ml * source_package_ml / source_net_g'
    assert proof['original_nutrition']['protein_g']==2.4
    assert not f.allergens_checked  # not promoted to allergen-safe
    other=p.model_copy(update={'gtin':'7310865003805','brand':'Arla Köket'})
    result=supplement_catalog_facts([other],{})
    assert project_usable_quantity(other,result.get((other.store_id,other.product_id))).usable_unit=='ml'

def test_drained_quantity_does_not_approve_drained_product_nutrition(retained):
    p,f=sourced(retained,'7350002402955');p=project_usable_quantity(p,f)
    assert p.usable_quantity==230 and p.package_quantity==380
    assert f.nutrition_preparation=='draining_unspecified'
    recipe=adapt(Recipe(name='Kikärtsgryta',servings=1,ingredients=[RecipeIngredient(name='kikärtor',quantity=200,unit='g')],instructions=['Sjud.']),'gryta')
    evidence=input_evidence(recipe,p,'kikärtor','g',False,f)
    assert evidence and evidence.nutrition==reference_evidence(3815).nutrition
    assert any(x.get('input_evidence_kind')=='generic_reference' for x in evidence.field_sources['nutrition.protein_g'])
    assert input_evidence(recipe,p,'kikärtor','g',False,replace(f,field_sources={})) is None

def test_conflicting_supplier_values_are_visible_and_blocked(retained):
    p,f=sourced(retained,'7310130009785')
    assert 'supplier_nutrition_conflict' in f.conflicts
    projected=project_usable_quantity(p,f)
    assert projected.usable_quantity==230 and projected.price==p.price
    recipe=adapt(Recipe(name='Böngryta',servings=1,ingredients=[RecipeIngredient(name='svarta bönor',quantity=200,unit='g')],instructions=['Sjud.']),'gryta')
    assert input_evidence(recipe,projected,'svarta bönor','g',False,f) is None
    assert project_usable_quantity(p,replace(f,conflicts=('unknown_identity_conflict',)))==p
    assert f.nutrition['protein_g']==7.4  # original retained, new contradictory source separate
    assert f.field_sources['supplier_nutrition_conflict'][0]['original_nutrition']['protein_g']==5.6

def test_shell_mass_projection_requires_separate_purchase_opt_in(retained):
    p,f=sourced(retained,'7300156482679')
    assert project_usable_quantity(p,f)==p
    estimate=project_usable_quantity(p,f,allow_estimates=True)
    assert estimate.usable_quantity==pytest.approx(636*.88)
    assert estimate.quantity_confidence=='estimated'
    assert estimate.price==p.price
    proof=f.field_sources['usable_quantity'][0]
    assert proof['quality']=='documented_population_estimate' and proof['page']
    recipe=adapt(Recipe(name='Äggrätt',servings=1,ingredients=[RecipeIngredient(name='ägg',quantity=100,unit='g')],instructions=['Stek.']),'panna')
    assert input_evidence(recipe,p,'ägg','g',True,f) is None
    assert input_evidence(recipe,estimate,'ägg','g',True,f) is not None
    count=p.model_copy(update={'package_quantity':12,'package_unit':'st'})
    counted=supplement_catalog_facts([count],{(count.store_id,count.product_id):replace(f,field_sources={})})[(count.store_id,count.product_id)]
    from app.services.official_product_facts import egg_standard_weight
    weight=egg_standard_weight(count.name)
    if weight is None:
        # Owner decision 2026-10-17: only M and L packs are counted as grams.
        assert not counted.field_sources
    else:
        (proof,)=counted.field_sources['usable_quantity']
        assert proof['basis']=='standard_egg_weight' and proof['quantity']==12*weight
        derived=project_usable_quantity(count,counted)
        assert derived.usable_unit=='g' and derived.quantity_confidence=='derived'

@pytest.mark.parametrize('name,expected',[('Rödlök',True),('Röd Lök',True),('Picklad Rödlök',False),('Rödlök Brynt Smör Chips',False),('Gul lök',False)])
def test_low_source_confidence_does_not_preempt_authoritative_matcher(name,expected):
    p=product(name,300,'g',15).model_copy(update={'semantic_confidence':'low'})
    q=prepared(p);f=ProductFacts(source='retained',source_product_id=p.product_id,source_snapshot_id='v2-frozen')
    planner=PersonalPlanner(request(),Settings(price_provider='mock'),q,state(),now=NOW,facts={(p.store_id,p.product_id):f})
    if expected:assert planner.resolve('rödlök',100,'g',profile=TasteProfile())
    else:
        with pytest.raises(PolicyConflict):planner.resolve('rödlök',100,'g',profile=TasteProfile())

@pytest.mark.parametrize('category',['Fläskfärs','Fläskfärs > Nötfärs'])
def test_broad_navigation_does_not_override_named_mixed_mince(category):
    p=product('Blandfärs',500,'g',55).model_copy(update={'category':category})
    assert evaluate_product_semantics('blandfärs',p).compatible
    assert not evaluate_product_semantics('nötfärs',p).compatible
    assert not evaluate_product_semantics('blandfärs',p.model_copy(update={'name':'Fläskfärs'})).compatible

def test_recipe_validation_cache_separates_units_version_and_policy():
    p=product('Rödlök',300,'g',15);q=prepared(p)
    planner=PersonalPlanner(request(),Settings(price_provider='mock'),q,state(),now=NOW)
    r=adapt(Recipe(name='Lökgryta',servings=1,ingredients=[RecipeIngredient(name='rödlök',quantity=100,unit='g')],instructions=['Sjud.']),'gryta')
    # Isolate cache behavior from an absent pantry oil in this synthetic setup.
    r=r.model_copy(update={'ingredients':r.ingredients[:1]})
    meal=MealSettings(meal_type='dinner',count=1,servings=1)
    clean=planner.clean_recipe(r,meal)
    assert planner.clean_recipe(r,meal) is clean
    bad=r.model_copy(update={'ingredients':[r.ingredients[0].model_copy(update={'unit':'ml'})]})
    with pytest.raises(PolicyConflict):planner.clean_recipe(bad,meal)
    changed=r.model_copy(update={'preparation':None})
    assert planner.clean_recipe(changed,meal) is not clean
    planner.request.purchase_planning_mode='estimated'
    assert planner.clean_recipe(r,meal) is not clean


def test_quantity_proof_is_bound_to_product_store_snapshot_and_package(retained):
    p,f=sourced(retained,'7310867003803')
    for changes in ({'product_id':'different'}, {'store_id':'different'}, {'package_quantity':500}, {'source_provenance':None}):
        other=p.model_copy(update=changes)
        assert project_usable_quantity(other,f)==other
    other=p.model_copy(update={'source_provenance':p.source_provenance.model_copy(update={'source_snapshot_id':'other'})})
    assert project_usable_quantity(other,f)==other


def test_source_paired_mass_keeps_native_volume_use_and_declared_values(retained):
    from app.services.official_product_facts import facts_for_quantity_unit
    p,f=sourced(retained,'7310867003803')
    assert project_usable_quantity(p,f,required_unit='ml')==p
    volume=facts_for_quantity_unit(p,f,'ml')
    assert volume.nutrition_unit=='ml'
    assert volume.nutrition['protein_g']==2.4
    assert f.nutrition_unit=='g'
    assert facts_for_quantity_unit(p.model_copy(update={'product_id':'other'}),f,'ml')==f
    assert project_usable_quantity(p,f,required_unit='g').usable_unit=='g'


@pytest.mark.parametrize('name',['Gravad Lax Skivad','Lax Gravad','Gravlax','Rimmad Torsk'])
def test_cured_fish_does_not_become_raw_fish_when_source_confidence_is_low(name):
    p=product(name,150,'g',50).model_copy(update={'semantic_confidence':'low'})
    need='torsk' if 'Torsk' in name else 'lax'
    assert not evaluate_product_semantics(need,p).compatible
    recipe=adapt(Recipe(name='Fiskgryta',servings=1,ingredients=[RecipeIngredient(name=need,quantity=100,unit='g')],instructions=['Sjud.']),'gryta')
    fact=ProductFacts(source='retained',source_product_id=p.product_id,source_snapshot_id='test',nutrition={'protein_g':20},nutrition_unit='g',nutrition_basis='per 100 g',nutrition_preparation='as_sold')
    assert input_evidence(recipe,p,need,'g',True,fact) is None


@pytest.mark.parametrize('identity',[1225,3816,3817,3761])
def test_new_slv_reference_keeps_its_actual_response_time(identity):
    from app.services.nutrition_reference import reference_data
    entry=reference_data()['foods'][str(identity)]
    acquisition=next(a for a in entry['acquisition'] if '/naringsvarden?' in a['url'])
    evidence=reference_evidence(identity)
    assert evidence.field_sources['nutrition.protein_g'][0]['retrieved_at']==acquisition['observed_at']
    assert acquisition['observed_at'].startswith('2026-09-26')


@pytest.mark.parametrize('name,need',[
    ('Soppgrönsaker & potatis','potatis'),
    ('Soppgrönsaker med morot','morot'),
    ('Burek Nötfärs Fryst','nötfärs'),
    ('Börek med ost','ost'),
])
def test_composite_food_is_not_its_named_component(name,need):
    p=product(name,500,'g',30)
    assert not evaluate_product_semantics(need,p).compatible


@pytest.mark.parametrize('name,need',[
    ('Tuc Ost','ost'),('Ärtor Gula Eko','ärtor'),('Poésie Torsk','fisk'),
    ('Burek Nötfärs Fryst','nötfärs'),
])
def test_retained_rebuild_products_preserve_actual_food_class(name,need):
    rows=json.loads((REPORT/'profile/rebuild-product-review.json').read_bytes())
    p=Product.model_validate(next(x for x in rows if x['name']==name))
    assert not evaluate_product_semantics(need,p).compatible


def test_broad_cheese_and_cracker_navigation_is_not_a_cracker_declaration():
    p=product('Hushållsost',1000,'g',80).model_copy(update={'category':'Ost & kex'})
    assert evaluate_product_semantics('ost',p).compatible


def test_recipe_cache_does_not_cross_product_universes_or_memberships():
    good=product('Rödlök',300,'g',15)
    bad=product('Picklad Rödlök',300,'g',15)
    recipe=Recipe(name='Rödlök',servings=1,ingredients=[RecipeIngredient(name='rödlök',quantity=100,unit='g')],instructions=['Skiva rödlöken.'])
    meal=MealSettings(meal_type='dinner',count=1,servings=1)
    settings=Settings(price_provider='mock')
    first=PersonalPlanner(request(),settings,prepared(good),state(),now=NOW)
    first.clean_recipe(recipe,meal)
    second=PersonalPlanner(request(),settings,prepared(bad),state(),now=NOW)
    assert second.clean_recipe_cache is not first.clean_recipe_cache
    with pytest.raises(PolicyConflict):second.clean_recipe(recipe,meal)
    plus_request=request().model_copy(update={'memberships':{'willys':True,'lidl':True}})
    plus=PersonalPlanner(plus_request,settings,prepared(good),state(),now=NOW)
    assert first.user.cache_identity != plus.user.cache_identity
    assert plus.clean_recipe_cache == {}
