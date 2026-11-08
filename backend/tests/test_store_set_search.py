"""The exact store-set search returns the enumeration's winner for any cap."""
from random import Random
from types import SimpleNamespace
from decimal import Decimal

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


@pytest.mark.parametrize("seed", range(12))
def test_nested_cap_keys_match_enumeration_for_frontier_caps(seed):
    rows, required, shops = instance(200 + seed, 8, 5, estimates=seed % 2 == 1)

    def keys(threshold):
        optimizer = BasketOptimizer(store_set_search_threshold=threshold)
        with optimizer.quote_cache():
            return optimizer.same_depth_nested_store_limited_keys(
                required, rows, [store(s) for s in shops], max_stores=6)

    fast, exact = keys(0), keys(None)
    assert len(fast) == len(exact) == 6
    # Caps 1-3 and the requested cap are exact; caps in between are never
    # used as frontiers and repeat the requested cap's key, a lower bound.
    assert fast[:3] == exact[:3] and fast[5] == exact[5]
    assert all(f is None or e is None or f <= e for f, e in zip(fast, exact, strict=True))


@pytest.mark.parametrize("seed", range(24))
@pytest.mark.parametrize("cap", [3, 4])
def test_cap_three_keys_from_search_match_enumeration(seed, cap):
    # Many stores at cap three use the store-set search seeded with the exact
    # best two-store key; every frontier key must equal plain enumeration.
    rows, required, shops = instance(400 + seed, 9 + seed % 5, 6 + seed % 3,
                                     sparse=seed % 3 != 0, estimates=seed % 2 == 1)

    def keys(threshold):
        optimizer = BasketOptimizer(store_set_search_threshold=threshold)
        with optimizer.quote_cache():
            return optimizer.same_depth_nested_store_limited_keys(
                required, rows, [store(s) for s in shops], max_stores=cap)

    fast, exact = keys(0), keys(None)
    assert len(fast) == len(exact) == cap
    assert fast[:3] == exact[:3] and fast[-1] == exact[-1]


def test_cap_three_uses_the_search_only_for_many_stores():
    optimizer = BasketOptimizer()
    assert not optimizer._use_store_set_search(22, 3)
    assert optimizer._use_store_set_search(23, 3)
    assert not optimizer._use_store_set_search(60, 2)


def test_menu_frontiers_for_large_caps_are_one_two_three_and_the_cap():
    from app.services.menu_optimizer import MenuOptimizer
    shops = [store(f"s{i:02d}") for i in range(20)]
    assert MenuOptimizer._nested_store_limits(3, shops) == (1, 2, 3)
    assert MenuOptimizer._nested_store_limits(2, shops) == (1, 2)
    assert MenuOptimizer._nested_store_limits(20, shops) == (1, 2, 3, 20)
    assert MenuOptimizer._nested_store_limits(4, shops) == (1, 2, 3, 4)


def test_all_selected_cap_must_match_the_chosen_stores():
    from app.models.plan import PlanRequest
    from pydantic import ValidationError
    ids = tuple(f"s{i}" for i in range(12))
    request = PlanRequest(allowed_store_ids=ids, max_stores=12, store_cap="all_selected")
    assert request.model_dump()["store_cap"] == "all_selected"
    assert "store_cap" not in PlanRequest(max_stores=3).model_dump()
    for bad in ({"allowed_store_ids": ids, "max_stores": 5, "store_cap": "all_selected"},
                {"max_stores": 3, "store_cap": "all_selected"},
                {"allowed_store_ids": ids, "max_stores": 12}):
        with pytest.raises(ValidationError):
            PlanRequest(**bad)


def test_cover_check_is_exact_without_listing_subsets():
    from types import SimpleNamespace
    from app.services.personal_planner import _covered_within
    def offer(*shops):
        return [SimpleNamespace(store_id=s) for s in shops]
    lines = [offer("a", "b"), offer("c"), offer("d", "a"), offer("e")]
    assert not _covered_within(lines, 2)
    assert _covered_within(lines, 3)  # a, c, e
    assert not _covered_within([offer("a"), []], 5)
    many = [offer(f"s{i}", f"s{i+1}") for i in range(0, 60, 2)]
    assert _covered_within(many, 30) and not _covered_within(many, 29)


def _plain(item):
    return item.model_copy(update={"sale_model": "fixed_package", "quantity_confidence": "exact"})


