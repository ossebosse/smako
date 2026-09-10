from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import inspect

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    CoverageLevel,
    PriceContextType,
    SaleModel,
    StoreContextRelationType,
)
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalPriceObservation,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.domain.store import PhysicalStore, StoreContextLink
from grocery_data.app.main import create_app
from grocery_data.app.services.external_price_import import (
    ExternalPriceSnapshotImportService,
)
from grocery_data.app.services.physical_price_candidates import (
    PersistedExternalPhysicalPriceCandidateReader,
)
from grocery_data.app.services.physical_price_validation import PhysicalPriceValidationService
from grocery_data.app.storage import (
    ExternalPriceCandidateRepository,
    PhysicalStoreRepository,
    StoreContextLinkRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)
STORE_ID = "physical:hemkop:4123"
CONTEXT_ID = "primat:hemkop:4123"
GTIN = "7310865004703"


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        with session_scope(factory) as session:
            PhysicalStoreRepository(session).upsert(
                PhysicalStore(
                    id=STORE_ID,
                    chain=Chain.HEMKOP,
                    external_store_id="4123",
                    name="Hemköp Lund Karhögstorg",
                    address="Karhögstorg 2A",
                    postal_code="22358",
                    city="Lund",
                    official_source="https://www.hemkop.se/",
                    discovered_at=NOW,
                    last_seen_at=NOW,
                )
            )
            StoreContextLinkRepository(session).upsert(
                StoreContextLink(
                    physical_store_id=STORE_ID,
                    grocery_context_id=CONTEXT_ID,
                    source_provider=SourceProvider.PRIMAT,
                    source_channel=SourceChannel.CATALOG,
                    grocery_context_name="Hemköp Karhögstorg",
                    price_context_type=PriceContextType.ONLINE_STORE,
                    coverage=CoverageLevel.FULL_CATALOG,
                    relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
                    confidence=Confidence.HIGH,
                    evidence="exact official address and postal code",
                    basket_eligible=True,
                    snapshot_id="primat-snapshot-1",
                    observed_at=NOW,
                    linked_at=NOW,
                    last_verified_at=NOW,
                )
            )
        yield engine, factory
    finally:
        engine.dispose()


def _candidate(
    *,
    snapshot_id: str,
    observed_at: datetime,
    product_id: str = "primat-milk",
    name: str = "Mjölk 1 l",
    gtin: str | None = GTIN,
    price: Decimal = Decimal("29.90"),
) -> DigitalPriceCandidate:
    return DigitalPriceCandidate(
        physical_store_id=STORE_ID,
        grocery_context_id=CONTEXT_ID,
        source_provider=SourceProvider.PRIMAT.value,
        source_snapshot_id=snapshot_id,
        observed_at=observed_at,
        product_id=product_id,
        product_name=name,
        gtin=gtin,
        current_price=price,
        regular_price=Decimal("31.90"),
        sale_model=SaleModel.FIXED_PACKAGE,
        common_product_score=Decimal(4),
    )


def test_persisted_external_reader_preserves_provenance_and_temporal_history(storage) -> None:  # type: ignore[no-untyped-def]
    _engine, factory = storage
    first_time = NOW - timedelta(days=7)
    with session_scope(factory) as session:
        repository = ExternalPriceCandidateRepository(session)
        first = _candidate(snapshot_id="primat-snapshot-1", observed_at=first_time)
        second = _candidate(
            snapshot_id="primat-snapshot-2",
            observed_at=NOW,
            price=Decimal("31.90"),
        )
        assert repository.import_snapshot([first]).products == 1
        assert repository.import_snapshot([second]).deactivated_rows == 1

        reader = PersistedExternalPhysicalPriceCandidateReader(session)
        [active] = reader.for_store(STORE_ID, limit=10)
        assert active.source_provider == SourceProvider.PRIMAT.value
        assert active.source_snapshot_id == "primat-snapshot-2"
        assert active.grocery_context_id == CONTEXT_ID
        assert active.observed_at == NOW
        assert active.current_price == Decimal("31.90")

        observation = PhysicalPriceObservation(
            id="observation-old",
            physical_store_id=STORE_ID,
            gtin=GTIN,
            shelf_price=Decimal("29.90"),
            observed_at=first_time,
            confidence=Confidence.UNKNOWN,
        )
        historical = reader.for_observation(observation)
        assert {row.source_snapshot_id for row in historical} == {
            "primat-snapshot-1",
            "primat-snapshot-2",
        }
        [current] = reader.current_for_observation(observation)
        assert current.source_snapshot_id == "primat-snapshot-2"
        assert current.current_price == Decimal("31.90")
        [comparison] = PhysicalPriceValidationService().compare_observation(
            observation,
            historical,
            expected_providers=(SourceProvider.PRIMAT.value,),
        )
        assert comparison.source_snapshot_id == "primat-snapshot-1"
        assert comparison.status.value == "match"


