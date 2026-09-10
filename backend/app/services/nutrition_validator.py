"""Deterministic meal-quality estimates for recipe candidate safeguards.

The reference values in this module are deliberately small, approximate PoC
defaults.  They are useful for rejecting obviously incomplete dinner
candidates, but they are not product-label facts or individual dietary advice.
Exact products can vary substantially within a canonical ingredient.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from app.models.recipe import Recipe
from app.services.ingredient_normalizer import (
    canonicalize_ingredient_name,
    normalize_quantity,
)
from app.services.ingredient_taxonomy import (
    TAXONOMY_BY_CANONICAL,
    IngredientCategory,
    get_taxonomy_entry,
)


class EstimateConfidence(StrEnum):
    """Coarse confidence band for the transparent PoC estimate."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True, slots=True)
class _NutritionReference:
    """Approximate energy and protein per 100 g or 100 ml."""

    kcal_per_100: float
    protein_g_per_100: float
    expected_unit: str
    piece_weight_g: float | None = None


# Conservative edible-weight assumptions are only used for taxonomy entries
# whose recipes are expressed as pieces.  Keeping them explicit avoids hidden
# conversions elsewhere in the application.
_PIECE_WEIGHT_G: dict[str, float] = {
    "ägg": 55.0,
    "tortillas": 40.0,
}


# Approximate generic values.  The ingredient taxonomy remains the source of
# truth for canonical identity and structural role; this table only adds the
# two coarse measures needed by this PoC safeguard.
_NUTRITION_REFERENCES: dict[str, _NutritionReference] = {
    # Protein
    "kyckling": _NutritionReference(165, 31.0, "g"),
    "fläskkött": _NutritionReference(242, 27.0, "g"),
    "falukorv": _NutritionReference(260, 11.0, "g"),
    "korv": _NutritionReference(250, 11.0, "g"),
    "nötfärs": _NutritionReference(210, 20.0, "g"),
    "blandfärs": _NutritionReference(240, 18.0, "g"),
    "fisk": _NutritionReference(90, 20.0, "g"),
    "lax": _NutritionReference(208, 20.0, "g"),
    "ägg": _NutritionReference(143, 12.6, "st", _PIECE_WEIGHT_G["ägg"]),
    "tofu": _NutritionReference(120, 13.0, "g"),
    # Carbohydrates
    "potatis": _NutritionReference(77, 2.0, "g"),
    "ris": _NutritionReference(360, 7.0, "g"),
    "pasta": _NutritionReference(350, 12.5, "g"),
    "nudlar": _NutritionReference(350, 10.0, "g"),
    "couscous": _NutritionReference(360, 12.0, "g"),
    "bröd": _NutritionReference(250, 9.0, "g"),
    "tortillas": _NutritionReference(
        310,
        8.0,
        "st",
        _PIECE_WEIGHT_G["tortillas"],
    ),
    # Vegetables
    "gul lök": _NutritionReference(40, 1.1, "g"),
    "rödlök": _NutritionReference(40, 1.1, "g"),
    "morot": _NutritionReference(41, 0.9, "g"),
    "tomat": _NutritionReference(18, 0.9, "g"),
    "paprika": _NutritionReference(31, 1.0, "g"),
    "broccoli": _NutritionReference(34, 2.8, "g"),
    "vitkål": _NutritionReference(25, 1.3, "g"),
    "ärtor": _NutritionReference(80, 5.4, "g"),
    "frysta grönsaker": _NutritionReference(50, 3.0, "g"),
    "majs": _NutritionReference(86, 3.4, "g"),
    # Lentils are matched as a dry staple in the current product taxonomy;
    # the bean canonicals below normally represent drained/cooked cans.
    "linser": _NutritionReference(330, 24.0, "g"),
    "kidneybönor": _NutritionReference(100, 7.0, "g"),
    "svarta bönor": _NutritionReference(110, 7.0, "g"),
    "kikärtor": _NutritionReference(130, 7.0, "g"),
    "bönor": _NutritionReference(90, 5.5, "g"),
    # Dairy, per 100 ml where the taxonomy uses volume
    "mjölk": _NutritionReference(60, 3.4, "ml"),
    "grädde": _NutritionReference(200, 2.0, "ml"),
    "crème fraiche": _NutritionReference(150, 3.0, "ml"),
    "ost": _NutritionReference(350, 25.0, "g"),
    # Sauce bases
    "krossade tomater": _NutritionReference(25, 1.2, "g"),
    "kokosmjölk": _NutritionReference(180, 1.5, "ml"),
    "tomatpuré": _NutritionReference(80, 4.3, "g"),
    # Flavour/support
    "vitlök": _NutritionReference(149, 6.4, "g"),
    "sojasås": _NutritionReference(53, 8.0, "ml"),
    "buljong": _NutritionReference(15, 1.0, "g"),
}


