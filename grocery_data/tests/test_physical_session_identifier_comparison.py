from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from grocery_data.__main__ import main as cli_main
from grocery_data.app.domain.enums import Chain, Confidence, SaleModel
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    ProductIdentifierEvidence,
    ProductIdentifierEvidenceSource,
    ProductIdentifierType,
    SessionItemIdentifierStatus,
)
from grocery_data.app.services.physical_validation_sessions import (
    build_physical_validation_session,
)
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import (
    PhysicalStoreModel,
    PhysicalValidationComparisonVersionModel,
    PhysicalValidationSessionCandidateModel,
    PhysicalValidationSessionItemIdentifierModel,
)
from grocery_data.app.storage.repositories import (
    PhysicalPriceObservationRepository,
    PhysicalValidationSessionRepository,
    ProductIdentifierEvidenceRepository,
)
from grocery_data.tests.test_physical_check_api import _client

NOW = datetime(2026, 8, 29, 12, tzinfo=UTC)
ENRICHED_GTIN = "7391737003437"


class _CandidateReader:
    def __init__(self, candidates: tuple[DigitalPriceCandidate, ...]) -> None:
        self.candidates = candidates

    def for_store(self, physical_store_id: str, *, limit: int):  # type: ignore[no-untyped-def]
        del limit
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.physical_store_id == physical_store_id
        )

    def for_observation(self, observation):  # type: ignore[no-untyped-def]
        return tuple(
            candidate
            for candidate in self.candidates
            if candidate.physical_store_id == observation.physical_store_id
        )

    def current_for_observation(self, observation):  # type: ignore[no-untyped-def]
        return self.for_observation(observation)


def _candidate(
    *,
    product_id: str = "selected-product",
    product_name: str = "Finbröd Skånskt",
    current_price: str = "29.95",
    sale_model: SaleModel = SaleModel.FIXED_PACKAGE,
) -> DigitalPriceCandidate:
    return DigitalPriceCandidate(
        physical_store_id="physical-hemkop-karhogstorg",
        grocery_context_id="own:hemkop:4123",
        source_provider="primat",
        source_snapshot_id="immutable-snapshot",
        observed_at=NOW,
        product_id=product_id,
        product_name=product_name,
        brand="Södervidinge",
        package_description=(
            "Viktvara" if sale_model is SaleModel.SOLD_BY_WEIGHT else "700 g"
        ),
        gtin=None,
        current_price=Decimal(current_price),
        comparison_price=(
            Decimal(current_price)
            if sale_model is SaleModel.SOLD_BY_WEIGHT
            else None
        ),
        comparison_unit=(
            "SEK/kg" if sale_model is SaleModel.SOLD_BY_WEIGHT else None
        ),
        sale_model=sale_model,
        common_product_score=Decimal(10),
    )


def _start(candidates: tuple[DigitalPriceCandidate, ...]):  # type: ignore[no-untyped-def]
    client, factory = _client()
    client.app.state.external_physical_price_candidate_reader = _CandidateReader(candidates)
    response = client.post(
        "/physical-check/sessions",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "target_sample_size": 1,
            "blind_capture": True,
        },
    )
    assert response.status_code == 201, response.text
    return client, factory, response.json()


