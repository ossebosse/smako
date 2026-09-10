from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from app.config import Settings
from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    QuantityConfidence,
    SemanticConfidence,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.basket_auditor import BasketAuditor
from app.services.basket_calculator import BasketCalculator
from app.services.basket_optimizer import BasketOptimizer
from app.services.exact_menu_search import ExactMenuSearch
from app.services.menu_optimizer import MenuOptimizer, admissible_checkout_lower_bound
from app.services.performance_trace import activate_performance_trace


def _store(store_id: str = "a") -> Store:
    return Store(
        store_id=store_id,
        name=f"Butik {store_id.upper()}",
        chain="Testkedjan",
        city="Lund",
        postal_code="22350",
    )


def _product(
    ingredient: str,
    price: float,
    *,
    product_id: str | None = None,
    store_id: str = "a",
    package_quantity: float = 1,
    offers: Iterable[OfferMetadata] = (),
) -> ProductCandidate:
    return ProductCandidate(
        product_id=product_id or f"{store_id}-{ingredient}-{price}",
        product_name=f"{ingredient} {package_quantity} st",
        canonical_name=ingredient,
        store_id=store_id,
        store_name=f"Butik {store_id.upper()}",
        package_quantity=package_quantity,
        package_unit="st",
        price=price,
        effective_price=price,
        match_score=1,
        semantic_confidence=SemanticConfidence.HIGH,
        semantic_evidence=["fixture exact identity"],
        quantity_confidence=QuantityConfidence.EXACT,
        offers=list(offers),
    )


def _recipe(name: str, ingredients: Iterable[tuple[str, float]]) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=ingredient,
                canonical_name=ingredient,
                quantity=quantity,
                unit="st",
            )
            for ingredient, quantity in ingredients
        ],
        instructions=["Tillaga."],
    )


def test_stability_rollout_flag_is_explicit(monkeypatch) -> None:
    monkeypatch.delenv("STABLE_CANDIDATE_SEARCH_ENABLED", raising=False)

    assert Settings().stable_candidate_search_enabled is False
    assert Settings.from_env().stable_candidate_search_enabled is False

    monkeypatch.setenv("STABLE_CANDIDATE_SEARCH_ENABLED", "true")
    assert Settings.from_env().stable_candidate_search_enabled is True


def test_canonical_requirement_cache_reuses_economically_equal_recipe_sets() -> None:
    # A+B and C+D aggregate to the same canonical x=2,y=1,z=1 basket even
    # though their individual recipe profiles and recipe ordering differ.
    recipes = [
        _recipe("A", [("x", 1), ("y", 1)]),
        _recipe("B", [("x", 1), ("z", 1)]),
        _recipe("C", [("x", 2), ("y", 1)]),
        _recipe("D", [("z", 1)]),
    ]
    products = {
        ingredient: [_product(ingredient, 1, package_quantity=10)]
        for ingredient in ("x", "y", "z")
    }

    legacy = MenuOptimizer().optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
        beam_width=10,
    )
    reused = MenuOptimizer().optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
        beam_width=10,
        search_reuse_enabled=True,
    )

    assert reused.basket.total == legacy.basket.total
    assert reused.stats.cache_misses < legacy.stats.cache_misses
    assert reused.stats.incremental_requirement_cache_hits > 0


