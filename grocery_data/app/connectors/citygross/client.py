from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.citygross.models import validated_catalog_page
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


class CityGrossHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class CityGrossSourcePolicyError(RuntimeError):
    """The requested collection is outside the explicit City Gross policy gate."""


class CityGrossAccessChallenge(CityGrossHttpError):
    """Ordinary public access was blocked; callers must not attempt a bypass."""


class CityGrossRateLimitStop(CityGrossHttpError):
    """Bounded 429 handling was exhausted and the current run must stop."""

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


class CityGrossAccessChallengeFetchError(ConnectorFetchError):
    """Persistable collector failure with a stable access-challenge type."""


class CityGrossRateLimitFetchError(ConnectorFetchError):
    """Persistable collector failure with a stable rate-limit type."""


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
_TRANSPORT_STOP_CONTENT_TYPE = "application/json; profile=transport-stop-diagnostic"
_TRANSPORT_STOP_SCHEMA = "citygross-transport-stop-v1"


def _environment_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise CityGrossSourcePolicyError(
        f"{name} must be one of true/false/1/0; refusing ambiguous policy value"
    )


def _configured_store_ids(value: Iterable[str] | str | None) -> frozenset[str]:
    if value is None:
        values: Iterable[str] = os.getenv("CITYGROSS_STORE_EXTERNAL_IDS", "").split(",")
    elif isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    return frozenset(store_id.strip() for store_id in values if store_id.strip())


