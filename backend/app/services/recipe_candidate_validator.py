"""Structural validation and duplicate pruning for recipe candidates."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.models.recipe import Recipe
from app.services.basket_auditor import BasketAuditor
from app.services.ingredient_normalizer import (
    canonicalize_ingredient_name,
    normalize_quantity,
)
from app.services.ingredient_taxonomy import IngredientCategory, get_taxonomy_entry


@dataclass(frozen=True, slots=True)
class RejectedRecipeCandidate:
    recipe: Recipe
    reasons: tuple[str, ...]


@dataclass(slots=True)
class CandidateValidationResult:
    valid_recipes: list[Recipe]
    rejected: list[RejectedRecipeCandidate]

    @property
    def generated_count(self) -> int:
        return len(self.valid_recipes) + len(self.rejected)

    @property
    def valid_count(self) -> int:
        return len(self.valid_recipes)

    @property
    def rejected_count(self) -> int:
        return len(self.rejected)


def _plain_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", unaccented).strip()


def ingredient_profile(recipe: Recipe) -> tuple[str, ...]:
    """Return the ingredient identity profile used for obvious duplicate pruning."""

    return tuple(
        sorted(
            {
                canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
                for ingredient in recipe.ingredients
            }
        )
    )


def recipe_id(recipe: Recipe) -> str:
    """Return a stable content ID suitable for beam-state cache keys."""

    ingredients: list[tuple[str, float, str]] = []
    for ingredient in recipe.ingredients:
        canonical = canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
        quantity, unit = normalize_quantity(ingredient.quantity, ingredient.unit)
        ingredients.append((canonical, round(quantity, 4), unit))
    payload = {
        "name": _plain_text(recipe.name),
        "servings": recipe.servings,
        "instructions": [_plain_text(step) for step in recipe.instructions],
        "ingredients": sorted(ingredients),
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return digest[:20]


def primary_ingredient(recipe: Recipe) -> str | None:
    """Select the most substantial protein/legume using taxonomy meal quantities."""

    ranked: list[tuple[float, int, str]] = []
    for index, ingredient in enumerate(recipe.ingredients):
        canonical = canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
        entry = get_taxonomy_entry(canonical)
        if entry is None or entry.category not in {
            IngredientCategory.PROTEIN,
            IngredientCategory.LEGUME,
        }:
            continue
        try:
            quantity, unit = normalize_quantity(ingredient.quantity, ingredient.unit)
        except (TypeError, ValueError):
            continue
        if unit != entry.expected_unit:
            continue
        expected = entry.typical_meal_quantity * recipe.servings / 4
        ratio = quantity / expected if expected else 0
        ranked.append((ratio, -index, canonical))
    if not ranked:
        return None
    primary = max(ranked)[2]
    # Closely related product canonicals can still describe the same dominant
    # meal pattern. Count falukorv and other sausage together for diversity so
    # a low price cannot produce three or more sausage dinners.
    return {"falukorv": "korv"}.get(primary, primary)


def carbohydrate_ingredient(recipe: Recipe) -> str | None:
    """Return the most substantial explicit carbohydrate in a candidate."""

    ranked: list[tuple[float, int, str]] = []
    for index, ingredient in enumerate(recipe.ingredients):
        canonical = canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
        entry = get_taxonomy_entry(canonical)
        if entry is None or entry.category != IngredientCategory.CARBOHYDRATE:
            continue
        try:
            quantity, unit = normalize_quantity(ingredient.quantity, ingredient.unit)
        except (TypeError, ValueError):
            continue
        if unit != entry.expected_unit:
            continue
        expected = entry.typical_meal_quantity * recipe.servings / 4
        ratio = quantity / expected if expected else 0
        ranked.append((ratio, -index, canonical))
    return max(ranked)[2] if ranked else None


def recipe_family(recipe: Recipe) -> str:
    """Return a conservative broad family for menu diversity constraints."""

    name = _plain_text(recipe.name)
    family_markers: tuple[tuple[str, tuple[str, ...]], ...] = (
        # Explicit dish-form words must win over carbohydrates mentioned later
        # in a generated name, e.g. "Chili ... nudlar" is still a chili.
        ("chili", ("chili",)),
        ("curry", ("curry",)),
        ("soppa", ("soppa",)),
        ("wok", ("wok",)),
        ("gryta", ("gryta", "stroganoff")),
        ("gratäng", ("gratäng", "gratang")),
        ("ugn", ("ugns", "ugnsp", "rostad")),
        # The generated family label should win over an ingredient mentioned
        # later in the name ("Middagspanna ... tortillas" is still a pan meal).
        ("panna", ("panna", "pytt")),
        ("wrap", ("wrap", "taco", "tortilla")),
        ("bowl", ("bowl",)),
        ("risrätt", ("risratt", "stekt ris")),
        ("nudelrätt", ("nudelratt", "nudlar")),
        ("potatisrätt", ("potatisratt", "stekt potatis")),
        ("pasta", ("pasta", "spaghetti", "makaron", "penne")),
        # Specific "stekt ris/potatis" families have already won above.
        ("husman", ("husman", "husmans", "stekt ")),
    )
    for family, markers in family_markers:
        if any(marker in name for marker in markers):
            return family

    profile = set(ingredient_profile(recipe))
    if "pasta" in profile:
        return "pasta"
    if "tortillas" in profile:
        return "wrap"
    if "nudlar" in profile:
        return "wok"
    if "potatis" in profile:
        return "panna"
    if "ris" in profile:
        return "gryta"
    return "övrigt"


def satisfies_diversity_constraints(
    recipes: Iterable[Recipe],
    *,
    max_same_primary_ingredient_meals: int = 2,
    max_same_recipe_family: int = 2,
    max_same_carbohydrate_meals: int = 3,
) -> bool:
    if (
        max_same_primary_ingredient_meals < 1
        or max_same_recipe_family < 1
        or max_same_carbohydrate_meals < 1
    ):
        raise ValueError("diversity limits must be at least one")
    recipe_list = list(recipes)
    primaries = Counter(
        primary for recipe in recipe_list if (primary := primary_ingredient(recipe))
    )
    families = Counter(recipe_family(recipe) for recipe in recipe_list)
    carbohydrates = Counter(
        carbohydrate for recipe in recipe_list if (carbohydrate := carbohydrate_ingredient(recipe))
    )
    return (
        max(primaries.values(), default=0) <= max_same_primary_ingredient_meals
        and max(families.values(), default=0) <= max_same_recipe_family
        and max(carbohydrates.values(), default=0) <= max_same_carbohydrate_meals
    )


def _candidate_unit(candidate: Any) -> str | None:
    def value(name: str, default: Any = None) -> Any:
        return (
            candidate.get(name, default)
            if isinstance(candidate, dict)
            else getattr(candidate, name, default)
        )

    sale_model = str(value("sale_model", "unknown"))
    if sale_model.endswith("sold_by_piece"):
        estimated_unit = value("estimated_piece_weight_unit")
        return str(estimated_unit) if value("estimated_piece_weight") else "st"
    if sale_model.endswith("sold_by_weight"):
        rate_unit = str(value("sale_unit") or value("comparison_unit") or "")
        if rate_unit.casefold() == "kg":
            return "g"
        if rate_unit.casefold() in {"l", "liter", "litre"}:
            return "ml"
    raw_unit = value("usable_unit") or value("package_unit")
    if not raw_unit:
        return None
    try:
        _, unit = normalize_quantity(1, str(raw_unit))
    except (TypeError, ValueError):
        return None
    return unit


def _normalise_candidate_map(
    candidates_by_name: Mapping[str, Sequence[Any]] | None,
) -> dict[str, tuple[Any, ...]] | None:
    if candidates_by_name is None:
        return None
    result: dict[str, tuple[Any, ...]] = {}
    for name, candidates in candidates_by_name.items():
        canonical = canonicalize_ingredient_name(name)
        result[canonical] = (*result.get(canonical, ()), *tuple(candidates))
    return result


class RecipeCandidateValidator:
    """Reject candidates that cannot become a sane, fully matched dinner."""

    def __init__(
        self,
        *,
        min_ingredients: int = 3,
        max_ingredients: int = 12,
        max_quantity_multiplier: float = 4.0,
        basket_auditor: BasketAuditor | None = None,
    ) -> None:
        if min_ingredients < 1 or max_ingredients < min_ingredients:
            raise ValueError("invalid ingredient count limits")
        if max_quantity_multiplier <= 1:
            raise ValueError("max_quantity_multiplier must exceed one")
        self.min_ingredients = min_ingredients
        self.max_ingredients = max_ingredients
        self.max_quantity_multiplier = max_quantity_multiplier
        self.basket_auditor = basket_auditor or BasketAuditor()

    def validate_recipe(
        self,
        recipe: Recipe,
        candidates_by_name: Mapping[str, Sequence[Any]] | None = None,
        *,
        servings: int = 4,
    ) -> tuple[str, ...]:
        reasons: list[str] = []
        if recipe.servings != servings:
            reasons.append("wrong_servings")
        if not self.min_ingredients <= len(recipe.ingredients) <= self.max_ingredients:
            reasons.append("unreasonable_ingredient_count")

        candidate_map = _normalise_candidate_map(candidates_by_name)
        role_ratios: Counter[IngredientCategory] = Counter()
        seen_dimensions: set[tuple[str, str]] = set()
        for ingredient in recipe.ingredients:
            canonical = canonicalize_ingredient_name(ingredient.canonical_name or ingredient.name)
            try:
                quantity, unit = normalize_quantity(ingredient.quantity, ingredient.unit)
            except (TypeError, ValueError):
                reasons.append(f"unsupported_quantity:{canonical}")
                continue
            dimension_key = (canonical, unit)
            if dimension_key in seen_dimensions:
                reasons.append(f"duplicate_ingredient:{canonical}")
            seen_dimensions.add(dimension_key)
            hard_limit = {"g": 8000.0, "ml": 5000.0, "st": 60.0}[unit]
            if quantity > hard_limit:
                reasons.append(f"unreasonable_quantity:{canonical}")
            # Pantry ingredients are explicitly free by policy. They still
            # undergo unit, duplicate and hard-quantity validation, but need
            # neither taxonomy roles nor a purchasable product candidate.
            if self.basket_auditor.is_pantry(canonical):
                continue

            entry = get_taxonomy_entry(canonical)
            if entry is None:
                reasons.append(f"outside_taxonomy:{canonical}")
                continue
            if unit != entry.expected_unit:
                reasons.append(f"wrong_unit:{canonical}")
                continue

            expected = entry.typical_meal_quantity * servings / 4
            if quantity > hard_limit or quantity > expected * self.max_quantity_multiplier:
                reasons.append(f"unreasonable_quantity:{canonical}")
            if expected > 0:
                role_ratios[entry.category] += quantity / expected

            if candidate_map is not None:
                candidates = candidate_map.get(canonical, ())
                if not candidates:
                    reasons.append(f"unmatchable:{canonical}")
                elif not any(_candidate_unit(candidate) == unit for candidate in candidates):
                    reasons.append(f"unmatchable_unit:{canonical}")

        substantial_primary = (
            role_ratios[IngredientCategory.PROTEIN] >= 0.35
            or role_ratios[IngredientCategory.LEGUME] >= 0.50
        )
        substantial_carbohydrate = (
            role_ratios[IngredientCategory.CARBOHYDRATE] >= 0.35
            or role_ratios[IngredientCategory.LEGUME] >= 0.65
        )
        substantial_vegetable = role_ratios[IngredientCategory.VEGETABLE] >= 0.25
        if not substantial_primary:
            reasons.append("missing_substantial_protein")
        if not substantial_carbohydrate:
            reasons.append("missing_substantial_carbohydrate")
        if not substantial_vegetable:
            reasons.append("missing_substantial_vegetable")
        return tuple(dict.fromkeys(reasons))

    def validate_and_prune(
        self,
        recipes: Iterable[Recipe],
        candidates_by_name: Mapping[str, Sequence[Any]] | None = None,
        *,
        servings: int = 4,
    ) -> CandidateValidationResult:
        valid: list[Recipe] = []
        rejected: list[RejectedRecipeCandidate] = []
        seen_names: set[str] = set()
        # Import locally: profile construction uses this module's ingredient roles.
        from app.services.recipe_profile import RecipeProfileBuilder

        seen_profiles: set[tuple[tuple[str, ...], tuple[str, str]]] = set()
        for recipe in recipes:
            reasons = list(
                self.validate_recipe(
                    recipe,
                    candidates_by_name,
                    servings=servings,
                )
            )
            name_key = _plain_text(recipe.name)
            profile = (ingredient_profile(recipe), RecipeProfileBuilder._structure(recipe))
            if name_key in seen_names:
                reasons.append("duplicate_name")
            if profile in seen_profiles:
                reasons.append("duplicate_profile")
            if reasons:
                rejected.append(
                    RejectedRecipeCandidate(
                        recipe=recipe,
                        reasons=tuple(dict.fromkeys(reasons)),
                    )
                )
                continue
            seen_names.add(name_key)
            seen_profiles.add(profile)
            valid.append(recipe)
        return CandidateValidationResult(valid_recipes=valid, rejected=rejected)


__all__ = [
    "CandidateValidationResult",
    "RecipeCandidateValidator",
    "RejectedRecipeCandidate",
    "carbohydrate_ingredient",
    "ingredient_profile",
    "primary_ingredient",
    "recipe_family",
    "recipe_id",
    "satisfies_diversity_constraints",
]
