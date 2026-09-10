from __future__ import annotations

import json
from collections import deque
from copy import deepcopy
from typing import Any

import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
    IcaOnlineBrowserTransport,
    _safe_response_url,
    reconcile_category_proof,
)
from grocery_data.app.connectors.ica.online_catalog_client import (
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
    IcaOnlineHttpError,
    IcaOnlineSourcePolicyError,
)
from grocery_data.app.connectors.ica.online_catalog_models import IcaOnlineSchemaError

REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
RETAILER_ID = "1088004"
CATEGORY_ID = "ea243faf-2eca-47d7-af07-1dc61dd7693a"
PRODUCT_A = "f4ec81a4-4fff-4696-92dc-4a3e7bf06c31"
PRODUCT_B = "b0a25230-ba6f-4c0c-991f-c223cfa58090"
PRODUCT_C = "cf78ca6f-30b1-4935-b48e-8f0386fc6c58"
TOKEN = "5260877e-b589-4766-afd4-278267b3cfc3"
API_BASE = (
    f"https://handlaprivatkund.ica.se/stores/{RETAILER_ID}"
    "/api/webproductpagews/v6"
)
CATEGORY_URL = (
    f"https://handlaprivatkund.ica.se/stores/{RETAILER_ID}"
    f"/categories/mejeri-ost/{CATEGORY_ID}?source=navigation"
)


def _product(product_id: str, *, price: float = 15.9) -> dict[str, Any]:
    suffix = {PRODUCT_A: "2052770", PRODUCT_B: "2052771", PRODUCT_C: "2052772"}[
        product_id
    ]
    return {
        "productId": product_id,
        "retailerProductId": suffix,
        "type": "PRODUCT",
        "name": f"Mjölk {suffix}",
        "brand": "ICA",
        "categoryPath": ["Mejeri & ost", "Mjölk"],
        "available": True,
        "isInCurrentCatalog": True,
        "packSizeDescription": "1.5L",
        "price": {"amount": price, "currency": "SEK"},
        "unitPrice": {"amount": price / 1.5, "currency": "SEK", "unit": "liter"},
    }


def _page(
    *,
    products: list[dict[str, Any]],
    other_ids: list[str] | None = None,
    next_token: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, object] = (
        {"nextPageToken": next_token} if next_token is not None else {"terminal": True}
    )
    return {
        "additionalPageInfo": {
            "productCount": 3,
            "metadata": metadata,
        },
        "productGroups": [
            {
                "groupType": "ungrouped",
                "decoratedProducts": products,
                "otherProductIds": other_ids or [],
            }
        ],
        "missingPromotions": [],
    }


def _batch(product_ids: list[str], *, price: float = 16.9) -> dict[str, Any]:
    return {
        "products": [_product(product_id, price=price) for product_id in product_ids],
        "missedPromotions": [],
        "restrictedGroups": {},
    }


def _context_html() -> str:
    state = {
        "regionId": REGION_ID,
        "retailerRegionId": RETAILER_ID,
        "cookie": "must-not-survive",
        "sessionId": "must-not-survive",
        "csrf": "must-not-survive",
        "Page-View-Id": "must-not-survive",
        "trackingId": "must-not-survive",
        "navigation": {
            "categories": [
                {
                    "categoryId": CATEGORY_ID,
                    "name": "Mejeri & ost",
                    "productCount": 3,
                    "retailerCategoryId": "1001",
                    "childCategories": [],
                }
            ]
        },
    }
    return f"<script>window.__INITIAL_DATA__ = {json.dumps(state)};</script>"


class _FakeRequest:
    def __init__(self, method: str, url: str, post_data_json: object | None = None) -> None:
        self.method = method
        self.url = url
        self.post_data_json = post_data_json

    @property
    def headers(self) -> dict[str, str]:
        raise AssertionError("ICA observer must never read frontend request headers")


