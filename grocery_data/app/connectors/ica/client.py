from __future__ import annotations

import json
import os
import re
import unicodedata
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from grocery_data.app.connectors.base import ConnectorFetchError
from grocery_data.app.connectors.http import AsyncRateLimiter, RetryPolicy, bounded_request
from grocery_data.app.connectors.ica.models import IcaSchemaError, sanitized_initial_data_payload
from grocery_data.app.domain import Chain, GeographicArea, RawBatch, RawFetch, SourceStore
from grocery_data.app.domain.raw import TransportMetrics


class IcaHttpError(RuntimeError):
    def __init__(self, message: str, raw: RawFetch) -> None:
        super().__init__(message)
        self.raw = raw


class IcaAccessChallenge(IcaHttpError):
    """Ordinary public access was challenged; collection stops without bypass."""


_ACCESS_MARKERS = (
    b"access denied",
    b"aws waf",
    b"aws-waf",
    b"captcha",
    b"cf-chl-",
    b"human verification",
    b"request blocked",
    b"verify you are human",
)


def _looks_like_access_challenge(response: httpx.Response) -> bool:
    if response.status_code in {401, 403, 405}:
        return True
    beginning = response.content[:65536].lstrip().lower()
    return any(marker in beginning for marker in _ACCESS_MARKERS)


