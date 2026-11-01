"""Leaf estimates plan purchases; only real measured leaves become leaf stock."""
import json
from copy import deepcopy
from dataclasses import replace

import pytest
from app.config import Settings
from app.models import Store
from app.models.personal import MintLeafTrimming, PantryItem, PersonalMutation, PreparedOrigin
from app.models.product import SemanticConfidence
from app.models.recipe_preferences import RecipePreferences
from app.services.ingredient_preparations import (
    MINT_LEAF_KEY,
    MINT_LEAVES,
    MINT_OPERAND,
    estimated_outputs,
    input_quantity,
    method_for,
    mint_reference,
)
from app.services.meal_library_content import ROOT, identity, load_entries, manifest_entries
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict, ProductFacts
from app.services.personal_store import PersonalConflict, write_state
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.recipe_library import current_recipes

from backend.tests.test_mint_review import mint  # noqa: F401 -- shared exact-source fixture
from backend.tests.test_personal_booked_revisions import OWNER, setup_plan
from backend.tests.test_personal_planning_v2 import prepared, request, state


def issued():
    return next(r for r in current_recipes() if method_for(r, 'mynta') == MINT_LEAVES)


@pytest.fixture
def planner(mint):  # noqa: F811 -- pytest injects the imported exact-source fixture
    _registry, _proof, raw = mint
    raw = raw.model_copy(update={'chain': raw.source_provenance.chain, 'semantic_confidence': SemanticConfidence.LOW})
    fact = ProductFacts(source='fixture', source_product_id=raw.product_id,
                        source_snapshot_id=raw.source_provenance.source_snapshot_id)
    req = request(allow_nutrition_estimates=True).model_copy(update={'purchase_planning_mode': 'estimated',
        'recipe_preferences': RecipePreferences(mode='complete')})
    base = prepared()
    universe = PriceUniverseBuilder().build(PriceUniverseKey.create(city='Lund', postal_codes=['22350'],
        snapshot_ids=[raw.source_provenance.source_snapshot_id], source_strategy_version='fixture',
        normalizer_version='v1', taxonomy_version='v1'), [raw], built_at=raw.source_provenance.source_observed_at)
    base = replace(base, universe=universe, stores=(Store(store_id=raw.store_id, name=raw.store_id,
                   chain=raw.chain, city='Lund'),))
    p = PersonalPlanner(req, Settings(price_provider='mock', complete_recipes_enabled=True), base, state(),
                        facts={(raw.store_id, raw.product_id): fact}, now=raw.source_provenance.source_observed_at)
    return p, raw


def test_issued_leaf_method_preserves_gross_purchase_and_cannot_borrow_generic_nutrients(planner):
    p, raw = planner
    candidates = p.resolve('mynta', 10, 'g', recipe=issued(), profile=p.spec.profile)
    assert candidates and candidates[0][1].usable_quantity == 21.25
    assert raw.package_quantity == 25
    assert input_quantity(MINT_LEAVES, {'mynta': 10}) == pytest.approx(10 * .85 / .5464)
    assert estimated_outputs(MINT_LEAVES, input_quantity(MINT_LEAVES, {'mynta': 10})) == {'mynta': 10}
    assert p.nutrition_evidence(raw, 'mynta', 'g', {'protein_g'}, issued()) is None
    p.request = p.request.model_copy(update={'purchase_planning_mode': 'exact'})
    with pytest.raises(PolicyConflict, match='uppskattningsläge'):
        p.resolve('mynta', 10, 'g', recipe=issued())


def test_old_leaf_recipe_and_edited_method_are_not_authority(planner):
    p, _raw = planner
    review = json.loads((ROOT.parents[3] / 'docs/reviews/mint-leaf-preparation-20261028/recipe-review.json').read_bytes())
    manifest = manifest_entries()
    all_issued = {identity(r): r for r in load_entries([*manifest['current'], *manifest['history']])}
    assert len(review['corrected']) == 40 and len(current_recipes()) == 2727
    for row in review['corrected']:
        before, after = (all_issued[row[k]] for k in ('previous_id', 'runtime_id'))
        assert before.design.content_sha256 == row['previous_sha256']
        assert after.design.content_sha256 == row['content_sha256']
        assert method_for(before, 'mynta') is None and method_for(after, 'mynta') == MINT_LEAVES
        assert after.design.active_minutes == before.design.active_minutes + 3
        assert after.design.total_minutes == before.design.total_minutes + 3
        assert after.design.waiting_minutes == before.design.waiting_minutes
        assert all(new == (old.model_copy(update={'product_requirements': (*old.product_requirements, MINT_OPERAND)})
                           if old.canonical_name == 'mynta' else old)
                   for old, new in zip(before.ingredients, after.ingredients, strict=True))
        assert all('pack:' + MINT_LEAF_KEY in i.product_requirements for i in after.ingredients if i.canonical_name == 'mynta')
    with pytest.raises(ValueError):
        p.resolve('mynta', 10, 'g', recipe=issued().model_copy(update={'instructions': ['Made up']}))
    with pytest.raises(PolicyConflict):
        p.resolve('mynta', 10, 'g', recipe=all_issued[review['corrected'][0]['previous_id']], profile=p.spec.profile)