class _FakeResponse:
    def __init__(
        self,
        request: _FakeRequest,
        *,
        status: int,
        content_type: str,
        payload: object | None,
    ) -> None:
        self.request = request
        self.url = request.url
        self.status = status
        self._content_type = content_type
        self._payload = payload
        self.json_reads = 0

    @property
    def headers(self) -> dict[str, str]:
        raise AssertionError("ICA observer must never materialize response headers")

    async def header_value(self, name: str) -> str | None:
        assert name.casefold() == "content-type"
        return self._content_type

    async def json(self) -> object:
        self.json_reads += 1
        if self._payload is None:
            raise ValueError("not JSON")
        return deepcopy(self._payload)


class _ExplodingMetadataResponse(_FakeResponse):
    async def header_value(self, name: str) -> str | None:
        del name
        raise RuntimeError("simulated target close while reading response metadata")


class _FakeNavigationResponse:
    status = 200

    async def header_value(self, name: str) -> str:
        assert name.casefold() == "content-type"
        return "text/html; charset=utf-8"

    @property
    def headers(self) -> dict[str, str]:
        raise AssertionError("ICA observer must not materialize navigation headers")


class _FakeLocator:
    async def inner_text(self, *, timeout: int) -> str:
        assert timeout > 0
        return "Mejeri & ost"


class _FakeMouse:
    def __init__(self, page: _FakePage) -> None:
        self._page = page

    async def wheel(self, x: int, y: int) -> None:
        assert x == 0 and y > 0
        self._page.scrolls += 1
        self._page.emit_next()


class _FakePage:
    def __init__(self, steps: list[_FakeResponse], *, html: str | None = None) -> None:
        self._steps = deque(steps)
        self._handlers: dict[str, list[Any]] = {"request": [], "response": []}
        self._html = html or _context_html()
        self.url = CATEGORY_URL
        self.mouse = _FakeMouse(self)
        self.closed = False
        self.scrolls = 0

    def on(self, event: str, callback: Any) -> None:
        self._handlers[event].append(callback)

    def emit_next(self) -> None:
        if not self._steps:
            return
        response = self._steps.popleft()
        for callback in self._handlers["request"]:
            callback(response.request)
        for callback in self._handlers["response"]:
            callback(response)

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> _FakeNavigationResponse:
        assert url == CATEGORY_URL
        assert wait_until == "domcontentloaded"
        assert timeout > 0
        self.url = url
        self.emit_next()
        return _FakeNavigationResponse()

    async def wait_for_timeout(self, milliseconds: int) -> None:
        assert milliseconds > 0

    def locator(self, selector: str) -> _FakeLocator:
        assert selector == "body"
        return _FakeLocator()

    async def content(self) -> str:
        return self._html

    async def evaluate(self, expression: str, argument: object | None = None) -> object:
        del expression, argument
        raise AssertionError("ICA observer must never synthesize window.fetch")

    async def close(self) -> None:
        self.closed = True


class _FakeContext:
    def __init__(self, page: _FakePage) -> None:
        self._page = page
        self.closed = False

    async def new_page(self) -> _FakePage:
        return self._page

    async def close(self) -> None:
        self.closed = True

    async def cookies(self) -> object:
        raise AssertionError("ICA observer must never inspect cookies")

    async def storage_state(self) -> object:
        raise AssertionError("ICA observer must never inspect storage state")


class _FakeBrowser:
    def __init__(self, context: _FakeContext) -> None:
        self._context = context
        self.context_kwargs: dict[str, object] | None = None
        self.closed = False

    async def new_context(self, **kwargs: object) -> _FakeContext:
        self.context_kwargs = kwargs
        return self._context

    async def close(self) -> None:
        self.closed = True


class _FakeChromium:
    def __init__(self, browser: _FakeBrowser) -> None:
        self._browser = browser
        self.launch_calls: list[dict[str, object]] = []

    async def launch(self, **kwargs: object) -> _FakeBrowser:
        self.launch_calls.append(kwargs)
        return self._browser


class _FakePlaywright:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class _FakeManager:
    def __init__(self, playwright: _FakePlaywright) -> None:
        self._playwright = playwright
        self.starts = 0

    async def start(self) -> _FakePlaywright:
        self.starts += 1
        return self._playwright


