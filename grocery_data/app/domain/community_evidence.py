from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grocery_data.app.domain.promotion_pricing import (
    PromotionEligibility,
    PromotionMechanism,
)


class CommunityEvidenceType(StrEnum):
    PRODUCT_FOUND = "PRODUCT_FOUND"
    PRODUCT_NOT_FOUND = "PRODUCT_NOT_FOUND"
    PRODUCT_MISSING_FROM_APP = "PRODUCT_MISSING_FROM_APP"
    PRICE_DIFFERENCE = "PRICE_DIFFERENCE"
    LOCAL_PROMOTION = "LOCAL_PROMOTION"
    PROMOTION_MISSING_FROM_APP = "PROMOTION_MISSING_FROM_APP"
    PROMOTION_EXPIRED = "PROMOTION_EXPIRED"
    RECEIPT_PURCHASE = "RECEIPT_PURCHASE"
    PRODUCT_IDENTITY_CORRECTION = "PRODUCT_IDENTITY_CORRECTION"


class CommunityEvidenceSource(StrEnum):
    BARCODE_SCAN = "BARCODE_SCAN"
    MANUAL = "MANUAL"
    SHELF_PRICE = "SHELF_PRICE"
    RECEIPT = "RECEIPT"
    PHOTO = "PHOTO"
    OTHER = "OTHER"


class EvidenceVerificationStatus(StrEnum):
    USER_REPORTED = "USER_REPORTED"
    VALID = "VALID"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"


class ProductIdentityConfidence(StrEnum):
    EXACT_GTIN = "EXACT_GTIN"
    EXACT_CHAIN_PRODUCT_ID = "EXACT_CHAIN_PRODUCT_ID"
    HIGH_CONFIDENCE_RECEIPT_MATCH = "HIGH_CONFIDENCE_RECEIPT_MATCH"
    AMBIGUOUS = "AMBIGUOUS"
    UNMATCHED = "UNMATCHED"


class AssortmentConfidence(StrEnum):
    VERIFIED_RECENTLY_AVAILABLE = "VERIFIED_RECENTLY_AVAILABLE"
    PROBABLE_AVAILABLE = "PROBABLE_AVAILABLE"
    UNKNOWN = "UNKNOWN"
    USER_REPORTED_NOT_FOUND = "USER_REPORTED_NOT_FOUND"
    SOURCE_REPORTED_UNAVAILABLE = "SOURCE_REPORTED_UNAVAILABLE"


class PriceEvidenceConfidence(StrEnum):
    RECEIPT_VERIFIED = "RECEIPT_VERIFIED"
    CORROBORATED = "CORROBORATED"
    USER_REPORTED = "USER_REPORTED"
    CONFLICTING = "CONFLICTING"
    UNKNOWN = "UNKNOWN"


class CommunityPromotion(BaseModel):
    """A user-observed promotion contract; eligibility and mechanism stay orthogonal."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    eligibility: PromotionEligibility = PromotionEligibility.UNKNOWN
    mechanism: PromotionMechanism
    regular_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    active_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    required_quantity: int | None = Field(default=None, ge=2, le=1000)
    total_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    percent_discount: Decimal | None = Field(default=None, gt=0, lt=100)
    max_quantity: int | None = Field(default=None, ge=1, le=10000)
    member_program: str | None = Field(default=None, max_length=100)
    valid_from: date | None = None
    valid_to: date | None = None
    description: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_contract(self) -> CommunityPromotion:
        if self.mechanism is PromotionMechanism.MULTIBUY:
            if self.required_quantity is None or self.total_price is None:
                raise ValueError("multibuy requires required_quantity and total_price")
        elif self.required_quantity is not None or self.total_price is not None:
            raise ValueError("multibuy fields require the multibuy mechanism")
        if self.mechanism is PromotionMechanism.PERCENT_DISCOUNT:
            if self.percent_discount is None and self.active_price is None:
                raise ValueError("percent discount requires percent_discount or active_price")
        elif self.percent_discount is not None:
            raise ValueError("percent_discount requires the percent-discount mechanism")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to")
        return self


class CommunityEvidenceSubmission(BaseModel):
    """Credential-free consumer report before server-side trust calculation."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    evidence_type: CommunityEvidenceType
    evidence_source: CommunityEvidenceSource = CommunityEvidenceSource.MANUAL
    anonymous_session_id: str | None = Field(default=None, min_length=8, max_length=255)
    user_id: str | None = Field(default=None, min_length=1, max_length=255)
    idempotency_key: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )
    observed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    chain: str | None = Field(default=None, max_length=32)
    physical_store_id: str | None = Field(default=None, max_length=128)
    source_provider_store_id: str | None = Field(default=None, max_length=255)
    store_display_name: str | None = Field(default=None, max_length=500)
    grocery_context_id: str | None = Field(default=None, max_length=255)
    gtin: str | None = Field(default=None, max_length=32)
    source_product_id: str | None = Field(default=None, max_length=500)
    product_name: str | None = Field(default=None, max_length=1000)
    brand: str | None = Field(default=None, max_length=500)
    package_description: str | None = Field(default=None, max_length=500)
    physical_presence: bool | None = None
    shelf_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    digital_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    unit_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    price_unit: str | None = Field(default=None, max_length=32)
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    promotion: CommunityPromotion | None = None
    receipt_ingestion_id: str | None = Field(default=None, max_length=64)
    plan_id: str | None = Field(default=None, max_length=128)
    price_snapshot_id: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_report(self) -> CommunityEvidenceSubmission:
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not any((self.gtin, self.source_product_id, self.product_name)):
            raise ValueError("gtin, source_product_id or product_name is required")
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
        if (
            self.evidence_type is CommunityEvidenceType.RECEIPT_PURCHASE
            and self.receipt_ingestion_id is None
            and self.evidence_source is not CommunityEvidenceSource.RECEIPT
        ):
            raise ValueError("receipt purchase requires receipt provenance")
        if self.evidence_source is CommunityEvidenceSource.BARCODE_SCAN and self.gtin is None:
            raise ValueError("barcode evidence requires gtin")
        if self.price_unit is not None and not any(
            (self.shelf_price, self.unit_price, self.digital_price)
        ):
            raise ValueError("price_unit requires a price")
        return self


class ModerationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EvidenceVerificationStatus
    reason: str = Field(min_length=3, max_length=1000)
    moderator_id: str | None = Field(default=None, max_length=255)
    idempotency_key: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
    )

    @model_validator(mode="after")
    def validate_status(self) -> ModerationDecision:
        if self.status is EvidenceVerificationStatus.USER_REPORTED:
            raise ValueError("moderation cannot reset evidence to USER_REPORTED")
        return self


__all__ = [
    "AssortmentConfidence",
    "CommunityEvidenceSource",
    "CommunityEvidenceSubmission",
    "CommunityEvidenceType",
    "CommunityPromotion",
    "EvidenceVerificationStatus",
    "ModerationDecision",
    "PriceEvidenceConfidence",
    "ProductIdentityConfidence",
]