def test_changed_source_and_quantity_conflict_still_block_leaf_method(planner):
    p, raw = planner
    key = (raw.store_id, raw.product_id)
    p.facts[key] = replace(p.facts[key], conflicts=('quantity.unknown',))
    with pytest.raises(PolicyConflict):
        p.resolve('mynta', 10, 'g', recipe=issued(), profile=p.spec.profile)


def test_generic_and_leaf_demands_share_purchase_without_double_allocating_raw_mint(planner):
    p, _raw = planner
    key = p.product_keys[0]
    raw = PantryItem(name='mynta', quantity=5, unit='g', product_key=key)
    p.items = [raw.model_dump()]
    available, allocations = {raw.id: 5}, []
    rows = [{'name': 'mynta', 'unallocated_quantity': q, 'unit': 'g', 'source': k, 'demand_key': k,
             **({'preparation': MINT_LEAVES} if k != 'generic' else {})}
            for k, q in [('leaf1', 3), ('leaf2', 7), ('generic', 2)]]
    groups = [{'name': 'mynta', 'positions': {0}, 'demand_keys': ['leaf1', 'leaf2', 'generic']}]
    result = p._prepare_groups(groups, rows, allocations, available)
    assert len(result) == 1 and groups[0]['quantity'] == pytest.approx(2 + 10 * .85 / .5464 - 5)
    assert result[0]['estimated_outputs_g'] == {'mynta': 10}
    assert available[raw.id] == 0 and sum(a['quantity'] for a in allocations) == 5


def measured_plan(tmp_path):
    _p, plans, private, saved, stock = setup_plan(tmp_path)
    stock['items'] = [PantryItem(id='mint-lot', name='mynta', quantity=100, unit='g', product_key='a' * 32).model_dump()]
    stock['reservations'][saved.plan_id] = [{'item_id': 'mint-lot', 'quantity': 40, 'unit': 'g', 'name': 'mynta',
        'source': 'prep', 'demand_key': 'prep', 'kind': 'preparation_input', 'method': MINT_LEAVES, 'product_key': 'a' * 32}]
    demands = [{'name': 'mynta', 'quantity': q, 'original_quantity': q, 'unit': 'g', 'source': k,
                'demand_key': k, 'preparation': MINT_LEAVES} for k, q in [('meal1', 10), ('meal2', 15)]]
    prep = {'id': 'prep', 'method': MINT_LEAVES, 'input_allocations': stock['reservations'][saved.plan_id], 'outputs': demands}
    saved = saved.model_copy(update={'plan': saved.plan.model_copy(update={
        'personal': saved.plan.personal.model_copy(update={'remaining_demands': demands, 'needs': [], 'allocations': [], 'preparations': [prep]}),
        'optimized_basket': saved.plan.optimized_basket.model_copy(update={'stores': [], 'total': 0})})})
    with plans._connect() as conn:
        stock = write_state(conn, OWNER, stock, stock['revision'])
    return private, saved, stock


def batch(leaves=25, input_g=40):
    return MintLeafTrimming(method=MINT_LEAVES, inputs={'mint-lot': input_g}, leaf_g=leaves)


