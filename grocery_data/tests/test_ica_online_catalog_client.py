from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from typing import Any

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.ica.online_catalog_client import (
    ICA_PRODUCT_BATCH_KIND,
    ICA_SEARCH_KIND,
    IcaOnlineCatalogClient,
    IcaOnlineSourcePolicyError,
)
from grocery_data.app.connectors.ica.online_catalog_models import IcaOnlineSchemaError
from grocery_data.app.domain import CoverageLevel
from grocery_data.app.services.collector import CatalogCompletenessError, GroceryCollector

REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
RETAILER_REGION_ID = "10880"
CATEGORY_A = "ea243faf-2eca-47d7-af07-1dc61dd7693a"
CATEGORY_B = "11111111-1111-4111-8111-111111111111"
PRODUCT_A = "f4ec81a4-4fff-4696-92dc-4a3e7bf06c31"
PRODUCT_B = "b0a25230-ba6f-4c0c-991f-c223cfa58090"
PRODUCT_C = "cf78ca6f-30b1-4935-b48e-8f0386fc6c58"


def _product(
    product_id: str = PRODUCT_A,
    *,
    category_path: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "productId": product_id,
        "retailerProductId": "2052770" if product_id == PRODUCT_A else "2052771",
        "type": "PRODUCT",
        "name": "Mellanmjölk 1,5l ICA",
        "brand": "ICA",
        "categoryPath": category_path or ["Mejeri", "Mjölk"],
        "available": True,
        "isInCurrentCatalog": True,
        "packSizeDescription": "1.5L",
        "price": {"amount": 15.9, "currency": "SEK"},
        "unitPrice": {"amount": 10.6, "currency": "SEK", "unit": "liter"},
    }


def _page(
    *,
    products: list[dict[str, Any]] | None = None,
    other_ids: list[str] | None = None,
    product_count: int = 1,
    next_token: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, object] = (
        {"nextPageToken": next_token} if next_token is not None else {"terminal": True}
    )
    return {
        "additionalPageInfo": {
            "productCount": product_count,
            "metadata": metadata,
        },
        "productGroups": [
            {
                "groupType": "ungrouped",
                "decoratedProducts": products if products is not None else [_product()],
                "otherProductIds": other_ids or [],
            }
        ],
        "missedPromotions": [],
    }


def _batch(product_ids: list[str]) -> dict[str, Any]:
    return {
        "products": [_product(product_id) for product_id in product_ids],
        "missedPromotions": [],
        "restrictedGroups": {},
    }


def _context_html(
    *,
    duplicate_first_product: bool = False,
    include_second_category: bool = True,
) -> str:
    first_rows = [_product(), deepcopy(_product())] if duplicate_first_product else [_product()]
    # `first_rows` is only included as irrelevant state to prove the context
    # sanitizer does not retain arbitrary page/product data.
    child_categories = [
        {
            "categoryId": CATEGORY_A,
            "name": "Mjölk",
            "productCount": 1,
            "retailerCategoryId": "1001",
            "childCategories": [],
        }
    ]
    if include_second_category:
        child_categories.append(
            {
                "categoryId": CATEGORY_B,
                "name": "Mejeri",
                "productCount": 1,
                "retailerCategoryId": "1002",
                "childCategories": [],
            }
        )
    state = {
        "regionId": REGION_ID,
        "retailerRegionId": RETAILER_REGION_ID,
        "trackingId": "context-tracking-secret",
        "unrelatedProducts": first_rows,
        "navigation": {
            "categories": [
                {
                    "categoryId": "22222222-2222-4222-8222-222222222222",
                    "name": "Matvaror",
                    "productCount": len(child_categories),
                    "retailerCategoryId": "1000",
                    "childCategories": child_categories,
                }
            ]
        },
    }
    return f"<script>window.__INITIAL_DATA__ = {json.dumps(state)};</script>"


