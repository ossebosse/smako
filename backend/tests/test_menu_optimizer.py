from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from app.models.product import ProductCandidate, QuantityConfidence, SemanticConfidence
from app.models.provenance import SourceProvenance
from app.models.recipe import Recipe, RecipeIngredient
from app.models.store import Store
from app.services.basket_calculator import BasketCalculator
from app.services.basket_optimizer import BasketOptimizer
from app.services.menu_optimizer import DiversityConstraints, MenuOptimizer


def store(store_id: str) -> Store:
    return Store(
        store_id=store_id,
        name=f"Butik {store_id.upper()}",
        chain="Testkedjan",
        city="Lund",
        postal_code="22350",
    )


def product(
    ingredient: str,
    store_id: str,
    price: float,
    *,
    package_quantity: float = 1000,
    unit: str = "g",
) -> ProductCandidate:
    return ProductCandidate(
        product_id=f"{store_id}-{ingredient}-{price}",
        product_name=f"{ingredient} {package_quantity} {unit}",
        canonical_name=ingredient,
        store_id=store_id,
        store_name=f"Butik {store_id.upper()}",
        package_quantity=package_quantity,
        package_unit=unit,
        price=price,
        effective_price=price,
        match_score=1,
    )


def recipe(
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
                unit=unit,
            )
            for ingredient, quantity, unit in ingredients
        ],
        instructions=["Tillaga."],
    )


def test_recipes_share_one_two_kilo_potato_package() -> None:
    recipes = [
        recipe("Potatisrätt A", [("potatis", 600, "g")]),
        recipe("Potatisrätt B", [("potatis", 700, "g")]),
    ]
    candidates = {
        "potatis": [
            product("potatis", "a", 19.90, package_quantity=2000),
        ]
    }

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=4,
    )

    assert result.basket.total == 19.90
    assert len(result.ingredients) == 1
    assert result.ingredients[0].required_quantity == 1300
    item = result.basket.stores[0].items[0]
    assert item.packages_needed == 1
    assert item.purchased_quantity == 2000
    assert item.waste_quantity == 700
    assert [row.marginal_cost for row in result.marginal_costs] == [19.90, 0.0]


def test_individually_cheapest_recipes_are_not_the_globally_cheapest_menu() -> None:
    # A and B each cost 10. C and D each cost 15 in isolation, but together
    # share one 2 kg package and therefore cost only 15 for the complete menu.
    recipes = [
        recipe("A", [("råvara a", 100, "g")]),
        recipe("B", [("råvara b", 100, "g")]),
        recipe("C", [("delad råvara", 600, "g")]),
        recipe("D", [("delad råvara", 700, "g")]),
    ]
    candidates = {
        "råvara a": [product("råvara a", "a", 10, package_quantity=100)],
        "råvara b": [product("råvara b", "a", 10, package_quantity=100)],
        "delad råvara": [
            product("delad råvara", "a", 15, package_quantity=2000),
        ],
    }

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=4,
    )

    assert {row.name for row in result.recipes} == {"C", "D"}
    assert result.basket.total == 15


def test_max_stores_is_applied_during_every_menu_evaluation() -> None:
    recipes = [
        recipe("Pastarätt", [("pasta", 500, "g")]),
        recipe("Bönrätt", [("bönor", 500, "g")]),
    ]
    candidates = {
        "pasta": [
            product("pasta", "a", 10, package_quantity=500),
            product("pasta", "b", 50, package_quantity=500),
        ],
        "bönor": [
            product("bönor", "a", 50, package_quantity=500),
            product("bönor", "b", 10, package_quantity=500),
        ],
    }
    stores = [store("a"), store("b")]
    optimizer = MenuOptimizer()

    one_store = optimizer.optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=1,
        beam_width=4,
    )
    two_stores = optimizer.optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=2,
        beam_width=4,
    )

    assert one_store.basket.store_count == 1
    assert one_store.basket.total == 60
    assert two_stores.basket.store_count == 2
    assert two_stores.basket.total == 20
    assert two_stores.basket.total < one_store.basket.total


