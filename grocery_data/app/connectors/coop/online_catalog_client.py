from __future__ import annotations

import asyncio
import html
import json
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import quote, urlsplit

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.coop.models import CoopSchemaError
from grocery_data.app.connectors.coop.online_catalog_models import (
    CoopOnlineCategoryNode,
    CoopOnlineResultsPage,
    validated_category_tree,
    validated_results_page,
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
    TransportMetrics,
)

COOP_CATEGORY_TREE_KIND = "coop_category_tree"
COOP_PRODUCT_SEARCH_KIND = "coop_product_search"
COOP_PRODUCT_CATEGORY_PAGE_KIND = "coop_product_category_page"
COOP_PRODUCT_BY_ID_KIND = "coop_product_by_id"
COOP_PROMOTIONS_KIND = "coop_promotions"
COOP_PROMOTION_KIND = "coop_promotion"
COOP_FULFILLMENT_MAPPING_KIND = "coop_fulfillment_mapping"

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
    b"request blocked",
    b"verify you are human",
)
_STOP_CONTENT_TYPE = "application/json; profile=coop-online-transport-stop-v1"
_SAFE_API_QUERY_KEYS = frozenset(
    {
        "api-version",
        "store",
        "groups",
        "device",
        "direct",
        "only-primary",
        "fields",
        "query",
    }
)
_SAFE_LOGICAL_QUERY_KEYS = frozenset(
    {
        "category_id",
        "category_name",
        "search_query",
        "skip",
        "take",
        "promotion_id",
        "product_ids",
        "point_of_service_id",
    }
)
_FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "accesstoken",
        "authtoken",
        "refreshtoken",
        "token",
        "uid",
        "sid",
        "userid",
        "sessionid",
        "trackingid",
        "visitorid",
        "deviceid",
    }
)
_FORBIDDEN_PAYLOAD_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "subscriptionkey",
    "apikey",
    "csrf",
    "xsrf",
    "session",
    "tracking",
)
_PURCHASE_SEMANTIC_FIELDS = (
    "id",
    "ean",
    "name",
    "variety",
    "manufacturerName",
    "availableOnline",
    "salesPriceData",
    "pricePriceData",
    "promotionPriceData",
    "piecePriceData",
    "comparativePriceData",
    "comparativePriceText",
    "comparativePriceUnit",
    "packageSize",
    "packageSizeInformation",
    "packageSizeUnit",
    "salesUnit",
    "displayWeightPrice",
    "pieceWeight",
    "onlinePromotions",
    "promotionProductsEans",
    "depositData",
)


class CoopOnlineHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class CoopOnlineSourcePolicyError(RuntimeError):
    """The requested online traversal is outside Coop's REVIEW authority."""


class CoopOnlineAccessChallenge(CoopOnlineHttpError):
    """The ordinary public API surface returned an access challenge."""


class CoopOnlineRateLimitStop(CoopOnlineHttpError):
    """A 429 stops the current run; no session or identity rotation is attempted."""

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


class CoopOnlineAccessChallengeFetchError(ConnectorFetchError):
    """Persistable fail-closed access result for an online collection."""


class CoopOnlineRateLimitFetchError(ConnectorFetchError):
    """Persistable fail-closed rate-limit result for an online collection."""


