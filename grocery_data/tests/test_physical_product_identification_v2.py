from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import delete, select

from grocery_data.app.domain.enums import Chain, Confidence, SaleModel
from grocery_data.app.domain.identifiers import InvalidGtinError, normalize_gtin
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentificationEvidence,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalProductIdentityStatus,
    ProductIdentifierEvidence,
    ProductIdentifierEvidenceSource,
    ProductIdentifierType,
    ShelfIdentifierEvidence,
)
from grocery_data.app.services.physical_identifier_enrichment import (
    IdentifierEnrichmentResult,
)
from grocery_data.app.services.physical_price_validation import (
    PhysicalPriceValidationService,
    build_accuracy_report,
)
from grocery_data.app.storage.models import (
    PhysicalIdentifierPreparationModel,
    PhysicalObservationV2EvidenceModel,
    PhysicalValidationSessionCandidateModel,
    PhysicalValidationSessionItemIdentifierModel,
    ShelfIdentifierEvidenceModel,
)
from grocery_data.app.storage.repositories import ProductIdentifierEvidenceRepository
from grocery_data.tests.test_physical_check_api import NOW, _client

FINBREAD_GTIN = "7391737003437"
OTHER_GTIN = "7310865004703"
BRUSHPEN_GTIN = "7340083462016"


class _OneCandidateReader:
    def __init__(self, candidate: DigitalPriceCandidate) -> None:
        self.candidate = candidate

    def for_store(self, physical_store_id: str, *, limit: int):  # type: ignore[no-untyped-def]
        del limit
        return (
            (self.candidate,)
            if self.candidate.physical_store_id == physical_store_id
            else ()
        )

    def for_observation(self, observation):  # type: ignore[no-untyped-def]
        del observation
        return (self.candidate,)

    def current_for_observation(self, observation):  # type: ignore[no-untyped-def]
        return self.for_observation(observation)


def _candidate(*, gtin: str | None = None, weight: bool = False) -> DigitalPriceCandidate:
    return DigitalPriceCandidate(
        physical_store_id="physical-hemkop-karhogstorg",
        grocery_context_id="own:hemkop:4123",
        source_provider="primat",
        source_snapshot_id="snapshot-v2",
        observed_at=NOW,
        product_id="finbread-product",
        product_name="Finbröd Skånskt",
        brand="Södervidinge",
        category="Bröd",
        package_description="700 g" if not weight else "375 g",
        gtin=gtin,
        current_price=Decimal("29.95"),
        regular_price=Decimal("46.95") if weight else Decimal("29.95"),
        comparison_price=Decimal("29.95") if weight else None,
        comparison_unit="SEK/kg" if weight else None,
        sale_model=SaleModel.SOLD_BY_WEIGHT if weight else SaleModel.FIXED_PACKAGE,
        common_product_score=Decimal(10),
    )


def _start_session(*, candidate: DigitalPriceCandidate):  # type: ignore[no-untyped-def]
    client, factory = _client()
    client.app.state.external_physical_price_candidate_reader = _OneCandidateReader(candidate)
    response = client.post(
        "/physical-check/sessions",
        json={
            "physical_store_id": candidate.physical_store_id,
            "target_sample_size": 1,
            "blind_capture": True,
        },
    )
    assert response.status_code == 201, response.text
    return client, factory, response.json()


