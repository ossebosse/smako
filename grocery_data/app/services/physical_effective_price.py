from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from grocery_data.app.domain.enums import PromotionType
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
    EffectivePriceResolution,
    EffectiveUnitRateResolution,
    FixedPackagePriceFacts,
    PromotionEligibility,
    PromotionMechanism,
    UnitRatePriceFacts,
)
from grocery_data.app.services.fixed_checkout_price import money, resolve_fixed_package_checkout

_PUBLIC_CURRENT_REFERENCE = "price-field:public-current"
_MEMBER_PRICE_REFERENCE = "price-field:member"


def _normalized_comparison_unit(value: str) -> str:
    normalized = value.strip().casefold().replace(" ", "")
    return {
        "kr/kg": "kg",
        "sek/kg": "kg",
        "kronor/kg": "kg",
        "kr/l": "l",
        "sek/l": "l",
        "liter": "l",
        "litre": "l",
        "lit": "l",
    }.get(normalized, normalized)


def _price_field_promotions(facts: FixedPackagePriceFacts) -> tuple[CheckoutPromotion, ...]:
    promotions = list(facts.promotions)
    if (
        facts.public_current_unit_price is not None
        and facts.public_current_unit_price < facts.regular_unit_price
    ):
        promotions.append(
            CheckoutPromotion(
                reference=_PUBLIC_CURRENT_REFERENCE,
                eligibility=PromotionEligibility.PUBLIC,
                mechanism=PromotionMechanism.SALE_PRICE,
                description="Public current price",
                price=facts.public_current_unit_price,
            )
        )
    if facts.member_unit_price is not None and facts.member_unit_price < facts.regular_unit_price:
        promotions.append(
            CheckoutPromotion(
                reference=_MEMBER_PRICE_REFERENCE,
                eligibility=PromotionEligibility.MEMBER,
                mechanism=PromotionMechanism.SALE_PRICE,
                description="Member price",
                price=facts.member_unit_price,
            )
        )
    return tuple(promotions)


def _deduplicate(promotions: tuple[CheckoutPromotion, ...]) -> tuple[CheckoutPromotion, ...]:
    by_terms: dict[tuple[object, ...], CheckoutPromotion] = {}
    for promotion in promotions:
        key = (
            promotion.eligibility,
            promotion.mechanism,
            money(promotion.price) if promotion.price is not None else None,
            promotion.percent_discount,
            promotion.required_packages,
            promotion.max_quantity,
            promotion.member_program,
            promotion.valid_from,
            promotion.valid_to,
        )
        current = by_terms.get(key)
        if current is None or promotion.reference < current.reference:
            by_terms[key] = promotion
    return tuple(sorted(by_terms.values(), key=lambda row: row.reference))


