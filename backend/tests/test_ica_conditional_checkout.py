"""Actual retained ICA campaign, with explicit diagnostic purchase quantities."""
from datetime import date
from pathlib import Path

import pytest
from app.models import Product
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.services.basket_calculator import BasketCalculator
from app.services.user_pricing import price_candidate_for_context

from grocery_data.app.domain.promotion_pricing import UserPricingContext


def real_product():
    return Product.model_validate_json((Path(__file__).parent / 'fixtures/ica-real-multibuy-20260916.json').read_bytes())


def test_actual_multibuy_without_ordinary_reaches_existing_checkout_only_for_complete_groups():
    p = real_product()
    before = p.model_dump(mode='json')
    c = price_candidate_for_context(ProductCandidate.from_product(p, 0), UserPricingContext(), on_date=date(2026, 9, 16))
    offer = next(o for o in c.offers if o.required_packages > 1)
    need = NormalizedIngredient(canonical_name=p.canonical_name,
        required_quantity=p.package_quantity * offer.required_packages, unit=p.package_unit)
    item = BasketCalculator().calculate_item(need, c)
    assert item.total_price == offer.price
    assert item.regular_total_price is None and item.regular_unit_price is None
    assert p.price is None and c.price is None and c.sale_price is None
    assert p.model_dump(mode='json') == before
    with pytest.raises(ValueError, match='complete purchase'):
        BasketCalculator().calculate_item(need.model_copy(update={'required_quantity': p.package_quantity}), c)
    limited = c.model_copy(update={'offers': [o.model_copy(update={'max_quantity': 1}) for o in c.offers]})
    with pytest.raises(ValueError, match='complete purchase'):
        BasketCalculator().calculate_item(need.model_copy(update={'required_quantity': need.required_quantity * 2}), limited)


def test_expired_or_member_only_contracts_cannot_become_public_ranking_prices():
    p = real_product()
    with pytest.raises(ValueError):
        price_candidate_for_context(ProductCandidate.from_product(p, 0), UserPricingContext(), on_date=date(2027, 1, 1))
    p = p.model_copy(update={'offers': [o.model_copy(update={'eligibility': 'member',
        'membership_program': 'ICA_STAMMIS', 'member_program': 'ica medlem'}) for o in p.offers]})
    with pytest.raises(ValueError):
        price_candidate_for_context(ProductCandidate.from_product(p, 0), UserPricingContext(), on_date=date(2026, 9, 16))


def test_checkout_also_enforces_observed_applicability_without_a_fabricated_start():
    from datetime import UTC, datetime
    from app.models import OfferMetadata
    from app.services.basket_calculator import resolve_fixed_checkout_price
    from grocery_data.app.domain.campaign_validity import CampaignEvidence
    proof=CampaignEvidence(store_external_id='official',offer_id='offer',source_reference='raw:retained',
        observed_current_at=datetime(2026,9,20,8,tzinfo=UTC),checked_at=datetime(2026,9,20,8,tzinfo=UTC))
    offer=OfferMetadata(kind='multipack',description='2 for 30',price=30,required_packages=2,
        valid_to=date(2026,9,20),campaign_evidence=proof)
    kwargs=dict(package_count=2,base_unit_price=15,regular_unit_price=None,offers=[offer])
    assert resolve_fixed_checkout_price(**kwargs,on_date=date(2026,9,20))[0]==30
    for day in [date(2026,9,19),date(2026,9,21)]:
        with pytest.raises(ValueError,match='complete purchase'):
            resolve_fixed_checkout_price(**kwargs,on_date=day)
