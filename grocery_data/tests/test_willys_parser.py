from pathlib import Path

import pytest

from grocery_data.app.connectors.willys import WillysConnector
from grocery_data.app.connectors.willys.parser import WillysParser, parse_package_text
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

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "willys" / "fixtures"


def _raw(name: str, *, kind: str = "catalog_page") -> RawBatch:
    payload = (FIXTURES / name).read_bytes()
    return RawBatch(
        chain=Chain.WILLYS,
        documents=(
            RawFetch(
                chain=Chain.WILLYS,
                store_external_id="2354",
                kind=kind,
                method="GET",
                url="https://public.example/catalog",
                http_status=200,
                content_type="application/json",
                payload=payload,
                connector_version="willys-v1",
            ),
        ),
    )


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.WILLYS,
        external_id="2354",
        name="Willys Lund Nova",
        city="Lund",
        coverage=CoverageLevel.FULL_CATALOG,
        raw_reference="raw:stores#2354",
    )


def test_optional_store_allowlist_is_exact_and_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    online = _store().model_copy(update={"online_shopping": True})
    other = online.model_copy(update={"external_id": "2244"})

    assert WillysConnector(allowed_store_ids={"2244"}).catalog_eligible(online) is False
    assert WillysConnector(allowed_store_ids={"2244"}).catalog_eligible(other) is True
    assert WillysConnector(allowed_store_ids=()).catalog_eligible(other) is False

    monkeypatch.setenv("WILLYS_STORE_EXTERNAL_IDS", " 2244, 2114 ")
    configured = WillysConnector()
    assert configured.allowed_store_ids == frozenset({"2244", "2114"})
    assert configured.catalog_eligible(other) is True


def test_collection_policy_audit_closes_over_env_scope_and_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WILLYS_STORE_EXTERNAL_IDS", " 2354,2176 ")
    monkeypatch.setenv("WILLYS_REQUESTS_PER_SECOND", "0.75")

    audit = WillysConnector().collection_policy_audit()

    assert audit.model_dump(mode="json") == {
        "source_policy": "allow",
        "operator_opt_in": False,
        "store_allowlist": ["2176", "2354"],
        "requests_per_second": 0.75,
        "max_concurrency": 1,
    }


def test_empty_store_allowlist_environment_preserves_reference_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WILLYS_STORE_EXTERNAL_IDS", "")
    online = _store().model_copy(update={"online_shopping": True})

    connector = WillysConnector()

    assert connector.allowed_store_ids is None
    assert connector.catalog_eligible(online) is True


def test_targeted_collection_drops_uncollected_store_contexts() -> None:
    online = _store().model_copy(update={"online_shopping": True})
    selected = online.model_copy(update={"external_id": "2244", "name": "Willys Malmö"})

    class FixtureStoreParser:
        parser_version = "fixture"

        def parse_stores(self, raw, references, area):  # type: ignore[no-untyped-def]
            del raw, references, area
            return [online, selected]

    connector = WillysConnector(
        client=object(),  # type: ignore[arg-type]
        parser=FixtureStoreParser(),  # type: ignore[arg-type]
        allowed_store_ids={"2244"},
    )

    assert connector.parse_stores(
        RawBatch(chain=Chain.WILLYS, documents=()), [], GeographicArea(city="Malmö")
    ) == [selected]


def _parse(name: str, *, kind: str = "catalog_page"):
    return WillysParser().parse_catalog(_raw(name, kind=kind), [f"raw:{name}"], _store())


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
def test_purchase_models_are_source_evidence_based(
    fixture: str,
    sale_model: SaleModel,
    quantity: int | None,
    confidence: Confidence,
) -> None:
    parsed = _parse(fixture)
    assert not parsed.failures
    normalized = ProductNormalizer().normalize(
        parsed.products[0], parser_version=WillysParser.parser_version
    )
    assert normalized.sale_model == sale_model
    assert normalized.package_quantity == quantity
    assert normalized.quantity_confidence == confidence


