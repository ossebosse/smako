from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from app.models.recipe import Recipe, RecipeCollection, RecipeIngredient
from app.services.ingredient_taxonomy import INGREDIENT_TAXONOMY
from app.services.recipe_candidate_generator import (
    DeterministicRecipeCandidateGenerator,
    OpenAIRecipeCandidateGenerator,
)
from app.services.recipe_candidate_validator import (
    ingredient_profile,
    primary_ingredient,
    recipe_family,
)


def full_pool() -> list[dict[str, str]]:
    return [{"canonical": entry.canonical} for entry in INGREDIENT_TAXONOMY]


def test_deterministic_generator_creates_configurable_distinct_candidates() -> None:
    recipes = DeterministicRecipeCandidateGenerator().generate_candidates(
        full_pool(), count=80, servings=4
    )

    assert len(recipes) == 80
    assert len({recipe.name.casefold() for recipe in recipes}) == 80
    assert len({ingredient_profile(recipe) for recipe in recipes}) == 80
    assert all(recipe.servings == 4 for recipe in recipes)
    assert all(
        ingredient.canonical_name
        for recipe in recipes
        for ingredient in recipe.ingredients
    )
    assert len({primary_ingredient(recipe) for recipe in recipes}) >= 8


def test_deterministic_generator_stratifies_300_naturally_named_candidates() -> None:
    generator = DeterministicRecipeCandidateGenerator()

    recipes = generator.generate_candidates(full_pool(), count=300, servings=4)

    expected_families = {
        "pasta",
        "risrätt",
        "potatisrätt",
        "gryta",
        "curry",
        "soppa",
        "ugn",
        "gratäng",
        "wok",
        "nudelrätt",
        "wrap",
        "panna",
        "husman",
        "bowl",
        "chili",
    }
    assert len(recipes) == 300
    assert len({recipe.name.casefold() for recipe in recipes}) == 300
    assert len({ingredient_profile(recipe) for recipe in recipes}) == 300
    assert set(generator.batch_statistics) == expected_families
    assert {recipe_family(recipe) for recipe in recipes} == expected_families - {"curry", "chili"}
    assert generator.batch_statistics == {
        family: 20 for family in generator.batch_statistics
    }
    assert not any(
        re.match(r"^(risrätt|nudelrätt|potatisrätt) med\b", recipe.name.casefold())
        for recipe in recipes
    )
    assert any(recipe.name.startswith("Stekt ris med ") for recipe in recipes)
    assert any(recipe.name.startswith("Nudlar med ") for recipe in recipes)
    assert any(recipe.name.startswith("Stekt potatis med ") for recipe in recipes)


def test_deterministic_generator_scales_all_quantities_with_servings() -> None:
    generator = DeterministicRecipeCandidateGenerator()
    four = generator.generate_candidates(full_pool(), count=1, servings=4)[0]
    two = generator.generate_candidates(full_pool(), count=1, servings=2)[0]

    assert two.name == four.name
    assert [ingredient.quantity for ingredient in two.ingredients] == [
        ingredient.quantity / 2 for ingredient in four.ingredients
    ]


def test_deterministic_instructions_use_requested_servings() -> None:
    recipes = DeterministicRecipeCandidateGenerator().generate_candidates(
        full_pool(), count=30, servings=2
    )
    instructions = [step for recipe in recipes for step in recipe.instructions]

    assert all("fyra portioner" not in step.casefold() for step in instructions)
    assert any("2 portioner" in step for step in instructions)


def test_economic_pool_order_influences_deterministic_candidates() -> None:
    generator = DeterministicRecipeCandidateGenerator()

    forward = generator.generate_candidates(full_pool(), count=1)[0]
    reverse = generator.generate_candidates(list(reversed(full_pool())), count=1)[0]

    assert primary_ingredient(forward) != primary_ingredient(reverse)


def test_deterministic_generator_requires_all_structural_roles() -> None:
    with pytest.raises(ValueError, match="protein/legume, carbohydrate and vegetable"):
        DeterministicRecipeCandidateGenerator().generate_candidates(
            [{"canonical": "potatis"}, {"canonical": "morot"}],
            count=1,
        )


