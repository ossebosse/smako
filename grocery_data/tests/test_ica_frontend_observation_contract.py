from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
    IcaOnlineBrowserTransport,
    reconcile_category_proof,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    ICA_PRODUCT_BATCH_KIND,
    ICA_PRODUCT_PAGE_KIND,
)
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore

REGION_ID = "92198f17-b02f-4fae-ad41-228bcc725420"
RETAILER_ID = "1088004"
CATEGORY_ID = "ea243faf-2eca-47d7-af07-1dc61dd7693a"
PRODUCT_A = "f4ec81a4-4fff-4696-92dc-4a3e7bf06c31"
PRODUCT_B = "b0a25230-ba6f-4c0c-991f-c223cfa58090"
PRODUCT_C = "cf78ca6f-30b1-4935-b48e-8f0386fc6c58"
API_BASE = f"https://handlaprivatkund.ica.se/stores/{RETAILER_ID}/api/webproductpagews/v6"
PAGE_URL = (
    f"{API_BASE}/product-pages?categoryId={CATEGORY_ID}"
    "&includeAdditionalPageInfo=true&maxPageSize=300"
    "&maxProductsToDecorate=50&sortOptionId=favorite"
    "&tag=web&tag=category-item"
)
BATCH_URL = f"{API_BASE}/products"
FIXTURE_DIR = Path(__file__).parents[1] / "app" / "connectors" / "ica" / "fixtures"


def _payloads() -> tuple[dict[str, object], dict[str, object]]:
    page = json.loads((FIXTURE_DIR / "online_v6_product_page.json").read_text("utf-8"))
    page["missedPromotions"] = []
    page.pop("missingPromotions", None)
    for group in page["productGroups"]:
        for product in group.get("decoratedProducts", []):
            product.pop("featuredProductCampaign", None)
    batch = json.loads((FIXTURE_DIR / "online_v6_product_batch.json").read_text("utf-8"))
    batch["missedPromotions"] = []
    return page, batch


def _initial_html() -> str:
    state = {
        "context": {
            "retailerRegionId": RETAILER_ID,
            "regionId": REGION_ID,
            "visitorId": "visitor-runtime-secret",
            "sessionId": "session-runtime-secret",
            "trackingId": "tracking-runtime-secret",
        },
        "navigation": {
            "categories": [
                {
                    "categoryId": CATEGORY_ID,
                    "name": "Mejeri och ost",
                    "productCount": 3,
                    "retailerCategoryId": "mejeri",
                    "childCategories": [],
                }
            ]
        },
    }
    encoded = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
    return f"<html><body>Mejeri och ost<script>window.__INITIAL_DATA__ = {encoded};</script></body></html>"


class _ObservedRequest:
    def __init__(
        self,
        *,
        method: str,
        url: str,
        post_data_json: object | None = None,
    ) -> None:
        self.method = method
        self.url = url
        self._post_data_json = post_data_json
        self.post_data_reads = 0
        self.header_reads = 0

    @property
    def post_data_json(self) -> object:
        self.post_data_reads += 1
        return self._post_data_json

    @property
    def headers(self) -> object:
        self.header_reads += 1
        raise AssertionError("ICA request headers are outside the observation contract")


class _ObservedResponse:
    def __init__(
        self,
        *,
        request: _ObservedRequest,
        status: int,
        content_type: str,
        payload: object,
    ) -> None:
        self.request = request
        self.url = request.url
        self.status = status
        self.content_type = content_type
        self.payload = payload
        self.json_calls = 0
        self.header_reads: list[str] = []

    async def header_value(self, name: str) -> str | None:
        self.header_reads.append(name)
        if name.casefold() != "content-type":
            raise AssertionError("only response content type may be inspected")
        return self.content_type

    async def json(self) -> object:
        self.json_calls += 1
        return self.payload

    @property
    def headers(self) -> object:
        raise AssertionError("response header collections must not be inspected")


class _NavigationResponse:
    status = 200

    async def header_value(self, name: str) -> str:
        assert name.casefold() == "content-type"
        return "text/html; charset=utf-8"


class _Body:
    async def inner_text(self, *, timeout: int) -> str:
        assert timeout > 0
        return "Mejeri och ost"


class _Mouse:
    def __init__(self) -> None:
        self.wheel_calls: list[tuple[int, int]] = []

    async def wheel(self, horizontal: int, vertical: int) -> None:
        self.wheel_calls.append((horizontal, vertical))


