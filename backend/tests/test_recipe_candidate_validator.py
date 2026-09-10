from __future__ import annotations

from types import SimpleNamespace

from app.models.recipe import Recipe, RecipeIngredient
from app.services.ingredient_taxonomy import INGREDIENT_TAXONOMY
from app.services.recipe_candidate_validator import (
    RecipeCandidateValidator,
    carbohydrate_ingredient,
    ingredient_profile,
    primary_ingredient,
    recipe_family,
    recipe_id,
    satisfies_diversity_constraints,
)


def recipe(
    name: str,
    ingredients: list[tuple[str, float, str]],
    *,
    servings: int = 4,
) -> Recipe:
    return Recipe(
        name=name,
        servings=servings,
        ingredients=[
            RecipeIngredient(
                name=canonical,
                canonical_name=canonical,
                quantity=quantity,
                unit=unit,
            )
            for canonical, quantity, unit in ingredients
        ],
        instructions=["Tillaga alla listade ingredienser."],
    )


def candidates_by_name():
    return {
        entry.canonical: [SimpleNamespace(package_unit=entry.expected_unit)]
        for entry in INGREDIENT_TAXONOMY
    }


def valid_chicken_dinner(name: str = "Kycklinggryta") -> Recipe:
    return recipe(
        name,
        [
            ("kyckling", 600, "g"),
            ("potatis", 1200, "g"),
            ("morot", 500, "g"),
        ],
    )


def test_validator_accepts_sane_fully_matchable_candidate() -> None:
    result = RecipeCandidateValidator().validate_and_prune(
        [valid_chicken_dinner()], candidates_by_name()
    )

    assert result.generated_count == 1
    assert result.valid_count == 1
    assert result.rejected_count == 0


def test_explicit_pantry_items_need_no_product_but_other_extras_do() -> None:
    candidate = recipe(
        "Kycklinggryta med skafferi",
        [
            ("kyckling", 600, "g"),
            ("potatis", 1200, "g"),
            ("morot", 500, "g"),
            ("salt", 5, "g"),
            ("crème fraiche", 200, "ml"),
        ],
    )
    matches = candidates_by_name()
    matches.pop("crème fraiche")

    reasons = RecipeCandidateValidator().validate_recipe(candidate, matches)

    assert "outside_taxonomy:salt" not in reasons
    assert "unmatchable:salt" not in reasons
    assert "unmatchable:crème fraiche" in reasons


def test_validator_rejects_unmatchable_and_outside_taxonomy_ingredients() -> None:
    candidate = recipe(
        "Specialgryta",
        [
            ("kyckling", 600, "g"),
            ("potatis", 1200, "g"),
            ("morot", 500, "g"),
            ("saffran", 1, "g"),
        ],
    )
    matches = candidates_by_name()
    matches.pop("morot")

    result = RecipeCandidateValidator().validate_and_prune([candidate], matches)

    reasons = result.rejected[0].reasons
    assert "unmatchable:morot" in reasons
    assert "outside_taxonomy:saffran" in reasons


def test_validator_rejects_unreasonable_amounts_and_incomplete_meals() -> None:
    unreasonable = recipe(
        "Potatisberg",
        [("ägg", 1, "st"), ("potatis", 6000, "g"), ("morot", 50, "g")],
    )

    reasons = RecipeCandidateValidator().validate_recipe(
        unreasonable, candidates_by_name()
    )

    assert "unreasonable_quantity:potatis" in reasons
    assert "missing_substantial_protein" in reasons
    assert "missing_substantial_vegetable" in reasons


def test_legumes_can_supply_both_primary_and_substantial_carbohydrate() -> None:
    dinner = recipe(
        "Linsgryta",
        [("linser", 300, "g"), ("morot", 500, "g"), ("krossade tomater", 600, "g")],
    )

    assert RecipeCandidateValidator().validate_recipe(
        dinner, candidates_by_name()
    ) == ()


