from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.lidl import (
    LidlAccessChallengeFetchError,
    LidlClient,
    LidlConnector,
    LidlParser,
    LidlRateLimitFetchError,
)
from grocery_data.app.connectors.lidl.models import (
    sanitized_store_detail,
    sanitized_store_index,
    validated_search_page,
)
from grocery_data.app.domain import (
    Chain,
    Confidence,
    CoverageLevel,
    GeographicArea,
    ParserErrorCode,
    PriceContextType,
    PromotionType,
    RawBatch,
    RawFetch,
    SaleModel,
    SourcePolicy,
    SourceStore,
)
from grocery_data.app.normalization import ProductNormalizer
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.replay import ReplayService

FIXTURES = Path(__file__).parents[1] / "app" / "connectors" / "lidl" / "fixtures"


def _offer_store() -> SourceStore:
    return SourceStore(
        chain=Chain.LIDL,
        external_id=LidlClient.public_offer_context_id,
        name="Lidl Sverige – publika erbjudanden (standardregion)",
        city="Sverige",
        coverage=CoverageLevel.OFFERS_ONLY,
        price_context_type=PriceContextType.REGIONAL,
        raw_reference="raw:store",
        source_fields={
            "price_region_id": "1",
            "store_price_verified": False,
        },
    )


def _offer_raw(name: str = "offer_samples.json") -> RawBatch:
    return RawBatch(
        chain=Chain.LIDL,
        documents=(
            RawFetch(
                chain=Chain.LIDL,
                store_external_id=LidlClient.public_offer_context_id,
                kind="offer_page",
                fetched_at=datetime(2026, 8, 20, 12, tzinfo=UTC),
                method="GET",
                url="https://www.lidl.se/q/api/search",
                query={"offset": "0"},
                http_status=200,
                content_type="application/mindshift.search+json;version=2",
                payload=(FIXTURES / name).read_bytes(),
                connector_version="lidl-v1",
                page_number=0,
            ),
        ),
    )


def _store_raw() -> RawBatch:
    return RawBatch(
        chain=Chain.LIDL,
        documents=(
            RawFetch(
                chain=Chain.LIDL,
                kind="store_index",
                method="GET",
                url="https://www.lidl.se/s/sv-SE/butiker/lund/",
                http_status=200,
                content_type="application/json; profile=sanitized-store_index",
                payload=(FIXTURES / "store_index.json").read_bytes(),
                connector_version="lidl-v1",
            ),
            RawFetch(
                chain=Chain.LIDL,
                kind="store_detail",
                method="GET",
                url=(
                    "https://www.lidl.se/s/sv-SE/butiker/lund/"
                    "akerlund-och-rausings-vaeg-1/"
                ),
                http_status=200,
                content_type="application/json; profile=sanitized-store_detail",
                payload=(FIXTURES / "store_detail.json").read_bytes(),
                connector_version="lidl-v1",
            ),
        ),
    )


def _national_context_probe_raw() -> RawBatch:
    return RawBatch(
        chain=Chain.LIDL,
        documents=(
            RawFetch(
                chain=Chain.LIDL,
                kind="offer_context_probe",
                method="GET",
                url="https://www.lidl.se/q/api/search",
                query={"fetchsize": "1", "offset": "0"},
                http_status=200,
                content_type="application/mindshift.search+json;version=2",
                payload=(FIXTURES / "offer_samples.json").read_bytes(),
                connector_version="lidl-v1",
                page_number=0,
            ),
        ),
    )


def _page(items: list[dict], *, total: int, offset: int) -> dict:
    return {
        "type": "search",
        "resultType": "search",
        "version": "v2.0.0",
        "numFound": total,
        "offset": offset,
        "fetchsize": 2,
        "maxfetchsize": 1000,
        "items": items,
    }


def test_store_html_is_reduced_to_closed_secret_free_evidence() -> None:
    city_html = b"""
        <script>window.runtime={"x-apikey":"must-not-survive"}</script>
        <a href="/s/sv-SE/butiker/lund/magistratsvaegen-6/">Butik</a>
        <a href="/s/sv-SE/butiker/lund/akerlund-och-rausings-vaeg-1/">Butik</a>
    """
    index = sanitized_store_index(
        city_html,
        source_url="https://www.lidl.se/s/sv-SE/butiker/lund/",
        city_slug="lund",
        requested_city="Lund",
    )
    assert b"must-not-survive" not in index
    assert b"x-apikey" not in index
    assert len(json.loads(index)["detail_urls"]) == 2

    detail_html = """
        <span class="main-info__headline-store">Åkerlund och Rausings väg 1, 227 30 Lund</span>
        <a href="https://bing.com/maps/default.aspx?rtp=~pos.55.69938_13.17783_Lund">Map</a>
        <a href="https://survey.example/?TNC=0303&token=must-not-survive">Survey</a>
    """.encode()
    detail = sanitized_store_detail(
        detail_html,
        source_url=(
            "https://www.lidl.se/s/sv-SE/butiker/lund/"
            "akerlund-och-rausings-vaeg-1/"
        ),
    )
    row = json.loads(detail)
    assert b"must-not-survive" not in detail
    assert b"token" not in detail
    assert row["external_id"] == "0303"
    assert row["postal_code"] == "22730"
    assert row["latitude"] == "55.69938"


