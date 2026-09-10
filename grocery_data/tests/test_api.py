from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from grocery_data.app.api.catalog import _effective_store_context, _product_rows_statement
from grocery_data.app.api.common import freshness_for_snapshot
from grocery_data.app.config import GroceryDataSettings, load_repository_dotenv
from grocery_data.app.main import _default_session_factory, create_app
from grocery_data.app.services.snapshot_manager import SnapshotManager
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    CollectorRunModel,
    ConnectorHealthModel,
    ParserFailureModel,
    PriceObservationModel,
    ProductModel,
    PromotionModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)


@pytest.fixture
def api_client():  # type: ignore[no-untyped-def]
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    now = datetime.now(tz=UTC) - timedelta(hours=2)
    today = now.date()

    with factory() as session:
        store = StoreModel(
            id="store-willys-lund",
            chain="willys",
            external_id="2354",
            name="Willys Lund Nova",
            address="Företagsvägen 10",
            postal_code="227 61",
            city="Lund",
            latitude=Decimal("55.716"),
            longitude=Decimal("13.158"),
            online_shopping=True,
            coverage="full_catalog",
            price_context_type="physical_store",
            physical_store_external_id="2354",
            raw_reference="raw://stores/2354",
            is_active=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        store_without_snapshot = StoreModel(
            id="store-coop-lund",
            chain="coop",
            external_id="coop-1",
            name="Coop Lund",
            postal_code="223 50",
            city="Lund",
            coverage="offers_only",
            raw_reference="raw://stores/coop-1",
            is_active=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        malmo_store = StoreModel(
            id="store-willys-malmo",
            chain="willys",
            external_id="willys-malmo-1",
            name="Willys Malmö",
            postal_code="211 20",
            city="Malmö",
            coverage="full_catalog",
            raw_reference="raw://stores/willys-malmo-1",
            is_active=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        run = CollectorRunModel(
            id="run-1",
            chain="willys",
            scope={"city": "Lund", "token": "must-not-leak"},
            status="success",
            connector_version="willys-v1",
            parser_version="willys-parser-v1",
            normalizer_version="normalizer-v1",
            started_at=now - timedelta(minutes=5),
            finished_at=now,
            successful=True,
            metrics={"products_parsed": 1, "products_with_price": 1},
            error_summary="token=run-secret was redacted",
        )
        snapshot = CatalogSnapshotModel(
            id="snapshot-active",
            chain="willys",
            scope_key="Lund",
            coverage="full_catalog",
            state="promoted",
            is_active=True,
            collector_run_id=run.id,
            connector_version="willys-v1",
            parser_version="willys-parser-v1",
            normalizer_version="normalizer-v1",
            schema_fingerprint="a" * 64,
            metrics={"products_parsed": 1},
            created_at=now - timedelta(minutes=10),
            parsed_at=now - timedelta(minutes=8),
            validated_at=now - timedelta(minutes=7),
            health_checked_at=now - timedelta(minutes=6),
            promoted_at=now,
        )
        rejected_snapshot = CatalogSnapshotModel(
            id="snapshot-rejected",
            chain="willys",
            scope_key="Lund",
            coverage="full_catalog",
            state="rejected",
            is_active=False,
            connector_version="willys-v2",
            parser_version="broken-parser",
            normalizer_version="normalizer-v1",
            metrics={
                "schema_diff": {
                    "added": ["catalog:$.product.salesPrice"],
                    "removed": ["catalog:$.product.price"],
                    "type_changed": [
                        {
                            "path": "catalog:$.product.packageSize",
                            "old_types": ["string"],
                            "new_types": ["object"],
                        }
                    ],
                    # Arbitrary values in stored metrics must never pass the
                    # structural allow-list in the health API.
                    "password": "must-not-leak",
                }
            },
            created_at=now + timedelta(minutes=10),
            rejected_at=now + timedelta(minutes=11),
            rejection_reason="schema changed",
        )
        malmo_snapshot = CatalogSnapshotModel(
            id="snapshot-active-malmo",
            chain="willys",
            scope_key="malmö",
            coverage="full_catalog",
            state="promoted",
            is_active=True,
            collector_run_id=run.id,
            connector_version="willys-v1",
            parser_version="willys-parser-v1",
            normalizer_version="normalizer-v1",
            schema_fingerprint="4" * 64,
            metrics={"products_parsed": 0},
            created_at=now + timedelta(minutes=1),
            parsed_at=now + timedelta(minutes=2),
            validated_at=now + timedelta(minutes=3),
            health_checked_at=now + timedelta(minutes=4),
            promoted_at=now + timedelta(minutes=5),
        )
        session.add_all([store, store_without_snapshot, malmo_store, run])
        session.flush()
        session.add_all([snapshot, rejected_snapshot, malmo_snapshot])
        session.flush()

        raw = RawSnapshotModel(
            id="raw-active",
            catalog_snapshot_id=snapshot.id,
            collector_run_id=run.id,
            chain="willys",
            store_external_id=store.external_id,
            kind="catalog",
            method="GET",
            url="https://public.example/catalog",
            query={},
            fetched_at=now,
            http_status=200,
            content_type="application/json",
            payload_hash="b" * 64,
            payload_size=100,
            payload_location="raw/willys/snapshot/page.json",
            request_fingerprint="c" * 64,
            connector_version="willys-v1",
            page_number=0,
            schema_fingerprint="a" * 64,
        )
        raw_rejected = RawSnapshotModel(
            id="raw-rejected",
            catalog_snapshot_id=rejected_snapshot.id,
            chain="willys",
            store_external_id=store.external_id,
            kind="catalog",
            method="GET",
            url="https://public.example/catalog?page=bad",
            query={},
            fetched_at=now,
            http_status=200,
            content_type="application/json",
            payload_hash="d" * 64,
            payload_size=50,
            payload_location="raw/willys/rejected/page.json",
            request_fingerprint="e" * 64,
            connector_version="willys-v2",
        )
        session.add_all([raw, raw_rejected])
        session.flush()

        source = SourceProductModel(
            id="source-pasta",
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            chain="willys",
            store_external_id=store.external_id,
            external_product_id="pasta-1kg",
            gtin="7310000000001",
            name="Pasta 1 kg",
            brand="Garant",
            category_path=["Skafferi", "Pasta"],
            sale_price=Decimal(20),
            regular_price=Decimal(24),
            member_price=Decimal(18),
            comparison_price=Decimal(20),
            comparison_unit="kg",
            package_text="1 kg",
            package_quantity=Decimal(1000),
            package_unit="g",
            sale_unit="st",
            availability="in_stock",
            raw_reference="raw://pasta",
            fetched_at=now,
            parser_version="willys-parser-v1",
            source_fields={"authorization": "must-not-leak"},
            source_record_hash="f" * 64,
        )
        rejected_source = SourceProductModel(
            id="source-secret-cheap",
            catalog_snapshot_id=rejected_snapshot.id,
            raw_snapshot_id=raw_rejected.id,
            store_id=store.id,
            chain="willys",
            store_external_id=store.external_id,
            external_product_id="hidden-cheap",
            name="Rejected cheap product",
            category_path=[],
            sale_price=Decimal(1),
            raw_reference="raw://rejected",
            fetched_at=now,
            parser_version="broken-parser",
            source_fields={},
            source_record_hash="1" * 64,
        )
        session.add_all([source, rejected_source])
        session.flush()

        product = ProductModel(
            id="product-pasta",
            source_product_id=source.id,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=store.id,
            source_product_key="willys:pasta-1kg",
            chain="willys",
            store_external_id=store.external_id,
            external_product_id=source.external_product_id,
            gtin=source.gtin,
            name=source.name,
            brand=source.brand,
            category_path=source.category_path,
            canonical_food="pasta",
            product_role="staple",
            product_form="dry",
            semantic_confidence="high",
            sale_model="fixed_package",
            quantity_confidence="exact",
            package_quantity=Decimal(1000),
            package_unit="g",
            usable_quantity=Decimal(1000),
            usable_unit="g",
            sale_price=Decimal(20),
            sale_unit="st",
            unit_price=Decimal(20),
            comparison_price=Decimal(20),
            comparison_unit="kg",
            availability="in_stock",
            raw_reference="raw://pasta",
            parser_version="willys-parser-v1",
            normalizer_version="normalizer-v1",
            observed_at=now,
        )
        rejected_product = ProductModel(
            id="product-rejected",
            source_product_id=rejected_source.id,
            catalog_snapshot_id=rejected_snapshot.id,
            raw_snapshot_id=raw_rejected.id,
            store_id=store.id,
            source_product_key="willys:hidden-cheap",
            chain="willys",
            store_external_id=store.external_id,
            external_product_id=rejected_source.external_product_id,
            name=rejected_source.name,
            category_path=[],
            canonical_food="pasta",
            semantic_confidence="high",
            sale_model="fixed_package",
            quantity_confidence="unknown",
            sale_price=Decimal(1),
            raw_reference="raw://rejected",
            parser_version="broken-parser",
            normalizer_version="normalizer-v1",
            observed_at=now,
        )
        session.add_all([product, rejected_product])
        session.flush()

        price = PriceObservationModel(
            id="price-pasta",
            catalog_snapshot_id=snapshot.id,
            product_id=product.id,
            source_product_id=source.id,
            store_id=store.id,
            raw_snapshot_id=raw.id,
            observed_at=now,
            currency="SEK",
            sale_price=Decimal(20),
            regular_price=Decimal(24),
            member_price=Decimal(18),
            comparison_price=Decimal(20),
            comparison_unit="kg",
            sale_unit="st",
        )
        promotion = PromotionModel(
            id="promotion-pasta",
            catalog_snapshot_id=snapshot.id,
            source_product_id=source.id,
            product_id=product.id,
            store_id=store.id,
            raw_snapshot_id=raw.id,
            price_observation_id=price.id,
            offer_fingerprint="2" * 64,
            external_id="offer-1",
            type="multibuy",
            valid_from=today - timedelta(days=1),
            valid_to=today + timedelta(days=1),
            price=Decimal(50),
            quantity=3,
            max_quantity=2,
            member_only=False,
            description="3 för 50 kr",
            source_payload={"cookie": "must-not-leak"},
            parser_version="willys-parser-v1",
        )
        health = ConnectorHealthModel(
            chain="willys",
            coverage="full_catalog",
            status="healthy",
            last_success_at=now,
            checked_at=now,
            active_snapshot_id=snapshot.id,
            metrics={
                "products_fetched": 1,
                "products_parsed": 1,
                "products_with_price": 1,
                "products_with_gtin": 1,
                "products_with_package_quantity": 1,
                "authorization": "must-not-leak",
            },
            warnings=["api_key=warning-secret was present"],
            schema_fingerprint="a" * 64,
        )
        failure = ParserFailureModel(
            id="failure-1",
            catalog_snapshot_id=snapshot.id,
            collector_run_id=run.id,
            raw_snapshot_id=raw.id,
            chain="willys",
            store_external_id=store.external_id,
            raw_record_reference="raw://secret-record",
            error_code="unknown_package_format",
            error_message="token=failure-secret in raw row",
            parser_version="willys-parser-v1",
            failure_fingerprint="3" * 64,
            sample={
                "code": "101240187_ST",
                "name": "Pasta token=sample-secret",
                "productLine2": "1 kg",
                "priceUnit": "kr/st",
                "password": "must-not-leak",
            },
        )
        session.add_all([price, promotion, health, failure])
        session.commit()

    with TestClient(create_app(factory)) as client:
        yield client
    engine.dispose()


def test_health_endpoints_are_complete_and_secret_safe(api_client: TestClient) -> None:
    summary = api_client.get("/health")
    connectors = api_client.get("/health/connectors")
    detail = api_client.get("/health/connectors/willys")

    assert summary.status_code == 200
    assert summary.json()["status"] == "healthy"
    assert connectors.status_code == 200
    assert connectors.json()["count"] == 6
    lidl = next(item for item in connectors.json()["items"] if item["chain"] == "lidl")
    assert lidl["status"] == "unknown"
    assert lidl["coverage"] == "offers_only"
    assert lidl["implemented"] is True
    assert lidl["acceptance_contract_passed"] is True
    assert lidl["limitation"]
    assert detail.status_code == 200
    body = detail.json()
    assert body["implemented"] is True
    assert body["acceptance_contract_passed"] is True
    assert body["missing_acceptance_checks"] == []
    assert body["limitation"] is None
    assert body["snapshot_id"] == "snapshot-active"
    assert body["metrics"]["price_coverage"] == 1
    assert body["recent_errors"] == [
        {
            "error_code": "unknown_package_format",
            "count": 1,
            "latest_at": body["recent_errors"][0]["latest_at"],
            "examples": [
                {
                    "external_product_id": "101240187_ST",
                    "name": "Pasta token=[REDACTED]",
                    "package_text": "1 kg",
                    "price_unit": "kr/st",
                }
            ],
        }
    ]
    assert body["schema_diff"] == {
        "snapshot_id": "snapshot-rejected",
        "scope_key": "Lund",
        "state": "rejected",
        "added": ["catalog:$.product.salesPrice"],
        "removed": ["catalog:$.product.price"],
        "type_changed": [
            {
                "path": "catalog:$.product.packageSize",
                "old_types": ["string"],
                "new_types": ["object"],
            }
        ],
        "total_added": 1,
        "total_removed": 1,
        "total_type_changed": 1,
        "truncated": False,
    }
    serialized = detail.text
    assert "must-not-leak" not in serialized
    assert "warning-secret" not in serialized
    assert "run-secret" not in serialized
    assert "failure-secret" not in serialized
    assert "sample-secret" not in serialized


def test_source_status_exposes_strategy_without_claiming_external_health(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OWN_SOURCES_ONLY", "false")
    monkeypatch.setenv("ALLOW_PROVIDER_FALLBACK", "false")
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "48")
    now = datetime.now(tz=UTC)
    with api_client.app.state.session_factory() as session:
        session.add(
            CatalogSnapshotModel(
                id="snapshot-coop-offers",
                chain="coop",
                scope_key="Lund",
                coverage="offers_only",
                state="promoted",
                is_active=True,
                connector_version="coop-v1",
                parser_version="coop-parser-v1",
                normalizer_version="normalizer-v1",
                created_at=now,
                promoted_at=now,
            )
        )
        session.commit()

    response = api_client.get("/sources/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["chains"] == 6
    assert payload["allow_provider_fallback"] is False
    willys = next(item for item in payload["items"] if item["chain"] == "willys")
    assert willys["basket_primary"] == {"provider": "own", "channel": "catalog"}
    assert willys["selected_provider"] == "own"
    assert willys["basket_eligible"] is True
    assert willys["fallback_used"] is False
    assert willys["own_snapshots"][0]["source"]["snapshot_id"]

    coop = next(item for item in payload["items"] if item["chain"] == "coop")
    assert coop["basket_primary"] == {"provider": "own", "channel": "catalog"}
    assert coop["basket_fallbacks"] == [
        {"provider": "primat", "channel": "catalog"}
    ]
    assert coop["offers_primary"] == {"provider": "own", "channel": "offers"}
    assert coop["basket_eligible"] is False
    assert "OWN primary" in coop["eligibility_reason"]
    assert coop["fallback_available"] == "primat"
    assert coop["own_snapshots"][0]["source"]["channel"] == "offers"


def test_own_sources_only_disables_external_primary_without_mutating_strategy(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OWN_SOURCES_ONLY", "true")
    monkeypatch.setenv("ALLOW_PROVIDER_FALLBACK", "true")

    payload = api_client.get("/sources/status").json()
    ica = next(item for item in payload["items"] if item["chain"] == "ica")

    assert payload["own_sources_only"] is True
    assert ica["basket_primary"] == {"provider": "primat", "channel": "catalog"}
    assert ica["selected_provider"] is None
    assert ica["basket_eligible"] is False
    assert ica["fallback_used"] is False


def test_catalog_api_adds_nested_source_provenance_without_removing_flat_fields(
    api_client: TestClient,
) -> None:
    product = api_client.get("/products/search", params={"q": "pasta"}).json()["items"][0]
    price = api_client.get("/prices", params={"product_id": product["id"]}).json()["items"][0]
    offer = api_client.get("/offers", params={"store_id": product["store_id"]}).json()["items"][0]

    for item in (product, price, offer):
        assert item["source_provider"] == "own"
        assert item["source_snapshot_id"] == "snapshot-active"
        assert item["fallback_used"] is False
        assert item["source"]["provider"] == "own"
        assert item["source"]["snapshot_id"] == "snapshot-active"
        assert item["source"]["coverage"] == "full_catalog"
        assert item["source"]["price_context"] == "physical_store"
        assert item["source"]["fallback_used"] is False
        assert item["source"]["chain"] == "willys"
        assert item["source"]["store_id"] == "store-willys-lund"

    assert product["semantic_confidence"] == "high"
    assert price["quantity_confidence"] == "exact"
    assert offer["source"]["channel"] == "offers"


def test_store_endpoints_support_city_and_normalized_postal_code(api_client: TestClient) -> None:
    response = api_client.get("/stores", params={"city": "lund", "postal_code": "22761"})

    assert response.status_code == 200
    body = response.json()
    assert body["stores"] == body["items"]
    assert [item["external_id"] for item in body["stores"]] == ["2354"]
    assert body["snapshot_id"] == "snapshot-active"
    assert body["connector_status"] == "healthy"
    assert body["observed_at"] is not None
    assert body["data_age_hours"] >= 0
    detail = api_client.get("/stores/store-willys-lund")
    assert detail.status_code == 200
    assert detail.json()["price_context_type"] == "physical_store"
    assert detail.json()["physical_store_external_id"] == "2354"
    assert api_client.get("/stores/missing").status_code == 404


def test_legacy_willys_online_snapshot_is_never_presented_as_shelf_price() -> None:
    legacy = StoreModel(
        id="legacy-willys",
        chain="willys",
        external_id="2176",
        name="Willys Lund",
        city="Lund",
        online_shopping=True,
        coverage="full_catalog",
        price_context_type=None,
        physical_store_external_id=None,
        raw_reference="raw://legacy-willys",
        is_active=True,
    )

    assert _effective_store_context(legacy) == ("online_store", "2176")

    legacy.online_shopping = False
    assert _effective_store_context(legacy) == (None, None)


def test_postal_code_resolves_to_supported_city_scope(api_client: TestClient) -> None:
    response = api_client.get("/stores", params={"postal_code": "22350"})

    assert response.status_code == 200
    body = response.json()
    assert {item["external_id"] for item in body["stores"]} == {"2354", "coop-1"}
    assert body["geography"]["resolved_city"] == "Lund"
    assert body["geography"]["resolution"] == "postal_prefix"
    assert "PoC" in body["geography"]["coverage_limitation"]
    coop = next(item for item in body["stores"] if item["chain"] == "coop")
    assert coop["source_channel"] == "offers"


def test_catalog_and_product_search_use_only_active_snapshot(api_client: TestClient) -> None:
    catalog = api_client.get("/catalog/store-willys-lund")
    search = api_client.get(
        "/products/search",
        params={"q": "pasta", "store_id": "store-willys-lund"},
    )
    product = api_client.get("/products/product-pasta")

    assert catalog.status_code == 200
    assert catalog.json()["products"][0]["name"] == "Pasta 1 kg"
    assert catalog.json()["snapshot_id"] == "snapshot-active"
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["products"]] == ["product-pasta"]
    assert search.json()["products"][0]["promotions"][0]["type"] == "multibuy"
    expected_lineage = {
        "source_snapshot_id": "snapshot-active",
        "raw_snapshot_id": "raw-active",
        "parser_version": "willys-parser-v1",
        "normalizer_version": "normalizer-v1",
        "observed_at": search.json()["products"][0]["observed_at"],
    }
    assert search.json()["products"][0]["lineage"] == expected_lineage
    assert catalog.json()["products"][0]["lineage"] == expected_lineage
    assert product.json()["lineage"] == expected_lineage
    assert product.json()["observed_at"] == search.json()["products"][0]["observed_at"]
    assert (
        product.json()["source_observed_at"] == search.json()["products"][0]["source_observed_at"]
    )
    assert product.json()["source"] == {
        "provider": "own",
        "channel": "catalog",
        "snapshot_id": "snapshot-active",
        "observed_at": search.json()["products"][0]["source_observed_at"],
        "coverage": "full_catalog",
        "price_context": "physical_store",
        "fallback_used": False,
        "chain": "willys",
        "store_id": "store-willys-lund",
        "store_name": "Willys Lund Nova",
    }
    assert product.json()["snapshot_freshness"]["snapshot_id"] == "snapshot-active"
    assert product.json()["snapshot_freshness"]["is_stale"] is False
    assert "Rejected cheap product" not in search.text
    assert "must-not-leak" not in search.text
    assert "payload_location" not in search.text
    assert "source_fields" not in search.text
    assert product.status_code == 200
    assert product.json()["gtin"] == "7310000000001"
    for item in (
        search.json()["products"][0],
        catalog.json()["products"][0],
        product.json(),
    ):
        assert item["source_provider"] == "own"
        assert item["source_channel"] == "catalog"
        assert item["source_snapshot_id"] == "snapshot-active"
        assert item["source_observed_at"] is not None


def test_product_search_uses_one_authoritative_snapshot_per_store_context(
    api_client: TestClient,
) -> None:
    """A legacy scope alias must not merge two active versions of one context."""

    with api_client.app.state.session_factory() as session:
        legacy = session.get(CatalogSnapshotModel, "snapshot-rejected")
        assert legacy is not None
        legacy.scope_key = "city:lund"
        legacy.state = "promoted"
        legacy.is_active = True
        legacy.promoted_at = legacy.created_at
        session.commit()

    catalog = api_client.get("/catalog/store-willys-lund")
    search = api_client.get(
        "/products/search",
        params={"q": "pasta", "store_id": "store-willys-lund"},
    )

    assert catalog.status_code == 200
    assert catalog.json()["snapshot_id"] == "snapshot-active"
    assert search.status_code == 200
    assert [item["id"] for item in search.json()["products"]] == ["product-pasta"]
    assert {item["source_snapshot_id"] for item in search.json()["products"]} == {
        "snapshot-active"
    }


def test_prices_offers_and_stores_expose_explicit_source_provenance(
    api_client: TestClient,
) -> None:
    store = api_client.get("/stores/store-willys-lund").json()
    price = api_client.get("/prices", params={"store_id": "store-willys-lund"}).json()["prices"][0]
    offer = api_client.get("/offers", params={"store_id": "store-willys-lund"}).json()["offers"][0]

    assert store["source_provider"] == "own"
    assert store["source_snapshot_id"] == "snapshot-active"
    assert price["source_provider"] == "own"
    assert price["source_channel"] == "catalog"
    assert price["source_snapshot_id"] == "snapshot-active"
    assert offer["source_provider"] == "own"
    assert offer["source_channel"] == "offers"
    assert offer["source_snapshot_id"] == "snapshot-active"


def test_catalog_price_join_uses_indexable_product_identity() -> None:
    sql = str(_product_rows_statement())

    assert "price_observations.product_id = products.id" in sql
    assert "price_observations.source_product_id = source_products.id" not in sql


def test_snapshot_diff_reads_persisted_parser_failure_counts(api_client: TestClient) -> None:
    manager = SnapshotManager(api_client.app.state.session_factory)

    result = manager.diff("snapshot-rejected", "snapshot-active")

    assert result.old_parser_failures == 0
    assert result.new_parser_failures == 1
    assert "parser failures increased from 0 to 1" in result.warnings


def test_catalog_resolves_parallel_active_city_snapshots_without_cross_mixing(
    api_client: TestClient,
) -> None:
    lund = api_client.get("/catalog/store-willys-lund")
    malmo = api_client.get("/catalog/store-willys-malmo")

    assert lund.status_code == 200
    assert lund.json()["snapshot_id"] == "snapshot-active"
    assert lund.json()["scope_key"] == "Lund"
    assert [item["id"] for item in lund.json()["products"]] == ["product-pasta"]

    # The synthetic Malmö snapshot deliberately has no product lineage. It must
    # not borrow Lund's catalog merely because both snapshots share a chain.
    assert malmo.status_code == 503


def test_offers_only_store_is_never_exposed_as_catalog(
    api_client: TestClient,
) -> None:
    response = api_client.get("/catalog/store-coop-lund")

    assert response.status_code == 409
    assert "offers-only store has no verified catalog" in response.json()["detail"]


def test_price_endpoints_support_single_and_bulk_queries(api_client: TestClient) -> None:
    current = api_client.get("/prices", params={"store_id": "store-willys-lund"})
    bulk = api_client.post(
        "/prices/query",
        json={"store_ids": ["store-willys-lund"], "canonical_foods": ["pasta"]},
    )

    assert current.status_code == 200
    assert current.json()["prices"][0]["sale_price"] == 20
    assert current.json()["snapshot_id"] == "snapshot-active"
    assert bulk.status_code == 200
    assert bulk.json()["prices"] == current.json()["prices"]
    assert api_client.post("/prices/query", json={}).status_code == 422


def test_offers_are_active_snapshot_only_and_hide_source_payload(api_client: TestClient) -> None:
    response = api_client.get("/offers", params={"store_id": "store-willys-lund"})

    assert response.status_code == 200
    body = response.json()
    assert body["offers"][0]["quantity"] == 3
    assert body["offers"][0]["max_quantity"] == 2
    assert body["offers"][0]["price"] == 50
    assert body["offers"][0]["product"]["id"] == "product-pasta"
    assert body["offers"][0]["product"]["source_channel"] == "catalog"
    assert body["snapshot_id"] == "snapshot-active"
    assert "source_payload" not in response.text
    assert "must-not-leak" not in response.text


def test_admin_pages_and_static_assets_are_delivered(api_client: TestClient) -> None:
    assert api_client.get("/").status_code == 200
    status_page = api_client.get("/").text
    assert "Connectorstatus" in status_page
    assert "STORE COVERAGE" in status_page
    assert "PRICE CONTEXTS" in status_page
    assert "PHYSICAL VALIDATION" in status_page
    assert "/physical-check" in status_page
    assert api_client.get("/admin/connectors/willys").status_code == 200
    status_script = api_client.get("/static/status.js")
    connector_script = api_client.get("/static/connector.js")
    assert status_script.status_code == 200
    assert connector_script.status_code == 200
    assert "basket_primary" in status_script.text
    assert "Basket source:" in status_script.text
    assert "OWN connector:" in status_script.text
    assert "OWN roller:" in status_script.text
    assert "/stores/coverage?city=Lund" in status_script.text
    assert "/stores/price-contexts?city=Lund" in status_script.text
    assert "store.reason" in status_script.text
    assert "official_evidence" in status_script.text
    assert "Locator health:" in status_script.text
    assert "physical_observations" in status_script.text
    assert "blockerar aldrig" in status_page
    assert (
        "Basket: ${basket.provider.toUpperCase()} · ${connector.coverage" not in status_script.text
    )
    assert "fallback_enabled" in connector_script.text


def test_default_app_uses_documented_database_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GROCERY_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("GROCERY_DATA_DATABASE_URL", "invalid-driver://must-not-be-used")

    _factory, engine = _default_session_factory()
    try:
        assert str(engine.url) == "sqlite+pysqlite:///:memory:"
    finally:
        engine.dispose()


def test_dependency_injected_app_is_isolated_from_repository_dotenv() -> None:
    """A developer's field-server dotenv must not restrict ordinary API tests."""

    assert os.environ["PYTHON_DOTENV_DISABLED"] == "1"
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    try:
        application = create_app(create_session_factory(engine))
        assert application.state.settings.field_mode_enabled is False
        with TestClient(application) as client:
            assert client.get("/health").status_code == 200
            assert client.get("/openapi.json").status_code == 200
    finally:
        engine.dispose()


def test_repository_dotenv_loader_is_explicit_and_disableable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(
        "GROCERY_DATABASE_URL=sqlite+pysqlite:///from-dotenv.sqlite\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GROCERY_DATABASE_URL", raising=False)
    monkeypatch.delenv("PYTHON_DOTENV_DISABLED", raising=False)

    assert load_repository_dotenv(dotenv_path) is True
    assert GroceryDataSettings.from_env().database_url.endswith("from-dotenv.sqlite")

    monkeypatch.delenv("GROCERY_DATABASE_URL", raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "true")
    assert load_repository_dotenv(dotenv_path) is False
    assert GroceryDataSettings.from_env().database_url.endswith("grocery_data.sqlite")


def test_freshness_marks_old_healthy_snapshot_stale(api_client: TestClient) -> None:
    factory = api_client.app.state.session_factory
    with factory() as session:
        snapshot = session.get(CatalogSnapshotModel, "snapshot-active")
        assert snapshot is not None and snapshot.promoted_at is not None
        freshness = freshness_for_snapshot(
            session,
            snapshot,
            now=snapshot.promoted_at + timedelta(hours=49),
        )

    assert freshness["is_stale"] is True
    assert freshness["connector_status"] == "stale"


def test_source_status_uses_configured_72_hour_freshness_threshold(
    api_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "72")
    observed_at = datetime.now(tz=UTC) - timedelta(hours=60)
    factory = api_client.app.state.session_factory
    with factory() as session:
        observation = session.get(PriceObservationModel, "price-pasta")
        assert observation is not None
        observation.observed_at = observed_at
        session.commit()

    payload = api_client.get("/sources/status").json()
    willys = next(item for item in payload["items"] if item["chain"] == "willys")
    snapshot = next(
        item for item in willys["own_snapshots"] if item["snapshot_id"] == "snapshot-active"
    )
    health = api_client.get("/health/connectors/willys").json()
    store = api_client.get("/stores/store-willys-lund").json()
    catalog = api_client.get("/catalog/store-willys-lund").json()
    search = api_client.get(
        "/products/search",
        params={"q": "pasta", "store_id": "store-willys-lund"},
    ).json()
    prices = api_client.get(
        "/prices",
        params={"store_id": "store-willys-lund"},
    ).json()

    assert snapshot["data_age_hours"] == pytest.approx(60, abs=0.05)
    assert snapshot["fresh"] is True
    assert snapshot["health"] == "healthy"
    assert snapshot["basket_eligible"] is True
    assert health["data_age_hours"] == pytest.approx(60, abs=0.05)
    assert health["connector_status"] == "healthy"
    assert health["status"] == "healthy"
    assert health["source_strategy"]["basket_eligible"] is True
    for response in (store, catalog, search, prices):
        assert response["data_age_hours"] == pytest.approx(60, abs=0.05)
        assert response["connector_status"] == "healthy"
    assert catalog["is_stale"] is False
    assert search["freshness"][0]["is_stale"] is False
    assert prices["freshness"][0]["is_stale"] is False


def test_failed_other_scope_does_not_poison_active_lund_snapshot(
    api_client: TestClient,
) -> None:
    factory = api_client.app.state.session_factory
    with factory() as session:
        health = session.get(ConnectorHealthModel, "willys")
        assert health is not None
        # Model the latest chain run failing for Malmö while both previously
        # promoted city snapshots remain active as last-known-good data.
        health.status = "broken"
        health.active_snapshot_id = "snapshot-active-malmo"
        health.warnings = ["Malmö collection failed"]
        session.commit()

    lund_store = api_client.get("/stores/store-willys-lund")
    lund_catalog = api_client.get("/catalog/store-willys-lund")
    global_health = api_client.get("/health/connectors/willys")

    assert lund_store.status_code == 200
    assert lund_store.json()["snapshot_id"] == "snapshot-active"
    assert lund_store.json()["connector_status"] == "healthy"
    assert lund_catalog.status_code == 200
    assert lund_catalog.json()["snapshot_id"] == "snapshot-active"
    assert lund_catalog.json()["connector_status"] == "healthy"

    assert global_health.status_code == 200
    assert global_health.json()["status"] == "broken"
    assert global_health.json()["latest_run_status"] == "broken"
    assert api_client.get("/health").json()["status"] == "broken"


def test_discovered_store_without_catalog_lineage_has_no_active_catalog(
    api_client: TestClient,
) -> None:
    factory = api_client.app.state.session_factory
    now = datetime.now(tz=UTC)
    with factory() as session:
        session.add(
            StoreModel(
                id="store-willys-offline-lund",
                chain="willys",
                external_id="offline-1",
                name="Willys Lund utan onlinekatalog",
                postal_code="223 51",
                city="Lund",
                online_shopping=False,
                coverage="partial_catalog",
                raw_reference="raw://stores/offline-1",
                is_active=True,
                first_seen_at=now,
                last_seen_at=now,
            )
        )
        session.commit()

    detail = api_client.get("/stores/store-willys-offline-lund")
    catalog = api_client.get("/catalog/store-willys-offline-lund")

    assert detail.status_code == 200
    assert detail.json()["snapshot_id"] is None
    assert detail.json()["connector_status"] == "unknown"
    assert catalog.status_code == 503

    online = api_client.get("/catalog/store-willys-lund")
    assert online.status_code == 200
    assert online.json()["snapshot_id"] == "snapshot-active"


def test_repromoting_old_observations_does_not_reset_data_age(
    api_client: TestClient,
) -> None:
    factory = api_client.app.state.session_factory
    now = datetime.now(tz=UTC)
    old_observation = now - timedelta(days=7)
    with factory() as session:
        snapshot = session.get(CatalogSnapshotModel, "snapshot-active")
        observation = session.get(PriceObservationModel, "price-pasta")
        assert snapshot is not None and observation is not None
        snapshot.promoted_at = now
        observation.observed_at = old_observation
        session.commit()

        freshness = freshness_for_snapshot(session, snapshot, now=now)

    assert freshness["observed_at"] == old_observation
    assert freshness["last_success_at"] == now
    assert freshness["data_age_hours"] == pytest.approx(168)
    assert freshness["is_stale"] is True
    assert freshness["connector_status"] == "stale"


def test_health_status_exposes_stale_active_snapshot_separately_from_latest_run(
    api_client: TestClient,
) -> None:
    factory = api_client.app.state.session_factory
    with factory() as session:
        observation = session.get(PriceObservationModel, "price-pasta")
        health = session.get(ConnectorHealthModel, "willys")
        assert observation is not None and health is not None
        observation.observed_at = datetime.now(tz=UTC) - timedelta(days=7)
        health.status = "healthy"
        session.commit()

    detail = api_client.get("/health/connectors/willys")
    summary = api_client.get("/health")
    connector_summary = api_client.get("/health/connectors")

    assert detail.status_code == 200
    assert detail.json()["latest_run_status"] == "healthy"
    assert detail.json()["connector_status"] == "stale"
    assert detail.json()["status"] == "stale"
    assert summary.json()["status"] == "degraded"
    assert connector_summary.json()["connector_status"] == "degraded"