def _client(
    handler: Any,
    *,
    allow_full_crawl: bool = False,
    product_batch_size: int | None = 2,
    max_categories: int | None = 1,
    max_pages_per_category: int | None = 1,
    max_batches_per_page: int | None = 1,
) -> tuple[IcaOnlineCatalogClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(
        base_url=IcaOnlineCatalogClient.base_url,
        transport=httpx.MockTransport(handler),
        cookies={"session": "browser-session-must-not-be-persisted"},
    )
    client = IcaOnlineCatalogClient(
        context_mappings={REGION_ID: RETAILER_REGION_ID},
        requests_per_second=1 if allow_full_crawl else 1000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
        max_categories=max_categories,
        max_pages_per_category=max_pages_per_category,
        max_batches_per_page=max_batches_per_page,
        product_batch_size=product_batch_size,
        allow_full_crawl=allow_full_crawl,
        allowed_context_ids=[REGION_ID],
        client=http_client,
    )
    return client, http_client


async def _disable_rate_wait(client: IcaOnlineCatalogClient) -> None:
    async def no_wait() -> None:
        return None

    client._limiter.wait = no_wait


@pytest.mark.asyncio
@pytest.mark.parametrize("declared_count,other_ids", [(1, []), (240, [PRODUCT_B])])
async def test_successful_anonymous_search_never_establishes_catalog_completeness(
    declared_count: int,
    other_ids: list[str],
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=_page(product_count=declared_count, other_ids=other_ids),
            request=request,
        )

    client, http_client = _client(handler)
    try:
        batch = await client.fetch_search(REGION_ID, "Mjölk", decorate_one_batch=False)
    finally:
        await client.aclose()
        await http_client.aclose()

    # A terminal keyword page is only complete for that keyword. Even a
    # successful response with no undecorated IDs proves no category traversal.
    assert batch.transport.request_count == 1
    assert batch.catalog_completion is None

    class FullCatalogSource:
        coverage = CoverageLevel.FULL_CATALOG

    with pytest.raises(CatalogCompletenessError, match="explicit traversal"):
        GroceryCollector._validate_catalog_completion(
            None,
            FullCatalogSource(),
            batch,
            minimum_products=100,
        )


@pytest.mark.asyncio
async def test_search_uses_exact_v6_url_and_query_contract() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_page(), request=request)

    client, http_client = _client(handler)
    try:
        batch = await client.fetch_search(REGION_ID, "  Mjölk  ", decorate_one_batch=False)
    finally:
        await client.aclose()
        await http_client.aclose()

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "GET"
    assert request.url.path == (
        f"/stores/{RETAILER_REGION_ID}/api/webproductpagews/v6/product-pages/search"
    )
    assert list(request.url.params.multi_items()) == [
        ("includeAdditionalPageInfo", "true"),
        ("maxPageSize", "300"),
        ("maxProductsToDecorate", "50"),
        ("q", "Mjölk"),
        ("tag", "web"),
    ]
    assert len(batch.documents) == 1
    assert batch.documents[0].kind == ICA_SEARCH_KIND
    assert batch.documents[0].url.endswith("/product-pages/search")
    assert "?" not in batch.documents[0].url
    assert batch.documents[0].query == {"search_query": "Mjölk", "page_index": "0"}


