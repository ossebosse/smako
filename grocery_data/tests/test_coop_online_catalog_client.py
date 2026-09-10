from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.coop.models import CoopSchemaError
from grocery_data.app.connectors.coop.online_catalog_client import (
    COOP_FULFILLMENT_MAPPING_KIND,
    CoopOnlineAccessChallengeFetchError,
    CoopOnlineCatalogClient,
    CoopOnlinePublicApiConfig,
    CoopOnlineRateLimitFetchError,
    CoopOnlineSourcePolicyError,
    public_api_config_from_html,
    reconcile_saved_catalog_completion,
    sanitized_api_payload,
)
from grocery_data.app.connectors.coop.online_catalog_connector import (
    CoopOnlineCatalogConnector,
)
from grocery_data.app.connectors.coop.online_catalog_models import (
    CoopOnlineCategoryNode,
    validated_category_tree,
)
from grocery_data.app.connectors.http import AsyncRateLimiter, RetryPolicy
from grocery_data.app.domain import Chain, CoverageLevel, GeographicArea, RawBatch, RawFetch


def _config() -> CoopOnlinePublicApiConfig:
    return CoopOnlinePublicApiConfig(
        personalization_base_url="https://public.example/personalization",
        ecommerce_base_url="https://public.example/ecommerce",
        personalization_subscription_key="personalization-test-value",
        ecommerce_subscription_key="ecommerce-test-value",
    )


def _client(handler, *, full: bool = False, category_page_size: int = 48):
    http_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        follow_redirects=False,
    )
    client = CoopOnlineCatalogClient(
        public_api_config=_config(),
        requests_per_second=0.5 if full else 10_000,
        retry_policy=RetryPolicy(attempts=1),
        category_page_size=category_page_size,
        search_page_size=2,
        max_categories=None if full else 1,
        max_pages_per_category=None if full else 1,
        allow_full_crawl=full,
        allowed_context_ids=("730400",),
        client=http_client,
    )
    # Keep policy values production-realistic while removing waits in mocked tests.
    client._limiter = AsyncRateLimiter(10_000)
    return client, http_client


