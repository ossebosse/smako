"""Preset factory for adjustable price-versus-variety policies."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.diversity import (
    DiversityMode,
    DiversityPolicy,
    DiversityPolicyOverrides,
)

VARIATION_POLICY_VERSION = "structural-menu-v2"

_MODE_DEFAULTS: dict[DiversityMode, dict[str, int | float | None]] = {
    DiversityMode.CHEAPEST: {
        "max_same_recipe_family": None,
        "max_same_primary_ingredient_meals": None,
        "max_same_carbohydrate_meals": None,
        "max_same_cooking_method_meals": None,
        "max_same_dish_form_meals": None,
        "max_pairwise_culinary_similarity": None,
    },
    DiversityMode.BALANCED: {
        "max_same_recipe_family": 2,
        "max_same_primary_ingredient_meals": 2,
        "max_same_carbohydrate_meals": 2,
        "max_same_cooking_method_meals": 2,
        "max_same_dish_form_meals": 2,
        "max_pairwise_culinary_similarity": 0.85,
    },
    DiversityMode.VARIED: {
        "max_same_recipe_family": 2,
        "max_same_primary_ingredient_meals": 2,
        "max_same_carbohydrate_meals": 2,
        "max_same_cooking_method_meals": 2,
        "max_same_dish_form_meals": 2,
        "max_pairwise_culinary_similarity": 0.85,
    },
}


def _coerce_mode(mode: DiversityMode | str) -> DiversityMode:
    if isinstance(mode, DiversityMode):
        return mode
    return DiversityMode(str(mode).strip().casefold())


def _override_values(
    overrides: DiversityPolicyOverrides | Mapping[str, Any] | None,
) -> dict[str, int | float | None]:
    if overrides is None:
        return {}
    parsed = (
        overrides
        if isinstance(overrides, DiversityPolicyOverrides)
        else DiversityPolicyOverrides.model_validate(dict(overrides))
    )
    # ``exclude_unset`` preserves preset values for absent request fields and
    # keeps an explicitly supplied None as an intentional disabled limit.
    return parsed.model_dump(exclude_unset=True)


class DiversityPolicyFactory:
    """Resolve a named preset and optional request overrides."""

    @staticmethod
    def create(
        mode: DiversityMode | str = DiversityMode.BALANCED,
        overrides: DiversityPolicyOverrides | Mapping[str, Any] | None = None,
    ) -> DiversityPolicy:
        resolved_mode = _coerce_mode(mode)
        values = {
            **_MODE_DEFAULTS[resolved_mode],
            **_override_values(overrides),
        }
        return DiversityPolicy(mode=resolved_mode, **values)


def create_diversity_policy(
    mode: DiversityMode | str = DiversityMode.BALANCED,
    overrides: DiversityPolicyOverrides | Mapping[str, Any] | None = None,
) -> DiversityPolicy:
    """Functional convenience wrapper around ``DiversityPolicyFactory``."""

    return DiversityPolicyFactory.create(mode, overrides)


__all__ = [
    "DiversityPolicyFactory",
    "create_diversity_policy",
]