def test_finbread_gtin_is_checksum_valid_but_unknown_source_is_not_no_match() -> None:
    client, _factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]

    response = client.get(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/identity",
        params={"gtin": FINBREAD_GTIN, "contract": "v2"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["scanner_status"] == "success"
    assert body["status"] == "gtin_not_known_by_source"
    assert body["lookup_status"] == "unknown_to_source"
    assert body["status"] != "no_match"
    assert body["digital_price_hidden"] is True

    capture = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/observation",
        json={
            "gtin": FINBREAD_GTIN,
            "product_name": "Finbröd Skånskt",
            "shelf_price": "29.95",
            "price_semantics": "regular",
            "identity_status": "gtin_not_known_by_source",
            "identification_evidence": "source_product_manual",
            "observed_at": NOW.isoformat(),
        },
    )
    assert capture.status_code == 201, capture.text
    assert capture.json()["observation"]["identity_status"] == (
        "gtin_not_known_by_source"
    )
    assert capture.json()["observation"]["identification_evidence"] == (
        "source_product_manual"
    )
    assert capture.json()["comparisons"][0]["match_method"] == (
        "verified_session_product"
    )
    assert capture.json()["observation"]["confidence"] == "medium"


def test_current_mobile_v2_capture_payload_is_accepted_by_current_contract() -> None:
    client, _factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]

    assert started["physical_check_contract"] == "product-identification-v2"
    response = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/observation",
        json={
            "gtin": None,
            "product_name": "Finbröd Skånskt",
            "shelf_price": "29.95",
            "price_semantics": "regular",
            "identity_status": "manual_exact_match",
            "identification_evidence": "source_product_manual",
            "regular_shelf_price": None,
            "weight_price_type": None,
            "comparison_price": None,
            "comparison_unit": None,
            "multibuy_quantity": None,
            "multibuy_total_price": None,
            "promotion_text": None,
            "notes": None,
            "client_request_id": "field-request-12345678",
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["observation"]["identity_status"] == "manual_exact_match"


def test_legacy_session_identifier_state_is_backfilled_from_unanimous_candidate() -> None:
    client, factory, started = _start_session(candidate=_candidate())
    session_id = started["session"]["id"]
    item_id = started["items"][0]["id"]
    with factory() as database_session:
        database_session.execute(
            delete(PhysicalIdentifierPreparationModel).where(
                PhysicalIdentifierPreparationModel.validation_session_id == session_id
            )
        )
        database_session.execute(
            delete(PhysicalValidationSessionItemIdentifierModel).where(
                PhysicalValidationSessionItemIdentifierModel.session_item_id == item_id
            )
        )
        database_session.commit()

    response = client.get(f"/physical-check/sessions/{session_id}")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["physical_check_contract"] == "product-identification-v2"
    [item] = body["items"]
    assert item["target_product_id"] == "finbread-product"
    assert item["target_source_provider"] == "primat"
    assert item["target_grocery_context_id"] == "own:hemkop:4123"
    assert item["target_sale_model"] == "fixed_package"
    assert item["identifier_status"] == "unknown_gtin"
    assert body["identifier_preparation"]["target_products"] == 1
    with factory() as database_session:
        assert (
            database_session.get(PhysicalValidationSessionItemIdentifierModel, item_id)
            is not None
        )
        assert database_session.get(PhysicalIdentifierPreparationModel, session_id) is not None


def test_legacy_session_never_selects_first_conflicting_candidate() -> None:
    client, factory, started = _start_session(candidate=_candidate())
    session_id = started["session"]["id"]
    item_id = started["items"][0]["id"]
    with factory() as database_session:
        original = database_session.scalar(
            select(PhysicalValidationSessionCandidateModel).where(
                PhysicalValidationSessionCandidateModel.session_item_id == item_id
            )
        )
        assert original is not None
        database_session.add(
            PhysicalValidationSessionCandidateModel(
                id="legacy-conflicting-candidate",
                session_item_id=item_id,
                physical_store_id=original.physical_store_id,
                grocery_context_id=original.grocery_context_id,
                source_provider=original.source_provider,
                source_snapshot_id=original.source_snapshot_id,
                observed_at=original.observed_at,
                product_id="another-product",
                product_name=original.product_name,
                brand=original.brand,
                category=original.category,
                package_description="Viktvara",
                gtin=None,
                current_price=original.current_price,
                regular_price=original.regular_price,
                member_price=original.member_price,
                comparison_price=Decimal("29.95"),
                comparison_unit="SEK/kg",
                promotion_type=original.promotion_type,
                member_only=original.member_only,
                multibuy_quantity=original.multibuy_quantity,
                multibuy_total_price=original.multibuy_total_price,
                sale_model=SaleModel.SOLD_BY_WEIGHT.value,
                common_product_score=original.common_product_score,
                recent_price_change=original.recent_price_change,
                candidate_sha256="b" * 64,
            )
        )
        database_session.execute(
            delete(PhysicalIdentifierPreparationModel).where(
                PhysicalIdentifierPreparationModel.validation_session_id == session_id
            )
        )
        database_session.execute(
            delete(PhysicalValidationSessionItemIdentifierModel).where(
                PhysicalValidationSessionItemIdentifierModel.session_item_id == item_id
            )
        )
        database_session.commit()

    response = client.get(f"/physical-check/sessions/{session_id}")

    assert response.status_code == 200, response.text
    [item] = response.json()["items"]
    assert item["target_product_id"] is None
    assert item["target_source_provider"] is None
    assert item["target_grocery_context_id"] is None
    assert item["target_sale_model"] == "unknown"
    assert item["weight_item"] is False
    assert item["identifier_enrichment_available"] is False


def test_known_gtin_matches_and_different_gtin_is_explicit_mismatch() -> None:
    client, _factory, started = _start_session(candidate=_candidate(gtin=FINBREAD_GTIN))
    item = started["items"][0]
    url = (
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/identity"
    )

    matched = client.get(url, params={"gtin": FINBREAD_GTIN, "contract": "v2"})
    mismatched = client.get(url, params={"gtin": OTHER_GTIN, "contract": "v2"})

    assert matched.json()["status"] == "gtin_match"
    assert matched.json()["identification_evidence"] == "gtin_verified"
    assert mismatched.json()["status"] == "gtin_mismatch"
    assert mismatched.json()["lookup_status"] == "mismatch"


def test_cached_product_detail_gtin_hydrates_target_across_product_id_churn() -> None:
    client, factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]
    evidence = ProductIdentifierEvidence(
        id=uuid4().hex,
        chain=Chain.HEMKOP,
        source_provider="own",
        scope_key="4123",
        source_product_id="prior-snapshot-product-id",
        external_product_id="101270305_ST",
        identifier_type=ProductIdentifierType.GTIN,
        identifier_value=BRUSHPEN_GTIN,
        evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
        evidence_reference="raw:test-brushpen-detail#ean",
        observed_at=NOW,
        confidence=Confidence.HIGH,
    )
    with factory() as database_session:
        repository = ProductIdentifierEvidenceRepository(database_session)
        repository.add(evidence)
        [cached] = repository.for_product(
            chain=Chain.HEMKOP,
            source_provider="own",
            scope_key="4123",
            external_product_id="101270305_ST",
        )
        identifier = database_session.get(
            PhysicalValidationSessionItemIdentifierModel,
            item["id"],
        )
        assert identifier is not None
        identifier.target_product_id = "current-snapshot-product-id"
        identifier.target_source_provider = "own"
        identifier.target_grocery_context_id = "own:hemkop:4123"
        identifier.target_external_product_id = "101270305_ST"
        identifier.target_store_external_id = "4123"
        identifier.identifier_status = "known_gtin"
        identifier.identifier_evidence_id = cached.id
        database_session.commit()
        frozen_candidate = database_session.scalar(
            select(PhysicalValidationSessionCandidateModel).where(
                PhysicalValidationSessionCandidateModel.session_item_id == item["id"]
            )
        )
        assert frozen_candidate is not None
        assert frozen_candidate.gtin is None

    refreshed = client.get(f"/physical-check/sessions/{started['session']['id']}")
    assert refreshed.status_code == 200, refreshed.text
    [hydrated] = refreshed.json()["items"]
    assert hydrated["target_product_id"] == "current-snapshot-product-id"
    assert hydrated["target_gtin"] == BRUSHPEN_GTIN
    assert hydrated["identifier_status"] == "known_gtin"

    matched = client.get(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/identity",
        params={"gtin": BRUSHPEN_GTIN, "contract": "v2"},
    )

    assert matched.status_code == 200, matched.text
    assert matched.json()["status"] == "gtin_match"
    assert matched.json()["lookup_status"] == "match"
    assert matched.json()["expected_gtin"] == BRUSHPEN_GTIN
    assert matched.json()["identification_evidence"] == "gtin_verified"


