"""PersonalPlanner regressions: real frozen meal and independent quality gates."""
from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.personal import TasteProfile
from app.models.recipe import Recipe, RecipeIngredient
from app.services.lidl_product_facts import reviewed_facts
from app.services.official_product_facts import declared_facts
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.product_planning_trace import ProductPlanningTrace

NOW = datetime(2026, 9, 24, 21, 16, tzinfo=UTC)
ROOT = Path(__file__).parents[2]

@pytest.fixture(scope='module')
def real():
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        (ROOT/'reports/purchase-planning-20260925/final/prepared-1281-second.json').read_bytes()).restore()
    facts = {**reviewed_facts(prepared.universe.products), **declared_facts(prepared.universe.products)}
    cheese = next(p for p in prepared.universe.products if p.name == 'Hushållsost')
    return prepared, facts, cheese


def request(store, mode='estimated'):
    return PlanRequest.model_validate({'recipes':0, 'max_stores':1, 'allowed_store_ids':[store],
        'purchase_planning_mode':mode, 'memberships':{'lidl':True}, 'personal':{'allow_nutrition_estimates':True,
        'meals':[{'meal_type':'breakfast','count':1,'servings':1,'limits':{'min_protein_g':30}}],
        'slots':[{'id':'breakfast-1','day':1,'meal_type':'breakfast','recipe':{
            'name':'Ostsmörgås','servings':1,
            'ingredients':[{'name':'bröd','quantity':100,'unit':'g'},{'name':'ost','quantity':100,'unit':'g'}],
            'instructions':['Servera tillsammans.']}}]}})


def planner(real, req, now=NOW):
    p, facts, _ = real
    return PersonalPlanner(req, Settings(price_provider='mock'), p,
        {'revision':0,'items':[],'reservations':{},'events':{}}, facts=facts, now=now)


def test_real_meal_uses_whole_approximate_pack_and_only_used_grams(real, tmp_path):
    from app.services.plan_store import PlanStore
    _, _, cheese = real
    req = request(cheese.store_id)
    result = planner(real, req).create()
    items = [i for s in result.optimized_basket.stores for i in s.items]
    row = next(i for i in items if i.product_id == cheese.product_id)
    assert row.total_price == 153.78 and row.packages_needed == 1
    assert row.required_quantity == 100 and row.purchased_quantity == 2200
    assert row.waste_quantity == 2100 and row.verification_status == 'VERIFIED_WITH_ESTIMATES'
    assert result.personal.checks['nutrition'][0]['values']['protein_g'] >= 30
    assert result.personal.checks['checkout_audit']['passed']
    store = PlanStore(tmp_path/'plans.sqlite')
    saved = store.create(req,result,owner_actor_hash='a'*64)
    restored = PlanStore(tmp_path/'plans.sqlite').get_owned(saved.plan_id,owner_actor_hash='a'*64)
    assert restored.plan == result and restored.request.allowed_store_ids == (cheese.store_id,)


@pytest.mark.parametrize('failure', ['exact','allergy','expired','store','ml','weight-limit','membership'])
def test_real_meal_keeps_critical_gates(real, failure):
    _, _, cheese = real
    req = request(cheese.store_id)
    now = NOW
    if failure == 'membership': req.memberships={'lidl':False}
    if failure == 'exact': req.purchase_planning_mode = 'exact'
    if failure == 'allergy': req.personal.profile = TasteProfile(allergies=['mjölk'])
    if failure == 'expired': now = datetime(2026,9,28,12,tzinfo=UTC)
    if failure == 'store': req.allowed_store_ids = ('not-a-real-store',)
    if failure == 'ml':
        recipe=req.personal.slots[0].recipe
        req.personal.slots[0].recipe=recipe.model_copy(update={'ingredients':[
            RecipeIngredient(name='ost',quantity=100,unit='ml'),recipe.ingredients[0]]})
    if failure == 'weight-limit':
        req.personal.meals[0].limits.min_weight_g=190 # no invented final/edible-weight evidence
    with pytest.raises(PolicyConflict): planner(real,req,now).create()


def test_trace_cache_retains_recipe_context_and_limits(real):
    p, _, cheese=real
    req=request(cheese.store_id, 'exact')
    engine=planner(real,req)
    for title in ('first','second'):
        recipe=Recipe(name=title,servings=1,ingredients=[RecipeIngredient(name='ost',quantity=100,unit='g')],instructions=['Servera tillsammans.'])
        with pytest.raises(PolicyConflict): engine.resolve('ost',100,'g',profile=TasteProfile(),recipe=recipe)
    traced=next(r for r in engine.product_trace.snapshot()['products'] if r['product_id']==cheese.product_id)
    assert {c['recipe']['name'] for c in traced['contexts']}=={'first','second'}
    assert all(c['first_stop']['stage']=='price_contract' for c in traced['contexts'])
    trace=ProductPlanningTrace(p,limit=1,event_limit=1)
    product=next(x for x in p.universe.products if (x.store_id,x.product_id) in trace.products)
    for name in ('one','two'):
        trace.event(product,None,name,'price','stopped','unknown')
    assert trace.snapshot()['omitted_products'] > 0 and trace.snapshot()['omitted_context_events']==1


