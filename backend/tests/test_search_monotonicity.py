"""Economic monotonicity controls for fixed requirements/candidate recipes."""

from __future__ import annotations

from collections.abc import Iterable

from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    OfferKind,
    OfferMetadata,
    ProductCandidate,
    SemanticConfidence,
)
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.basket_optimizer import BasketOptimizer
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
    product_id: str,
    price: float,
    *,
    store_id: str = "a",
    package_quantity: float = 1,
    offers: Iterable[OfferMetadata] = (),
) -> ProductCandidate:
    return ProductCandidate(
        product_id=product_id,
        product_name=f"{ingredient} {package_quantity} st",
        canonical_name=ingredient,
        store_id=store_id,
        store_name=f"Butik {store_id.upper()}",
        package_quantity=package_quantity,
        package_unit="st",
        semantic_confidence=SemanticConfidence.HIGH,
        price=price,
        effective_price=price,
        match_score=1,
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


def test_fixed_basket_cannot_become_more_expensive_when_products_are_added() -> None:
    requirements = [
        NormalizedIngredient(canonical_name="ris", required_quantity=1, unit="st")
    ]
    original = {"ris": [_product("ris", "original", 20)]}
    expanded = {
        "ris": [
            *original["ris"],
            _product("ris", "additional", 15),
        ]
    }
    optimizer = BasketOptimizer()

    before = optimizer.optimize(requirements, original, [_store()], max_stores=1)
    after = optimizer.optimize(requirements, expanded, [_store()], max_stores=1)

    assert after.total <= before.total
    assert before.total == 20
    assert after.total == 15


def test_exact_cheapest_menu_is_monotone_for_fixed_recipe_candidates() -> None:
    recipes = [
        _recipe("Separat A", [("a", 1)]),
        _recipe("Separat B", [("b", 1)]),
        _recipe("Delad C", [("delad", 4)]),
        _recipe("Delad D", [("delad", 5)]),
    ]
    original = {
        "a": [_product("a", "a-original", 10)],
        "b": [_product("b", "b-original", 10)],
        "delad": [_product("delad", "shared-original", 15, package_quantity=10)],
    }
    expanded = {
        **original,
        "a": [*original["a"], _product("a", "a-additional", 8)],
    }
    search = ExactMenuSearch()

    before = search.optimize(
        recipes,
        original,
        [_store()],
        recipe_count=2,
        max_stores=1,
    )
    after = search.optimize(
        recipes,
        expanded,
        [_store()],
        recipe_count=2,
        max_stores=1,
    )

    assert after.basket.total <= before.basket.total
    assert before.basket.total == after.basket.total == 15
    assert {recipe.name for recipe in after.recipes} == {"Delad C", "Delad D"}


def test_production_beam_cheapest_is_monotone_when_products_are_only_added() -> None:
    multibuy = OfferMetadata(
        kind=OfferKind.MULTIPACK,
        description="2 for 12",
        price=12,
        required_packages=2,
    )
    recipes = [
        _recipe("Delad A", [("x", 1), ("y", 1)]),
        _recipe("Delad B", [("x", 1), ("z", 1)]),
        _recipe("Separat C", [("c", 1)]),
        _recipe("Separat D", [("d", 1)]),
        _recipe("Mix E", [("c", 1), ("y", 1)]),
    ]
    original = {
        "x": [_product("x", "a-x", 10, offers=[multibuy])],
        "y": [_product("y", "b-y", 3, store_id="b")],
        "z": [_product("z", "b-z", 4, store_id="b")],
        "c": [_product("c", "a-c", 11)],
        "d": [_product("d", "b-d", 12, store_id="b")],
    }
    expanded = {
        **original,
        "c": [
            *original["c"],
            _product("c", "b-c-additional", 8, store_id="b"),
        ],
        "d": [
            *original["d"],
            _product("d", "a-d-additional", 9),
        ],
    }
    stores = [_store("a"), _store("b")]
    optimizer = MenuOptimizer()
    search_options = {
        "recipe_count": 2,
        "max_stores": 2,
        "beam_width": 3,
        "search_reuse_enabled": True,
        "admissible_lower_bound_enabled": True,
    }

    before = optimizer.optimize(recipes, original, stores, **search_options)
    after = optimizer.optimize(recipes, expanded, stores, **search_options)

    old_solution_in_expanded_universe = BasketOptimizer().optimize(
        optimizer.normalizer.normalize_and_aggregate(before.recipes),
        expanded,
        stores,
        max_stores=2,
    )
    assert before.basket.store_count == 2
    assert old_solution_in_expanded_universe.total <= before.basket.total
    assert after.basket.total <= before.basket.total
