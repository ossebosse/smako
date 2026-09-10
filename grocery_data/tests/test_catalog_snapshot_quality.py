from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from grocery_data.__main__ import _parser
from grocery_data.app.services.catalog_snapshot_quality import (
    CatalogSnapshotQualityReporter,
    is_valid_gtin,
)
from grocery_data.app.storage import (
    CatalogSnapshotModel,
    CollectorRunModel,
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

NOW = datetime(2026, 8, 23, 12, tzinfo=UTC)


def _database() -> tuple[Session, StoreModel, CatalogSnapshotModel, list[RawSnapshotModel]]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    session = create_session_factory(engine)()
    run = CollectorRunModel(
        id="run-quality",
        chain="citygross",
        scope={"city": "Malmö"},
        status="finished",
        connector_version="citygross-v1",
        parser_version="citygross-parser-v1",
        normalizer_version="normalizer-v2",
        started_at=NOW - timedelta(seconds=2),
        finished_at=NOW,
        successful=True,
        metrics={
            "products_parsed": 4,
            "request_count": 3,
            "http_error_count": 1,
            "rate_limit_count": 1,
            "runtime_ms": 1234,
        },
    )
    store = StoreModel(
        id="store-3211",
        chain="citygross",
        external_id="3211",
        name="City Gross Malmö Hyllie",
        city="Malmö",
        coverage="partial_catalog",
        raw_reference="raw:stores#3211",
    )
    snapshot = CatalogSnapshotModel(
        id="snapshot-quality",
        chain="citygross",
        scope_key="malmö",
        coverage="partial_catalog",
        state="health_checked",
        collector_run_id=run.id,
        connector_version="citygross-v1",
        parser_version="citygross-parser-v1",
        normalizer_version="normalizer-v2",
        metrics={
            "run_metrics": run.metrics,
            "catalog_completion": {
                "3211": {
                    "complete": True,
                    "limited": False,
                    "pages_fetched": 2,
                    "products_observed": 4,
                    "expected_products": 4,
                    "raw_rows": 4,
                    "unique_products": 4,
                    "duplicate_products": 0,
                    "expected_pages": 2,
                }
            },
        },
    )
    raw_rows = [
        RawSnapshotModel(
            id="raw-stores",
            catalog_snapshot_id=snapshot.id,
            collector_run_id=run.id,
            chain="citygross",
            kind="stores",
            method="GET",
            url="https://public.example/stores",
            query={},
            fetched_at=NOW,
            http_status=200,
            content_type="application/json",
            payload_hash="a" * 64,
            payload_size=40,
            payload_location="raw/stores.json",
            request_fingerprint="request-stores",
            connector_version="citygross-v1",
        ),
        RawSnapshotModel(
            id="raw-page-1",
            catalog_snapshot_id=snapshot.id,
            collector_run_id=run.id,
            chain="citygross",
            store_external_id=store.external_id,
            kind="catalog_page",
            method="GET",
            url="https://public.example/products",
            query={"skip": "0"},
            fetched_at=NOW,
            http_status=200,
            content_type="application/json",
            payload_hash="b" * 64,
            payload_size=100,
            payload_location="raw/page-1.json",
            request_fingerprint="request-page-1",
            connector_version="citygross-v1",
            page_number=1,
        ),
        RawSnapshotModel(
            id="raw-page-2",
            catalog_snapshot_id=snapshot.id,
            collector_run_id=run.id,
            chain="citygross",
            store_external_id=store.external_id,
            kind="rate_limit",
            method="GET",
            url="https://public.example/products",
            query={"skip": "2"},
            fetched_at=NOW,
            http_status=429,
            content_type="application/json",
            payload_hash="c" * 64,
            payload_size=50,
            payload_location="raw/page-2.json",
            request_fingerprint="request-page-2",
            connector_version="citygross-v1",
            page_number=2,
        ),
    ]
    # These models intentionally have no ORM relationship attributes, so make
    # the FK insertion order explicit for SQLite's enabled FK checks.
    session.add(run)
    session.flush()
    session.add_all([store, snapshot])
    session.flush()
    session.add_all(raw_rows)
    session.flush()
    return session, store, snapshot, raw_rows


def _add_product(
    session: Session,
    store: StoreModel,
    snapshot: CatalogSnapshotModel,
    raw: RawSnapshotModel,
    *,
    suffix: str,
    name: str,
    category: str,
    raw_gtin: str | None,
    sale_model: str,
    quantity_confidence: str,
    package_quantity: Decimal | None,
    availability: str | None,
    sale_price: Decimal | None,
    regular_price: Decimal | None,
    with_price_row: bool = True,
) -> tuple[SourceProductModel, ProductModel, PriceObservationModel | None]:
    raw_reference = f"raw:{raw.id}#items[{suffix}]"
    source = SourceProductModel(
        id=f"source-{suffix}",
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=f"external-{suffix}",
        gtin=raw_gtin if is_valid_gtin(raw_gtin) else None,
        name=name,
        brand="Testbrand",
        category_path=[category, "Test"],
        sale_price=sale_price,
        regular_price=regular_price,
        package_quantity=package_quantity,
        package_unit="kg" if package_quantity is not None else None,
        availability=availability,
        raw_reference=raw_reference,
        fetched_at=NOW,
        parser_version="citygross-parser-v1",
        source_fields={"raw_gtin": raw_gtin},
        source_record_hash=f"record-hash-{suffix}",
    )
    product = ProductModel(
        id=f"product-{suffix}",
        source_product_id=source.id,
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw.id,
        store_id=store.id,
        source_product_key=f"citygross:{store.external_id}:external-{suffix}",
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=source.external_product_id,
        gtin=source.gtin,
        name=name,
        brand=source.brand,
        category_path=source.category_path,
        canonical_food=suffix,
        semantic_confidence="high",
        sale_model=sale_model,
        quantity_confidence=quantity_confidence,
        package_quantity=package_quantity,
        package_unit=source.package_unit,
        usable_quantity=package_quantity,
        usable_unit=source.package_unit,
        sale_price=sale_price,
        sale_unit="st",
        availability=availability,
        raw_reference=raw_reference,
        parser_version="citygross-parser-v1",
        normalizer_version="normalizer-v2",
        observed_at=NOW,
    )
    session.add(source)
    session.flush()
    session.add(product)
    session.flush()
    price = None
    if with_price_row:
        price = PriceObservationModel(
            id=f"price-{suffix}",
            catalog_snapshot_id=snapshot.id,
            product_id=product.id,
            source_product_id=source.id,
            store_id=store.id,
            raw_snapshot_id=raw.id,
            observed_at=NOW,
            sale_price=sale_price,
            regular_price=regular_price,
            comparison_price=Decimal(20) if sale_price is not None else None,
            comparison_unit="kg" if sale_price is not None else None,
            sale_unit="st",
        )
        session.add(price)
    session.flush()
    return source, product, price


def _seed_products(
    session: Session,
    store: StoreModel,
    snapshot: CatalogSnapshotModel,
    raw: RawSnapshotModel,
) -> list[tuple[SourceProductModel, ProductModel, PriceObservationModel | None]]:
    return [
        _add_product(
            session,
            store,
            snapshot,
            raw,
            suffix="milk",
            name="A Milk",
            category="Mejeri",
            raw_gtin="4006381333931",
            sale_model="fixed_package",
            quantity_confidence="exact",
            package_quantity=Decimal(1),
            availability="available",
            sale_price=Decimal(15),
            regular_price=Decimal(17),
        ),
        _add_product(
            session,
            store,
            snapshot,
            raw,
            suffix="meat",
            name="B Meat",
            category="Kött",
            raw_gtin="4006381333932",
            sale_model="sold_by_weight",
            quantity_confidence="derived",
            package_quantity=None,
            availability=None,
            sale_price=Decimal(99),
            regular_price=None,
        ),
        _add_product(
            session,
            store,
            snapshot,
            raw,
            suffix="cleaning",
            name="C Cleaning",
            category="Hushåll",
            raw_gtin=None,
            sale_model="unknown",
            quantity_confidence="unknown",
            package_quantity=None,
            availability=None,
            sale_price=None,
            regular_price=None,
            with_price_row=False,
        ),
        _add_product(
            session,
            store,
            snapshot,
            raw,
            suffix="pasta",
            name="D Pasta",
            category="Skafferi",
            raw_gtin=None,
            sale_model="fixed_package",
            quantity_confidence="estimated",
            package_quantity=Decimal("0.5"),
            availability="available",
            sale_price=Decimal(0),
            regular_price=None,
        ),
    ]


def _add_promotions(
    session: Session,
    store: StoreModel,
    snapshot: CatalogSnapshotModel,
    raw: RawSnapshotModel,
    products: list[tuple[SourceProductModel, ProductModel, PriceObservationModel | None]],
) -> None:
    milk_source, milk, milk_price = products[0]
    meat_source, meat, meat_price = products[1]
    assert milk_price is not None and meat_price is not None
    session.add_all(
        [
            PromotionModel(
                id="promotion-sale",
                catalog_snapshot_id=snapshot.id,
                source_product_id=milk_source.id,
                product_id=milk.id,
                store_id=store.id,
                raw_snapshot_id=raw.id,
                price_observation_id=milk_price.id,
                offer_fingerprint="offer-sale",
                type="sale_price",
                valid_from=date(2026, 8, 17),
                valid_to=date(2026, 8, 23),
                price=Decimal(15),
                quantity=1,
                member_only=False,
                max_quantity=3,
                parser_version="citygross-parser-v1",
            ),
            PromotionModel(
                id="promotion-member-multi",
                catalog_snapshot_id=snapshot.id,
                source_product_id=meat_source.id,
                product_id=meat.id,
                store_id=store.id,
                raw_snapshot_id=raw.id,
                price_observation_id=meat_price.id,
                offer_fingerprint="offer-member-multi",
                type="multibuy",
                valid_from=date(2026, 8, 17),
                price=Decimal(150),
                quantity=2,
                member_only=True,
                max_quantity=1,
                parser_version="citygross-parser-v1",
            ),
        ]
    )
    session.flush()


def test_quality_report_reconciles_persisted_product_and_transport_evidence() -> None:
    session, store, snapshot, raw_rows = _database()
    products = _seed_products(session, store, snapshot, raw_rows[1])
    _add_promotions(session, store, snapshot, raw_rows[1], products)
    session.add_all(
        [
            ParserFailureModel(
                id="failure-selected",
                catalog_snapshot_id=snapshot.id,
                collector_run_id=snapshot.collector_run_id,
                raw_snapshot_id=raw_rows[1].id,
                chain=store.chain,
                store_external_id=store.external_id,
                raw_record_reference="raw:bad#1",
                error_code="invalid_price",
                error_message="sanitized",
                parser_version="citygross-parser-v1",
                failure_fingerprint="failure-selected-fingerprint",
            ),
            ParserFailureModel(
                id="failure-other-store",
                catalog_snapshot_id=snapshot.id,
                collector_run_id=snapshot.collector_run_id,
                raw_snapshot_id=raw_rows[1].id,
                chain=store.chain,
                store_external_id="3203",
                raw_record_reference="raw:bad#2",
                error_code="schema_changed",
                error_message="sanitized",
                parser_version="citygross-parser-v1",
                failure_fingerprint="failure-other-fingerprint",
            ),
        ]
    )
    session.flush()

    report = CatalogSnapshotQualityReporter(session).run(
        snapshot.id,
        store.id,
        max_manual_samples=3,
    )

    assert report.normalized_rows == 4
    assert report.overall.products == 4
    assert report.overall.products_with_price == 2
    assert report.overall.price_coverage_percent == Decimal("50.00")
    assert report.overall.products_with_regular_price == 1
    assert report.overall.regular_price_coverage_percent == Decimal("25.00")
    assert report.overall.products_with_raw_gtin == 2
    assert report.overall.products_with_valid_gtin == 1
    assert report.overall.valid_gtin_percent_of_raw == Decimal("50.00")
    assert report.overall.products_with_package_quantity == 2
    assert report.overall.products_with_resolved_purchase_model == 3
    assert report.overall.resolved_purchase_model_percent == Decimal("75.00")
    assert report.overall.quantity_confidence_distribution == {
        "derived": 1,
        "estimated": 1,
        "exact": 1,
        "unknown": 1,
    }
    assert report.overall.products_with_availability == 2

    assert report.recipe_relevant.products == 3
    assert report.recipe_relevant.products_with_price == 2
    assert report.recipe_relevant.products_with_package_quantity == 2
    assert report.recipe_relevant.products_with_resolved_purchase_model == 3
    assert report.recipe_relevant.quantity_confidence_distribution == {
        "derived": 1,
        "estimated": 1,
        "exact": 1,
    }

    assert report.promotions.promotions == 2
    assert report.promotions.promoted_products == 2
    assert report.promotions.type_distribution == {"multibuy": 1, "sale_price": 1}
    assert report.promotions.member_only == 1
    assert report.promotions.multibuy == 1
    assert report.promotions.member_multibuy == 1
    assert report.promotions.with_max_quantity == 2
    assert report.promotions.max_quantity_distribution == {"1": 1, "3": 1}
    assert report.promotions.with_valid_from == 2
    assert report.promotions.with_valid_to == 1
    assert report.promotions.with_complete_validity_period == 1

    assert report.raw_payloads.snapshot_payloads == 3
    assert report.raw_payloads.snapshot_bytes == 190
    assert report.raw_payloads.selected_store_payloads == 2
    assert report.raw_payloads.selected_store_bytes == 150
    assert report.raw_payloads.http_status_distribution == {"200": 2, "429": 1}
    assert report.raw_payloads.captured_http_errors == 1
    assert report.raw_payloads.captured_429_responses == 1

    assert report.transport.request_count == 3
    assert report.transport.http_error_count == 1
    assert report.transport.rate_limit_count == 1
    assert report.transport.runtime_ms == 1234
    assert report.transport.wall_clock_runtime_ms == 2000
    assert report.transport.run_metrics_valid is True
    assert report.completion.valid is True
    assert report.completion.full_traversal_proven is True
    assert report.completion.expected_products == 4
    assert report.completion.unique_products == 4
    assert report.completion.duplicate_products == 0

    assert report.quarantine.snapshot_failures == 2
    assert report.quarantine.selected_store_failures == 1
    assert report.quarantine.selected_store_code_distribution == {"invalid_price": 1}

    assert [sample.category_path[0] for sample in report.manual_samples] == [
        "Hushåll",
        "Kött",
        "Mejeri",
    ]
    assert report.manual_samples[-1].promotion_types == ["sale_price"]
    dumped_sample = report.manual_samples[0].model_dump(mode="json")
    assert "raw_reference" not in dumped_sample
    assert "source_fields" not in dumped_sample
    assert "payload_location" not in dumped_sample


def test_report_deduplicates_normalizer_versions_by_source_identity() -> None:
    session, store, snapshot, raw_rows = _database()
    source, original, _ = _add_product(
        session,
        store,
        snapshot,
        raw_rows[1],
        suffix="milk",
        name="Milk",
        category="Mejeri",
        raw_gtin="4006381333931",
        sale_model="fixed_package",
        quantity_confidence="exact",
        package_quantity=Decimal(1),
        availability="available",
        sale_price=Decimal(15),
        regular_price=Decimal(17),
    )
    replayed = ProductModel(
        id="product-milk-replayed",
        source_product_id=source.id,
        catalog_snapshot_id=snapshot.id,
        raw_snapshot_id=raw_rows[1].id,
        store_id=store.id,
        source_product_key=original.source_product_key,
        chain=store.chain,
        store_external_id=store.external_id,
        external_product_id=source.external_product_id,
        gtin=source.gtin,
        name=source.name,
        category_path=source.category_path,
        canonical_food="milk",
        semantic_confidence="high",
        sale_model="fixed_package",
        quantity_confidence="exact",
        package_quantity=Decimal(1),
        package_unit="kg",
        raw_reference=source.raw_reference,
        parser_version="citygross-parser-v1",
        normalizer_version="normalizer-v3",
        observed_at=NOW + timedelta(seconds=1),
    )
    session.add(replayed)
    session.flush()

    report = CatalogSnapshotQualityReporter(session).run(snapshot.id, store.id)

    assert report.normalized_rows == 2
    assert report.overall.products == 1


def test_invalid_or_missing_completion_evidence_fails_closed_in_report() -> None:
    session, store, snapshot, _ = _database()
    snapshot.metrics = {
        "catalog_completion": {
            store.external_id: {
                "complete": True,
                "expected_products": 4,
            }
        }
    }
    session.flush()

    invalid = CatalogSnapshotQualityReporter(session).run(snapshot.id, store.id)
    assert invalid.completion.present is True
    assert invalid.completion.valid is False
    assert invalid.completion.full_traversal_proven is False
    assert invalid.completion.validation_error == "invalid_catalog_completion_evidence"

    snapshot.metrics = {}
    session.flush()
    missing = CatalogSnapshotQualityReporter(session).run(snapshot.id, store.id)
    assert missing.completion.present is False
    assert missing.completion.valid is False
    assert missing.completion.full_traversal_proven is False


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        ("4006381333931", True),
        ("4006381333932", False),
        ("96385074", True),
        ("24000124962", False),
        ("", False),
        (None, False),
    ],
)
def test_gtin_validation_is_strict_and_never_pads(value: str | None, valid: bool) -> None:
    assert is_valid_gtin(value) is valid


