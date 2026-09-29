"""Compare diversity policies on one immutable grocery/candidate snapshot.

The provider, stores, economic pool, deterministic candidate set, structural
validation and nutrition validation are built exactly once.  Each requested
candidate prefix is then passed once to ``MenuOptimizer.optimize_variants`` so
CHEAPEST, BALANCED and VARIED see identical products and recipes.  Primat mode
never falls back to Mock and no credential or request parameter is printed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from decimal import ROUND_HALF_UP, Decimal
from itertools import combinations
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_CENT = Decimal("0.01")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=("Jämför cheapest, balanced och varied på samma pris- och kandidatsnapshot.")
    )
    parser.add_argument("--provider", choices=("mock", "primat"), default="mock")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--recipes", type=int, default=5)
    parser.add_argument("--servings", type=int, default=4)
    parser.add_argument("--max-stores", type=int, default=2)
    parser.add_argument("--beam-width", type=int, default=30)
    parser.add_argument(
        "--counts",
        "--candidate-count",
        dest="counts",
        type=int,
        nargs="+",
        default=[160],
        metavar="N",
        help=("Kandidatprefix att jämföra; exempel: --counts 120 160 200 300 (standard: 160)."),
    )
    return parser


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP))


def _recipe_key(recipe: Any) -> str:
    return recipe.name.casefold().strip()


def _distribution(values: Sequence[str | None]) -> dict[str, int]:
    counts = Counter(value or "unknown" for value in values)
    return dict(sorted(counts.items()))


def _profile_distributions(profiles: Sequence[Any]) -> dict[str, dict[str, int]]:
    return {
        "family": _distribution([profile.recipe_family for profile in profiles]),
        "protein": _distribution([profile.primary_protein for profile in profiles]),
        "carb": _distribution([profile.primary_carb for profile in profiles]),
        "dish": _distribution([profile.dish_form for profile in profiles]),
        "cooking": _distribution([profile.cooking_method for profile in profiles]),
    }


def _family_coverage(profiles: Sequence[Any]) -> dict[str, Any]:
    distribution = _distribution([profile.recipe_family for profile in profiles])
    return {
        "unique": len(distribution),
        "families": list(distribution),
        "distribution": distribution,
    }


def _pairwise_scores(
    recipes: Sequence[Any],
    profiles_by_name: Mapping[str, Any],
    analyzer: Any,
) -> dict[tuple[str, str], float]:
    rows = [(_recipe_key(recipe), profiles_by_name[_recipe_key(recipe)]) for recipe in recipes]
    return {
        tuple(sorted((left_name, right_name))): analyzer.compare_profiles(
            left_profile,
            right_profile,
        ).score
        for (left_name, left_profile), (right_name, right_profile) in combinations(
            rows,
            2,
        )
    }


def build_mode_constraints(
    recipes: Sequence[Any],
    profiles_by_name: Mapping[str, Any],
    policies: Mapping[Any, Any],
    analyzer: Any,
) -> dict[str, Any]:
    """Translate all policies using one shared culinary profile/similarity map."""

    from app.services.menu_optimizer import DiversityConstraints

    pairwise = _pairwise_scores(recipes, profiles_by_name, analyzer)
    profiles_by_display_name = {
        recipe.name: profiles_by_name[_recipe_key(recipe)] for recipe in recipes
    }
    common = {
        "recipe_families": {
            name: profile.recipe_family for name, profile in profiles_by_display_name.items()
        },
        "primary_ingredients": {
            name: profile.primary_protein
            for name, profile in profiles_by_display_name.items()
            if profile.primary_protein
        },
        "carbohydrates": {
            name: profile.primary_carb
            for name, profile in profiles_by_display_name.items()
            if profile.primary_carb
        },
        "cooking_methods": {
            name: profile.cooking_method for name, profile in profiles_by_display_name.items()
        },
        "dish_forms": {
            name: profile.dish_form for name, profile in profiles_by_display_name.items()
        },
        "pairwise_recipe_similarities": pairwise,
    }
    return {
        policy.mode.value: DiversityConstraints(
            max_same_recipe_family=policy.max_same_recipe_family,
            max_same_primary_ingredient_meals=(policy.max_same_primary_ingredient_meals),
            max_same_carbohydrate_meals=policy.max_same_carbohydrate_meals,
            max_same_cooking_method=policy.max_same_cooking_method_meals,
            max_same_dish_form=policy.max_same_dish_form_meals,
            max_pairwise_recipe_similarity=(policy.max_pairwise_culinary_similarity),
            **common,
        )
        for policy in policies.values()
    }


def _similarity_summary(profiles: Sequence[Any], analyzer: Any) -> dict[str, float]:
    scores = [
        analyzer.compare_profiles(left, right).score for left, right in combinations(profiles, 2)
    ]
    average = sum(scores) / len(scores) if scores else 0.0
    return {
        "diversity_score": round(1 - average, 6),
        "average_pairwise_similarity": round(average, 6),
        "max_pairwise_similarity": round(max(scores, default=0.0), 6),
    }


def summarize_variant(
    result: Any,
    *,
    profiles_by_name: Mapping[str, Any],
    analyzer: Any,
    portions: int,
    cheapest_total: float | None,
) -> dict[str, Any]:
    """Build a deterministic, credential-free report for one search result."""

    profiles = [profiles_by_name[_recipe_key(recipe)] for recipe in result.recipes]
    premium = (
        _money(Decimal(str(result.basket.total)) - Decimal(str(cheapest_total)))
        if cheapest_total is not None
        else None
    )
    premium_percent = (
        round(premium / cheapest_total * 100, 4) if premium is not None and cheapest_total else None
    )
    return {
        "total": result.basket.total,
        "verification_status": getattr(
            result.basket,
            "verification_status",
            "UNVERIFIED",
        ),
        "verification_warnings": getattr(
            result.basket,
            "verification_warnings",
            [],
        ),
        "price_per_portion": _money(Decimal(str(result.basket.total)) / Decimal(portions)),
        "premium_vs_cheapest": premium,
        "premium_percent_vs_cheapest": premium_percent,
        **_similarity_summary(profiles, analyzer),
        "recipes": [recipe.name for recipe in result.recipes],
        "stores": [group.store_name for group in result.basket.stores],
        "store_count": result.basket.store_count,
        "distributions": _profile_distributions(profiles),
        "family_coverage": _family_coverage(profiles),
        "states_evaluated": result.stats.states_evaluated,
        "basket_calculations": result.stats.basket_calculations,
        "search_stats": asdict(result.stats),
    }


async def _build_provider(provider_name: str) -> tuple[Any, Counter[str]]:
    endpoint_counts: Counter[str] = Counter()
    if provider_name == "mock":
        from app.providers.mock import MockPriceProvider

        return MockPriceProvider(use_member_prices=False), endpoint_counts

    from app.config import Settings
    from app.providers.primat import PrimatPriceProvider

    settings = Settings.from_env()
    if not settings.primat_api_key:
        raise ValueError("Primat benchmark requires configured credentials")

    class CountingPrimatPriceProvider(PrimatPriceProvider):
        async def _request(
            self,
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            json: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            # Paths are safe aggregate metadata; params, headers and keys are
            # deliberately neither retained nor returned.
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
    from app.models.diversity import DiversityMode
    from app.services.culinary_similarity import CulinarySimilarity
    from app.services.diversity_policy import create_diversity_policy
    from app.services.economic_ingredient_selector import EconomicIngredientSelector
    from app.services.nutrition_validator import NutritionValidator
    from app.services.recipe_candidate_generator import (
        DeterministicRecipeCandidateGenerator,
    )
    from app.services.recipe_candidate_validator import RecipeCandidateValidator
    from scripts.benchmark_verification import strict_live_menu_optimizer

    total_started = perf_counter()
    provider, endpoint_counts = await _build_provider(args.provider)
    try:
        stores_started = perf_counter()
        stores = await provider.find_stores(args.postal_code)
        stores_seconds = perf_counter() - stores_started
        if not stores:
            raise RuntimeError("No stores found")

        pool_started = perf_counter()
        pool = await EconomicIngredientSelector().select(provider, stores)
        pool_seconds = perf_counter() - pool_started
        if not pool.ingredients or not pool.candidates_by_name:
            raise RuntimeError("Economic ingredient pool is empty")

        maximum_count = max(args.counts)
        # This benchmark measures the legacy taxonomy/quantity model below.
        # Edible-input recipes require the product-bound personal planner's
        # preparation checks, not NutritionValidator's generic piece estimates.
        generator = DeterministicRecipeCandidateGenerator(recipe_version="legacy")
        generation_started = perf_counter()
        generated = await asyncio.to_thread(
            generator.generate_candidates,
            pool,
            maximum_count,
            args.servings,
        )
        generation_seconds = perf_counter() - generation_started

        validation_started = perf_counter()
        validation = await asyncio.to_thread(
            RecipeCandidateValidator().validate_and_prune,
            generated,
            pool.candidates_by_name,
            servings=args.servings,
        )
        validation_seconds = perf_counter() - validation_started

        nutrition_started = perf_counter()
        nutrition_report = await asyncio.to_thread(
            NutritionValidator().validate_recipes,
            validation.valid_recipes,
        )
        nutrition_valid = [
            recipe
            for recipe, result in zip(
                validation.valid_recipes,
                nutrition_report.results,
                strict=True,
            )
            if result.is_valid
        ]
        nutrition_seconds = perf_counter() - nutrition_started

        generated_indexes = {_recipe_key(recipe): index for index, recipe in enumerate(generated)}
        if len(generated_indexes) != len(generated):
            raise RuntimeError("Generated recipe names are not unique")

        analyzer = CulinarySimilarity()
        profiles_started = perf_counter()
        profiles_by_name = {
            _recipe_key(recipe): analyzer.build_profile(recipe) for recipe in generated
        }
        profiles_seconds = perf_counter() - profiles_started
        policies = {mode: create_diversity_policy(mode) for mode in DiversityMode}
        optimizer = strict_live_menu_optimizer()

        scenarios: list[dict[str, Any]] = []
        for requested_count in sorted(set(args.counts)):
            scenario_started = perf_counter()
            generated_prefix = generated[:requested_count]
            valid_prefix = [
                recipe
                for recipe in nutrition_valid
                if generated_indexes[_recipe_key(recipe)] < requested_count
            ]
            if len(valid_prefix) < args.recipes:
                raise RuntimeError("Too few quality-valid candidates")

            constraints_started = perf_counter()
            constraints = await asyncio.to_thread(
                build_mode_constraints,
                valid_prefix,
                profiles_by_name,
                policies,
                analyzer,
            )
            constraints_seconds = perf_counter() - constraints_started

            search_started = perf_counter()
            variant_search = await asyncio.to_thread(
                optimizer.optimize_variants,
                valid_prefix,
                pool.candidates_by_name,
                stores,
                constraints,
                recipe_count=args.recipes,
                max_stores=args.max_stores,
                beam_width=args.beam_width,
                candidate_limit=None,
            )
            search_seconds = perf_counter() - search_started
            cheapest = variant_search.results.get(DiversityMode.CHEAPEST.value)
            cheapest_total = cheapest.basket.total if cheapest is not None else None
            portions = args.recipes * args.servings
            modes = {
                mode.value: summarize_variant(
                    result,
                    profiles_by_name=profiles_by_name,
                    analyzer=analyzer,
                    portions=portions,
                    cheapest_total=cheapest_total,
                )
                for mode in DiversityMode
                if (result := variant_search.results.get(mode.value)) is not None
            }
            scenarios.append(
                {
                    "candidate_count": requested_count,
                    "candidates_generated": len(generated_prefix),
                    "candidates_structurally_valid": sum(
                        generated_indexes[_recipe_key(recipe)] < requested_count
                        for recipe in validation.valid_recipes
                    ),
                    "candidates_nutrition_valid": len(valid_prefix),
                    "family_coverage": {
                        "generated": _family_coverage(
                            [profiles_by_name[_recipe_key(recipe)] for recipe in generated_prefix]
                        ),
                        "valid": _family_coverage(
                            [profiles_by_name[_recipe_key(recipe)] for recipe in valid_prefix]
                        ),
                        "selected": {
                            mode: summary["family_coverage"] for mode, summary in modes.items()
                        },
                    },
                    "policies": {
                        mode.value: policy.model_dump(mode="json")
                        for mode, policy in policies.items()
                    },
                    "modes": modes,
                    "errors": {
                        mode: "No feasible menu for this diversity policy"
                        for mode in variant_search.errors
                    },
                    "constraints_seconds": round(constraints_seconds, 6),
                    "variant_search_seconds": round(search_seconds, 6),
                    "runtime_seconds": round(
                        perf_counter() - scenario_started,
                        6,
                    ),
                }
            )

        return {
            "provider": args.provider,
            "recipe_version": "legacy",
            "postal_code": "".join(
                character for character in args.postal_code if character.isdigit()
            ),
            "recipes": args.recipes,
            "servings": args.servings,
            "max_stores": args.max_stores,
            "beam_width": args.beam_width,
            "counts": sorted(set(args.counts)),
            "snapshot": {
                "stores": [store.name for store in stores],
                "economic_ingredients": len(pool.ingredients),
                "products_considered": pool.products_considered,
                "product_queries": pool.search_queries_executed,
                "candidates_generated_once": len(generated),
                "candidates_structurally_valid_once": len(validation.valid_recipes),
                "candidates_nutrition_valid_once": len(nutrition_valid),
                "candidates_nutrition_rejected_once": nutrition_report.rejected_count,
                "candidate_family_batches": generator.batch_statistics,
                "timings_seconds": {
                    "stores": round(stores_seconds, 6),
                    "economic_pool": round(pool_seconds, 6),
                    "candidate_generation": round(generation_seconds, 6),
                    "structural_validation": round(validation_seconds, 6),
                    "nutrition_validation": round(nutrition_seconds, 6),
                    "culinary_profiles": round(profiles_seconds, 6),
                },
            },
            "endpoint_counts": dict(sorted(endpoint_counts.items())),
            "scenarios": scenarios,
            "runtime_seconds": round(perf_counter() - total_started, 6),
        }
    finally:
        close = getattr(provider, "aclose", None)
        if close is not None:
            await close()


def _validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    digits = "".join(character for character in args.postal_code if character.isdigit())
    if len(digits) != 5:
        parser.error("--postal-code must contain exactly five digits")
    if args.recipes < 1:
        parser.error("--recipes must be at least one")
    if args.servings < 1:
        parser.error("--servings must be at least one")
    if args.max_stores < 1:
        parser.error("--max-stores must be at least one")
    if args.beam_width < 1:
        parser.error("--beam-width must be at least one")
    if not args.counts or min(args.counts) < args.recipes:
        parser.error("every candidate count must be at least --recipes")
    if max(args.counts) > 300:
        parser.error("candidate counts are capped at 300")


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = _parser()
    args = parser.parse_args(argv)
    _validate_args(parser, args)
    try:
        output = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - never emit operational details
        print(
            json.dumps(
                {
                    "provider": args.provider,
                    "error": f"Diversity benchmark failed ({type(exc).__name__})",
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