def _environment_flag(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    raise CoopOnlineSourcePolicyError(
        f"{name} must be one of true/false/1/0; refusing ambiguous policy value"
    )


def _configured_context_ids(value: Iterable[str] | str | None) -> frozenset[str]:
    if value is None:
        values: Iterable[str] = os.getenv("COOP_ONLINE_CONTEXT_IDS", "").split(",")
    elif isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    return frozenset(context_id.strip() for context_id in values if context_id.strip())


@dataclass(frozen=True, slots=True)
class CoopOnlineOperatorCrawlPolicy:
    """Closed, non-secret view of explicit operator authority."""

    allow_full_crawl: bool
    allowed_context_ids: frozenset[str]

    @classmethod
    def from_environment(cls) -> CoopOnlineOperatorCrawlPolicy:
        return cls(
            allow_full_crawl=_environment_flag("COOP_ALLOW_FULL_CRAWL", default=False),
            allowed_context_ids=_configured_context_ids(None),
        )

    def permits(self, context_id: str) -> bool:
        normalized = context_id.strip()
        return bool(normalized and self.allow_full_crawl and normalized in self.allowed_context_ids)

    def require(self, context_id: str) -> str:
        normalized = context_id.strip()
        if not normalized:
            raise CoopOnlineSourcePolicyError("Coop online context ID must not be blank")
        if not self.allow_full_crawl:
            raise CoopOnlineSourcePolicyError(
                "Coop source policy REVIEW requires COOP_ALLOW_FULL_CRAWL=true"
            )
        if normalized not in self.allowed_context_ids:
            raise CoopOnlineSourcePolicyError(
                f"Coop online context {normalized} is outside COOP_ONLINE_CONTEXT_IDS"
            )
        return normalized


@dataclass(frozen=True, slots=True, repr=False)
class CoopOnlinePublicApiConfig:
    """Transient public-frontend transport configuration.

    Subscription values are intentionally private to this in-memory object. It
    has a redacted representation and is never included in RawFetch metadata.
    """

    personalization_base_url: str
    ecommerce_base_url: str
    personalization_subscription_key: str = field(repr=False)
    ecommerce_subscription_key: str = field(repr=False)
    api_version: str = "v1"
    ecommerce_api_version: str | None = None

    def __repr__(self) -> str:
        return (
            "CoopOnlinePublicApiConfig("
            f"personalization_base_url={self.personalization_base_url!r}, "
            f"ecommerce_base_url={self.ecommerce_base_url!r}, "
            "personalization_subscription_key='[REDACTED]', "
            "ecommerce_subscription_key='[REDACTED]', "
            f"api_version={self.api_version!r}, "
            f"ecommerce_api_version={self.ecommerce_api_version!r})"
        )


def _config_value(document: str, *names: str) -> str | None:
    # Runtime JSON is embedded in ordinary public HTML. Decode HTML entities
    # and JSON-escaped quote delimiters without logging the resulting document.
    decoded = html.unescape(document).replace(r"\"", '"')
    for name in names:
        pattern = re.compile(
            rf'["\']{re.escape(name)}["\']\s*:\s*["\']([^"\']+)["\']',
            re.IGNORECASE,
        )
        match = pattern.search(decoded)
        if match is not None:
            return match.group(1).strip()
    return None


def _validated_public_key(value: str | None, *, field_name: str) -> str:
    if (
        value is None
        or not 8 <= len(value) <= 512
        or any(character.isspace() for character in value)
    ):
        raise CoopOnlineSourcePolicyError(f"Coop public runtime config lacks a valid {field_name}")
    return value


def _validated_runtime_base(
    value: str | None,
    *,
    fallback: str,
    expected_path_suffix: str,
) -> str:
    candidate = (value or fallback).strip().rstrip("/")
    parsed = urlsplit(candidate)
    if parsed.scheme != "https" or parsed.hostname != "external.api.coop.se":
        raise CoopOnlineSourcePolicyError("Coop runtime config referenced an unexpected API host")
    path = parsed.path.rstrip("/")
    # Some frontend configurations include the `/coop` OCC prefix and some
    # expose the API root. Normalize to the stable root used by this client.
    if expected_path_suffix == "/ecommerce" and path.endswith("/ecommerce/coop"):
        path = path.removesuffix("/coop")
    if not path.endswith(expected_path_suffix):
        raise CoopOnlineSourcePolicyError("Coop runtime config referenced an unexpected API path")
    return f"https://{parsed.hostname}{path}"


def public_api_config_from_html(document: str) -> CoopOnlinePublicApiConfig:
    """Extract only the two public frontend transport values, in memory."""

    personalization_key = _validated_public_key(
        _config_value(
            document,
            "personalizationApiSubscriptionKey",
            "personalizationSubscriptionKey",
        ),
        field_name="personalization subscription value",
    )
    ecommerce_key = _validated_public_key(
        _config_value(
            document,
            "hybrisApiSubscriptionKey",
            "ecommerceApiSubscriptionKey",
        ),
        field_name="ecommerce subscription value",
    )
    api_version = (
        _config_value(
            document,
            "personalizationApiVersion",
            "apiVersion",
        )
        or "v1"
    )
    if not re.fullmatch(r"v\d+", api_version):
        raise CoopOnlineSourcePolicyError("Coop runtime config has an invalid API version")
    ecommerce_api_version = (
        _config_value(document, "hybrisApiVersion", "ecommerceApiVersion", "apiVersion")
        or "v1"
    )
    if not re.fullmatch(r"v\d+", ecommerce_api_version):
        raise CoopOnlineSourcePolicyError("Coop runtime config has an invalid ecommerce API version")
    return CoopOnlinePublicApiConfig(
        personalization_base_url=_validated_runtime_base(
            _config_value(
                document,
                "personalizationApiUrl",
                "personalizationApiBaseUrl",
            ),
            fallback="https://external.api.coop.se/personalization",
            expected_path_suffix="/personalization",
        ),
        ecommerce_base_url=_validated_runtime_base(
            _config_value(document, "hybrisApiUrl", "ecommerceApiUrl"),
            fallback="https://external.api.coop.se/ecommerce",
            expected_path_suffix="/ecommerce",
        ),
        personalization_subscription_key=personalization_key,
        ecommerce_subscription_key=ecommerce_key,
        api_version=api_version,
        ecommerce_api_version=ecommerce_api_version,
    )


def _normalized_payload_key(value: object) -> str:
    return "".join(character for character in str(value).casefold() if character.isalnum())


def _payload_key_is_forbidden(value: object) -> bool:
    normalized = _normalized_payload_key(value)
    return normalized in _FORBIDDEN_PAYLOAD_KEYS or any(
        fragment in normalized for fragment in _FORBIDDEN_PAYLOAD_KEY_FRAGMENTS
    )


def _sanitized_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {
            str(key): _sanitized_json_value(child)
            for key, child in value.items()
            if not _payload_key_is_forbidden(key)
        }
    if isinstance(value, list):
        return [_sanitized_json_value(child) for child in value]
    return value


def sanitized_api_payload(payload: object) -> bytes:
    """Canonical sanitized JSON; request/session identity is never retained."""

    return json.dumps(
        _sanitized_json_value(payload),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _looks_like_access_challenge(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return False
    if response.status_code in {401, 403, 405}:
        return True
    beginning = response.content[:65536].lstrip().lower()
    return any(marker in beginning for marker in _ACCESS_CHALLENGE_MARKERS)


def _purchase_semantic_fingerprint(row: dict[str, Any]) -> str:
    return json.dumps(
        {field: row.get(field) for field in _PURCHASE_SEMANTIC_FIELDS},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


@dataclass(slots=True)
class _DuplicateTracker:
    seen_ids: set[str] = field(default_factory=set)
    semantic_by_id: dict[str, str] = field(default_factory=dict)
    exact_by_partition_id: dict[tuple[str, str], str] = field(default_factory=dict)
    page_by_partition_id: dict[tuple[str, str], int] = field(default_factory=dict)
    raw_rows: int = 0
    within_partition_duplicates: int = 0
    cross_partition_duplicates: int = 0
    exact_duplicates_removed: int = 0
    conflicting_duplicates: int = 0
    pagination_overlaps: int = 0

    def observe(self, row: dict[str, Any], *, partition: str, page_number: int) -> None:
        self.raw_rows += 1
        product_id = str(row.get("id") or "").strip()
        if not product_id:
            raise CoopSchemaError("Coop online row lacks stable product id")
        key = (partition, product_id)
        # Navigation placement, rank and search decoration can legitimately
        # differ. A repeat is removable only when every captured identity,
        # price, package, promotion and availability field is unchanged.
        exact = _purchase_semantic_fingerprint(row)
        semantic = _purchase_semantic_fingerprint(row)
        if key in self.exact_by_partition_id:
            self.within_partition_duplicates += 1
            if self.exact_by_partition_id[key] != exact:
                self.conflicting_duplicates += 1
                raise CoopSchemaError(
                    f"Coop within-category duplicate changed product fields: {product_id}"
                )
            self.exact_duplicates_removed += 1
            if self.page_by_partition_id[key] != page_number:
                self.pagination_overlaps += 1
            return

        self.exact_by_partition_id[key] = exact
        self.page_by_partition_id[key] = page_number
        if product_id in self.seen_ids:
            self.cross_partition_duplicates += 1
            if self.semantic_by_id[product_id] != semantic:
                self.conflicting_duplicates += 1
                raise CoopSchemaError(
                    f"Coop cross-category duplicate changed purchase semantics: {product_id}"
                )
            return
        self.seen_ids.add(product_id)
        self.semantic_by_id[product_id] = semantic

    @property
    def duplicate_products(self) -> int:
        return self.within_partition_duplicates + self.cross_partition_duplicates

    def completion_fields(self) -> dict[str, int]:
        return {
            "within_partition_duplicates": self.within_partition_duplicates,
            "cross_partition_duplicates": self.cross_partition_duplicates,
            "exact_duplicates_removed": self.exact_duplicates_removed,
            "conflicting_duplicates": self.conflicting_duplicates,
            "pagination_overlaps": self.pagination_overlaps,
        }


class CoopOnlineCatalogClient:
    """Public Coop online API transport with a closed REVIEW policy.

    The anonymous storefront's APIM subscription values are loaded from its
    ordinary HTML runtime configuration, held only in memory, passed only to
    the matching API surface, and never represented in raw evidence.
    """

    connector_version = "coop-online-catalog-v1"
    default_bootstrap_url = "https://www.coop.se/handla/"

    def __init__(
        self,
        *,
        bootstrap_url: str | None = None,
        public_api_config: CoopOnlinePublicApiConfig | None = None,
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        category_page_size: int = 48,
        search_page_size: int = 24,
        max_categories: int | None = 1,
        max_pages_per_category: int | None = 1,
        allow_full_crawl: bool | None = None,
        max_concurrency: int | None = None,
        allowed_context_ids: Iterable[str] | str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if category_page_size <= 0 or search_page_size <= 0:
            raise ValueError("Coop online page sizes must be positive")
        if max_categories is not None and max_categories <= 0:
            raise ValueError("max_categories must be positive or None")
        if max_pages_per_category is not None and max_pages_per_category <= 0:
            raise ValueError("max_pages_per_category must be positive or None")
        self.allow_full_crawl = (
            _environment_flag("COOP_ALLOW_FULL_CRAWL", default=False)
            if allow_full_crawl is None
            else allow_full_crawl
        )
        if not isinstance(self.allow_full_crawl, bool):
            raise TypeError("allow_full_crawl must be a boolean")
        traversal_is_bounded = max_categories == 1 and max_pages_per_category == 1
        if not self.allow_full_crawl and not traversal_is_bounded:
            raise CoopOnlineSourcePolicyError(
                "Coop source policy REVIEW permits one category/page only; "
                "set COOP_ALLOW_FULL_CRAWL=true for a wider traversal"
            )
        if not self.allow_full_crawl and (category_page_size > 48 or search_page_size > 24):
            raise CoopOnlineSourcePolicyError(
                "Coop bounded discovery is limited to normal frontend page sizes"
            )

        self.requests_per_second = (
            float(os.getenv("COOP_ONLINE_REQUESTS_PER_SECOND", "0.5"))
            if requests_per_second is None
            else requests_per_second
        )
        if self.requests_per_second <= 0:
            raise ValueError("COOP_ONLINE_REQUESTS_PER_SECOND must be positive")
        if self.allow_full_crawl and not 0.5 <= self.requests_per_second <= 1.0:
            raise CoopOnlineSourcePolicyError(
                "Coop full collection must run between 0.5 and 1 request/second"
            )
        self.max_concurrency = (
            int(os.getenv("COOP_ONLINE_MAX_CONCURRENCY", "1"))
            if max_concurrency is None
            else max_concurrency
        )
        if self.max_concurrency != 1:
            raise CoopOnlineSourcePolicyError("Coop online collection requires concurrency=1")

        self.allowed_context_ids = _configured_context_ids(allowed_context_ids)
        if self.allow_full_crawl and not self.allowed_context_ids:
            raise CoopOnlineSourcePolicyError(
                "Coop full crawl requires non-empty COOP_ONLINE_CONTEXT_IDS"
            )
        self.category_page_size = category_page_size
        self.search_page_size = search_page_size
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        self.bootstrap_url = (bootstrap_url or self.default_bootstrap_url).strip()
        parsed_bootstrap = urlsplit(self.bootstrap_url)
        if parsed_bootstrap.scheme != "https" or not parsed_bootstrap.netloc:
            raise ValueError("Coop bootstrap URL must be absolute HTTPS")

        self._limiter = AsyncRateLimiter(self.requests_per_second)
        self._request_slots = asyncio.Semaphore(1)
        self._retry = retry_policy or RetryPolicy()
        if not 1 <= self._retry.attempts <= 3:
            raise ValueError("Coop retry attempts must be between 1 and 3")
        if self._retry.base_delay_seconds < 0 or self._retry.max_delay_seconds < 0:
            raise ValueError("Coop retry delays must be non-negative")
        self._request_count = 0
        self._http_error_count = 0
        self._rate_limit_count = 0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
            headers={
                "User-Agent": os.getenv(
                    "GROCERY_DATA_USER_AGENT",
                    "grocery-data-poc/0.1 (+source-transparency)",
                )
            },
        )
        self._public_api_config = public_api_config

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
        # Drop public frontend values before closing; they were never persisted.
        self._public_api_config = None
        if self._owns_client:
            await self._client.aclose()

    def context_allowed(self, context_id: str) -> bool:
        return context_id.strip() in self.allowed_context_ids

    def require_context(self, context_id: str) -> str:
        normalized = context_id.strip()
        if not normalized:
            raise CoopOnlineSourcePolicyError("Coop online context ID must not be blank")
        if normalized not in self.allowed_context_ids:
            raise CoopOnlineSourcePolicyError(
                f"Coop online context {normalized} is outside COOP_ONLINE_CONTEXT_IDS"
            )
        return normalized

    async def _config(self) -> CoopOnlinePublicApiConfig:
        if self._public_api_config is not None:
            return self._public_api_config
        async with self._request_slots:
            response = await bounded_request(
                self._client,
                self._limiter,
                self._retry,
                "GET",
                self.bootstrap_url,
                headers={"Accept": "text/html,application/xhtml+xml"},
                on_attempt=self._observe_attempt,
                stop_retry=_looks_like_access_challenge,
                retry_rate_limits=False,
            )
        # Cookies or other browser state are neither needed nor retained.
        self._client.cookies.clear()
        if response.status_code == 429:
            raise CoopOnlineSourcePolicyError("Coop public bootstrap was rate limited")
        if response.is_error or _looks_like_access_challenge(response):
            raise CoopOnlineSourcePolicyError("Coop public bootstrap was unavailable")
        try:
            config = public_api_config_from_html(response.text)
        finally:
            # Do not retain the HTML document that contains runtime transport values.
            response = None  # type: ignore[assignment]
        self._public_api_config = config
        return config

    @staticmethod
    def _safe_query_metadata(
        params: dict[str, object],
        logical: dict[str, object] | None,
    ) -> dict[str, str]:
        unexpected = set(params) - _SAFE_API_QUERY_KEYS
        if unexpected:
            raise ValueError("Coop raw query metadata contains a non-allowlisted key")
        logical_values = logical or {}
        unexpected_logical = set(logical_values) - _SAFE_LOGICAL_QUERY_KEYS
        if unexpected_logical:
            raise ValueError("Coop raw logical metadata contains a non-allowlisted key")
        return {
            str(key): ",".join(str(item) for item in value)
            if isinstance(value, (tuple, list))
            else str(value).lower()
            if isinstance(value, bool)
            else str(value)
            for key, value in {**params, **logical_values}.items()
        }

    async def _api_request(
        self,
        surface: Literal["personalization", "ecommerce"],
        method: Literal["GET", "POST"],
        path: str,
        *,
        kind: str,
        context_id: str | None,
        params: dict[str, object],
        logical_query: dict[str, object] | None = None,
        json_body: object | None = None,
        page_number: int | None = None,
    ) -> RawFetch:
        if not path.startswith("/") or urlsplit(path).scheme or urlsplit(path).netloc:
            raise ValueError("Coop API path must be a same-service absolute path")
        config = await self._config()
        if surface == "personalization":
            base_url = config.personalization_base_url
            subscription_value = config.personalization_subscription_key
        else:
            base_url = config.ecommerce_base_url
            subscription_value = config.ecommerce_subscription_key
        request_params = dict(params)
        version = (config.ecommerce_api_version or config.api_version) if surface == "ecommerce" else config.api_version
        request_params.setdefault("api-version", version)
        safe_query = self._safe_query_metadata(request_params, logical_query)
        async with self._request_slots:
            response = await bounded_request(
                self._client,
                self._limiter,
                self._retry,
                method,
                f"{base_url}{path}",
                params=request_params,
                json=json_body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Ocp-Apim-Subscription-Key": subscription_value,
                },
                on_attempt=self._observe_attempt,
                stop_retry=_looks_like_access_challenge,
                retry_rate_limits=False,
            )

        is_rate_limit = response.status_code == 429
        is_challenge = _looks_like_access_challenge(response)
        try:
            decoded: object = response.json()
        except ValueError:
            decoded = None
        if is_rate_limit or is_challenge or decoded is None:
            classification = (
                "rate_limited"
                if is_rate_limit
                else "access_challenge"
                if is_challenge
                else "non_json_response"
            )
            payload = json.dumps(
                {
                    "classification": classification,
                    "http_status": response.status_code,
                    "schema": "coop-online-transport-stop-v1",
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            raw_kind = classification
            content_type = _STOP_CONTENT_TYPE
        else:
            payload = sanitized_api_payload(decoded)
            raw_kind = kind
            content_type = "application/json; profile=sanitized-coop-public-api-v1"
        raw = RawFetch(
            chain=Chain.COOP,
            store_external_id=context_id,
            kind=raw_kind,
            method=method,
            url=str(response.request.url.copy_with(query=None)),
            query=safe_query,
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=content_type,
            payload=payload,
            connector_version=self.connector_version,
            page_number=page_number,
        )
        if is_rate_limit:
            raise CoopOnlineRateLimitStop(
                "Coop online API was rate limited; current run stopped",
                raw,
                retry_after=retry_after_seconds(response, self._retry.max_delay_seconds),
                retry_after_raw=response.headers.get("Retry-After"),
            )
        if is_challenge:
            raise CoopOnlineAccessChallenge(
                f"Coop online API returned an access challenge (HTTP {response.status_code})",
                raw,
            )
        if response.is_error:
            raise CoopOnlineHttpError(
                f"Coop online API returned HTTP {response.status_code}",
                raw,
            )
        if decoded is None:
            raise CoopOnlineHttpError("Coop online API returned non-JSON content", raw)
        return raw

    @staticmethod
    def _result_page(
        document: RawFetch,
        *,
        skip: int,
        take: int,
        expected_query: str | None = None,
    ) -> CoopOnlineResultsPage:
        return validated_results_page(
            document.json_payload(),
            requested_skip=skip,
            requested_take=take,
            expected_query=expected_query,
        )

    @staticmethod
    def _search_params(context_id: str, *, direct: bool = False) -> dict[str, object]:
        return {
            "store": context_id,
            "groups": "CUSTOMER_PRIVATE",
            "device": "desktop",
            "direct": direct,
        }

    @staticmethod
    def _completion(
        *,
        complete: bool,
        limited: bool,
        expected_categories: int,
        completed_categories: int,
        pages_fetched: int,
        expected_products: int,
        expected_pages: int,
        tracker: _DuplicateTracker,
        reason: str | None,
    ) -> CatalogCompletion:
        return CatalogCompletion(
            complete=complete,
            limited=limited,
            expected_categories=expected_categories,
            completed_categories=completed_categories,
            pages_fetched=pages_fetched,
            products_observed=len(tracker.seen_ids),
            expected_products=expected_products,
            raw_rows=tracker.raw_rows,
            unique_products=len(tracker.seen_ids),
            duplicate_products=tracker.duplicate_products,
            expected_pages=expected_pages,
            reason=reason,
            **tracker.completion_fields(),
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
        error_type: type[ConnectorFetchError] = (
            CoopOnlineAccessChallengeFetchError
            if isinstance(exc, CoopOnlineAccessChallenge)
            else CoopOnlineRateLimitFetchError
            if isinstance(exc, CoopOnlineRateLimitStop)
            else ConnectorFetchError
        )
        message = (
            str(exc)
            if isinstance(exc, (CoopOnlineAccessChallenge, CoopOnlineRateLimitStop))
            else fallback_message
        )
        return error_type(
            message,
            partial_batch=RawBatch(
                chain=Chain.COOP,
                documents=tuple(documents),
                transport=self._metrics_since(before),
                catalog_completion=completion,
            ),
        )

    async def fetch_category_tree(self, context_id: str) -> RawFetch:
        context_id = self.require_context(context_id)
        document = await self._api_request(
            "ecommerce",
            "GET",
            f"/coop/users/anonymous/categories/tree/{quote(context_id, safe='')}",
            kind=COOP_CATEGORY_TREE_KIND,
            context_id=context_id,
            params={},
        )
        try:
            validated_category_tree(document.json_payload())
        except (TypeError, ValueError) as exc:
            raise CoopOnlineHttpError(
                "Coop online category-tree schema changed",
                document,
            ) from exc
        return document

    async def _category_page(
        self,
        context_id: str,
        category: CoopOnlineCategoryNode,
        *,
        skip: int,
        page_number: int,
    ) -> tuple[RawFetch, CoopOnlineResultsPage]:
        details = category.url or category.canonical_path or ""
        document = await self._api_request(
            "personalization",
            "POST",
            "/search/entities/by-attribute",
            kind=COOP_PRODUCT_CATEGORY_PAGE_KIND,
            context_id=context_id,
            params=self._search_params(context_id),
            logical_query={
                "category_id": category.code,
                "category_name": category.name,
                "skip": skip,
                "take": self.category_page_size,
            },
            json_body={
                "attribute": {"name": "categoryIds", "value": category.code},
                "requestAlias": {
                    "name": "Subcategory",
                    "value": category.name,
                    "details": details,
                },
                "resultsOptions": {
                    "skip": skip,
                    "take": self.category_page_size,
                    "sortBy": [],
                    "facets": [
                        {
                            "attributeName": "manufacturerName",
                            "type": "distinct",
                            "operator": "OR",
                            "name": "brand",
                            "selected": [],
                        },
                        {
                            "attributeName": "filterLabels",
                            "type": "distinct",
                            "operator": "OR",
                            "name": "environmentalLabels",
                            "selected": [],
                        },
                    ],
                },
                "customData": {"getEntitiesByAttributeABTest": False},
            },
            page_number=page_number,
        )
        try:
            page = self._result_page(
                document,
                skip=skip,
                take=self.category_page_size,
            )
        except (TypeError, ValueError) as exc:
            raise CoopOnlineHttpError(
                "Coop online category-page schema changed",
                document,
            ) from exc
        return document, page

    async def fetch_category(
        self,
        context_id: str,
        category: CoopOnlineCategoryNode,
        *,
        max_pages: int | None = 1,
    ) -> RawBatch:
        """Fetch one category to a declared offset termination condition."""

        context_id = self.require_context(context_id)
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive or None")
        if max_pages != 1 and not self.allow_full_crawl:
            raise CoopOnlineSourcePolicyError(
                "Coop multi-page category proof requires COOP_ALLOW_FULL_CRAWL=true"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        tracker = _DuplicateTracker()
        first_count: int | None = None
        expected_pages = 0
        pages_fetched = 0
        completed = False
        try:
            page_number = 0
            while True:
                skip = page_number * self.category_page_size
                document, page = await self._category_page(
                    context_id,
                    category,
                    skip=skip,
                    page_number=page_number,
                )
                documents.append(document)
                pages_fetched += 1
                if first_count is None:
                    first_count = page.reported_count
                    expected_pages = page.expected_pages
                elif page.reported_count != first_count:
                    raise CoopSchemaError("Coop category total changed during traversal")
                for row in page.items:
                    tracker.observe(row, partition=category.code, page_number=page_number)
                page_number += 1
                if page_number >= expected_pages:
                    completed = True
                    break
                if max_pages is not None and page_number >= max_pages:
                    break
        except Exception as exc:
            if isinstance(exc, CoopOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            completion = (
                self._completion(
                    complete=False,
                    limited=max_pages is not None,
                    expected_categories=1,
                    completed_categories=0,
                    pages_fetched=pages_fetched,
                    expected_products=first_count,
                    expected_pages=expected_pages,
                    tracker=tracker,
                    reason=type(exc).__name__,
                )
                if first_count is not None
                else None
            )
            raise self._fetch_error(
                exc,
                "Coop online category traversal aborted",
                documents=documents,
                before=before,
                completion=completion,
            ) from exc

        assert first_count is not None
        explicitly_limited = max_pages is not None
        exact_reconciles = (
            completed
            and tracker.raw_rows == first_count
            and tracker.conflicting_duplicates == 0
            and tracker.exact_duplicates_removed == tracker.within_partition_duplicates
        )
        completion = self._completion(
            complete=not explicitly_limited and exact_reconciles,
            limited=explicitly_limited,
            expected_categories=1,
            completed_categories=1 if completed else 0,
            pages_fetched=pages_fetched,
            expected_products=first_count,
            expected_pages=expected_pages,
            tracker=tracker,
            reason=None
            if not explicitly_limited and exact_reconciles
            else "bounded category proof",
        )
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )

    async def fetch_search(
        self,
        context_id: str,
        query: str,
        *,
        max_pages: int | None = 1,
    ) -> RawBatch:
        """Reproduce the public skip/take product-search contract."""

        context_id = self.require_context(context_id)
        normalized_query = " ".join(query.split())
        if not normalized_query:
            raise ValueError("Coop product search query must not be blank")
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive or None")
        if max_pages != 1 and not self.allow_full_crawl:
            raise CoopOnlineSourcePolicyError(
                "Coop multi-page search proof requires COOP_ALLOW_FULL_CRAWL=true"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        tracker = _DuplicateTracker()
        first_count: int | None = None
        expected_pages = 0
        pages_fetched = 0
        completed = False
        try:
            page_number = 0
            while True:
                skip = page_number * self.search_page_size
                document = await self._api_request(
                    "personalization",
                    "POST",
                    "/search/products",
                    kind=COOP_PRODUCT_SEARCH_KIND,
                    context_id=context_id,
                    params=self._search_params(context_id),
                    logical_query={
                        "search_query": normalized_query,
                        "skip": skip,
                        "take": self.search_page_size,
                    },
                    json_body={
                        "query": normalized_query,
                        "resultsOptions": {
                            "skip": skip,
                            "take": self.search_page_size,
                            "sortBy": [],
                            "facets": [],
                        },
                        "relatedResultsOptions": {"skip": 0, "take": 16},
                        "customData": {"consent": True},
                    },
                    page_number=page_number,
                )
                documents.append(document)
                try:
                    page = self._result_page(
                        document,
                        skip=skip,
                        take=self.search_page_size,
                        expected_query=normalized_query,
                    )
                except (TypeError, ValueError) as exc:
                    raise CoopOnlineHttpError(
                        "Coop online search-page schema changed",
                        document,
                    ) from exc
                pages_fetched += 1
                if first_count is None:
                    first_count = page.reported_count
                    expected_pages = page.expected_pages
                elif page.reported_count != first_count:
                    raise CoopSchemaError("Coop search result count changed during traversal")
                for row in page.items:
                    tracker.observe(row, partition="search", page_number=page_number)
                page_number += 1
                if page_number >= expected_pages:
                    completed = True
                    break
                if max_pages is not None and page_number >= max_pages:
                    break
        except Exception as exc:
            if isinstance(exc, CoopOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            completion = (
                self._completion(
                    complete=False,
                    limited=max_pages is not None,
                    expected_categories=1,
                    completed_categories=0,
                    pages_fetched=pages_fetched,
                    expected_products=first_count,
                    expected_pages=expected_pages,
                    tracker=tracker,
                    reason=type(exc).__name__,
                )
                if first_count is not None
                else None
            )
            raise self._fetch_error(
                exc,
                "Coop product search traversal aborted",
                documents=documents,
                before=before,
                completion=completion,
            ) from exc

        assert first_count is not None
        explicitly_limited = max_pages is not None
        exact_reconciles = (
            completed
            and tracker.raw_rows == first_count
            and tracker.conflicting_duplicates == 0
            and tracker.exact_duplicates_removed == tracker.within_partition_duplicates
        )
        completion = self._completion(
            complete=not explicitly_limited and exact_reconciles,
            limited=explicitly_limited,
            expected_categories=1,
            completed_categories=1 if completed else 0,
            pages_fetched=pages_fetched,
            expected_products=first_count,
            expected_pages=expected_pages,
            tracker=tracker,
            reason=None if not explicitly_limited and exact_reconciles else "bounded search proof",
        )
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )

    async def fetch_catalog(self, context_id: str) -> RawBatch:
        """Traverse every terminal category under an explicit full-crawl gate."""

        context_id = self.require_context(context_id)
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        tracker = _DuplicateTracker()
        expected_products = 0
        expected_pages = 0
        pages_fetched = 0
        completed_categories = 0
        expected_categories: int | None = None
        try:
            tree_document = await self.fetch_category_tree(context_id)
            documents.append(tree_document)
            terminal_categories = list(
                validated_category_tree(tree_document.json_payload()).terminal_nodes()
            )
            expected_categories = len(terminal_categories)
            selected_categories = (
                terminal_categories
                if self.max_categories is None
                else terminal_categories[: self.max_categories]
            )
            for category in selected_categories:
                category_count: int | None = None
                category_expected_pages = 0
                page_number = 0
                while True:
                    skip = page_number * self.category_page_size
                    document, page = await self._category_page(
                        context_id,
                        category,
                        skip=skip,
                        page_number=page_number,
                    )
                    documents.append(document)
                    pages_fetched += 1
                    if category_count is None:
                        category_count = page.reported_count
                        category_expected_pages = page.expected_pages
                        expected_products += category_count
                        expected_pages += category_expected_pages
                    elif page.reported_count != category_count:
                        raise CoopSchemaError(
                            f"Coop category total changed during traversal: {category.code}"
                        )
                    for row in page.items:
                        tracker.observe(
                            row,
                            partition=category.code,
                            page_number=page_number,
                        )
                    page_number += 1
                    if page_number >= category_expected_pages:
                        completed_categories += 1
                        break
                    if (
                        self.max_pages_per_category is not None
                        and page_number >= self.max_pages_per_category
                    ):
                        break
        except Exception as exc:
            if isinstance(exc, CoopOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            completion = (
                self._completion(
                    complete=False,
                    limited=(
                        self.max_categories is not None or self.max_pages_per_category is not None
                    ),
                    expected_categories=expected_categories,
                    completed_categories=completed_categories,
                    pages_fetched=pages_fetched,
                    expected_products=expected_products,
                    expected_pages=expected_pages,
                    tracker=tracker,
                    reason=type(exc).__name__,
                )
                if expected_categories is not None and expected_pages >= pages_fetched
                else None
            )
            raise self._fetch_error(
                exc,
                "Coop full online catalog traversal aborted",
                documents=documents,
                before=before,
                completion=completion,
            ) from exc

        assert expected_categories is not None
        full_authority = (
            self.allow_full_crawl
            and self.max_categories is None
            and self.max_pages_per_category is None
        )
        exact_reconciles = (
            completed_categories == expected_categories
            and pages_fetched == expected_pages
            and tracker.raw_rows == expected_products
            and tracker.raw_rows
            == len(tracker.seen_ids)
            + tracker.cross_partition_duplicates
            + tracker.exact_duplicates_removed
            and tracker.exact_duplicates_removed == tracker.within_partition_duplicates
            and tracker.conflicting_duplicates == 0
        )
        completion = self._completion(
            complete=full_authority and exact_reconciles,
            limited=not full_authority,
            expected_categories=expected_categories,
            completed_categories=completed_categories,
            pages_fetched=pages_fetched,
            expected_products=expected_products,
            expected_pages=expected_pages,
            tracker=tracker,
            reason=(
                None
                if full_authority and exact_reconciles
                else "source policy REVIEW: bounded discovery"
                if not full_authority
                else "category union did not reconcile"
            ),
        )
        batch = RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )
        if full_authority and not exact_reconciles:
            raise ConnectorFetchError(
                "Coop category union did not reconcile",
                partial_batch=batch,
            )
        return batch

    async def fetch_products_by_id(
        self,
        context_id: str,
        product_ids: Iterable[str],
    ) -> RawFetch:
        context_id = self.require_context(context_id)
        ids = tuple(dict.fromkeys(value.strip() for value in product_ids if value.strip()))
        if not ids:
            raise ValueError("Coop by-id request requires at least one product ID")
        if len(ids) > 50:
            raise ValueError("Coop by-id parity request is bounded to 50 products")
        document = await self._api_request(
            "personalization",
            "POST",
            "/search/entities/by-id",
            kind=COOP_PRODUCT_BY_ID_KIND,
            context_id=context_id,
            params=self._search_params(context_id),
            logical_query={"product_ids": ids},
            json_body=list(ids),
        )
        page = self._result_page(document, skip=0, take=len(ids))
        returned_ids = {str(row["id"]) for row in page.items}
        if page.reported_count != len(ids) or returned_ids != set(ids):
            raise CoopSchemaError("Coop by-id response did not reconcile requested identities")
        return document

    async def fetch_promotions(
        self,
        context_id: str,
        *,
        max_pages: int | None = 1,
        take: int = 50,
    ) -> RawBatch:
        context_id = self.require_context(context_id)
        if take <= 0 or take > 50:
            raise ValueError("Coop promotion page size must be between 1 and 50")
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive or None")
        if max_pages != 1 and not self.allow_full_crawl:
            raise CoopOnlineSourcePolicyError(
                "Coop promotion traversal requires COOP_ALLOW_FULL_CRAWL=true"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        first_count: int | None = None
        expected_pages = 0
        page_number = 0
        try:
            while True:
                skip = page_number * take
                document = await self._api_request(
                    "personalization",
                    "POST",
                    "/search/products/promotions",
                    kind=COOP_PROMOTIONS_KIND,
                    context_id=context_id,
                    params={
                        **self._search_params(context_id),
                        "only-primary": False,
                    },
                    logical_query={"skip": skip, "take": take},
                    json_body={
                        "resultsOptions": {
                            "skip": skip,
                            "take": take,
                            "sortBy": [],
                            "facets": [],
                        },
                        "customData": {"personalizeCampaigns": False},
                    },
                    page_number=page_number,
                )
                documents.append(document)
                page = self._result_page(document, skip=skip, take=take)
                if first_count is None:
                    first_count = page.reported_count
                    expected_pages = page.expected_pages
                elif page.reported_count != first_count:
                    raise CoopSchemaError("Coop promotion count changed during traversal")
                page_number += 1
                if page_number >= expected_pages:
                    break
                if max_pages is not None and page_number >= max_pages:
                    break
        except Exception as exc:
            if isinstance(exc, CoopOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            raise self._fetch_error(
                exc,
                "Coop promotion listing aborted",
                documents=documents,
                before=before,
            ) from exc
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    async def fetch_promotion(
        self,
        context_id: str,
        promotion_id: str,
        *,
        max_pages: int | None = 1,
        take: int = 50,
    ) -> RawBatch:
        context_id = self.require_context(context_id)
        normalized_id = " ".join(promotion_id.split())
        if not normalized_id:
            raise ValueError("Coop promotion ID must not be blank")
        if take <= 0 or take > 50:
            raise ValueError("Coop promotion page size must be between 1 and 50")
        if max_pages is not None and max_pages <= 0:
            raise ValueError("max_pages must be positive or None")
        if max_pages != 1 and not self.allow_full_crawl:
            raise CoopOnlineSourcePolicyError(
                "Coop promotion traversal requires COOP_ALLOW_FULL_CRAWL=true"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        first_count: int | None = None
        expected_pages = 0
        page_number = 0
        try:
            while True:
                skip = page_number * take
                document = await self._api_request(
                    "personalization",
                    "POST",
                    "/search/products/promotion",
                    kind=COOP_PROMOTION_KIND,
                    context_id=context_id,
                    params={
                        key: value
                        for key, value in self._search_params(context_id).items()
                        if key != "device"
                    },
                    logical_query={
                        "promotion_id": normalized_id,
                        "skip": skip,
                        "take": take,
                    },
                    json_body={
                        "promotionId": normalized_id,
                        "resultsOptions": {"skip": skip, "take": take},
                        "customData": {"consent": True},
                    },
                    page_number=page_number,
                )
                documents.append(document)
                page = self._result_page(document, skip=skip, take=take)
                if first_count is None:
                    first_count = page.reported_count
                    expected_pages = page.expected_pages
                elif page.reported_count != first_count:
                    raise CoopSchemaError("Coop promotion total changed during traversal")
                page_number += 1
                if page_number >= expected_pages:
                    break
                if max_pages is not None and page_number >= max_pages:
                    break
        except Exception as exc:
            if isinstance(exc, CoopOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            raise self._fetch_error(
                exc,
                "Coop promotion traversal aborted",
                documents=documents,
                before=before,
            ) from exc
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    async def fetch_point_of_service(self, point_of_service_id: str) -> RawFetch:
        """Fetch one pickup identity; its `storeId` is the online context ID."""

        normalized = point_of_service_id.strip()
        if not normalized:
            raise ValueError("Coop point-of-service ID must not be blank")
        document = await self._api_request(
            "ecommerce",
            "GET",
            f"/coop/pointofservice/{quote(normalized, safe='')}",
            kind=COOP_FULFILLMENT_MAPPING_KIND,
            context_id=None,
            params={"fields": "FULL"},
            logical_query={"point_of_service_id": normalized},
        )
        payload = document.json_payload()
        if (
            not isinstance(payload, dict)
            or str(payload.get("name") or "").strip() != normalized
            or not str(payload.get("displayName") or "").strip()
            or not str(payload.get("storeId") or "").strip()
        ):
            raise CoopOnlineHttpError(
                "Coop point-of-service detail lacks point/context identity",
                document,
            )
        return document

    async def fetch_point_of_services(self, query: str) -> RawBatch:
        """Bounded public pickup search; physical points may share one context."""

        normalized = " ".join(query.split())
        if not normalized:
            raise ValueError("Coop point-of-service query must not be blank")
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        try:
            documents.append(
                await self._api_request(
                    "ecommerce",
                    "GET",
                    "/coop/pointofservices",
                    kind=COOP_FULFILLMENT_MAPPING_KIND,
                    context_id=None,
                    params={"query": normalized, "fields": "FULL"},
                )
            )
            payload = documents[0].json_payload()
            if not isinstance(payload, dict) or not isinstance(payload.get("stores"), list):
                raise CoopSchemaError("Coop point-of-services response lacks stores")
            for row in payload["stores"]:
                if (
                    not isinstance(row, dict)
                    or not str(row.get("name") or "").strip()
                    or not str(row.get("displayName") or "").strip()
                    or not str(row.get("storeId") or "").strip()
                ):
                    raise CoopSchemaError(
                        "Coop point-of-services row lacks point/context identity"
                    )
        except Exception as exc:
            if isinstance(exc, CoopOnlineHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            raise self._fetch_error(
                exc,
                "Coop point-of-service discovery aborted",
                documents=documents,
                before=before,
            ) from exc
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )


def reconcile_saved_catalog_completion(
    raw: RawBatch,
    *,
    expected_context_id: str,
) -> CatalogCompletion:
    """Recompute Coop traversal proof from sanitized raw data with no network."""

    tree_documents = [
        document for document in raw.documents if document.kind == COOP_CATEGORY_TREE_KIND
    ]
    page_documents = [
        document for document in raw.documents if document.kind == COOP_PRODUCT_CATEGORY_PAGE_KIND
    ]
    if len(tree_documents) != 1 or not page_documents:
        raise CoopSchemaError("Coop replay requires one category tree and product pages")
    tree_document = tree_documents[0]
    if tree_document.store_external_id != expected_context_id:
        raise CoopSchemaError("Coop replay category tree context mismatch")
    categories = validated_category_tree(tree_document.json_payload()).terminal_nodes()
    categories_by_code = {category.code: category for category in categories}
    documents_by_category: dict[str, list[RawFetch]] = {}
    for document in page_documents:
        if document.store_external_id != expected_context_id:
            raise CoopSchemaError("Coop replay product page context mismatch")
        category_id = document.query.get("category_id")
        if category_id not in categories_by_code:
            raise CoopSchemaError("Coop replay page references an unknown terminal category")
        documents_by_category.setdefault(category_id, []).append(document)
    if set(documents_by_category) != set(categories_by_code):
        raise CoopSchemaError("Coop replay does not cover every terminal category")

    tracker = _DuplicateTracker()
    expected_products = 0
    expected_pages = 0
    pages_fetched = 0
    completed_categories = 0
    for category_id in categories_by_code:
        documents = sorted(
            documents_by_category[category_id],
            key=lambda document: int(document.query["skip"]),
        )
        first_count: int | None = None
        category_expected_pages = 0
        for page_number, document in enumerate(documents):
            try:
                skip = int(document.query["skip"])
                take = int(document.query["take"])
            except (KeyError, TypeError, ValueError) as exc:
                raise CoopSchemaError("Coop replay page lacks valid offset metadata") from exc
            if skip != page_number * take:
                raise CoopSchemaError("Coop replay category offsets are not contiguous")
            page = validated_results_page(
                document.json_payload(),
                requested_skip=skip,
                requested_take=take,
            )
            if first_count is None:
                first_count = page.reported_count
                category_expected_pages = page.expected_pages
                expected_products += first_count
                expected_pages += category_expected_pages
            elif page.reported_count != first_count:
                raise CoopSchemaError("Coop replay category total changed between pages")
            for row in page.items:
                tracker.observe(row, partition=category_id, page_number=page_number)
            pages_fetched += 1
        if len(documents) != category_expected_pages:
            raise CoopSchemaError("Coop replay category page count is incomplete")
        completed_categories += 1

    return CoopOnlineCatalogClient._completion(
        complete=True,
        limited=False,
        expected_categories=len(categories),
        completed_categories=completed_categories,
        pages_fetched=pages_fetched,
        expected_products=expected_products,
        expected_pages=expected_pages,
        tracker=tracker,
        reason=None,
    )
