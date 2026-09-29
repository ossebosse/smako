"""Real retained Lidl offer in an ordinary warm PersonalPlanner meal."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.models.recipe import Recipe
from app.services.lidl_product_facts import reviewed_facts
from app.services.official_product_facts import declared_facts
from app.services.personal_planner import PersonalPlanner
from app.services.personal_policy import PolicyConflict
from app.services.plan_store import PlanStore
from app.services.price_universe_runtime import PreparedPriceUniverseArtifact
from app.services.recipe_preparation import adapt


def case():
    root = Path(__file__).parents[2]
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        (root / "reports/purchase-planning-20260925/final/prepared-1281-second.json").read_bytes()
    ).restore()
    facts = {
        **reviewed_facts(prepared.universe.products),
        **declared_facts(prepared.universe.products),
    }
    cheese = next(
        p for p in prepared.universe.products if p.name == "Hushållsost" and p.chain == "lidl"
    )
    original = Recipe.model_validate(
        {
            "name": "Varm ostsmörgås",
            "servings": 1,
            "ingredients": [
                {"name": "bröd", "quantity": 100, "unit": "g"},
                {"name": "ost", "quantity": 100, "unit": "g"},
            ],
            "instructions": ["Värm smörgåsen."],
        }
    )
    recipe = adapt(original, "cheese_toast", origin="explicit_adaptation")
    request = PlanRequest.model_validate(
        {
            "recipes": 0,
            "max_stores": 1,
            "allowed_store_ids": [cheese.store_id],
            "memberships": {"lidl": True},
            "purchase_planning_mode": "estimated",
            "personal": {
                "allow_nutrition_estimates": True,
                "meals": [
                    {
                        "meal_type": "breakfast",
                        "count": 1,
                        "servings": 1,
                        "limits": {"min_protein_g": 30},
                    }
                ],
                "slots": [
                    {
                        "id": "breakfast-1",
                        "day": 1,
                        "meal_type": "breakfast",
                        "recipe": recipe.model_dump(mode="json"),
                    }
                ],
            },
        }
    )
    return prepared, facts, cheese, request


def test_real_warm_ingredient_plan_roundtrip(tmp_path):
    prepared, facts, cheese, request = case()
    result = PersonalPlanner(
        request,
        Settings(price_provider="mock"),
        prepared,
        {"revision": 0, "items": [], "reservations": {}, "events": {}},
        facts=facts,
        now=datetime(2026, 9, 24, 21, 16, tzinfo=UTC),
    ).create()
    bought = next(
        i
        for s in result.optimized_basket.stores
        for i in s.items
        if i.product_id == cheese.product_id
    )
    assert (
        bought.total_price == 153.78
        and bought.required_quantity == 100
        and bought.purchased_quantity == 2200
    )
    nutrition = result.personal.checks["nutrition"][0]
    assert nutrition["status"] == "ESTIMATED" and nutrition["values"]["protein_g"] == pytest.approx(
        33.8
    )
    assert nutrition["calculation_basis"]["per_100g_cooked"] == "NOT_AVAILABLE"
    assert all(
        s["used_edible_quantity"] == 100 and s["cooked_quantity_g"] is None
        for s in nutrition["sources"]
    )
    assert result.personal.checks["checkout_audit"]["passed"]
    store = PlanStore(tmp_path / "plans.sqlite")
    saved = store.create(request, result, owner_actor_hash="a" * 64)
    reread = PlanStore(tmp_path / "plans.sqlite").get_owned(
        saved.plan_id, owner_actor_hash="a" * 64
    )
    assert reread.plan == result and reread.request == request


@pytest.mark.parametrize("gate", ["opt-in", "allergy", "cooked-weight"])
def test_warm_preparation_never_bypasses_independent_guards(gate):
    prepared, facts, _, request = case()
    if gate == "opt-in":
        request.personal.allow_nutrition_estimates = False
    if gate == "allergy":
        request.personal.profile.allergies = ["mjölk"]
    if gate == "cooked-weight":
        request.personal.meals[0].limits.min_weight_g = 180
    with pytest.raises(PolicyConflict):
        PersonalPlanner(
            request,
            Settings(price_provider="mock"),
            prepared,
            {"revision": 0, "items": [], "reservations": {}, "events": {}},
            facts=facts,
            now=datetime(2026, 9, 24, 21, 16, tzinfo=UTC),
        ).create()