def _row(product_id: str, price: float = 10.0) -> dict[str, object]:
    return {
        "id": product_id,
        "ean": product_id,
        "name": f"Product {product_id}",
        "availableOnline": True,
        "salesPriceData": {"b2cPrice": price},
        "pricePriceData": {"b2cPrice": price},
        "packageSize": 1000,
        "packageSizeInformation": "1 kg",
        "packageSizeUnit": "Gram",
        "salesUnit": "Styck",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "body", "expected_error", "expected_kind"),
    [
        (429, "rate limited", CoopOnlineRateLimitFetchError, "rate_limited"),
        (403, "access denied", CoopOnlineAccessChallengeFetchError, "access_challenge"),
    ],
)
async def test_transport_stop_is_sanitized_and_fails_closed(
    status: int,
    body: str,
    expected_error: type[ConnectorFetchError],
    expected_kind: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        headers = {"Retry-After": "120"} if status == 429 else {}
        return httpx.Response(status, text=body, headers=headers)

    client, http_client = _client(handler, full=True)
    try:
        with pytest.raises(expected_error) as raised:
            await client.fetch_category(
                "730400",
                CoopOnlineCategoryNode(code="milk", name="Milk", url="/milk"),
                max_pages=None,
            )
    finally:
        await http_client.aclose()

    partial = raised.value.partial_batch
    assert len(partial.documents) == 1
    document = partial.documents[0]
    assert document.kind == expected_kind
    assert document.http_status == status
    assert body.encode() not in document.payload
    assert document.json_payload()["classification"] == expected_kind
    assert partial.transport.request_count == 1
    assert partial.transport.http_error_count == 1
    assert partial.transport.rate_limit_count == (1 if status == 429 else 0)


@pytest.mark.asyncio
async def test_timeout_aborts_collection_without_promotable_documents() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated timeout", request=request)

    client, http_client = _client(handler, full=True)
    try:
        with pytest.raises(ConnectorFetchError) as raised:
            await client.fetch_category(
                "730400",
                CoopOnlineCategoryNode(code="milk", name="Milk", url="/milk"),
                max_pages=None,
            )
    finally:
        await http_client.aclose()

    partial = raised.value.partial_batch
    assert partial.documents == ()
    assert partial.catalog_completion is None
    assert partial.transport.request_count == 1
    assert partial.transport.http_error_count == 1


@pytest.mark.asyncio
async def test_non_json_success_is_diagnostic_only_and_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not the public JSON contract</html>")

    client, http_client = _client(handler, full=True)
    try:
        with pytest.raises(ConnectorFetchError) as raised:
            await client.fetch_category(
                "730400",
                CoopOnlineCategoryNode(code="milk", name="Milk", url="/milk"),
                max_pages=None,
            )
    finally:
        await http_client.aclose()

    partial = raised.value.partial_batch
    assert len(partial.documents) == 1
    document = partial.documents[0]
    assert document.kind == "non_json_response"
    assert document.http_status == 200
    assert b"not the public JSON contract" not in document.payload
    assert partial.catalog_completion is None


def test_public_runtime_config_is_transient_and_has_redacted_repr() -> None:
    document = """
    <script type="application/json">
      {&quot;personalizationApiSubscriptionKey&quot;:&quot;personalization-public-value&quot;,
       &quot;hybrisApiSubscriptionKey&quot;:&quot;ecommerce-public-value&quot;,
       &quot;personalizationApiUrl&quot;:
         &quot;https://external.api.coop.se/personalization&quot;,
       &quot;hybrisApiUrl&quot;:&quot;https://external.api.coop.se/ecommerce/coop&quot;,
       &quot;personalizationApiVersion&quot;:&quot;v1&quot;}
    </script>
    """
    config = public_api_config_from_html(document)

    assert config.personalization_base_url.endswith("/personalization")
    assert config.ecommerce_base_url.endswith("/ecommerce")
    rendered = repr(config)
    assert "personalization-public-value" not in rendered
    assert "ecommerce-public-value" not in rendered
    assert rendered.count("[REDACTED]") == 2


def test_raw_payload_sanitizer_removes_nested_credentials_and_browser_identity() -> None:
    sanitized = json.loads(
        sanitized_api_payload(
            {
                "results": {
                    "items": [
                        {
                            "id": "7300156573186",
                            "name": "Milk",
                            "Authorization": "must-not-survive",
                            "cookieJar": "must-not-survive",
                            "csrfToken": "must-not-survive",
                            "xXsrfToken": "must-not-survive",
                            "accessToken": "must-not-survive",
                            "refresh_token": "must-not-survive",
                            "sessionStorage": "must-not-survive",
                            "trackingIdentity": "must-not-survive",
                            "uid": "must-not-survive",
                            "sid": "must-not-survive",
                        }
                    ]
                }
            }
        )
    )

    assert sanitized == {
        "results": {"items": [{"id": "7300156573186", "name": "Milk"}]}
    }


def test_raw_query_metadata_rejects_non_allowlisted_transport_state() -> None:
    with pytest.raises(ValueError, match="non-allowlisted key"):
        CoopOnlineCatalogClient._safe_query_metadata(
            {"store": "730400", "access_token": "must-not-survive"},
            None,
        )


def test_sanitized_online_fixtures_contain_no_transport_or_browser_identity() -> None:
    fixture_root = Path(__file__).parents[1] / "app" / "connectors" / "coop" / "fixtures"
    fixtures = [
        *fixture_root.glob("online_api_*.json"),
        fixture_root / "online_contexts_2026_08_25.json",
    ]
    assert fixtures and all(path.is_file() for path in fixtures)
    forbidden = (
        "authorization",
        "cookie",
        "csrf",
        "xsrf",
        "session",
        "tracking",
        "subscription-key",
        "subscription_key",
        "access_token",
        "refresh_token",
        '"uid"',
        '"sid"',
    )
    for path in fixtures:
        payload = path.read_text(encoding="utf-8").casefold()
        assert all(value not in payload for value in forbidden), path.name


def test_full_policy_requires_exact_context_and_production_rate() -> None:
    with pytest.raises(CoopOnlineSourcePolicyError, match="COOP_ONLINE_CONTEXT_IDS"):
        CoopOnlineCatalogClient(
            public_api_config=_config(),
            allow_full_crawl=True,
            max_categories=None,
            max_pages_per_category=None,
            allowed_context_ids=(),
        )
    with pytest.raises(CoopOnlineSourcePolicyError, match="between 0.5 and 1"):
        CoopOnlineCatalogClient(
            public_api_config=_config(),
            allow_full_crawl=True,
            requests_per_second=2,
            max_categories=None,
            max_pages_per_category=None,
            allowed_context_ids=("730400",),
        )


@pytest.mark.asyncio
async def test_search_uses_exact_skip_take_and_reconciles_all_rows() -> None:
    requests: list[httpx.Request] = []
    rows = [_row(str(7300000000000 + index)) for index in range(5)]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.path == "/personalization/search/products"
        assert request.url.params["store"] == "730400"
        assert request.url.params["groups"] == "CUSTOMER_PRIVATE"
        assert request.url.params["direct"] == "false"
        body = json.loads(request.content)
        skip = body["resultsOptions"]["skip"]
        take = body["resultsOptions"]["take"]
        return httpx.Response(
            200,
            json={
                "queryUsed": "mjölk",
                "results": {"count": 5, "items": rows[skip : skip + take]},
                "sid": "must-not-survive",
                "trackingId": "must-not-survive",
            },
        )

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_search("730400", "mjölk", max_pages=None)
    finally:
        await http_client.aclose()

    assert len(requests) == 3
    assert [json.loads(request.content)["resultsOptions"]["skip"] for request in requests] == [
        0,
        2,
        4,
    ]
    completion = batch.catalog_completion
    assert completion is not None and completion.is_full_traversal
    assert completion.expected_products == 5
    assert completion.raw_rows == 5
    assert completion.unique_products == 5
    assert all(document.query["search_query"] == "mjölk" for document in batch.documents)
    serialized = json.dumps([document.model_dump(mode="json") for document in batch.documents])
    for forbidden in (
        "personalization-test-value",
        "Ocp-Apim-Subscription-Key",
        "must-not-survive",
        "trackingId",
        '"sid"',
    ):
        assert forbidden not in serialized


@pytest.mark.asyncio
async def test_full_category_tree_reconciles_safe_cross_category_overlap() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/categories/tree/730400"):
            return httpx.Response(
                200,
                json={
                    "nodes": [
                        {"children": [], "code": "0001", "url": "/varor/"},
                        {"children": [], "code": "0002", "url": "/varor/"},
                        {
                            "code": "root",
                            "name": "Root",
                            "children": [
                                {"code": "a", "name": "A", "url": "/a"},
                                {"code": "b", "name": "B", "url": "/b"},
                                # The live tree currently has one identical
                                # duplicate terminal code. It is navigation
                                # evidence, not a second product partition.
                                {"code": "a", "name": "A", "url": "/a"},
                            ],
                        }
                    ]
                },
            )
        assert request.url.path.endswith("/search/entities/by-attribute")
        body = json.loads(request.content)
        category_id = body["attribute"]["value"]
        items = (
            [_row("7300000000001"), _row("7300000000002")]
            if category_id == "a"
            else [_row("7300000000002"), _row("7300000000003")]
        )
        assert body["requestAlias"]["details"] == f"/{category_id}"
        return httpx.Response(200, json={"results": {"count": 2, "items": items}})

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_catalog("730400")
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None and completion.is_full_traversal
    assert completion.expected_categories == 2
    assert completion.completed_categories == 2
    assert completion.expected_products == 4
    assert completion.raw_rows == 4
    assert completion.unique_products == 3
    assert completion.cross_partition_duplicates == 1
    assert completion.within_partition_duplicates == 0
    assert completion.conflicting_duplicates == 0
    assert batch.transport.request_count == 3
    tree = validated_category_tree(batch.documents[0].json_payload())
    assert tree.ignored_sentinel_rows == 2
    assert tree.ignored_sentinel_codes == ("0001", "0002")
    assert tree.duplicate_terminal_rows == 1
    assert len(tree.terminal_nodes()) == 2

    replay = reconcile_saved_catalog_completion(batch, expected_context_id="730400")
    assert replay == completion


@pytest.mark.parametrize(
    "sentinel",
    [
        {"children": [], "code": "0001", "name": "Named", "url": "/varor/"},
        {
            "children": [{"children": [], "code": "child", "name": "Child"}],
            "code": "0001",
            "url": "/varor/",
        },
        {"children": [], "code": "0001", "url": "/another-route/"},
    ],
)
def test_category_tree_rejects_changed_root_sentinel_shape(
    sentinel: dict[str, object],
) -> None:
    with pytest.raises(CoopSchemaError, match="sentinel changed shape"):
        validated_category_tree({"nodes": [sentinel]})


def test_category_tree_rejects_nested_or_unrelated_nameless_nodes() -> None:
    with pytest.raises(CoopSchemaError, match="sentinel changed shape"):
        validated_category_tree(
            {
                "nodes": [
                    {
                        "code": "root",
                        "name": "Root",
                        "children": [
                            {"children": [], "code": "0002", "url": "/varor/"}
                        ],
                    }
                ]
            }
        )
    with pytest.raises(CoopSchemaError, match="has no name"):
        validated_category_tree(
            {"nodes": [{"children": [], "code": "ordinary", "url": "/ordinary/"}]}
        )


@pytest.mark.asyncio
async def test_within_category_conflict_fails_closed_with_partial_raw() -> None:
    first = [_row("7300000000001", 10), _row("7300000000002", 20)]
    changed = _row("7300000000001", 11)

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        skip = body["resultsOptions"]["skip"]
        return httpx.Response(
            200,
            json={"results": {"count": 3, "items": first if skip == 0 else [changed]}},
        )

    client, http_client = _client(handler, full=True, category_page_size=2)
    category = CoopOnlineCategoryNode(code="milk", name="Milk", url="/milk")
    try:
        with pytest.raises(ConnectorFetchError) as raised:
            await client.fetch_category("730400", category, max_pages=None)
    finally:
        await http_client.aclose()

    partial = raised.value.partial_batch
    assert len(partial.documents) == 2
    completion = partial.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.conflicting_duplicates == 1
    assert completion.within_partition_duplicates == 1
    assert completion.exact_duplicates_removed == 0


@pytest.mark.asyncio
async def test_identical_pagination_overlap_is_classified_and_safe() -> None:
    first = [_row("7300000000001", 10), _row("7300000000002", 20)]

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        skip = body["resultsOptions"]["skip"]
        return httpx.Response(
            200,
            json={"results": {"count": 3, "items": first if skip == 0 else [first[0]]}},
        )

    client, http_client = _client(handler, full=True, category_page_size=2)
    try:
        batch = await client.fetch_category(
            "730400",
            CoopOnlineCategoryNode(code="milk", name="Milk", url="/milk"),
            max_pages=None,
        )
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None and completion.is_full_traversal
    assert completion.raw_rows == 3
    assert completion.unique_products == 2
    assert completion.within_partition_duplicates == 1
    assert completion.exact_duplicates_removed == 1
    assert completion.pagination_overlaps == 1


@pytest.mark.asyncio
async def test_pickup_identity_is_separate_from_shared_online_context() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["fields"] == "FULL"
        if request.url.path.endswith("/pointofservice/257611"):
            return httpx.Response(
                200,
                json={
                    "name": "257611",
                    "displayName": "Stora Coop Lund",
                    "storeId": "730400",
                    "sid": "must-not-survive",
                },
            )
        assert request.url.path.endswith("/pointofservices")
        assert request.url.params["query"] == "Hjärup"
        return httpx.Response(
            200,
            json={
                "stores": [
                    {
                        "name": "257611",
                        "displayName": "Stora Coop Lund",
                        "storeId": "730400",
                    },
                    {
                        "name": "106530",
                        "displayName": "Coop Hjärup",
                        "storeId": "730400",
                    },
                ]
            },
        )

    client, http_client = _client(handler)
    try:
        detail = await client.fetch_point_of_service("257611")
        listing = await client.fetch_point_of_services("Hjärup")
    finally:
        await http_client.aclose()

    assert detail.store_external_id is None
    assert detail.kind == COOP_FULFILLMENT_MAPPING_KIND
    assert detail.json_payload()["storeId"] == "730400"
    assert "sid" not in detail.json_payload()
    assert listing.documents[0].store_external_id is None

    connector = CoopOnlineCatalogConnector(client=client)
    contexts = connector.parse_stores(
        listing,
        ["raw:pickup-list"],
        GeographicArea(city="Lund"),
    )
    assert len(contexts) == 1
    context = contexts[0]
    assert context.external_id == "730400"
    assert context.name == "Coop Online Syd"
    assert context.physical_store_external_id is None
    assert context.coverage is CoverageLevel.PARTIAL_CATALOG


def test_730400_source_store_is_online_fulfillment_not_physical() -> None:
    context = CoopOnlineCatalogConnector.source_store(
        "730400",
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        raw_reference="raw:pointofservice#storeId=730400",
    )

    assert context.chain is Chain.COOP
    assert context.external_id == "730400"
    assert context.name == "Coop Online Syd"
    assert context.physical_store_external_id is None
    assert context.source_fields["price_semantics"] == "online_price"
    assert context.source_fields["customer_group_semantics"] == "private_b2c_not_membership"


def test_fulfillment_payload_raw_fixture_has_no_tracking_or_session_data() -> None:
    document = RawFetch(
        chain=Chain.COOP,
        kind=COOP_FULFILLMENT_MAPPING_KIND,
        method="GET",
        url="https://external.api.coop.se/ecommerce/coop/pointofservice/257611",
        fetched_at=datetime.now(tz=UTC),
        http_status=200,
        content_type="application/json",
        payload=json.dumps(
            {"name": "257611", "displayName": "Stora Coop Lund", "storeId": "730400"}
        ).encode(),
        connector_version="coop-online-catalog-v1",
    )
    batch = RawBatch(chain=Chain.COOP, documents=(document,))

    serialized = json.dumps(batch.model_dump(mode="json")).casefold()
    for forbidden in ("authorization", "cookie", "subscription", "trackingid", '"sid"'):
        assert forbidden not in serialized
