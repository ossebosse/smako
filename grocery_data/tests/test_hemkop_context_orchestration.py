from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from grocery_data import __main__ as cli
from grocery_data.app.connectors.hemkop import (
    HemkopConnector,
    HemkopOperatorCrawlPolicy,
)
from grocery_data.app.connectors.hemkop.client import HemkopSourcePolicyError
from grocery_data.app.domain import (
    Chain,
    Confidence,
    ConnectorStatus,
    CoverageLevel,
    PhysicalStore,
    PriceContextType,
    RunMetrics,
    SourceCollectionAudit,
    SourcePolicy,
    SourceStore,
    StoreContextLink,
    StoreContextRelationType,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.services.collector import CollectionResult
from grocery_data.app.services.hemkop_context_collection import (
    HemkopContextActivationError,
    HemkopMultiContextCollectionPlanner,
    activate_promoted_hemkop_online_context,
)
from grocery_data.app.storage import (
    PhysicalStoreRepository,
    StoreContextLinkRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PriceObservationModel,
    ProductModel,
    RawSnapshotModel,
    SourceProductModel,
)


def _seed_context(
    factory,
    external_id: str,
    *,
    online_link: bool = True,
    city: str = "Lund",
) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 8, tzinfo=UTC)
    physical_id = f"physical:hemkop:{external_id}"
    with session_scope(factory) as session:
        PhysicalStoreRepository(session).upsert(
            PhysicalStore(
                id=physical_id,
                chain=Chain.HEMKOP,
                external_store_id=external_id,
                name=f"Hemköp {city} {external_id}",
                address=f"Testgatan {external_id}",
                postal_code="22358",
                city=city,
                official_source="https://www.hemkop.se/official-locator",
                discovered_at=now,
                last_seen_at=now,
            )
        )
        if online_link:
            StoreContextLinkRepository(session).upsert(
                StoreContextLink(
                    physical_store_id=physical_id,
                    grocery_context_id=f"own:hemkop:{external_id}",
                    source_provider=SourceProvider.OWN,
                    source_channel=SourceChannel.CATALOG,
                    grocery_context_name=f"Hemköp {city} {external_id} Online",
                    price_context_type=PriceContextType.ONLINE_STORE,
                    coverage=CoverageLevel.FULL_ONLINE_CATALOG,
                    relation_type=StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT,
                    confidence=Confidence.EXACT,
                    evidence="official physical_store_external_id exact match",
                    basket_eligible=False,
                    linked_at=now,
                    last_verified_at=now,
                )
            )


