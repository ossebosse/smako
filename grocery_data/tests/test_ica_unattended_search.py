"""Synthetic traversal fixtures; monetary examples are never global data."""
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from grocery_data.app.connectors.ica.online_catalog_models import IcaOnlineSchemaError
from grocery_data.app.connectors.ica.unattended_search import (
    API_PREFIX,
    IcaUnattendedSearchTransport,
    SearchEvidence,
    observed_request,
    public_product,
)

FIXTURES = Path(__file__).parents[1] / "app/connectors/ica/fixtures"
OBSERVED = "2026-09-15T09:00:00+00:00"


def row(index=1):
    value = json.loads((FIXTURES / "online_v6_product_batch.json").read_text("utf8"))[
        "products"][0]
    value["productId"] = str(UUID(int=index))
    value["retailerProductId"] = str(index)
    return value


def request(kind="search"):
    return {"path": API_PREFIX + ("product-pages/search" if kind == "search" else "products"),
            "method": "GET" if kind == "search" else "PUT", "query": {"q": ["mjölk"]}}


def page(count=3, decorated=1):
    return {"totalProducts": count, "additionalPageInfo": {"metadata": {"terminal": True}},
            "productGroups": [{"decoratedProducts": [row(i) for i in range(1, decorated + 1)],
                               "otherProductIds": [str(UUID(int=i)) for i in range(
                                   decorated + 1, count + 1)]}]}


def batch(evidence, start, end):
    rows = [row(i) for i in range(start, end + 1)]
    req = {**request("batch"), "requestedProductIds": [r["productId"] for r in rows]}
    evidence.add(req, {"products": rows, "missedPromotions": [], "restrictedGroups": {}},
                 observed_at=OBSERVED, status=200)


def test_dynamic_total_and_frontend_batches_beyond_first_50():
    evidence = SearchEvidence("mjölk")
    evidence.add(request(), page(83, 50), observed_at=OBSERVED, status=200)
    assert not evidence.complete()
    assert len(evidence.result()["unresolved_ids"]) == 33
    batch(evidence, 51, 83)
    result = evidence.result()
    assert result["search_complete"]
    assert result["accepted_count"] == result["declared_total"] == 83
    assert result["without_price_ids"] == result["rejected"] == []
    assert all(p["fetched_at"] == OBSERVED.replace("+00:00", "Z") for p in result["products"])
    assert not result["catalog_complete"]


def test_replay_preserves_earliest_observation_and_classifies_duplicates():
    evidence = SearchEvidence("mjölk")
    evidence.add(request(), page(), observed_at=OBSERVED, status=200)
    batch(evidence, 2, 3)
    previous = evidence.result()
    batch(evidence, 2, 3)
    after = evidence.result()
    assert after["exact_duplicate_count"] == 2
    assert after["products"] == previous["products"]


def test_conflicting_duplicate_does_not_win_by_latest_observation():
    evidence = SearchEvidence("mjölk")
    evidence.add(request(), page(), observed_at=OBSERVED, status=200)
    changed = page()
    changed["productGroups"][0]["decoratedProducts"][0]["price"]["amount"] = 999
    with pytest.raises(IcaOnlineSchemaError, match="conflicting duplicate"):
        evidence.add(request(), changed, observed_at=OBSERVED, status=200)


def test_missing_price_is_not_sold_out_or_zero_and_bad_package_rejected():
    evidence = SearchEvidence("mjölk")
    payload = page(3, 3)
    rows = payload["productGroups"][0]["decoratedProducts"]
    rows[0]["price"] = None
    rows[1]["packSizeDescription"] = "ca 1 kg"
    rows[2]["featuredProductCampaign"] = {"personal": True}
    evidence.add(request(), payload, observed_at=OBSERVED, status=200)
    result = evidence.result()
    assert result["search_complete"]
    assert result["accepted_count"] == 0
    assert len(result["without_price_ids"]) == 1
    assert result["rejected_count"] == 2


