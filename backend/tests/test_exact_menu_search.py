from __future__ import annotations

from collections.abc import Iterable

import pytest
from app.models.product import ProductCandidate, SemanticConfidence
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.exact_menu_search import ExactMenuSearch
from app.services.menu_optimizer import MenuOptimizer


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
    package_quantity: float = 1,
    unit: str = "st",
    store_id: str = "a",
) -> ProductCandidate:
    return ProductCandidate(
        product_id=f"{store_id}-{ingredient}-{price}",
        product_name=f"{ingredient} {package_quantity} {unit}",
        canonical_name=ingredient,
        store_id=store_id,
        store_name=f"Butik {store_id.upper()}",
        package_quantity=package_quantity,
        package_unit=unit,
        semantic_confidence=SemanticConfidence.HIGH,
        price=price,
        effective_price=price,
        match_score=1,
    )


def _recipe(
    name: str,
    ingredients: Iterable[tuple[str, float, str]],
) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=ingredient,
                canonical_name=ingredient,
                quantity=quantity,
                unit=unit,  # type: ignore[arg-type]
            )
            for ingredient, quantity, unit in ingredients
        ],
        instructions=["Tillaga."],
    )


def test_exact_search_finds_known_shared_package_optimum() -> None:
    recipes = [
        _recipe("Separat A", [("råvara a", 1, "st")]),
        _recipe("Separat B", [("råvara b", 1, "st")]),
        _recipe("Delad C", [("delad", 4, "st")]),
        _recipe("Delad D", [("delad", 5, "st")]),
    ]
    candidates = {
        "råvara a": [_product("råvara a", 10)],
        "råvara b": [_product("råvara b", 10)],
        "delad": [_product("delad", 15, package_quantity=10)],
    }

    result = ExactMenuSearch().optimize(
        recipes,
        candidates,
        [_store()],
        recipe_count=2,
        max_stores=1,
    )

    assert {recipe.name for recipe in result.recipes} == {"Delad C", "Delad D"}
    assert result.basket.total == 15
    assert result.stats.combinations_total == 6
    assert result.stats.combinations_considered == 6
    assert result.stats.basket_calculations == result.stats.basket_cache_misses + 1


def test_exact_search_exposes_a_known_narrow_beam_quality_gap() -> None:
    # A looks cheapest at depth one. B and C cost more individually but share
    # a single package, so a width-one beam loses the global optimum.
    recipes = [
        _recipe("A", [("separat", 1, "st")]),
        _recipe("B", [("delad", 4, "st")]),
        _recipe("C", [("delad", 5, "st")]),
    ]
    candidates = {
        "separat": [_product("separat", 1)],
        "delad": [_product("delad", 10, package_quantity=10)],
    }
    stores = [_store()]

    exact = ExactMenuSearch().optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=1,
    )
    beam = MenuOptimizer().optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=1,
        beam_width=1,
    )

    assert {recipe.name for recipe in exact.recipes} == {"B", "C"}
    assert exact.basket.total == 10
    assert beam.basket.total == 11
    assert beam.basket.total > exact.basket.total


def test_exact_search_caches_equal_aggregate_requirement_states() -> None:
    recipes = [
        _recipe("A", [("x", 1, "st"), ("y", 1, "st")]),
        _recipe("B", [("x", 3, "st")]),
        _recipe("C", [("x", 2, "st"), ("y", 1, "st")]),
        _recipe("D", [("x", 2, "st")]),
    ]
    candidates = {
        "x": [_product("x", 1, package_quantity=10)],
        "y": [_product("y", 1, package_quantity=10)],
    }

    result = ExactMenuSearch().optimize(
        recipes,
        candidates,
        [_store()],
        recipe_count=2,
        max_stores=1,
    )

    assert result.stats.basket_cache_hits >= 1
    assert result.stats.basket_cache_misses < result.stats.combinations_evaluated
    assert result.stats.quote_cache_hits > 0


def test_exact_search_plan_predicate_can_enforce_later_invariants() -> None:
    recipes = [
        _recipe("Separat A", [("råvara a", 1, "st")]),
        _recipe("Separat B", [("råvara b", 1, "st")]),
        _recipe("Delad C", [("delad", 4, "st")]),
        _recipe("Delad D", [("delad", 5, "st")]),
    ]
    candidates = {
        "råvara a": [_product("råvara a", 10)],
        "råvara b": [_product("råvara b", 10)],
        "delad": [_product("delad", 15, package_quantity=10)],
    }

    result = ExactMenuSearch().optimize(
        recipes,
        candidates,
        [_store()],
        recipe_count=2,
        max_stores=1,
        plan_predicate=lambda plan: (
            {recipe.name for recipe in plan.recipes} != {"Delad C", "Delad D"}
        ),
    )

    assert {recipe.name for recipe in result.recipes} == {"Separat A", "Separat B"}
    assert result.basket.total == 20
    assert result.stats.predicate_rejections == 1


def test_exact_search_refuses_candidate_sets_above_its_safety_limit() -> None:
    recipes = [_recipe(f"Rätt {index}", [(f"råvara {index}", 1, "st")]) for index in range(4)]

    with pytest.raises(ValueError, match="at most 3 candidates"):
        ExactMenuSearch(max_candidates=3).optimize(
            recipes,
            {},
            [_store()],
            recipe_count=2,
            max_stores=1,
        )
