import json

import httpx
import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.hemkop import HemkopConnector
from grocery_data.app.connectors.hemkop.client import (
    HemkopAccessChallengeFetchError,
    HemkopClient,
    HemkopRateLimitFetchError,
    HemkopSourcePolicyError,
    reconcile_saved_catalog_completion,
)
from grocery_data.app.connectors.http import RetryPolicy
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    PriceContextType,
    SourcePolicy,
    SourceStore,
)


def _store(store_id: str = "4224") -> SourceStore:
    return SourceStore(
        chain=Chain.HEMKOP,
        external_id=store_id,
        name="Hemköp Lund Brunnshög",
        city="Lund",
        online_shopping=True,
        coverage=CoverageLevel.FULL_ONLINE_CATALOG,
        price_context_type=PriceContextType.ONLINE_STORE,
        physical_store_external_id=store_id,
        raw_reference="raw:stores#storeId=4224",
        source_fields={"price_context_activation_required": True},
    )


def _facets(store_id: str = "4224") -> list[dict[str, object]]:
    return [
        {
            "values": [
                {
                    "query": {
                        "query": {
                            "value": (
                                ":topRated:allCategories_string_mv:N00:"
                                f"salableOnlineInStore_string_mv:{store_id}"
                            )
                        }
                    }
                }
            ]
        }
    ]


def _client(
    handler,
    *,
    full: bool = False,
    retry_policy: RetryPolicy | None = None,
) -> tuple[HemkopClient, httpx.AsyncClient]:
    http_client = httpx.AsyncClient(
        base_url="https://public.example",
        transport=httpx.MockTransport(handler),
        headers={"Accept": "application/json"},
    )
    client = HemkopClient(
        base_url="https://public.example",
        requests_per_second=10_000,
        retry_policy=retry_policy or RetryPolicy(attempts=1),
        page_size=2 if full else 30,
        max_categories=None if full else 1,
        max_pages_per_category=None if full else 1,
        allow_full_crawl=full,
        allowed_store_ids={"4224"} if full else (),
        client=http_client,
    )
    return client, http_client


