import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.citygross import CityGrossConnector
from grocery_data.app.connectors.citygross.client import (
    CityGrossAccessChallenge,
    CityGrossAccessChallengeFetchError,
    CityGrossClient,
    CityGrossRateLimitFetchError,
    CityGrossRateLimitStop,
    CityGrossSourcePolicyError,
)
from grocery_data.app.connectors.citygross.models import (
    CityGrossSchemaError,
    validated_catalog_page,
)
from grocery_data.app.connectors.citygross.parser import CityGrossParser, parse_package_text
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.registry import ConnectorRegistry
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
    SourcePolicy,
    SourceStore,
    SourceTechnicalCapability,
)
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import ReplayService

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "citygross" / "fixtures"


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.CITY_GROSS,
        external_id="3211",
        name="Malmö Hyllie",
        city="Malmö",
        online_shopping=True,
        coverage=CoverageLevel.PARTIAL_CATALOG,
        raw_reference="raw:stores#siteId=169",
        source_fields={
            "site_id": "169",
            "store_number": "3211",
            "price_context_verified": True,
        },
    )


def _catalog_raw(fixture: str = "catalog_samples.json") -> RawBatch:
    payload = (FIXTURES / fixture).read_bytes()
    parsed = json.loads(payload)
    return RawBatch(
        chain=Chain.CITY_GROSS,
        documents=(
            RawFetch(
                chain=Chain.CITY_GROSS,
                store_external_id="3211",
                kind="catalog_page",
                method="GET",
                url="https://www.citygross.se/api/v1/Loop54/products",
                query={
                    "store": "3211",
                    "skip": "0",
                    "take": str(parsed["pageSize"]),
                },
                http_status=200,
                content_type="application/json; charset=utf-8",
                payload=payload,
                connector_version="citygross-v1",
                page_number=0,
            ),
        ),
    )


def _stores_raw() -> RawBatch:
    return RawBatch(
        chain=Chain.CITY_GROSS,
        documents=(
            RawFetch(
                chain=Chain.CITY_GROSS,
                kind="stores",
                method="GET",
                url="https://www.citygross.se/api/v1/PageData/stores",
                http_status=200,
                content_type="application/json",
                payload=(FIXTURES / "stores.json").read_bytes(),
                connector_version="citygross-v1",
            ),
            RawFetch(
                chain=Chain.CITY_GROSS,
                kind="store_number_map",
                method="GET",
                url="https://www.citygross.se/api/v1/sites",
                query={"siteTypeId": "3"},
                http_status=200,
                content_type="application/json",
                payload=(FIXTURES / "sites.json").read_bytes(),
                connector_version="citygross-v1",
            ),
        ),
    )


def _parsed_products() -> dict[str, object]:
    result = CityGrossParser().parse_catalog(
        _catalog_raw(),
        ["raw:citygross-samples"],
        _store(),
    )
    assert result.failures == []
    return {product.external_product_id or "": product for product in result.products}


def _page(ids: list[str], *, total: int, page: int, size: int = 2, store: str = "3211"):
    return {
        "items": [{"id": product_id, "productStoreDetails": {"id": store}} for product_id in ids],
        "facets": [],
        "totalCount": total,
        "pageSize": size,
        "currentPage": page,
        "totalPages": (total + size - 1) // size if total else 0,
    }


def test_store_discovery_joins_public_page_and_site_sources() -> None:
    raw = _stores_raw()
    stores = CityGrossParser().parse_stores(
        raw,
        ["raw:stores", "raw:sites"],
        GeographicArea(city="Malmö"),
    )

    assert [(store.name, store.external_id) for store in stores] == [
        ("Malmö Hyllie", "3211"),
        ("Malmö Stora Bernstorp", "3203"),
    ]
    hyllie = stores[0]
    assert hyllie.address == "Hyllie Allé 3 C"
    assert hyllie.postal_code == "21534"
    assert hyllie.coverage is CoverageLevel.PARTIAL_CATALOG
    assert hyllie.price_context_type is PriceContextType.ONLINE_STORE
    assert hyllie.physical_store_external_id == "169"
    assert hyllie.source_fields["site_id"] == "169"
    assert hyllie.source_fields["price_context_type"] == "online_store"
    assert hyllie.source_fields["fulfillment_type"] is None
    assert hyllie.source_fields["provider"] is None
    bernstorp = stores[1]
    assert bernstorp.online_shopping is True
    assert bernstorp.source_fields["price_context_verified"] is True

    lund = CityGrossParser().parse_stores(
        raw,
        ["raw:stores", "raw:sites"],
        GeographicArea(city="Lund"),
    )
    assert lund == []


