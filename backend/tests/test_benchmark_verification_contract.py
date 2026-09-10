from __future__ import annotations

import inspect

import pytest
from app.errors import IncompleteBasketError
from app.models.ingredient import NormalizedIngredient
from app.models.product import (
    ProductCandidate,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from app.models.store import Store
from scripts import (
    benchmark_candidate_coverage,
    benchmark_diversity_modes,
    benchmark_search_quality,
)
from scripts.benchmark_plan import _summary
from scripts.benchmark_verification import (
    strict_live_basket_optimizer,
    strict_live_menu_optimizer,
)


def _unknown_quantity_candidate() -> ProductCandidate:
    return ProductCandidate(
        product_id="unknown-potato",
        product_name="Potatis 1 kg",
        canonical_name="potatis",
        canonical_food="potato",
        food_family="vegetable",
        product_role="raw_potato",
        product_form="raw",
        semantic_confidence=SemanticConfidence.HIGH,
        semantic_evidence=["visible_identity_match"],
        store_id="store",
        store_name="Testbutiken",
        sale_model=SaleModel.FIXED_PACKAGE,
        sale_price=10,
        package_quantity=1000,
        package_unit="g",
        usable_quantity=1000,
        usable_unit="g",
        quantity_confidence=QuantityConfidence.UNKNOWN,
        price=10,
        effective_price=10,
        match_score=1,
    )


def test_standalone_benchmarks_share_the_strict_live_verification_factory() -> None:
    basket_optimizer = strict_live_basket_optimizer()
    policy = basket_optimizer.verification_policy

    assert policy.allow_medium_semantic is False
    assert policy.allow_estimated_quantities is True
    assert policy.allow_unknown_quantities is False
    assert policy.allow_unknown_sale_model is False
    assert policy.allow_legacy_low_without_evidence is False
    assert policy.enforce_audit_verification is True
    assert strict_live_menu_optimizer().basket_optimizer.verification_policy == policy

    for benchmark_run in (
        benchmark_candidate_coverage._run,
        benchmark_diversity_modes._run,
        benchmark_search_quality._run_matrix,
    ):
        source = inspect.getsource(benchmark_run)
        assert "strict_live_" in source


def test_strict_benchmark_optimizer_cannot_price_an_unknown_quantity() -> None:
    ingredient = NormalizedIngredient(
        canonical_name="potatis",
        required_quantity=500,
        unit="g",
    )
    store = Store(
        store_id="store",
        name="Testbutiken",
        chain="Test",
        postal_code="22350",
        city="Lund",
    )

    with pytest.raises(IncompleteBasketError):
        strict_live_basket_optimizer().optimize(
            [ingredient],
            {"potatis": [_unknown_quantity_candidate()]},
            [store],
            max_stores=1,
        )


def test_plan_benchmark_preserves_verification_evidence_and_ranks_trust_first() -> None:
    product = {
        "ingredient": "potatis",
        "product_id": "verified-potato",
        "product_name": "Potatis 1 kg",
        "verification_status": "VERIFIED",
        "canonical_food": "potato",
        "food_family": "vegetable",
        "product_role": "raw_potato",
        "product_form": "raw",
        "semantic_confidence": "high",
        "semantic_evidence": ["visible_identity_match"],
        "sale_model": "fixed_package",
        "sale_price": 10,
        "sale_unit": "package",
        "comparison_price": 10,
        "comparison_unit": "kg",
        "packages_needed": 1,
        "package_quantity": 1000,
        "package_unit": "g",
        "usable_quantity": 1000,
        "usable_unit": "g",
        "unit": "g",
        "required_quantity": 500,
        "purchased_quantity": 1000,
        "purchased_unit": "g",
        "purchased_usable_quantity": 1000,
        "waste_quantity": 500,
        "quantity_confidence": "derived",
        "variable_weight": False,
        "unit_price": 10,
        "total_price": 10,
        "purchase_warning": None,
    }
    data = {
        "data_source": "mock",
        "strategy": "optimized",
        "optimized_basket": {
            "total": 10,
            "verification_status": "VERIFIED",
            "verification_warnings": [],
            "stores": [
                {
                    "store_id": "verified-store",
                    "store_name": "Verifierad butik",
                    "subtotal": 10,
                    "items": [product],
                }
            ],
        },
        "single_store_options": [
            {
                "store_id": "unknown-store",
                "store_name": "Billig men osäker",
                "total": 1,
                "is_complete": True,
                "verification_status": "UNVERIFIED",
                "verification_warnings": ["Okänd mängd."],
            },
            {
                "store_id": "verified-store",
                "store_name": "Verifierad butik",
                "total": 10,
                "is_complete": True,
                "verification_status": "VERIFIED",
                "verification_warnings": [],
            },
        ],
        "optimization": {},
        "quality": {
            "status": "PASS",
            "basket_audit": {
                "status": "PASS",
                "verification_status": "VERIFIED",
                "verification_warnings": [],
                "deficits": [],
                "unknown_quantities": 0,
                "totals_reconciled": True,
                "calculated_total": 10,
                "reported_total": 10,
                "total_reconciliation_errors": [],
            },
            "nutrition": {},
            "diversity": {},
        },
        "debug_info": {
            "basket_verification": {
                "status": "VERIFIED",
                "products": [{"ingredient": "potatis"}],
            }
        },
    }

    result = _summary(data, 0.25)
    basket = result["basket"]
    row = basket["stores"][0]["products"][0]

    assert basket["verification_status"] == "VERIFIED"
    assert row["verification_status"] == "VERIFIED"
    assert row["semantic_confidence"] == "high"
    assert row["semantic_evidence"] == ["visible_identity_match"]
    assert row["sale_model"] == "fixed_package"
    assert row["quantity_confidence"] == "derived"
    assert result["quality"]["basket_audit"]["verification_status"] == "VERIFIED"
    assert result["quality"]["basket_audit"]["totals_reconciled"] is True
    assert result["cheapest_single_store"]["store"] == "Verifierad butik"
    assert result["cheapest_single_store"]["verification_status"] == "VERIFIED"
    assert result["debug"]["basket_verification"]["status"] == "VERIFIED"
