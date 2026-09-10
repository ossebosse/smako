"""Canonical, quantity-aware recipe similarity for menu diversity checks."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from itertools import combinations

from app.models.recipe import Recipe
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.ingredient_taxonomy import IngredientCategory, get_taxonomy_entry


@dataclass(frozen=True, slots=True)
class RecipeSimilarityConstraints:
    """Configurable threshold and structural role weights."""

    near_duplicate_threshold: float = 0.70
    primary_weight: float = 4.0
    carbohydrate_weight: float = 4.0
    vegetable_weight: float = 2.0
    dairy_weight: float = 2.0
    sauce_weight: float = 3.0
    flavour_weight: float = 0.5
    unknown_weight: float = 1.0

    def __post_init__(self) -> None:
        if not 0 <= self.near_duplicate_threshold <= 1:
            raise ValueError("near_duplicate_threshold must be between zero and one")
        weights = (
            self.primary_weight,
            self.carbohydrate_weight,
            self.vegetable_weight,
            self.dairy_weight,
            self.sauce_weight,
            self.flavour_weight,
            self.unknown_weight,
        )
        if any(not math.isfinite(weight) or weight <= 0 for weight in weights):
            raise ValueError("recipe similarity weights must be finite and positive")


@dataclass(frozen=True, slots=True)
class IngredientProfileWeight:
    """One canonical ingredient's contribution to a recipe profile."""

    canonical_name: str
    role: str
    quantity_ratio: float
    weight: float


@dataclass(frozen=True, slots=True)
class WeightedRecipeProfile:
    """Stable weighted canonical profile for one recipe."""

    recipe_name: str
    ingredients: tuple[IngredientProfileWeight, ...]

    @property
    def weights(self) -> dict[str, float]:
        return {
            ingredient.canonical_name: ingredient.weight
            for ingredient in self.ingredients
        }


@dataclass(frozen=True, slots=True)
class RecipeSimilarityPair:
    """Similarity result for one unordered recipe pair."""

    left_recipe: str
    right_recipe: str
    score: float
    threshold: float
    is_near_duplicate: bool
    shared_ingredients: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecipeSimilarityReport:
    """All pairwise comparisons and the maximum score in a recipe plan."""

    pairs: tuple[RecipeSimilarityPair, ...]
    maximum_similarity: float
    threshold: float
    near_duplicate_pairs: tuple[RecipeSimilarityPair, ...]

    @property
    def is_valid(self) -> bool:
        return not self.near_duplicate_pairs


_ROLE_BY_CATEGORY = {
    IngredientCategory.PROTEIN: "primary",
    IngredientCategory.LEGUME: "primary",
    IngredientCategory.CARBOHYDRATE: "carbohydrate",
    IngredientCategory.VEGETABLE: "vegetable",
    IngredientCategory.DAIRY: "dairy",
    IngredientCategory.SAUCE_BASE: "sauce",
    IngredientCategory.FLAVOUR_SUPPORT: "flavour",
}


