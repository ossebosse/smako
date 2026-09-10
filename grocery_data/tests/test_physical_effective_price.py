from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from grocery_data.app.domain.enums import Confidence, PromotionType, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    WeightPriceType,
)
from grocery_data.app.domain.promotion_pricing import (
    CheckoutPromotion,
    ComparablePriceBasis,
    FixedPackagePriceFacts,
    PromotionEligibility,
    PromotionMechanism,
    UnitRatePriceFacts,
)
from grocery_data.app.services.physical_effective_price import (
    PhysicalEffectivePriceResolver,
    digital_candidate_price_facts,
    physical_observation_price_facts,
    physical_weight_price_facts,
)

TODAY = date(2026, 8, 30)


def _promotion(**overrides: object) -> CheckoutPromotion:
    values: dict[str, object] = {
        "reference": "offer-1",
        "eligibility": PromotionEligibility.PUBLIC,
        "mechanism": PromotionMechanism.SALE_PRICE,
        "description": "Kampanj",
        "price": Decimal("12.00"),
    }
    values.update(overrides)
    return CheckoutPromotion.model_validate(values)


def _candidate(**overrides: object) -> DigitalPriceCandidate:
    values: dict[str, object] = {
        "physical_store_id": "physical:hemkop:4123",
        "grocery_context_id": "own:hemkop:4123",
        "source_provider": "own",
        "source_snapshot_id": "snapshot-1",
        "observed_at": datetime(2026, 8, 29, 12, tzinfo=UTC),
        "product_id": "product-1",
        "product_name": "Pasta 500 g",
        "current_price": Decimal("15.09"),
        "regular_price": Decimal("15.09"),
        "sale_model": SaleModel.FIXED_PACKAGE,
    }
    values.update(overrides)
    return DigitalPriceCandidate.model_validate(values)


def test_eligibility_and_mechanism_are_orthogonal_for_member_multibuy() -> None:
    promotion = _promotion(
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.MULTIBUY,
        price=Decimal(30),
        required_packages=2,
        member_program="Hemköp Klubb",
    )

    assert promotion.eligibility is PromotionEligibility.MEMBER
    assert promotion.mechanism is PromotionMechanism.MULTIBUY
    assert promotion.required_packages == 2
    assert promotion.price == Decimal(30)


def test_invalid_multibuy_is_rejected_without_flattening() -> None:
    with pytest.raises(ValidationError, match="at least two packages"):
        _promotion(mechanism=PromotionMechanism.MULTIBUY, required_packages=1)
    with pytest.raises(ValidationError, match="only multibuy"):
        _promotion(mechanism=PromotionMechanism.SALE_PRICE, required_packages=2)


def test_simultaneous_public_multibuy_and_member_unit_price_choose_by_eligibility() -> None:
    facts = FixedPackagePriceFacts(
        regular_unit_price=Decimal("15.09"),
        member_unit_price=Decimal("10.00"),
        promotions=(
            _promotion(
                reference="public-3-for-39",
                mechanism=PromotionMechanism.MULTIBUY,
                price=Decimal(39),
                required_packages=3,
                description="3 för 39",
            ),
        ),
    )
    resolver = PhysicalEffectivePriceResolver()

    public = resolver.resolve(
        facts,
        package_count=3,
        member_eligible=False,
        on_date=TODAY,
    )
    member = resolver.resolve(
        facts,
        package_count=3,
        member_eligible=True,
        on_date=TODAY,
    )

    assert public.checkout_total == Decimal("39.00")
    assert public.applied_promotion is not None
    assert public.applied_promotion.reference == "public-3-for-39"
    assert public.comparable.eligibility is PromotionEligibility.PUBLIC
    assert public.comparable.mechanism is PromotionMechanism.MULTIBUY
    assert public.comparable.condition_required_packages == 3
    assert public.comparable.condition_total_price == Decimal("39.00")
    assert member.checkout_total == Decimal("30.00")
    assert member.applied_promotion is not None
    assert member.applied_promotion.reference == "price-field:member"
    assert member.comparable.eligibility is PromotionEligibility.MEMBER
    assert member.comparable.mechanism is PromotionMechanism.SALE_PRICE
    assert public.comparable.comparability_key != member.comparable.comparability_key


