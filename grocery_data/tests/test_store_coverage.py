from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    ConnectorStatus,
    CoverageLevel,
    PhysicalStoreCoverageState,
    PhysicalStoreLifecycleState,
    PriceContextType,
    StoreContextRelationType,
    StoreDiscoveryErrorCode,
)
from grocery_data.app.domain.physical_price import PhysicalPriceObservation
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.domain.store import PhysicalStore, StoreContextLink
from grocery_data.app.main import create_app
from grocery_data.app.services.store_coverage import (
    ExactStoreIdentityMatcher,
    GroceryContextEvidence,
    StoreCoverageAuditor,
)
from grocery_data.app.storage import (
    PhysicalPriceObservationRepository,
    PhysicalStoreDiscoveryHealthRepository,
    PhysicalStoreRepository,
    StoreContextLinkRepository,
    StoreDiscoveryDriftError,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield engine, factory
    finally:
        engine.dispose()


def _physical(
    *,
    store_id: str = "physical-hemkop-karhogstorg",
    external_id: str | None = "4123",
    name: str = "Hemköp Lund Karhögstorg",
    address: str = "Karhögstorg 2A",
    now: datetime,
) -> PhysicalStore:
    return PhysicalStore(
        id=store_id,
        chain=Chain.HEMKOP,
        external_store_id=external_id,
        name=name,
        address=address,
        postal_code="223 58",
        city="Lund",
        latitude=Decimal("55.7041000"),
        longitude=Decimal("13.2111000"),
        official_source="https://www.hemkop.se/butik/4123",
        discovered_at=now,
        last_seen_at=now,
    )


def _external_link(*, physical_store_id: str, now: datetime) -> StoreContextLink:
    return StoreContextLink(
        physical_store_id=physical_store_id,
        grocery_context_id="primat:hemkop:4123",
        source_provider=SourceProvider.PRIMAT,
        source_channel=SourceChannel.CATALOG,
        grocery_context_name="Hemköp Karhögstorg",
        price_context_type=PriceContextType.ONLINE_STORE,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
        confidence=Confidence.EXACT,
        evidence="official external ID 4123",
        basket_eligible=True,
        snapshot_id="primat-snapshot-1",
        observed_at=now,
        linked_at=now,
        last_verified_at=now,
    )


def test_physical_store_lifecycle_is_history_safe(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    first = datetime(2026, 8, 23, 8, tzinfo=UTC)
    second = first + timedelta(days=1)
    third = second + timedelta(days=1)
    with session_scope(factory) as session:
        repository = PhysicalStoreRepository(session)
        original = repository.upsert(_physical(now=first))
        repeated = repository.upsert(_physical(now=second), seen_at=second)
        assert repeated.id == original.id
        assert repeated.discovered_at == first
        assert repeated.last_seen_at == second

        with pytest.raises(StoreDiscoveryDriftError):
            repository.reconcile_discovery(
                Chain.HEMKOP,
                city="Lund",
                seen_physical_store_ids=set(),
                observed_at=third,
            )
        assert repeated.is_active is True

        other = repository.upsert(
            _physical(
                store_id="physical-hemkop-other",
                external_id="4999",
                name="Hemköp Lund Andra",
                address="Andra gatan 1",
                now=first,
            )
        )
        result = repository.reconcile_discovery(
            Chain.HEMKOP,
            city="Lund",
            seen_physical_store_ids={original.id},
            observed_at=third,
        )
        assert result.marked_not_seen == 1
        assert other.is_active is False
        assert other.lifecycle_state == PhysicalStoreLifecycleState.NOT_SEEN.value
        assert other.not_seen_at == third
        report = StoreCoverageAuditor(session).audit("Lund", now=third)
        assert report.physical_stores == 1
        assert report.stale == 1
        assert len(report.chains["hemkop"].stores) == 2


def test_external_context_link_does_not_fabricate_local_store(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    with session_scope(factory) as session:
        physical = PhysicalStoreRepository(session).upsert(_physical(now=now))
        links = StoreContextLinkRepository(session)
        first = links.upsert(_external_link(physical_store_id=physical.id, now=now))
        second = links.upsert(_external_link(physical_store_id=physical.id, now=now))
        assert first.id == second.id
        assert first.local_store_id is None
        assert first.source_provider == SourceProvider.PRIMAT.value

        # Many-to-many is allowed: a second physical site may share an explicit
        # delivery/region context without changing the first link.
        other = PhysicalStoreRepository(session).upsert(
            _physical(
                store_id="physical-hemkop-other",
                external_id="4999",
                name="Hemköp Lund Andra",
                address="Andra gatan 1",
                now=now,
            )
        )
        links.upsert(_external_link(physical_store_id=other.id, now=now))
        assert (
            len(
                links.list_for_context(
                    source_provider=SourceProvider.PRIMAT.value,
                    grocery_context_id="primat:hemkop:4123",
                )
            )
            == 2
        )


def test_exact_context_matching_never_uses_name_only() -> None:
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    physical = _physical(now=now)
    name_only = GroceryContextEvidence(
        grocery_context_id="primat:name-only",
        chain=Chain.HEMKOP,
        name=physical.name,
        city="Lund",
        source_provider=SourceProvider.PRIMAT,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        basket_eligible=True,
        snapshot_id="snapshot",
        observed_at=now,
    )
    exact_external = name_only.model_copy(
        update={
            "grocery_context_id": "primat:exact",
            "physical_store_external_id": physical.external_store_id,
        }
    )
    assert ExactStoreIdentityMatcher.physical_to_context(physical, [name_only]) == []
    matches = ExactStoreIdentityMatcher.physical_to_context(physical, [exact_external])
    assert len(matches) == 1
    assert matches[0].confidence == Confidence.EXACT


def test_coverage_audit_reports_basket_and_missing_without_fuzzy_mapping(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    registered = _physical(now=now)
    missing = _physical(
        store_id="physical-hemkop-missing",
        external_id="4555",
        name="Hemköp Lund Saknad",
        address="Saknad väg 1",
        now=now,
    )
    with session_scope(factory) as session:
        PhysicalStoreRepository(session).upsert(registered)
        StoreContextLinkRepository(session).upsert(
            _external_link(physical_store_id=registered.id, now=now)
        )
        report = StoreCoverageAuditor(session).audit(
            "Lund",
            official_stores=[registered, missing],
            now=now,
        )
        assert report.official_evidence == "fresh_discovery"
        assert report.official_last_seen_at == now
        hemkop = report.chains[Chain.HEMKOP.value]
        assert hemkop.official_physical_stores == 2
        assert hemkop.known_physical_stores == 1
        assert hemkop.mapped_contexts == 1
        assert hemkop.basket_capable_contexts == 1
        assert hemkop.missing_physical_stores == 1
        assert hemkop.missing_mappings == 1
        assert {item.coverage_state for item in hemkop.stores} == {
            PhysicalStoreCoverageState.BASKET_CAPABLE,
            PhysicalStoreCoverageState.MISSING,
        }


def test_inactive_external_context_is_historical_not_mapped_or_basket_capable(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    with session_scope(factory) as session:
        physical = PhysicalStoreRepository(session).upsert(_physical(now=now))
        link = StoreContextLinkRepository(session).upsert(
            _external_link(physical_store_id=physical.id, now=now).model_copy(
                update={"active": False}
            )
        )
        assert link.is_active is False

        report = StoreCoverageAuditor(session).audit("Lund", now=now)
        hemkop = report.chains[Chain.HEMKOP.value]
        [store] = hemkop.stores

        assert hemkop.mapped_physical_stores == 0
        assert hemkop.mapped_contexts == 0
        assert hemkop.basket_capable_contexts == 0
        assert store.coverage_state is PhysicalStoreCoverageState.NO_PRICE_CONTEXT
        assert store.contexts[0].active is False
        assert store.contexts[0].basket_eligible is False


def test_stale_offer_context_precedes_offers_only_and_is_not_counted(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    observed_at = now - timedelta(hours=49)
    with session_scope(factory) as session:
        physical = PhysicalStoreRepository(session).upsert(_physical(now=now))
        StoreContextLinkRepository(session).upsert(
            StoreContextLink(
                physical_store_id=physical.id,
                grocery_context_id="own:hemkop:offers:4123",
                source_provider=SourceProvider.OWN,
                source_channel=SourceChannel.OFFERS,
                grocery_context_name="Hemköp Karhögstorg offers",
                price_context_type=PriceContextType.ONLINE_STORE,
                coverage=CoverageLevel.OFFERS_ONLY,
                relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
                confidence=Confidence.EXACT,
                evidence="exact official store identity",
                offers_only=True,
                snapshot_id="offers-snapshot-1",
                observed_at=observed_at,
                linked_at=observed_at,
                last_verified_at=observed_at,
            )
        )

        report = StoreCoverageAuditor(session, max_price_age_hours=48).audit(
            "Lund",
            now=now,
        )
        hemkop = report.chains[Chain.HEMKOP.value]
        [store] = hemkop.stores

        assert hemkop.mapped_physical_stores == 0
        assert hemkop.mapped_contexts == 0
        assert hemkop.offers_only_contexts == 0
        assert store.coverage_state is PhysicalStoreCoverageState.STALE
        assert store.contexts[0].stale is True
        assert store.contexts[0].offers_only is False


def test_manual_observation_storage_never_mutates_catalog_prices(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    with session_scope(factory) as session:
        physical = PhysicalStoreRepository(session).upsert(_physical(now=now))
        repository = PhysicalPriceObservationRepository(session)
        observation = PhysicalPriceObservation(
            id="observation-1",
            physical_store_id=physical.id,
            gtin="7310000000001",
            shelf_price=Decimal("29.90"),
            observed_at=now,
            confidence=Confidence.HIGH,
        )
        saved = repository.add(observation)
        assert repository.add(observation).id == saved.id
        assert repository.list_for_store(physical.id) == [saved]
        assert saved.shelf_price == Decimal("29.90")


def test_store_coverage_api_precedes_dynamic_store_route(storage, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime.now(tz=UTC)
    with session_scope(factory) as session:
        physical = PhysicalStoreRepository(session).upsert(_physical(now=now))
        StoreContextLinkRepository(session).upsert(
            _external_link(physical_store_id=physical.id, now=now)
        )
        PhysicalStoreDiscoveryHealthRepository(session).record(
            chain=Chain.HEMKOP,
            city="Lund",
            status=ConnectorStatus.DEGRADED,
            complete=False,
            discovered_count=0,
            previous_count=1,
            observed_at=now,
            error_code=StoreDiscoveryErrorCode.EMPTY_LOCATOR_RESULT,
        )
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    client = TestClient(create_app(factory))
    response = client.get("/stores/coverage", params={"city": "Lund"})
    assert response.status_code == 200
    body = response.json()
    assert body["city"] == "Lund"
    assert body["official_evidence"] == "persisted_registry"
    assert body["official_last_seen_at"] == now.isoformat().replace("+00:00", "Z")
    assert body["physical_stores"] == 1
    assert body["basket_capable"] == 1
    assert body["discovery_health"]["hemkop"] == {
        "chain": "hemkop",
        "city": "Lund",
        "status": "degraded",
        "complete": False,
        "discovered_count": 0,
        "previous_count": 1,
        "observed_at": now.isoformat().replace("+00:00", "Z"),
        "error_code": "empty_locator_result",
    }
    assert body["chains"]["hemkop"]["stores"][0]["name"] == ("Hemköp Lund Karhögstorg")