def test_v2_identity_and_capture_reject_checksum_invalid_gtin() -> None:
    client, _factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]
    url = (
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}"
    )

    identity = client.get(
        f"{url}/identity",
        params={"gtin": "7391737003438", "contract": "v2"},
    )
    capture = client.post(
        f"{url}/observation",
        json={
            "gtin": "7391737003438",
            "product_name": "Finbröd Skånskt",
            "shelf_price": "29.95",
            "price_semantics": "regular",
            "identity_status": "gtin_not_known_by_source",
            "identification_evidence": "source_product_manual",
            "observed_at": NOW.isoformat(),
        },
    )

    assert identity.status_code == 422
    assert "INVALID_GTIN" in identity.text
    assert capture.status_code == 422
    assert "INVALID_GTIN" in capture.text


def test_weight_item_needs_no_gtin_and_persists_sek_per_kg_semantics() -> None:
    client, factory, started = _start_session(candidate=_candidate(weight=True))
    item = started["items"][0]

    assert item["weight_item"] is True
    assert item["barcode_required"] is False
    assert item["display_package"] == "Viktvara / kr per kg"
    response = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/observation",
        json={
            "product_name": "Finbröd Skånskt",
            "shelf_price": "29.95",
            "regular_shelf_price": "46.95",
            "comparison_unit": "SEK/kg",
            "price_semantics": "weight",
            "weight_price_type": "sale",
            "identity_status": "weight_item_no_gtin_required",
            "identification_evidence": "weight_source_product",
            "observed_at": NOW.isoformat(),
        },
    )

    assert response.status_code == 201, response.text
    observation = response.json()["observation"]
    assert observation["gtin"] is None
    assert observation["shelf_price"] == "29.95"
    assert observation["comparison_unit"] == "SEK/kg"
    assert observation["regular_shelf_price"] == "46.95"
    assert observation["weight_price_type"] == "sale"
    assert observation["promotion_type"] == "sale_price"
    with factory() as session:
        v2 = session.get(PhysicalObservationV2EvidenceModel, observation["id"])
        assert v2 is not None
        assert v2.identification_evidence == "weight_source_product"


