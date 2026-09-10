from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

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
    ComparablePriceBasis,
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
)
from grocery_data.app.services.physical_source_price_evidence import (
    PhysicalSourceSemanticPriceAdapter,
    SemanticPriceChangeReason,
)
from grocery_data.app.services.physical_validation_v3 import (
    ComparisonExclusionReason,
    PhysicalValidationV3Service,
)
from grocery_data.app.storage.database import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreModel,
)

OBSERVED_AT = datetime(2026, 8, 29, 12, tzinfo=UTC)
LOCKED_SNAPSHOT_ID = "snapshot:hemkop:4123:locked"
PHYSICAL_STORE_ID = "physical:hemkop:4123"
CONTEXT_ID = "own:hemkop:4123"
STORE_ID = "store:hemkop:4123"
PRODUCT_ID = "product:locked"
SOURCE_PRODUCT_ID = "source-product:locked"


@dataclass(frozen=True, slots=True)
class PromotionSeed:
    id: str
    promotion_type: PromotionType
    price: Decimal
    quantity: int = 1
    member_only: bool = False


@contextmanager
def _locked_snapshot(
    *,
    product_name: str,
    sale_model: SaleModel,
    regular_price: Decimal,
    sale_price: Decimal | None,
    member_price: Decimal | None = None,
    comparison_price: Decimal | None = None,
    comparison_unit: str | None = None,
    promotions: tuple[PromotionSeed, ...] = (),
) -> Iterator[tuple[Session, DigitalPriceCandidate]]:
    """Persist exact source rows behind one immutable physical-session candidate."""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        snapshot = CatalogSnapshotModel(
            id=LOCKED_SNAPSHOT_ID,
            chain="hemkop",
            scope_key="lund:hemkop:4123",
            coverage="full_online_catalog",
            state="promoted",
            is_active=True,
            connector_version="test",
            parser_version="test",
            normalizer_version="test",
            created_at=OBSERVED_AT,
            promoted_at=OBSERVED_AT,
        )
        session.add(snapshot)
        session.flush()
        raw = RawSnapshotModel(
            id="raw:locked",
            catalog_snapshot_id=snapshot.id,
            chain="hemkop",
            store_external_id="4123",
            kind="hemkop_product_category_page",
            method="POST",
            url="https://example.invalid/catalog",
            query={},
            fetched_at=OBSERVED_AT,
            http_status=200,
            content_type="application/json",
            payload_hash="1" * 64,
            payload_size=2,
            payload_location="fixture://locked-snapshot",
            request_fingerprint="2" * 64,
            connector_version="test",
        )
        session.add(raw)
        session.flush()
        store = StoreModel(
            id=STORE_ID,
            chain="hemkop",
            external_id="4123",
            name="Hemköp Karhögstorg Online",
            city="Lund",
            coverage="full_online_catalog",
            price_context_type="online_store",
            raw_reference="fixture://store",
            is_active=True,
            first_seen_at=OBSERVED_AT,
            last_seen_at=OBSERVED_AT,
        )
        session.add(store)
        session.flush()
        source = SourceProductModel(
            id=SOURCE_PRODUCT_ID,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            chain="hemkop",
            store_external_id="4123",
            external_product_id="locked-product",
            name=product_name,
            category_path=["fixture"],
            sale_price=sale_price,
            regular_price=regular_price,
            member_price=member_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            package_text=(None if sale_model is SaleModel.SOLD_BY_WEIGHT else "700 g"),
            sale_unit=("kg" if sale_model is SaleModel.SOLD_BY_WEIGHT else "st"),
            availability="available",
            raw_reference="fixture://locked-snapshot#product",
            fetched_at=OBSERVED_AT,
            parser_version="test",
            source_fields={},
            source_record_hash="3" * 64,
        )
        session.add(source)
        session.flush()
        product = ProductModel(
            id=PRODUCT_ID,
            source_product_id=source.id,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            source_product_key="hemkop:4123:locked-product",
            chain="hemkop",
            store_external_id="4123",
            external_product_id="locked-product",
            name=product_name,
            category_path=["fixture"],
            canonical_food="fixture-food",
            semantic_confidence="high",
            sale_model=sale_model.value,
            quantity_confidence="high",
            sale_price=sale_price,
            sale_unit=source.sale_unit,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            availability="available",
            raw_reference=source.raw_reference,
            parser_version="test",
            normalizer_version="test",
            observed_at=OBSERVED_AT,
        )
        session.add(product)
        session.flush()
        price = PriceObservationModel(
            id="price:locked",
            catalog_snapshot_id=snapshot.id,
            product_id=product.id,
            source_product_id=source.id,
            store_id=store.id,
            raw_snapshot_id=raw.id,
            observed_at=OBSERVED_AT,
            sale_price=sale_price,
            regular_price=regular_price,
            member_price=member_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            sale_unit=source.sale_unit,
        )
        session.add(price)
        session.flush()
        for index, promotion in enumerate(promotions):
            session.add(
                PromotionModel(
                    id=promotion.id,
                    catalog_snapshot_id=snapshot.id,
                    source_product_id=source.id,
                    product_id=product.id,
                    store_id=store.id,
                    raw_snapshot_id=raw.id,
                    price_observation_id=price.id,
                    offer_fingerprint=f"{index + 4}" * 64,
                    external_id=promotion.id,
                    type=promotion.promotion_type.value,
                    price=promotion.price,
                    quantity=promotion.quantity,
                    member_only=promotion.member_only,
                    description=promotion.id,
                    source_payload={"fixture": "locked source promotion evidence"},
                    parser_version="test",
                )
            )
        session.flush()

        candidate = DigitalPriceCandidate(
            physical_store_id=PHYSICAL_STORE_ID,
            grocery_context_id=CONTEXT_ID,
            source_provider="own",
            source_snapshot_id=snapshot.id,
            observed_at=OBSERVED_AT,
            product_id=product.id,
            product_name=product.name,
            current_price=sale_price or regular_price,
            regular_price=regular_price,
            member_price=member_price,
            comparison_price=comparison_price,
            comparison_unit=comparison_unit,
            sale_model=sale_model,
        )
        yield session, candidate
    engine.dispose()