def test_store_parser_keeps_physical_stores_separate_from_public_price_context() -> None:
    connector = LidlConnector(client=object())  # type: ignore[arg-type]
    stores = connector.parse_stores(
        _store_raw(),
        ["raw:index", "raw:detail"],
        GeographicArea(city="Lund"),
    )

    assert len(stores) == 2
    physical = next(store for store in stores if store.external_id == "0303")
    regional = next(
        store for store in stores if store.external_id == LidlClient.public_offer_context_id
    )
    assert physical.city == "Lund"
    assert physical.price_context_type == PriceContextType.PHYSICAL_STORE
    assert physical.source_fields["public_offer_price_assigned"] is False
    assert connector.catalog_eligible(physical) is False
    assert regional.city == "Sverige"
    assert regional.price_context_type == PriceContextType.REGIONAL
    assert regional.source_fields["store_price_verified"] is False
    assert connector.catalog_eligible(regional) is True


def test_national_context_probe_creates_only_one_truthful_operational_context() -> None:
    connector = LidlConnector(client=object())  # type: ignore[arg-type]
    stores = connector.parse_stores(
        _national_context_probe_raw(),
        ["raw:context-probe"],
        GeographicArea(city="Sverige"),
    )

    assert len(stores) == 1
    context = stores[0]
    assert context.external_id == LidlClient.public_offer_context_id
    assert context.name == "Lidl Sverige – publika erbjudanden (standardregion)"
    assert context.city == "Sverige"
    assert context.price_context_type == PriceContextType.REGIONAL
    assert context.source_fields["price_region_id"] == "1"
    assert context.source_fields["store_price_verified"] is False
    assert context.source_fields["requested_city"] == "Sverige"
    assert connector.catalog_eligible(context) is True