class PhysicalEffectivePriceResolver:
    """Membership-aware adapter around the shared authoritative checkout math."""

    def resolve(
        self,
        facts: FixedPackagePriceFacts,
        *,
        package_count: int,
        member_eligible: bool,
        on_date: date | None = None,
    ) -> EffectivePriceResolution:
        target_date = on_date or datetime.now(tz=UTC).date()
        all_promotions = _deduplicate(_price_field_promotions(facts))
        eligible: list[CheckoutPromotion] = []
        ignored: list[str] = []
        for promotion in all_promotions:
            can_use = (
                promotion.eligibility is PromotionEligibility.PUBLIC
                or (
                    promotion.eligibility is PromotionEligibility.MEMBER
                    and member_eligible
                )
            )
            if (
                not can_use
                or not promotion.is_active(target_date)
                or promotion.mechanism is PromotionMechanism.OTHER
            ):
                ignored.append(promotion.reference)
                continue
            eligible.append(promotion)

        regular = money(facts.regular_unit_price)
        single_prices = [regular]
        for promotion in eligible:
            if promotion.mechanism not in {
                PromotionMechanism.SALE_PRICE,
                PromotionMechanism.PERCENT_DISCOUNT,
            }:
                continue
            resolved = promotion.resolved_price(regular)
            if resolved is not None:
                single_prices.append(money(resolved))
        base = min(single_prices)
        return resolve_fixed_package_checkout(
            package_count=package_count,
            base_unit_price=base,
            regular_unit_price=regular,
            promotions=tuple(eligible),
            on_date=target_date,
            ignored_promotion_references=tuple(ignored),
        )

    def resolve_unit_rate(
        self,
        facts: UnitRatePriceFacts,
        *,
        member_eligible: bool,
        on_date: date | None = None,
    ) -> EffectiveUnitRateResolution:
        """Resolve a comparable rate without pretending it is a package checkout.

        The filtering deliberately mirrors the fixed-package resolver's eligibility
        and validity gates.  Multibuy and capped promotions fail closed for a rate:
        without a purchased package quantity there is no safe way to translate
        those terms to a shelf ``SEK/kg`` observation.
        """

        target_date = on_date or datetime.now(tz=UTC).date()
        regular = money(facts.regular_unit_rate)
        promotions = list(facts.promotions)
        if (
            facts.public_current_unit_rate is not None
            and facts.public_current_unit_rate < facts.regular_unit_rate
        ):
            promotions.append(
                CheckoutPromotion(
                    reference=_PUBLIC_CURRENT_REFERENCE,
                    eligibility=PromotionEligibility.PUBLIC,
                    mechanism=PromotionMechanism.SALE_PRICE,
                    description="Public current unit rate",
                    price=facts.public_current_unit_rate,
                )
            )
        if (
            facts.member_unit_rate is not None
            and facts.member_unit_rate < facts.regular_unit_rate
        ):
            promotions.append(
                CheckoutPromotion(
                    reference=_MEMBER_PRICE_REFERENCE,
                    eligibility=PromotionEligibility.MEMBER,
                    mechanism=PromotionMechanism.SALE_PRICE,
                    description="Member unit rate",
                    price=facts.member_unit_rate,
                )
            )

        applicable: list[tuple[Decimal, CheckoutPromotion]] = []
        ignored: list[str] = []
        for promotion in _deduplicate(tuple(promotions)):
            can_use = promotion.eligibility is PromotionEligibility.PUBLIC or (
                promotion.eligibility is PromotionEligibility.MEMBER and member_eligible
            )
            cannot_apply_to_rate = (
                promotion.mechanism
                in {PromotionMechanism.MULTIBUY, PromotionMechanism.OTHER}
                or promotion.max_quantity is not None
            )
            if (
                not can_use
                or not promotion.is_active(target_date)
                or cannot_apply_to_rate
            ):
                ignored.append(promotion.reference)
                continue
            resolved = promotion.resolved_price(regular)
            if resolved is None:
                ignored.append(promotion.reference)
                continue
            applicable.append((money(resolved), promotion))

        effective = regular
        applied: CheckoutPromotion | None = None
        for candidate_rate, promotion in sorted(
            applicable,
            key=lambda row: (
                row[0],
                0 if row[1].eligibility is PromotionEligibility.PUBLIC else 1,
                row[1].reference,
            ),
        ):
            if candidate_rate < effective:
                effective = candidate_rate
                applied = promotion

        eligibility = (
            applied.eligibility if applied is not None else PromotionEligibility.PUBLIC
        )
        mechanism = (
            applied.mechanism if applied is not None else PromotionMechanism.REGULAR
        )
        unit = _normalized_comparison_unit(facts.comparison_unit)
        comparable = ComparableCheckoutPrice(
            basis=ComparablePriceBasis.UNIT_RATE,
            eligibility=eligibility,
            mechanism=mechanism,
            package_count=1,
            checkout_total=effective,
            displayed_unit_price=effective,
            condition_required_packages=1,
            condition_total_price=(effective if applied is not None else None),
            member_program=(applied.member_program if applied is not None else None),
            comparison_unit=unit,
        )
        return EffectiveUnitRateResolution(
            comparison_unit=unit,
            regular_unit_rate=regular,
            effective_unit_rate=effective,
            applied_promotion=applied,
            comparable=comparable,
            ignored_promotion_references=tuple(sorted(ignored)),
        )


def _mechanism(promotion_type: PromotionType | None) -> PromotionMechanism:
    return {
        PromotionType.SALE_PRICE: PromotionMechanism.SALE_PRICE,
        PromotionType.MEMBER_PRICE: PromotionMechanism.SALE_PRICE,
        PromotionType.MULTIBUY: PromotionMechanism.MULTIBUY,
        PromotionType.PERCENT_DISCOUNT: PromotionMechanism.PERCENT_DISCOUNT,
        PromotionType.OTHER: PromotionMechanism.OTHER,
        None: PromotionMechanism.REGULAR,
    }[promotion_type]


