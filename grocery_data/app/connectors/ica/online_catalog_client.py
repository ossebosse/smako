from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import AsyncRateLimiter, RetryPolicy, bounded_request
from grocery_data.app.connectors.ica.online_catalog_models import (
    IcaBatchResult,
    IcaCategoryTree,
    IcaOnlineSchemaError,
    IcaProductPage,
    purchase_semantic_fingerprint,
    sanitized_category_tree_payload,
    sanitized_context_payload,
)
from grocery_data.app.domain import CatalogCompletion, Chain, RawBatch, RawFetch
from grocery_data.app.domain.raw import TransportMetrics

ICA_STORE_CONTEXT_KIND = "ica_store_context"
ICA_CATEGORY_TREE_KIND = "ica_category_tree"
ICA_SEARCH_KIND = "ica_search"
ICA_PRODUCT_PAGE_KIND = "ica_product_page"
ICA_PRODUCT_BATCH_KIND = "ica_product_batch"
ICA_PROMOTION_RESOLUTION_KIND = "ica_promotion_resolution"

_HOST = "handlaprivatkund.ica.se"
_BASE_URL = f"https://{_HOST}"
_REGION_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_RETAILER_REGION_ID = re.compile(r"^\d{5,12}$")
_PRODUCT_ID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_TRUE_VALUES = frozenset({"1", "true"})
_FALSE_VALUES = frozenset({"0", "false"})
_STOP_STATUSES = frozenset({401, 403, 405, 429})
_CHALLENGE_MARKERS = (
    b"access denied",
    b"aws waf",
    b"aws-waf",
    b"captcha",
    b"challenge.js",
    b"human verification",
    b"request blocked",
    b"verify you are human",
)
_FORBIDDEN_RAW_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "cookies",
        "csrf",
        "csrftoken",
        "session",
        "sessionid",
        "sid",
        "uid",
        "userid",
        "visitorid",
        "requestid",
        "pageviewid",
        "trackingid",
        "analyticsid",
        "correlationid",
        "quantityinbasket",
    }
)


class IcaOnlineHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class IcaOnlineAccessChallenge(IcaOnlineHttpError):
    """ICA stopped returning the expected ordinary public representation."""


class IcaOnlineRateLimitStop(IcaOnlineHttpError):
    """A 429 ends the current context run; identity/session rotation is forbidden."""


class IcaOnlineSourcePolicyError(RuntimeError):
    """The requested traversal exceeds explicit REVIEW authority."""


def _environment_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise IcaOnlineSourcePolicyError(
        f"{name} must be one of true/false/1/0; refusing ambiguous policy value"
    )


def _configured_context_ids(value: Iterable[str] | str | None) -> frozenset[str]:
    if value is None:
        values: Iterable[str] = os.getenv("ICA_ONLINE_CONTEXT_IDS", "").split(",")
    elif isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    normalized = frozenset(item.strip().casefold() for item in values if item.strip())
    invalid = sorted(item for item in normalized if _REGION_ID.fullmatch(item) is None)
    if invalid:
        raise IcaOnlineSourcePolicyError("ICA_ONLINE_CONTEXT_IDS contains an invalid region UUID")
    return normalized


def _configured_batch_size(value: int | None) -> int | None:
    if value is not None:
        return value
    raw = os.getenv("ICA_PRODUCT_BATCH_SIZE")
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise IcaOnlineSourcePolicyError("ICA_PRODUCT_BATCH_SIZE must be an integer") from exc


@dataclass(frozen=True, slots=True)
class IcaOnlineOperatorCrawlPolicy:
    allow_full_crawl: bool
    allowed_context_ids: frozenset[str]
    product_batch_size: int | None

    @classmethod
    def from_environment(cls) -> IcaOnlineOperatorCrawlPolicy:
        return cls(
            allow_full_crawl=_environment_flag("ICA_ALLOW_FULL_CRAWL", default=False),
            allowed_context_ids=_configured_context_ids(None),
            product_batch_size=_configured_batch_size(None),
        )

    def require(self, region_id: str) -> str:
        normalized = _validated_region_id(region_id)
        if not self.allow_full_crawl:
            raise IcaOnlineSourcePolicyError(
                "ICA source policy REVIEW requires ICA_ALLOW_FULL_CRAWL=true"
            )
        if normalized not in self.allowed_context_ids:
            raise IcaOnlineSourcePolicyError(
                f"ICA online context {normalized} is outside ICA_ONLINE_CONTEXT_IDS"
            )
        if self.product_batch_size is None:
            raise IcaOnlineSourcePolicyError(
                "ICA full collection requires a browser-verified ICA_PRODUCT_BATCH_SIZE"
            )
        return normalized


