"""Prepared terms and quantity results preserve the independent resolver."""
from datetime import date
from decimal import Inexact, InvalidOperation, localcontext

import pytest
from app.models.product import OfferMetadata
from app.services import basket_calculator as module


def offers():
    return [
        OfferMetadata(kind='campaign', description='Single cap', price=9, max_quantity=2,
                      valid_to=date(2026, 10, 13), price_contract_id='single'),
        OfferMetadata(kind='multipack', description='Three for twenty', price=20,
                      required_packages=3, max_quantity=2, price_contract_id='multi'),
    ]


@pytest.mark.parametrize('count', range(1, 10))
@pytest.mark.parametrize('on_date', [date(2026, 10, 13), date(2026, 10, 14)])
def test_prepared_quantity_totals_match_uncached_resolver_for_caps_and_expiry(count, on_date):
    rows = offers()
    prepared, cacheable = module._prepare_checkout_offers(tuple(rows))
    assert cacheable
    expected = module.resolve_fixed_package_checkout(
        package_count=count, base_unit_price=9, regular_unit_price=12,
        promotions=prepared.promotions, on_date=on_date,
    )
    for _ in range(2):
        actual = module.resolve_fixed_checkout_price(
            package_count=count, base_unit_price=9, regular_unit_price=12, offers=rows, on_date=on_date,
        )
        assert actual[:2] == (expected.checkout_total, expected.displayed_unit_price)
        if expected.applied_promotion:
            assert actual[2] is next(o for o in rows if o.price_contract_id == expected.applied_promotion.reference)


def test_replacing_offer_in_mutable_list_changes_prepared_terms_and_price():
    rows = [OfferMetadata(kind='multipack', description='Pair', required_packages=2, price=10)]
    def quote():
        return module.resolve_fixed_checkout_price(package_count=2, base_unit_price=9,
            regular_unit_price=9, offers=rows, on_date=date(2026, 10, 13))
    assert quote()[0] == 10
    rows[0] = rows[0].model_copy(update={'price': 15.0})
    assert quote()[0] == 15
    rows.clear()
    assert quote()[0] == 18


@pytest.mark.parametrize('precision', [4, 28, 40])
def test_cached_results_replay_decimal_flags_and_separate_precision(precision):
    rows = (OfferMetadata(kind='multipack', description='Three', required_packages=3, price=10),)
    prepared, _ = module._prepare_checkout_offers(rows)
    with localcontext() as ctx:
        ctx.prec = precision
        ctx.clear_flags()
        expected = module.resolve_fixed_package_checkout(package_count=3, base_unit_price='5',
            regular_unit_price='5', promotions=prepared.promotions, on_date=date(2026, 10, 13))
        expected_flags = ctx.flags.copy()
        for _ in range(2):
            ctx.clear_flags()
            actual = module.resolve_fixed_checkout_price(package_count=3, base_unit_price=5,
                regular_unit_price=5, offers=rows, on_date=date(2026, 10, 13))
            assert actual[:2] == (expected.checkout_total, expected.displayed_unit_price)
            assert ctx.flags == expected_flags
        ctx.traps[Inexact] = True
        for _ in range(2):
            ctx.clear_flags()
            with pytest.raises(Inexact):
                module.resolve_fixed_checkout_price(package_count=3, base_unit_price=5,
                    regular_unit_price=5, offers=rows, on_date=date(2026, 10, 13))
            assert ctx.flags[Inexact]


def test_trapped_low_precision_failure_sets_original_flags_and_is_not_cached():
    with localcontext() as ctx:
        ctx.prec = 2
        before = module._prepared_checkout_resolution.cache_info().currsize
        for _ in range(2):
            ctx.clear_flags()
            with pytest.raises(InvalidOperation):
                module.resolve_fixed_checkout_price(package_count=3, base_unit_price=5,
                    regular_unit_price=5, on_date=date(2026, 10, 13))
            assert ctx.flags[InvalidOperation]
        assert module._prepared_checkout_resolution.cache_info().currsize == before


def test_prepared_terms_and_quantity_caches_are_bounded():
    for i in range(260):
        module._prepare_checkout_offers((OfferMetadata(kind='campaign', description=str(i), price=1),))
    assert len(module._PREPARED_OFFERS) <= 256
    assert not module._prepare_checkout_offers(tuple(offers()) * 5)[1]
    assert module._prepared_checkout_resolution.cache_info().maxsize == 2048
    assert module._prepared_checkout_resolution.cache_info().currsize <= 2048
