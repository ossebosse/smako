from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from enum import StrEnum
from math import isfinite
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from grocery_data.app.domain.campaign_validity import CampaignEvidence
from grocery_data.app.domain.counted_offer_checkout import uses_counted_offer_checkout
from grocery_data.app.domain.promotion_pricing import (
    DepositContract,
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.domain.purchase_terms import PurchaseTerms

_STOCKHOLM = ZoneInfo("Europe/Stockholm")

from .provenance import GlobalProductIdentity, SourceProvenance

CanonicalUnit = Literal["g", "ml", "st"]


class QuantityConfidence(StrEnum):
    """How trustworthy a product's usable quantity is."""

    EXACT = "exact"
    DERIVED = "derived"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class SaleModel(StrEnum):
    """How a shopper is charged for a product.

    This is deliberately independent from comparison-price metadata.  A
    ``kr/kg`` comparison price describes a rate; it does not prove that the
    product is a fixed one-kilogram package or even that it is sold by weight.
    """

    FIXED_PACKAGE = "fixed_package"
    SOLD_BY_WEIGHT = "sold_by_weight"
    SOLD_BY_PIECE = "sold_by_piece"
    VARIABLE_WEIGHT_PACKAGE = "variable_weight_package"
    UNKNOWN = "unknown"


class SemanticConfidence(StrEnum):
    """Confidence that a product is an appropriate food replacement."""

    EXACT = "exact"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    REJECTED = "rejected"


class OfferKind(StrEnum):
    CAMPAIGN = "campaign"
    MEMBER = "member"
    MULTIPACK = "multipack"


class PromotionGroup(BaseModel):
    """Explicit source group. No name/category-derived eligibility is permitted."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    group_id: str = Field(min_length=1, max_length=255)
    chain: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    eligible_product_ids: tuple[str, ...] = Field(min_length=1, max_length=500)
    required_packages: int = Field(ge=2, le=100)
    pricing_rule: Literal["fixed_total", "group_discount"]
    amount: float = Field(gt=0)
    valid_from: date
    valid_to: date
    membership_program: MembershipProgram | None = None
    max_groups: int | None = Field(default=None, ge=1)
    limit_scope: Literal["store", "household_campaign"] = Field(default="store", exclude_if=lambda v: v == "store")
    limit_key: str | None = Field(default=None, min_length=1, exclude_if=lambda v: v is None)
    source: str = Field(min_length=1)
    source_snapshot_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def valid_group(self):
        if self.limit_scope == "household_campaign" and (not self.limit_key or self.max_groups is None):
            raise ValueError("Household group limit requires an explicit shared source key and cap")
        if self.valid_from > self.valid_to:
            raise ValueError("Invalid group validity window")
        if len(set(self.eligible_product_ids)) != len(self.eligible_product_ids):
            raise ValueError("Duplicate eligible product identity")
        if self.membership_program and self.membership_program.chain != self.chain:
            raise ValueError("Group membership and retailer differ")
        return self


class OfferMetadata(BaseModel):
    """A compact normalized price contract stored inside PriceUniverse.

    ``kind`` remains as a backwards-compatible source projection. Eligibility
    and mechanism are the authoritative orthogonal dimensions: a member-only
    multibuy is therefore represented without flattening it into either a plain
    member unit price or a public multipack. ``price`` covers the complete
    ``required_packages`` group.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    purchase_terms: PurchaseTerms | None = Field(default=None, exclude_if=lambda v: v is None)
    kind: OfferKind
    description: str = Field(min_length=1)
    price: float = Field(gt=0)
    price_basis_unit: Literal['package', 'kg'] = Field(default='package',
        exclude_if=lambda value: value == 'package')
    required_packages: int = Field(default=1, ge=1)
    max_quantity: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum discounted packages for a single-package offer, or maximum "
            "discounted groups for a multipack offer"
        ),
    )
    price_contract_id: str | None = Field(default=None, min_length=1, max_length=255)
    eligibility: PromotionEligibility | None = None
    mechanism: PromotionMechanism | None = None
    membership_program: MembershipProgram | None = None
    member_program: str | None = None
    percent_discount: float | None = Field(default=None, gt=0, lt=100)
    currency: Literal["SEK"] = "SEK"
    source_confidence: str | None = Field(default=None, min_length=1, max_length=64)
    semantic_confidence: str | None = Field(default=None, min_length=1, max_length=64)
    quantity_confidence: str | None = Field(default=None, min_length=1, max_length=64)
    valid_from: date | None = None
    valid_to: date | None = None
    campaign_evidence: CampaignEvidence | None = Field(default=None, exclude_if=lambda value: value is None)
    deposit: DepositContract | None = Field(default=None, exclude_if=lambda value: value is None)

    @model_validator(mode="before")
    @classmethod
    def normalize_contract_axes(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        kind = data.get("kind")
        member_label = data.get("member_program")
        explicit_program = data.get("membership_program")
        if explicit_program is None and member_label:
            try:
                data["membership_program"] = MembershipProgram.from_value(str(member_label))
            except ValueError:
                # Preserve unknown source wording as provenance, but never turn
                # it into request-time eligibility.
                pass
        if data.get("eligibility") is None:
            data["eligibility"] = (
                PromotionEligibility.MEMBER
                if kind in {OfferKind.MEMBER, OfferKind.MEMBER.value}
                or member_label
                or explicit_program
                else PromotionEligibility.PUBLIC
            )
        if data.get("mechanism") is None:
            if kind in {OfferKind.MULTIPACK, OfferKind.MULTIPACK.value}:
                data["mechanism"] = PromotionMechanism.MULTIBUY
            elif data.get("percent_discount") is not None:
                data["mechanism"] = PromotionMechanism.PERCENT_DISCOUNT
            else:
                data["mechanism"] = PromotionMechanism.SALE_PRICE
        return data

    @model_validator(mode="after")
    def validate_offer(self) -> OfferMetadata:
        if self.purchase_terms and self.purchase_terms.complete_group_size != self.required_packages:
            raise ValueError('physical purchase group and price group differ')
        if self.eligibility is PromotionEligibility.USER_SPECIFIC:
            raise ValueError("user-specific contracts cannot enter shared product offers")
        if self.eligibility is PromotionEligibility.MEMBER and not (
            self.membership_program or self.member_program
        ):
            raise ValueError("member offers require a membership program")
        if self.mechanism is PromotionMechanism.MULTIBUY:
            if self.required_packages < 2:
                raise ValueError("multibuy offers require multiple packages")
        elif self.required_packages != 1:
            raise ValueError("only multibuy offers can require multiple packages")
        if self.mechanism is PromotionMechanism.PERCENT_DISCOUNT:
            if self.percent_discount is None:
                raise ValueError("percent-discount offers require percent_discount")
        elif self.percent_discount is not None:
            raise ValueError("percent_discount requires percent-discount mechanism")
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to")
        return self

    def is_active(self, on_date: date | None = None) -> bool:
        target = on_date or datetime.now(tz=_STOCKHOLM).date()
        if self.campaign_evidence is not None:
            return self.campaign_evidence.applies(target, self.valid_from, self.valid_to)
        return not (
            (self.valid_from is not None and target < self.valid_from)
            or (self.valid_to is not None and target > self.valid_to)
        )


class ProductSemantics(BaseModel):
    """Central semantic and physical purchase interpretation of a product.

    ``package_quantity`` and ``usable_quantity`` are intentionally nullable.
    Unknown source metadata must remain unknown rather than being inferred
    from a comparison-price unit.  Legacy callers that provide an explicit
    package quantity and unit are interpreted as fixed packages, while the
    old ``variable_weight=True`` input maps to ``SOLD_BY_WEIGHT``.
    """

    # Reject NaN and infinities at the structured-data boundary.  Field bounds
    # such as ``gt=0`` alone still accept positive infinity, which would later
    # fail Decimal checkout arithmetic inside the quantity resolver.
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    product_id: str = Field(min_length=1)
    canonical_food: str | None = None
    food_family: str | None = None
    product_role: str | None = None
    product_form: str | None = None
    sale_model: SaleModel = SaleModel.UNKNOWN
    package_quantity: float | None = Field(default=None, gt=0)
    package_unit: CanonicalUnit | None = None
    usable_quantity: float | None = Field(
        default=None,
        gt=0,
        description="Usable recipe quantity per package or priced reference unit",
    )
    usable_unit: CanonicalUnit | None = None
    sale_price: float | None = Field(default=None, gt=0)
    conditional_price_signal: bool = Field(default=False, exclude_if=lambda value: not value,
        description='Ranking/quantity signal only; checkout requires the explicit eligible offer group')
    sale_unit: str | None = None
    comparison_price: float | None = Field(default=None, gt=0)
    comparison_unit: str | None = None
    piece_price: float | None = Field(default=None, gt=0)
    estimated_piece_weight: float | None = Field(default=None, gt=0)
    estimated_piece_weight_unit: CanonicalUnit = "g"
    semantic_confidence: SemanticConfidence = SemanticConfidence.LOW
    quantity_confidence: QuantityConfidence = QuantityConfidence.UNKNOWN
    variable_weight: bool = False
    purchase_terms: PurchaseTerms | None = Field(default=None, exclude_if=lambda v: v is None)
    conditional_variant_choice: bool = Field(default=False, exclude_if=lambda v: not v)

    @model_validator(mode="before")
    @classmethod
    def map_legacy_purchase_fields(cls, value: Any) -> Any:
        """Map old payloads without manufacturing physical quantities."""

        if not isinstance(value, Mapping):
            return value
        data = dict(value)

        terms = [o.get("purchase_terms") if isinstance(o, Mapping) else o.purchase_terms
                 for o in data.get("offers", ())]
        terms = [PurchaseTerms.model_validate(t) for t in terms if t is not None]
        if terms:
            if any(t != terms[0] for t in terms):
                raise ValueError("conflicting purchase evidence across offers")
            if data.get("purchase_terms") is not None and PurchaseTerms.model_validate(data["purchase_terms"]) != terms[0]:
                raise ValueError("product and offer purchase evidence differ")
            data["purchase_terms"] = terms[0]

        # Product and ProductCandidate historically called this field ``price``.
        # It remains available on both subclasses; sale_price is the common
        # semantics name used by the resolver.
        if data.get("sale_price") is None and data.get("price") is not None:
            data["sale_price"] = data["price"]

        if data.get("canonical_food") is None and data.get("canonical_name"):
            data["canonical_food"] = data["canonical_name"]

        sale_model = data.get("sale_model")
        sale_model_is_unknown = sale_model in {None, SaleModel.UNKNOWN, "unknown"}
        if bool(data.get("variable_weight", False)) and sale_model_is_unknown:
            data["sale_model"] = SaleModel.SOLD_BY_WEIGHT
        elif sale_model_is_unknown:
            # Backward-compatible only when a package amount is explicit.  A
            # comparison price is never considered evidence of package size.
            if data.get("package_quantity") is not None and data.get("package_unit"):
                data["sale_model"] = SaleModel.FIXED_PACKAGE
        elif sale_model in {SaleModel.SOLD_BY_WEIGHT, "sold_by_weight"}:
            # Keep old readers working while the resolver becomes the single
            # calculation path. Explicit variable-weight packages remain a
            # separate model and must not be treated as fractionally purchasable.
            data["variable_weight"] = True

        return data

    @model_validator(mode="after")
    def validate_purchase_semantics(self) -> ProductSemantics:
        if self.sale_price is None and not (
            getattr(self, "offers", None) and uses_counted_offer_checkout(self)
        ):
            raise ValueError("missing purchase price without an explicit counted offer contract")
        if (self.package_quantity is None) != (self.package_unit is None):
            raise ValueError("package_quantity and package_unit must be provided together")
        if (self.usable_quantity is None) != (self.usable_unit is None):
            raise ValueError("usable_quantity and usable_unit must be provided together")
        if (self.comparison_price is None) != (self.comparison_unit is None):
            raise ValueError("comparison_price and comparison_unit must be provided together")
        if (
            self.sale_model in {SaleModel.FIXED_PACKAGE, SaleModel.VARIABLE_WEIGHT_PACKAGE}
            and self.package_quantity is not None
            and self.usable_quantity is not None
            and self.package_unit == self.usable_unit
            and self.usable_quantity > self.package_quantity
        ):
            raise ValueError("usable_quantity cannot exceed gross package_quantity")
        if self.sale_model == SaleModel.SOLD_BY_PIECE and self.piece_price is None:
            object.__setattr__(self, "piece_price", self.sale_price)
        if (
            self.usable_quantity is None
            and self.package_quantity is not None
            and self.sale_model
            in {
                SaleModel.FIXED_PACKAGE,
                SaleModel.SOLD_BY_WEIGHT,
                SaleModel.VARIABLE_WEIGHT_PACKAGE,
            }
        ):
            object.__setattr__(self, "usable_quantity", self.package_quantity)
            object.__setattr__(self, "usable_unit", self.package_unit)
        return self


class Product(ProductSemantics):
    """A purchasable product with package size and deterministic price data."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    name: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    price: float | None = Field(default=None, gt=0, description="Independently observed ordinary package price in SEK; unknown stays null")
    effective_price: float | None = Field(
        default=None,
        gt=0,
        description="Best eligible one-package price in SEK",
    )
    member_price: float | None = Field(default=None, gt=0)
    offers: list[OfferMetadata] = Field(default_factory=list)
    promotion_groups: tuple[PromotionGroup, ...] = Field(default=(), exclude_if=lambda v: not v)
    brand: str | None = None
    chain: str | None = Field(default=None, min_length=1)
    gtin: str | None = Field(default=None, pattern=r"^\d{8,14}$")
    price_context_type: str | None = Field(default=None, min_length=1)
    coverage: str | None = Field(default=None, min_length=1)
    search_terms: list[str] = Field(default_factory=list, exclude=True)
    source_provenance: SourceProvenance | None = None

    @computed_field
    @property
    def global_identity(self) -> GlobalProductIdentity | None:
        return GlobalProductIdentity(gtin=self.gtin) if self.gtin is not None else None

    @model_validator(mode="after")
    def fill_and_validate_prices(self) -> Product:
        if self.conditional_variant_choice:
            raise ValueError("Conditional variant choice belongs to a private request, not source product identity")
        if self.price is None:
            unmeasured_rate = (self.sale_model in {SaleModel.UNKNOWN, SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}
                and (self.purchase_terms is not None or (self.package_quantity is None and self.usable_quantity is None))
                and self.coverage == 'offers_only' and self.offers
                and all(o.price_basis_unit == 'kg' and o.campaign_evidence for o in self.offers))
            retained_group = self.purchase_terms and self.purchase_terms.identity_scope == "campaign_group"
            if (not uses_counted_offer_checkout(self) and not unmeasured_rate and not retained_group) or not self.offers:
                raise ValueError("offer-only products require fixed packages or verified sales-unit contracts")
            if any(o.valid_to is None or (o.valid_from is None and o.campaign_evidence is None)
                   for o in self.offers):
                raise ValueError("offer-only contracts require bounded validity")
            if self.effective_price is None:
                object.__setattr__(self, "effective_price", min(o.price / o.required_packages for o in self.offers))
            return self
        effective = self.price if self.effective_price is None else self.effective_price
        if not isfinite(effective):
            raise ValueError("effective_price must be finite")
        if effective > self.price:
            raise ValueError("effective_price cannot exceed ordinary price")
        if self.member_price is not None and self.member_price > self.price:
            raise ValueError("member_price cannot exceed ordinary price")
        if self.effective_price is None:
            object.__setattr__(self, "effective_price", self.price)
        return self

    @computed_field
    @property
    def normalized_unit_price(self) -> float | None:
        """SEK/kg, SEK/litre or SEK/item, based on effective price."""

        sale_unit = (self.sale_unit or "").casefold().strip()
        comparison_unit = (self.comparison_unit or "").casefold().strip()
        if self.sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }:
            if sale_unit in {"kg", "l", "liter", "litre"}:
                return round(self.sale_price, 2)
            if self.comparison_price is not None and comparison_unit in {
                "kg",
                "l",
                "liter",
                "litre",
            }:
                return round(self.comparison_price, 2)
        if self.sale_model == SaleModel.SOLD_BY_PIECE and self.piece_price is not None:
            return round(self.piece_price, 2)
        if self.usable_quantity is None or self.usable_unit is None:
            return None
        multiplier = 1000 if self.usable_unit in {"g", "ml"} else 1
        return round(float(self.effective_price) * multiplier / self.usable_quantity, 2)

    @computed_field
    @property
    def normalized_unit(self) -> Literal["kg", "liter", "st"] | None:
        sale_unit = (self.sale_unit or "").casefold().strip()
        comparison_unit = (self.comparison_unit or "").casefold().strip()
        if self.sale_model == SaleModel.SOLD_BY_PIECE:
            return "st"
        if self.sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }:
            rate_unit = sale_unit or comparison_unit
            if rate_unit == "kg":
                return "kg"
            if rate_unit in {"l", "liter", "litre"}:
                return "liter"
        if self.usable_unit is None:
            return None
        return {"g": "kg", "ml": "liter", "st": "st"}[self.usable_unit]  # type: ignore[return-value]

    @property
    def product_name(self) -> str:
        """Compatibility/readability alias used by basket presentation code."""

        return self.name

    def active_offers(self, on_date: date | None = None) -> list[OfferMetadata]:
        return [offer for offer in self.offers if offer.is_active(on_date)]


class ProductCandidate(ProductSemantics):
    """A scored product match for a normalized recipe ingredient."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    product_name: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    store_id: str = Field(min_length=1)
    store_name: str = Field(min_length=1)
    price: float | None = Field(default=None, gt=0)
    purchase_date: date | None = None
    effective_price: float = Field(gt=0)
    member_price: float | None = Field(default=None, gt=0)
    selected_price_contract_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    selected_price_eligibility: PromotionEligibility = PromotionEligibility.PUBLIC
    selected_price_mechanism: PromotionMechanism = PromotionMechanism.REGULAR
    selected_membership_program: MembershipProgram | None = None
    match_score: float = Field(ge=0, le=1)
    offers: list[OfferMetadata] = Field(default_factory=list)
    promotion_groups: tuple[PromotionGroup, ...] = Field(default=(), exclude_if=lambda v: not v)
    category: str | None = None
    chain: str | None = Field(default=None, min_length=1)
    gtin: str | None = Field(default=None, pattern=r"^\d{8,14}$")
    price_context_type: str | None = Field(default=None, min_length=1)
    coverage: str | None = Field(default=None, min_length=1)
    semantic_evidence: list[str] = Field(default_factory=list)
    source_provenance: SourceProvenance | None = None

    @computed_field
    @property
    def global_identity(self) -> GlobalProductIdentity | None:
        return GlobalProductIdentity(gtin=self.gtin) if self.gtin is not None else None

    @classmethod
    def from_product(cls, product: Product, match_score: float) -> ProductCandidate:
        return cls(
            product_id=product.product_id,
            product_name=product.name,
            canonical_name=product.canonical_name,
            store_id=product.store_id,
            store_name=product.store_name,
            package_quantity=product.package_quantity,
            package_unit=product.package_unit,
            usable_quantity=product.usable_quantity,
            usable_unit=product.usable_unit,
            quantity_confidence=product.quantity_confidence,
            variable_weight=product.variable_weight,
            price=product.price,
            effective_price=float(product.effective_price),
            member_price=product.member_price,
            selected_price_eligibility=PromotionEligibility.PUBLIC,
            selected_price_mechanism=(
                PromotionMechanism.SALE_PRICE
                if product.price is None or float(product.effective_price) < product.price
                else PromotionMechanism.REGULAR
            ),
            match_score=match_score,
            offers=product.offers,
            promotion_groups=product.promotion_groups,
            category=product.category,
            chain=product.chain,
            gtin=product.gtin,
            price_context_type=product.price_context_type,
            coverage=product.coverage,
            canonical_food=product.canonical_food,
            food_family=product.food_family,
            product_role=product.product_role,
            product_form=product.product_form,
            sale_model=product.sale_model,
            sale_price=product.sale_price,
            conditional_price_signal=product.conditional_price_signal,
            purchase_terms=product.purchase_terms,
            sale_unit=product.sale_unit,
            comparison_price=product.comparison_price,
            comparison_unit=product.comparison_unit,
            piece_price=product.piece_price,
            estimated_piece_weight=product.estimated_piece_weight,
            estimated_piece_weight_unit=product.estimated_piece_weight_unit,
            semantic_confidence=product.semantic_confidence,
            source_provenance=product.source_provenance,
        )


class FederatedProductCandidate(ProductCandidate):
    """A unified candidate returned across provider and chain boundaries."""


class CheapIngredient(BaseModel):
    """Compact economic signal passed to a recipe generator."""

    ingredient: str
    product: str
    product_id: str
    store: str
    store_id: str
    price: float = Field(gt=0)
    unit_price: float = Field(gt=0)
    unit: Literal["kg", "liter", "st"]
    is_offer: bool = False