@pytest.mark.parametrize("seed", range(20))
def test_store_winner_quotes_match_full_quote_sets_over_a_search(seed):
    """Only each store's winner is quoted in full; every basket is unchanged."""
    rng = Random(900 + seed)
    rows, _required, shops = instance(900 + seed, 9, 6, estimates=seed % 3 == 0)
    rows = {name: tuple(_plain(item) if rng.random() < 0.8 else item for item in items)
            for name, items in rows.items()}
    # Several products per store, including ties on price.
    rows = {name: (*items, *(item.model_copy(update={"product_id": item.product_id + "-twin",
                                                     "product_name": item.product_name + " twin"})
                             for item in items[:2]))
            for name, items in rows.items()}
    names = sorted(rows)
    requests = [[NormalizedIngredient(canonical_name=n, required_quantity=rng.choice([120, 200, 250, 400, 499, 500, 650, 1000, 1001]), unit="g")
                 for n in rng.sample(names, rng.randint(2, len(names)))] for _ in range(25)]
    caps = [rng.choice([1, 2, 3, None]) for _ in requests]

    def run(full):
        optimizer = BasketOptimizer()
        if full:
            optimizer._store_best_quotes_with_key = optimizer._candidate_quotes_with_key
        results = []
        with optimizer.quote_cache() as stats:
            for required, cap in zip(requests, caps):
                try:
                    results.append(optimizer.optimize(required, rows, [store(s) for s in shops], cap).model_dump())
                except IncompleteBasketError as exc:
                    results.append(("incomplete", str(exc)))
        return results, stats

    pruned, stats = run(False)
    full, _ = run(True)
    assert pruned == full
    assert stats.fixed_template_hits > 0


@pytest.mark.parametrize("seed", range(30))
def test_lower_bound_never_exceeds_the_optimized_total(seed):
    rng = Random(1300 + seed)
    rows, required, shops = instance(1300 + seed, rng.randint(3, 9), rng.randint(2, 7), estimates=seed % 2 == 0)
    rows = {name: tuple(_plain(item) if rng.random() < 0.7 else item for item in items)
            for name, items in rows.items()}
    optimizer = BasketOptimizer()
    with optimizer.quote_cache():
        bound = optimizer.lower_bound(required, rows)
        for cap in (1, 2, 3, None):
            try:
                total = Decimal(str(optimizer.optimize(required, rows, [store(s) for s in shops], cap).total))
            except IncompleteBasketError:
                continue
            assert bound is not None and bound <= total
    assert BasketOptimizer().lower_bound(required, rows) is None  # no quote session, no bound


def test_complete_menu_search_with_bound_pruning_returns_the_same_menu():
    from app.services.menu_optimizer import MenuBoundPruned, MenuOptimizer

    rng = Random(77)
    saved = 0
    for trial in range(40):
        groups = [[SimpleNamespace(id=f"d{day}", recipe=SimpleNamespace(name=f"r{day}-{k}"))
                   for k in range(rng.randint(3, 9))] for day in range(rng.randint(2, 4))]
        price = {slot.recipe.name: rng.randint(10, 60) for group in groups for slot in group}
        floor = {name: value - rng.randint(0, 8) for name, value in price.items()}
        taste = {name: rng.choice([0, 0, 1, -1]) for name in price}
        evaluated = []

        def evaluate(slots, final=True):
            evaluated.append(tuple(s.recipe.name for s in slots))
            return {"total": sum(price[s.recipe.name] for s in slots)}

        def score(slots, result):
            tastes = sum(taste[s.recipe.name] for s in slots)
            return (result["total"] + tastes * 2, result["total"], tuple(s.recipe.name for s in slots))

        def bounded(slots, incumbent_rank):
            bound = incumbent_rank[0] - sum(taste[s.recipe.name] for s in slots) * 2
            if sum(floor[s.recipe.name] for s in slots) > bound + 0.01:
                raise MenuBoundPruned
            return evaluate(slots)

        def run(**extra):
            evaluated.clear()
            return MenuOptimizer.__new__(MenuOptimizer)._optimize_complete_slots(
                groups, evaluate=evaluate, accepts=lambda slots, final=False: True, score=score,
                search_trace=[], state_identity=lambda slots: tuple(s.recipe.name for s in slots),
                decision_observer=None,
                candidate_priority=lambda slot: price[slot.recipe.name], candidate_packages=None, **extra)

        plain = run()
        plain_evaluations = len(evaluated)
        pruned = run(bounded_evaluate=bounded)
        assert [s.recipe.name for s in plain[0]] == [s.recipe.name for s in pruned[0]], trial
        assert plain[1] == pruned[1]
        assert len(evaluated) <= plain_evaluations
        saved += plain_evaluations - len(evaluated)
    assert saved > 0