class RecipeSimilarityAnalyzer:
    """Build profiles and identify overly similar recipes deterministically."""

    def __init__(
        self,
        constraints: RecipeSimilarityConstraints | None = None,
        normalizer: IngredientNormalizer | None = None,
    ) -> None:
        self.constraints = constraints or RecipeSimilarityConstraints()
        self.normalizer = normalizer or IngredientNormalizer()

    def _role_weight(self, role: str) -> float:
        return {
            "primary": self.constraints.primary_weight,
            "carbohydrate": self.constraints.carbohydrate_weight,
            "vegetable": self.constraints.vegetable_weight,
            "dairy": self.constraints.dairy_weight,
            "sauce": self.constraints.sauce_weight,
            "flavour": self.constraints.flavour_weight,
            "unknown": self.constraints.unknown_weight,
        }[role]

    def build_profile(self, recipe: Recipe) -> WeightedRecipeProfile:
        rows: list[IngredientProfileWeight] = []
        for ingredient in self.normalizer.normalize_and_aggregate([recipe]):
            entry = get_taxonomy_entry(ingredient.canonical_name)
            if entry is None or ingredient.unit != entry.expected_unit:
                role = "unknown"
                quantity_ratio = 1.0
            else:
                role = _ROLE_BY_CATEGORY[entry.category]
                expected = entry.typical_meal_quantity * recipe.servings / 4
                quantity_ratio = (
                    ingredient.required_quantity / expected if expected > 0 else 1.0
                )

            # Square-root scaling lets meaningful quantity differences affect
            # similarity without allowing a single large amount to dominate
            # the complete ingredient identity profile.
            bounded_ratio = min(max(quantity_ratio, 0.25), 4.0)
            weight = self._role_weight(role) * math.sqrt(bounded_ratio)
            rows.append(
                IngredientProfileWeight(
                    canonical_name=ingredient.canonical_name,
                    role=role,
                    quantity_ratio=round(quantity_ratio, 4),
                    weight=round(weight, 6),
                )
            )
        return WeightedRecipeProfile(
            recipe_name=recipe.name,
            ingredients=tuple(sorted(rows, key=lambda row: row.canonical_name)),
        )

    def compare_profiles(
        self,
        left: WeightedRecipeProfile,
        right: WeightedRecipeProfile,
    ) -> RecipeSimilarityPair:
        left_weights = left.weights
        right_weights = right.weights
        score = weighted_jaccard(left_weights, right_weights)
        shared = tuple(sorted(set(left_weights) & set(right_weights)))
        return RecipeSimilarityPair(
            left_recipe=left.recipe_name,
            right_recipe=right.recipe_name,
            # Keep the full deterministic score so ``is_near_duplicate`` can
            # never contradict a rounded value displayed at the threshold.
            score=score,
            threshold=self.constraints.near_duplicate_threshold,
            is_near_duplicate=score >= self.constraints.near_duplicate_threshold,
            shared_ingredients=shared,
        )

    def compare_recipes(self, left: Recipe, right: Recipe) -> RecipeSimilarityPair:
        return self.compare_profiles(
            self.build_profile(left),
            self.build_profile(right),
        )

    def analyze_plan(self, recipes: Iterable[Recipe]) -> RecipeSimilarityReport:
        profiles = [self.build_profile(recipe) for recipe in recipes]
        pairs = tuple(
            self.compare_profiles(left, right)
            for left, right in combinations(profiles, 2)
        )
        near_duplicates = tuple(pair for pair in pairs if pair.is_near_duplicate)
        return RecipeSimilarityReport(
            pairs=pairs,
            maximum_similarity=max((pair.score for pair in pairs), default=0.0),
            threshold=self.constraints.near_duplicate_threshold,
            near_duplicate_pairs=near_duplicates,
        )

    def validate_plan(self, recipes: Iterable[Recipe]) -> RecipeSimilarityReport:
        """Return the pairwise report; ``is_valid`` is false for near duplicates."""

        return self.analyze_plan(recipes)


def weighted_jaccard(
    left: Mapping[str, float],
    right: Mapping[str, float],
) -> float:
    """Return weighted Jaccard similarity for non-negative feature mappings."""

    keys = set(left) | set(right)
    if not keys:
        return 1.0
    if any(
        not math.isfinite(value) or value < 0
        for value in (*left.values(), *right.values())
    ):
        raise ValueError("weighted Jaccard values must be finite and non-negative")
    numerator = sum(min(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)
    denominator = sum(max(left.get(key, 0.0), right.get(key, 0.0)) for key in keys)
    return numerator / denominator if denominator else 1.0


def build_weighted_profile(
    recipe: Recipe,
    constraints: RecipeSimilarityConstraints | None = None,
) -> WeightedRecipeProfile:
    """Build a canonical profile using optional weights."""

    return RecipeSimilarityAnalyzer(constraints).build_profile(recipe)


def compare_recipes(
    left: Recipe,
    right: Recipe,
    constraints: RecipeSimilarityConstraints | None = None,
) -> RecipeSimilarityPair:
    """Compare two recipes with the configured threshold."""

    return RecipeSimilarityAnalyzer(constraints).compare_recipes(left, right)


def analyze_recipe_plan(
    recipes: Iterable[Recipe],
    constraints: RecipeSimilarityConstraints | None = None,
) -> RecipeSimilarityReport:
    """Return all unordered recipe pairs and their maximum similarity."""

    return RecipeSimilarityAnalyzer(constraints).analyze_plan(recipes)


__all__ = [
    "IngredientProfileWeight",
    "RecipeSimilarityAnalyzer",
    "RecipeSimilarityConstraints",
    "RecipeSimilarityPair",
    "RecipeSimilarityReport",
    "WeightedRecipeProfile",
    "analyze_recipe_plan",
    "build_weighted_profile",
    "compare_recipes",
    "weighted_jaccard",
]
