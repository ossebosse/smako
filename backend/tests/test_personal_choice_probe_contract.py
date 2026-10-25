"""Frozen performance requests retain the UI's omitted-default semantics."""
import json
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services.complete_recipes import prepare_request


def test_frozen_payloads_keep_real_ui_fields_and_no_explicit_legacy_diversity_defaults():
    path = Path(__file__).parents[2] / "docs/reviews/personal-choice-latency-20261025/requests.json"
    cases = json.loads(path.read_bytes())
    assert set(cases) == set("ABCDE")
    for case, payload in cases.items():
        request = PlanRequest.model_validate(payload)
        normalized = prepare_request(request, Settings(complete_recipes_enabled=True))
        assert normalized.recipe_diversity_overrides == {}
        assert "max_same_primary_ingredient_meals" not in request.model_fields_set
        assert request.postal_code == "21120" and request.max_stores == 2
        meal = request.personal.meals[0]
        assert meal.count == 5 and meal.servings == 4
        assert request.recipe_preferences.cuisine_distribution == "free"
        assert request.recipe_preferences.cuisines == (("italian", "indian") if case in "BE" else ())
        assert meal.limits.min_protein_g == (40 if case in "CE" else None)
        assert meal.distribution == ({"chicken": 3, "vegetarian": 2, "meat": 0, "fish": 0} if case in "DE" else {})
        assert request.membership_price_policy == "all_advertised"
