from __future__ import annotations

import pytest
from app.models.recipe import Recipe, RecipeIngredient
from app.services.culinary_similarity import (
    CulinarySimilarity,
    CulinarySimilarityWeights,
    analyze_culinary_menu,
    compare_culinary_similarity,
)


def recipe(
    name: str,
    ingredients: list[tuple[str, float, str]],
    instructions: list[str],
) -> Recipe:
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
        instructions=instructions,
    )


TOFU_RICE = recipe(
    "Risgryta med tofu och lök",
    [("tofu", 400, "g"), ("ris", 320, "g"), ("gul lök", 300, "g")],
    ["Fräs löken.", "Låt allt sjuda tillsammans."],
)

SAUSAGE_RICE = recipe(
    "Risgryta med korv och lök",
    [("korv", 500, "g"), ("ris", 320, "g"), ("gul lök", 300, "g")],
    ["Fräs löken.", "Låt allt sjuda tillsammans."],
)

LENTIL_CURRY = recipe(
    "Linscurry med ris",
    [
        ("linser", 300, "g"),
        ("ris", 320, "g"),
        ("gul lök", 300, "g"),
        ("kokosmjölk", 400, "ml"),
    ],
    ["Låt currygrytan sjuda.", "Koka riset."],
)

SAUSAGE_TRAY = recipe(
    "Ugnsplåt med korv och potatis",
    [("korv", 500, "g"), ("potatis", 1200, "g"), ("morot", 500, "g")],
    ["Fördela på plåt.", "Tillaga i ugn vid 225 grader."],
)


def test_default_weights_match_requested_contract() -> None:
    weights = CulinarySimilarityWeights()

    assert weights.ingredient == 0.30
    assert weights.family == 0.20
    assert weights.cooking == 0.10
    assert weights.dish == 0.15
    assert weights.carb == 0.10
    assert weights.protein == 0.10
    assert weights.sauce == 0.05
    assert weights.total == pytest.approx(1.0)


def test_shared_rice_dish_structure_stays_high_when_protein_changes() -> None:
    pair = compare_culinary_similarity(TOFU_RICE, SAUSAGE_RICE)

    assert pair.score >= 0.65
    assert pair.is_high_similarity
    assert pair.components.family == 1
    assert pair.components.cooking == 1
    assert pair.components.dish == 1
    assert pair.components.carb == 1
    assert pair.components.protein == 0
    assert pair.shared_major_ingredients == ("gul lök", "ris")


def test_lentil_curry_and_sausage_oven_tray_have_low_similarity() -> None:
    pair = compare_culinary_similarity(LENTIL_CURRY, SAUSAGE_TRAY)

    assert pair.score < 0.20
    assert not pair.is_high_similarity
    assert pair.components.family == 0
    assert pair.components.cooking == 0
    assert pair.components.dish == 0
    assert pair.components.carb == 0
    assert pair.components.protein == 0
    assert pair.components.sauce == 0


def test_menu_report_contains_average_max_diversity_pairs_and_repetitions() -> None:
    report = analyze_culinary_menu([TOFU_RICE, SAUSAGE_RICE, SAUSAGE_TRAY])

    assert len(report.profiles) == 3
    assert len(report.pairs) == 3
    assert report.average_similarity == pytest.approx(sum(pair.score for pair in report.pairs) / 3)
    assert report.max_similarity == max(pair.score for pair in report.pairs)
    assert report.diversity_score == pytest.approx(1 - report.average_similarity)
    assert report.repetitions.family == {"gryta": 2}
    assert report.repetitions.protein == {"korv": 2}
    assert report.repetitions.carb == {"ris": 2}
    assert report.repetitions.dish == {"stew": 2}
    assert report.repetitions.cooking == {"simmer": 2}


def test_weights_and_high_similarity_threshold_are_configurable() -> None:
    family_only = CulinarySimilarityWeights(
        ingredient=0,
        family=1,
        cooking=0,
        dish=0,
        carb=0,
        protein=0,
        sauce=0,
    )
    similarity = CulinarySimilarity(
        weights=family_only,
        high_similarity_threshold=1,
    )

    same_family = similarity.compare_recipes(TOFU_RICE, SAUSAGE_RICE)
    different_family = similarity.compare_recipes(LENTIL_CURRY, SAUSAGE_TRAY)
    assert same_family.score == 1
    assert same_family.is_high_similarity
    assert different_family.score == 0
    assert not different_family.is_high_similarity


def test_invalid_weight_and_threshold_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match="at least one"):
        CulinarySimilarityWeights(
            ingredient=0,
            family=0,
            cooking=0,
            dish=0,
            carb=0,
            protein=0,
            sauce=0,
        )
    with pytest.raises(ValueError, match="between zero and one"):
        CulinarySimilarity(high_similarity_threshold=1.1)