def test_unverified_site_mapping_is_discovery_only() -> None:
    sites = json.loads((FIXTURES / "sites.json").read_bytes())
    sites["sites"][1]["storeNumber"] = "3999"
    raw = RawBatch(
        chain=Chain.CITY_GROSS,
        documents=(
            RawFetch(
                chain=Chain.CITY_GROSS,
                kind="stores",
                method="GET",
                url="https://www.citygross.se/api/v1/PageData/stores",
                http_status=200,
                content_type="application/json",
                payload=(FIXTURES / "stores.json").read_bytes(),
                connector_version="citygross-v1",
            ),
            RawFetch(
                chain=Chain.CITY_GROSS,
                kind="store_number_map",
                method="GET",
                url="https://www.citygross.se/api/v1/sites",
                query={"siteTypeId": "3"},
                http_status=200,
                content_type="application/json",
                payload=json.dumps(sites).encode(),
                connector_version="citygross-v1",
            ),
        ),
    )

    stores = CityGrossParser().parse_stores(
        raw,
        ["raw:stores", "raw:sites"],
        GeographicArea(city="Malmö"),
    )
    unknown = next(store for store in stores if store.external_id == "3999")
    assert unknown.online_shopping is None
    assert unknown.source_fields["price_context_verified"] is False
    assert unknown.source_fields["fulfillment_type"] is None
    assert CityGrossConnector(client=object()).catalog_eligible(unknown) is False  # type: ignore[arg-type]


def test_real_sanitized_samples_map_identity_price_and_category() -> None:
    products = _parsed_products()
    pear = products["100001971_ST"]
    assert pear.gtin is None
    assert pear.source_fields["raw_gtin"] == "24000124962"
    assert pear.source_fields["raw_gtin_valid"] is False
    farfalle = products["101548710_ST"]
    assert farfalle.gtin == "7311043008377"
    assert farfalle.sale_price == Decimal("14.1")
    assert farfalle.regular_price == Decimal("14.1")
    assert farfalle.comparison_price == Decimal("28.2")
    assert farfalle.comparison_unit == "kg"
    assert products["101187348_ST"].category_path == (
        "Mejeri, ost & ägg",
        "Ägg",
        "ÄGG/ÄGGMIX, ÄGG FRIGÅENDE INNE",
    )
    assert all(product.availability is None for product in products.values())


@pytest.mark.parametrize(
    ("product_id", "sale_model", "quantity", "unit", "confidence"),
    [
        ("101548710_ST", SaleModel.FIXED_PACKAGE, 500, "g", Confidence.EXACT),
        ("101233933_ST", SaleModel.FIXED_PACKAGE, 1500, "ml", Confidence.EXACT),
        ("101187348_ST", SaleModel.FIXED_PACKAGE, 24, "st", Confidence.EXACT),
        ("100688141_KG", SaleModel.SOLD_BY_WEIGHT, None, None, Confidence.DERIVED),
    ],
)
def test_quantity_semantics_use_only_source_evidence(
    product_id: str,
    sale_model: SaleModel,
    quantity: int | None,
    unit: str | None,
    confidence: Confidence,
) -> None:
    source = _parsed_products()[product_id]
    normalized = ProductNormalizer().normalize(source, parser_version="citygross-parser-v1")
    assert normalized.sale_model is sale_model
    assert normalized.package_quantity == quantity
    assert normalized.package_unit == unit
    assert normalized.quantity_confidence is confidence


def test_explicit_piece_and_reversed_multipack_package_labels_are_exact() -> None:
    assert parse_package_text("ST") == (Decimal(1), "st", None, False, False)
    assert parse_package_text("500GX2") == (Decimal(1000), "g", None, False, False)
    assert parse_package_text("125MLX4") == (Decimal(500), "ml", None, False, False)


def test_slash_package_is_accepted_only_with_independent_price_proof() -> None:
    pear = _parsed_products()["100001971_ST"]
    assert pear.package_quantity == Decimal(415)
    assert pear.drained_quantity == Decimal(230)
    assert pear.source_fields["package_slash_validated_by_comparison_price"] is True
    # The contradictory generic source values never override descriptiveSize.
    assert pear.source_fields["netContent"] == {"unitOfMeasure": 0, "value": 1000}
    normalized = ProductNormalizer().normalize(pear, parser_version="citygross-parser-v1")
    assert normalized.sale_model is SaleModel.FIXED_PACKAGE
    assert normalized.usable_quantity == Decimal(230)
    assert normalized.quantity_confidence is Confidence.DERIVED