class _FakeRuntime:
    def __init__(self, steps: list[_FakeResponse], *, html: str | None = None) -> None:
        self.page = _FakePage(steps, html=html)
        self.context = _FakeContext(self.page)
        self.browser = _FakeBrowser(self.context)
        self.chromium = _FakeChromium(self.browser)
        self.playwright = _FakePlaywright(self.chromium)
        self.manager = _FakeManager(self.playwright)
        self.factory_calls = 0

    def factory(self) -> _FakeManager:
        self.factory_calls += 1
        return self.manager


def _response(
    method: str,
    url: str,
    payload: object | None,
    *,
    body: object | None = None,
    status: int = 200,
    content_type: str = "application/json; charset=utf-8",
) -> _FakeResponse:
    return _FakeResponse(
        _FakeRequest(method, url, body),
        status=status,
        content_type=content_type,
        payload=payload,
    )


def _normal_steps() -> list[_FakeResponse]:
    return [
        _response(
            "GET",
            f"{API_BASE}/product-pages?categoryId={CATEGORY_ID}",
            _page(products=[_product(PRODUCT_A)], other_ids=[PRODUCT_B], next_token=TOKEN),
        ),
        _response(
            "PUT",
            f"{API_BASE}/products",
            _batch([PRODUCT_B]),
            body=[PRODUCT_B],
        ),
        _response(
            "GET",
            f"{API_BASE}/product-pages?categoryId={CATEGORY_ID}&pageToken={TOKEN}",
            _page(products=[_product(PRODUCT_C)]),
        ),
    ]


def _client(
    runtime: _FakeRuntime,
    *,
    frontend_headless: bool = False,
    frontend_max_scrolls: int = 5,
) -> IcaOnlineBrowserTransport:
    return IcaOnlineBrowserTransport(
        context_mappings={REGION_ID: RETAILER_ID},
        requests_per_second=1_000,
        max_categories=1,
        max_pages_per_category=1,
        max_batches_per_page=1,
        product_batch_size=None,
        allow_category_proof=True,
        allow_full_crawl=False,
        allowed_context_ids=[REGION_ID],
        frontend_headless=frontend_headless,
        frontend_max_scrolls=frontend_max_scrolls,
        frontend_settle_ms=1,
        playwright_factory=runtime.factory,
    )


def _cause(error: ConnectorFetchError) -> BaseException | None:
    return error.__cause__


def _http_cause(error: ConnectorFetchError) -> IcaOnlineHttpError:
    cause = error.__cause__
    assert isinstance(cause, IcaOnlineHttpError)
    return cause


@pytest.mark.asyncio
async def test_frontend_observer_captures_runtime_requests_and_offline_replays() -> None:
    runtime = _FakeRuntime(_normal_steps())
    client = _client(runtime)

    raw = await client.fetch_category_proof(REGION_ID, CATEGORY_ID)
    replay = reconcile_category_proof(raw, region_id=REGION_ID, category_id=CATEGORY_ID)
    await client.aclose()

    assert raw.catalog_completion is not None
    assert raw.catalog_completion.complete is True
    assert raw.catalog_completion.unique_products == 3
    assert raw.catalog_completion.pages_fetched == 2
    assert replay.catalog_completion == raw.catalog_completion
    assert raw.transport.request_count == 4  # navigation + 3 ICA-owned JSON responses
    assert runtime.factory_calls == 1
    assert runtime.manager.starts == 1
    assert runtime.chromium.launch_calls == [{"headless": False}]
    assert runtime.browser.context_kwargs == {}
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True

    batches = [document for document in raw.documents if document.kind == ICA_PRODUCT_BATCH_KIND]
    pages = [document for document in raw.documents if document.kind == ICA_PRODUCT_PAGE_KIND]
    assert len(batches) == 1
    assert len(pages) == 2
    assert batches[0].query["observed_batch_size"] == "1"
    assert batches[0].query["frontend_observed"] == "true"
    assert TOKEN not in b"".join(document.payload for document in raw.documents).decode()
    assert TOKEN not in json.dumps([document.query for document in raw.documents])
    assert pages[1].query["previous_page_token_hash"]
    serialized = json.dumps(
        [document.model_dump(mode="json") for document in raw.documents],
        ensure_ascii=False,
    ).casefold()
    for secret in ("must-not-survive", "cookie", "sessionid", "csrf", "page-view-id", "trackingid"):
        assert secret not in serialized