def test_economic_cache_hits_are_audited_once_with_winner_recipe_lineage() -> None:
    class CountingAuditor(BasketAuditor):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def audit(self, *args, **kwargs):
            self.calls += 1
            return super().audit(*args, **kwargs)

    # A+B and C+D have the same purchasable and pantry requirements, while
    # their recipe names differ. Search may reuse their economic evaluation,
    # but the public result must retain the selected recipes' exact lineage.
    recipes = [
        _recipe("A", [("x", 1), ("salt", 1)]),
        _recipe("B", [("y", 1)]),
        _recipe("C", [("x", 1)]),
        _recipe("D", [("y", 1), ("salt", 1)]),
    ]
    products = {
        ingredient: [_product(ingredient, 1, package_quantity=10)]
        for ingredient in ("x", "y")
    }
    auditor = CountingAuditor()

    result = MenuOptimizer(basket_auditor=auditor).optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
        beam_width=10,
        search_reuse_enabled=True,
    )

    selected_names = {recipe.name for recipe in result.recipes}
    for ingredient in result.ingredients:
        expected = {
            recipe.name
            for recipe in result.recipes
            if any(
                row.canonical_name == ingredient.canonical_name
                for row in recipe.ingredients
            )
        }
        assert set(ingredient.source_recipes) == expected
    assert set(result.basket_audit.pantry_items[0].source_recipes) == (
        selected_names & {"A", "D"}
    )
    assert result.stats.cache_hits > 0
    # One audit per successful economic miss, plus the empty basket and the
    # final lineage-bound winner; cache hits themselves perform no audit.
    assert auditor.calls == result.stats.cache_misses + 2


def test_store_subsets_are_memoized_without_changing_basket() -> None:
    optimizer = BasketOptimizer(memoize_store_subsets=True)
    recipe = _recipe("A", [("x", 1)])
    ingredients = MenuOptimizer().normalizer.normalize_and_aggregate([recipe])
    products = {
        "x": [
            _product("x", 4, store_id="a"),
            _product("x", 3, store_id="b"),
        ]
    }
    stores = [_store("a"), _store("b")]

    first = optimizer.optimize(ingredients, products, stores, max_stores=2)
    second = optimizer.optimize(ingredients, products, stores, max_stores=2)

    assert first == second
    assert optimizer.store_subset_cache_stats.hits == 1
    assert optimizer.store_subset_cache_stats.misses == 1
    assert optimizer.store_subset_cache_stats.entries == 1


def test_lower_bound_remains_admissible_when_multibuy_total_drops() -> None:
    # Deliberately extreme source semantics: two packages cost less than one.
    # A partial-state current basket is therefore *not* a safe lower bound,
    # while the conservative checkout floor still is.
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 för 8",
        price=8,
        required_packages=2,
    )
    products = {"x": [_product("x", 10, offers=[offer])]}
    optimizer = MenuOptimizer()
    one = _recipe("En", [("x", 1)])
    two = _recipe("Två", [("x", 2)])
    profile = optimizer._profile(one)
    floor = admissible_checkout_lower_bound([profile], products)
    one_basket = optimizer.basket_optimizer.optimize(
        optimizer.normalizer.normalize_and_aggregate([one]),
        products,
        [_store()],
        max_stores=1,
    )
    two_basket = optimizer.basket_optimizer.optimize(
        optimizer.normalizer.normalize_and_aggregate([two]),
        products,
        [_store()],
        max_stores=1,
    )

    assert one_basket.total == 10
    assert two_basket.total == 8
    assert floor == 8
    assert floor <= one_basket.total
    assert floor <= two_basket.total


def test_optimized_search_matches_exact_reference_on_small_candidate_set() -> None:
    recipes = [
        _recipe("Separat A", [("a", 1)]),
        _recipe("Separat B", [("b", 1)]),
        _recipe("Delad C", [("shared", 4)]),
        _recipe("Delad D", [("shared", 5)]),
        _recipe("Mix E", [("a", 1), ("shared", 1)]),
    ]
    products = {
        "a": [_product("a", 10)],
        "b": [_product("b", 10)],
        "shared": [_product("shared", 15, package_quantity=10)],
    }
    exact = ExactMenuSearch(max_candidates=10).optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
    )
    optimized = MenuOptimizer().optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
        beam_width=10,
        search_reuse_enabled=True,
        admissible_lower_bound_enabled=True,
    )

    assert optimized.basket.total == exact.basket.total
    assert optimized.basket.total - exact.basket.total == 0


