from __future__ import annotations

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.ingredient_taxonomy import TAXONOMY_BY_CANONICAL
from app.services.nutrition_validator import (
    _NUTRITION_REFERENCES,
    EstimateConfidence,
    MealQualityConstraints,
    NutritionValidator,
    validate_recipe,
    validate_recipes,
)


def recipe(name: str, ingredients: list[tuple[str, float, str]]) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=canonical,
                canonical_name=canonical,
                quantity=quantity,
                unit=unit,
            )
            for canonical, quantity, unit in ingredients
        ],
        instructions=["Tillaga alla ingredienser."],
    )


def test_reference_table_covers_current_taxonomy_and_all_base_units() -> None:
    assert set(_NUTRITION_REFERENCES) == set(TAXONOMY_BY_CANONICAL)
    assert {reference.expected_unit for reference in _NUTRITION_REFERENCES.values()} == {
        "g",
        "ml",
        "st",
    }
    assert _NUTRITION_REFERENCES["ägg"].piece_weight_g
    assert _NUTRITION_REFERENCES["tortillas"].piece_weight_g


def test_obviously_incomplete_meal_is_rejected_with_specific_reasons() -> None:
    result = validate_recipe(
        recipe(
            "Liten pastatallrik",
            [("pasta", 120, "g"), ("tomat", 100, "g")],
        )
    )

    assert not result.is_valid
    assert "kcal_per_portion_below_minimum" in result.violations
    assert "protein_per_portion_below_minimum" in result.violations
    assert "vegetable_per_portion_below_minimum" in result.violations
    assert result.estimate.is_estimate


def test_normal_chicken_pasta_meal_passes_default_safeguards() -> None:
    result = validate_recipe(
        recipe(
            "Kycklingpasta med morot",
            [
                ("kyckling", 600, "g"),
                ("pasta", 400, "g"),
                ("morot", 500, "g"),
                ("krossade tomater", 600, "g"),
            ],
        )
    )

    assert result.is_valid
    assert result.violations == ()
    assert 450 <= result.estimate.kcal_per_portion <= 900
    assert result.estimate.protein_g_per_portion >= 18
    assert result.estimate.vegetable_g_per_portion == 125
    assert result.estimate.confidence == EstimateConfidence.HIGH


def test_piece_and_volume_references_are_estimated_transparently() -> None:
    result = NutritionValidator(
        MealQualityConstraints(
            min_kcal_per_portion=0,
            max_kcal_per_portion=2000,
            min_protein_g_per_portion=0,
            min_vegetable_g_per_portion=0,
        )
    ).validate_recipe(
        recipe(
            "Äggwrap med sås",
            [
                ("ägg", 8, "st"),
                ("tortillas", 8, "st"),
                ("crème fraiche", 250, "ml"),
                ("morot", 500, "g"),
            ],
        )
    )

    assert result.is_valid
    assert result.estimate.total_kcal > 0
    assert result.estimate.piece_weight_assumptions == (
        "tortillas:40g/st",
        "ägg:55g/st",
    )
    assert result.estimate.confidence_score < 0.9


def test_unknown_important_ingredient_lowers_confidence_and_batch_preserves_order() -> None:
    unknown = recipe(
        "Okänd rätt",
        [("mystiskt protein", 600, "g"), ("pasta", 400, "g"), ("morot", 500, "g")],
    )
    normal = recipe(
        "Normal rätt",
        [("tofu", 400, "g"), ("ris", 320, "g"), ("broccoli", 500, "g")],
    )

    report = validate_recipes([unknown, normal])

    assert [result.recipe_name for result in report.results] == ["Okänd rätt", "Normal rätt"]
    assert report.rejected_count == 1
    assert report.valid_count == 1
    assert "mystiskt protein" in report.results[0].estimate.unestimated_ingredients
    assert "estimate_confidence_below_minimum" in report.results[0].violations


@pytest.mark.parametrize(
    "constraints",
    [
        MealQualityConstraints(min_kcal_per_portion=500, max_kcal_per_portion=501),
        MealQualityConstraints(min_confidence_score=1),
    ],
)
def test_constraints_are_configurable(constraints: MealQualityConstraints) -> None:
    assert NutritionValidator(constraints).constraints is constraints