def test_enriched_gtin_uses_exact_immutable_session_product_for_price_comparison() -> None:
    candidate = _candidate()
    client, factory, started = _start((candidate,))
    session_id = started["session"]["id"]
    item_id = started["items"][0]["id"]

    with factory() as database_session:
        identifier = database_session.get(
            PhysicalValidationSessionItemIdentifierModel,
            item_id,
        )
        assert identifier is not None
        identifier.target_external_product_id = "101230686_ST"
        identifier.target_store_external_id = "4123"
        evidence = ProductIdentifierEvidenceRepository(database_session).add(
            ProductIdentifierEvidence(
                id="finbread-detail-evidence",
                chain=Chain.HEMKOP,
                source_provider="primat",
                scope_key="4123",
                source_product_id=candidate.product_id,
                external_product_id="101230686_ST",
                identifier_type=ProductIdentifierType.GTIN,
                identifier_value=ENRICHED_GTIN,
                evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
                evidence_reference="raw:test-detail#ean",
                evidence_payload_sha256="a" * 64,
                observed_at=NOW,
                confidence=Confidence.HIGH,
            )
        )
        PhysicalValidationSessionRepository(database_session).record_identifier_resolution(
            session_id,
            item_id,
            status=SessionItemIdentifierStatus.KNOWN_GTIN,
            evidence_id=evidence.id,
            result="enriched",
        )
        frozen_before = database_session.scalar(
            select(PhysicalValidationSessionCandidateModel).where(
                PhysicalValidationSessionCandidateModel.session_item_id == item_id
            )
        )
        assert frozen_before is not None
        frozen_sha = frozen_before.candidate_sha256
        assert frozen_before.gtin is None
        database_session.commit()

    identity = client.get(
        f"/physical-check/sessions/{session_id}/items/{item_id}/identity",
        params={"gtin": ENRICHED_GTIN, "contract": "v2"},
    )
    assert identity.status_code == 200, identity.text
    assert identity.json()["status"] == "gtin_match"

    captured = client.post(
        f"/physical-check/sessions/{session_id}/items/{item_id}/observation",
        json={
            "gtin": ENRICHED_GTIN,
            "product_name": candidate.product_name,
            "shelf_price": "29.95",
            "price_semantics": "regular",
            "identity_status": "gtin_match",
            "identification_evidence": "gtin_verified",
            "observed_at": NOW.isoformat(),
        },
    )
    assert captured.status_code == 201, captured.text
    [comparison] = captured.json()["comparisons"]
    assert comparison["status"] == "match"
    assert comparison["match_method"] == "verified_session_product"
    assert comparison["product_id"] == candidate.product_id
    assert comparison["source_snapshot_id"] == candidate.source_snapshot_id
    assert comparison["digital_price"] == "29.95"
    assert comparison["observation_confidence"] == "high"

    report = client.get(
        f"/physical-check/sessions/{session_id}/report"
    )
    assert report.status_code == 200, report.text
    [reported] = report.json()["comparisons"]
    assert reported["status"] == "match"
    assert reported["match_method"] == "verified_session_product"
    assert reported["source_snapshot_id"] == candidate.source_snapshot_id

    with factory() as database_session:
        frozen_after = database_session.scalar(
            select(PhysicalValidationSessionCandidateModel).where(
                PhysicalValidationSessionCandidateModel.session_item_id == item_id
            )
        )
        assert frozen_after is not None
        assert frozen_after.gtin is None
        assert frozen_after.candidate_sha256 == frozen_sha
        assert frozen_after.current_price == candidate.current_price


def test_exact_session_target_beats_same_name_candidate_with_wrong_sale_model() -> None:
    selected = _candidate(
        product_id="a-selected-weight",
        product_name="Champinjoner",
        current_price="29.95",
        sale_model=SaleModel.SOLD_BY_WEIGHT,
    )
    wrong = _candidate(
        product_id="z-fixed-package",
        product_name="Champinjoner",
        current_price="48.95",
        sale_model=SaleModel.FIXED_PACKAGE,
    )
    client, _factory, started = _start((selected, wrong))
    item = started["items"][0]
    assert item["target_product_id"] == selected.product_id
    assert item["weight_item"] is True

    captured = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/observation",
        json={
            "gtin": None,
            "product_name": "Champinjoner",
            "shelf_price": "29.95",
            "comparison_unit": "SEK/kg",
            "price_semantics": "weight",
            "weight_price_type": "regular",
            "identity_status": "weight_item_no_gtin_required",
            "identification_evidence": "weight_source_product",
            "observed_at": NOW.isoformat(),
        },
    )

    assert captured.status_code == 201, captured.text
    [comparison] = captured.json()["comparisons"]
    assert comparison["status"] == "match"
    assert comparison["match_method"] == "verified_session_product"
    assert comparison["product_id"] == selected.product_id
    assert comparison["sale_model"] == SaleModel.SOLD_BY_WEIGHT.value
    assert comparison["digital_price"] == "29.95"


def test_true_gtin_mismatch_never_uses_verified_session_product_bridge() -> None:
    candidate = _candidate()
    client, factory, started = _start((candidate,))
    session_id = started["session"]["id"]
    item_id = started["items"][0]["id"]
    with factory() as database_session:
        identifier = database_session.get(
            PhysicalValidationSessionItemIdentifierModel,
            item_id,
        )
        assert identifier is not None
        identifier.target_external_product_id = "101230686_ST"
        identifier.target_store_external_id = "4123"
        evidence = ProductIdentifierEvidenceRepository(database_session).add(
            ProductIdentifierEvidence(
                id="mismatch-detail-evidence",
                chain=Chain.HEMKOP,
                source_provider="primat",
                scope_key="4123",
                source_product_id=candidate.product_id,
                external_product_id="101230686_ST",
                identifier_type=ProductIdentifierType.GTIN,
                identifier_value=ENRICHED_GTIN,
                evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
                evidence_reference="raw:test-detail#ean",
                observed_at=NOW,
                confidence=Confidence.HIGH,
            )
        )
        PhysicalValidationSessionRepository(database_session).record_identifier_resolution(
            session_id,
            item_id,
            status=SessionItemIdentifierStatus.KNOWN_GTIN,
            evidence_id=evidence.id,
            result="enriched",
        )
        database_session.commit()

    captured = client.post(
        f"/physical-check/sessions/{session_id}/items/{item_id}/observation",
        json={
            "gtin": "7310865004703",
            "product_name": candidate.product_name,
            "shelf_price": "29.95",
            "price_semantics": "regular",
            "identity_status": PhysicalProductIdentityStatus.GTIN_MISMATCH.value,
            "identification_evidence": PhysicalIdentificationEvidence.UNVERIFIED.value,
            "observed_at": NOW.isoformat(),
        },
    )

    assert captured.status_code == 201, captured.text
    [comparison] = captured.json()["comparisons"]
    assert comparison["status"] == "no_digital_match"
    assert comparison["digital_price"] is None
    assert comparison["match_method"] is None


