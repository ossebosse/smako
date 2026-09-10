from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.coop.store_locator import (
    CoopStoreLocatorError,
    sanitized_store_locator_payload,
    validated_store_locator,
)
from grocery_data.app.domain import (
    Chain,
    ConnectorStatus,
    CoverageLevel,
    GeographicArea,
    PhysicalStoreLifecycleState,
    PriceContextType,
    RawBatch,
    SourceStore,
    StoreDiscoveryErrorCode,
)
from grocery_data.app.services.official_store_discovery import (
    FixtureOfficialStoreAdapter,
    OfficialStoreDiscoveryService,
    SourceStoreOfficialAdapter,
    fixture_official_store_adapters,
    live_official_store_adapters,
    persisted_own_context_evidence,
    stable_physical_store_id,
)
from grocery_data.app.storage import (
    PhysicalStoreDiscoveryHealthRepository,
    PhysicalStoreRepository,
    SnapshotRepository,
    StoreContextLinkRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import RawSnapshotModel, SourceProductModel

FIXTURE = Path(__file__).parents[1] / "app" / "services" / "fixtures" / "official_stores_lund.json"


@pytest.mark.asyncio
async def test_live_adapter_factory_builds_only_requested_chain() -> None:
    adapters = live_official_store_adapters((Chain.ICA,))
    try:
        assert set(adapters) == {Chain.ICA}
    finally:
        await adapters[Chain.ICA].aclose()


@pytest.mark.asyncio
async def test_live_coop_adapter_preserves_public_ledger_account_alias() -> None:
    adapters = live_official_store_adapters((Chain.COOP,))
    adapter = adapters[Chain.COOP]
    try:
        assert isinstance(adapter, SourceStoreOfficialAdapter)
        official = SourceStore(
            chain=Chain.COOP,
            external_id="2696",
            name="Stora Coop Lund",
            address="Traktorvägen 2",
            postal_code="22660",
            city="Lund",
            online_shopping=None,
            coverage=CoverageLevel.OFFERS_ONLY,
            raw_reference="raw:coop:official-store-page",
            source_fields={"ledger_account_number": 105760},
        )

        assert tuple(adapter.physical_external_aliases(official)) == ("105760",)
    finally:
        await adapter.aclose()


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_sanitized_lund_fixture_reconciles_all_six_official_locators(storage) -> None:  # type: ignore[no-untyped-def]
    observed = datetime(2026, 8, 23, 12, tzinfo=UTC)
    with session_scope(storage) as session:
        report = await OfficialStoreDiscoveryService(
            fixture_official_store_adapters(FIXTURE),
            session=session,
        ).discover_city("Lund", observed_at=observed)

        assert report.errors == {}
        assert report.healthy_chains == 6
        assert report.physical_stores == 23
        assert report.own_contexts_considered == 20
        assert report.external_contexts_considered == 0
        assert report.context_links_verified == 20
        assert {chain: len(result.stores) for chain, result in report.results.items()} == {
            "willys": 3,
            "hemkop": 2,
            "ica": 9,
            "coop": 7,
            "lidl": 2,
            "citygross": 0,
        }
        assert report.results["ica"].source_scope_total == 12
        assert report.results["ica"].outside_city_count == 3
        assert PhysicalStoreRepository(session).list_for_city("Lund", active_only=True)


@pytest.mark.asyncio
async def test_hemkop_karhogstorg_official_regression_uses_stable_identity() -> None:
    report = await OfficialStoreDiscoveryService(
        fixture_official_store_adapters(FIXTURE)
    ).discover_city("Lund", chains=[Chain.HEMKOP])

    stores = report.results[Chain.HEMKOP.value].stores
    karhogstorg = next(store for store in stores if store.external_store_id == "4123")
    assert karhogstorg.id == stable_physical_store_id(Chain.HEMKOP, "4123")
    assert karhogstorg.name == "Hemköp Lund Karhögstorg"
    assert karhogstorg.address.casefold() == "karhögstorg 2a"
    assert karhogstorg.postal_code == "22358"
    assert karhogstorg.city == "Lund"


@pytest.mark.asyncio
async def test_ica_fixture_preserves_secondary_store_id_alias() -> None:
    report = await OfficialStoreDiscoveryService(
        fixture_official_store_adapters(FIXTURE)
    ).discover_city("Lund", chains=[Chain.ICA])

    clemenstorget = next(
        store
        for store in report.results[Chain.ICA.value].stores
        if store.external_store_id == "1004409"
    )
    assert clemenstorget.id == stable_physical_store_id(Chain.ICA, "1004409")
    assert clemenstorget.external_store_aliases == ("2771",)


@pytest.mark.asyncio
async def test_coop_fixture_preserves_secondary_ledger_account_alias() -> None:
    report = await OfficialStoreDiscoveryService(
        fixture_official_store_adapters(FIXTURE)
    ).discover_city("Lund", chains=[Chain.COOP])

    martenstorget = next(
        store
        for store in report.results[Chain.COOP.value].stores
        if store.external_store_id == "3813"
    )
    assert martenstorget.id == stable_physical_store_id(Chain.COOP, "3813")
    assert martenstorget.external_store_aliases == ("106430",)


@pytest.mark.asyncio
async def test_discovery_marks_missing_store_not_seen_without_deleting_history(storage) -> None:  # type: ignore[no-untyped-def]
    root = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hemkop = root["chains"]["hemkop"]
    first = datetime(2026, 8, 23, 12, tzinfo=UTC)
    second = first + timedelta(days=1)
    adapter = FixtureOfficialStoreAdapter(Chain.HEMKOP, hemkop)

    with session_scope(storage) as session:
        service = OfficialStoreDiscoveryService({Chain.HEMKOP: adapter}, session=session)
        first_report = await service.discover_city("Lund", chains=[Chain.HEMKOP], observed_at=first)
        assert first_report.errors == {}

        changed = deepcopy(hemkop)
        changed["stores"] = [row for row in changed["stores"] if row["external_store_id"] == "4123"]
        changed["source_scope_total"] = 1
        service = OfficialStoreDiscoveryService(
            {Chain.HEMKOP: FixtureOfficialStoreAdapter(Chain.HEMKOP, changed)},
            session=session,
        )
        second_report = await service.discover_city(
            "Lund",
            chains=[Chain.HEMKOP],
            observed_at=second,
            confirm_store_removals=True,
        )
        assert second_report.errors == {}

        rows = PhysicalStoreRepository(session).list_for_city(
            "Lund", chain=Chain.HEMKOP, active_only=False
        )
        assert len(rows) == 2
        states = {row.external_store_id: row.lifecycle_state for row in rows}
        assert states == {
            "4123": PhysicalStoreLifecycleState.ACTIVE.value,
            "4224": PhysicalStoreLifecycleState.NOT_SEEN.value,
        }
        health = PhysicalStoreDiscoveryHealthRepository(session).get(Chain.HEMKOP, "Lund")
        assert health is not None
        assert health.status == ConnectorStatus.HEALTHY.value
        assert health.complete is True
        assert health.discovered_count == 1
        assert health.previous_count == 2
        assert health.error_code is None


@pytest.mark.asyncio
async def test_empty_locator_result_is_drift_and_retains_existing_sites(storage) -> None:  # type: ignore[no-untyped-def]
    root = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hemkop = root["chains"]["hemkop"]
    first = datetime(2026, 8, 23, 12, tzinfo=UTC)

    with session_scope(storage) as session:
        await OfficialStoreDiscoveryService(
            {Chain.HEMKOP: FixtureOfficialStoreAdapter(Chain.HEMKOP, hemkop)},
            session=session,
        ).discover_city("Lund", chains=[Chain.HEMKOP], observed_at=first)
        empty = deepcopy(hemkop)
        empty["stores"] = []
        empty["source_scope_total"] = 0
        report = await OfficialStoreDiscoveryService(
            {Chain.HEMKOP: FixtureOfficialStoreAdapter(Chain.HEMKOP, empty)},
            session=session,
        ).discover_city(
            "Lund",
            chains=[Chain.HEMKOP],
            observed_at=first + timedelta(days=1),
        )

        assert report.errors["hemkop"] == "store_count_collapse_requires_confirmation"
        assert report.results["hemkop"].status == ConnectorStatus.DEGRADED
        assert report.results["hemkop"].complete is False
        assert report.healthy_chains == 0
        rows = PhysicalStoreRepository(session).list_for_city(
            "Lund", chain=Chain.HEMKOP, active_only=True
        )
        assert {row.external_store_id for row in rows} == {"4123", "4224"}
        health = PhysicalStoreDiscoveryHealthRepository(session).get(Chain.HEMKOP, "Lund")
        assert health is not None
        assert health.status == ConnectorStatus.DEGRADED.value
        assert health.complete is False
        assert health.discovered_count == 0
        assert health.previous_count == 2
        assert health.error_code == StoreDiscoveryErrorCode.STORE_COUNT_COLLAPSE.value


@pytest.mark.asyncio
async def test_nonempty_count_collapse_requires_explicit_removal_confirmation(storage) -> None:  # type: ignore[no-untyped-def]
    root = json.loads(FIXTURE.read_text(encoding="utf-8"))
    hemkop = root["chains"]["hemkop"]
    changed = deepcopy(hemkop)
    changed["stores"] = [row for row in changed["stores"] if row["external_store_id"] == "4123"]
    changed["source_scope_total"] = 1
    first = datetime(2026, 8, 23, 12, tzinfo=UTC)

    with session_scope(storage) as session:
        await OfficialStoreDiscoveryService(
            {Chain.HEMKOP: FixtureOfficialStoreAdapter(Chain.HEMKOP, hemkop)},
            session=session,
        ).discover_city("Lund", observed_at=first)
        report = await OfficialStoreDiscoveryService(
            {Chain.HEMKOP: FixtureOfficialStoreAdapter(Chain.HEMKOP, changed)},
            session=session,
        ).discover_city("Lund", observed_at=first + timedelta(days=1))

        assert report.errors == {"hemkop": "store_count_collapse_requires_confirmation"}
        assert report.results["hemkop"].status == ConnectorStatus.DEGRADED
        rows = PhysicalStoreRepository(session).list_for_city(
            "Lund", chain=Chain.HEMKOP, active_only=True
        )
        assert {row.external_store_id for row in rows} == {"4123", "4224"}
        health = PhysicalStoreDiscoveryHealthRepository(session).get(Chain.HEMKOP, "Lund")
        assert health is not None
        assert health.status == ConnectorStatus.DEGRADED.value
        assert health.discovered_count == 1
        assert health.previous_count == 2
        assert health.error_code == StoreDiscoveryErrorCode.STORE_COUNT_COLLAPSE.value


@pytest.mark.asyncio
async def test_identity_failure_rolls_back_all_rows_for_one_chain(storage) -> None:  # type: ignore[no-untyped-def]
    root = json.loads(FIXTURE.read_text(encoding="utf-8"))
    ica = root["chains"]["ica"]
    observed = datetime(2026, 8, 23, 12, tzinfo=UTC)

    with session_scope(storage) as session:
        await OfficialStoreDiscoveryService(
            {Chain.ICA: FixtureOfficialStoreAdapter(Chain.ICA, ica)},
            session=session,
        ).discover_city("Lund", chains=[Chain.ICA], observed_at=observed)

        changed = deepcopy(ica)
        changed["stores"] = changed["stores"][:2]
        changed["source_scope_total"] = 2
        changed["outside_city_count"] = 0
        changed["stores"][0]["name"] = "MUST ROLL BACK"
        # The second row now claims the first row's exact secondary ID while
        # retaining its own stable registry ID. This must fail closed.
        changed["stores"][1]["secondary_external_store_id"] = changed["stores"][0][
            "secondary_external_store_id"
        ]
        report = await OfficialStoreDiscoveryService(
            {Chain.ICA: FixtureOfficialStoreAdapter(Chain.ICA, changed)},
            session=session,
        ).discover_city(
            "Lund",
            chains=[Chain.ICA],
            observed_at=observed + timedelta(hours=1),
        )

        assert report.results["ica"].status == ConnectorStatus.BROKEN
        assert report.results["ica"].complete is False
        assert "ica" in report.errors
        original = PhysicalStoreRepository(session).get(
            stable_physical_store_id(Chain.ICA, changed["stores"][0]["external_store_id"])
        )
        assert original is not None
        assert original.name != "MUST ROLL BACK"
        assert (
            len(
                PhysicalStoreRepository(session).list_for_city(
                    "Lund", chain=Chain.ICA, active_only=True
                )
            )
            == 9
        )
        health = PhysicalStoreDiscoveryHealthRepository(session).get(Chain.ICA, "Lund")
        assert health is not None
        assert health.status == ConnectorStatus.BROKEN.value
        assert health.previous_count == 9
        assert health.error_code == (
            StoreDiscoveryErrorCode.SCHEMA_OR_IDENTITY_CONTRACT_FAILED.value
        )


def test_coop_visible_card_envelope_is_closed_and_city_bounded() -> None:
    cards = [
        {
            "name": "Stora Coop Lund",
            "address_text": "Traktorvägen 2, Lund",
            "detail_href": "/butiker-erbjudanden/stora-coop/stora-coop-lund/",
            "map_href": "https://maps.google.com/maps?q=Traktorvägen%202%2022660%20Lund",
            "cookie": "must-not-survive",
            "authorization": "must-not-survive",
        }
    ]
    payload = sanitized_store_locator_payload(
        cards,
        requested_city="Lund",
        declared_total=1,
    )
    assert b"must-not-survive" not in payload
    assert b"cookie" not in payload.lower()
    assert validated_store_locator(payload) == (
        {
            "name": "Stora Coop Lund",
            "address": "Traktorvägen 2",
            "postal_code": "22660",
            "city": "Lund",
            "store_page_path": "/butiker-erbjudanden/stora-coop/stora-coop-lund/",
        },
    )

    escaped = deepcopy(cards)
    escaped[0]["address_text"] = "Traktorvägen 2, Malmö"
    with pytest.raises(CoopStoreLocatorError, match="escaped requested city"):
        sanitized_store_locator_payload(
            escaped,
            requested_city="Lund",
            declared_total=1,
        )


@pytest.mark.asyncio
async def test_persisted_own_context_requires_promoted_snapshot_for_basket(storage) -> None:  # type: ignore[no-untyped-def]
    observed = datetime(2026, 8, 23, 12, tzinfo=UTC)
    with session_scope(storage) as session:
        store = StoreRepository(session).upsert(
            SourceStore(
                chain=Chain.WILLYS,
                external_id="2176",
                name="Willys Lund",
                address="Magistratsvägen 22",
                postal_code="22643",
                city="Lund",
                online_shopping=True,
                coverage=CoverageLevel.FULL_CATALOG,
                raw_reference="raw:willys:2176",
            ),
            seen_at=observed,
        )
        capability = persisted_own_context_evidence(session, "Lund")
        assert len(capability) == 1
        assert capability[0].local_store_id == store.id
        assert capability[0].snapshot_id is None
        assert capability[0].observed_at is None
        assert capability[0].basket_eligible is False

        snapshots = SnapshotRepository(session)
        snapshot = snapshots.create(
            chain=Chain.WILLYS,
            coverage=CoverageLevel.FULL_CATALOG,
            connector_version="test",
            scope_key="lund",
            created_at=observed,
        )
        snapshots.mark_ready(snapshot.id, at=observed)
        snapshots.promote(snapshot.id, at=observed)

        # A city-level snapshot is not sufficient evidence for every store in
        # that city; the exact store must occur in the persisted source rows.
        raw = RawSnapshotModel(
            id="raw-willys-2176",
            catalog_snapshot_id=snapshot.id,
            chain=Chain.WILLYS.value,
            store_external_id="2176",
            kind="catalog",
            method="GET",
            url="https://public.example/catalog",
            query={},
            fetched_at=observed,
            http_status=200,
            content_type="application/json",
            payload_hash="a" * 64,
            payload_size=2,
            payload_location="fixture://willys-2176.json",
            request_fingerprint="b" * 64,
            connector_version="test",
        )
        source = SourceProductModel(
            id="source-willys-2176",
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            chain=Chain.WILLYS.value,
            store_external_id="2176",
            external_product_id="milk-1",
            gtin="7310000000001",
            name="Mjölk",
            category_path=["Mejeri"],
            sale_price=Decimal("15.90"),
            package_text="1 l",
            package_quantity=Decimal(1),
            package_unit="l",
            sale_unit="st",
            raw_reference="fixture://willys-2176.json",
            fetched_at=observed,
            parser_version="test",
            source_fields={},
            source_record_hash="c" * 64,
        )
        session.add_all([raw, source])
        session.flush()

        eligible = persisted_own_context_evidence(session, "Lund")
        assert len(eligible) == 1
        assert eligible[0].snapshot_id == snapshot.id
        assert eligible[0].observed_at == observed
        assert eligible[0].basket_eligible is True

        report = await OfficialStoreDiscoveryService(
            fixture_official_store_adapters(FIXTURE),
            session=session,
        ).discover_city("Lund", chains=[Chain.WILLYS], observed_at=observed)
        assert report.context_links_verified == 2
        links = StoreContextLinkRepository(session).list_for_physical_store(
            stable_physical_store_id(Chain.WILLYS, "2176")
        )
        assert len(links) == 1
        assert links[0].local_store_id == store.id
        assert links[0].snapshot_id == snapshot.id
        assert links[0].basket_eligible is True


class _FixtureConnector:
    chain = Chain.LIDL

    def __init__(self, stores: list[SourceStore]) -> None:
        self.stores = stores

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        return RawBatch(chain=self.chain, documents=())

    def parse_stores(
        self,
        raw: RawBatch,
        references: list[str],
        area: GeographicArea,
    ) -> list[SourceStore]:
        return self.stores

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_lidl_regional_default_is_excluded_and_scope_totals_reconcile() -> None:
    physical = [
        SourceStore(
            chain=Chain.LIDL,
            external_id=f"TNC0{index}",
            name=f"Lidl Lund {index}",
            city="Lund",
            coverage=CoverageLevel.OFFERS_ONLY,
            price_context_type=PriceContextType.PHYSICAL_STORE,
            raw_reference=f"raw:{index}",
        )
        for index in (1, 2)
    ]
    regional = SourceStore(
        chain=Chain.LIDL,
        external_id="public-default-region-1",
        name="Lidl Sverige – publika erbjudanden",
        city="Sverige",
        coverage=CoverageLevel.OFFERS_ONLY,
        price_context_type=PriceContextType.REGIONAL,
        raw_reference="raw:regional",
    )
    adapter = SourceStoreOfficialAdapter(
        _FixtureConnector([*physical, regional]),
        official_source="https://www.lidl.se/s/sv-SE/butiker/lund/",
        include=lambda store: store.price_context_type == PriceContextType.PHYSICAL_STORE,
    )

    result = await adapter.discover(
        GeographicArea(city="Lund"),
        observed_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )

    assert len(result.stores) == 2
    assert result.source_scope_total == 3
    assert result.excluded_context_count == 1
    assert result.outside_city_count == 0
    assert result.contexts == ()


@pytest.mark.asyncio
async def test_citygross_zero_lund_is_explicit_healthy_no_context() -> None:
    connector = _FixtureConnector([])
    connector.chain = Chain.CITY_GROSS
    adapter = SourceStoreOfficialAdapter(
        connector,
        official_source="https://www.citygross.se/api/v1/PageData/stores",
        allow_empty_result=True,
        empty_city_outcome="no_lund_context",
    )

    result = await adapter.discover(
        GeographicArea(city="Lund"),
        observed_at=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )

    assert result.status == ConnectorStatus.HEALTHY
    assert result.complete is True
    assert result.city_outcome == "no_lund_context"
    assert result.stores == ()


class _FailingAdapter:
    chain = Chain.ICA

    async def discover(self, area: GeographicArea, *, observed_at: datetime):
        raise ValueError("private-session-value-must-not-surface")

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_discovery_error_is_a_closed_reason_without_source_exception_text() -> None:
    report = await OfficialStoreDiscoveryService({Chain.ICA: _FailingAdapter()}).discover_city(
        "Lund"
    )

    assert set(report.errors) == {"ica"}
    assert report.errors["ica"] == ("ValueError: schema_or_identity_contract_failed")
    assert "private-session" not in report.errors["ica"]