def test_comparison_price_never_manufactures_package_size() -> None:
    parsed = _parse("sold_by_weight.json").products[0]
    normalized = ProductNormalizer().normalize(parsed, parser_version="test")
    assert normalized.comparison_price == parsed.comparison_price
    assert normalized.comparison_unit == "kg"
    assert normalized.package_quantity is None


def test_drained_weight_is_preserved_as_usable_quantity() -> None:
    payload = """{"results":[{
      "code":"beans","name":"Kidneybönor","priceValue":14.9,"priceUnit":"kr/st",
      "productLine2":"380g, avrunnen vikt 230g","productBasketType":{"code":"ST"}
    }],"pagination":{"currentPage":0,"numberOfPages":1}}""".encode()
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

    source = WillysParser().parse_catalog(raw, ["raw:catalog"], _store()).products[0]
    normalized = ProductNormalizer().normalize(source, parser_version="test")

    assert source.package_quantity == 380
    assert source.drained_quantity == 230
    assert normalized.package_quantity == 380
    assert normalized.usable_quantity == 230
    assert normalized.quantity_confidence == Confidence.DERIVED


def test_willys_multibuy_preserves_group_price() -> None:
    product = _parse("multipack.json").products[0]
    offer = product.offers[0]
    assert offer.type == PromotionType.MULTIBUY
    assert offer.quantity == 3
    assert offer.price == 32


def test_willys_member_price_remains_conditional() -> None:
    product = _parse("member_price.json").products[0]
    offer = product.offers[0]
    assert offer.type == PromotionType.MEMBER_PRICE
    assert offer.member_only is True
    assert offer.price == 105
    assert product.sale_price == 119


def test_product_detail_enriches_gtin() -> None:
    product = _parse("product_detail.json", kind="product_detail").products[0]
    assert product.gtin == "7611612150729"


def test_real_catalog_page_category_context_is_ordered_and_deduplicated() -> None:
    product = _parse("category_context.json").products[0]

    assert product.category_path == ("Skafferi", "Pasta, ris & matgryn", "Ris")
    assert "Alla varor" not in product.category_path
    assert product.category_path.count("Ris") == 1


def test_category_parser_version_is_exposed_and_preserved_in_lineage() -> None:
    parser = WillysParser()
    connector = WillysConnector(parser=parser)
    source = _parse("category_context.json").products[0]
    normalized = ProductNormalizer().normalize(source, parser_version=connector.parser_version)

    assert parser.parser_version == "willys-parser-v5"
    assert connector.parser_version == parser.parser_version
    assert normalized.parser_version == parser.parser_version


def test_schema_break_is_quarantined() -> None:
    result = _parse("schema_changed.json")
    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code in {"invalid_price", "unknown_price_unit"}


@pytest.mark.parametrize(
    "payload",
    [
        b"[]",
        b'{"results":{}}',
        b'{"results":["not-an-object"]}',
    ],
    ids=("payload-not-object", "results-not-list", "row-not-object"),
)
def test_catalog_shape_changes_are_explicit_parser_failures(payload: bytes) -> None:
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

    result = WillysParser().parse_catalog(raw, ["raw:catalog"], _store())

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "schema_changed"


def test_parser_replays_proven_terminal_null_results_as_empty_page() -> None:
    payload = b"""{
      "results": null,
      "pagination": {
        "currentPage": 2,
        "numberOfPages": 3,
        "pageSize": 30,
        "totalNumberOfResults": 60
      }
    }"""
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
                page_number=2,
            ),
        ),
    )

    result = WillysParser().parse_catalog(raw, ["raw:terminal-null"], _store())

    assert result.products == []
    assert result.failures == []


def test_parser_rejects_null_results_without_terminal_consistency_proof() -> None:
    payload = b"""{
      "results": null,
      "pagination": {
        "currentPage": 1,
        "numberOfPages": 2,
        "pageSize": 30,
        "totalNumberOfResults": 31
      }
    }"""
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
                page_number=1,
            ),
        ),
    )

    result = WillysParser().parse_catalog(raw, ["raw:ambiguous-null"], _store())

    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "schema_changed"


