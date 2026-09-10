from __future__ import annotations

import asyncio
import json
import math
import os
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import (
    AsyncRateLimiter,
    RetryPolicy,
    bounded_request,
    retry_after_seconds,
)
from grocery_data.app.connectors.lidl.models import (
    LidlSchemaError,
    sanitized_store_detail,
    sanitized_store_index,
    store_detail_urls,
    validated_search_page,
)
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    GeographicArea,
    RawBatch,
    RawFetch,
    SourceStore,
    TransportMetrics,
)


class LidlHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class LidlAccessChallenge(LidlHttpError):
    """Ordinary public access was challenged; no bypass or new session is attempted."""


class LidlRateLimitStop(LidlHttpError):
    """A first 429 stops the current bounded run."""


class LidlAccessChallengeFetchError(ConnectorFetchError):
    """Persistable fail-closed access-challenge result."""


class LidlRateLimitFetchError(ConnectorFetchError):
    """Persistable fail-closed rate-limit result."""


_ACCESS_MARKERS = (
    b"access denied",
    b"aws waf",
    b"aws-waf",
    b"captcha",
    b"cf-chl-",
    b"cf-turnstile",
    b"human verification",
    b"request blocked",
    b"request could not be satisfied",
    b"verify you are human",
)
_CITY_SLUGS = {"lund": "lund", "malmö": "malmoe", "malmo": "malmoe"}


def _looks_like_access_challenge(response: httpx.Response) -> bool:
    if response.status_code == 429:
        return False
    if response.status_code in {401, 403, 405}:
        return True
    beginning = response.content[:65536].lstrip().lower()
    return any(marker in beginning for marker in _ACCESS_MARKERS)