def test_external_reader_uses_exact_normalized_name_and_rejects_partial_retry(storage) -> None:  # type: ignore[no-untyped-def]
    _engine, factory = storage
    with session_scope(factory) as session:
        repository = ExternalPriceCandidateRepository(session)
        milk = _candidate(snapshot_id="snapshot", observed_at=NOW)
        rice = _candidate(
            snapshot_id="snapshot",
            observed_at=NOW,
            product_id="primat-rice",
            name="Ris 1 kg",
            gtin="7310000000049",
        )
        repository.import_snapshot([milk, rice])
        with pytest.raises(ValueError, match="different product identity set"):
            repository.import_snapshot([milk])

        reader = PersistedExternalPhysicalPriceCandidateReader(session)
        exact = PhysicalPriceObservation(
            id="name-exact",
            physical_store_id=STORE_ID,
            product_name="  MJÖLK   1 L ",
            shelf_price=Decimal("29.90"),
            observed_at=NOW,
            confidence=Confidence.UNKNOWN,
        )
        different = exact.model_copy(
            update={"id": "name-different", "product_name": "Ekologisk mjölk 1 l"}
        )
        assert [row.product_id for row in reader.for_observation(exact)] == ["primat-milk"]
        assert reader.for_observation(different) == ()


def test_external_cache_requires_exact_active_mapping_and_never_accepts_own(storage) -> None:  # type: ignore[no-untyped-def]
    _engine, factory = storage
    with session_scope(factory) as session:
        repository = ExternalPriceCandidateRepository(session)
        own = _candidate(snapshot_id="own", observed_at=NOW).model_copy(
            update={"source_provider": SourceProvider.OWN.value}
        )
        with pytest.raises(ValueError, match="OWN candidates"):
            repository.import_snapshot([own])

        link = StoreContextLinkRepository(session).get(
            STORE_ID,
            source_provider=SourceProvider.PRIMAT.value,
            grocery_context_id=CONTEXT_ID,
        )
        assert link is not None
        link.relation_type = StoreContextRelationType.REGIONAL_CONTEXT.value
        session.flush()
        with pytest.raises(LookupError, match="active exact store-context link"):
            repository.import_snapshot([_candidate(snapshot_id="regional", observed_at=NOW)])


def test_default_physical_api_reads_local_primat_cache_without_live_client(
    storage,
    monkeypatch,
) -> None:  # type: ignore[no-untyped-def]
    _engine, factory = storage
    with session_scope(factory) as session:
        ExternalPriceCandidateRepository(session).import_snapshot(
            [_candidate(snapshot_id="primat-api", observed_at=NOW)]
        )
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    client = TestClient(create_app(factory))

    response = client.post(
        "/physical-check/observations",
        json={
            "physical_store_id": STORE_ID,
            "gtin": GTIN,
            "shelf_price": "29.90",
            "observed_at": NOW.isoformat(),
        },
    )

    assert response.status_code == 201
    [comparison] = response.json()["comparisons"]
    assert comparison["source_provider"] == SourceProvider.PRIMAT.value
    assert comparison["source_snapshot_id"] == "primat-api"
    assert comparison["status"] == "match"


def test_external_cache_schema_has_no_secret_or_session_payload_columns(storage) -> None:  # type: ignore[no-untyped-def]
    engine, _factory = storage
    names = {
        column["name"].casefold()
        for column in inspect(engine).get_columns("external_price_candidates")
    }
    forbidden = {"authorization", "cookie", "credentials", "headers", "secret", "token"}
    assert names.isdisjoint(forbidden)
    assert "source_snapshot_id" in names
    assert "observed_at" in names


def test_credential_free_snapshot_file_is_a_bounded_production_ingest_seam(
    storage,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    _engine, factory = storage
    candidate = _candidate(snapshot_id="primat-file-1", observed_at=NOW)
    payload = {
        "schema": "external-price-candidates-v1",
        "candidates": [candidate.model_dump(mode="json")],
    }
    path = tmp_path / "primat-snapshot.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with session_scope(factory) as session:
        service = ExternalPriceSnapshotImportService(session)
        with pytest.raises(ValueError, match="file-size limit"):
            service.import_file(path, max_bytes=1)
        result = service.import_file(path)
        assert result.source_provider == SourceProvider.PRIMAT.value
        assert result.source_snapshot_id == "primat-file-1"
        assert result.products == 1

        leaked = {
            **payload,
            "authorization": "must-not-be-accepted",
        }
        with pytest.raises(ValidationError):
            service.import_payload(leaked)

    with session_scope(factory) as session:
        [persisted] = PersistedExternalPhysicalPriceCandidateReader(session).for_store(
            STORE_ID,
            limit=10,
        )
        assert persisted.source_snapshot_id == "primat-file-1"