def test_duplicate_name_and_ingredient_profile_are_pruned() -> None:
    first = valid_chicken_dinner("Kycklinggryta")
    same_name = recipe(
        "Kycklinggryta",
        [("ägg", 8, "st"), ("ris", 320, "g"), ("broccoli", 400, "g")],
    )
    same_profile = valid_chicken_dinner("Kycklingpanna")

    result = RecipeCandidateValidator().validate_and_prune(
        [first, same_name, same_profile], candidates_by_name()
    )

    assert result.valid_recipes == [first]
    assert "duplicate_name" in result.rejected[0].reasons
    assert "duplicate_profile" in result.rejected[1].reasons


def test_family_and_primary_helpers_support_diversity_constraint() -> None:
    recipes = [
        recipe(
            f"Pasta variant {index}",
            [(primary, 500, "g"), ("pasta", 400, "g"), (vegetable, 400, "g")],
        )
        for index, (primary, vegetable) in enumerate(
            [("kyckling", "morot"), ("fisk", "broccoli"), ("tofu", "paprika")],
            start=1,
        )
    ]

    assert recipe_family(recipes[0]) == "pasta"
    assert primary_ingredient(recipes[0]) == "kyckling"
    assert not satisfies_diversity_constraints(recipes, max_same_recipe_family=2)
    assert satisfies_diversity_constraints(recipes, max_same_recipe_family=3)


def test_diversity_groups_sausage_types_and_prefers_named_recipe_family() -> None:
    sausage_recipes = [
        recipe(
            "Middagspanna med korv och tortillas",
            [(primary, 500, "g"), ("tortillas", 8, "st"), ("morot", 500, "g")],
        )
        for primary in ("korv", "falukorv", "korv")
    ]

    assert recipe_family(sausage_recipes[0]) == "panna"
    assert primary_ingredient(sausage_recipes[1]) == "korv"
    assert not satisfies_diversity_constraints(
        sausage_recipes,
        max_same_primary_ingredient_meals=2,
        max_same_recipe_family=3,
    )


def test_explicit_dish_family_wins_over_carbohydrate_words_in_name() -> None:
    cases = {
        "Chili på linser med nudlar och morot": "chili",
        "Curry med linser, pasta och vitkål": "curry",
        "Matig soppa med ägg, pasta och morot": "soppa",
        "Wok med tofu, nudlar och morot": "wok",
        "Mustig gryta på korv med pasta och lök": "gryta",
        "Ugnsplåt med tofu, pasta och broccoli": "ugn",
        "Pastagratäng med korv och broccoli": "gratäng",
        "Tofupanna med nudlar och morot": "panna",
        "Tacos med tofu och morot": "wrap",
        "Bowl med linser, pasta och vitkål": "bowl",
        "Stekt ris med tofu och lök": "risrätt",
        "Nudlar med tofu och morot": "nudelrätt",
        "Stekt potatis med korv och vitkål": "potatisrätt",
        "Pasta med tofu och broccoli": "pasta",
        "Stekt falukorv med ris och morot": "husman",
    }

    for name, expected_family in cases.items():
        candidate = recipe(
            name,
            [("tofu", 600, "g"), ("pasta", 400, "g"), ("morot", 500, "g")],
        )
        assert recipe_family(candidate) == expected_family


def test_diversity_limits_repeated_main_carbohydrate() -> None:
    recipes = [
        recipe(
            f"Familj {index}",
            [(primary, 500, "g"), ("tortillas", 8, "st"), (vegetable, 500, "g")],
        )
        for index, (primary, vegetable) in enumerate(
            [
                ("kyckling", "morot"),
                ("tofu", "broccoli"),
                ("linser", "paprika"),
                ("ägg", "vitkål"),
            ],
            start=1,
        )
    ]

    assert carbohydrate_ingredient(recipes[0]) == "tortillas"
    assert not satisfies_diversity_constraints(
        recipes,
        max_same_primary_ingredient_meals=2,
        max_same_recipe_family=5,
        max_same_carbohydrate_meals=3,
    )


def test_recipe_id_is_stable_but_sensitive_to_quantity() -> None:
    original = valid_chicken_dinner()
    changed = recipe(
        "Kycklinggryta",
        [("kyckling", 500, "g"), ("potatis", 1200, "g"), ("morot", 500, "g")],
    )

    assert recipe_id(original) == recipe_id(original.model_copy(deep=True))
    assert recipe_id(original) != recipe_id(changed)
    assert ingredient_profile(original) == ingredient_profile(changed)
