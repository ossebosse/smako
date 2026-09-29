from __future__ import annotations

import asyncio
import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from grocery_data.app.domain import Chain, RawFetch, SourceStore


class CoopAccessChallenge(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 0) -> None:
        super().__init__(message)
        self.status_code = status_code


_CHALLENGE = re.compile(
    r"captcha|human verification|access denied|aws[ -]?waf|verify you are human",
    re.IGNORECASE,
)
# Physical offer cards can themselves say "Se 2 varor". Only the page-level
# "N erbjudanden" heading is a completeness boundary for this transport.
_TOTAL = re.compile(r"\b(?P<count>\d[\d\s]*)\s+erbjudanden\b", re.IGNORECASE)


class CoopBrowserOffersTransport:
    """Ordinary Chromium transport for the public physical-store offer page.

    The session is fresh and discarded for every fetch. Cookies, storage,
    headers and network credentials are never inspected or persisted.
    """

    transport_version = "coop-browser-offers-v3"

    def __init__(self, *, navigation_timeout_ms: int = 30_000) -> None:
        self.navigation_timeout_ms = navigation_timeout_ms

    async def fetch(self, store: SourceStore) -> RawFetch:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        path = str(store.source_fields.get("store_page_path") or "")
        if not path.startswith("/butiker-erbjudanden/"):
            raise ValueError("Coop store has no verified public detail path")
        url = f"https://www.coop.se{path}"
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                # Observe the SAME public response used by this page. Never copy
                # credentials, request headers, runtime state or online prices.
                from .structured_offers import capture_public_response, confirmed_empty_response
                captures: list[dict] = []
                tasks: list = []
                page.on("response", lambda response: tasks.append(asyncio.create_task(
                    capture_public_response(response, store, captures))))
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.navigation_timeout_ms,
                )
                status = response.status if response is not None else 0
                if status >= 400:
                    raise CoopAccessChallenge(
                        f"Coop offer page returned HTTP {status}", status_code=status
                    )
                visible = await page.locator("body").inner_text()
                if _CHALLENGE.search(visible):
                    raise CoopAccessChallenge("Coop public page displayed an access challenge")
                selector = (
                    "article a[href^='/handla/varor/'][aria-label], article button[aria-label]"
                )
                try:
                    await page.wait_for_function(
                        """selector => [...document.querySelectorAll(selector)].some(element =>
                            /pris|kronor|öre/i.test(element.getAttribute('aria-label') || '')
                        )""",
                        arg=selector,
                        timeout=self.navigation_timeout_ms,
                    )
                except PlaywrightTimeoutError as exc:
                    visible = await page.locator("body").inner_text()
                    if _CHALLENGE.search(visible):
                        raise CoopAccessChallenge(
                            "Coop public page displayed an access challenge"
                        ) from exc
                    await asyncio.gather(*tasks)
                    if not confirmed_empty_response(captures, store):
                        raise RuntimeError("Coop public offer page rendered no product cards") from exc
                visible = await page.locator("body").inner_text()
                if _CHALLENGE.search(visible):
                    raise CoopAccessChallenge("Coop public page displayed an access challenge")
                self._validate_store_context(
                    page.url,
                    await page.locator("h1").first.text_content() or "",
                    store,
                )
                declared_total = self._declared_offer_total(visible)
                cards = await self._stable_cards(
                    page,
                    selector,
                    declared_total=declared_total,
                )
                await asyncio.gather(*tasks)
                payload = self._sanitized_payload(
                    cards,
                    declared_total=declared_total,
                    store=store,
                    structured_responses=captures,
                )
                return RawFetch(
                    chain=Chain.COOP,
                    store_external_id=store.external_id,
                    kind="rendered_offers_page",
                    method="GET",
                    url=url,
                    fetched_at=datetime.now(tz=UTC),
                    http_status=status,
                    content_type="application/json; profile=rendered-offer-cards",
                    payload=payload,
                    connector_version=self.transport_version,
                )
            finally:
                await browser.close()

    @staticmethod
    def _sanitized_payload(
        cards: list[dict[str, Any]],
        *,
        declared_total: int | None,
        store: SourceStore,
        structured_responses: list[dict] | None = None,
    ) -> bytes:
        safe_cards: list[dict[str, str | None]] = []
        for card in cards:
            href = str(card.get("href") or "")
            aria_label = " ".join(str(card.get("ariaLabel") or "").split())
            if not aria_label:
                continue
            safe_href = href if href.startswith("/handla/varor/") else None
            safe_cards.append({"href": safe_href, "aria_label": aria_label,
                               "visible_text": str(card.get("visibleText") or "")})
        from .structured_offers import confirmed_empty_response
        if not safe_cards and not confirmed_empty_response(structured_responses, store):
            raise RuntimeError("Coop public offer page yielded no safe offer cards")
        if declared_total is not None and len(safe_cards) != declared_total:
            raise RuntimeError(
                "Coop public offer page was incomplete: "
                f"declared {declared_total}, captured {len(safe_cards)}"
            )
        path = str(store.source_fields.get("store_page_path") or "")
        if not path.startswith("/butiker-erbjudanden/"):
            raise ValueError("Coop store has no verified public detail path")
        envelope = {
            "store_external_id": store.external_id,
            "store_page_path": path,
            "declared_total": declared_total,
            "captured_total": len(safe_cards),
            "capture_evidence": "declared_total" if declared_total is not None else "dom_stable",
            "cards": safe_cards,
        }
        if structured_responses:
            if len(structured_responses) != 1:
                raise RuntimeError("Coop public page exposed ambiguous structured responses")
            envelope["structured_offers"] = structured_responses[0]
        return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()

    @staticmethod
    def _validate_store_context(final_url: str, heading: str, store: SourceStore) -> None:
        expected_path = str(store.source_fields.get("store_page_path") or "")
        parsed = urlsplit(final_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "www.coop.se"
            or parsed.path.rstrip("/") != expected_path.rstrip("/")
        ):
            raise RuntimeError("Coop public offer page changed store context")
        normalized_heading = " ".join(heading.split()).casefold()
        normalized_name = " ".join(store.name.split()).casefold()
        if normalized_heading != normalized_name:
            raise RuntimeError("Coop public offer page heading did not match the requested store")

    @staticmethod
    def _declared_offer_total(visible_text: str) -> int | None:
        totals = {
            int(match.group("count").replace(" ", "")) for match in _TOTAL.finditer(visible_text)
        }
        if not totals:
            return None
        if len(totals) != 1:
            raise RuntimeError("Coop public offer page exposed conflicting offer totals")
        return totals.pop()

    async def _stable_cards(
        self,
        page: Any,
        selector: str,
        *,
        declared_total: int | None,
    ) -> list[dict[str, Any]]:
        previous: list[dict[str, Any]] | None = None
        stable_observations = 0
        for _ in range(12):
            cards: list[dict[str, Any]] = await page.locator(selector).evaluate_all(
                """elements => elements.filter(element =>
                    /pris|kronor|öre/i.test(element.getAttribute('aria-label') || '')
                ).map(element => ({
                    href: element.getAttribute('href'),
                    ariaLabel: element.getAttribute('aria-label'),
                    visibleText: element.closest('article').innerText
                }))"""
            )
            if declared_total is not None and len(cards) > declared_total:
                raise RuntimeError("Coop public offer page exceeded its declared offer total")
            if cards == previous:
                stable_observations += 1
            else:
                stable_observations = 0
            if (
                declared_total is not None
                and len(cards) == declared_total
                or declared_total is None
                and stable_observations >= 3
            ):
                return cards
            previous = cards
            await page.wait_for_timeout(500)
            visible = await page.locator("body").inner_text()
            if _CHALLENGE.search(visible):
                raise CoopAccessChallenge("Coop public page displayed an access challenge")
        captured = len(previous or [])
        boundary = f"declared {declared_total}" if declared_total is not None else "DOM stability"
        raise RuntimeError(
            f"Coop public offer page did not reach {boundary}; captured {captured} cards"
        )