def test_mixed_kg_g_slash_uses_price_proof_for_real_drained_weight_samples() -> None:
    raw = _catalog_raw("catalog_mixed_unit_drained.json")
    result = CityGrossParser().parse_catalog(
        raw,
        ["raw:citygross-mixed-unit-drained"],
        _store(),
    )

    assert result.failures == []
    by_id = {product.external_product_id: product for product in result.products}
    expected = {
        "101186737_ST": (Decimal(1600), Decimal(880)),
        "101271033_ST": (Decimal(1500), Decimal(800)),
        "101402226_ST": (Decimal(1500), Decimal(800)),
    }
    for product_id, (gross, drained) in expected.items():
        product = by_id[product_id]
        assert product.package_quantity == gross
        assert product.package_unit == "g"
        assert product.drained_quantity == drained
        assert product.source_fields["package_slash_validated_by_comparison_price"] is True
        assert product.source_fields["package_slash_mixed_kg_g"] is True
        normalized = ProductNormalizer().normalize(
            product,
            parser_version="citygross-parser-v1",
        )
        assert normalized.sale_model is SaleModel.FIXED_PACKAGE
        assert normalized.usable_quantity == drained
        assert normalized.quantity_confidence is Confidence.DERIVED


def test_promotions_preserve_public_member_and_multibuy_conditions() -> None:
    products = _parsed_products()
    farfalle = products["101548710_ST"]
    multi = farfalle.offers[0]
    assert multi.type is PromotionType.MULTIBUY
    assert multi.quantity == 4
    assert multi.price == Decimal(50)
    assert farfalle.sale_price == Decimal("14.1")

    public_sale = products["101805404_KG"]
    assert public_sale.sale_price == Decimal("79.95")
    assert public_sale.regular_price == Decimal("99.95")
    assert public_sale.offers[0].type is PromotionType.SALE_PRICE
    assert public_sale.offers[0].max_quantity == 3
    assert public_sale.offers[0].source_payload["active"] is True
    json.dumps(public_sale.offers[0].source_payload)

    member = products["101241333_KG"]
    assert member.sale_price == Decimal("99.95")
    assert member.member_price == Decimal("89.95")
    assert member.offers[0].type is PromotionType.MEMBER_PRICE
    assert member.offers[0].member_only is True

    member_multi = products["101295643_ST"].offers[0]
    assert member_multi.type is PromotionType.MULTIBUY
    assert member_multi.quantity == 4
    assert member_multi.price == Decimal(99)
    assert member_multi.member_only is True
    assert member_multi.max_quantity == 1
    # max_quantity is one discounted 4-item group, not one package.
    assert member_multi.source_payload["maxAppliedPerReceipt"] == 1


def test_only_explicit_active_promotion_can_override_current_price() -> None:
    payload = json.loads((FIXTURES / "catalog_samples.json").read_bytes())
    farfalle = next(item for item in payload["items"] if item["id"] == "101548710_ST")
    prices = farfalle["productStoreDetails"]["prices"]
    assert prices["promotions"] and prices["activePromotion"] is None
    result = CityGrossParser().parse_catalog(
        _catalog_raw(),
        ["raw:citygross-samples"],
        _store(),
    )
    parsed = next(
        product for product in result.products if product.external_product_id == "101548710_ST"
    )

    assert parsed.sale_price == Decimal("14.1")
    assert parsed.offers[0].price == Decimal(50)
    assert parsed.offers[0].source_payload["active"] is False