@pytest.mark.asyncio
async def test_relevant_non_json_response_stops_without_reading_body_and_closes() -> None:
    challenge = _response(
        "PUT",
        f"{API_BASE}/products",
        None,
        body=[PRODUCT_B],
        status=405,
        content_type="text/html; charset=utf-8",
    )
    runtime = _FakeRuntime([_normal_steps()[0], challenge])
    client = _client(runtime)

    with pytest.raises(ConnectorFetchError) as captured:
        await client.fetch_category_proof(REGION_ID, CATEGORY_ID)

    assert challenge.json_reads == 0
    cause = _http_cause(captured.value)
    assert cause.raw.http_status == 405
    assert cause.raw.json_payload()["classification"] == "access_challenge"
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True
    await client.aclose()


@pytest.mark.asyncio
async def test_background_search_challenge_stops_before_body_read() -> None:
    challenge = _response(
        "GET",
        f"{API_BASE}/product-pages/search?q=Mj%C3%B6lk",
        None,
        status=202,
        content_type="text/html",
    )
    runtime = _FakeRuntime([_normal_steps()[0], challenge])
    client = _client(runtime)

    with pytest.raises(ConnectorFetchError) as captured:
        await client.fetch_category_proof(REGION_ID, CATEGORY_ID)

    assert challenge.json_reads == 0
    assert _http_cause(captured.value).raw.http_status == 202
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True
    await client.aclose()


@pytest.mark.asyncio
async def test_unrelated_api_failure_does_not_poison_exact_catalog_proof() -> None:
    unrelated = _response(
        "GET",
        f"https://handlaprivatkund.ica.se/stores/{RETAILER_ID}/api/active",
        None,
        status=405,
        content_type="text/html",
    )
    runtime = _FakeRuntime([unrelated, *_normal_steps()])
    client = _client(runtime)

    raw = await client.fetch_category_proof(REGION_ID, CATEGORY_ID)
    await client.aclose()

    assert raw.catalog_completion is not None
    assert raw.catalog_completion.unique_products == 3
    assert unrelated.json_reads == 0


@pytest.mark.asyncio
async def test_products_request_body_must_be_exact_public_uuid_array() -> None:
    invalid = _response(
        "PUT",
        f"{API_BASE}/products",
        _batch([PRODUCT_B]),
        body={"ids": [PRODUCT_B], "csrf": "runtime-secret"},
    )
    runtime = _FakeRuntime([_normal_steps()[0], invalid])
    client = _client(runtime)

    with pytest.raises(ConnectorFetchError) as captured:
        await client.fetch_category_proof(REGION_ID, CATEGORY_ID)

    assert invalid.json_reads == 0
    cause = _http_cause(captured.value)
    assert cause.raw.json_payload()["classification"] == (
        "frontend_request_schema_error"
    )
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True
    await client.aclose()


@pytest.mark.asyncio
async def test_category_without_frontend_product_page_fails_closed() -> None:
    runtime = _FakeRuntime([], html=_context_html())
    client = _client(runtime, frontend_max_scrolls=2)

    with pytest.raises(ConnectorFetchError) as captured:
        await client.fetch_category_proof(REGION_ID, CATEGORY_ID)

    assert isinstance(_cause(captured.value), IcaOnlineSchemaError)
    assert captured.value.partial_batch.catalog_completion is None
    assert not any(
        document.kind in {ICA_PRODUCT_PAGE_KIND, ICA_PRODUCT_BATCH_KIND}
        for document in captured.value.partial_batch.documents
    )
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True
    await client.aclose()


