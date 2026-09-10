from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from grocery_data.app.main import create_app
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    RawSnapshotModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
    create_database_engine,
    create_schema,
    create_session_factory,
)


def _client() -> tuple[TestClient, object]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    observed_at = datetime.now(tz=UTC) - timedelta(hours=1)
    with factory() as session:
        context = StoreModel(
            id="store-coop-730400",
            chain="coop",
            external_id="730400",
            name="Coop Online Syd",
            address=None,
            postal_code=None,
            city=None,
            online_shopping=True,
            coverage="full_online_catalog",
            price_context_type="online_fulfillment",
            physical_store_external_id=None,
            raw_reference="raw://coop/context/730400",
            is_active=True,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )
        physicals = (
            PhysicalStoreModel(
                id="physical:coop:2696",
                chain="coop",
                external_store_id="2696",
                external_store_aliases=[],
                name="Stora Coop Lund",
                address="Traktorvägen 2",
                postal_code="226 60",
                city="Lund",
                official_source="https://www.coop.se/butiker-erbjudanden/",
                discovered_at=observed_at,
                last_seen_at=observed_at,
                is_active=True,
                lifecycle_state="active",
            ),
            PhysicalStoreModel(
                id="physical:coop:test-pickup",
                chain="coop",
                external_store_id="test-pickup",
                external_store_aliases=[],
                name="Coop Lund Testpickup",
                address="Testvägen 1",
                postal_code="223 50",
                city="Lund",
                official_source="unit fixture",
                discovered_at=observed_at,
                last_seen_at=observed_at,
                is_active=True,
                lifecycle_state="active",
            ),
            PhysicalStoreModel(
                id="physical:coop:3813",
                chain="coop",
                external_store_id="3813",
                external_store_aliases=[],
                name="Coop Mårtenstorget",
                address="Mårtenstorget 11",
                postal_code="223 51",
                city="Lund",
                official_source="https://www.coop.se/butiker-erbjudanden/",
                discovered_at=observed_at,
                last_seen_at=observed_at,
                is_active=True,
                lifecycle_state="active",
            ),
        )
        snapshot = CatalogSnapshotModel(
            id="snapshot-coop-730400",
            chain="coop",
            scope_key="coop:online:730400",
            coverage="full_online_catalog",
            state="promoted",
            is_active=True,
            connector_version="coop-online-v1",
            parser_version="coop-online-parser-v1",
            normalizer_version="normalizer-v1",
            schema_fingerprint="a" * 64,
            metrics={"products_parsed": 1, "products_with_price": 1},
            created_at=observed_at,
            parsed_at=observed_at,
            validated_at=observed_at,
            health_checked_at=observed_at,
            promoted_at=observed_at,
        )
        session.add_all([context, *physicals, snapshot])
        session.flush()
        raw = RawSnapshotModel(
            id="raw-coop-730400",
            catalog_snapshot_id=snapshot.id,
            chain="coop",
            store_external_id="730400",
            kind="coop_product_category_page",
            method="POST",
            url="https://external.api.coop.se/personalization/search/entities/by-attribute",
            query={},
            fetched_at=observed_at,
            http_status=200,
            content_type="application/json",
            payload_hash="b" * 64,
            payload_size=1,
            payload_location="raw/coop/730400/page.json",
            request_fingerprint="c" * 64,
            connector_version="coop-online-v1",
            page_number=0,
            schema_fingerprint="a" * 64,
        )
        session.add(raw)
        session.flush()
        session.add(
            SourceProductModel(
                id="source-coop-milk",
                catalog_snapshot_id=snapshot.id,
                raw_snapshot_id=raw.id,
                store_id=context.id,
                chain="coop",
                store_external_id="730400",
                external_product_id="7300156573186",
                gtin="7300156573186",
                name="Mellanmjölk 1.5 l",
                category_path=["Mejeri & ägg", "Mjölk"],
                sale_price=16.27,
                package_text="1.5 l",
                package_quantity=1500,
                package_unit="ml",
                sale_unit="st",
                availability="available",
                raw_reference="raw://coop/730400/7300156573186",
                fetched_at=observed_at,
                parser_version="coop-online-parser-v1",
                source_fields={},
                source_record_hash="d" * 64,
            )
        )
        for physical_id, pickup_id in (
            ("physical:coop:2696", "257611"),
            ("physical:coop:test-pickup", "test-pickup-point"),
        ):
            session.add(
                StoreContextLinkModel(
                    physical_store_id=physical_id,
                    grocery_context_id="own:coop:730400",
                    source_provider="own",
                    source_channel="catalog",
                    local_store_id=context.id,
                    pickup_point_external_id=pickup_id,
                    grocery_context_name="Coop Online Syd",
                    price_context_type="online_fulfillment",
                    coverage="full_online_catalog",
                    relation_type="pickup_context",
                    confidence="exact",
                    evidence="sanitized public fulfillment fixture",
                    basket_eligible=True,
                    offers_only=False,
                    snapshot_id=snapshot.id,
                    observed_at=observed_at,
                    linked_at=observed_at,
                    last_verified_at=observed_at,
                    is_active=True,
                )
            )
        session.commit()
    return TestClient(create_app(factory)), engine


def test_lund_postal_returns_shared_coop_context_once_with_pickup_options() -> None:
    client, engine = _client()
    try:
        response = client.get("/stores", params={"postal_code": "22350"})
    finally:
        engine.dispose()

    assert response.status_code == 200
    rows = response.json()["stores"]
    assert [row["external_id"] for row in rows] == ["730400"]
    context = rows[0]
    assert context["name"] == "Coop Online Syd"
    assert context["address"] is None
    assert context["postal_code"] is None
    assert context["city"] == "Lund"
    assert context["price_context_type"] == "online_fulfillment"
    assert context["physical_store_external_id"] is None
    assert context["price_semantics"] == "online_price"
    assert context["price_label"] == "Coop onlinepris"
    assert context["service_area"]["availability_basis"] == "verified_pickup_context"
    assert context["service_area"]["requested_postal_code"] == "22350"
    assert {row["pickup_point_external_id"] for row in context["pickup_options"]} == {
        "257611",
        "test-pickup-point",
    }
    assert all(row["name"] != "Coop Mårtenstorget" for row in context["pickup_options"])


def test_city_query_deduplicates_many_pickups_and_unlinked_store_adds_no_context() -> None:
    client, engine = _client()
    try:
        rows = client.get("/stores", params={"city": "Lund"}).json()["stores"]
    finally:
        engine.dispose()

    assert len(rows) == 1
    assert rows[0]["id"] == "store-coop-730400"
    assert len(rows[0]["pickup_options"]) == 2

