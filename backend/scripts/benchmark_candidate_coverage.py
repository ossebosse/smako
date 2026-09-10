"""Measure menu-search coverage as the candidate prefix grows.

One provider, store list, economic ingredient pool and generated candidate list
are shared by every scenario. Primat mode never falls back to Mock and records
only endpoint paths, never headers, parameters or credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
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
            "Mät pris och sökkostnad för växande kandidatprefix på en snapshot."
        )
    )
    parser.add_argument("--provider", choices=("mock", "primat"), default="mock")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--recipes", type=int, default=5)
    parser.add_argument("--servings", type=int, default=4)
    parser.add_argument("--max-stores", type=int, default=2)
    parser.add_argument("--beam-width", type=int, default=30)
    parser.add_argument(
        "--counts",
        type=int,
        nargs="+",
        default=[40, 80, 120, 200],
        metavar="N",
    )
    return parser


def candidate_invariant(_recipe: Any) -> bool:
    """Extension hook for safeguards beyond the default nutrition validator."""

    return True


def build_diversity_constraints(
    pairwise_recipe_similarities: dict[tuple[str, str], float],
    similarity_threshold: float,
) -> Any:
    """Extension hook matching the production structural menu safeguards."""

    from app.services.menu_optimizer import DiversityConstraints
    from app.services.recipe_candidate_validator import (
        carbohydrate_ingredient,
        primary_ingredient,
        recipe_family,
    )

    return DiversityConstraints(
        max_same_primary_ingredient_meals=2,
        max_same_recipe_family=2,
        max_same_carbohydrate_meals=3,
        family_resolver=recipe_family,
        primary_ingredient_resolver=primary_ingredient,
        carbohydrate_resolver=carbohydrate_ingredient,
        max_pairwise_recipe_similarity=similarity_threshold,
        pairwise_recipe_similarities=pairwise_recipe_similarities,
    )


def _apply_candidate_invariant(
    recipes: Sequence[Any],
    predicate: Callable[[Any], bool] = candidate_invariant,
) -> list[Any]:
    return [recipe for recipe in recipes if predicate(recipe)]


def _pairwise_similarity_scores(
    recipes: Sequence[Any],
    analyzer: Any,
) -> dict[tuple[str, str], float]:
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


def _price_improvement(previous: float | None, current: float) -> float | None:
    if previous is None:
        return None
    return round(float(Decimal(str(previous)) - Decimal(str(current))), 2)


async def _build_provider(
    provider_name: str,
) -> tuple[Any, Counter[str]]:
    endpoint_counts: Counter[str] = Counter()
    if provider_name == "mock":
        from app.providers.mock import MockPriceProvider

        return MockPriceProvider(use_member_prices=False), endpoint_counts

    from app.config import Settings
    from app.providers.primat import PrimatPriceProvider

    settings = Settings.from_env()
    if not settings.primat_api_key:
        raise ValueError("Primat mode requires PRIMAT_API_KEY")

    class CountingPrimatPriceProvider(PrimatPriceProvider):
        async def _request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            # Endpoint path only: parameters, headers and credentials are
            # deliberately never retained by the benchmark.
            endpoint_counts[path] += 1
            return await super()._request(
                method,
                path,
                params=params,
                json=json,
            )

    return (
        CountingPrimatPriceProvider(
            api_key=settings.primat_api_key,
            base_url=settings.primat_base_url,
            use_member_prices=False,
        ),
        endpoint_counts,
    )


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    from app.services.economic_ingredient_selector import EconomicIngredientSelector
    from app.services.nutrition_validator import NutritionValidator
    from app.services.recipe_candidate_generator import (
        DeterministicRecipeCandidateGenerator,
    )
    from app.services.recipe_candidate_validator import RecipeCandidateValidator
    from app.services.recipe_similarity import RecipeSimilarityAnalyzer
    from scripts.benchmark_verification import strict_live_menu_optimizer

    provider, endpoint_counts = await _build_provider(args.provider)
    try:
        snapshot_started = perf_counter()
        stores = await provider.find_stores(args.postal_code)
        pool = await EconomicIngredientSelector().select(provider, stores)
        snapshot_seconds = perf_counter() - snapshot_started
        if not pool.ingredients or not pool.candidates_by_name:
            raise RuntimeError("The economic ingredient pool is empty")

        maximum_count = max(args.counts)
        generation_started = perf_counter()
        generated = await asyncio.to_thread(
            DeterministicRecipeCandidateGenerator().generate_candidates,
            pool,
            maximum_count,
            args.servings,
        )
        generation_seconds = perf_counter() - generation_started
        validator = RecipeCandidateValidator()
        nutrition_validator = NutritionValidator()
        similarity_analyzer = RecipeSimilarityAnalyzer()
        optimizer = strict_live_menu_optimizer()

        scenarios: list[dict[str, Any]] = []
        first_total: float | None = None
        previous_total: float | None = None
        for requested_count in sorted(set(args.counts)):
            scenario_started = perf_counter()
            prefix = generated[:requested_count]
            structural_started = perf_counter()
            validation = await asyncio.to_thread(
                validator.validate_and_prune,
                prefix,
                pool.candidates_by_name,
                servings=args.servings,
            )
            structural_seconds = perf_counter() - structural_started

            nutrition_started = perf_counter()
            nutrition_report = await asyncio.to_thread(
                nutrition_validator.validate_recipes,
                validation.valid_recipes,
            )
            nutrition_valid = [
                recipe
                for recipe, quality in zip(
                    validation.valid_recipes,
                    nutrition_report.results,
                    strict=True,
                )
                if quality.is_valid
            ]
            nutrition_seconds = perf_counter() - nutrition_started
            allowed = _apply_candidate_invariant(nutrition_valid)
            if len(allowed) < args.recipes:
                raise RuntimeError(
                    f"Only {len(allowed)} candidates remain for prefix "
                    f"{requested_count}"
                )

            similarity_started = perf_counter()
            similarity_scores = await asyncio.to_thread(
                _pairwise_similarity_scores,
                allowed,
                similarity_analyzer,
            )
            similarity_seconds = perf_counter() - similarity_started
            constraints = build_diversity_constraints(
                similarity_scores,
                similarity_analyzer.constraints.near_duplicate_threshold,
            )
            search_started = perf_counter()
            result = await asyncio.to_thread(
                optimizer.optimize,
                allowed,
                pool.candidates_by_name,
                stores,
                recipe_count=args.recipes,
                max_stores=args.max_stores,
                beam_width=args.beam_width,
                diversity_constraints=constraints,
                candidate_limit=None,
            )
            search_seconds = perf_counter() - search_started
            selected_nutrition = nutrition_validator.validate_recipes(result.recipes)
            selected_similarity = similarity_analyzer.validate_plan(result.recipes)
            if first_total is None:
                first_total = result.basket.total
            improvement_previous = _price_improvement(
                previous_total,
                result.basket.total,
            )
            improvement_first = _price_improvement(
                first_total,
                result.basket.total,
            )
            scenarios.append(
                {
                    "candidate_prefix": requested_count,
                    "candidate_generated_prefix": len(prefix),
                    "candidate_valid": len(allowed),
                    "candidate_structurally_valid": len(
                        validation.valid_recipes
                    ),
                    "candidate_nutrition_valid": len(nutrition_valid),
                    "candidate_nutrition_rejected": (
                        nutrition_report.rejected_count
                    ),
                    "candidate_invariant_valid": len(allowed),
                    "candidate_rejected": len(validation.rejected),
                    "candidate_analyzed": result.stats.candidate_count,
                    "total": result.basket.total,
                    "verification_status": result.basket.verification_status,
                    "verification_warnings": result.basket.verification_warnings,
                    "price_improvement_vs_previous": improvement_previous,
                    "price_improvement_vs_first": improvement_first,
                    "store_count": result.basket.store_count,
                    "recipes": [recipe.name for recipe in result.recipes],
                    "runtime_seconds": round(
                        perf_counter() - scenario_started,
                        6,
                    ),
                    "search_seconds": round(search_seconds, 6),
                    "quality": {
                        "status": (
                            "PASS"
                            if selected_nutrition.is_valid
                            and selected_similarity.is_valid
                            else "FAIL"
                        ),
                        "nutrition_valid_candidates": len(nutrition_valid),
                        "nutrition_rejected_candidates": (
                            nutrition_report.rejected_count
                        ),
                        "pairwise_similarity_scores": len(similarity_scores),
                        "similarity_threshold": (
                            similarity_analyzer.constraints.near_duplicate_threshold
                        ),
                        "selected_max_pairwise_similarity": round(
                            selected_similarity.maximum_similarity,
                            6,
                        ),
                        "timings_seconds": {
                            "structural_validation": round(
                                structural_seconds,
                                6,
                            ),
                            "nutrition_validation": round(
                                nutrition_seconds,
                                6,
                            ),
                            "similarity_map": round(
                                similarity_seconds,
                                6,
                            ),
                        },
                    },
                    "states_evaluated": result.stats.states_evaluated,
                    "basket_calculations": result.stats.basket_calculations,
                    "search_stats": asdict(result.stats),
                }
            )
            previous_total = result.basket.total

        return {
            "provider": args.provider,
            "postal_code": "".join(
                character
                for character in args.postal_code
                if character.isdigit()
            ),
            "recipes": args.recipes,
            "servings": args.servings,
            "max_stores": args.max_stores,
            "beam_width": args.beam_width,
            "counts": sorted(set(args.counts)),
            "snapshot": {
                "stores": len(stores),
                "economic_ingredients": len(pool.ingredients),
                "products_considered": pool.products_considered,
                "product_queries": pool.search_queries_executed,
                "snapshot_seconds": round(snapshot_seconds, 6),
                "generated_once": len(generated),
                "generation_seconds": round(generation_seconds, 6),
            },
            "endpoint_counts": dict(sorted(endpoint_counts.items())),
            "scenarios": scenarios,
        }
    finally:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()


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
    if args.beam_width < 1:
        parser.error("--beam-width must be at least one")
    if not args.counts or min(args.counts) < args.recipes:
        parser.error("every --counts value must be at least --recipes")
    if max(args.counts) > 250:
        parser.error("--counts is capped at the generator safety limit of 250")

    try:
        output = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - never emit operational details
        print(
            json.dumps(
                {
                    "provider": args.provider,
                    "error": f"Coverage benchmark failed ({type(exc).__name__})",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