@pytest.mark.asyncio
async def test_national_store_discovery_uses_one_bounded_public_context_probe() -> None:
    payload = json.loads((FIXTURES / "offer_samples.json").read_bytes())
    payload["numFound"] = 421
    payload["fetchsize"] = 1
    payload["items"] = payload["items"][:1]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json=payload,
            headers={"content-type": "application/mindshift.search+json;version=2"},
        )

    http_client = httpx.AsyncClient(
        base_url="https://www.lidl.se",
        transport=httpx.MockTransport(handler),
    )
    client = LidlClient(
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        batch = await client.fetch_stores(GeographicArea(city="Sverige"))
    finally:
        await http_client.aclose()

    assert len(requests) == 1
    assert requests[0].url.path == "/q/api/search"
    assert requests[0].url.params["fetchsize"] == "1"
    assert requests[0].url.params["offset"] == "0"
    assert batch.transport.request_count == 1
    assert [document.kind for document in batch.documents] == ["offer_context_probe"]
    assert batch.documents[0].store_external_id is None
    stores = LidlParser().parse_stores(
        batch,
        ["raw:context-probe"],
        GeographicArea(city="Sverige"),
    )
    assert [store.external_id for store in stores] == [
        LidlClient.public_offer_context_id
    ]


def test_real_offer_fixture_preserves_price_quantity_and_promotion_semantics() -> None:
    result = LidlParser().parse_catalog(
        _offer_raw(),
        ["raw:offers"],
        _offer_store(),
    )

    assert result.failures == []
    assert len(result.products) == 5
    by_id = {product.external_product_id: product for product in result.products}

    fixed = by_id["11001450"]
    assert fixed.sale_price == Decimal("23.5")
    assert fixed.package_quantity == 250
    assert fixed.package_unit == "g"
    assert fixed.comparison_price == 94
    assert fixed.comparison_unit == "kg"
    assert fixed.gtin == "4056489167037"
    assert fixed.source_fields["gtin_evidence"] == "explicit_gridbox_meta_ean"
    assert fixed.offers[0].type == PromotionType.OTHER
    fixed_normalized = ProductNormalizer().normalize(
        fixed,
        parser_version=LidlParser.parser_version,
    )
    assert fixed_normalized.sale_model == SaleModel.FIXED_PACKAGE
    assert fixed_normalized.quantity_confidence == Confidence.EXACT

    weight = by_id["11029717"]
    assert weight.sale_price == Decimal("24.9")
    assert weight.regular_price is None
    assert weight.source_fields["deleted_price"] == "44.9"
    assert weight.sale_unit == "kg"
    assert weight.package_quantity is None
    assert weight.offers[0].type == PromotionType.PERCENT_DISCOUNT
    assert weight.offers[0].source_payload["percentage_discount"] == 44
    weight_normalized = ProductNormalizer().normalize(
        weight,
        parser_version=LidlParser.parser_version,
    )
    assert weight_normalized.sale_model == SaleModel.SOLD_BY_WEIGHT

    member = by_id["11001090"]
    assert member.sale_price is None
    assert member.regular_price is None
    assert member.member_price is None  # Future campaign remains conditional offer evidence.
    assert member.offers[0].price == Decimal("24.9")
    assert member.offers[0].type == PromotionType.MEMBER_PRICE
    assert member.offers[0].member_only is True
    assert member.offers[0].source_payload["member_offer_scope"] == "generic_member"
    assert member.offers[0].source_payload["shared_price_universe_eligible"] is True
    assert member.source_fields["public_lidl_plus"] is True
    assert member.source_fields["coupon_scope_unknown"] is False
    assert member.gtin is None

    multibuy = by_id["11006571"]
    assert multibuy.sale_price is None
    assert multibuy.regular_price is None
    assert multibuy.package_quantity == 1
    assert multibuy.package_unit == "l"
    assert multibuy.offers[0].type == PromotionType.MULTIBUY
    assert multibuy.offers[0].quantity == 2
    assert multibuy.offers[0].price == 27

    variable = by_id["11209994"]
    assert variable.sale_unit == "kg"
    assert variable.average_weight_kg == 1
    variable_normalized = ProductNormalizer().normalize(
        variable,
        parser_version=LidlParser.parser_version,
    )
    assert variable_normalized.sale_model == SaleModel.VARIABLE_WEIGHT_PACKAGE
    assert variable_normalized.quantity_confidence == Confidence.ESTIMATED


def test_lidl_plus_coupon_is_not_promoted_as_generic_member_price() -> None:
    payload = json.loads((FIXTURES / "offer_samples.json").read_bytes())
    member = payload["items"][2]["gridbox"]["data"]
    member["regionsPrices"]["1"]["currentLidlPlusPrice"]["price"]["discount"][
        "discountText"
    ] = "Kupong -22%"
    document = _offer_raw().documents[0].model_copy(
        update={"payload": json.dumps(payload, ensure_ascii=False).encode("utf-8")}
    )

    result = LidlParser().parse_catalog(
        _offer_raw().model_copy(update={"documents": (document,)}),
        ["raw:lidl-plus-coupon"],
        _offer_store(),
    )

    assert result.failures == []
    product = next(row for row in result.products if row.external_product_id == "11001090")
    assert product.offers[0].member_only is True
    assert product.offers[0].source_payload["member_offer_scope"] == "unknown"
    assert product.offers[0].source_payload["shared_price_universe_eligible"] is False
    assert product.source_fields["public_lidl_plus"] is False
    assert product.source_fields["personalized_coupon"] is False
    assert product.source_fields["coupon_scope_unknown"] is True


def test_gtin_requires_explicit_meta_ean_and_valid_checksum() -> None:
    payload = json.loads((FIXTURES / "offer_samples.json").read_bytes())
    # A checksum-invalid explicit EAN remains visible as raw lineage but is
    # never promoted to GTIN.
    payload["items"][1]["gridbox"]["meta"] = {"ean": "4056489167038"}
    # Lidl internal IDs are numeric, but a missing meta.ean must stay missing.
    payload["items"][2]["gridbox"].pop("meta", None)
    document = _offer_raw().documents[0].model_copy(
        update={"payload": json.dumps(payload, ensure_ascii=False).encode("utf-8")}
    )
    result = LidlParser().parse_catalog(
        _offer_raw().model_copy(update={"documents": (document,)}),
        ["raw:gtin-evidence"],
        _offer_store(),
    )

    assert result.failures == []
    by_id = {product.external_product_id: product for product in result.products}
    assert by_id["11001450"].gtin == "4056489167037"
    invalid = by_id["11029717"]
    assert invalid.gtin is None
    assert invalid.source_fields["raw_gtin"] == "4056489167038"
    assert invalid.source_fields["raw_gtin_valid"] is False
    missing = by_id["11001090"]
    assert missing.gtin is None
    assert missing.source_fields["raw_gtin"] is None
    assert missing.source_fields["raw_gtin_valid"] is False
    assert missing.external_product_id == "11001090"


def test_schema_break_is_quarantined_and_never_persisted_as_product_data() -> None:
    result = LidlParser().parse_catalog(
        _offer_raw("schema_changed.json"),
        ["raw:changed"],
        _offer_store(),
    )
    assert result.products == []
    assert len(result.failures) == 1
    assert result.failures[0].error_code == ParserErrorCode.SCHEMA_CHANGED


def test_search_page_validation_rejects_offset_or_identity_drift() -> None:
    payload = json.loads((FIXTURES / "offer_samples.json").read_bytes())
    with pytest.raises(ValueError, match="requested offset"):
        validated_search_page(payload, requested_offset=5)
    payload["items"][0]["gridbox"]["data"].pop("productId")
    with pytest.raises(ValueError, match="productId"):
        validated_search_page(payload)


@pytest.mark.asyncio
async def test_public_offer_pagination_reconciles_exact_declared_set() -> None:
    rows = json.loads((FIXTURES / "offer_samples.json").read_bytes())["items"][:3]
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        offset = int(request.url.params["offset"])
        body = _page(rows[:2], total=3, offset=0) if offset == 0 else _page(rows[2:], total=3, offset=2)
        return httpx.Response(
            200,
            json=body,
            headers={"content-type": "application/mindshift.search+json;version=2"},
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = LidlClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_offer_store())
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
    # Exact traversal of the published set does not upgrade catalog coverage.
    assert LidlConnector(client=client).coverage == CoverageLevel.OFFERS_ONLY


@pytest.mark.asyncio
async def test_bounded_canary_returns_truthful_partial_offer_evidence() -> None:
    rows = json.loads((FIXTURES / "offer_samples.json").read_bytes())["items"][:2]
    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=_page(rows, total=5, offset=0),
                headers={"content-type": "application/mindshift.search+json;version=2"},
            )
        ),
    )
    client = LidlClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        max_pages=1,
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_offer_store())
    finally:
        await http_client.aclose()
    completion = batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.limited is True
    assert completion.expected_products == 5
    assert completion.unique_products == 2
    assert completion.expected_pages == 3