class IcaClient:
    connector_version = "ica-v2"
    base_url = "https://www.ica.se"

    def __init__(
        self,
        *,
        requests_per_second: float | None = None,
        retry_policy: RetryPolicy | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        rate = requests_per_second or float(os.getenv("ICA_REQUESTS_PER_SECOND", "0.5"))
        self._limiter = AsyncRateLimiter(rate)
        self._retry = retry_policy or RetryPolicy()
        self._request_count = self._http_error_count = self._rate_limit_count = 0
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=False,
            headers={
                "Accept": "text/html,application/xhtml+xml",
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

    def _metrics(self, before: tuple[int, int, int]) -> TransportMetrics:
        return TransportMetrics(
            request_count=self._request_count - before[0],
            http_error_count=self._http_error_count - before[1],
            rate_limit_count=self._rate_limit_count - before[2],
        )

    async def _get(self, path: str, *, kind: str, store_id: str | None = None) -> RawFetch:
        response = await bounded_request(
            self._client,
            self._limiter,
            self._retry,
            "GET",
            path,
            on_attempt=self._observe,
            stop_retry=_looks_like_access_challenge,
        )
        challenge = _looks_like_access_challenge(response)
        sanitization_failed = False
        if challenge or response.is_error:
            payload = json.dumps(
                {
                    "schema": "ica-transport-stop-v1",
                    "classification": (
                        "access_challenge"
                        if challenge
                        else "rate_limit"
                        if response.status_code == 429
                        else "http_error"
                    ),
                    "http_status": response.status_code,
                },
                separators=(",", ":"),
                sort_keys=True,
            ).encode()
            content_type = "application/json; profile=transport-stop-diagnostic"
        else:
            try:
                payload = sanitized_initial_data_payload(response.content, kind=kind)
                content_type = f"application/json; profile=sanitized-{kind}"
            except (UnicodeError, IcaSchemaError) as exc:
                sanitization_failed = True
                payload = json.dumps(
                    {
                        "schema": "ica-sanitization-failure-v1",
                        "kind": kind,
                        "failure_type": type(exc).__name__,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode()
                content_type = "application/json; profile=sanitization-failure"
        raw = RawFetch(
            chain=Chain.ICA,
            store_external_id=store_id,
            kind=kind,
            method="GET",
            url=str(response.request.url.copy_with(query=None)),
            fetched_at=datetime.now(tz=UTC),
            http_status=response.status_code,
            content_type=content_type,
            payload=payload,
            connector_version=self.connector_version,
        )
        if challenge:
            raise IcaAccessChallenge(
                f"ICA access challenge stopped collection (HTTP {response.status_code})",
                raw,
            )
        if response.is_error:
            raise IcaHttpError(f"ICA returned HTTP {response.status_code}", raw)
        if sanitization_failed:
            raise IcaHttpError("ICA public SSR schema could not be sanitized", raw)
        return raw

    async def fetch_stores(self, area: GeographicArea) -> RawBatch:
        before = (self._request_count, self._http_error_count, self._rate_limit_count)
        slug = area.city.strip().casefold()
        if slug not in {"lund", "malmö", "malmo"}:
            raise ValueError("ICA Phase 2 discovery is limited to Lund and Malmö")
        slug = "malmo" if slug in {"malmö", "malmo"} else "lund"
        try:
            raw = await self._get(f"/butiker/oppettider/handla-online/{slug}/", kind="stores_page")
        except Exception as exc:
            docs = (exc.raw,) if isinstance(exc, IcaHttpError) else ()
            raise ConnectorFetchError(
                "ICA store discovery failed; partial raw evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.ICA, documents=docs, transport=self._metrics(before)
                ),
            ) from exc
        return RawBatch(chain=Chain.ICA, documents=(raw,), transport=self._metrics(before))

    async def fetch_physical_stores(self, area: GeographicArea) -> RawBatch:
        """Fetch the complete public municipality locator page, not its online filter.

        The normal ICA connector intentionally uses the online-filtered page for its
        operational offers surface.  Physical-store coverage is a separate bounded
        concern and therefore has an explicit method.  The response still passes
        through the same closed SSR allowlist before a :class:`RawFetch` exists.
        """

        before = (self._request_count, self._http_error_count, self._rate_limit_count)
        slug = "".join(c for c in unicodedata.normalize("NFKD", area.city.casefold())
                       if not unicodedata.combining(c)).strip().replace(" ", "-")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError("city has no supported ICA locator slug")
        documents = []
        pending = [f"https://www.ica.se/butiker/{slug}/"]
        visited = set()
        try:
            while pending:
                url = pending.pop(0)
                if url in visited or len(visited) >= 50:
                    raise ValueError("ICA pagination cycle or page budget exceeded")
                visited.add(url)
                raw = await self._get(url, kind="stores_page")
                documents.append(raw)
                pending.extend(json.loads(raw.payload).get("public_links", {}).get("next_pages", []))
        except Exception as exc:
            docs = (*documents, exc.raw) if isinstance(exc, IcaHttpError) else tuple(documents)
            raise ConnectorFetchError(
                "ICA physical-store discovery failed; partial sanitized evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.ICA,
                    documents=docs,
                    transport=self._metrics(before),
                ),
            ) from exc
        return RawBatch(chain=Chain.ICA, documents=tuple(documents), transport=self._metrics(before))

    async def fetch_public_page(self, url: str, *, store_id: str) -> RawFetch:
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.netloc != "www.ica.se"
                or not parsed.path.startswith(("/butiker/", "/erbjudanden/"))):
            raise ValueError("unverified official store document URL")
        return await self._get(url, kind="public_page", store_id=store_id)

    async def fetch_catalog(self, store: SourceStore) -> RawBatch:
        before = (self._request_count, self._http_error_count, self._rate_limit_count)
        offers_url = str(store.source_fields.get("offers_url") or "")
        parsed = urlparse(offers_url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "www.ica.se"
            or not parsed.path.startswith("/erbjudanden/")
        ):
            raise ValueError("ICA store has no verified public offers URL")
        try:
            raw = await self._get(parsed.path, kind="offers_page", store_id=store.external_id)
        except Exception as exc:
            docs = (exc.raw,) if isinstance(exc, IcaHttpError) else ()
            raise ConnectorFetchError(
                "ICA offers fetch failed; partial raw evidence is attached",
                partial_batch=RawBatch(
                    chain=Chain.ICA, documents=docs, transport=self._metrics(before)
                ),
            ) from exc
        return RawBatch(chain=Chain.ICA, documents=(raw,), transport=self._metrics(before))

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