def test_invalid_promotion_is_quarantined_without_dropping_product() -> None:
    payload = b"""{"results":[{
      "code":"pasta","name":"Pasta","priceValue":20,"priceUnit":"kr/st",
      "productLine2":"500g","productBasketType":{"code":"ST"},
      "potentialPromotions":[{
        "code":"broken-multibuy","qualifyingCount":"many",
        "promotionType":"MixMatchPricePromotion"
      }]
    }],"pagination":{"currentPage":0,"numberOfPages":1}}"""
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

    result = WillysParser().parse_catalog(raw, ["raw:catalog"], _store())

    assert [product.external_product_id for product in result.products] == ["pasta"]
    assert result.products[0].offers == ()
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "invalid_promotion"
    assert "potentialPromotions[0]" in result.failures[0].raw_record_reference


def test_store_parser_filters_without_hardcoded_ids() -> None:
    payload = b"""[
      {"storeId":"2354","name":"Willys Lund Nova","onlineStore":true,
       "address":{"town":"Lund","line1":"Foretagsvagen","postalCode":"22761"}},
      {"storeId":"2114","name":"Willys Malmo Katrinelund","onlineStore":true,
       "address":{"town":"Malmo"}},
      {"storeId":"2339","name":"Willys Vasteras Erikslund","onlineStore":true,
       "address":{"town":"Vasteras"}},
      {"storeId":"9999","name":"Willys Uppsala","onlineStore":true,
       "address":{"town":"Uppsala"}}
    ]"""
    raw = RawBatch(
        chain=Chain.WILLYS,
        documents=(
            RawFetch(
                chain=Chain.WILLYS,
                kind="stores",
                method="GET",
                url="https://public.example/stores",
                http_status=200,
                payload=payload,
                connector_version="willys-v1",
            ),
        ),
    )
    stores = WillysParser().parse_stores(raw, ["raw:stores"], GeographicArea(city="Lund"))
    assert [store.external_id for store in stores] == ["2354"]
    assert stores[0].price_context_type is PriceContextType.ONLINE_STORE
    assert stores[0].physical_store_external_id == "2354"


def test_store_parser_uses_whole_city_word_when_town_is_missing() -> None:
    payload = b"""[
      {"storeId":"fallback","name":"Willys Lund Centrum","onlineStore":true},
      {"storeId":"false-positive","name":"Willys Erikslund","onlineStore":true}
    ]"""
    raw = RawBatch(
        chain=Chain.WILLYS,
        documents=(
            RawFetch(
                chain=Chain.WILLYS,
                kind="stores",
                method="GET",
                url="https://public.example/stores",
                http_status=200,
                payload=payload,
                connector_version="willys-v1",
            ),
        ),
    )

    stores = WillysParser().parse_stores(raw, ["raw:stores"], GeographicArea(city="Lund"))

    assert [store.external_id for store in stores] == ["fallback"]


def test_store_parser_does_not_claim_full_catalog_for_offline_store() -> None:
    payload = b"""[
      {"storeId":"2354","name":"Willys Lund Nova","onlineStore":"false",
       "address":{"town":"Lund"}}
    ]"""
    raw = RawBatch(
        chain=Chain.WILLYS,
        documents=(
            RawFetch(
                chain=Chain.WILLYS,
                kind="stores",
                method="GET",
                url="https://public.example/stores",
                http_status=200,
                payload=payload,
                connector_version="willys-v1",
            ),
        ),
    )

    stores = WillysParser().parse_stores(raw, ["raw:stores"], GeographicArea(city="Lund"))

    assert stores[0].online_shopping is False
    assert stores[0].coverage is CoverageLevel.PARTIAL_CATALOG
    assert stores[0].price_context_type is None
    assert stores[0].physical_store_external_id == "2354"


@pytest.mark.parametrize(
    ("text", "quantity", "unit", "estimated"),
    [
        ("2x500g", 1000, "g", False),
        ("1st ca 1,2kg", 1200, "g", True),
        ("6-pack", 6, "st", False),
        ("GARANT, 10p", 10, "st", False),
    ],
)
def test_package_text_formats(
    text: str,
    quantity: int,
    unit: str,
    estimated: bool,
) -> None:
    assert parse_package_text(text) == (quantity, unit, estimated)
