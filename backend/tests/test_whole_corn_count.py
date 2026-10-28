"""Whole-piece purchase identity, immutable recipes and unknown edible mass."""
import copy
import json
from dataclasses import replace

import pytest
from app.models.provenance import SourceProvenance
from app.services import intake_product_links as links
from app.services.official_product_facts import project_usable_quantity
from app.services.personal_policy import ProductFacts
from app.services.purchase_quantity_resolver import PurchaseQuantityResolver

from backend.tests.test_personal_planning_v2 import product

KEY = 'intake_all_shape_frozen_whole_corn_count'


@pytest.fixture
def corn(monkeypatch):
    row = copy.deepcopy(links.entries()[KEY])
    proof = row['reviewed_links'][0]
    p = product(proof['name'], 400, 'g', 20, identity=proof['product_id'], store=proof['store_id']).model_copy(
        update={'brand':proof['brand'], 'category':proof['category'], 'gtin':proof['gtin'],
                'source_provenance':SourceProvenance.model_validate(proof['source_provenance'])})
    fact = ProductFacts(source='test-exact-manufacturer-declaration', source_product_id=p.product_id,
        source_snapshot_id=p.source_provenance.source_snapshot_id,
        ingredients=('2 majskolvar. Förvällda.',), ingredients_complete=True,
        ingredient_evidence_kind='product_declaration')
    assert links.composition_signature(fact) == proof['composition_sha256']
    monkeypatch.setattr(links, 'entries', lambda: {KEY:row})
    links._quantity_reviews.cache_clear()
    yield p, fact, row, proof
    links._quantity_reviews.cache_clear()


def test_declared_count_buys_whole_packages_and_preserves_gross_source(corn):
    p, fact, row, _ = corn
    original = p.model_dump()
    counted = project_usable_quantity(p, fact, required_unit='st')
    assert counted.usable_quantity == 2 and counted.usable_unit == 'st'
    assert counted.quantity_confidence == 'exact'
    assert counted.package_quantity == 400 and counted.package_unit == 'g'
    assert links.ingredient_product('majskolv', 'as_sold', row['requirements'], counted, fact)
    quote = PurchaseQuantityResolver().resolve(counted, required_quantity=3, required_unit='st')
    assert quote.resolved and quote.packages_needed == 2 and quote.total_price == 40
    assert quote.purchased_quantity == 800 and quote.purchased_unit == 'g'
    assert quote.purchased_usable_quantity == 4 and quote.usable_unit == 'st' and quote.waste_quantity == 1
    assert p.model_dump() == original
    for unit in ('g', 'ml', None):
        assert project_usable_quantity(p, fact, allow_estimates=True, required_unit=unit) is p


@pytest.mark.parametrize('field,value', [
    ('name','Majskorn'), ('brand','Other'), ('gtin','unreviewed'), ('package_quantity',800),
    ('package_unit','ml'), ('store_id','other-context'), ('sale_model','sold_by_weight'),
    ('quantity_confidence','estimated'), ('source_provenance',None),
])
def test_different_product_or_uncertain_package_cannot_borrow_count(corn, field, value):
    p, fact, _, _ = corn
    changed = p.model_copy(update={field:value})
    assert project_usable_quantity(changed, fact, required_unit='st') is changed


@pytest.mark.parametrize('value', [0, -1, True, 2.0, 2.5, 100000, None])
def test_invalid_or_unverified_count_is_not_a_quantity(corn, value):
    p, fact, _, proof = corn
    proof['quantity']['usable_quantity'] = value
    assert project_usable_quantity(p, fact, required_unit='st') is p


@pytest.mark.parametrize('field', ['sha256','url','consumer_gtin','declared_piece_count','declared_net_g','evidence_kind'])
def test_count_requires_complete_exact_manufacturer_proof(corn, field):
    p, fact, _, proof = corn
    proof['quantity']['source'].pop(field)
    assert project_usable_quantity(p, fact, required_unit='st') is p


def test_new_price_reuses_content_but_requires_current_facts_and_context(corn):
    p, fact, _, _ = corn
    fresh = p.model_copy(update={'product_id':'new-row','price':30,'sale_price':30,'effective_price':30,
        'source_provenance':p.source_provenance.model_copy(update={'source_snapshot_id':'new-price-source'})})
    current_fact = replace(fact, source_product_id=fresh.product_id, source_snapshot_id='new-price-source')
    counted = project_usable_quantity(fresh, current_fact, required_unit='st')
    assert counted.usable_quantity == 2 and counted.price == 30
    assert counted.source_provenance.source_snapshot_id == 'new-price-source'
    assert project_usable_quantity(fresh, fact, required_unit='st') is fresh
    for changed in (None, replace(current_fact, ingredients_complete=False),
                    replace(current_fact, ingredients=('Majskorn',)),
                    replace(current_fact, conflicts=('package_quantity',))):
        assert project_usable_quantity(fresh, changed, required_unit='st') is fresh


