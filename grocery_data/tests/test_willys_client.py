import json

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.domain import Chain, CoverageLevel, SourceStore


def _store() -> SourceStore:
    return SourceStore(
        chain=Chain.WILLYS,
        external_id="2354",
        name="Willys Lund Nova",
        coverage=CoverageLevel.FULL_CATALOG,
        raw_reference="raw:stores",
    )


@pytest.mark.asyncio
async def test_catalog_uses_public_store_context_and_pagination() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="csrf-secret")
        if path.endswith("/store/activate"):
            assert request.headers["X-CSRF-Token"] == "csrf-secret"
            return httpx.Response(200, json={"activated": True})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"pickingStore": {"storeId": "2354"}})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Alla varor",
                    "url": "",
                    "children": [{"id": "N1", "title": "Pasta", "url": "/pasta", "children": []}],
                },
            )
        if path.endswith("/c/pasta"):
            page = int(request.url.params["page"])
            return httpx.Response(
                200,
                json={
                    "results": [{"code": f"p{page}"}],
                    "pagination": {"currentPage": page, "numberOfPages": 2},
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    transport = httpx.MockTransport(handler)
    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=transport,
        headers={"Accept": "application/json"},
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    assert [document.kind for document in batch.documents] == [
        "store_activation",
        "store_context",
        "category_tree",
        "catalog_page",
        "catalog_page",
    ]
    assert all(
        "csrf-secret" not in json.dumps(document.model_dump(mode="json"))
        for document in batch.documents
    )
    assert len(requests) == 6
    assert batch.transport.request_count == 6
    assert batch.catalog_completion is not None
    assert batch.catalog_completion.is_full_traversal
    assert batch.catalog_completion.products_observed == 2


@pytest.mark.asyncio
async def test_catalog_accepts_only_proven_terminal_null_results_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "2354"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "root",
                    "title": "Root",
                    "url": "",
                    "children": [{"id": "p", "title": "Pasta", "url": "/pasta"}],
                },
            )
        if path.endswith("/c/pasta"):
            page = int(request.url.params["page"])
            if page == 0:
                return httpx.Response(
                    200,
                    json={
                        "results": [{"code": f"p{index}"} for index in range(30)],
                        "pagination": {
                            "currentPage": 0,
                            "numberOfPages": 2,
                            "pageSize": 30,
                            "totalNumberOfResults": 30,
                        },
                    },
                )
            return httpx.Response(
                200,
                json={
                    "results": None,
                    "pagination": {
                        "currentPage": 1,
                        "numberOfPages": 2,
                        "pageSize": 30,
                        "totalNumberOfResults": 30,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    assert batch.catalog_completion is not None
    assert batch.catalog_completion.is_full_traversal
    assert batch.catalog_completion.pages_fetched == 2
    assert batch.catalog_completion.products_observed == 30


@pytest.mark.asyncio
async def test_catalog_fails_when_store_context_is_not_confirmed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if request.url.path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if request.url.path.endswith("/store/active"):
            return httpx.Response(200, json={"pickingStore": {"storeId": "another"}})
        raise AssertionError("catalog fetch must stop before category traversal")

    http_client = httpx.AsyncClient(
        base_url="https://public.example", transport=httpx.MockTransport(handler)
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()
    partial = caught.value.partial_batch
    assert [document.kind for document in partial.documents] == [
        "store_activation",
        "store_context",
    ]
    assert partial.catalog_completion is not None
    assert partial.catalog_completion.complete is False


@pytest.mark.asyncio
async def test_optional_detail_enrichment_captures_gtin_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "2354"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "url": "",
                    "children": [{"id": "N1", "title": "Pasta", "url": "/pasta"}],
                },
            )
        if path.endswith("/c/pasta"):
            return httpx.Response(
                200,
                json={
                    "results": [{"code": "p1"}, {"code": "p2"}],
                    "pagination": {"currentPage": 0, "numberOfPages": 1},
                },
            )
        if path.endswith("/p/p1"):
            return httpx.Response(200, json={"code": "p1", "ean": "7310000000001"})
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        detail_enrichment_limit=1,
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()
    assert [document.kind for document in batch.documents].count("product_detail") == 1
    assert batch.documents[-1].json_payload()["ean"] == "7310000000001"


@pytest.mark.asyncio
async def test_catalog_error_preserves_completed_pages_and_inert_diagnostic() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "2354"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "root",
                    "title": "Root",
                    "url": "",
                    "children": [{"id": "p", "title": "Pasta", "url": "/pasta"}],
                },
            )
        if path.endswith("/c/pasta") and request.url.params["page"] == "0":
            return httpx.Response(
                200,
                json={
                    "results": [{"code": "kept-product"}],
                    "pagination": {"currentPage": 0, "numberOfPages": 2},
                },
            )
        if path.endswith("/c/pasta"):
            return httpx.Response(503, json={"error": "temporary"})
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    partial = caught.value.partial_batch
    pages = [item for item in partial.documents if item.kind == "catalog_page"]
    assert len(pages) == 1
    assert pages[0].http_status == 200
    assert pages[0].json_payload()["results"][0]["code"] == "kept-product"
    diagnostic = partial.documents[-1]
    assert diagnostic.http_status == 503
    assert diagnostic.kind == "http_error"
    assert diagnostic.content_type == "application/json; profile=transport-stop-diagnostic"
    assert diagnostic.json_payload() == {
        "classification": "http_error",
        "http_status": 503,
        "schema": "willys-transport-stop-v1",
    }
    assert partial.transport.request_count == 6
    assert partial.transport.http_error_count == 1
    assert partial.catalog_completion is not None
    assert partial.catalog_completion.complete is False
    assert partial.catalog_completion.products_observed == 1


