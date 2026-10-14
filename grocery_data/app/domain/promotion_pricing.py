from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

from grocery_data.app.domain.campaign_validity import CampaignEvidence


def _normalize_binary_decimal_noise(
    value: Any,
    *,
    decimal_places: int,
) -> Any:
    """Remove only negligible float round-trip noise at a decimal boundary.

    PriceUniverse stores compact numeric values as JSON numbers. A legitimate
    ``24.99`` can therefore return to Python as ``24.990000000000002`` before
    an adapter creates a Decimal. Price contracts allow six price decimals
    (four for percentages), so that representation noise must not invalidate
    otherwise exact source evidence.

    Values materially more precise than the field contract remain untouched
    and are rejected by Pydantic. This is deliberately not a general-purpose
    rounding policy.
    """

    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except (ArithmeticError, ValueError):
        return value
    if not parsed.is_finite() or parsed.as_tuple().exponent >= -decimal_places:
        return parsed
    quantum = Decimal(1).scaleb(-decimal_places)
    try:
        quantized = parsed.quantize(quantum, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return parsed
    tolerance = Decimal(1).scaleb(-(decimal_places + 6))
    return quantized if abs(parsed - quantized) <= tolerance else parsed


class PromotionEligibility(StrEnum):
    """Who may use a price, independent of how the discount works."""

    PUBLIC = "public"
    MEMBER = "member"
    USER_SPECIFIC = "user_specific"
    UNKNOWN = "unknown"


class MembershipProgram(StrEnum):
    """Stable program identities used from source normalization to checkout.

    Consumer labels and source-native strings are deliberately not eligibility
    identifiers.  ``from_value`` is the single compatibility boundary for the
    chain flags and labels used by older callers.
    """

    ICA_STAMMIS = "ICA_STAMMIS"
    COOP_MEMBER = "COOP_MEMBER"
    HEMKOP_MEMBER = "HEMKOP_MEMBER"
    LIDL_PLUS = "LIDL_PLUS"
    WILLYS_PLUS = "WILLYS_PLUS"
    CITY_GROSS_PRIO = "CITY_GROSS_PRIO"

    @classmethod
    def from_value(cls, value: MembershipProgram | str) -> MembershipProgram:
        if isinstance(value, cls):
            return value
        normalized = " ".join(str(value).casefold().replace("_", " ").split())
        aliases = {
            "ica": cls.ICA_STAMMIS,
            "ica stammis": cls.ICA_STAMMIS,
            "stammis": cls.ICA_STAMMIS,
            "coop": cls.COOP_MEMBER,
            "coop medlem": cls.COOP_MEMBER,
            "coop member": cls.COOP_MEMBER,
            "hemkop": cls.HEMKOP_MEMBER,
            "hemköp": cls.HEMKOP_MEMBER,
            "hemkop medlem": cls.HEMKOP_MEMBER,
            "hemköp medlem": cls.HEMKOP_MEMBER,
            "hemkop klubb": cls.HEMKOP_MEMBER,
            "hemköp klubb": cls.HEMKOP_MEMBER,
            "klubb hemkop": cls.HEMKOP_MEMBER,
            "klubb hemköp": cls.HEMKOP_MEMBER,
            "lidl": cls.LIDL_PLUS,
            "lidl plus": cls.LIDL_PLUS,
            "willys": cls.WILLYS_PLUS,
            "willys plus": cls.WILLYS_PLUS,
            "citygross": cls.CITY_GROSS_PRIO,
            "city gross": cls.CITY_GROSS_PRIO,
            "city gross prio": cls.CITY_GROSS_PRIO,
            "prio": cls.CITY_GROSS_PRIO,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return cls(str(value).strip().upper())
        except ValueError as exc:
            raise ValueError(f"unknown membership program: {value!r}") from exc

    @property
    def consumer_label(self) -> str:
        return {
            self.ICA_STAMMIS: "ICA Stammis",
            self.COOP_MEMBER: "Coop medlem",
            self.HEMKOP_MEMBER: "Klubb Hemköp",
            self.LIDL_PLUS: "Lidl Plus",
            self.WILLYS_PLUS: "Willys Plus",
            self.CITY_GROSS_PRIO: "City Gross Prio",
        }[self]

    @property
    def chain(self) -> str:
        return {
            self.ICA_STAMMIS: "ica",
            self.COOP_MEMBER: "coop",
            self.HEMKOP_MEMBER: "hemkop",
            self.LIDL_PLUS: "lidl",
            self.WILLYS_PLUS: "willys",
            self.CITY_GROSS_PRIO: "citygross",
        }[self]


class PromotionMechanism(StrEnum):
    """How a price is obtained, independent of customer eligibility."""

    REGULAR = "regular"
    SALE_PRICE = "sale_price"
    MULTIBUY = "multibuy"
    PERCENT_DISCOUNT = "percent_discount"
    OTHER = "other"


class ComparablePriceBasis(StrEnum):
    """The monetary basis that must agree before two observations are compared."""

    PACKAGE_PRICE = "package_price"
    CHECKOUT_TOTAL = "checkout_total"
    UNIT_RATE = "unit_rate"


class DepositContract(BaseModel):
    """Deposit per purchased package, with explicit exact or estimated evidence."""
    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")
    gtin: str | None = Field(default=None, min_length=8, max_length=14)
    confidence: Literal['exact', 'estimated'] = Field(default='exact', exclude_if=lambda v: v == 'exact')
    minimum_per_container: Decimal | None = Field(default=None, gt=0, exclude_if=lambda v: v is None)
    assumption: str | None = Field(default=None, min_length=1, exclude_if=lambda v: v is None)
    per_container: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    containers_per_package: int = Field(ge=1, le=1000)
    inclusion: Literal["included", "additional"]
    evidence: str = Field(min_length=1)

    @model_validator(mode="after")
    def exact_identity(self):
        from grocery_data.app.domain.identifiers import normalize_gtin
        if self.confidence == 'exact' and not self.gtin:
            raise ValueError('Exact deposit requires exact GTIN')
        if self.gtin:
            normalize_gtin(self.gtin)
        if self.confidence == 'estimated' and (not self.assumption
                or self.minimum_per_container is None
                or self.minimum_per_container > self.per_container):
            raise ValueError('Estimated deposit requires assumption and bounded amount')
        return self

    def additional_total(self, package_count: int) -> Decimal:
        return (self.per_container * self.containers_per_package * package_count
                if self.inclusion == "additional" else Decimal(0))


class PriceContract(BaseModel):
    """A verified, provider-neutral price contract.

    ``price`` is the total amount for ``required_packages``.  In particular a
    2-for-30 promotion remains ``price=30`` and ``required_packages=2``; it is
    never flattened into an unconditional 15 currency-unit package price.
    Eligibility and mechanism are deliberately orthogonal, so a member-only
    multibuy is represented without inventing a hybrid promotion type.  A
    regular price is represented by the same model, allowing a shared
    PriceUniverse to retain all contracts and defer eligibility to a request.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    reference: str = Field(min_length=1, max_length=255)
    eligibility: PromotionEligibility
    mechanism: PromotionMechanism
    description: str = Field(min_length=1, max_length=1000)
    price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=6)
    percent_discount: Decimal | None = Field(
        default=None,
        gt=0,
        lt=100,
        max_digits=7,
        decimal_places=4,
    )
    required_packages: int = Field(default=1, ge=1)
    max_quantity: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Maximum discounted packages for a single-price promotion, or "
            "maximum discounted groups for a multibuy"
        ),
    )
    membership_program: MembershipProgram | None = None
    member_program: str | None = Field(
        default=None,
        max_length=255,
        description="Source/consumer label retained for backwards-compatible provenance",
    )
    personal_offer_id: str | None = Field(default=None, min_length=1, max_length=255)
    product_id: str | None = Field(default=None, min_length=1, max_length=255)
    price_context_id: str | None = Field(default=None, min_length=1, max_length=255)
    source: str | None = Field(default=None, min_length=1, max_length=255)
    source_snapshot_id: str | None = Field(default=None, min_length=1, max_length=255)
    observed_at: datetime | None = None
    currency: Literal["SEK"] = "SEK"
    source_confidence: str | None = Field(default=None, min_length=1, max_length=64)
    semantic_confidence: str | None = Field(default=None, min_length=1, max_length=64)
    quantity_confidence: str | None = Field(default=None, min_length=1, max_length=64)
    valid_from: date | None = None
    valid_to: date | None = None
    campaign_evidence: CampaignEvidence | None = Field(default=None, exclude_if=lambda value: value is None)
    deposit: DepositContract | None = Field(default=None, exclude_if=lambda value: value is None)

    @field_validator("price", mode="before")
    @classmethod
    def normalize_price_decimal_noise(cls, value: Any) -> Any:
        return _normalize_binary_decimal_noise(value, decimal_places=6)

    @field_validator("percent_discount", mode="before")
    @classmethod
    def normalize_percent_decimal_noise(cls, value: Any) -> Any:
        return _normalize_binary_decimal_noise(value, decimal_places=4)

    @model_validator(mode="before")
    @classmethod
    def normalize_membership_identity(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        explicit = data.get("membership_program")
        legacy = data.get("member_program")
        if explicit is None and legacy:
            try:
                data["membership_program"] = MembershipProgram.from_value(str(legacy))
            except ValueError:
                # Historical/diagnostic rows may only contain a free-text club
                # label. Preserve it as evidence, but never make it eligible in
                # a UserPricingContext without a stable program identity.
                pass
        elif explicit is not None:
            program = MembershipProgram.from_value(explicit)
            data["membership_program"] = program
            if not legacy:
                data["member_program"] = program.consumer_label
        return data

    @model_validator(mode="after")
    def validate_terms(self) -> PriceContract:
        if self.mechanism is PromotionMechanism.MULTIBUY:
            if self.required_packages < 2 or self.price is None:
                raise ValueError("multibuy requires at least two packages and a bundle price")
            if self.percent_discount is not None:
                raise ValueError("multibuy cannot also carry a percent discount")
        elif self.required_packages != 1:
            raise ValueError("only multibuy may require multiple packages")
        if self.mechanism is PromotionMechanism.PERCENT_DISCOUNT:
            if self.percent_discount is None and self.price is None:
                raise ValueError("percent discount requires a percentage or explicit price")
        elif self.percent_discount is not None:
            raise ValueError("percent_discount belongs to the percent-discount mechanism")
        if self.mechanism is PromotionMechanism.SALE_PRICE and self.price is None:
            raise ValueError("sale price requires an explicit price")
        if self.mechanism is PromotionMechanism.REGULAR:
            if self.price is None:
                raise ValueError("regular price requires an explicit price")
            if self.eligibility is not PromotionEligibility.PUBLIC:
                raise ValueError("regular price must be public")
            if self.max_quantity is not None:
                raise ValueError("regular price cannot have a promotion cap")
        if (
            self.eligibility is PromotionEligibility.USER_SPECIFIC
            and self.personal_offer_id is None
        ):
            raise ValueError("user-specific price requires personal_offer_id")
        if (
            self.eligibility is not PromotionEligibility.USER_SPECIFIC
            and self.personal_offer_id is not None
        ):
            raise ValueError("personal_offer_id belongs to user-specific eligibility")
        if self.observed_at is not None:
            if self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None:
                raise ValueError("observed_at must be timezone-aware")
            object.__setattr__(self, "observed_at", self.observed_at.astimezone(UTC))
        if self.valid_from and self.valid_to and self.valid_from > self.valid_to:
            raise ValueError("valid_from must not be after valid_to")
        return self

    @property
    def price_contract_id(self) -> str:
        return self.reference

    def is_active(self, on_date: date) -> bool:
        if self.campaign_evidence is not None:
            return self.campaign_evidence.applies(on_date, self.valid_from, self.valid_to)
        return not (
            (self.valid_from is not None and on_date < self.valid_from)
            or (self.valid_to is not None and on_date > self.valid_to)
        )

    def resolved_price(self, regular_unit_price: Decimal | None) -> Decimal | None:
        if self.price is not None:
            return self.price
        if (
            self.mechanism is PromotionMechanism.PERCENT_DISCOUNT
            and self.percent_discount is not None
        ):
            return regular_unit_price * (Decimal(100) - self.percent_discount) / Decimal(100) if regular_unit_price is not None else None
        return None


# ``CheckoutPromotion`` is the established public name. Keep it as an alias so
# source adapters and historical artifacts deserialize without a parallel
# promotion hierarchy while new code can use the more accurate PriceContract.
CheckoutPromotion = PriceContract


class UserPricingContext(BaseModel):
    """Request-level eligibility; it never changes shared PriceUniverse data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    memberships: frozenset[MembershipProgram] = frozenset()
    personalized_offer_ids: frozenset[str] = frozenset()
    activated_coupon_ids: frozenset[str] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def normalize_inputs(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        data = dict(value)
        supplied = data.get("memberships") or ()
        if isinstance(supplied, Mapping):
            supplied = [program for program, enabled in supplied.items() if bool(enabled)]
        data["memberships"] = frozenset(
            MembershipProgram.from_value(program) for program in supplied
        )
        for field_name in ("personalized_offer_ids", "activated_coupon_ids"):
            data[field_name] = frozenset(
                str(identifier).strip()
                for identifier in (data.get(field_name) or ())
                if str(identifier).strip()
            )
        return data

    @classmethod
    def from_chain_flags(cls, memberships: Mapping[str, bool] | None) -> UserPricingContext:
        return cls(memberships=memberships or {})

    def has_membership(self, program: MembershipProgram | str) -> bool:
        return MembershipProgram.from_value(program) in self.memberships

    def allows(self, contract: PriceContract) -> bool:
        if contract.eligibility is PromotionEligibility.PUBLIC:
            return True
        if contract.eligibility is PromotionEligibility.MEMBER:
            return (
                contract.membership_program is not None
                and contract.membership_program in self.memberships
            )
        if contract.eligibility is PromotionEligibility.USER_SPECIFIC:
            offer_id = contract.personal_offer_id
            return offer_id is not None and offer_id in (
                self.personalized_offer_ids | self.activated_coupon_ids
            )
        return False

    @property
    def cache_identity(self) -> str:
        payload = {
            "memberships": sorted(program.value for program in self.memberships),
            "personalized_offer_ids": sorted(self.personalized_offer_ids),
            "activated_coupon_ids": sorted(self.activated_coupon_ids),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return f"pricing-context:{hashlib.sha256(encoded).hexdigest()}"


class ComparableCheckoutPrice(BaseModel):
    """Comparison-ready checkout facts without erasing promotion conditions."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    basis: ComparablePriceBasis
    eligibility: PromotionEligibility
    mechanism: PromotionMechanism
    package_count: int = Field(ge=1)
    checkout_total: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    displayed_unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    condition_required_packages: int = Field(default=1, ge=1)
    condition_total_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=2,
    )
    member_program: str | None = Field(default=None, max_length=255)
    membership_program: MembershipProgram | None = None
    personal_offer_id: str | None = Field(default=None, min_length=1, max_length=255)
    comparison_unit: str | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_basis(self) -> ComparableCheckoutPrice:
        if (self.basis is ComparablePriceBasis.UNIT_RATE) != (
            self.comparison_unit is not None
        ):
            raise ValueError("unit-rate comparison basis and comparison_unit must be paired")
        return self

    @computed_field
    @property
    def condition_is_required(self) -> bool:
        return (
            self.eligibility is not PromotionEligibility.PUBLIC
            or self.mechanism is PromotionMechanism.MULTIBUY
        )

    @computed_field
    @property
    def comparability_key(self) -> str:
        """Stable semantic key; amounts are compared only when this agrees."""

        member = (
            self.membership_program.value
            if self.membership_program is not None
            else (self.member_program or "").strip().casefold()
        )
        return "|".join(
            (
                self.basis.value,
                self.eligibility.value,
                self.mechanism.value,
                str(self.package_count),
                str(self.condition_required_packages),
                (self.comparison_unit or "").strip().casefold(),
                member,
                self.personal_offer_id or "",
            )
        )


class EffectivePriceResolution(BaseModel):
    """Authoritative fixed-package checkout plus comparison projection."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    package_count: int = Field(ge=1)
    regular_unit_price: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    eligible_base_unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    checkout_total: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    displayed_unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    applied_promotion: CheckoutPromotion | None = None
    applied_groups_or_packages: int = Field(default=0, ge=0)
    condition_remainder_packages: int = Field(default=0, ge=0)
    comparable: ComparableCheckoutPrice
    ignored_promotion_references: tuple[str, ...] = ()


class FixedPackagePriceFacts(BaseModel):
    """All independently observed price channels for one fixed package.

    ``public_current_unit_price`` and ``member_unit_price`` are kept separate
    from regular price.  ``promotions`` may contain several simultaneous rows,
    for example a public 3-for-39 offer and a member package price of 10.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    regular_unit_price: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    public_current_unit_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    member_unit_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    promotions: tuple[CheckoutPromotion, ...] = ()


class UnitRatePriceFacts(BaseModel):
    """Independently observed price channels for a verified rate such as SEK/kg."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    comparison_unit: str = Field(min_length=1, max_length=32)
    regular_unit_rate: Decimal = Field(gt=0, max_digits=18, decimal_places=6)
    public_current_unit_rate: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    member_unit_rate: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=18,
        decimal_places=6,
    )
    promotions: tuple[CheckoutPromotion, ...] = ()


class EffectiveUnitRateResolution(BaseModel):
    """Resolved comparable rate; it is not a fabricated package checkout."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False, extra="forbid")

    comparison_unit: str = Field(min_length=1, max_length=32)
    regular_unit_rate: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    effective_unit_rate: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    applied_promotion: CheckoutPromotion | None = None
    comparable: ComparableCheckoutPrice
    ignored_promotion_references: tuple[str, ...] = ()


__all__ = [
    "CheckoutPromotion",
    "ComparableCheckoutPrice",
    "ComparablePriceBasis",
    "EffectivePriceResolution",
    "EffectiveUnitRateResolution",
    "FixedPackagePriceFacts",
    "MembershipProgram",
    "PriceContract",
    "PromotionEligibility",
    "PromotionMechanism",
    "UnitRatePriceFacts",
    "UserPricingContext",
]