def test_frozen_successors_scale_count_and_keep_originals_and_unknown_nutrition():
    from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
    from app.services.recipe_library import _scaled, current_recipes, validate_recipe_design
    from app.services.recipe_preparation import input_evidence

    review = json.loads((ROOT.parents[3]/'docs/reviews/whole-corn-20261028/recipe-review.json').read_bytes())
    manifest = manifest_entries()
    history = {identity(r):r for r in load_entries([*manifest['current'], *manifest['history']], ROOT)}
    current = {identity(r):r for r in current_recipes()}
    assert len(review['corrected']) == 2
    for transition in review['corrected']:
        old = history[transition['previous_id']]
        new = current[transition['runtime_id']]
        assert old.design.content_sha256 == transition['before_content_sha256']
        assert transition['previous_id'] not in current
        assert any('hel rå majskolv' in s.text for s in old.design.steps)
        assert any('direkt från frysen' in s.text for s in new.design.steps)
        assert new.design.provenance.cooking_test == 'not_cooked'
        for servings in (1, 2, 4, 12):
            scaled = _scaled(new, servings)
            assert validate_recipe_design(scaled)
            corn = next(i for i in scaled.ingredients if i.canonical_name == 'majskolv')
            assert (corn.quantity, corn.unit, corn.form) == (servings, 'st', 'as_sold')
            assert links.gross_purchase_input(scaled, 'majskolv')
            assert input_evidence(scaled, None, 'majskolv', 'st', None, None) is None
            assert not links.ingredient_product('majskolv', 'raw_edible', corn.product_requirements, None)
        for before, after in zip(old.ingredients, new.ingredients, strict=True):
            if before.canonical_name != 'majskolv':
                assert before == after


def test_count_cannot_be_declared_as_raw_edible_mass():
    from app.services.recipe_library import _structural_check, current_recipes

    recipe = next(r for r in current_recipes() if any(KEY in requirement for i in r.ingredients
                  for requirement in i.product_requirements or ()))
    changed = recipe.model_copy(update={'ingredients': [
        i.model_copy(update={'form':'raw_edible'}) if i.canonical_name == 'majskolv' else i
        for i in recipe.ingredients]})
    with pytest.raises(ValueError, match='massa, volym eller antal'):
        _structural_check(changed)


def test_count_and_gross_mass_stay_separate_in_purchase_and_consumption(tmp_path):
    from app.models.personal import MealSettings, MealSlot
    from app.models.recipe import RecipeIngredient
    from app.services.personal_store import PersonalConflict, PersonalStore
    from app.services.plan_store import PlanStore

    from backend.tests.test_personal_booked_revisions import OWNER
    from backend.tests.test_personal_planning_v2 import prepared, recipe, request, run

    # Exercise the existing ledger with an already-qualified count projection.
    # Source qualification and exact manufacturer identity are tested above.
    p = prepared(product('majskolv',400,'g',20,usable_quantity=2,usable_unit='st'))
    food = recipe(ingredients=[RecipeIngredient(name='majskolv',quantity=3,unit='st')])
    req = request(slots=[MealSlot(id='dinner',day=1,meal_type='dinner',recipe=food)],
        meals=[MealSettings(count=1,servings=1)])
    plans = PlanStore(tmp_path/'plans.sqlite')
    private = PersonalStore(plans)
    saved = plans.create(req,run(p,req),owner_actor_hash=OWNER)
    stock = private.read(OWNER)
    item = saved.plan.optimized_basket.stores[0].items[0]
    assert (item.purchased_quantity,item.purchased_unit,item.purchased_usable_quantity,item.unit) == (800,'g',4,'st')
    with pytest.raises(PersonalConflict,match='verklig användbar inköpsmängd'):
        private.inventory_action(OWNER,saved,'purchase',stock['revision'])
    assert private.read(OWNER) == stock
    key = f'{item.store_id}|{item.product_id}|{item.ingredient}'
    bought = private.inventory_action(OWNER,saved,'purchase',stock['revision'],measured_purchase_quantities={key:4})
    assert [(i['quantity'],i['unit']) for i in bought['items']] == [(4,'st')]
    consumed = private.inventory_action(OWNER,saved,'consume',bought['revision'])
    assert [(i['quantity'],i['unit']) for i in consumed['items']] == [(1,'st')]
    assert consumed['ledger'][0] == bought['ledger'][0]
    assert [(r['quantity'],r['unit']) for r in consumed['ledger'][-1]['rows']] == [(3,'st')]
