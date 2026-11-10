"""Requirement-set keys shared across one request's quote sessions are exact."""
import pytest
from app.services import basket_optimizer as module
from app.services.basket_optimizer import BasketOptimizer, requirement_key_scope

from backend.tests.test_optimizer import store
from backend.tests.test_store_set_search import instance


def _requirements(required):
    return tuple((line.canonical_name, line.required_quantity, line.unit) for line in required)


@pytest.mark.parametrize("seed", range(8))
def test_second_session_reuses_keys_over_the_same_candidates(seed, monkeypatch):
    rows, required, shops = instance(900 + seed, 10 + seed % 4, 7, sparse=seed % 2 == 0)
    first = {name: tuple(values) for name, values in rows.items()}
    # A later search rebuilds its candidate tuples around the same products.
    second = {name: tuple(values) for name, values in rows.items()}
    stores = tuple(store(s) for s in shops)
    subsets = [_requirements(required[:4]), _requirements(required), _requirements(required[2:])]
    optimizer = BasketOptimizer(store_set_search_threshold=0)

    def keys(candidates, cap):
        with optimizer.quote_cache():
            return [optimizer.same_depth_nested_store_limited_requirement_keys(
                lines, candidates, stores, max_stores=cap) for lines in subsets]

    expected = {cap: keys(first, cap) for cap in (2, 3)}
    with requirement_key_scope():
        assert keys(first, 3) == expected[3]
        computed = []
        original = BasketOptimizer._same_depth_nested_store_limited_quote_keys
        monkeypatch.setattr(BasketOptimizer, "_same_depth_nested_store_limited_quote_keys",
                            lambda self, *a, **k: computed.append(1) or original(self, *a, **k))
        assert keys(second, 3) == expected[3]
        assert not computed, "same lines, products, stores and cap must reuse the key"
        assert keys(second, 2) == expected[2]
        assert computed, "another cap is a different key"
    assert module._REQUIREMENT_KEY_SCOPE.get() is None


def test_other_products_are_not_shared():
    rows, required, shops = instance(950, 11, 6)
    first = {name: tuple(values) for name, values in rows.items()}
    cheaper = {name: tuple(v.model_copy(update={"price": v.price / 2}) if v.price else v for v in values)
               for name, values in rows.items()}
    stores = tuple(store(s) for s in shops)
    lines = _requirements(required)
    optimizer = BasketOptimizer(store_set_search_threshold=0)

    def key(candidates):
        with optimizer.quote_cache():
            return optimizer.same_depth_nested_store_limited_requirement_keys(
                lines, candidates, stores, max_stores=3)

    alone = key(cheaper)
    with requirement_key_scope():
        key(first)
        assert key(cheaper) == alone


def test_outside_a_scope_nothing_is_shared():
    rows, required, shops = instance(960, 10, 6)
    optimizer = BasketOptimizer()
    with optimizer.quote_cache():
        resolved = [(line.canonical_name, line.required_quantity, line.unit, tuple(rows[line.canonical_name]))
                    for line in required]
        assert optimizer._shared_requirement_key(resolved, [store(s) for s in shops], 3) is None
