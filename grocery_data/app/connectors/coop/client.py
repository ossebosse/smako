from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import ClassVar
from urllib.parse import urlparse

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.coop.browser import (
    CoopAccessChallenge,
    CoopBrowserOffersTransport,
)
from grocery_data.app.connectors.coop.models import sanitized_store_page_html
from grocery_data.app.connectors.coop.store_locator import (
    CoopBrowserStoreLocatorTransport,
    validated_store_locator,
)
from grocery_data.app.connectors.http import AsyncRateLimiter, RetryPolicy, bounded_request
from grocery_data.app.domain import Chain, GeographicArea, RawBatch, RawFetch, SourceStore
from grocery_data.app.domain.raw import TransportMetrics


class CoopHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class CoopClient:
    """Conservative public HTTP transport; no browser credentials are copied."""

    connector_version = "coop-v1"
    base_url = "https://www.coop.se"
    # Verified bootstrap/canary seeds only. This is deliberately not described
    # as dynamic store-locator discovery; a future public locator adapter may
    # replace it without changing the parser contract.
    _VERIFIED_STORE_PAGES: ClassVar[dict[str, tuple[str, ...]]] = {
        "lund": (
            "/butiker-erbjudanden/stora-coop/stora-coop-lund/",
            "/butiker-erbjudanden/coop/coop-varpinge-lund/",
            "/butiker-erbjudanden/coop/coop-trollebergsvagen/",
            "/butiker-erbjudanden/coop/coop-flojtvagen/",
            "/butiker-erbjudanden/coop/coop-klostergarden/",
            "/butiker-erbjudanden/coop/coop-martenstorget/",
            "/butiker-erbjudanden/coop/coop-vildgasen-lund/",
        ),
        "malmö": (
            "/butiker-erbjudanden/coop/coop-slottsstaden/",
            "/butiker-erbjudanden/stora-coop/stora-coop-stadion/",
            "/butiker-erbjudanden/coop-forum/coop-forum-jagersro/",
            "/butiker-erbjudanden/coop/coop-kopenhamnsvagen/",
            "/butiker-erbjudanden/coop/coop-varnhem/",
            "/butiker-erbjudanden/coop/coop-nobeltorget/",
            "/butiker-erbjudanden/coop/coop-malmo-central/",
            "/butiker-erbjudanden/coop/coop-kornettsgatan/",
            "/butiker-erbjudanden/coop/coop--norra-parkgatan/",
            "/butiker-erbjudanden/coop/coop-karolingatan/",
            "/butiker-erbjudanden/coop/coop-kirseberg/",
            "/butiker-erbjudanden/coop/coop-bulltofta/",
            "/butiker-erbjudanden/coop/coop-vastra-hamnen/",
        ),
        "malmo": (
            "/butiker-erbjudanden/coop/coop-slottsstaden/",
            "/butiker-erbjudanden/stora-coop/stora-coop-stadion/",
            "/butiker-erbjudanden/coop-forum/coop-forum-jagersro/",
            "/butiker-erbjudanden/coop/coop-kopenhamnsvagen/",
            "/butiker-erbjudanden/coop/coop-varnhem/",
            "/butiker-erbjudanden/coop/coop-nobeltorget/",
            "/butiker-erbjudanden/coop/coop-malmo-central/",
            "/butiker-erbjudanden/coop/coop-kornettsgatan/",
            "/butiker-erbjudanden/coop/coop--norra-parkgatan/",
            "/butiker-erbjudanden/coop/coop-karolingatan/",
            "/butiker-erbjudanden/coop/coop-kirseberg/",
            "/butiker-erbjudanden/coop/coop-bulltofta/",
            "/butiker-erbjudanden/coop/coop-vastra-hamnen/",
        ),
    }

    def __init__(
        self,
        *,
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        client: httpx.AsyncClient | None = None,
        offers_transport: CoopBrowserOffersTransport | None = None,
        store_locator_transport: CoopBrowserStoreLocatorTransport | None = None,
    ) -> None:
        rate = requests_per_second or float(os.getenv("COOP_REQUESTS_PER_SECOND", "0.5"))
        self._limiter = AsyncRateLimiter(rate)
        self._retry = retry_policy or RetryPolicy()
        self._request_count = self._http_error_count = self._rate_limit_count = 0
        self._owns_client = client is None
        self._offers_transport = offers_transport or CoopBrowserOffersTransport()
        self._store_locator_transport = (
            store_locator_transport or CoopBrowserStoreLocatorTransport()
        )
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml",
                "User-Agent": os.getenv(
                    "GROCERY_DATA_USER_AGENT", "grocery-data-poc/0.1 (+source-transparency)"
                ),
            },
        )

    def _observe(self, status: int | None) -> None:
        self._request_count += 1
        if status is None or status >= 400:
            self._http_error_count += 1
        if status == 429:
            self._rate_limit_count += 1

    def _before(self) -> tuple[int, int, int]:
        return self._request_count, self._http_error_count, self._rate_limit_count

    def _metrics(self, before: tuple[int, int, int]) -> TransportMetrics:
        return TransportMetrics(
            request_count=self._request_count - before[0],
            http_error_count=self._http_error_count - before[1],
            rate_limit_count=self._rate_limit_count - before[2],
        )

    async def _get(
        self,
        path: str,
        *,
        kind: str,
        store_external_id: str | None = None,
    ) -> RawFetch:
        parsed = urlparse(path)
        if parsed.scheme or parsed.netloc or not parsed.path.startswith("/"):
            raise ValueError("Coop transport accepts only same-origin public paths")
        response = await bounded_request(
            self._client,
            self._limiter,
            self._retry,
            "GET",
            parsed.path,
            on_attempt=self._observe,
        )
        payload = (
            sanitized_store_page_html(response.content)
            if kind == "store_page"
            else response.content
        )
        content_type = (
            "text/html; profile=sanitized-store-evidence"
            if kind == "store_page"
            else response.headers.get("content-type")
        )
        raw = RawFetch(
            chain=Chain.COOP,
            store_external_id=store_external_id,
            kind=kind,
            method="GET",
            url=str(response.request.url.copy_with(query=None)),
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=content_type,
            payload=payload,
            connector_version=self.connector_version,
        )
        if response.is_error:
            raise CoopHttpError(f"Coop returned HTTP {response.status_code}", raw)
        return raw

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        city = area.city.casefold().strip()
        paths = self._VERIFIED_STORE_PAGES.get(city)
        if not paths:
            raise ValueError(
                "Coop has no verified public store-detail discovery seed for this city yet"
            )
        before = self._before()
        documents: list[RawFetch] = []
        try:
            for path in paths:
                documents.append(await self._get(path, kind="store_page"))
        except Exception as exc:
            if isinstance(exc, CoopHttpError):
                documents.append(exc.raw)
            raise ConnectorFetchError(
                "Coop store discovery aborted; partial raw evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.COOP,
                    documents=tuple(documents),
                    transport=self._metrics(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics(before),
        )

    async def fetch_physical_stores(self, area: GeographicArea) -> RawBatch:
        """Run the fresh public locator, then close identity on its detail pages."""

        before = self._before()
        documents: list[RawFetch] = []
        try:
            locator = await self._store_locator_transport.fetch(area)
            self._observe(locator.http_status)
            documents.append(locator)
            for row in validated_store_locator(locator.payload):
                documents.append(
                    await self._get(row["store_page_path"], kind="store_page")
                )
        except Exception as exc:
            if isinstance(exc, CoopHttpError) and exc.raw not in documents:
                documents.append(exc.raw)
            raise ConnectorFetchError(
                "Coop dynamic physical-store discovery aborted; sanitized partial evidence "
                "is attached",
                partial_batch=RawBatch(
                    chain=Chain.COOP,
                    documents=tuple(documents),
                    transport=self._metrics(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.COOP,
            documents=tuple(documents),
            transport=self._metrics(before),
        )

    async def fetch_product_sitemap(self) -> RawBatch:
        before = self._before()
        try:
            raw = await self._get("/handla/sitemap_products.xml", kind="product_sitemap")
        except Exception as exc:
            documents = (exc.raw,) if isinstance(exc, CoopHttpError) else ()
            raise ConnectorFetchError(
                "Coop product sitemap fetch aborted; partial raw evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.COOP,
                    documents=documents,
                    transport=self._metrics(before),
                ),
            ) from exc
        return RawBatch(
            chain=Chain.COOP,
            documents=(raw,),
            transport=self._metrics(before),
        )

    async def fetch_offers(self, store: SourceStore) -> RawBatch:
        before = self._before()
        try:
            raw = await self._offers_transport.fetch(store)
        except Exception as exc:
            documents: tuple[RawFetch, ...] = ()
            message = "Coop public offer-page rendering aborted"
            if isinstance(exc, CoopAccessChallenge):
                message = "Coop ACCESS_CHALLENGE stopped the current run"
                documents = (
                    RawFetch(
                        chain=Chain.COOP,
                        store_external_id=store.external_id,
                        kind="access_challenge",
                        method="GET",
                        url=f"{self.base_url}{store.source_fields.get('store_page_path')}",
                        http_status=exc.status_code,
                        content_type="application/json; profile=sanitized-diagnostic",
                        payload=b'{"reason":"access_challenge"}',
                        connector_version=self.connector_version,
                    ),
                )
            raise ConnectorFetchError(
                message,
                partial_batch=RawBatch(
                    chain=Chain.COOP,
                    documents=documents,
                    transport=TransportMetrics(
                        request_count=1,
                        http_error_count=1,
                    ),
                ),
            ) from exc
        self._request_count += 1
        return RawBatch(
            chain=Chain.COOP,
            documents=(raw,),
            transport=self._metrics(before),
        )

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        """Collector adapter: OFFERS_ONLY chains use the catalog fetch hook."""

        return await self.fetch_offers(store)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