class _Page:
    def __init__(self, events: list[tuple[_ObservedRequest, _ObservedResponse]]) -> None:
        self.events = events
        self.handlers: dict[str, list[Callable[[Any], None]]] = {}
        self.url = ""
        self.mouse = _Mouse()
        self.goto_calls: list[tuple[str, str, int]] = []
        self.evaluate_calls = 0
        self.closed = False

    def on(self, name: str, callback: Callable[[Any], None]) -> None:
        self.handlers.setdefault(name, []).append(callback)

    async def goto(self, url: str, *, wait_until: str, timeout: int) -> _NavigationResponse:
        self.url = url
        self.goto_calls.append((url, wait_until, timeout))
        for request, response in self.events:
            for callback in self.handlers.get("request", []):
                callback(request)
            for callback in self.handlers.get("response", []):
                callback(response)
        return _NavigationResponse()

    def locator(self, selector: str) -> _Body:
        assert selector == "body"
        return _Body()

    async def content(self) -> str:
        return _initial_html()

    async def wait_for_timeout(self, milliseconds: int) -> None:
        assert milliseconds > 0
        await asyncio.sleep(0)

    async def evaluate(self, *_args: object, **_kwargs: object) -> object:
        self.evaluate_calls += 1
        raise AssertionError("frontend observation must not synthesize requests")

    async def close(self) -> None:
        self.closed = True


class _BrowserContext:
    def __init__(self, page: _Page) -> None:
        self.page = page
        self.closed = False
        self.runtime_state_reads = 0

    async def new_page(self) -> _Page:
        return self.page

    async def cookies(self) -> object:
        self.runtime_state_reads += 1
        raise AssertionError("ICA cookies must never be inspected")

    async def storage_state(self) -> object:
        self.runtime_state_reads += 1
        raise AssertionError("ICA browser storage must never be inspected")

    async def close(self) -> None:
        self.closed = True


class _Browser:
    def __init__(self, context: _BrowserContext) -> None:
        self.context = context
        self.new_context_kwargs: list[dict[str, object]] = []
        self.closed = False

    async def new_context(self, **kwargs: object) -> _BrowserContext:
        self.new_context_kwargs.append(kwargs)
        return self.context

    async def close(self) -> None:
        self.closed = True


class _Chromium:
    def __init__(self, browser: _Browser) -> None:
        self.browser = browser
        self.launch_kwargs: list[dict[str, object]] = []

    async def launch(self, **kwargs: object) -> _Browser:
        self.launch_kwargs.append(kwargs)
        return self.browser


class _Playwright:
    def __init__(self, chromium: _Chromium) -> None:
        self.chromium = chromium
        self.stopped = False

    async def stop(self) -> None:
        self.stopped = True


class _Manager:
    def __init__(self, playwright: _Playwright) -> None:
        self.playwright = playwright
        self.start_calls = 0

    async def start(self) -> _Playwright:
        self.start_calls += 1
        return self.playwright


class _BrowserRuntime:
    def __init__(self, responses: list[_ObservedResponse]) -> None:
        events = [(response.request, response) for response in responses]
        self.page = _Page(events)
        self.context = _BrowserContext(self.page)
        self.browser = _Browser(self.context)
        self.chromium = _Chromium(self.browser)
        self.playwright = _Playwright(self.chromium)
        self.manager = _Manager(self.playwright)

    def factory(self) -> _Manager:
        return self.manager


def _transport(runtime: _BrowserRuntime) -> IcaOnlineBrowserTransport:
    return IcaOnlineBrowserTransport(
        context_mappings={REGION_ID: RETAILER_ID},
        requests_per_second=1000,
        max_categories=1,
        max_pages_per_category=1,
        max_batches_per_page=1,
        product_batch_size=None,
        allow_full_crawl=False,
        allowed_context_ids=(REGION_ID,),
        max_concurrency=1,
        allow_category_proof=True,
        frontend_settle_ms=1,
        frontend_max_scrolls=2,
        playwright_factory=runtime.factory,
    )


