from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from grocery_data.app.api.physical_check import (
    PhysicalValidationCaptureCreate,
    PhysicalValidationSessionCreate,
)
from grocery_data.app.domain.physical_price import (
    PhysicalPriceSemantics,
    WeightPriceType,
)
from grocery_data.app.storage.models import PhysicalValidationSessionModel
from grocery_data.tests.test_physical_check_api import _client


def test_default_field_session_targets_twenty_five_products() -> None:
    payload = PhysicalValidationSessionCreate(
        physical_store_id="physical-hemkop-karhogstorg"
    )

    assert payload.target_sample_size == 25


def test_compound_member_multibuy_projects_to_legacy_fields() -> None:
    payload = PhysicalValidationCaptureCreate.model_validate(
        {
            "shelf_price": "30.00",
            "price_basis": "package",
            "promotion_mechanism": "multibuy",
            "member_only": True,
            "multibuy_quantity": 2,
            "multibuy_total_price": "30.00",
        }
    )

    assert payload.price_semantics is PhysicalPriceSemantics.MULTIBUY
    assert payload.member_only is True
    assert payload.multibuy_quantity == 2
    assert payload.multibuy_total_price == Decimal("30.00")


def test_compound_regular_package_path_needs_no_promotion_fields() -> None:
    payload = PhysicalValidationCaptureCreate.model_validate(
        {
            "shelf_price": "29.95",
            "price_basis": "package",
            "promotion_mechanism": "none",
            "member_only": False,
        }
    )

    assert payload.price_semantics is PhysicalPriceSemantics.REGULAR
    assert payload.multibuy_quantity is None
    assert payload.weight_price_type is None


def test_compound_weight_sale_member_keeps_membership_orthogonal() -> None:
    payload = PhysicalValidationCaptureCreate.model_validate(
        {
            "shelf_price": "29.95",
            "price_basis": "weight",
            "promotion_mechanism": "sale",
            "member_only": True,
            "comparison_unit": "SEK/kg",
        }
    )

    assert payload.price_semantics is PhysicalPriceSemantics.WEIGHT
    assert payload.weight_price_type is WeightPriceType.SALE
    assert payload.member_only is True


def test_compound_weight_multibuy_is_rejected() -> None:
    with pytest.raises(ValidationError, match="weight price basis cannot use multibuy"):
        PhysicalValidationCaptureCreate.model_validate(
            {
                "shelf_price": "30.00",
                "price_basis": "weight",
                "promotion_mechanism": "multibuy",
                "member_only": False,
                "multibuy_quantity": 2,
                "multibuy_total_price": "30.00",
                "comparison_unit": "SEK/kg",
            }
        )


def test_stale_session_start_requires_refresh_and_rolls_back() -> None:
    client, factory = _client()
    client.app.state.settings = replace(
        client.app.state.settings,
        field_validation_max_price_age_hours=2.0,
    )

    response = client.post(
        "/physical-check/sessions",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "target_sample_size": 1,
            "sampling_strategy": "stratified",
            "blind_capture": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "refresh_required"
    with factory() as session:
        assert (
            session.scalar(
                select(func.count()).select_from(PhysicalValidationSessionModel)
            )
            == 0
        )