@pytest.mark.asyncio
async def test_validation_detail_fetch_is_exact_bounded_and_keeps_runtime_state_ephemeral() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="ephemeral-secret")
        if path.endswith("/store/activate"):
            assert request.headers["X-CSRF-Token"] == "ephemeral-secret"
            return httpx.Response(200, json={"activated": True})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"pickingStore": {"storeId": "4224"}})
        if path.endswith("/axfood/rest/p/101230686_ST"):
            assert request.url.params["isEanCode"] == "false"
            return httpx.Response(
                200,
                json={
                    "code": "101230686_ST",
                    "ean": "7391737003437",
                    "name": "Finbröd Skånskt",
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_validation_product_details(
            _store(),
            ("101230686_ST",),
            max_products=1,
        )
    finally:
        await http_client.aclose()

    assert [document.kind for document in batch.documents] == [
        "store_activation",
        "store_context",
        "product_detail",
    ]
    assert batch.transport.request_count == 4
    serialized = json.dumps([document.model_dump(mode="json") for document in batch.documents])
    assert "ephemeral-secret" not in serialized
    assert "X-CSRF-Token" not in serialized
    assert len(requests) == 4


@pytest.mark.asyncio
async def test_full_catalog_reconciles_nonoverlapping_top_level_fixture() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="session-only-csrf")
        if path.endswith("/store/activate"):
            assert request.headers["X-CSRF-Token"] == "session-only-csrf"
            assert request.url.params["storeId"] == "4224"
            return httpx.Response(200, json={"activated": True})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"pickingStore": {"storeId": "4224"}})
        if path.endswith("/categorytree"):
            assert request.url.params["storeId"] == "4224"
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Alla varor",
                    "url": "",
                    "children": [
                        {"id": "N01", "title": "Mejeri", "url": "/mejeri"},
                        {"id": "N02", "title": "Skafferi", "url": "/skafferi"},
                    ],
                },
            )
        if path.endswith("/c/mejeri"):
            page = int(request.url.params["page"])
            rows = [{"code": "milk-1"}, {"code": "milk-2"}] if page == 0 else [{"code": "milk-3"}]
            return httpx.Response(
                200,
                json={
                    "results": rows,
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": page,
                        "numberOfPages": 2,
                        "pageSize": 2,
                        "totalNumberOfResults": 3,
                    },
                },
            )
        if path.endswith("/c/skafferi"):
            return httpx.Response(
                200,
                json={
                    "results": [{"code": "rice-1"}],
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": 0,
                        "numberOfPages": 1,
                        "pageSize": 2,
                        "totalNumberOfResults": 1,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.is_full_traversal
    assert completion.expected_categories == 2
    assert completion.completed_categories == 2
    assert completion.expected_products == 4
    assert completion.raw_rows == 4
    assert completion.unique_products == 4
    assert completion.duplicate_products == 0
    assert completion.expected_pages == 3
    assert completion.pages_fetched == 3
    assert batch.transport.request_count == 7
    assert [document.kind for document in batch.documents] == [
        "store_activation",
        "store_context",
        "category_tree",
        "catalog_page",
        "catalog_page",
        "catalog_page",
    ]
    serialized = json.dumps([document.model_dump(mode="json") for document in batch.documents])
    assert "session-only-csrf" not in serialized
    assert all("csrf-token" not in document.url for document in batch.documents)
    assert len(requests) == 7


@pytest.mark.asyncio
async def test_explicit_category_proof_reconciles_every_declared_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/c/mejeri-ost-och-agg"):
            page = int(request.url.params["page"])
            rows = (
                [{"code": "dairy-1"}, {"code": "dairy-2"}] if page == 0 else [{"code": "dairy-3"}]
            )
            return httpx.Response(
                200,
                json={
                    "results": rows,
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": page,
                        "numberOfPages": 2,
                        "pageSize": 2,
                        "totalNumberOfResults": 3,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_category(
            _store(),
            "mejeri-ost-och-agg",
            max_pages=None,
        )
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.is_full_traversal
    assert completion.expected_categories == 1
    assert completion.expected_products == 3
    assert completion.unique_products == 3
    assert completion.pages_fetched == completion.expected_pages == 2


@pytest.mark.asyncio
async def test_identical_cross_partition_overlap_is_explicitly_reconciled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "children": [
                        {"id": "a", "title": "A", "url": "/a"},
                        {"id": "b", "title": "B", "url": "/b"},
                    ],
                },
            )
        if path.endswith(("/c/a", "/c/b")):
            return httpx.Response(
                200,
                json={
                    "results": [{"code": "same-product"}],
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": 0,
                        "numberOfPages": 1,
                        "pageSize": 2,
                        "totalNumberOfResults": 1,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.complete is True
    assert completion.limited is False
    assert completion.expected_products == 2
    assert completion.raw_rows == 2
    assert completion.unique_products == 1
    assert completion.duplicate_products == 1
    assert completion.within_partition_duplicates == 0
    assert completion.cross_partition_duplicates == 1
    assert completion.exact_evidence_reconciles is True


@pytest.mark.asyncio
async def test_conflicting_cross_partition_duplicate_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "children": [
                        {"id": "a", "title": "A", "url": "/a"},
                        {"id": "b", "title": "B", "url": "/b"},
                    ],
                },
            )
        if path.endswith(("/c/a", "/c/b")):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "code": "same-product",
                            "name": "First" if path.endswith("/a") else "Changed",
                            "priceValue": 10,
                        }
                    ],
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": 0,
                        "numberOfPages": 1,
                        "pageSize": 2,
                        "totalNumberOfResults": 1,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        with pytest.raises(ConnectorFetchError, match="aborted") as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = caught.value.partial_batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.cross_partition_duplicates == 1
    assert completion.within_partition_duplicates == 0
    assert completion.reason == "ValueError"


