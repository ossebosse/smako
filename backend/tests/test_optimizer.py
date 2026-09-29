from random import Random

import pytest
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
)
from app.models.store import Store
from app.services import basket_optimizer as basket_optimizer_module
from app.services.basket_calculator import BasketCalculator, BasketItemQuote
from app.services.basket_optimizer import BasketOptimizer
from app.services.performance_trace import activate_performance_trace


def store(store_id: str, name: str | None = None) -> Store:
    return Store(
        store_id=store_id,
        name=name or store_id,
        chain="Testkedjan",
        city="Lund",
        postal_code="22350",
    )


def product(
    ingredient: str,
    product_id: str,
    store_id: str,
    package_quantity: float,
    price: float,
    *,
    unit: str = "g",
    match_score: float = 1,
    offers: list[OfferMetadata] | None = None,
) -> ProductCandidate:
    return ProductCandidate(
        product_id=product_id,
        product_name=product_id,
        canonical_name=ingredient,
        store_id=store_id,
        store_name=store_id,
        package_quantity=package_quantity,
        package_unit=unit,
        price=price,
        effective_price=price,
        match_score=match_score,
        offers=offers or [],
    )


def test_cheapest_purchase_not_lowest_unit_price() -> None:
    # Specens exakta exempel: A 500 g/30 kr och B 1000 g/55 kr för behov 1200 g.
    # A kostar 3*30=90, B kostar 2*55=110, trots B:s lägre kilopris.
    ingredient = NormalizedIngredient(canonical_name="kyckling", required_quantity=1200, unit="g")
    candidates = {
        "kyckling": [
            product("kyckling", "A", "s1", 500, 30),
            product("kyckling", "B", "s1", 1000, 55),
        ]
    }

    option = BasketOptimizer().single_store_options([ingredient], candidates, [store("s1")])[0]

    assert option.is_complete
    assert option.items[0].product_id == "A"
    assert option.items[0].packages_needed == 3
    assert option.total == 90


def multi_store_case():
    ingredients = [
        NormalizedIngredient(canonical_name="pasta", required_quantity=500, unit="g"),
        NormalizedIngredient(canonical_name="bönor", required_quantity=500, unit="g"),
    ]
    candidates = {
        "pasta": [
            product("pasta", "pasta-a", "a", 500, 10),
            product("pasta", "pasta-b", "b", 500, 50),
        ],
        "bönor": [
            product("bönor", "beans-a", "a", 500, 50),
            product("bönor", "beans-b", "b", 500, 10),
        ],
    }
    stores = [store("a", "Butik A"), store("b", "Butik B")]
    return ingredients, candidates, stores


def test_two_store_optimizer_beats_best_single_store() -> None:
    ingredients, candidates, stores = multi_store_case()
    optimizer = BasketOptimizer()

    singles = optimizer.single_store_options(ingredients, candidates, stores)
    optimized = optimizer.optimize(ingredients, candidates, stores, max_stores=2)

    assert singles[0].total == 60
    assert optimized.total == 20
    assert optimized.store_count == 2
    assert [group.store_id for group in optimized.stores] == ["a", "b"]
    assert [group.subtotal for group in optimized.stores] == [10, 10]
    assert optimized.savings_vs_single_store == 40


def test_requested_store_cap_above_available_is_equivalent_to_available_cap() -> None:
    ingredients, candidates, stores = multi_store_case()
    optimizer = BasketOptimizer()

    available_cap = optimizer.optimize(
        ingredients,
        candidates,
        stores,
        max_stores=2,
    )
    requested_cap = optimizer.optimize(
        ingredients,
        candidates,
        stores,
        max_stores=5,
    )

    assert requested_cap.max_stores == 5
    assert requested_cap.store_count <= len(stores) == 2
    assert requested_cap.model_dump(exclude={"max_stores"}) == (
        available_cap.model_dump(exclude={"max_stores"})
    )


