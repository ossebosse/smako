from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.community_evidence import (
    AssortmentConfidence,
    CommunityEvidenceSource,
    CommunityEvidenceSubmission,
    CommunityEvidenceType,
    CommunityPromotion,
    EvidenceVerificationStatus,
    ModerationDecision,
    PriceEvidenceConfidence,
)
from grocery_data.app.domain.identifiers import InvalidGtinError
from grocery_data.app.domain.promotion_pricing import (
    PromotionEligibility,
    PromotionMechanism,
)
from grocery_data.app.main import create_app
from grocery_data.app.services.community_receipts import (
    ReceiptIngestionRequest,
    ReceiptIngestionService,
    ReceiptLine,
    ReceiptRateLimitError,
)
from grocery_data.app.services.evidence_reconciler import EvidenceReconciler
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    CommunityEvidenceModerationEventModel,
    CommunityEvidenceObservationModel,
    CommunityEvidenceRepository,
    CommunityReceiptIngestionModel,
    PhysicalStoreModel,
    StoreContextLinkModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)

NOW = datetime(2026, 8, 31, 10, 0, tzinfo=UTC)
STORE_ID = "physical:hemkop:4123"
GTIN = "7391737003437"


@pytest.fixture
def runtime():
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id=STORE_ID,
                chain="hemkop",
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                city="Lund",
                official_source="fixture",
                discovered_at=NOW,
                last_seen_at=NOW,
            )
        )
        session.commit()
    yield engine, factory
    engine.dispose()


def submission(**overrides: object) -> CommunityEvidenceSubmission:
    values: dict[str, object] = {
        "evidence_type": CommunityEvidenceType.PRODUCT_FOUND,
        "evidence_source": CommunityEvidenceSource.BARCODE_SCAN,
        "anonymous_session_id": "anonymous-session-a",
        "idempotency_key": "request-0000000001",
        "observed_at": NOW,
        "chain": "hemkop",
        "physical_store_id": STORE_ID,
        "gtin": GTIN,
        "product_name": "Finbröd Skånskt",
    }
    values.update(overrides)
    return CommunityEvidenceSubmission.model_validate(values)


def test_exact_barcode_found_is_append_only_observed_available(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        created = repository.create(submission(), now=NOW)
        session.commit()
        assert created.observation.gtin == GTIN
        assert created.observation.physical_presence is True
        assert created.observation.store_identity_verified is True

        reconciled = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            source_supported_available=None,
            now=NOW,
        )
        assert reconciled.assortment_confidence is AssortmentConfidence.VERIFIED_RECENTLY_AVAILABLE
        with pytest.raises(ValueError, match="append-only"):
            created.observation.product_name = "mutated"
            session.flush()


