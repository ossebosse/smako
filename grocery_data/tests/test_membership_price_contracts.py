from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PriceContract,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)
from grocery_data.app.services.fixed_checkout_price import resolve_effective_price

TODAY = date(2026, 8, 31)


def _contract(**overrides: object) -> PriceContract:
    values: dict[str, object] = {
        "reference": "regular",
        "eligibility": PromotionEligibility.PUBLIC,
        "mechanism": PromotionMechanism.REGULAR,
        "description": "Ordinarie pris",
        "price": Decimal("15.00"),
    }
    values.update(overrides)
    return PriceContract.model_validate(values)


def _regular(price: str = "15.00") -> PriceContract:
    return _contract(price=Decimal(price))


def test_membership_program_normalizes_legacy_chain_flags_and_labels() -> None:
    context = UserPricingContext(
        memberships={"ica": True, "Coop medlem": True, "hemkop": False}
    )
    contract = _contract(
        reference="coop-member",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.SALE_PRICE,
        price=Decimal("10.00"),
        member_program="Coop Medlem",
    )

    assert context.memberships == frozenset(
        {MembershipProgram.ICA_STAMMIS, MembershipProgram.COOP_MEMBER}
    )
    assert contract.membership_program is MembershipProgram.COOP_MEMBER
    assert context.allows(contract) is True


def test_price_contract_normalizes_only_negligible_binary_decimal_noise() -> None:
    normalized = _contract(price=Decimal("24.990000000000002"))

    assert normalized.price == Decimal("24.990000")

    with pytest.raises(ValidationError, match="decimal places"):
        _contract(price=Decimal("24.1234567"))


def test_generic_member_unit_price_requires_exact_program() -> None:
    coop = _contract(
        reference="coop-member",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.SALE_PRICE,
        price=Decimal("10.00"),
        membership_program=MembershipProgram.COOP_MEMBER,
    )
    contracts = [_regular(), coop]

    public = resolve_effective_price(contracts, 1, UserPricingContext(), on_date=TODAY)
    wrong_chain = resolve_effective_price(
        contracts,
        1,
        UserPricingContext(memberships={MembershipProgram.ICA_STAMMIS}),
        on_date=TODAY,
    )
    member = resolve_effective_price(
        contracts,
        1,
        UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}),
        on_date=TODAY,
    )

    assert public.checkout_total == Decimal("15.00")
    assert wrong_chain.checkout_total == Decimal("15.00")
    assert member.checkout_total == Decimal("10.00")
    assert member.applied_promotion == coop
    assert member.comparable.membership_program is MembershipProgram.COOP_MEMBER
    assert member.comparable.member_program == "Coop medlem"


@pytest.mark.parametrize(
    ("quantity", "expected"),
    ((2, "30.00"), (3, "30.00"), (4, "45.00")),
)
def test_member_multibuy_keeps_quantity_contract_and_residual(
    quantity: int, expected: str
) -> None:
    member_multibuy = _contract(
        reference="coop-member-3-for-30",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.MULTIBUY,
        description="Medlem: 3 för 30",
        price=Decimal("30.00"),
        required_packages=3,
        membership_program=MembershipProgram.COOP_MEMBER,
    )
    result = resolve_effective_price(
        [_regular(), member_multibuy],
        quantity,
        UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}),
        on_date=TODAY,
    )

    assert result.checkout_total == Decimal(expected)
    if quantity >= 3:
        assert result.applied_promotion == member_multibuy
        assert result.comparable.condition_required_packages == 3
        assert result.comparable.condition_total_price == Decimal("30.00")
    else:
        assert result.applied_promotion is None


def test_public_multibuy_needs_no_membership() -> None:
    public_multibuy = _contract(
        reference="public-2-for-20",
        mechanism=PromotionMechanism.MULTIBUY,
        description="2 för 20",
        price=Decimal("20.00"),
        required_packages=2,
    )

    result = resolve_effective_price(
        [_regular(), public_multibuy], 2, UserPricingContext(), on_date=TODAY
    )

    assert result.checkout_total == Decimal("20.00")
    assert result.comparable.eligibility is PromotionEligibility.PUBLIC


