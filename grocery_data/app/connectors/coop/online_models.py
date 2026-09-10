from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoopOnlineContextKind(StrEnum):
    ONLINE_FULFILLMENT = "online_fulfillment"


class CoopOnlineContextIdVerification(StrEnum):
    """Whether the actual online production-unit identity was observed."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"


class CoopOnlineCaptureSurface(StrEnum):
    RENDERED_CATEGORY = "rendered_category"
    PRODUCT_DETAIL_JSON_LD = "product_detail_json_ld"


class CoopOnlineCaptureContext(BaseModel):
    """Allowlisted browser-visible context, not browser session state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["online_fulfillment"]
    fulfillment_mode: Literal["pickup"]
    label: str = Field(min_length=1)
    external_context_id: str | None = None
    physical_store_external_id: str | None = None
    verification: Literal["visible_selected_context"]

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("selected Coop online context label is empty")
        return normalized


class CoopOnlineCaptureCard(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    href: str = Field(min_length=1)
    aria_label: str = Field(min_length=1)

    @field_validator("href")
    @classmethod
    def same_origin_product_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("Coop online card href must be a same-origin path")
        if not parsed.path.startswith("/handla/varor/"):
            raise ValueError("Coop online card href is not a product path")
        return parsed.path

    @field_validator("aria_label")
    @classmethod
    def normalize_aria_label(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Coop online card has no accessible label")
        return normalized


class CoopOnlineCapturePage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page_number: int = Field(ge=1)
    cards: tuple[CoopOnlineCaptureCard, ...] = Field(min_length=1)


class CoopOnlineCategoryCapture(BaseModel):
    """Sanitized evidence produced by an ordinary browser discovery session."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: Literal["coop-online-rendered-category-v1"]
    captured_at: datetime
    context: CoopOnlineCaptureContext
    route: str = Field(min_length=1)
    reported_total: int = Field(ge=1)
    pages: tuple[CoopOnlineCapturePage, ...] = Field(min_length=1)

    @field_validator("captured_at")
    @classmethod
    def captured_at_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Coop online capture timestamp must include a timezone")
        return value

    @field_validator("route")
    @classmethod
    def same_origin_category_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            raise ValueError("Coop online category route must be a same-origin path")
        if not parsed.path.startswith("/handla/varor/"):
            raise ValueError("Coop online capture route is not a category path")
        return parsed.path.rstrip("/")


class CoopOnlineProductDetailOfferCapture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    price: Decimal = Field(gt=0)
    price_currency: Literal["SEK"] = Field(alias="priceCurrency")
    availability: str = Field(min_length=1)


class CoopOnlineProductDetailSizeCapture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    value: Decimal = Field(gt=0)
    unit_code: str = Field(alias="unitCode", min_length=1)


class CoopOnlineProductDetailRowCapture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    gtin: str | None = None
    gtin13: str | None = None
    brand: str | None = None
    category: str | None = None
    size: CoopOnlineProductDetailSizeCapture
    offer: CoopOnlineProductDetailOfferCapture


class CoopOnlineProductDetailSampleCapture(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str = Field(min_length=1)
    product_path: str = Field(alias="productPath", min_length=1)
    challenge: bool
    products: tuple[CoopOnlineProductDetailRowCapture, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_paths_and_single_product(self) -> CoopOnlineProductDetailSampleCapture:
        for value, description in (
            (self.path, "category"),
            (self.product_path, "product"),
        ):
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                raise ValueError(f"Coop online {description} sample path must be same-origin")
            if not parsed.path.startswith("/handla/varor/"):
                raise ValueError(f"Coop online {description} sample path is invalid")
        if not self.product_path.startswith(f"{self.path.rstrip('/')}/"):
            raise ValueError("Coop online product sample is outside its category path")
        if len(self.products) != 1:
            raise ValueError("Coop online product detail sample must contain exactly one Product")
        return self


class CoopOnlineProductDetailSampleEnvelope(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: Literal["coop-online-product-detail-sample-v1"]
    captured_at: datetime
    context: CoopOnlineCaptureContext
    samples: tuple[CoopOnlineProductDetailSampleCapture, ...] = Field(min_length=1)

    @field_validator("captured_at")
    @classmethod
    def captured_at_has_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Coop online product sample timestamp must include a timezone")
        return value


class CoopOnlineContextEvidence(BaseModel):
    """Normalized context assessment used only by online diagnostics."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: CoopOnlineContextKind
    fulfillment_mode: Literal["pickup"]
    selected_label: str
    external_online_context_id: str | None = None
    external_context_id_verification: CoopOnlineContextIdVerification
    physical_store_external_id: str | None = None

    @model_validator(mode="after")
    def verified_context_requires_id(self) -> CoopOnlineContextEvidence:
        if (
            self.external_context_id_verification == CoopOnlineContextIdVerification.VERIFIED
            and not self.external_online_context_id
        ):
            raise ValueError("verified Coop online context requires an external context ID")
        return self


class CoopOnlineProductIdentity(BaseModel):
    """Identity observed in a rendered card; URL suffix is never a GTIN claim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    external_product_id: str
    href: str
    aria_label: str
    gtin: None = None


class CoopOnlineTraversalDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    context: CoopOnlineContextEvidence
    surface: Literal[CoopOnlineCaptureSurface.RENDERED_CATEGORY]
    route: str
    reported_total: int
    pages_fetched: int
    page_row_counts: tuple[int, ...]
    raw_rows: int
    unique_products: int
    duplicate_products: int
    complete_page_union: bool
    store_price_context_verified: bool
    products: tuple[CoopOnlineProductIdentity, ...]
    raw_references: tuple[str, ...]

    @model_validator(mode="after")
    def verified_price_context_requires_verified_online_identity(
        self,
    ) -> CoopOnlineTraversalDiagnostic:
        if self.store_price_context_verified and (
            self.context.external_context_id_verification
            != CoopOnlineContextIdVerification.VERIFIED
            or self.context.external_online_context_id is None
        ):
            raise ValueError(
                "verified Coop online traversal price requires a verified online context ID"
            )
        return self


class CoopOnlineProductDetailObservation(BaseModel):
    """JSON-LD facts retained diagnostically while store price context is unverified."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    context: CoopOnlineContextEvidence
    surface: Literal[CoopOnlineCaptureSurface.PRODUCT_DETAIL_JSON_LD]
    external_product_id: str
    url_source_id: str | None = None
    gtin: str | None = None
    gtin_evidence: Literal["explicit_jsonld"] | None = None
    name: str
    brand: str | None = None
    category_path: tuple[str, ...] = ()
    package_quantity: Decimal | None = Field(default=None, gt=0)
    package_unit: str | None = None
    sale_price: Decimal | None = Field(default=None, gt=0)
    price_currency: str | None = None
    availability: str | None = None
    price_context_verified: bool
    raw_reference: str
    source_url: str

    @model_validator(mode="after")
    def paired_package_fields(self) -> CoopOnlineProductDetailObservation:
        if (self.package_quantity is None) != (self.package_unit is None):
            raise ValueError("package quantity and unit must be supplied together")
        if (self.gtin is None) != (self.gtin_evidence is None):
            raise ValueError("GTIN evidence must accompany exactly one explicit GTIN")
        if self.price_context_verified and (
            self.context.external_context_id_verification
            != CoopOnlineContextIdVerification.VERIFIED
            or self.context.external_online_context_id is None
        ):
            raise ValueError(
                "verified Coop online product price requires a verified online context ID"
            )
        return self


class CoopOnlineDiagnosticReplayResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    traversal: CoopOnlineTraversalDiagnostic
    product_details: tuple[CoopOnlineProductDetailObservation, ...] = ()
    network_requests: Literal[0] = 0
    browser_launches: Literal[0] = 0