def test_combined_cap_frontier_matches_prior_isolated_cap_searches() -> None:
    """Shared depth expansion preserves each cap's historical beam result."""

    recipes = [
        recipe("Pastarätt", [("pasta", 500, "g")]),
        recipe("Bönrätt", [("bönor", 500, "g")]),
    ]
    candidates = {
        "pasta": [
            product("pasta", "a", 10, package_quantity=500),
            product("pasta", "b", 50, package_quantity=500),
        ],
        "bönor": [
            product("bönor", "a", 50, package_quantity=500),
            product("bönor", "b", 10, package_quantity=500),
        ],
    }
    stores = [store("a"), store("b")]
    optimizer = MenuOptimizer()

    isolated_one = optimizer._optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=1,
        beam_width=4,
    )
    isolated_two = optimizer._optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=2,
        beam_width=4,
    )
    public_one = optimizer.optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=1,
        beam_width=4,
    )
    combined_two = optimizer.optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=2,
        beam_width=4,
    )

    assert [row.name for row in public_one.recipes] == [
        row.name for row in isolated_one.recipes
    ]
    assert public_one.basket.model_dump() == isolated_one.basket.model_dump()
    assert [row.name for row in combined_two.recipes] == [
        row.name for row in isolated_two.recipes
    ]
    assert combined_two.basket.model_dump() == isolated_two.basket.model_dump()


def test_standalone_max_three_keeps_the_nested_lower_cap_menu_incumbent() -> None:
    """A relaxed store cap must retain a better lower-cap beam result.

    With a width-one beam, the three-store search ranks recipe A first because
    its three ingredients can be split across three stores for 3 kr.  That
    branch ultimately costs 13 kr.  Under one/two stores A is infeasible and
    B+C share one package for 10 kr.  A cold max-three call must carry that
    complete lower-cap menu forward and reprice the real basket at cap three.
    """

    recipes = [
        recipe("A", [("x", 1, "st"), ("y", 1, "st"), ("z", 1, "st")]),
        recipe("B", [("q", 0.9, "st")]),
        recipe("C", [("q", 1.1, "st")]),
    ]
    candidates = {
        "x": [product("x", "a", 1, package_quantity=1, unit="st")],
        "y": [product("y", "b", 1, package_quantity=1, unit="st")],
        "z": [product("z", "c", 1, package_quantity=1, unit="st")],
        "q": [product("q", "a", 10, package_quantity=2, unit="st")],
    }
    provenance = SourceProvenance(
        source_provider="fixture",
        source_channel="catalog",
        source_snapshot_id="snapshot:nested-cap",
        source_observed_at=datetime(2026, 8, 31, 8, tzinfo=UTC),
        store_id="a",
    )
    candidates["q"][0] = candidates["q"][0].model_copy(
        update={"source_provenance": provenance}
    )
    stores = [store("a"), store("b"), store("c")]

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=3,
        beam_width=1,
    )

    assert {row.name for row in result.recipes} == {"B", "C"}
    assert result.basket.total == 10
    assert result.basket.max_stores == 3
    assert result.basket.store_count == 1
    assert result.basket.stores[0].items[0].product_id == "a-q-10"
    assert result.basket.stores[0].items[0].source_provenance == provenance