@pytest.mark.parametrize("change", ["total", "query", "missing_batch", "continuation"])
def test_incomplete_or_changed_search_never_complete(change):
    evidence = SearchEvidence("mjölk")
    payload = page(3, 3)
    req = request()
    if change == "total":
        payload["totalProducts"] = 4
    elif change == "query":
        req["query"]["q"] = ["annan"]
    elif change == "missing_batch":
        payload = page(3, 1)
    else:
        payload["additionalPageInfo"]["metadata"] = {"nextPageToken": "fixture-next"}
    if change == "query":
        with pytest.raises(IcaOnlineSchemaError, match="another query"):
            evidence.add(req, payload, observed_at=OBSERVED, status=200)
    else:
        evidence.add(req, payload, observed_at=OBSERVED, status=200)
        assert not evidence.complete()


def test_only_public_catalogue_fields_are_retained():
    raw = {**row(), "quantityInBasket": 7, "customer": {"email": "private"},
           "sessionToken": "secret", "featuredProductCampaign": {"customer": "private"}}
    sanitized = public_product(raw)
    assert "private" not in json.dumps(sanitized)
    assert "secret" not in json.dumps(sanitized)
    assert sanitized["unreviewedConditionFields"] == ["featuredProductCampaign"]
    raw["price"]["customer"] = {"email": "private", "secret": "must-not-persist"}
    assert "must-not-persist" not in json.dumps(public_product(raw))
    assert "price.customer" in public_product(raw)["unreviewedConditionFields"]
    raw["name"] = {"customer": {"email": "nested-private"}}
    assert "nested-private" not in json.dumps(public_product(raw))
    assert "name.unexpected_type" in public_product(raw)["unreviewedConditionFields"]


def test_saved_real_public_projection_reuses_existing_adapter():
    saved = json.loads((FIXTURES / "browser_public_prices_20260915.json").read_text("utf8"))
    payload = page(1, 1)
    payload["productGroups"][0]["decoratedProducts"] = [saved["products"][0]]
    evidence = SearchEvidence("mjölk")
    evidence.add(request(), payload, observed_at=OBSERVED, status=200)
    product = evidence.result()["products"][0]
    assert product["regular_price"] == "15.90"
    assert product["package_quantity"] == "1500.0"
    assert product["fetched_at"] == OBSERVED.replace("+00:00", "Z")


def test_observed_method_and_body_are_not_guessed_or_secrets_retained():
    observed = observed_request(SimpleNamespace(
        url="https://handlaprivatkund.ica.se" + API_PREFIX
            + "products?sessionToken=secret", method="POST", post_data_json=[str(UUID(int=1))]))
    assert observed["method"] == "POST"
    assert observed["requestedProductIds"] == [str(UUID(int=1))]
    assert "secret" not in json.dumps(observed)
    assert observed_request(SimpleNamespace(url="https://handlaprivatkund.ica.se/stores/1088004"
                                          "/api/cart/v1/carts/active", method="GET")) is None


async def test_document_403_stops_before_search_and_discards_fresh_context():
    class Resource:
        closed = False

        async def close(self):
            self.closed = True

    class Page(Resource):
        url = "https://handlaprivatkund.ica.se/stores/1088004"

        def on(self, *_):
            pass

        async def goto(self, *_args, **_kwargs):
            return SimpleNamespace(status=403, request=SimpleNamespace(method="GET"))

        def locator(self, selector):
            assert selector == "body"
            return self

        async def inner_text(self, **_kwargs):
            return "Access denied"

    the_page = Page()
    context, browser = Resource(), Resource()

    async def new_page():
        return the_page

    async def new_context():
        return context

    async def launch(**kwargs):
        assert kwargs == {"headless": True}
        return browser

    context.new_page, browser.new_context = new_page, new_context
    runtime = Resource()
    runtime.chromium = SimpleNamespace(launch=launch)
    runtime.stop = runtime.close

    async def start():
        return runtime

    transport = IcaUnattendedSearchTransport(
        playwright_factory=lambda: SimpleNamespace(start=start))
    result = await transport.collect(["mjölk"])
    assert result["blocker"]["stage"] == "store_document"
    assert result["blocker"]["status"] == 403
    assert result["searches"] == []
    assert not result["candidate_validated"]
    assert all(resource.closed for resource in (the_page, context, browser, runtime))


