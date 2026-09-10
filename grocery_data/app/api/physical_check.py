from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from statistics import median
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.api.dependencies import get_session
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    PriceContextType,
    PromotionType,
    SaleModel,
)
from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalObservationAmendment,
    PhysicalObservationAmendmentKind,
    PhysicalObservationTimePrecision,
    PhysicalPriceComparison,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    PhysicalValidationSession,
    PhysicalValidationSessionItem,
    PhysicalValidationSessionStatus,
    SessionItemIdentifierStatus,
    ShelfIdentifierEvidence,
    WeightPriceType,
    physical_observation_payload_sha256,
)
from grocery_data.app.field_security import PHYSICAL_CHECK_CONTRACT
from grocery_data.app.services.physical_identifier_enrichment import (
    HemkopProductDetailIdentifierEnricher,
    IdentifierEnrichmentTarget,
    PhysicalProductIdentifierEnricher,
)
from grocery_data.app.services.physical_observation_amendments import (
    PhysicalObservationAmendmentService,
)
from grocery_data.app.services.physical_price_candidates import (
    ExternalPhysicalPriceCandidateReader,
    PersistedExternalPhysicalPriceCandidateReader,
    PersistedPhysicalPriceCandidateReader,
    combined_candidates_for_observation,
    combined_candidates_for_store,
    expected_providers_for_store,
    physical_observation_from_row,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
    PhysicalVerificationSuggestionSampler,
    build_accuracy_report,
    compare_frozen_session_observation,
    derived_observation_confidence,
)
from grocery_data.app.services.physical_session_reconciliation import (
    PhysicalSessionComparisonBundle,
    PhysicalSessionReconciliationService,
)
from grocery_data.app.services.physical_source_price_evidence import (
    PhysicalSourceSemanticPriceAdapter,
    SemanticPriceDiagnostic,
)
from grocery_data.app.services.physical_validation_sessions import (
    build_physical_validation_session,
)
from grocery_data.app.services.physical_validation_v3 import (
    PhysicalValidationV3Service,
)
from grocery_data.app.storage.models import (
    BarcodeScanDiagnosticModel,
    PhysicalPriceObservationModel,
    PhysicalStoreModel,
    StoreContextLinkModel,
)
from grocery_data.app.storage.repositories import (
    PhysicalObservationAmendmentHeadConflict,
    PhysicalObservationAmendmentRepository,
    PhysicalPriceObservationRepository,
    PhysicalStoreRepository,
    PhysicalValidationSessionRepository,
    ProductIdentifierEvidenceRepository,
    ShelfIdentifierEvidenceRepository,
)

router = APIRouter(tags=["physical-validation"])
SessionDep = Annotated[Session, Depends(get_session)]
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _csv_safe_cell(value: object) -> object:
    """Prevent spreadsheet formula execution in the optional field export."""

    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


class PhysicalPriceObservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_store_id: str = Field(min_length=1, max_length=64)
    gtin: str | None = None
    product_name: str | None = Field(default=None, max_length=1000)
    shelf_price: Decimal = Field(gt=0)
    comparison_price: Decimal | None = Field(default=None, gt=0)
    comparison_unit: str | None = Field(default=None, max_length=32)
    promotion_type: PromotionType | None = None
    member_only: bool | None = None
    multibuy_quantity: int | None = Field(default=None, ge=1)
    multibuy_total_price: Decimal | None = Field(default=None, gt=0)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    notes: str | None = Field(default=None, max_length=2000)
    photo_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_identity(self) -> PhysicalPriceObservationCreate:
        if not (self.gtin or "").strip() and not (self.product_name or "").strip():
            raise ValueError("gtin or product_name is required")
        return self


class PhysicalValidationSessionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_store_id: str = Field(min_length=1, max_length=64)
    target_sample_size: int = Field(default=25, ge=1, le=100)
    sampling_strategy: Literal["stratified"] = "stratified"
    blind_capture: bool = True
    notes: str | None = Field(default=None, max_length=2000)


class PhysicalValidationCaptureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gtin: str | None = None
    product_name: str | None = Field(default=None, max_length=1000)
    shelf_price: Decimal = Field(gt=0)
    price_semantics: PhysicalPriceSemantics = PhysicalPriceSemantics.REGULAR
    # V3 separates the thing being priced from promotional conditions.  The
    # legacy price_semantics field remains accepted for older field clients.
    price_basis: Literal["package", "weight"] | None = None
    promotion_mechanism: Literal["none", "sale", "multibuy", "unknown"] | None = None
    member_only: bool | None = None
    identity_status: PhysicalProductIdentityStatus = PhysicalProductIdentityStatus.EXACT
    identification_evidence: PhysicalIdentificationEvidence | None = None
    comparison_price: Decimal | None = Field(default=None, gt=0)
    comparison_unit: str | None = Field(default=None, max_length=32)
    regular_shelf_price: Decimal | None = Field(default=None, gt=0)
    weight_price_type: WeightPriceType | None = None
    multibuy_quantity: int | None = Field(default=None, ge=2)
    multibuy_total_price: Decimal | None = Field(default=None, gt=0)
    promotion_text: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=2000)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    client_request_id: str | None = Field(
        default=None,
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    @model_validator(mode="after")
    def validate_capture_fields(self) -> PhysicalValidationCaptureCreate:
        uses_compound_contract = (
            self.price_basis is not None
            or self.promotion_mechanism is not None
            or self.member_only is not None
        )
        if uses_compound_contract:
            basis = self.price_basis or (
                "weight"
                if self.price_semantics is PhysicalPriceSemantics.WEIGHT
                else "package"
            )
            mechanism = self.promotion_mechanism or "none"
            member_only = bool(self.member_only)
            self.price_basis = basis
            self.promotion_mechanism = mechanism
            self.member_only = member_only
            if basis == "weight":
                if mechanism == "multibuy":
                    raise ValueError("weight price basis cannot use multibuy")
                self.price_semantics = PhysicalPriceSemantics.WEIGHT
                self.weight_price_type = (
                    WeightPriceType.SALE
                    if mechanism == "sale"
                    else WeightPriceType.UNKNOWN
                    if mechanism == "unknown"
                    else WeightPriceType.MEMBER
                    if member_only
                    else WeightPriceType.REGULAR
                )
            else:
                self.price_semantics = (
                    PhysicalPriceSemantics.MULTIBUY
                    if mechanism == "multibuy"
                    else PhysicalPriceSemantics.SALE
                    if mechanism == "sale"
                    else PhysicalPriceSemantics.MEMBER
                    if member_only
                    else PhysicalPriceSemantics.UNKNOWN
                    if mechanism == "unknown"
                    else PhysicalPriceSemantics.REGULAR
                )
        if self.price_semantics is not PhysicalPriceSemantics.WEIGHT and (
            (self.comparison_price is None) != (self.comparison_unit is None)
        ):
            raise ValueError("comparison price and unit must be provided together")
        if (self.multibuy_quantity is None) != (self.multibuy_total_price is None):
            raise ValueError("multibuy quantity and total price must be provided together")
        if self.price_semantics is PhysicalPriceSemantics.MULTIBUY:
            if self.multibuy_quantity is None:
                raise ValueError("multibuy capture requires quantity and total price")
        elif self.multibuy_quantity is not None:
            raise ValueError("multibuy fields require multibuy price semantics")
        if (
            self.price_semantics is PhysicalPriceSemantics.WEIGHT
            and self.comparison_unit is None
        ):
            raise ValueError("weight capture requires a shelf-price unit")
        if self.price_semantics is PhysicalPriceSemantics.WEIGHT:
            if self.weight_price_type is None:
                self.weight_price_type = WeightPriceType.UNKNOWN
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


class PhysicalObservationAmendmentCreate(BaseModel):
    """Explicit append-only evidence supplied after a session was completed."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["late_capture", "correction"]
    observation: PhysicalValidationCaptureCreate
    base_observation_id: str | None = Field(default=None, min_length=1, max_length=64)
    supersedes_amendment_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    observed_at_precision: Literal[
        "exact",
        "minute",
        "hour",
        "day",
        "visit_window",
        "unknown",
    ]
    reason: str = Field(min_length=1, max_length=2000)
    evidence_source: str = Field(min_length=1, max_length=64)
    evidence_reference: str = Field(min_length=1, max_length=1000)
    client_request_id: str = Field(
        min_length=16,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    @model_validator(mode="after")
    def validate_amendment_contract(self) -> PhysicalObservationAmendmentCreate:
        if "observed_at" not in self.observation.model_fields_set:
            raise ValueError("amendment observation requires an explicit observed_at")
        if self.observation.client_request_id is not None:
            raise ValueError("use the amendment-level client_request_id")
        if self.kind == "late_capture" and (
            self.base_observation_id is not None
            or self.supersedes_amendment_id is not None
        ):
            raise ValueError("late capture cannot supersede existing evidence")
        if self.kind == "correction" and (
            self.base_observation_id is None
            and self.supersedes_amendment_id is None
        ):
            raise ValueError(
                "correction requires base_observation_id or supersedes_amendment_id"
            )
        return self


class PhysicalIdentifierPreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_requests: Literal[1] = 1


class ShelfIdentifierEvidenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    physical_store_id: str = Field(min_length=1, max_length=64)
    validation_session_id: str | None = Field(default=None, min_length=1, max_length=64)
    validation_session_item_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
    )
    raw_value: str = Field(min_length=1, max_length=255)
    barcode_format: Literal[
        "CODE_128",
        "CODE_39",
        "ITF",
        "EAN_13",
        "EAN_8",
        "UPC_A",
        "UPC_E",
        "RSS_14",
        "RSS_EXPANDED",
    ]
    observed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class PhysicalValidationSessionComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")

    completed_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


ScannerProvider = Literal["native_barcode_detector", "zxing", "manual"]
ScannerOutcome = Literal["success", "failure", "manual_fallback", "no_match"]
ScannerBarcodeFormat = Literal["EAN_13", "EAN_8", "UPC_A", "UPC_E", "CODE_128"]
ScannerFailureReason = Literal[
    "permission_denied",
    "no_camera",
    "camera_busy",
    "initialization_failed",
    "unsupported_browser",
    "no_barcode_detected",
    "invalid_checksum",
    "decode_failed",
    "cancelled",
    "unknown",
]


class BarcodeScanDiagnosticCreate(BaseModel):
    """One bounded scanner event without barcode or user-identifying data."""

    model_config = ConfigDict(extra="forbid")

    scanner_provider: ScannerProvider
    outcome: ScannerOutcome
    barcode_format: ScannerBarcodeFormat | None = None
    duration_ms: int | None = Field(default=None, ge=0, le=120_000)
    failure_reason: ScannerFailureReason | None = None

    @model_validator(mode="after")
    def validate_event_semantics(self) -> BarcodeScanDiagnosticCreate:
        if self.scanner_provider == "manual":
            if self.outcome != "manual_fallback":
                raise ValueError("manual provider requires manual_fallback outcome")
            if self.barcode_format is not None:
                raise ValueError("manual fallback must not claim a decoded barcode format")
        elif self.outcome == "manual_fallback":
            raise ValueError("manual_fallback outcome requires manual provider")
        if self.outcome == "failure" and self.failure_reason is None:
            raise ValueError("failed scan requires a bounded failure reason")
        if self.outcome != "failure" and self.failure_reason is not None:
            raise ValueError("failure reason is valid only for failed scans")
        return self


def _capture_observation_id(
    validation_session_id: str,
    item_id: str,
    client_request_id: str | None,
) -> str:
    if client_request_id is None:
        return uuid4().hex
    return uuid5(
        NAMESPACE_URL,
        f"physical-check:{validation_session_id}:{item_id}:{client_request_id}",
    ).hex


def _amendment_id(
    validation_session_id: str,
    item_id: str,
    client_request_id: str,
) -> str:
    return uuid5(
        NAMESPACE_URL,
        f"physical-check-amendment:{validation_session_id}:{item_id}:{client_request_id}",
    ).hex


def _external_reader(
    request: Request,
    session: Session,
) -> ExternalPhysicalPriceCandidateReader:
    """Return the injected reader or the credential-free persisted cache."""

    configured = getattr(
        request.app.state,
        "external_physical_price_candidate_reader",
        None,
    )
    return configured or PersistedExternalPhysicalPriceCandidateReader(session)


def _identifier_enricher(request: Request) -> PhysicalProductIdentifierEnricher:
    configured = getattr(request.app.state, "physical_product_identifier_enricher", None)
    if configured is not None:
        return configured
    settings = getattr(request.app.state, "settings", None) or GroceryDataSettings.from_env()
    return HemkopProductDetailIdentifierEnricher(raw_root=settings.raw_snapshot_root)


def _default_identification_evidence(
    status: PhysicalProductIdentityStatus,
    *,
    gtin: str | None,
) -> PhysicalIdentificationEvidence:
    return {
        PhysicalProductIdentityStatus.EXACT: (
            PhysicalIdentificationEvidence.GTIN_VERIFIED
            if gtin is not None
            else PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL
        ),
        PhysicalProductIdentityStatus.GTIN_MATCH: (
            PhysicalIdentificationEvidence.GTIN_VERIFIED
        ),
        PhysicalProductIdentityStatus.GTIN_MISMATCH: (
            PhysicalIdentificationEvidence.UNVERIFIED
        ),
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
        PhysicalProductIdentityStatus.NO_MATCH: (
            PhysicalIdentificationEvidence.UNVERIFIED
        ),
    }[status]


def _physical_store_item(
    row: PhysicalStoreModel,
    *,
    observation_count: int = 0,
    minimum_sample: int = 20,
) -> dict[str, object]:
    if observation_count == 0:
        sample_confidence = "no_physical_sample"
    elif observation_count < minimum_sample:
        sample_confidence = "limited_sample"
    else:
        sample_confidence = "good_sample"
    return {
        "id": row.id,
        "chain": row.chain,
        "external_store_id": row.external_store_id,
        "external_store_aliases": tuple(row.external_store_aliases or ()),
        "name": row.name,
        "address": row.address,
        "postal_code": row.postal_code,
        "city": row.city,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "active": row.is_active,
        "lifecycle_state": row.lifecycle_state,
        "physical_observations": observation_count,
        "physical_sample_confidence": sample_confidence,
        "accuracy_score_available": observation_count >= minimum_sample,
        "minimum_sample_for_accuracy_score": minimum_sample,
    }


def _digital_price_presentation(
    session: Session,
    *,
    physical_store_id: str,
    chain: Chain,
    candidates: list[tuple[str, DigitalPriceCandidate]],
) -> dict[tuple[str, str], tuple[str | None, str, str]]:
    """Describe persisted digital context semantics without claiming shelf parity."""

    normalized_chain = Chain(chain)
    identities = {
        (candidate.source_provider, candidate.grocery_context_id)
        for _, candidate in candidates
    }
    if not identities:
        return {}
    links = session.scalars(
        select(StoreContextLinkModel).where(
            StoreContextLinkModel.physical_store_id == physical_store_id,
            StoreContextLinkModel.is_active.is_(True),
        )
    )
    context_types = {
        (link.source_provider, link.grocery_context_id): link.price_context_type
        for link in links
        if (link.source_provider, link.grocery_context_id) in identities
    }
    result: dict[tuple[str, str], tuple[str | None, str, str]] = {}
    for identity in identities:
        context_type = context_types.get(identity)
        if context_type in {
            PriceContextType.ONLINE_STORE.value,
            PriceContextType.ONLINE_FULFILLMENT.value,
        }:
            label = {
                Chain.COOP: "Coop onlinepris",
                Chain.ICA: "ICA onlinepris",
            }.get(normalized_chain, "Onlinepris")
            semantics = "online_price"
        elif context_type == PriceContextType.REGIONAL.value:
            label = "Regionalt digitalpris"
            semantics = "regional_digital_price"
        elif context_type == PriceContextType.PHYSICAL_STORE.value:
            label = "Butikskopplat digitalpris"
            semantics = "store_linked_digital_price"
        else:
            label = "Digitalt pris"
            semantics = "digital_price"
        result[identity] = (context_type, semantics, label)
    return result


def _session_candidate_payload(
    candidate: DigitalPriceCandidate,
    *,
    presentation: dict[tuple[str, str], tuple[str | None, str, str]],
) -> dict[str, object]:
    context = presentation.get(
        (candidate.source_provider, candidate.grocery_context_id),
        (None, "digital_price", "Digitalt pris"),
    )
    return {
        "source_provider": candidate.source_provider,
        "grocery_context_id": candidate.grocery_context_id,
        "source_snapshot_id": candidate.source_snapshot_id,
        "digital_observed_at": candidate.observed_at,
        "product_id": candidate.product_id,
        "product_name": candidate.product_name,
        "gtin": candidate.gtin,
        "package": candidate.package_description,
        "digital_price": candidate.current_price,
        "regular_price": candidate.regular_price,
        "member_price": candidate.member_price,
        "comparison_price": candidate.comparison_price,
        "comparison_unit": candidate.comparison_unit,
        "promotion_type": candidate.promotion_type,
        "member_only": candidate.member_only,
        "multibuy_quantity": candidate.multibuy_quantity,
        "multibuy_total_price": candidate.multibuy_total_price,
        "price_context_type": context[0],
        "price_semantics": context[1],
        "price_label": context[2],
    }


def _session_payload(
    database_session: Session,
    validation_session: PhysicalValidationSession,
    items: tuple[PhysicalValidationSessionItem, ...],
) -> dict[str, object]:
    staged = [
        ("frozen_session_evidence", candidate)
        for item in items
        for candidate in item.candidates
    ]
    presentation = _digital_price_presentation(
        database_session,
        physical_store_id=validation_session.physical_store_id,
        chain=Chain(validation_session.chain),
        candidates=staged,
    )
    response_items: list[dict[str, object]] = []
    for item in items:
        captured = item.captured_observation_id is not None
        reveal = captured or not validation_session.blind_capture
        weight_item = item.target_sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }
        response_items.append(
            {
                "id": item.id,
                "ordinal": item.ordinal,
                "stratum": item.stratum,
                "target_gtin": item.target_gtin,
                "target_product_name": item.target_product_name,
                "target_brand": item.target_brand,
                "target_category": item.target_category,
                "target_package": item.target_package_description,
                "display_package": (
                    "Viktvara / kr per kg"
                    if weight_item
                    else item.target_package_description
                ),
                "target_product_id": item.target_product_id,
                "target_source_provider": item.target_source_provider,
                "target_grocery_context_id": item.target_grocery_context_id,
                "target_external_product_id": item.target_external_product_id,
                "target_sale_model": item.target_sale_model,
                "identifier_status": item.identifier_status,
                "weight_item": weight_item,
                "barcode_required": False,
                "barcode_recommended": not weight_item,
                "manual_exact_allowed": True,
                "identifier_enrichment_available": bool(
                    not weight_item
                    and item.target_source_provider == "own"
                    and item.target_external_product_id
                    and item.target_store_external_id
                ),
                "shelf_price_unit": "SEK/kg" if weight_item else None,
                "reasons": item.reasons,
                "captured": captured,
                "captured_observation_id": item.captured_observation_id,
                "digital_price_hidden": not reveal,
                "digital_evidence": (
                    [
                        _session_candidate_payload(
                            candidate,
                            presentation=presentation,
                        )
                        for candidate in item.candidates
                    ]
                    if reveal
                    else []
                ),
            }
        )
    captured_count = sum(item.captured_observation_id is not None for item in items)
    composition: dict[str, int] = {}
    for item in items:
        composition[item.stratum.value] = composition.get(item.stratum.value, 0) + 1
    preparation = PhysicalValidationSessionRepository(database_session).preparation(
        validation_session.id
    )
    return {
        "physical_check_contract": PHYSICAL_CHECK_CONTRACT,
        "session": validation_session.model_dump(mode="json"),
        "items": response_items,
        "available_suggestions": len(items),
        "progress": {
            "captured": captured_count,
            "target": validation_session.target_count,
            "complete": validation_session.status
            is PhysicalValidationSessionStatus.COMPLETED,
        },
        "sample_composition": composition,
        "identifier_preparation": (
            preparation.model_dump(mode="json") if preparation is not None else None
        ),
        "sampled_only": True,
        "physical_validation_required": False,
        "live_provider_requests": 0,
    }


def _promotion_fields(
    semantics: PhysicalPriceSemantics,
    *,
    weight_price_type: WeightPriceType | None = None,
) -> tuple[PromotionType | None, bool | None]:
    if semantics is PhysicalPriceSemantics.WEIGHT:
        return {
            WeightPriceType.REGULAR: (None, False),
            WeightPriceType.SALE: (PromotionType.SALE_PRICE, False),
            WeightPriceType.MEMBER: (PromotionType.MEMBER_PRICE, True),
            WeightPriceType.UNKNOWN: (None, None),
            None: (None, False),
        }[weight_price_type]
    return {
        PhysicalPriceSemantics.REGULAR: (None, False),
        PhysicalPriceSemantics.SALE: (PromotionType.SALE_PRICE, False),
        PhysicalPriceSemantics.MEMBER: (PromotionType.MEMBER_PRICE, True),
        PhysicalPriceSemantics.MULTIBUY: (PromotionType.MULTIBUY, False),
        PhysicalPriceSemantics.UNKNOWN: (None, None),
    }[semantics]


def _compound_comparison_output(
    observation: PhysicalPriceObservation,
    comparisons: tuple[PhysicalPriceComparison, ...],
    *,
    semantic_diagnostic: SemanticPriceDiagnostic | None = None,
) -> dict[str, object]:
    """Stable V3 projection for the compact post-save mobile summary."""

    weight_basis = observation.price_semantics is PhysicalPriceSemantics.WEIGHT
    basis = "weight" if weight_basis else "package"
    unit = "SEK/kg" if weight_basis else "SEK/package"
    promotion_type = observation.promotion_type
    mechanism = (
        "multibuy"
        if promotion_type is PromotionType.MULTIBUY
        else "sale"
        if promotion_type in {PromotionType.SALE_PRICE, PromotionType.PERCENT_DISCOUNT}
        else "unknown"
        if promotion_type is PromotionType.OTHER
        else "none"
    )
    comparison = comparisons[0] if comparisons else None
    semantically_comparable = bool(
        comparison is not None
        and comparison.digital_price is not None
        and semantic_diagnostic is not None
        and semantic_diagnostic.comparable
    )
    result_status = (
        comparison.status.value
        if semantically_comparable and comparison is not None
        else "not_comparable"
    )
    return {
        "physical": {
            "price": observation.shelf_price,
            "basis": basis,
            "unit": unit,
            "promotion_mechanism": mechanism,
            "member_only": bool(observation.member_only),
            "multibuy_quantity": observation.multibuy_quantity,
            "multibuy_total_price": observation.multibuy_total_price,
        },
        "digital": (
            {
                "price": comparison.digital_price,
                "basis": basis,
                "unit": unit,
                "promotion_type": (
                    comparison.digital_promotion_type.value
                    if comparison.digital_promotion_type is not None
                    else None
                ),
                "promotion_status": comparison.promotion_status.value,
            }
            if comparison is not None
            else None
        ),
        "result": (
            {
                "status": result_status,
                "signed_difference": comparison.signed_difference,
                "member_restriction_match": comparison.member_restriction_match,
                "multibuy_match": comparison.multibuy_match,
                "semantically_comparable": semantically_comparable,
                "comparison_basis": (
                    semantic_diagnostic.physical.basis.value
                    if semantic_diagnostic is not None
                    and semantic_diagnostic.physical is not None
                    else None
                ),
                "promotion_eligibility": (
                    semantic_diagnostic.physical.eligibility.value
                    if semantic_diagnostic is not None
                    and semantic_diagnostic.physical is not None
                    else None
                ),
                "promotion_mechanism": (
                    semantic_diagnostic.physical.mechanism.value
                    if semantic_diagnostic is not None
                    and semantic_diagnostic.physical is not None
                    else None
                ),
                "not_comparable_reasons": (
                    list(semantic_diagnostic.mismatch_dimensions)
                    if semantic_diagnostic is not None
                    else ["digital_semantics_unavailable"]
                ),
            }
            if comparison is not None
            else {
                "status": "not_comparable",
                "semantically_comparable": False,
                "not_comparable_reasons": ["no_digital_match"],
            }
        ),
    }


def _target_semantic_diagnostic(
    database_session: Session,
    observation: PhysicalPriceObservation,
    candidates: tuple[DigitalPriceCandidate, ...],
    *,
    item: PhysicalValidationSessionItem,
) -> SemanticPriceDiagnostic | None:
    target = next(
        (
            candidate
            for candidate in candidates
            if (
                candidate.source_provider == item.target_source_provider
                and candidate.grocery_context_id == item.target_grocery_context_id
                and candidate.product_id == item.target_product_id
            )
        ),
        None,
    )
    if target is None:
        return None
    return PhysicalSourceSemanticPriceAdapter(database_session).compare(
        observation,
        target,
    )


def _frozen_session_comparisons(
    observation: PhysicalPriceObservation,
    candidates: tuple[DigitalPriceCandidate, ...],
    *,
    database_session: Session,
    item: PhysicalValidationSessionItem | None = None,
) -> tuple[PhysicalPriceComparison, ...]:
    adapter = PhysicalSourceSemanticPriceAdapter(database_session)
    adjusted = tuple(
        adapter.compare(observation, candidate).adjusted_candidate
        for candidate in candidates
    )
    return compare_frozen_session_observation(
        observation,
        adjusted,
        item=item,
    )


def _build_amended_observation(
    database_session: Session,
    validation_session: PhysicalValidationSession,
    item: PhysicalValidationSessionItem,
    payload: PhysicalValidationCaptureCreate,
    *,
    observation_id: str,
) -> tuple[
    PhysicalPriceObservation,
    tuple[PhysicalPriceComparison, ...],
    SemanticPriceDiagnostic | None,
]:
    """Validate a recovered payload exactly against its immutable session item."""

    product_name = (payload.product_name or item.target_product_name).strip()
    normalized_name = " ".join(product_name.casefold().split())
    expected_name = " ".join(item.target_product_name.casefold().split())
    normalized_gtin = payload.gtin
    if payload.gtin:
        try:
            normalized_gtin = normalize_gtin(payload.gtin).normalized_gtin
        except InvalidGtinError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    exact_manual_target = normalized_name == expected_name
    target_is_weight = item.target_sale_model in {
        SaleModel.SOLD_BY_WEIGHT,
        SaleModel.VARIABLE_WEIGHT_PACKAGE,
    }
    if (payload.price_semantics is PhysicalPriceSemantics.WEIGHT) != target_is_weight:
        raise HTTPException(
            status_code=422,
            detail="SEK/kg price semantics must match a verified weight product",
        )
    if payload.identity_status is PhysicalProductIdentityStatus.GTIN_MATCH:
        if item.target_gtin is None or normalized_gtin != item.target_gtin:
            raise HTTPException(
                status_code=422,
                detail="GTIN match requires the exact verified target GTIN",
            )
    elif payload.identity_status is PhysicalProductIdentityStatus.GTIN_MISMATCH:
        if item.target_gtin is None or normalized_gtin is None:
            raise HTTPException(
                status_code=422,
                detail="GTIN mismatch requires both a scanned and verified target GTIN",
            )
        if normalized_gtin == item.target_gtin:
            raise HTTPException(status_code=422, detail="the scanned GTIN matches the target")
    elif payload.identity_status is PhysicalProductIdentityStatus.GTIN_NOT_KNOWN_BY_SOURCE:
        if item.target_gtin is not None or normalized_gtin is None:
            raise HTTPException(
                status_code=422,
                detail="unknown-source GTIN requires a valid scan and no verified source GTIN",
            )
        if not exact_manual_target:
            raise HTTPException(
                status_code=422,
                detail="unknown-source GTIN requires manual confirmation of the exact target",
            )
    elif payload.identity_status is PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH:
        if not exact_manual_target:
            raise HTTPException(
                status_code=422,
                detail="manual exact identity must match the immutable session target",
            )
        normalized_gtin = None
    elif payload.identity_status is PhysicalProductIdentityStatus.WEIGHT_ITEM_NO_GTIN_REQUIRED:
        if not target_is_weight or not exact_manual_target:
            raise HTTPException(
                status_code=422,
                detail="weight identity requires the exact selected weight product",
            )
        normalized_gtin = None
    elif payload.identity_status is PhysicalProductIdentityStatus.SHELF_CODE_MATCH:
        raise HTTPException(
            status_code=422,
            detail="shelf codes are diagnostic until a verified mapping exists",
        )
    elif payload.identity_status is PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN:
        normalized_gtin = None

    evidence = payload.identification_evidence or _default_identification_evidence(
        payload.identity_status,
        gtin=normalized_gtin,
    )
    promotion_type, derived_member_only = _promotion_fields(
        payload.price_semantics,
        weight_price_type=payload.weight_price_type,
    )
    member_only = (
        payload.member_only
        if payload.member_only is not None
        else derived_member_only
    )
    try:
        provisional = PhysicalPriceObservation(
            id=observation_id,
            physical_store_id=validation_session.physical_store_id,
            gtin=normalized_gtin,
            product_name=product_name,
            shelf_price=payload.shelf_price,
            comparison_price=payload.comparison_price,
            comparison_unit=payload.comparison_unit,
            promotion_type=promotion_type,
            member_only=member_only,
            multibuy_quantity=payload.multibuy_quantity,
            multibuy_total_price=payload.multibuy_total_price,
            promotion_text=payload.promotion_text,
            observed_at=payload.observed_at,
            confidence=Confidence.UNKNOWN,
            notes=payload.notes,
            validation_session_id=validation_session.id,
            validation_session_item_id=item.id,
            price_semantics=payload.price_semantics,
            identity_status=payload.identity_status,
            identification_evidence=evidence,
            regular_shelf_price=payload.regular_shelf_price,
            weight_price_type=payload.weight_price_type,
            immutable_candidate_set_sha256=item.candidate_set_sha256,
        )
    except ValidationError as exc:
        detail = "; ".join(error["msg"] for error in exc.errors(include_url=False))
        raise HTTPException(status_code=422, detail=detail) from exc

    candidates = item.candidates
    if payload.identity_status is PhysicalProductIdentityStatus.EXACT:
        exact_identity = (
            normalized_gtin is not None
            and (
                normalized_gtin == item.target_gtin
                or any(candidate.gtin == normalized_gtin for candidate in candidates)
            )
        ) or (normalized_gtin is None and exact_manual_target)
        if not exact_identity:
            raise HTTPException(
                status_code=422,
                detail="exact identity must match the immutable session target",
            )
    comparisons = _frozen_session_comparisons(
        provisional,
        candidates,
        database_session=database_session,
        item=item,
    )
    semantic_diagnostic = _target_semantic_diagnostic(
        database_session,
        provisional,
        candidates,
        item=item,
    )
    observation = provisional.model_copy(
        update={
            "confidence": derived_observation_confidence(
                comparisons,
                gtin=provisional.gtin,
                identity_status=provisional.identity_status,
                identification_evidence=provisional.identification_evidence,
            )
        }
    )
    return observation, comparisons, semantic_diagnostic


def _validation_session_report(
    database_session: Session,
    validation_session: PhysicalValidationSession,
) -> tuple[
    list[PhysicalPriceObservation],
    tuple[PhysicalPriceComparison, ...],
    dict[str, object],
    PhysicalSessionComparisonBundle,
]:
    comparison_bundle = PhysicalSessionReconciliationService(
        database_session
    ).current_report(validation_session.id)
    observations = list(comparison_bundle.observations)
    comparisons = comparison_bundle.comparisons
    minimum_sample = GroceryDataSettings.from_env().min_sample_for_accuracy_score
    report = build_accuracy_report(
        observations,
        comparisons,
        scope_label=f"{validation_session.store_name} field sessions",
        minimum_sample=minimum_sample,
    )
    return observations, comparisons, report.model_dump(mode="json"), comparison_bundle


def _completed_v3_official_metadata(
    database_session: Session,
    validation_session: PhysicalValidationSession,
) -> dict[str, object]:
    """Return the completed session's official comparable-sample contract."""

    settings = GroceryDataSettings.from_env()
    return PhysicalValidationV3Service(
        database_session,
        official_freshness_hours=Decimal(
            str(settings.field_validation_max_price_age_hours)
        ),
        minimum_comparable_sample=settings.min_sample_for_accuracy_score,
    ).preview_official(validation_session.id).metadata()


def _completed_v3_amended_metadata(
    database_session: Session,
    validation_session: PhysicalValidationSession,
) -> tuple[dict[str, object], tuple[PhysicalObservationAmendment, ...]] | None:
    """Return the opt-in amended report without changing the official result."""

    settings = GroceryDataSettings.from_env()
    service = PhysicalObservationAmendmentService(
        database_session,
        official_freshness_hours=Decimal(
            str(settings.field_validation_max_price_age_hours)
        ),
        minimum_comparable_sample=settings.min_sample_for_accuracy_score,
    )
    state = service.amended_state(validation_session.id)
    if state is None:
        return None
    metadata = service.v3.amended_report(
        validation_session.id,
        observations=state.effective_observations,
        evidence_sha256=state.effective_evidence_sha256,
    ).metadata()
    return metadata, state.amendments


@router.get("/physical-check", include_in_schema=False)
def physical_check_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "physical-check.html")