@pytest.mark.asyncio
async def test_category_first_and_continuation_requests_preserve_exact_page_token_contract() -> (
    None
):
    requests: list[httpx.Request] = []
    continuation = "ephemeral-next-page-token"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = _page(next_token=continuation) if len(requests) == 1 else _page()
        return httpx.Response(200, json=payload, request=request)

    client, http_client = _client(handler)
    try:
        first_raw, first = await client.fetch_product_page(REGION_ID, CATEGORY_A)
        second_raw, second = await client.fetch_product_page(
            REGION_ID,
            CATEGORY_A,
            page_token=continuation,
            page_index=1,
        )
    finally:
        await client.aclose()
        await http_client.aclose()

    assert first.next_page_token == continuation
    assert second.terminal
    first_query = list(requests[0].url.params.multi_items())
    assert first_query == [
        ("categoryId", CATEGORY_A),
        ("includeAdditionalPageInfo", "true"),
        ("maxPageSize", "300"),
        ("maxProductsToDecorate", "50"),
        ("sortOptionId", "favorite"),
        ("tag", "web"),
        ("tag", "category-item"),
    ]
    second_query = list(requests[1].url.params.multi_items())
    assert second_query == [
        ("categoryId", CATEGORY_A),
        ("pageToken", continuation),
        ("maxPageSize", "300"),
        ("maxProductsToDecorate", "50"),
        ("sortOptionId", "favorite"),
        ("tag", "web"),
        ("tag", "category-item"),
    ]
    first_payload = first_raw.json_payload()
    assert continuation not in first_raw.payload.decode()
    assert (
        first_payload["additionalPageInfo"]["metadata"]["nextPageTokenHash"]
        == sha256(continuation.encode()).hexdigest()
    )
    assert second_raw.query["previous_page_token_hash"] == sha256(continuation.encode()).hexdigest()


@pytest.mark.asyncio
async def test_product_batch_is_one_put_with_exact_uuid_array() -> None:
    requests: list[httpx.Request] = []
    ids = [PRODUCT_A, PRODUCT_B]

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_batch(ids), request=request)

    client, http_client = _client(handler)
    try:
        raw, result = await client.fetch_product_batch(
            REGION_ID,
            ids,
            category_id=CATEGORY_A,
            page_index=2,
            batch_index=1,
        )
    finally:
        await client.aclose()
        await http_client.aclose()

    assert len(requests) == 1
    request = requests[0]
    assert request.method == "PUT"
    assert request.url.path == (f"/stores/{RETAILER_REGION_ID}/api/webproductpagews/v6/products")
    assert request.url.query == b""
    assert json.loads(request.content) == ids
    assert result.product_ids == tuple(ids)
    assert raw.kind == ICA_PRODUCT_BATCH_KIND
    assert json.loads(raw.query["requested_product_ids"]) == ids


@pytest.mark.asyncio
async def test_202_html_challenge_stops_immediately_without_retry() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            202,
            headers={"Content-Type": "text/html"},
            text="<html>Human Verification session-secret</html>",
            request=request,
        )

    client, http_client = _client(handler)
    try:
        with pytest.raises(ConnectorFetchError) as raised:
            await client.fetch_search(REGION_ID, "Mjölk", decorate_one_batch=False)
    finally:
        await client.aclose()
        await http_client.aclose()

    assert calls == 1
    partial = raised.value.partial_batch
    assert partial.transport.request_count == 1
    assert partial.transport.http_error_count == 1
    assert len(partial.documents) == 1
    diagnostic = partial.documents[0]
    assert diagnostic.http_status == 202
    assert diagnostic.json_payload()["classification"] == "access_challenge"
    assert "session-secret" not in diagnostic.payload.decode()


