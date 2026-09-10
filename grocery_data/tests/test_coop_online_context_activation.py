from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select

from grocery_data.app.connectors.coop.online_context import (
    CoopOnlineContextEvidenceBundle,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    Confidence,
    CoverageLevel,
    GeographicArea,
    PhysicalStore,
    ProductParseResult,
    RawBatch,
    RawFetch,
    RunMetrics,
    SaleModel,
    SourceProduct,
)
from grocery_data.app.domain.physical_price import PhysicalPriceObservation
from grocery_data.app.monitoring import fingerprint_json
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.coop_online_context_activation import (
    CoopOnlineContextActivationError,
    CoopOnlineContextActivationService,
)
from grocery_data.app.services.physical_price_candidates import (
    PersistedPhysicalPriceCandidateReader,
)
from grocery_data.app.services.price_context_audit import PriceContextAuditor
from grocery_data.app.services.snapshot_manager import SnapshotManager
from grocery_data.app.storage import (
    PhysicalStoreRepository,
    RawSnapshotRepository,
    SnapshotRepository,
    StoreContextLinkRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    PhysicalStoreModel,
    PriceObservationModel,
    ProductModel,
    SourceProductModel,
    StoreContextLinkModel,
)

NOW = datetime(2026, 8, 25, 12, tzinfo=UTC)
CONTEXT_ID = "730400"
PHYSICAL_ID = "physical:coop:2696"


@pytest.fixture
def storage():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    try:
        yield factory
    finally:
        engine.dispose()


def _physical() -> PhysicalStore:
    return PhysicalStore(
        id=PHYSICAL_ID,
        chain=Chain.COOP,
        external_store_id="2696",
        name="Stora Coop Lund",
        address="Traktorvägen 2",
        postal_code="22660",
        city="Lund",
        official_source="https://www.coop.se/butiker-erbjudanden/",
        discovered_at=NOW - timedelta(days=1),
        last_seen_at=NOW,
    )