def test_admissible_bound_prunes_only_states_worse_than_verified_incumbent() -> None:
    recipes = [
        _recipe("Delad A", [("shared", 4)]),
        _recipe("Delad B", [("shared", 5)]),
        _recipe("Dyr C", [("expensive", 1)]),
    ]
    products = {
        "shared": [_product("shared", 10, package_quantity=10)],
        "expensive": [_product("expensive", 100)],
    }

    result = MenuOptimizer().optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
        search_reuse_enabled=True,
        admissible_lower_bound_enabled=True,
    )

    assert result.basket.total == 10
    assert result.stats.lower_bound_rejections > 0
    assert result.stats.greedy_seed_evaluations > 0


def test_lazy_exact_bound_preserves_beam_result_and_reduces_full_baskets() -> None:
    recipes = [
        _recipe(
            f"Recipe {index:02d}",
            [(f"ingredient-{index:02d}", index + 1)],
        )
        for index in range(36)
    ]
    products = {
        f"ingredient-{index:02d}": [
            _product(
                f"ingredient-{index:02d}",
                1,
                package_quantity=1,
            )
        ]
        for index in range(36)
    }
    optimizer = MenuOptimizer()

    eager = optimizer.optimize(
        recipes,
        products,
        [_store()],
        recipe_count=3,
        max_stores=1,
        beam_width=8,
        search_reuse_enabled=True,
        admissible_lower_bound_enabled=False,
    )
    lazy = optimizer.optimize(
        recipes,
        products,
        [_store()],
        recipe_count=3,
        max_stores=1,
        beam_width=8,
        search_reuse_enabled=True,
        admissible_lower_bound_enabled=True,
    )

    assert [row.name for row in lazy.recipes] == [row.name for row in eager.recipes]
    assert lazy.basket.model_dump() == eager.basket.model_dump()
    assert lazy.stats.basket_calculations < eager.stats.basket_calculations
    assert lazy.stats.optimistic_bound_evaluations > 0
    assert lazy.stats.optimistic_bound_rejections > 0


def test_lazy_bound_evaluates_equal_cost_states_for_deterministic_ties() -> None:
    recipes = [
        _recipe("A", [("a", 1)]),
        _recipe("B", [("b", 1)]),
        _recipe("C", [("c", 1)]),
    ]
    products = {
        ingredient: [_product(ingredient, 5, package_quantity=1)]
        for ingredient in ("a", "b", "c")
    }
    optimizer = MenuOptimizer()
    eager = optimizer.optimize(
        recipes,
        products,
        [_store()],
        recipe_count=1,
        max_stores=1,
        beam_width=1,
        search_reuse_enabled=True,
    )
    lazy = optimizer.optimize(
        recipes,
        products,
        [_store()],
        recipe_count=1,
        max_stores=1,
        beam_width=1,
        search_reuse_enabled=True,
        admissible_lower_bound_enabled=True,
    )

    assert [row.name for row in lazy.recipes] == [row.name for row in eager.recipes]
    assert lazy.basket.model_dump() == eager.basket.model_dump()


def test_quantity_aware_relaxation_is_below_authoritative_multibuy_basket() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 för 8",
        price=8,
        required_packages=2,
    )
    ingredient = MenuOptimizer().normalizer.normalize_and_aggregate(
        [_recipe("Två", [("x", 2)])]
    )
    products = {"x": (_product("x", 10, offers=[offer]),)}
    basket_optimizer = BasketOptimizer()

    with basket_optimizer.quote_cache():
        relaxed = basket_optimizer.optimistic_relaxed_key(
            ingredient,
            products,
            allowed_store_ids=("a",),
        )
        authoritative = basket_optimizer.optimize(
            ingredient,
            products,
            [_store()],
            max_stores=1,
        )

    assert relaxed is not None
    assert relaxed[1] == 8
    assert relaxed[1] <= authoritative.total


