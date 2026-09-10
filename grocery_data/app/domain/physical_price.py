from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from grocery_data.app.domain.enums import Chain, Confidence, PromotionType, SaleModel
from grocery_data.app.domain.identifiers import normalize_gtin


class PhysicalPriceComparisonStatus(StrEnum):
    MATCH = "match"
    MINOR_DIFFERENCE = "minor_difference"
    MAJOR_DIFFERENCE = "major_difference"
    NO_DIGITAL_MATCH = "no_digital_match"
    STALE_DIGITAL_PRICE = "stale_digital_price"


class PromotionComparisonStatus(StrEnum):
    MATCH = "match"
    DIFFERENT = "different"
    NOT_COMPARABLE = "not_comparable"


class PhysicalSampleConfidence(StrEnum):
    """Display confidence for optional, explicitly sampled ground truth."""

    NO_PHYSICAL_SAMPLE = "no_physical_sample"
    LIMITED_SAMPLE = "limited_sample"
    GOOD_SAMPLE = "good_sample"


class PhysicalPriceSemantics(StrEnum):
    """Legacy primary shelf-label axis retained for stored V1/V2 captures.

    V3 promotion eligibility and mechanism are orthogonal; for example a row
    may use ``MULTIBUY`` here while ``member_only`` is also true.
    """

    REGULAR = "regular"
    SALE = "sale"
    MEMBER = "member"
    MULTIBUY = "multibuy"
    WEIGHT = "weight"
    UNKNOWN = "unknown"


class WeightPriceType(StrEnum):
    REGULAR = "regular"
    SALE = "sale"
    MEMBER = "member"
    UNKNOWN = "unknown"


class PhysicalProductIdentityStatus(StrEnum):
    """Closed, evidence-preserving identity result for a field capture."""

    # Retained so already persisted V1 observations remain readable. New field
    # captures use one of the explicit V2 states below.
    EXACT = "exact"
    GTIN_MATCH = "gtin_match"
    GTIN_MISMATCH = "gtin_mismatch"
    GTIN_NOT_KNOWN_BY_SOURCE = "gtin_not_known_by_source"
    WEIGHT_ITEM_NO_GTIN_REQUIRED = "weight_item_no_gtin_required"
    SHELF_CODE_MATCH = "shelf_code_match"
    SHELF_CODE_UNKNOWN = "shelf_code_unknown"
    MANUAL_EXACT_MATCH = "manual_exact_match"
    NO_MATCH = "no_match"


class PhysicalIdentificationEvidence(StrEnum):
    """Strength/type of evidence used to identify the physical product."""

    GTIN_VERIFIED = "gtin_verified"
    SOURCE_PRODUCT_MANUAL = "source_product_manual"
    WEIGHT_SOURCE_PRODUCT = "weight_source_product"
    SHELF_CODE_VERIFIED = "shelf_code_verified"
    UNVERIFIED = "unverified"


class ProductIdentifierType(StrEnum):
    GTIN = "gtin"
    SHELF_CODE = "shelf_code"


class ProductIdentifierEvidenceSource(StrEnum):
    CATALOG = "catalog"
    PRODUCT_DETAIL = "product_detail"
    MANUAL_DIAGNOSTIC = "manual_diagnostic"


class SessionItemIdentifierStatus(StrEnum):
    KNOWN_GTIN = "known_gtin"
    UNKNOWN_GTIN = "unknown_gtin"
    NOT_REQUIRED_WEIGHT = "not_required_weight"
    AMBIGUOUS_GTIN = "ambiguous_gtin"
    ENRICHMENT_UNAVAILABLE = "enrichment_unavailable"
    ENRICHMENT_ERROR = "enrichment_error"


class PhysicalValidationSessionStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PhysicalObservationAmendmentKind(StrEnum):
    """Why an immutable post-completion observation payload was appended."""

    LATE_CAPTURE = "late_capture"
    CORRECTION = "correction"