@pytest.mark.asyncio
async def test_pagination_fails_closed_if_effective_fetchsize_changes() -> None:
    rows = json.loads((FIXTURES / "offer_samples.json").read_bytes())["items"][:3]

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        body = _page(rows[:2], total=3, offset=0)
        if offset == 2:
            body = _page(rows[2:], total=3, offset=2)
            body["fetchsize"] = 3
        return httpx.Response(
            200,
            json=body,
            headers={"content-type": "application/mindshift.search+json;version=2"},
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = LidlClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        page_size=2,
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_offer_store())
    finally:
        await http_client.aclose()
    completion = caught.value.partial_batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.pages_fetched == 2
    assert completion.expected_pages == 2


@pytest.mark.asyncio
async def test_store_transport_discovers_lund_without_persisting_page_runtime() -> None:
    city_html = b"""
        <script>window.runtime={"x-apikey":"must-not-survive"}</script>
        <a href="/s/sv-SE/butiker/lund/magistratsvaegen-6/">One</a>
        <a href="/s/sv-SE/butiker/lund/akerlund-och-rausings-vaeg-1/">Two</a>
    """

    def detail(address: str, postal: str, tnc: str, lat: str) -> bytes:
        return f"""
            <span class="main-info__headline-store">{address}, {postal} Lund</span>
            <a href="https://bing.com/maps/default.aspx?rtp=~pos.{lat}_13.17783_Lund">Map</a>
            <a href="https://survey.example/?TNC={tnc}&token=must-not-survive">Survey</a>
        """.encode()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/butiker/lund/"):
            return httpx.Response(200, content=city_html, headers={"content-type": "text/html"})
        if "magistratsvaegen" in path:
            return httpx.Response(
                200,
                content=detail("Magistratsvägen 6", "226 43", "0302", "55.72000"),
                headers={"content-type": "text/html"},
            )
        return httpx.Response(
            200,
            content=detail("Åkerlund och Rausings väg 1", "227 30", "0303", "55.69938"),
            headers={"content-type": "text/html"},
        )

    http_client = httpx.AsyncClient(
        base_url="https://www.lidl.se",
        transport=httpx.MockTransport(handler),
    )
    client = LidlClient(
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        batch = await client.fetch_stores(GeographicArea(city="Lund"))
    finally:
        await http_client.aclose()
    assert batch.transport.request_count == 3
    serialized = json.dumps(batch.model_dump(mode="json"))
    assert "must-not-survive" not in serialized
    assert "x-apikey" not in serialized
    stores = LidlParser().parse_stores(
        batch,
        ["raw:index", "raw:one", "raw:two"],
        GeographicArea(city="Lund"),
    )
    assert {store.external_id for store in stores} == {
        "0302",
        "0303",
        LidlClient.public_offer_context_id,
    }


@pytest.mark.parametrize(
    ("status", "payload", "content_type", "error"),
    [
        (403, b'{"error":"forbidden"}', "application/json", LidlAccessChallengeFetchError),
        (200, b"<html>Human Verification</html>", "text/html", LidlAccessChallengeFetchError),
        (429, b'{"error":"slow down"}', "application/json", LidlRateLimitFetchError),
    ],
)
@pytest.mark.asyncio
async def test_access_controls_and_rate_limit_stop_after_first_response(
    status: int,
    payload: bytes,
    content_type: str,
    error: type[Exception],
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, content=payload, headers={"content-type": content_type})

    http_client = httpx.AsyncClient(
        base_url="https://www.lidl.se",
        transport=httpx.MockTransport(handler),
    )
    client = LidlClient(
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
        client=http_client,
    )
    try:
        with pytest.raises(error) as caught:
            await client.fetch_stores(GeographicArea(city="Lund"))
    finally:
        await http_client.aclose()
    assert attempts == 1
    partial = caught.value.partial_batch  # type: ignore[attr-defined]
    assert len(partial.documents) == 1
    assert partial.transport.request_count == 1
    assert payload not in partial.documents[0].payload
    diagnostic = partial.documents[0].json_payload()
    assert diagnostic["http_status"] == status
    if status == 429:
        assert diagnostic["classification"] == "rate_limit"


@pytest.mark.asyncio
async def test_rate_limit_diagnostic_allowlists_numeric_retry_after_only() -> None:
    secret_body = b'{"session":"must-not-survive"}'
    http_client = httpx.AsyncClient(
        base_url="https://www.lidl.se",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                429,
                content=secret_body,
                headers={
                    "content-type": "application/json",
                    "retry-after": "17",
                    "set-cookie": "clearance=must-not-survive",
                },
            )
        ),
    )
    client = LidlClient(
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
        client=http_client,
    )
    try:
        with pytest.raises(LidlRateLimitFetchError) as caught:
            await client.fetch_stores(GeographicArea(city="Sverige"))
    finally:
        await http_client.aclose()

    partial = caught.value.partial_batch
    assert partial.transport.request_count == 1
    assert len(partial.documents) == 1
    diagnostic_payload = partial.documents[0].payload
    assert secret_body not in diagnostic_payload
    assert b"must-not-survive" not in diagnostic_payload
    assert partial.documents[0].json_payload() == {
        "schema": "lidl-transport-stop-v1",
        "classification": "rate_limit",
        "http_status": 429,
        "retry_after_seconds": 17.0,
    }


def test_offline_replay_uses_zero_transport_and_is_deterministic(tmp_path: Path) -> None:
    raw_store = FilesystemRawSnapshotStore(tmp_path / "raw")
    records = raw_store.save_batch(_offer_raw(), snapshot_id="lidl-offline")
    connector = LidlConnector(client=object())  # type: ignore[arg-type]

    first = ReplayService(raw_store).replay_catalog(connector, records, _offer_store())
    second = ReplayService(raw_store).replay_catalog(connector, records, _offer_store())

    assert first.network_requests == second.network_requests == 0
    assert len(first.parsed.products) == len(second.parsed.products) == 5
    assert first.parsed.model_dump(mode="json") == second.parsed.model_dump(mode="json")


def test_source_policy_is_allow_and_bounded_factory_stays_bounded() -> None:
    connector = LidlConnector.for_bounded_discovery(page_size=5)
    assert connector.source_policy == SourcePolicy.ALLOW
    assert connector.coverage == CoverageLevel.OFFERS_ONLY
    assert connector.client.max_pages == 1
    audit = connector.collection_policy_audit()
    assert audit.source_policy == SourcePolicy.ALLOW
    assert audit.operator_opt_in is False
    assert audit.max_concurrency == 1