def test_fixed_package_cannot_be_captured_as_weight_item() -> None:
    client, _factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]

    response = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/observation",
        json={
            "product_name": "Finbröd Skånskt",
            "shelf_price": "29.95",
            "comparison_unit": "SEK/kg",
            "price_semantics": "weight",
            "identity_status": "weight_item_no_gtin_required",
            "identification_evidence": "weight_source_product",
        },
    )

    assert response.status_code == 422
    assert "verified weight product" in response.text


def test_identifier_registry_cache_and_conflicting_gtin_are_visible() -> None:
    _client_instance, factory = _client()
    with factory() as session:
        repository = ProductIdentifierEvidenceRepository(session)
        for gtin in (FINBREAD_GTIN, OTHER_GTIN):
            repository.add(
                ProductIdentifierEvidence(
                    id=uuid4().hex,
                    chain=Chain.HEMKOP,
                    source_provider="own",
                    scope_key="4123",
                    source_product_id="source-product-id",
                    external_product_id="101230686_ST",
                    identifier_type=ProductIdentifierType.GTIN,
                    identifier_value=gtin,
                    evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
                    evidence_reference=f"raw:test#{gtin}",
                    observed_at=datetime.now(tz=UTC),
                    confidence=Confidence.HIGH,
                )
            )
        session.commit()

        cached = repository.for_product(
            chain=Chain.HEMKOP,
            source_provider="own",
            scope_key="4123",
            external_product_id="101230686_ST",
        )
        assert {row.identifier_value for row in cached} == {
            FINBREAD_GTIN,
            OTHER_GTIN,
        }
        assert len(repository.resolve_gtin(chain=Chain.HEMKOP, gtin=FINBREAD_GTIN)) == 1


class _SuccessfulEnricher:
    def __init__(self) -> None:
        self.calls = 0

    async def enrich(self, target):  # type: ignore[no-untyped-def]
        self.calls += 1
        return IdentifierEnrichmentResult(
            evidence=ProductIdentifierEvidence(
                id=uuid4().hex,
                chain=Chain.HEMKOP,
                source_provider="own",
                scope_key=target.store_external_id,
                source_product_id=target.source_product_id,
                external_product_id=target.external_product_id,
                identifier_type=ProductIdentifierType.GTIN,
                identifier_value=FINBREAD_GTIN,
                evidence_source=ProductIdentifierEvidenceSource.PRODUCT_DETAIL,
                evidence_reference="raw:test-detail#ean",
                observed_at=NOW,
                confidence=Confidence.HIGH,
            ),
            requests=1,
            status="enriched",
        )


def test_targeted_enrichment_is_one_item_bounded_and_cached() -> None:
    client, factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]
    enricher = _SuccessfulEnricher()
    client.app.state.physical_product_identifier_enricher = enricher
    with factory() as session:
        identifier = session.get(PhysicalValidationSessionItemIdentifierModel, item["id"])
        assert identifier is not None
        identifier.target_source_provider = "own"
        identifier.target_external_product_id = "101230686_ST"
        identifier.target_store_external_id = "4123"
        session.commit()

    first = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/enrich-identifier"
    )
    second = client.post(
        f"/physical-check/sessions/{started['session']['id']}"
        f"/items/{item['id']}/enrich-identifier"
    )

    assert first.status_code == 200, first.text
    assert first.json()["status"] == "enriched"
    assert first.json()["gtin"] == FINBREAD_GTIN
    assert first.json()["identifier_preparation"]["detail_requests"] == 1
    assert second.json()["status"] == "already_cached"
    assert enricher.calls == 1