def _capture(
    *,
    observation_id: str,
    product_name: str,
    shelf_price: Decimal,
    semantics: PhysicalPriceSemantics,
    promotion_type: PromotionType | None = None,
    member_only: bool = False,
    multibuy_quantity: int | None = None,
    multibuy_total_price: Decimal | None = None,
    comparison_price: Decimal | None = None,
    comparison_unit: str | None = None,
    regular_shelf_price: Decimal | None = None,
    weight_price_type: WeightPriceType | None = None,
) -> PhysicalPriceObservation:
    return PhysicalPriceObservation(
        id=observation_id,
        physical_store_id=PHYSICAL_STORE_ID,
        product_name=product_name,
        shelf_price=shelf_price,
        promotion_type=promotion_type,
        member_only=member_only,
        multibuy_quantity=multibuy_quantity,
        multibuy_total_price=multibuy_total_price,
        comparison_price=comparison_price,
        comparison_unit=comparison_unit,
        regular_shelf_price=regular_shelf_price,
        weight_price_type=weight_price_type,
        observed_at=OBSERVED_AT,
        confidence=Confidence.MEDIUM,
        validation_session_id="session:locked",
        validation_session_item_id=f"item:{observation_id}",
        price_semantics=semantics,
        identity_status=PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH,
        identification_evidence=PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL,
        immutable_candidate_set_sha256="a" * 64,
    )


def test_locked_sale_row_selects_sale_for_sale_and_regular_for_regular_capture() -> None:
    product_name = "Finbröd Skånskt 700 g"
    sale = PromotionSeed(
        id="public-sale-29.95",
        promotion_type=PromotionType.SALE_PRICE,
        price=Decimal("29.95"),
    )
    # The ordinary amount is persisted on the price observation; the effective
    # campaign amount exists only on the explicit immutable promotion row.
    with _locked_snapshot(
        product_name=product_name,
        sale_model=SaleModel.FIXED_PACKAGE,
        regular_price=Decimal("34.97"),
        sale_price=Decimal("34.97"),
        promotions=(sale,),
    ) as (session, candidate):
        adapter = PhysicalSourceSemanticPriceAdapter(session)
        sale_result = adapter.compare(
            _capture(
                observation_id="sale-capture",
                product_name=product_name,
                shelf_price=Decimal("29.95"),
                semantics=PhysicalPriceSemantics.SALE,
                promotion_type=PromotionType.SALE_PRICE,
            ),
            candidate,
        )
        regular_result = adapter.compare(
            _capture(
                observation_id="regular-capture",
                product_name=product_name,
                shelf_price=Decimal("34.97"),
                semantics=PhysicalPriceSemantics.REGULAR,
            ),
            candidate,
        )

    assert sale_result.comparable is True
    assert sale_result.exact_amount_match is True
    assert sale_result.digital is not None
    assert sale_result.digital.checkout_total == Decimal("29.95")
    assert sale_result.digital.mechanism is PromotionMechanism.SALE_PRICE
    assert sale_result.adjusted_candidate.source_snapshot_id == LOCKED_SNAPSHOT_ID
    assert SemanticPriceChangeReason.SELECTED_PUBLIC_SALE in sale_result.change_reasons

    assert regular_result.comparable is True
    assert regular_result.exact_amount_match is True
    assert regular_result.digital is not None
    assert regular_result.digital.checkout_total == Decimal("34.97")
    assert regular_result.digital.mechanism is PromotionMechanism.REGULAR
    assert regular_result.adjusted_candidate.source_snapshot_id == LOCKED_SNAPSHOT_ID
    assert (
        SemanticPriceChangeReason.SELECTED_REGULAR_CHANNEL
        in regular_result.change_reasons
    )


