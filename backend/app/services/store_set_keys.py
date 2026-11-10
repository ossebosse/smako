"""Exact nested store-cap keys in whole öre, vectorized with numpy.

Same objective as ``BasketOptimizer._grouped_subset_keys`` over every store
subset of at most two stores: each line takes the store whose quote comes
first in that line's authoritative quote order; a subset is feasible when
every line has a quote; its key is (max verification rank, total öre, stores
that win a line). Integer arithmetic only, so sums are exact; callers use it
only where every price is a whole number of öre (exponent -2), the same
condition under which the scalar code sums integers.
"""
from __future__ import annotations

import numpy as np

MISSING = np.iinfo(np.int64).max
_PAIRS: dict[int, tuple[np.ndarray, np.ndarray]] = {}
# rank << 46 | öre << 2 | stores: rank <= 3, öre < 2**44, stores <= 2.
_RANK_SHIFT = 46
_TOTAL_LIMIT = 1 << 44


def _pairs(n: int) -> tuple[np.ndarray, np.ndarray]:
    cached = _PAIRS.get(n)
    if cached is None:
        cached = _PAIRS[n] = np.triu_indices(n, 1)
    return cached


def nested_keys_up_to_two(order: np.ndarray, rank: np.ndarray, cents: np.ndarray, limit: int):
    """Keys for caps 1..limit (limit 1 or 2) and the infeasible subset count.

    ``order``/``rank``/``cents`` have shape (lines, stores); ``order`` is the
    store's position in the line's quote order or MISSING. Returns None when
    a total could exceed the packed range (the caller then uses the scalar
    path), else ``([(rank, öre, stores) | None, ...], infeasible)`` where
    subsets are counted as in ``_eligible_store_subsets``.
    """
    lines, stores = order.shape
    present = order != MISSING
    if lines == 0 or int(cents.max(initial=0)) * lines >= _TOTAL_LIMIT or int(rank.max(initial=0)) > 3:
        return None
    feasible1 = present.all(axis=0)
    rank1 = rank.max(axis=0)
    total1 = cents.sum(axis=0)
    packed1 = (rank1 << _RANK_SHIFT) | (total1 << 2) | 1
    best = [int(packed1[feasible1].min()) if feasible1.any() else None]
    infeasible = int(stores - np.count_nonzero(feasible1))
    if limit >= 2 and stores >= 2:
        first, second = _pairs(stores)
        order_a, order_b = order[:, first], order[:, second]
        wins_a = order_a < order_b
        feasible2 = np.minimum(order_a, order_b) != MISSING
        feasible2 = feasible2.all(axis=0)
        rank2 = np.where(wins_a, rank[:, first], rank[:, second]).max(axis=0)
        total2 = np.where(wins_a, cents[:, first], cents[:, second]).sum(axis=0)
        used2 = wins_a.any(axis=0).astype(np.int64) + (~wins_a).any(axis=0)
        packed2 = (rank2 << _RANK_SHIFT) | (total2 << 2) | used2
        infeasible += int(feasible2.size - np.count_nonzero(feasible2))
        pair_best = int(packed2[feasible2].min()) if feasible2.any() else None
        candidates = [key for key in (best[0], pair_best) if key is not None]
        best.append(min(candidates) if candidates else None)
    elif limit >= 2:
        best.append(best[0])
    return [None if key is None else (key >> _RANK_SHIFT, (key >> 2) & (_TOTAL_LIMIT - 1), key & 3)
            for key in best], infeasible


def cap_three_total(order: np.ndarray, cents: np.ndarray, smaller_total: int):
    """Best (öre, stores) over three-store sets cheaper than ``smaller_total``.

    For one verification rank only: a line's winner is the store first in its
    quote order, which within one rank is ordered by price, so a set costs
    the sum of its winners' öre. ``smaller_total`` is the exact best total of
    at most two stores. A three-store set can beat that key only with a
    strictly lower total (an equal total uses at least as many stores, or is
    itself a smaller set).

    Each set {a < b < c} is reached from its first store a. A lower bound for
    every set from a: lines a sells cost a's price minus at most the two
    largest single-store savings over stores after a; lines a lacks cost at
    least their cheapest price after a. First stores whose bound reaches
    ``smaller_total`` are skipped; the others try all pairs b < c after a.
    Returns (öre, stores) of the best such set, or None if none is cheaper.
    """
    lines, stores = order.shape
    if stores < 3:
        return None
    present = order != MISSING
    price = np.where(present, cents, _TOTAL_LIMIT)
    # saving[a, s] = sum over lines a sells of max(0, price_a - price_s).
    diff = price[:, :, None] - price[:, None, :]
    diff = np.where(present[:, :, None] & (diff > 0), diff, 0)
    saving = diff.sum(axis=0)
    later = np.triu(np.ones((stores, stores), dtype=bool), 1)
    saving = np.where(later, saving, 0)
    top_two = -np.partition(-saving, 1, axis=1)[:, :2].sum(axis=1) if stores > 2 else saving.max(axis=1)
    covered = np.where(present, price, 0).sum(axis=0)
    # Cheapest price over stores after a, per line.
    suffix_low = np.minimum.accumulate(price[:, ::-1], axis=1)[:, ::-1]
    after = np.concatenate([suffix_low[:, 1:], np.full((lines, 1), _TOTAL_LIMIT, dtype=np.int64)], axis=1)
    uncovered = np.where(present, 0, after).sum(axis=0)
    bound = covered - top_two + uncovered
    best = None
    for a in np.nonzero(bound < smaller_total)[0]:
        a = int(a)
        if a > stores - 3:
            continue
        rest = np.arange(a + 1, stores)
        first, second = _pairs(rest.size)
        b, c = rest[first], rest[second]
        order_a = order[:, a:a + 1]
        order_b, order_c = order[:, b], order[:, c]
        winner = np.where(order_a < order_b, 0, 1)
        winner_order = np.minimum(order_a, order_b)
        winner = np.where(order_c < winner_order, 2, winner)
        winner_order = np.minimum(winner_order, order_c)
        feasible = (winner_order != MISSING).all(axis=0)
        total = np.where(winner == 0, price[:, a:a + 1], np.where(winner == 1, price[:, b], price[:, c])).sum(axis=0)
        used = (winner == 0).any(axis=0).astype(np.int64) + (winner == 1).any(axis=0) + (winner == 2).any(axis=0)
        packed = (total << 2) | used
        packed = packed[feasible & (total < smaller_total)]
        if packed.size:
            value = int(packed.min())
            if best is None or value < best:
                best = value
                smaller_total = min(smaller_total, value >> 2) + 1 if False else smaller_total
    if best is None:
        return None
    return best >> 2, best & 3