def test_member_multibuy_is_ignored_without_membership_and_applied_with_it() -> None:
    member_multibuy = _promotion(
        reference="member-2-for-30",
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.MULTIBUY,
        price=Decimal(30),
        required_packages=2,
        member_program="Hemköp Klubb",
    )
    facts = FixedPackagePriceFacts(
        regular_unit_price=Decimal(20),
        promotions=(member_multibuy,),
    )
    resolver = PhysicalEffectivePriceResolver()

    public = resolver.resolve(facts, package_count=2, member_eligible=False, on_date=TODAY)
    member = resolver.resolve(facts, package_count=2, member_eligible=True, on_date=TODAY)

    assert public.checkout_total == Decimal("40.00")
    assert public.applied_promotion is None
    assert public.ignored_promotion_references == ("member-2-for-30",)
    assert member.checkout_total == Decimal("30.00")
    assert member.applied_promotion == member_multibuy
    assert member.applied_groups_or_packages == 1
    assert member.condition_remainder_packages == 0


def test_equal_public_and_member_price_keeps_least_restrictive_public_evidence() -> None:
    facts = FixedPackagePriceFacts(
        regular_unit_price=Decimal(20),
        public_current_unit_price=Decimal(10),
        member_unit_price=Decimal(10),
    )

    result = PhysicalEffectivePriceResolver().resolve(
        facts,
        package_count=1,
        member_eligible=True,
        on_date=TODAY,
    )

    assert result.checkout_total == Decimal("10.00")
    assert result.applied_promotion is not None
    assert result.applied_promotion.reference == "price-field:public-current"
    assert result.comparable.eligibility is PromotionEligibility.PUBLIC


def test_multibuy_remainder_keeps_authoritative_checkout_total_and_condition() -> None:
    facts = FixedPackagePriceFacts(
        regular_unit_price=Decimal("20.00"),
        promotions=(
            _promotion(
                mechanism=PromotionMechanism.MULTIBUY,
                price=Decimal(30),
                required_packages=2,
                description="2 för 30",
            ),
        ),
    )

    result = PhysicalEffectivePriceResolver().resolve(
        facts,
        package_count=3,
        member_eligible=False,
        on_date=TODAY,
    )

    assert result.checkout_total == Decimal("50.00")
    assert result.displayed_unit_price == Decimal("16.67")
    assert result.applied_groups_or_packages == 1
    assert result.condition_remainder_packages == 1
    assert result.comparable.basis is ComparablePriceBasis.CHECKOUT_TOTAL
    assert result.comparable.condition_required_packages == 2
    assert result.comparable.condition_total_price == Decimal("30.00")


def test_percent_discount_uses_regular_price_and_preserves_mechanism() -> None:
    facts = FixedPackagePriceFacts(
        regular_unit_price=Decimal(40),
        promotions=(
            _promotion(
                mechanism=PromotionMechanism.PERCENT_DISCOUNT,
                price=None,
                percent_discount=Decimal(25),
                description="25 % rabatt",
            ),
        ),
    )

    result = PhysicalEffectivePriceResolver().resolve(
        facts,
        package_count=2,
        member_eligible=False,
        on_date=TODAY,
    )

    assert result.eligible_base_unit_price == Decimal("30.00")
    assert result.checkout_total == Decimal("60.00")
    assert result.comparable.mechanism is PromotionMechanism.PERCENT_DISCOUNT


def test_unknown_eligibility_and_expired_rows_fail_closed() -> None:
    facts = FixedPackagePriceFacts(
        regular_unit_price=Decimal(20),
        promotions=(
            _promotion(
                reference="unknown",
                eligibility=PromotionEligibility.UNKNOWN,
                price=Decimal(1),
            ),
            _promotion(
                reference="expired",
                price=Decimal(2),
                valid_to=date(2026, 8, 29),
            ),
        ),
    )

    result = PhysicalEffectivePriceResolver().resolve(
        facts,
        package_count=1,
        member_eligible=True,
        on_date=TODAY,
    )

    assert result.checkout_total == Decimal("20.00")
    assert result.applied_promotion is None
    assert result.ignored_promotion_references == ("expired", "unknown")


def test_digital_projection_adds_to_richer_promotions_instead_of_replacing_them() -> None:
    public_multibuy = _promotion(
        reference="source:public-3-for-39",
        mechanism=PromotionMechanism.MULTIBUY,
        price=Decimal(39),
        required_packages=3,
    )

    facts = digital_candidate_price_facts(
        _candidate(member_price=Decimal(10)),
        promotions=(public_multibuy,),
    )

    assert public_multibuy in facts.promotions
    assert facts.member_unit_price == Decimal(10)
    assert len(facts.promotions) == 1


def test_legacy_member_multibuy_projects_as_two_orthogonal_axes() -> None:
    observation = PhysicalPriceObservation(
        id="observation-1",
        physical_store_id="physical:hemkop:4123",
        product_name="Pasta",
        shelf_price=Decimal(15),
        promotion_type=PromotionType.MEMBER_PRICE,
        member_only=True,
        multibuy_quantity=2,
        multibuy_total_price=Decimal(30),
        observed_at=datetime(2026, 8, 29, 12, tzinfo=UTC),
        confidence=Confidence.HIGH,
    )

    facts = physical_observation_price_facts(observation)
    [promotion] = facts.promotions

    assert promotion.eligibility is PromotionEligibility.MEMBER
    assert promotion.mechanism is PromotionMechanism.MULTIBUY
    assert promotion.price == Decimal(30)
    assert promotion.required_packages == 2


