from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import PromotionType, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    WeightPriceType,
)
from grocery_data.app.domain.promotion_pricing import (
    CheckoutPromotion,
    ComparableCheckoutPrice,
    ComparablePriceBasis,
    FixedPackagePriceFacts,
    PromotionEligibility,
    PromotionMechanism,
    UnitRatePriceFacts,
)
from grocery_data.app.services.physical_effective_price import (
    PhysicalEffectivePriceResolver,
    digital_candidate_price_facts,
)
from grocery_data.app.storage.models import PriceObservationModel, PromotionModel

_CENT = Decimal("0.01")


class SemanticPriceChangeReason(StrEnum):
    ALL_SOURCE_PROMOTIONS_LOADED = "all_source_promotions_loaded"
    MULTIPLE_SIMULTANEOUS_OFFERS = "multiple_simultaneous_offers"
    INVALID_SOURCE_PROMOTION_IGNORED = "invalid_source_promotion_ignored"
    CANDIDATE_ONLY_FALLBACK = "candidate_only_fallback"
    SELECTED_REGULAR_CHANNEL = "selected_regular_channel"
    SELECTED_PUBLIC_SALE = "selected_public_sale"
    SELECTED_MEMBER_PRICE = "selected_member_price"
    SELECTED_MULTIBUY_CONTRACT = "selected_multibuy_contract"
    SELECTED_UNIT_RATE = "selected_unit_rate"
    SINGULAR_CANDIDATE_PROJECTION_CHANGED = "singular_candidate_projection_changed"
    NO_MATCHING_DIGITAL_SEMANTICS = "no_matching_digital_semantics"


@dataclass(frozen=True, slots=True)
class LockedSourcePriceEvidence:
    candidate: DigitalPriceCandidate
    fixed_facts: FixedPackagePriceFacts | None
    unit_rate_facts: UnitRatePriceFacts | None
    source_promotion_rows: int
    normalized_promotions: int
    invalid_promotion_rows: int
    candidate_only_fallback: bool


@dataclass(frozen=True, slots=True)
class SemanticPriceDiagnostic:
    adjusted_candidate: DigitalPriceCandidate
    physical: ComparableCheckoutPrice | None
    digital: ComparableCheckoutPrice | None
    source_promotion_rows: int
    normalized_promotions: int
    invalid_promotion_rows: int
    change_reasons: tuple[SemanticPriceChangeReason, ...]
    mismatch_dimensions: tuple[str, ...]

    @property
    def comparable(self) -> bool:
        return self.physical is not None and self.digital is not None and not (
            self.mismatch_dimensions
        )

    @property
    def exact_amount_match(self) -> bool:
        return bool(
            self.comparable
            and self.physical is not None
            and self.digital is not None
            and self.physical.checkout_total == self.digital.checkout_total
        )

    @property
    def signed_difference(self) -> Decimal | None:
        if not self.comparable or self.physical is None or self.digital is None:
            return None
        return _money(self.physical.checkout_total - self.digital.checkout_total)

    @property
    def absolute_difference(self) -> Decimal | None:
        signed = self.signed_difference
        return abs(signed) if signed is not None else None

    @property
    def semantic_result(self) -> str:
        difference = self.absolute_difference
        if difference is None:
            return "not_comparable"
        if difference == 0:
            return "exact_match"
        if difference <= Decimal("0.50"):
            return "within_050"
        if difference <= Decimal("1.00"):
            return "within_100"
        return "major_difference"


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _promotion_axes(row: PromotionModel) -> tuple[PromotionEligibility, PromotionMechanism]:
    promotion_type = (
        PromotionType(row.type) if row.type in PromotionType._value2member_map_ else PromotionType.OTHER
    )
    eligibility = (
        PromotionEligibility.MEMBER
        if row.member_only or promotion_type is PromotionType.MEMBER_PRICE
        else PromotionEligibility.PUBLIC
    )
    if promotion_type is PromotionType.MULTIBUY or (
        promotion_type is PromotionType.MEMBER_PRICE and (row.quantity or 1) > 1
    ):
        mechanism = PromotionMechanism.MULTIBUY
    else:
        mechanism = {
            PromotionType.SALE_PRICE: PromotionMechanism.SALE_PRICE,
            PromotionType.MEMBER_PRICE: PromotionMechanism.SALE_PRICE,
            PromotionType.PERCENT_DISCOUNT: PromotionMechanism.PERCENT_DISCOUNT,
            PromotionType.OTHER: PromotionMechanism.OTHER,
        }.get(promotion_type, PromotionMechanism.OTHER)
    return eligibility, mechanism