def test_locked_public_multibuy_and_member_unit_rows_select_requested_semantics() -> None:
    product_name = "Pasta 500 g"
    with _locked_snapshot(
        product_name=product_name,
        sale_model=SaleModel.FIXED_PACKAGE,
        regular_price=Decimal("15.09"),
        sale_price=Decimal("15.09"),
        promotions=(
            PromotionSeed(
                id="public-3-for-39",
                promotion_type=PromotionType.MULTIBUY,
                price=Decimal("39.00"),
                quantity=3,
            ),
            PromotionSeed(
                id="member-unit-10",
                promotion_type=PromotionType.MEMBER_PRICE,
                price=Decimal("10.00"),
                member_only=True,
            ),
            PromotionSeed(
                id="member-2-for-18",
                promotion_type=PromotionType.MULTIBUY,
                price=Decimal("18.00"),
                quantity=2,
                member_only=True,
            ),
        ),
    ) as (session, candidate):
        adapter = PhysicalSourceSemanticPriceAdapter(session)
        public = adapter.compare(
            _capture(
                observation_id="public-multibuy",
                product_name=product_name,
                shelf_price=Decimal("13.00"),
                semantics=PhysicalPriceSemantics.MULTIBUY,
                promotion_type=PromotionType.MULTIBUY,
                multibuy_quantity=3,
                multibuy_total_price=Decimal("39.00"),
            ),
            candidate,
        )
        member = adapter.compare(
            _capture(
                observation_id="member-unit",
                product_name=product_name,
                shelf_price=Decimal("10.00"),
                semantics=PhysicalPriceSemantics.MEMBER,
                promotion_type=PromotionType.MEMBER_PRICE,
                member_only=True,
            ),
            candidate,
        )
        member_multibuy = adapter.compare(
            _capture(
                observation_id="member-multibuy",
                product_name=product_name,
                shelf_price=Decimal("9.00"),
                semantics=PhysicalPriceSemantics.MULTIBUY,
                promotion_type=PromotionType.MULTIBUY,
                member_only=True,
                multibuy_quantity=2,
                multibuy_total_price=Decimal("18.00"),
            ),
            candidate,
        )

    assert public.source_promotion_rows == 3
    assert public.normalized_promotions == 3
    assert SemanticPriceChangeReason.MULTIPLE_SIMULTANEOUS_OFFERS in public.change_reasons
    assert public.comparable is True
    assert public.exact_amount_match is True
    assert public.digital is not None
    assert public.digital.basis is ComparablePriceBasis.CHECKOUT_TOTAL
    assert public.digital.eligibility is PromotionEligibility.PUBLIC
    assert public.digital.mechanism is PromotionMechanism.MULTIBUY
    assert public.digital.condition_required_packages == 3
    assert public.digital.condition_total_price == Decimal("39.00")

    assert member.source_promotion_rows == 3
    assert member.comparable is True
    assert member.exact_amount_match is True
    assert member.digital is not None
    assert member.digital.basis is ComparablePriceBasis.PACKAGE_PRICE
    assert member.digital.eligibility is PromotionEligibility.MEMBER
    assert member.digital.mechanism is PromotionMechanism.SALE_PRICE
    assert member.digital.displayed_unit_price == Decimal("10.00")
    assert member.digital.comparability_key != public.digital.comparability_key

    assert member_multibuy.comparable is True
    assert member_multibuy.exact_amount_match is True
    assert member_multibuy.digital is not None
    assert member_multibuy.digital.eligibility is PromotionEligibility.MEMBER
    assert member_multibuy.digital.mechanism is PromotionMechanism.MULTIBUY
    assert member_multibuy.digital.condition_required_packages == 2
    assert member_multibuy.digital.condition_total_price == Decimal("18.00")
    assert member_multibuy.digital.comparability_key != public.digital.comparability_key