@router.get("/physical-check/scanner-test", include_in_schema=False)
def physical_check_scanner_test_page() -> FileResponse:
    """Serve the read-only, authenticated real-device scanner diagnostic."""

    return FileResponse(STATIC_DIR / "scanner-test.html")


@router.get("/physical-check/scanner-test.js", include_in_schema=False)
def physical_check_scanner_test_javascript() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "scanner-test.js",
        media_type="application/javascript",
    )


@router.get("/physical-check/scanner-test.css", include_in_schema=False)
def physical_check_scanner_test_stylesheet() -> FileResponse:
    return FileResponse(STATIC_DIR / "scanner-test.css", media_type="text/css")


@router.get("/physical-check/stores")
def physical_check_stores(
    session: SessionDep,
    city: str | None = None,
    chain: Chain | None = None,
) -> dict[str, object]:
    statement = select(PhysicalStoreModel).where(PhysicalStoreModel.is_active.is_(True))
    if city is not None:
        city_key = city.casefold().strip()
        if not city_key:
            raise HTTPException(status_code=422, detail="city must not be blank")
        statement = statement.where(func.lower(func.trim(PhysicalStoreModel.city)) == city_key)
    if chain is not None:
        statement = statement.where(PhysicalStoreModel.chain == chain.value)
    rows = list(
        session.scalars(statement.order_by(PhysicalStoreModel.chain, PhysicalStoreModel.name))
    )
    counts = dict(
        session.execute(
            select(
                PhysicalPriceObservationModel.physical_store_id,
                func.count(PhysicalPriceObservationModel.id),
            )
            .where(PhysicalPriceObservationModel.physical_store_id.in_([row.id for row in rows]))
            .group_by(PhysicalPriceObservationModel.physical_store_id)
        ).all()
    )
    minimum_sample = GroceryDataSettings.from_env().min_sample_for_accuracy_score
    return {
        "items": [
            _physical_store_item(
                row,
                observation_count=int(counts.get(row.id, 0)),
                minimum_sample=minimum_sample,
            )
            for row in rows
        ],
        "count": len(rows),
        "note": "Physical validation is optional and never controls basket eligibility.",
    }


