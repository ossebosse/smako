"""The exact store-set search returns the enumeration's winner for any cap."""
from random import Random

import pytest
from app.models.ingredient import NormalizedIngredient
from app.services.basket_optimizer import BasketOptimizer
from app.errors import IncompleteBasketError
from app.services.basket_calculator import QuantityConfidence

from backend.tests.test_optimizer import product, store


def basket(rows, required, shops, cap, threshold, prune=True):
    optimizer = BasketOptimizer(prune_dominated_stores=prune, store_set_search_threshold=threshold)
    with optimizer.quote_cache():
        try:
            return optimizer.optimize(required, rows, [store(s) for s in shops], cap).model_dump()
        except IncompleteBasketError as exc:
            return ("incomplete", str(exc))


def instance(seed, shop_count, line_count, *, sparse=True, estimates=False):
    rng = Random(seed)
    shops = [f"s{i:02d}" for i in range(shop_count)]
    names = [f"vara{i}" for i in range(line_count)]
    rows = {}
    for name in names:
        offers = []
        for shop in shops:
            if sparse and rng.random() < 0.4:
                continue
            for size in (250, 500):
                if rng.random() < 0.6:
                    item = product(name, f"{name}-{shop}-{size}", shop, size, rng.randint(5, 40))
                    if estimates and rng.random() < 0.3:
                        item = item.model_copy(update={"quantity_confidence": QuantityConfidence.ESTIMATED})
                    offers.append(item)
        if not offers:
            offers.append(product(name, f"{name}-s00-500", shops[0], 500, 20))
        rows[name] = tuple(offers)
    required = [NormalizedIngredient(canonical_name=n, required_quantity=rng.choice([200, 400, 650]), unit="g")
                for n in names]
    return rows, required, shops


@pytest.mark.parametrize("seed", range(30))
@pytest.mark.parametrize("cap", [1, 2, 3, 5, None])
def test_search_matches_enumeration(seed, cap):
    rows, required, shops = instance(seed, 7, 5)
    assert basket(rows, required, shops, cap, 0) == basket(rows, required, shops, cap, None)


@pytest.mark.parametrize("seed", range(15))
@pytest.mark.parametrize("prune", [True, False])
def test_search_matches_enumeration_with_mixed_verification(seed, prune):
    rows, required, shops = instance(100 + seed, 8, 6, estimates=True)
    for cap in (2, 4, None):
        assert (basket(rows, required, shops, cap, 0, prune)
                == basket(rows, required, shops, cap, None, prune))


def test_all_stores_on_a_large_selection_is_fast_and_never_dearer_than_three():
    from time import perf_counter
    rows, required, shops = instance(7, 33, 25)
    started = perf_counter()
    every = basket(rows, required, shops, None, 0)
    assert perf_counter() - started < 5
    three = basket(rows, required, shops, 3, None)
    assert (every["total"], every["store_count"]) <= (three["total"], 10**6)