def test_locked_paprika_weight_rows_select_public_sale_rate_per_kg() -> None:
    product_name = "Paprika Röd Klass 1"
    with _locked_snapshot(
        product_name=product_name,
        sale_model=SaleModel.SOLD_BY_WEIGHT,
        regular_price=Decimal("46.95"),
        sale_price=Decimal("29.95"),
        comparison_price=Decimal("46.95"),
        comparison_unit="SEK/kg",
        promotions=(
            PromotionSeed(
                id="paprika-public-sale-29.95-per-kg",
                promotion_type=PromotionType.SALE_PRICE,
                price=Decimal("29.95"),
            ),
        ),
    ) as (session, candidate):
        result = PhysicalSourceSemanticPriceAdapter(session).compare(
            _capture(
                observation_id="paprika-weight-sale",
                product_name=product_name,
                shelf_price=Decimal("29.95"),
                semantics=PhysicalPriceSemantics.WEIGHT,
                promotion_type=PromotionType.SALE_PRICE,
                comparison_price=Decimal("29.95"),
                comparison_unit="kr/kg",
                regular_shelf_price=Decimal("46.95"),
                weight_price_type=WeightPriceType.SALE,
            ),
            candidate,
        )

    assert result.source_promotion_rows == 1
    assert result.normalized_promotions == 1
    assert result.comparable is True
    assert result.exact_amount_match is True
    assert result.digital is not None
    assert result.digital.basis is ComparablePriceBasis.UNIT_RATE
    assert result.digital.eligibility is PromotionEligibility.PUBLIC
    assert result.digital.mechanism is PromotionMechanism.SALE_PRICE
    assert result.digital.comparison_unit == "kg"
    assert result.digital.checkout_total == Decimal("29.95")
    assert SemanticPriceChangeReason.SELECTED_UNIT_RATE in result.change_reasons


def test_missing_locked_sale_semantics_is_excluded_instead_of_using_regular_price() -> None:
    product_name = "Finbröd utan digital kampanj"
    observation = _capture(
        observation_id="missing-sale-semantics",
        product_name=product_name,
        shelf_price=Decimal("29.95"),
        semantics=PhysicalPriceSemantics.SALE,
        promotion_type=PromotionType.SALE_PRICE,
    )
    with _locked_snapshot(
        product_name=product_name,
        sale_model=SaleModel.FIXED_PACKAGE,
        regular_price=Decimal("34.97"),
        sale_price=Decimal("34.97"),
    ) as (session, candidate):
        diagnostic = PhysicalSourceSemanticPriceAdapter(session).compare(
            observation,
            candidate,
        )
        [comparison] = PhysicalPriceValidationService().compare_observation(
            observation,
            (diagnostic.adjusted_candidate,),
            expected_providers=(candidate.source_provider,),
            verified_session_product_identity=(
                candidate.source_provider,
                candidate.grocery_context_id,
                candidate.product_id,
            ),
        )
        assessment = PhysicalValidationV3Service._assess(
            observation,
            comparison,
            freshness_hours=Decimal(2),
            diagnostic_only=False,
            semantic_diagnostic=diagnostic,
        )

    assert diagnostic.digital is None
    assert diagnostic.comparable is False
    assert diagnostic.mismatch_dimensions == ("digital_semantics_unavailable",)
    assert assessment.comparable is False
    assert assessment.exclusion_reasons == (
        ComparisonExclusionReason.PROMOTION_SEMANTICS_INCOMPLETE,
    )


def test_explicit_sale_equal_to_base_remains_comparable_source_evidence() -> None:
    product_name = "Falukorv Ring 800 g"
    with _locked_snapshot(
        product_name=product_name,
        sale_model=SaleModel.FIXED_PACKAGE,
        regular_price=Decimal("33.95"),
        sale_price=Decimal("33.95"),
        promotions=(
            PromotionSeed(
                id="always-good-price-33.95",
                promotion_type=PromotionType.SALE_PRICE,
                price=Decimal("33.95"),
            ),
        ),
    ) as (session, candidate):
        result = PhysicalSourceSemanticPriceAdapter(session).compare(
            _capture(
                observation_id="falukorv-sale-30",
                product_name=product_name,
                shelf_price=Decimal("30.00"),
                semantics=PhysicalPriceSemantics.SALE,
                promotion_type=PromotionType.SALE_PRICE,
            ),
            candidate,
        )

    assert result.comparable is True
    assert result.digital is not None
    assert result.digital.mechanism is PromotionMechanism.SALE_PRICE
    assert result.digital.checkout_total == Decimal("33.95")
    assert result.signed_difference == Decimal("-3.95")
    assert result.absolute_difference == Decimal("3.95")
    assert result.semantic_result == "major_difference"