def test_same_depth_store_limited_key_matches_authoritative_multistore_multibuy() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 för 8",
        price=8,
        required_packages=2,
    )
    ingredients = MenuOptimizer().normalizer.normalize_and_aggregate(
        [_recipe("Veckokorg", [("x", 2), ("y", 1)])]
    )
    products = {
        "x": (
            _product("x", 10, store_id="a", offers=[offer]),
            _product("x", 12, store_id="b"),
        ),
        "y": (
            _product("y", 20, store_id="a"),
            _product("y", 3, store_id="b"),
        ),
    }
    optimizer = BasketOptimizer(memoize_store_subsets=True)

    with optimizer.quote_cache():
        leading = optimizer.same_depth_store_limited_key(
            ingredients,
            products,
            [_store("a"), _store("b")],
            max_stores=2,
        )
        authoritative = optimizer.optimize(
            ingredients,
            products,
            [_store("a"), _store("b")],
            max_stores=2,
        )

    assert leading == (0, Decimal("11.00"), 2)
    assert leading[1] == Decimal(str(authoritative.total))
    assert leading[2] == authoritative.store_count


def test_compact_requirement_keys_match_normalized_same_depth_vectors() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 för 8",
        price=8,
        required_packages=2,
    )
    ingredients = MenuOptimizer().normalizer.normalize_and_aggregate(
        [_recipe("Veckokorg", [("x", 2), ("y", 1)])]
    )
    requirements = tuple(
        (
            ingredient.canonical_name,
            str(Decimal(str(ingredient.required_quantity)).normalize()),
            ingredient.unit,
        )
        for ingredient in ingredients
    )
    products = {
        "x": (
            _product("x", 10, store_id="a", offers=[offer]),
            _product("x", 12, store_id="b"),
        ),
        "y": (
            _product("y", 20, store_id="a"),
            _product("y", 3, store_id="b"),
        ),
    }
    stores = (_store("a"), _store("b"))
    optimizer = BasketOptimizer(memoize_store_subsets=True)

    with optimizer.quote_cache():
        compact = optimizer.same_depth_nested_store_limited_requirement_keys(
            requirements,
            products,
            stores,
            max_stores=2,
        )
        normalized = optimizer.same_depth_nested_store_limited_keys(
            ingredients,
            products,
            stores,
            max_stores=2,
        )

    assert compact == normalized == (
        (0, Decimal("27.00"), 1),
        (0, Decimal("11.00"), 2),
    )


def test_same_depth_reuses_exact_quote_subset_vectors() -> None:
    ingredients = MenuOptimizer().normalizer.normalize_and_aggregate(
        [_recipe("Veckokorg", [("x", 1), ("y", 1)])]
    )
    products = {
        "x": (
            _product("x", 5, store_id="a"),
            _product("x", 6, store_id="b"),
        ),
        "y": (
            _product("y", 7, store_id="a"),
            _product("y", 4, store_id="b"),
        ),
    }
    stores = [_store("a"), _store("b")]
    optimizer = BasketOptimizer(memoize_store_subsets=True)

    with activate_performance_trace() as trace:
        with optimizer.quote_cache() as stats:
            first = optimizer.same_depth_store_limited_key(
                ingredients,
                products,
                stores,
                max_stores=2,
            )
            misses_after_first = stats.subset_vector_misses
            second = optimizer.same_depth_store_limited_key(
                ingredients,
                products,
                stores,
                max_stores=2,
            )
        counters = trace.snapshot().operation_counters

    # Two exact quantity-specific quote sets build their complete three-subset
    # vectors once. The repeated state performs two vector-cache hits and no
    # authoritative selection-cache work.
    assert first == second == (0, Decimal("9.00"), 2)
    assert misses_after_first == 2
    assert stats.subset_vector_misses == 2
    assert stats.subset_vector_hits == 2
    assert stats.selection_misses == 0
    assert stats.selection_hits == 0
    assert stats.per_store_selection_misses == 2
    assert stats.per_store_selection_hits == 0
    assert counters["optimistic_store_subset_evaluations"] == 6
    assert counters.get("optimistic_store_subsets_infeasible", 0) == 0