def test_invalid_barcode_is_rejected_before_persistence(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        with pytest.raises(InvalidGtinError):
            CommunityEvidenceRepository(session).create(submission(gtin="7391737003438"), now=NOW)
        assert session.scalar(select(func.count(CommunityEvidenceObservationModel.id))) == 0


def test_unknown_gtin_can_be_reported_missing_from_app_without_fabricated_product(
    runtime,
) -> None:
    _engine, factory = runtime
    with factory() as session:
        row = (
            CommunityEvidenceRepository(session)
            .create(
                submission(
                    evidence_type=CommunityEvidenceType.PRODUCT_MISSING_FROM_APP,
                    physical_store_id=None,
                    source_product_id=None,
                    product_name="Okänd vara",
                    idempotency_key="request-0000000002",
                ),
                now=NOW,
            )
            .observation
        )
        session.commit()
        assert row.initial_status == EvidenceVerificationStatus.USER_REPORTED.value
        assert row.source_product_id is None
        assert row.physical_store_id is None


def test_one_not_found_report_is_advisory_not_global_out_of_stock(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        CommunityEvidenceRepository(session).create(
            submission(
                evidence_type=CommunityEvidenceType.PRODUCT_NOT_FOUND,
                evidence_source=CommunityEvidenceSource.MANUAL,
                idempotency_key="request-0000000003",
            ),
            now=NOW,
        )
        session.commit()
        reconciled = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            source_supported_available=True,
            now=NOW,
        )
        assert reconciled.assortment_confidence is AssortmentConfidence.USER_REPORTED_NOT_FOUND
        assert reconciled.advisory_only is True
        assert reconciled.source_supported_available is True
        assert any("does not remove" in text for text in reconciled.explanations)


def test_explicit_source_unavailable_has_priority_over_not_found_reports(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        CommunityEvidenceRepository(session).create(
            submission(
                evidence_type=CommunityEvidenceType.PRODUCT_NOT_FOUND,
                evidence_source=CommunityEvidenceSource.MANUAL,
                idempotency_key="request-source-unavailable-01",
            ),
            now=NOW,
        )
        session.commit()
        result = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            source_supported_available=False,
            now=NOW,
        )
        assert (
            result.assortment_confidence
            is AssortmentConfidence.SOURCE_REPORTED_UNAVAILABLE
        )


def test_exact_provider_store_id_resolves_but_context_id_does_not(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        exact = repository.create(
            submission(
                physical_store_id=None,
                source_provider_store_id="4123",
                idempotency_key="request-0000000004",
            ),
            now=NOW,
        ).observation
        unresolved = repository.create(
            submission(
                physical_store_id=None,
                source_provider_store_id="own:hemkop:4123",
                idempotency_key="request-0000000005",
            ),
            now=NOW,
        ).observation
        assert exact.physical_store_id == STORE_ID
        assert exact.store_identity_verified is True
        assert unresolved.physical_store_id is None
        assert unresolved.store_identity_verified is False
        assert unresolved.initial_status == EvidenceVerificationStatus.QUARANTINED.value


def test_verified_store_identity_uses_registry_facts_and_rejects_spoofed_context(
    runtime,
) -> None:
    _engine, factory = runtime
    other_store_id = "physical:hemkop:9999"
    conflicting_context = "own:hemkop:9999"
    with factory() as session:
        session.add(
            PhysicalStoreModel(
                id=other_store_id,
                chain="hemkop",
                external_store_id="9999",
                name="Hemköp Annan Butik",
                city="Lund",
                official_source="fixture",
                discovered_at=NOW,
                last_seen_at=NOW,
            )
        )
        session.add(
            StoreContextLinkModel(
                physical_store_id=other_store_id,
                grocery_context_id=conflicting_context,
                source_provider="own",
                source_channel="own",
                relation_type="exact_store",
                confidence="verified",
                basket_eligible=True,
                offers_only=False,
                linked_at=NOW,
                last_verified_at=NOW,
                is_active=True,
            )
        )
        session.commit()

        row = CommunityEvidenceRepository(session).create(
            submission(
                chain="ica",
                source_provider_store_id="spoofed-provider-id",
                store_display_name="Spoofed Store Name",
                grocery_context_id=conflicting_context,
                idempotency_key="spoofed-store-facts-0001",
            ),
            now=NOW,
        ).observation
        session.commit()

        assert row.store_identity_verified is True
        assert row.physical_store_id == STORE_ID
        assert row.chain == "hemkop"
        assert row.store_display_name == "Hemköp Lund Karhögstorg"
        assert row.source_provider_store_id == "4123"
        assert row.grocery_context_id is None


def test_verified_store_keeps_only_an_active_exact_context_link(runtime) -> None:
    _engine, factory = runtime
    context_id = "own:hemkop:4123"
    with factory() as session:
        session.add(
            StoreContextLinkModel(
                physical_store_id=STORE_ID,
                grocery_context_id=context_id,
                source_provider="own",
                source_channel="own",
                relation_type="exact_store",
                confidence="verified",
                basket_eligible=True,
                offers_only=False,
                linked_at=NOW,
                last_verified_at=NOW,
                is_active=True,
            )
        )
        session.commit()
        row = CommunityEvidenceRepository(session).create(
            submission(
                grocery_context_id=context_id,
                idempotency_key="verified-store-context-01",
            ),
            now=NOW,
        ).observation
        assert row.store_identity_verified is True
        assert row.grocery_context_id == context_id


def test_member_multibuy_and_price_disagreement_are_advisory(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        row = repository.create(
            submission(
                evidence_type=CommunityEvidenceType.LOCAL_PROMOTION,
                evidence_source=CommunityEvidenceSource.SHELF_PRICE,
                idempotency_key="request-0000000006",
                shelf_price=Decimal(10),
                price_unit="kr/st",
                promotion=CommunityPromotion(
                    eligibility=PromotionEligibility.MEMBER,
                    mechanism=PromotionMechanism.MULTIBUY,
                    required_quantity=3,
                    total_price=Decimal(30),
                    regular_price=Decimal("15.09"),
                ),
            ),
            now=NOW,
        ).observation
        session.commit()
        assert row.promotion_eligibility == "member"
        assert row.promotion_mechanism == "multibuy"
        assert row.promotion_required_quantity == 3
        assert row.promotion_total_price == Decimal(30)
        reconciled = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            source_price=Decimal("15.09"),
            source_price_unit="SEK/item",
            now=NOW,
        )
        assert reconciled.price_confidence is PriceEvidenceConfidence.CONFLICTING
        assert reconciled.source_price == Decimal("15.09")
        assert reconciled.observed_community_price_unit == "SEK/item"
        assert reconciled.price_basis_comparable is True
        assert session.scalar(select(func.count(CatalogSnapshotModel.id))) == 0


def test_duplicate_and_idempotent_submissions_do_not_append_extra_rows(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        first = repository.create(submission(), now=NOW)
        replay = repository.create(submission(), now=NOW + timedelta(minutes=1))
        duplicate = repository.create(
            submission(idempotency_key="different-request-0001"),
            now=NOW + timedelta(minutes=2),
        )
        assert replay.replayed is True
        assert duplicate.duplicate is True
        assert first.observation.id == replay.observation.id == duplicate.observation.id
        assert session.scalar(select(func.count(CommunityEvidenceObservationModel.id))) == 1


def test_multiple_independent_reports_and_decay(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        for index, actor in enumerate(("session-one", "session-two"), start=1):
            repository.create(
                submission(
                    evidence_source=CommunityEvidenceSource.MANUAL,
                    anonymous_session_id=actor,
                    idempotency_key=f"independent-request-{index:04d}",
                    observed_at=NOW - timedelta(days=8),
                ),
                now=NOW,
            )
        session.commit()
        reconciled = EvidenceReconciler(
            session,
            availability_half_life_hours=24,
            recent_hours=24,
        ).reconcile(physical_store_id=STORE_ID, gtin=GTIN, now=NOW)
        assert reconciled.independent_reporters == 2
        assert reconciled.assortment_confidence is AssortmentConfidence.UNKNOWN
        assert reconciled.positive_presence_weight < 0.01
        assert any("historical" in text for text in reconciled.explanations)


def test_recent_independent_presence_reports_can_be_probable(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        for index, actor in enumerate(("recent-one", "recent-two"), start=1):
            repository.create(
                submission(
                    evidence_source=CommunityEvidenceSource.MANUAL,
                    anonymous_session_id=actor,
                    idempotency_key=f"recent-presence-{index:04d}",
                    observed_at=NOW - timedelta(hours=1),
                ),
                now=NOW,
            )
        session.commit()
        reconciled = EvidenceReconciler(
            session,
            availability_half_life_hours=168,
            recent_hours=24,
        ).reconcile(physical_store_id=STORE_ID, gtin=GTIN, now=NOW)
        assert reconciled.assortment_confidence is AssortmentConfidence.PROBABLE_AVAILABLE


def test_receipt_multibuy_uses_unit_price_not_paid_line_total(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        CommunityEvidenceRepository(session).create(
            submission(
                evidence_type=CommunityEvidenceType.RECEIPT_PURCHASE,
                evidence_source=CommunityEvidenceSource.RECEIPT,
                anonymous_session_id="receipt-multibuy",
                idempotency_key="receipt-multibuy-0001",
                gtin=None,
                source_product_id="receipt-product-multibuy",
                shelf_price=Decimal(30),
                unit_price=Decimal(10),
                quantity=Decimal(3),
                price_unit="SEK/item",
            ),
            now=NOW,
        )
        session.commit()
        reconciled = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            source_product_id="receipt-product-multibuy",
            source_price=Decimal(10),
            source_price_unit="kr/st",
            now=NOW,
        )
        assert reconciled.observed_community_price == Decimal(10)
        assert reconciled.observed_community_price_unit == "SEK/item"
        assert reconciled.price_confidence is PriceEvidenceConfidence.RECEIPT_VERIFIED
        assert reconciled.price_conflict is False


def test_receipt_multibuy_total_without_unit_price_is_incomplete(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        CommunityEvidenceRepository(session).create(
            submission(
                evidence_type=CommunityEvidenceType.RECEIPT_PURCHASE,
                evidence_source=CommunityEvidenceSource.RECEIPT,
                anonymous_session_id="receipt-total-only",
                idempotency_key="receipt-total-only-0001",
                gtin=None,
                source_product_id="receipt-product-total-only",
                shelf_price=Decimal(30),
                quantity=Decimal(3),
            ),
            now=NOW,
        )
        session.commit()
        reconciled = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            source_product_id="receipt-product-total-only",
            source_price=Decimal(10),
            source_price_unit="SEK/item",
            now=NOW,
        )
        assert reconciled.observed_community_price is None
        assert reconciled.price_confidence is PriceEvidenceConfidence.UNKNOWN
        assert reconciled.price_evidence_incomplete is True
        assert reconciled.excluded_price_reports == 1
        assert reconciled.price_conflict is False


def test_mixed_price_units_are_never_merged_or_compared(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        repository.create(
            submission(
                evidence_type=CommunityEvidenceType.PRICE_DIFFERENCE,
                evidence_source=CommunityEvidenceSource.SHELF_PRICE,
                anonymous_session_id="item-price-actor",
                idempotency_key="mixed-unit-item-0001",
                shelf_price=Decimal(20),
                price_unit="kr/st",
            ),
            now=NOW,
        )
        repository.create(
            submission(
                evidence_type=CommunityEvidenceType.PRICE_DIFFERENCE,
                evidence_source=CommunityEvidenceSource.SHELF_PRICE,
                anonymous_session_id="weight-price-actor",
                idempotency_key="mixed-unit-weight-01",
                shelf_price=Decimal(100),
                price_unit="kr/kg",
            ),
            now=NOW,
        )
        session.commit()

        untyped = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            now=NOW,
        )
        assert untyped.observed_community_price is None
        assert untyped.price_confidence is PriceEvidenceConfidence.UNKNOWN
        assert untyped.price_evidence_incomplete is True
        assert untyped.price_conflict is False

        item_basis = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            source_price=Decimal(20),
            source_price_unit="SEK/item",
            now=NOW,
        )
        assert item_basis.observed_community_price == Decimal(20)
        assert item_basis.observed_community_price_unit == "SEK/item"
        assert item_basis.considered_price_reports == 1
        assert item_basis.excluded_price_reports == 1
        assert item_basis.price_basis_comparable is True
        assert item_basis.price_conflict is False

        incompatible = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            source_price=Decimal(20),
            source_price_unit="SEK/item",
            price_unit="SEK/kg",
            now=NOW,
        )
        assert incompatible.observed_community_price == Decimal(100)
        assert incompatible.price_basis_comparable is False
        assert incompatible.price_confidence is PriceEvidenceConfidence.UNKNOWN
        assert incompatible.price_conflict is False


def test_promotion_corroboration_requires_same_recent_contract(runtime) -> None:
    _engine, factory = runtime
    promotion = CommunityPromotion(
        eligibility=PromotionEligibility.MEMBER,
        mechanism=PromotionMechanism.MULTIBUY,
        required_quantity=3,
        total_price=Decimal(30),
    )
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        for index, actor in enumerate(("promo-one", "promo-two"), start=1):
            repository.create(
                submission(
                    evidence_type=CommunityEvidenceType.LOCAL_PROMOTION,
                    evidence_source=CommunityEvidenceSource.SHELF_PRICE,
                    anonymous_session_id=actor,
                    idempotency_key=f"same-promotion-{index:04d}",
                    promotion=promotion,
                ),
                now=NOW,
            )
        session.commit()
        corroborated = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            now=NOW,
        )
        assert corroborated.promotion_confidence is PriceEvidenceConfidence.CORROBORATED
        assert corroborated.promotion_contract_conflict is False

        repository.create(
            submission(
                evidence_type=CommunityEvidenceType.LOCAL_PROMOTION,
                evidence_source=CommunityEvidenceSource.SHELF_PRICE,
                anonymous_session_id="promo-three",
                idempotency_key="different-promotion-01",
                promotion=CommunityPromotion(
                    eligibility=PromotionEligibility.MEMBER,
                    mechanism=PromotionMechanism.MULTIBUY,
                    required_quantity=2,
                    total_price=Decimal(25),
                ),
            ),
            now=NOW,
        )
        session.commit()
        conflicting = EvidenceReconciler(session).reconcile(
            physical_store_id=STORE_ID,
            gtin=GTIN,
            now=NOW,
        )
        assert conflicting.promotion_confidence is PriceEvidenceConfidence.CONFLICTING
        assert conflicting.promotion_contract_conflict is True


def test_receipt_exact_gtin_is_structured_and_raw_content_is_discarded(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        row = ReceiptIngestionService(session).ingest(
            ReceiptIngestionRequest(
                anonymous_session_id="receipt-session",
                retailer="hemkop",
                physical_store_id=STORE_ID,
                raw_text="Hemköp\n2026-08-31 12:30\nFINBRÖD  32,00\nKORT 1234",
                lines=(
                    ReceiptLine(
                        description="Finbröd",
                        paid_price=Decimal(32),
                        gtin=GTIN,
                    ),
                ),
            ),
            now=NOW,
        )
        session.commit()
        assert row.status == "PARSED_STRUCTURED"
        assert row.raw_retained is False
        assert row.raw_discarded_at == NOW
        assert row.raw_sha256 is not None
        assert "KORT" not in str(row.parsed_lines)
        assert row.parsed_lines[0]["match_confidence"] == "EXACT_GTIN"


def test_hemkop_receipt_text_is_beta_and_never_claims_exact_identity(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        row = ReceiptIngestionService(session).ingest(
            ReceiptIngestionRequest(
                anonymous_session_id="receipt-session",
                retailer="Hemköp",
                physical_store_id=STORE_ID,
                raw_text="HEMKÖP\n31-08-2026 14:25\nFALUKORV  36,95\nTOTALT  36,95",
            ),
            now=NOW,
        )
        assert row.status == "PARSED"
        assert row.purchase_observed_at == datetime(2026, 8, 31, 12, 25, tzinfo=UTC)
        assert row.parsed_lines[0]["match_confidence"] == "UNMATCHED"


def test_unmatched_receipt_retry_is_idempotent_before_rate_limit(runtime) -> None:
    _engine, factory = runtime
    request = ReceiptIngestionRequest(
        anonymous_session_id="unmatched-receipt-session",
        retailer="unsupported-retailer",
        physical_store_id=STORE_ID,
        raw_text="UNSUPPORTED RECEIPT CONTENT\nNO PARSABLE LINES",
    )
    with factory() as session:
        service = ReceiptIngestionService(session)
        first = service.ingest(request, now=NOW, max_receipts_per_hour=1)
        retry = service.ingest(
            request,
            now=NOW + timedelta(minutes=1),
            max_receipts_per_hour=1,
        )
        assert first.id == retry.id
        assert first.status == "UNSUPPORTED_RECEIPT_FORMAT"
        assert session.scalar(select(func.count(CommunityReceiptIngestionModel.id))) == 1

        with pytest.raises(ReceiptRateLimitError):
            service.ingest(
                request.model_copy(update={"raw_text": "A DIFFERENT UNSUPPORTED RECEIPT"}),
                now=NOW + timedelta(minutes=2),
                max_receipts_per_hour=1,
            )
        assert session.scalar(select(func.count(CommunityReceiptIngestionModel.id))) == 1


def test_moderation_is_append_only_and_effective_status_uses_latest(runtime) -> None:
    _engine, factory = runtime
    with factory() as session:
        repository = CommunityEvidenceRepository(session)
        evidence = repository.create(submission(), now=NOW).observation
        repository.moderate(
            evidence.id,
            ModerationDecision(
                status=EvidenceVerificationStatus.VALID,
                reason="Receipt and barcode checked",
                idempotency_key="moderation-request-0001",
            ),
            now=NOW,
        )
        repository.moderate(
            evidence.id,
            ModerationDecision(
                status=EvidenceVerificationStatus.SUPERSEDED,
                reason="Newer evidence exists",
                idempotency_key="moderation-request-0002",
            ),
            now=NOW + timedelta(minutes=1),
        )
        assert repository.current_status(evidence.id) is EvidenceVerificationStatus.SUPERSEDED
        assert session.scalar(select(func.count(CommunityEvidenceModerationEventModel.id))) == 2


def test_api_submission_receipt_metrics_and_source_tables_unchanged(runtime) -> None:
    _engine, factory = runtime
    api_observed_at = datetime.now(tz=UTC)
    settings = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=Path("raw_snapshots"),
        user_agent="test",
    )
    app = create_app(session_factory=factory, settings=settings)
    app.state.community_evidence_settings = settings
    with TestClient(app) as client:
        response = client.post(
            "/api/community-evidence",
            json=submission().model_dump(mode="json"),
        )
        assert response.status_code == 201, response.text
        assert response.json()["store_identity_verified"] is True
        metrics = client.get("/api/community-evidence/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["total"] == 1
        store_options = client.get(
            "/api/community-evidence/store-options",
            params={"city": "Lund"},
        )
        assert store_options.status_code == 200
        assert store_options.json() == [
            {
                "id": STORE_ID,
                "chain": "hemkop",
                "external_store_id": "4123",
                "name": "Hemköp Lund Karhögstorg",
                "address": None,
                "postal_code": None,
                "city": "Lund",
            }
        ]
        assert client.get("/api/community-evidence").status_code == 503

        receipt = client.post(
            "/api/community-evidence/receipt",
            json={
                "anonymous_session_id": "receipt-api-session",
                "retailer": "hemkop",
                "physical_store_id": STORE_ID,
                "purchase_observed_at": api_observed_at.isoformat(),
                "lines": [
                    {
                        "description": "Finbröd",
                        "quantity": "1",
                        "paid_price": "32.00",
                        "gtin": GTIN,
                    }
                ],
            },
        )
        assert receipt.status_code == 201, receipt.text
        assert receipt.json()["raw_retained"] is False
        assert len(receipt.json()["evidence_ids"]) == 1
        receipt_retry = client.post(
            "/api/community-evidence/receipt",
            json={
                "anonymous_session_id": "receipt-api-session",
                "retailer": "hemkop",
                "physical_store_id": STORE_ID,
                "purchase_observed_at": api_observed_at.isoformat(),
                "lines": [
                    {
                        "description": "Finbröd",
                        "quantity": "1",
                        "paid_price": "32.00",
                        "gtin": GTIN,
                    }
                ],
            },
        )
        assert receipt_retry.status_code == 201, receipt_retry.text
        assert receipt_retry.json()["id"] == receipt.json()["id"]
        assert receipt_retry.json()["evidence_ids"] == receipt.json()["evidence_ids"]

        multibuy_receipt = client.post(
            "/api/community-evidence/receipt",
            json={
                "anonymous_session_id": "receipt-api-multibuy",
                "retailer": "hemkop",
                "physical_store_id": STORE_ID,
                "purchase_observed_at": api_observed_at.isoformat(),
                "lines": [
                    {
                        "description": "Couscous 3-pack",
                        "quantity": "3",
                        "paid_price": "30.00",
                        "unit_price": "10.00",
                        "gtin": "7311043007851",
                    }
                ],
            },
        )
        assert multibuy_receipt.status_code == 201, multibuy_receipt.text
        reconciled = client.get(
            "/api/community-evidence/reconcile",
            params={
                "physical_store_id": STORE_ID,
                "gtin": "7311043007851",
                "source_price": "10.00",
                "source_price_unit": "kr/st",
            },
        )
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["observed_community_price"] == "10.000000"
        assert reconciled.json()["observed_community_price_unit"] == "SEK/item"
        assert reconciled.json()["price_basis_comparable"] is True
        assert reconciled.json()["price_conflict"] is False
    with factory() as session:
        assert session.scalar(select(func.count(CatalogSnapshotModel.id))) == 0


def test_receipt_api_rate_limits_new_unmatched_payloads_but_allows_retry(runtime) -> None:
    _engine, factory = runtime
    settings = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=Path("raw_snapshots"),
        user_agent="test",
        community_evidence_max_reports_per_hour=1,
    )
    app = create_app(session_factory=factory, settings=settings)
    app.state.community_evidence_settings = settings
    payload = {
        "anonymous_session_id": "unmatched-api-session",
        "retailer": "unsupported-retailer",
        "physical_store_id": STORE_ID,
        "raw_text": "UNSUPPORTED RECEIPT WITH NO MATCHED LINES",
    }
    with TestClient(app) as client:
        first = client.post("/api/community-evidence/receipt", json=payload)
        assert first.status_code == 201, first.text
        assert first.json()["evidence_ids"] == []

        retry = client.post("/api/community-evidence/receipt", json=payload)
        assert retry.status_code == 201, retry.text
        assert retry.json()["id"] == first.json()["id"]

        limited = client.post(
            "/api/community-evidence/receipt",
            json={**payload, "raw_text": "A DIFFERENT UNSUPPORTED RECEIPT"},
        )
        assert limited.status_code == 429
        assert "kvitton" in limited.json()["detail"]

    with factory() as session:
        rows = list(session.scalars(select(CommunityReceiptIngestionModel)))
        assert len(rows) == 1
        assert rows[0].raw_retained is False
        assert "UNSUPPORTED RECEIPT" not in str(rows[0].parsed_lines)
