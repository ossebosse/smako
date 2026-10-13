"""Compare the optimized exact aggregate with exhaustive independent subsets."""
from decimal import Decimal
from itertools import combinations
from random import Random

import pytest
from app.services.basket_optimizer import (
    BasketOptimizer,
    _CompactQuoteSelection,
    _QuoteCacheSession,
)


@pytest.mark.parametrize("count_ceiling,repeats", [(9, 160), (24, 24)])
def test_partition_keys_match_scalar_for_all_caps_including_ties_and_missing_stores(count_ceiling, repeats):
    random = Random(1729)
    for _ in range(repeats):
        count, limit = random.randrange(2, count_ceiling), random.randrange(2, 5)
        limit = min(count, limit)
        subsets = tuple(c for size in range(1, limit + 1) for c in combinations(range(count), size))
        vectors = []
        for _ingredient in range(random.randrange(0, 12)):
            stores = {s: (random.randrange(0, 3), Decimal(random.randrange(0, 20)) / 100)
                      for s in range(count) if random.random() > .3}
            vector = []
            for combo in subsets:
                present = [s for s in combo if s in stores]
                if not present:
                    vector.append(_CompactQuoteSelection(quote=None))
                else:
                    winner = min(present, key=lambda s: (*stores[s], s))
                    rank, price = stores[winner]
                    vector.append(_CompactQuoteSelection(quote=None, verification_rank=rank,
                                  total_price=price, store_id=str(winner), store_mask=1 << winner))
            vectors.append(tuple(vector))
        expected, infeasible = [None] * limit, 0
        scalar_keys = []
        for index, combo in enumerate(subsets):
            chosen = [vector[index] for vector in vectors]
            if any(s.store_id is None for s in chosen):
                infeasible += 1
                scalar_keys.append(None)
                continue
            key = (max((s.verification_rank for s in chosen), default=0),
                   sum((s.total_price for s in chosen), Decimal(0)),
                   len({s.store_id for s in chosen}))
            scalar_keys.append(key)
            for cap in range(len(combo) - 1, limit):
                expected[cap] = min(expected[cap], key) if expected[cap] else key
        session = _QuoteCacheSession()
        for _repeat in range(2):
            actual = BasketOptimizer._grouped_subset_keys(vectors, subsets, limit, session)
            assert actual == (expected, infeasible)
            winners = sum(1 << i for i, key in enumerate(scalar_keys)
                          if key is not None and key == expected[-1])
            assert BasketOptimizer._grouped_subset_keys(vectors, subsets, limit, session, winning_mask=True) == (expected, infeasible, winners)


def test_partition_cache_keeps_source_references_and_different_operands_separate():
    session = _QuoteCacheSession()
    subsets = ((0,), (1,), (0, 1))
    for price in (Decimal('.01'), Decimal('100.00')):
        vector = tuple(_CompactQuoteSelection(quote=None, store_id='0', store_mask=1,
                       total_price=price) for _ in subsets)
        actual, missing = BasketOptimizer._grouped_subset_keys((vector,), subsets, 2, session)
        assert actual == [(0, price, 1), (0, price, 1)] and missing == 0


def test_singleton_finishes_remaining_prices_and_rejects_later_missing_quote():
    def selected(store, price, rank=0):
        return _CompactQuoteSelection(quote=None, store_id=str(store),
                                      store_mask=1 << store, total_price=Decimal(price),
                                      verification_rank=rank)
    absent = _CompactQuoteSelection(quote=None)
    subsets = ((0,), (1,), (0, 1))
    vectors = (
        (selected(0, '1'), selected(1, '1', 1), selected(0, '3')),
        (absent, selected(1, '2'), selected(0, '2')),
        (selected(0, '4'), selected(1, '4', 2), absent),
    )
    expected = (2, Decimal(7), 1)
    assert BasketOptimizer._grouped_subset_keys(
        vectors, subsets, 2, winning_mask=True,
    ) == ([expected, expected], 2, 0b010)