@router.post("/physical-check/sessions", status_code=201)
def start_physical_validation_session(
    payload: PhysicalValidationSessionCreate,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    store = PhysicalStoreRepository(session).get(payload.physical_store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    if not store.is_active:
        raise HTTPException(status_code=409, detail="physical store is not currently active")
    candidates = combined_candidates_for_store(
        store.id,
        persisted_reader=PersistedPhysicalPriceCandidateReader(session),
        external_reader=_external_reader(request, session),
        limit=5000,
    )
    try:
        validation_session, items = build_physical_validation_session(
            candidates,
            physical_store_id=store.id,
            chain=store.chain,
            store_name=store.name,
            target_count=payload.target_sample_size,
            blind_capture=payload.blind_capture,
            sampling_strategy=payload.sampling_strategy,
            notes=payload.notes,
        )
        repository = PhysicalValidationSessionRepository(session)
        repository.add(validation_session, items)
        max_age_hours = Decimal(
            str(
                (
                    getattr(request.app.state, "settings", None)
                    or GroceryDataSettings.from_env()
                ).field_validation_max_price_age_hours
            )
        )
        candidate_observed_at = tuple(
            candidate.observed_at
            for item in items
            for candidate in item.candidates
        )
        if not candidate_observed_at:
            raise ValueError("validation session has no digital evidence timestamp")
        oldest_observed_at = min(candidate_observed_at)
        oldest_age_hours = Decimal(
            str(
                max(
                    0.0,
                    (
                        validation_session.started_at - oldest_observed_at
                    ).total_seconds()
                    / 3600,
                )
            )
        )
        if oldest_age_hours > max_age_hours:
            session.rollback()
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "refresh_required",
                    "message": (
                        "Prisunderlaget är för gammalt för ett nytt officiellt "
                        "fältpass. Uppdatera priserna och försök igen."
                    ),
                    "oldest_price_age_hours": float(oldest_age_hours.quantize(Decimal("0.01"))),
                    "maximum_price_age_hours": float(max_age_hours),
                },
            )
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    persisted_session = repository.get(validation_session.id)
    assert persisted_session is not None
    return _session_payload(session, persisted_session, repository.items(validation_session.id))


@router.get("/physical-check/sessions/{validation_session_id}")
def get_physical_validation_session(
    validation_session_id: str,
    session: SessionDep,
) -> dict[str, object]:
    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    # Sessions created by the pre-V2 field server have complete immutable
    # candidate evidence but no identifier/preparation companion rows. Persist
    # the conservative additive derivation once so later mobile requests do not
    # depend on a particular request order.
    if repository.ensure_legacy_identifier_state(validation_session_id):
        session.commit()
    return _session_payload(
        session,
        validation_session,
        repository.items(validation_session_id),
    )


async def _enrich_validation_item_identifier(
    *,
    validation_session_id: str,
    item_id: str,
    request: Request,
    session: Session,
) -> dict[str, object]:
    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    if validation_session.status is not PhysicalValidationSessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="validation session is not active")
    items = {item.id: item for item in repository.items(validation_session_id)}
    item = items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="validation session item not found")
    common = {
        "item_id": item_id,
        "target_product_id": item.target_product_id,
        "digital_price_hidden": True,
    }
    if item.target_sale_model in {
        SaleModel.SOLD_BY_WEIGHT,
        SaleModel.VARIABLE_WEIGHT_PACKAGE,
    }:
        return {
            **common,
            "status": "not_required_weight",
            "identifier_status": SessionItemIdentifierStatus.NOT_REQUIRED_WEIGHT,
            "gtin": None,
            "identifier_preparation": repository.preparation(
                validation_session_id
            ).model_dump(mode="json"),
        }
    if item.target_gtin is not None:
        return {
            **common,
            "status": "already_cached",
            "identifier_status": SessionItemIdentifierStatus.KNOWN_GTIN,
            "gtin": item.target_gtin,
            "identifier_preparation": repository.preparation(
                validation_session_id
            ).model_dump(mode="json"),
        }
    if item.identifier_status is SessionItemIdentifierStatus.AMBIGUOUS_GTIN:
        return {
            **common,
            "status": "ambiguous",
            "identifier_status": item.identifier_status,
            "gtin": None,
            "identifier_preparation": repository.preparation(
                validation_session_id
            ).model_dump(mode="json"),
        }
    if item.identifier_status is SessionItemIdentifierStatus.ENRICHMENT_UNAVAILABLE:
        return {
            **common,
            "status": "unavailable",
            "identifier_status": item.identifier_status,
            "gtin": None,
            "reason": "the approved detail source has no verified GTIN",
            "identifier_preparation": repository.preparation(
                validation_session_id
            ).model_dump(mode="json"),
        }
    if (
        Chain(validation_session.chain) is not Chain.HEMKOP
        or item.target_source_provider != "own"
        or not item.target_product_id
        or not item.target_external_product_id
        or not item.target_store_external_id
    ):
        repository.record_identifier_resolution(
            validation_session_id,
            item_id,
            status=SessionItemIdentifierStatus.ENRICHMENT_UNAVAILABLE,
            result="unavailable",
        )
        session.commit()
        preparation = repository.preparation(validation_session_id)
        assert preparation is not None
        return {
            **common,
            "status": "unavailable",
            "identifier_status": SessionItemIdentifierStatus.ENRICHMENT_UNAVAILABLE,
            "gtin": None,
            "reason": "no exact approved product-detail target is available",
            "identifier_preparation": preparation.model_dump(mode="json"),
        }
    if not repository.reserve_identifier_detail_request(validation_session_id):
        session.rollback()
        return {
            **common,
            "status": "budget_exhausted",
            "identifier_status": item.identifier_status,
            "gtin": None,
            "identifier_preparation": repository.preparation(
                validation_session_id
            ).model_dump(mode="json"),
        }
    # The monotonically consumed request budget is committed before the slow
    # network operation.  This avoids holding a SQLite writer lock while the
    # approved detail source is contacted and prevents concurrent over-budget
    # requests from the mobile UI.
    session.commit()
    target = IdentifierEnrichmentTarget(
        chain=Chain.HEMKOP,
        source_provider="own",
        physical_store_id=validation_session.physical_store_id,
        store_external_id=item.target_store_external_id,
        source_product_id=item.target_product_id,
        external_product_id=item.target_external_product_id,
        product_name=item.target_product_name,
    )
    try:
        result = await _identifier_enricher(request).enrich(target)
    except Exception:  # noqa: BLE001 - provider boundary is deliberately fail-closed
        repository.record_identifier_resolution(
            validation_session_id,
            item_id,
            status=SessionItemIdentifierStatus.ENRICHMENT_ERROR,
            result="error",
        )
        session.commit()
        return {
            **common,
            "status": "error",
            "identifier_status": SessionItemIdentifierStatus.ENRICHMENT_ERROR,
            "gtin": None,
            "reason": "approved product-detail enrichment failed",
            "identifier_preparation": repository.preparation(
                validation_session_id
            ).model_dump(mode="json"),
        }
    if result.evidence is not None:
        evidence_row = ProductIdentifierEvidenceRepository(session).add(result.evidence)
        repository.record_identifier_resolution(
            validation_session_id,
            item_id,
            status=SessionItemIdentifierStatus.KNOWN_GTIN,
            evidence_id=evidence_row.id,
            result="enriched",
        )
        response_status = "enriched"
        gtin = result.evidence.identifier_value
    elif result.status == "unavailable":
        repository.record_identifier_resolution(
            validation_session_id,
            item_id,
            status=SessionItemIdentifierStatus.ENRICHMENT_UNAVAILABLE,
            result="unavailable",
        )
        response_status = "unavailable"
        gtin = None
    else:
        repository.record_identifier_resolution(
            validation_session_id,
            item_id,
            status=SessionItemIdentifierStatus.ENRICHMENT_ERROR,
            result="error",
        )
        response_status = "error"
        gtin = None
    session.commit()
    preparation = repository.preparation(validation_session_id)
    assert preparation is not None
    return {
        **common,
        "status": response_status,
        "identifier_status": (
            SessionItemIdentifierStatus.KNOWN_GTIN
            if gtin is not None
            else SessionItemIdentifierStatus.ENRICHMENT_UNAVAILABLE
            if response_status == "unavailable"
            else SessionItemIdentifierStatus.ENRICHMENT_ERROR
        ),
        "gtin": gtin,
        "provider_requests": result.requests,
        "reason": result.reason,
        "identifier_preparation": preparation.model_dump(mode="json"),
    }


