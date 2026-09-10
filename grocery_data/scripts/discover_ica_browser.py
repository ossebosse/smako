"""Low-volume ICA browser discovery without credentials or WAF workarounds.

This diagnostic intentionally records response metadata and structural summaries
only. It never reads or persists request headers, cookies, browser storage or
session state.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from collections import Counter
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Response, async_playwright

ICA_HOST = "handlaprivatkund.ica.se"
STRUCTURED_PATH_MARKERS = ("/api/", "search", "catalog", "product")
CHALLENGE_MARKERS = ("captcha", "access denied", "aws waf", "challenge", "human verification")


def is_access_challenge(status: int, content_type: str, body: str) -> bool:
    """Classify a browser response without retaining its potentially sensitive body."""

    text = body.casefold()
    has_marker = any(marker in text for marker in CHALLENGE_MARKERS)
    return has_marker or (status in {403, 405} and "text/html" in content_type.casefold())


def _shape(value: Any, *, depth: int = 0) -> Any:
    if depth >= 3:
        if isinstance(value, list):
            return {"type": "array", "count": len(value)}
        if isinstance(value, dict):
            return {"type": "object", "keys": sorted(value)[:40]}
        return type(value).__name__
    if isinstance(value, dict):
        return {key: _shape(item, depth=depth + 1) for key, item in list(value.items())[:60]}
    if isinstance(value, list):
        return {
            "type": "array",
            "count": len(value),
            "item": _shape(value[0], depth=depth + 1) if value else None,
        }
    return type(value).__name__


def _route_type(path: str) -> str:
    lowered = path.casefold()
    if lowered.startswith("search") or "/search" in lowered:
        return "search_ssr"
    if "/products/" in lowered:
        return "product_detail_ssr"
    if "category" in lowered or "categories" in lowered:
        return "category_ssr"
    if "recipe" in lowered or "recept" in lowered:
        return "recipe_page"
    return "store_root"


def _product_metrics(payload: object) -> dict[str, int]:
    products = payload.get("products") if isinstance(payload, dict) else None
    if not isinstance(products, list):
        return {"product_ids": 0, "full_products": 0, "priced_products": 0, "gtin": 0, "package": 0}
    rows = [row for row in products if isinstance(row, dict)]
    return {
        "product_ids": len(
            {str(row.get("retailerProductId") or row.get("productId")) for row in rows}
        ),
        "full_products": sum(bool(row.get("name") and row.get("price")) for row in rows),
        "priced_products": sum(bool(row.get("price")) for row in rows),
        "gtin": sum(bool(row.get("gtin") or row.get("ean")) for row in rows),
        "package": sum(bool(row.get("packSizeDescription")) for row in rows),
    }


async def inspect(store: str, path: str, scrolls: int, *, headless: bool) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    structured: list[dict[str, Any]] = []
    error_responses: list[dict[str, Any]] = []
    product_metrics = {
        "product_ids": 0,
        "full_products": 0,
        "priced_products": 0,
        "gtin": 0,
        "package": 0,
    }
    challenge_seen = asyncio.Event()
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()

        async def observe(response: Response) -> None:
            parsed = urlsplit(response.url)
            if parsed.hostname != ICA_HOST:
                return
            content_type = (await response.header_value("content-type") or "").split(";", 1)[0]
            event = {
                "method": response.request.method,
                "host": parsed.hostname,
                "path": parsed.path,
                "status": response.status,
                "content_type": content_type,
            }
            events.append(event)
            if response.status >= 400:
                try:
                    text = (await response.text()).casefold()
                except PlaywrightError:
                    text = ""
                challenge = is_access_challenge(response.status, content_type, text)
                if challenge:
                    challenge_seen.set()
                error_responses.append(
                    {
                        **event,
                        "body_bytes": len(text.encode("utf-8")),
                        "challenge_marker": next(
                            (marker for marker in CHALLENGE_MARKERS if marker in text), None
                        ),
                        "access_challenge": challenge,
                    }
                )
            if "json" in content_type and any(
                marker in parsed.path.casefold() for marker in STRUCTURED_PATH_MARKERS
            ):
                try:
                    payload = await response.json()
                except (PlaywrightError, json.JSONDecodeError, TypeError, ValueError):
                    # Discovery must not turn body errors into collection success.
                    return
                request_payload: Any = None
                try:
                    request_payload = response.request.post_data_json
                except (json.JSONDecodeError, TypeError, ValueError):
                    request_payload = None
                structured.append(
                    {
                        **event,
                        "request_shape": _shape(request_payload),
                        "shape": _shape(payload),
                    }
                )
                metrics = _product_metrics(payload)
                for key, value in metrics.items():
                    product_metrics[key] += value

        page.on("response", observe)
        url = f"https://{ICA_HOST}/stores/{store}/{path.lstrip('/')}"
        response = await page.goto(url, wait_until="domcontentloaded", timeout=45_000)
        await page.wait_for_timeout(2_000)
        for _ in range(scrolls):
            if challenge_seen.is_set():
                break
            await page.mouse.wheel(0, 8_000)
            await page.wait_for_timeout(1_500)

        body = (await page.locator("body").inner_text()).casefold()
        document_challenge = response is not None and is_access_challenge(
            response.status, await response.header_value("content-type") or "", body
        )
        result = {
            "url": page.url,
            "document_status": response.status if response else None,
            "title": await page.title(),
            "challenge_detected": document_challenge or challenge_seen.is_set(),
            "route_yield": {
                "route_type": _route_type(path),
                "pages": 1,
                **product_metrics,
                "challenge_encountered": document_challenge or challenge_seen.is_set(),
                "ids_per_page": product_metrics["product_ids"],
                "priced_products_per_page": product_metrics["priced_products"],
            },
            "product_links_visible": await page.locator('a[href*="/products/"]').count(),
            "response_counts": [
                {"method": method, "path": response_path, "status": status, "count": count}
                for (method, response_path, status), count in Counter(
                    (e["method"], e["path"], e["status"]) for e in events
                ).most_common()
            ],
            "structured_responses": structured,
            "error_responses": error_responses[:20],
        }
        await context.close()
        await browser.close()
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", default="1088004")
    parser.add_argument("--path", default="search?q=pasta")
    parser.add_argument("--scrolls", type=int, default=2)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    result = asyncio.run(inspect(args.store, args.path, args.scrolls, headless=args.headless))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 2 if result["challenge_detected"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
