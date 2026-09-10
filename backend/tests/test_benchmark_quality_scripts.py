from __future__ import annotations

from app.models.recipe import Recipe, RecipeIngredient
from app.services.recipe_similarity import RecipeSimilarityAnalyzer
from scripts.benchmark_candidate_coverage import (
    _pairwise_similarity_scores as coverage_similarity_scores,
)
from scripts.benchmark_candidate_coverage import (
    _price_improvement,
    build_diversity_constraints,
)
from scripts.benchmark_plan import _summary
from scripts.benchmark_search_quality import (
    _pairwise_similarity_scores as search_similarity_scores,
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
        instructions=["Tillaga."],
    )


def test_benchmarks_build_the_same_complete_pairwise_similarity_map() -> None:
    recipes = [
        _recipe("Rätt A", "kyckling", "ris", "morot"),
        _recipe("Rätt B", "kyckling", "pasta", "morot"),
        _recipe("Rätt C", "linser", "ris", "vitkål"),
    ]
    analyzer = RecipeSimilarityAnalyzer()

    search_scores = search_similarity_scores(recipes, analyzer)
    coverage_scores = coverage_similarity_scores(recipes, analyzer)

    assert search_scores == coverage_scores
    assert len(search_scores) == 3
    constraints = build_diversity_constraints(
        coverage_scores,
        analyzer.constraints.near_duplicate_threshold,
    )
    assert constraints.pairwise_recipe_similarities == coverage_scores
    assert constraints.max_pairwise_recipe_similarity == 0.70


def test_coverage_price_improvement_is_deterministic_and_signed() -> None:
    assert _price_improvement(None, 100) is None
    assert _price_improvement(100.10, 90.05) == 10.05
    assert _price_improvement(90, 95) == -5.0


def test_plan_benchmark_summary_includes_quality_surplus_and_store_tradeoff() -> None:
    data = {
        "data_source": "mock",
        "strategy": "optimized",
        "optimized_basket": {"total": 100, "stores": []},
        "optimization": {},
        "quality": {
            "status": "PASS",
            "basket_audit": {
                "status": "PASS",
                "ingredients_checked": 8,
                "deficits": [],
                "unknown_quantities": 0,
            },
            "nutrition": {
                "status": "PASS",
                "average_kcal_per_serving": 600,
                "min_kcal_per_serving": 500,
                "average_protein_g_per_serving": 25,
                "min_protein_g_per_serving": 20,
                "average_vegetable_g_per_serving": 150,
            },
            "diversity": {
                "status": "PASS",
                "threshold": 0.7,
                "max_pairwise_similarity": 0.5,
            },
        },
        "surplus": {
            "estimated_surplus_value": 12.5,
            "unit_totals": [],
        },
        "store_tradeoff": {
            "selected_total": 100,
            "selected_store_count": 2,
            "extra_store_savings": 5,
        },
    }

    result = _summary(data, 1.25)

    assert result["quality"]["status"] == "PASS"
    assert result["quality"]["diversity"]["max_pairwise_similarity"] == 0.5
    assert result["surplus"]["estimated_surplus_value"] == 12.5
    assert result["store_tradeoff"]["extra_store_savings"] == 5
