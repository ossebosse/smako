from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from grocery_data.app.domain.enums import Confidence, PromotionType
from grocery_data.app.domain.physical_price import (
    PhysicalIdentificationEvidence,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
)
from grocery_data.app.services.physical_price_candidates import (
    PersistedPhysicalPriceCandidateReader,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
)

NOW = datetime(2026, 8, 29, 13, tzinfo=UTC)


class _PromotionSession:
    def __init__(self, promotion: SimpleNamespace | None) -> None:
        self.promotion = promotion

    def scalars(self, _statement: object) -> tuple[SimpleNamespace, ...]:
        return (self.promotion,) if self.promotion is not None else ()


def _promotion(
    promotion_type: PromotionType,
    *,
    price: str,
    quantity: int | None,
    member_only: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        id="promotion",
        type=promotion_type.value,
        price=Decimal(price),
        quantity=quantity,
        member_only=member_only,
    )


def _candidate(
    promotion: SimpleNamespace,
    *,
    regular_price: str,
    sale_price: str | None = None,
    member_price: str | None = None,
):  # type: ignore[no-untyped-def]
    reader = PersistedPhysicalPriceCandidateReader(_PromotionSession(promotion))  # type: ignore[arg-type]
    product = SimpleNamespace(
        id="product",
        name="Testprodukt",
        brand="Test",
        category_path=["Test"],
        gtin=None,
        sale_model="fixed_package",
        package_quantity=Decimal(1),
        package_unit="st",
    )
    price = SimpleNamespace(
        store_id="store",
        observed_at=NOW,
        sale_price=Decimal(sale_price) if sale_price is not None else None,
        regular_price=Decimal(regular_price),
        member_price=(Decimal(member_price) if member_price is not None else None),
        comparison_price=None,
        comparison_unit=None,
    )
    snapshot = SimpleNamespace(id="snapshot")
    candidate = reader._candidate(
        "physical-store",
        "context",
        product,
        price,
        snapshot,
    )
    assert candidate is not None
    return candidate


def _observation(
    semantics: PhysicalPriceSemantics,
    *,
    shelf_price: str,
    multibuy_quantity: int | None = None,
    multibuy_total_price: str | None = None,
) -> PhysicalPriceObservation:
    promotion_type = {
        PhysicalPriceSemantics.SALE: PromotionType.SALE_PRICE,
        PhysicalPriceSemantics.MEMBER: PromotionType.MEMBER_PRICE,
        PhysicalPriceSemantics.MULTIBUY: PromotionType.MULTIBUY,
    }[semantics]
    return PhysicalPriceObservation(
        id="observation",
        physical_store_id="physical-store",
        product_name="Testprodukt",
        shelf_price=Decimal(shelf_price),
        promotion_type=promotion_type,
        member_only=semantics is PhysicalPriceSemantics.MEMBER,
        multibuy_quantity=multibuy_quantity,
        multibuy_total_price=(
            Decimal(multibuy_total_price)
            if multibuy_total_price is not None
            else None
        ),
        observed_at=NOW,
        confidence=Confidence.UNKNOWN,
        validation_session_id="session",
        validation_session_item_id="item",
        price_semantics=semantics,
        identity_status=PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH,
        identification_evidence=PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL,
        immutable_candidate_set_sha256="a" * 64,
    )


def test_explicit_member_promotion_price_is_projected_without_fake_multibuy() -> None:
    candidate = _candidate(
        _promotion(
            PromotionType.MEMBER_PRICE,
            price="29.95",
            quantity=1,
            member_only=True,
        ),
        regular_price="46.95",
    )

    assert candidate.current_price == Decimal("46.95")
    assert candidate.regular_price == Decimal("46.95")
    assert candidate.member_price == Decimal("29.95")
    assert candidate.multibuy_quantity is None
    assert candidate.multibuy_total_price is None
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(PhysicalPriceSemantics.MEMBER, shelf_price="29.95"),
        (candidate,),
    )
    assert comparison.status == "match"
    assert comparison.digital_price == Decimal("29.95")
    assert comparison.member_restriction_match is True


def test_explicit_sale_promotion_price_is_the_effective_current_price() -> None:
    candidate = _candidate(
        _promotion(PromotionType.SALE_PRICE, price="29.95", quantity=1),
        regular_price="34.97",
    )

    assert candidate.current_price == Decimal("29.95")
    assert candidate.regular_price == Decimal("34.97")
    assert candidate.member_price is None
    assert candidate.multibuy_quantity is None
    assert candidate.multibuy_total_price is None
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(PhysicalPriceSemantics.SALE, shelf_price="29.95"),
        (candidate,),
    )
    assert comparison.status == "match"
    assert comparison.digital_price == Decimal("29.95")


def test_only_actual_multibuy_projects_quantity_and_conditional_total() -> None:
    candidate = _candidate(
        _promotion(PromotionType.MULTIBUY, price="46.00", quantity=2),
        regular_price="26.45",
    )

    assert candidate.current_price == Decimal("26.45")
    assert candidate.multibuy_quantity == 2
    assert candidate.multibuy_total_price == Decimal("46.00")
    [comparison] = PhysicalPriceValidationService().compare_observation(
        _observation(
            PhysicalPriceSemantics.MULTIBUY,
            shelf_price="23.00",
            multibuy_quantity=2,
            multibuy_total_price="46.00",
        ),
        (candidate,),
    )
    assert comparison.status == "match"
    assert comparison.physical_price == Decimal("46.00")
    assert comparison.digital_price == Decimal("46.00")
    assert comparison.multibuy_match is True