@pytest.mark.parametrize(
    ("status", "payload", "content_type", "classification"),
    [
        (401, b'{"error":"unauthorized"}', "application/json", "access_challenge"),
        (403, b'{"error":"forbidden"}', "application/json", "access_challenge"),
        (200, b"<html>ordinary invalid response</html>", "text/html", "non_json_response"),
        (
            200,
            b'{"message":"Human Verification","private":"body-secret"}',
            "application/json",
            "access_challenge",
        ),
        (503, b'{"error":"temporary"}', "application/json", "http_error"),
    ],
)
@pytest.mark.asyncio
async def test_transport_stop_never_persists_body_headers_or_session_values(
    status: int,
    payload: bytes,
    content_type: str,
    classification: str,
) -> None:
    body_sentinel = "willys-response-body-secret"
    header_sentinel = "willys-response-header-secret"
    session_sentinel = "willys-response-session-secret"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/store")
        body = (
            payload.replace(b"body-secret", body_sentinel.encode())
            if b"body-secret" in payload
            else payload + body_sentinel.encode()
        )
        return httpx.Response(
            status,
            content=body,
            headers={
                "Content-Type": f'{content_type}; trace="{header_sentinel}"',
                "Set-Cookie": f"session={session_sentinel}",
            },
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    raw = caught.value.partial_batch.documents[0]
    assert raw.kind == classification
    assert raw.http_status == status
    assert raw.content_type == "application/json; profile=transport-stop-diagnostic"
    assert raw.json_payload() == {
        "classification": classification,
        "http_status": status,
        "schema": "willys-transport-stop-v1",
    }
    serialized = json.dumps(raw.model_dump(mode="json"))
    assert body_sentinel not in serialized
    assert header_sentinel not in serialized
    assert session_sentinel not in serialized


@pytest.mark.asyncio
async def test_terminal_rate_limit_keeps_only_parsed_retry_after() -> None:
    body_sentinel = "willys-rate-body-secret"
    header_sentinel = "willys-rate-header-secret"
    session_sentinel = "willys-rate-session-secret"
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        assert request.url.path.endswith("/store")
        attempts += 1
        return httpx.Response(
            429,
            json={"error": "slow down", "private": body_sentinel},
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
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    raw = caught.value.partial_batch.documents[0]
    assert attempts == 1
    assert caught.value.partial_batch.transport.request_count == 1
    assert caught.value.partial_batch.transport.http_error_count == 1
    assert caught.value.partial_batch.transport.rate_limit_count == 1
    assert raw.kind == "rate_limit"
    assert raw.json_payload() == {
        "classification": "rate_limit",
        "http_status": 429,
        "retry_after_seconds": 4.0,
        "schema": "willys-transport-stop-v1",
    }
    serialized = json.dumps(raw.model_dump(mode="json"))
    assert body_sentinel not in serialized
    assert header_sentinel not in serialized
    assert session_sentinel not in serialized


@pytest.mark.parametrize(
    "catalog_payload",
    [
        {"results": []},
        {"results": [], "pagination": {"currentPage": "0", "numberOfPages": 1}},
        {"results": [], "pagination": {"currentPage": 1, "numberOfPages": 2}},
        {"results": {}, "pagination": {"currentPage": 0, "numberOfPages": 1}},
        {
            "results": None,
            "pagination": {
                "currentPage": 0,
                "numberOfPages": 2,
                "pageSize": 30,
                "totalNumberOfResults": 0,
            },
        },
        {
            "results": None,
            "pagination": {
                "currentPage": 0,
                "numberOfPages": 1,
                "pageSize": 30,
                "totalNumberOfResults": 1,
            },
        },
        {
            "pagination": {
                "currentPage": 0,
                "numberOfPages": 1,
                "pageSize": 30,
                "totalNumberOfResults": 0,
            },
        },
    ],
    ids=(
        "missing-pagination",
        "wrong-pagination-type",
        "page-mismatch",
        "wrong-results-type",
        "null-nonterminal",
        "null-total-mismatch",
        "missing-results-key",
    ),
)
@pytest.mark.asyncio
async def test_catalog_rejects_ambiguous_traversal_contract(
    catalog_payload: object,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "2354"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "root",
                    "title": "Root",
                    "url": "",
                    "children": [{"id": "p", "title": "Pasta", "url": "/pasta"}],
                },
            )
        if path.endswith("/c/pasta"):
            return httpx.Response(200, json=catalog_payload)
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    partial = caught.value.partial_batch
    assert partial.documents[-1].kind == "catalog_page"
    assert partial.catalog_completion is not None
    assert partial.catalog_completion.complete is False
    assert partial.catalog_completion.completed_categories == 0
    assert partial.catalog_completion.reason in {"TypeError", "ValueError"}


@pytest.mark.asyncio
async def test_empty_category_tree_cannot_claim_full_catalog() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "2354"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={"id": "root", "title": "Root", "url": "", "children": []},
            )
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    partial = caught.value.partial_batch
    assert partial.documents[-1].kind == "category_tree"
    assert partial.catalog_completion is not None
    assert partial.catalog_completion.complete is False
    assert partial.catalog_completion.expected_categories == 0