def digital_candidate_price_facts(
    candidate: DigitalPriceCandidate,
    *,
    promotions: tuple[CheckoutPromotion, ...] = (),
) -> FixedPackagePriceFacts:
    """Project a comparison candidate without collapsing supplied source offers.

    Callers with the source promotion rows should pass all of them through
    ``promotions``.  The legacy candidate fields are used only to preserve the
    current single-row contract; they must not replace richer simultaneous
    offers such as public multibuy plus member unit price.
    """

    regular = candidate.regular_price or candidate.current_price
    rows = list(promotions)
    has_multibuy = (
        candidate.multibuy_quantity is not None
        and candidate.multibuy_total_price is not None
    )
    if has_multibuy:
        rows.append(
            CheckoutPromotion(
                reference="digital-candidate:multibuy",
                eligibility=(
                    PromotionEligibility.MEMBER
                    if candidate.member_only
                    else PromotionEligibility.PUBLIC
                ),
                mechanism=PromotionMechanism.MULTIBUY,
                description="Digital multibuy",
                price=candidate.multibuy_total_price,
                required_packages=candidate.multibuy_quantity or 1,
            )
        )
    elif candidate.promotion_type is not None:
        mechanism = _mechanism(candidate.promotion_type)
        price = (
            candidate.member_price
            if candidate.member_only and candidate.member_price is not None
            else candidate.current_price
        )
        rows.append(
            CheckoutPromotion(
                reference="digital-candidate:promotion",
                eligibility=(
                    PromotionEligibility.MEMBER
                    if candidate.member_only
                    else PromotionEligibility.PUBLIC
                ),
                mechanism=mechanism,
                description="Digital promotion",
                price=price,
            )
        )
    return FixedPackagePriceFacts(
        regular_unit_price=regular,
        public_current_unit_price=(
            candidate.current_price if not candidate.member_only and not has_multibuy else None
        ),
        member_unit_price=(candidate.member_price if not has_multibuy else None),
        promotions=tuple(rows),
    )


def physical_observation_price_facts(
    observation: PhysicalPriceObservation,
    *,
    promotions: tuple[CheckoutPromotion, ...] = (),
) -> FixedPackagePriceFacts:
    """Project legacy/manual evidence into the orthogonal V3 price contract."""

    regular = observation.regular_shelf_price or observation.shelf_price
    rows = list(promotions)
    has_multibuy = (
        observation.multibuy_quantity is not None
        and observation.multibuy_total_price is not None
    )
    if has_multibuy:
        rows.append(
            CheckoutPromotion(
                reference="physical-observation:multibuy",
                eligibility=(
                    PromotionEligibility.MEMBER
                    if observation.member_only
                    else PromotionEligibility.PUBLIC
                ),
                mechanism=PromotionMechanism.MULTIBUY,
                description=observation.promotion_text or "Physical multibuy",
                price=observation.multibuy_total_price,
                required_packages=observation.multibuy_quantity or 1,
            )
        )
    elif observation.promotion_type is not None:
        rows.append(
            CheckoutPromotion(
                reference="physical-observation:promotion",
                eligibility=(
                    PromotionEligibility.MEMBER
                    if observation.member_only
                    else PromotionEligibility.PUBLIC
                ),
                mechanism=_mechanism(observation.promotion_type),
                description=observation.promotion_text or "Physical promotion",
                price=observation.shelf_price,
            )
        )
    return FixedPackagePriceFacts(
        regular_unit_price=regular,
        public_current_unit_price=(
            observation.shelf_price
            if observation.promotion_type is not None and not observation.member_only
            else None
        ),
        member_unit_price=(observation.shelf_price if observation.member_only else None),
        promotions=tuple(rows),
    )


def physical_weight_price_facts(
    observation: PhysicalPriceObservation,
    *,
    promotions: tuple[CheckoutPromotion, ...] = (),
) -> UnitRatePriceFacts:
    """Project an explicit weight capture to a rate-only comparison contract."""

    if observation.price_semantics is not PhysicalPriceSemantics.WEIGHT:
        raise ValueError("physical observation is not an explicit weight-price capture")
    if observation.comparison_unit is None:
        raise ValueError("weight-price capture requires a comparison unit")

    current_rate = observation.comparison_price or observation.shelf_price
    regular_rate = observation.regular_shelf_price or current_rate
    public_current: Decimal | None = None
    member_current: Decimal | None = None
    if observation.weight_price_type is WeightPriceType.SALE:
        public_current = current_rate
    elif observation.weight_price_type is WeightPriceType.MEMBER:
        member_current = current_rate

    return UnitRatePriceFacts(
        comparison_unit=_normalized_comparison_unit(observation.comparison_unit),
        regular_unit_rate=regular_rate,
        public_current_unit_rate=public_current,
        member_unit_rate=member_current,
        promotions=promotions,
    )


__all__ = [
    "PhysicalEffectivePriceResolver",
    "digital_candidate_price_facts",
    "physical_observation_price_facts",
    "physical_weight_price_facts",
]