def test_explicit_store_selection_is_validated_and_not_silently_ignored():
    assert PlanRequest(allowed_store_ids=['x']).allowed_store_ids == ('x',)
    with pytest.raises(ValueError): PlanRequest(allowed_store_ids=[' '],personal={})
    with pytest.raises(ValueError): PlanRequest(allowed_store_ids=['x','x'],personal={})
    assert 'allowed_store_ids' not in PlanRequest().model_dump(mode='json')


def test_declaration_classification_is_not_name_or_campaign_permission(real):
    from dataclasses import replace

    from app.services.declaration_semantics import declaration_food_class, document_classification
    prepared, facts, _ = real
    bread=next(p for p in prepared.universe.products if p.name=='Lingongrova')
    fact=facts[(bread.store_id,bread.product_id)]
    assert declaration_food_class(bread,fact)=='bröd'
    assert declaration_food_class(bread.model_copy(update={'gtin':'7311071330526'}),fact) is None
    assert declaration_food_class(bread,replace(fact,product_classification=('Matbröd','changed'))) is None
    assert document_classification('Välsmakande bröd nämns bara i ett recept')==()
    assert document_classification('Dabas produktklassificering 123 / Färskvaror -- Konditorivaror Märkning')==('Färskvaror','Konditorivaror')
    # The enriched candidate retains the real price, source identity and name.
    req=request(bread.store_id);engine=planner(real,req)
    candidates=engine.resolve('bröd',100,'g',profile=TasteProfile())
    candidate=next(c for _,c in candidates if c.product_id==bread.product_id)
    assert candidate.product_name==bread.name and candidate.price is None
    assert candidate.source_provenance==bread.source_provenance
    assert candidate.selected_membership_program=='LIDL_PLUS'


def test_resolver_cache_and_beam_are_observed_without_claiming_economic_loss(real):
    _,_,cheese=real
    req=request(cheese.store_id);engine=planner(real,req)
    recipe=req.personal.slots[0].recipe
    for title in ('one','two'):
        engine.resolve('ost',100,'g',profile=TasteProfile(),recipe=recipe.model_copy(update={'name':title}))
    row=engine.product_trace.products[(cheese.store_id,cheese.product_id)]
    assert {c['recipe']['name'] for c in row['contexts'].values()}=={'one','two'}
    assert all(c['first_stop'] is None for c in row['contexts'].values())
    result=engine.create()
    trace=result.personal.checks['planning_diagnostics']['product_decisions']
    search=next(r for r in trace['recipe_search'] if r['recipe']['name']=='Ostsmörgås')
    assert search['events']['priced']['example_basket']['quality']=='VERIFIED_WITH_ESTIMATES'
    assert search['events']['retained']['count']>=1
    assert not trace['whole_basket_comparisons']  # no hidden economic rejection assertion


def test_derived_canonical_names_do_not_split_trace_identity():
    from app.services.product_planning_trace import recipe_identity
    recipe=Recipe(name='Ost',servings=1,ingredients=[RecipeIngredient(name='ost',quantity=100,unit='g')],instructions=['Servera tillsammans.'])
    clean=recipe.model_copy(update={'ingredients':[recipe.ingredients[0].model_copy(update={'canonical_name':'ost'})]})
    assert recipe_identity(recipe)==recipe_identity(clean)


def test_estimated_price_candidate_is_not_conditional_on_loading_nutrition(real):
    prepared, _, cheese=real
    req=request(cheese.store_id)
    engine=PersonalPlanner(req, Settings(price_provider='mock'),prepared,
        {'revision':0,'items':[],'reservations':{},'events':{}},facts={},now=NOW)
    candidates=engine.resolve('ost',100,'g',profile=TasteProfile())
    selected=next(c for _,c in candidates if c.product_id==cheese.product_id)
    assert selected.purchase_terms.usage=='estimated'
    assert not engine.facts
    # Qualification remains independent: a price candidate is not nutrition evidence.
    assert engine.nutrition_evidence(cheese,'ost','g',{'protein_g'},req.personal.slots[0].recipe) is None


def test_later_recipe_rejection_does_not_claim_product_was_never_evaluated(real):
    p,_,cheese=real
    trace=ProductPlanningTrace(p)
    recipe=request(cheese.store_id).personal.slots[0].recipe
    trace.event(cheese,recipe,'ost','nutrition','passed','applicable declaration')
    trace.recipe(recipe,'nutrition','whole meal below target')
    row=trace.products[(cheese.store_id,cheese.product_id)]
    assert not row.get('unreached_recipes')
    assert next(iter(row['recipe_outcomes'].values()))['product_evaluated'] is True
    assert next(iter(row['contexts'].values()))['first_stop'] is None
