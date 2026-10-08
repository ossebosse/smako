from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.hemkop.models import (
    HemkopCatalogPage,
    top_level_category_paths,
    validated_catalog_page,
)
from grocery_data.app.connectors.http import (
    AsyncRateLimiter,
    RetryPolicy,
    bounded_request,
    retry_after_seconds,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    RawBatch,
    RawFetch,
    SourceStore,
    TransportMetrics,
)


class HemkopHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class HemkopSourcePolicyError(RuntimeError):
    """The requested traversal is outside Hemköp's explicit REVIEW gate."""


class HemkopAccessChallenge(HemkopHttpError):
    """Ordinary public access was blocked; the current run must stop."""


class HemkopRateLimitStop(HemkopHttpError):
    """A 429 was observed; no retry or new session is permitted."""

    def __init__(
        self,
        message: str,
        raw: RawFetch,
        *,
        retry_after: float | None,
        retry_after_raw: str | None,
    ) -> None:
        super().__init__(message, raw)
        self.retry_after = retry_after
        self.retry_after_raw = retry_after_raw


class HemkopAccessChallengeFetchError(ConnectorFetchError):
    """Persistable fail-closed access-challenge result."""


class HemkopRateLimitFetchError(ConnectorFetchError):
    """Persistable fail-closed rate-limit result."""


_TRUE_VALUES = frozenset({"1", "true"})
_FALSE_VALUES = frozenset({"", "0", "false"})
_ACCESS_CHALLENGE_MARKERS = (
    b"access denied",
    b"aws waf",
    b"aws-waf",
    b"captcha",
    b"cf-chl-",
    b"cf-turnstile",
    b"human verification",
    b"/cdn-cgi/challenge-platform/",
    b"request blocked",
    b"request could not be satisfied",
    b"verify you are human",
)
_SANITIZED_ACCESS_PAYLOAD = b'{"reason":"access_challenge"}'
_SANITIZED_RATE_PAYLOAD = b'{"reason":"rate_limited"}'
_DUPLICATE_SEMANTIC_FIELDS = (
    "code",
    "ean",
    "name",
    "manufacturer",
    "priceValue",
    "salesPrice",
    "priceUnit",
    "comparePrice",
    "comparePriceUnit",
    "productLine2",
    "averageWeight",
    "incrementValue",
    "productBasketType",
    "outOfStock",
    "online",
    "potentialPromotions",
)


def _environment_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise HemkopSourcePolicyError(
        f"{name} must be one of true/false/1/0; refusing ambiguous policy value"
    )


def _configured_store_ids(value: Iterable[str] | str | None) -> frozenset[str]:
    if value is None:
        values: Iterable[str] = os.getenv("HEMKOP_STORE_EXTERNAL_IDS", "").split(",")
    elif isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    return frozenset(store_id.strip() for store_id in values if store_id.strip())


@dataclass(frozen=True, slots=True)
class HemkopOperatorCrawlPolicy:
    """Closed view of the explicit operator authority for a full crawl.

    Reading this object never creates a HTTP client and never grants authority.
    A caller must still build an exact one-store transport, whose connector-local
    policy guard is the final enforcement boundary.
    """

    allow_full_crawl: bool
    allowed_store_ids: frozenset[str]

    @classmethod
    def from_environment(cls) -> HemkopOperatorCrawlPolicy:
        return cls(
            allow_full_crawl=_environment_flag(
                "HEMKOP_ALLOW_FULL_CRAWL",
                default=False,
            ),
            allowed_store_ids=_configured_store_ids(None),
        )

    def permits(self, store_external_id: str) -> bool:
        store_id = store_external_id.strip()
        return bool(store_id and self.allow_full_crawl and store_id in self.allowed_store_ids)

    def require(self, store_external_id: str) -> str:
        store_id = store_external_id.strip()
        if not store_id:
            raise HemkopSourcePolicyError("Hemköp exact store ID must not be blank")
        if not self.allow_full_crawl:
            raise HemkopSourcePolicyError(
                "Hemköp source policy REVIEW requires explicit HEMKOP_ALLOW_FULL_CRAWL=true"
            )
        if store_id not in self.allowed_store_ids:
            raise HemkopSourcePolicyError(
                f"Hemköp store {store_id} is outside HEMKOP_STORE_EXTERNAL_IDS"
            )
        return store_id


