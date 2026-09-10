from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select

from grocery_data.app.domain.enums import Confidence, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
)
from grocery_data.app.services.physical_session_reconciliation import (
    RECONCILED_COMPARISON_BASIS,
    PhysicalSessionReconciliationService,
)
from grocery_data.app.services.physical_validation_sessions import (
    build_physical_validation_session,
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
    PhysicalPriceObservationModel,
    PhysicalStoreModel,
    PhysicalValidationComparisonVersionModel,
    PhysicalValidationSessionCandidateModel,
    PhysicalValidationSessionReconciliationModel,
    PhysicalValidationSnapshotLockModel,
    PriceObservationModel,
    ProductModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)
from grocery_data.app.storage.repositories import (
    PhysicalPriceObservationRepository,
    PhysicalValidationSessionRepository,
)

FIELD_TIME = datetime(2026, 8, 29, 13, tzinfo=UTC)
PHYSICAL_STORE_ID = "physical:hemkop:4123"
CONTEXT_ID = "own:hemkop:4123"
EXTERNAL_PRODUCT_ID = "101230686_ST"


def _seed_catalog_row(
    database_session,  # type: ignore[no-untyped-def]
    *,
    snapshot_id: str,
    observed_at: datetime,
    price: str,
    active: bool,
) -> ProductModel:
    snapshot = CatalogSnapshotModel(
        id=snapshot_id,
        chain="hemkop",
        scope_key="lund:hemkop:4123",
        coverage="full_online_catalog",
        state="promoted",
        is_active=active,
        connector_version="test",
        parser_version="test",
        normalizer_version="test",
        created_at=observed_at,
        promoted_at=observed_at,
    )
    raw = RawSnapshotModel(
        id=f"raw-{snapshot_id}",
        catalog_snapshot_id=snapshot_id,
        chain="hemkop",
        store_external_id="4123",
        kind="hemkop_product_category_page",
        method="POST",
        url="https://example.invalid/catalog",
        query={},
        fetched_at=observed_at,
        http_status=200,
        content_type="application/json",
        payload_hash=(snapshot_id + "0" * 64)[:64],
        payload_size=2,
        payload_location=f"fixture://{snapshot_id}",
        request_fingerprint=(snapshot_id[::-1] + "1" * 64)[:64],
        connector_version="test",
    )
    source = SourceProductModel(
        id=f"source-{snapshot_id}",
        catalog_snapshot_id=snapshot_id,
        raw_snapshot_id=raw.id,
        store_id="store-4123",
        chain="hemkop",
        store_external_id="4123",
        external_product_id=EXTERNAL_PRODUCT_ID,
        gtin=None,
        name="Finbröd Skånskt",
        category_path=["Bröd"],
        sale_price=Decimal(price),
        regular_price=Decimal(price),
        package_text="700 g",
        package_quantity=Decimal(700),
        package_unit="g",
        sale_unit="st",
        availability="available",
        raw_reference=f"fixture://{snapshot_id}#product",
        fetched_at=observed_at,
        parser_version="test",
        source_fields={},
        source_record_hash=("2" + snapshot_id + "0" * 64)[:64],
    )
    product = ProductModel(
        id=f"product-{snapshot_id}",
        source_product_id=source.id,
        catalog_snapshot_id=snapshot_id,
        raw_snapshot_id=raw.id,
        store_id="store-4123",
        source_product_key=f"hemkop:4123:{EXTERNAL_PRODUCT_ID}",
        chain="hemkop",
        store_external_id="4123",
        external_product_id=EXTERNAL_PRODUCT_ID,
        name=source.name,
        category_path=["Bröd"],
        canonical_food="bread",
        semantic_confidence="high",
        sale_model=SaleModel.FIXED_PACKAGE.value,
        quantity_confidence="high",
        package_quantity=Decimal(700),
        package_unit="g",
        usable_quantity=Decimal(700),
        usable_unit="g",
        sale_price=Decimal(price),
        sale_unit="st",
        availability="available",
        raw_reference=source.raw_reference,
        parser_version="test",
        normalizer_version="test",
        observed_at=observed_at,
    )
    price_row = PriceObservationModel(
        id=f"price-{snapshot_id}",
        catalog_snapshot_id=snapshot_id,
        product_id=product.id,
        source_product_id=source.id,
        store_id="store-4123",
        raw_snapshot_id=raw.id,
        observed_at=observed_at,
        sale_price=Decimal(price),
        regular_price=Decimal(price),
        sale_unit="st",
    )
    # The production rows are written in the same raw-first order.  Explicit
    # flushes keep this fixture independent of ORM relationship configuration
    # while SQLite foreign-key enforcement is enabled.
    database_session.add(snapshot)
    database_session.flush()
    database_session.add(raw)
    database_session.flush()
    database_session.add(source)
    database_session.flush()
    database_session.add(product)
    database_session.flush()
    database_session.add(price_row)
    database_session.flush()
    return product


