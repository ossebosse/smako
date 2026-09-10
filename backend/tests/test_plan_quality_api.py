from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest
from app.main import app
from app.models import NormalizedIngredient
from app.services.basket_auditor import BasketAuditor
from fastapi.testclient import TestClient


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _optimized_mock_plan(client: TestClient, *, max_stores: int) -> dict:
    response = client.post(
        "/api/plan",
        json={
            "postal_code": "22350",
            "recipes": 5,
            "servings": 4,
            "max_stores": max_stores,
            "strategy": "optimized",
            "candidate_recipe_count": 12,
            "beam_width": 5,
            "optimization_iterations": 0,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_audited_basket_contract(plan: dict) -> None:
    auditor = BasketAuditor()
    audit = plan["quality"]["basket_audit"]
    assert plan["quality"]["status"] == "PASS"
    assert plan["optimized_basket"]["verification_status"] in {
        "VERIFIED",
        "VERIFIED_WITH_ESTIMATES",
    }
    assert audit["status"] == "PASS"
    assert audit["passed"] is True
    assert audit["verification_status"] in {
        "VERIFIED",
        "VERIFIED_WITH_ESTIMATES",
    }
    assert audit["deficits"] == []
    assert len(plan["recipes"]) == 5
    assert all(recipe["servings"] == 4 for recipe in plan["recipes"])

    nutrition = plan["quality"]["nutrition"]
    assert nutrition["status"] == "PASS"
    assert nutrition["is_estimate"] is True
    assert len(nutrition["recipes"]) == 5
    assert all(row["status"] == "PASS" for row in nutrition["recipes"])
    assert all(450 <= row["kcal_per_serving"] <= 900 for row in nutrition["recipes"])
    assert all(row["protein_g_per_serving"] >= 18 for row in nutrition["recipes"])
    assert all(row["vegetable_g_per_serving"] >= 100 for row in nutrition["recipes"])

    diversity = plan["quality"]["diversity"]
    assert diversity["status"] == "PASS"
    assert len(diversity["pairs"]) == 10
    assert diversity["max_pairwise_similarity"] < diversity["threshold"]
    assert all(not pair["is_near_duplicate"] for pair in diversity["pairs"])

    required = {
        (ingredient["canonical_name"], ingredient["unit"]): ingredient
        for ingredient in plan["ingredients"]
        if not auditor.is_pantry(NormalizedIngredient.model_validate(ingredient))
    }
    audited = {(item["canonical_name"], item["unit"]): item for item in audit["items"]}
    assert audited.keys() == required.keys()
    assert audit["ingredients_checked"] == len(required)

    basket_items = {
        (item["store_id"], item["product_id"]): item
        for store in plan["optimized_basket"]["stores"]
        for item in store["items"]
    }
    known_confidences = {"exact", "derived", "estimated", "unknown"}
    for key, row in audited.items():
        assert row["status"] == "PASS"
        assert row["quantity_reconciled"] is True
        assert row["cost_reconciled"] is True
        assert row["required_quantity"] == pytest.approx(required[key]["required_quantity"])
        assert row["purchased_usable_quantity"] >= row["required_quantity"]
        assert row["deficit_quantity"] == 0
        assert row["surplus_quantity"] == pytest.approx(
            row["purchased_usable_quantity"] - row["required_quantity"]
        )
        assert row["quantity_confidence"] in known_confidences
        assert row["selected_products"]

        if row["required_quantity"]:
            assert row["surplus_percent"] == pytest.approx(
                100 * row["surplus_quantity"] / row["required_quantity"],
                abs=0.01,
            )

        selected_total = 0.0
        for selected in row["selected_products"]:
            basket_item = basket_items[(selected["store_id"], selected["product_id"])]
            assert selected["packages_needed"] == basket_item["packages_needed"]
            assert selected["usable_quantity"] == basket_item["usable_quantity"]
            assert selected["usable_unit"] == basket_item["usable_unit"]
            assert selected["purchased_usable_quantity"] == basket_item["purchased_usable_quantity"]
            assert selected["quantity_confidence"] == basket_item["quantity_confidence"]
            assert selected["semantic_confidence"] in {"exact", "high", "medium"}
            assert selected["quantity_reconciled"] is True
            assert selected["cost_reconciled"] is True
            assert selected["sale_model"] != "unknown"
            assert selected["quantity_reconciled"] is True
            selected_total += selected["total_price"]

        expected_surplus_value = (
            _money(selected_total * row["surplus_quantity"] / row["purchased_usable_quantity"])
            if row["surplus_quantity"]
            else 0.0
        )
        assert row["estimated_surplus_value"] == expected_surplus_value

    positive_surplus = {
        (item["canonical_name"], item["unit"]): item
        for item in audit["items"]
        if item["surplus_quantity"] > 0
    }
    surplus = plan["surplus"]
    assert {
        (item["canonical_name"], item["unit"]): item for item in surplus["items"]
    } == positive_surplus
    assert surplus["estimated_surplus_value"] == audit["estimated_surplus_value_total"]
    assert surplus["estimated_surplus_value"] == _money(
        sum(item["estimated_surplus_value"] for item in audit["items"])
    )
    assert surplus["unit_totals"] == audit["unit_totals"]


def test_optimized_mock_response_proves_usable_coverage_and_store_tradeoff(
    monkeypatch,
) -> None:
    monkeypatch.setenv("PRICE_PROVIDER", "mock")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(app)

    plans = {
        max_stores: _optimized_mock_plan(client, max_stores=max_stores) for max_stores in (1, 2)
    }

    for max_stores, plan in plans.items():
        _assert_audited_basket_contract(plan)

        basket = plan["optimized_basket"]
        tradeoff = plan["store_tradeoff"]
        selected_names = [store["store_name"] for store in basket["stores"]]
        assert basket["max_stores"] == max_stores
        assert basket["store_count"] <= max_stores
        assert tradeoff["selected_total"] == basket["total"]
        assert tradeoff["selected_store_count"] == basket["store_count"]
        assert tradeoff["selected_store_count"] <= max_stores
        assert tradeoff["selected_store_names"] == selected_names
        assert tradeoff["selected_verification_status"] == basket["verification_status"]
        assert tradeoff["one_store_total"] is not None
        assert len(tradeoff["one_store_names"]) == 1
        assert tradeoff["one_store_verification_status"] in {
            "VERIFIED",
            "VERIFIED_WITH_ESTIMATES",
        }
        assert tradeoff["extra_store_savings"] == _money(
            max(0.0, tradeoff["one_store_total"] - tradeoff["selected_total"])
        )

    one_store = plans[1]["store_tradeoff"]
    assert one_store["one_store_total"] == one_store["selected_total"]
    assert one_store["one_store_names"] == one_store["selected_store_names"]
    assert one_store["extra_store_savings"] == 0

    two_stores = plans[2]["store_tradeoff"]
    assert two_stores["one_store_total"] >= two_stores["selected_total"]
