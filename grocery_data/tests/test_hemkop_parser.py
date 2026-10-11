import json
from decimal import Decimal
from pathlib import Path

import pytest

from grocery_data.app.connectors.hemkop.parser import HemkopParser
from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    GeographicArea,
    PriceContextType,
    PromotionType,
    RawBatch,
    RawFetch,
    SaleModel,
    SourceStore,
)
from grocery_data.app.normalization import ProductNormalizer

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "hemkop" / "fixtures"


def _raw(name: str, *, kind: str = "catalog_page") -> RawBatch:
    documents: tuple[RawFetch, ...]
    source = RawFetch(
        chain=Chain.HEMKOP,
        store_external_id="4224",
        kind=kind,
        method="GET",
        url="https://public.example/hemkop/catalog",
        http_status=200,
        content_type="application/json",
        payload=(FIXTURES / name).read_bytes(),
        connector_version="hemkop-v1",
        page_number=0 if kind == "catalog_page" else None,
    )
    if kind == "catalog_page":
        documents = (_context(), source)
    else:
        documents = (source,)
    return RawBatch(
        chain=Chain.HEMKOP,
        documents=documents,
    )


def _context(store_id: str = "4224") -> RawFetch:
    return RawFetch(
        chain=Chain.HEMKOP,
        store_external_id=store_id,
        kind="store_context",
        method="GET",
        url="https://public.example/axfood/rest/store/active",
        http_status=200,
        content_type="application/json",
        payload=(f'{{"pickingStore":{{"storeId":"{store_id}"}}}}').encode(),
        connector_version="hemkop-v1",
    )


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.HEMKOP,
        external_id="4224",
        name="Hemköp Lund Brunnshög",
        city="Lund",
        online_shopping=True,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        price_context_type=PriceContextType.ONLINE_STORE,
        physical_store_external_id="4224",
        raw_reference="raw:stores#storeId=4224",
    )


def _parse(name: str, *, kind: str = "catalog_page"):
    raw = _raw(name, kind=kind)
    return HemkopParser().parse_catalog(
        raw,
        [f"raw:{index}:{name}" for index, _ in enumerate(raw.documents)],
        _store(),
    )


def test_store_parser_preserves_hemkop_online_context_and_exact_city_scope() -> None:
    raw = RawBatch(
        chain=Chain.HEMKOP,
        documents=(
            RawFetch(
                chain=Chain.HEMKOP,
                kind="stores",
                method="GET",
                url="https://public.example/hemkop/stores",
                http_status=200,
                content_type="application/json",
                payload=(FIXTURES / "stores.json").read_bytes(),
                connector_version="hemkop-v1",
            ),
        ),
    )

    stores = HemkopParser().parse_stores(raw, ["raw:stores"], GeographicArea(city="Lund"))

    assert [store.external_id for store in stores] == ["4224", "4123"]
    assert all(store.chain is Chain.HEMKOP for store in stores)
    assert all(store.online_shopping is True for store in stores)
    assert all(store.coverage is CoverageLevel.FULL_ONLINE_CATALOG for store in stores)
    assert all(store.price_context_type is PriceContextType.ONLINE_STORE for store in stores)
    assert all(store.physical_store_external_id == store.external_id for store in stores)
    assert all(
        store.source_fields["price_context_activation_required"] is True
        for store in stores
    )
    assert all(store.source_fields["price_context_verified"] is False for store in stores)
    assert "4000" not in {store.external_id for store in stores}


def test_product_observation_records_only_actual_activation_readback() -> None:
    catalog = _raw("fixed_package.json").documents[-1]
    context = _context()
    result = HemkopParser().parse_catalog(
        RawBatch(chain=Chain.HEMKOP, documents=(context, catalog)),
        ["raw:context", "raw:catalog"],
        _store(),
    )

    assert result.products[0].source_fields["price_context_activation_confirmed"] is True
    detail_without_context = _parse("product_detail.json", kind="product_detail").products[0]
    assert detail_without_context.source_fields["price_context_activation_confirmed"] is False