def _seed_completed_session(  # type: ignore[no-untyped-def]
    database_session,
    *,
    old_age_hours: int = 72,
    complete: bool = True,
    identity_status: PhysicalProductIdentityStatus = (
        PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH
    ),
    identification_evidence: PhysicalIdentificationEvidence = (
        PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL
    ),
):
    database_session.add_all(
        [
            StoreModel(
                id="store-4123",
                chain="hemkop",
                external_id="4123",
                name="Hemköp Karhögstorg Online",
                city="Lund",
                coverage="full_online_catalog",
                price_context_type="online_store",
                raw_reference="fixture://store",
                is_active=True,
                first_seen_at=FIELD_TIME,
                last_seen_at=FIELD_TIME,
            ),
            PhysicalStoreModel(
                id=PHYSICAL_STORE_ID,
                chain="hemkop",
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="22358",
                city="Lund",
                official_source="https://example.invalid/store",
                discovered_at=FIELD_TIME,
                last_seen_at=FIELD_TIME,
                is_active=True,
                lifecycle_state="active",
            ),
        ]
    )
    database_session.flush()
    database_session.add(
        StoreContextLinkModel(
            id="link-4123",
            physical_store_id=PHYSICAL_STORE_ID,
            grocery_context_id=CONTEXT_ID,
            source_provider="own",
            source_channel="catalog",
            local_store_id="store-4123",
            grocery_context_name="Hemköp Karhögstorg Online",
            price_context_type="online_store",
            coverage="full_online_catalog",
            relation_type="exact_store_online_context",
            confidence="high",
            evidence="exact fixture identity",
            basket_eligible=True,
            offers_only=False,
            linked_at=FIELD_TIME,
            last_verified_at=FIELD_TIME,
            is_active=True,
        )
    )
    old_product = _seed_catalog_row(
        database_session,
        snapshot_id="old-snapshot",
        observed_at=FIELD_TIME - timedelta(hours=old_age_hours),
        price="34.97",
        active=False,
    )
    _seed_catalog_row(
        database_session,
        snapshot_id="new-snapshot",
        observed_at=FIELD_TIME + timedelta(hours=2),
        price="32.00",
        active=True,
    )
    candidate = DigitalPriceCandidate(
        physical_store_id=PHYSICAL_STORE_ID,
        grocery_context_id=CONTEXT_ID,
        source_provider="own",
        source_snapshot_id="old-snapshot",
        observed_at=FIELD_TIME - timedelta(hours=old_age_hours),
        product_id=old_product.id,
        product_name=old_product.name,
        package_description="700 g",
        current_price=Decimal("34.97"),
        regular_price=Decimal("34.97"),
        sale_model=SaleModel.FIXED_PACKAGE,
        common_product_score=Decimal(1),
    )
    validation_session, items = build_physical_validation_session(
        (candidate,),
        physical_store_id=PHYSICAL_STORE_ID,
        chain="hemkop",
        store_name="Hemköp Lund Karhögstorg",
        target_count=1,
        started_at=FIELD_TIME - timedelta(minutes=5),
    )
    repository = PhysicalValidationSessionRepository(database_session)
    repository.add(validation_session, items)
    [item] = items
    observation = PhysicalPriceObservation(
        id="physical-observation",
        physical_store_id=PHYSICAL_STORE_ID,
        product_name=old_product.name,
        shelf_price=Decimal("32.00"),
        observed_at=FIELD_TIME,
        confidence=Confidence.MEDIUM,
        validation_session_id=validation_session.id,
        validation_session_item_id=item.id,
        price_semantics=PhysicalPriceSemantics.REGULAR,
        identity_status=identity_status,
        identification_evidence=identification_evidence,
        immutable_candidate_set_sha256=item.candidate_set_sha256,
    )
    PhysicalPriceObservationRepository(database_session).add(observation)
    if complete:
        repository.complete(
            validation_session.id,
            completed_at=FIELD_TIME + timedelta(minutes=5),
        )
    database_session.flush()
    return validation_session.id, item.id


def test_v3_snapshot_lock_exists_while_session_is_active() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        session_id, _ = _seed_completed_session(database_session, complete=False)
        locks = PhysicalValidationV3Service(database_session).lock_session_start(
            session_id
        )
        assert len(locks) == 1
        assert locks[0].source_snapshot_id == "old-snapshot"
        assert locks[0].locked_at == FIELD_TIME - timedelta(minutes=5)
        assert (
            PhysicalValidationSessionRepository(database_session).get(session_id).status.value
            == "active"
        )
    engine.dispose()