@pytest.mark.asyncio
async def test_exact_within_partition_duplicate_is_safely_deduplicated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "children": [{"id": "a", "title": "A", "url": "/a"}],
                },
            )
        if path.endswith("/c/a"):
            page = int(request.url.params["page"])
            rows = [{"code": "repeat"}, {"code": "unique"}] if page == 0 else [{"code": "repeat"}]
            return httpx.Response(
                200,
                json={
                    "results": rows,
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": page,
                        "numberOfPages": 2,
                        "pageSize": 2,
                        "totalNumberOfResults": 3,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.complete is True
    assert completion.within_partition_duplicates == 1
    assert completion.cross_partition_duplicates == 0
    assert completion.duplicate_products == 1
    assert completion.exact_duplicates_removed == 1
    assert completion.conflicting_duplicates == 0
    assert completion.pagination_overlaps == 1
    assert completion.exact_evidence_reconciles is True

    offline = reconcile_saved_catalog_completion(
        batch.model_copy(update={"catalog_completion": None}),
        expected_store_id="4224",
    )
    assert offline == completion


@pytest.mark.asyncio
async def test_conflicting_within_partition_duplicate_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "children": [{"id": "a", "title": "A", "url": "/a"}],
                },
            )
        if path.endswith("/c/a"):
            page = int(request.url.params["page"])
            rows = (
                [{"code": "repeat", "priceValue": 10}, {"code": "unique"}]
                if page == 0
                else [{"code": "repeat", "priceValue": 11}]
            )
            return httpx.Response(
                200,
                json={
                    "results": rows,
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": page,
                        "numberOfPages": 2,
                        "pageSize": 2,
                        "totalNumberOfResults": 3,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        with pytest.raises(ConnectorFetchError, match="aborted") as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = caught.value.partial_batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.within_partition_duplicates == 1
    assert completion.cross_partition_duplicates == 0
    assert completion.exact_duplicates_removed == 0
    assert completion.conflicting_duplicates == 1
    assert completion.pagination_overlaps == 0
    assert completion.exact_evidence_reconciles is False
    with pytest.raises(ValueError, match="within-partition duplicate changed"):
        reconcile_saved_catalog_completion(
            caught.value.partial_batch.model_copy(update={"catalog_completion": None}),
            expected_store_id="4224",
        )


@pytest.mark.asyncio
async def test_aborted_full_run_preserves_exact_partial_page_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "children": [{"id": "a", "title": "A", "url": "/a"}],
                },
            )
        if path.endswith("/c/a") and request.url.params["page"] == "0":
            return httpx.Response(
                200,
                json={
                    "results": [{"code": "p1"}, {"code": "p2"}],
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": 0,
                        "numberOfPages": 2,
                        "pageSize": 2,
                        "totalNumberOfResults": 3,
                    },
                },
            )
        if path.endswith("/c/a"):
            return httpx.Response(503, json={"error": "temporary"})
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler, full=True)
    try:
        with pytest.raises(ConnectorFetchError) as caught:
            await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = caught.value.partial_batch.catalog_completion
    assert completion is not None
    assert completion.expected_products == 3
    assert completion.raw_rows == 2
    assert completion.unique_products == 2
    assert completion.duplicate_products == 0
    assert completion.expected_pages == 2
    assert completion.pages_fetched == 1
    assert completion.complete is False


@pytest.mark.asyncio
async def test_bounded_discovery_can_never_claim_full_traversal() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/csrf-token"):
            return httpx.Response(200, json="secret")
        if path.endswith("/store/activate"):
            return httpx.Response(200, json={})
        if path.endswith("/store/active"):
            return httpx.Response(200, json={"storeId": "4224"})
        if path.endswith("/categorytree"):
            return httpx.Response(
                200,
                json={
                    "id": "N00",
                    "title": "Root",
                    "children": [{"id": "a", "title": "A", "url": "/a"}],
                },
            )
        if path.endswith("/c/a"):
            return httpx.Response(
                200,
                json={
                    "results": [{"code": f"p-{index}"} for index in range(30)],
                    "facets": _facets(),
                    "pagination": {
                        "currentPage": 0,
                        "numberOfPages": 2,
                        "pageSize": 30,
                        "totalNumberOfResults": 31,
                    },
                },
            )
        raise AssertionError(f"unexpected request: {request.url}")

    client, http_client = _client(handler)
    try:
        batch = await client.fetch_catalog(_store())
    finally:
        await http_client.aclose()

    completion = batch.catalog_completion
    assert completion is not None
    assert completion.complete is False
    assert completion.limited is True
    assert completion.completed_categories == 0
    assert completion.pages_fetched == 1
    assert completion.products_observed == 30
    assert completion.has_exact_evidence is False


