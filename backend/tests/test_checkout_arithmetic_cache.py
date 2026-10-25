"""Numeric reuse never carries a quote, personal decision or approval."""
import gc
import weakref
from decimal import Decimal, localcontext
from itertools import permutations

import pytest
from app.models import NormalizedIngredient
from app.services import planner_shared_cache
from app.services.basket_optimizer import BasketOptimizer, _CompactQuoteSelection
from app.services.planner_shared_cache import CheckoutArithmeticCache

from backend.tests.test_search_reuse import _product, _store


@pytest.fixture
def cache(monkeypatch):
    value = CheckoutArithmeticCache()
    monkeypatch.setattr(planner_shared_cache, "CHECKOUT_ARITHMETIC", value)
    return value


def selection(store, cents, rank=0, quote=None):
    return _CompactQuoteSelection(quote=quote, store_id=str(store), store_mask=1 << store,
        total_price=Decimal(cents).scaleb(-2), verification_rank=rank)


def test_reordered_integer_operands_share_exact_results_without_sharing_inputs(cache):
    subsets = ((0,), (1,), (0, 1))
    vectors = ((selection(0, 100), selection(1, 200), selection(0, 100)),
               (selection(0, 300), selection(1, 100), selection(1, 100)),
               (selection(0, 100, 1), selection(1, 100), selection(1, 100)))
    expected = BasketOptimizer._grouped_subset_keys(vectors, subsets, 2, winning_mask=True, _integer_prices=False)
    for order in permutations(vectors):
        actual = BasketOptimizer._grouped_subset_keys(order, subsets, 2, winning_mask=True)
        assert actual == expected
        actual[0].clear()  # Returned lists belong only to this caller.
    assert cache.stats()["entries"] == 1
    assert cache.stats()["hits"] == 5


@pytest.mark.parametrize("changed", ["price", "rank", "winning_store", "caps", "missing"])
def test_every_numeric_read_dependency_changes_the_key_including_negatives(cache, changed):
    subsets = ((0,), (1,), (0, 1))
    vectors = [(selection(0, 100), selection(1, 100), selection(0, 100))]
    if changed == "missing":
        vectors = [tuple(_CompactQuoteSelection(quote=None) for _ in subsets)]
    first = BasketOptimizer._grouped_subset_keys(vectors, subsets, 2, winning_mask=True)
    assert BasketOptimizer._grouped_subset_keys(vectors, subsets, 2, winning_mask=True) == first
    if changed == "price":
        vectors = [(selection(0, 200), selection(1, 200), selection(0, 200))]
    elif changed == "rank":
        vectors = [(selection(0, 100, 1), selection(1, 100, 1), selection(0, 100, 1))]
    elif changed == "winning_store":
        vectors = [(selection(1, 100), selection(0, 100), selection(1, 100))]
    elif changed == "caps":
        subsets = ((0, 1), (0,), (1,))
    else:
        vectors = [(selection(0, 100), selection(1, 100), selection(0, 100))]
    expected = BasketOptimizer._grouped_subset_keys(vectors, subsets, 2, winning_mask=True, _integer_prices=False)
    assert BasketOptimizer._grouped_subset_keys(vectors, subsets, 2, winning_mask=True) == expected
    assert cache.stats()["entries"] == 2


def test_new_source_and_owner_get_current_products_even_when_arithmetic_hits(cache):
    ingredients = [NormalizedIngredient(canonical_name="x", required_quantity=3, unit="st")]
    for product_id, store_name in (("old-source", "Old"), ("new-source", "New")):
        optimizer = BasketOptimizer()
        candidate = _product("x", 5, product_id=product_id, package_quantity=2).model_copy(update={"store_name": store_name})
        with optimizer.quote_cache():
            result = optimizer.optimize(ingredients, {"x": (candidate,)}, [_store()], max_stores=1)
        assert result.total == 10
        assert result.stores[0].items[0].product_id == product_id
        assert result.stores[0].items[0].store_name == store_name
    assert cache.stats()["hits"] >= 1


def test_no_quote_or_search_object_is_retained(cache):
    class PrivateQuote:
        pass

    quote = PrivateQuote()
    reference = weakref.ref(quote)
    vectors = [(selection(0, 100, quote=quote),)]
    BasketOptimizer._grouped_subset_keys(vectors, ((0,),), 1, winning_mask=True)
    del vectors, quote
    gc.collect()
    assert reference() is None
    assert cache.stats()["entries"] == 1


def test_decimal_fallback_never_borrows_integer_arithmetic(cache):
    vectors = [(selection(0, 100),)]
    BasketOptimizer._grouped_subset_keys(vectors, ((0,),), 1)
    before = cache.stats()
    with localcontext() as context:
        context.prec = 3
        assert BasketOptimizer._grouped_subset_keys(vectors, ((0,),), 1) == ([(0, Decimal("1.00"), 1)], 0)
    assert cache.stats() == before


def test_eviction_byte_bound_and_restart_are_safe_misses():
    cache = CheckoutArithmeticCache(max_entries=2, max_bytes=2048)
    for i in range(10):
        cache.put((i,), ((i,), 0, 1))
    assert cache.stats()["entries"] == 2
    assert cache.stats()["bytes"] <= 2048
    assert cache.get((0,)) is None
    assert cache.get((9,)) == ((9,), 0, 1)
    cache.put(tuple(range(1000)), ((), 0, 0))
    assert cache.stats()["entries"] == 2
    cache.clear()
    assert cache.get((9,)) is None


@pytest.mark.parametrize("bounds", [{"max_entries": 0}, {"max_bytes": 0}])
def test_invalid_bounds_are_rejected(bounds):
    with pytest.raises(ValueError):
        CheckoutArithmeticCache(**bounds)