def _verify_reference_coverage() -> None:
    taxonomy_names = set(TAXONOMY_BY_CANONICAL)
    reference_names = set(_NUTRITION_REFERENCES)
    if taxonomy_names != reference_names:
        missing = sorted(taxonomy_names - reference_names)
        unexpected = sorted(reference_names - taxonomy_names)
        raise RuntimeError(
            "Nutrition reference table must cover the ingredient taxonomy exactly; "
            f"missing={missing}, unexpected={unexpected}"
        )
    mismatched_units = sorted(
        canonical
        for canonical, reference in _NUTRITION_REFERENCES.items()
        if reference.expected_unit
        != TAXONOMY_BY_CANONICAL[canonical].expected_unit
    )
    if mismatched_units:
        raise RuntimeError(
            "Nutrition reference units differ from the ingredient taxonomy: "
            f"{mismatched_units}"
        )


_verify_reference_coverage()


@dataclass(frozen=True, slots=True)
class MealQualityConstraints:
    """Configurable structural bounds for a four-portion-style dinner."""

    min_kcal_per_portion: float = 450.0
    max_kcal_per_portion: float = 900.0
    min_protein_g_per_portion: float = 18.0
    min_vegetable_g_per_portion: float = 100.0
    min_confidence_score: float = 0.65

    def __post_init__(self) -> None:
        values = (
            self.min_kcal_per_portion,
            self.max_kcal_per_portion,
            self.min_protein_g_per_portion,
            self.min_vegetable_g_per_portion,
            self.min_confidence_score,
        )
        if any(not math.isfinite(value) for value in values):
            raise ValueError("meal-quality constraints must be finite")
        if self.min_kcal_per_portion < 0:
            raise ValueError("min_kcal_per_portion cannot be negative")
        if self.max_kcal_per_portion <= self.min_kcal_per_portion:
            raise ValueError("max_kcal_per_portion must exceed the minimum")
        if self.min_protein_g_per_portion < 0:
            raise ValueError("min_protein_g_per_portion cannot be negative")
        if self.min_vegetable_g_per_portion < 0:
            raise ValueError("min_vegetable_g_per_portion cannot be negative")
        if not 0 <= self.min_confidence_score <= 1:
            raise ValueError("min_confidence_score must be between zero and one")


@dataclass(frozen=True, slots=True)
class MealQualityEstimate:
    """Transparent aggregate estimate for one recipe."""

    is_estimate: bool
    total_kcal: float
    kcal_per_portion: float
    total_protein_g: float
    protein_g_per_portion: float
    total_vegetable_g: float
    vegetable_g_per_portion: float
    confidence_score: float
    confidence: EstimateConfidence
    estimated_ingredients: tuple[str, ...]
    unestimated_ingredients: tuple[str, ...]
    piece_weight_assumptions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RecipeQualityValidation:
    """Validation outcome plus the estimate used to reach it."""

    recipe_name: str
    is_valid: bool
    violations: tuple[str, ...]
    estimate: MealQualityEstimate


@dataclass(frozen=True, slots=True)
class RecipeQualityValidationReport:
    """Ordered validation results for several recipes."""

    results: tuple[RecipeQualityValidation, ...]

    @property
    def is_valid(self) -> bool:
        return all(result.is_valid for result in self.results)

    @property
    def valid_count(self) -> int:
        return sum(result.is_valid for result in self.results)

    @property
    def rejected_count(self) -> int:
        return len(self.results) - self.valid_count


_CONFIDENCE_BY_UNIT = {"g": 0.90, "ml": 0.85, "st": 0.75}
_IMPORTANCE_BY_CATEGORY = {
    IngredientCategory.PROTEIN: 3.0,
    IngredientCategory.LEGUME: 3.0,
    IngredientCategory.CARBOHYDRATE: 3.0,
    IngredientCategory.VEGETABLE: 2.0,
    IngredientCategory.DAIRY: 1.5,
    IngredientCategory.SAUCE_BASE: 1.5,
    IngredientCategory.FLAVOUR_SUPPORT: 0.5,
}


def _confidence_band(score: float) -> EstimateConfidence:
    if score >= 0.85:
        return EstimateConfidence.HIGH
    if score >= 0.65:
        return EstimateConfidence.MEDIUM
    return EstimateConfidence.LOW


def _ingredient_importance(canonical: str, quantity: float, unit: str, servings: int) -> float:
    entry = get_taxonomy_entry(canonical)
    if entry is None:
        # An unknown 5 g garnish must not count like an unknown 600 g main
        # component.  These generic anchors are only confidence weights; they
        # never create energy or protein estimates for the unknown ingredient.
        generic_quantity = {"g": 400.0, "ml": 400.0, "st": 4.0}.get(unit, 1.0)
        ratio = quantity / generic_quantity
        return 2.0 * min(max(ratio, 0.25), 2.0)
    base = _IMPORTANCE_BY_CATEGORY[entry.category]
    expected = entry.typical_meal_quantity * servings / 4
    ratio = quantity / expected if unit == entry.expected_unit and expected > 0 else 1.0
    return base * min(max(ratio, 0.25), 2.0)


