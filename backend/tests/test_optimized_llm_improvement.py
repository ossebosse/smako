from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import pytest
from app.config import Settings
from app.models import DiversityMode, PlanRequest, Recipe, RecipeIngredient
from app.services.meal_plan_optimizer import MealPlanService
from app.services.recipe_candidate_generator import RecipeCandidateGenerator
from app.services.recipe_generator import MockRecipeGenerator


def _recipe(
    name: str,
    ingredients: list[tuple[str, str, float, str]],
) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(
                name=display_name,
                canonical_name=canonical,
                quantity=quantity,
                unit=unit,  # type: ignore[arg-type]
            )
            for canonical, display_name, quantity, unit in ingredients
        ],
        instructions=["Tillaga alla ingredienser och smaka av."],
    )


def _expensive_candidates() -> list[Recipe]:
    return [
        _recipe(
            "Nötfärspasta med paprika",
            [
                ("nötfärs", "nötfärs", 500, "g"),
                ("pasta", "pasta", 400, "g"),
                ("paprika", "paprika", 400, "g"),
                ("ost", "ost", 200, "g"),
            ],
        ),
        _recipe(
            "Nötfärsgryta med ris",
            [
                ("nötfärs", "nötfärs", 500, "g"),
                ("ris", "ris", 350, "g"),
                ("tomat", "tomat", 500, "g"),
                ("grädde", "grädde", 300, "ml"),
            ],
        ),
        _recipe(
            "Ugnsfisk med potatis",
            [
                ("fisk", "fisk", 600, "g"),
                ("potatis", "potatis", 1200, "g"),
                ("broccoli", "broccoli", 500, "g"),
                ("crème fraiche", "crème fraiche", 300, "ml"),
            ],
        ),
        _recipe(
            "Fiskwok med nudlar",
            [
                ("fisk", "fisk", 600, "g"),
                ("nudlar", "nudlar", 350, "g"),
                ("paprika", "paprika", 400, "g"),
                ("kokosmjölk", "kokosmjölk", 400, "ml"),
            ],
        ),
        _recipe(
            "Fläskpanna med potatis",
            [
                ("fläskkött", "fläskkött", 600, "g"),
                ("potatis", "potatis", 1200, "g"),
                ("tomat", "tomat", 500, "g"),
            ],
        ),
        _recipe(
            "Fläskgratäng med pasta",
            [
                ("fläskkött", "fläskkött", 600, "g"),
                ("pasta", "pasta", 400, "g"),
                ("broccoli", "broccoli", 500, "g"),
                ("ost", "ost", 200, "g"),
            ],
        ),
        _recipe(
            "Kycklingcurry med ris",
            [
                ("kyckling", "kyckling", 600, "g"),
                ("ris", "ris", 350, "g"),
                ("paprika", "paprika", 400, "g"),
                ("kokosmjölk", "kokosmjölk", 400, "ml"),
            ],
        ),
        _recipe(
            "Kycklingwok med nudlar",
            [
                ("kyckling", "kyckling", 600, "g"),
                ("nudlar", "nudlar", 350, "g"),
                ("tomat", "tomat", 500, "g"),
                ("grädde", "grädde", 300, "ml"),
            ],
        ),
        _recipe(
            "Blandfärsbowl med couscous",
            [
                ("blandfärs", "blandfärs", 500, "g"),
                ("couscous", "couscous", 350, "g"),
                ("broccoli", "broccoli", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Wrap med blandfärs och paprika",
            [
                ("blandfärs", "blandfärs", 500, "g"),
                ("tortillas", "tortillas", 8, "st"),
                ("paprika", "paprika", 400, "g"),
                ("crème fraiche", "crème fraiche", 300, "ml"),
            ],
        ),
    ]


def _cheap_candidates() -> list[Recipe]:
    return [
        _recipe(
            "Kikärtsgryta med potatis och vitkål",
            [
                ("kikärtor", "kikärtor", 760, "g"),
                ("potatis", "potatis", 1200, "g"),
                ("vitkål", "vitkål", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Kikärtschili med tortillas och morot",
            [
                ("kikärtor", "kikärtor", 760, "g"),
                ("tortillas", "tortillas", 8, "st"),
                ("morot", "morot", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Kidneybönsoppa med potatis och vitkål",
            [
                ("kidneybönor", "kidneybönor", 760, "g"),
                ("potatis", "potatis", 1200, "g"),
                ("vitkål", "vitkål", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Kidneybönbowl med couscous och morot",
            [
                ("kidneybönor", "kidneybönor", 760, "g"),
                ("couscous", "couscous", 350, "g"),
                ("morot", "morot", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Linspasta med morot",
            [
                ("linser", "linser", 300, "g"),
                ("pasta", "pasta", 400, "g"),
                ("morot", "morot", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Linscurry med ris och vitkål",
            [
                ("linser", "linser", 300, "g"),
                ("ris", "ris", 350, "g"),
                ("vitkål", "vitkål", 500, "g"),
                ("krossade tomater", "krossade tomater", 400, "g"),
            ],
        ),
        _recipe(
            "Ugnsfalukorv med potatis och vitkål",
            [
                ("falukorv", "falukorv", 600, "g"),
                ("potatis", "potatis", 1200, "g"),
                ("vitkål", "vitkål", 500, "g"),
            ],
        ),
        _recipe(
            "Falukorvspanna med couscous och morot",
            [
                ("falukorv", "falukorv", 600, "g"),
                ("couscous", "couscous", 350, "g"),
                ("morot", "morot", 500, "g"),
            ],
        ),
        _recipe(
            "Äggwok med ris och grönsaker",
            [
                ("ägg", "ägg", 8, "st"),
                ("ris", "ris", 350, "g"),
                ("frysta grönsaker", "frysta grönsaker", 500, "g"),
            ],
        ),
        _recipe(
            "Korvwrap med vitkål",
            [
                ("korv", "korv", 600, "g"),
                ("tortillas", "tortillas", 8, "st"),
                ("vitkål", "vitkål", 500, "g"),
            ],
        ),
    ]


class _ReplacementGenerator(RecipeCandidateGenerator):
    def __init__(
        self,
        initial: list[Recipe],
        replacements: list[Recipe],
    ) -> None:
        self.initial = initial
        self.replacements = replacements
        self.feedback: dict[str, Any] | None = None
        self.replacement_calls = 0
        self.anchor_recipe_names: list[str] | None = None

    def generate_candidates(
        self,
        economic_ingredients: Iterable[Any] | Any,
        count: int = 80,
        servings: int = 4,
    ) -> list[Recipe]:
        assert count == len(self.initial)
        assert servings == 4
        return self.initial

    def generate_replacement_candidates(
        self,
        current_recipes: list[Recipe],
        cost_feedback: dict[str, Any],
        economic_ingredients: Iterable[Any] | Any,
        count: int = 10,
        servings: int = 4,
    ) -> list[Recipe]:
        self.replacement_calls += 1
        self.feedback = cost_feedback
        self.anchor_recipe_names = [recipe.name for recipe in current_recipes]
        assert len(current_recipes) == 5
        assert count == 10
        assert servings == 4
        return self.replacements


async def _create_plan(
    monkeypatch: pytest.MonkeyPatch,
    generator: _ReplacementGenerator,
    *,
    api_key: str | None = "test-openai-key",
    diversity_mode: DiversityMode = DiversityMode.BALANCED,
    beam_width: int = 5,
):
    service = MealPlanService(
        Settings(
            price_provider="mock",
            meal_plan_strategy="optimized",
            openai_api_key=api_key,
        ),
        candidate_generator=generator,
    )
    # The legacy comparison is not part of this test and must not construct a
    # real OpenAI client just because the improvement gate has a fake key.
    monkeypatch.setattr(
        service,
        "_recipe_generator",
        lambda: (MockRecipeGenerator(), "mock-test-baseline"),
    )
    return await service.create_plan(
        PlanRequest(
            postal_code="22350",
            recipes=5,
            servings=4,
            max_stores=2,
            strategy="optimized",
            candidate_recipe_count=10,
            beam_width=beam_width,
            optimization_iterations=2,
            debug=True,
            diversity_mode=diversity_mode,
        )
    )


@pytest.mark.asyncio
async def test_optimized_llm_pass_accepts_only_deterministically_cheaper_menu(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = _ReplacementGenerator(
        _expensive_candidates(),
        _cheap_candidates(),
    )

    plan = await _create_plan(monkeypatch, generator)

    assert generator.replacement_calls == 1
    assert generator.feedback is not None
    assert generator.feedback["deterministic_basket_total"] > plan.optimized_basket.total
    assert generator.feedback["expensive_ingredients"]
    assert plan.optimization_iterations_attempted == 1
    assert plan.optimization_iterations_accepted == 1
    assert plan.debug_info is not None
    assert plan.debug_info["llm_improvement"]["accepted"] is True
    assert plan.debug_info["llm_improvement"]["deterministic_savings"] > 0


@pytest.mark.asyncio
async def test_optimized_llm_pass_rejects_more_expensive_replacements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = _ReplacementGenerator(
        _cheap_candidates(),
        _expensive_candidates(),
    )

    plan = await _create_plan(monkeypatch, generator)

    assert generator.replacement_calls == 1
    assert generator.feedback is not None
    assert plan.optimized_basket.total == generator.feedback["deterministic_basket_total"]
    assert plan.optimization_iterations_attempted == 1
    assert plan.optimization_iterations_accepted == 0
    assert plan.debug_info is not None
    assert plan.debug_info["llm_improvement"]["accepted"] is False


@pytest.mark.asyncio
async def test_optimized_llm_pass_is_disabled_without_openai_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = _ReplacementGenerator(
        _expensive_candidates(),
        _cheap_candidates(),
    )

    plan = await _create_plan(monkeypatch, generator, api_key=None)

    assert generator.replacement_calls == 0
    assert plan.optimization_iterations_attempted == 0
    assert plan.optimization_iterations_accepted == 0
    assert plan.debug_info is not None
    assert plan.debug_info["llm_improvement"] is None


@pytest.mark.asyncio
async def test_replacement_union_is_searched_identically_for_every_requested_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # These ten valid, cheap candidates deliberately share one culinary family.
    # CHEAPEST can select five, BALANCED at most two and VARIED at most one. If
    # the replacement union were searched only under the requested mode, the
    # returned CHEAPEST plan would therefore depend on that request field.
    replacements = [
        recipe.model_copy(update={"name": f"Pasta billig variant {index}"})
        for index, recipe in enumerate(_cheap_candidates(), start=1)
    ]
    snapshots: list[dict[str, tuple[float, tuple[str, ...]]]] = []
    anchors: list[tuple[str, ...]] = []

    for requested_mode in DiversityMode:
        generator = _ReplacementGenerator(_expensive_candidates(), replacements)
        plan = await _create_plan(
            monkeypatch,
            generator,
            diversity_mode=requested_mode,
            beam_width=20,
        )

        assert generator.anchor_recipe_names is not None
        anchors.append(tuple(generator.anchor_recipe_names))
        assert plan.optimization_iterations_attempted == 1
        assert plan.optimization_iterations_accepted == 1
        assert plan.recipes == plan.plans[requested_mode].recipes
        assert (
            plan.optimized_basket
            == plan.plans[requested_mode].optimized_basket
        )
        assert plan.debug_info is not None
        improvement = plan.debug_info["llm_improvement"]
        assert improvement["accepted"] is True
        assert set(improvement["mode_totals"]) == {
            mode.value for mode in DiversityMode
        }
        snapshots.append(
            {
                mode.value: (
                    option.optimized_basket.total,
                    tuple(sorted(recipe.name for recipe in option.recipes)),
                )
                for mode, option in plan.plans.items()
            }
        )

        cheapest_total = plan.plans[DiversityMode.CHEAPEST].optimized_basket.total
        for option in plan.plans.values():
            assert cheapest_total <= option.optimized_basket.total
            assert option.premium_vs_cheapest == pytest.approx(
                option.optimized_basket.total - cheapest_total,
                abs=0.01,
            )

    assert anchors[1:] == anchors[:-1]
    assert snapshots[1:] == snapshots[:-1]