@pytest.mark.parametrize(
    "context",
    [None, _context("4114")],
    ids=("missing-context", "mismatched-context"),
)
def test_catalog_parser_fails_closed_without_matching_activation_readback(
    context: RawFetch | None,
) -> None:
    catalog = _raw("fixed_package.json").documents[-1]
    documents = (catalog,) if context is None else (context, catalog)
    result = HemkopParser().parse_catalog(
        RawBatch(chain=Chain.HEMKOP, documents=documents),
        [f"raw:{index}" for index, _ in enumerate(documents)],
        _store(),
    )

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "price_context_unverified"


@pytest.mark.parametrize("page_store_id", [None, "4114"], ids=("missing", "switched"))
def test_catalog_parser_rejects_missing_or_switched_page_context(
    page_store_id: str | None,
) -> None:
    payload = json.loads((FIXTURES / "fixed_package.json").read_bytes())
    if page_store_id is None:
        payload.pop("facets")
    else:
        payload["facets"][0]["values"][0]["query"]["query"]["value"] = (
            f":topRated:salableOnlineInStore_string_mv:{page_store_id}"
        )
    page = _raw("fixed_package.json").documents[-1].model_copy(
        update={"payload": json.dumps(payload).encode()}
    )
    result = HemkopParser().parse_catalog(
        RawBatch(chain=Chain.HEMKOP, documents=(_context(), page)),
        ["raw:context", "raw:page"],
        _store(),
    )

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "schema_changed"
    assert "facet" in result.failures[0].error_message


@pytest.mark.parametrize(
    ("fixture", "sale_model", "quantity", "confidence"),
    [
        ("fixed_package.json", SaleModel.FIXED_PACKAGE, 500, Confidence.EXACT),
        ("sold_by_weight.json", SaleModel.SOLD_BY_WEIGHT, None, Confidence.DERIVED),
        ("sold_by_piece.json", SaleModel.SOLD_BY_PIECE, 1, Confidence.EXACT),
        (
            "variable_weight.json",
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
            850,
            Confidence.ESTIMATED,
        ),
    ],
)
def test_purchase_models_are_derived_only_from_source_evidence(
    fixture: str,
    sale_model: SaleModel,
    quantity: int | None,
    confidence: Confidence,
) -> None:
    result = _parse(fixture)

    assert result.failures == []
    assert len(result.products) == 1
    source = result.products[0]
    canonical = ProductNormalizer().normalize(
        source,
        parser_version=HemkopParser.parser_version,
    )

    assert source.chain is Chain.HEMKOP
    assert source.store_external_id == "4224"
    assert canonical.chain is Chain.HEMKOP
    assert canonical.sale_model is sale_model
    assert canonical.package_quantity == quantity
    assert canonical.quantity_confidence is confidence


def test_fixed_package_keeps_price_comparison_and_category_as_separate_facts() -> None:
    source = _parse("fixed_package.json").products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=HemkopParser.parser_version)

    assert source.external_product_id == "101548687_ST"
    assert source.name == "Fusilli"
    assert source.brand == "Garant"
    assert source.sale_price == Decimal("15.09")
    assert source.comparison_price == Decimal("30.18")
    assert source.comparison_unit == "kg"
    assert source.package_quantity == 500
    assert source.package_unit == "g"
    assert source.category_path == ("Skafferi", "Pasta")
    assert canonical.sale_price == Decimal("15.09")
    assert canonical.package_quantity == 500


def test_comparison_price_never_manufactures_a_weight_package() -> None:
    source = _parse("sold_by_weight.json").products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=HemkopParser.parser_version)

    assert source.comparison_price == Decimal("14.9")
    assert source.comparison_unit == "kr/kg"
    assert canonical.comparison_unit == "kg"
    assert canonical.package_quantity is None
    assert canonical.sale_model is SaleModel.SOLD_BY_WEIGHT