@pytest.mark.parametrize("product_status", [200, 403, "late403", "lateConflict"])
async def test_normal_text_search_then_real_frontend_events_or_access_stop(
    product_status, monkeypatch,
):
    """UI fixture uses the observed text/placeholder, not invented search type."""
    closed = []
    response_handler = None
    scroll_count = 0

    class Response:
        def __init__(self, kind="search"):
            self.status = product_status if isinstance(product_status, int) else 200
            self.request = SimpleNamespace(
                url="https://handlaprivatkund.ica.se" + API_PREFIX + (
                    "product-pages/search?q=mj%C3%B6lk" if kind == "search" else "products"),
                method="GET" if kind == "search" else "PUT",
                post_data_json=[str(UUID(int=i)) for i in range(51, 84)])
            self.kind = kind

        async def json(self):
            assert self.status == 200, "never read access-stop body"
            payload = page(83, 50) if self.kind == "search" else {
                "products": [row(i) for i in range(51, 84)],
                "missedPromotions": [], "restrictedGroups": {}}
            if getattr(self, "conflict", False):
                payload["products"][0]["price"]["amount"] = 999
            return payload

    class Page:
        url = "https://handlaprivatkund.ica.se/stores/1088004"

        def on(self, _event, handler):
            nonlocal response_handler
            response_handler = handler

        async def goto(self, *_args, **_kwargs):
            return SimpleNamespace(status=200, request=SimpleNamespace(method="GET"))

        async def close(self):
            closed.append("page")

        def locator(self, _selector):
            return self

        def get_by_role(self, *_args, **_kwargs):
            return self

        async def count(self):
            return 0

        async def inner_text(self, **_kwargs):
            return "Maxi Gunnesbo"

        async def wait_for_timeout(self, _milliseconds):
            pass

        async def wait_for_function(self, *_args, **_kwargs):
            pass

        async def evaluate_all(self, _script):
            return [{"index": 0, "type": "text", "placeholder": "Sök produkt",
                     "ariaLabel": None, "role": "combobox", "visible": True}]

        def nth(self, index):
            assert index == 0
            return self

        async def fill(self, query):
            assert query == "mjölk"

        async def press(self, key):
            assert key == "Enter"
            response_handler(Response())

        async def wheel(self, x, y):
            nonlocal scroll_count
            assert (x, y) == (0, 1600)
            scroll_count += 1
            response_handler(Response("batch"))

    the_page = Page()
    the_page.mouse = the_page

    async def new_page():
        return the_page

    async def close_context():
        closed.append("context")

    context = SimpleNamespace(new_page=new_page, close=close_context)

    async def new_context():
        return context

    async def close_browser():
        closed.append("browser")

    browser = SimpleNamespace(new_context=new_context, close=close_browser)

    async def launch(**kwargs):
        assert kwargs == {"headless": True}
        return browser

    async def stop():
        closed.append("runtime")

    runtime = SimpleNamespace(chromium=SimpleNamespace(launch=launch), stop=stop)

    async def start():
        return runtime

    if product_status in {"late403", "lateConflict"}:
        original_result = SearchEvidence.result
        injected = False

        def result_with_late_response(evidence):
            nonlocal injected
            value = original_result(evidence)
            if not injected:
                injected = True
                late = Response("batch")
                if product_status == "late403":
                    late.status = 403
                else:
                    late.conflict = True
                response_handler(late)
            return value

        monkeypatch.setattr(SearchEvidence, "result", result_with_late_response)

    result = await IcaUnattendedSearchTransport(
        playwright_factory=lambda: SimpleNamespace(start=start)).collect(["mjölk"])
    assert closed == ["page", "context", "browser", "runtime"]
    if product_status == 403:
        assert result["blocker"]["stage"] == "product_request"
        assert result["blocker"]["method"] == "GET"
        assert result["blocker"]["status"] == 403
        assert scroll_count == 0
        assert not result["candidate_validated"]
    elif product_status == 200:
        assert result["candidate_validated"]
        assert result["searches"][0]["accepted_count"] == 83
        assert scroll_count == 1
        assert len(result["products"]) == 83
        assert not result["promoted"]
    else:
        assert result["status"] == "blocked"
        assert not result["candidate_validated"]
        assert scroll_count == 1
        assert result["blocker"]["stage"] == (
            "product_request" if product_status == "late403" else "final_response_drain")
