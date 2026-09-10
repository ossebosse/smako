"""Compare beam-search quality with an exact oracle on one Mock snapshot.

The default matrix evaluates candidate subsets 10/15/20 and beam widths
10/25/50. No environment credentials are read, accepted or printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from decimal import Decimal
from itertools import combinations
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Jämför beam search mot exakt kombinationssökning på en Mock-snapshot."
        )
    )
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--recipes", type=int, default=5)
    parser.add_argument("--servings", type=int, default=4)
    parser.add_argument("--max-stores", type=int, default=2)
    parser.add_argument(
        "--subsets",
        type=int,
        nargs="+",
        default=[10, 15, 20],
        metavar="N",
    )
    parser.add_argument(
        "--beam-widths",
        type=int,
        nargs="+",
        default=[10, 25, 50],
        metavar="N",
    )
    return parser


async def _snapshot(
    *,
    postal_code: str,
    candidate_count: int,
    servings: int,
) -> tuple[list[Any], dict[str, list[Any]], list[Any], dict[str, Any]]:
    from app.providers.mock import MockPriceProvider
    from app.services.economic_ingredient_selector import EconomicIngredientSelector
    from app.services.nutrition_validator import NutritionValidator
    from app.services.recipe_candidate_generator import (
        DeterministicRecipeCandidateGenerator,
    )
    from app.services.recipe_candidate_validator import RecipeCandidateValidator

    provider = MockPriceProvider()
    stores = await provider.find_stores(postal_code)
    pool = await EconomicIngredientSelector().select(provider, stores)
    generated = DeterministicRecipeCandidateGenerator().generate_candidates(
        pool,
        count=candidate_count,
        servings=servings,
    )
    structural_started = perf_counter()
    validation = RecipeCandidateValidator().validate_and_prune(
        generated,
        pool.candidates_by_name,
        servings=servings,
    )
    structural_seconds = perf_counter() - structural_started
    nutrition_started = perf_counter()
    nutrition_report = NutritionValidator().validate_recipes(
        validation.valid_recipes
    )
    quality_candidates = [
        recipe
        for recipe, result in zip(
            validation.valid_recipes,
            nutrition_report.results,
            strict=True,
        )
        if result.is_valid
    ]
    nutrition_seconds = perf_counter() - nutrition_started
    if len(quality_candidates) < candidate_count:
        raise RuntimeError(
            f"Only {len(quality_candidates)} quality-valid Mock candidates remain; "
            f"{candidate_count} are required"
        )
    metadata = {
        "stores": len(stores),
        "economic_ingredients": len(pool.ingredients),
        "products_considered": pool.products_considered,
        "candidates_generated": len(generated),
        "candidates_structurally_valid": len(validation.valid_recipes),
        "candidates_structurally_rejected": len(validation.rejected),
        "candidates_nutrition_valid": len(quality_candidates),
        "candidates_nutrition_rejected": nutrition_report.rejected_count,
        "quality_timings_seconds": {
            "structural_validation": round(structural_seconds, 6),
            "nutrition_validation": round(nutrition_seconds, 6),
        },
    }
    return (
        quality_candidates,
        pool.candidates_by_name,
        stores,
        metadata,
    )


def _money_gap(beam_total: float, exact_total: float) -> tuple[float, float]:
    gap = Decimal(str(beam_total)) - Decimal(str(exact_total))
    percentage = (
        gap / Decimal(str(exact_total)) * Decimal(100)
        if exact_total
        else Decimal(0)
    )
    return round(float(gap), 2), round(float(percentage), 4)


def _pairwise_similarity_scores(
    recipes: Sequence[Any],
    analyzer: Any,
) -> dict[tuple[str, str], float]:
    """Build the exact map consumed by ``DiversityConstraints``."""

    profiles = [
        (recipe.name.casefold().strip(), analyzer.build_profile(recipe))
        for recipe in recipes
    ]
    return {
        tuple(sorted((left_name, right_name))): analyzer.compare_profiles(
            left_profile,
            right_profile,
        ).score
        for (left_name, left_profile), (right_name, right_profile) in combinations(
            profiles,
            2,
        )
    }


def _run_matrix(args: argparse.Namespace) -> dict[str, Any]:
    from app.services.exact_menu_search import ExactMenuSearch
    from app.services.menu_optimizer import DiversityConstraints
    from app.services.recipe_candidate_validator import (
        carbohydrate_ingredient,
        primary_ingredient,
        recipe_family,
    )
    from app.services.recipe_similarity import RecipeSimilarityAnalyzer
    from scripts.benchmark_verification import (
        strict_live_basket_optimizer,
        strict_live_menu_optimizer,
    )

    subset_sizes = sorted(set(args.subsets))
    beam_widths = sorted(set(args.beam_widths))
    maximum = max(subset_sizes)
    candidates, candidates_by_name, stores, metadata = asyncio.run(
        _snapshot(
            postal_code=args.postal_code,
            candidate_count=maximum,
            servings=args.servings,
        )
    )
    similarity_analyzer = RecipeSimilarityAnalyzer()

    rows: list[dict[str, Any]] = []
    for subset_size in subset_sizes:
        subset = candidates[:subset_size]
        similarity_started = perf_counter()
        similarity_scores = _pairwise_similarity_scores(
            subset,
            similarity_analyzer,
        )
        similarity_seconds = perf_counter() - similarity_started
        constraints = DiversityConstraints(
            max_same_primary_ingredient_meals=2,
            max_same_recipe_family=2,
            max_same_carbohydrate_meals=3,
            family_resolver=recipe_family,
            primary_ingredient_resolver=primary_ingredient,
            carbohydrate_resolver=carbohydrate_ingredient,
            max_pairwise_recipe_similarity=(
                similarity_analyzer.constraints.near_duplicate_threshold
            ),
            pairwise_recipe_similarities=similarity_scores,
        )
        exact_started = perf_counter()
        exact = ExactMenuSearch(
            max_candidates=maximum,
            basket_optimizer=strict_live_basket_optimizer(),
        ).optimize(
            subset,
            candidates_by_name,
            stores,
            recipe_count=args.recipes,
            max_stores=args.max_stores,
            diversity_constraints=constraints,
        )
        exact_wall = perf_counter() - exact_started
        exact_similarity = similarity_analyzer.validate_plan(exact.recipes)
        exact_summary = {
            "total": exact.basket.total,
            "verification_status": exact.basket.verification_status,
            "verification_warnings": exact.basket.verification_warnings,
            "recipes": [recipe.name for recipe in exact.recipes],
            "wall_seconds": round(exact_wall, 6),
            "max_pairwise_similarity": round(
                exact_similarity.maximum_similarity,
                6,
            ),
            "stats": asdict(exact.stats),
        }

        beam_rows: list[dict[str, Any]] = []
        for width in beam_widths:
            beam_started = perf_counter()
            beam = strict_live_menu_optimizer().optimize(
                subset,
                candidates_by_name,
                stores,
                recipe_count=args.recipes,
                max_stores=args.max_stores,
                beam_width=width,
                diversity_constraints=constraints,
                candidate_limit=None,
            )
            beam_wall = perf_counter() - beam_started
            beam_similarity = similarity_analyzer.validate_plan(beam.recipes)
            gap, gap_percent = _money_gap(
                beam.basket.total,
                exact.basket.total,
            )
            beam_rows.append(
                {
                    "beam_width": width,
                    "total": beam.basket.total,
                    "verification_status": beam.basket.verification_status,
                    "verification_warnings": beam.basket.verification_warnings,
                    "recipes": [recipe.name for recipe in beam.recipes],
                    "wall_seconds": round(beam_wall, 6),
                    "gap_sek": gap,
                    "gap_percent": gap_percent,
                    "matches_exact_total": gap == 0,
                    "max_pairwise_similarity": round(
                        beam_similarity.maximum_similarity,
                        6,
                    ),
                    "stats": asdict(beam.stats),
                }
            )
        rows.append(
            {
                "candidate_subset": subset_size,
                "quality": {
                    "nutrition_valid_candidates": len(subset),
                    "similarity_threshold": (
                        similarity_analyzer.constraints.near_duplicate_threshold
                    ),
                    "pairwise_similarity_scores": len(similarity_scores),
                    "similarity_build_seconds": round(similarity_seconds, 6),
                },
                "exact": exact_summary,
                "beams": beam_rows,
            }
        )

    return {
        "provider": "mock",
        "postal_code": "".join(
            character for character in args.postal_code if character.isdigit()
        ),
        "recipes": args.recipes,
        "servings": args.servings,
        "max_stores": args.max_stores,
        "candidate_subsets": subset_sizes,
        "beam_widths": beam_widths,
        "snapshot": metadata,
        "results": rows,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = _parser()
    args = parser.parse_args(argv)
    if args.recipes < 1:
        parser.error("--recipes must be at least one")
    if args.servings < 1:
        parser.error("--servings must be at least one")
    if args.max_stores < 1:
        parser.error("--max-stores must be at least one")
    if not args.subsets or min(args.subsets) < args.recipes:
        parser.error("every --subsets value must be at least --recipes")
    if max(args.subsets) > 20:
        parser.error("--subsets is capped at 20 for exact-search safety")
    if not args.beam_widths or min(args.beam_widths) < 1:
        parser.error("every --beam-widths value must be at least one")

    try:
        result = _run_matrix(args)
    except Exception as exc:  # noqa: BLE001 - emit no operational details
        print(
            json.dumps(
                {
                    "provider": "mock",
                    "error": f"Benchmark failed ({type(exc).__name__})",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