def test_report_validates_scope_and_sample_bound() -> None:
    session, store, snapshot, _ = _database()
    reporter = CatalogSnapshotQualityReporter(session)
    with pytest.raises(ValueError, match="between 0 and 100"):
        reporter.run(snapshot.id, store.id, max_manual_samples=101)
    with pytest.raises(LookupError, match="does not exist"):
        reporter.run("missing", store.id)

    other_store = StoreModel(
        id="store-other-chain",
        chain="willys",
        external_id="other",
        name="Other",
        coverage="full_catalog",
        raw_reference="raw:other",
    )
    session.add(other_store)
    session.flush()
    with pytest.raises(ValueError, match="same chain"):
        reporter.run(snapshot.id, other_store.id)


def test_snapshot_quality_cli_wiring_is_explicit_and_bounded() -> None:
    args = _parser().parse_args(
        [
            "snapshot-quality",
            "--snapshot-id",
            "candidate",
            "--store-id",
            "store-3211",
            "--sample-limit",
            "12",
        ]
    )
    assert args.command == "snapshot-quality"
    assert args.snapshot_id == "candidate"
    assert args.store_id == "store-3211"
    assert args.sample_limit == 12

    with pytest.raises(SystemExit):
        _parser().parse_args(
            [
                "snapshot-quality",
                "--snapshot-id",
                "candidate",
                "--store-id",
                "store-3211",
                "--sample-limit",
                "101",
            ]
        )
