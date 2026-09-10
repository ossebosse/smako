from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.online_context import (
    CoopOnlineContextEvidenceBundle,
    CoopPickupContextEvidence,
)
from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    CoverageLevel,
    PriceContextType,
    StoreContextRelationType,
)
from grocery_data.app.domain.source_strategy import SourceProvider
from grocery_data.app.domain.store import PhysicalStore, StoreContextLink
from grocery_data.app.services.store_coverage import StoreCoverageAuditor
from grocery_data.app.storage import (
    PhysicalStoreRepository,
    StoreContextLinkRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)

FIXTURE = (
    Path(__file__).parents[1]
    / "app"
    / "connectors"
    / "coop"
    / "fixtures"
    / "online_contexts_2026_08_25.json"
)
OBSERVED_AT = datetime(2026, 8, 25, 8, tzinfo=UTC)


@pytest.fixture
def bundle() -> CoopOnlineContextEvidenceBundle:
    return CoopOnlineContextEvidenceBundle.from_path(FIXTURE)


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _physical(
    external_id: str,
    name: str,
    *,
    physical_id: str | None = None,
) -> PhysicalStore:
    return PhysicalStore(
        id=physical_id or f"physical:coop:{external_id}",
        chain=Chain.COOP,
        external_store_id=external_id,
        name=name,
        address="Test address 1" if external_id.startswith("test-") else "Traktorvägen 2",
        postal_code="22660",
        city="Lund",
        official_source="https://www.coop.se/butiker-erbjudanden/",
        discovered_at=OBSERVED_AT,
        last_seen_at=OBSERVED_AT,
    )


def _basket_link(
    bundle: CoopOnlineContextEvidenceBundle,
    physical: PhysicalStore,
) -> StoreContextLink:
    return bundle.as_pickup_link(
        physical,
        verified_at=OBSERVED_AT,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        basket_eligible=True,
        snapshot_id="snapshot:coop:730400:test",
        observed_at=OBSERVED_AT,
    )


def test_730400_is_neutral_online_context_and_stockholm_is_distinct(
    bundle: CoopOnlineContextEvidenceBundle,
) -> None:
    syd = bundle.context("730400")
    stockholm = bundle.context("256600")

    assert syd.grocery_context_id == "own:coop:730400"
    assert syd.display_name == "Coop Online Syd"
    assert syd.context_type is PriceContextType.ONLINE_FULFILLMENT
    assert stockholm.external_context_id == "256600"
    assert stockholm.grocery_context_id != syd.grocery_context_id

    source_store = syd.as_source_store()
    assert source_store.external_id == "730400"
    assert source_store.name == "Coop Online Syd"
    assert source_store.price_context_type is PriceContextType.ONLINE_FULFILLMENT
    assert source_store.physical_store_external_id is None
    assert source_store.city is None

    context = syd.as_context_evidence()
    assert context.grocery_context_id == "own:coop:730400"
    assert context.name == "Coop Online Syd"
    assert context.price_context_type is PriceContextType.ONLINE_FULFILLMENT
    assert context.physical_store_external_id is None
    assert context.basket_eligible is False


def test_store_context_link_is_backward_compatible_and_pickup_identity_is_typed() -> None:
    legacy = StoreContextLink.model_validate(
        {
            "physical_store_id": "physical:coop:2696",
            "grocery_context_id": "own:coop:730400",
            "source_provider": "own",
            "source_channel": "catalog",
            "grocery_context_name": "Coop Online Syd",
            "price_context_type": "online_fulfillment",
            "relation_type": "pickup_context",
            "confidence": "high",
            "linked_at": OBSERVED_AT,
            "last_verified_at": OBSERVED_AT,
        }
    )
    assert legacy.pickup_point_external_id is None
    assert "pickup_point_external_id" not in legacy.model_dump(exclude_none=True)

    with pytest.raises(ValueError, match="PICKUP_CONTEXT"):
        StoreContextLink.model_validate(
            {
                **legacy.model_dump(),
                "pickup_point_external_id": "257611",
                "relation_type": StoreContextRelationType.DELIVERY_CONTEXT,
            }
        )