@pytest.mark.asyncio
async def test_response_task_failure_still_discards_every_browser_object() -> None:
    initial = _normal_steps()[0]
    exploding = _ExplodingMetadataResponse(
        initial.request,
        status=initial.status,
        content_type="application/json",
        payload=initial._payload,
    )
    runtime = _FakeRuntime([exploding])
    client = _client(runtime, frontend_max_scrolls=1)

    with pytest.raises(ConnectorFetchError) as captured:
        await client.fetch_category_proof(REGION_ID, CATEGORY_ID)

    assert _http_cause(captured.value).raw.json_payload()["classification"] == (
        "frontend_response_capture_error"
    )
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True
    await client.aclose()


@pytest.mark.asyncio
async def test_identical_repeated_frontend_batch_is_safely_suppressed() -> None:
    repeated = _normal_steps()[1]
    identical_repeat = _response(
        "PUT",
        f"{API_BASE}/products",
        _batch([PRODUCT_B]),
        body=[PRODUCT_B],
    )
    steps = [_normal_steps()[0], repeated, identical_repeat, _normal_steps()[2]]
    runtime = _FakeRuntime(steps)
    client = _client(runtime)

    raw = await client.fetch_category_proof(REGION_ID, CATEGORY_ID)
    await client.aclose()

    assert raw.catalog_completion is not None
    assert raw.catalog_completion.unique_products == 3
    assert len(
        [document for document in raw.documents if document.kind == ICA_PRODUCT_BATCH_KIND]
    ) == 1


@pytest.mark.asyncio
async def test_conflicting_repeated_frontend_batch_fails_closed() -> None:
    conflicting_repeat = _response(
        "PUT",
        f"{API_BASE}/products",
        _batch([PRODUCT_B], price=99.0),
        body=[PRODUCT_B],
    )
    steps = [_normal_steps()[0], _normal_steps()[1], conflicting_repeat, _normal_steps()[2]]
    runtime = _FakeRuntime(steps)
    client = _client(runtime)

    with pytest.raises(ConnectorFetchError) as captured:
        await client.fetch_category_proof(REGION_ID, CATEGORY_ID)

    assert isinstance(_cause(captured.value), IcaOnlineSchemaError)
    assert "conflicting" in str(_cause(captured.value)).casefold()
    assert runtime.page.closed is True
    assert runtime.context.closed is True
    assert runtime.browser.closed is True
    assert runtime.playwright.stopped is True
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize("headless", [False, True])
async def test_frontend_mode_is_fixed_for_one_run(headless: bool) -> None:
    runtime = _FakeRuntime(_normal_steps())
    client = _client(runtime, frontend_headless=headless)

    await client.fetch_category_proof(REGION_ID, CATEGORY_ID)
    await client.aclose()

    assert runtime.factory_calls == 1
    assert runtime.manager.starts == 1
    assert runtime.chromium.launch_calls == [{"headless": headless}]


@pytest.mark.asyncio
async def test_hand_built_browser_fetch_is_disabled() -> None:
    runtime = _FakeRuntime(_normal_steps())
    client = _client(runtime)

    with pytest.raises(IcaOnlineSourcePolicyError, match="frontend runtime"):
        await client.fetch_product_page(REGION_ID, CATEGORY_ID)

    assert runtime.factory_calls == 0
    await client.aclose()


def test_category_proof_does_not_require_preconfigured_product_batch_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ICA_PRODUCT_BATCH_SIZE", raising=False)
    runtime = _FakeRuntime(_normal_steps())

    client = _client(runtime)

    assert client.product_batch_size is None


@pytest.mark.parametrize(
    "url",
    [
        (
            "https://runtime-secret@handlaprivatkund.ica.se/"
            f"stores/{RETAILER_ID}/api/webproductpagews/v6/products"
        ),
        (
            "https://handlaprivatkund.ica.se:444/"
            f"stores/{RETAILER_ID}/api/webproductpagews/v6/products"
        ),
    ],
)
def test_safe_response_url_rejects_userinfo_and_non_https_port(url: str) -> None:
    with pytest.raises(ValueError):
        _safe_response_url(
            url,
            expected_path_prefix=f"/stores/{RETAILER_ID}/api/webproductpagews/v6/",
        )