def test_measured_leaf_loss_partial_consumption_release_and_idempotency(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    booked = private.inventory_action(OWNER, saved, 'prepare', stock['revision'], operation_id='mint-prepare-1', preparation=batch())
    assert sum(i['quantity'] for i in booked['items']) == 85
    assert booked['ledger'][-1]['preparation']['loss_g'] == 15
    leaf = next(i for i in booked['items'] if i.get('prepared_origin'))
    assert leaf['name'] == 'myntablad' and leaf['quantity'] == 25 and leaf['product_key'] is None
    assert private.inventory_action(OWNER, saved, 'prepare', stock['revision'], operation_id='mint-prepare-1', preparation=batch()) == booked
    with pytest.raises(PersonalConflict, match='annat innehåll'):
        private.inventory_action(OWNER, saved, 'prepare', booked['revision'], operation_id='mint-prepare-1', preparation=batch(24))
    consumed = private.inventory_action(OWNER, saved, 'consume', booked['revision'], operation_id='mint-consume-half', consume_fraction=.5)
    assert sum(i['quantity'] for i in consumed['items']) == 72.5
    released = private.inventory_action(OWNER, saved, 'release', consumed['revision'])
    assert released['items'] == consumed['items'] and saved.plan_id not in released['reservations']


def test_short_leaf_yield_is_real_but_never_counts_as_ready(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    with pytest.raises(PersonalConflict, match='bokför'):
        private.inventory_action(OWNER, saved, 'consume', stock['revision'])
    booked = private.inventory_action(OWNER, saved, 'prepare', stock['revision'], operation_id='mint-short-yield', preparation=batch(20))
    assert booked['ledger'][-1]['preparation']['loss_g'] == 20
    with pytest.raises(PersonalConflict, match='täcker inte'):
        private.inventory_action(OWNER, saved, 'consume', booked['revision'])
    assert private.read(OWNER) == booked


def test_direct_and_other_method_or_plan_reservations_are_protected(tmp_path):
    private, saved, stock = measured_plan(tmp_path)
    changed = deepcopy(stock)
    changed['reservations'][saved.plan_id].append({'item_id': 'mint-lot', 'quantity': 65, 'unit': 'g', 'name': 'mynta',
        'source': 'other', 'demand_key': 'other', 'kind': 'preparation_input', 'method': 'other'})
    with private.plans._connect() as conn:
        changed = write_state(conn, OWNER, changed, stock['revision'])
    with pytest.raises(PersonalConflict, match='disponibelt'):
        private.inventory_action(OWNER, saved, 'prepare', changed['revision'], operation_id='mint-protected', preparation=batch())
    assert private.read(OWNER) == changed


def test_leaf_stock_requires_current_exact_source_and_never_borrows_raw_mint_mass(planner):
    p, _raw = planner
    candidates = p.resolve('mynta', 10, 'g', recipe=issued(), profile=p.spec.profile)
    key = p.product_keys[0]
    raw = PantryItem(name='mynta', quantity=50, unit='g', product_key=key)
    leaf = PantryItem(name='myntablad', quantity=10, unit='g', form='raw_edible',
                     prepared_origin=PreparedOrigin(method=MINT_LEAVES, product_key=key, operation_id='mint-stock-1'))
    p.items = [i.model_dump() for i in (raw, leaf)]
    row = {'name': 'mynta', 'quantity': 10, 'unit': 'g', 'use_pantry': True, 'source': 'meal', 'demand_key': 'leaf',
           'preparation': MINT_LEAVES, 'profile': p.spec.profile, 'organic_animals': False, 'properties': [],
           'product_key': None, 'input_form': 'raw_edible', 'nutrients': []}
    left, allocation = p._allocate(row, candidates, {raw.id: 50, leaf.id: 10})
    assert left == 0 and [a['item_id'] for a in allocation] == [leaf.id]
    assert p._allocate(row, [], {raw.id: 50, leaf.id: 10}) == (10, [])
    p.items = [leaf.model_dump()]
    assert p._allocate({**row, 'preparation': None}, candidates, {leaf.id: 10})[0] == 0
    assert p._allocate({**row, 'preparation': None, 'nutrients': ['protein_g']}, candidates, {leaf.id: 10}) == (10, [])


@pytest.mark.parametrize('inputs,leaves', [({'x': 0}, 1), ({'x': float('nan')}, 1), ({'x': 10}, 11), ({'x': 10}, 0)])
def test_conservation_is_enforced_before_any_stock_write(inputs, leaves):
    with pytest.raises(ValueError):
        MintLeafTrimming(method=MINT_LEAVES, inputs=inputs, leaf_g=leaves)


def test_discriminated_api_and_reference_do_not_claim_a_pack_guarantee():
    mutation = PersonalMutation(action='prepare', revision=1, pantry_revision=0, operation_id='mint-method-1', preparation=batch())
    assert isinstance(mutation.preparation, MintLeafTrimming)
    r = mint_reference()
    assert not r['population_or_pack_guarantee'] and r['sample_species'] == 'not_reported'
    assert r['nutrition'] == 'unknown_for_picked_leaves' and r['reported_mint_bundle_g'] == 2123
    with pytest.raises(ValueError):
        PantryItem(name='mynta', quantity=10, unit='g', form='raw_edible',
                   prepared_origin=PreparedOrigin(method=MINT_LEAVES, product_key='a' * 32, operation_id='mint-forged-1'))
