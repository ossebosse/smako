"""Immutable consumer-plan persistence contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grocery_data.app.domain.community_evidence import (
    CommunityEvidenceSource,
    CommunityEvidenceType,
    CommunityPromotion,
)

from .plan import PlanRequest, PlanResponse


class SavedPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(min_length=1)
    app_version: str = Field(default="0.1.0", min_length=1, max_length=64)
    build_id: str = Field(default="local", min_length=1, max_length=128)
    revision: int = Field(ge=1)
    parent_revision: int | None = Field(default=None, ge=1)
    created_at: datetime
    operation: Literal["created", "recipe_replaced", "product_replaced"]
    request: PlanRequest
    plan: PlanResponse
    price_universe_id: str | None = None
    prices_changed_since_creation: bool = False
    price_contexts_changed_since_creation: bool = False
    unavailable_saved_context_ids: tuple[str, ...] = ()
    price_version_status: Literal[
        "current",
        "newer_available",
        "coverage_changed",
        "unavailable",
    ] = "unavailable"
    active_price_freshness: Literal[
        "fresh", "aging", "degraded", "stale", "broken"
    ] | None = None
    recalculation_available: bool = False
    reproducible: bool = True


class ReplaceRecipeRequest(BaseModel):
    recipe_index: int = Field(ge=0, le=6)
    replacement_recipe_name: str | None = Field(default=None, min_length=1)


class ReplaceProductRequest(BaseModel):
    product_id: str = Field(min_length=1)
    replacement_product_id: str = Field(min_length=1)


class PlanProductEvidenceRequest(BaseModel):
    """User-entered facts for a report bound to one saved basket row.

    Product identity, digital price, grocery context, plan and snapshot are
    intentionally absent.  The server derives those immutable facts from the
    referenced saved plan so callers cannot forge source provenance.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    evidence_type: CommunityEvidenceType
    evidence_source: CommunityEvidenceSource = CommunityEvidenceSource.MANUAL
    anonymous_session_id: str | None = Field(default=None, min_length=8, max_length=255)
    user_id: str | None = Field(default=None, min_length=1, max_length=255)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    physical_store_id: str = Field(min_length=1, max_length=128)
    shelf_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    unit_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    price_unit: str | None = Field(default=None, max_length=32)
    quantity: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    promotion: CommunityPromotion | None = None
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_report(self) -> PlanProductEvidenceRequest:
        if self.evidence_type in {
            CommunityEvidenceType.PRODUCT_MISSING_FROM_APP,
            CommunityEvidenceType.RECEIPT_PURCHASE,
        }:
            raise ValueError(
                "selected-plan reports cannot be missing-app or receipt reports"
            )
        if self.evidence_source is CommunityEvidenceSource.RECEIPT:
            raise ValueError("receipt evidence must use the receipt endpoint")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if (
            self.evidence_type is CommunityEvidenceType.PRICE_DIFFERENCE
            and self.shelf_price is None
        ):
            raise ValueError("PRICE_DIFFERENCE requires shelf_price")
        if (
            self.evidence_type
            in {
                CommunityEvidenceType.LOCAL_PROMOTION,
                CommunityEvidenceType.PROMOTION_MISSING_FROM_APP,
            }
            and self.promotion is None
        ):
            raise ValueError("promotion report requires a promotion contract")
        if self.price_unit is not None and self.shelf_price is None and self.unit_price is None:
            raise ValueError("price_unit requires a reported price")
        return self


class ProductAlternative(BaseModel):
    model_config = ConfigDict(frozen=True)

    ingredient: str
    product_id: str
    product_name: str
    gtin: str | None = None
    store_id: str
    store_name: str
    packages_needed: int = Field(ge=1)
    total_price: float = Field(gt=0)
    source_provider: str | None = None
    source_snapshot_id: str | None = None


__all__ = [
    "PlanProductEvidenceRequest",
    "ProductAlternative",
    "ReplaceProductRequest",
    "ReplaceRecipeRequest",
    "SavedPlan",
]
