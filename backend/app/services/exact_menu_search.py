"""Exact package-aware menu search for small candidate sets.

This module is intentionally separate from the production beam search. It is
useful as a quality oracle in tests and benchmarks where the candidate count is
small enough to enumerate every menu combination safely.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from itertools import combinations
from math import comb
from time import perf_counter

from app.errors import IncompleteBasketError
from app.models.basket import BasketAuditResult, OptimizedBasket
from app.models.ingredient import NormalizedIngredient
from app.models.product import ProductCandidate
from app.models.recipe import Recipe
from app.models.store import Store
from app.services.basket_calculator import money
from app.services.basket_optimizer import BasketOptimizer
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.menu_optimizer import DiversityConstraints, MenuOptimizer

from grocery_data.app.domain.promotion_pricing import UserPricingContext

type IngredientProfile = tuple[tuple[str, str, str], ...]
type RequirementKey = tuple[int | None, tuple[tuple[str, str, str], ...]]


@dataclass(frozen=True, slots=True)
class ExactPlanEvaluation:
    """Fully deterministic state exposed to an optional invariant predicate."""

    recipes: tuple[Recipe, ...]
    ingredients: tuple[NormalizedIngredient, ...]
    basket: OptimizedBasket
    basket_audit: BasketAuditResult


type ExactPlanPredicate = Callable[[ExactPlanEvaluation], bool]


@dataclass(frozen=True, slots=True)
class ExactMenuSearchStats:
    """Counters and runtime for one request-local exhaustive search."""

    candidates_received: int
    candidates_deduplicated: int
    candidate_count: int
    combinations_total: int
    combinations_considered: int
    combinations_evaluated: int
    diversity_rejections: int
    predicate_rejections: int
    incomplete_rejections: int
    basket_cache_hits: int
    basket_cache_misses: int
    basket_calculations: int
    quote_cache_hits: int
    quote_cache_misses: int
    runtime_seconds: float


@dataclass(frozen=True, slots=True)
class ExactMenuSearchResult:
    """Globally cheapest valid menu within the supplied candidate set."""

    recipes: list[Recipe]
    basket: OptimizedBasket
    ingredients: list[NormalizedIngredient]
    stats: ExactMenuSearchStats
    basket_audit: BasketAuditResult


@dataclass(frozen=True, slots=True)
class _Candidate:
    recipe: Recipe
    profile: IngredientProfile
    family: str | None
    primary_ingredient: str | None
    carbohydrate: str | None
    cooking_method: str | None
    dish_form: str | None


@dataclass(frozen=True, slots=True)
class _Evaluation:
    ingredients: tuple[NormalizedIngredient, ...]
    basket: OptimizedBasket
    audit: BasketAuditResult


class ExactMenuSearch(MenuOptimizer):
    """Enumerate all recipe combinations under the production constraints."""

    def __init__(
        self,
        *,
        normalizer: IngredientNormalizer | None = None,
        basket_optimizer: BasketOptimizer | None = None,
        max_candidates: int = 20,
    ) -> None:
        if max_candidates < 1:
            raise ValueError("max_candidates must be at least one")
        super().__init__(
            normalizer=normalizer,
            basket_optimizer=basket_optimizer,
        )
        self.max_candidates = max_candidates

    @staticmethod
    def _requirement_key(
        ingredients: Sequence[NormalizedIngredient],
        max_stores: int | None,
    ) -> RequirementKey:
        effective_limit = (
            None if max_stores is None or max_stores <= 0 else max_stores
        )
        requirements = tuple(
            sorted(
                (
                    ingredient.canonical_name,
                    ingredient.unit,
                    str(
                        Decimal(str(ingredient.required_quantity)).normalize()
                    ),
                )
                for ingredient in ingredients
            )
        )
        return effective_limit, requirements

    @staticmethod
    def _winner_key(
        candidates: Sequence[_Candidate],
        evaluation: _Evaluation,
    ) -> tuple[object, ...]:
        return (
            money(evaluation.basket.total),
            evaluation.basket.store_count,
            tuple(sorted(candidate.profile for candidate in candidates)),
            tuple(sorted(candidate.recipe.name.casefold() for candidate in candidates)),
        )

    def optimize(
        self,
        candidates: Sequence[Recipe],
        candidates_by_name: Mapping[str, Sequence[ProductCandidate]],
        stores: Sequence[Store],
        *,
        recipe_count: int = 5,
        max_stores: int | None = 2,
        diversity_constraints: DiversityConstraints | None = None,
        plan_predicate: ExactPlanPredicate | None = None,
        user_pricing_context: UserPricingContext | None = None,
    ) -> ExactMenuSearchResult:
        """Return the exact optimum, or fail before unsafe enumeration.

        ``plan_predicate`` runs after deterministic product/package pricing and
        can enforce future basket, nutrition or similarity invariants without
        coupling them to this search implementation.
        """

        started = perf_counter()
        if recipe_count < 1:
            raise ValueError("recipe_count must be at least one")
        if len(candidates) > self.max_candidates:
            raise ValueError(
                f"Exact search accepts at most {self.max_candidates} candidates; "
                f"received {len(candidates)}"
            )
        if not stores:
            raise IncompleteBasketError(
                "No stores are available for exact menu optimisation"
            )

        constraints = diversity_constraints or DiversityConstraints()
        representatives: dict[IngredientProfile, Recipe] = {}
        for recipe in sorted(
            candidates,
            key=lambda row: (row.name.casefold(), row.name),
        ):
            representatives.setdefault(self._profile(recipe), recipe)

        classified: list[_Candidate] = []
        for profile, recipe in representatives.items():
            family, primary, carbohydrate, cooking_method, dish_form = (
                self._classify(recipe, constraints)
            )
            classified.append(
                _Candidate(
                    recipe=recipe,
                    profile=profile,
                    family=family,
                    primary_ingredient=primary,
                    carbohydrate=carbohydrate,
                    cooking_method=cooking_method,
                    dish_form=dish_form,
                )
            )
        classified.sort(
            key=lambda row: (
                row.recipe.name.casefold(),
                row.recipe.name,
                row.profile,
            )
        )
        if len(classified) < recipe_count:
            raise IncompleteBasketError(
                f"Only {len(classified)} distinct candidates are available; "
                f"{recipe_count} are required"
            )

        total_combinations = comb(len(classified), recipe_count)
        basket_cache: dict[RequirementKey, _Evaluation] = {}
        incomplete_cache: set[RequirementKey] = set()
        combinations_considered = 0
        combinations_evaluated = 0
        diversity_rejections = 0
        predicate_rejections = 0
        incomplete_rejections = 0
        basket_cache_hits = 0
        basket_cache_misses = 0
        best_candidates: tuple[_Candidate, ...] | None = None
        best_evaluation: _Evaluation | None = None
        best_key: tuple[object, ...] | None = None

        with self.basket_optimizer.quote_cache() as quote_stats:
            for selected in combinations(classified, recipe_count):
                combinations_considered += 1
                if not self._satisfies_diversity(selected, constraints):
                    diversity_rejections += 1
                    continue

                recipes = tuple(candidate.recipe for candidate in selected)
                ingredients = tuple(self.normalizer.normalize_and_aggregate(recipes))
                purchasable_ingredients = tuple(
                    ingredient
                    for ingredient in ingredients
                    if not self.basket_auditor.is_pantry(ingredient)
                )
                cache_key = self._requirement_key(ingredients, max_stores)
                if cache_key in basket_cache:
                    basket_cache_hits += 1
                    evaluation = basket_cache[cache_key]
                elif cache_key in incomplete_cache:
                    basket_cache_hits += 1
                    incomplete_rejections += 1
                    continue
                else:
                    basket_cache_misses += 1
                    try:
                        basket = self.basket_optimizer.optimize(
                            purchasable_ingredients,
                            candidates_by_name,
                            stores,
                            max_stores=max_stores,
                            calculate_savings=False,
                        )
                    except (IncompleteBasketError, ValueError):
                        incomplete_cache.add(cache_key)
                        incomplete_rejections += 1
                        continue
                    audit = self.basket_auditor.audit(
                        ingredients,
                        basket,
                        user_pricing_context=user_pricing_context,
                    )
                    if not audit.passed:
                        incomplete_cache.add(cache_key)
                        incomplete_rejections += 1
                        continue
                    evaluation = _Evaluation(
                        ingredients=ingredients,
                        basket=basket,
                        audit=audit,
                    )
                    basket_cache[cache_key] = evaluation

                combinations_evaluated += 1
                if plan_predicate is not None and not plan_predicate(
                    ExactPlanEvaluation(
                        recipes=recipes,
                        ingredients=evaluation.ingredients,
                        basket=evaluation.basket,
                        basket_audit=evaluation.audit,
                    )
                ):
                    predicate_rejections += 1
                    continue

                candidate_key = self._winner_key(selected, evaluation)
                if best_key is None or candidate_key < best_key:
                    best_key = candidate_key
                    best_candidates = selected
                    best_evaluation = evaluation

            if best_candidates is None or best_evaluation is None:
                raise IncompleteBasketError(
                    "No complete menu satisfies the basket, diversity and plan "
                    "constraints"
                )

            # Materialise complete savings metadata only for the exact winner.
            final_basket = self.basket_optimizer.optimize(
                [
                    ingredient
                    for ingredient in best_evaluation.ingredients
                    if not self.basket_auditor.is_pantry(ingredient)
                ],
                candidates_by_name,
                stores,
                max_stores=max_stores,
            )
            runtime = perf_counter() - started
            stats = ExactMenuSearchStats(
                candidates_received=len(candidates),
                candidates_deduplicated=len(candidates) - len(representatives),
                candidate_count=len(classified),
                combinations_total=total_combinations,
                combinations_considered=combinations_considered,
                combinations_evaluated=combinations_evaluated,
                diversity_rejections=diversity_rejections,
                predicate_rejections=predicate_rejections,
                incomplete_rejections=incomplete_rejections,
                basket_cache_hits=basket_cache_hits,
                basket_cache_misses=basket_cache_misses,
                basket_calculations=basket_cache_misses + 1,
                quote_cache_hits=quote_stats.hits,
                quote_cache_misses=quote_stats.misses,
                runtime_seconds=round(runtime, 6),
            )

        return ExactMenuSearchResult(
            recipes=[candidate.recipe for candidate in best_candidates],
            basket=final_basket,
            ingredients=list(best_evaluation.ingredients),
            stats=stats,
            basket_audit=self.basket_auditor.audit(
                best_evaluation.ingredients,
                final_basket,
                user_pricing_context=user_pricing_context,
            ),
        )


__all__ = [
    "ExactMenuSearch",
    "ExactMenuSearchResult",
    "ExactMenuSearchStats",
    "ExactPlanEvaluation",
    "ExactPlanPredicate",
]