def test_member_percent_discount_and_max_quantity_are_enforced() -> None:
    percent = _contract(
        reference="hemkop-25-percent",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.PERCENT_DISCOUNT,
        description="25 % för medlemmar",
        price=None,
        percent_discount=Decimal(25),
        max_quantity=2,
        membership_program=MembershipProgram.HEMKOP_MEMBER,
    )

    result = resolve_effective_price(
        [_regular("20.00"), percent],
        3,
        UserPricingContext(memberships={MembershipProgram.HEMKOP_MEMBER}),
        on_date=TODAY,
    )

    assert result.checkout_total == Decimal("50.00")
    assert result.applied_groups_or_packages == 2
    assert result.condition_remainder_packages == 1
    assert result.comparable.mechanism is PromotionMechanism.PERCENT_DISCOUNT


def test_offer_validity_filters_future_and_expired_member_contracts() -> None:
    expired = _contract(
        reference="expired",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.SALE_PRICE,
        price=Decimal(1),
        membership_program=MembershipProgram.LIDL_PLUS,
        valid_to=date(2026, 8, 30),
    )
    future = expired.model_copy(
        update={"reference": "future", "valid_from": date(2026, 9, 1), "valid_to": None}
    )

    result = resolve_effective_price(
        [_regular(), expired, future],
        1,
        UserPricingContext(memberships={MembershipProgram.LIDL_PLUS}),
        on_date=TODAY,
    )

    assert result.checkout_total == Decimal("15.00")
    assert result.ignored_promotion_references == ("expired", "future")


def test_user_specific_contract_requires_exact_overlay_offer() -> None:
    personal = _contract(
        reference="personal-contract",
        eligibility=PromotionEligibility.USER_SPECIFIC,
        mechanism=PromotionMechanism.SALE_PRICE,
        price=Decimal("5.00"),
        personal_offer_id="offer-user-17",
    )
    contracts = [_regular(), personal]

    public = resolve_effective_price(contracts, 1, UserPricingContext(), on_date=TODAY)
    exact = resolve_effective_price(
        contracts,
        1,
        UserPricingContext(personalized_offer_ids={"offer-user-17"}),
        on_date=TODAY,
    )

    assert public.checkout_total == Decimal("15.00")
    assert exact.checkout_total == Decimal("5.00")
    assert exact.comparable.personal_offer_id == "offer-user-17"


def test_user_specific_contract_without_offer_identity_is_rejected() -> None:
    with pytest.raises(ValidationError, match="personal_offer_id"):
        _contract(
            eligibility=PromotionEligibility.USER_SPECIFIC,
            mechanism=PromotionMechanism.SALE_PRICE,
            price=Decimal(5),
        )


def test_unknown_free_text_member_program_fails_closed() -> None:
    unknown = _contract(
        reference="unknown-club",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.SALE_PRICE,
        price=Decimal(1),
        member_program="Okänd bonusklubb",
    )

    result = resolve_effective_price(
        [_regular(), unknown],
        1,
        UserPricingContext(memberships={MembershipProgram.COOP_MEMBER}),
        on_date=TODAY,
    )

    assert unknown.membership_program is None
    assert result.checkout_total == Decimal("15.00")
    assert result.ignored_promotion_references == ("unknown-club",)


def test_membership_context_has_stable_cache_identity() -> None:
    left = UserPricingContext(
        memberships={MembershipProgram.COOP_MEMBER, MembershipProgram.ICA_STAMMIS},
        activated_coupon_ids={"coupon-b", "coupon-a"},
    )
    right = UserPricingContext(
        memberships={MembershipProgram.ICA_STAMMIS, MembershipProgram.COOP_MEMBER},
        activated_coupon_ids={"coupon-a", "coupon-b"},
    )

    assert left.cache_identity == right.cache_identity
    assert left.cache_identity.startswith("pricing-context:")
    assert "coupon-a" not in left.cache_identity


def test_price_contract_and_user_context_json_round_trip_without_derived_fields() -> None:
    contract = _contract(
        reference="coop-member",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.SALE_PRICE,
        price=Decimal(10),
        membership_program=MembershipProgram.COOP_MEMBER,
    )
    context = UserPricingContext(memberships={MembershipProgram.COOP_MEMBER})

    restored_contract = PriceContract.model_validate_json(contract.model_dump_json())
    restored_context = UserPricingContext.model_validate_json(context.model_dump_json())

    assert restored_contract == contract
    assert restored_contract.price_contract_id == "coop-member"
    assert restored_context == context
