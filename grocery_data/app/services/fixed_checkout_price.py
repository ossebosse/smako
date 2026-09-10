from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from grocery_data.app.domain.promotion_pricing import (
    CheckoutPromotion,
    ComparableCheckoutPrice,
    ComparablePriceBasis,
    EffectivePriceResolution,
    PriceContract,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)

_CENT = Decimal("0.01")
_STOCKHOLM = ZoneInfo("Europe/Stockholm")


def _eligibility_priority(value: PromotionEligibility) -> int:
    """Prefer the least restrictive evidence when checkout totals are tied."""

    return {
        PromotionEligibility.PUBLIC: 2,
        PromotionEligibility.MEMBER: 1,
        PromotionEligibility.USER_SPECIFIC: 0,
        PromotionEligibility.UNKNOWN: 0,
    }[value]


def money(value: Decimal | float | str) -> Decimal:
    return Decimal(str(value)).quantize(_CENT, rounding=ROUND_HALF_UP)


def _normalized_promotions(
    promotions: tuple[CheckoutPromotion, ...],
    *,
    regular_unit_price: Decimal,
    on_date: date,
) -> tuple[CheckoutPromotion, ...]:
    normalized: list[CheckoutPromotion] = []
    for promotion in promotions:
        if not promotion.is_active(on_date):
            continue
        price = promotion.resolved_price(regular_unit_price)
        if price is None or promotion.mechanism is PromotionMechanism.OTHER:
            continue
        normalized.append(promotion.model_copy(update={"price": money(price)}))
    return tuple(normalized)


def _matching_single_promotion(
    promotions: tuple[CheckoutPromotion, ...],
    *,
    base_unit_price: Decimal,
    regular_unit_price: Decimal,
) -> CheckoutPromotion | None:
    if base_unit_price >= regular_unit_price:
        return None
    matches = tuple(
        promotion
        for promotion in promotions
        if promotion.mechanism
        in {PromotionMechanism.SALE_PRICE, PromotionMechanism.PERCENT_DISCOUNT}
        and promotion.required_packages == 1
        and promotion.price == base_unit_price
    )
    if not matches:
        return None
    return max(
        matches,
        key=lambda promotion: (
            _eligibility_priority(promotion.eligibility),
            promotion.max_quantity is None,
            promotion.max_quantity or 0,
            promotion.description,
        ),
    )


def _single_total(
    *,
    package_count: int,
    base_price: Decimal,
    regular_price: Decimal,
    promotion: CheckoutPromotion | None,
) -> tuple[Decimal, int, int]:
    if promotion is None:
        applied_packages = package_count if base_price < regular_price else 0
        return money(base_price * package_count), applied_packages, package_count - applied_packages
    if promotion.max_quantity is None:
        return money(base_price * package_count), package_count, 0
    discounted = min(package_count, promotion.max_quantity)
    remainder = package_count - discounted
    return money(discounted * base_price + remainder * regular_price), discounted, remainder


