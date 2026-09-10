from types import SimpleNamespace

from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    RawBatch,
    RawFetch,
    SaleModel,
    SourceStore,
)
from grocery_data.app.services.catalog_processor import CatalogProcessor


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.WILLYS,
        external_id="2354",
        name="Willys Lund Nova",
        coverage=CoverageLevel.FULL_CATALOG,
        raw_reference="raw:stores",
    )


def test_processor_quarantines_bad_record_without_dropping_it() -> None:
    payload = b"""{"results":[
      {"code":"good","name":"Pasta","priceValue":20,"priceUnit":"kr/st",
       "productLine2":"500g","productBasketType":{"code":"ST"}},
      {"code":"bad","name":"Oklar vara","priceValue":10,"priceUnit":"oklart"}
    ],"pagination":{"currentPage":0,"numberOfPages":1}}"""
    raw = RawBatch(
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
    parser = WillysParser()
    connector = SimpleNamespace(
        chain=Chain.WILLYS,
        parser_version=parser.parser_version,
        parse_catalog=parser.parse_catalog,
    )
    result = CatalogProcessor().process(connector, raw, ["raw:catalog"], _store())
    assert [product.source.external_product_id for product in result.products] == ["good"]
    assert len(result.failures) == 1
    assert result.failures[0].raw_record_reference.endswith("#results[1]")
    assert result.metrics.parse_success_rate == 0.5


def test_kr_per_sales_unit_without_package_evidence_stays_unknown() -> None:
    payload = b"""{"results":[
      {"code":"unknown","name":"Oklar vara","priceValue":10,"priceUnit":"kr/st",
       "productBasketType":{"code":"ST"}}
    ],"pagination":{"currentPage":0,"numberOfPages":1}}"""
    raw = RawBatch(
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
    parser = WillysParser()
    connector = SimpleNamespace(
        chain=Chain.WILLYS,
        parser_version=parser.parser_version,
        parse_catalog=parser.parse_catalog,
    )

    result = CatalogProcessor().process(connector, raw, ["raw:catalog"], _store())
    product = result.products[0].canonical

    assert product.sale_model is SaleModel.UNKNOWN
    assert product.quantity_confidence is Confidence.UNKNOWN
    assert product.package_quantity is None


def test_missing_stock_field_does_not_claim_availability() -> None:
    payload = b"""{"results":[
      {"code":"unknown-stock","name":"Pasta","priceValue":20,"priceUnit":"kr/st",
       "productLine2":"500g","productBasketType":{"code":"ST"}}
    ],"pagination":{"currentPage":0,"numberOfPages":1}}"""
    raw = RawBatch(
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

    product = WillysParser().parse_catalog(raw, ["raw:catalog"], _store()).products[0]

    assert product.availability is None


def test_missing_price_is_retained_for_coverage_metrics() -> None:
    payload = b"""{"results":[
      {"code":"no-price","name":"Tillfalligt oprissatt pasta","productLine2":"500g",
       "productBasketType":{"code":"ST"}}
    ],"pagination":{"currentPage":0,"numberOfPages":1}}"""
    raw = RawBatch(
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
    parser = WillysParser()
    connector = SimpleNamespace(
        chain=Chain.WILLYS,
        parser_version=parser.parser_version,
        parse_catalog=parser.parse_catalog,
    )

    result = CatalogProcessor().process(connector, raw, ["raw:catalog"], _store())

    assert len(result.products) == 1
    assert result.products[0].source.sale_price is None
    assert result.metrics.products_with_price == 0
    assert result.metrics.price_coverage == 0
    assert any("no sale or unit price" in warning for warning in result.warnings)