def test_explicit_reconciliation_preserves_original_and_removes_stale_status() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        session_id, item_id = _seed_completed_session(database_session)
        database_session.commit()
        frozen_before = database_session.scalar(
            select(PhysicalValidationSessionCandidateModel).where(
                PhysicalValidationSessionCandidateModel.session_item_id == item_id
            )
        )
        assert frozen_before is not None
        frozen_hash = frozen_before.candidate_sha256

        service = PhysicalSessionReconciliationService(database_session)
        preview = service.preview(session_id, snapshot_id="new-snapshot")
        assert [row.status.value for row in preview.original_comparisons] == [
            "stale_digital_price"
        ]
        assert [row.status.value for row in preview.comparisons] == [
            "stale_digital_price"
        ]
        assert [row.status.value for row in preview.diagnostic_comparisons] == [
            "match"
        ]
        assert preview.temporal_relation == "post_visit"
        assert preview.min_signed_offset_hours == Decimal("2.00")
        assert preview.max_signed_offset_hours == Decimal("2.00")
        assert preview.comparison_basis == "frozen_session_evidence"
        assert preview.metadata()["post_visit_diagnostic_basis"] == (
            RECONCILED_COMPARISON_BASIS
        )
        assert preview.metadata()["immutable_session_evidence_preserved"] is True

        result = service.bind(
            session_id,
            snapshot_id="new-snapshot",
            reason="explicit same-day post-visit refresh",
            reconciled_at=FIELD_TIME + timedelta(hours=3),
        )
        database_session.commit()
        assert [row.status.value for row in result.comparisons] == [
            "stale_digital_price"
        ]
        assert [row.status.value for row in result.diagnostic_comparisons] == [
            "match"
        ]
        assert result.reconciliation is not None
        assert result.reconciliation.source_snapshot_id == "new-snapshot"

        repeated = service.bind(
            session_id,
            snapshot_id="new-snapshot",
            reason="explicit same-day post-visit refresh",
        )
        database_session.commit()
        assert repeated.reconciliation == result.reconciliation
        assert (
            database_session.scalar(
                select(func.count()).select_from(
                    PhysicalValidationSessionReconciliationModel
                )
            )
            == 1
        )
        frozen_after = database_session.scalar(
            select(PhysicalValidationSessionCandidateModel).where(
                PhysicalValidationSessionCandidateModel.session_item_id == item_id
            )
        )
        assert frozen_after is not None
        assert frozen_after.source_snapshot_id == "old-snapshot"
        assert frozen_after.candidate_sha256 == frozen_hash
        observation = database_session.get(
            PhysicalPriceObservationModel,
            "physical-observation",
        )
        assert observation is not None
        assert observation.shelf_price == Decimal("32.00")
    engine.dispose()


