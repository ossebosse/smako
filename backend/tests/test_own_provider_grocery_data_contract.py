from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest
from app.models import OfferKind, QuantityConfidence, SaleModel, SemanticConfidence
from app.providers.own import OwnGroceryPriceProvider

from grocery_data.app.main import create_app
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    ConnectorHealthModel,
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


def _contract_database(
    *,
    observed_at: datetime | None = None,
):  # type: ignore[no-untyped-def]
    """Build the smallest real grocery-data lineage used by the provider contract."""

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    observed_at = observed_at or datetime.now(tz=UTC) - timedelta(minutes=10)

    with factory() as session:
        willys = StoreModel(
            id="store-willys-lund",
            chain="willys",
            external_id="2354",
            name="Willys Lund Nova",
            address="Företagsvägen 10",
            postal_code="227 61",
            city="Lund",
            online_shopping=True,
            coverage="full_catalog",
            raw_reference="raw://stores/willys/2354",
            is_active=True,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )
        broken_coop = StoreModel(
            id="store-coop-lund",
            chain="coop",
            external_id="coop-lund-1",
            name="Coop Lund",
            postal_code="223 50",
            city="Lund",
            online_shopping=True,
            coverage="partial_catalog",
            raw_reference="raw://stores/coop/coop-lund-1",
            is_active=True,
            first_seen_at=observed_at,
            last_seen_at=observed_at,
        )
        session.add_all([willys, broken_coop])

        snapshot = CatalogSnapshotModel(
            id="snapshot-willys-lund",
            chain="willys",
            scope_key="lund",
            coverage="full_catalog",
            state="promoted",
            is_active=True,
            connector_version="willys-v1",
            parser_version="willys-parser-v1",
            normalizer_version="product-normalizer-v1",
            schema_fingerprint="a" * 64,
            metrics={"products_parsed": 1, "products_with_price": 1},
            created_at=observed_at,
            parsed_at=observed_at,
            validated_at=observed_at,
            health_checked_at=observed_at,
            promoted_at=observed_at,
        )
        session.add(snapshot)
        session.flush()

        raw = RawSnapshotModel(
            id="raw-willys-catalog",
            catalog_snapshot_id=snapshot.id,
            chain="willys",
            store_external_id=willys.external_id,
            kind="catalog_page",
            method="GET",
            url="https://public.example/catalog",
            query={"page": "0"},
            fetched_at=observed_at,
            http_status=200,
            content_type="application/json",
            payload_hash="b" * 64,
            payload_size=100,
            payload_location="raw/willys/catalog-page.json",
            request_fingerprint="c" * 64,
            connector_version="willys-v1",
            page_number=0,
            schema_fingerprint="a" * 64,
        )
        session.add(raw)
        session.flush()

        source = SourceProductModel(
            id="source-pasta",
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=willys.id,
            chain="willys",
            store_external_id=willys.external_id,
            external_product_id="pasta-1kg",
            gtin="7310000000001",
            name="Spaghetti 1 kg",
            brand="Garant",
            category_path=["Skafferi", "Pasta"],
            sale_price=Decimal("20.00"),
            regular_price=Decimal("24.00"),
            member_price=Decimal("18.00"),
            comparison_price=Decimal("20.00"),
            comparison_unit="kg",
            package_text="1 kg",
            package_quantity=Decimal(1000),
            package_unit="g",
            sale_unit="st",
            availability="available",
            raw_reference="raw://willys/pasta-1kg",
            fetched_at=observed_at,
            parser_version="willys-parser-v1",
            source_fields={},
            source_record_hash="d" * 64,
        )
        session.add(source)
        session.flush()

        product = ProductModel(
            id="product-pasta",
            source_product_id=source.id,
            catalog_snapshot_id=snapshot.id,
            raw_snapshot_id=raw.id,
            store_id=willys.id,
            source_product_key="willys:pasta-1kg",
            chain="willys",
            store_external_id=willys.external_id,
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
            sale_price=Decimal("20.00"),
            sale_unit="st",
            unit_price=Decimal("20.00"),
            comparison_price=Decimal("20.00"),
            comparison_unit="kg",
            availability="available",
            raw_reference="raw://willys/pasta-1kg",
            parser_version="willys-parser-v1",
            normalizer_version="product-normalizer-v1",
            observed_at=observed_at,
        )
        session.add(product)
        session.flush()

        price = PriceObservationModel(
            id="price-pasta",
            catalog_snapshot_id=snapshot.id,
            product_id=product.id,
            source_product_id=source.id,
            store_id=willys.id,
            raw_snapshot_id=raw.id,
            observed_at=observed_at,
            currency="SEK",
            sale_price=Decimal("20.00"),
            regular_price=Decimal("24.00"),
            member_price=Decimal("18.00"),
            comparison_price=Decimal("20.00"),
            comparison_unit="kg",
            sale_unit="st",
        )
        session.add(price)
        session.flush()

        promotion = PromotionModel(
            id="promotion-pasta",
            catalog_snapshot_id=snapshot.id,
            source_product_id=source.id,
            product_id=product.id,
            store_id=willys.id,
            raw_snapshot_id=raw.id,
            price_observation_id=price.id,
            offer_fingerprint="e" * 64,
            external_id="offer-3-for-50",
            type="multibuy",
            valid_from=observed_at.date() - timedelta(days=1),
            valid_to=observed_at.date() + timedelta(days=2),
            price=Decimal("50.00"),
            quantity=3,
            member_only=False,
            description="3 för 50 kr",
            source_payload={},
            parser_version="willys-parser-v1",
        )
        healthy = ConnectorHealthModel(
            chain="willys",
            coverage="full_catalog",
            status="healthy",
            last_success_at=observed_at,
            checked_at=observed_at,
            active_snapshot_id=snapshot.id,
            metrics={"products_parsed": 1, "products_with_price": 1},
            warnings=[],
            schema_fingerprint="a" * 64,
        )
        broken = ConnectorHealthModel(
            chain="coop",
            coverage="partial_catalog",
            status="broken",
            last_success_at=None,
            checked_at=observed_at,
            active_snapshot_id=None,
            metrics={},
            warnings=["schema change"],
        )
        session.add_all([promotion, healthy, broken])
        session.commit()

    return engine, factory