@router.post(
    "/physical-check/sessions/{validation_session_id}/items/{item_id}/enrich-identifier"
)
async def enrich_physical_validation_item_identifier(
    validation_session_id: str,
    item_id: str,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    return await _enrich_validation_item_identifier(
        validation_session_id=validation_session_id,
        item_id=item_id,
        request=request,
        session=session,
    )


@router.post("/physical-check/sessions/{validation_session_id}/prepare-identifiers")
async def prepare_physical_validation_identifiers(
    validation_session_id: str,
    payload: PhysicalIdentifierPreparationRequest,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    del payload  # Contract intentionally permits exactly one bounded detail attempt.
    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    pending = next(
        (
            item
            for item in repository.items(validation_session_id)
            if item.identifier_status is SessionItemIdentifierStatus.UNKNOWN_GTIN
            and item.target_sale_model
            not in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}
        ),
        None,
    )
    if pending is None:
        preparation = repository.preparation(validation_session_id)
        assert preparation is not None
        return {
            "status": "complete",
            "processed": 0,
            "identifier_preparation": preparation.model_dump(mode="json"),
        }
    result = await _enrich_validation_item_identifier(
        validation_session_id=validation_session_id,
        item_id=pending.id,
        request=request,
        session=session,
    )
    return {"status": "progress", "processed": 1, "result": result}


@router.get(
    "/physical-check/sessions/{validation_session_id}/items/{item_id}/identity"
)
def verify_physical_validation_item_identity(
    validation_session_id: str,
    item_id: str,
    session: SessionDep,
    gtin: Annotated[str, Query(min_length=8, max_length=20)],
    contract: Literal["v1", "v2"] = "v1",
) -> dict[str, object]:
    """Verify a barcode against frozen session evidence without revealing a price."""

    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    item_row = repository.item_model(validation_session_id, item_id)
    if item_row is None:
        raise HTTPException(status_code=404, detail="validation session item not found")
    items = {item.id: item for item in repository.items(validation_session_id)}
    item = items[item_id]
    try:
        normalized_gtin = (
            normalize_gtin(gtin).normalized_gtin
            if contract == "v2"
            else PhysicalPriceObservation.validate_gtin(gtin)
        )
    except InvalidGtinError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    matches = tuple(
        candidate
        for candidate in repository.candidates_for_item(item_id)
        if candidate.gtin == normalized_gtin
    )
    if contract == "v2":
        common = {
            "gtin": normalized_gtin,
            "raw_scan_value": gtin,
            "target_product_name": item.target_product_name,
            "target_product_id": item.target_product_id,
            "scanner_status": "success",
            "digital_price_hidden": True,
        }
        if item.target_sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }:
            return {
                **common,
                "status": PhysicalProductIdentityStatus.WEIGHT_ITEM_NO_GTIN_REQUIRED,
                "lookup_status": "not_required",
                "identification_evidence": (
                    PhysicalIdentificationEvidence.WEIGHT_SOURCE_PRODUCT
                ),
            }
        if item.target_gtin is not None:
            status = (
                PhysicalProductIdentityStatus.GTIN_MATCH
                if item.target_gtin == normalized_gtin
                else PhysicalProductIdentityStatus.GTIN_MISMATCH
            )
            return {
                **common,
                "status": status,
                "lookup_status": "match" if status is PhysicalProductIdentityStatus.GTIN_MATCH else "mismatch",
                "expected_gtin": item.target_gtin,
                "identification_evidence": (
                    PhysicalIdentificationEvidence.GTIN_VERIFIED
                    if status is PhysicalProductIdentityStatus.GTIN_MATCH
                    else PhysicalIdentificationEvidence.UNVERIFIED
                ),
            }
        scope_key = item.target_store_external_id
        registry_matches = ProductIdentifierEvidenceRepository(session).resolve_gtin(
            chain=Chain(validation_session.chain),
            gtin=normalized_gtin,
            scope_key=scope_key,
            source_provider=item.target_source_provider,
        )
        mapped_products = {row.external_product_id for row in registry_matches}
        if len(mapped_products) > 1:
            return {
                **common,
                "status": "ambiguous_gtin",
                "lookup_status": "ambiguous",
                "matching_external_product_ids": sorted(mapped_products),
                "identification_evidence": PhysicalIdentificationEvidence.UNVERIFIED,
            }
        if mapped_products:
            mapped_product = next(iter(mapped_products))
            status = (
                PhysicalProductIdentityStatus.GTIN_MATCH
                if mapped_product == item.target_external_product_id
                else PhysicalProductIdentityStatus.GTIN_MISMATCH
            )
            return {
                **common,
                "status": status,
                "lookup_status": "match" if status is PhysicalProductIdentityStatus.GTIN_MATCH else "mismatch",
                "identification_evidence": (
                    PhysicalIdentificationEvidence.GTIN_VERIFIED
                    if status is PhysicalProductIdentityStatus.GTIN_MATCH
                    else PhysicalIdentificationEvidence.UNVERIFIED
                ),
            }
        return {
            **common,
            "status": PhysicalProductIdentityStatus.GTIN_NOT_KNOWN_BY_SOURCE,
            "lookup_status": "unknown_to_source",
            "identification_evidence": PhysicalIdentificationEvidence.UNVERIFIED,
            "can_enrich": bool(
                item.target_source_provider == "own"
                and item.target_external_product_id
                and item.target_store_external_id
            ),
            "manual_exact_allowed": True,
        }
    if not matches:
        return {
            "status": "no_match",
            "match_method": None,
            "gtin": normalized_gtin,
            "target_product_name": item_row.target_product_name,
            "digital_price_hidden": True,
        }
    distinct_products: dict[tuple[str, str], list[DigitalPriceCandidate]] = {}
    for candidate in matches:
        identity = (
            " ".join(candidate.product_name.casefold().split()),
            " ".join((candidate.package_description or "").casefold().split()),
        )
        distinct_products.setdefault(identity, []).append(candidate)
    if len(distinct_products) > 1:
        return {
            "status": "multiple_matches",
            "match_method": "exact_gtin",
            "gtin": normalized_gtin,
            "products": [
                {
                    "product_name": rows[0].product_name,
                    "brand": rows[0].brand,
                    "package": rows[0].package_description,
                    "product_ids": sorted({row.product_id for row in rows}),
                    "matching_evidence_rows": len(rows),
                }
                for _, rows in sorted(distinct_products.items())
            ],
            "digital_price_hidden": True,
        }
    [product_matches] = distinct_products.values()
    product = product_matches[0]
    return {
        "status": "match",
        "match_method": "exact_gtin",
        "gtin": normalized_gtin,
        "product_name": product.product_name,
        "brand": product.brand,
        "package": product.package_description,
        "matching_evidence_rows": len(matches),
        "digital_price_hidden": True,
    }


