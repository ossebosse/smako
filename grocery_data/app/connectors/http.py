from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from random import random
from time import monotonic

import httpx


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    attempts: int = 3
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 5.0


class AsyncRateLimiter:
    """Small per-connector limiter; it never disguises request identity."""

    def __init__(self, requests_per_second: float) -> None:
        if requests_per_second <= 0:
            raise ValueError("requests_per_second must be positive")
        self._interval = 1.0 / requests_per_second
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def wait(self) -> None:
        async with self._lock:
            delay = self._interval - (monotonic() - self._last_request)
            if delay > 0:
                await asyncio.sleep(delay)
            self._last_request = monotonic()


def retry_after_seconds(response: httpx.Response, maximum: float) -> float | None:
    raw = response.headers.get("Retry-After")
    if not raw:
        return None
    try:
        return min(float(raw), maximum)
    except ValueError:
        try:
            seconds = (
                parsedate_to_datetime(raw) - parsedate_to_datetime(response.headers["Date"])
            ).total_seconds()
            return max(0.0, min(seconds, maximum))
        except (KeyError, TypeError, ValueError):
            return None


async def bounded_request(
    client: httpx.AsyncClient,
    limiter: AsyncRateLimiter,
    retry: RetryPolicy,
    method: str,
    url: str,
    *,
    on_attempt: Callable[[int | None], None] | None = None,
    stop_retry: Callable[[httpx.Response], bool] | None = None,
    retry_rate_limits: bool = True,
    **kwargs: object,
) -> httpx.Response:
    response: httpx.Response | None = None
    for attempt in range(retry.attempts):
        await limiter.wait()
        try:
            response = await client.request(method, url, **kwargs)
        except (httpx.ConnectError, httpx.ReadTimeout):
            if on_attempt is not None:
                on_attempt(None)
            if attempt + 1 >= retry.attempts:
                raise
        else:
            if on_attempt is not None:
                on_attempt(response.status_code)
            if stop_retry is not None and stop_retry(response):
                return response
            if response.status_code == 429 and not retry_rate_limits:
                return response
            if response.status_code != 429 and response.status_code < 500:
                return response
            if attempt + 1 >= retry.attempts:
                return response
        retry_after = retry_after_seconds(response, retry.max_delay_seconds) if response else None
        exponential = min(retry.max_delay_seconds, retry.base_delay_seconds * (2**attempt))
        await asyncio.sleep(
            retry_after if retry_after is not None else exponential + random() * 0.1
        )
    if response is None:  # pragma: no cover - loop always returns or raises
        raise RuntimeError("bounded request exhausted without a response")
    return response
