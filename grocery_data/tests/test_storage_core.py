from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateIndex, CreateTable

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    ConnectorStatus,
    CoverageLevel,
    PriceContextType,
    PromotionType,
    SaleModel,
    SnapshotState,
)
from grocery_data.app.domain.health import ConnectorHealth, RunMetrics
from grocery_data.app.domain.product import (
    CanonicalProduct,
    ParseFailure,
    SourceOffer,
    SourceProduct,
)
from grocery_data.app.domain.raw import RawFetch
from grocery_data.app.domain.store import SourceStore
from grocery_data.app.storage import (
    Base,
    CatalogReadRepository,
    ConnectorHealthRepository,
    ParserFailureRepository,
    PriceObservationModel,
    PriceObservationRepository,
    ProductBundleRepository,
    ProductModel,
    PromotionModel,
    RawSnapshotRepository,
    SnapshotRepository,
    SnapshotTransitionError,
    SourceProductModel,
    StoreRepository,
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


def _store(repository: StoreRepository, *, seen_at: datetime) -> object:
    return repository.upsert(
        SourceStore(
            chain=Chain.WILLYS,
            external_id="1234",
            name="Willys Lund Nova",
            address="Företagsvägen 10",
            postal_code="22761",
            city="Lund",
            latitude=Decimal("55.716"),
            longitude=Decimal("13.158"),
            online_shopping=True,
            coverage=CoverageLevel.FULL_CATALOG,
            raw_reference="raw://stores/1234",
        ),
        seen_at=seen_at,
    )


def _snapshot(repository: SnapshotRepository, *, created_at: datetime):
    return repository.create(
        chain=Chain.WILLYS,
        coverage=CoverageLevel.FULL_CATALOG,
        connector_version="willys-v1",
        parser_version="willys-parser-v1",
        normalizer_version="normalizer-v1",
        created_at=created_at,
    )


def _raw(
    repository: RawSnapshotRepository,
    *,
    snapshot_id: str,
    fetched_at: datetime,
    suffix: str,
):
    return repository.record_fetch(
        RawFetch(
            chain=Chain.WILLYS,
            store_external_id="1234",
            kind="catalog",
            method="GET",
            url=f"https://example.invalid/catalog?page={suffix}",
            fetched_at=fetched_at,
            http_status=200,
            content_type="application/json",
            payload=f'{{"page":"{suffix}"}}'.encode(),
            connector_version="willys-v1",
            page_number=int(suffix),
        ),
        catalog_snapshot_id=snapshot_id,
        payload_location=f"raw/willys/{snapshot_id}/{suffix}.json",
    )


def _source_product(
    session: Session,
    *,
    snapshot_id: str,
    raw_id: str,
    store_id: str,
    observed_at: datetime,
    suffix: str,
) -> SourceProductModel:
    row = SourceProductModel(
        catalog_snapshot_id=snapshot_id,
        raw_snapshot_id=raw_id,
        store_id=store_id,
        chain=Chain.WILLYS.value,
        store_external_id="1234",
        external_product_id="pasta-1kg",
        gtin="7310000000001",
        name="Pasta 1 kg",
        category_path=["Skafferi", "Pasta"],
        sale_price=Decimal(20),
        package_quantity=Decimal(1000),
        package_unit="g",
        raw_reference=f"raw://product/{suffix}",
        fetched_at=observed_at,
        parser_version="willys-parser-v1",
        source_fields={},
        source_record_hash=f"{int(suffix):064x}",
    )
    session.add(row)
    session.flush()
    return row


def _product(
    session: Session,
    *,
    source_product: SourceProductModel,
    observed_at: datetime,
) -> ProductModel:
    row = ProductModel(
        source_product_id=source_product.id,
        catalog_snapshot_id=source_product.catalog_snapshot_id,
        raw_snapshot_id=source_product.raw_snapshot_id,
        store_id=source_product.store_id,
        source_product_key="willys:pasta-1kg",
        chain=Chain.WILLYS.value,
        store_external_id="1234",
        external_product_id="pasta-1kg",
        gtin="7310000000001",
        name="Pasta 1 kg",
        category_path=["Skafferi", "Pasta"],
        canonical_food="pasta",
        semantic_confidence="high",
        sale_model="fixed_package",
        quantity_confidence="exact",
        package_quantity=Decimal(1000),
        package_unit="g",
        usable_quantity=Decimal(1000),
        usable_unit="g",
        sale_price=Decimal(20),
        raw_reference="raw://product/1",
        parser_version="willys-parser-v1",
        normalizer_version="normalizer-v1",
        observed_at=observed_at,
    )
    session.add(row)
    session.flush()
    return row


def test_schema_contains_required_tables(storage) -> None:  # type: ignore[no-untyped-def]
    engine, _ = storage
    names = set(inspect(engine).get_table_names())
    assert names == {
        "barcode_scan_diagnostics",
        "beta_feedback",
        "beta_request_metrics",
        "catalog_snapshots",
        "collector_runs",
        "community_evidence_moderation_events",
        "community_evidence_observations",
        "community_receipt_ingestions",
        "connector_health",
        "external_price_candidates",
        "frontend_errors",
        "ica_category_registry",
        "ica_discovery_events",
        "ica_enrichment_runs",
        "ica_product_registry",
        "ica_store_product_observations",
            "parser_failures",
            "physical_identifier_preparations",
            "physical_observation_amendments",
            "physical_observation_v2_evidence",
            "physical_price_observations",
        "physical_store_discovery_health",
        "physical_stores",
            "physical_validation_session_candidates",
            "physical_validation_comparison_versions",
            "physical_validation_session_reconciliations",
            "physical_validation_session_item_identifiers",
            "physical_validation_session_items",
        "physical_validation_sessions",
        "physical_validation_snapshot_locks",
        "price_observations",
        "privacy_erasure_suppressions",
        "products",
        "product_analytics_events",
        "promotions",
            "provider_store_identity_mappings",
            "product_identifier_evidence",
        "raw_snapshots",
            "source_products",
            "shelf_identifier_evidence",
        "store_context_links",
        "stores",
    }


def test_store_upsert_is_idempotent_and_preserves_first_seen(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    first = datetime(2026, 8, 20, 2, tzinfo=UTC)
    second = first + timedelta(days=1)

    with session_scope(factory) as session:
        repository = StoreRepository(session)
        original = _store(repository, seen_at=first)
        store_id = original.id  # type: ignore[attr-defined]
        updated = repository.upsert(
            SourceStore(
                chain=Chain.WILLYS,
                external_id="1234",
                name="Willys Lund Nova (uppdaterad)",
                city="Lund",
                coverage=CoverageLevel.FULL_CATALOG,
                raw_reference="raw://stores/new",
            ),
            seen_at=second,
        )
        assert updated.id == store_id
        assert updated.first_seen_at == first
        assert updated.last_seen_at == second

    with session_scope(factory) as session:
        assert session.scalar(select(func.count()).select_from(type(updated))) == 1
        persisted = StoreRepository(session).get(Chain.WILLYS, "1234")
        assert persisted is not None
        assert persisted.name.endswith("(uppdaterad)")


def test_store_upsert_persists_explicit_price_context_without_inference(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    observed_at = datetime(2026, 8, 23, 8, tzinfo=UTC)

    with session_scope(factory) as session:
        online = StoreRepository(session).upsert(
            SourceStore(
                chain=Chain.CITY_GROSS,
                external_id="3211",
                name="Malmö Hyllie",
                city="Malmö",
                online_shopping=True,
                coverage=CoverageLevel.FULL_ONLINE_CATALOG,
                price_context_type=PriceContextType.ONLINE_STORE,
                physical_store_external_id="169",
                raw_reference="raw://citygross/stores#siteId=169",
            ),
            seen_at=observed_at,
        )
        assert online.price_context_type == "online_store"
        assert online.physical_store_external_id == "169"

        unspecified = StoreRepository(session).upsert(
            SourceStore(
                chain=Chain.WILLYS,
                external_id="no-context",
                name="No inferred context",
                coverage=CoverageLevel.FULL_CATALOG,
                raw_reference="raw://willys/stores/no-context",
            ),
            seen_at=observed_at,
        )
        assert unspecified.price_context_type is None
        assert unspecified.physical_store_external_id is None


def test_raw_snapshot_records_metadata_only_and_redacts_secrets(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        snapshot = _snapshot(SnapshotRepository(session), created_at=now)
        fetch = RawFetch(
            chain=Chain.WILLYS,
            kind="catalog",
            method="get",
            url=(
                "https://example.invalid/catalog?token=secret&accessToken=access-secret"
                "&csrfToken=csrf-secret&sessionId=session-secret&apiKey=api-secret"
                "&nextPageToken=public-page&page=1"
            ),
            query={
                "api_key": "also-secret",
                "refreshToken": "refresh-secret",
                "clientSecret": "client-secret",
                "Ocp-Apim-Subscription-Key": "subscription-secret",
                "clientId": "client-id-secret",
                "pageToken": "public-page-2",
                "page": "1",
            },
            fetched_at=now,
            http_status=200,
            content_type="application/json",
            payload=b'{"products": []}',
            connector_version="willys-v1",
            page_number=1,
        )
        repository = RawSnapshotRepository(session)
        first = repository.record_fetch(
            fetch,
            catalog_snapshot_id=snapshot.id,
            payload_location="raw/willys/snapshot/page-1.json",
        )
        duplicate = repository.record_fetch(
            fetch,
            catalog_snapshot_id=snapshot.id,
            payload_location="raw/willys/snapshot/page-1-again.json",
        )

        assert duplicate.id == first.id
        assert first.payload_size == len(fetch.payload)
        assert first.payload_hash == fetch.payload_hash
        assert "secret" not in first.url
        assert first.query["api_key"] == "[REDACTED]"
        assert first.query["refreshToken"] == "[REDACTED]"
        assert first.query["clientSecret"] == "[REDACTED]"
        assert first.query["Ocp-Apim-Subscription-Key"] == "[REDACTED]"
        assert first.query["clientId"] == "[REDACTED]"
        assert first.query["pageToken"] == "public-page-2"
        assert "nextPageToken=public-page" in first.url
        assert not hasattr(first, "payload")


def test_price_observations_are_historical_and_queryable_at_time(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    day_one = datetime(2026, 8, 20, 2, tzinfo=UTC)
    day_two = day_one + timedelta(days=1)

    with session_scope(factory) as session:
        store = _store(StoreRepository(session), seen_at=day_one)
        snapshots = SnapshotRepository(session)
        raw_repository = RawSnapshotRepository(session)
        first_snapshot = _snapshot(snapshots, created_at=day_one)
        first_raw = _raw(
            raw_repository,
            snapshot_id=first_snapshot.id,
            fetched_at=day_one,
            suffix="1",
        )
        first_source = _source_product(
            session,
            snapshot_id=first_snapshot.id,
            raw_id=first_raw.id,
            store_id=store.id,  # type: ignore[attr-defined]
            observed_at=day_one,
            suffix="1",
        )
        product = _product(
            session,
            source_product=first_source,
            observed_at=day_one,
        )
        observations = PriceObservationRepository(session)
        first = observations.add(
            catalog_snapshot_id=first_snapshot.id,
            product_id=product.id,
            source_product_id=first_source.id,
            store_id=store.id,  # type: ignore[attr-defined]
            raw_snapshot_id=first_raw.id,
            observed_at=day_one,
            sale_price="19.90",
            comparison_price="19.90",
            comparison_unit="kg",
        )
        duplicate = observations.add(
            catalog_snapshot_id=first_snapshot.id,
            product_id=product.id,
            source_product_id=first_source.id,
            store_id=store.id,  # type: ignore[attr-defined]
            raw_snapshot_id=first_raw.id,
            observed_at=day_one,
            sale_price="999.00",
        )
        assert duplicate.id == first.id

        second_snapshot = _snapshot(snapshots, created_at=day_two)
        second_raw = _raw(
            raw_repository,
            snapshot_id=second_snapshot.id,
            fetched_at=day_two,
            suffix="2",
        )
        second_source = _source_product(
            session,
            snapshot_id=second_snapshot.id,
            raw_id=second_raw.id,
            store_id=store.id,  # type: ignore[attr-defined]
            observed_at=day_two,
            suffix="2",
        )
        second_product = _product(
            session,
            source_product=second_source,
            observed_at=day_two,
        )
        observations.add(
            catalog_snapshot_id=second_snapshot.id,
            product_id=second_product.id,
            source_product_id=second_source.id,
            store_id=store.id,  # type: ignore[attr-defined]
            raw_snapshot_id=second_raw.id,
            observed_at=day_two,
            sale_price="17.90",
        )

        history = observations.history_by_source_key(
            chain=Chain.WILLYS,
            source_product_key="willys:pasta-1kg",
            store_id=store.id,  # type: ignore[attr-defined]
        )
        assert [item.sale_price for item in history] == [
            Decimal("19.900000"),
            Decimal("17.900000"),
        ]
        at_first = observations.at_time_by_source_key(
            chain=Chain.WILLYS,
            source_product_key="willys:pasta-1kg",
            store_id=store.id,  # type: ignore[attr-defined]
            at=day_one + timedelta(hours=12),
        )
        assert at_first is not None
        assert at_first.sale_price == Decimal("19.900000")


def test_snapshot_promotion_is_per_chain_and_keeps_last_known_good(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    first_time = datetime(2026, 8, 20, 2, tzinfo=UTC)
    second_time = first_time + timedelta(days=1)

    with session_scope(factory) as session:
        repository = SnapshotRepository(session)
        first = _snapshot(repository, created_at=first_time)
        repository.mark_ready(first.id, at=first_time)
        repository.promote(first.id, at=first_time)
        first_id = first.id

        rejected = _snapshot(repository, created_at=second_time)
        repository.transition(rejected.id, SnapshotState.PARSED, at=second_time)
        repository.reject(rejected.id, reason="schema changed", at=second_time)
        assert repository.active(Chain.WILLYS).id == first_id  # type: ignore[union-attr]

        replacement = _snapshot(repository, created_at=second_time)
        repository.mark_ready(replacement.id, at=second_time)
        repository.promote(replacement.id, at=second_time)
        assert repository.active(Chain.WILLYS).id == replacement.id  # type: ignore[union-attr]
        assert replacement.previous_active_snapshot_id == first_id
        assert repository.last_known_good(Chain.WILLYS).id == replacement.id  # type: ignore[union-attr]


def test_same_chain_can_have_active_snapshots_for_lund_and_malmo(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        repository = SnapshotRepository(session)
        lund = repository.create(
            chain=Chain.WILLYS,
            coverage=CoverageLevel.FULL_CATALOG,
            connector_version="willys-v1",
            scope_key="city:lund",
            created_at=now,
        )
        malmo = repository.create(
            chain=Chain.WILLYS,
            coverage=CoverageLevel.FULL_CATALOG,
            connector_version="willys-v1",
            scope_key="city:malmo",
            created_at=now,
        )
        repository.mark_ready(lund.id, at=now)
        repository.mark_ready(malmo.id, at=now)
        repository.promote(lund.id, at=now)
        repository.promote(malmo.id, at=now)

        assert repository.active(Chain.WILLYS, scope_key="city:lund").id == lund.id  # type: ignore[union-attr]
        assert repository.active(Chain.WILLYS, scope_key="city:malmo").id == malmo.id  # type: ignore[union-attr]


def test_failed_promotion_transaction_leaves_previous_snapshot_active(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        repository = SnapshotRepository(session)
        active = _snapshot(repository, created_at=now)
        repository.mark_ready(active.id, at=now)
        repository.promote(active.id, at=now)
        active_id = active.id
        candidate = _snapshot(repository, created_at=now + timedelta(minutes=1))
        repository.mark_ready(candidate.id, at=now + timedelta(minutes=1))
        candidate_id = candidate.id

    with (
        pytest.raises(RuntimeError, match="simulated failure"),
        session_scope(factory) as session,
    ):
        SnapshotRepository(session).promote(candidate_id)
        raise RuntimeError("simulated failure")

    with session_scope(factory) as session:
        repository = SnapshotRepository(session)
        assert repository.active(Chain.WILLYS).id == active_id  # type: ignore[union-attr]
        candidate = repository.get(candidate_id)
        assert candidate is not None
        assert candidate.state == SnapshotState.HEALTH_CHECKED.value
        assert candidate.is_active is False


def test_snapshot_cannot_bypass_validation(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    with session_scope(factory) as session:
        repository = SnapshotRepository(session)
        snapshot = _snapshot(repository, created_at=datetime.now(tz=UTC))
        with pytest.raises(SnapshotTransitionError):
            repository.transition(snapshot.id, SnapshotState.HEALTH_CHECKED)
        with pytest.raises(SnapshotTransitionError):
            repository.promote(snapshot.id)


def test_mark_ready_resumes_after_a_committed_parse_step(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        repository = SnapshotRepository(session)
        snapshot = _snapshot(repository, created_at=now)
        repository.transition(snapshot.id, SnapshotState.PARSED, at=now)
        snapshot_id = snapshot.id

    with session_scope(factory) as session:
        resumed = SnapshotRepository(session).mark_ready(snapshot_id, at=now)
        assert resumed.state == SnapshotState.HEALTH_CHECKED.value


def test_connector_health_upsert_replaces_current_state(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        repository = ConnectorHealthRepository(session)
        first = repository.upsert(
            ConnectorHealth(
                chain=Chain.WILLYS,
                coverage=CoverageLevel.FULL_CATALOG,
                status=ConnectorStatus.HEALTHY,
                last_success_at=now,
                checked_at=now,
                metrics=RunMetrics(products_parsed=100, products_with_price=99),
            )
        )
        second = repository.upsert(
            ConnectorHealth(
                chain=Chain.WILLYS,
                coverage=CoverageLevel.FULL_CATALOG,
                status=ConnectorStatus.DEGRADED,
                last_success_at=now,
                checked_at=now + timedelta(hours=1),
                metrics=RunMetrics(products_parsed=10, products_quarantined=90),
                warnings=("product count collapsed",),
            )
        )
        assert first.chain == second.chain
        assert second.status == ConnectorStatus.DEGRADED.value
        assert second.warnings == ["product count collapsed"]
        assert second.metrics["products_quarantined"] == 90

        count = session.scalar(select(func.count()).select_from(type(second)))
        assert count == 1


def test_invalid_database_backend_is_rejected() -> None:
    with pytest.raises(ValueError, match="PostgreSQL or SQLite"):
        create_database_engine("mysql+pymysql://localhost/test")


def test_naive_observation_timestamp_is_rejected(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    with session_scope(factory) as session, pytest.raises(ValueError, match="timezone-aware"):
        PriceObservationRepository(session).add(
            catalog_snapshot_id="missing",
            product_id="missing",
            source_product_id="missing",
            store_id="missing",
            raw_snapshot_id="missing",
            observed_at=datetime(2026, 8, 21),  # noqa: DTZ001 - intentionally naive
            sale_price="20",
        )


def test_price_must_be_positive_and_finite(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    with (
        session_scope(factory) as session,
        pytest.raises(ValueError, match="greater than zero"),
    ):
        PriceObservationRepository(session).add(
            catalog_snapshot_id="missing",
            product_id="missing",
            source_product_id="missing",
            store_id="missing",
            raw_snapshot_id="missing",
            observed_at=datetime.now(tz=UTC),
            sale_price="0",
        )


def test_price_observation_table_uses_stable_product_foreign_key(storage) -> None:  # type: ignore[no-untyped-def]
    engine, _ = storage
    foreign_keys = inspect(engine).get_foreign_keys(PriceObservationModel.__tablename__)
    constrained = {column for key in foreign_keys for column in key["constrained_columns"]}
    assert {
        "catalog_snapshot_id",
        "product_id",
        "source_product_id",
        "store_id",
        "raw_snapshot_id",
    } <= constrained


def test_product_bundle_is_atomic_idempotent_and_visible_only_after_promotion(
    storage,  # type: ignore[no-untyped-def]
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        store = _store(StoreRepository(session), seen_at=now)
        snapshots = SnapshotRepository(session)
        snapshot = _snapshot(snapshots, created_at=now)
        raw = _raw(
            RawSnapshotRepository(session),
            snapshot_id=snapshot.id,
            fetched_at=now,
            suffix="1",
        )
        source = SourceProduct(
            chain=Chain.WILLYS,
            store_external_id="1234",
            external_product_id="pasta-1kg",
            gtin="7310000000001",
            name="Pasta 1 kg",
            category_path=("Skafferi", "Pasta"),
            sale_price=Decimal("19.90"),
            regular_price=Decimal("24.90"),
            comparison_price=Decimal("19.90"),
            comparison_unit="kg",
            package_text="1 kg",
            package_quantity=Decimal(1000),
            package_unit="g",
            sale_unit="st",
            offers=(
                SourceOffer(
                    external_id="offer-1",
                    type=PromotionType.MULTIBUY,
                    price=Decimal(30),
                    quantity=2,
                    description="2 för 30",
                ),
            ),
            raw_reference="raw://product/1",
            fetched_at=now,
        )
        canonical = CanonicalProduct(
            source_product_key="willys:pasta-1kg",
            chain=Chain.WILLYS,
            store_external_id="1234",
            external_product_id="pasta-1kg",
            gtin="7310000000001",
            name="Pasta 1 kg",
            category_path=("Skafferi", "Pasta"),
            canonical_food="pasta",
            semantic_confidence=Confidence.HIGH,
            sale_model=SaleModel.FIXED_PACKAGE,
            quantity_confidence=Confidence.EXACT,
            package_quantity=Decimal(1000),
            package_unit="g",
            usable_quantity=Decimal(1000),
            usable_unit="g",
            sale_price=Decimal("19.90"),
            sale_unit="st",
            comparison_price=Decimal("19.90"),
            comparison_unit="kg",
            offers=source.offers,
            raw_reference="raw://product/1",
            parser_version="willys-parser-v1",
            normalizer_version="normalizer-v1",
            observed_at=now,
        )
        repository = ProductBundleRepository(session)

        def fail_late(*args, **kwargs):  # type: ignore[no-untyped-def]
            raise ValueError("simulated late promotion failure")

        with monkeypatch.context() as patcher:
            patcher.setattr(repository, "_promotion", fail_late)
            with pytest.raises(ValueError, match="late promotion failure"):
                repository.persist(
                    source=source,
                    canonical=canonical,
                    catalog_snapshot_id=snapshot.id,
                    raw_snapshot_id=raw.id,
                    store_id=store.id,  # type: ignore[attr-defined]
                )
        assert session.scalar(select(func.count()).select_from(SourceProductModel)) == 0
        assert session.scalar(select(func.count()).select_from(ProductModel)) == 0
        assert session.scalar(select(func.count()).select_from(PriceObservationModel)) == 0
        assert session.scalar(select(func.count()).select_from(PromotionModel)) == 0

        first = repository.persist(
            source=source,
            canonical=canonical,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,  # type: ignore[attr-defined]
        )
        duplicate = repository.persist(
            source=source,
            canonical=canonical,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,  # type: ignore[attr-defined]
        )
        assert duplicate.source_product.id == first.source_product.id
        assert duplicate.product.id == first.product.id
        assert duplicate.price_observation.id == first.price_observation.id
        assert duplicate.promotions[0].id == first.promotions[0].id
        assert CatalogReadRepository(session).list_active(chain=Chain.WILLYS) == []

        snapshots.mark_ready(snapshot.id, at=now)
        snapshots.promote(snapshot.id, at=now)
        active = CatalogReadRepository(session).list_active(chain=Chain.WILLYS)
        assert len(active) == 1
        assert active[0].product.name == "Pasta 1 kg"
        assert active[0].price.sale_price == Decimal("19.900000")
        assert session.scalar(select(func.count()).select_from(PromotionModel)) == 1


def test_parse_failure_is_quarantined_idempotently(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        snapshot = _snapshot(SnapshotRepository(session), created_at=now)
        raw = _raw(
            RawSnapshotRepository(session),
            snapshot_id=snapshot.id,
            fetched_at=now,
            suffix="1",
        )
        failure = ParseFailure(
            raw_record_reference="raw://record/17",
            error_code="unknown_package_format",
            error_message="Unsupported package text: ca 850 g",
            parser_version="willys-parser-v1",
            sample={"package": "ca 850 g"},
        )
        repository = ParserFailureRepository(session)
        first = repository.record(
            failure,
            chain=Chain.WILLYS,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_external_id="1234",
        )
        duplicate = repository.record(
            failure,
            chain=Chain.WILLYS,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_external_id="1234",
        )
        assert duplicate.id == first.id


def test_active_catalog_scope_does_not_mix_cities(storage) -> None:  # type: ignore[no-untyped-def]
    _, factory = storage
    now = datetime(2026, 8, 21, 2, tzinfo=UTC)
    with session_scope(factory) as session:
        snapshots = SnapshotRepository(session)
        lund = snapshots.create(
            chain=Chain.WILLYS,
            coverage=CoverageLevel.FULL_CATALOG,
            connector_version="willys-v1",
            scope_key="city:lund",
            created_at=now,
        )
        malmo = snapshots.create(
            chain=Chain.WILLYS,
            coverage=CoverageLevel.FULL_CATALOG,
            connector_version="willys-v1",
            scope_key="city:malmo",
            created_at=now,
        )
        snapshots.mark_ready(lund.id, at=now)
        snapshots.mark_ready(malmo.id, at=now)
        snapshots.promote(lund.id, at=now)
        snapshots.promote(malmo.id, at=now)
        # Neither empty snapshot leaks the other scope, and both stay independently active.
        reader = CatalogReadRepository(session)
        assert reader.list_active(chain=Chain.WILLYS, scope_key="city:lund") == []
        assert reader.list_active(chain=Chain.WILLYS, scope_key="city:malmo") == []


def test_schema_compiles_for_postgresql_without_connecting() -> None:
    dialect = postgresql.dialect()
    for table in Base.metadata.sorted_tables:
        assert "CREATE TABLE" in str(CreateTable(table).compile(dialect=dialect))
        for index in table.indexes:
            assert "CREATE" in str(CreateIndex(index).compile(dialect=dialect))


def test_catalog_read_hot_paths_have_explicit_indexes(storage) -> None:  # type: ignore[no-untyped-def]
    engine, _ = storage
    inspector = inspect(engine)

    expected = {
        "source_products": "ix_source_products_snapshot_store",
        "products": "ix_products_snapshot_store_name",
        "price_observations": "ix_price_observations_snapshot_source",
        "promotions": "ix_promotions_source_product",
    }
    for table, index_name in expected.items():
        actual = {item["name"] for item in inspector.get_indexes(table)}
        assert index_name in actual