class _FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.next_index = 1

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        user_prompt = kwargs["input"][1]["content"]
        match = re.search(r"Skapa exakt (\d+) distinkta", user_prompt)
        assert match is not None
        count = int(match.group(1))
        recipes: list[Recipe] = []
        for _ in range(count):
            index = self.next_index
            self.next_index += 1
            recipes.append(
                Recipe(
                    name=f"Kandidaträtt {index}",
                    servings=4,
                    ingredients=[
                        RecipeIngredient(
                            name="kyckling",
                            canonical_name="kyckling",
                            quantity=600,
                            unit="g",
                        ),
                        RecipeIngredient(
                            name="potatis",
                            canonical_name="potatis",
                            quantity=1200,
                            unit="g",
                        ),
                        RecipeIngredient(
                            name="morot",
                            canonical_name="morot",
                            quantity=500,
                            unit="g",
                        ),
                    ],
                    instructions=["Tillaga allt."],
                )
            )
        return SimpleNamespace(output_parsed=RecipeCollection(recipes=recipes))


def test_openai_generator_uses_bounded_structured_output_batches() -> None:
    responses = _FakeResponses()
    client = SimpleNamespace(responses=responses)
    generator = OpenAIRecipeCandidateGenerator(
        None,
        "test-model",
        batch_size=20,
        client=client,
    )

    recipes = generator.generate_candidates(
        [
            {"canonical": "kyckling", "best_local_unit_price": 70.0},
            {"canonical": "potatis", "best_local_unit_price": 10.0},
            {"canonical": "morot", "best_local_unit_price": 12.0},
        ],
        count=45,
        servings=4,
    )

    assert len(recipes) == 45
    assert len(responses.calls) == 5
    assert [
        int(re.search(r"Skapa exakt (\d+) distinkta", call["input"][1]["content"])[1])
        for call in responses.calls
    ] == [10, 10, 7, 9, 9]
    assert generator.batch_statistics == {
        "lowest_cost": 10,
        "cheap_protein": 10,
        "vegetarian": 7,
        "weekday": 9,
        "reuse": 9,
    }
    assert all(
        "Sökbias för denna batch" in call["input"][1]["content"]
        for call in responses.calls
    )
    assert all(
        "Rättformsbias" in call["input"][1]["content"]
        for call in responses.calls
    )
    prompted_forms = " ".join(
        call["input"][1]["content"] for call in responses.calls
    )
    for dish_form in (
        "gryta",
        "soppa",
        "chili",
        "husmanskost/tallriksrätt",
        "ugnsplåt",
        "wok",
        "curry",
        "gratäng",
        "bowl",
        "pastarätt",
        "risrätt",
        "potatisrätt",
        "nudelrätt",
        "wraps/tacos",
        "pytt eller stekpannerätt",
    ):
        assert dish_form in prompted_forms
    assert all(call["text_format"] is RecipeCollection for call in responses.calls)
    assert all("aldrig hitta på" in call["input"][0]["content"] for call in responses.calls)


def test_openai_replacement_candidates_use_structured_backend_cost_feedback() -> None:
    responses = _FakeResponses()
    generator = OpenAIRecipeCandidateGenerator(
        None,
        "test-model",
        client=SimpleNamespace(responses=responses),
    )
    current = Recipe(
        name="Nuvarande rätt",
        servings=4,
        ingredients=[
            RecipeIngredient(
                name="kyckling",
                canonical_name="kyckling",
                quantity=600,
                unit="g",
            ),
            RecipeIngredient(
                name="potatis",
                canonical_name="potatis",
                quantity=1200,
                unit="g",
            ),
            RecipeIngredient(
                name="morot",
                canonical_name="morot",
                quantity=500,
                unit="g",
            ),
        ],
        instructions=["Tillaga allt."],
    )

    recipes = generator.generate_replacement_candidates(
        [current],
        {
            "deterministic_basket_total": 199.9,
            "expensive_ingredients": [{"ingredient": "kyckling"}],
        },
        [
            {"canonical": "kyckling", "best_local_unit_price": 70.0},
            {"canonical": "potatis", "best_local_unit_price": 10.0},
            {"canonical": "morot", "best_local_unit_price": 12.0},
        ],
        count=10,
        servings=4,
    )

    assert len(recipes) == 10
    assert len(responses.calls) == 1
    call = responses.calls[0]
    assert call["text_format"] is RecipeCollection
    assert "Backendens pris- och korgdata är fakta" in call["input"][0]["content"]
    assert "Returnera inga priser" in call["input"][1]["content"]
    assert '"deterministic_basket_total":199.9' in call["input"][1]["content"]