def test_unknown_promotion_shape_is_other_even_with_multiple_items() -> None:
    payload = json.loads((FIXTURES / "catalog_samples.json").read_bytes())
    payload["items"] = [payload["items"][0]]
    payload["totalCount"] = 1
    payload["pageSize"] = 1
    prices = payload["items"][0]["productStoreDetails"]["prices"]
    prices["promotions"] = [
        {
            "id": "unknown-shape",
            "type": "99",
            "effectType": "UnknownEffect",
            "membersOnly": False,
            "minQuantity": 3,
            "value": 20,
            "priceDetails": {"price": 10, "unit": "PCE"},
        },
        {
            "id": "fractional-quantity",
            "type": "1",
            "effectType": "ItemsTotal",
            "membersOnly": False,
            "minQuantity": 2.5,
            "value": 20,
            "priceDetails": {"price": 10, "unit": "PCE"},
        },
    ]
    prices["activePromotion"] = prices["promotions"][0]
    raw = RawBatch(
        chain=Chain.CITY_GROSS,
        documents=(
            RawFetch(
                chain=Chain.CITY_GROSS,
                store_external_id="3211",
                kind="catalog_page",
                method="GET",
                url="https://www.citygross.se/api/v1/Loop54/products",
                query={"store": "3211", "skip": "0", "take": "1"},
                http_status=200,
                content_type="application/json",
                payload=json.dumps(payload).encode(),
                connector_version="citygross-v1",
                page_number=0,
            ),
        ),
    )

    result = CityGrossParser().parse_catalog(raw, ["raw:unknown"], _store())
    assert result.failures == []
    assert result.products[0].offers[0].type is PromotionType.OTHER
    assert result.products[0].offers[0].quantity == 3
    assert result.products[0].offers[1].type is PromotionType.OTHER
    assert result.products[0].offers[1].quantity is None
    assert result.products[0].sale_price == Decimal("31.5")


def test_opaque_compact_package_marker_remains_unknown() -> None:
    product = _parsed_products()["101805404_KG"]
    assert product.package_text == "C900G"
    assert product.package_quantity is None
    assert product.package_unit is None
    assert product.source_fields["package_approximate"] is False


def test_comparison_price_never_manufactures_package_quantity() -> None:
    weight = _parsed_products()["100688141_KG"]
    normalized = ProductNormalizer().normalize(weight, parser_version="test")
    assert normalized.comparison_price == Decimal(195)
    assert normalized.comparison_unit == "kg"
    assert normalized.package_quantity is None


def test_schema_break_is_quarantined_during_offline_replay() -> None:
    result = CityGrossParser().parse_catalog(
        _catalog_raw("schema_changed.json"),
        ["raw:schema-changed"],
        _store(),
    )
    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == "invalid_price"


def test_replay_is_deterministic_and_requires_no_transport() -> None:
    raw = _catalog_raw()
    parser = CityGrossParser()
    first = parser.parse_catalog(raw, ["raw:saved"], _store())
    second = parser.parse_catalog(raw, ["raw:saved"], _store())
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert len(first.products) == 8


def test_filesystem_raw_replay_makes_zero_transport_calls(tmp_path: Path) -> None:
    class NoNetworkClient:
        async def fetch_stores(self):
            raise AssertionError("replay must not discover stores")

        async def fetch_catalog(self, store):
            del store
            raise AssertionError("replay must not fetch catalog pages")

        async def aclose(self):
            return None

    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    records = raw_store.save_batch(_catalog_raw(), snapshot_id="citygross-offline")
    connector = CityGrossConnector(client=NoNetworkClient())  # type: ignore[arg-type]

    replay = ReplayService(raw_store).replay_catalog(connector, records, _store())

    assert replay.network_requests == 0
    assert len(replay.parsed.products) == 8
    assert len(replay.normalized) == 8
    assert all(product.raw_reference.startswith("raw:") for product in replay.normalized)


@pytest.mark.parametrize(
    "payload,skip,take,store",
    [
        ({"items": []}, 0, 2, "3211"),
        (_page(["p1"], total=2, page=0), 0, 2, "3211"),
        (_page(["p1", "p2"], total=2, page=0, store="other"), 0, 2, "3211"),
        (_page(["p1", "p2"], total=2, page=0), 2, 2, "3211"),
    ],
    ids=("missing-pagination", "short-nonterminal", "context-mismatch", "offset-mismatch"),
)
def test_catalog_page_validation_fails_closed(payload, skip, take, store) -> None:
    with pytest.raises(CityGrossSchemaError):
        validated_catalog_page(
            payload,
            requested_skip=skip,
            requested_take=take,
            expected_store_id=store,
        )