def test_nested_incumbent_is_repriced_with_new_products_and_provenance() -> None:
    """A carried menu receives a fresh higher-cap basket, audit and lineage."""

    observed_at = datetime(2026, 8, 31, 8, tzinfo=UTC)

    def priced(
        ingredient: str,
        store_id: str,
        price: float,
        snapshot_id: str,
    ) -> ProductCandidate:
        candidate = product(
            ingredient,
            store_id,
            price,
            package_quantity=1,
            unit="st",
        )
        return candidate.model_copy(
            update={
                "semantic_confidence": SemanticConfidence.HIGH,
                "quantity_confidence": QuantityConfidence.EXACT,
                "source_provenance": SourceProvenance(
                    source_provider="fixture",
                    source_channel="catalog",
                    source_snapshot_id=snapshot_id,
                    source_observed_at=observed_at,
                    store_id=store_id,
                ),
            }
        )

    recipes = [
        recipe("A", [("x", 1, "st"), ("y", 1, "st"), ("z", 1, "st")]),
        recipe("B", [("q", 0.4, "st"), ("r", 0.4, "st")]),
        recipe("C", [("q", 0.6, "st"), ("r", 0.6, "st")]),
    ]
    candidates = {
        "x": [priced("x", "b", 1, "snapshot:x")],
        "y": [priced("y", "c", 1, "snapshot:y")],
        "z": [priced("z", "d", 1, "snapshot:z")],
        "q": [
            priced("q", "a", 6, "snapshot:q-one-store"),
            priced("q", "b", 2, "snapshot:q-split"),
        ],
        "r": [
            priced("r", "a", 6, "snapshot:r-one-store"),
            priced("r", "c", 2, "snapshot:r-split"),
        ],
    }
    stores = [store(store_id) for store_id in ("a", "b", "c", "d")]
    constraints = DiversityConstraints(
        max_same_recipe_family=None,
        max_same_primary_ingredient_meals=None,
        max_same_carbohydrate_meals=None,
        max_pairwise_recipe_similarity=None,
    )
    optimizer = MenuOptimizer()

    lower_cap = optimizer.optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=1,
        beam_width=1,
        diversity_constraints=constraints,
    )
    isolated_higher_cap = optimizer._optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=3,
        beam_width=1,
        diversity_constraints=constraints,
    )
    higher_cap = optimizer.optimize(
        recipes,
        candidates,
        stores,
        recipe_count=2,
        max_stores=3,
        beam_width=1,
        diversity_constraints=constraints,
    )

    assert {row.name for row in lower_cap.recipes} == {"B", "C"}
    assert lower_cap.basket.total == 12
    assert lower_cap.basket.store_count == 1
    assert {
        item.source_provenance.source_snapshot_id
        for group in lower_cap.basket.stores
        for item in group.items
        if item.source_provenance is not None
    } == {"snapshot:q-one-store", "snapshot:r-one-store"}

    # The isolated width-one high-cap beam loses B+C; nested search carries
    # that lower-cap winner and then authoritatively reprices it.
    assert "A" in {row.name for row in isolated_higher_cap.recipes}
    assert isolated_higher_cap.basket.total == 7
    assert {row.name for row in higher_cap.recipes} == {"B", "C"}
    assert higher_cap.basket.max_stores == 3
    assert higher_cap.basket.store_count == 2
    assert higher_cap.basket.total == 4
    assert [(group.store_id, group.subtotal) for group in higher_cap.basket.stores] == [
        ("b", 2),
        ("c", 2),
    ]
    assert {
        item.product_id
        for group in higher_cap.basket.stores
        for item in group.items
    } == {"b-q-2", "c-r-2"}
    assert {
        item.source_provenance.source_snapshot_id
        for group in higher_cap.basket.stores
        for item in group.items
        if item.source_provenance is not None
    } == {"snapshot:q-split", "snapshot:r-split"}
    assert higher_cap.basket.total_reconciled
    assert all(group.subtotal_reconciled for group in higher_cap.basket.stores)
    assert higher_cap.basket_audit.passed
    assert higher_cap.basket_audit.totals_reconciled
    assert higher_cap.basket_audit.calculated_total == higher_cap.basket.total
    assert higher_cap.basket_audit.reported_total == higher_cap.basket.total
    assert {
        product.product_id
        for item in higher_cap.basket_audit.items
        for product in item.selected_products
    } == {"b-q-2", "c-r-2"}