@pytest.mark.asyncio
async def test_frontend_owned_requests_are_captured_and_replayed_without_runtime_state(
    tmp_path: Path,
) -> None:
    page_payload, batch_payload = _payloads()
    page_request = _ObservedRequest(method="GET", url=PAGE_URL)
    batch_request = _ObservedRequest(
        method="PUT",
        url=BATCH_URL,
        post_data_json=[PRODUCT_B, PRODUCT_C],
    )
    page_response = _ObservedResponse(
        request=page_request,
        status=200,
        content_type="application/json; charset=utf-8",
        payload=page_payload,
    )
    batch_response = _ObservedResponse(
        request=batch_request,
        status=200,
        content_type="application/json",
        payload=batch_payload,
    )
    runtime = _BrowserRuntime([page_response, batch_response])
    transport = _transport(runtime)
    try:
        raw = await transport.observe_category_frontend(REGION_ID, CATEGORY_ID)
    finally:
        await transport.aclose()

    assert page_request.method == "GET"
    assert page_request.url == PAGE_URL
    assert batch_request.method == "PUT"
    assert batch_request.url == BATCH_URL
    assert batch_request._post_data_json == [PRODUCT_B, PRODUCT_C]
    assert batch_request.post_data_reads == 1
    assert page_request.header_reads == batch_request.header_reads == 0
    assert page_response.json_calls == batch_response.json_calls == 1
    assert page_response.header_reads == batch_response.header_reads == ["content-type"]
    assert runtime.page.evaluate_calls == 0
    assert runtime.context.runtime_state_reads == 0
    assert runtime.chromium.launch_kwargs == [{"headless": False}]
    assert runtime.browser.new_context_kwargs == [{}]
    assert runtime.page.closed
    assert runtime.context.closed
    assert runtime.browser.closed
    assert runtime.playwright.stopped

    page_document = next(
        document for document in raw.documents if document.kind == ICA_PRODUCT_PAGE_KIND
    )
    batch_document = next(
        document for document in raw.documents if document.kind == ICA_PRODUCT_BATCH_KIND
    )
    assert page_document.method == "GET"
    assert page_document.url == f"{API_BASE}/product-pages"
    assert page_document.http_status == 200
    assert batch_document.method == "PUT"
    assert batch_document.url == BATCH_URL
    assert batch_document.http_status == 200
    assert json.loads(batch_document.query["requested_product_ids"]) == [
        PRODUCT_B,
        PRODUCT_C,
    ]
    assert batch_document.query["observed_batch_size"] == "2"
    assert batch_document.query["frontend_observed"] == "true"
    assert transport.product_batch_size is None

    store = FilesystemRawSnapshotStore(tmp_path / "raw")
    records = store.save_batch(raw, snapshot_id="frontend-observation")
    retained = "\n".join(
        [
            *(document.payload.decode("utf-8") for document in raw.documents),
            *(json.dumps(document.query, sort_keys=True) for document in raw.documents),
            *(store.load(record).decode("utf-8") for record in records),
        ]
    )
    assert PRODUCT_A in retained
    for forbidden in (
        "visitor-runtime-secret",
        "session-runtime-secret",
        "tracking-runtime-secret",
    ):
        assert forbidden not in retained

    # The replay function owns no transport and must leave the closed browser
    # runtime entirely untouched.
    before = (
        runtime.manager.start_calls,
        page_response.json_calls,
        batch_response.json_calls,
    )
    replayed = reconcile_category_proof(
        raw,
        region_id=REGION_ID,
        category_id=CATEGORY_ID,
    )
    after = (
        runtime.manager.start_calls,
        page_response.json_calls,
        batch_response.json_calls,
    )
    assert after == before
    assert replayed.catalog_completion == raw.catalog_completion
    assert replayed.catalog_completion is not None
    assert replayed.catalog_completion.unique_products == 3


@pytest.mark.asyncio
async def test_frontend_challenge_stops_without_body_or_runtime_state_capture() -> None:
    request = _ObservedRequest(method="GET", url=PAGE_URL)
    response = _ObservedResponse(
        request=request,
        status=202,
        content_type="text/html; charset=utf-8",
        payload={
            "challenge": "Human Verification",
            "sessionId": "challenge-runtime-secret",
        },
    )
    runtime = _BrowserRuntime([response])
    transport = _transport(runtime)
    try:
        with pytest.raises(ConnectorFetchError) as captured:
            await transport.observe_category_frontend(REGION_ID, CATEGORY_ID)
    finally:
        await transport.aclose()

    assert response.json_calls == 0
    assert runtime.page.mouse.wheel_calls == []
    assert runtime.page.evaluate_calls == 0
    assert runtime.context.runtime_state_reads == 0
    assert runtime.manager.start_calls == 1
    assert runtime.page.closed
    assert runtime.context.closed
    assert runtime.browser.closed
    assert runtime.playwright.stopped

    partial = captured.value.partial_batch
    diagnostic = partial.documents[-1]
    assert diagnostic.http_status == 202
    assert diagnostic.json_payload() == {
        "classification": "access_challenge",
        "http_status": 202,
        "observed_content_type": "text/html",
        "schema": "ica-online-transport-stop-v1",
    }
    retained = "\n".join(document.payload.decode("utf-8") for document in partial.documents)
    assert "challenge-runtime-secret" not in retained
    assert "Human Verification" not in retained