class PhysicalObservationTimePrecision(StrEnum):
    """Declared precision of a recovered observation timestamp."""

    EXACT = "exact"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    VISIT_WINDOW = "visit_window"
    UNKNOWN = "unknown"


class PhysicalPriceObservation(BaseModel):
    """A manual shelf-price sample, never a catalog-price replacement."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    physical_store_id: str = Field(min_length=1, max_length=64)
    gtin: str | None = None
    product_name: str | None = Field(default=None, max_length=1000)
    shelf_price: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    comparison_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    comparison_unit: str | None = Field(default=None, max_length=32)
    promotion_type: PromotionType | None = None
    member_only: bool | None = None
    multibuy_quantity: int | None = Field(default=None, ge=1)
    multibuy_total_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    promotion_text: str | None = Field(default=None, max_length=1000)
    observed_at: datetime
    source: Literal["manual"] = "manual"
    confidence: Confidence
    notes: str | None = Field(default=None, max_length=2000)
    photo_reference: str | None = Field(default=None, max_length=500)
    validation_session_id: str | None = Field(default=None, min_length=1, max_length=64)
    validation_session_item_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    price_semantics: PhysicalPriceSemantics | None = None
    identity_status: PhysicalProductIdentityStatus | None = None
    identification_evidence: PhysicalIdentificationEvidence | None = None
    regular_shelf_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    weight_price_type: WeightPriceType | None = None
    immutable_candidate_set_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )

    @field_validator("gtin")
    @classmethod
    def validate_gtin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "".join(character for character in value if character not in " -")
        if not normalized.isdigit() or len(normalized) not in {8, 12, 13, 14}:
            raise ValueError("gtin must contain 8, 12, 13 or 14 digits")
        return normalized

    @field_validator(
        "product_name",
        "comparison_unit",
        "notes",
        "promotion_text",
        "photo_reference",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        return normalized or None

    @field_validator("observed_at")
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_identity_and_paired_fields(self) -> PhysicalPriceObservation:
        if self.gtin is None and self.product_name is None:
            raise ValueError("gtin or product_name is required")
        if self.price_semantics is not PhysicalPriceSemantics.WEIGHT and (
            (self.comparison_price is None) != (self.comparison_unit is None)
        ):
            raise ValueError("comparison price and unit must be provided together")
        if (self.multibuy_quantity is None) != (self.multibuy_total_price is None):
            raise ValueError("multibuy quantity and total price must be provided together")
        if self.multibuy_quantity is not None and self.promotion_type not in {
            PromotionType.MULTIBUY,
            PromotionType.MEMBER_PRICE,
        }:
            raise ValueError("multibuy values require a multibuy or member promotion")
        session_fields = (
            self.validation_session_id,
            self.validation_session_item_id,
            self.price_semantics,
            self.identity_status,
            self.immutable_candidate_set_sha256,
        )
        if any(value is not None for value in session_fields) and not all(
            value is not None for value in session_fields
        ):
            raise ValueError("all validation-session linkage fields must be provided together")
        expected_evidence = {
            PhysicalProductIdentityStatus.EXACT: PhysicalIdentificationEvidence.GTIN_VERIFIED
            if self.gtin is not None
            else PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL,
            PhysicalProductIdentityStatus.GTIN_MATCH: PhysicalIdentificationEvidence.GTIN_VERIFIED,
            PhysicalProductIdentityStatus.GTIN_MISMATCH: PhysicalIdentificationEvidence.UNVERIFIED,
            PhysicalProductIdentityStatus.GTIN_NOT_KNOWN_BY_SOURCE: (
                PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL
            ),
            PhysicalProductIdentityStatus.WEIGHT_ITEM_NO_GTIN_REQUIRED: (
                PhysicalIdentificationEvidence.WEIGHT_SOURCE_PRODUCT
            ),
            PhysicalProductIdentityStatus.SHELF_CODE_MATCH: (
                PhysicalIdentificationEvidence.SHELF_CODE_VERIFIED
            ),
            PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN: (
                PhysicalIdentificationEvidence.UNVERIFIED
            ),
            PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH: (
                PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL
            ),
            PhysicalProductIdentityStatus.NO_MATCH: PhysicalIdentificationEvidence.UNVERIFIED,
        }.get(self.identity_status)
        if (
            self.identification_evidence is not None
            and expected_evidence is not None
            and self.identification_evidence is not expected_evidence
        ):
            raise ValueError("identification evidence is inconsistent with identity status")
        if self.price_semantics is PhysicalPriceSemantics.REGULAR:
            if (
                self.promotion_type is not None
                or self.member_only is True
                or self.multibuy_quantity is not None
            ):
                raise ValueError("regular capture cannot contain promotion semantics")
        elif self.price_semantics is PhysicalPriceSemantics.SALE:
            if self.promotion_type not in {
                PromotionType.SALE_PRICE,
                PromotionType.PERCENT_DISCOUNT,
            }:
                raise ValueError("sale capture requires a sale or percent-discount promotion")
            if self.multibuy_quantity is not None:
                raise ValueError("unit sale capture cannot also contain multibuy terms")
        elif self.price_semantics is PhysicalPriceSemantics.MEMBER:
            if self.promotion_type is not PromotionType.MEMBER_PRICE or self.member_only is not True:
                raise ValueError("member capture requires member price and member_only=true")
            if self.multibuy_quantity is not None:
                raise ValueError("member capture is distinct from multibuy")
        elif self.price_semantics is PhysicalPriceSemantics.MULTIBUY:
            if self.promotion_type is not PromotionType.MULTIBUY:
                raise ValueError("multibuy capture requires multibuy promotion")
            if self.multibuy_quantity is None:
                raise ValueError("multibuy capture requires quantity and total price")
        elif self.price_semantics is PhysicalPriceSemantics.WEIGHT:
            if self.multibuy_quantity is not None:
                raise ValueError("weight capture cannot be multibuy")
            if self.comparison_unit is None:
                raise ValueError("weight capture requires a shelf-price unit")
            normalized_unit = re.sub(r"\s+", "", self.comparison_unit.casefold())
            if normalized_unit not in {"kg", "kr/kg", "sek/kg"}:
                raise ValueError("weight capture currently requires SEK/kg")
            if self.weight_price_type is WeightPriceType.SALE:
                if self.promotion_type is not PromotionType.SALE_PRICE:
                    raise ValueError("weight sale requires a sale promotion")
            elif self.weight_price_type is WeightPriceType.MEMBER:
                if (
                    self.promotion_type is not PromotionType.MEMBER_PRICE
                    or self.member_only is not True
                ):
                    raise ValueError("weight member price requires member evidence")
            elif self.promotion_type is not None or self.member_only is True:
                raise ValueError("regular/unknown weight price cannot contain a promotion")
        elif self.weight_price_type is not None:
            raise ValueError("weight price type requires weight semantics")
        elif self.regular_shelf_price is not None and self.price_semantics not in {
            PhysicalPriceSemantics.SALE,
            PhysicalPriceSemantics.MEMBER,
            PhysicalPriceSemantics.MULTIBUY,
        }:
            raise ValueError(
                "regular shelf price requires promotional or weight semantics"
            )
        return self


def canonical_physical_observation_payload(
    observation: PhysicalPriceObservation,
) -> str:
    """Serialize one typed observation deterministically for immutable storage."""

    return json.dumps(
        observation.model_dump(mode="json", exclude_none=True),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def physical_observation_payload_sha256(
    observation: PhysicalPriceObservation,
) -> str:
    return hashlib.sha256(
        canonical_physical_observation_payload(observation).encode("utf-8")
    ).hexdigest()


class PhysicalObservationAmendment(BaseModel):
    """Append-only recovery evidence for one item in a completed field session.

    ``payload`` is a complete typed observation.  It is never written back over
    the historical observation row; consumers must opt in to applying the
    amendment chain.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    validation_session_id: str = Field(min_length=1, max_length=64)
    validation_session_item_id: str = Field(min_length=1, max_length=64)
    kind: PhysicalObservationAmendmentKind
    payload: PhysicalPriceObservation
    payload_schema_version: Literal[1] = 1
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    supersedes_amendment_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    observed_at: datetime
    observed_at_precision: PhysicalObservationTimePrecision
    reason: str = Field(min_length=1, max_length=2000)
    source: str = Field(min_length=1, max_length=64)
    reference: str = Field(min_length=1, max_length=2000)
    client_request_id: str = Field(min_length=8, max_length=128)
    created_at: datetime | None = None

    @field_validator("reason", "source", "reference", "client_request_id", mode="before")
    @classmethod
    def strip_required_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("observed_at", "created_at")
    @classmethod
    def amendment_time_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("amendment timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_amendment_chain_and_payload(self) -> PhysicalObservationAmendment:
        if self.payload.validation_session_id != self.validation_session_id:
            raise ValueError("payload validation session does not match amendment")
        if self.payload.validation_session_item_id != self.validation_session_item_id:
            raise ValueError("payload validation session item does not match amendment")
        if self.payload.observed_at != self.observed_at:
            raise ValueError("payload observed_at does not match amendment")
        if physical_observation_payload_sha256(self.payload) != self.payload_sha256:
            raise ValueError("payload_sha256 does not match canonical payload")
        if self.base_observation_id == self.id or self.supersedes_amendment_id == self.id:
            raise ValueError("an amendment cannot refer to itself")
        if self.kind is PhysicalObservationAmendmentKind.LATE_CAPTURE:
            if self.base_observation_id is not None or self.supersedes_amendment_id is not None:
                raise ValueError("late capture must start a new amendment chain")
        elif self.base_observation_id is None and self.supersedes_amendment_id is None:
            raise ValueError("correction requires a base observation or superseded amendment")
        return self


class DigitalPriceCandidate(BaseModel):
    """Small credential-free projection used for ground-truth comparison."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    physical_store_id: str = Field(min_length=1)
    grocery_context_id: str = Field(min_length=1)
    source_provider: str = Field(min_length=1)
    source_snapshot_id: str = Field(min_length=1)
    observed_at: datetime
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    brand: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=500)
    package_description: str | None = Field(default=None, max_length=128)
    gtin: str | None = None
    current_price: Decimal = Field(gt=0)
    regular_price: Decimal | None = Field(default=None, gt=0)
    member_price: Decimal | None = Field(default=None, gt=0)
    comparison_price: Decimal | None = Field(default=None, gt=0)
    comparison_unit: str | None = None
    promotion_type: PromotionType | None = None
    member_only: bool = False
    multibuy_quantity: int | None = Field(default=None, ge=1)
    multibuy_total_price: Decimal | None = Field(default=None, gt=0)
    sale_model: SaleModel = SaleModel.UNKNOWN
    common_product_score: Decimal = Field(default=Decimal(0), ge=0)
    recent_price_change: Decimal | None = Field(default=None, ge=0)

    @field_validator("gtin")
    @classmethod
    def normalize_gtin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "".join(character for character in value if character not in " -")
        return normalized if normalized.isdigit() else None

    @field_validator("observed_at")
    @classmethod
    def aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_paired_fields(self) -> DigitalPriceCandidate:
        if (self.comparison_price is None) != (self.comparison_unit is None):
            raise ValueError("comparison price and unit must be provided together")
        if (self.multibuy_quantity is None) != (self.multibuy_total_price is None):
            raise ValueError("multibuy quantity and total price must be provided together")
        return self


class PhysicalPriceComparison(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    observation_id: str
    physical_store_id: str
    source_provider: str | None = None
    grocery_context_id: str | None = None
    source_snapshot_id: str | None = None
    product_id: str | None = None
    gtin: str | None = None
    product_name: str | None = None
    sale_model: SaleModel = SaleModel.UNKNOWN
    physical_promotion_type: PromotionType | None = None
    digital_promotion_type: PromotionType | None = None
    physical_price: Decimal
    digital_price: Decimal | None = None
    digital_observed_at: datetime | None = None
    digital_age_hours: Decimal | None = Field(default=None, ge=0)
    signed_difference: Decimal | None = None
    absolute_difference: Decimal | None = Field(default=None, ge=0)
    percentage_difference: Decimal | None = None
    exact_match: bool = False
    within_050: bool = False
    within_100: bool = False
    status: PhysicalPriceComparisonStatus
    promotion_status: PromotionComparisonStatus = PromotionComparisonStatus.NOT_COMPARABLE
    promotion_type_match: bool | None = None
    member_restriction_match: bool | None = None
    multibuy_match: bool | None = None
    comparison_price_match: bool | None = None
    input_anomaly_suspected: bool = False
    match_method: Literal[
        "gtin",
        "exact_name",
        "verified_session_product",
    ] | None = None
    observation_confidence: Confidence


class AccuracyBucket(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    comparisons: int = Field(ge=0)
    exact_matches: int = Field(ge=0)
    within_050: int = Field(ge=0)
    within_100: int = Field(ge=0)
    minor_differences: int = Field(ge=0)
    major_differences: int = Field(ge=0)
    no_digital_match: int = Field(ge=0)
    stale_digital_price: int = Field(ge=0)
    exact_percent: Decimal = Field(ge=0, le=100)
    within_050_percent: Decimal = Field(ge=0, le=100)
    within_100_percent: Decimal = Field(ge=0, le=100)
    minimum_sample_for_score: int = Field(default=20, ge=1)
    score_eligible: bool = False
    sample_confidence: PhysicalSampleConfidence = (
        PhysicalSampleConfidence.NO_PHYSICAL_SAMPLE
    )
    display_exact_percent: Decimal | None = Field(default=None, ge=0, le=100)
    display_within_050_percent: Decimal | None = Field(default=None, ge=0, le=100)
    display_within_100_percent: Decimal | None = Field(default=None, ge=0, le=100)
    priced_comparisons: int = Field(default=0, ge=0)
    mean_absolute_error: Decimal | None = Field(default=None, ge=0)
    median_absolute_error: Decimal | None = Field(default=None, ge=0)
    mean_signed_error: Decimal | None = None
    digital_lower_than_shelf_count: int = Field(default=0, ge=0)
    digital_higher_than_shelf_count: int = Field(default=0, ge=0)


class SourceAccuracyReport(BaseModel):
    """Accuracy for sampled observations only; never a national accuracy claim."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    scope_label: str = Field(min_length=1)
    sampled_observations_note: str = (
        "Resultaten gäller endast frivilligt insamlade stickprov i angivet scope."
    )
    observation_count: int = Field(ge=0)
    days_sampled: int = Field(ge=0)
    campaign_weeks_sampled: int = Field(ge=0)
    minimum_sample_for_score: int = Field(default=20, ge=1)
    score_eligible: bool = False
    sample_confidence: PhysicalSampleConfidence = (
        PhysicalSampleConfidence.NO_PHYSICAL_SAMPLE
    )
    sampled_only: Literal[True] = True
    providers: dict[str, AccuracyBucket]
    segments: dict[str, AccuracyBucket]
    identity_status_breakdown: dict[str, int] = Field(default_factory=dict)
    identification_evidence_breakdown: dict[str, int] = Field(default_factory=dict)


class VerificationSuggestion(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    physical_store_id: str
    grocery_context_id: str
    source_provider: str
    product_id: str
    gtin: str | None = None
    product_name: str
    brand: str | None = None
    category: str | None = None
    package_description: str | None = None
    current_price: Decimal
    sale_model: SaleModel
    promotion_type: PromotionType | None = None
    stratum: PhysicalPriceSemantics = PhysicalPriceSemantics.REGULAR
    priority_score: Decimal = Field(ge=0)
    reasons: tuple[str, ...]


class PhysicalValidationSession(BaseModel):
    """Bounded voluntary field session; it never controls basket eligibility."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    physical_store_id: str = Field(min_length=1, max_length=64)
    chain: str = Field(min_length=1, max_length=32)
    store_name: str = Field(min_length=1, max_length=1000)
    status: PhysicalValidationSessionStatus = PhysicalValidationSessionStatus.ACTIVE
    blind_capture: bool = True
    target_count: int = Field(default=20, ge=1, le=100)
    sampling_strategy: str = Field(default="stratified", min_length=1, max_length=64)
    notes: str | None = Field(default=None, max_length=2000)
    suggestion_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    started_at: datetime
    completed_at: datetime | None = None

    @field_validator("started_at", "completed_at")
    @classmethod
    def session_time_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("session timestamps must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_completion(self) -> PhysicalValidationSession:
        if self.status is PhysicalValidationSessionStatus.COMPLETED:
            if self.completed_at is None:
                raise ValueError("completed session requires completed_at")
        elif self.completed_at is not None:
            raise ValueError("only a completed session may have completed_at")
        return self


class PhysicalValidationSessionItem(BaseModel):
    """Immutable target plus all digital rows captured at session start."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(min_length=1, max_length=64)
    ordinal: int = Field(ge=1, le=100)
    stratum: PhysicalPriceSemantics
    target_gtin: str | None = None
    target_product_name: str = Field(min_length=1, max_length=1000)
    target_brand: str | None = Field(default=None, max_length=500)
    target_category: str | None = Field(default=None, max_length=500)
    target_package_description: str | None = Field(default=None, max_length=128)
    target_product_id: str | None = Field(default=None, min_length=1, max_length=255)
    target_source_provider: str | None = Field(default=None, min_length=1, max_length=32)
    target_grocery_context_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    target_external_product_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    target_store_external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    target_sale_model: SaleModel = SaleModel.UNKNOWN
    identifier_status: SessionItemIdentifierStatus = SessionItemIdentifierStatus.UNKNOWN_GTIN
    reasons: tuple[str, ...] = ()
    candidate_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    candidates: tuple[DigitalPriceCandidate, ...] = ()
    captured_observation_id: str | None = None

    @field_validator("target_gtin")
    @classmethod
    def normalize_target_gtin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = "".join(character for character in value if character not in " -")
        if not normalized.isdigit() or len(normalized) not in {8, 12, 13, 14}:
            raise ValueError("target_gtin must contain 8, 12, 13 or 14 digits")
        return normalized


class ProductIdentifierEvidence(BaseModel):
    """Persistent, source-explicit product identifier evidence.

    Identifier enrichment is deliberately separate from immutable price
    snapshots. ``scope_key`` is an exact source/store scope (never a fuzzy
    geographic guess), so evidence is not silently shared across contexts.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    chain: Chain
    source_provider: str = Field(min_length=1, max_length=32)
    scope_key: str = Field(min_length=1, max_length=255)
    source_product_id: str | None = Field(default=None, min_length=1, max_length=255)
    external_product_id: str = Field(min_length=1, max_length=255)
    identifier_type: ProductIdentifierType
    identifier_value: str = Field(min_length=1, max_length=255)
    evidence_source: ProductIdentifierEvidenceSource
    evidence_reference: str = Field(min_length=1, max_length=2000)
    evidence_payload_sha256: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    observed_at: datetime
    confidence: Confidence
    active: bool = True

    @field_validator("observed_at")
    @classmethod
    def identifier_time_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("identifier evidence timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_identifier_value(self) -> ProductIdentifierEvidence:
        if self.identifier_type is ProductIdentifierType.GTIN:
            normalized = normalize_gtin(self.identifier_value).normalized_gtin
            if normalized != self.identifier_value:
                raise ValueError("GTIN evidence must already be normalized")
        return self


class ShelfIdentifierEvidence(BaseModel):
    """Uninterpreted shelf-code evidence; never an implicit GTIN mapping."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    id: str = Field(min_length=1, max_length=64)
    chain: Chain
    physical_store_id: str = Field(min_length=1, max_length=64)
    validation_session_id: str | None = Field(default=None, min_length=1, max_length=64)
    validation_session_item_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    selected_source_product_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    raw_value: str = Field(min_length=1, max_length=255)
    barcode_format: str = Field(min_length=1, max_length=64)
    observed_at: datetime
    verified: bool = False

    @field_validator("observed_at")
    @classmethod
    def shelf_identifier_time_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("shelf identifier timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def diagnostic_is_not_authoritative(self) -> ShelfIdentifierEvidence:
        if self.verified:
            raise ValueError("new shelf-code diagnostics cannot be authoritative")
        if (self.validation_session_id is None) != (
            self.validation_session_item_id is None
        ):
            raise ValueError("shelf-code session and item IDs must be provided together")
        return self


class PhysicalIdentifierPreparation(BaseModel):
    """Bounded per-session identifier preparation counters."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    validation_session_id: str = Field(min_length=1, max_length=64)
    target_products: int = Field(ge=0, le=100)
    known_gtin_before: int = Field(ge=0, le=100)
    enriched_gtin: int = Field(default=0, ge=0, le=100)
    gtin_unavailable: int = Field(default=0, ge=0, le=100)
    weight_no_gtin_required: int = Field(default=0, ge=0, le=100)
    true_unresolved: int = Field(default=0, ge=0, le=100)
    detail_requests: int = Field(default=0, ge=0, le=120)
    cache_hits: int = Field(default=0, ge=0, le=100)
    errors: int = Field(default=0, ge=0, le=100)
    request_limit: int = Field(default=20, ge=0, le=120)

    @model_validator(mode="after")
    def validate_preparation_counts(self) -> PhysicalIdentifierPreparation:
        identified = (
            self.known_gtin_before
            + self.enriched_gtin
            + self.gtin_unavailable
            + self.weight_no_gtin_required
            + self.true_unresolved
        )
        if identified > self.target_products:
            raise ValueError("identifier preparation counts exceed target products")
        if self.detail_requests > self.request_limit:
            raise ValueError("identifier detail requests exceed the session budget")
        return self


__all__ = [
    "AccuracyBucket",
    "DigitalPriceCandidate",
    "PhysicalIdentificationEvidence",
    "PhysicalIdentifierPreparation",
    "PhysicalObservationAmendment",
    "PhysicalObservationAmendmentKind",
    "PhysicalObservationTimePrecision",
    "PhysicalPriceComparison",
    "PhysicalPriceComparisonStatus",
    "PhysicalPriceObservation",
    "PhysicalPriceSemantics",
    "PhysicalProductIdentityStatus",
    "PhysicalSampleConfidence",
    "PhysicalValidationSession",
    "PhysicalValidationSessionItem",
    "PhysicalValidationSessionStatus",
    "ProductIdentifierEvidence",
    "ProductIdentifierEvidenceSource",
    "ProductIdentifierType",
    "PromotionComparisonStatus",
    "SessionItemIdentifierStatus",
    "ShelfIdentifierEvidence",
    "SourceAccuracyReport",
    "VerificationSuggestion",
    "WeightPriceType",
    "canonical_physical_observation_payload",
    "physical_observation_payload_sha256",
]