def _validated_region_id(value: str) -> str:
    normalized = value.strip().casefold()
    if _REGION_ID.fullmatch(normalized) is None:
        raise ValueError("ICA region ID must be a UUID")
    return normalized


def _validated_retailer_region_id(value: str) -> str:
    normalized = value.strip()
    if _RETAILER_REGION_ID.fullmatch(normalized) is None:
        raise ValueError("ICA retailer region ID must be numeric")
    return normalized


def _token_hash(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def _normalized_key(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _sanitize_json_value(value: object) -> object:
    if isinstance(value, dict):
        result: dict[str, object] = {}
        for key, child in value.items():
            normalized = _normalized_key(key)
            if normalized == "nextpagetoken":
                if isinstance(child, str) and child.strip():
                    result["nextPageTokenHash"] = _token_hash(child.strip())
                continue
            if normalized in _FORBIDDEN_RAW_KEYS or normalized.endswith(("token", "tokens")):
                continue
            result[str(key)] = _sanitize_json_value(child)
        return result
    if isinstance(value, list):
        return [_sanitize_json_value(child) for child in value]
    return value


def sanitized_api_payload(payload: object) -> bytes:
    return json.dumps(
        _sanitize_json_value(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _content_type(response: httpx.Response) -> str:
    return response.headers.get("Content-Type", "").split(";", 1)[0].strip().casefold()


def _looks_like_access_stop(response: httpx.Response, *, expect_json: bool) -> bool:
    if response.status_code in _STOP_STATUSES:
        return True
    if expect_json and _content_type(response) != "application/json":
        return True
    beginning = response.content[:65536].lstrip().lower()
    return any(marker in beginning for marker in _CHALLENGE_MARKERS)


def _safe_raw_query(values: Mapping[str, object] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in (values or {}).items():
        normalized = _normalized_key(key)
        if normalized in _FORBIDDEN_RAW_KEYS or normalized in {"pagetoken", "nextpagetoken"}:
            raise ValueError("ICA raw query metadata contains private or unhashed state")
        if isinstance(value, bool):
            result[str(key)] = str(value).lower()
        elif isinstance(value, (tuple, list)):
            result[str(key)] = json.dumps(list(value), separators=(",", ":"))
        else:
            result[str(key)] = str(value)
    return result


@dataclass(slots=True)
class _TraversalTracker:
    seen: dict[str, tuple[str, str]]
    raw_rows: int = 0
    within_duplicates: int = 0
    cross_duplicates: int = 0
    exact_duplicates: int = 0
    conflicting_duplicates: int = 0
    pagination_overlaps: int = 0

    @classmethod
    def create(cls) -> _TraversalTracker:
        return cls(seen={})

    def observe(
        self,
        product: dict[str, Any],
        *,
        category_id: str,
        page_index: int,
    ) -> None:
        product_id = str(product.get("productId") or "").strip()
        if _PRODUCT_ID.fullmatch(product_id) is None:
            raise IcaOnlineSchemaError("ICA decorated product has no stable product UUID")
        fingerprint = purchase_semantic_fingerprint(product)
        self.raw_rows += 1
        previous = self.seen.get(product_id)
        if previous is None:
            self.seen[product_id] = (category_id, fingerprint)
            return
        previous_category, previous_fingerprint = previous
        if previous_fingerprint != fingerprint:
            self.conflicting_duplicates += 1
            raise IcaOnlineSchemaError(
                "ICA product identity has conflicting purchase semantics in one context"
            )
        self.exact_duplicates += 1
        if previous_category == category_id:
            self.within_duplicates += 1
            if page_index > 0:
                self.pagination_overlaps += 1
        else:
            self.cross_duplicates += 1


@dataclass(frozen=True, slots=True)
class _CategoryRun:
    declared_products: int
    page_count: int
    products: tuple[dict[str, Any], ...]
    raw_rows: int
    exact_group_duplicates: int
    within_duplicates: int
    pagination_overlaps: int
    complete: bool


class IcaOnlineCatalogClient:
    """Current anonymous ICA v6 catalogue client with fail-closed REVIEW gates."""

    connector_version = "ica-online-catalog-v1"
    base_url = _BASE_URL

    def __init__(
        self,
        *,
        context_mappings: Mapping[str, str],
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        max_categories: int | None = 1,
        max_pages_per_category: int | None = 1,
        max_batches_per_page: int | None = 1,
        product_batch_size: int | None = None,
        allow_full_crawl: bool | None = None,
        allowed_context_ids: Iterable[str] | str | None = None,
        max_concurrency: int | None = None,
        page_size: int = 300,
        max_products_to_decorate: int = 50,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.allow_full_crawl = (
            _environment_flag("ICA_ALLOW_FULL_CRAWL", default=False)
            if allow_full_crawl is None
            else allow_full_crawl
        )
        if not isinstance(self.allow_full_crawl, bool):
            raise TypeError("allow_full_crawl must be a boolean")
        if page_size != 300 or max_products_to_decorate != 50:
            raise IcaOnlineSourcePolicyError(
                "ICA collection must retain the verified frontend 300/50 page contract"
            )
        if max_categories is not None and max_categories <= 0:
            raise ValueError("max_categories must be positive or None")
        if max_pages_per_category is not None and max_pages_per_category <= 0:
            raise ValueError("max_pages_per_category must be positive or None")
        if max_batches_per_page is not None and max_batches_per_page <= 0:
            raise ValueError("max_batches_per_page must be positive or None")

        bounded = (
            max_categories == 1
            and max_pages_per_category == 1
            and max_batches_per_page == 1
        )
        if not self.allow_full_crawl and not bounded:
            raise IcaOnlineSourcePolicyError(
                "ICA source policy REVIEW permits one category/page/batch only"
            )
        if self.allow_full_crawl and any(
            value is not None
            for value in (max_categories, max_pages_per_category, max_batches_per_page)
        ):
            raise IcaOnlineSourcePolicyError(
                "ICA full collection cannot retain bounded traversal limits"
            )

        batch_size = _configured_batch_size(product_batch_size)
        if batch_size is not None and not 1 <= batch_size <= 300:
            raise IcaOnlineSourcePolicyError("ICA product batch size must be between 1 and 300")
        if self.allow_full_crawl and batch_size is None:
            raise IcaOnlineSourcePolicyError(
                "ICA full collection requires browser-verified ICA_PRODUCT_BATCH_SIZE"
            )
        self.product_batch_size = batch_size

        rate = (
            float(os.getenv("ICA_ONLINE_REQUESTS_PER_SECOND", "0.5"))
            if requests_per_second is None
            else requests_per_second
        )
        if rate <= 0:
            raise ValueError("ICA_ONLINE_REQUESTS_PER_SECOND must be positive")
        if self.allow_full_crawl and not 0.5 <= rate <= 1.0:
            raise IcaOnlineSourcePolicyError(
                "ICA full collection must run between 0.5 and 1 request/second"
            )
        self.requests_per_second = rate
        self.max_concurrency = (
            int(os.getenv("ICA_ONLINE_MAX_CONCURRENCY", "1"))
            if max_concurrency is None
            else max_concurrency
        )
        if self.max_concurrency != 1:
            raise IcaOnlineSourcePolicyError("ICA online collection requires concurrency=1")

        mappings = {
            _validated_region_id(region): _validated_retailer_region_id(retailer)
            for region, retailer in context_mappings.items()
        }
        if not mappings:
            raise ValueError("ICA online client requires an exact context mapping")
        # Bounded canaries may use the exact verified mapping supplied by the
        # operator. A full traversal additionally requires the explicit
        # allow-list (normally ICA_ONLINE_CONTEXT_IDS) so it cannot broaden
        # scope merely because a mapping exists in application config.
        self.allowed_context_ids = (
            _configured_context_ids(allowed_context_ids)
            if self.allow_full_crawl or allowed_context_ids is not None
            else frozenset(mappings)
        )
        if set(self.allowed_context_ids) - set(mappings):
            raise IcaOnlineSourcePolicyError(
                "ICA_ONLINE_CONTEXT_IDS contains a context without exact mapping"
            )
        if self.allow_full_crawl and not self.allowed_context_ids:
            raise IcaOnlineSourcePolicyError(
                "ICA full collection requires non-empty ICA_ONLINE_CONTEXT_IDS"
            )
        self.context_mappings = mappings
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        self.max_batches_per_page = max_batches_per_page
        self.page_size = page_size
        self.max_products_to_decorate = max_products_to_decorate

        self._limiter = AsyncRateLimiter(rate)
        self._request_slot = asyncio.Semaphore(1)
        self._retry = retry_policy or RetryPolicy()
        self._request_count = 0
        self._http_error_count = 0
        self._rate_limit_count = 0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": os.getenv(
                    "GROCERY_DATA_USER_AGENT",
                    "grocery-data-poc/0.1 (+source-transparency)",
                ),
            },
        )

    def _observe(self, status: int | None) -> None:
        self._request_count += 1
        if status is None or status >= 400:
            self._http_error_count += 1
        if status == 429:
            self._rate_limit_count += 1

    def _metrics_snapshot(self) -> tuple[int, int, int]:
        return self._request_count, self._http_error_count, self._rate_limit_count

    def _metrics_since(self, before: tuple[int, int, int]) -> TransportMetrics:
        return TransportMetrics(
            request_count=self._request_count - before[0],
            http_error_count=self._http_error_count - before[1],
            rate_limit_count=self._rate_limit_count - before[2],
        )

    def context_allowed(self, region_id: str) -> bool:
        try:
            normalized = _validated_region_id(region_id)
        except ValueError:
            return False
        return normalized in self.context_mappings and normalized in self.allowed_context_ids

    def require_context(self, region_id: str) -> tuple[str, str]:
        normalized = _validated_region_id(region_id)
        if normalized not in self.allowed_context_ids:
            raise IcaOnlineSourcePolicyError(
                f"ICA online context {normalized} is outside ICA_ONLINE_CONTEXT_IDS"
            )
        retailer = self.context_mappings.get(normalized)
        if retailer is None:
            raise IcaOnlineSourcePolicyError("ICA region has no exact verified retailer route")
        return normalized, retailer

    def _diagnostic_raw(
        self,
        response: httpx.Response,
        *,
        method: str,
        kind: str,
        region_id: str,
        logical_query: Mapping[str, object] | None,
        page_number: int | None,
        classification: str,
    ) -> RawFetch:
        payload = json.dumps(
            {
                "schema": "ica-online-transport-stop-v1",
                "classification": classification,
                "http_status": response.status_code,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return RawFetch(
            chain=Chain.ICA,
            store_external_id=region_id,
            kind=kind,
            method=method,
            url=str(response.request.url.copy_with(query=None)),
            query=_safe_raw_query(logical_query),
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type="application/json; profile=transport-stop-diagnostic",
            payload=payload,
            connector_version=self.connector_version,
            page_number=page_number,
        )

    async def _json_request(
        self,
        method: Literal["GET", "PUT"],
        path: str,
        *,
        kind: str,
        region_id: str,
        params: Mapping[str, object] | Sequence[tuple[str, object]] | None = None,
        logical_query: Mapping[str, object] | None = None,
        json_body: object | None = None,
        page_number: int | None = None,
    ) -> tuple[RawFetch, dict[str, Any]]:
        _, retailer_id = self.require_context(region_id)
        expected_prefix = f"/stores/{retailer_id}/api/"
        parsed = urlsplit(path)
        if parsed.scheme or parsed.netloc or not path.startswith(expected_prefix):
            raise ValueError("ICA API request must stay on the exact verified store route")
        async with self._request_slot:
            response = await bounded_request(
                self._client,
                self._limiter,
                self._retry,
                method,
                path,
                params=params,
                json=json_body,
                headers={"Accept": "application/json"},
                on_attempt=self._observe,
                stop_retry=lambda item: _looks_like_access_stop(item, expect_json=True),
                retry_rate_limits=False,
            )
        if _looks_like_access_stop(response, expect_json=True):
            if response.status_code < 400:
                # A successful-looking HTML/challenge response is still one
                # failed transport attempt for source-health accounting.
                self._http_error_count += 1
            classification = (
                "rate_limit" if response.status_code == 429 else "access_challenge"
            )
            raw = self._diagnostic_raw(
                response,
                method=method,
                kind=kind,
                region_id=region_id,
                logical_query=logical_query,
                page_number=page_number,
                classification=classification,
            )
            error_type = (
                IcaOnlineRateLimitStop
                if response.status_code == 429
                else IcaOnlineAccessChallenge
            )
            raise error_type(
                f"ICA online collection stopped ({classification}, HTTP {response.status_code})",
                raw,
            )
        if response.is_error:
            raw = self._diagnostic_raw(
                response,
                method=method,
                kind=kind,
                region_id=region_id,
                logical_query=logical_query,
                page_number=page_number,
                classification="http_error",
            )
            raise IcaOnlineHttpError(f"ICA online API returned HTTP {response.status_code}", raw)
        try:
            decoded = response.json()
        except (json.JSONDecodeError, UnicodeError, ValueError) as exc:
            raw = self._diagnostic_raw(
                response,
                method=method,
                kind=kind,
                region_id=region_id,
                logical_query=logical_query,
                page_number=page_number,
                classification="invalid_json",
            )
            raise IcaOnlineHttpError("ICA online API returned invalid JSON", raw) from exc
        if not isinstance(decoded, dict):
            raw = self._diagnostic_raw(
                response,
                method=method,
                kind=kind,
                region_id=region_id,
                logical_query=logical_query,
                page_number=page_number,
                classification="schema_error",
            )
            raise IcaOnlineHttpError("ICA online API response is not an object", raw)
        raw = RawFetch(
            chain=Chain.ICA,
            store_external_id=region_id,
            kind=kind,
            method=method,
            url=str(response.request.url.copy_with(query=None)),
            query=_safe_raw_query(logical_query),
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type="application/json; profile=sanitized-ica-online-v1",
            payload=sanitized_api_payload(decoded),
            connector_version=self.connector_version,
            page_number=page_number,
        )
        return raw, decoded

    async def fetch_context(self, region_id: str) -> RawBatch:
        region_id, retailer_id = self.require_context(region_id)
        before = self._metrics_snapshot()
        path = f"/stores/{retailer_id}"
        async with self._request_slot:
            response = await bounded_request(
                self._client,
                self._limiter,
                self._retry,
                "GET",
                path,
                headers={"Accept": "text/html,application/xhtml+xml"},
                on_attempt=self._observe,
                stop_retry=lambda item: _looks_like_access_stop(item, expect_json=False),
                retry_rate_limits=False,
            )
        if _looks_like_access_stop(response, expect_json=False) or response.is_error:
            classification = (
                "rate_limit"
                if response.status_code == 429
                else "access_challenge"
                if _looks_like_access_stop(response, expect_json=False)
                else "http_error"
            )
            if classification == "access_challenge" and response.status_code < 400:
                self._http_error_count += 1
            raw = self._diagnostic_raw(
                response,
                method="GET",
                kind=ICA_STORE_CONTEXT_KIND,
                region_id=region_id,
                logical_query={"retailer_region_id": retailer_id},
                page_number=None,
                classification=classification,
            )
            error_type = (
                IcaOnlineRateLimitStop
                if response.status_code == 429
                else IcaOnlineAccessChallenge
                if classification == "access_challenge"
                else IcaOnlineHttpError
            )
            raise ConnectorFetchError(
                "ICA online context verification stopped",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=(raw,),
                    transport=self._metrics_since(before),
                ),
            ) from error_type("ICA context verification failed", raw)
        try:
            context_payload = sanitized_context_payload(
                response.text,
                expected_retailer_region_id=retailer_id,
                expected_region_id=region_id,
            )
            category_payload = sanitized_category_tree_payload(
                response.text,
                expected_retailer_region_id=retailer_id,
                expected_region_id=region_id,
            )
        except (UnicodeError, ValueError, IcaOnlineSchemaError) as exc:
            diagnostic = self._diagnostic_raw(
                response,
                method="GET",
                kind=ICA_STORE_CONTEXT_KIND,
                region_id=region_id,
                logical_query={"retailer_region_id": retailer_id},
                page_number=None,
                classification="sanitization_failure",
            )
            raise ConnectorFetchError(
                "ICA context readback failed closed",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=(diagnostic,),
                    transport=self._metrics_since(before),
                ),
            ) from exc
        fetched_at = datetime.now(tz=UTC)
        raw_url = str(response.request.url.copy_with(query=None))
        common = {
            "chain": Chain.ICA,
            "store_external_id": region_id,
            "method": "GET",
            "url": raw_url,
            "query": {"retailer_region_id": retailer_id},
            "fetched_at": fetched_at,
            "http_status": response.status_code,
            "connector_version": self.connector_version,
        }
        documents = (
            RawFetch(
                **common,
                kind=ICA_STORE_CONTEXT_KIND,
                content_type="application/json; profile=sanitized-ica-store-context-v1",
                payload=context_payload,
            ),
            RawFetch(
                **common,
                kind=ICA_CATEGORY_TREE_KIND,
                content_type="application/json; profile=sanitized-ica-category-tree-v1",
                payload=category_payload,
            ),
        )
        return RawBatch(
            chain=Chain.ICA,
            documents=documents,
            transport=self._metrics_since(before),
        )

    def _page_params(
        self,
        category_id: str,
        *,
        page_token: str | None,
    ) -> list[tuple[str, object]]:
        params: list[tuple[str, object]] = [
            ("categoryId", category_id),
            ("maxPageSize", self.page_size),
            ("maxProductsToDecorate", self.max_products_to_decorate),
            ("sortOptionId", "favorite"),
            ("tag", "web"),
            ("tag", "category-item"),
        ]
        if page_token is None:
            params.insert(1, ("includeAdditionalPageInfo", "true"))
        else:
            params.insert(1, ("pageToken", page_token))
        return params

    async def fetch_product_page(
        self,
        region_id: str,
        category_id: str,
        *,
        page_token: str | None = None,
        page_index: int = 0,
    ) -> tuple[RawFetch, IcaProductPage]:
        region_id, retailer_id = self.require_context(region_id)
        raw, decoded = await self._json_request(
            "GET",
            f"/stores/{retailer_id}/api/webproductpagews/v6/product-pages",
            kind=ICA_PRODUCT_PAGE_KIND,
            region_id=region_id,
            params=self._page_params(category_id, page_token=page_token),
            logical_query={
                "category_id": category_id,
                "page_index": page_index,
                **(
                    {"previous_page_token_hash": _token_hash(page_token)}
                    if page_token is not None
                    else {}
                ),
            },
            page_number=page_index,
        )
        return raw, IcaProductPage.from_payload(decoded, category_id=category_id)

    async def fetch_product_batch(
        self,
        region_id: str,
        product_ids: Sequence[str],
        *,
        category_id: str,
        page_index: int,
        batch_index: int,
    ) -> tuple[RawFetch, IcaBatchResult]:
        region_id, retailer_id = self.require_context(region_id)
        ids = tuple(
            dict.fromkeys(str(value).strip() for value in product_ids if str(value).strip())
        )
        if not ids:
            raise ValueError("ICA product batch cannot be empty")
        if any(_PRODUCT_ID.fullmatch(value) is None for value in ids):
            raise ValueError("ICA product batch contains an invalid product UUID")
        if self.product_batch_size is None or len(ids) > self.product_batch_size:
            raise IcaOnlineSourcePolicyError("ICA product batch exceeds the verified batch size")
        raw, decoded = await self._json_request(
            "PUT",
            f"/stores/{retailer_id}/api/webproductpagews/v6/products",
            kind=ICA_PRODUCT_BATCH_KIND,
            region_id=region_id,
            logical_query={
                "category_id": category_id,
                "page_index": page_index,
                "batch_index": batch_index,
                "requested_product_ids": ids,
            },
            json_body=list(ids),
            page_number=page_index,
        )
        return raw, IcaBatchResult.from_payload(decoded, requested_product_ids=ids)

    async def fetch_search(
        self,
        region_id: str,
        query: str,
        *,
        decorate_one_batch: bool = True,
    ) -> RawBatch:
        region_id, retailer_id = self.require_context(region_id)
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise ValueError("ICA search query cannot be blank")
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        try:
            raw, decoded = await self._json_request(
                "GET",
                f"/stores/{retailer_id}/api/webproductpagews/v6/product-pages/search",
                kind=ICA_SEARCH_KIND,
                region_id=region_id,
                params={
                    "includeAdditionalPageInfo": "true",
                    "maxPageSize": self.page_size,
                    "maxProductsToDecorate": self.max_products_to_decorate,
                    "q": normalized_query,
                    "tag": "web",
                },
                logical_query={"search_query": normalized_query, "page_index": 0},
                page_number=0,
            )
            documents.append(raw)
            page = IcaProductPage.from_payload(decoded, category_id=f"search:{normalized_query}")
            if decorate_one_batch and page.other_product_ids and self.product_batch_size:
                ids = page.other_product_ids[: self.product_batch_size]
                batch_raw, _ = await self.fetch_product_batch(
                    region_id,
                    ids,
                    category_id=f"search:{normalized_query}",
                    page_index=0,
                    batch_index=0,
                )
                documents.append(batch_raw)
        except Exception as exc:
            if isinstance(exc, IcaOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            raise ConnectorFetchError(
                "ICA bounded search stopped",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=tuple(documents),
                    transport=self._metrics_since(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.ICA,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    async def _fetch_category(
        self,
        region_id: str,
        category_id: str,
        *,
        raw_sink: list[RawFetch] | None = None,
    ) -> tuple[list[RawFetch], _CategoryRun]:
        documents: list[RawFetch] = []
        products_by_id: dict[str, dict[str, Any]] = {}
        category_positions: list[str] = []
        declared_products: int | None = None
        page_token: str | None = None
        seen_token_hashes: set[str] = set()
        page_index = 0
        raw_rows = 0
        group_duplicates = 0
        placement_overlaps = 0
        completed = False
        while True:
            raw, page = await self.fetch_product_page(
                region_id,
                category_id,
                page_token=page_token,
                page_index=page_index,
            )
            documents.append(raw)
            if raw_sink is not None:
                raw_sink.append(raw)
            if page_index == 0:
                declared_products = page.declared_product_count
                if declared_products is None:
                    raise IcaOnlineSchemaError("ICA first category page lacks productCount")
            raw_rows += page.raw_product_rows
            group_duplicates += page.duplicate_metrics.exact_duplicates
            placement_overlaps += page.duplicate_metrics.placement_overlaps
            decorated = {str(row["productId"]): row for row in page.decorated_products}
            unresolved = list(page.other_product_ids)
            if unresolved:
                if self.product_batch_size is None:
                    if self.allow_full_crawl:
                        raise IcaOnlineSourcePolicyError(
                            "ICA full traversal lacks verified product batch size"
                        )
                else:
                    batches = [
                        unresolved[index : index + self.product_batch_size]
                        for index in range(0, len(unresolved), self.product_batch_size)
                    ]
                    if self.max_batches_per_page is not None:
                        batches = batches[: self.max_batches_per_page]
                    for batch_index, ids in enumerate(batches):
                        batch_raw, batch = await self.fetch_product_batch(
                            region_id,
                            ids,
                            category_id=category_id,
                            page_index=page_index,
                            batch_index=batch_index,
                        )
                        documents.append(batch_raw)
                        if raw_sink is not None:
                            raw_sink.append(batch_raw)
                        for product in batch.products:
                            decorated[str(product["productId"])] = product
            missing = [
                product_id
                for product_id in page.ordered_product_ids
                if product_id not in decorated
            ]
            if missing and self.allow_full_crawl:
                raise IcaOnlineSchemaError("ICA page has undecorated product IDs after batching")
            for product_id in page.ordered_product_ids:
                if product_id in decorated:
                    product = decorated[product_id]
                    previous = products_by_id.get(product_id)
                    if previous is not None and (
                        purchase_semantic_fingerprint(previous)
                        != purchase_semantic_fingerprint(product)
                    ):
                        raise IcaOnlineSchemaError(
                            "ICA category repeats a product with conflicting purchase semantics"
                        )
                    products_by_id.setdefault(product_id, product)
                    category_positions.append(product_id)
            if page.terminal:
                completed = True
                break
            if (
                self.max_pages_per_category is not None
                and page_index + 1 >= self.max_pages_per_category
            ):
                break
            if page.next_page_token is None:
                raise IcaOnlineSchemaError("ICA continuation page lacks its in-memory token")
            token_hash = _token_hash(page.next_page_token)
            if token_hash in seen_token_hashes:
                raise IcaOnlineSchemaError("PAGINATION_LOOP")
            seen_token_hashes.add(token_hash)
            page_token = page.next_page_token
            page_index += 1
        assert declared_products is not None
        fully_decorated = not missing
        if completed and fully_decorated and len(set(category_positions)) != declared_products:
            raise IcaOnlineSchemaError("ICA category productCount did not reconcile")
        pagination_overlaps = len(category_positions) - len(products_by_id)
        within_duplicates = group_duplicates + placement_overlaps + pagination_overlaps
        if fully_decorated and raw_rows != len(products_by_id) + within_duplicates:
            raise IcaOnlineSchemaError("ICA category duplicate metrics do not reconcile raw rows")
        return documents, _CategoryRun(
            declared_products=declared_products,
            page_count=page_index + 1,
            products=tuple(products_by_id.values()),
            raw_rows=raw_rows,
            exact_group_duplicates=group_duplicates,
            within_duplicates=within_duplicates,
            pagination_overlaps=pagination_overlaps,
            complete=completed and fully_decorated,
        )

    @staticmethod
    def _completion(
        *,
        complete: bool,
        limited: bool,
        expected_categories: int,
        completed_categories: int,
        pages_fetched: int,
        tracker: _TraversalTracker,
        reason: str | None,
    ) -> CatalogCompletion:
        duplicates = tracker.within_duplicates + tracker.cross_duplicates
        return CatalogCompletion(
            complete=complete,
            limited=limited,
            expected_categories=expected_categories,
            completed_categories=completed_categories,
            pages_fetched=pages_fetched,
            products_observed=len(tracker.seen),
            expected_products=tracker.raw_rows,
            raw_rows=tracker.raw_rows,
            unique_products=len(tracker.seen),
            duplicate_products=duplicates,
            within_partition_duplicates=tracker.within_duplicates,
            cross_partition_duplicates=tracker.cross_duplicates,
            # CatalogCompletion defines this counter inside one traversal
            # partition. Cross-category overlap is legitimate and reported
            # separately, not presented as an intra-category repair.
            exact_duplicates_removed=tracker.within_duplicates,
            conflicting_duplicates=tracker.conflicting_duplicates,
            pagination_overlaps=tracker.pagination_overlaps,
            expected_pages=pages_fetched,
            reason=reason,
        )

    async def fetch_catalog(self, region_id: str) -> RawBatch:
        region_id, _ = self.require_context(region_id)
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        tracker = _TraversalTracker.create()
        expected_categories = 0
        completed_categories = 0
        pages_fetched = 0
        try:
            context_batch = await self.fetch_context(region_id)
            documents.extend(context_batch.documents)
            tree_document = next(
                document
                for document in context_batch.documents
                if document.kind == ICA_CATEGORY_TREE_KIND
            )
            tree = IcaCategoryTree.from_payload(tree_document.json_payload())
            terminal_categories = list(tree.terminal_nodes)
            expected_categories = len(terminal_categories)
            selected = (
                terminal_categories
                if self.max_categories is None
                else terminal_categories[: self.max_categories]
            )
            for category in selected:
                _, result = await self._fetch_category(
                    region_id,
                    category.category_id,
                    raw_sink=documents,
                )
                pages_fetched += result.page_count
                if result.complete:
                    completed_categories += 1
                for product in result.products:
                    tracker.observe(
                        product,
                        category_id=category.category_id,
                        page_index=0,
                    )
                # `_fetch_category` has already proven every repeated row has
                # identical purchase semantics. Account for those source rows
                # after observing the category's unique products globally.
                classified_within = (
                    result.raw_rows - len(result.products)
                    if result.complete
                    else result.within_duplicates
                )
                tracker.raw_rows += classified_within
                tracker.within_duplicates += classified_within
                tracker.exact_duplicates += classified_within
                tracker.pagination_overlaps += result.pagination_overlaps
        except Exception as exc:
            if isinstance(exc, IcaOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            completion = (
                self._completion(
                    complete=False,
                    limited=not self.allow_full_crawl,
                    expected_categories=expected_categories,
                    completed_categories=completed_categories,
                    pages_fetched=pages_fetched,
                    tracker=tracker,
                    reason=type(exc).__name__,
                )
                if expected_categories
                else None
            )
            raise ConnectorFetchError(
                "ICA online catalogue traversal stopped",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=tuple(documents),
                    transport=self._metrics_since(before),
                    catalog_completion=completion,
                ),
            ) from exc

        full_authority = (
            self.allow_full_crawl
            and self.max_categories is None
            and self.max_pages_per_category is None
            and self.max_batches_per_page is None
            and self.product_batch_size is not None
        )
        complete = (
            full_authority
            and completed_categories == expected_categories
            and tracker.conflicting_duplicates == 0
        )
        completion = self._completion(
            complete=complete,
            limited=not full_authority,
            expected_categories=expected_categories,
            completed_categories=completed_categories,
            pages_fetched=pages_fetched,
            tracker=tracker,
            reason=None if complete else "source policy REVIEW: bounded discovery",
        )
        batch = RawBatch(
            chain=Chain.ICA,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )
        if full_authority and not completion.is_full_traversal:
            raise ConnectorFetchError("ICA category union did not reconcile", partial_batch=batch)
        return batch

    async def aclose(self) -> None:
        self._client.cookies.clear()
        if self._owns_client:
            await self._client.aclose()