def test_store_availability_prunes_only_infeasible_subsets() -> None:
    ingredients, candidates, stores = multi_store_case()
    candidates = {
        "pasta": [candidates["pasta"][0]],
        "bönor": [candidates["bönor"][1]],
    }
    stores.append(store("c", "Butik C utan kandidater"))

    with activate_performance_trace() as trace:
        optimized = BasketOptimizer().optimize(
            ingredients,
            candidates,
            stores,
            max_stores=2,
        )

    counters = trace.snapshot().operation_counters
    assert optimized.total == 20
    assert [group.store_id for group in optimized.stores] == ["a", "b"]
    assert counters["store_combinations"] == 6
    assert counters["store_combinations_pruned_infeasible"] == 5


def test_store_combination_trace_is_batched_without_changing_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingredients, candidates, stores = multi_store_case()
    candidates = {
        "pasta": [candidates["pasta"][0]],
        "bönor": [candidates["bönor"][1]],
    }
    stores.append(store("c", "Butik C utan kandidater"))
    increments: list[tuple[str, int]] = []

    monkeypatch.setattr(
        basket_optimizer_module,
        "increment_performance_counter",
        lambda name, amount=1: increments.append((name, amount)),
    )

    optimized = BasketOptimizer().optimize(
        ingredients,
        candidates,
        stores,
        max_stores=2,
    )

    assert optimized.total == 20
    assert [group.store_id for group in optimized.stores] == ["a", "b"]
    assert [row for row in increments if row[0] == "store_combinations"] == [
        ("store_combinations", 6)
    ]
    assert [
        row
        for row in increments
        if row[0] == "store_combinations_pruned_infeasible"
    ] == [("store_combinations_pruned_infeasible", 5)]


@pytest.mark.parametrize("max_stores", [1, 2, 3, None, 0])
def test_store_limit_scenarios(max_stores: int | None) -> None:
    ingredients, candidates, stores = multi_store_case()
    # A third store proves max=3 and unlimited still select only stores that are
    # actually useful; an allowed combination does not inflate store_count.
    stores.append(store("c", "Butik C"))
    candidates["pasta"].append(product("pasta", "pasta-c", "c", 500, 90))
    candidates["bönor"].append(product("bönor", "beans-c", "c", 500, 90))

    optimized = BasketOptimizer().optimize(ingredients, candidates, stores, max_stores=max_stores)

    if max_stores == 1:
        assert optimized.total == 60
        assert optimized.store_count == 1
    else:
        assert optimized.total == 20
        assert optimized.store_count == 2


@pytest.mark.parametrize("seed", range(12))
def test_fixed_basket_cost_is_monotone_for_nested_store_caps(seed: int) -> None:
    """Property-style check of the exact AT MOST N subset contract."""

    random = Random(seed)
    stores = [store(store_id) for store_id in ("a", "b", "c")]
    ingredients = [
        NormalizedIngredient(
            canonical_name=f"ingredient-{index}",
            required_quantity=1 + (index % 3),
            unit="st",
        )
        for index in range(5)
    ]
    candidates = {
        ingredient.canonical_name: [
            product(
                ingredient.canonical_name,
                f"{store_row.store_id}-{ingredient.canonical_name}",
                store_row.store_id,
                random.randint(1, 4),
                random.randint(1, 50),
                unit="st",
            )
            for store_row in stores
        ]
        for ingredient in ingredients
    }
    optimizer = BasketOptimizer()

    baskets = [
        optimizer.optimize(ingredients, candidates, stores, max_stores=cap)
        for cap in (1, 2, 3)
    ]

    assert baskets[1].total <= baskets[0].total
    assert baskets[2].total <= baskets[1].total
    for cap, basket in enumerate(baskets, start=1):
        assert basket.max_stores == cap
        assert basket.store_count <= cap
        assert all(
            item.product_id.startswith(f"{group.store_id}-")
            for group in basket.stores
            for item in group.items
        )


def test_incomplete_single_store_is_marked_and_sorted_after_complete() -> None:
    ingredients, candidates, stores = multi_store_case()
    candidates["bönor"] = [candidates["bönor"][0]]  # only store a has beans

    options = BasketOptimizer().single_store_options(ingredients, candidates, stores)

    assert options[0].store_id == "a"
    assert options[0].is_complete
    assert options[1].store_id == "b"
    assert not options[1].is_complete
    assert options[1].missing_ingredients == ["bönor"]