@pytest.mark.asyncio
async def test_explicit_full_transport_reconciles_every_exact_count() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        skip = int(request.url.params["skip"])
        return httpx.Response(
            200,
            json=(
                _page(["p1", "p2"], total=3, page=0)
                if skip == 0
                else _page(["p3"], total=3, page=1)
            ),
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        max_pages=None,
        allow_full_crawl=True,
        allowed_store_ids={"3211"},
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    assert len(requests) == 2
    assert batch.transport.request_count == 2
    completion = batch.catalog_completion
    assert completion is not None and completion.is_full_traversal
    assert completion.expected_products == 3
    assert completion.raw_rows == 3
    assert completion.unique_products == 3
    assert completion.duplicate_products == 0
    assert completion.expected_pages == 2


@pytest.mark.asyncio
async def test_default_hold_budget_returns_partial_exact_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page(["p1", "p2"], total=3, page=0))

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.limited is True
    assert completion.expected_products == 3
    assert completion.raw_rows == 2
    assert completion.unique_products == 2
    assert completion.expected_pages == 2


@pytest.mark.asyncio
async def test_empty_catalog_cannot_be_promoted_as_complete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_page([], total=0, page=0))

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        max_pages=None,
        allow_full_crawl=True,
        allowed_store_ids={"3211"},
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = caught.value.partial_batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.expected_products == 0
    assert completion.raw_rows == 0
    assert completion.unique_products == 0
    assert completion.expected_pages == 0


@pytest.mark.asyncio
async def test_http_failure_preserves_raw_pages_and_exact_partial_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["skip"] == "0":
            return httpx.Response(200, json=_page(["p1", "p2"], total=3, page=0))
        return httpx.Response(503, json={"error": "temporary"})

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        max_pages=None,
        allow_full_crawl=True,
        allowed_store_ids={"3211"},
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    partial = caught.value.partial_batch
    assert [document.http_status for document in partial.documents] == [200, 503]
    assert partial.documents[1].json_payload() == {"error": "temporary"}
    completion = partial.catalog_completion
    assert completion is not None and completion.complete is False
    assert completion.expected_products == 3
    assert completion.raw_rows == 2
    assert completion.unique_products == 2
    assert completion.expected_pages == 2
    assert partial.transport.http_error_count == 1


@pytest.mark.asyncio
async def test_duplicate_product_aborts_with_replayable_partial_batch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["skip"] == "0":
            return httpx.Response(200, json=_page(["p1", "p2"], total=3, page=0))
        return httpx.Response(200, json=_page(["p2"], total=3, page=1))

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        max_pages=None,
        allow_full_crawl=True,
        allowed_store_ids={"3211"},
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = caught.value.partial_batch.catalog_completion
    assert completion is not None
    assert completion.raw_rows == 3
    assert completion.unique_products == 2
    assert completion.duplicate_products == 1


@pytest.mark.asyncio
async def test_store_transport_captures_both_public_raw_sources() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/PageData/stores"):
            return httpx.Response(
                200,
                content=(FIXTURES / "stores.json").read_bytes(),
                headers={"Content-Type": "application/json"},
            )
        if request.url.path.endswith("/sites"):
            assert request.url.params["siteTypeId"] == "3"
            return httpx.Response(
                200,
                content=(FIXTURES / "sites.json").read_bytes(),
                headers={"Content-Type": "application/json"},
            )
        raise AssertionError(request.url)

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        batch = await client.fetch_stores()
    finally:
        await http_client.aclose()

    assert [document.kind for document in batch.documents] == [
        "stores",
        "store_number_map",
    ]
    assert batch.transport.request_count == 2
    serialized = json.dumps(batch.model_dump(mode="json"))
    assert "cookie" not in serialized.casefold()
    assert "authorization" not in serialized.casefold()


def test_source_policy_model_is_separate_from_operational_coverage() -> None:
    assert {policy.value for policy in SourcePolicy} == {"allow", "review", "block"}
    connector = CityGrossConnector(client=object())  # type: ignore[arg-type]
    assert connector.source_policy is SourcePolicy.REVIEW
    assert connector.technical_capability is SourceTechnicalCapability.LIKELY_FULL_ONLINE_CATALOG
    assert connector.coverage is CoverageLevel.PARTIAL_CATALOG


def test_review_defaults_are_conservative(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "CITYGROSS_ALLOW_FULL_CRAWL",
        "CITYGROSS_REQUESTS_PER_SECOND",
        "CITYGROSS_MAX_CONCURRENCY",
        "CITYGROSS_STORE_EXTERNAL_IDS",
    ):
        monkeypatch.delenv(name, raising=False)

    client = CityGrossClient(client=object())  # type: ignore[arg-type]

    assert client.allow_full_crawl is False
    assert client.max_pages == 1
    assert client.requests_per_second == 1
    assert client.max_concurrency == 1
    assert client.allowed_store_ids == frozenset()