def test_store_cap_relaxation_is_monotone_for_every_menu_policy() -> None:
    recipes = [
        recipe("A", [("x", 1, "st"), ("y", 1, "st"), ("z", 1, "st")]),
        recipe("B", [("q", 0.9, "st")]),
        recipe("C", [("q", 1.1, "st")]),
    ]
    candidates = {
        "x": [product("x", "a", 1, package_quantity=1, unit="st")],
        "y": [product("y", "b", 1, package_quantity=1, unit="st")],
        "z": [product("z", "c", 1, package_quantity=1, unit="st")],
        "q": [product("q", "a", 10, package_quantity=2, unit="st")],
    }
    stores = [store("a"), store("b"), store("c")]
    variants = {
        "cheapest": DiversityConstraints(
            max_same_recipe_family=None,
            max_same_primary_ingredient_meals=None,
            max_same_carbohydrate_meals=None,
            max_pairwise_recipe_similarity=None,
        ),
        "balanced": DiversityConstraints(),
        "varied": DiversityConstraints(
            max_same_recipe_family=1,
            max_same_primary_ingredient_meals=1,
            max_same_carbohydrate_meals=1,
            max_pairwise_recipe_similarity=0.45,
        ),
    }
    optimizer = MenuOptimizer()

    by_cap = {
        cap: optimizer.optimize_variants(
            recipes,
            candidates,
            stores,
            variants,
            recipe_count=2,
            max_stores=cap,
            beam_width=1,
        )
        for cap in (1, 2, 3)
    }

    for mode in variants:
        totals = [by_cap[cap].results[mode].basket.total for cap in (1, 2, 3)]
        assert totals[1] <= totals[0]
        assert totals[2] <= totals[1]
        for cap in (1, 2, 3):
            basket = by_cap[cap].results[mode].basket
            assert basket.max_stores == cap
            assert basket.store_count <= cap


def test_recipe_family_diversity_is_enforced_inside_search() -> None:
    recipes = [
        recipe("Pasta ett", [("pasta ett", 100, "g")]),
        recipe("Pasta två", [("pasta två", 110, "g")]),
        recipe("Pasta tre", [("pasta tre", 120, "g")]),
        recipe("Risrätt", [("risråvara", 100, "g")]),
        recipe("Potatisrätt", [("potatisråvara", 100, "g")]),
    ]
    candidates = {
        ingredient: [product(ingredient, "a", price, package_quantity=100)]
        for ingredient, price in (
            ("pasta", 1),
            ("risråvara", 10),
            ("potatisråvara", 10),
        )
    }
    constraints = DiversityConstraints(
        max_same_recipe_family=1,
        max_same_primary_ingredient_meals=None,
        recipe_families={
            "Pasta ett": "pasta",
            "Pasta två": "pasta",
            "Pasta tre": "pasta",
            "Risrätt": "ris",
            "Potatisrätt": "potatis",
        },
    )

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=3,
        max_stores=1,
        beam_width=10,
        diversity_constraints=constraints,
    )

    chosen_families = [constraints.recipe_families[row.name] for row in result.recipes]
    assert chosen_families.count("pasta") == 1
    assert set(chosen_families) == {"pasta", "ris", "potatis"}
    assert result.stats.diversity_rejections > 0


def test_carbohydrate_diversity_is_enforced_inside_search() -> None:
    recipes = [
        recipe("Tortilla ett", [("delad", 1, "st")]),
        recipe("Tortilla två", [("delad", 2, "st")]),
        recipe("Tortilla tre", [("delad", 3, "st")]),
        recipe("Risrätt", [("risråvara", 1, "st")]),
    ]
    candidates = {
        "delad": [product("delad", "a", 1, package_quantity=10, unit="st")],
        "risråvara": [
            product("risråvara", "a", 5, package_quantity=1, unit="st")
        ],
    }
    constraints = DiversityConstraints(
        max_same_recipe_family=None,
        max_same_primary_ingredient_meals=None,
        max_same_carbohydrate_meals=2,
        carbohydrates={
            "Tortilla ett": "tortillas",
            "Tortilla två": "tortillas",
            "Tortilla tre": "tortillas",
            "Risrätt": "ris",
        },
    )

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=3,
        max_stores=1,
        beam_width=10,
        diversity_constraints=constraints,
    )

    chosen_carbs = [constraints.carbohydrates[row.name] for row in result.recipes]
    assert chosen_carbs.count("tortillas") == 2
    assert "ris" in chosen_carbs
    assert result.stats.diversity_rejections > 0