@pytest.mark.asyncio
async def test_raw_payload_strips_session_tracking_headers_and_plain_continuation_token() -> None:
    token = "plain-continuation-must-not-survive"
    requests: list[httpx.Request] = []
    payload = _page(next_token=token)
    payload.update(
        {
            "Cookie": "response-cookie-secret",
            "Authorization": "bearer-secret",
            "csrfToken": "csrf-secret",
            "sessionId": "session-secret",
            "tracking_id": "tracking-secret",
            "uid": "user-secret",
            "accessToken": "access-token-secret",
            "refresh_token": "refresh-token-secret",
            "sessionTokens": ["session-token-list-secret"],
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload, request=request)

    client, http_client = _client(handler)
    try:
        raw, _ = await client.fetch_product_page(REGION_ID, CATEGORY_A)
    finally:
        await client.aclose()
        await http_client.aclose()

    saved = raw.payload.decode()
    assert "browser-session-must-not-be-persisted" in requests[0].headers["cookie"]
    for secret in (
        "browser-session-must-not-be-persisted",
        "response-cookie-secret",
        "bearer-secret",
        "csrf-secret",
        "session-secret",
        "tracking-secret",
        "user-secret",
        "access-token-secret",
        "refresh-token-secret",
        "session-token-list-secret",
        token,
    ):
        assert secret not in saved
    assert raw.url.startswith("https://handlaprivatkund.ica.se/stores/")
    assert "?" not in raw.url
    assert (
        raw.json_payload()["additionalPageInfo"]["metadata"]["nextPageTokenHash"]
        == sha256(token.encode()).hexdigest()
    )


@pytest.mark.asyncio
async def test_repeated_next_page_token_fails_closed_after_two_requests() -> None:
    requests: list[httpx.Request] = []
    repeated = "same-token"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=_page(next_token=repeated), request=request)

    client, http_client = _client(
        handler,
        allow_full_crawl=True,
        product_batch_size=50,
        max_categories=None,
        max_pages_per_category=None,
        max_batches_per_page=None,
    )
    await _disable_rate_wait(client)
    raw_sink = []
    try:
        with pytest.raises(IcaOnlineSchemaError, match="PAGINATION_LOOP"):
            await client._fetch_category(REGION_ID, CATEGORY_A, raw_sink=raw_sink)
    finally:
        await client.aclose()
        await http_client.aclose()

    assert len(requests) == 2
    assert len(raw_sink) == 2
    assert repeated not in raw_sink[0].payload.decode()
    assert requests[1].url.params["pageToken"] == repeated


@pytest.mark.asyncio
async def test_bounded_catalog_canary_stays_partial_when_one_batch_cannot_decorate_page() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == f"/stores/{RETAILER_REGION_ID}":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                text=_context_html(),
                request=request,
            )
        if request.method == "PUT":
            requested = json.loads(request.content)
            return httpx.Response(200, json=_batch(requested), request=request)
        return httpx.Response(
            200,
            json=_page(
                other_ids=[PRODUCT_B, PRODUCT_C],
                product_count=3,
            ),
            request=request,
        )

    client, http_client = _client(handler, product_batch_size=1)
    await _disable_rate_wait(client)
    try:
        batch = await client.fetch_catalog(REGION_ID)
    finally:
        await client.aclose()
        await http_client.aclose()

    assert len(requests) == 3
    assert json.loads(requests[-1].content) == [PRODUCT_B]
    completion = batch.catalog_completion
    assert completion is not None
    assert completion.limited
    assert not completion.complete
    assert completion.completed_categories == 0
    assert completion.products_observed == 2