def test_full_crawl_requires_opt_in_bounded_page_and_store_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CITYGROSS_ALLOW_FULL_CRAWL", raising=False)
    monkeypatch.delenv("CITYGROSS_STORE_EXTERNAL_IDS", raising=False)
    with pytest.raises(CityGrossSourcePolicyError, match="one-page canary"):
        CityGrossClient(max_pages=None, client=object())  # type: ignore[arg-type]
    with pytest.raises(CityGrossSourcePolicyError, match="at most 100"):
        CityGrossClient(page_size=101, client=object())  # type: ignore[arg-type]

    monkeypatch.setenv("CITYGROSS_ALLOW_FULL_CRAWL", "true")
    with pytest.raises(CityGrossSourcePolicyError, match="non-empty"):
        CityGrossClient(max_pages=None, client=object())  # type: ignore[arg-type]

    monkeypatch.setenv("CITYGROSS_STORE_EXTERNAL_IDS", "3211")
    client = CityGrossClient(
        max_pages=None,
        client=object(),  # type: ignore[arg-type]
    )
    assert client.allow_full_crawl is True
    assert client.allowed_store_ids == frozenset({"3211"})


def test_full_connector_upgrades_only_the_explicit_verified_online_context() -> None:
    client = CityGrossClient(
        page_size=100,
        max_pages=None,
        allow_full_crawl=True,
        allowed_store_ids={"3211"},
        client=object(),  # type: ignore[arg-type]
    )
    connector = CityGrossConnector.for_full_collection(client=client)

    stores = connector.parse_stores(
        _stores_raw(),
        ["raw:stores", "raw:sites"],
        GeographicArea(city="Malmö"),
    )

    assert connector.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert connector.minimum_full_catalog_products == 10_000
    assert [store.external_id for store in stores if connector.catalog_eligible(store)] == ["3211"]
    hyllie = next(store for store in stores if store.external_id == "3211")
    bernstorp = next(store for store in stores if store.external_id == "3203")
    assert hyllie.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert bernstorp.coverage is CoverageLevel.PARTIAL_CATALOG


@pytest.mark.asyncio
async def test_full_replay_factory_has_no_live_crawl_authority() -> None:
    connector = CityGrossConnector.for_replay(store_external_ids=("3211",))
    try:
        assert connector.coverage is CoverageLevel.FULL_ONLINE_CATALOG
        assert connector.client.allow_full_crawl is False
        assert connector.client.max_pages == 1
        assert connector.client.allowed_store_ids == frozenset({"3211"})
    finally:
        await connector.aclose()


def test_ambiguous_full_crawl_environment_value_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CITYGROSS_ALLOW_FULL_CRAWL", "yes")
    with pytest.raises(CityGrossSourcePolicyError, match="ambiguous"):
        CityGrossClient(client=object())  # type: ignore[arg-type]