def test_pairwise_similarity_is_enforced_inside_search() -> None:
    recipes = [
        recipe("Lik A", [("a", 1, "st")]),
        recipe("Lik B", [("b", 1, "st")]),
        recipe("Annan", [("c", 1, "st")]),
    ]
    candidates = {
        ingredient: [product(ingredient, "a", 1, package_quantity=1, unit="st")]
        for ingredient in ("a", "b", "c")
    }
    constraints = DiversityConstraints(
        max_same_recipe_family=None,
        max_same_primary_ingredient_meals=None,
        max_same_carbohydrate_meals=None,
        max_pairwise_recipe_similarity=0.70,
        pairwise_recipe_similarities={
            ("lik a", "lik b"): 0.91,
            ("annan", "lik a"): 0.10,
            ("annan", "lik b"): 0.12,
        },
    )

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
        diversity_constraints=constraints,
    )

    assert {row.name for row in result.recipes} != {"Lik A", "Lik B"}
    assert "Annan" in {row.name for row in result.recipes}
    assert result.stats.diversity_rejections > 0


def test_cooking_method_and_dish_form_are_enforced_inside_search() -> None:
    recipes = [
        recipe("Panna A", [("a", 1, "st")]),
        recipe("Panna B", [("b", 1, "st")]),
        recipe("Gryta C", [("c", 1, "st")]),
    ]
    candidates = {
        ingredient: [product(ingredient, "a", price, package_quantity=1, unit="st")]
        for ingredient, price in (("a", 1), ("b", 1), ("c", 5))
    }
    constraints = DiversityConstraints(
        max_same_recipe_family=None,
        max_same_primary_ingredient_meals=None,
        max_same_carbohydrate_meals=None,
        max_pairwise_recipe_similarity=None,
        max_same_cooking_method=1,
        max_same_dish_form=1,
        cooking_methods={"Panna A": "pan", "Panna B": "pan", "Gryta C": "simmer"},
        dish_forms={
            "Panna A": "one_pan_hash",
            "Panna B": "one_pan_hash",
            "Gryta C": "stew",
        },
    )

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
        diversity_constraints=constraints,
    )

    assert "Gryta C" in {row.name for row in result.recipes}
    assert result.stats.diversity_rejections > 0


def test_optimize_variants_keeps_cheapest_unrestricted_but_varied_costs_more() -> None:
    recipes = [
        recipe("Lik A", [("a", 1, "st")]),
        recipe("Lik B", [("b", 1, "st")]),
        recipe("Annan C", [("c", 1, "st")]),
    ]
    candidates = {
        ingredient: [product(ingredient, "a", price, package_quantity=1, unit="st")]
        for ingredient, price in (("a", 1), ("b", 1), ("c", 10))
    }
    common = {
        "recipe_families": {"Lik A": "pan", "Lik B": "pan", "Annan C": "stew"},
        "dish_forms": {
            "Lik A": "one_pan_hash",
            "Lik B": "one_pan_hash",
            "Annan C": "stew",
        },
    }

    result = MenuOptimizer().optimize_variants(
        recipes,
        candidates,
        [store("a")],
        {
            "cheapest": DiversityConstraints(
                max_same_recipe_family=None,
                max_same_primary_ingredient_meals=None,
                max_same_carbohydrate_meals=None,
                max_pairwise_recipe_similarity=None,
                **common,
            ),
            "varied": DiversityConstraints(
                max_same_recipe_family=1,
                max_same_primary_ingredient_meals=None,
                max_same_carbohydrate_meals=None,
                max_pairwise_recipe_similarity=None,
                max_same_dish_form=1,
                **common,
            ),
        },
        recipe_count=2,
        max_stores=1,
        beam_width=3,
    )

    assert result.errors == {}
    assert {row.name for row in result.results["cheapest"].recipes} == {
        "Lik A",
        "Lik B",
    }
    assert result.results["cheapest"].basket.total == 2
    assert "Annan C" in {row.name for row in result.results["varied"].recipes}
    assert result.results["varied"].basket.total == 11


