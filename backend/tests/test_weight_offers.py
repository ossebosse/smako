"""Retained online observations, not prices transplanted from a physical flyer."""
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest, Product, Store
from app.models.personal import ExtraNeed, PersonalMutation, PersonalPlanning
from app.models.product import ProductCandidate
from app.services.basket_calculator import comparable_weight_rate
from app.services.economic_ingredient_selector import EconomicIngredientPool
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.price_universe import PriceUniverseBuilder, PriceUniverseKey
from app.services.price_universe_runtime import PreparedPriceUniverse
from app.services.user_pricing import price_candidate_for_context
from pydantic import ValidationError

from backend.tests.test_product_search import search
from grocery_data.app.domain.promotion_pricing import UserPricingContext

NOW = datetime(2026, 10, 10, 12, tzinfo=UTC)
ROWS = json.loads((Path(__file__).parent / 'fixtures/weight-products-20261010.json').read_text(encoding='utf8'))


def retained(index=0):
    return Product.model_validate(ROWS['products'][index])


def prepare(*products):
    key = PriceUniverseKey.create(city='Lund', postal_codes=['22350'],
        snapshot_ids=[ROWS['observed_source_snapshot']], source_strategy_version='retained',
        normalizer_version='v1', taxonomy_version='v1')
    return PreparedPriceUniverse(
        universe=PriceUniverseBuilder().build(key, products, built_at=NOW),
        stores=(Store(store_id=products[0].store_id, name='Coop Online Syd', chain='coop',
            city='Lund', price_context_type='online_fulfillment', price_semantics='online_price'),),
        economic_pool=EconomicIngredientPool(), source_name='retained')


def test_retained_satsumas_member_and_public_rate_not_a_package_total():
    p = prepare(retained())
    public = search(p, 'satsumas', now=NOW)['results'][0]
    member = search(p, 'satsumas', now=NOW, memberships=['COOP_MEMBER'])['results'][0]
    assert public['display_price'] == 29.9
    assert member['display_price'] == 20
    assert public['best_price'] is member['best_price'] is None
    assert member['display_price_unit'] == 'kg'
    assert member['prices'][0]['price_basis'] == 'unit'
    assert search(p, 'satsumas', now=NOW)['results'][0] == public


def test_retained_rate_obeys_campaign_end_without_refreshing_observation():
    candidate = price_candidate_for_context(
        ProductCandidate.from_product(retained(), 1),
        UserPricingContext.from_chain_flags({'coop': True}),
        on_date=date(2026, 10, 12), planning_mode='estimated',
    )
    assert comparable_weight_rate(candidate) == (29.9, 'kg')
    assert candidate.source_provenance.source_observed_at == retained().source_provenance.source_observed_at


def test_scan_online_observation_does_not_invent_flyer_offer():
    scan = next(Product.model_validate(p) for p in ROWS['products'] if p.get('brand') == 'Scan')
    row = search(prepare(scan), 'fläskytterfilé', now=NOW, memberships=['COOP_MEMBER'])['results'][0]
    assert row['display_price'] == 105
    assert row['display_price_unit'] == 'kg'
    assert not row['has_campaign']


def plan(mode):
    req = PlanRequest(recipes=0, diversity_mode='cheapest', max_stores=2,
        purchase_planning_mode=mode, memberships=['COOP_MEMBER'],
        personal=PersonalPlanning(extras=[ExtraNeed(query='Satsumas', quantity=1000, unit='g', confirmed=True)]))
    return PersonalPlanner(req, Settings(price_provider='mock'), prepare(retained()),
        {'id': 'test-weight', 'revision': 0, 'items': [], 'reservations': {}, 'events': {}}, now=NOW).create()


def test_exact_request_gets_actionable_consent_error_no_implicit_estimate():
    with pytest.raises(PolicyConflict, match='Tillåt uppskattad vikt'):
        plan('exact')


def test_real_personal_planner_rounds_whole_weight_packages_and_audits():
    result = plan('estimated')
    assert result.optimized_basket.total == 22.4
    item = result.optimized_basket.stores[0].items[0]
    assert item.packages_needed == 8
    assert item.purchased_quantity == 1120
    assert item.waste_quantity == 120
    assert item.verification_status == 'VERIFIED_WITH_ESTIMATES'
    assert result.personal.checks['checkout_audit']['passed']


def test_mutation_default_hash_payload_unchanged_and_mode_is_explicit():
    assert 'purchase_planning_mode' not in PersonalMutation(action='recalculate', revision=1, pantry_revision=0).model_dump(mode='json')
    assert PersonalMutation(action='recalculate', revision=1, pantry_revision=0, purchase_planning_mode='estimated').purchase_planning_mode == 'estimated'
    with pytest.raises(ValidationError):
        PersonalMutation(action='consume', revision=1, pantry_revision=0, purchase_planning_mode='estimated')


def test_weight_recipe_and_own_item_share_pack_rounding():
    from app.models.personal import MealSettings, MealSlot
    from app.models.recipe import Recipe, RecipeIngredient

    from backend.tests.test_personal_planning_v2 import prepared, product, request, run

    p = product('tomat', 500, 'g', 20, sale_model='variable_weight_package', sale_unit='kg')
    recipe = Recipe(name='Tomatsallad', servings=1,
        ingredients=[RecipeIngredient(name='tomat', quantity=200, unit='g')],
        instructions=['Skär tomaterna och servera.'])
    req = request(slots=[MealSlot(id='dinner-1', day=1, meal_type='dinner', recipe=recipe)],
        meals=[MealSettings(meal_type='dinner', count=1, servings=1)],
        extras=[ExtraNeed(query='tomat', quantity=200, unit='g', confirmed=True)])
    req.purchase_planning_mode = 'estimated'
    result = run(prepared(p), req)
    assert result.optimized_basket.total == 10
    assert sum(i.purchased_quantity for s in result.optimized_basket.stores for i in s.items) == 500
    assert result.personal.checks['checkout_audit']['passed']


def test_unproven_weight_quantity_is_not_comparable():
    p = Product.model_validate({**retained().model_dump(), 'package_quantity': None,
        'package_unit': None, 'usable_quantity': None, 'usable_unit': None,
        'quantity_confidence': 'unknown', 'estimated_piece_weight': None})
    row = search(prepare(p), 'satsumas', now=NOW)['results'][0]
    assert row['display_price'] is None
    assert row['prices'][0]['price_basis'] == 'not_compared'


@pytest.mark.parametrize('chain', ['ica', 'coop', 'willys', 'hemkop', 'citygross', 'lidl'])
def test_explicit_weight_contract_rate_uses_shared_guards(chain):
    from backend.tests.test_purchase_planning_modes import DAY, rate
    p = rate(chain)
    candidate = price_candidate_for_context(ProductCandidate.from_product(p, 1),
        UserPricingContext(), on_date=DAY, planning_mode='estimated')
    assert comparable_weight_rate(candidate) == (49.9, 'kg')
    blocked = p.purchase_terms.model_copy(update={'deposit_status': 'unknown'})
    p = p.model_copy(update={'purchase_terms': blocked,
        'offers': [p.offers[0].model_copy(update={'purchase_terms': blocked})]})
    with pytest.raises(ValueError):
        price_candidate_for_context(ProductCandidate.from_product(p, 1),
            UserPricingContext(), on_date=DAY, planning_mode='estimated')

