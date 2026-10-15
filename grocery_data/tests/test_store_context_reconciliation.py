from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    PhysicalStore,
    PriceContextType,
    SourceStore,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.services.store_context_reconciliation import (
    CredentialFreeContextImporter,
    ExactStoreContextReconciler,
    OwnContextEvidenceProjector,
    read_credential_free_context_bundle,
)
from grocery_data.app.services.store_coverage import GroceryContextEvidence
from grocery_data.app.storage import (
    PhysicalStoreRepository,
    StoreRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    session_scope,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreContextLinkModel,
)


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
    chain: Chain,
    external_id: str,
    *,
    name: str,
    address: str,
    postal_code: str,
    now: datetime,
) -> PhysicalStore:
    return PhysicalStore(
        id=f"physical:{chain.value}:{external_id}",
        chain=chain,
        external_store_id=external_id,
        name=name,
        address=address,
        postal_code=postal_code,
        city="Lund",
        official_source=f"https://official.example/{chain.value}/{external_id}",
        discovered_at=now,
        last_seen_at=now,
    )


def _own_store(
    chain: Chain,
    external_id: str,
    *,
    name: str,
    address: str,
    postal_code: str,
    coverage: CoverageLevel,
    context_type: PriceContextType,
    physical_external_id: str | None,
) -> SourceStore:
    return SourceStore(
        chain=chain,
        external_id=external_id,
        name=name,
        address=address,
        postal_code=postal_code,
        city="Lund",
        online_shopping=True,
        coverage=coverage,
        price_context_type=context_type,
        physical_store_external_id=physical_external_id,
        raw_reference="fixture://store-context",
    )


def _attach_snapshot(
    session,  # type: ignore[no-untyped-def]
    store,  # type: ignore[no-untyped-def]
    *,
    snapshot_id: str,
    now: datetime,
    state: str = "promoted",
    active: bool = True,
) -> None:
    snapshot = CatalogSnapshotModel(
        id=snapshot_id,
        chain=store.chain,
        scope_key=f"context:{store.external_id}:{snapshot_id}",
        coverage=store.coverage,
        state=state,
        is_active=active,
        connector_version="fixture-v1",
        parser_version="fixture-v1",
        normalizer_version="fixture-v1",
        created_at=now,
        promoted_at=now if state == "promoted" else None,
    )
    raw = RawSnapshotModel(
        id=f"raw-{snapshot_id}",
        catalog_snapshot_id=snapshot_id,
        chain=store.chain,
        store_external_id=store.external_id,
        kind="catalog",
        method="GET",
        url="https://public.example/catalog",
        query={},
        fetched_at=now,
        http_status=200,
        content_type="application/json",
        payload_hash="a" * 64,
        payload_size=2,
        payload_location=f"fixture://{snapshot_id}.json",
        request_fingerprint=(snapshot_id * 64)[:64],
        connector_version="fixture-v1",
    )
    source = SourceProductModel(
        id=f"source-{snapshot_id}",
        catalog_snapshot_id=snapshot_id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id="product-1",
        gtin="7310000000001",
        name="Fixture product",
        category_path=[],
        sale_price=Decimal("29.90"),
        package_text="1 st",
        package_quantity=Decimal(1),
        package_unit="st",
        sale_unit="st",
        raw_reference="fixture://product",
        fetched_at=now,
        parser_version="fixture-v1",
        source_fields={},
        source_record_hash=(snapshot_id[::-1] * 64)[:64],
    )
    session.add_all([snapshot, raw, source])
    session.flush()


def test_own_context_requires_active_promoted_snapshot_for_basket(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    with session_scope(storage) as session:
        store = StoreRepository(session).upsert(
            _own_store(
                Chain.HEMKOP,
                "4123",
                name="Hemköp Lund Karhögstorg Online",
                address="Karhögstorg 2A",
                postal_code="22358",
                coverage=CoverageLevel.FULL_ONLINE_CATALOG,
                context_type=PriceContextType.ONLINE_STORE,
                physical_external_id="4123",
            ),
            seen_at=now,
        )
        _attach_snapshot(session, store, snapshot_id="hemkop-promoted", now=now)

        contexts = OwnContextEvidenceProjector(session).project_city("Lund")
        assert len(contexts) == 1
        context = contexts[0]
        assert context.grocery_context_id == "own:hemkop:4123"
        assert context.local_store_id == store.id
        assert context.snapshot_id == "hemkop-promoted"
        assert context.source_provider == SourceProvider.OWN
        assert context.source_channel == SourceChannel.CATALOG
        assert context.basket_eligible is True

        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.HEMKOP,
                "4123",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="22358",
                now=now,
            )
        )
        report = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", contexts, verified_at=now
        )
        assert report.linked_physical_stores == (physical.id,)
        row = session.query(StoreContextLinkModel).one()
        assert row.local_store_id == store.id
        assert row.source_provider == "own"
        assert row.basket_eligible is True