def test_beam_search_finds_known_package_sharing_optimum() -> None:
    recipes = [
        recipe("Billig separat", [("separat", 1, "st")]),
        recipe("Delning 1", [("delning", 4, "st")]),
        recipe("Delning 2", [("delning", 5, "st")]),
    ]
    candidates = {
        "separat": [product("separat", "a", 8, package_quantity=1, unit="st")],
        "delning": [product("delning", "a", 10, package_quantity=10, unit="st")],
    }

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
    )

    assert {row.name for row in result.recipes} == {"Delning 1", "Delning 2"}
    assert result.basket.total == 10
    assert result.stats.states_by_depth == (3, 3)


def test_order_independent_basket_cache_avoids_recalculation() -> None:
    recipes = [
        recipe("A", [("a", 1, "st")]),
        recipe("B", [("b", 1, "st")]),
        recipe("C", [("c", 1, "st")]),
    ]
    candidates = {
        ingredient: [product(ingredient, "a", 1, package_quantity=1, unit="st")]
        for ingredient in ("a", "b", "c")
    }

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
    )

    # Three singleton states + the three unordered two-recipe combinations.
    # Singleton scoring is reused by depth one, and winning prefixes are reused
    # again for marginal-cost reporting.
    assert result.stats.cache_misses == 6
    assert result.stats.basket_calculations == 6
    assert result.stats.cache_hits >= 5
    assert result.stats.duplicate_state_rejections >= 3
    assert result.stats.states_evaluated == (
        result.stats.cache_hits + result.stats.cache_misses
    )


def test_identical_ingredient_profiles_are_deduplicated() -> None:
    recipes = [
        recipe("Variant A", [("potatis", 500, "g")]),
        recipe("Variant B", [("potatis", 500, "g")]),
        recipe("Annan", [("ris", 500, "g")]),
    ]
    candidates = {
        "potatis": [product("potatis", "a", 10, package_quantity=1000)],
        "ris": [product("ris", "a", 10, package_quantity=1000)],
    }

    result = MenuOptimizer().optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
    )

    assert result.stats.candidates_received == 3
    assert result.stats.candidates_deduplicated == 1
    assert result.stats.candidate_count == 2


def test_menu_search_reuses_quotes_across_different_basket_states(
    monkeypatch,
) -> None:
    recipes = [
        recipe("A", [("potatis", 500, "g")]),
        recipe("B", [("potatis", 500, "g"), ("bönor", 1, "st")]),
        recipe("C", [("potatis", 500, "g"), ("ärtor", 1, "st")]),
    ]
    candidates = {
        "potatis": [product("potatis", "a", 10, package_quantity=1000)],
        "bönor": [product("bönor", "a", 5, package_quantity=1, unit="st")],
        "ärtor": [product("ärtor", "a", 5, package_quantity=1, unit="st")],
    }
    calculator = BasketCalculator()
    original = calculator.quote_item
    quote_calls = 0

    def counted_quote(ingredient, candidate):
        nonlocal quote_calls
        quote_calls += 1
        return original(ingredient, candidate)

    monkeypatch.setattr(calculator, "quote_item", counted_quote)

    result = MenuOptimizer(
        basket_optimizer=BasketOptimizer(calculator=calculator)
    ).optimize(
        recipes,
        candidates,
        [store("a")],
        recipe_count=2,
        max_stores=1,
        beam_width=3,
    )

    # Six basket states contain twelve ingredient/product evaluations, but
    # only four distinct normalized requirements exist: potatoes at 500/1000g
    # plus one piece each of beans and peas.
    assert quote_calls == 4
    assert result.basket.total == 15