def test_same_depth_per_store_vector_is_order_invariant_and_authoritative() -> None:
    offer = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 for 8",
        price=8,
        required_packages=2,
    )
    ingredients = MenuOptimizer().normalizer.normalize_and_aggregate(
        [_recipe("Weekly basket", [("x", 2), ("y", 1), ("z", 1)])]
    )
    products = {
        "x": (
            _product("x", 10, product_id="a-x-z", store_id="a", offers=[offer]),
            _product("x", 10, product_id="a-x-a", store_id="a", offers=[offer]),
            _product("x", 9, product_id="b-x", store_id="b"),
            _product("x", 7, product_id="c-x", store_id="c"),
        ),
        "y": (
            _product("y", 3, product_id="a-y", store_id="a"),
            _product("y", 4, product_id="b-y", store_id="b"),
            _product("y", 12, product_id="c-y", store_id="c"),
        ),
        "z": (
            _product("z", 15, product_id="a-z", store_id="a"),
            _product("z", 5, product_id="b-z", store_id="b"),
            _product("z", 6, product_id="c-z", store_id="c"),
        ),
    }
    stores = [_store("a"), _store("b"), _store("c")]

    for product_order, store_order in (
        (products, stores),
        (
            {name: tuple(reversed(rows)) for name, rows in reversed(products.items())},
            list(reversed(stores)),
        ),
    ):
        for max_stores in (1, 2, 3):
            optimizer = BasketOptimizer(memoize_store_subsets=True)
            with optimizer.quote_cache():
                leading = optimizer.same_depth_store_limited_key(
                    ingredients,
                    product_order,
                    store_order,
                    max_stores=max_stores,
                )
                authoritative = optimizer.optimize(
                    ingredients,
                    product_order,
                    store_order,
                    max_stores=max_stores,
                )

            assert leading == (
                0,
                Decimal(str(authoritative.total)),
                authoritative.store_count,
            )


def test_same_depth_custom_calculator_keeps_uncached_fallback() -> None:
    class CountingCalculator(BasketCalculator):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def quote_item(self, ingredient, candidate):
            self.calls += 1
            return super().quote_item(ingredient, candidate)

    calculator = CountingCalculator()
    optimizer = BasketOptimizer(
        calculator=calculator,
        memoize_store_subsets=True,
    )
    ingredients = MenuOptimizer().normalizer.normalize_and_aggregate(
        [_recipe("Veckokorg", [("x", 1)])]
    )
    products = {
        "x": (
            _product("x", 5, store_id="a"),
            _product("x", 6, store_id="b"),
        )
    }
    stores = [_store("a"), _store("b")]

    with optimizer.quote_cache() as stats:
        first = optimizer.same_depth_store_limited_key(
            ingredients,
            products,
            stores,
            max_stores=2,
        )
        second = optimizer.same_depth_store_limited_key(
            ingredients,
            products,
            stores,
            max_stores=2,
        )

    assert first == second == (0, Decimal("5.00"), 1)
    assert calculator.calls == 4
    assert stats.quote_set_hits == 0
    assert stats.quote_set_misses == 0
    assert stats.selection_hits == 0
    assert stats.selection_misses == 0


def test_search_space_counters_are_exact_and_additive() -> None:
    recipes = [
        _recipe("A", [("a", 1)]),
        _recipe("B", [("b", 1)]),
        _recipe("C", [("c", 1)]),
    ]
    products = {
        ingredient: [_product(ingredient, 5)] for ingredient in ("a", "b", "c")
    }

    result = MenuOptimizer().optimize(
        recipes,
        products,
        [_store()],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
        search_reuse_enabled=True,
    )

    assert result.stats.possible_menu_combinations == 3
    # Depth one visits three candidates. Depth two visits all three candidates
    # from each of the three retained states, including the selected-profile
    # checks which are rejected before pricing.
    assert result.stats.expansion_candidates_visited == 12
    assert result.stats.unique_economic_states == result.stats.optimistic_bound_evaluations
    assert result.stats.duplicate_economic_state_hits >= 0
    assert result.stats.full_basket_evaluations == result.stats.basket_calculations
