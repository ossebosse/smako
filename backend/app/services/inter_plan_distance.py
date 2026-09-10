"""Versioned, order-independent alternatives conditioned on a selected week."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, replace
from decimal import ROUND_FLOOR, Decimal
from typing import Any

from app.errors import IncompleteBasketError
from app.models.recipe import Recipe
from app.services.culinary_similarity import CulinarySimilarity
from app.services.recipe_candidate_validator import recipe_id

INTER_PLAN_POLICY_VERSION = "balanced-conditioned-v1"
MIN_CHANGED_DINNERS = {3: 2, 4: 2, 5: 3, 6: 3, 7: 4}
NEAR_DUPLICATE_THRESHOLD = 0.85


def required_changes(count: int) -> int:
    return MIN_CHANGED_DINNERS.get(count, (count + 1) // 2)


def exact_identity(recipe: Recipe) -> str:
    # Display names never establish a new recipe identity.
    return recipe_id(recipe.model_copy(update={"name": "identity"}))


def reference_identity(recipes: Sequence[Recipe]) -> list[str]:
    return sorted(exact_identity(recipe) for recipe in recipes)


def compare_plans(balanced: Sequence[Recipe], alternative: Sequence[Recipe]) -> dict[str, Any]:
    similarity = CulinarySimilarity()
    references = [similarity.build_profile(recipe) for recipe in balanced]
    rows = []
    for recipe in alternative:
        profile = similarity.build_profile(recipe)
        pairs = [similarity.compare_profiles(profile, other) for other in references]
        exact = exact_identity(recipe) in reference_identity(balanced)
        nearest = max(pairs, key=lambda pair: pair.score, default=None)
        changed = not exact and (nearest is None or nearest.score < NEAR_DUPLICATE_THRESHOLD)
        rows.append({
            "recipe": recipe.name,
            "exact_overlap": exact,
            "structurally_changed": changed,
            "nearest_balanced_recipe": nearest.right_recipe if nearest else None,
            "distance_from_nearest": 1 - nearest.score if nearest else 1.0,
            "profile": asdict(profile),
            "comparisons": [asdict(pair) for pair in pairs],
        })
    exact_overlaps = sum((Counter(reference_identity(balanced)) & Counter(reference_identity(alternative))).values())
    changed_count = sum(row["structurally_changed"] for row in rows)
    return {
        "policy_version": INTER_PLAN_POLICY_VERSION,
        "balanced_reference_identity": reference_identity(balanced),
        "required_changes": required_changes(len(balanced)),
        "dinner_count": len(alternative),
        "exact_overlap_count": exact_overlaps,
        "structurally_different_dinners": changed_count,
        "target_met": changed_count >= required_changes(len(balanced)),
        "near_duplicate_threshold": NEAR_DUPLICATE_THRESHOLD,
        "dinners": rows,
    }


@dataclass(frozen=True)
class ConditionedSearchResult:
    result: Any
    internal_targets_relaxed: bool
    attempts: tuple[dict[str, Any], ...]


def search_conditioned_varied(
    optimizer: Any,
    candidates: Sequence[Recipe],
    products: Any,
    stores: Any,
    *,
    balanced_result: Any,
    target_constraints: Any,
    fallback_constraints: Any,
    budget_percent: float = 25,
    **search_options: Any,
) -> ConditionedSearchResult:
    """Minimize checkout cost at the requested distance, then degrade honestly.

    Distance is a beam feasibility dimension, not a post-hoc swap or SEK bonus.
    Each candidate must be novel against ALL reference dinners, so a matching
    permutation or several near copies cannot inflate the changed count.
    Bounded search exhaustion is reported, never claimed as global infeasibility.
    """
    comparison = compare_plans(balanced_result.recipes, candidates)
    novel = frozenset(row["recipe"] for row in comparison["dinners"] if row["structurally_changed"])
    ceiling = (Decimal(str(balanced_result.basket.total)) *
               (1 + Decimal(str(budget_percent)) / 100)).quantize(Decimal("0.01"), rounding=ROUND_FLOOR)
    attempts = []
    for changed in range(required_changes(len(balanced_result.recipes)), -1, -1):
        for relaxed, base in ((False, target_constraints), (True, fallback_constraints)):
            if relaxed and base == target_constraints:
                continue
            constraints = replace(base, min_reference_changes=changed,
                                  reference_distinct_recipes=novel,
                                  target_recipe_count=len(balanced_result.recipes))
            evidence = {"required_changes": changed, "internal_targets_relaxed": relaxed,
                        "novel_candidates": len(novel), "candidate_count": len(candidates),
                        "budget_ceiling": float(ceiling)}
            if len(novel) < changed:
                attempts.append({**evidence, "reason": "insufficient_structurally_distinct_candidates"})
                continue
            try:
                result = optimizer.optimize(candidates, products, stores,
                                            diversity_constraints=constraints, **search_options)
            except IncompleteBasketError:
                attempts.append({**evidence, "reason": "bounded_search_exhausted"})
                continue
            evidence.update(total=result.basket.total, search_stats=asdict(result.stats))
            if Decimal(str(result.basket.total)) > ceiling:
                attempts.append({**evidence, "reason": "lowest_found_plan_over_budget"})
                continue
            attempts.append({**evidence, "reason": "selected"})
            return ConditionedSearchResult(result, relaxed, tuple(attempts))
    return ConditionedSearchResult(balanced_result, True, tuple(attempts))