def test_unpromoted_own_snapshot_never_claims_basket_capability(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    with session_scope(storage) as session:
        store = StoreRepository(session).upsert(
            _own_store(
                Chain.WILLYS,
                "2176",
                name="Willys Lund",
                address="Magistratsvägen 22",
                postal_code="22643",
                coverage=CoverageLevel.FULL_CATALOG,
                context_type=PriceContextType.ONLINE_STORE,
                physical_external_id="2176",
            ),
            seen_at=now,
        )
        _attach_snapshot(
            session,
            store,
            snapshot_id="willys-candidate",
            now=now,
            state="validated",
            active=True,
        )
        context = OwnContextEvidenceProjector(session).project_city("Lund")[0]
        assert context.snapshot_id is None
        assert context.observed_at is None
        assert context.basket_eligible is False


def test_credential_free_primat_projection_maps_only_official_identity(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    exact_export = {
        "schema": "grocery-context-evidence-v1",
        "provider": "primat",
        "source_channel": "catalog",
        "context_id": "primat:ica:2771",
        "chain": "ica",
        "name": "ICA official context",
        "city": "Lund",
        "price_context_type": "physical_store",
        "coverage": "full_catalog",
        "source_snapshot_id": "primat-observation-1",
        "source_observed_at": now.isoformat(),
        "connector_status": "healthy",
        "physical_identity": {
            "basis": "official_external_id",
            "official_external_store_id": "2771",
        },
    }
    # Pin freshness to the fixture clock. Relying on wall-clock time makes a
    # once-valid full context become stale as the test suite ages.
    contexts = CredentialFreeContextImporter.import_rows([exact_export], now=now)
    assert contexts[0].basket_eligible is True
    assert contexts[0].external_store_id is None
    assert contexts[0].physical_store_external_id == "2771"

    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.ICA,
                "2771",
                name="ICA Lund",
                address="Exaktgatan 1",
                postal_code="22350",
                now=now,
            )
        )
        report = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", contexts, verified_at=now
        )
        assert report.linked_physical_stores == (physical.id,)
        link = session.query(StoreContextLinkModel).one()
        assert link.local_store_id is None
        assert link.source_provider == "primat"

    with pytest.raises(ValidationError):
        CredentialFreeContextImporter.import_rows([{**exact_export, "api_key": "must-not-enter"}])
    with pytest.raises(ValidationError):
        CredentialFreeContextImporter.import_rows([{**exact_export, "source_observed_at": None}])
    with pytest.raises(ValidationError):
        CredentialFreeContextImporter.import_rows(
            [{key: value for key, value in exact_export.items() if key != "schema"}]
        )


