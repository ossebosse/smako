from __future__ import annotations

import pytest
from app.models import PlanRequest
from app.models.diversity import (
    DiversityMode,
    DiversityPolicyOverrides,
)
from app.services.diversity_policy import (
    DiversityPolicyFactory,
    create_diversity_policy,
)
from app.services.meal_plan_optimizer import MealPlanService
from pydantic import ValidationError


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (
            DiversityMode.CHEAPEST,
            (None, None, None, None, None, None),
        ),
        (
            DiversityMode.BALANCED,
            (2, 2, 2, 2, 2, 0.85),
        ),
        (
            DiversityMode.VARIED,
            (2, 2, 2, 2, 2, 0.85),
        ),
    ],
)
def test_mode_factory_resolves_documented_defaults(
    mode: DiversityMode,
    expected: tuple[int | float | None, ...],
) -> None:
    policy = create_diversity_policy(mode)

    assert (
        policy.max_same_recipe_family,
        policy.max_same_primary_ingredient_meals,
        policy.max_same_carbohydrate_meals,
        policy.max_same_cooking_method_meals,
        policy.max_same_dish_form_meals,
        policy.max_pairwise_culinary_similarity,
    ) == expected
    assert policy.reject_exact_recipe_duplicates is True
    assert policy.reject_duplicate_ingredient_profiles is True


def test_policy_is_json_serializable_with_stable_mode_value() -> None:
    policy = DiversityPolicyFactory.create(" BALANCED ")

    payload = policy.model_dump(mode="json")

    assert payload["mode"] == "balanced"
    assert payload["max_same_recipe_family"] == 2
    assert '"mode":"balanced"' in policy.model_dump_json()


def test_request_overrides_only_replace_explicit_fields() -> None:
    overrides = DiversityPolicyOverrides(
        max_same_recipe_family=3,
        max_pairwise_culinary_similarity=0.55,
    )

    policy = create_diversity_policy(DiversityMode.BALANCED, overrides)

    assert policy.max_same_recipe_family == 3
    assert policy.max_pairwise_culinary_similarity == 0.55
    assert policy.max_same_primary_ingredient_meals == 2
    assert policy.max_same_carbohydrate_meals == 2


def test_explicit_none_override_can_disable_one_preset_limit() -> None:
    policy = create_diversity_policy(
        DiversityMode.VARIED,
        DiversityPolicyOverrides(max_same_dish_form_meals=None),
    )

    assert policy.max_same_dish_form_meals is None
    assert policy.max_same_recipe_family == 2
    assert policy.max_pairwise_culinary_similarity == 0.85


def test_mapping_overrides_are_validated_and_constraint_ready() -> None:
    policy = create_diversity_policy(
        "cheapest",
        {
            "max_same_primary_ingredient_meals": 3,
            "max_same_cooking_method_meals": 2,
        },
    )

    assert policy.constraint_limit_values() == {
        "max_same_recipe_family": None,
        "max_same_primary_ingredient_meals": 3,
        "max_same_carbohydrate_meals": None,
        "max_same_cooking_method_meals": 2,
        "max_same_dish_form_meals": None,
        "max_pairwise_culinary_similarity": None,
    }


def test_invalid_mode_limit_and_unknown_override_are_rejected() -> None:
    with pytest.raises(ValueError):
        create_diversity_policy("unknown")
    with pytest.raises(ValidationError):
        create_diversity_policy(
            "balanced",
            {"max_same_recipe_family": 0},
        )
    with pytest.raises(ValidationError):
        create_diversity_policy(
            "balanced",
            {"unsupported_limit": 2},
        )


def test_serialized_legacy_defaults_do_not_rewrite_named_mode_presets() -> None:
    for requested_mode in DiversityMode:
        request = PlanRequest.model_validate(
            {
                "diversity_mode": requested_mode,
                "max_same_primary_ingredient_meals": 2,
                "max_same_recipe_family": 2,
                "max_same_carbohydrate_meals": 3,
                "max_pairwise_recipe_similarity": 0.70,
            }
        )

        policies = {
            mode: MealPlanService._diversity_policy_for(request, mode)
            for mode in DiversityMode
        }

        assert policies[DiversityMode.CHEAPEST] == create_diversity_policy(
            DiversityMode.CHEAPEST
        )
        assert policies[DiversityMode.BALANCED] == create_diversity_policy(
            DiversityMode.BALANCED
        ).model_copy(update={"target_recipe_count": 5})
        assert policies[DiversityMode.VARIED] == create_diversity_policy(
            DiversityMode.VARIED
        ).model_copy(update={"target_recipe_count": 5, "min_recipe_families": 4, "min_cooking_methods": 3})


def test_non_default_legacy_override_customizes_only_requested_mode() -> None:
    request = PlanRequest(
        diversity_mode=DiversityMode.BALANCED,
        max_same_recipe_family=3,
    )

    policies = {
        mode: MealPlanService._diversity_policy_for(request, mode)
        for mode in DiversityMode
    }

    assert policies[DiversityMode.BALANCED].max_same_recipe_family == 3
    assert policies[DiversityMode.CHEAPEST].max_same_recipe_family is None
    assert policies[DiversityMode.VARIED].max_same_recipe_family == 2