def test_drained_weight_becomes_usable_quantity_without_replacing_gross_weight() -> None:
    result = _parse("drained_weight.json")

    assert result.failures == []
    source = result.products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=HemkopParser.parser_version)

    assert source.gtin is None
    assert source.package_quantity == 380
    assert source.package_unit == "g"
    assert source.drained_quantity == 230
    assert canonical.package_quantity == 380
    assert canonical.usable_quantity == 230
    assert canonical.usable_unit == "g"
    assert canonical.quantity_confidence is Confidence.DERIVED


def test_product_detail_preserves_the_verified_gtin() -> None:
    result = _parse("product_detail.json", kind="product_detail")

    assert result.failures == []
    assert result.products[0].chain is Chain.HEMKOP
    assert result.products[0].external_product_id == "101548687_ST"
    assert result.products[0].gtin == "7311043008346"


def test_member_price_remains_conditional_and_separate_from_regular_price() -> None:
    product = _parse("member_price.json").products[0]

    assert product.sale_price == 119
    assert product.regular_price == 119
    assert len(product.offers) == 1
    offer = product.offers[0]
    assert offer.type is PromotionType.MEMBER_PRICE
    assert offer.member_only is True
    assert offer.price == 105
    assert offer.quantity == 1
    assert offer.max_quantity == 3


def test_multibuy_preserves_the_group_condition_and_total_price() -> None:
    product = _parse("multibuy.json").products[0]

    assert product.sale_price == Decimal("15.09")
    assert len(product.offers) == 1
    offer = product.offers[0]
    assert offer.type is PromotionType.MULTIBUY
    assert offer.member_only is False
    assert offer.quantity == 3
    assert offer.price == 39
    assert "3 för 39" in (offer.description or "")


def test_missing_gtin_and_ambiguous_package_remain_unknown() -> None:
    result = _parse("missing_gtin_unknown_quantity.json")

    assert result.failures == []
    source = result.products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=HemkopParser.parser_version)

    assert source.gtin is None
    assert source.package_quantity is None
    assert source.package_unit is None
    assert canonical.sale_model is SaleModel.UNKNOWN
    assert canonical.quantity_confidence is Confidence.UNKNOWN
    assert canonical.package_quantity is None


def test_parser_contract_version_and_lineage_are_hemkop_specific() -> None:
    source = _parse("fixed_package.json").products[0]
    canonical = ProductNormalizer().normalize(source, parser_version=HemkopParser.parser_version)

    assert HemkopParser.parser_version == "hemkop-parser-v1.3-reviewed-catalog"
    assert canonical.parser_version == HemkopParser.parser_version
    assert source.chain is Chain.HEMKOP
    assert source.raw_reference.startswith("raw:1:fixed_package.json#results[0]")


@pytest.mark.parametrize(
    "payload",
    [
        b'{"results":null,"pagination":{"currentPage":0,"numberOfPages":1,"pageSize":30,"totalNumberOfResults":1}}',
        b'{"results":[],"pagination":{"currentPage":1,"numberOfPages":1,"pageSize":30,"totalNumberOfResults":0}}',
        b'{"results":[]}',
    ],
    ids=("null-results", "page-mismatch", "missing-pagination"),
)
def test_parser_quarantines_ambiguous_catalog_pagination(payload: bytes) -> None:
    raw = RawBatch(
        chain=Chain.HEMKOP,
        documents=(
            _context(),
            RawFetch(
                chain=Chain.HEMKOP,
                store_external_id="4224",
                kind="catalog_page",
                method="GET",
                url="https://public.example/hemkop/catalog",
                http_status=200,
                content_type="application/json",
                payload=payload,
                connector_version="hemkop-v1",
                page_number=0,
            ),
        ),
    )

    result = HemkopParser().parse_catalog(
        raw,
        ["raw:context", "raw:ambiguous"],
        _store(),
    )

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "schema_changed"
