from __future__ import annotations

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.recipe_similarity import (
    RecipeSimilarityAnalyzer,
    RecipeSimilarityConstraints,
    analyze_recipe_plan,
    build_weighted_profile,
    compare_recipes,
    weighted_jaccard,
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


BASE = recipe(
    "Kycklingpasta med morot",
    [
        ("kyckling", 600, "g"),
        ("pasta", 400, "g"),
        ("morot", 500, "g"),
        ("krossade tomater", 600, "g"),
        ("vitlök", 30, "g"),
    ],
)

NEAR_DUPLICATE = recipe(
    "Tomatig kycklingpasta",
    [
        ("kyckling", 600, "g"),
        ("pasta", 400, "g"),
        ("morot", 500, "g"),
        ("krossade tomater", 600, "g"),
        ("sojasås", 60, "ml"),
    ],
)

DIFFERENT = recipe(
    "Tofugryta med ris",
    [
        ("tofu", 400, "g"),
        ("ris", 320, "g"),
        ("broccoli", 500, "g"),
        ("kokosmjölk", 400, "ml"),
    ],
)


def test_near_duplicate_is_rejected_at_default_threshold() -> None:
    result = compare_recipes(BASE, NEAR_DUPLICATE)

    assert result.score >= 0.70
    assert result.is_near_duplicate
    assert result.shared_ingredients == (
        "krossade tomater",
        "kyckling",
        "morot",
        "pasta",
    )


def test_structurally_different_recipe_is_accepted() -> None:
    result = compare_recipes(BASE, DIFFERENT)

    assert result.score < 0.70
    assert not result.is_near_duplicate


def test_plan_report_contains_all_pairs_maximum_and_rejection() -> None:
    report = analyze_recipe_plan([BASE, NEAR_DUPLICATE, DIFFERENT])

    assert len(report.pairs) == 3
    assert report.maximum_similarity == max(pair.score for pair in report.pairs)
    assert len(report.near_duplicate_pairs) == 1
    assert not report.is_valid


def test_primary_and_carbohydrate_changes_matter_more_than_flavour_change() -> None:
    flavour_change = NEAR_DUPLICATE
    primary_change = recipe(
        "Tofupasta med morot",
        [
            ("tofu", 400, "g"),
            ("pasta", 400, "g"),
            ("morot", 500, "g"),
            ("krossade tomater", 600, "g"),
            ("vitlök", 30, "g"),
        ],
    )

    assert compare_recipes(BASE, flavour_change).score > compare_recipes(
        BASE, primary_change
    ).score
    profile = build_weighted_profile(BASE)
    weights = profile.weights
    assert weights["kyckling"] > weights["vitlök"]
    assert weights["pasta"] > weights["vitlök"]
    assert weights["krossade tomater"] > weights["vitlök"]


def test_threshold_is_configurable_and_analyzer_validate_plan_returns_report() -> None:
    analyzer = RecipeSimilarityAnalyzer(
        RecipeSimilarityConstraints(near_duplicate_threshold=0.99)
    )
    report = analyzer.validate_plan([BASE, NEAR_DUPLICATE])

    assert report.is_valid
    assert report.maximum_similarity < 0.99


def test_weighted_jaccard_handles_empty_profiles_and_rejects_invalid_weights() -> None:
    assert weighted_jaccard({}, {}) == 1
    assert weighted_jaccard({"a": 2}, {"a": 1, "b": 1}) == pytest.approx(1 / 3)
    with pytest.raises(ValueError, match="non-negative"):
        weighted_jaccard({"a": -1}, {"a": 1})
