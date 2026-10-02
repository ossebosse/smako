"""Rich canonical recipe profiles for deterministic culinary comparisons."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from app.models.recipe import Recipe
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.ingredient_taxonomy import IngredientCategory, get_taxonomy_entry
from app.services.recipe_candidate_validator import (
    carbohydrate_ingredient,
    primary_ingredient,
)
from app.services.recipe_similarity import RecipeSimilarityAnalyzer


def _authored_role(recipe, role):
    operands = [(i.quantity, i.canonical_name or i.name) for i in recipe.ingredients if i.role == role]
    return max(operands)[1] if operands else None


@dataclass(frozen=True, slots=True)
class RecipeProfile:
    """Canonical culinary structure extracted from one recipe."""

    recipe_name: str
    recipe_family: str
    cooking_method: str
    dish_form: str
    primary_protein: str | None
    primary_carb: str | None
    sauce_base: str | None
    vegetables: tuple[str, ...]
    major_ingredients: tuple[str, ...]
    ingredient_weights: tuple[tuple[str, float], ...]
    authored_base_id: str | None = None
    flavor_profile: tuple[str, ...] = ()
    side_description: str | None = None

    @property
    def ingredient_weight_map(self) -> dict[str, float]:
        """Return a fresh mapping suitable for weighted similarity functions."""

        return dict(self.ingredient_weights)


def _plain_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    unaccented = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", unaccented).strip()


def _dominant_in_category(
    recipe: Recipe,
    category: IngredientCategory,
    normalizer: IngredientNormalizer,
) -> str | None:
    ranked: list[tuple[float, str]] = []
    for ingredient in normalizer.normalize_and_aggregate([recipe]):
        entry = get_taxonomy_entry(ingredient.canonical_name)
        if entry is None or entry.category != category or ingredient.unit != entry.expected_unit:
            continue
        expected = entry.typical_meal_quantity * recipe.servings / 4
        ratio = ingredient.required_quantity / expected if expected > 0 else 0
        ranked.append((ratio, ingredient.canonical_name))
    return max(ranked)[1] if ranked else None


class RecipeProfileBuilder:
    """Build a stable culinary profile from recipe names, steps and taxonomy."""

    def __init__(
        self,
        normalizer: IngredientNormalizer | None = None,
        ingredient_similarity: RecipeSimilarityAnalyzer | None = None,
    ) -> None:
        self.normalizer = normalizer or IngredientNormalizer()
        self.ingredient_similarity = ingredient_similarity or RecipeSimilarityAnalyzer(
            normalizer=self.normalizer
        )

    @staticmethod
    def _structure(recipe: Recipe) -> tuple[str, str]:
        if getattr(recipe, "design", None) is not None:
            from app.services.recipe_library import validate_recipe_design
            validate_recipe_design(recipe)
            method = {"pan": "pan_cook", "pot": "simmer", "bake": "oven"}.get(recipe.design.method, recipe.design.method)
            return recipe.design.family, method
        # Names are display text. Only actual instructions establish technique
        # and serving structure; unsupported labels earn no diversity credit.
        text = _plain_text(" ".join(recipe.instructions))
        if ("couscous" in text and "lat svalla" in text
                and "vand ihop" in text and "sallad" in text):
            return "grynsallad", "rehydrate_and_assemble"
        if "gratinera" in text or "gratinering" in text:
            return "gratäng", "oven"
        if "ugn" in text and any(x in text for x in ("rosta", "225", "200", "baka")):
            return "ugn", "oven"
        if "soppa" in text and any(x in text for x in ("sjud", "koka", "puttra")):
            return "soppa", "simmer"
        if any(x in text for x in ("sjud", "puttra", "koka ihop")):
            return "gryta", "simmer"
        if "tortillas" in text and any(x in text for x in ("vik", "rulla", "fyll")):
            return "wrap", "pan_cook"
        if "hall komponenterna atskilda" in text:
            return "bowl", "pan_cook"
        if "pasta" in text and "sas" in text:
            return "pasta", "boil_and_sauce"
        if "woka" in text or "stek" in text or "fras" in text:
            carb = carbohydrate_ingredient(recipe)
            return ("potatisrätt" if carb == "potatis" else "panna"), "pan_cook"
        return "övrigt", "mixed"

    @staticmethod
    def _cooking_method(recipe: Recipe, family: str) -> str:
        return RecipeProfileBuilder._structure(recipe)[1]

    @staticmethod
    def _dish_form(family: str) -> str:
        return {
            "wrap": "wrap",
            "grynsallad": "grain_salad",
            "soppa": "soup",
            "gryta": "stew",
            "curry": "curry",
            "chili": "stew",
            "ugn": "oven_tray",
            "gratäng": "gratin",
            "wok": "stir_fry",
            "pasta": "pasta",
            "panna": "one_pan_hash",
            "bowl": "bowl",
            "risrätt": "rice_bowl",
            "nudelrätt": "noodle_bowl",
            "potatisrätt": "potato_plate",
            "husman": "traditional_plate",
        }.get(family, "plated_meal")

    def build(self, recipe: Recipe) -> RecipeProfile:
        family, method = self._structure(recipe)
        normalized = self.normalizer.normalize_and_aggregate([recipe])
        vegetables = tuple(
            sorted(
                ingredient.canonical_name
                for ingredient in normalized
                if (
                    (entry := get_taxonomy_entry(ingredient.canonical_name)) is not None
                    and entry.category == IngredientCategory.VEGETABLE
                )
            )
        )

        major: set[str] = set()
        for ingredient in normalized:
            entry = get_taxonomy_entry(ingredient.canonical_name)
            if entry is None or ingredient.unit != entry.expected_unit:
                # Unknown canonical ingredients remain visible rather than
                # disappearing from a culinary comparison.
                major.add(ingredient.canonical_name)
                continue
            expected = entry.typical_meal_quantity * recipe.servings / 4
            ratio = ingredient.required_quantity / expected if expected > 0 else 0
            if entry.category != IngredientCategory.FLAVOUR_SUPPORT and ratio >= 0.20:
                major.add(ingredient.canonical_name)

        weighted_profile = self.ingredient_similarity.build_profile(recipe)
        if recipe.design:
            major = {i.canonical_name or i.name for i in recipe.ingredients if i.role not in {"flavour", "cooking"}}
            vegetables = tuple(sorted(i.canonical_name or i.name for i in recipe.ingredients if i.role == "vegetable"))
        filtered_weights = tuple(
            sorted(
                (
                    canonical,
                    weight,
                )
                for canonical, weight in weighted_profile.weights.items()
                if canonical in major
            )
        )
        return RecipeProfile(
            recipe_name=recipe.name,
            recipe_family=family,
            cooking_method=method,
            dish_form=self._dish_form(family),
            primary_protein=recipe.design.primary_ingredient if recipe.design else primary_ingredient(recipe),
            primary_carb=_authored_role(recipe, "side") if recipe.design else carbohydrate_ingredient(recipe),
            sauce_base=_authored_role(recipe, "sauce") if recipe.design else _dominant_in_category(
                recipe,
                IngredientCategory.SAUCE_BASE,
                self.normalizer,
            ),
            vegetables=vegetables,
            major_ingredients=tuple(sorted(major)),
            ingredient_weights=filtered_weights,
            authored_base_id=recipe.design.base_id if recipe.design else None,
            flavor_profile=recipe.design.flavor_profile if recipe.design else (),
            side_description=recipe.design.side if recipe.design else None,
        )


def build_recipe_profile(recipe: Recipe) -> RecipeProfile:
    """Functional convenience wrapper for one recipe."""

    return RecipeProfileBuilder().build(recipe)


__all__ = ["RecipeProfile", "RecipeProfileBuilder", "build_recipe_profile"]