def _looks_like_access_challenge(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return False
    if response.status_code in {401, 403, 405}:
        return True
    content_type = response.headers.get("content-type", "").casefold()
    beginning = response.content[:65536].lstrip().lower()
    is_json = "json" in content_type
    has_marker = any(marker in beginning for marker in _ACCESS_CHALLENGE_MARKERS)
    return not is_json or has_marker


class CityGrossClient:
    """Conservative transport for City Gross' public storefront responses.

    The default one-page limit is intentional while the source policy remains
    REVIEW. An unlimited traversal requires both ``max_pages=None`` and the
    explicit ``CITYGROSS_ALLOW_FULL_CRAWL=true`` opt-in (or the equivalent
    constructor argument). Registry/store-discovery construction remains
    bounded even though the separately gated full-online connector has passed
    its operational acceptance contract.
    """

    connector_version = "citygross-v1"
    default_base_url = "https://www.citygross.se"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        page_size: int = 100,
        max_pages: int | None = 1,
        allow_full_crawl: bool | None = None,
        max_concurrency: int | None = None,
        allowed_store_ids: Iterable[str] | str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive or None")
        self.allow_full_crawl = (
            _environment_flag("CITYGROSS_ALLOW_FULL_CRAWL", default=False)
            if allow_full_crawl is None
            else allow_full_crawl
        )
        if not isinstance(self.allow_full_crawl, bool):
            raise TypeError("allow_full_crawl must be a boolean")
        if not self.allow_full_crawl and max_pages != 1:
            raise CityGrossSourcePolicyError(
                "City Gross source policy REVIEW permits only a one-page canary; "
                "set CITYGROSS_ALLOW_FULL_CRAWL=true explicitly for wider traversal"
            )
        if not self.allow_full_crawl and page_size > 100:
            raise CityGrossSourcePolicyError(
                "City Gross source policy REVIEW limits canary pages to at most 100 rows"
            )
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.page_size = page_size
        self.max_pages = max_pages
        self.requests_per_second = (
            float(os.getenv("CITYGROSS_REQUESTS_PER_SECOND", "1"))
            if requests_per_second is None
            else requests_per_second
        )
        self.max_concurrency = (
            int(os.getenv("CITYGROSS_MAX_CONCURRENCY", "1"))
            if max_concurrency is None
            else max_concurrency
        )
        if isinstance(self.max_concurrency, bool) or self.max_concurrency <= 0:
            raise ValueError("CITYGROSS_MAX_CONCURRENCY must be positive")
        self.allowed_store_ids = _configured_store_ids(allowed_store_ids)
        if self.allow_full_crawl and not self.allowed_store_ids:
            raise CityGrossSourcePolicyError(
                "City Gross full crawl requires an explicit non-empty "
                "CITYGROSS_STORE_EXTERNAL_IDS allowlist"
            )
        self._limiter = AsyncRateLimiter(self.requests_per_second)
        self._request_slots = asyncio.Semaphore(self.max_concurrency)
        self._retry = retry_policy or RetryPolicy()
        if not 1 <= self._retry.attempts <= 3:
            raise ValueError("City Gross retry attempts must be between 1 and 3")
        if self._retry.base_delay_seconds < 0 or self._retry.max_delay_seconds < 0:
            raise ValueError("City Gross retry delays must be non-negative")
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

    async def _request(
        self,
        path: str,
        *,
        kind: str,
        store_external_id: str | None = None,
        params: dict[str, Any] | None = None,
        page_number: int | None = None,
    ) -> RawFetch:
        async with self._request_slots:
            response = await bounded_request(
                self._client,
                self._limiter,
                self._retry,
                "GET",
                path,
                params=params,
                on_attempt=self._observe_attempt,
                stop_retry=_looks_like_access_challenge,
                retry_rate_limits=False,
            )
        is_access_challenge = _looks_like_access_challenge(response)
        is_rate_limit = response.status_code == 429
        raw_kind = (
            "access_challenge" if is_access_challenge else "rate_limit" if is_rate_limit else kind
        )
        if is_access_challenge or is_rate_limit:
            payload = json.dumps(
                {
                    "schema": _TRANSPORT_STOP_SCHEMA,
                    "classification": raw_kind,
                    "http_status": response.status_code,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            content_type = _TRANSPORT_STOP_CONTENT_TYPE
        else:
            payload = response.content
            content_type = response.headers.get("content-type")
        raw = RawFetch(
            chain=Chain.CITY_GROSS,
            store_external_id=store_external_id,
            kind=raw_kind,
            method="GET",
            url=str(response.request.url.copy_with(query=None)),
            query={key: str(value) for key, value in (params or {}).items()},
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=content_type,
            payload=payload,
            connector_version=self.connector_version,
            page_number=page_number,
        )
        if response.status_code == 429:
            retry_after = retry_after_seconds(response, self._retry.max_delay_seconds)
            raise CityGrossRateLimitStop(
                "City Gross RATE_LIMITED; Retry-After was observed and current run stopped",
                raw,
                retry_after=retry_after,
                retry_after_raw=response.headers.get("Retry-After"),
            )
        if is_access_challenge:
            raise CityGrossAccessChallenge(
                f"City Gross ACCESS_CHALLENGE stopped the current run "
                f"(HTTP {response.status_code})",
                raw,
            )
        if response.is_error:
            raise CityGrossHttpError(
                f"City Gross returned HTTP {response.status_code}",
                raw,
            )
        return raw

    async def fetch_stores(self) -> RawBatch:
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        try:
            documents.append(await self._request("/api/v1/PageData/stores", kind="stores"))
            documents.append(
                await self._request(
                    "/api/v1/sites",
                    kind="store_number_map",
                    params={"siteTypeId": 3},
                )
            )
        except Exception as exc:
            if isinstance(exc, CityGrossHttpError):
                documents.append(exc.raw)
            message = (
                str(exc)
                if isinstance(
                    exc,
                    (CityGrossAccessChallenge, CityGrossRateLimitStop),
                )
                else "City Gross store discovery aborted; partial raw evidence is attached"
            )
            error_type: type[ConnectorFetchError] = (
                CityGrossAccessChallengeFetchError
                if isinstance(exc, CityGrossAccessChallenge)
                else CityGrossRateLimitFetchError
                if isinstance(exc, CityGrossRateLimitStop)
                else ConnectorFetchError
            )
            raise error_type(
                message,
                partial_batch=RawBatch(
                    chain=Chain.CITY_GROSS,
                    documents=tuple(documents),
                    transport=self._metrics_since(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.CITY_GROSS,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        if not self.store_allowed(store.external_id):
            raise CityGrossSourcePolicyError(
                f"City Gross store {store.external_id} is outside CITYGROSS_STORE_EXTERNAL_IDS"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        seen_ids: set[str] = set()
        expected_total: int | None = None
        expected_pages: int | None = None
        pages_fetched = 0
        raw_rows = 0
        duplicate_products = 0
        try:
            while True:
                skip = pages_fetched * self.page_size
                document = await self._request(
                    "/api/v1/Loop54/products",
                    kind="catalog_page",
                    store_external_id=store.external_id,
                    params={
                        "store": store.external_id,
                        "skip": skip,
                        "take": self.page_size,
                    },
                    page_number=pages_fetched,
                )
                documents.append(document)
                page = validated_catalog_page(
                    json.loads(document.payload),
                    requested_skip=skip,
                    requested_take=self.page_size,
                    expected_store_id=store.external_id,
                )
                if expected_total is None:
                    expected_total = page.total_count
                    expected_pages = page.total_pages
                elif page.total_count != expected_total:
                    raise ValueError("City Gross totalCount changed during traversal")
                elif page.total_pages != expected_pages:
                    raise ValueError("City Gross totalPages changed during traversal")
                if page.total_count == 0:
                    raise ValueError(
                        "City Gross empty catalog cannot establish plausible completeness"
                    )
                pages_fetched += 1
                for row in page.items:
                    raw_rows += 1
                    product_id = str(row["id"])
                    if product_id in seen_ids:
                        duplicate_products += 1
                        raise ValueError("City Gross traversal returned duplicate product IDs")
                    seen_ids.add(product_id)
                if len(seen_ids) == page.total_count:
                    break
                if len(seen_ids) > page.total_count:
                    raise ValueError("City Gross traversal exceeded declared totalCount")
                if self.max_pages is not None and pages_fetched >= self.max_pages:
                    break
        except Exception as exc:
            if isinstance(exc, CityGrossHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            exact_evidence = (
                {
                    "expected_products": expected_total,
                    "raw_rows": raw_rows,
                    "unique_products": len(seen_ids),
                    "duplicate_products": duplicate_products,
                    "expected_pages": expected_pages,
                }
                if expected_total is not None and expected_pages is not None
                else {}
            )
            completion = CatalogCompletion(
                complete=False,
                limited=self.max_pages is not None,
                expected_categories=1,
                completed_categories=0,
                pages_fetched=pages_fetched,
                products_observed=len(seen_ids),
                reason=type(exc).__name__,
                **exact_evidence,
            )
            message = (
                str(exc)
                if isinstance(
                    exc,
                    (CityGrossAccessChallenge, CityGrossRateLimitStop),
                )
                else "City Gross catalog fetch aborted; partial raw evidence is attached"
            )
            error_type = (
                CityGrossAccessChallengeFetchError
                if isinstance(exc, CityGrossAccessChallenge)
                else CityGrossRateLimitFetchError
                if isinstance(exc, CityGrossRateLimitStop)
                else ConnectorFetchError
            )
            raise error_type(
                message,
                partial_batch=RawBatch(
                    chain=Chain.CITY_GROSS,
                    documents=tuple(documents),
                    transport=self._metrics_since(before),
                    catalog_completion=completion,
                ),
            ) from exc

        traversal_reconciled = expected_total is not None and len(seen_ids) == expected_total
        complete = self.allow_full_crawl and traversal_reconciled
        limited = not complete
        return RawBatch(
            chain=Chain.CITY_GROSS,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=CatalogCompletion(
                complete=complete,
                limited=limited,
                expected_categories=1,
                completed_categories=1 if complete else 0,
                pages_fetched=pages_fetched,
                products_observed=len(seen_ids),
                expected_products=expected_total,
                raw_rows=raw_rows,
                unique_products=len(seen_ids),
                duplicate_products=duplicate_products,
                expected_pages=expected_pages,
                reason=(
                    None
                    if complete
                    else (
                        "source policy REVIEW: full crawl not opted in"
                        if traversal_reconciled
                        else "explicit traversal limit"
                    )
                ),
            ),
        )