def resolve_fixed_package_checkout(
    *,
    package_count: int,
    base_unit_price: Decimal | float | str,
    regular_unit_price: Decimal | float | str,
    promotions: tuple[CheckoutPromotion, ...] = (),
    on_date: date | None = None,
    ignored_promotion_references: tuple[str, ...] = (),
) -> EffectivePriceResolution:
    """Resolve fixed-package checkout using the application's basket semantics.

    Callers must pass only promotions for which the shopper is eligible.  That
    keeps eligibility policy separate from checkout arithmetic.  Conditional
    multibuys are evaluated against the actual package count and are never
    flattened into an unconditional package price.
    """

    if package_count < 1:
        raise ValueError("package_count must be at least one")
    base_price = money(base_unit_price)
    regular_price = money(regular_unit_price)
    if base_price <= 0 or regular_price <= 0:
        raise ValueError("checkout prices must be positive")
    target_date = on_date or datetime.now(tz=_STOCKHOLM).date()
    offer_rows = _normalized_promotions(
        tuple(promotions),
        regular_unit_price=regular_price,
        on_date=target_date,
    )
    applied = _matching_single_promotion(
        offer_rows,
        base_unit_price=base_price,
        regular_unit_price=regular_price,
    )
    best_total, applied_count, remainder = _single_total(
        package_count=package_count,
        base_price=base_price,
        regular_price=regular_price,
        promotion=applied,
    )

    for promotion in sorted(
        offer_rows,
        key=lambda row: (
            -_eligibility_priority(row.eligibility),
            row.description,
            row.price or Decimal(0),
            row.reference,
        ),
    ):
        if (
            promotion.mechanism is not PromotionMechanism.MULTIBUY
            or promotion.price is None
            or package_count < promotion.required_packages
        ):
            continue
        available_groups, _ = divmod(package_count, promotion.required_packages)
        groups = min(available_groups, promotion.max_quantity or available_groups)
        offer_remainder = package_count - groups * promotion.required_packages
        remainder_total, _, _ = _single_total(
            package_count=offer_remainder,
            base_price=base_price,
            regular_price=regular_price,
            promotion=_matching_single_promotion(
                offer_rows,
                base_unit_price=base_price,
                regular_unit_price=regular_price,
            ),
        ) if offer_remainder else (Decimal(0), 0, 0)
        offer_total = money(groups * promotion.price + remainder_total)
        if offer_total < best_total:
            best_total = offer_total
            applied = promotion
            applied_count = groups
            remainder = offer_remainder

    displayed_unit_price = money(best_total / package_count)
    eligibility = (
        applied.eligibility if applied is not None else PromotionEligibility.PUBLIC
    )
    mechanism = (
        applied.mechanism
        if applied is not None
        else (
            PromotionMechanism.SALE_PRICE
            if base_price < regular_price
            else PromotionMechanism.REGULAR
        )
    )
    comparable = ComparableCheckoutPrice(
        basis=(
            ComparablePriceBasis.CHECKOUT_TOTAL
            if package_count > 1 or mechanism is PromotionMechanism.MULTIBUY
            else ComparablePriceBasis.PACKAGE_PRICE
        ),
        eligibility=eligibility,
        mechanism=mechanism,
        package_count=package_count,
        checkout_total=best_total,
        displayed_unit_price=displayed_unit_price,
        condition_required_packages=(applied.required_packages if applied else 1),
        condition_total_price=(
            money(applied.price) if applied is not None and applied.price is not None else None
        ),
        member_program=applied.member_program if applied is not None else None,
        membership_program=(
            applied.membership_program if applied is not None else None
        ),
        personal_offer_id=(applied.personal_offer_id if applied is not None else None),
    )
    return EffectivePriceResolution(
        package_count=package_count,
        regular_unit_price=regular_price,
        eligible_base_unit_price=base_price,
        checkout_total=best_total,
        displayed_unit_price=displayed_unit_price,
        applied_promotion=applied,
        applied_groups_or_packages=applied_count,
        condition_remainder_packages=remainder,
        comparable=comparable,
        ignored_promotion_references=tuple(sorted(set(ignored_promotion_references))),
    )


def resolve_effective_price(
    price_contracts: tuple[PriceContract, ...] | list[PriceContract],
    purchase_quantity: int,
    user_pricing_context: UserPricingContext,
    *,
    on_date: date | None = None,
) -> EffectivePriceResolution:
    """Resolve one product's checkout from all shared and per-user contracts.

    This is the request-time eligibility boundary. Shared artifacts retain
    every verified public and generic-member contract; callers supply a
    :class:`UserPricingContext` instead of rebuilding or mutating that
    artifact. Personal contracts are usable only when their exact offer ID is
    present in the per-user overlay.
    """

    if purchase_quantity < 1:
        raise ValueError("purchase_quantity must be at least one")
    target_date = on_date or datetime.now(tz=_STOCKHOLM).date()
    contracts = tuple(price_contracts)
    active_regular = tuple(
        contract
        for contract in contracts
        if contract.mechanism is PromotionMechanism.REGULAR
        and contract.is_active(target_date)
        and user_pricing_context.allows(contract)
    )
    if not active_regular:
        raise ValueError("at least one active public regular price contract is required")
    regular_contract = min(
        active_regular,
        key=lambda contract: (money(contract.price or Decimal(0)), contract.reference),
    )
    assert regular_contract.price is not None
    regular = money(regular_contract.price)

    eligible: list[PriceContract] = []
    ignored: list[str] = []
    for contract in contracts:
        if contract.mechanism is PromotionMechanism.REGULAR:
            continue
        if (
            not contract.is_active(target_date)
            or not user_pricing_context.allows(contract)
            or contract.mechanism is PromotionMechanism.OTHER
        ):
            ignored.append(contract.reference)
            continue
        eligible.append(contract)

    single_prices = [regular]
    for contract in eligible:
        if contract.mechanism not in {
            PromotionMechanism.SALE_PRICE,
            PromotionMechanism.PERCENT_DISCOUNT,
        }:
            continue
        resolved = contract.resolved_price(regular)
        if resolved is not None:
            single_prices.append(money(resolved))
    base = min(single_prices)
    return resolve_fixed_package_checkout(
        package_count=purchase_quantity,
        base_unit_price=base,
        regular_unit_price=regular,
        promotions=tuple(eligible),
        on_date=target_date,
        ignored_promotion_references=tuple(ignored),
    )


__all__ = ["money", "resolve_effective_price", "resolve_fixed_package_checkout"]
