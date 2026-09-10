from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlsplit

from grocery_data.app.domain import Chain, GeographicArea, RawFetch


class CoopStoreLocatorError(RuntimeError):
    """The ordinary public locator did not satisfy its bounded contract."""


class CoopStoreLocatorAccessChallenge(CoopStoreLocatorError):
    """The public locator displayed an access challenge; callers must stop."""


_CHALLENGE = re.compile(
    r"captcha|human verification|access denied|aws[ -]?waf|verify you are human",
    re.IGNORECASE,
)
_DECLARED_TOTAL = re.compile(
    r"Resultat\s+för\s+(?P<city>[^,]+),\s*(?P<count>\d+)\s+butiker",
    re.IGNORECASE,
)


def _normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def sanitized_store_locator_payload(
    cards: list[dict[str, Any]],
    *,
    requested_city: str,
    declared_total: int,
) -> bytes:
    """Return a closed public-card envelope with no browser runtime state."""

    if declared_total < 0 or len(cards) != declared_total:
        raise CoopStoreLocatorError("Coop locator cards do not match declared total")
    safe: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    requested_key = _normalize(requested_city)
    for position, card in enumerate(cards):
        name = " ".join(str(card.get("name") or "").split())
        address_text = " ".join(str(card.get("address_text") or "").split())
        detail_href = str(card.get("detail_href") or "").strip()
        map_href = str(card.get("map_href") or "").strip()
        detail = urlsplit(detail_href)
        if detail.scheme or detail.netloc or not detail.path.startswith("/butiker-erbjudanden/"):
            raise CoopStoreLocatorError(f"Coop locator card {position} has unsafe detail URL")
        if detail.query or detail.fragment or detail.path in seen_paths:
            raise CoopStoreLocatorError("Coop locator returned duplicate or decorated detail paths")
        if not name or not address_text:
            raise CoopStoreLocatorError(f"Coop locator card {position} lacks name/address")
        suffix = f", {requested_city}"
        if not address_text.casefold().endswith(suffix.casefold()):
            raise CoopStoreLocatorError("Coop locator card escaped requested city scope")
        address = address_text[: -len(suffix)].strip()
        parsed_map = urlsplit(map_href)
        if parsed_map.scheme != "https" or parsed_map.hostname != "maps.google.com":
            raise CoopStoreLocatorError("Coop locator card has an unexpected map URL")
        query = parse_qs(parsed_map.query).get("q", [])
        if len(query) != 1:
            raise CoopStoreLocatorError("Coop locator card lacks one public map query")
        postal_match = re.search(
            rf"(?P<postal>\d{{5}})\s+{re.escape(requested_city)}$",
            query[0],
            re.IGNORECASE,
        )
        if postal_match is None:
            raise CoopStoreLocatorError("Coop locator map query lacks postcode/city")
        if requested_key != _normalize(query[0].split()[-1]):
            raise CoopStoreLocatorError("Coop locator map query escaped requested city")
        seen_paths.add(detail.path)
        safe.append(
            {
                "name": name,
                "address": address,
                "postal_code": postal_match.group("postal"),
                "city": requested_city,
                "store_page_path": detail.path,
            }
        )
    envelope = {
        "schema": "coop-public-store-locator-v1",
        "requested_city": requested_city,
        "declared_total": declared_total,
        "captured_total": len(safe),
        "stores": safe,
    }
    return json.dumps(envelope, ensure_ascii=False, separators=(",", ":")).encode()


def validated_store_locator(payload: bytes) -> tuple[dict[str, str], ...]:
    try:
        root = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise CoopStoreLocatorError("Coop sanitized locator is not JSON") from exc
    if not isinstance(root, dict) or root.get("schema") != "coop-public-store-locator-v1":
        raise CoopStoreLocatorError("Coop sanitized locator schema changed")
    requested_city = str(root.get("requested_city") or "").strip()
    declared = root.get("declared_total")
    captured = root.get("captured_total")
    stores = root.get("stores")
    if (
        not requested_city
        or isinstance(declared, bool)
        or not isinstance(declared, int)
        or captured != declared
        or not isinstance(stores, list)
        or len(stores) != declared
    ):
        raise CoopStoreLocatorError("Coop sanitized locator totals are inconsistent")
    result: list[dict[str, str]] = []
    for value in stores:
        if not isinstance(value, dict):
            raise CoopStoreLocatorError("Coop sanitized locator store must be an object")
        row = {
            key: str(value.get(key) or "").strip()
            for key in (
                "name",
                "address",
                "postal_code",
                "city",
                "store_page_path",
            )
        }
        if any(not item for item in row.values()) or _normalize(row["city"]) != _normalize(
            requested_city
        ):
            raise CoopStoreLocatorError("Coop sanitized locator store is incomplete")
        result.append(row)
    if len({row["store_page_path"] for row in result}) != len(result):
        raise CoopStoreLocatorError("Coop sanitized locator contains duplicate paths")
    return tuple(result)