@pytest.mark.asyncio
async def test_explicit_page_limit_can_never_claim_full_traversal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "2354"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "root",
                    "title": "Root",
                    "url": "",
                    "children": [{"id": "p", "title": "Pasta", "url": "/pasta"}],
                },
            )
        if path.endswith("/c/pasta"):
            return httpx.Response(
                200,
                json={
                    "results": [{"code": "p1"}],
                    "pagination": {"currentPage": 0, "numberOfPages": 5},
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=1),
        max_pages_per_category=1,
        client=http_client,
    )
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    assert batch.catalog_completion is not None
    assert batch.catalog_completion.limited is True
    assert batch.catalog_completion.complete is False
    assert batch.catalog_completion.completed_categories == 0


@pytest.mark.asyncio
async def test_rate_limit_never_retries_into_a_successful_response() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        assert request.url.path.endswith("/store")
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(200, json=[])

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(
            attempts=2,
            base_delay_seconds=0,
            max_delay_seconds=0,
        ),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    batch = caught.value.partial_batch
    assert attempts == 1
    assert batch.transport.request_count == 1
    assert batch.transport.http_error_count == 1
    assert batch.transport.rate_limit_count == 1
    assert len(batch.documents) == 1
    assert batch.documents[0].kind == "rate_limit"
    assert batch.documents[0].http_status == 429


@pytest.mark.asyncio
async def test_csrf_rate_limit_stops_first_and_preserves_safe_diagnostic() -> None:
    attempts = 0
    secret = "never-persist-this-csrf-rate-limit-body"

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        assert request.url.path.endswith("/csrf-token")
        attempts += 1
        return httpx.Response(
            429,
            json={"secret": secret},
            headers={"Retry-After": "7", "Set-Cookie": "session=never-persist"},
        )

    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
    )
    client = WillysClient(
        base_url="https://public.example",
        requests_per_second=10000,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
        client=http_client,
    )
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    partial = caught.value.partial_batch
    assert attempts == 1
    assert partial.transport.request_count == 1
    assert partial.transport.rate_limit_count == 1
    assert len(partial.documents) == 1
    diagnostic = partial.documents[0]
    assert diagnostic.kind == "rate_limit"
    assert diagnostic.store_external_id == "2354"
    assert diagnostic.json_payload() == {
        "classification": "rate_limit",
        "http_status": 429,
        "retry_after_seconds": 7.0,
        "schema": "willys-transport-stop-v1",
    }
    assert secret not in json.dumps(diagnostic.model_dump(mode="json"))
