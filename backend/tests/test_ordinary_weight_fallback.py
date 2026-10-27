"""An unbound promotion cap must not hide a separately observed kg price."""
from datetime import date

import pytest
from app.models.basket import BasketItem
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate, QuantityConfidence
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator, comparable_weight_rate
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import DepositContract, UserPricingContext


def candidate():
    return ProductCandidate(
        product_id='variable-beef', product_name='Whole beef cut', canonical_name='nötkött',
        store_id='store', store_name='Store', chain='willys', match_score=1,
        price=369, effective_price=369, sale_price=369, sale_unit='kg',
        comparison_price=369, comparison_unit='kg', sale_model='variable_weight_package',
        package_quantity=1800, package_unit='g', usable_quantity=1800, usable_unit='g',
        quantity_confidence='estimated', semantic_confidence='high',
        offers=[{'kind': 'member', 'description': 'Member kg rate, cap unit unknown',
                 'price': 269, 'price_basis_unit': 'kg', 'max_quantity': 3,
                 'member_program': 'WILLYS_PLUS', 'valid_to': '2026-10-25'}],
    )


def priced(p, *, member=False, day=date(2026, 10, 23), mode='estimated'):
    return price_candidate_for_context(p, UserPricingContext.from_chain_flags({'willys': member}),
                                       on_date=day, planning_mode=mode)


@pytest.mark.parametrize('member', [False, True])
@pytest.mark.parametrize('day', [date(2026, 10, 23), date(2026, 10, 27)])
@pytest.mark.parametrize(('grams', 'packs', 'total'), [(600, 1, 664.2), (2000, 2, 1328.4), (6000, 4, 2656.8)])
def test_ordinary_rate_rounds_whole_packs_without_applying_unknown_cap(member, day, grams, packs, total):
    source = candidate()
    before = source.model_dump_json()
    selected = priced(source, member=member, day=day)
    assert selected.offers == source.offers  # Retained evidence, never a newly qualified promotion.
    assert selected.purchase_terms is None and selected.member_price is None
    assert selected.selected_price_mechanism == 'regular'
    assert selected.selected_price_eligibility == 'public'
    assert comparable_weight_rate(selected) == (369, 'kg')
    need = NormalizedIngredient(canonical_name='nötkött', required_quantity=grams, unit='g')
    item = BasketCalculator().calculate_item(need, selected)
    assert item.packages_needed == packs and item.total_price == total
    assert item.purchased_quantity == 1800 * packs
    assert item.waste_quantity == 1800 * packs - grams
    assert item.applied_offer is None and item.offer_description is None
    assert item.regular_total_price == total and item.price_mechanism == 'regular'
    assert item.verification_status == 'VERIFIED_WITH_ESTIMATES'
    restored = BasketItem.model_validate_json(item.model_dump_json())
    assert BasketAuditor(pantry_items=frozenset()).audit([need], [restored]).passed
    assert source.model_dump_json() == before


def test_exact_mode_still_requires_explicit_estimate_consent():
    with pytest.raises(ValueError, match='estimated planning mode'):
        priced(candidate(), mode='exact')


@pytest.mark.parametrize('updates', [
    {'sale_unit': 'package'}, {'sale_price': 269}, {'price': None},
    {'price': 269, 'sale_price': 269}, {'sale_model': 'fixed_package'},
])
def test_no_comparison_price_or_package_total_can_supply_ordinary_kg_rate(updates):
    with pytest.raises(ValueError, match='independent ordinary kg rate'):
        priced(candidate().model_copy(update=updates))


@pytest.mark.parametrize('updates', [
    {'max_quantity': None}, {'required_packages': 2, 'mechanism': 'multibuy'},
    {'deposit': DepositContract(gtin='7350086160659', per_container=2,
                               containers_per_package=1, inclusion='additional', evidence='fixture')},
])
def test_other_unresolved_offer_shapes_remain_blocked(updates):
    p = candidate()
    with pytest.raises(ValueError):
        priced(p.model_copy(update={'offers': [p.offers[0].model_copy(update=updates)]}))


def test_legacy_effective_and_member_signals_cannot_reintroduce_discount():
    selected = priced(candidate().model_copy(update={'effective_price': 269, 'member_price': 269}), member=True)
    assert selected.effective_price == selected.sale_price == 369


