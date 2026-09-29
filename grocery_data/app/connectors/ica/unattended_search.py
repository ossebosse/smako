"""Optional, anonymous frontend transport. Never submits a retailer API request.

Only ICA's normal UI issues search/continuation/batch requests. This diagnostic
reuses the existing online page/batch models and product parser and is absent
from source registration. A bounded or blocked run cannot become a candidate.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.parse import parse_qs, urlsplit

from grocery_data.app.connectors.ica.access_diagnostics import (
    AccessDiagnostics,
    browser_runtime,
    public_error_markers,
)
from grocery_data.app.connectors.ica.online_catalog_browser_transport import (
    IcaOnlineBrowserTransport,
    _challenge_marker,
)
from grocery_data.app.connectors.ica.online_catalog_models import (
    IcaBatchResult,
    IcaOnlineSchemaError,
    IcaProductPage,
)
from grocery_data.app.connectors.ica.online_catalog_parser import IcaOnlineCatalogParser
from grocery_data.app.domain import Chain, CoverageLevel, PriceContextType, SourceStore
from grocery_data.app.services.ica_browser_price_evaluation import adapt_public_browser_product

STORE_ID = "1088004"
STORE_URL = "https://handlaprivatkund.ica.se/stores/1088004"
HOST = "handlaprivatkund.ica.se"
API_PREFIX = "/stores/1088004/api/webproductpagews/v6/"
_UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.IGNORECASE)
_PRODUCT_FIELDS = frozenset({
    "productId", "retailerProductId", "type", "name", "brand", "countryOfOrigin",
    "available", "isInCurrentCatalog", "packSizeDescription", "price", "unitPrice",
    "categoryPath", "gtin", "ean", "size",
})
_CONDITION_FIELDS = frozenset({
    "featuredProductCampaign", "campaign", "campaigns", "promotion", "promotions",
    "memberPrice", "deposit", "depositPrice", "maximumQuantity", "purchaseLimit",
})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def public_product(row: dict) -> dict:
    """Whitelist catalogue values; preserve unreviewed condition *names* only."""
    projected = {}
    conditions = sorted(key for key in _CONDITION_FIELDS if row.get(key) is not None)
    for key in _PRODUCT_FIELDS - {"price", "unitPrice", "size", "categoryPath"}:
        if key not in row:
            continue
        if isinstance(row[key], str | int | float | bool) or row[key] is None:
            projected[key] = row[key]
        else:
            conditions.append(key + ".unexpected_type")

    def bounded(value, allowed, path):
        if value is None:
            return None
        if not isinstance(value, dict):
            conditions.append(path + ".unexpected_type")
            return None
        extra = set(value) - set(allowed)
        conditions.extend(path + "." + key for key in sorted(extra))
        result = {}
        for key, nested in allowed.items():
            if key not in value:
                continue
            child = value[key]
            if nested is not None:
                result[key] = bounded(child, nested, path + "." + key)
            elif isinstance(child, str | int | float | bool) or child is None:
                result[key] = child
            else:
                conditions.append(path + "." + key + ".unexpected_type")
        return result

    money = {"amount": None, "currency": None}
    for field, contract in {
        "price": (money if not isinstance(row.get("price"), dict)
                  or "current" not in row["price"] else {
                      "current": money, "unit": {"label": None, "current": money}}),
        "unitPrice": {**money, "unit": None, "unitName": None,
                      "unitCode": None, "priceUnit": None},
        "size": {"value": None},
    }.items():
        if field in row:
            projected[field] = bounded(row[field], contract, field)
    if "categoryPath" in row:
        if isinstance(row["categoryPath"], list) and all(
            isinstance(value, str) for value in row["categoryPath"]
        ):
            projected["categoryPath"] = row["categoryPath"]
        else:
            conditions.append("categoryPath.unreviewed_shape")
    if conditions:
        projected["unreviewedConditionFields"] = sorted(set(conditions))
    return projected


def observed_request(request) -> dict | None:
    """Project actual method and public query/body identities, never headers."""
    url = urlsplit(request.url)
    if url.scheme != "https" or url.hostname != HOST or url.username or url.password:
        return None
    if url.path not in {API_PREFIX + "product-pages/search", API_PREFIX + "products"}:
        return None
    query = parse_qs(url.query, keep_blank_values=True)
    safe_query = {key: values for key, values in query.items() if key in {
        "q", "maxPageSize", "maxProductsToDecorate", "includeAdditionalPageInfo", "tag",
    }}
    if query.get("pageToken"):
        safe_query["continuationHash"] = [sha256(
            query["pageToken"][0].encode()).hexdigest()]
    result = {"method": request.method, "path": url.path, "query": safe_query}
    if url.path.endswith("/products"):
        # Read the body only on this already verified public catalogue route.
        try:
            body = request.post_data_json
        except (ValueError, TypeError):
            body = None
        if not isinstance(body, list) or not body or any(
            not isinstance(value, str) or not _UUID.fullmatch(value) for value in body
        ):
            raise IcaOnlineSchemaError("observed product batch body is not public UUID array")
        result["requestedProductIds"] = body
    return result


class SearchEvidence:
    """Fail-closed identity/continuation accounting, independent of the browser."""

    def __init__(self, query: str):
        self.query = query
        self.ids: set[str] = set()
        self.rows: dict[str, dict] = {}
        self.observed: dict[str, str] = {}
        self.fingerprints: dict[str, str] = {}
        self.declared: int | None = None
        self.pages: dict[str | None, str | None] = {}
        self.duplicates = 0
        self.events: list[dict] = []

    def add(self, request: dict, payload: dict, *, observed_at: str, status: int) -> None:
        if status != 200:
            raise IcaOnlineSchemaError("non-success product response cannot provide prices")
        if request["path"].endswith("/search"):
            if request["query"].get("q") != [self.query]:
                raise IcaOnlineSchemaError("search response belongs to another query")
            page = IcaProductPage.from_payload(payload, category_id="search:" + self.query)
            if page.missed_promotions:
                raise IcaOnlineSchemaError("search contains unresolved promotion groups")
            if page.declared_product_count is not None:
                if self.declared is not None and self.declared != page.declared_product_count:
                    raise IcaOnlineSchemaError("search total changed during collection")
                self.declared = page.declared_product_count
            previous = request["query"].get("continuationHash", [None])[0]
            if previous in self.pages and self.pages[previous] != page.next_page_token_hash:
                raise IcaOnlineSchemaError("conflicting repeated search page")
            self.pages[previous] = page.next_page_token_hash
            self.ids.update(page.ordered_product_ids)
            products = page.decorated_products
            page_fields = {"declaredProductCount": page.declared_product_count,
                           "orderedProductIds": list(page.ordered_product_ids),
                           "nextPageHash": page.next_page_token_hash, "terminal": page.terminal}
        else:
            batch = IcaBatchResult.from_payload(
                payload, requested_product_ids=request["requestedProductIds"])
            if batch.missed_promotions or batch.restricted_groups:
                raise IcaOnlineSchemaError("batch contains unresolved/restricted promotions")
            products = batch.products
            page_fields = {"returnedProductIds": list(batch.product_ids)}
        for original in products:
            row = public_product(original)
            identity = row["productId"]
            fingerprint = sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
            if identity in self.rows:
                if self.fingerprints[identity] != fingerprint:
                    raise IcaOnlineSchemaError("conflicting duplicate product purchase semantics")
                self.duplicates += 1
                continue
            self.rows[identity] = row
            self.fingerprints[identity] = fingerprint
            self.observed[identity] = observed_at
        self.events.append({**request, "status": status, "observedAt": observed_at,
                            "page": page_fields,
                            "products": [public_product(row) for row in products]})

    def complete(self) -> bool:
        if self.declared is None or len(self.ids) != self.declared or not self.pages:
            return False
        cursor, visited = None, set()
        while cursor in self.pages and cursor not in visited:
            visited.add(cursor)
            cursor = self.pages[cursor]
            if cursor is None:
                return len(visited) == len(self.pages) and self.ids <= self.rows.keys()
        return False

    def result(self) -> dict:
        store = SourceStore(
            chain=Chain.ICA, external_id=STORE_ID, name="Maxi ICA Gunnesbo Online",
            city="Lund", online_shopping=True, coverage=CoverageLevel.PARTIAL_CATALOG,
            price_context_type=PriceContextType.ONLINE_STORE,
            physical_store_external_id=STORE_ID, raw_reference=STORE_URL,
        )
        accepted, rejected, missing_price = [], [], []
        for identity in sorted(self.ids & self.rows.keys()):
            row = self.rows[identity]
            if not row.get("price"):
                missing_price.append(identity)
                continue
            try:
                if row.get("unreviewedConditionFields"):
                    raise ValueError("unreviewed product price conditions")
                if "size" in row:
                    row = adapt_public_browser_product(row)
                if not isinstance(row["price"], dict) or set(row["price"]) != {
                    "amount", "currency"
                }:
                    raise ValueError("unreviewed ordinary price schema")
                product = IcaOnlineCatalogParser().parse_product(
                    row, store=store, reference=STORE_URL,
                    fetched_at=datetime.fromisoformat(self.observed[identity]),
                )
                if product.regular_price is None:
                    raise ValueError("no purchasable ordinary price")
                if product.package_quantity is None or product.package_unit is None:
                    raise ValueError("unknown exact purchase package")
                accepted.append(product.model_copy(update={"source_fields": {
                    **product.source_fields, "transport": "anonymous_frontend_observer",
                    "observation_basis": "live_product_response_received_at",
                    "price_change_time": None, "deposit_status": "not_verified",
                    "shared_candidate_approved": False,
                }}).model_dump(mode="json"))
            except (ValueError, TypeError, KeyError) as exc:
                rejected.append({"productId": identity, "reason": str(exc)})
        return {
            "query": self.query, "declared_total": self.declared,
            "search_complete": self.complete(), "catalog_complete": False,
            "product_ids": sorted(self.ids), "fetched_count": len(self.rows),
            "accepted_count": len(accepted), "rejected_count": len(rejected),
            "priced_ids": [p["external_product_id"] for p in accepted],
            "without_price_ids": missing_price,
            "unresolved_ids": sorted(self.ids - self.rows.keys()),
            "orphan_response_ids": sorted(self.rows.keys() - self.ids),
            "exact_duplicate_count": self.duplicates,
            "products": accepted, "rejected": rejected, "network": self.events,
        }


class IcaUnattendedSearchTransport:
    """Normal UI, new anonymous Chromium context, bounded frontend scrolling."""

    def __init__(self, *, max_scrolls: int = 250, settle_ms: int = 1000,
                 playwright_factory=None, browser_channel: str | None = None,
                 access_diagnostics: bool = False):
        if max_scrolls < 1 or settle_ms < 250:
            raise ValueError("invalid search bounds")
        self.max_scrolls, self.settle_ms = max_scrolls, settle_ms
        if browser_channel not in {None, "chromium"}:
            raise ValueError("only default shell or bundled chromium is supported")
        self.browser_channel = browser_channel
        self.access_diagnostics = access_diagnostics
        self.factory = playwright_factory or IcaOnlineBrowserTransport._default_playwright_factory

    async def collect(self, queries: list[str]) -> dict:
        if not queries or queries[0] != "mjölk" or any(
            not value.strip() or len(value) > 80 for value in queries
        ):
            raise ValueError("first bounded query must be mjölk; invalid query list")
        started, clock = _now(), monotonic()
        result = {"schema": "ica-unattended-search-v1", "store_id": STORE_ID,
                  "channel": "online_price", "promoted": False,
                  "started_at": started, "status": "blocked", "searches": [],
                  "documents": [], "response_errors": [], "search_controls": [], "blocker": None,
                  "frontend_errors": [], "initialization": {"new_anonymous_context": True,
                  "consent_action": "not_present_or_not_matched"}}
        diagnostics = AccessDiagnostics()
        browser_config = None
        runtime = browser = context = page = None
        tasks: list[asyncio.Task] = []
        current: SearchEvidence | None = None
        stop: dict | None = None
        stage = "browser_launch"

        async def observe(response, evidence: SearchEvidence | None):
            nonlocal stop
            if evidence is None:
                return
            request = observed_request(response.request)
            if request is None:
                return
            received = _now()
            if response.status != 200:
                stop = {"stage": "product_request", **request, "status": response.status,
                        "classification": "access_stop" if response.status in {
                            202, 401, 403, 405, 429} else "http_error"}
                if self.access_diagnostics:
                    stop.update(await diagnostics.error(response))
                return
            payload = await response.json()
            try:
                evidence.add(request, payload, observed_at=received, status=response.status)
            except IcaOnlineSchemaError:
                result["response_errors"].append({
                    **request, "status": response.status, "observedAt": received,
                    "public_schema": sorted(payload) if isinstance(payload, dict) else "non_object",
                    "group_count": len(payload.get("productGroups", []))
                    if isinstance(payload, dict) else None,
                })
                raise

        async def drain():
            for _ in range(10):
                if not tasks:
                    return
                pending = list(tasks)
                tasks.clear()
                await asyncio.wait_for(asyncio.gather(*pending), timeout=30)
            if tasks:
                raise IcaOnlineSchemaError("bounded response draining did not quiesce")

        async def check_document(response):
            nonlocal stop
            url = urlsplit(page.url)
            if url.hostname != HOST or not url.path.startswith("/stores/1088004"):
                raise ValueError("browser navigation left verified store context")
            status = response.status if response is not None else 0
            result["documents"].append({"method": response.request.method if response else None,
                                        "path": url.path, "status": status,
                                        "observed_at": _now()})
            text = await page.locator("body").inner_text(timeout=30000)
            if status >= 400 or status in {0, 202} or _challenge_marker(text):
                stop = {"stage": stage, "path": url.path, "status": status,
                        "classification": "document_access_stop"}
                if self.access_diagnostics and response is not None:
                    stop.update(await diagnostics.error(response))

        def frontend_error(kind, value):
            if len(result["frontend_errors"]) < 30:
                result["frontend_errors"].append({"stage": stage, "kind": kind,
                    "public_error_markers": public_error_markers(value)})

        try:
            runtime = await self.factory().start()
            launch_options = {"headless": True}
            if self.browser_channel:
                launch_options["channel"] = self.browser_channel
                # Full Chromium's Crashpad requires writable XDG storage in
                # the read-only scheduler image. Own disposable configuration,
                # no inherited user profile and no disabling crash/security features.
                browser_config = TemporaryDirectory(prefix="ica-browser-config-")
                launch_options["env"] = {**os.environ,
                    "XDG_CONFIG_HOME": browser_config.name,
                    "XDG_CACHE_HOME": browser_config.name + "/cache"}
            browser = await runtime.chromium.launch(**launch_options)
            result["browser_runtime"] = await browser_runtime(
                browser, channel=self.browser_channel)
            result["browser_runtime"]["ephemeral_writable_xdg"] = bool(browser_config)
            context = await browser.new_context()
            page = await context.new_page()
            if self.access_diagnostics:
                await diagnostics.start(context, page)
                page.on("pageerror", lambda error: frontend_error("pageerror", str(error)))
                page.on("console", lambda message: frontend_error("console_error", message.text)
                        if message.type == "error" else None)
            # Event closure fixes query ownership at response arrival, even if a
            # later query starts while response body decoding is still running.
            page.on("response", lambda response: tasks.append(
                asyncio.create_task(observe(response, current))))
            stage = "store_document"
            response = await page.goto(STORE_URL, wait_until="domcontentloaded", timeout=45000)
            await check_document(response)
            if stop is None:
                await page.wait_for_timeout(2000)
                # Consent is normal public UI, not login or challenge handling.
                decline = page.get_by_role("button", name=re.compile(
                    r"^(Avvisa alla|Neka alla|Endast nödvändiga)$", re.IGNORECASE))
                if await decline.count() == 1 and await decline.is_visible():
                    await decline.click()
                    result["initialization"]["consent_action"] = "decline_optional"
            for query in dict.fromkeys(queries):
                if stop is not None:
                    break
                current = SearchEvidence(query)
                stage = "search_ui"
                # Inspect actual form controls; do not manufacture an API/URL.
                await page.wait_for_function("document.querySelectorAll('input').length > 0",
                                             timeout=20000)
                controls = await page.locator("input").evaluate_all("""elements => elements.map(
                    (e, index) => ({index, type:e.type, placeholder:e.getAttribute('placeholder'),
                     ariaLabel:e.getAttribute('aria-label'), role:e.getAttribute('role'),
                     visible:!!(e.offsetWidth || e.offsetHeight || e.getClientRects().length)}))""")
                result["search_controls"] = controls
                matching = [item for item in controls if item["visible"] and (
                    item["type"] == "search" or "sök" in (
                        str(item["placeholder"] or "") + " " + str(item["ariaLabel"] or "")
                    ).casefold())]
                if len(matching) != 1:
                    raise ValueError("normal search control is absent or ambiguous")
                inputs = page.locator("input").nth(matching[0]["index"])
                await inputs.fill(query)
                await inputs.press("Enter")
                for _ in range(self.max_scrolls + 1):
                    await page.wait_for_timeout(self.settle_ms)
                    await drain()
                    if stop or current.complete():
                        break
                    stage = "frontend_pagination"
                    # Scrolling lets the retailer runtime choose actual batch
                    # sizes and continuation tokens. We never issue fetch().
                    await page.mouse.wheel(0, 1600)
                    if _challenge_marker(await page.locator("body").inner_text()):
                        stop = {"stage": stage, "classification": "visible_access_stop"}
                        break
                result["searches"].append(current.result())
                if not current.complete() and stop is None:
                    stop = {"stage": stage, "classification": "bounded_incomplete_search"}
            result["blocker"] = stop
            if stop is None and result["searches"] and all(
                search["search_complete"] for search in result["searches"]
            ):
                result["status"] = "collected"
        except Exception as exc:  # noqa: BLE001 - diagnostic boundary excludes secret-bearing errors
            # Playwright errors can contain launch/session details. Persist only
            # class + stage. Catalogue validation messages contain public fields.
            result["blocker"] = {"stage": stage, "classification": type(exc).__name__}
            if isinstance(exc, IcaOnlineSchemaError | ValueError):
                result["blocker"]["reason"] = str(exc)
            if current is not None and not result["searches"]:
                result["searches"].append(current.result())
        finally:
            try:
                await drain()
            except Exception as exc:  # noqa: BLE001 - cleanup errors invalidate a diagnostic candidate
                result["status"] = "blocked"
                result["blocker"] = {"stage": "final_response_drain",
                                     "classification": type(exc).__name__}
            if stop is not None:
                result["status"] = "blocked"
                result["blocker"] = stop
            if current is not None:
                # Recompute after all observed responses have been drained;
                # never export the stale pre-drain view of the last search.
                final_search = current.result()
                if result["searches"] and result["searches"][-1]["query"] == current.query:
                    result["searches"][-1] = final_search
                else:
                    result["searches"].append(final_search)
            for resource, method in ((page, "close"), (context, "close"),
                                     (browser, "close"), (runtime, "stop")):
                if resource is not None:
                    with suppress(Exception):
                        await getattr(resource, method)()
            await diagnostics.close()
            if browser_config is not None:
                browser_config.cleanup()
        result["finished_at"] = _now()
        result["runtime_seconds"] = round(monotonic() - clock, 3)
        result["candidate_validated"] = False
        result["automatic_schedule_trigger"] = False
        # Cross-search deduplication keeps the earliest real observation. A
        # changed price within this run blocks the candidate rather than wins.
        products, conflicts, overlap = {}, [], 0
        for search in result["searches"]:
            for product in search["products"]:
                identity = product["external_product_id"]
                if identity in products:
                    old = products[identity]
                    fields = ("regular_price", "package_quantity", "package_unit", "gtin")
                    if any(old.get(field) != product.get(field) for field in fields):
                        conflicts.append(identity)
                    overlap += 1
                else:
                    products[identity] = product
        result["products"] = list(products.values())
        result["overlapping_search_products"] = overlap
        result["conflicting_search_products"] = sorted(set(conflicts))
        result["candidate_validated"] = (
            result["status"] == "collected" and bool(products) and not conflicts
            and all(not s["rejected"] and not s["without_price_ids"]
                    and not s["orphan_response_ids"]
                    for s in result["searches"])
        )
        return result
