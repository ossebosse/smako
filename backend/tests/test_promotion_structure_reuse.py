"""Structural reuse never caches mutable caps or bypasses source validation."""
from types import SimpleNamespace

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import OfferMetadata, ProductCandidate
from app.services import basket_optimizer as module
from app.services.basket_calculator import GroupPricingError

from backend.tests.test_personal_planning_v2 import product
from backend.tests.test_promotion_groups import catalog, group


def candidate(**changes):
    return ProductCandidate.from_product(product('ris', 1000, 'g', 30), match_score=1).model_copy(update=changes)


def test_current_mutable_offer_caps_are_checked_after_structural_cache_hit():
    c = candidate(price=None, offers=[])
    rows = {'ris': (c,), 'alias': (c,)}
    session = module._QuoteCacheSession()
    for offers, expected in (([], False), ([OfferMetadata(kind='campaign', description='Synthetic cap', price=20, max_quantity=1)], True), ([], False)):
        c.offers[:] = offers
        assert module._has_coupled_checkout(rows, session=session) is expected
        assert module._has_coupled_checkout(rows) is expected
        assert not module._has_coupled_checkout(rows, ['ris'], session=session)
    assert session.promotion_structure_rows


def test_lists_and_non_frozen_candidate_types_never_reuse_structure():
    session = module._QuoteCacheSession()
    rows = [candidate()]
    assert not module._has_coupled_checkout({'ris': rows}, session=session)
    rows[0] = candidate(promotion_groups=(group(),))
    assert module._has_coupled_checkout({'ris': rows}, session=session)
    dynamic = SimpleNamespace(price=30, promotion_groups=())
    assert module._promotion_structure((dynamic,), session) == ((), ())
    dynamic.promotion_groups = (group(),)
    assert module._promotion_structure((dynamic,), session)[0] == (dynamic,)
    assert not session.promotion_structure_rows


def test_unvalidated_mutable_group_list_is_never_cached():
    session = module._QuoteCacheSession()
    c = candidate(promotion_groups=[])
    rows = {'ris': (c,)}
    assert not module._has_coupled_checkout(rows, session=session)
    c.promotion_groups.append(group())
    assert module._has_coupled_checkout(rows, session=session)
    assert not session.promotion_structure_rows


@pytest.mark.parametrize('change', [
    {'source_snapshot_id': 'different-snapshot'},
    {'store_id': 'another-store'},
    {'source': 'different-provider'},
    {'eligible_product_ids': ('unrelated-product',)},
    {'amount': 80},
])
def test_changed_source_contract_still_fails_after_valid_cached_structure(change):
    p = catalog(group())
    rows = {v.name: (ProductCandidate.from_product(v, match_score=1),) for v in p.universe.products}
    needs = [NormalizedIngredient(canonical_name=v.name, required_quantity=1000, unit=v.package_unit)
             for v in p.universe.products]
    optimizer = module.BasketOptimizer()
    with optimizer.quote_cache():
        expected = optimizer.optimize(needs, rows, p.stores, 2)
        assert optimizer.optimize(needs, rows, p.stores, 2) == expected
        first = next(iter(rows))
        rows[first] = (rows[first][0].model_copy(update={'promotion_groups': (group(**change),)}),)
        with pytest.raises(GroupPricingError):
            optimizer.optimize(needs, rows, p.stores, 2)


def test_structure_cache_has_entry_and_candidate_limits_and_releases_on_exit(monkeypatch):
    monkeypatch.setattr(module, '_MAX_PROMOTION_STRUCTURE_ROWS', 2)
    monkeypatch.setattr(module, '_MAX_PROMOTION_STRUCTURE_CANDIDATES', 3)
    optimizer = module.BasketOptimizer()
    with optimizer.quote_cache():
        session = optimizer._quote_cache_context.get()
        for n in range(10):
            rows = (candidate(product_id=str(n)),) * (1 + n % 3)
            assert module._promotion_structure(rows, session) == ((), ())
            assert len(session.promotion_structure_rows) <= 2
            assert session.promotion_structure_candidates <= 3
        oversized = (candidate(price=None),) * 4
        assert module._promotion_structure(oversized, session) == ((), oversized)
        assert id(oversized) not in session.promotion_structure_rows
        # The existing global reuse eviction also releases this auxiliary map.
        session.quotes.update(dict.fromkeys(range(32769)))
        with optimizer.quote_cache(reuse_existing=True):
            assert not session.promotion_structure_rows
            assert session.promotion_structure_candidates == 0
        module._promotion_structure((candidate(),), session)
    assert not session.promotion_structure_rows
    assert session.promotion_structure_candidates == 0
    assert optimizer._quote_cache_context.get() is None