class LidlClient:
    """Low-rate transport for Lidl's unauthenticated public web responses."""

    connector_version = "lidl-v1"
    default_base_url = "https://www.lidl.se"
    public_offer_context_id = "public-default-region"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        requests_per_second: float | None = None,
        max_concurrency: int | None = None,
        retry_policy: RetryPolicy | None = None,
        page_size: int = 48,
        max_pages: int | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if page_size <= 0 or page_size > 108:
            raise ValueError("Lidl page_size must be between 1 and the verified maximum 108")
        if max_pages is not None and max_pages <= 0:
            raise ValueError("Lidl max_pages must be positive or None")
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.page_size = page_size
        self.max_pages = max_pages
        self.requests_per_second = (
            float(os.getenv("LIDL_REQUESTS_PER_SECOND", "1"))
            if requests_per_second is None
            else requests_per_second
        )
        self.max_concurrency = (
            int(os.getenv("LIDL_MAX_CONCURRENCY", "1"))
            if max_concurrency is None
            else max_concurrency
        )
        if self.requests_per_second <= 0:
            raise ValueError("LIDL_REQUESTS_PER_SECOND must be positive")
        if isinstance(self.max_concurrency, bool) or self.max_concurrency <= 0:
            raise ValueError("LIDL_MAX_CONCURRENCY must be positive")
        self._limiter = AsyncRateLimiter(self.requests_per_second)
        self._request_slots = asyncio.Semaphore(self.max_concurrency)
        self._retry = retry_policy or RetryPolicy(attempts=2)
        if not 1 <= self._retry.attempts <= 3:
            raise ValueError("Lidl retry attempts must be between 1 and 3")
        self._request_count = 0
        self._http_error_count = 0
        self._rate_limit_count = 0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
            headers={
                "Accept": "*/*",
                "User-Agent": os.getenv(
                    "GROCERY_DATA_USER_AGENT",
                    "grocery-data-poc/0.1 (+source-transparency; low-rate)",
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

    async def _request(
        self,
        path: str,
        *,
        kind: str,
        store_external_id: str | None = None,
        params: dict[str, Any] | None = None,
        page_number: int | None = None,
        sanitizer: Callable[[bytes, str], bytes] | None = None,
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
                stop_retry=lambda value: (
                    value.status_code == 429 or _looks_like_access_challenge(value)
                ),
                retry_rate_limits=False,
            )
        challenge = _looks_like_access_challenge(response)
        raw_kind = (
            "access_challenge"
            if challenge
            else "rate_limit"
            if response.status_code == 429
            else kind
        )
        source_url = str(response.request.url.copy_with(query=None))
        payload = response.content
        content_type = response.headers.get("content-type")
        if challenge or response.status_code == 429:
            payload = json.dumps(
                {
                    "schema": "lidl-transport-stop-v1",
                    "classification": "access_challenge" if challenge else "rate_limit",
                    "http_status": response.status_code,
                    "retry_after_seconds": (
                        retry_after_seconds(response, 3600)
                        if response.status_code == 429
                        else None
                    ),
                },
                sort_keys=True,
            ).encode()
            content_type = "application/json; profile=transport-stop-diagnostic"
        if sanitizer is not None and response.is_success and not challenge:
            try:
                payload = sanitizer(payload, source_url)
                content_type = f"application/json; profile=sanitized-{kind}"
            except (UnicodeError, LidlSchemaError) as exc:
                # Persist a closed diagnostic instead of page scripts that may
                # contain runtime configuration values irrelevant to replay.
                payload = json.dumps(
                    {
                        "schema": "lidl-sanitization-failure-v1",
                        "source_url": source_url,
                        "failure_type": type(exc).__name__,
                    },
                    sort_keys=True,
                ).encode()
                content_type = "application/json; profile=sanitization-failure"
        raw = RawFetch(
            chain=Chain.LIDL,
            store_external_id=store_external_id,
            kind=raw_kind,
            method="GET",
            url=source_url,
            query={key: str(value) for key, value in (params or {}).items()},
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=content_type,
            payload=payload,
            connector_version=self.connector_version,
            page_number=page_number,
        )
        if response.status_code == 429:
            raise LidlRateLimitStop(
                "Lidl RATE_LIMITED; the current run stopped without retry",
                raw,
            )
        if challenge:
            raise LidlAccessChallenge(
                f"Lidl ACCESS_CHALLENGE stopped the current run (HTTP {response.status_code})",
                raw,
            )
        if response.is_error:
            raise LidlHttpError(f"Lidl returned HTTP {response.status_code}", raw)
        if content_type == "application/json; profile=sanitization-failure":
            raise LidlHttpError("Lidl public store-page schema changed", raw)
        return raw

    @staticmethod
    def _wrap_failure(
        exc: Exception,
        *,
        documents: list[RawFetch],
        transport: TransportMetrics,
        completion: CatalogCompletion | None = None,
    ) -> ConnectorFetchError:
        if isinstance(exc, LidlHttpError) and exc.raw not in documents:
            documents.append(exc.raw)
        error_type: type[ConnectorFetchError] = (
            LidlAccessChallengeFetchError
            if isinstance(exc, LidlAccessChallenge)
            else LidlRateLimitFetchError
            if isinstance(exc, LidlRateLimitStop)
            else ConnectorFetchError
        )
        message = (
            str(exc)
            if isinstance(exc, (LidlAccessChallenge, LidlRateLimitStop))
            else "Lidl fetch aborted; partial sanitized raw evidence is attached"
        )
        return error_type(
            message,
            partial_batch=RawBatch(
                chain=Chain.LIDL,
                documents=tuple(documents),
                transport=transport,
                catalog_completion=completion,
            ),
        )

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        city_key = area.city.casefold().strip()
        if city_key == "sverige":
            before = self._metrics_snapshot()
            documents: list[RawFetch] = []
            try:
                probe = await self._request(
                    "/q/api/search",
                    kind="offer_context_probe",
                    params={
                        "fetchsize": 1,
                        "offset": 0,
                        "locale": "sv_SE",
                        "assortment": "SE",
                        "version": "2.1.0",
                    },
                    page_number=0,
                )
                if not (probe.content_type or "").casefold().startswith(
                    "application/mindshift.search+json"
                ):
                    raise LidlHttpError("Lidl context probe changed content type", probe)
                page = validated_search_page(probe.payload, requested_offset=0)
                if not page.items:
                    raise LidlSchemaError("Lidl default-region context probe returned no product")
                if "1" not in page.items[0].get("regionsPrices", {}):
                    raise LidlSchemaError("Lidl default-region context probe lacks region 1")
                documents.append(probe)
            except Exception as exc:
                raise self._wrap_failure(
                    exc,
                    documents=documents,
                    transport=self._metrics_since(before),
                ) from exc
            return RawBatch(
                chain=Chain.LIDL,
                documents=tuple(documents),
                transport=self._metrics_since(before),
            )
        city_slug = _CITY_SLUGS.get(city_key)
        if city_slug is None:
            raise ValueError("Lidl public store discovery is verified only for Lund and Malmö")
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        try:
            city_document = await self._request(
                f"/s/sv-SE/butiker/{city_slug}/",
                kind="store_index",
                sanitizer=lambda payload, url: sanitized_store_index(
                    payload,
                    source_url=url,
                    city_slug=city_slug,
                    requested_city=area.city,
                ),
            )
            documents.append(city_document)
            for detail_url in store_detail_urls(city_document.payload):
                documents.append(
                    await self._request(
                        detail_url,
                        kind="store_detail",
                        sanitizer=lambda payload, url: sanitized_store_detail(
                            payload,
                            source_url=url,
                        ),
                    )
                )
        except Exception as exc:
            raise self._wrap_failure(
                exc,
                documents=documents,
                transport=self._metrics_since(before),
            ) from exc
        return RawBatch(
            chain=Chain.LIDL,
            documents=tuple(documents),
            transport=self._metrics_since(before),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        if store.external_id != self.public_offer_context_id:
            raise ValueError(
                "Lidl public offer prices cannot be assigned to a physical store context"
            )
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        seen_ids: set[str] = set()
        total: int | None = None
        expected_pages: int | None = None
        raw_rows = 0
        offset = 0
        effective_fetch_size: int | None = None
        try:
            while True:
                document = await self._request(
                    "/q/api/search",
                    kind="offer_page",
                    store_external_id=store.external_id,
                    params={
                        "fetchsize": self.page_size,
                        "offset": offset,
                        "locale": "sv_SE",
                        "assortment": "SE",
                        "version": "2.1.0",
                    },
                    page_number=len(documents),
                )
                if not (document.content_type or "").casefold().startswith(
                    "application/mindshift.search+json"
                ):
                    raise LidlHttpError("Lidl offer endpoint changed content type", document)
                documents.append(document)
                page = validated_search_page(document.payload, requested_offset=offset)
                if total is None:
                    total = page.total
                    effective_fetch_size = page.fetch_size
                    expected_pages = max(1, math.ceil(page.total / page.fetch_size))
                elif page.total != total:
                    raise LidlSchemaError("Lidl numFound changed during traversal")
                elif page.fetch_size != effective_fetch_size:
                    raise LidlSchemaError("Lidl fetchsize changed during traversal")
                for row in page.items:
                    raw_rows += 1
                    product_id = str(row["productId"])
                    if product_id in seen_ids:
                        raise LidlSchemaError("Lidl offer traversal repeated a product ID")
                    seen_ids.add(product_id)
                if len(seen_ids) == page.total:
                    break
                if len(seen_ids) > page.total:
                    raise LidlSchemaError("Lidl offer traversal exceeded numFound")
                if self.max_pages is not None and len(documents) >= self.max_pages:
                    break
                next_offset = page.offset + len(page.items)
                if next_offset <= offset:
                    raise LidlSchemaError("Lidl pagination did not advance")
                offset = next_offset
        except Exception as exc:
            completion = (
                CatalogCompletion(
                    complete=False,
                    limited=self.max_pages is not None,
                    expected_categories=1,
                    completed_categories=0,
                    pages_fetched=len(documents),
                    products_observed=len(seen_ids),
                    expected_products=total,
                    raw_rows=raw_rows,
                    unique_products=len(seen_ids),
                    duplicate_products=raw_rows - len(seen_ids),
                    expected_pages=expected_pages,
                    reason=type(exc).__name__,
                )
                if total is not None and expected_pages is not None
                else None
            )
            raise self._wrap_failure(
                exc,
                documents=documents,
                transport=self._metrics_since(before),
                completion=completion,
            ) from exc
        assert total is not None and expected_pages is not None
        complete = len(seen_ids) == total
        return RawBatch(
            chain=Chain.LIDL,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            # This proves traversal only for the public published-offer set.
            # Connector coverage remains OFFERS_ONLY and can never satisfy a
            # basket/full-catalog eligibility gate.
            catalog_completion=CatalogCompletion(
                complete=complete,
                limited=not complete,
                expected_categories=1,
                completed_categories=1 if complete else 0,
                pages_fetched=len(documents),
                products_observed=len(seen_ids),
                expected_products=total,
                raw_rows=raw_rows,
                unique_products=len(seen_ids),
                duplicate_products=raw_rows - len(seen_ids),
                expected_pages=expected_pages,
                reason=None if complete else "explicit bounded canary",
            ),
        )

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        return await self.fetch_catalog(store)
