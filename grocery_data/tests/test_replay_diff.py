from decimal import Decimal
from pathlib import Path

from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.domain import Chain, CoverageLevel, RawBatch, RawFetch, SourceStore
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.diff import SnapshotDiffer
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import ReplayService


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.WILLYS,
        external_id="2354",
        name="Willys Lund Nova",
        coverage=CoverageLevel.FULL_CATALOG,
        raw_reference="raw:stores",
    )


def test_replay_parses_saved_raw_without_network(tmp_path: Path) -> None:
    payload = b"""{"results":[{"code":"p1","name":"Pasta","priceValue":19.9,
        "priceUnit":"kr/st","productLine2":"500g","productBasketType":{"code":"ST"}}],
        "pagination":{"currentPage":0,"numberOfPages":1}}"""
    batch = RawBatch(
        chain=Chain.WILLYS,
        documents=(
            RawFetch(
                chain=Chain.WILLYS,
                store_external_id="2354",
                kind="catalog_page",
                method="GET",
                url="https://public.example/catalog",
                http_status=200,
                content_type="application/json",
                payload=payload,
                connector_version="willys-v1",
            ),
        ),
    )
    raw_store = FilesystemRawSnapshotStore(tmp_path)
    records = raw_store.save_batch(batch, snapshot_id="snapshot-1")
    connector = WillysConnector(client=WillysClient(max_categories=1))
    try:
        result = ReplayService(raw_store).replay_catalog(connector, records, _store())
    finally:
        # No request was made; close the unentered HTTP client deterministically.
        import asyncio

        asyncio.run(connector.aclose())
    assert result.network_requests == 0
    assert [product.external_product_id for product in result.normalized] == ["p1"]


def test_snapshot_diff_prefers_gtin_and_reports_price_change() -> None:
    source = WillysConnector().parser._parse_product(
        {
            "code": "old-id",
            "ean": "7310000000001",
            "name": "Pasta",
            "priceValue": 20,
            "priceUnit": "kr/st",
            "productLine2": "500g",
            "productBasketType": {"code": "ST"},
        },
        _store(),
        "raw:1",
        RawFetch(
            chain=Chain.WILLYS,
            kind="x",
            method="GET",
            url="https://public.example",
            http_status=200,
            payload=b"{}",
            connector_version="v1",
        ).fetched_at,
    )
    old = ProductNormalizer().normalize(source, parser_version="v1")
    new = old.model_copy(update={"external_product_id": "new-id", "sale_price": 21})
    result = SnapshotDiffer().compare([old], [new])
    assert result.added_product_keys == ()
    assert result.removed_product_keys == ()
    assert result.shared_products == 1
    assert result.price_changed_products == 1
    assert result.price_changed_keys == ("willys:2354:gtin:7310000000001",)


def test_snapshot_diff_keeps_same_gtin_separate_per_store() -> None:
    source = WillysConnector().parser._parse_product(
        {
            "code": "pasta",
            "ean": "7310000000001",
            "name": "Pasta",
            "priceValue": 20,
            "priceUnit": "kr/st",
            "productLine2": "500g",
            "productBasketType": {"code": "ST"},
        },
        _store(),
        "raw:1",
        RawFetch(
            chain=Chain.WILLYS,
            kind="x",
            method="GET",
            url="https://public.example",
            http_status=200,
            payload=b"{}",
            connector_version="v1",
        ).fetched_at,
    )
    lund_old = ProductNormalizer().normalize(source, parser_version="v1")
    malmo_old = lund_old.model_copy(
        update={
            "store_external_id": "9999",
            "source_product_key": "willys:9999:pasta",
            "sale_price": 25,
        }
    )
    lund_new = lund_old.model_copy(update={"sale_price": 21})
    malmo_new = malmo_old.model_copy(update={"sale_price": 25})

    result = SnapshotDiffer().compare(
        [lund_old, malmo_old],
        [lund_new, malmo_new],
    )

    assert result.old_products == 2
    assert result.new_products == 2
    assert result.shared_products == 2
    assert result.price_changed_products == 1
    assert result.price_changed_keys == ("willys:2354:gtin:7310000000001",)


def test_snapshot_diff_does_not_collapse_unidentified_offer_variants() -> None:
    source = WillysConnector().parser._parse_product(
        {
            "code": "temporary-source-id",
            "name": "Erbjudandegrupp",
            "priceValue": 10,
            "priceUnit": "kr/st",
            "productLine2": "500g",
            "productBasketType": {"code": "ST"},
        },
        _store(),
        "raw:old-a",
        RawFetch(
            chain=Chain.WILLYS,
            kind="x",
            method="GET",
            url="https://public.example",
            http_status=200,
            payload=b"{}",
            connector_version="v1",
        ).fetched_at,
    )
    base = (
        ProductNormalizer()
        .normalize(source, parser_version="v1")
        .model_copy(
            update={"external_product_id": None, "gtin": None, "source_product_key": "group"}
        )
    )
    first = base.model_copy(update={"sale_price": Decimal(10), "raw_reference": "raw:old-a"})
    second = base.model_copy(update={"sale_price": Decimal(20), "raw_reference": "raw:old-b"})
    replay_first = first.model_copy(update={"raw_reference": "raw:new-a", "parser_version": "v2"})
    replay_second = second.model_copy(update={"raw_reference": "raw:new-b", "parser_version": "v2"})

    result = SnapshotDiffer().compare(
        [first, second],
        [replay_second, replay_first],
    )

    assert result.old_products == result.new_products == 2
    assert result.shared_products == 2
    assert result.added_product_keys == ()
    assert result.removed_product_keys == ()
    assert result.price_changed_products == 0


def test_snapshot_diff_reports_coverage_and_parser_failure_regressions() -> None:
    source = WillysConnector().parser._parse_product(
        {
            "code": "pasta",
            "ean": "7310000000001",
            "name": "Pasta",
            "priceValue": 20,
            "priceUnit": "kr/st",
            "productLine2": "500g",
            "productBasketType": {"code": "ST"},
        },
        _store(),
        "raw:1",
        RawFetch(
            chain=Chain.WILLYS,
            kind="x",
            method="GET",
            url="https://public.example",
            http_status=200,
            payload=b"{}",
            connector_version="v1",
        ).fetched_at,
    )
    complete = ProductNormalizer().normalize(source, parser_version="v1")
    incomplete = complete.model_copy(
        update={
            "gtin": None,
            "sale_price": None,
            "package_quantity": None,
            "package_unit": None,
        }
    )

    result = SnapshotDiffer().compare(
        [complete],
        [incomplete],
        old_parser_failures=1,
        new_parser_failures=4,
    )

    assert result.old_parser_failures == 1
    assert result.new_parser_failures == 4
    assert result.old_gtin_coverage == 1
    assert result.new_gtin_coverage == 0
    assert result.old_price_coverage == 1
    assert result.new_price_coverage == 0
    assert result.old_package_quantity_coverage == 1
    assert result.new_package_quantity_coverage == 0
    assert "GTIN coverage dropped by more than 10 percentage points" in result.warnings
    assert "price coverage dropped by more than 10 percentage points" in result.warnings
    assert "missing package quantity increased by more than 10 percentage points" in result.warnings
    assert "parser failures increased from 1 to 4" in result.warnings