def test_v3_official_lock_is_idempotent_and_post_visit_is_diagnostic_only() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        session_id, _ = _seed_completed_session(database_session)
        database_session.commit()
        observation_before = database_session.get(
            PhysicalPriceObservationModel,
            "physical-observation",
        )
        assert observation_before is not None
        observation_bytes_before = repr(
            tuple(
                getattr(observation_before, column.name)
                for column in PhysicalPriceObservationModel.__table__.columns
            )
        ).encode()

        service = PhysicalValidationV3Service(
            database_session,
            official_freshness_hours=Decimal(2),
            minimum_comparable_sample=1,
        )
        official = service.lock_official(session_id, created_at=FIELD_TIME)
        repeated_official = service.lock_official(session_id, created_at=FIELD_TIME)
        assert repeated_official.version == official.version
        assert official.official is True
        assert official.comparable_denominator == 0
        assert official.score_eligible is False
        assert official.metadata()["exclusion_reason_counts"] == {
            ComparisonExclusionReason.STALE_DIGITAL.value: 1
        }
        official_semantic = official.metadata()["semantic_price_diagnostics"]
        assert official_semantic["comparable_count"] == 1
        assert official_semantic["temporal_neutral_amount_summary"] == {
            "priced_comparable_count": 1,
            "exact_matches": 0,
            "within_050": 0,
            "within_100": 0,
            "major_difference": 1,
            "mean_absolute_error": Decimal("2.97"),
            "median_absolute_error": Decimal("2.97"),
            "mean_signed_error": Decimal("-2.97"),
            "signed_error_definition": (
                "physical_semantic_price_minus_digital_semantic_price_sek; "
                "independent of freshness/diagnostic-only score eligibility"
            ),
        }
        assert official_semantic["rows"][0]["semantic_result"] == "major_difference"
        assert official_semantic["rows"][0]["signed_difference"] == Decimal("-2.97")

        diagnostic = service.register_post_visit_diagnostic(
            session_id,
            snapshot_id="new-snapshot",
            reason="same-day post-visit diagnostic",
            created_at=FIELD_TIME + timedelta(hours=3),
        )
        database_session.commit()
        assert diagnostic.official is False
        assert diagnostic.diagnostic_only is True
        assert [row.status.value for row in diagnostic.comparisons] == ["match"]
        assert diagnostic.comparable_denominator == 0
        assert diagnostic.score_eligible is False
        assert diagnostic.metadata()["exclusion_reason_counts"] == {
            ComparisonExclusionReason.POST_VISIT_DIAGNOSTIC_ONLY.value: 1,
        }
        diagnostic_semantic = diagnostic.metadata()["semantic_price_diagnostics"]
        assert diagnostic_semantic["comparable_count"] == 1
        assert diagnostic_semantic["temporal_neutral_amount_summary"][
            "exact_matches"
        ] == 1
        assert diagnostic_semantic["rows"][0]["semantic_result"] == "exact_match"
        combined = service.report(session_id)
        assert combined["official_replaced_by_diagnostic"] is False
        assert combined["official"]["status_counts"] == {  # type: ignore[index]
            "stale_digital_price": 1
        }
        assert len(combined["post_visit_diagnostics"]) == 1  # type: ignore[arg-type]
        assert (
            database_session.scalar(
                select(func.count()).select_from(
                    PhysicalValidationSnapshotLockModel
                )
            )
            == 1
        )
        assert (
            database_session.scalar(
                select(func.count()).select_from(
                    PhysicalValidationComparisonVersionModel
                )
            )
            == 2
        )
        observation_after = database_session.get(
            PhysicalPriceObservationModel,
            "physical-observation",
        )
        assert observation_after is not None
        database_session.refresh(observation_after)
        observation_bytes_after = repr(
            tuple(
                getattr(observation_after, column.name)
                for column in PhysicalPriceObservationModel.__table__.columns
            )
        ).encode()
        assert observation_bytes_after == observation_bytes_before
    engine.dispose()


def test_v3_comparable_denominator_controls_score_threshold() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        session_id, _ = _seed_completed_session(database_session, old_age_hours=1)
        database_session.commit()
        service = PhysicalValidationV3Service(
            database_session,
            official_freshness_hours=Decimal(2),
            minimum_comparable_sample=1,
        )
        report = service.lock_official(session_id, created_at=FIELD_TIME)
        assert report.comparable_denominator == 1
        assert report.score_eligible is True
        metadata = report.metadata()
        assert metadata["physical_observation_count"] == 1
        assert metadata["comparable_denominator"] == 1
        assert metadata["minimum_comparable_sample"] == 1
        assert metadata["score_eligible"] is True
        assert metadata["excluded_comparisons"] == 0
    engine.dispose()


def test_semantic_amount_summary_excludes_true_no_match_identity() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        session_id, _ = _seed_completed_session(
            database_session,
            old_age_hours=1,
            identity_status=PhysicalProductIdentityStatus.NO_MATCH,
            identification_evidence=PhysicalIdentificationEvidence.UNVERIFIED,
        )
        database_session.commit()
        report = PhysicalValidationV3Service(
            database_session,
            official_freshness_hours=Decimal(2),
            minimum_comparable_sample=1,
        ).lock_official(session_id, created_at=FIELD_TIME)

        metadata = report.metadata()
        semantic = metadata["semantic_price_diagnostics"]
        assert semantic["comparison_count"] == 1
        assert semantic["contract_comparable_count"] == 1
        assert semantic["comparable_count"] == 0
        assert semantic["exact_amount_match_count"] == 0
        assert semantic["temporal_neutral_amount_summary"][
            "priced_comparable_count"
        ] == 0
        assert semantic["temporal_neutral_amount_summary"][
            "mean_absolute_error"
        ] is None
        assert semantic["rows"][0]["comparison_status"] == "no_digital_match"
        assert semantic["rows"][0]["amount_summary_eligible"] is False
        assert semantic["rows"][0]["signed_difference"] is None
        assert semantic["rows"][0]["semantic_result"] == (
            "excluded_from_amount_summary"
        )
        assert metadata["exclusion_reason_counts"] == {
            ComparisonExclusionReason.IDENTITY_UNCERTAIN.value: 1,
            ComparisonExclusionReason.NO_DIGITAL_MATCH.value: 1,
        }
    engine.dispose()