@pytest.mark.asyncio
@pytest.mark.parametrize("relay", [False, True])
async def test_own_provider_consumes_real_grocery_data_api_contract_offline(
    monkeypatch: pytest.MonkeyPatch,
    relay: bool,
) -> None:
    """Exercise stores/search/catalog/offers through the actual ASGI serializers."""

    # A developer may be running the phone-only field UI through the repository
    # dotenv.  This contract test needs the ordinary catalog API explicitly and
    # must not depend on that unrelated local process mode.
    monkeypatch.setenv("FIELD_MODE_ENABLED", "false")
    engine, factory = _contract_database()
    if relay:
        with factory() as session:
            snapshot = session.get(CatalogSnapshotModel, "snapshot-willys-lund")
            snapshot.metrics = {
                **(snapshot.metrics or {}),
                "source_artifact": {"collection_location": "LOCAL_RELAY"},
            }
            session.commit()
    app = create_app(factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        base_url="http://grocery-data.test/",
        transport=transport,
    ) as api_client:
        provider = OwnGroceryPriceProvider(
            "http://grocery-data.test/",
            use_member_prices=False,
            client=api_client,
        )

        # The API collection response is globally broken because Coop is broken,
        # but its Willys row carries independent healthy snapshot lineage.
        stores = await provider.find_stores("22350")
        assert [store.store_id for store in stores] == ["store-willys-lund"]

        searched = await provider.search_products("pasta", [stores[0].store_id])
        catalog = await provider.get_store_products(stores[0].store_id)
        offers = await provider.get_offers(stores[0].store_id)

    engine.dispose()

    assert [product.product_id for product in searched] == ["product-pasta"]
    assert [product.product_id for product in catalog] == ["product-pasta"]
    product = catalog[0]
    assert product.store_name == "Willys Lund Nova"
    assert product.sale_model == SaleModel.FIXED_PACKAGE
    assert product.quantity_confidence == QuantityConfidence.EXACT
    assert product.semantic_confidence == SemanticConfidence.HIGH
    assert product.package_quantity == 1000
    assert product.usable_quantity == 1000
    assert product.package_unit == product.usable_unit == "g"
    assert product.price == 24
    assert product.effective_price == 20
    assert product.member_price == 18
    assert product.source_provenance is not None
    assert product.source_provenance.collection_location == ("LOCAL_RELAY" if relay else None)
    assert product.source_provenance.source_provider == "own"
    assert product.source_provenance.source_snapshot_id == "snapshot-willys-lund"

    assert len(offers) == 1
    multipack = next(offer for offer in offers[0].offers if offer.kind == OfferKind.MULTIPACK)
    assert multipack.required_packages == 3
    assert multipack.price == 50
    # The conditional multibuy must not be flattened to 50/3 as a package price.
    assert offers[0].effective_price == 20


@pytest.mark.asyncio
async def test_own_provider_accepts_api_snapshot_under_shared_72_hour_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The API and federated OWN adapter must apply the same eligibility clock."""

    monkeypatch.setenv("FIELD_MODE_ENABLED", "false")
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "72")
    engine, factory = _contract_database(
        observed_at=datetime.now(tz=UTC) - timedelta(hours=60),
    )
    app = create_app(factory)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        base_url="http://grocery-data.test/",
        transport=transport,
    ) as api_client:
        provider = OwnGroceryPriceProvider(
            "http://grocery-data.test/",
            max_age_hours=72,
            client=api_client,
        )

        stores = await provider.find_stores("22350")
        searched = await provider.search_products("pasta", [stores[0].store_id])
        catalog = await provider.get_store_products(stores[0].store_id)

    engine.dispose()

    assert [store.store_id for store in stores] == ["store-willys-lund"]
    assert [product.product_id for product in searched] == ["product-pasta"]
    assert [product.product_id for product in catalog] == ["product-pasta"]