def _seed_candidate(
    session,  # type: ignore[no-untyped-def]
    *,
    suffix: str,
    observed_at: datetime,
    include_physical: bool = True,
    include_price: bool = True,
    promote: bool = True,
):  # type: ignore[no-untyped-def]
    evidence = CoopOnlineContextEvidenceBundle.from_path(
        Path(__file__).parents[1]
        / "app"
        / "connectors"
        / "coop"
        / "fixtures"
        / "online_contexts_2026_08_25.json"
    )
    if include_physical and session.get(PhysicalStoreModel, PHYSICAL_ID) is None:
        PhysicalStoreRepository(session).upsert(_physical())
    store = StoreRepository(session).upsert(
        evidence.context(CONTEXT_ID).as_source_store(
            coverage=CoverageLevel.FULL_ONLINE_CATALOG,
            raw_reference=f"fixture:coop:context:{suffix}",
        ),
        seen_at=observed_at,
    )
    snapshots = SnapshotRepository(session)
    snapshot = snapshots.create(
        chain=Chain.COOP,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        connector_version="coop-online-test-v1",
        parser_version="coop-online-parser-test-v1",
        normalizer_version="normalizer-test-v1",
        scope_key="lund:coop:730400",
        created_at=observed_at,
    )
    raw = RawSnapshotRepository(session).record_fetch(
        RawFetch(
            chain=Chain.COOP,
            store_external_id=CONTEXT_ID,
            kind="coop_product_category_page",
            method="POST",
            url="https://external.api.coop.se/personalization/search/entities/by-attribute",
            fetched_at=observed_at,
            http_status=200,
            content_type="application/json",
            payload=f'{{"item":"{suffix}"}}'.encode(),
            connector_version="coop-online-test-v1",
            page_number=0,
        ),
        catalog_snapshot_id=snapshot.id,
        payload_location=f"raw/coop/{snapshot.id}/{suffix}.json",
    )
    source = SourceProductModel(
        id=f"source-{suffix}",
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        chain=Chain.COOP.value,
        store_external_id=CONTEXT_ID,
        external_product_id=f"73000000000{suffix}",
        gtin=None,
        name=f"Coop test product {suffix}",
        category_path=["Test"],
        sale_price=Decimal("19.90"),
        regular_price=Decimal("21.90"),
        package_quantity=Decimal(1),
        package_unit="st",
        sale_unit="st",
        availability="available",
        raw_reference=f"raw:{raw.id}#item",
        fetched_at=observed_at,
        parser_version="coop-online-parser-test-v1",
        source_fields={"price_semantics": "online_price"},
        source_record_hash=f"{int(suffix):064x}",
    )
    session.add(source)
    session.flush()
    product = ProductModel(
        id=f"product-{suffix}",
        source_product_id=source.id,
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        source_product_key=f"coop:{CONTEXT_ID}:product-{suffix}",
        chain=Chain.COOP.value,
        store_external_id=CONTEXT_ID,
        external_product_id=source.external_product_id,
        name=source.name,
        category_path=["Test"],
        canonical_food="test_product",
        semantic_confidence=Confidence.HIGH.value,
        sale_model=SaleModel.FIXED_PACKAGE.value,
        quantity_confidence=Confidence.EXACT.value,
        package_quantity=Decimal(1),
        package_unit="st",
        usable_quantity=Decimal(1),
        usable_unit="st",
        sale_price=Decimal("19.90"),
        sale_unit="st",
        availability="available",
        raw_reference=f"raw:{raw.id}#item",
        parser_version="coop-online-parser-test-v1",
        normalizer_version="normalizer-test-v1",
        observed_at=observed_at,
    )
    session.add(product)
    session.flush()
    if include_price:
        session.add(
            PriceObservationModel(
                id=f"price-{suffix}",
                catalog_snapshot_id=snapshot.id,
                product_id=product.id,
                source_product_id=source.id,
                store_id=store.id,
                raw_snapshot_id=raw.id,
                observed_at=observed_at,
                sale_price=Decimal("19.90"),
                regular_price=Decimal("21.90"),
                sale_unit="st",
            )
        )
        session.flush()

    schema = fingerprint_json({"item": suffix})
    kind = f"{CONTEXT_ID}:coop_product_category_page"
    completion = CatalogCompletion(
        complete=True,
        expected_categories=1,
        completed_categories=1,
        pages_fetched=1,
        products_observed=1,
        expected_products=1,
        raw_rows=1,
        unique_products=1,
        duplicate_products=0,
        expected_pages=1,
    )
    snapshot.metrics = {
        "run_metrics": RunMetrics(
            stores_found=1,
            stores_successful=1,
            products_fetched=1,
            products_parsed=1,
            products_with_price=1,
        ).model_dump(mode="json"),
        "schemas": {kind: schema.model_dump(mode="json")},
        "catalog_completion": {CONTEXT_ID: completion.model_dump(mode="json")},
        "minimum_products_for_full_catalog": 1,
    }
    snapshot.schema_fingerprint = fingerprint_json({kind: schema.digest}).digest
    snapshots.mark_ready(snapshot.id, at=observed_at)
    if promote:
        snapshots.promote(snapshot.id, at=observed_at)
    session.flush()
    return snapshot, store