def _checkout_promotion(row: PromotionModel) -> CheckoutPromotion:
    eligibility, mechanism = _promotion_axes(row)
    return CheckoutPromotion(
        reference=f"promotion:{row.id}",
        eligibility=eligibility,
        mechanism=mechanism,
        description=(row.description or row.type or "Source promotion").strip(),
        price=row.price,
        required_packages=((row.quantity or 1) if mechanism is PromotionMechanism.MULTIBUY else 1),
        max_quantity=row.max_quantity,
        valid_from=row.valid_from,
        valid_to=row.valid_to,
    )


class PersistedPhysicalSourcePriceEvidenceReader:
    """Read every price/promotion row for one exact immutable product snapshot."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def for_candidate(self, candidate: DigitalPriceCandidate) -> LockedSourcePriceEvidence:
        price_rows = tuple(
            self.session.scalars(
                select(PriceObservationModel).where(
                    PriceObservationModel.catalog_snapshot_id == candidate.source_snapshot_id,
                    PriceObservationModel.product_id == candidate.product_id,
                )
            )
        )
        if len(price_rows) > 1:
            raise ValueError("locked snapshot/product has conflicting price observations")
        if not price_rows:
            if (
                candidate.sale_model
                in {SaleModel.SOLD_BY_WEIGHT, SaleModel.VARIABLE_WEIGHT_PACKAGE}
                and candidate.comparison_price is not None
                and candidate.comparison_unit is not None
            ):
                return LockedSourcePriceEvidence(
                    candidate=candidate,
                    fixed_facts=None,
                    unit_rate_facts=UnitRatePriceFacts(
                        comparison_unit=candidate.comparison_unit,
                        regular_unit_rate=(
                            candidate.regular_price or candidate.comparison_price
                        ),
                        public_current_unit_rate=(
                            candidate.comparison_price
                            if not candidate.member_only
                            else None
                        ),
                        member_unit_rate=(
                            candidate.comparison_price if candidate.member_only else None
                        ),
                    ),
                    source_promotion_rows=0,
                    normalized_promotions=0,
                    invalid_promotion_rows=0,
                    candidate_only_fallback=True,
                )
            facts = digital_candidate_price_facts(candidate)
            return LockedSourcePriceEvidence(
                candidate=candidate,
                fixed_facts=facts,
                unit_rate_facts=None,
                source_promotion_rows=0,
                normalized_promotions=len(facts.promotions),
                invalid_promotion_rows=0,
                candidate_only_fallback=True,
            )

        price = price_rows[0]
        promotion_rows = tuple(
            self.session.scalars(
                select(PromotionModel)
                .where(
                    PromotionModel.catalog_snapshot_id == candidate.source_snapshot_id,
                    PromotionModel.store_id == price.store_id,
                    or_(
                        PromotionModel.product_id == candidate.product_id,
                        PromotionModel.source_product_id == price.source_product_id,
                    ),
                )
                .order_by(PromotionModel.id)
            )
        )
        promotions: list[CheckoutPromotion] = []
        invalid = 0
        for row in promotion_rows:
            try:
                promotions.append(_checkout_promotion(row))
            except (ValidationError, ValueError):
                invalid += 1

        is_unit_rate = candidate.sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }
        if is_unit_rate:
            regular_rate = (
                price.comparison_price
                or candidate.comparison_price
                or price.regular_price
                or candidate.regular_price
                or candidate.current_price
            )
            unit = price.comparison_unit or candidate.comparison_unit
            if unit is not None:
                return LockedSourcePriceEvidence(
                    candidate=candidate,
                    fixed_facts=None,
                    unit_rate_facts=UnitRatePriceFacts(
                        comparison_unit=unit,
                        regular_unit_rate=regular_rate,
                        public_current_unit_rate=price.sale_price,
                        member_unit_rate=price.member_price,
                        promotions=tuple(promotions),
                    ),
                    source_promotion_rows=len(promotion_rows),
                    normalized_promotions=len(promotions),
                    invalid_promotion_rows=invalid,
                    candidate_only_fallback=False,
                )

        regular = (
            price.regular_price
            or candidate.regular_price
            or price.sale_price
            or candidate.current_price
        )
        return LockedSourcePriceEvidence(
            candidate=candidate,
            fixed_facts=FixedPackagePriceFacts(
                regular_unit_price=regular,
                public_current_unit_price=price.sale_price,
                member_unit_price=price.member_price,
                promotions=tuple(promotions),
            ),
            unit_rate_facts=None,
            source_promotion_rows=len(promotion_rows),
            normalized_promotions=len(promotions),
            invalid_promotion_rows=invalid,
            candidate_only_fallback=False,
        )


def _physical_contract(
    observation: PhysicalPriceObservation,
) -> ComparableCheckoutPrice | None:
    semantics = observation.price_semantics
    if semantics in {None, PhysicalPriceSemantics.UNKNOWN}:
        return None
    member = bool(observation.member_only)
    eligibility = PromotionEligibility.MEMBER if member else PromotionEligibility.PUBLIC
    if semantics is PhysicalPriceSemantics.WEIGHT:
        mechanism = {
            WeightPriceType.REGULAR: PromotionMechanism.REGULAR,
            WeightPriceType.SALE: PromotionMechanism.SALE_PRICE,
            WeightPriceType.MEMBER: PromotionMechanism.SALE_PRICE,
            WeightPriceType.UNKNOWN: PromotionMechanism.OTHER,
            None: PromotionMechanism.OTHER,
        }[observation.weight_price_type]
        rate = _money(observation.comparison_price or observation.shelf_price)
        unit = (observation.comparison_unit or "").strip().casefold().replace("sek/", "")
        unit = unit.replace("kr/", "")
        return ComparableCheckoutPrice(
            basis=ComparablePriceBasis.UNIT_RATE,
            eligibility=eligibility,
            mechanism=mechanism,
            package_count=1,
            checkout_total=rate,
            displayed_unit_price=rate,
            condition_required_packages=1,
            condition_total_price=(rate if mechanism is not PromotionMechanism.REGULAR else None),
            comparison_unit=unit,
        )
    if semantics is PhysicalPriceSemantics.MULTIBUY:
        if observation.multibuy_quantity is None or observation.multibuy_total_price is None:
            return None
        total = _money(observation.multibuy_total_price)
        return ComparableCheckoutPrice(
            basis=ComparablePriceBasis.CHECKOUT_TOTAL,
            eligibility=eligibility,
            mechanism=PromotionMechanism.MULTIBUY,
            package_count=observation.multibuy_quantity,
            checkout_total=total,
            displayed_unit_price=_money(total / observation.multibuy_quantity),
            condition_required_packages=observation.multibuy_quantity,
            condition_total_price=total,
        )
    mechanism = {
        PhysicalPriceSemantics.REGULAR: PromotionMechanism.REGULAR,
        PhysicalPriceSemantics.SALE: (
            PromotionMechanism.PERCENT_DISCOUNT
            if observation.promotion_type is PromotionType.PERCENT_DISCOUNT
            else PromotionMechanism.SALE_PRICE
        ),
        PhysicalPriceSemantics.MEMBER: PromotionMechanism.SALE_PRICE,
    }.get(semantics, PromotionMechanism.OTHER)
    value = _money(observation.shelf_price)
    return ComparableCheckoutPrice(
        basis=ComparablePriceBasis.PACKAGE_PRICE,
        eligibility=eligibility,
        mechanism=mechanism,
        package_count=1,
        checkout_total=value,
        displayed_unit_price=value,
        condition_required_packages=1,
        condition_total_price=(value if mechanism is not PromotionMechanism.REGULAR else None),
    )


def _matching_promotions(
    promotions: tuple[CheckoutPromotion, ...],
    physical: ComparableCheckoutPrice,
) -> tuple[CheckoutPromotion, ...]:
    return tuple(
        row
        for row in promotions
        if row.eligibility is physical.eligibility and row.mechanism is physical.mechanism
    )


def _mismatch_dimensions(
    physical: ComparableCheckoutPrice | None,
    digital: ComparableCheckoutPrice | None,
) -> tuple[str, ...]:
    if physical is None:
        return ("physical_semantics_unknown",)
    if digital is None:
        return ("digital_semantics_unavailable",)
    mismatches: list[str] = []
    if physical.basis is not digital.basis:
        mismatches.append("basis")
    if physical.eligibility is not digital.eligibility:
        mismatches.append("eligibility")
    if physical.mechanism is not digital.mechanism:
        mismatches.append("mechanism")
    if physical.package_count != digital.package_count:
        mismatches.append("package_count")
    if physical.condition_required_packages != digital.condition_required_packages:
        mismatches.append("condition_required_packages")
    if physical.comparison_unit != digital.comparison_unit:
        mismatches.append("comparison_unit")
    return tuple(mismatches)


def _explicit_fixed_contract(
    promotions: tuple[CheckoutPromotion, ...],
    *,
    regular_unit_price: Decimal,
    package_count: int,
    on_date: date,
) -> ComparableCheckoutPrice | None:
    """Preserve explicit source semantics when its amount equals the baseline.

    The basket resolver remains economically authoritative and therefore quite
    correctly does not *apply* a non-saving offer.  Physical validation has a
    different question: whether the shelf label and source advertise the same
    explicit contract.  This projection retains that evidence without changing
    checkout optimization behavior.
    """

    regular = _money(regular_unit_price)
    candidates: list[tuple[Decimal, CheckoutPromotion, int]] = []
    for promotion in promotions:
        if not promotion.is_active(on_date):
            continue
        resolved = promotion.resolved_price(regular)
        if resolved is None:
            continue
        if promotion.mechanism is PromotionMechanism.MULTIBUY:
            if package_count < promotion.required_packages:
                continue
            available_groups = package_count // promotion.required_packages
            groups = min(available_groups, promotion.max_quantity or available_groups)
            remainder = package_count - groups * promotion.required_packages
            total = _money(groups * resolved + remainder * regular)
        else:
            discounted = min(package_count, promotion.max_quantity or package_count)
            remainder = package_count - discounted
            total = _money(discounted * resolved + remainder * regular)
        candidates.append((total, promotion, remainder))
    if not candidates:
        return None
    total, promotion, _remainder = min(
        candidates,
        key=lambda row: (row[0], row[1].reference),
    )
    displayed = _money(total / package_count)
    return ComparableCheckoutPrice(
        basis=(
            ComparablePriceBasis.CHECKOUT_TOTAL
            if package_count > 1
            or promotion.mechanism is PromotionMechanism.MULTIBUY
            else ComparablePriceBasis.PACKAGE_PRICE
        ),
        eligibility=promotion.eligibility,
        mechanism=promotion.mechanism,
        package_count=package_count,
        checkout_total=total,
        displayed_unit_price=displayed,
        condition_required_packages=promotion.required_packages,
        condition_total_price=(
            _money(promotion.price) if promotion.price is not None else displayed
        ),
        member_program=promotion.member_program,
    )


def _explicit_unit_rate_contract(
    promotions: tuple[CheckoutPromotion, ...],
    *,
    regular_unit_rate: Decimal,
    comparison_unit: str,
    on_date: date,
) -> ComparableCheckoutPrice | None:
    candidates: list[tuple[Decimal, CheckoutPromotion]] = []
    regular = _money(regular_unit_rate)
    for promotion in promotions:
        if (
            not promotion.is_active(on_date)
            or promotion.mechanism is PromotionMechanism.MULTIBUY
            or promotion.max_quantity is not None
        ):
            continue
        resolved = promotion.resolved_price(regular)
        if resolved is not None:
            candidates.append((_money(resolved), promotion))
    if not candidates:
        return None
    rate, promotion = min(candidates, key=lambda row: (row[0], row[1].reference))
    unit = comparison_unit.strip().casefold().replace("sek/", "").replace("kr/", "")
    return ComparableCheckoutPrice(
        basis=ComparablePriceBasis.UNIT_RATE,
        eligibility=promotion.eligibility,
        mechanism=promotion.mechanism,
        package_count=1,
        checkout_total=rate,
        displayed_unit_price=rate,
        condition_required_packages=1,
        condition_total_price=rate,
        member_program=promotion.member_program,
        comparison_unit=unit,
    )


class PhysicalSourceSemanticPriceAdapter:
    """Resolve an exact source row to the physical capture's semantic channel."""

    def __init__(self, session: Session) -> None:
        self.reader = PersistedPhysicalSourcePriceEvidenceReader(session)
        self.resolver = PhysicalEffectivePriceResolver()

    def compare(
        self,
        observation: PhysicalPriceObservation,
        candidate: DigitalPriceCandidate,
    ) -> SemanticPriceDiagnostic:
        evidence = self.reader.for_candidate(candidate)
        physical = _physical_contract(observation)
        reasons: list[SemanticPriceChangeReason] = []
        if evidence.candidate_only_fallback:
            reasons.append(SemanticPriceChangeReason.CANDIDATE_ONLY_FALLBACK)
        else:
            reasons.append(SemanticPriceChangeReason.ALL_SOURCE_PROMOTIONS_LOADED)
        if evidence.source_promotion_rows > 1:
            reasons.append(SemanticPriceChangeReason.MULTIPLE_SIMULTANEOUS_OFFERS)
        if evidence.invalid_promotion_rows:
            reasons.append(SemanticPriceChangeReason.INVALID_SOURCE_PROMOTION_IGNORED)

        digital: ComparableCheckoutPrice | None = None
        adjusted = candidate
        target_date = candidate.observed_at.date()
        if physical is not None and evidence.unit_rate_facts is not None:
            facts = evidence.unit_rate_facts
            if physical.mechanism is PromotionMechanism.REGULAR:
                selected = facts.model_copy(
                    update={
                        "public_current_unit_rate": None,
                        "member_unit_rate": None,
                        "promotions": (),
                    }
                )
            else:
                selected = facts.model_copy(
                    update={
                        "public_current_unit_rate": (
                            facts.public_current_unit_rate
                            if physical.eligibility is PromotionEligibility.PUBLIC
                            and physical.mechanism is PromotionMechanism.SALE_PRICE
                            else None
                        ),
                        "member_unit_rate": (
                            facts.member_unit_rate
                            if physical.eligibility is PromotionEligibility.MEMBER
                            and physical.mechanism is PromotionMechanism.SALE_PRICE
                            else None
                        ),
                        "promotions": _matching_promotions(facts.promotions, physical),
                    }
                )
            resolved = self.resolver.resolve_unit_rate(
                selected,
                member_eligible=physical.eligibility is PromotionEligibility.MEMBER,
                on_date=target_date,
            )
            explicit_contract = (
                _explicit_unit_rate_contract(
                    selected.promotions,
                    regular_unit_rate=selected.regular_unit_rate,
                    comparison_unit=selected.comparison_unit,
                    on_date=target_date,
                )
                if physical.mechanism is not PromotionMechanism.REGULAR
                and resolved.applied_promotion is None
                else None
            )
            if (
                physical.mechanism is PromotionMechanism.REGULAR
                or resolved.applied_promotion is not None
                or explicit_contract is not None
            ):
                digital = explicit_contract or resolved.comparable
                reasons.append(SemanticPriceChangeReason.SELECTED_UNIT_RATE)
                adjusted = candidate.model_copy(
                    update={
                        "current_price": digital.displayed_unit_price,
                        "regular_price": resolved.regular_unit_rate,
                        "member_price": (
                            digital.displayed_unit_price
                            if physical.eligibility is PromotionEligibility.MEMBER
                            else None
                        ),
                        "comparison_price": digital.displayed_unit_price,
                        "comparison_unit": resolved.comparison_unit,
                        "promotion_type": _legacy_promotion_type(physical),
                        "member_only": physical.eligibility is PromotionEligibility.MEMBER,
                        "multibuy_quantity": None,
                        "multibuy_total_price": None,
                    }
                )
        elif physical is not None and evidence.fixed_facts is not None:
            facts = evidence.fixed_facts
            if physical.mechanism is PromotionMechanism.REGULAR:
                selected = facts.model_copy(
                    update={
                        "public_current_unit_price": None,
                        "member_unit_price": None,
                        "promotions": (),
                    }
                )
            else:
                selected = facts.model_copy(
                    update={
                        "public_current_unit_price": (
                            facts.public_current_unit_price
                            if physical.eligibility is PromotionEligibility.PUBLIC
                            and physical.mechanism is PromotionMechanism.SALE_PRICE
                            else None
                        ),
                        "member_unit_price": (
                            facts.member_unit_price
                            if physical.eligibility is PromotionEligibility.MEMBER
                            and physical.mechanism is PromotionMechanism.SALE_PRICE
                            else None
                        ),
                        "promotions": _matching_promotions(facts.promotions, physical),
                    }
                )
            resolved = self.resolver.resolve(
                selected,
                package_count=physical.package_count,
                member_eligible=physical.eligibility is PromotionEligibility.MEMBER,
                on_date=target_date,
            )
            explicit_contract = (
                _explicit_fixed_contract(
                    selected.promotions,
                    regular_unit_price=selected.regular_unit_price,
                    package_count=physical.package_count,
                    on_date=target_date,
                )
                if physical.mechanism is not PromotionMechanism.REGULAR
                and resolved.applied_promotion is None
                else None
            )
            if (
                physical.mechanism is PromotionMechanism.REGULAR
                or resolved.applied_promotion is not None
                or explicit_contract is not None
            ):
                digital = explicit_contract or resolved.comparable
                reasons.append(_selection_reason(physical))
                adjusted = candidate.model_copy(
                    update={
                        "current_price": digital.displayed_unit_price,
                        "regular_price": resolved.regular_unit_price,
                        "member_price": (
                            digital.displayed_unit_price
                            if physical.eligibility is PromotionEligibility.MEMBER
                            and physical.mechanism is not PromotionMechanism.MULTIBUY
                            else None
                        ),
                        "promotion_type": _legacy_promotion_type(physical),
                        "member_only": physical.eligibility is PromotionEligibility.MEMBER,
                        "multibuy_quantity": (
                            digital.condition_required_packages
                            if physical.mechanism is PromotionMechanism.MULTIBUY
                            else None
                        ),
                        "multibuy_total_price": (
                            digital.condition_total_price
                            if physical.mechanism is PromotionMechanism.MULTIBUY
                            else None
                        ),
                    }
                )

        if digital is None:
            reasons.append(SemanticPriceChangeReason.NO_MATCHING_DIGITAL_SEMANTICS)
        if adjusted != candidate:
            reasons.append(SemanticPriceChangeReason.SINGULAR_CANDIDATE_PROJECTION_CHANGED)
        mismatches = list(_mismatch_dimensions(physical, digital))
        if evidence.invalid_promotion_rows and physical is not None and (
            physical.mechanism is not PromotionMechanism.REGULAR
        ):
            mismatches.append("invalid_source_promotion_rows")
        return SemanticPriceDiagnostic(
            adjusted_candidate=adjusted,
            physical=physical,
            digital=digital,
            source_promotion_rows=evidence.source_promotion_rows,
            normalized_promotions=evidence.normalized_promotions,
            invalid_promotion_rows=evidence.invalid_promotion_rows,
            change_reasons=tuple(dict.fromkeys(reasons)),
            mismatch_dimensions=tuple(dict.fromkeys(mismatches)),
        )


