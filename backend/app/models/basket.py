from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)

from .ingredient import NormalizedIngredient
from .product import (
    CanonicalUnit,
    OfferMetadata,
    PromotionGroup,
    QuantityConfidence,
    SaleModel,
    SemanticConfidence,
)
from .provenance import SourceProvenance


class BasketAuditStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class BasketVerificationStatus(StrEnum):
    """Trust level for the semantic and physical interpretation of a basket."""

    VERIFIED = "VERIFIED"
    VERIFIED_WITH_ESTIMATES = "VERIFIED_WITH_ESTIMATES"
    UNVERIFIED = "UNVERIFIED"
    INVALID = "INVALID"


_VERIFICATION_RANK = {
    BasketVerificationStatus.VERIFIED: 0,
    BasketVerificationStatus.VERIFIED_WITH_ESTIMATES: 1,
    BasketVerificationStatus.UNVERIFIED: 2,
    BasketVerificationStatus.INVALID: 3,
}

_CENT = Decimal("0.01")


def _money(value: float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def worst_verification_status(
    statuses: list[BasketVerificationStatus],
) -> BasketVerificationStatus:
    """Return the least trustworthy status in a deterministic way."""

    return max(
        statuses or [BasketVerificationStatus.VERIFIED],
        key=_VERIFICATION_RANK.__getitem__,
    )


class BasketItem(BaseModel):
    """The concrete packages bought for one aggregated ingredient."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    ingredient: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    gtin: str | None = Field(default=None, pattern=r"^\d{8,14}$")
    chain: str | None = Field(default=None, min_length=1)
    price_context_type: str | None = Field(default=None, min_length=1)
    coverage: str | None = Field(default=None, min_length=1)
    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    required_quantity: float = Field(gt=0)
    strategic_extra_quantity: float = Field(default=0, ge=0)
    unit: CanonicalUnit
    canonical_food: str | None = None
    food_family: str | None = None
    product_role: str | None = None
    product_form: str | None = None
    semantic_confidence: SemanticConfidence = SemanticConfidence.LOW
    semantic_evidence: list[str] = Field(default_factory=list)
    sale_model: SaleModel = SaleModel.UNKNOWN
    sale_price: float | None = Field(default=None, gt=0)
    sale_unit: str | None = None
    comparison_price: float | None = Field(default=None, gt=0)
    comparison_unit: str | None = None
    piece_price: float | None = Field(default=None, gt=0)
    estimated_piece_weight: float | None = Field(default=None, gt=0)
    estimated_piece_weight_unit: CanonicalUnit = "g"
    package_quantity: float | None = Field(default=None, gt=0)
    package_unit: CanonicalUnit | None = None
    usable_quantity: float | None = Field(
        default=None,
        gt=0,
        description="Usable recipe quantity supplied by one package",
    )
    usable_unit: CanonicalUnit | None = None
    quantity_confidence: QuantityConfidence = QuantityConfidence.UNKNOWN
    variable_weight: bool = False
    packages_needed: int = Field(ge=1)
    purchased_quantity: float = Field(
        gt=0,
        description="Purchased gross/reference quantity in purchased_unit",
    )
    purchased_unit: CanonicalUnit | None = None
    purchased_usable_quantity: float | None = Field(default=None, gt=0)
    waste_quantity: float = Field(ge=0)
    unit_price: float = Field(ge=0, description="Applied per-package price in SEK")
    regular_unit_price: float | None = Field(default=None, gt=0)
    price_contract_id: str | None = Field(default=None, min_length=1, max_length=255)
    eligibility: PromotionEligibility = PromotionEligibility.PUBLIC
    price_mechanism: PromotionMechanism = PromotionMechanism.REGULAR
    membership_program: MembershipProgram | None = None
    base_checkout_unit_price: float | None = Field(
        default=None,
        gt=0,
        description=("Eligible one-package checkout price before a conditional multipack offer"),
    )
    total_price: float = Field(ge=0)
    regular_total_price: float | None = Field(default=None, gt=0)
    purchase_warning: str | None = None
    offer_description: str | None = None
    applied_offer: OfferMetadata | None = None
    promotion_groups: tuple[PromotionGroup, ...] = ()
    checkout_offers: tuple[OfferMetadata, ...] = ()
    group_applications: list[dict] = Field(default_factory=list)
    group_residual_packages: int | None = Field(default=None, ge=0)
    group_residual_total: float | None = Field(default=None, ge=0)
    ungrouped_total_price: float | None = Field(default=None, ge=0)
    source_provenance: SourceProvenance | None = None

    @computed_field
    @property
    def membership_required(self) -> bool:
        return self.eligibility is PromotionEligibility.MEMBER

    @model_validator(mode="before")
    @classmethod
    def map_legacy_sale_model(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        sale_model = data.get("sale_model")
        if sale_model in {None, SaleModel.UNKNOWN, "unknown"}:
            if data.get("variable_weight"):
                data["sale_model"] = SaleModel.SOLD_BY_WEIGHT
            elif data.get("package_quantity") is not None:
                data["sale_model"] = SaleModel.FIXED_PACKAGE
        return data

    @model_validator(mode="after")
    def validate_quantities(self) -> BasketItem:
        if self.sale_price is None:
            object.__setattr__(self, "sale_price", self.unit_price)
        if self.regular_unit_price is None:
            object.__setattr__(
                self,
                "regular_unit_price",
                (
                    self.regular_total_price / self.packages_needed
                    if self.regular_total_price is not None
                    else self.base_checkout_unit_price or self.unit_price
                ),
            )
        if self.eligibility is PromotionEligibility.MEMBER:
            if self.membership_program is None:
                raise ValueError("member checkout requires membership_program")
            normalized_chain = (self.chain or "").casefold().replace(" ", "")
            if normalized_chain and self.membership_program.chain != normalized_chain:
                raise ValueError("membership program does not match basket item chain")
        elif self.membership_program is not None:
            raise ValueError("membership_program requires member eligibility")
        if (
            self.price_mechanism is not PromotionMechanism.REGULAR
            and self.price_contract_id is None
        ):
            raise ValueError("promotional checkout requires price_contract_id")
        if self.sale_model == SaleModel.FIXED_PACKAGE and self.base_checkout_unit_price is None:
            # Backward-compatible evidence for basket payloads created before
            # this field existed. New calculator output always persists the
            # actual pre-multipack checkout price explicitly.
            object.__setattr__(self, "base_checkout_unit_price", self.unit_price)
        if self.package_quantity is not None and self.package_unit is None:
            object.__setattr__(self, "package_unit", self.unit)
        if (
            self.usable_quantity is None
            and self.package_quantity is not None
            and self.sale_model in {SaleModel.FIXED_PACKAGE, SaleModel.VARIABLE_WEIGHT_PACKAGE}
        ):
            object.__setattr__(self, "usable_quantity", self.package_quantity)
        if self.usable_quantity is not None and self.usable_unit is None:
            object.__setattr__(self, "usable_unit", self.unit)
        if self.purchased_usable_quantity is None:
            object.__setattr__(self, "purchased_usable_quantity", self.purchased_quantity)
        if self.purchased_unit is None:
            object.__setattr__(self, "purchased_unit", self.package_unit or self.unit)
        if self.usable_unit is not None and self.usable_unit != self.unit:
            raise ValueError("usable_unit must match the required ingredient unit")

        usable_tolerance = max(1e-6, self.purchased_usable_quantity * 1e-9)
        if self.sale_model in {
            SaleModel.FIXED_PACKAGE,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }:
            if self.package_quantity is None or self.package_unit is None:
                raise ValueError("package purchases require explicit package quantity")
            if self.usable_quantity is None or self.usable_unit is None:
                raise ValueError("package purchases require explicit usable quantity")
            if (
                self.package_unit == self.usable_unit
                and self.usable_quantity > self.package_quantity
            ):
                raise ValueError("usable_quantity cannot exceed gross package_quantity")
            expected_purchased = self.package_quantity * self.packages_needed
            gross_tolerance = max(1e-6, expected_purchased * 1e-9)
            if abs(self.purchased_quantity - expected_purchased) > gross_tolerance:
                raise ValueError("purchased_quantity must equal package_quantity * packages_needed")
            expected_usable = self.usable_quantity * self.packages_needed
            usable_tolerance = max(1e-6, expected_usable * 1e-9)
            if abs(self.purchased_usable_quantity - expected_usable) > usable_tolerance:
                raise ValueError(
                    "purchased_usable_quantity must equal usable_quantity * packages_needed"
                )
        elif self.sale_model == SaleModel.SOLD_BY_PIECE:
            gross_tolerance = max(1e-6, self.packages_needed * 1e-9)
            if abs(self.purchased_quantity - self.packages_needed) > gross_tolerance:
                raise ValueError("piece purchases must buy packages_needed pieces")
        elif self.sale_model == SaleModel.SOLD_BY_WEIGHT:
            if self.purchased_quantity != self.purchased_usable_quantity:
                raise ValueError("sold-by-weight gross and usable quantities must agree")

        expected_waste = self.purchased_usable_quantity - self.required_quantity
        if expected_waste < -usable_tolerance:
            raise ValueError("purchased quantity cannot be smaller than required quantity")
        if abs(self.waste_quantity - max(0.0, expected_waste)) > usable_tolerance:
            raise ValueError("waste_quantity must equal purchased usable minus required quantity")
        return self

    @computed_field
    @property
    def verification_status(self) -> BasketVerificationStatus:
        if self.semantic_confidence in {
            SemanticConfidence.LOW,
            SemanticConfidence.REJECTED,
        }:
            return BasketVerificationStatus.INVALID
        if self.sale_model == SaleModel.UNKNOWN:
            return BasketVerificationStatus.UNVERIFIED
        if self.quantity_confidence == QuantityConfidence.UNKNOWN:
            return BasketVerificationStatus.UNVERIFIED
        if self.quantity_confidence == QuantityConfidence.ESTIMATED:
            return BasketVerificationStatus.VERIFIED_WITH_ESTIMATES
        return BasketVerificationStatus.VERIFIED


class StoreBasket(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    total: float = Field(ge=0)
    items: list[BasketItem] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)
    is_complete: bool = True
    verification_status: BasketVerificationStatus = BasketVerificationStatus.VERIFIED
    verification_warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def total_reconciled(self) -> bool:
        return _money(self.total) == _money(sum((item.total_price for item in self.items), 0.0))

    @model_validator(mode="after")
    def sync_completeness(self) -> StoreBasket:
        expected = not self.missing_ingredients
        if self.is_complete != expected:
            object.__setattr__(self, "is_complete", expected)
        status = worst_verification_status(
            [self.verification_status, *(item.verification_status for item in self.items)]
        )
        if not expected:
            status = BasketVerificationStatus.INVALID
        if not self.total_reconciled:
            status = BasketVerificationStatus.INVALID
        object.__setattr__(self, "verification_status", status)
        warnings = list(self.verification_warnings)
        if status == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES:
            warnings.append("Matkassen innehåller uppskattade mängder eller vikter.")
        elif status == BasketVerificationStatus.UNVERIFIED:
            warnings.append("Minst en produkts inköpsmängd kan inte verifieras.")
        elif status == BasketVerificationStatus.INVALID:
            warnings.append("Matkassen är ofullständig eller semantiskt ogiltig.")
        if not self.total_reconciled:
            warnings.append("Butikssumman stämmer inte med de valda produktraderna.")
        object.__setattr__(self, "verification_warnings", list(dict.fromkeys(warnings)))
        return self


class OptimizedStoreGroup(BaseModel):
    model_config = ConfigDict(frozen=True)

    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    items: list[BasketItem] = Field(default_factory=list)
    subtotal: float = Field(ge=0)

    @computed_field
    @property
    def subtotal_reconciled(self) -> bool:
        return _money(self.subtotal) == _money(sum((item.total_price for item in self.items), 0.0))


class OptimizedBasket(BaseModel):
    model_config = ConfigDict(frozen=True)

    total: float = Field(ge=0)
    stores: list[OptimizedStoreGroup] = Field(default_factory=list)
    max_stores: int | None = Field(default=None, ge=1)
    savings_vs_single_store: float | None = Field(default=None, ge=0)
    verification_status: BasketVerificationStatus = BasketVerificationStatus.VERIFIED
    verification_warnings: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def total_reconciled(self) -> bool:
        return all(group.subtotal_reconciled for group in self.stores) and _money(
            self.total
        ) == _money(sum((group.subtotal for group in self.stores), 0.0))

    @model_validator(mode="after")
    def aggregate_verification(self) -> OptimizedBasket:
        items = [item for group in self.stores for item in group.items]
        status = worst_verification_status(
            [self.verification_status, *(item.verification_status for item in items)]
        )
        if not self.total_reconciled:
            status = BasketVerificationStatus.INVALID
        object.__setattr__(self, "verification_status", status)
        warnings = list(self.verification_warnings)
        if status == BasketVerificationStatus.VERIFIED_WITH_ESTIMATES:
            warnings.append("Matkassen innehåller uppskattade mängder eller vikter.")
        elif status == BasketVerificationStatus.UNVERIFIED:
            warnings.append("Totalpriset är inte verifierat på grund av okänd mängdmetadata.")
        elif status == BasketVerificationStatus.INVALID:
            warnings.append("Matkassen innehåller en ogiltig produktmatchning.")
        if not self.total_reconciled:
            warnings.append("Matkassans total eller butikssummor stämmer inte med produktraderna.")
        object.__setattr__(self, "verification_warnings", list(dict.fromkeys(warnings)))
        return self

    @computed_field
    @property
    def store_count(self) -> int:
        return len(self.stores)


class BasketAuditSelectedProduct(BaseModel):
    """Product evidence behind an audited usable quantity."""

    model_config = ConfigDict(frozen=True)

    product_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    packages_needed: int = Field(ge=1)
    usable_quantity: float = Field(gt=0)
    usable_unit: CanonicalUnit
    purchased_quantity: float = Field(gt=0)
    purchased_unit: CanonicalUnit
    purchased_usable_quantity: float = Field(gt=0)
    quantity_confidence: QuantityConfidence
    semantic_confidence: SemanticConfidence = SemanticConfidence.LOW
    sale_model: SaleModel = SaleModel.UNKNOWN
    quantity_reconciled: bool = True
    cost_reconciled: bool = True
    reconciliation_error: str | None = None
    total_price: float = Field(ge=0)


class BasketAuditItem(BaseModel):
    """Coverage result for one canonical ingredient and physical unit."""

    model_config = ConfigDict(frozen=True)

    canonical_name: str = Field(min_length=1)
    unit: CanonicalUnit
    status: BasketAuditStatus
    required_quantity: float = Field(ge=0)
    purchased_usable_quantity: float = Field(ge=0)
    deficit_quantity: float = Field(ge=0)
    surplus_quantity: float = Field(ge=0)
    surplus_percent: float | None = Field(default=None, ge=0)
    estimated_surplus_value: float = Field(default=0, ge=0)
    quantity_confidence: QuantityConfidence = QuantityConfidence.UNKNOWN
    quantity_reconciled: bool = True
    cost_reconciled: bool = True
    selected_products: list[BasketAuditSelectedProduct] = Field(default_factory=list)


class BasketAuditUnitTotals(BaseModel):
    model_config = ConfigDict(frozen=True)

    unit: CanonicalUnit
    required_quantity: float = Field(ge=0)
    purchased_usable_quantity: float = Field(ge=0)
    deficit_quantity: float = Field(ge=0)
    surplus_quantity: float = Field(ge=0)
    estimated_surplus_value: float = Field(ge=0)


class BasketAuditResult(BaseModel):
    """Deterministic audit of an optimized basket against recipe requirements."""

    model_config = ConfigDict(frozen=True)

    status: BasketAuditStatus
    items: list[BasketAuditItem] = Field(default_factory=list)
    pantry_items: list[NormalizedIngredient] = Field(default_factory=list)
    deficits: list[BasketAuditItem] = Field(default_factory=list)
    unit_totals: list[BasketAuditUnitTotals] = Field(default_factory=list)
    estimated_surplus_value_total: float = Field(default=0, ge=0)
    verification_status: BasketVerificationStatus = BasketVerificationStatus.VERIFIED
    verification_warnings: list[str] = Field(default_factory=list)
    totals_reconciled: bool = True
    calculated_total: float = Field(default=0, ge=0)
    reported_total: float | None = Field(default=None, ge=0)
    total_reconciliation_errors: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def passed(self) -> bool:
        return self.status == BasketAuditStatus.PASS

    @computed_field
    @property
    def ingredients_checked(self) -> int:
        return len(self.items)

    @computed_field
    @property
    def unknown_quantities(self) -> int:
        return sum(item.quantity_confidence == QuantityConfidence.UNKNOWN for item in self.items)