def test_unknown_quantity_is_not_upgraded_by_ordinary_price_fallback():
    with pytest.raises(ValueError, match='known source quantity evidence'):
        priced(candidate().model_copy(update={'quantity_confidence': 'unknown'}))


def test_mixed_price_units_cannot_be_flattened_into_an_ordinary_rate():
    p = candidate()
    with pytest.raises(ValueError, match='independent ordinary kg rate'):
        priced(p.model_copy(update={'offers': [*p.offers, p.offers[0].model_copy(update={
            'price_basis_unit': 'package', 'price': 400,
        })]}))


def test_public_unknown_cap_and_loose_weight_keep_only_independent_ordinary_rate():
    p = candidate()
    p = p.model_copy(update={'sale_model': 'sold_by_weight', 'offers': [p.offers[0].model_copy(update={
        'kind': 'campaign', 'eligibility': 'public', 'membership_program': None, 'member_program': None,
    })]})
    need = NormalizedIngredient(canonical_name='nötkött', required_quantity=2000, unit='g')
    item = BasketCalculator().calculate_item(need, priced(p))
    assert item.total_price == 738 and item.purchased_quantity == 2000
    assert item.applied_offer is None


def test_verified_counted_cap_still_uses_existing_discount_checkout():
    p = candidate()
    p = p.model_copy(update={'offers': [p.offers[0].model_copy(update={
        'limit_unit': 'purchase_packages', 'price_contract_id': 'verified-count-cap',
    })]})
    selected = priced(p, member=True)
    need = NormalizedIngredient(canonical_name='nötkött', required_quantity=6000, unit='g')
    item = BasketCalculator().calculate_item(need, selected)
    assert item.total_price == 3 * 484.2 + 664.2
    assert item.applied_offer.limit_unit == 'purchase_packages'


def test_existing_source_purchase_limit_is_still_enforced():
    from backend.tests.test_personal_planning_v2 import product

    source = product('beef', 1800, 'g', 369, store='store').source_provenance
    p = candidate().model_copy(update={
        'source_provenance': source.model_copy(update={'maximum_purchase_units': 3}),
    })
    need = NormalizedIngredient(canonical_name='nötkött', required_quantity=6000, unit='g')
    with pytest.raises(ValueError, match='source purchase-unit limit exceeded'):
        BasketCalculator().calculate_item(need, priced(p))


def test_ordinary_fallback_still_requires_measured_purchase_in_private_pantry(tmp_path):
    from app.models.personal import ExtraNeed
    from app.services.personal_store import PersonalConflict, PersonalStore
    from app.services.plan_store import PlanStore

    from backend.tests.test_personal_planning_v2 import key_for, prepared, product, request, run

    p = product('Whole beef cut', 1800, 'g', 369, store='willys',
                sale_model='variable_weight_package', sale_unit='kg').model_copy(update={
        'quantity_confidence': QuantityConfidence.ESTIMATED, 'offers': candidate().offers,
    })
    universe = prepared(p)
    req = request(extras=[ExtraNeed(kind='exact', query=p.name, quantity=800, unit='g',
        product_key=key_for(universe, p.name), confirmed=True)]).model_copy(update={
            'purchase_planning_mode': 'estimated',
        })
    result = run(universe, req)
    assert result.optimized_basket.total == 664.2
    store = PlanStore(tmp_path / 'plans.sqlite')
    owner = 'a' * 64
    saved = store.create(req, result, owner_actor_hash=owner)
    pantry = PersonalStore(store)
    revision = pantry.read(owner)['revision']
    with pytest.raises(PersonalConflict, match='verklig'):
        pantry.inventory_action(owner, saved, 'purchase', revision)
    item = result.optimized_basket.stores[0].items[0]
    assert item.purchase_terms is None
    key = item.store_id + '|' + item.product_id + '|' + item.ingredient
    state = pantry.inventory_action(owner, saved, 'purchase', revision,
                                    measured_purchase_quantities={key: 1710})
    assert state['items'][0]['quantity'] == 1710
    assert state['ledger'][0]['rows'][0]['checkout']['quantity_confidence'] == 'estimated'
    assert store.get(saved.plan_id).request.purchase_planning_mode == 'estimated'