class CoopBrowserStoreLocatorTransport:
    """Fresh normal Chromium transport for the public rendered store locator.

    Cookies, storage, request headers and frontend subscription values are never
    inspected.  Only visible store cards are copied into the closed envelope.
    """

    transport_version = "coop-browser-store-locator-v1"

    def __init__(self, *, navigation_timeout_ms: int = 30_000) -> None:
        self.navigation_timeout_ms = navigation_timeout_ms

    async def fetch(self, area: GeographicArea) -> RawFetch:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright

        requested_city = area.city.strip()
        if not requested_city:
            raise ValueError("Coop store locator requires a city")
        url = "https://www.coop.se/butiker-erbjudanden/"
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.navigation_timeout_ms,
                )
                status = response.status if response is not None else 0
                if status >= 400:
                    raise CoopStoreLocatorAccessChallenge(f"Coop locator returned HTTP {status}")
                # The public cookie banner may cover the normal locator. A
                # regular user can choose the necessary-only option; this does
                # not inspect, export or persist any cookie/storage value.
                necessary = page.get_by_role(
                    "button",
                    name="Endast nödvändiga cookies",
                    exact=True,
                )
                try:
                    await necessary.wait_for(state="visible", timeout=5_000)
                    await necessary.click(timeout=self.navigation_timeout_ms)
                except PlaywrightTimeoutError:
                    pass
                search = page.get_by_placeholder("Sök butik", exact=True)
                try:
                    await search.wait_for(state="visible", timeout=10_000)
                except PlaywrightTimeoutError:
                    opener = page.get_by_role(
                        "button",
                        name=re.compile(r"^(?:Hitta butik|Välj butik via karta)$", re.IGNORECASE),
                    )
                    await opener.click(timeout=self.navigation_timeout_ms)
                    await search.wait_for(
                        state="visible",
                        timeout=self.navigation_timeout_ms,
                    )
                await search.fill(requested_city, timeout=self.navigation_timeout_ms)
                option = page.get_by_role("option", name=requested_city, exact=True)
                await option.wait_for(state="visible", timeout=self.navigation_timeout_ms)
                if await necessary.count() and await necessary.is_visible():
                    await necessary.click(timeout=self.navigation_timeout_ms)
                await option.click(timeout=self.navigation_timeout_ms)
                dialog = page.get_by_role("dialog")
                await dialog.get_by_text(
                    re.compile(
                        rf"Resultat\s+för\s+{re.escape(requested_city)},\s*\d+\s+butiker",
                        re.IGNORECASE,
                    )
                ).wait_for(state="visible", timeout=self.navigation_timeout_ms)
                visible = await dialog.inner_text()
                if _CHALLENGE.search(visible):
                    raise CoopStoreLocatorAccessChallenge(
                        "Coop public locator displayed an access challenge"
                    )
                match = _DECLARED_TOTAL.search(visible)
                if match is None or _normalize(match.group("city")) != _normalize(requested_city):
                    raise CoopStoreLocatorError("Coop locator lacks an exact declared city total")
                declared_total = int(match.group("count"))
                cards: list[dict[str, Any]] = await dialog.locator("li").evaluate_all(
                    """elements => elements.map(element => {
                        const detail = element.querySelector('a[href^="/butiker-erbjudanden/"]');
                        const map = element.querySelector('a[href^="https://maps.google.com/maps?q="]');
                        const heading = element.querySelector('h4');
                        if (!detail || !map || !heading) return null;
                        return {
                            name: heading.innerText,
                            address_text: map.innerText,
                            detail_href: detail.getAttribute('href'),
                            map_href: map.getAttribute('href')
                        };
                    }).filter(Boolean)"""
                )
                payload = sanitized_store_locator_payload(
                    cards,
                    requested_city=requested_city,
                    declared_total=declared_total,
                )
                return RawFetch(
                    chain=Chain.COOP,
                    kind="store_locator",
                    method="BROWSER",
                    url=url,
                    fetched_at=datetime.now(tz=UTC),
                    http_status=status,
                    content_type="application/json; profile=rendered-store-cards",
                    payload=payload,
                    connector_version=self.transport_version,
                )
            finally:
                await browser.close()


__all__ = [
    "CoopBrowserStoreLocatorTransport",
    "CoopStoreLocatorAccessChallenge",
    "CoopStoreLocatorError",
    "sanitized_store_locator_payload",
    "validated_store_locator",
]
