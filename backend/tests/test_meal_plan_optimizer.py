from __future__ import annotations

import pytest
from app.config import Settings
from app.errors import IncompleteBasketError
from app.models import PlanRequest, Recipe, RecipeIngredient, Store
from app.providers.mock import MockPriceProvider
from app.services.meal_plan_optimizer import MealPlanService
from app.services.recipe_generator import RecipeGenerator


def recipe(name: str, ingredients: list[tuple[str, float, str]]) -> Recipe:
    return Recipe(
        name=name,
        servings=4,
        ingredients=[
            RecipeIngredient(name=ingredient, quantity=quantity, unit=unit)
            for ingredient, quantity, unit in ingredients
        ],
        instructions=["Tillaga alla ingredienser och smaka av."],
    )


class ImprovingGenerator(RecipeGenerator):
    def __init__(self) -> None:
        self.initial = recipe(
            "Dyr färspanna",
            [("nötfärs", 500, "g"), ("potatis", 1000, "g")],
        )
        self.cheaper = recipe(
            "Billig linsgryta",
            [
                ("röda linser", 250, "g"),
                ("krossade tomater", 400, "g"),
                ("ris", 300, "g"),
            ],
        )
        self.feedback_total: float | None = None

    def generate_recipes(self, cheap_ingredients, count=5, servings=4):
        assert count == 1 and servings == 4
        return [self.initial]

    def improve_recipes(self, recipes, cost_feedback, cheap_ingredients, servings=4):
        self.feedback_total = cost_feedback["deterministic_basket_total"]
        return [self.cheaper]


def test_meal_optimizer_rejects_offers_only_store_before_product_search() -> None:
    store = Store(
        store_id="coop:offers",
        name="Coop erbjudanden",
        chain="coop",
        city="Lund",
        postal_code="22350",
        tier="offers_only",
    )

    with pytest.raises(IncompleteBasketError, match="endast offer-only-butiker"):
        MealPlanService._full_basket_stores([store])


def test_price_provider_fetch_timing_is_neutral_with_narrow_primat_compatibility() -> None:
    provider = MockPriceProvider()
    for source_name in ("own", "federated", "mock"):
        provider.source_name = source_name
        timings: dict[str, float] = {}

        MealPlanService._record_price_provider_fetch_timing(
            timings,
            provider,
            1.25,
        )

        assert timings == {"price_provider_fetch": 1.25}

    provider.source_name = "primat"
    timings = {}
    MealPlanService._record_price_provider_fetch_timing(timings, provider, 2.5)

    assert timings == {
        "price_provider_fetch": 2.5,
        "primat_fetch": 2.5,
    }


@pytest.mark.asyncio
async def test_second_pass_is_accepted_only_after_deterministic_repricing(monkeypatch) -> None:
    generator = ImprovingGenerator()
    service = MealPlanService(Settings(price_provider="mock"))
    monkeypatch.setattr(service, "_recipe_generator", lambda: (generator, "test-llm"))

    plan = await service.create_plan(
        PlanRequest(
            postal_code="22350",
            recipes=1,
            servings=4,
            max_stores=2,
            optimization_iterations=1,
        )
    )

    assert generator.feedback_total is not None
    assert plan.recipes[0].name == "Billig linsgryta"
    assert plan.optimization_iterations_attempted == 1
    assert plan.optimization_iterations_accepted == 1
    assert plan.optimized_basket.total < generator.feedback_total