def _selection_reason(physical: ComparableCheckoutPrice) -> SemanticPriceChangeReason:
    if physical.mechanism is PromotionMechanism.REGULAR:
        return SemanticPriceChangeReason.SELECTED_REGULAR_CHANNEL
    if physical.mechanism is PromotionMechanism.MULTIBUY:
        return SemanticPriceChangeReason.SELECTED_MULTIBUY_CONTRACT
    if physical.eligibility is PromotionEligibility.MEMBER:
        return SemanticPriceChangeReason.SELECTED_MEMBER_PRICE
    return SemanticPriceChangeReason.SELECTED_PUBLIC_SALE


def _legacy_promotion_type(physical: ComparableCheckoutPrice) -> PromotionType | None:
    if physical.mechanism is PromotionMechanism.REGULAR:
        return None
    if physical.mechanism is PromotionMechanism.MULTIBUY:
        return PromotionType.MULTIBUY
    if physical.mechanism is PromotionMechanism.PERCENT_DISCOUNT:
        return PromotionType.PERCENT_DISCOUNT
    if physical.eligibility is PromotionEligibility.MEMBER:
        return PromotionType.MEMBER_PRICE
    return PromotionType.SALE_PRICE


__all__ = [
    "LockedSourcePriceEvidence",
    "PersistedPhysicalSourcePriceEvidenceReader",
    "PhysicalSourceSemanticPriceAdapter",
    "SemanticPriceChangeReason",
    "SemanticPriceDiagnostic",
]
