"""Multi-dimensional culinary similarity and menu repetition reporting."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations

from app.models.recipe import Recipe
from app.services.recipe_profile import RecipeProfile, RecipeProfileBuilder
from app.services.recipe_similarity import weighted_jaccard


@dataclass(frozen=True, slots=True)
class CulinarySimilarityWeights:
    """Configurable component weights; arbitrary positive totals are normalized."""

    ingredient: float = 0.30
    family: float = 0.20
    cooking: float = 0.10
    dish: float = 0.15
    carb: float = 0.10
    protein: float = 0.10
    sauce: float = 0.05

    def __post_init__(self) -> None:
        values = self.values
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("culinary similarity weights must be finite and non-negative")
        if sum(values) <= 0:
            raise ValueError("at least one culinary similarity weight must be positive")

    @property
    def values(self) -> tuple[float, ...]:
        return (
            self.ingredient,
            self.family,
            self.cooking,
            self.dish,
            self.carb,
            self.protein,
            self.sauce,
        )

    @property
    def total(self) -> float:
        return sum(self.values)


@dataclass(frozen=True, slots=True)
class CulinarySimilarityComponents:
    """Normalized component scores behind a pair's total."""

    ingredient: float
    family: float
    cooking: float
    dish: float
    carb: float
    protein: float
    sauce: float


@dataclass(frozen=True, slots=True)
class CulinarySimilarityPair:
    """Detailed culinary similarity for one unordered recipe pair."""

    left_recipe: str
    right_recipe: str
    score: float
    is_high_similarity: bool
    components: CulinarySimilarityComponents
    shared_major_ingredients: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CulinaryRepetitionReport:
    """Repeated profile values, omitting values which occur only once."""

    family: dict[str, int]
    protein: dict[str, int]
    carb: dict[str, int]
    dish: dict[str, int]
    cooking: dict[str, int]


@dataclass(frozen=True, slots=True)
class CulinaryMenuReport:
    """Pairwise menu summary and structural repetition counters."""

    profiles: tuple[RecipeProfile, ...]
    pairs: tuple[CulinarySimilarityPair, ...]
    average_similarity: float
    max_similarity: float
    diversity_score: float
    repetitions: CulinaryRepetitionReport


def _exact_similarity(left: str | None, right: str | None) -> float:
    # Two missing sauce bases are the same explicit absence, not unknown data:
    # profile construction has already inspected every canonical ingredient.
    if left is None and right is None:
        return 1.0
    if left is None or right is None:
        return 0.0
    return 1.0 if left.casefold() == right.casefold() else 0.0


def _repetitions(values: Iterable[str | None]) -> dict[str, int]:
    counts = Counter(value for value in values if value)
    return {value: count for value, count in sorted(counts.items()) if count > 1}