@router.post("/physical-check/shelf-identifiers", status_code=201)
def record_shelf_identifier_evidence(
    payload: ShelfIdentifierEvidenceCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Record an uninterpreted shelf-code diagnostic without creating a price sample."""

    store = PhysicalStoreRepository(session).get(payload.physical_store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    selected_source_product_id: str | None = None
    if payload.validation_session_id is not None:
        validation_repository = PhysicalValidationSessionRepository(session)
        validation_session = validation_repository.get(payload.validation_session_id)
        if validation_session is None:
            raise HTTPException(status_code=404, detail="validation session not found")
        if validation_session.physical_store_id != payload.physical_store_id:
            raise HTTPException(
                status_code=422,
                detail="validation session belongs to another physical store",
            )
        item = validation_repository.item_identifier_model(
            payload.validation_session_id,
            payload.validation_session_item_id or "",
        )
        if item is None:
            raise HTTPException(status_code=404, detail="validation session item not found")
        selected_source_product_id = item.target_product_id
    evidence = ShelfIdentifierEvidence(
        id=uuid4().hex,
        chain=store.chain,
        physical_store_id=store.id,
        validation_session_id=payload.validation_session_id,
        validation_session_item_id=payload.validation_session_item_id,
        selected_source_product_id=selected_source_product_id,
        raw_value=payload.raw_value,
        barcode_format=payload.barcode_format,
        observed_at=payload.observed_at,
        verified=False,
    )
    try:
        row = ShelfIdentifierEvidenceRepository(session).add(evidence)
        session.commit()
    except (LookupError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "id": row.id,
        "status": PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN,
        "identification_evidence": PhysicalIdentificationEvidence.UNVERIFIED,
        "raw_value": row.raw_value,
        "barcode_format": row.barcode_format,
        "length": len(row.raw_value),
        "verified": False,
        "authoritative_product_identity": False,
        "treated_as_gtin": False,
        "physical_observation_created": False,
    }


@router.post("/physical-check/scanner-diagnostics", status_code=201)
def record_barcode_scan_diagnostic(
    payload: BarcodeScanDiagnosticCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Persist privacy-minimal scanner reliability data.

    The request schema intentionally rejects raw/normalized barcode values,
    camera labels, browser strings, store/session IDs and arbitrary error
    messages.  Camera media is never accepted by this endpoint.
    """

    row = BarcodeScanDiagnosticModel(
        scanner_provider=payload.scanner_provider,
        barcode_format=payload.barcode_format,
        outcome=payload.outcome,
        duration_ms=payload.duration_ms,
        failure_reason=payload.failure_reason,
    )
    session.add(row)
    session.commit()
    return {
        "accepted": True,
        "scanner_provider": row.scanner_provider,
        "outcome": row.outcome,
        "barcode_format": row.barcode_format,
        "duration_ms": row.duration_ms,
        "failure_reason": row.failure_reason,
        "barcode_value_recorded": False,
        "camera_media_recorded": False,
        "identifying_data_recorded": False,
    }


@router.get("/physical-check/scanner-diagnostics/metrics")
def barcode_scan_diagnostic_metrics(
    session: SessionDep,
    contract: Literal["v1", "v2"] = "v1",
) -> dict[str, object]:
    """Return aggregate scanner health without exposing event-level data."""

    rows = tuple(session.scalars(select(BarcodeScanDiagnosticModel)))
    scan_rows = tuple(row for row in rows if row.scanner_provider != "manual")
    successful = tuple(
        row for row in scan_rows if row.outcome in {"success", "no_match"}
    )
    durations = sorted(
        row.duration_ms
        for row in successful
        if row.duration_ms is not None
    )
    by_provider: dict[str, dict[str, int]] = {}
    for row in rows:
        counts = by_provider.setdefault(
            row.scanner_provider,
            {"events": 0, "successful_scans": 0, "failed_scans": 0, "no_matches": 0},
        )
        counts["events"] += 1
        if row.outcome in {"success", "no_match"}:
            counts["successful_scans"] += 1
        if row.outcome == "failure":
            counts["failed_scans"] += 1
        if row.outcome == "no_match":
            counts["no_matches"] += 1
    observation_rows = tuple(
        session.execute(
            select(
                PhysicalPriceObservationModel.identity_status,
                PhysicalPriceObservationModel.gtin,
            )
        ).all()
    )
    identity_counts: dict[str, int] = {}
    for identity_status, _ in observation_rows:
        key = identity_status or "legacy"
        identity_counts[key] = identity_counts.get(key, 0) + 1
    gtin_statuses = {
        PhysicalProductIdentityStatus.GTIN_MATCH.value,
        PhysicalProductIdentityStatus.GTIN_MISMATCH.value,
        PhysicalProductIdentityStatus.GTIN_NOT_KNOWN_BY_SOURCE.value,
    }
    gtin_observations = [
        (identity_status, gtin)
        for identity_status, gtin in observation_rows
        if identity_status in gtin_statuses
    ]
    valid_gtin_observations = 0
    for _, gtin in gtin_observations:
        try:
            if gtin is not None:
                normalize_gtin(gtin)
                valid_gtin_observations += 1
        except InvalidGtinError:
            continue
    source_match_count = identity_counts.get(
        PhysicalProductIdentityStatus.GTIN_MATCH.value,
        0,
    )
    source_lookup_count = len(gtin_observations)
    response: dict[str, object] = {
        "scan_attempts": len(scan_rows),
        "successful_scans": len(successful),
        "failed_scans": sum(row.outcome == "failure" for row in scan_rows),
        "manual_fallbacks": sum(row.outcome == "manual_fallback" for row in rows),
        "no_matches": sum(row.outcome == "no_match" for row in rows),
        "median_scan_time_ms": median(durations) if durations else None,
        "events": len(rows),
        "by_provider": by_provider,
        "barcode_values_recorded": False,
        "camera_media_recorded": False,
        "identifying_data_recorded": False,
    }
    if contract == "v2":
        response.update(
            {
                "scan_success_rate": (
                    round(len(successful) / len(scan_rows), 4) if scan_rows else None
                ),
                "valid_gtin_rate": (
                    round(valid_gtin_observations / len(gtin_observations), 4)
                    if gtin_observations
                    else None
                ),
                "source_identifier_match_rate": (
                    round(source_match_count / source_lookup_count, 4)
                    if source_lookup_count
                    else None
                ),
                "source_identifier_matches": source_match_count,
                "source_identifier_unknown": identity_counts.get(
                    PhysicalProductIdentityStatus.GTIN_NOT_KNOWN_BY_SOURCE.value,
                    0,
                ),
                "manual_exact_matches": identity_counts.get(
                    PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH.value,
                    0,
                ),
                "weight_no_barcode": identity_counts.get(
                    PhysicalProductIdentityStatus.WEIGHT_ITEM_NO_GTIN_REQUIRED.value,
                    0,
                ),
                "true_no_matches": identity_counts.get(
                    PhysicalProductIdentityStatus.NO_MATCH.value,
                    0,
                ),
                "identity_status_breakdown": dict(sorted(identity_counts.items())),
            }
        )
    return response


@router.post(
    "/physical-check/sessions/{validation_session_id}/items/{item_id}/observation",
    status_code=201,
)
def capture_physical_validation_item(
    validation_session_id: str,
    item_id: str,
    payload: PhysicalValidationCaptureCreate,
    session: SessionDep,
) -> dict[str, object]:
    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    if validation_session.status is not PhysicalValidationSessionStatus.ACTIVE:
        raise HTTPException(status_code=409, detail="validation session is not active")
    item_row = repository.item_model(validation_session_id, item_id)
    if item_row is None:
        raise HTTPException(status_code=404, detail="validation session item not found")
    existing_observation_id = session.scalar(
        select(PhysicalPriceObservationModel.id).where(
            PhysicalPriceObservationModel.validation_session_item_id == item_id
        )
    )
    candidates = repository.candidates_for_item(item_id)
    items = {item.id: item for item in repository.items(validation_session_id)}
    item = items[item_id]
    if existing_observation_id is not None:
        expected_id = _capture_observation_id(
            validation_session_id,
            item_id,
            payload.client_request_id,
        )
        if payload.client_request_id is None or existing_observation_id != expected_id:
            raise HTTPException(
                status_code=409,
                detail="validation session item is already captured",
            )
        existing_row = session.get(PhysicalPriceObservationModel, existing_observation_id)
        assert existing_row is not None
        existing_observation = physical_observation_from_row(existing_row)
        current = repository.get(validation_session_id)
        assert current is not None
        item_payload = next(
            item
            for item in _session_payload(
                session,
                current,
                repository.items(validation_session_id),
            )["items"]
            if isinstance(item, dict) and item["id"] == item_id
        )
        existing_comparisons = _frozen_session_comparisons(
            existing_observation,
            candidates,
            database_session=session,
            item=item,
        )
        existing_semantic = _target_semantic_diagnostic(
            session,
            existing_observation,
            candidates,
            item=item,
        )
        return {
            "observation": existing_observation.model_dump(mode="json"),
            "comparisons": [
                comparison.model_dump(mode="json")
                for comparison in existing_comparisons
            ],
            "comparison_output": _compound_comparison_output(
                existing_observation,
                existing_comparisons,
                semantic_diagnostic=existing_semantic,
            ),
            "item": item_payload,
            "blind_price_revealed_after_commit": validation_session.blind_capture,
            "catalog_price_updated": False,
            "sampled_only": True,
            "idempotent_replay": True,
        }

    product_name = (payload.product_name or item_row.target_product_name).strip()
    normalized_name = " ".join(product_name.casefold().split())
    expected_name = " ".join(item.target_product_name.casefold().split())
    normalized_gtin = payload.gtin
    legacy_no_match = (
        payload.identity_status is PhysicalProductIdentityStatus.NO_MATCH
        and payload.identification_evidence is None
    )
    if (
        payload.identity_status is not PhysicalProductIdentityStatus.EXACT
        and not legacy_no_match
        and payload.gtin
    ):
        try:
            normalized_gtin = normalize_gtin(payload.gtin).normalized_gtin
        except InvalidGtinError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    exact_manual_target = normalized_name == expected_name
    target_is_weight = item.target_sale_model in {
        SaleModel.SOLD_BY_WEIGHT,
        SaleModel.VARIABLE_WEIGHT_PACKAGE,
    }
    if (payload.price_semantics is PhysicalPriceSemantics.WEIGHT) != target_is_weight:
        raise HTTPException(
            status_code=422,
            detail="SEK/kg price semantics must match a verified weight product",
        )
    if payload.identity_status is PhysicalProductIdentityStatus.GTIN_MATCH:
        if item.target_gtin is None or normalized_gtin != item.target_gtin:
            raise HTTPException(
                status_code=422,
                detail="GTIN match requires the exact verified target GTIN",
            )
    elif payload.identity_status is PhysicalProductIdentityStatus.GTIN_MISMATCH:
        if item.target_gtin is None or normalized_gtin is None:
            raise HTTPException(
                status_code=422,
                detail="GTIN mismatch requires both a scanned and verified target GTIN",
            )
        if normalized_gtin == item.target_gtin:
            raise HTTPException(status_code=422, detail="the scanned GTIN matches the target")
    elif (
        payload.identity_status
        is PhysicalProductIdentityStatus.GTIN_NOT_KNOWN_BY_SOURCE
    ):
        if item.target_gtin is not None or normalized_gtin is None:
            raise HTTPException(
                status_code=422,
                detail="unknown-source GTIN requires a valid scan and no verified source GTIN",
            )
        if item.identifier_status is SessionItemIdentifierStatus.AMBIGUOUS_GTIN:
            raise HTTPException(
                status_code=422,
                detail="ambiguous source GTIN requires explicit resolution",
            )
        if not exact_manual_target:
            raise HTTPException(
                status_code=422,
                detail="unknown-source GTIN requires manual confirmation of the exact target",
            )
    elif payload.identity_status is PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH:
        if not exact_manual_target:
            raise HTTPException(
                status_code=422,
                detail="manual exact identity must match the immutable session target",
            )
    elif (
        payload.identity_status
        is PhysicalProductIdentityStatus.WEIGHT_ITEM_NO_GTIN_REQUIRED
    ):
        if not target_is_weight or not exact_manual_target:
            raise HTTPException(
                status_code=422,
                detail="weight identity requires the exact selected weight product",
            )
        if payload.price_semantics is not PhysicalPriceSemantics.WEIGHT:
            raise HTTPException(
                status_code=422,
                detail="weight identity requires SEK/kg price semantics",
            )
        normalized_gtin = None
    elif payload.identity_status is PhysicalProductIdentityStatus.SHELF_CODE_MATCH:
        raise HTTPException(
            status_code=422,
            detail="shelf codes are diagnostic until a verified mapping exists",
        )
    elif payload.identity_status is PhysicalProductIdentityStatus.SHELF_CODE_UNKNOWN:
        normalized_gtin = None

    evidence = (
        None
        if legacy_no_match
        else payload.identification_evidence
        or _default_identification_evidence(
            payload.identity_status,
            gtin=normalized_gtin,
        )
    )
    promotion_type, derived_member_only = _promotion_fields(
        payload.price_semantics,
        weight_price_type=payload.weight_price_type,
    )
    member_only = (
        payload.member_only
        if payload.member_only is not None
        else derived_member_only
    )
    try:
        provisional = PhysicalPriceObservation(
            id=_capture_observation_id(
                validation_session_id,
                item_id,
                payload.client_request_id,
            ),
            physical_store_id=validation_session.physical_store_id,
            gtin=normalized_gtin,
            product_name=product_name,
            shelf_price=payload.shelf_price,
            comparison_price=payload.comparison_price,
            comparison_unit=payload.comparison_unit,
            promotion_type=promotion_type,
            member_only=member_only,
            multibuy_quantity=payload.multibuy_quantity,
            multibuy_total_price=payload.multibuy_total_price,
            promotion_text=payload.promotion_text,
            observed_at=payload.observed_at,
            confidence=Confidence.UNKNOWN,
            notes=payload.notes,
            validation_session_id=validation_session_id,
            validation_session_item_id=item_id,
            price_semantics=payload.price_semantics,
            identity_status=payload.identity_status,
            identification_evidence=evidence,
            regular_shelf_price=payload.regular_shelf_price,
            weight_price_type=payload.weight_price_type,
            immutable_candidate_set_sha256=item_row.candidate_set_sha256,
        )
    except ValidationError as exc:
        detail = "; ".join(error["msg"] for error in exc.errors(include_url=False))
        raise HTTPException(status_code=422, detail=detail) from exc

    if payload.identity_status is PhysicalProductIdentityStatus.EXACT:
        if provisional.gtin is not None:
            exact_identity = any(
                candidate.gtin == provisional.gtin for candidate in candidates
            )
        else:
            exact_identity = (
                product_name.casefold().strip()
                == item_row.target_product_name.casefold().strip()
            )
        if not exact_identity:
            raise HTTPException(
                status_code=422,
                detail="exact identity must match the immutable session target",
            )

    comparisons = _frozen_session_comparisons(
        provisional,
        candidates,
        database_session=session,
        item=item,
    )
    semantic_diagnostic = _target_semantic_diagnostic(
        session,
        provisional,
        candidates,
        item=item,
    )
    observation = provisional.model_copy(
        update={
            "confidence": derived_observation_confidence(
                comparisons,
                gtin=provisional.gtin,
                identity_status=provisional.identity_status,
                identification_evidence=provisional.identification_evidence,
            )
        }
    )
    try:
        PhysicalPriceObservationRepository(session).add(observation)
        session.commit()
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    current = repository.get(validation_session_id)
    assert current is not None
    item_payload = next(
        item
        for item in _session_payload(
            session,
            current,
            repository.items(validation_session_id),
        )["items"]
        if isinstance(item, dict) and item["id"] == item_id
    )
    return {
        "observation": observation.model_dump(mode="json"),
        "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
        "comparison_output": _compound_comparison_output(
            observation,
            comparisons,
            semantic_diagnostic=semantic_diagnostic,
        ),
        "item": item_payload,
        "blind_price_revealed_after_commit": validation_session.blind_capture,
        "catalog_price_updated": False,
        "sampled_only": True,
        "idempotent_replay": False,
    }


@router.post(
    "/physical-check/sessions/{validation_session_id}/items/{item_id}/amendments",
    status_code=201,
)
def append_physical_validation_amendment(
    validation_session_id: str,
    item_id: str,
    payload: PhysicalObservationAmendmentCreate,
    session: SessionDep,
) -> dict[str, object]:
    """Append explicit late/corrected evidence without rewriting the raw visit."""

    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    if validation_session.status is not PhysicalValidationSessionStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail="physical evidence amendments require a completed session",
        )
    items = {item.id: item for item in repository.items(validation_session_id)}
    item = items.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="validation session item not found")

    observation_id = _amendment_id(
        validation_session_id,
        item_id,
        payload.client_request_id,
    )
    if payload.kind == "correction":
        if payload.base_observation_id is not None:
            observation_id = payload.base_observation_id
        elif payload.supersedes_amendment_id is not None:
            previous = PhysicalObservationAmendmentRepository(session).get(
                payload.supersedes_amendment_id
            )
            if previous is None:
                raise HTTPException(
                    status_code=404,
                    detail="superseded physical evidence amendment not found",
                )
            if (
                previous.validation_session_id != validation_session_id
                or previous.validation_session_item_id != item_id
            ):
                raise HTTPException(
                    status_code=409,
                    detail="superseded physical evidence belongs to another item",
                )
            observation_id = previous.payload.id
    observation, comparisons, semantic_diagnostic = _build_amended_observation(
        session,
        validation_session,
        item,
        payload.observation,
        observation_id=observation_id,
    )
    try:
        amendment = PhysicalObservationAmendment(
            id=_amendment_id(
                validation_session_id,
                item_id,
                payload.client_request_id,
            ),
            validation_session_id=validation_session_id,
            validation_session_item_id=item_id,
            kind=PhysicalObservationAmendmentKind(payload.kind),
            payload=observation,
            payload_sha256=physical_observation_payload_sha256(observation),
            base_observation_id=payload.base_observation_id,
            supersedes_amendment_id=payload.supersedes_amendment_id,
            observed_at=observation.observed_at,
            observed_at_precision=PhysicalObservationTimePrecision(
                payload.observed_at_precision
            ),
            reason=payload.reason,
            source=payload.evidence_source,
            reference=payload.evidence_reference,
            client_request_id=payload.client_request_id,
        )
    except ValidationError as exc:
        detail = "; ".join(error["msg"] for error in exc.errors(include_url=False))
        raise HTTPException(status_code=422, detail=detail) from exc

    settings = GroceryDataSettings.from_env()
    service = PhysicalObservationAmendmentService(
        session,
        official_freshness_hours=Decimal(
            str(settings.field_validation_max_price_age_hours)
        ),
        minimum_comparable_sample=settings.min_sample_for_accuracy_score,
    )
    try:
        result = service.append(amendment)
        v3_amended = service.v3.amended_report(
            validation_session_id,
            observations=result.effective_observations,
            evidence_sha256=result.effective_evidence_sha256,
        ).metadata()
        v3_official = service.v3.preview_official(validation_session_id).metadata()
        session.commit()
    except PhysicalObservationAmendmentHeadConflict as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (RuntimeError, ValueError) as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    raw_row = session.scalar(
        select(PhysicalPriceObservationModel).where(
            PhysicalPriceObservationModel.validation_session_id
            == validation_session_id,
            PhysicalPriceObservationModel.validation_session_item_id == item_id,
        )
    )
    return {
        "amendment": result.amendment.model_dump(mode="json"),
        "raw_observation": (
            physical_observation_from_row(raw_row).model_dump(mode="json")
            if raw_row is not None
            else None
        ),
        "effective_observation": observation.model_dump(mode="json"),
        "comparisons": [row.model_dump(mode="json") for row in comparisons],
        "comparison_output": _compound_comparison_output(
            observation,
            comparisons,
            semantic_diagnostic=semantic_diagnostic,
        ),
        "v3_official": v3_official,
        "v3_amended": v3_amended,
        "accuracy_display": (
            "scored" if v3_official["score_eligible"] else "insufficient_sample"
        ),
        "amended_accuracy_display": (
            "scored" if v3_amended["score_eligible"] else "insufficient_sample"
        ),
        "raw_observation_preserved": True,
        "official_replaced_by_amendment": False,
        "idempotent_replay": result.idempotent_replay,
    }