def test_optimizer_materializes_only_the_winning_quotes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingredients, candidates, stores = multi_store_case()
    stores.append(store("c", "Butik C"))
    candidates["pasta"].append(product("pasta", "pasta-c", "c", 500, 30))
    candidates["bönor"].append(product("bönor", "beans-c", "c", 500, 30))
    materialized: list[str] = []
    original = BasketItemQuote.to_basket_item

    def materialize(quote: BasketItemQuote):
        materialized.append(quote.product_id)
        return original(quote)

    monkeypatch.setattr(BasketItemQuote, "to_basket_item", materialize)

    optimized = BasketOptimizer().optimize(
        ingredients,
        candidates,
        stores,
        max_stores=3,
        calculate_savings=True,
    )

    assert optimized.total == 20
    assert materialized == ["pasta-a", "beans-b"]


def test_quote_tie_break_keeps_match_score_before_waste() -> None:
    ingredient = NormalizedIngredient(canonical_name="potatis", required_quantity=600, unit="g")
    candidates = {
        "potatis": [
            product(
                "potatis",
                "exact-lower-match",
                "s1",
                600,
                10,
                match_score=0.9,
            ),
            product(
                "potatis",
                "wasteful-higher-match",
                "s1",
                1000,
                10,
                match_score=1,
            ),
        ]
    }

    result = BasketOptimizer().optimize([ingredient], candidates, [store("s1")], max_stores=1)

    assert result.stores[0].items[0].product_id == "wasteful-higher-match"
    assert result.stores[0].items[0].waste_quantity == 400


def test_optimizer_quote_path_preserves_multipack_and_savings_flag() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="3 för 90 kr",
        price=90,
        required_packages=3,
    )
    ingredient = NormalizedIngredient(canonical_name="kyckling", required_quantity=1200, unit="g")
    candidates = {
        "kyckling": [
            product(
                "kyckling",
                "multipack",
                "s1",
                500,
                40,
                offers=[offer],
            ),
            product("kyckling", "ordinary", "s1", 1000, 50),
        ]
    }

    result = BasketOptimizer().optimize(
        [ingredient],
        candidates,
        [store("s1")],
        max_stores=1,
        calculate_savings=False,
    )

    assert result.total == 90
    assert result.savings_vs_single_store is None
    assert result.stores[0].items[0].product_id == "multipack"
    assert result.stores[0].items[0].applied_offer == offer


def test_injected_calculate_item_override_remains_supported() -> None:
    class SurchargeCalculator(BasketCalculator):
        def calculate_item(self, ingredient, candidate):
            item = super().calculate_item(ingredient, candidate)
            return item.model_copy(
                update={
                    "unit_price": item.unit_price + 5,
                    "total_price": item.total_price + 5 * item.packages_needed,
                }
            )

    ingredient = NormalizedIngredient(canonical_name="pasta", required_quantity=500, unit="g")
    candidates = {"pasta": [product("pasta", "pasta", "s1", 500, 10)]}

    result = BasketOptimizer(calculator=SurchargeCalculator()).optimize(
        [ingredient], candidates, [store("s1")], max_stores=1
    )

    assert result.total == 15
    assert result.stores[0].items[0].unit_price == 15


def test_quote_cache_hits_and_misses_are_request_local() -> None:
    ingredient = NormalizedIngredient(canonical_name="potatis", required_quantity=1200, unit="g")
    candidates = {
        "potatis": (
            product("potatis", "small", "s1", 500, 10),
            product("potatis", "large", "s1", 1000, 19),
        )
    }
    optimizer = BasketOptimizer()

    with optimizer.quote_cache() as first:
        optimizer.optimize([ingredient], candidates, [store("s1")], 1, calculate_savings=False)
        optimizer.optimize([ingredient], candidates, [store("s1")], 1, calculate_savings=False)
        repriced = candidates["potatis"][1].model_copy(update={"price": 5, "effective_price": 5})
        repriced_result = optimizer.optimize(
            [ingredient],
            {"potatis": [repriced]},
            [store("s1")],
            1,
            calculate_savings=False,
        )

    assert first.misses == 3
    # The second basket now reuses the exact requirement-level quote tuple and
    # store-subset winner before it needs to touch either package quote again.
    assert first.hits == 0
    assert first.quote_set_hits == 1
    assert first.quote_set_misses == 1
    assert first.selection_hits == 1
    assert first.selection_misses == 1
    assert repriced_result.total == 10

    # A new request/session must recalculate from its own product snapshot.
    with optimizer.quote_cache() as second:
        optimizer.optimize([ingredient], candidates, [store("s1")], 1, calculate_savings=False)

    assert second.misses == 2
    assert second.hits == 0
    assert second.quote_set_hits == 0
    assert second.selection_hits == 0