@pytest.mark.parametrize(
    ("status", "body", "content_type"),
    [
        (403, b"request could not be satisfied: trace-secret", "text/html"),
        (405, b"Human Verification", "text/html"),
        (200, b"ordinary HTML login/challenge", "text/html"),
        (200, b'{"challenge":"AWS WAF"}', "application/json"),
    ],
)
@pytest.mark.asyncio
async def test_access_challenge_stops_immediately_with_sanitized_raw(
    status: int,
    body: bytes,
    content_type: str,
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, content=body, headers={"content-type": content_type})

    client, http_client = _client(
        handler,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=0),
    )
    try:
        with pytest.raises(HemkopAccessChallengeFetchError) as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    assert attempts == 1
    assert caught.value.partial_batch.documents[0].kind == "access_challenge"
    assert caught.value.partial_batch.documents[0].payload == b'{"reason":"access_challenge"}'
    assert b"trace-secret" not in caught.value.partial_batch.documents[0].payload


@pytest.mark.asyncio
async def test_429_stops_immediately_and_preserves_only_safe_diagnostic() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(
            429,
            content=b'{"private_request_id":"do-not-persist"}',
            headers={"content-type": "application/json", "Retry-After": "30"},
        )

    client, http_client = _client(
        handler,
        retry_policy=RetryPolicy(attempts=3, base_delay_seconds=0, max_delay_seconds=60),
    )
    try:
        with pytest.raises(HemkopRateLimitFetchError) as caught:
            await client.fetch_stores()
    finally:
        await http_client.aclose()

    assert attempts == 1
    partial = caught.value.partial_batch
    assert partial.transport.request_count == 1
    assert partial.transport.rate_limit_count == 1
    assert partial.documents[0].kind == "rate_limit"
    assert partial.documents[0].payload == b'{"reason":"rate_limited"}'


def test_review_policy_requires_unambiguous_opt_in_and_exact_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HEMKOP_ALLOW_FULL_CRAWL", raising=False)
    with pytest.raises(HemkopSourcePolicyError, match="REVIEW"):
        HemkopClient(max_categories=None, max_pages_per_category=None)

    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "perhaps")
    with pytest.raises(HemkopSourcePolicyError, match="ambiguous"):
        HemkopClient()

    monkeypatch.setenv("HEMKOP_ALLOW_FULL_CRAWL", "true")
    monkeypatch.delenv("HEMKOP_STORE_EXTERNAL_IDS", raising=False)
    with pytest.raises(HemkopSourcePolicyError, match="allowlist"):
        HemkopClient(max_categories=None, max_pages_per_category=None)


def test_connector_factories_separate_live_authority_from_offline_replay() -> None:
    full_client = HemkopClient(
        max_categories=None,
        max_pages_per_category=None,
        allow_full_crawl=True,
        allowed_store_ids={"4224"},
        requests_per_second=1,
    )
    full = HemkopConnector.for_full_collection(client=full_client)
    replay = HemkopConnector.for_replay(store_external_ids=("4224",))
    smaller_replay = HemkopConnector.for_replay(store_external_ids=("4123",))
    bounded = HemkopConnector.for_bounded_discovery()

    assert full.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert full.minimum_full_catalog_products == 8_000
    assert full.collection_policy_audit().source_policy is SourcePolicy.REVIEW
    assert full.collection_policy_audit().operator_opt_in is True
    assert full.collection_policy_audit().store_allowlist == ("4224",)
    assert replay.coverage is CoverageLevel.FULL_ONLINE_CATALOG
    assert replay.minimum_full_catalog_products == 4_500
    assert smaller_replay.minimum_full_catalog_products == 5_000
    assert replay.collection_policy_audit().operator_opt_in is False
    assert replay.client.max_categories == 1
    assert replay.client.max_pages_per_category == 1
    assert bounded.coverage is CoverageLevel.PARTIAL_CATALOG
    assert bounded.collection_policy_audit().operator_opt_in is False


def test_full_connector_requires_the_exact_allowlisted_context() -> None:
    client = HemkopClient(
        max_categories=None,
        max_pages_per_category=None,
        allow_full_crawl=True,
        allowed_store_ids={"4224"},
    )
    connector = HemkopConnector.for_full_collection(client=client)
    selected = _store("4224")
    another = _store("4123")

    assert connector.catalog_eligible(selected) is True
    assert connector.catalog_eligible(another) is False