@pytest.mark.asyncio
async def test_exact_context_policy_skip_is_not_duplicated_as_unapproved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A resolved REVIEW target must produce one truthful skip diagnostic."""

    class EngineProxy:
        def dispose(self) -> None:
            return None

    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: (
            SimpleNamespace(raw_snapshot_root=tmp_path / "raw"),
            EngineProxy(),
            object(),
        ),
    )
    monkeypatch.setattr(
        cli,
        "_collect_all_plan",
        lambda _cities, *, selected_chains: (
            [],
            [
                {
                    "chain": Chain.HEMKOP.value,
                    "city": "Lund",
                    "status": "skipped",
                    "reason": "no verified OWN source context for this geography",
                }
            ],
        ),
    )
    monkeypatch.setattr(
        cli,
        "_hemkop_collect_all_contexts",
        lambda _factory, _cities: (
            [],
            [
                {
                    "chain": Chain.HEMKOP.value,
                    "city": "Lund",
                    "context_store_id": "4123",
                    "physical_store_id": "physical:hemkop:4123",
                    "grocery_context_id": "own:hemkop:4123",
                    "status": "skipped",
                    "reason": "REVIEW source requires HEMKOP_ALLOW_FULL_CRAWL=true",
                    "source_policy": "review",
                    "operator_opt_in": False,
                    "network_requests": 0,
                }
            ],
            0,
        ),
    )
    args = SimpleNamespace(
        city=["Lund"],
        chain=[Chain.HEMKOP.value],
        context_store_id="4123",
        no_promote=False,
    )

    report, exit_code = await cli._run_collect_all(args)

    assert exit_code == 2
    assert len(report["results"]) == 1
    [result] = report["results"]
    assert result["context_store_id"] == "4123"
    assert result["grocery_context_id"] == "own:hemkop:4123"
    assert result["reason"] == "REVIEW source requires HEMKOP_ALLOW_FULL_CRAWL=true"
    assert all(
        row.get("reason") != "requested context is not an approved exact refresh target"
        for row in report["results"]
    )


def _seed_promoted_snapshot(
    session,  # type: ignore[no-untyped-def]
    *,
    snapshot_id: str,
    external_id: str,
    observed_at: datetime,
    promoted_at: datetime,
    product_count: int = 1,
    priced_product_count: int = 1,
):  # type: ignore[no-untyped-def]
    store = StoreRepository(session).upsert(
        SourceStore(
            chain=Chain.HEMKOP,
            external_id=external_id,
            name=f"Hemköp Lund {external_id} Online",
            address=f"Testgatan {external_id}",
            postal_code="22358",
            city="Lund",
            online_shopping=True,
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
            price_context_type=PriceContextType.ONLINE_STORE,
            physical_store_external_id=external_id,
            raw_reference=f"fixture://hemkop/store/{external_id}",
        ),
        seen_at=observed_at,
    )
    snapshot = CatalogSnapshotModel(
        id=snapshot_id,
        chain=Chain.HEMKOP.value,
        scope_key=f"lund:hemkop:{external_id}",
        coverage=CoverageLevel.FULL_ONLINE_CATALOG.value,
        state="promoted",
        is_active=True,
        connector_version="hemkop-context-hook-test-v1",
        parser_version="hemkop-context-hook-test-v1",
        normalizer_version="normalizer-test-v1",
        created_at=observed_at,
        parsed_at=observed_at,
        validated_at=observed_at,
        health_checked_at=observed_at,
        promoted_at=promoted_at,
    )
    fingerprint = (snapshot_id.replace("-", "") + "0" * 64)[:64]
    raw = RawSnapshotModel(
        id=f"raw-{snapshot_id}",
        catalog_snapshot_id=snapshot.id,
        chain=Chain.HEMKOP.value,
        store_external_id=external_id,
        kind="hemkop_product_category_page",
        method="POST",
        url="https://www.hemkop.se/public-fixture/catalog",
        query={},
        fetched_at=observed_at,
        http_status=200,
        content_type="application/json",
        payload_hash=fingerprint,
        payload_size=2,
        payload_location=f"fixture://hemkop/{snapshot_id}.json",
        request_fingerprint=(fingerprint[::-1] + "1" * 64)[:64],
        connector_version="hemkop-context-hook-test-v1",
    )
    session.add_all([snapshot, raw])
    session.flush()

    for index in range(product_count):
        source = SourceProductModel(
            id=f"src-{snapshot_id}-{index}",
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            chain=Chain.HEMKOP.value,
            store_external_id=external_id,
            external_product_id=f"external-{snapshot_id}-{index}",
            gtin=None,
            name=f"Hemköp fixture product {index}",
            category_path=["Fixture"],
            sale_price=Decimal("29.90"),
            regular_price=Decimal("31.90"),
            package_text="1 st",
            package_quantity=Decimal(1),
            package_unit="st",
            sale_unit="st",
            availability="available",
            raw_reference=f"fixture://hemkop/{snapshot_id}.json#product-{index}",
            fetched_at=observed_at,
            parser_version="hemkop-context-hook-test-v1",
            source_fields={},
            source_record_hash=(f"{index}{fingerprint}" + "2" * 64)[:64],
        )
        session.add(source)
        session.flush()
        product = ProductModel(
            id=f"product-{snapshot_id}-{index}",
            source_product_id=source.id,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            source_product_key=f"hemkop:{external_id}:{snapshot_id}:{index}",
            chain=Chain.HEMKOP.value,
            store_external_id=external_id,
            external_product_id=source.external_product_id,
            name=source.name,
            category_path=["Fixture"],
            canonical_food="milk",
            semantic_confidence=Confidence.HIGH.value,
            sale_model="fixed_package",
            quantity_confidence=Confidence.HIGH.value,
            package_quantity=Decimal(1),
            package_unit="st",
            usable_quantity=Decimal(1),
            usable_unit="st",
            sale_price=Decimal("29.90"),
            sale_unit="st",
            availability="available",
            raw_reference=source.raw_reference,
            parser_version="hemkop-context-hook-test-v1",
            normalizer_version="normalizer-test-v1",
            observed_at=observed_at,
        )
        session.add(product)
        session.flush()
        if index < priced_product_count:
            session.add(
                PriceObservationModel(
                    id=f"price-{snapshot_id}-{index}",
                    catalog_snapshot_id=snapshot.id,
                    product_id=product.id,
                    source_product_id=source.id,
                    store_id=store.id,
                    raw_snapshot_id=raw.id,
                    observed_at=observed_at + timedelta(minutes=index),
                    sale_price=Decimal("29.90"),
                    regular_price=Decimal("31.90"),
                    sale_unit="st",
                )
            )
    session.flush()
    return snapshot, store


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield engine, factory
    finally:
        engine.dispose()


def test_plan_intersects_two_proven_contexts_with_exact_operator_allowlist(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    _seed_context(factory, "4123")
    _seed_context(factory, "4224")
    _seed_context(factory, "4999", online_link=False)

    with session_scope(factory) as session:
        plan = HemkopMultiContextCollectionPlanner(session).plan(
            "Lund",
            policy=HemkopOperatorCrawlPolicy(
                allow_full_crawl=True,
                allowed_store_ids=frozenset({"4123", "4224", "4999", "9999"}),
            ),
        )

    assert plan.eligible_contexts == 2
    assert [target.store_external_id for target in plan.targets] == ["4123", "4224"]
    assert [target.scope_key for target in plan.targets] == [
        "lund:hemkop:4123",
        "lund:hemkop:4224",
    ]
    assert plan.unmatched_allowlist_ids == ("4999", "9999")


def test_managed_dry_run_scopes_global_allowlist_without_cross_city_unmatched(
    storage,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    _seed_context(factory, "4123", city="Lund")
    _seed_context(factory, "4224", city="Lund")
    _seed_context(factory, "4247", city="Malmö")
    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("HEMKOP_STORE_EXTERNAL_IDS", "4123,4224,4247")

    class EngineProxy:
        def dispose(self) -> None:
            return None

    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: (
            SimpleNamespace(
                price_age_warning_hours=36,
                max_price_age_hours=48,
            ),
            EngineProxy(),
            factory,
        ),
    )
    database = tmp_path / "refresh.sqlite"
    database.touch()
    monkeypatch.setattr(cli, "_sqlite_database_path", lambda _settings: database)

    def dry_run(city: str) -> dict[str, object]:
        return cli._daily_refresh_dry_run(
            SimpleNamespace(
                city=[city],
                chain=[Chain.HEMKOP.value],
                context_store_id=None,
                postal_code=None,
                no_external_refresh=True,
            )
        )

    lund = dry_run("Lund")
    malmo = dry_run("Malmö")
    lund_rows = [
        row
        for row in lund["own_targets"]  # type: ignore[union-attr]
        if row.get("context_store_id") is not None
    ]
    malmo_rows = [
        row
        for row in malmo["own_targets"]  # type: ignore[union-attr]
        if row.get("context_store_id") is not None
    ]

    assert {row["context_store_id"] for row in lund_rows} == {"4123", "4224"}
    assert {row["context_store_id"] for row in malmo_rows} == {"4247"}
    assert lund["planning_failures"] == 0
    assert malmo["planning_failures"] == 0


def test_plan_is_inert_without_review_opt_in_or_exact_allowlist(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    _seed_context(factory, "4123")
    _seed_context(factory, "4224")

    with session_scope(factory) as session:
        disabled = HemkopMultiContextCollectionPlanner(session).plan(
            "Lund",
            policy=HemkopOperatorCrawlPolicy(
                allow_full_crawl=False,
                allowed_store_ids=frozenset({"4123", "4224"}),
            ),
        )
        partial = HemkopMultiContextCollectionPlanner(session).plan(
            "Lund",
            policy=HemkopOperatorCrawlPolicy(
                allow_full_crawl=True,
                allowed_store_ids=frozenset({"4123"}),
            ),
        )

    assert disabled.targets == ()
    assert len(disabled.skipped) == 2
    assert [target.store_external_id for target in partial.targets] == ["4123"]
    assert [item.store_external_id for item in partial.skipped] == ["4224"]


@pytest.mark.asyncio
async def test_exact_connector_rechecks_env_and_contains_one_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("HEMKOP_STORE_EXTERNAL_IDS", "4123,4224")
    connector = HemkopConnector.for_exact_full_collection("4123")
    try:
        audit = connector.collection_policy_audit()
        assert audit.operator_opt_in is True
        assert audit.store_allowlist == ("4123",)
        assert connector.client.page_size == 100
        assert connector.minimum_full_catalog_products == 5_000
    finally:
        await connector.aclose()

    with pytest.raises(HemkopSourcePolicyError, match="outside"):
        HemkopConnector.for_exact_full_collection("4999")

    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "false")
    with pytest.raises(HemkopSourcePolicyError, match="explicit"):
        HemkopConnector.for_exact_full_collection(
            "4123",
            policy=HemkopOperatorCrawlPolicy(
                allow_full_crawl=True,
                allowed_store_ids=frozenset({"4123"}),
            ),
        )


def test_context_reconciliation_never_deactivates_a_peer_store(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    with session_scope(factory) as session:
        stores = StoreRepository(session)
        for external_id in ("4123", "4224"):
            stores.upsert(
                SourceStore(
                    chain=Chain.HEMKOP,
                    external_id=external_id,
                    name=f"Hemköp {external_id}",
                    city="Lund",
                    online_shopping=True,
                    coverage=CoverageLevel.FULL_ONLINE_CATALOG,
                    price_context_type=PriceContextType.ONLINE_STORE,
                    raw_reference=f"raw:{external_id}",
                )
            )
        stores.reconcile_scope(
            Chain.HEMKOP,
            city="Lund",
            seen_external_ids={"4123"},
            deactivate_unseen=False,
        )
        assert stores.get(Chain.HEMKOP, "4123").is_active is True
        assert stores.get(Chain.HEMKOP, "4224").is_active is True


def test_promoted_hemkop_snapshot_updates_exact_context_link_lineage(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    _seed_context(factory, "4123")
    observed_at = datetime(2026, 8, 26, 8, 15, tzinfo=UTC)
    promoted_at = observed_at + timedelta(minutes=5)

    with session_scope(factory) as session:
        snapshot, store = _seed_promoted_snapshot(
            session,
            snapshot_id="hemkop-hook-success",
            external_id="4123",
            observed_at=observed_at,
            promoted_at=promoted_at,
        )
        result = activate_promoted_hemkop_online_context(session, snapshot)
        assert result is not None
        assert result.snapshot_id == snapshot.id
        assert result.physical_store_id == "physical:hemkop:4123"
        assert result.grocery_context_id == "own:hemkop:4123"
        assert result.local_store_id == store.id
        assert result.observed_at == observed_at

    with session_scope(factory) as session:
        links = StoreContextLinkRepository(session)
        persisted = links.get(
            "physical:hemkop:4123",
            source_provider=SourceProvider.OWN.value,
            grocery_context_id="own:hemkop:4123",
        )
        assert persisted is not None
        assert len(links.list_for_physical_store("physical:hemkop:4123")) == 1
        assert persisted.local_store_id == result.local_store_id
        assert persisted.snapshot_id == result.snapshot_id
        assert persisted.observed_at == observed_at
        assert persisted.last_verified_at == promoted_at
        assert persisted.basket_eligible is True
        assert persisted.offers_only is False
        assert persisted.is_active is True


def test_incomplete_price_lineage_rolls_back_and_preserves_lkg_link(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    _seed_context(factory, "4123")
    lkg_observed_at = datetime(2026, 8, 25, 7, 30, tzinfo=UTC)
    lkg_promoted_at = lkg_observed_at + timedelta(minutes=5)

    with session_scope(factory) as session:
        lkg_snapshot, lkg_store = _seed_promoted_snapshot(
            session,
            snapshot_id="hemkop-hook-lkg",
            external_id="4123",
            observed_at=lkg_observed_at,
            promoted_at=lkg_promoted_at,
        )
        activated = activate_promoted_hemkop_online_context(session, lkg_snapshot)
        assert activated is not None
        lkg_link = StoreContextLinkRepository(session).get(
            "physical:hemkop:4123",
            source_provider=SourceProvider.OWN.value,
            grocery_context_id="own:hemkop:4123",
        )
        assert lkg_link is not None
        lkg_link_id = lkg_link.id
        lkg_store_id = lkg_store.id

    candidate_observed_at = lkg_observed_at + timedelta(days=1)
    candidate_id = "hemkop-hook-incomplete"
    with factory() as session:
        active_lkg = session.get(CatalogSnapshotModel, "hemkop-hook-lkg")
        assert active_lkg is not None
        active_lkg.is_active = False
        session.flush()
        candidate, _store = _seed_promoted_snapshot(
            session,
            snapshot_id=candidate_id,
            external_id="4123",
            observed_at=candidate_observed_at,
            promoted_at=candidate_observed_at + timedelta(minutes=5),
            product_count=2,
            priced_product_count=1,
        )
        with pytest.raises(
            HemkopContextActivationError,
            match="product/price lineage is incomplete",
        ):
            activate_promoted_hemkop_online_context(session, candidate)
        session.rollback()

    with session_scope(factory) as session:
        lkg_snapshot = session.get(CatalogSnapshotModel, "hemkop-hook-lkg")
        assert lkg_snapshot is not None
        assert lkg_snapshot.is_active is True
        assert session.get(CatalogSnapshotModel, candidate_id) is None
        persisted = StoreContextLinkRepository(session).get(
            "physical:hemkop:4123",
            source_provider=SourceProvider.OWN.value,
            grocery_context_id="own:hemkop:4123",
        )
        assert persisted is not None
        assert persisted.id == lkg_link_id
        assert persisted.local_store_id == lkg_store_id
        assert persisted.snapshot_id == "hemkop-hook-lkg"
        assert persisted.observed_at == lkg_observed_at
        assert persisted.last_verified_at == lkg_promoted_at
        assert persisted.basket_eligible is True
        assert persisted.offers_only is False


@pytest.mark.asyncio
async def test_daily_two_context_failures_are_isolated_and_use_scoped_lkg(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    _seed_context(factory, "4123")
    _seed_context(factory, "4224")
    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.setenv("HEMKOP_STORE_EXTERNAL_IDS", "4123,4224")
    monkeypatch.setattr(
        cli,
        "_runtime",
        lambda: (SimpleNamespace(raw_snapshot_root=tmp_path / "raw"), engine, factory),
    )
    monkeypatch.setattr(
        cli,
        "_collect_all_plan",
        lambda _cities: (
            [],
            [
                {
                    "chain": "hemkop",
                    "city": "Lund",
                    "status": "skipped",
                    "reason": "no verified OWN source context for this geography",
                }
            ],
        ),
    )

    closed: list[str] = []

    class FakeConnector:
        chain = Chain.HEMKOP
        coverage = CoverageLevel.FULL_ONLINE_CATALOG

        def __init__(self, store_id: str) -> None:
            self.store_id = store_id

        def collection_policy_audit(self) -> SourceCollectionAudit:
            return SourceCollectionAudit(
                source_policy=SourcePolicy.REVIEW,
                operator_opt_in=True,
                store_allowlist=(self.store_id,),
                requests_per_second=0.1,
                max_concurrency=1,
            )

        async def aclose(self) -> None:
            closed.append(self.store_id)

    monkeypatch.setattr(
        cli.HemkopConnector,
        "for_exact_full_collection",
        lambda store_id, *, policy: FakeConnector(store_id),
    )

    calls: list[tuple[str, str]] = []

    class FakeCollector:
        def __init__(self, *_: object) -> None:
            pass

        async def collect_area(
            self,
            connector: FakeConnector,
            area,
            *,
            auto_promote: bool,
            scope_key: str,
        ) -> CollectionResult:
            assert area.city == "Lund"
            assert auto_promote is True
            calls.append((connector.store_id, scope_key))
            if connector.store_id == "4123":
                raise RuntimeError("private upstream detail must not be printed")
            return CollectionResult(
                chain=Chain.HEMKOP,
                scope_key=scope_key,
                snapshot_id="snapshot-4224",
                status=ConnectorStatus.HEALTHY,
                promoted=True,
                active_snapshot_id="snapshot-4224",
                stores=(),
                metrics=RunMetrics(products_parsed=9_000, request_count=118),
                warnings=(),
                raw_documents=117,
                source_policy_audit=connector.collection_policy_audit(),
            )

    monkeypatch.setattr(cli, "GroceryCollector", FakeCollector)
    lkg_scopes: list[str] = []

    def fake_lkg(_factory, _chain, scope_key: str) -> dict[str, object]:  # type: ignore[no-untyped-def]
        lkg_scopes.append(scope_key)
        return {
            "active_snapshot_id": f"lkg:{scope_key}",
            "active_snapshot_age_hours": 2.0,
            "active_snapshot_coverage": "full_online_catalog",
        }

    monkeypatch.setattr(cli, "_last_known_good", fake_lkg)

    exit_code = await cli._collect_all(SimpleNamespace(city=["Lund"], no_promote=False))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 2
    assert calls == [
        ("4123", "lund:hemkop:4123"),
        ("4224", "lund:hemkop:4224"),
    ]
    assert closed == ["4123", "4224"]
    assert lkg_scopes == ["lund:hemkop:4123", "lund:hemkop:4224"]
    assert payload["summary"] == {
        "targets": 2,
        "completed": 1,
        "failed": 1,
        "skipped": 0,
        "external_provider_requests": 0,
        "fallbacks_used": 0,
    }
    assert payload["results"][0]["context_store_id"] == "4123"
    assert payload["results"][0]["active_snapshot_id"] == "lkg:lund:hemkop:4123"
    assert payload["results"][1]["context_store_id"] == "4224"
    assert "private upstream detail" not in json.dumps(payload)