def test_explicit_nested_request_reuse_and_version_isolation() -> None:
    ingredient = NormalizedIngredient(canonical_name="potatis", required_quantity=600, unit="g")
    candidates = {"potatis": (product("potatis", "same", "s1", 500, 10),)}
    optimizer = BasketOptimizer()
    with optimizer.quote_cache() as outer:
        with optimizer.quote_cache(reuse_existing=True) as nested:
            assert nested is outer
            first = optimizer.optimize([ingredient], candidates, [store("s1")], 1)
        with optimizer.quote_cache(reuse_existing=True) as nested:
            second = optimizer.optimize([ingredient], candidates, [store("s1")], 1)
        assert first == second
        with optimizer.quote_cache(reuse_existing=True, calculator_version="another") as isolated:
            assert isolated is not outer
            optimizer.optimize([ingredient], candidates, [store("s1")], 1)
            assert isolated.calculations > 0
        assert outer.quote_set_hits > 0
    with optimizer.quote_cache(reuse_existing=True) as next_request:
        assert next_request is not outer
        optimizer.optimize([ingredient], candidates, [store("s1")], 1)
        assert next_request.calculations > 0


def test_mutable_candidate_sequence_never_reuses_a_stale_quote_set() -> None:
    ingredient = NormalizedIngredient(
        canonical_name="potatis",
        required_quantity=500,
        unit="g",
    )
    rows = [product("potatis", "first", "s1", 500, 10)]
    candidates = {"potatis": rows}
    optimizer = BasketOptimizer()

    with optimizer.quote_cache() as stats:
        first = optimizer.optimize(
            [ingredient], candidates, [store("s1")], 1, calculate_savings=False
        )
        rows[0] = product("potatis", "replacement", "s1", 500, 5)
        second = optimizer.optimize(
            [ingredient], candidates, [store("s1")], 1, calculate_savings=False
        )

    assert first.total == 10
    assert second.total == 5
    assert stats.quote_set_hits == 0


def test_cached_and_uncached_baskets_are_identical() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="3 för 25 kr",
        price=25,
        required_packages=3,
    )
    ingredients, candidates, stores = multi_store_case()
    candidates["pasta"].append(product("pasta", "pasta-offer", "a", 250, 10, offers=[offer]))
    optimizer = BasketOptimizer()

    uncached = optimizer.optimize(ingredients, candidates, stores, max_stores=2)
    with optimizer.quote_cache():
        cached = optimizer.optimize(ingredients, candidates, stores, max_stores=2)

    assert cached.model_dump() == uncached.model_dump()


def test_quote_cache_fingerprint_includes_usable_quantity_metadata() -> None:
    ingredient = NormalizedIngredient(canonical_name="kidneybönor", required_quantity=350, unit="g")
    gross = product("kidneybönor", "can", "s1", 380, 12.90)
    drained = gross.model_copy(
        update={
            "usable_quantity": 230,
            "usable_unit": "g",
            "quantity_confidence": QuantityConfidence.EXACT,
        }
    )
    optimizer = BasketOptimizer()

    with optimizer.quote_cache() as stats:
        gross_result = optimizer.optimize([ingredient], {"kidneybönor": [gross]}, [store("s1")], 1)
        drained_result = optimizer.optimize(
            [ingredient], {"kidneybönor": [drained]}, [store("s1")], 1
        )

    assert stats.misses == 2
    assert stats.hits == 0
    assert gross_result.total == 12.90
    assert drained_result.total == 25.80