class NutritionValidator:
    """Estimate recipe structure and reject candidates outside configured bounds."""

    def __init__(self, constraints: MealQualityConstraints | None = None) -> None:
        self.constraints = constraints or MealQualityConstraints()

    def estimate_recipe(self, recipe: Recipe) -> MealQualityEstimate:
        total_kcal = 0.0
        total_protein = 0.0
        vegetable_g = 0.0
        confidence_numerator = 0.0
        confidence_denominator = 0.0
        estimated: set[str] = set()
        unestimated: set[str] = set()
        piece_assumptions: set[str] = set()

        for ingredient in recipe.ingredients:
            canonical = canonicalize_ingredient_name(
                ingredient.canonical_name or ingredient.name
            )
            try:
                quantity, unit = normalize_quantity(
                    ingredient.quantity,
                    ingredient.unit,
                )
            except (TypeError, ValueError):
                unestimated.add(canonical)
                confidence_denominator += 1.0
                continue

            importance = _ingredient_importance(
                canonical,
                quantity,
                unit,
                recipe.servings,
            )
            confidence_denominator += importance
            reference = _NUTRITION_REFERENCES.get(canonical)
            entry = get_taxonomy_entry(canonical)
            if reference is None or entry is None or unit != reference.expected_unit:
                unestimated.add(canonical)
                continue

            if unit == "st":
                if reference.piece_weight_g is None:
                    unestimated.add(canonical)
                    continue
                basis_quantity = quantity * reference.piece_weight_g
                piece_assumptions.add(
                    f"{canonical}:{reference.piece_weight_g:g}g/st"
                )
            else:
                basis_quantity = quantity

            total_kcal += basis_quantity * reference.kcal_per_100 / 100
            total_protein += basis_quantity * reference.protein_g_per_100 / 100
            if entry.category == IngredientCategory.VEGETABLE:
                # All current vegetable taxonomy entries use grams.  The
                # branch remains explicit so a future unit change lowers
                # confidence rather than silently assuming a density.
                if unit == "g":
                    vegetable_g += quantity
                elif unit == "st" and reference.piece_weight_g is not None:
                    vegetable_g += basis_quantity

            confidence_numerator += importance * _CONFIDENCE_BY_UNIT[unit]
            estimated.add(canonical)

        confidence_score = (
            confidence_numerator / confidence_denominator
            if confidence_denominator > 0
            else 0.0
        )
        servings = recipe.servings
        return MealQualityEstimate(
            is_estimate=True,
            total_kcal=round(total_kcal, 1),
            kcal_per_portion=round(total_kcal / servings, 1),
            total_protein_g=round(total_protein, 1),
            protein_g_per_portion=round(total_protein / servings, 1),
            total_vegetable_g=round(vegetable_g, 1),
            vegetable_g_per_portion=round(vegetable_g / servings, 1),
            confidence_score=round(confidence_score, 4),
            confidence=_confidence_band(confidence_score),
            estimated_ingredients=tuple(sorted(estimated)),
            unestimated_ingredients=tuple(sorted(unestimated)),
            piece_weight_assumptions=tuple(sorted(piece_assumptions)),
        )

    def validate_recipe(self, recipe: Recipe) -> RecipeQualityValidation:
        estimate = self.estimate_recipe(recipe)
        constraints = self.constraints
        violations: list[str] = []
        if estimate.kcal_per_portion < constraints.min_kcal_per_portion:
            violations.append("kcal_per_portion_below_minimum")
        if estimate.kcal_per_portion > constraints.max_kcal_per_portion:
            violations.append("kcal_per_portion_above_maximum")
        if estimate.protein_g_per_portion < constraints.min_protein_g_per_portion:
            violations.append("protein_per_portion_below_minimum")
        if estimate.vegetable_g_per_portion < constraints.min_vegetable_g_per_portion:
            violations.append("vegetable_per_portion_below_minimum")
        if estimate.confidence_score < constraints.min_confidence_score:
            violations.append("estimate_confidence_below_minimum")
        return RecipeQualityValidation(
            recipe_name=recipe.name,
            is_valid=not violations,
            violations=tuple(violations),
            estimate=estimate,
        )

    def validate_recipes(
        self,
        recipes: Iterable[Recipe],
    ) -> RecipeQualityValidationReport:
        return RecipeQualityValidationReport(
            results=tuple(self.validate_recipe(recipe) for recipe in recipes)
        )


def estimate_recipe_quality(recipe: Recipe) -> MealQualityEstimate:
    """Estimate one recipe with the default reference table."""

    return NutritionValidator().estimate_recipe(recipe)


def validate_recipe(
    recipe: Recipe,
    constraints: MealQualityConstraints | None = None,
) -> RecipeQualityValidation:
    """Validate one recipe with optional bounds."""

    return NutritionValidator(constraints).validate_recipe(recipe)


def validate_recipes(
    recipes: Iterable[Recipe],
    constraints: MealQualityConstraints | None = None,
) -> RecipeQualityValidationReport:
    """Validate several recipes while preserving their input order."""

    return NutritionValidator(constraints).validate_recipes(recipes)


__all__ = [
    "EstimateConfidence",
    "MealQualityConstraints",
    "MealQualityEstimate",
    "NutritionValidator",
    "RecipeQualityValidation",
    "RecipeQualityValidationReport",
    "estimate_recipe_quality",
    "validate_recipe",
    "validate_recipes",
]
