from __future__ import annotations

import argparse
import asyncio
from itertools import combinations
from types import SimpleNamespace

from app.models.diversity import DiversityMode
from app.models.recipe import Recipe, RecipeIngredient
from app.services.culinary_similarity import CulinarySimilarity
from app.services.diversity_policy import create_diversity_policy
from app.services.menu_optimizer import MenuSearchStats
from scripts.benchmark_diversity_modes import (
    _parser,
    _recipe_key,
    _run,
    build_mode_constraints,
    summarize_variant,
)


def _recipe(name: str, primary: str, carbohydrate: str, vegetable: str) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=primary,
                canonical_name=primary,
                quantity=600,
                unit="g",
            ),
            RecipeIngredient(
                name=carbohydrate,
                canonical_name=carbohydrate,
                quantity=400,
                unit="g",
            ),
            RecipeIngredient(
                name=vegetable,
                canonical_name=vegetable,
                quantity=500,
                unit="g",
            ),
        ],
        instructions=["Tillaga allt."],
    )


def test_diversity_benchmark_defaults_and_coverage_counts() -> None:
    defaults = _parser().parse_args([])
    coverage = _parser().parse_args(["--counts", "120", "160", "200", "300"])

    assert defaults.provider == "mock"
    assert defaults.postal_code == "22350"
    assert (defaults.recipes, defaults.servings, defaults.max_stores) == (5, 4, 2)
    assert defaults.counts == [160]
    assert defaults.beam_width == 30
    assert coverage.counts == [120, 160, 200, 300]


def test_mode_constraints_reuse_one_complete_culinary_profile_map() -> None:
    recipes = [
        _recipe("Kycklingpasta", "kyckling", "pasta", "morot"),
        _recipe("Linsgryta", "linser", "ris", "vitkål"),
        _recipe("Fisk i ugn", "fisk", "potatis", "broccoli"),
    ]
    analyzer = CulinarySimilarity()
    profiles = {_recipe_key(recipe): analyzer.build_profile(recipe) for recipe in recipes}
    policies = {mode: create_diversity_policy(mode) for mode in DiversityMode}

    constraints = build_mode_constraints(
        recipes,
        profiles,
        policies,
        analyzer,
    )

    assert set(constraints) == {mode.value for mode in DiversityMode}
    expected_pairs = {
        tuple(sorted((_recipe_key(left), _recipe_key(right))))
        for left, right in combinations(recipes, 2)
    }
    for mode_constraints in constraints.values():
        assert set(mode_constraints.pairwise_recipe_similarities) == expected_pairs
        assert set(mode_constraints.recipe_families) == {recipe.name for recipe in recipes}
        assert set(mode_constraints.cooking_methods) == {recipe.name for recipe in recipes}
        assert set(mode_constraints.dish_forms) == {recipe.name for recipe in recipes}
    assert constraints["cheapest"].max_same_recipe_family is None
    assert constraints["balanced"].max_same_recipe_family == 2
    assert constraints["varied"].max_same_recipe_family == 2
    assert constraints["varied"].max_pairwise_recipe_similarity == 0.85


def test_variant_summary_rounds_half_cent_up_without_float_division() -> None:
    recipe = _recipe("Linsgryta", "linser", "ris", "vitkål")
    analyzer = CulinarySimilarity()
    profiles = {_recipe_key(recipe): analyzer.build_profile(recipe)}
    stats = MenuSearchStats(
        candidate_count=1,
        candidates_received=1,
        candidates_deduplicated=1,
        candidates_pruned=0,
        beam_width=1,
        states_evaluated=1,
        cache_hits=0,
        cache_misses=1,
        basket_calculations=1,
        cache_hit_rate=0,
        diversity_rejections=0,
        incomplete_rejections=0,
        duplicate_state_rejections=0,
        states_by_depth=(1,),
    )
    result = SimpleNamespace(
        recipes=[recipe],
        basket=SimpleNamespace(total=253.70, stores=[], store_count=0),
        stats=stats,
    )

    summary = summarize_variant(
        result,
        profiles_by_name=profiles,
        analyzer=analyzer,
        portions=20,
        cheapest_total=253.70,
    )

    assert summary["price_per_portion"] == 12.69


def test_mock_diversity_benchmark_uses_one_snapshot_for_all_modes() -> None:
    output = asyncio.run(
        _run(
            argparse.Namespace(
                provider="mock",
                postal_code="22350",
                recipes=5,
                servings=4,
                max_stores=2,
                beam_width=5,
                counts=[30],
            )
        )
    )

    assert output["provider"] == "mock"
    assert output["recipe_version"] == "legacy"
    assert output["snapshot"]["candidates_generated_once"] == 30
    assert output["snapshot"]["candidates_structurally_valid_once"] >= 5
    assert output["snapshot"]["candidates_nutrition_valid_once"] >= 5
    assert sum(output["snapshot"]["candidate_family_batches"].values()) == 30
    assert output["endpoint_counts"] == {}

    scenario = output["scenarios"][0]
    assert scenario["candidate_count"] == 30
    assert scenario["errors"] == {}
    assert set(scenario["modes"]) == {mode.value for mode in DiversityMode}
    assert set(scenario["family_coverage"]["selected"]) == {mode.value for mode in DiversityMode}
    for mode, summary in scenario["modes"].items():
        assert len(summary["recipes"]) == 5
        assert summary["store_count"] <= 2
        assert summary["states_evaluated"] > 0
        assert summary["total"] > 0
        assert summary["price_per_portion"] > 0
        assert 0 <= summary["diversity_score"] <= 1
        assert 0 <= summary["average_pairwise_similarity"] <= 1
        assert 0 <= summary["max_pairwise_similarity"] <= 1
        assert all(
            sum(distribution.values()) == 5 for distribution in summary["distributions"].values()
        )
        if mode == DiversityMode.CHEAPEST.value:
            assert summary["premium_vs_cheapest"] == 0
            assert summary["premium_percent_vs_cheapest"] == 0