def test_shelf_code_is_diagnostic_and_never_treated_as_gtin() -> None:
    client, factory, started = _start_session(candidate=_candidate())
    item = started["items"][0]
    response = client.post(
        "/physical-check/shelf-identifiers",
        json={
            "physical_store_id": "physical-hemkop-karhogstorg",
            "validation_session_id": started["session"]["id"],
            "validation_session_item_id": item["id"],
            "raw_value": "ABC123456789",
            "barcode_format": "CODE_128",
            "observed_at": NOW.isoformat(),
        },
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "shelf_code_unknown"
    assert body["treated_as_gtin"] is False
    assert body["authoritative_product_identity"] is False
    assert body["physical_observation_created"] is False
    with factory() as session:
        [row] = list(session.scalars(select(ShelfIdentifierEvidenceModel)))
        assert row.verified is False
        assert row.raw_value == "ABC123456789"


def test_mismatch_and_no_match_are_not_compared_as_selected_product() -> None:
    candidate = _candidate(gtin=FINBREAD_GTIN)
    base = {
        "id": "observation",
        "physical_store_id": candidate.physical_store_id,
        "gtin": OTHER_GTIN,
        "product_name": candidate.product_name,
        "shelf_price": Decimal("30.00"),
        "observed_at": NOW,
        "confidence": Confidence.LOW,
        "validation_session_id": "session",
        "validation_session_item_id": "item",
        "price_semantics": PhysicalPriceSemantics.REGULAR,
        "immutable_candidate_set_sha256": "a" * 64,
    }
    mismatch = PhysicalPriceObservation(
        **base,
        identity_status=PhysicalProductIdentityStatus.GTIN_MISMATCH,
        identification_evidence=PhysicalIdentificationEvidence.UNVERIFIED,
    )
    no_match = mismatch.model_copy(
        update={
            "id": "no-match",
            "identity_status": PhysicalProductIdentityStatus.NO_MATCH,
        }
    )
    service = PhysicalPriceValidationService()

    [mismatch_result] = service.compare_observation(
        mismatch,
        (candidate,),
        expected_providers=("primat",),
    )
    [no_match_result] = service.compare_observation(
        no_match,
        (candidate,),
        expected_providers=("primat",),
    )

    assert mismatch_result.status == "no_digital_match"
    assert mismatch_result.digital_price is None
    assert no_match_result.status == "no_digital_match"
    assert no_match_result.digital_price is None


def test_accuracy_report_preserves_identification_evidence_breakdown() -> None:
    observation = PhysicalPriceObservation(
        id="manual",
        physical_store_id="physical-hemkop-karhogstorg",
        product_name="Finbröd Skånskt",
        shelf_price=Decimal("29.95"),
        observed_at=NOW,
        confidence=Confidence.MEDIUM,
        validation_session_id="session",
        validation_session_item_id="item",
        price_semantics=PhysicalPriceSemantics.REGULAR,
        identity_status=PhysicalProductIdentityStatus.MANUAL_EXACT_MATCH,
        identification_evidence=PhysicalIdentificationEvidence.SOURCE_PRODUCT_MANUAL,
        immutable_candidate_set_sha256="a" * 64,
    )
    comparison = PhysicalPriceValidationService().compare_observation(
        observation,
        (_candidate(),),
        expected_providers=("primat",),
    )

    report = build_accuracy_report(
        (observation,),
        comparison,
        scope_label="Karhögstorg",
    )

    assert report.identity_status_breakdown == {"manual_exact_match": 1}
    assert report.identification_evidence_breakdown == {"source_product_manual": 1}
    assert report.sampled_only is True


def test_identifier_models_reject_malformed_gtin_and_authoritative_shelf_code() -> None:
    with pytest.raises(InvalidGtinError):
        normalize_gtin("7391737003438")
    with pytest.raises(ValidationError):
        ShelfIdentifierEvidence(
            id="shelf",
            chain=Chain.HEMKOP,
            physical_store_id="physical-hemkop-karhogstorg",
            raw_value="internal-code",
            barcode_format="CODE_128",
            observed_at=NOW,
            verified=True,
        )