def test_context_bundle_reader_is_bounded_and_rejects_legacy_or_secret_fields(
    tmp_path: Path,
) -> None:
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    item = {
        "schema": "grocery-context-evidence-v1",
        "provider": "primat",
        "source_channel": "catalog",
        "context_id": "primat:ica:2771",
        "chain": "ica",
        "name": "ICA official context",
        "city": "Lund",
        "price_context_type": "physical_store",
        "coverage": "full_catalog",
        "source_snapshot_id": "primat-observation-1",
        "source_observed_at": now.isoformat(),
        "connector_status": "healthy",
        "physical_identity": {
            "basis": "official_external_id",
            "official_external_store_id": "2771",
        },
    }
    valid = {
        "schema": "grocery-context-evidence-bundle-v1",
        "postal_code": "22350",
        "captured_at": now.isoformat(),
        "items": [item],
    }
    valid_path = tmp_path / "valid.json"
    valid_path.write_text(json.dumps(valid), encoding="utf-8")
    bundle = read_credential_free_context_bundle(valid_path)
    assert bundle.postal_code == "22350"
    assert bundle.items[0].context_id == "primat:ica:2771"

    missing_schema_path = tmp_path / "missing-schema.json"
    missing_schema_path.write_text(
        json.dumps({key: value for key, value in valid.items() if key != "schema"}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        read_credential_free_context_bundle(missing_schema_path)

    legacy_path = tmp_path / "legacy-list.json"
    legacy_path.write_text(json.dumps([item]), encoding="utf-8")
    with pytest.raises(ValidationError):
        read_credential_free_context_bundle(legacy_path)

    secret_path = tmp_path / "secret-item.json"
    secret_path.write_text(
        json.dumps({**valid, "items": [{**item, "cookie": "must-not-enter"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        read_credential_free_context_bundle(secret_path)

    shaped_value_path = tmp_path / "credential-shaped-value.json"
    shaped_value_path.write_text(
        json.dumps({**valid, "items": [{**item, "name": "Bearer hidden-value"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="credential-shaped value"):
        read_credential_free_context_bundle(shaped_value_path)

    duplicate_path = tmp_path / "duplicate.json"
    duplicate_path.write_text(
        '{"schema":"grocery-context-evidence-bundle-v1",'
        '"schema":"grocery-context-evidence-bundle-v1"}',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate key"):
        read_credential_free_context_bundle(duplicate_path)

    oversized_path = tmp_path / "oversized.json"
    oversized_path.write_bytes(b"{" + b" " * 100 + b"}")
    with pytest.raises(ValueError, match="100 MB import limit"):
        read_credential_free_context_bundle(oversized_path, max_bytes=100)


def test_ica_primat_store_id_maps_exactly_to_official_account_alias(storage) -> None:  # type: ignore[no-untyped-def]
    """Clemenstorget accountNumber=1004409 and storeId=2771 are one site."""

    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    context = CredentialFreeContextImporter.import_rows(
        [
            {
                "schema": "grocery-context-evidence-v1",
                "provider": "primat",
                "context_id": "primat:ica:2771",
                "chain": "ica",
                "name": "ICA Kvantum Malmborgs Clemenstorget",
                "city": "Lund",
                "price_context_type": "physical_store",
                "coverage": "full_catalog",
                "source_snapshot_id": "primat-clemenstorget-1",
                "source_observed_at": now,
                "connector_status": "healthy",
                "physical_identity": {
                    "basis": "official_external_id",
                    "official_external_store_id": "2771",
                },
            }
        ],
        now=now,
    )
    official = _physical(
        Chain.ICA,
        "1004409",
        name="ICA Kvantum Malmborgs Clemenstorget",
        address="Clemenstorget 5",
        postal_code="22221",
        now=now,
    ).model_copy(update={"external_store_aliases": ("2771",)})

    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(official)
        assert physical.id == "physical:ica:1004409"
        assert physical.external_store_aliases == ["2771"]
        assert (
            PhysicalStoreRepository(session).get_by_any_external_id(Chain.ICA, "2771").id
            == physical.id
        )

        result = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", context, verified_at=now
        )
        assert result.linked_physical_stores == (physical.id,)
        assert result.decisions[0].confidence == Confidence.EXACT
        assert "primary/alias" in result.decisions[0].evidence


@pytest.mark.parametrize(
    ("updates", "expected_active"),
    [
        ({"coverage": "partial_catalog"}, True),
        ({"source_snapshot_id": None, "source_observed_at": None}, True),
        ({"connector_status": "broken"}, False),
    ],
)
def test_external_context_without_healthy_fresh_full_evidence_is_not_basket_capable(
    updates: dict[str, object],
    expected_active: bool,
) -> None:
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    row: dict[str, object] = {
        "schema": "grocery-context-evidence-v1",
        "provider": "primat",
        "context_id": "primat:ica:2771",
        "chain": "ica",
        "name": "ICA Lund",
        "city": "Lund",
        "price_context_type": "physical_store",
        "coverage": "full_catalog",
        "source_snapshot_id": "primat-observation",
        "source_observed_at": now,
        "connector_status": "healthy",
        "physical_identity": {
            "basis": "official_external_id",
            "official_external_store_id": "2771",
        },
    }
    context = CredentialFreeContextImporter.import_rows([{**row, **updates}], now=now)[0]
    assert context.basket_eligible is False
    assert context.active is expected_active


def test_external_older_base_observation_remains_basket_capable() -> None:
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    context = CredentialFreeContextImporter.import_rows(
        [
            {
                "schema": "grocery-context-evidence-v1",
                "provider": "primat",
                "context_id": "primat:ica:2771",
                "chain": "ica",
                "name": "ICA Lund",
                "coverage": "full_catalog",
                "source_snapshot_id": "old-observation",
                "source_observed_at": now - timedelta(hours=49),
                "connector_status": "healthy",
                "physical_identity": {
                    "basis": "official_external_id",
                    "official_external_store_id": "2771",
                },
            }
        ],
        now=now,
        max_age_hours=48,
    )[0]
    assert context.basket_eligible is True


def test_external_address_match_is_exact_and_names_are_never_fuzzy(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    base = {
        "schema": "grocery-context-evidence-v1",
        "provider": "primat",
        "context_id": "primat:coop:3813",
        "chain": "coop",
        "name": "Coop Mårtenstorget",
        "city": "Lund",
        "price_context_type": "physical_store",
        "coverage": "full_catalog",
        "source_snapshot_id": "primat-coop-1",
        "source_observed_at": now,
        "connector_status": "healthy",
    }
    wrong = CredentialFreeContextImporter.import_rows(
        [
            {
                **base,
                "physical_identity": {
                    "basis": "official_address_postal_code",
                    "address": "Mårtenstorget 12",
                    "postal_code": "22351",
                },
            }
        ]
    )
    exact = CredentialFreeContextImporter.import_rows(
        [
            {
                **base,
                "physical_identity": {
                    "basis": "official_address_postal_code",
                    "address": "Mårtenstorget 11",
                    "postal_code": "22351",
                },
            }
        ]
    )
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                name="Coop Mårtenstorget",
                address="Mårtenstorget 11",
                postal_code="22351",
                now=now,
            )
        )
        rejected = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", wrong, verified_at=now
        )
        assert rejected.linked_physical_stores == ()
        assert rejected.missing_physical_stores == (physical.id,)
        accepted = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", exact, verified_at=now
        )
        assert accepted.linked_physical_stores == (physical.id,)
        assert accepted.decisions[0].confidence == Confidence.HIGH


def test_ica_coop_own_offers_need_explicit_official_context_identity(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    unproven = GroceryContextEvidence(
        grocery_context_id="own:coop:unproven-offers",
        chain=Chain.COOP,
        name="Coop Mårtenstorget",
        city="Lund",
        address="Mårtenstorget 11",
        postal_code="22351",
        source_provider=SourceProvider.OWN,
        source_channel=SourceChannel.OFFERS,
        coverage=CoverageLevel.OFFERS_ONLY,
        offers_only=True,
        snapshot_id="coop-offers-1",
        observed_at=now,
    )
    proven = unproven.model_copy(
        update={
            "grocery_context_id": "own:coop:3813-offers",
            "physical_store_external_id": "3813",
        }
    )
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                name="Coop Mårtenstorget",
                address="Mårtenstorget 11",
                postal_code="22351",
                now=now,
            )
        )
        rejected = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", [unproven], verified_at=now
        )
        assert rejected.linked_physical_stores == ()
        accepted = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", [proven], verified_at=now
        )
        assert accepted.linked_physical_stores == (physical.id,)


def test_own_offer_projection_uses_independent_official_registry_identity(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    with session_scope(storage) as session:
        store = StoreRepository(session).upsert(
            _own_store(
                Chain.COOP,
                "3813",
                name="Coop Mårtenstorget",
                address="Mårtenstorget 11",
                postal_code="22351",
                coverage=CoverageLevel.OFFERS_ONLY,
                context_type=PriceContextType.PHYSICAL_STORE,
                physical_external_id=None,
            ),
            seen_at=now,
        )
        _attach_snapshot(session, store, snapshot_id="coop-offers-promoted", now=now)
        unproven = OwnContextEvidenceProjector(session).project_city("Lund")[0]
        assert unproven.physical_store_external_id is None
        assert unproven.address is None

        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "3813",
                name="Coop Mårtenstorget",
                address="Mårtenstorget 11",
                postal_code="22351",
                now=now,
            )
        )
        proven = OwnContextEvidenceProjector(session).project_city("Lund")[0]
        assert proven.physical_store_external_id == "3813"
        assert proven.offers_only is True
        result = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", [proven], verified_at=now
        )
        assert result.linked_physical_stores == (physical.id,)


def test_lidl_regional_own_offers_never_attach_to_a_physical_store(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    regional = GroceryContextEvidence(
        grocery_context_id="public-default-region",
        chain=Chain.LIDL,
        name="Lidl public offer region",
        city="Lund",
        physical_store_external_id="0163",
        price_context_type=PriceContextType.REGIONAL,
        source_provider=SourceProvider.OWN,
        source_channel=SourceChannel.OFFERS,
        coverage=CoverageLevel.OFFERS_ONLY,
        offers_only=True,
        snapshot_id="lidl-offers",
        observed_at=now,
    )
    primat = CredentialFreeContextImporter.import_rows(
        [
            {
                "schema": "grocery-context-evidence-v1",
                "provider": "primat",
                "context_id": "primat:lidl:0163",
                "chain": "lidl",
                "name": "Lidl Lund",
                "city": "Lund",
                "price_context_type": "physical_store",
                "coverage": "full_catalog",
                "source_snapshot_id": "primat-lidl-1",
                "source_observed_at": now,
                "connector_status": "healthy",
                "physical_identity": {
                    "basis": "official_external_id",
                    "official_external_store_id": "0163",
                },
            }
        ]
    )[0]
    with session_scope(storage) as session:
        physical = PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.LIDL,
                "0163",
                name="Lidl Lund",
                address="Magistratsvägen 6",
                postal_code="22643",
                now=now,
            )
        )
        own_result = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", [regional], verified_at=now
        )
        assert own_result.linked_physical_stores == ()
        external_result = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", [primat], verified_at=now
        )
        assert external_result.linked_physical_stores == (physical.id,)
        assert session.query(StoreContextLinkModel).one().source_provider == "primat"