def test_unit_rate_resolver_keeps_paprika_sale_separate_from_regular_rate() -> None:
    facts = UnitRatePriceFacts(
        comparison_unit="SEK/kg",
        regular_unit_rate=Decimal("46.95"),
        public_current_unit_rate=Decimal("29.95"),
    )

    result = PhysicalEffectivePriceResolver().resolve_unit_rate(
        facts,
        member_eligible=False,
        on_date=TODAY,
    )

    assert result.regular_unit_rate == Decimal("46.95")
    assert result.effective_unit_rate == Decimal("29.95")
    assert result.applied_promotion is not None
    assert result.applied_promotion.reference == "price-field:public-current"
    assert result.comparable.basis is ComparablePriceBasis.UNIT_RATE
    assert result.comparable.comparison_unit == "kg"
    assert result.comparable.mechanism is PromotionMechanism.SALE_PRICE
    assert result.comparable.checkout_total == Decimal("29.95")


def test_unit_rate_member_eligibility_is_independent_from_sale_mechanism() -> None:
    facts = UnitRatePriceFacts(
        comparison_unit="kr/kg",
        regular_unit_rate=Decimal("46.95"),
        public_current_unit_rate=Decimal("39.95"),
        member_unit_rate=Decimal("29.95"),
    )
    resolver = PhysicalEffectivePriceResolver()

    public = resolver.resolve_unit_rate(facts, member_eligible=False, on_date=TODAY)
    member = resolver.resolve_unit_rate(facts, member_eligible=True, on_date=TODAY)

    assert public.effective_unit_rate == Decimal("39.95")
    assert public.comparable.eligibility is PromotionEligibility.PUBLIC
    assert member.effective_unit_rate == Decimal("29.95")
    assert member.comparable.eligibility is PromotionEligibility.MEMBER
    assert member.comparable.mechanism is PromotionMechanism.SALE_PRICE
    assert public.comparable.comparability_key != member.comparable.comparability_key


def test_unit_rate_fails_closed_for_multibuy_and_capped_offer() -> None:
    facts = UnitRatePriceFacts(
        comparison_unit="kg",
        regular_unit_rate=Decimal("40.00"),
        promotions=(
            _promotion(
                reference="multi",
                mechanism=PromotionMechanism.MULTIBUY,
                price=Decimal("30.00"),
                required_packages=2,
            ),
            _promotion(
                reference="capped-rate",
                price=Decimal("20.00"),
                max_quantity=1,
            ),
        ),
    )

    result = PhysicalEffectivePriceResolver().resolve_unit_rate(
        facts,
        member_eligible=True,
        on_date=TODAY,
    )

    assert result.effective_unit_rate == Decimal("40.00")
    assert result.applied_promotion is None
    assert result.ignored_promotion_references == ("capped-rate", "multi")


def test_physical_weight_projection_preserves_regular_and_current_sek_per_kg() -> None:
    observation = PhysicalPriceObservation(
        id="observation-weight",
        physical_store_id="physical:hemkop:4123",
        product_name="Paprika Röd Klass 1",
        shelf_price=Decimal("29.95"),
        comparison_price=Decimal("29.95"),
        comparison_unit="kr/kg",
        promotion_type=PromotionType.SALE_PRICE,
        member_only=False,
        observed_at=datetime(2026, 8, 29, 12, tzinfo=UTC),
        confidence=Confidence.HIGH,
        validation_session_id="session-1",
        validation_session_item_id="item-1",
        price_semantics=PhysicalPriceSemantics.WEIGHT,
        identity_status=PhysicalProductIdentityStatus.WEIGHT_ITEM_NO_GTIN_REQUIRED,
        identification_evidence=PhysicalIdentificationEvidence.WEIGHT_SOURCE_PRODUCT,
        regular_shelf_price=Decimal("46.95"),
        weight_price_type=WeightPriceType.SALE,
        immutable_candidate_set_sha256="0" * 64,
    )

    facts = physical_weight_price_facts(observation)
    result = PhysicalEffectivePriceResolver().resolve_unit_rate(
        facts,
        member_eligible=False,
        on_date=TODAY,
    )

    assert facts.regular_unit_rate == Decimal("46.95")
    assert facts.public_current_unit_rate == Decimal("29.95")
    assert result.effective_unit_rate == Decimal("29.95")
    assert result.comparable.comparison_unit == "kg"