class CulinarySimilarity:
    """Compare rich recipe profiles with explainable weighted components."""

    def __init__(
        self,
        *,
        weights: CulinarySimilarityWeights | None = None,
        high_similarity_threshold: float = 0.65,
        profile_builder: RecipeProfileBuilder | None = None,
    ) -> None:
        if not math.isfinite(high_similarity_threshold) or not 0 <= high_similarity_threshold <= 1:
            raise ValueError("high_similarity_threshold must be between zero and one")
        self.weights = weights or CulinarySimilarityWeights()
        self.high_similarity_threshold = high_similarity_threshold
        self.profile_builder = profile_builder or RecipeProfileBuilder()

    def build_profile(self, recipe: Recipe) -> RecipeProfile:
        return self.profile_builder.build(recipe)

    def compare_profiles(
        self,
        left: RecipeProfile,
        right: RecipeProfile,
    ) -> CulinarySimilarityPair:
        components = CulinarySimilarityComponents(
            ingredient=weighted_jaccard(
                left.ingredient_weight_map,
                right.ingredient_weight_map,
            ),
            family=_exact_similarity(left.recipe_family, right.recipe_family),
            cooking=_exact_similarity(left.cooking_method, right.cooking_method),
            dish=_exact_similarity(left.dish_form, right.dish_form),
            carb=_exact_similarity(left.primary_carb, right.primary_carb),
            protein=_exact_similarity(left.primary_protein, right.primary_protein),
            sauce=_exact_similarity(left.sauce_base, right.sauce_base),
        )
        weights = self.weights
        score = (
            components.ingredient * weights.ingredient
            + components.family * weights.family
            + components.cooking * weights.cooking
            + components.dish * weights.dish
            + components.carb * weights.carb
            + components.protein * weights.protein
            + components.sauce * weights.sauce
        ) / weights.total
        # A protein swap or a vegetable garnish cannot turn the same cooked
        # carbohydrate/serving structure into a distinct dinner.
        same_structure = (
            left.recipe_family == right.recipe_family
            and left.cooking_method == right.cooking_method
            and left.primary_carb == right.primary_carb
        )
        same_main_combination = (
            left.primary_protein == right.primary_protein
            and left.primary_carb == right.primary_carb
            and left.cooking_method == right.cooking_method
        )
        same_core_with_different_side = (
            left.recipe_family == right.recipe_family
            and left.primary_protein == right.primary_protein
            and left.cooking_method == right.cooking_method
            and left.sauce_base == right.sauce_base
        )
        if same_structure or same_main_combination or same_core_with_different_side:
            score = max(score, 0.90)
        return CulinarySimilarityPair(
            left_recipe=left.recipe_name,
            right_recipe=right.recipe_name,
            score=score,
            is_high_similarity=score >= self.high_similarity_threshold,
            components=components,
            shared_major_ingredients=tuple(
                sorted(set(left.major_ingredients) & set(right.major_ingredients))
            ),
        )

    def compare_recipes(self, left: Recipe, right: Recipe) -> CulinarySimilarityPair:
        return self.compare_profiles(
            self.build_profile(left),
            self.build_profile(right),
        )

    def analyze_menu(self, recipes: Iterable[Recipe]) -> CulinaryMenuReport:
        profiles = tuple(self.build_profile(recipe) for recipe in recipes)
        pairs = tuple(
            self.compare_profiles(left, right) for left, right in combinations(profiles, 2)
        )
        average = sum(pair.score for pair in pairs) / len(pairs) if pairs else 0.0
        return CulinaryMenuReport(
            profiles=profiles,
            pairs=pairs,
            average_similarity=average,
            max_similarity=max((pair.score for pair in pairs), default=0.0),
            diversity_score=1.0 - average,
            repetitions=CulinaryRepetitionReport(
                family=_repetitions(profile.recipe_family for profile in profiles),
                protein=_repetitions(profile.primary_protein for profile in profiles),
                carb=_repetitions(profile.primary_carb for profile in profiles),
                dish=_repetitions(profile.dish_form for profile in profiles),
                cooking=_repetitions(profile.cooking_method for profile in profiles),
            ),
        )


def compare_culinary_similarity(
    left: Recipe,
    right: Recipe,
    *,
    weights: CulinarySimilarityWeights | None = None,
    high_similarity_threshold: float = 0.65,
) -> CulinarySimilarityPair:
    """Functional convenience wrapper for one recipe pair."""

    return CulinarySimilarity(
        weights=weights,
        high_similarity_threshold=high_similarity_threshold,
    ).compare_recipes(left, right)


def analyze_culinary_menu(
    recipes: Iterable[Recipe],
    *,
    weights: CulinarySimilarityWeights | None = None,
    high_similarity_threshold: float = 0.65,
) -> CulinaryMenuReport:
    """Return a detailed pairwise and repetition report for a menu."""

    return CulinarySimilarity(
        weights=weights,
        high_similarity_threshold=high_similarity_threshold,
    ).analyze_menu(recipes)


__all__ = [
    "CulinaryMenuReport",
    "CulinaryRepetitionReport",
    "CulinarySimilarity",
    "CulinarySimilarityComponents",
    "CulinarySimilarityPair",
    "CulinarySimilarityWeights",
    "analyze_culinary_menu",
    "compare_culinary_similarity",
]