def _looks_like_access_challenge(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return False
    if response.status_code in {401, 403, 405}:
        return True
    content_type = response.headers.get("content-type", "").casefold()
    beginning = response.content[:65536].lstrip().lower()
    return "json" not in content_type or any(
        marker in beginning for marker in _ACCESS_CHALLENGE_MARKERS
    )


def _product_semantic_fingerprint(row: dict[str, Any]) -> str:
    """Compare duplicate products without category/ranking/facet decoration."""

    return json.dumps(
        {field: row.get(field) for field in _DUPLICATE_SEMANTIC_FIELDS},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _exact_product_fingerprint(row: dict[str, Any]) -> str:
    """Canonical full-row proof for a safely removable local repeat.

    Cross-category navigation decoration is intentionally ignored by
    ``_product_semantic_fingerprint``. Within one category we can be stricter:
    every captured field must be byte-semantically equal after canonical JSON
    ordering. A price, package, promotion, availability, ranking or any other
    field change therefore remains a hard conflict.
    """

    return json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


@dataclass(slots=True)
class _DuplicateTracker:
    seen_ids: set[str]
    seen_semantic_fingerprints: dict[str, str]
    raw_rows: int = 0
    within_partition_duplicates: int = 0
    cross_partition_duplicates: int = 0
    exact_duplicates_removed: int = 0
    conflicting_duplicates: int = 0
    pagination_overlaps: int = 0

    @classmethod
    def create(cls) -> _DuplicateTracker:
        return cls(seen_ids=set(), seen_semantic_fingerprints={})

    def observe(
        self,
        row: dict[str, Any],
        *,
        category_fingerprints: dict[str, str],
        category_pages: dict[str, int],
        page_number: int,
    ) -> None:
        self.raw_rows += 1
        product_id = str(row["code"])
        semantic_fingerprint = _product_semantic_fingerprint(row)
        exact_fingerprint = _exact_product_fingerprint(row)
        if product_id in category_fingerprints:
            self.within_partition_duplicates += 1
            if category_fingerprints[product_id] != exact_fingerprint:
                self.conflicting_duplicates += 1
                raise ValueError(
                    f"Hemköp within-partition duplicate changed product fields: {product_id}"
                )
            self.exact_duplicates_removed += 1
            if category_pages[product_id] != page_number:
                self.pagination_overlaps += 1
            return
        if product_id in self.seen_ids:
            self.cross_partition_duplicates += 1
            if self.seen_semantic_fingerprints[product_id] != semantic_fingerprint:
                self.conflicting_duplicates += 1
                raise ValueError(
                    "Hemköp cross-partition duplicate changed semantic "
                    f"product fields: {product_id}"
                )
        else:
            self.seen_ids.add(product_id)
            self.seen_semantic_fingerprints[product_id] = semantic_fingerprint
        category_fingerprints[product_id] = exact_fingerprint
        category_pages[product_id] = page_number

    def classification_fields(self) -> dict[str, int]:
        if not (
            self.within_partition_duplicates
            or self.conflicting_duplicates
            or self.pagination_overlaps
        ):
            return {}
        return {
            "exact_duplicates_removed": self.exact_duplicates_removed,
            "conflicting_duplicates": self.conflicting_duplicates,
            "pagination_overlaps": self.pagination_overlaps,
        }


def reconcile_saved_catalog_completion(
    batch: RawBatch,
    *,
    expected_store_id: str,
) -> CatalogCompletion:
    """Rebuild exact Hemköp traversal evidence from immutable raw responses.

    This is deliberately a pure offline operation. It validates the category
    tree, every declared page, store facet and duplicate semantic before it can
    replace historical completion evidence during replay.
    """

    tree_documents = [document for document in batch.documents if document.kind == "category_tree"]
    if len(tree_documents) != 1:
        raise ValueError("Hemköp replay requires exactly one category tree")
    expected_paths = top_level_category_paths(tree_documents[0].payload)
    if not expected_paths:
        raise ValueError("Hemköp replay category tree has no top-level partitions")

    pages_by_path: dict[str, dict[int, RawFetch]] = {}
    for document in batch.documents:
        if document.kind != "catalog_page":
            continue
        path = urlsplit(document.url).path.strip("/")
        if not path.startswith("c/"):
            raise ValueError("Hemköp replay catalog page has an unexpected URL")
        category_path = path.removeprefix("c/")
        if category_path not in expected_paths:
            raise ValueError("Hemköp replay contains a catalog page outside the category tree")
        if document.page_number is None:
            raise ValueError("Hemköp replay catalog page lacks a page number")
        category_pages = pages_by_path.setdefault(category_path, {})
        if document.page_number in category_pages:
            raise ValueError("Hemköp replay contains duplicate page evidence")
        category_pages[document.page_number] = document

    if set(pages_by_path) != set(expected_paths):
        raise ValueError("Hemköp replay does not cover every top-level category")

    tracker = _DuplicateTracker.create()
    expected_products = 0
    expected_pages = 0
    pages_fetched = 0
    for category_path in expected_paths:
        raw_pages = pages_by_path[category_path]
        if 0 not in raw_pages:
            raise ValueError("Hemköp replay category does not start at page zero")
        parsed_pages: dict[int, HemkopCatalogPage] = {}
        for page_number, document in sorted(raw_pages.items()):
            query_page = int(document.query.get("page", page_number))
            if query_page != page_number:
                raise ValueError("Hemköp replay page query disagrees with raw metadata")
            requested_size_raw = document.query.get("size")
            requested_size = int(requested_size_raw) if requested_size_raw is not None else None
            parsed_pages[page_number] = validated_catalog_page(
                document.json_payload(),
                requested_page=page_number,
                requested_size=requested_size,
                expected_store_id=expected_store_id,
            )
        first_page = parsed_pages[0]
        if first_page.total_results == 0:
            raise ValueError("Hemköp replay contains an empty top-level partition")
        if set(parsed_pages) != set(range(first_page.number_of_pages)):
            raise ValueError("Hemköp replay category pages are not contiguous and complete")
        expected_products += first_page.total_results
        expected_pages += first_page.number_of_pages
        category_fingerprints: dict[str, str] = {}
        category_pages: dict[str, int] = {}
        for page_number, page in sorted(parsed_pages.items()):
            HemkopClient._same_page_contract(first_page, page)
            pages_fetched += 1
            for row in page.results:
                tracker.observe(
                    row,
                    category_fingerprints=category_fingerprints,
                    category_pages=category_pages,
                    page_number=page_number,
                )

    return CatalogCompletion(
        complete=True,
        limited=False,
        expected_categories=len(expected_paths),
        completed_categories=len(expected_paths),
        pages_fetched=pages_fetched,
        products_observed=len(tracker.seen_ids),
        expected_products=expected_products,
        raw_rows=tracker.raw_rows,
        unique_products=len(tracker.seen_ids),
        duplicate_products=(
            tracker.within_partition_duplicates + tracker.cross_partition_duplicates
        ),
        within_partition_duplicates=tracker.within_partition_duplicates,
        cross_partition_duplicates=tracker.cross_partition_duplicates,
        expected_pages=expected_pages,
        **tracker.classification_fields(),
    )


class HemkopClient:
    """Conservative same-origin transport for Hemköp's public storefront.

    Ordinary construction is deliberately limited to one category and one
    page.  Complete traversal requires explicit operator opt-in plus an exact
    store allowlist.  CSRF and cookie state remains inside the disposable
    ``httpx`` session and is never copied into raw evidence.
    """

    connector_version = "hemkop-v1"
    default_base_url = "https://www.hemkop.se"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        page_size: int = 30,
        max_categories: int | None = 1,
        max_pages_per_category: int | None = 1,
        detail_enrichment_limit: int | None = 0,
        allow_full_crawl: bool | None = None,
        max_concurrency: int | None = None,
        allowed_store_ids: Iterable[str] | str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if max_categories is not None and max_categories <= 0:
            raise ValueError("max_categories must be positive or None")
        if max_pages_per_category is not None and max_pages_per_category <= 0:
            raise ValueError("max_pages_per_category must be positive or None")
        if detail_enrichment_limit is not None and detail_enrichment_limit < 0:
            raise ValueError("detail_enrichment_limit must be non-negative or None")

        self.allow_full_crawl = (
            _environment_flag("HEMKOP_ALLOW_FULL_CRAWL", default=False)
            if allow_full_crawl is None
            else allow_full_crawl
        )
        if not isinstance(self.allow_full_crawl, bool):
            raise TypeError("allow_full_crawl must be a boolean")
        traversal_is_bounded = max_categories == 1 and max_pages_per_category == 1
        if not self.allow_full_crawl and not traversal_is_bounded:
            raise HemkopSourcePolicyError(
                "Hemköp source policy REVIEW permits only a one-category/one-page "
                "canary; set HEMKOP_ALLOW_FULL_CRAWL=true explicitly for wider traversal"
            )
        if not self.allow_full_crawl and page_size > 30:
            raise HemkopSourcePolicyError(
                "Hemköp source policy REVIEW limits canary pages to 30 rows"
            )

        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.page_size = page_size
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        self.detail_enrichment_limit = detail_enrichment_limit
        self.requests_per_second = (
            float(os.getenv("HEMKOP_REQUESTS_PER_SECOND", "0.1"))
            if requests_per_second is None
            else requests_per_second
        )
        if self.requests_per_second <= 0:
            raise ValueError("HEMKOP_REQUESTS_PER_SECOND must be positive")
        self.max_concurrency = (
            int(os.getenv("HEMKOP_MAX_CONCURRENCY", "1"))
            if max_concurrency is None
            else max_concurrency
        )
        if isinstance(self.max_concurrency, bool) or self.max_concurrency <= 0:
            raise ValueError("HEMKOP_MAX_CONCURRENCY must be positive")
        self.allowed_store_ids = _configured_store_ids(allowed_store_ids)
        if self.allow_full_crawl and not self.allowed_store_ids:
            raise HemkopSourcePolicyError(
                "Hemköp full crawl requires a non-empty HEMKOP_STORE_EXTERNAL_IDS allowlist"
            )

        self._limiter = AsyncRateLimiter(self.requests_per_second)
        self._request_slots = asyncio.Semaphore(self.max_concurrency)
        self._retry = retry_policy or RetryPolicy()
        if not 1 <= self._retry.attempts <= 3:
            raise ValueError("Hemköp retry attempts must be between 1 and 3")
        if self._retry.base_delay_seconds < 0 or self._retry.max_delay_seconds < 0:
            raise ValueError("Hemköp retry delays must be non-negative")
        self._request_count = 0
        self._http_error_count = 0
        self._rate_limit_count = 0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(20.0, connect=10.0),
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "Origin": "https://www.hemkop.se",
                "Referer": "https://www.hemkop.se/",
                "User-Agent": os.getenv(
                    "GROCERY_DATA_USER_AGENT",
                    "grocery-data-poc/0.1 (+source-transparency)",
                ),
            },
        )

    def _observe_attempt(self, status_code: int | None) -> None:
        self._request_count += 1
        if status_code is None or status_code >= 400:
            self._http_error_count += 1
        if status_code == 429:
            self._rate_limit_count += 1

    def _metrics_snapshot(self) -> tuple[int, int, int]:
        return self._request_count, self._http_error_count, self._rate_limit_count

    def _metrics_since(self, before: tuple[int, int, int]) -> TransportMetrics:
        return TransportMetrics(
            request_count=self._request_count - before[0],
            http_error_count=self._http_error_count - before[1],
            rate_limit_count=self._rate_limit_count - before[2],
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def store_allowed(self, store_external_id: str) -> bool:
        return not self.allowed_store_ids or store_external_id in self.allowed_store_ids

    @staticmethod
    def _raw_from_response(
        response: httpx.Response,
        *,
        kind: str,
        store_external_id: str | None,
        params: dict[str, Any] | None,
        connector_version: str,
        page_number: int | None,
        capture: bool,
    ) -> RawFetch:
        is_challenge = _looks_like_access_challenge(response)
        is_rate_limit = response.status_code == 429
        payload = (
            _SANITIZED_ACCESS_PAYLOAD
            if is_challenge
            else _SANITIZED_RATE_PAYLOAD
            if is_rate_limit
            else response.content
            if capture
            else b"{}"
        )
        return RawFetch(
            chain=Chain.HEMKOP,
            store_external_id=store_external_id,
            kind=("access_challenge" if is_challenge else "rate_limit" if is_rate_limit else kind),
            method=response.request.method,
            url=str(response.request.url.copy_with(query=None)),
            query={key: str(value) for key, value in (params or {}).items()},
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=(
                "application/json"
                if is_challenge or is_rate_limit
                else response.headers.get("content-type")
            ),
            payload=payload,
            connector_version=connector_version,
            page_number=page_number,
        )

    async def _send(
        self,
        method: str,
        path: str,
        *,
        kind: str,
        store_external_id: str | None = None,
        params: dict[str, Any] | None = None,
        page_number: int | None = None,
        headers: dict[str, str] | None = None,
        capture: bool = True,
    ) -> tuple[httpx.Response, RawFetch]:
        async with self._request_slots:
            response = await bounded_request(
                self._client,
                self._limiter,
                self._retry,
                method,
                path,
                params=params,
                headers=headers,
                on_attempt=self._observe_attempt,
                stop_retry=_looks_like_access_challenge,
                retry_rate_limits=False,
            )
        raw = self._raw_from_response(
            response,
            kind=kind,
            store_external_id=store_external_id,
            params=params,
            connector_version=self.connector_version,
            page_number=page_number,
            capture=capture,
        )
        if response.status_code == 429:
            raise HemkopRateLimitStop(
                "Hemköp RATE_LIMITED; current run stopped without retry",
                raw,
                retry_after=retry_after_seconds(response, self._retry.max_delay_seconds),
                retry_after_raw=response.headers.get("Retry-After"),
            )
        if _looks_like_access_challenge(response):
            raise HemkopAccessChallenge(
                f"Hemköp ACCESS_CHALLENGE stopped the current run (HTTP {response.status_code})",
                raw,
            )
        if response.is_error:
            raise HemkopHttpError(f"Hemköp returned HTTP {response.status_code}", raw)
        return response, raw

    async def _request(
        self,
        method: str,
        path: str,
        *,
        kind: str,
        store_external_id: str | None = None,
        params: dict[str, Any] | None = None,
        page_number: int | None = None,
        headers: dict[str, str] | None = None,
        capture: bool = True,
    ) -> RawFetch:
        _, raw = await self._send(
            method,
            path,
            kind=kind,
            store_external_id=store_external_id,
            params=params,
            page_number=page_number,
            headers=headers,
            capture=capture,
        )
        return raw

    @staticmethod
    def _contains_store_id(value: object, expected: str) -> bool:
        if isinstance(value, dict):
            if str(value.get("storeId") or "") == expected:
                return True
            return any(HemkopClient._contains_store_id(child, expected) for child in value.values())
        if isinstance(value, list):
            return any(HemkopClient._contains_store_id(child, expected) for child in value)
        return False

    async def fetch_stores(self) -> RawBatch:
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        try:
            documents.append(
                await self._request(
                    "GET",
                    "/axfood/rest/store",
                    kind="stores",
                    params={"online": "false"},
                )
            )
        except Exception as exc:
            if isinstance(exc, HemkopHttpError):
                documents.append(exc.raw)
            raise self._fetch_error(
                exc,
                "Hemköp store discovery aborted; partial raw evidence is attached",
                documents=documents,
                before=before,
            ) from exc
        return RawBatch(
            chain=Chain.HEMKOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    async def _activate_store(
        self,
        store_external_id: str,
        documents: list[RawFetch],
    ) -> None:
        # Public, session-scoped CSRF state stays in memory and is never stored.
        token_response, _ = await self._send(
            "GET",
            "/axfood/rest/csrf-token",
            kind="csrf_token",
            store_external_id=store_external_id,
            capture=False,
        )
        try:
            token = token_response.json()
        except ValueError as exc:
            raise RuntimeError("Hemköp CSRF response is not JSON") from exc
        if not isinstance(token, str) or not token:
            raise RuntimeError("Hemköp did not return a usable CSRF token")
        documents.append(
            await self._request(
                "POST",
                "/axfood/rest/store/activate",
                kind="store_activation",
                store_external_id=store_external_id,
                params={
                    "storeId": store_external_id,
                    "activelySelected": "true",
                    "forceAsPickingStore": "true",
                },
                capture=False,
                headers={"X-CSRF-Token": token},
            )
        )
        active = await self._request(
            "GET",
            "/axfood/rest/store/active",
            kind="store_context",
            store_external_id=store_external_id,
        )
        documents.append(active)
        try:
            payload = active.json_payload()
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Hemköp active-store response is not JSON") from exc
        from grocery_data.app.connectors.hemkop.models import validated_store_context
        if not validated_store_context(payload, store_external_id):
            raise RuntimeError("Hemköp did not confirm the requested store context")

    @staticmethod
    def _category_url(path: str) -> str:
        normalized = path.strip("/").removeprefix("c/")
        if not normalized:
            raise ValueError("Hemköp category path is empty")
        return f"/c/{normalized}"

    @staticmethod
    def _same_page_contract(first: HemkopCatalogPage, current: HemkopCatalogPage) -> None:
        if current.total_results != first.total_results:
            raise ValueError("Hemköp category total changed during traversal")
        if current.number_of_pages != first.number_of_pages:
            raise ValueError("Hemköp category page count changed during traversal")
        if current.page_size != first.page_size:
            raise ValueError("Hemköp category page size changed during traversal")

    async def fetch_category(
        self,
        store: SourceStore,
        category_path: str,
        *,
        max_pages: int | None = 1,
    ) -> RawBatch:
        """Capture one category for a bounded canary or explicit pagination proof.

        A one-page diagnostic remains available without broad crawl authority.
        Traversing more pages (including ``None`` for the declared end) is a
        REVIEW operation and therefore needs the same opt-in and exact store
        allowlist as a full catalog run.
        """

        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive or None")
        if max_pages != 1 and not self.allow_full_crawl:
            raise HemkopSourcePolicyError(
                "Hemköp multi-page category proof requires HEMKOP_ALLOW_FULL_CRAWL=true"
            )
        if not self.store_allowed(store.external_id):
            raise HemkopSourcePolicyError(
                f"Hemköp store {store.external_id} is outside HEMKOP_STORE_EXTERNAL_IDS"
            )

        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        tracker = _DuplicateTracker.create()
        category_fingerprints: dict[str, str] = {}
        category_pages: dict[str, int] = {}
        pages_fetched = 0
        first_page: HemkopCatalogPage | None = None
        explicitly_limited = max_pages is not None
        try:
            await self._activate_store(store.external_id, documents)
            requested_page = 0
            while True:
                document = await self._request(
                    "GET",
                    self._category_url(category_path),
                    kind="catalog_page",
                    store_external_id=store.external_id,
                    params={"page": requested_page, "size": self.page_size},
                    page_number=requested_page,
                )
                documents.append(document)
                page = validated_catalog_page(
                    json.loads(document.payload),
                    requested_page=requested_page,
                    requested_size=self.page_size,
                    expected_store_id=store.external_id,
                )
                if page.total_results == 0:
                    raise ValueError("Hemköp category proof returned no products")
                if first_page is None:
                    first_page = page
                else:
                    self._same_page_contract(first_page, page)
                pages_fetched += 1
                for row in page.results:
                    tracker.observe(
                        row,
                        category_fingerprints=category_fingerprints,
                        category_pages=category_pages,
                        page_number=requested_page,
                    )
                requested_page += 1
                if requested_page >= page.number_of_pages:
                    break
                if max_pages is not None and requested_page >= max_pages:
                    break
        except Exception as exc:
            if isinstance(exc, HemkopHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            exact_partial = (
                {
                    "expected_products": first_page.total_results,
                    "raw_rows": tracker.raw_rows,
                    "unique_products": len(tracker.seen_ids),
                    "duplicate_products": tracker.within_partition_duplicates,
                    "within_partition_duplicates": tracker.within_partition_duplicates,
                    "cross_partition_duplicates": 0,
                    "expected_pages": first_page.number_of_pages,
                    **tracker.classification_fields(),
                }
                if first_page is not None
                else {}
            )
            completion = CatalogCompletion(
                complete=False,
                limited=explicitly_limited,
                expected_categories=1,
                completed_categories=0,
                pages_fetched=pages_fetched,
                products_observed=len(tracker.seen_ids),
                reason=type(exc).__name__,
                **exact_partial,
            )
            raise self._fetch_error(
                exc,
                "Hemköp category proof aborted; partial raw evidence is attached",
                documents=documents,
                before=before,
                completion=completion,
            ) from exc

        assert first_page is not None
        reached_end = pages_fetched == first_page.number_of_pages
        exact_reconciles = (
            reached_end
            and tracker.raw_rows == first_page.total_results
            and tracker.conflicting_duplicates == 0
            and tracker.exact_duplicates_removed == tracker.within_partition_duplicates
        )
        completion = CatalogCompletion(
            complete=not explicitly_limited and exact_reconciles,
            limited=explicitly_limited,
            expected_categories=1,
            completed_categories=1 if reached_end else 0,
            pages_fetched=pages_fetched,
            products_observed=len(tracker.seen_ids),
            expected_products=first_page.total_results,
            raw_rows=tracker.raw_rows,
            unique_products=len(tracker.seen_ids),
            duplicate_products=tracker.within_partition_duplicates,
            within_partition_duplicates=tracker.within_partition_duplicates,
            cross_partition_duplicates=0,
            expected_pages=first_page.number_of_pages,
            **tracker.classification_fields(),
            reason=(
                None
                if not explicitly_limited and exact_reconciles
                else "category IDs/pages did not reconcile"
                if reached_end and not exact_reconciles
                else "explicit category page limit"
            ),
        )
        batch = RawBatch(
            chain=Chain.HEMKOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )
        if reached_end and not exact_reconciles:
            raise ConnectorFetchError(
                "Hemköp category proof did not reconcile product identities",
                partial_batch=batch,
            )
        return batch

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        if not self.store_allowed(store.external_id):
            raise HemkopSourcePolicyError(
                f"Hemköp store {store.external_id} is outside HEMKOP_STORE_EXTERNAL_IDS"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        tracker = _DuplicateTracker.create()
        expected_products = 0
        expected_pages = 0
        expected_categories: int | None = None
        completed_categories = 0
        pages_fetched = 0
        explicitly_limited = (
            self.max_categories is not None or self.max_pages_per_category is not None
        )
        try:
            await self._activate_store(store.external_id, documents)
            tree = await self._request(
                "GET",
                "/leftMenu/categorytree",
                kind="category_tree",
                store_external_id=store.external_id,
                params={"storeId": store.external_id},
            )
            documents.append(tree)
            all_paths = top_level_category_paths(tree.payload)
            expected_categories = len(all_paths)
            if expected_categories == 0:
                raise ValueError("Hemköp category tree has no top-level source partitions")
            selected_paths = (
                all_paths if self.max_categories is None else all_paths[: self.max_categories]
            )

            for path in selected_paths:
                category_fingerprints: dict[str, str] = {}
                category_pages: dict[str, int] = {}
                first_page: HemkopCatalogPage | None = None
                requested_page = 0
                category_complete = False
                while True:
                    document = await self._request(
                        "GET",
                        self._category_url(path),
                        kind="catalog_page",
                        store_external_id=store.external_id,
                        params={"page": requested_page, "size": self.page_size},
                        page_number=requested_page,
                    )
                    documents.append(document)
                    page = validated_catalog_page(
                        json.loads(document.payload),
                        requested_page=requested_page,
                        requested_size=self.page_size,
                        expected_store_id=store.external_id,
                    )
                    if page.total_results == 0:
                        raise ValueError(
                            "Hemköp empty top-level partition cannot prove catalog completeness"
                        )
                    if first_page is None:
                        first_page = page
                        expected_products += page.total_results
                        expected_pages += page.number_of_pages
                    else:
                        self._same_page_contract(first_page, page)

                    pages_fetched += 1
                    for row in page.results:
                        tracker.observe(
                            row,
                            category_fingerprints=category_fingerprints,
                            category_pages=category_pages,
                            page_number=requested_page,
                        )
                    requested_page += 1
                    if requested_page >= page.number_of_pages:
                        category_complete = True
                        break
                    if (
                        self.max_pages_per_category is not None
                        and requested_page >= self.max_pages_per_category
                    ):
                        break
                if category_complete:
                    completed_categories += 1

            enrichment_ids = (
                tuple(sorted(tracker.seen_ids))
                if self.detail_enrichment_limit is None
                else tuple(sorted(tracker.seen_ids))[: self.detail_enrichment_limit]
            )
            for product_id in enrichment_ids:
                documents.append(await self.fetch_product_detail(store, product_id))
        except Exception as exc:
            if isinstance(exc, HemkopHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            exact_partial = (
                {
                    "expected_products": expected_products,
                    "raw_rows": tracker.raw_rows,
                    "unique_products": len(tracker.seen_ids),
                    "duplicate_products": (
                        tracker.within_partition_duplicates + tracker.cross_partition_duplicates
                    ),
                    "within_partition_duplicates": tracker.within_partition_duplicates,
                    "cross_partition_duplicates": tracker.cross_partition_duplicates,
                    "expected_pages": expected_pages,
                    **tracker.classification_fields(),
                }
                if expected_pages > 0
                else {}
            )
            completion = CatalogCompletion(
                complete=False,
                limited=explicitly_limited,
                expected_categories=expected_categories,
                completed_categories=completed_categories,
                pages_fetched=pages_fetched,
                products_observed=len(tracker.seen_ids),
                reason=type(exc).__name__,
                **exact_partial,
            )
            raise self._fetch_error(
                exc,
                "Hemköp catalog fetch aborted; partial raw evidence is attached",
                documents=documents,
                before=before,
                completion=completion,
            ) from exc

        full_authority = self.allow_full_crawl and not explicitly_limited
        exact_reconciles = (
            expected_categories is not None
            and completed_categories == expected_categories
            and expected_products == tracker.raw_rows
            and tracker.raw_rows
            == len(tracker.seen_ids)
            + tracker.cross_partition_duplicates
            + tracker.exact_duplicates_removed
            and tracker.exact_duplicates_removed == tracker.within_partition_duplicates
            and tracker.conflicting_duplicates == 0
            and expected_pages == pages_fetched
        )
        completion = CatalogCompletion(
            complete=full_authority and exact_reconciles,
            limited=explicitly_limited,
            expected_categories=expected_categories,
            completed_categories=completed_categories,
            pages_fetched=pages_fetched,
            products_observed=len(tracker.seen_ids),
            **(
                {
                    "expected_products": expected_products,
                    "raw_rows": tracker.raw_rows,
                    "unique_products": len(tracker.seen_ids),
                    "duplicate_products": (
                        tracker.within_partition_duplicates + tracker.cross_partition_duplicates
                    ),
                    "within_partition_duplicates": tracker.within_partition_duplicates,
                    "cross_partition_duplicates": tracker.cross_partition_duplicates,
                    "expected_pages": expected_pages,
                    **tracker.classification_fields(),
                }
                if full_authority
                else {}
            ),
            reason=(
                None
                if full_authority and exact_reconciles
                else "top-level partitions overlap or exact totals did not reconcile"
                if full_authority
                else "source policy REVIEW: bounded discovery"
            ),
        )
        batch = RawBatch(
            chain=Chain.HEMKOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )
        if full_authority and not exact_reconciles:
            raise ConnectorFetchError(
                "Hemköp full traversal did not reconcile disjoint source partitions",
                partial_batch=batch,
            )
        return batch

    async def fetch_product_detail(
        self,
        store: SourceStore,
        external_product_id: str,
    ) -> RawFetch:
        if not self.store_allowed(store.external_id):
            raise HemkopSourcePolicyError(
                f"Hemköp store {store.external_id} is outside HEMKOP_STORE_EXTERNAL_IDS"
            )
        return await self._request(
            "GET",
            f"/axfood/rest/p/{external_product_id}",
            kind="product_detail",
            store_external_id=store.external_id,
            params={"isEanCode": "false"},
        )

    async def fetch_validation_product_details(
        self,
        store: SourceStore,
        external_product_ids: Iterable[str],
        *,
        max_products: int = 1,
    ) -> RawBatch:
        """Fetch an exact, bounded field-validation detail set.

        The normal anonymous store activation/readback happens once in the
        ephemeral client. CSRF/cookies remain in memory and are not included in
        returned raw documents. This is not a catalog traversal and it never
        accepts an inferred or name-matched source product ID.
        """

        if not 1 <= max_products <= 100:
            raise ValueError("max_products must be 1..100")
        requested = tuple(dict.fromkeys(str(value).strip() for value in external_product_ids))
        if not requested or any(not value for value in requested):
            raise ValueError("at least one exact external product ID is required")
        if len(requested) > max_products:
            raise HemkopSourcePolicyError(
                "Hemköp validation detail request exceeds its explicit product budget"
            )
        if not self.store_allowed(store.external_id):
            raise HemkopSourcePolicyError(
                f"Hemköp store {store.external_id} is outside HEMKOP_STORE_EXTERNAL_IDS"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        try:
            await self._activate_store(store.external_id, documents)
            for product_id in requested:
                detail = await self.fetch_product_detail(store, product_id)
                payload = detail.json_payload()
                if not isinstance(payload, dict):
                    raise TypeError("Hemköp product detail is not an object")
                if str(payload.get("code") or "").strip() != product_id:
                    raise ValueError("Hemköp product detail identity does not match request")
                documents.append(detail)
        except Exception as exc:
            if isinstance(exc, HemkopHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            raise self._fetch_error(
                exc,
                "Hemköp validation detail enrichment aborted",
                documents=documents,
                before=before,
            ) from exc
        return RawBatch(
            chain=Chain.HEMKOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    def _fetch_error(
        self,
        exc: Exception,
        fallback_message: str,
        *,
        documents: list[RawFetch],
        before: tuple[int, int, int],
        completion: CatalogCompletion | None = None,
    ) -> ConnectorFetchError:
        message = (
            str(exc)
            if isinstance(exc, (HemkopAccessChallenge, HemkopRateLimitStop))
            else fallback_message
        )
        error_type: type[ConnectorFetchError] = (
            HemkopAccessChallengeFetchError
            if isinstance(exc, HemkopAccessChallenge)
            else HemkopRateLimitFetchError
            if isinstance(exc, HemkopRateLimitStop)
            else ConnectorFetchError
        )
        return error_type(
            message,
            partial_batch=RawBatch(
                chain=Chain.HEMKOP,
                documents=tuple(documents),
                transport=self._metrics_since(before),
                catalog_completion=completion,
            ),
        )
