from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    PromotionType,
    SaleModel,
)


class SourceOffer(BaseModel):
    """Promotion facts as stated by a source; eligibility remains conditional."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    external_id: str | None = None
    type: PromotionType
    valid_from: date | None = None
    valid_to: date | None = None
    price: Decimal | None = Field(default=None, gt=0)
    quantity: int | None = Field(default=None, ge=1)
    member_only: bool = False
    max_quantity: int | None = Field(default=None, ge=1)
    description: str | None = None
    source_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_dates(self) -> "SourceOffer":
        if self.source_payload.get('purchase_terms'):
            from grocery_data.app.domain.purchase_terms import PurchaseTerms
            terms = PurchaseTerms.model_validate(self.source_payload['purchase_terms'])
            if terms.mixing_allowed and (terms.complete_group_size != self.quantity
                                         or self.price is None or self.valid_from is None or self.valid_to is None):
                raise ValueError('Mixed source campaign requires complete price, quantity and dates')
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to")
        return self


class SourceProduct(BaseModel):
    """Loss-minimising source record. No comparison-price inference is allowed."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    chain: Chain
    store_external_id: str
    external_product_id: str | None = None
    gtin: str | None = None
    name: str = Field(min_length=1)
    brand: str | None = None
    category_path: tuple[str, ...] = ()
    sale_price: Decimal | None = Field(default=None, gt=0)
    regular_price: Decimal | None = Field(default=None, gt=0)
    member_price: Decimal | None = Field(default=None, gt=0)
    comparison_price: Decimal | None = Field(default=None, gt=0)
    comparison_unit: str | None = None
    package_text: str | None = None
    package_quantity: Decimal | None = Field(default=None, gt=0)
    package_unit: str | None = None
    drained_quantity: Decimal | None = Field(default=None, gt=0)
    sale_unit: str | None = None
    offers: tuple[SourceOffer, ...] = ()
    availability: str | None = None
    average_weight_kg: Decimal | None = Field(default=None, gt=0)
    increment_value: Decimal | None = Field(default=None, gt=0)
    basket_type: str | None = None
    raw_reference: str
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    source_fields: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def paired_fields(self) -> "SourceProduct":
        if (self.comparison_price is None) != (self.comparison_unit is None):
            raise ValueError("comparison price and unit must be provided together")
        if (self.package_quantity is None) != (self.package_unit is None):
            raise ValueError("package quantity and unit must be provided together")
        return self


class CanonicalProduct(BaseModel):
    """Conservative purchase interpretation derived from a SourceProduct."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    source_product_key: str
    chain: Chain
    store_external_id: str
    external_product_id: str | None = None
    gtin: str | None = None
    name: str
    brand: str | None = None
    category_path: tuple[str, ...] = ()
    canonical_food: str | None = None
    product_role: str | None = None
    product_form: str | None = None
    semantic_confidence: Confidence = Confidence.UNKNOWN
    sale_model: SaleModel = SaleModel.UNKNOWN
    quantity_confidence: Confidence = Confidence.UNKNOWN
    package_quantity: Decimal | None = Field(default=None, gt=0)
    package_unit: str | None = None
    usable_quantity: Decimal | None = Field(default=None, gt=0)
    usable_unit: str | None = None
    sale_price: Decimal | None = Field(default=None, gt=0)
    sale_unit: str | None = None
    unit_price: Decimal | None = Field(default=None, gt=0)
    comparison_price: Decimal | None = Field(default=None, gt=0)
    comparison_unit: str | None = None
    availability: str | None = None
    offers: tuple[SourceOffer, ...] = ()
    raw_reference: str
    parser_version: str
    normalizer_version: str
    observed_at: datetime


class ParseFailure(BaseModel):
    model_config = ConfigDict(frozen=True)

    raw_record_reference: str
    error_code: str
    error_message: str
    parser_version: str
    sample: dict[str, Any] = Field(default_factory=dict)


class ProductParseResult(BaseModel):
    products: list[SourceProduct] = Field(default_factory=list)
    failures: list[ParseFailure] = Field(default_factory=list)