@router.post("/physical-check/sessions/{validation_session_id}/complete")
def complete_physical_validation_session(
    validation_session_id: str,
    payload: PhysicalValidationSessionComplete,
    session: SessionDep,
) -> dict[str, object]:
    repository = PhysicalValidationSessionRepository(session)
    try:
        validation_session = repository.complete(
            validation_session_id,
            completed_at=payload.completed_at,
        )
        session.commit()
    except LookupError as exc:
        session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    observations, comparisons, report, comparison_bundle = _validation_session_report(
        session,
        validation_session,
    )
    v3_official = _completed_v3_official_metadata(session, validation_session)
    amended = _completed_v3_amended_metadata(session, validation_session)
    return {
        **_session_payload(
            session,
            validation_session,
            repository.items(validation_session_id),
        ),
        "report": report,
        "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
        "comparison_provenance": comparison_bundle.metadata(),
        "post_visit_diagnostic_comparisons": [
            comparison.model_dump(mode="json")
            for comparison in comparison_bundle.diagnostic_comparisons
        ],
        "original_comparisons": (
            [
                comparison.model_dump(mode="json")
                for comparison in comparison_bundle.original_comparisons
            ]
            if comparison_bundle.comparison_basis
            != "frozen_session_evidence"
            else []
        ),
        "captured_observations": len(observations),
        "v3_official": v3_official,
        **(
            {
                "v3_amended": amended[0],
                "physical_evidence_amendments": [
                    row.model_dump(mode="json") for row in amended[1]
                ],
                "amended_accuracy_display": (
                    "scored"
                    if amended[0]["score_eligible"]
                    else "insufficient_sample"
                ),
            }
            if amended is not None
            else {}
        ),
        "accuracy_display": (
            "scored" if v3_official["score_eligible"] else "insufficient_sample"
        ),
    }


@router.get("/physical-check/sessions/{validation_session_id}/report")
def physical_validation_session_report(
    validation_session_id: str,
    session: SessionDep,
) -> dict[str, object]:
    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    observations, comparisons, report, comparison_bundle = _validation_session_report(
        session,
        validation_session,
    )
    v3_official = (
        _completed_v3_official_metadata(session, validation_session)
        if validation_session.status is PhysicalValidationSessionStatus.COMPLETED
        else None
    )
    amended = (
        _completed_v3_amended_metadata(session, validation_session)
        if validation_session.status is PhysicalValidationSessionStatus.COMPLETED
        else None
    )
    return {
        "session_id": validation_session_id,
        "observation_count": len(observations),
        "report": report,
        "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
        "comparison_provenance": comparison_bundle.metadata(),
        "post_visit_diagnostic_comparisons": [
            comparison.model_dump(mode="json")
            for comparison in comparison_bundle.diagnostic_comparisons
        ],
        "original_comparisons": (
            [
                comparison.model_dump(mode="json")
                for comparison in comparison_bundle.original_comparisons
            ]
            if comparison_bundle.comparison_basis
            != "frozen_session_evidence"
            else []
        ),
        "sampled_only": True,
        **({"v3_official": v3_official} if v3_official is not None else {}),
        **(
            {
                "v3_amended": amended[0],
                "physical_evidence_amendments": [
                    row.model_dump(mode="json") for row in amended[1]
                ],
                "amended_accuracy_display": (
                    "scored"
                    if amended[0]["score_eligible"]
                    else "insufficient_sample"
                ),
            }
            if amended is not None
            else {}
        ),
        "accuracy_display": (
            "scored"
            if (
                v3_official["score_eligible"]
                if v3_official is not None
                else report["score_eligible"]
            )
            else "insufficient_sample"
        ),
    }


