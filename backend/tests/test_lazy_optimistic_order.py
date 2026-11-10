"""Lazily priced optimistic keys visit menu states in the exact sorted order."""
from random import Random

import pytest
from app.services.basket_optimizer import BasketOptimizer
from app.services.menu_optimizer import MenuOptimizer

from backend.tests.test_optimizer import store
from backend.tests.test_search_reuse import _product, _recipe, _store
from backend.tests.test_store_set_search import instance


@pytest.mark.parametrize("seed", range(16))
def test_relaxed_key_never_exceeds_a_nested_key(seed):
    rows, required, shops = instance(1200 + seed, 8 + seed % 6, 7, sparse=seed % 2 == 0,
                                     estimates=seed % 3 == 0)
    candidates = {name: tuple(values) for name, values in rows.items()}
    stores = tuple(store(s) for s in shops)
    optimizer = BasketOptimizer()
    with optimizer.quote_cache():
        for lines in (required, required[:3], required[2:6]):
            requirements = tuple((line.canonical_name, line.required_quantity, line.unit) for line in lines)
            relaxed = optimizer.relaxed_requirement_key(requirements, candidates, stores)
            keys = optimizer.same_depth_nested_store_limited_requirement_keys(
                requirements, candidates, stores, max_stores=3)
            for key in keys:
                if key is not None:
                    assert relaxed is not None
                    assert relaxed <= key[:2]


def _menu_instance(seed):
    rng = Random(seed)
    names = [f"vara{i}" for i in range(9)]
    shops = [f"s{i}" for i in range(5)]
    products = {
        name: [
            _product(name, rng.randint(8, 40), store_id=shop, package_quantity=rng.choice([1, 2, 4]),
                     product_id=f"{shop}-{name}")
            for shop in shops if rng.random() < 0.75
        ] or [_product(name, 20, store_id=shops[0], product_id=f"{shops[0]}-{name}")]
        for name in names
    }
    recipes = [
        _recipe(f"Rätt {index}", [(name, rng.choice([1, 2, 3])) for name in rng.sample(names, 3)])
        for index in range(12)
    ]
    return recipes, products, [_store(shop) for shop in shops]


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("max_stores", [1, 2, 3])
def test_lazy_keys_choose_the_same_menu_as_sorted_keys(seed, max_stores, monkeypatch):
    recipes, products, stores = _menu_instance(seed)

    def search():
        result = MenuOptimizer().optimize(
            recipes, products, stores, recipe_count=3, max_stores=max_stores, beam_width=3,
            search_reuse_enabled=True, admissible_lower_bound_enabled=True)
        return ([recipe.name for recipe in result.recipes], result.basket.total,
                sorted(group.store_id for group in result.basket.stores))

    lazy = search()
    drain, greedy = MenuOptimizer._drain_pending_frontier, MenuOptimizer._greedy_best_expansion
    monkeypatch.setattr(MenuOptimizer, "_drain_pending_frontier",
                        lambda self, *args, **kwargs: drain(self, *args, **{**kwargs, "lazy": False}))
    monkeypatch.setattr(MenuOptimizer, "_greedy_best_expansion",
                        lambda self, *args, **kwargs: greedy(self, *args, **{**kwargs, "lazy": False}))
    assert search() == lazy


def test_a_key_below_its_floor_falls_back_to_sorted_keys(monkeypatch):
    recipes, products, stores = _menu_instance(5)

    def search():
        result = MenuOptimizer().optimize(
            recipes, products, stores, recipe_count=3, max_stores=2, beam_width=3,
            search_reuse_enabled=True, admissible_lower_bound_enabled=True)
        return [recipe.name for recipe in result.recipes], result.basket.total

    expected = search()
    from decimal import Decimal

    from app.services import menu_optimizer
    monkeypatch.setattr(menu_optimizer._EvaluationCache, "ordering_floor",
                        lambda self, profiles: (0, Decimal(1000000)))
    assert search() == expected