def test_promoted_full_snapshot_activates_exact_pickup_with_lineage(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        snapshot, store = _seed_candidate(
            session,
            suffix="1",
            observed_at=NOW,
        )
        result = CoopOnlineContextActivationService(session).activate(snapshot.id)
        link = StoreContextLinkRepository(session).get(
            PHYSICAL_ID,
            source_provider="own",
            grocery_context_id="own:coop:730400",
        )

        assert result.links_activated == 1
        assert result.local_store_id == store.id
        assert result.observed_at == NOW
        assert result.pickup_point_external_ids == ("257611",)
        assert link is not None
        assert link.local_store_id == store.id
        assert link.pickup_point_external_id == "257611"
        assert link.coverage == CoverageLevel.FULL_ONLINE_CATALOG.value
        assert link.basket_eligible is True
        assert link.offers_only is False
        assert link.snapshot_id == snapshot.id
        assert link.observed_at == NOW
        assert link.price_context_type == "online_fulfillment"
        assert link.relation_type == "pickup_context"
        assert "public_fulfillment_response" in (link.evidence or "")

        audit = PriceContextAuditor(session).audit("Lund", now=NOW)
        [coop] = audit.chains["coop"].stores
        assert coop.grocery_context_id == "own:coop:730400"
        assert coop.context_scope == "regional_online"
        assert coop.basket_eligible is True


def test_activated_pickup_exposes_local_online_price_to_physical_preview(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        snapshot, _store = _seed_candidate(
            session,
            suffix="7",
            observed_at=NOW,
        )
        CoopOnlineContextActivationService(session).activate(snapshot.id)

        candidates = PersistedPhysicalPriceCandidateReader(session).current_for_observation(
            PhysicalPriceObservation(
                id="preview-only",
                physical_store_id=PHYSICAL_ID,
                product_name="Coop test product 7",
                shelf_price=Decimal("0.01"),
                observed_at=NOW,
                confidence=Confidence.UNKNOWN,
            )
        )

        assert len(candidates) == 1
        assert candidates[0].source_provider == "own"
        assert candidates[0].grocery_context_id == "own:coop:730400"
        assert candidates[0].source_snapshot_id == snapshot.id
        assert candidates[0].current_price == Decimal("19.90")


@pytest.mark.parametrize("case", ["not_promoted", "no_physical", "no_price"])
def test_activation_fails_closed_without_complete_evidence(storage, case: str) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        snapshot, _store = _seed_candidate(
            session,
            suffix="2",
            observed_at=NOW,
            promote=case != "not_promoted",
            include_physical=case != "no_physical",
            include_price=case != "no_price",
        )
        with pytest.raises(CoopOnlineContextActivationError):
            CoopOnlineContextActivationService(session).activate(snapshot.id)
        assert StoreContextLinkRepository(session).list_for_context(
            source_provider="own",
            grocery_context_id="own:coop:730400",
        ) == []


def test_refresh_repoints_existing_link_and_preserves_first_link_time(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        first, _store = _seed_candidate(
            session,
            suffix="3",
            observed_at=NOW,
        )
        CoopOnlineContextActivationService(session).activate(first.id)
        first_link = StoreContextLinkRepository(session).get(
            PHYSICAL_ID,
            source_provider="own",
            grocery_context_id="own:coop:730400",
        )
        assert first_link is not None
        linked_at = first_link.linked_at

        second_time = NOW + timedelta(days=1)
        second, _store = _seed_candidate(
            session,
            suffix="4",
            observed_at=second_time,
        )
        result = CoopOnlineContextActivationService(session).activate(second.id)
        refreshed = StoreContextLinkRepository(session).get(
            PHYSICAL_ID,
            source_provider="own",
            grocery_context_id="own:coop:730400",
        )

        assert refreshed is not None
        assert refreshed.snapshot_id == second.id
        assert refreshed.observed_at == second_time
        assert refreshed.linked_at == linked_at
        assert refreshed.last_verified_at == second_time
        assert result.grocery_context_id == "own:coop:730400"
        assert session.scalar(
            select(func.count())
            .select_from(StoreContextLinkModel)
            .where(StoreContextLinkModel.grocery_context_id == "own:coop:730400")
        ) == 1


def test_snapshot_manager_manual_promotion_activates_pickup_link(storage) -> None:  # type: ignore[no-untyped-def]
    with session_scope(storage) as session:
        candidate, store = _seed_candidate(
            session,
            suffix="5",
            observed_at=NOW,
            promote=False,
        )
        candidate_id = candidate.id
        local_store_id = store.id

    promoted = SnapshotManager(storage, full_catalog_min_products=1).promote(candidate_id)

    assert promoted.is_active is True
    with session_scope(storage) as session:
        link = StoreContextLinkRepository(session).get(
            PHYSICAL_ID,
            source_provider="own",
            grocery_context_id="own:coop:730400",
        )
        assert link is not None
        assert link.local_store_id == local_store_id
        assert link.snapshot_id == candidate_id
        assert link.basket_eligible is True


class _SingleProductCoopConnector:
    """Minimal FULL fixture used only to exercise collector hook ordering."""

    chain = Chain.COOP
    coverage = CoverageLevel.FULL_ONLINE_CATALOG
    connector_version = "coop-auto-hook-test-v1"
    parser_version = "coop-auto-hook-parser-v1"
    minimum_full_catalog_products = 1

    async def fetch_stores(self, area):  # type: ignore[no-untyped-def]
        del area
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    kind="coop_fulfillment_mapping",
                    method="GET",
                    url="https://example.invalid/coop/pointofservice/257611",
                    http_status=200,
                    content_type="application/json",
                    payload=b'{"name":"257611","storeId":"730400"}',
                    connector_version=self.connector_version,
                ),
            ),
        )

    def parse_stores(self, raw, references, area):  # type: ignore[no-untyped-def]
        del raw, area
        evidence = CoopOnlineContextEvidenceBundle.from_path(
            Path(__file__).parents[1]
            / "app"
            / "connectors"
            / "coop"
            / "fixtures"
            / "online_contexts_2026_08_25.json"
        )
        return [
            evidence.context(CONTEXT_ID).as_source_store(
                coverage=self.coverage,
                raw_reference=references[0],
            )
        ]

    def catalog_eligible(self, store):  # type: ignore[no-untyped-def]
        return store.external_id == CONTEXT_ID

    async def fetch_catalog(self, store):  # type: ignore[no-untyped-def]
        return RawBatch(
            chain=self.chain,
            documents=(
                RawFetch(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    kind="coop_product_category_page",
                    method="POST",
                    url="https://example.invalid/coop/products",
                    fetched_at=NOW,
                    http_status=200,
                    content_type="application/json",
                    payload=b'{"items":[{"id":"1"}]}',
                    connector_version=self.connector_version,
                    page_number=0,
                ),
            ),
            catalog_completion=CatalogCompletion(
                complete=True,
                expected_categories=1,
                completed_categories=1,
                pages_fetched=1,
                products_observed=1,
                expected_products=1,
                raw_rows=1,
                unique_products=1,
                duplicate_products=0,
                expected_pages=1,
            ),
        )

    def parse_catalog(self, raw, references, store):  # type: ignore[no-untyped-def]
        return ProductParseResult(
            products=[
                SourceProduct(
                    chain=self.chain,
                    store_external_id=store.external_id,
                    external_product_id="1",
                    name="Mjölk 1 l",
                    sale_price=Decimal("15.90"),
                    regular_price=Decimal("15.90"),
                    package_text="1 l",
                    package_quantity=Decimal(1),
                    package_unit="l",
                    sale_unit="st",
                    availability="available",
                    raw_reference=f"{references[0]}#items[0]",
                    fetched_at=raw.documents[0].fetched_at,
                )
            ]
        )

    async def fetch_offers(self, store):  # type: ignore[no-untyped-def]
        del store
        return RawBatch(chain=self.chain, documents=())

    async def aclose(self) -> None:
        return None


