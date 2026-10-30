from __future__ import annotations

import pytest
from app.api import plan as plan_api
from app.config import Settings
from app.main import app
from app.models import PlanRequest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.usefixtures("verified_smako_member")

def test_request_mode_sets_planner_quantity_policy_without_mutating_shared_settings(monkeypatch) -> None:
    shared = Settings(price_provider="mock", allow_estimated_quantities=True)
    monkeypatch.setattr(plan_api, "get_settings", lambda: shared)

    exact = plan_api._service(PlanRequest(purchase_planning_mode="exact"))
    estimated = plan_api._service(PlanRequest(purchase_planning_mode="estimated"))

    assert exact.settings.allow_estimated_quantities is False
    assert estimated.settings.allow_estimated_quantities is True
    assert shared.allow_estimated_quantities is True


def test_mock_plan_is_complete_and_package_priced(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("STABLE_CANDIDATE_SEARCH_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    response = client.post(
        "/api/plan",
        json={
            "postal_code": "223 50",
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "strategy": "legacy",
            "optimization_iterations": 1,
        },
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["location"] == "Lund"
    assert plan["data_source"] == "mock"
    assert plan["recipe_source"] == "mock"
    assert len(plan["recipes"]) == 5
    assert all(recipe["servings"] == 4 for recipe in plan["recipes"])
    assert plan["portions"] == 20
    assert plan["price_per_portion"] == round(plan["optimized_basket"]["total"] / 20, 2)

    items = [item for store in plan["optimized_basket"]["stores"] for item in store["items"]]
    assert len(items) == len(plan["ingredients"])
    assert all(item["packages_needed"] >= 1 for item in items)
    assert all(item["purchased_quantity"] >= item["required_quantity"] for item in items)
    assert round(sum(item["total_price"] for item in items), 2) == plan["optimized_basket"]["total"]

    complete_single = [option for option in plan["single_store_options"] if option["is_complete"]]
    assert complete_single
    assert plan["optimized_basket"]["total"] <= complete_single[0]["total"]
    assert [scenario["label"] for scenario in plan["optimization_scenarios"]] == [
        "1 butik",
        "Max 2 butiker",
        "Max 3 butiker",
        "Obegränsat",
    ]
    assert plan["optimization_iterations_attempted"] == 1
    assert plan["optimization_iterations_accepted"] == 0


def test_invalid_postal_code_is_rejected() -> None:
    response = TestClient(app).post(
        "/api/plan",
        json={"postal_code": "223", "recipes": 5, "servings": 4, "max_stores": 2},
    )
    assert response.status_code == 422


def test_optimized_plan_exposes_search_metadata_and_legacy_comparison(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.setenv("STABLE_CANDIDATE_SEARCH_ENABLED", "false")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).post(
        "/api/plan?debug=true",
        json={
            "postal_code": "22350",
            "recipes": 5,
            "servings": 4,
            "max_stores": 2,
            "strategy": "optimized",
            "candidate_recipe_count": 12,
            "beam_width": 5,
            "optimization_iterations": 0,
            "debug": False,
        },
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["strategy"] == "optimized"
    assert plan["postal_code"] == "22350"
    assert len(plan["recipes"]) == 5
    assert plan["optimized_basket"]["store_count"] <= 2
    assert plan["optimization"]["candidate_recipes_generated"] == 12
    assert plan["optimization"]["candidate_recipes_valid"] >= 5
    assert (
        plan["optimization"]["candidate_recipes_search_pool"]
        >= plan["optimization"]["candidate_recipes_valid"]
    )
    assert plan["optimization"]["legacy_candidates_added"] >= 0
    assert plan["optimization"]["states_evaluated"] > 0
    assert plan["optimization"]["basket_cache_hits"] > 0
    assert plan["legacy_comparison"] is not None
    assert plan["optimized_basket"]["total"] <= plan["legacy_comparison"]["total"]
    assert plan["debug_info"]["economic_ingredients"]
    assert plan["debug_info"]["marginal_costs"]
    verification = plan["debug_info"]["basket_verification"]
    assert verification["status"] in {"VERIFIED", "VERIFIED_WITH_ESTIMATES"}
    assert verification["products"]
    assert all(
        row["semantic"]["confidence"] in {"exact", "high", "medium"}
        and row["purchase"]["sale_model"] != "unknown"
        and row["purchase"]["quantity_confidence"] != "unknown"
        for row in verification["products"]
    )
    assert plan["debug_info"]["selected_plan_origin"] in {
        "beam_search",
        "legacy_upper_bound",
        "openai_improvement",
    }


def test_static_frontend_and_health_are_served() -> None:
    client = TestClient(app)
    redirect = client.get("/?return_case=x", follow_redirects=False)
    root = client.get("/klassisk")
    health = client.get("/api/health")

    assert redirect.status_code == 302
    assert redirect.headers["location"] == "/personal?return_case=x"
    assert root.status_code == 200
    assert "Billigaste veckomenyn" in root.text
    assert 'id="recipes"' in root.text
    assert 'max="7"' in root.text
    assert health.json() == {"status": "ok"}


def test_mock_fallback_requires_explicit_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("ALLOW_MOCK_FALLBACK", raising=False)

    assert Settings.from_env().allow_mock_fallback is False


def test_live_verification_gates_are_safe_and_configurable(monkeypatch) -> None:
    for name in (
        "ALLOW_MEDIUM_SEMANTIC_MATCHES",
        "ALLOW_ESTIMATED_QUANTITIES",
        "ALLOW_UNKNOWN_QUANTITIES",
        "ALLOW_UNKNOWN_SALE_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    safe = Settings.from_env()
    assert not safe.allow_medium_semantic_matches
    assert safe.allow_estimated_quantities
    assert not safe.allow_unknown_quantities
    assert not safe.allow_unknown_sale_model

    monkeypatch.setenv("ALLOW_MEDIUM_SEMANTIC_MATCHES", "true")
    monkeypatch.setenv("ALLOW_ESTIMATED_QUANTITIES", "false")
    monkeypatch.setenv("ALLOW_UNKNOWN_QUANTITIES", "true")
    monkeypatch.setenv("ALLOW_UNKNOWN_SALE_MODEL", "true")
    configured = Settings.from_env()
    assert configured.allow_medium_semantic_matches
    assert not configured.allow_estimated_quantities
    assert configured.allow_unknown_quantities
    assert configured.allow_unknown_sale_model


def test_settings_repr_never_contains_credentials() -> None:
    settings = Settings(
        primat_api_key="primat-secret-value",
        openai_api_key="openai-secret-value",
    )

    rendered = repr(settings)
    assert "primat-secret-value" not in rendered
    assert "openai-secret-value" not in rendered


def test_plan_request_validates_quality_range_and_supports_200_candidates() -> None:
    request = PlanRequest(candidate_recipe_count=200)
    assert request.candidate_recipe_count == 200

    response = TestClient(app).post(
        "/api/plan",
        json={
            "postal_code": "22350",
            "min_kcal_per_serving": 900,
            "max_kcal_per_serving": 450,
        },
    )
    assert response.status_code == 422


def test_legacy_strategy_warns_when_diversity_mode_is_explicit(monkeypatch) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).post(
        "/api/plan",
        json={
            "postal_code": "22350",
            "strategy": "legacy",
            "diversity_mode": "varied",
            "optimization_iterations": 0,
        },
    )

    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["strategy"] == "legacy"
    assert plan["diversity_mode"] == "varied"
    assert plan["plans"] == {}
    assert any("diversity_mode tillämpas endast" in warning for warning in plan["warnings"])