def test_stora_coop_lund_pickup_relation_is_persisted_and_reported_once(
    storage,  # type: ignore[no-untyped-def]
    bundle: CoopOnlineContextEvidenceBundle,
) -> None:
    physical = _physical("2696", "Stora Coop Lund")
    link = _basket_link(bundle, physical)

    assert physical.id == "physical:coop:2696"
    assert link.grocery_context_id == "own:coop:730400"
    assert link.grocery_context_name == "Coop Online Syd"
    assert link.pickup_point_external_id == "257611"
    assert link.relation_type is StoreContextRelationType.PICKUP_CONTEXT
    assert link.confidence is Confidence.EXACT
    assert link.price_context_type is PriceContextType.ONLINE_FULFILLMENT

    with session_scope(storage) as session:
        PhysicalStoreRepository(session).upsert(physical)
        persisted = StoreContextLinkRepository(session).upsert(link)
        assert persisted.pickup_point_external_id == "257611"
        assert persisted.grocery_context_id != physical.external_store_id

        report = StoreCoverageAuditor(session).audit("Lund", now=OBSERVED_AT)
        coop = report.chains[Chain.COOP.value]
        assert coop.official_physical_stores == 1
        assert coop.mapped_physical_stores == 1
        assert coop.mapped_contexts == 1
        assert coop.basket_capable_contexts == 1
        assert coop.stores[0].contexts[0].pickup_point_external_id == "257611"


def test_multiple_pickups_share_one_price_context_without_store_duplication(
    storage,  # type: ignore[no-untyped-def]
    bundle: CoopOnlineContextEvidenceBundle,
) -> None:
    synthetic_relation = CoopPickupContextEvidence(
        physical_store_external_id="test-pickup-store",
        physical_store_name="Synthetic Coop Pickup",
        pickup_point_external_id="test-pickup-point",
        online_context_external_id="730400",
        evidence_kind="public_fulfillment_response",
        evidence_reference="synthetic unit fixture for many-to-one cardinality",
    )
    expanded = bundle.model_copy(
        update={"pickup_relations": (*bundle.pickup_relations, synthetic_relation)}
    )
    # Revalidate after model_copy so bundle-level reference/cardinality gates run.
    expanded = CoopOnlineContextEvidenceBundle.model_validate(expanded.model_dump())
    lund = _physical("2696", "Stora Coop Lund")
    synthetic = _physical("test-pickup-store", "Synthetic Coop Pickup")

    with session_scope(storage) as session:
        physicals = PhysicalStoreRepository(session)
        links = StoreContextLinkRepository(session)
        for physical in (lund, synthetic):
            physicals.upsert(physical)
            links.upsert(_basket_link(expanded, physical))

        assert len(
            links.list_for_context(
                source_provider=SourceProvider.OWN.value,
                grocery_context_id="own:coop:730400",
            )
        ) == 2
        report = StoreCoverageAuditor(session).audit("Lund", now=OBSERVED_AT)
        coop = report.chains[Chain.COOP.value]
        assert coop.mapped_physical_stores == 2
        assert coop.mapped_contexts == 1
        assert coop.basket_capable_contexts == 1


def test_martenstorget_is_not_linked_without_explicit_pickup_evidence(
    storage,  # type: ignore[no-untyped-def]
    bundle: CoopOnlineContextEvidenceBundle,
) -> None:
    martenstorget = _physical("3813", "Coop Mårtenstorget")
    with pytest.raises(LookupError, match="explicit pickup evidence"):
        bundle.as_pickup_link(martenstorget, verified_at=OBSERVED_AT)

    with session_scope(storage) as session:
        PhysicalStoreRepository(session).upsert(martenstorget)
        assert StoreContextLinkRepository(session).list_for_physical_store(
            martenstorget.id
        ) == []
        report = StoreCoverageAuditor(session).audit("Lund", now=OBSERVED_AT)
        coop = report.chains[Chain.COOP.value]
        assert coop.mapped_contexts == 0
        assert coop.missing_mappings == 1


def test_context_fixture_contains_no_transport_or_tracking_state() -> None:
    payload = FIXTURE.read_text(encoding="utf-8").casefold()
    forbidden = (
        "authorization",
        "cookie",
        "csrf",
        "session",
        "subscription-key",
        '"uid"',
        '"sid"',
    )
    assert all(value not in payload for value in forbidden)
