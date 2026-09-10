from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from grocery_data.app.domain.enums import Confidence
from grocery_data.app.domain.physical_price import (
    PhysicalIdentificationEvidence,
    PhysicalObservationAmendment,
    PhysicalObservationAmendmentKind,
    PhysicalObservationTimePrecision,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    physical_observation_payload_sha256,
)
from grocery_data.app.storage import (
    PhysicalObservationAmendmentHeadConflict,
    PhysicalObservationAmendmentRepository,
    PhysicalPriceObservationRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import (
    PhysicalObservationAmendmentModel,
    PhysicalStoreModel,
    PhysicalValidationSessionItemModel,
    PhysicalValidationSessionModel,
)

NOW = datetime(2026, 8, 30, 15, 0, tzinfo=UTC)
SESSION_ID = "completed-field-session"
STORE_ID = "physical-store-4123"


def _seed_completed_session(database_session) -> None:  # type: ignore[no-untyped-def]
    database_session.add(
        PhysicalStoreModel(
            id=STORE_ID,
            chain="hemkop",
            external_store_id="4123",
            name="Hemköp Karhögstorg",
            city="Lund",
            official_source="test",
            discovered_at=NOW,
            last_seen_at=NOW,
        )
    )
    database_session.flush()
    database_session.add(
        PhysicalValidationSessionModel(
            id=SESSION_ID,
            physical_store_id=STORE_ID,
            chain="hemkop",
            store_name="Hemköp Karhögstorg",
            status="completed",
            target_count=2,
            suggestion_set_sha256="a" * 64,
            started_at=NOW,
            completed_at=NOW + timedelta(hours=1),
        )
    )
    database_session.flush()
    for ordinal, item_id in enumerate(("late-item", "corrected-item"), start=1):
        database_session.add(
            PhysicalValidationSessionItemModel(
                id=item_id,
                session_id=SESSION_ID,
                ordinal=ordinal,
                stratum="regular",
                target_product_name=f"Product {ordinal}",
                candidate_set_sha256=str(ordinal) * 64,
            )
        )
    database_session.flush()


def _payload(*, item_id: str, observation_id: str, price: str) -> PhysicalPriceObservation:
    candidate_hash = "1" * 64 if item_id == "late-item" else "2" * 64
    return PhysicalPriceObservation(
        id=observation_id,
        physical_store_id=STORE_ID,
        product_name="Recovered shelf product",
        shelf_price=Decimal(price),
        observed_at=NOW + timedelta(minutes=30),
        confidence=Confidence.HIGH,
        validation_session_id=SESSION_ID,
        validation_session_item_id=item_id,
        price_semantics=PhysicalPriceSemantics.REGULAR,
        identity_status=PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH,
        identification_evidence=PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL,
        immutable_candidate_set_sha256=candidate_hash,
    )


def _amendment(
    *,
    amendment_id: str,
    payload: PhysicalPriceObservation,
    kind: PhysicalObservationAmendmentKind,
    client_request_id: str,
    base_observation_id: str | None = None,
    supersedes_amendment_id: str | None = None,
) -> PhysicalObservationAmendment:
    return PhysicalObservationAmendment(
        id=amendment_id,
        validation_session_id=SESSION_ID,
        validation_session_item_id=payload.validation_session_item_id or "",
        kind=kind,
        payload=payload,
        payload_sha256=physical_observation_payload_sha256(payload),
        base_observation_id=base_observation_id,
        supersedes_amendment_id=supersedes_amendment_id,
        observed_at=payload.observed_at,
        observed_at_precision=PhysicalObservationTimePrecision.VISIT_WINDOW,
        reason="Recovered from contemporaneous field notes",
        source="field_notes",
        reference="field-check:2026-08-30:karhogstorg",
        client_request_id=client_request_id,
        created_at=NOW + timedelta(hours=2),
    )


def test_append_only_amendment_chain_is_typed_idempotent_and_head_guarded() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as database_session:
            _seed_completed_session(database_session)
            repository = PhysicalObservationAmendmentRepository(database_session)

            late_payload = _payload(
                item_id="late-item",
                observation_id="late-observation",
                price="22.50",
            )
            late = _amendment(
                amendment_id="late-amendment",
                payload=late_payload,
                kind=PhysicalObservationAmendmentKind.LATE_CAPTURE,
                client_request_id="request-late-0001",
            )
            stored_late = repository.add_amendment(late)
            assert stored_late.payload == late_payload
            assert repository.add_amendment(late) == stored_late
            assert (
                repository.idempotency_lookup(
                    SESSION_ID,
                    "late-item",
                    "request-late-0001",
                )
                == stored_late
            )

            corrected_payload = _payload(
                item_id="late-item",
                observation_id="late-observation",
                price="23.00",
            )
            correction = _amendment(
                amendment_id="late-correction",
                payload=corrected_payload,
                kind=PhysicalObservationAmendmentKind.CORRECTION,
                client_request_id="request-late-0002",
                supersedes_amendment_id=stored_late.id,
            )
            stored_correction = repository.add_amendment(correction)
            assert repository.head_for_item("late-item") == stored_correction
            assert repository.amendments_for_session(SESSION_ID) == (
                stored_late,
                stored_correction,
            )

            stale_branch = _amendment(
                amendment_id="stale-branch",
                payload=corrected_payload,
                kind=PhysicalObservationAmendmentKind.CORRECTION,
                client_request_id="request-late-0003",
                supersedes_amendment_id=stored_late.id,
            )
            with pytest.raises(PhysicalObservationAmendmentHeadConflict):
                repository.add_amendment(stale_branch)

            row = database_session.get(
                PhysicalObservationAmendmentModel,
                stored_late.id,
            )
            assert row is not None
            row.reason = "rewrite"
            with pytest.raises(ValueError, match="append-only"):
                database_session.flush()
    finally:
        engine.dispose()


def test_first_correction_must_bind_the_existing_item_observation() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as database_session:
            _seed_completed_session(database_session)
            base = _payload(
                item_id="corrected-item",
                observation_id="base-observation",
                price="31.00",
            )
            PhysicalPriceObservationRepository(database_session).add(base)
            corrected = _payload(
                item_id="corrected-item",
                observation_id=base.id,
                price="32.00",
            )
            amendment = _amendment(
                amendment_id="base-correction",
                payload=corrected,
                kind=PhysicalObservationAmendmentKind.CORRECTION,
                client_request_id="request-base-0001",
                base_observation_id=base.id,
            )

            stored = PhysicalObservationAmendmentRepository(
                database_session
            ).add_amendment(amendment)

            assert stored.base_observation_id == base.id
            assert stored.payload.shelf_price == Decimal("32.00")
    finally:
        engine.dispose()