@router.get("/physical-check/sessions/{validation_session_id}/export")
def export_physical_validation_session(
    validation_session_id: str,
    session: SessionDep,
    export_format: Annotated[Literal["json", "csv"], Query(alias="format")] = "json",
) -> Response:
    repository = PhysicalValidationSessionRepository(session)
    validation_session = repository.get(validation_session_id)
    if validation_session is None:
        raise HTTPException(status_code=404, detail="validation session not found")
    observations, comparisons, report, comparison_bundle = _validation_session_report(
        session,
        validation_session,
    )
    v3_official = (
        _completed_v3_official_metadata(session, validation_session)
        if validation_session.status is PhysicalValidationSessionStatus.COMPLETED
        else None
    )
    amended = (
        _completed_v3_amended_metadata(session, validation_session)
        if validation_session.status is PhysicalValidationSessionStatus.COMPLETED
        else None
    )
    item_by_id = {item.id: item for item in repository.items(validation_session_id)}
    comparison_by_observation: dict[str, list[PhysicalPriceComparison]] = {}
    for comparison in comparisons:
        comparison_by_observation.setdefault(comparison.observation_id, []).append(comparison)
    rows: list[dict[str, object]] = []
    for observation in observations:
        item = item_by_id.get(observation.validation_session_item_id or "")
        observation_comparisons = comparison_by_observation.get(observation.id) or [None]
        for comparison in observation_comparisons:
            rows.append(
                {
                    "timestamp": observation.observed_at,
                    "store": validation_session.store_name,
                    "physical_store_id": validation_session.physical_store_id,
                    "gtin": observation.gtin,
                    "product_name": observation.product_name,
                    "package": item.target_package_description if item else None,
                    "provider": comparison.source_provider if comparison else None,
                    "context_id": comparison.grocery_context_id if comparison else None,
                    "snapshot_id": comparison.source_snapshot_id if comparison else None,
                    "comparison_basis": comparison_bundle.comparison_basis,
                    "original_snapshot_ids": ";".join(
                        comparison_bundle.original_snapshot_ids
                    ),
                    "digital_observed_at": (
                        comparison.digital_observed_at if comparison else None
                    ),
                    "digital_price": comparison.digital_price if comparison else None,
                    "shelf_price": observation.shelf_price,
                    "regular_shelf_price": observation.regular_shelf_price,
                    "weight_price_type": (
                        observation.weight_price_type.value
                        if observation.weight_price_type
                        else None
                    ),
                    "difference": comparison.signed_difference if comparison else None,
                    "price_type": (
                        observation.price_semantics.value
                        if observation.price_semantics
                        else "unknown"
                    ),
                    "promotion_text": observation.promotion_text,
                    "identity_status": (
                        observation.identity_status.value
                        if observation.identity_status
                        else None
                    ),
                    "identification_evidence": (
                        observation.identification_evidence.value
                        if observation.identification_evidence
                        else None
                    ),
                    "match_result": comparison.status.value if comparison else "no_digital_match",
                }
            )
    filename = f"physical-validation-{validation_session_id}"
    if export_format == "json":
        return JSONResponse(
            content=jsonable_encoder(
                {
                    "session": validation_session.model_dump(mode="json"),
                    "rows": rows,
                    "report": report,
                    "comparison_provenance": comparison_bundle.metadata(),
                    "sampled_only": True,
                    **(
                        {
                            "v3_official": v3_official,
                            "accuracy_display": (
                                "scored"
                                if v3_official["score_eligible"]
                                else "insufficient_sample"
                            ),
                        }
                        if v3_official is not None
                        else {}
                    ),
                    **(
                        {
                            "v3_amended": amended[0],
                            "physical_evidence_amendments": [
                                row.model_dump(mode="json")
                                for row in amended[1]
                            ],
                            "amended_accuracy_display": (
                                "scored"
                                if amended[0]["score_eligible"]
                                else "insufficient_sample"
                            ),
                        }
                        if amended is not None
                        else {}
                    ),
                }
            ),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}.json"'
            },
        )
    output = io.StringIO(newline="")
    fieldnames = list(rows[0]) if rows else [
        "timestamp",
        "store",
        "physical_store_id",
        "gtin",
        "product_name",
        "package",
        "provider",
        "context_id",
        "snapshot_id",
        "comparison_basis",
        "original_snapshot_ids",
        "digital_observed_at",
        "digital_price",
        "shelf_price",
        "regular_shelf_price",
        "weight_price_type",
        "difference",
        "price_type",
        "promotion_text",
        "identity_status",
        "identification_evidence",
        "match_result",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        {
            key: _csv_safe_cell(value)
            for key, value in row.items()
        }
        for row in jsonable_encoder(rows)
    )
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@router.get("/physical-check/digital-price-preview")
def digital_price_preview(
    store_id: Annotated[str, Query(min_length=1, max_length=64)],
    request: Request,
    session: SessionDep,
    gtin: Annotated[str | None, Query(min_length=8, max_length=20)] = None,
    product_name: Annotated[str | None, Query(min_length=2, max_length=1000)] = None,
) -> dict[str, object]:
    """Preview current persisted digital prices without biasing shelf entry.

    The endpoint never writes an observation and never creates a provider
    client. Both OWN and external rows come from locally persisted snapshots.
    """

    store = PhysicalStoreRepository(session).get(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    if not store.is_active:
        raise HTTPException(status_code=409, detail="physical store is not currently active")
    if not (gtin or "").strip() and not (product_name or "").strip():
        raise HTTPException(status_code=422, detail="gtin or product_name is required")
    try:
        direct_lookup = PhysicalPriceObservation(
            id="digital-preview",
            physical_store_id=store_id,
            gtin=gtin,
            product_name=None if gtin else product_name,
            shelf_price=Decimal("0.01"),
            observed_at=datetime.now(tz=UTC),
            confidence=Confidence.UNKNOWN,
        )
    except ValidationError as exc:
        detail = "; ".join(error["msg"] for error in exc.errors(include_url=False))
        raise HTTPException(status_code=422, detail=detail) from exc
    own_reader = PersistedPhysicalPriceCandidateReader(session)
    external_reader = _external_reader(request, session)
    staged: list[tuple[str, DigitalPriceCandidate]] = []
    direct_own = own_reader.current_for_observation(direct_lookup)
    staged.extend(("own_gtin" if gtin else "own_exact_name", row) for row in direct_own)

    current_external = getattr(external_reader, "current_for_observation", None)
    direct_external = (
        tuple(current_external(direct_lookup))
        if callable(current_external)
        else tuple(external_reader.for_observation(direct_lookup))
    )
    staged.extend(("external_gtin" if gtin else "external_exact_name", row) for row in direct_external)

    if gtin and not direct_own:
        staged.extend(
            ("persisted_detail_identity", row)
            for row in own_reader.current_for_known_detail_identity(direct_lookup)
        )
    if product_name:
        try:
            name_lookup = PhysicalPriceObservation(
                id="digital-preview-name",
                physical_store_id=store_id,
                product_name=product_name,
                shelf_price=Decimal("0.01"),
                observed_at=datetime.now(tz=UTC),
                confidence=Confidence.UNKNOWN,
            )
        except ValidationError as exc:
            detail = "; ".join(error["msg"] for error in exc.errors(include_url=False))
            raise HTTPException(status_code=422, detail=detail) from exc
        staged.extend(
            ("manual_exact_name", row)
            for row in own_reader.current_for_observation(name_lookup)
        )
        external_name = (
            tuple(current_external(name_lookup))
            if callable(current_external)
            else tuple(external_reader.for_observation(name_lookup))
        )
        staged.extend(("manual_exact_name", row) for row in external_name)

    path_priority = {
        "own_gtin": 0,
        "external_gtin": 1,
        "persisted_detail_identity": 2,
        "own_exact_name": 3,
        "external_exact_name": 4,
        "manual_exact_name": 5,
    }
    newest: dict[tuple[str, str, str], tuple[str, DigitalPriceCandidate]] = {}
    for path, candidate in staged:
        key = (
            candidate.source_provider,
            candidate.grocery_context_id,
            candidate.product_id,
        )
        previous = newest.get(key)
        if previous is None or path_priority[path] < path_priority[previous[0]]:
            newest[key] = (path, candidate)
    candidates = sorted(
        newest.values(),
        key=lambda item: (
            path_priority[item[0]],
            item[1].source_provider,
            item[1].product_name,
            item[1].product_id,
        ),
    )
    presentation = _digital_price_presentation(
        session,
        physical_store_id=store_id,
        chain=store.chain,
        candidates=candidates,
    )
    return {
        "physical_store_id": store_id,
        "gtin": direct_lookup.gtin,
        "product_name": product_name,
        "lookup_order": [
            "own_gtin",
            "external_gtin",
            "persisted_detail_identity",
            "manual_exact_name",
        ],
        "items": [
            {
                "match_path": match_path,
                "source_provider": candidate.source_provider,
                "grocery_context_id": candidate.grocery_context_id,
                "price_context_type": presentation[
                    (candidate.source_provider, candidate.grocery_context_id)
                ][0],
                "price_semantics": presentation[
                    (candidate.source_provider, candidate.grocery_context_id)
                ][1],
                "price_label": presentation[
                    (candidate.source_provider, candidate.grocery_context_id)
                ][2],
                "source_snapshot_id": candidate.source_snapshot_id,
                "observed_at": candidate.observed_at,
                "product_id": candidate.product_id,
                "product_name": candidate.product_name,
                "current_price": candidate.current_price,
                "regular_price": candidate.regular_price,
                "member_price": candidate.member_price,
                "promotion_type": candidate.promotion_type,
                "member_only": candidate.member_only,
            }
            for match_path, candidate in candidates
        ],
        "count": len(candidates),
        "preview_only": True,
        "shelf_price_prefilled": False,
        "live_provider_requests": 0,
    }


@router.post("/physical-check/observations", status_code=201)
def record_physical_observation(
    payload: PhysicalPriceObservationCreate,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    store = PhysicalStoreRepository(session).get(payload.physical_store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    if not store.is_active:
        raise HTTPException(status_code=409, detail="physical store is not currently active")

    try:
        provisional = PhysicalPriceObservation(
            id=uuid4().hex,
            **payload.model_dump(),
            confidence=Confidence.UNKNOWN,
        )
    except ValidationError as exc:
        # Reuse the stricter domain invariants (GTIN, paired comparison/
        # multibuy fields and timezone awareness) without turning ordinary
        # malformed mobile input into an internal-server error.
        detail = "; ".join(error["msg"] for error in exc.errors(include_url=False))
        raise HTTPException(status_code=422, detail=detail) from exc
    candidates = combined_candidates_for_observation(
        provisional,
        persisted_reader=PersistedPhysicalPriceCandidateReader(session),
        external_reader=_external_reader(request, session),
    )
    validator = PhysicalPriceValidationService()
    comparisons = validator.compare_observation(
        provisional,
        candidates,
        expected_providers=expected_providers_for_store(session, provisional.physical_store_id),
    )
    observation = provisional.model_copy(
        update={
            "confidence": derived_observation_confidence(
                comparisons,
                gtin=provisional.gtin,
            )
        }
    )
    PhysicalPriceObservationRepository(session).add(observation)
    session.commit()
    return {
        "observation": observation.model_dump(mode="json"),
        "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
        "catalog_price_updated": False,
    }


@router.get("/physical-check/observations")
def list_physical_observations(
    store_id: str,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> dict[str, object]:
    if PhysicalStoreRepository(session).get(store_id) is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    rows = PhysicalPriceObservationRepository(session).list_for_store(
        store_id,
        limit=limit,
    )
    observations = [physical_observation_from_row(row) for row in rows]
    return {
        "items": [observation.model_dump(mode="json") for observation in observations],
        "count": len(observations),
        "sampled_only": True,
    }


@router.get("/physical-check/suggestions")
def physical_check_suggestions(
    store_id: str,
    request: Request,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict[str, object]:
    if PhysicalStoreRepository(session).get(store_id) is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    candidates = combined_candidates_for_store(
        store_id,
        persisted_reader=PersistedPhysicalPriceCandidateReader(session),
        external_reader=_external_reader(request, session),
        limit=1000,
    )
    suggestions = PhysicalVerificationSuggestionSampler().suggest_stratified(
        candidates,
        physical_store_id=store_id,
        limit=limit,
    )
    return {
        "items": [suggestion.model_dump(mode="json") for suggestion in suggestions],
        "count": len(suggestions),
        "sampling_strategy": "stratified",
        "sampled_only": True,
        "note": "Verify a few products only when convenient; this list is optional.",
    }


@router.get("/physical-check/report")
def physical_price_report(
    store_id: str,
    request: Request,
    session: SessionDep,
) -> dict[str, object]:
    store = PhysicalStoreRepository(session).get(store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="physical store not found")
    observations = [
        physical_observation_from_row(row)
        for row in PhysicalPriceObservationRepository(session).list_for_store(store_id)
    ]
    validator = PhysicalPriceValidationService()
    expected_providers = expected_providers_for_store(session, store_id)
    external_reader = _external_reader(request, session)
    session_comparisons: dict[str, dict[str, tuple[PhysicalPriceComparison, ...]]] = {}
    session_comparison_provenance: dict[str, dict[str, object]] = {}
    comparison_rows: list[PhysicalPriceComparison] = []
    for observation in observations:
        if observation.validation_session_item_id:
            session_id = observation.validation_session_id or ""
            if session_id not in session_comparisons:
                bundle = PhysicalSessionReconciliationService(session).current_report(
                    session_id
                )
                grouped: dict[str, list[PhysicalPriceComparison]] = {}
                for comparison in bundle.comparisons:
                    grouped.setdefault(comparison.observation_id, []).append(comparison)
                session_comparisons[session_id] = {
                    key: tuple(value) for key, value in grouped.items()
                }
                session_comparison_provenance[session_id] = bundle.metadata()
            comparison_rows.extend(
                session_comparisons[session_id].get(observation.id, ())
            )
            continue
        comparison_rows.extend(
            validator.compare_observation(
                observation,
                combined_candidates_for_observation(
                    observation,
                    persisted_reader=PersistedPhysicalPriceCandidateReader(session),
                    external_reader=external_reader,
                ),
                expected_providers=expected_providers,
            )
        )
    comparisons = tuple(comparison_rows)
    scope = ", ".join(part for part in (store.name, store.city) if part)
    minimum_sample = GroceryDataSettings.from_env().min_sample_for_accuracy_score
    report = build_accuracy_report(
        observations,
        comparisons,
        scope_label=scope or store.id,
        minimum_sample=minimum_sample,
    )
    return {
        "report": report.model_dump(mode="json"),
        "comparisons": [comparison.model_dump(mode="json") for comparison in comparisons],
        "session_comparison_provenance": session_comparison_provenance,
        "sampled_only": True,
        "blocks_normal_use": False,
        "accuracy_display": (
            "scored" if report.score_eligible else "insufficient_sample"
        ),
    }


__all__ = ["PhysicalPriceObservationCreate", "router"]