def test_retry_budget_is_bounded_to_three_attempts() -> None:
    with pytest.raises(ValueError, match="between 1 and 3"):
        CityGrossClient(
            retry_policy=RetryPolicy(attempts=4),
            client=object(),  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_store_allowlist_makes_only_hyllie_catalog_eligible() -> None:
    client = CityGrossClient(
        allowed_store_ids={"3211"},
        client=object(),  # type: ignore[arg-type]
    )
    connector = CityGrossConnector(client=client)
    stores = connector.parse_stores(
        _stores_raw(),
        ["raw:stores", "raw:sites"],
        GeographicArea(city="Malmö"),
    )

    assert [store.external_id for store in stores if connector.catalog_eligible(store)] == ["3211"]
    bernstorp = next(store for store in stores if store.external_id == "3203")
    with pytest.raises(CityGrossSourcePolicyError, match="outside"):
        await client.fetch_catalog(bernstorp)


@pytest.mark.parametrize(
    ("status", "payload", "content_type"),
    [
        (401, b'{"error":"unauthorized"}', "application/json"),
        (403, b'{"error":"forbidden"}', "application/json"),
        (405, b'{"error":"blocked"}', "application/json"),
        (503, b"<html>AWS WAF request blocked</html>", "text/html"),
        (200, b"<html>Human Verification</html>", "text/html"),
        (200, b'{"error":"CAPTCHA required"}', "application/json"),
        (200, b'{"error":"Verify you are human"}', "application/json"),
        (200, b'{"error":"Request could not be satisfied"}', "application/json"),
        (200, b'{"challenge":"aws-waf"}', "application/json"),
    ],
)
@pytest.mark.asyncio
async def test_access_challenge_stops_after_first_response_with_inert_diagnostic(
    status: int,
    payload: bytes,
    content_type: str,
) -> None:
    attempts = 0
    body_sentinel = b"citygross-response-body-secret"
    header_sentinel = "citygross-response-header-secret"
    session_sentinel = "citygross-session-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            status,
            content=payload + body_sentinel,
            headers={
                "Content-Type": f'{content_type}; trace="{header_sentinel}"',
                "Set-Cookie": f"session={session_sentinel}",
            },
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
        client=http_client,
    )
    try:
        with pytest.raises(CityGrossAccessChallengeFetchError, match="ACCESS_CHALLENGE") as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    assert attempts == 1
    assert isinstance(caught.value.__cause__, CityGrossAccessChallenge)
    assert len(caught.value.partial_batch.documents) == 1
    raw = caught.value.partial_batch.documents[0]
    assert raw.kind == "access_challenge"
    assert raw.http_status == status
    assert raw.content_type == "application/json; profile=transport-stop-diagnostic"
    assert raw.json_payload() == {
        "classification": "access_challenge",
        "http_status": status,
        "schema": "citygross-transport-stop-v1",
    }
    serialized = json.dumps(raw.model_dump(mode="json"))
    assert body_sentinel.decode() not in serialized
    assert header_sentinel not in serialized
    assert session_sentinel not in serialized


@pytest.mark.asyncio
async def test_rate_limit_stops_on_first_429_and_observes_retry_after() -> None:
    attempts = 0
    body_sentinel = "citygross-rate-limit-response-secret"
    header_sentinel = "citygross-rate-limit-header-secret"
    session_sentinel = "citygross-rate-limit-session-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            json={"error": "slow down", "request_id": body_sentinel},
            headers={
                "Content-Type": f'application/json; trace="{header_sentinel}"',
                "Retry-After": "4",
                "Set-Cookie": f"session={session_sentinel}",
            },
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=5),
        client=http_client,
    )
    try:
        with pytest.raises(CityGrossRateLimitFetchError, match="RATE_LIMITED") as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    assert attempts == 1
    assert isinstance(caught.value.__cause__, CityGrossRateLimitStop)
    assert caught.value.__cause__.retry_after == 4
    assert caught.value.__cause__.retry_after_raw == "4"
    partial = caught.value.partial_batch
    assert partial.transport.request_count == 1
    assert partial.transport.rate_limit_count == 1
    assert partial.documents[0].kind == "rate_limit"
    assert partial.documents[0].http_status == 429
    assert (
        partial.documents[0].content_type == "application/json; profile=transport-stop-diagnostic"
    )
    assert partial.documents[0].json_payload() == {
        "classification": "rate_limit",
        "http_status": 429,
        "schema": "citygross-transport-stop-v1",
    }
    serialized = json.dumps(partial.documents[0].model_dump(mode="json"))
    assert body_sentinel not in serialized
    assert header_sentinel not in serialized
    assert session_sentinel not in serialized


@pytest.mark.asyncio
async def test_transient_5xx_uses_bounded_retry_but_review_never_declares_full() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json=_page(["p1", "p2"], total=2, page=0))

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = CityGrossClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=2, base_delay_seconds=0, max_delay_seconds=0),
        page_size=2,
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    assert attempts == 2
    assert batch.transport.request_count == 2
    assert batch.transport.http_error_count == 1
    assert batch.catalog_completion is not None
    assert batch.catalog_completion.complete is False
    assert batch.catalog_completion.reason == "source policy REVIEW: full crawl not opted in"


def test_registry_factory_stays_bounded_after_full_online_activation() -> None:
    connector = CityGrossConnector(client=object())  # type: ignore[arg-type]
    assert connector.coverage is CoverageLevel.PARTIAL_CATALOG
    assert connector.catalog_eligible(_store()) is True
    registered = ConnectorRegistry().create(Chain.CITY_GROSS)
    assert isinstance(registered, CityGrossConnector)
    assert registered.coverage is CoverageLevel.PARTIAL_CATALOG
    assert registered.client.max_pages == 1
    assert registered.client.allow_full_crawl is False