@pytest.mark.asyncio
async def test_collector_auto_promotion_activates_after_store_reconciliation(
    storage, tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    from grocery_data.app.services.collector import GroceryCollector
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore

    with session_scope(storage) as session:
        PhysicalStoreRepository(session).upsert(_physical())
    collector = GroceryCollector(
        storage,
        FilesystemRawSnapshotStore(tmp_path / "raw"),
        normalizer=ProductNormalizer(),
        full_catalog_min_products=1,
    )

    result = await collector.collect_area(
        _SingleProductCoopConnector(),
        GeographicArea(city="Lund"),
        scope_key="lund:coop:730400",
    )

    assert result.promoted is True
    with session_scope(storage) as session:
        link = StoreContextLinkRepository(session).get(
            PHYSICAL_ID,
            source_provider="own",
            grocery_context_id="own:coop:730400",
        )
        assert link is not None
        assert link.snapshot_id == result.snapshot_id
        assert link.basket_eligible is True


def test_explicit_database_cli_activates_existing_promoted_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from grocery_data import __main__ as cli

    database = tmp_path / "coop-candidate.sqlite"
    engine = create_database_engine(f"sqlite+pysqlite:///{database.as_posix()}")
    create_schema(engine)
    factory = create_session_factory(engine)
    with session_scope(factory) as session:
        snapshot, _store = _seed_candidate(
            session,
            suffix="6",
            observed_at=NOW,
        )
        snapshot_id = snapshot.id
    engine.dispose()
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "true")

    exit_code = cli.main(
        [
            "activate-coop-online-context",
            "--database",
            str(database),
            "--snapshot-id",
            snapshot_id,
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["network_requests"] == 0
    assert payload["price_semantics"] == "online_price"
    assert payload["physical_shelf_price_claimed"] is False
    assert payload["result"]["snapshot_id"] == snapshot_id
    verification_engine = create_database_engine(
        f"sqlite+pysqlite:///{database.as_posix()}"
    )
    verification_factory = create_session_factory(verification_engine)
    with session_scope(verification_factory) as session:
        link = StoreContextLinkRepository(session).get(
            PHYSICAL_ID,
            source_provider="own",
            grocery_context_id="own:coop:730400",
        )
        assert link is not None
        assert link.snapshot_id == snapshot_id
    verification_engine.dispose()