def test_authoritative_projection_deactivates_only_superseded_source_links(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    physical = _physical(
        Chain.ICA,
        "2771",
        name="ICA Lund",
        address="Exaktgatan 1",
        postal_code="22350",
        now=now,
    )

    def context(
        context_id: str,
        provider: SourceProvider,
        *,
        chain: Chain = Chain.ICA,
        external_id: str = "2771",
    ) -> GroceryContextEvidence:
        return GroceryContextEvidence(
            grocery_context_id=context_id,
            chain=chain,
            name=f"{chain.value} Lund context",
            physical_store_external_id=external_id,
            price_context_type=PriceContextType.PHYSICAL_STORE,
            source_provider=provider,
            source_channel=SourceChannel.CATALOG,
            coverage=CoverageLevel.FULL_CATALOG,
            basket_eligible=True,
            snapshot_id=f"snapshot:{context_id}",
            observed_at=now,
        )

    with session_scope(storage) as session:
        PhysicalStoreRepository(session).upsert(physical)
        PhysicalStoreRepository(session).upsert(
            _physical(
                Chain.COOP,
                "coop-lund",
                name="Coop Lund",
                address="Coopgatan 1",
                postal_code="22350",
                now=now,
            )
        )
        reconciler = ExactStoreContextReconciler(session)
        reconciler.reconcile_city("Lund", [context("primat:old", SourceProvider.PRIMAT)])
        reconciler.reconcile_city("Lund", [context("licensed:stable", SourceProvider.LICENSED)])
        reconciler.reconcile_city(
            "Lund",
            [
                context(
                    "primat:coop:old",
                    SourceProvider.PRIMAT,
                    chain=Chain.COOP,
                    external_id="coop-lund",
                )
            ],
        )

        report = reconciler.reconcile_city(
            "Lund",
            [context("primat:new", SourceProvider.PRIMAT)],
            verified_at=now + timedelta(hours=1),
            authoritative_sources={(Chain.ICA, SourceProvider.PRIMAT, SourceChannel.CATALOG)},
        )
        assert report.links_deactivated == 1
        rows = {
            (row.source_provider, row.grocery_context_id): row.is_active
            for row in session.query(StoreContextLinkModel).all()
        }
        assert rows == {
            ("primat", "primat:old"): False,
            ("primat", "primat:new"): True,
            ("primat", "primat:coop:old"): True,
            ("licensed", "licensed:stable"): True,
        }

        with pytest.raises(ValueError, match="projection is empty"):
            reconciler.reconcile_city(
                "Lund",
                [],
                authoritative_sources={(Chain.ICA, SourceProvider.PRIMAT, SourceChannel.CATALOG)},
            )


def test_citygross_malmo_context_is_not_imported_as_a_lund_store(storage) -> None:  # type: ignore[no-untyped-def]
    now = datetime(2026, 8, 23, 9, tzinfo=UTC)
    hyllie = GroceryContextEvidence(
        grocery_context_id="own:citygross:3211",
        chain=Chain.CITY_GROSS,
        name="City Gross Malmö Hyllie Online",
        city="Malmö",
        address="Hyllie Stationsväg 22",
        postal_code="21532",
        external_store_id="3211",
        physical_store_external_id="3211",
        price_context_type=PriceContextType.ONLINE_STORE,
        source_provider=SourceProvider.OWN,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        basket_eligible=True,
        snapshot_id="cg-hyllie",
        observed_at=now,
    )
    with session_scope(storage) as session:
        result = ExactStoreContextReconciler(session).reconcile_city(
            "Lund", [hyllie], verified_at=now
        )
        assert result.physical_stores_considered == 0
        assert result.links_written == 0
        assert result.missing_physical_stores == ()