@pytest.mark.asyncio
async def test_bounded_and_full_crawl_policy_gates_are_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ICA_PRODUCT_BATCH_SIZE", raising=False)
    monkeypatch.delenv("ICA_ONLINE_MAX_CONCURRENCY", raising=False)
    monkeypatch.delenv("ICA_ONLINE_REQUESTS_PER_SECOND", raising=False)
    transport = httpx.MockTransport(lambda request: httpx.Response(500, request=request))
    http_client = httpx.AsyncClient(base_url=IcaOnlineCatalogClient.base_url, transport=transport)
    with pytest.raises(IcaOnlineSourcePolicyError, match="one category/page/batch"):
        IcaOnlineCatalogClient(
            context_mappings={REGION_ID: RETAILER_REGION_ID},
            allow_full_crawl=False,
            max_categories=2,
            client=http_client,
        )
    with pytest.raises(IcaOnlineSourcePolicyError, match="cannot retain bounded"):
        IcaOnlineCatalogClient(
            context_mappings={REGION_ID: RETAILER_REGION_ID},
            allow_full_crawl=True,
            allowed_context_ids=[REGION_ID],
            product_batch_size=50,
            client=http_client,
        )
    with pytest.raises(IcaOnlineSourcePolicyError, match="requires browser-verified"):
        IcaOnlineCatalogClient(
            context_mappings={REGION_ID: RETAILER_REGION_ID},
            allow_full_crawl=True,
            allowed_context_ids=[REGION_ID],
            product_batch_size=None,
            max_categories=None,
            max_pages_per_category=None,
            max_batches_per_page=None,
            client=http_client,
        )
    with pytest.raises(IcaOnlineSourcePolicyError, match="without exact mapping"):
        IcaOnlineCatalogClient(
            context_mappings={REGION_ID: RETAILER_REGION_ID},
            allow_full_crawl=True,
            allowed_context_ids=["25cd762f-f65f-49e9-b12d-d02265c04165"],
            product_batch_size=50,
            max_categories=None,
            max_pages_per_category=None,
            max_batches_per_page=None,
            client=http_client,
        )
    other_region = "25cd762f-f65f-49e9-b12d-d02265c04165"
    valid = IcaOnlineCatalogClient(
        context_mappings={REGION_ID: RETAILER_REGION_ID, other_region: "10881"},
        allow_full_crawl=True,
        allowed_context_ids=[REGION_ID],
        product_batch_size=50,
        max_categories=None,
        max_pages_per_category=None,
        max_batches_per_page=None,
        client=http_client,
    )
    assert valid.context_allowed(REGION_ID)
    assert not valid.context_allowed(other_region)
    await valid.aclose()
    await http_client.aclose()


@pytest.mark.asyncio
async def test_catalog_completion_classifies_within_and_cross_category_duplicates() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == f"/stores/{RETAILER_REGION_ID}":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                text=_context_html(duplicate_first_product=True),
                request=request,
            )
        category_id = request.url.params["categoryId"]
        product = _product(
            category_path=["Mejeri", "Mjölk"]
            if category_id == CATEGORY_A
            else ["Mejeri", "Alla mjölkprodukter"]
        )
        products = [product, deepcopy(product)] if category_id == CATEGORY_A else [product]
        return httpx.Response(
            200,
            json=_page(products=products, product_count=1),
            request=request,
        )

    client, http_client = _client(
        handler,
        allow_full_crawl=True,
        product_batch_size=50,
        max_categories=None,
        max_pages_per_category=None,
        max_batches_per_page=None,
    )
    await _disable_rate_wait(client)
    try:
        batch = await client.fetch_catalog(REGION_ID)
    finally:
        await client.aclose()
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.is_full_traversal
    assert completion.raw_rows == 3
    assert completion.unique_products == 1
    assert completion.duplicate_products == 2
    assert completion.within_partition_duplicates == 1
    assert completion.cross_partition_duplicates == 1
    assert completion.exact_duplicates_removed == 1
    assert completion.conflicting_duplicates == 0
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_catalog_completion_classifies_safe_pagination_overlap() -> None:
    requests: list[httpx.Request] = []
    token = "next-category-page"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == f"/stores/{RETAILER_REGION_ID}":
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html"},
                text=_context_html(include_second_category=False),
                request=request,
            )
        payload = _page(next_token=token) if "pageToken" not in request.url.params else _page()
        return httpx.Response(200, json=payload, request=request)

    client, http_client = _client(
        handler,
        allow_full_crawl=True,
        product_batch_size=50,
        max_categories=None,
        max_pages_per_category=None,
        max_batches_per_page=None,
    )
    await _disable_rate_wait(client)
    try:
        batch = await client.fetch_catalog(REGION_ID)
    finally:
        await client.aclose()
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.is_full_traversal
    assert completion.raw_rows == 2
    assert completion.unique_products == 1
    assert completion.within_partition_duplicates == 1
    assert completion.cross_partition_duplicates == 0
    assert completion.exact_duplicates_removed == 1
    assert completion.pagination_overlaps == 1
    assert len(requests) == 3
