from __future__ import annotations

import json
import os
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
from grocery_data.app.connectors.willys.models import validated_catalog_page
from grocery_data.app.connectors.willys.parser import WillysParser
from grocery_data.app.domain import (
    CatalogCompletion,
    Chain,
    RawBatch,
    RawFetch,
    SourceStore,
    TransportMetrics,
)


class WillysHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


_ACCESS_CHALLENGE_MARKERS = (
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
_TRANSPORT_STOP_CONTENT_TYPE = "application/json; profile=transport-stop-diagnostic"
_TRANSPORT_STOP_SCHEMA = "willys-transport-stop-v1"


def _looks_like_access_challenge(response: httpx.Response) -> bool:
    if response.status_code in {401, 403, 405}:
        return True
    beginning = response.content[:65536].lower()
    return any(marker in beginning for marker in _ACCESS_CHALLENGE_MARKERS)


def _transport_stop_classification(response: httpx.Response) -> str | None:
    if response.status_code == 429:
        return "rate_limit"
    if _looks_like_access_challenge(response):
        return "access_challenge"
    if response.is_error:
        return "http_error"
    if "json" not in response.headers.get("content-type", "").casefold():
        return "non_json_response"
    return None


class WillysClient:
    connector_version = "willys-v1"
    default_api_url = "https://www.willys.prod.axcsfprod.aws.axfoodapp.cloud"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        page_size: int = 30,
        max_categories: int | None = None,
        max_pages_per_category: int | None = None,
        detail_enrichment_limit: int | None = 0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = (base_url or self.default_api_url).rstrip("/")
        self.requests_per_second = (
            float(os.getenv("WILLYS_REQUESTS_PER_SECOND", "1"))
            if requests_per_second is None
            else requests_per_second
        )
        # The Willys traversal is intentionally sequential. Expose this fixed,
        # non-secret guardrail through the connector's closed policy audit.
        self.max_concurrency = 1
        self._limiter = AsyncRateLimiter(self.requests_per_second)
        self._retry = retry_policy or RetryPolicy()
        if page_size <= 0:
            raise ValueError("page_size must be positive")
        if max_categories is not None and max_categories <= 0:
            raise ValueError("max_categories must be positive or None")
        if max_pages_per_category is not None and max_pages_per_category <= 0:
            raise ValueError("max_pages_per_category must be positive or None")
        self.page_size = page_size
        self.max_categories = max_categories
        self.max_pages_per_category = max_pages_per_category
        if detail_enrichment_limit is not None and detail_enrichment_limit < 0:
            raise ValueError("detail_enrichment_limit must be non-negative or None")
        self.detail_enrichment_limit = detail_enrichment_limit
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
                "Origin": "https://www.willys.se",
                "Referer": "https://www.willys.se/",
                "User-Agent": os.getenv(
                    "GROCERY_DATA_USER_AGENT", "grocery-data-poc/0.1 (+source-transparency)"
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

    @staticmethod
    def _validated_catalog_page(
        payload: object,
        *,
        requested_page: int,
    ) -> tuple[list[object], int]:
        """Fail closed when Willys' traversal contract is incomplete."""

        return validated_catalog_page(payload, requested_page=requested_page)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        kind: str,
        store_external_id: str | None = None,
        params: dict[str, Any] | None = None,
        capture: bool = True,
        page_number: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> RawFetch:
        response = await bounded_request(
            self._client,
            self._limiter,
            self._retry,
            method,
            path,
            on_attempt=self._observe_attempt,
            stop_retry=_looks_like_access_challenge,
            # A rate-limit response is a crawler stop signal, not a transient
            # response to retry inside the same collection. The sanitized raw
            # diagnostic below preserves Retry-After without storing headers,
            # cookies or response content.
            retry_rate_limits=False,
            params=params,
            headers=headers,
        )
        stop_classification = _transport_stop_classification(response)
        raw_kind = stop_classification or kind
        if stop_classification is not None:
            diagnostic: dict[str, object] = {
                "schema": _TRANSPORT_STOP_SCHEMA,
                "classification": stop_classification,
                "http_status": response.status_code,
            }
            if response.status_code == 429:
                parsed_retry_after = retry_after_seconds(response, 3600)
                if parsed_retry_after is not None:
                    diagnostic["retry_after_seconds"] = parsed_retry_after
            payload = json.dumps(
                diagnostic,
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            content_type = _TRANSPORT_STOP_CONTENT_TYPE
        else:
            payload = response.content if capture else b"{}"
            content_type = response.headers.get("content-type")
        raw = RawFetch(
            chain=Chain.WILLYS,
            store_external_id=store_external_id,
            kind=raw_kind,
            method=method,
            url=str(response.request.url.copy_with(query=None)),
            query={key: str(value) for key, value in (params or {}).items()},
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=content_type,
            payload=payload,
            connector_version=self.connector_version,
            page_number=page_number,
        )
        if stop_classification is not None:
            raise WillysHttpError(
                f"Willys transport stopped ({stop_classification}, HTTP {response.status_code})",
                raw,
            )
        return raw

    async def fetch_stores(self) -> RawBatch:
        before = self._metrics_snapshot()
        try:
            raw = await self._request("GET", "/axfood/rest/v1/store", kind="stores")
        except Exception as exc:
            documents = (exc.raw,) if isinstance(exc, WillysHttpError) else ()
            raise ConnectorFetchError(
                "Willys store discovery aborted; partial raw evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.WILLYS,
                    documents=documents,
                    transport=self._metrics_since(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.WILLYS,
            documents=(raw,),
            transport=self._metrics_since(before),
        )

    async def _activate_store(
        self,
        store_external_id: str,
        documents: list[RawFetch],
    ) -> RawFetch:
        # The official frontend obtains this public, session-scoped CSRF token.
        # It is used in-memory only and is never captured in metadata or fixtures.
        token_response = await bounded_request(
            self._client,
            self._limiter,
            self._retry,
            "GET",
            "/axfood/rest/v1/csrf-token",
            on_attempt=self._observe_attempt,
            stop_retry=_looks_like_access_challenge,
            retry_rate_limits=False,
        )
        stop_classification = _transport_stop_classification(token_response)
        if stop_classification is not None:
            diagnostic: dict[str, object] = {
                "schema": _TRANSPORT_STOP_SCHEMA,
                "classification": stop_classification,
                "http_status": token_response.status_code,
            }
            if token_response.status_code == 429:
                parsed_retry_after = retry_after_seconds(token_response, 3600)
                if parsed_retry_after is not None:
                    diagnostic["retry_after_seconds"] = parsed_retry_after
            raw = RawFetch(
                chain=Chain.WILLYS,
                store_external_id=store_external_id,
                kind=stop_classification,
                method="GET",
                url=str(token_response.request.url.copy_with(query=None)),
                query={},
                fetched_at=datetime.now(tz=UTC),
                http_status=token_response.status_code,
                content_type=_TRANSPORT_STOP_CONTENT_TYPE,
                payload=json.dumps(
                    diagnostic,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode(),
                connector_version=self.connector_version,
            )
            raise WillysHttpError(
                "Willys transport stopped "
                f"({stop_classification}, HTTP {token_response.status_code})",
                raw,
            )
        token_response.raise_for_status()
        token = token_response.json()
        if not isinstance(token, str) or not token:
            raise RuntimeError("Willys did not return a usable CSRF token")
        activation = await self._request(
            "POST",
            "/axfood/rest/v1/store/activate",
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
        documents.append(activation)
        active = await self._request(
            "GET",
            "/axfood/rest/v1/store/active",
            kind="store_context",
            store_external_id=store_external_id,
        )
        documents.append(active)
        try:
            active_payload = active.json_payload()
        except (TypeError, ValueError) as exc:
            raise RuntimeError("Willys active-store response is not JSON") from exc
        from grocery_data.app.connectors.willys.models import validated_store_context

        if not validated_store_context(active_payload, store_external_id):
            raise RuntimeError("Willys did not confirm the requested store context")
        return active

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        before = self._metrics_snapshot()
        documents: list[RawFetch] = []
        expected_categories: int | None = None
        completed_categories = 0
        pages_fetched = 0
        product_ids: list[str] = []
        seen_product_ids: set[str] = set()
        explicitly_limited = (
            self.max_categories is not None or self.max_pages_per_category is not None
        )
        try:
            await self._activate_store(store.external_id, documents)
            tree = await self._request(
                "GET",
                "/axfood/rest/v1/leftMenu/categorytree",
                kind="category_tree",
                store_external_id=store.external_id,
            )
            documents.append(tree)
            all_leaf_paths = WillysParser.category_leaf_paths(tree.payload)
            expected_categories = len(all_leaf_paths)
            if expected_categories == 0:
                raise RuntimeError("Willys category tree contained no traversable leaf categories")
            leaf_paths = all_leaf_paths
            if self.max_categories is not None:
                leaf_paths = leaf_paths[: self.max_categories]
            for category_path in leaf_paths:
                page = 0
                category_complete = False
                while True:
                    catalog_page = await self._request(
                        "GET",
                        f"/axfood/rest/v1/c/{category_path}",
                        kind="catalog_page",
                        store_external_id=store.external_id,
                        params={"page": page, "size": self.page_size},
                        page_number=page,
                    )
                    documents.append(catalog_page)
                    pages_fetched += 1
                    payload = json.loads(catalog_page.payload)
                    results, number_of_pages = self._validated_catalog_page(
                        payload,
                        requested_page=page,
                    )
                    for row in results:
                        if not isinstance(row, dict) or not row.get("code"):
                            continue
                        product_id = str(row["code"])
                        if product_id not in seen_product_ids:
                            product_ids.append(product_id)
                            seen_product_ids.add(product_id)
                    page += 1
                    if page >= number_of_pages:
                        category_complete = True
                        break
                    if (
                        self.max_pages_per_category is not None
                        and page >= self.max_pages_per_category
                    ):
                        break
                if category_complete:
                    completed_categories += 1
            enrichment_ids = (
                product_ids
                if self.detail_enrichment_limit is None
                else product_ids[: self.detail_enrichment_limit]
            )
            for product_id in enrichment_ids:
                documents.append(await self.fetch_product_detail(store, product_id))
        except Exception as exc:
            if isinstance(exc, WillysHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            completion = CatalogCompletion(
                complete=False,
                limited=explicitly_limited,
                expected_categories=expected_categories,
                completed_categories=completed_categories,
                pages_fetched=pages_fetched,
                products_observed=len(product_ids),
                reason=type(exc).__name__,
            )
            raise ConnectorFetchError(
                "Willys catalog fetch aborted; partial raw evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.WILLYS,
                    documents=tuple(documents),
                    transport=self._metrics_since(before),
                    catalog_completion=completion,
                ),
            ) from exc

        complete = (
            not explicitly_limited
            and expected_categories is not None
            and completed_categories == expected_categories
        )
        completion = CatalogCompletion(
            complete=complete,
            limited=explicitly_limited,
            expected_categories=expected_categories,
            completed_categories=completed_categories,
            pages_fetched=pages_fetched,
            products_observed=len(product_ids),
            reason=None if complete else "explicit traversal limit",
        )
        return RawBatch(
            chain=Chain.WILLYS,
            documents=tuple(documents),
            transport=self._metrics_since(before),
            catalog_completion=completion,
        )

    async def fetch_product_detail(
        self,
        store: SourceStore,
        external_product_id: str,
    ) -> RawFetch:
        return await self._request(
            "GET",
            f"/axfood/rest/v1/p/{external_product_id}",
            kind="product_detail",
            store_external_id=store.external_id,
        )