def test_cli_report_reuses_enriched_session_target_without_mutating_candidate(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    database = tmp_path / "enriched-session-report.sqlite"
    database_url = f"sqlite+pysqlite:///{database.as_posix()}"
    engine = create_database_engine(database_url)
    create_schema(engine)
    factory = create_session_factory(engine)
    candidate = _candidate()
    with factory() as database_session:
        database_session.add(
            PhysicalStoreModel(
                id=candidate.physical_store_id,
                chain=Chain.HEMKOP.value,
                external_store_id="4123",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="22358",
                city="Lund",
                official_source="https://www.hemkop.se/butik/karhogstorg",
                discovered_at=NOW,
                last_seen_at=NOW,
                is_active=True,
                lifecycle_state="active",
            )
        )
        database_session.flush()
        validation_session, items = build_physical_validation_session(
            (candidate,),
            physical_store_id=candidate.physical_store_id,
            chain=Chain.HEMKOP.value,
            store_name="Hemköp Lund Karhögstorg",
            target_count=1,
            started_at=NOW,
        )
        repository = PhysicalValidationSessionRepository(database_session)
        repository.add(validation_session, items)
        [item] = items
        identifier = database_session.get(
            PhysicalValidationSessionItemIdentifierModel,
            item.id,
        )
        assert identifier is not None
        identifier.target_external_product_id = "101230686_ST"
        identifier.target_store_external_id = "4123"
        evidence = ProductIdentifierEvidenceRepository(database_session).add(
            ProductIdentifierEvidence(
                id="cli-detail-evidence",
                chain=Chain.HEMKOP,
                source_provider=candidate.source_provider,
                scope_key="4123",
                source_product_id=candidate.product_id,
                external_product_id="101230686_ST",
                identifier_type=ProductIdentifierType.GTIN,
                identifier_value=ENRICHED_GTIN,
                evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
                evidence_reference="raw:cli-detail#ean",
                observed_at=NOW,
                confidence=Confidence.HIGH,
            )
        )
        repository.record_identifier_resolution(
            validation_session.id,
            item.id,
            status=SessionItemIdentifierStatus.KNOWN_GTIN,
            evidence_id=evidence.id,
            result="enriched",
        )
        PhysicalPriceObservationRepository(database_session).add(
            PhysicalPriceObservation(
                id="cli-physical-observation",
                physical_store_id=candidate.physical_store_id,
                gtin=ENRICHED_GTIN,
                product_name=candidate.product_name,
                shelf_price=candidate.current_price,
                observed_at=NOW,
                confidence=Confidence.HIGH,
                validation_session_id=validation_session.id,
                validation_session_item_id=item.id,
                price_semantics=PhysicalPriceSemantics.REGULAR,
                identity_status=PhysicalProductIdentityStatus.GTIN_MATCH,
                identification_evidence=PhysicalIdentificationEvidence.GTIN_VERIFIED,
                immutable_candidate_set_sha256=item.candidate_set_sha256,
            )
        )
        repository.complete(
            validation_session.id,
            completed_at=NOW + timedelta(minutes=5),
        )
        database_session.commit()
    engine.dispose()

    monkeypatch.setenv("GROCERY_DATABASE_URL", database_url)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    assert (
        cli_main(
            [
                "physical-price-report",
                "--store",
                candidate.physical_store_id,
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    [comparison] = report["comparisons"]
    assert comparison["status"] == "match"
    assert comparison["match_method"] == "verified_session_product"
    assert comparison["source_snapshot_id"] == candidate.source_snapshot_id
    assert comparison["digital_price"] == "29.95"
    session_contract = report["completed_session_reports"][validation_session.id]
    assert session_contract["counts"] == {
        "raw_observations": 1,
        "identified_observations": 1,
        "digital_matches": 1,
        "comparable_comparisons": 1,
        "excluded_comparisons": 0,
    }
    assert session_contract["legacy_comparison"]["comparisons"][0]["status"] == "match"
    assert session_contract["semantic_v2_official"]["official"] is True
    assert session_contract["semantic_v2_official"]["comparable_denominator"] == 1
    assert session_contract["post_visit_diagnostics"] == []
    assert session_contract["v3_metadata"]["official_replaced_by_diagnostic"] is False
    assert report["comparisons"] == session_contract["legacy_comparison"]["comparisons"]
    verification_engine = create_database_engine(database_url)
    with create_session_factory(verification_engine)() as verification_session:
        assert (
            verification_session.scalar(
                select(func.count()).select_from(
                    PhysicalValidationComparisonVersionModel
                )
            )
            == 0
        )
    verification_engine.dispose()
