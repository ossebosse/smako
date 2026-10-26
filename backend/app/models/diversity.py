"""Serializable diversity-mode configuration, independent of search code."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DiversityMode(StrEnum):
    """User-facing trade-off between pure price and menu variety."""

    CHEAPEST = "cheapest"
    BALANCED = "balanced"
    VARIED = "varied"


class DiversityPolicyOverrides(BaseModel):
    """Optional request-level changes layered on top of a mode preset.

    ``model_fields_set`` distinguishes an omitted field from an explicitly
    supplied ``None``. This lets a future request disable one preset limit
    without losing the ability to inherit all other defaults.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_same_recipe_family: int | None = Field(default=None, ge=1)
    max_same_primary_ingredient_meals: int | None = Field(default=None, ge=1)
    max_same_carbohydrate_meals: int | None = Field(default=None, ge=1)
    max_same_cooking_method_meals: int | None = Field(default=None, ge=1)
    max_same_dish_form_meals: int | None = Field(default=None, ge=1)
    max_pairwise_culinary_similarity: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )


VariationField = Literal["max_same_primary_ingredient_meals", "max_same_recipe_family",
    "max_same_carbohydrate_meals", "max_same_cooking_method_meals", "max_same_dish_form_meals",
    "max_pairwise_culinary_similarity", "max_pairwise_recipe_similarity"]


class VariationIntent(BaseModel):
    """New intent is explicit opt-in; absence keeps historical interpretation."""
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["explicit-over-default-v2"] = "explicit-over-default-v2"
    field_origins: dict[VariationField, Literal["default", "explicit", "unknown"]] = Field(max_length=7)


class DiversityPolicy(BaseModel):
    """Resolved limits ready for later translation to search constraints.

    The duplicate guards are always explicit. ``None`` on a limit means that
    dimension is intentionally unrestricted, which is how ``cheapest`` keeps
    only the basic duplicate protection.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    policy_version: str = "structural-menu-v2"
    min_recipe_families: int = Field(default=0, ge=0)
    min_cooking_methods: int = Field(default=0, ge=0)
    target_recipe_count: int = Field(default=0, ge=0)
    mode: DiversityMode
    reject_exact_recipe_duplicates: bool = True
    reject_duplicate_ingredient_profiles: bool = True
    max_same_recipe_family: int | None = Field(default=None, ge=1)
    max_same_primary_ingredient_meals: int | None = Field(default=None, ge=1)
    max_same_carbohydrate_meals: int | None = Field(default=None, ge=1)
    max_same_cooking_method_meals: int | None = Field(default=None, ge=1)
    max_same_dish_form_meals: int | None = Field(default=None, ge=1)
    max_pairwise_culinary_similarity: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    def constraint_limit_values(self) -> dict[str, int | float | None]:
        """Return only fields intended for a future constraint adapter."""

        return {
            "max_same_recipe_family": self.max_same_recipe_family,
            "max_same_primary_ingredient_meals": (
                self.max_same_primary_ingredient_meals
            ),
            "max_same_carbohydrate_meals": self.max_same_carbohydrate_meals,
            "max_same_cooking_method_meals": (
                self.max_same_cooking_method_meals
            ),
            "max_same_dish_form_meals": self.max_same_dish_form_meals,
            "max_pairwise_culinary_similarity": (
                self.max_pairwise_culinary_similarity
            ),
        }


__all__ = [
    "DiversityMode",
    "DiversityPolicy",
    "DiversityPolicyOverrides",
]
