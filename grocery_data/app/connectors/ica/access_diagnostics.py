"""Bounded passive diagnostics for the existing anonymous browser transport.

No request replay/interception, headers, raw errors, session IDs or HAR export.
CDP IDs live only in memory until browser teardown. Response data is read only
after decoded byte counts and the browser's bounded resource buffer allow it.
"""
from __future__ import annotations

import asyncio
import base64
import json
from contextlib import suppress
from pathlib import Path
from urllib.parse import urlsplit

BODY_LIMIT = 16_384
BODY_TIMEOUT = 3.0
HOST = "handlaprivatkund.ica.se"
STORE_PATH = "/stores/1088004"


def public_path(url: str) -> str | None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname != HOST or parsed.username or parsed.password:
        return None
    if parsed.path in {STORE_PATH, STORE_PATH + "/search",
                       STORE_PATH + "/api/webproductpagews/v6/product-pages/search",
                       STORE_PATH + "/api/webproductpagews/v6/products"}:
        return parsed.path
    return None


def public_error_markers(value: str) -> list[str]:
    """Only fixed, reviewed phrases are exported, never arbitrary source text."""
    text = value[:BODY_LIMIT].casefold()
    phrases = {
        "access_denied": ("access denied", "access_denied"),
        "forbidden": ("forbidden",),
        "permission_denied": ("you don't have permission to access",),
        "human_verification": ("verify you are human", "human verification"),
        "captcha": ("captcha",),
        "robots_denied": ("robots_denied",),
        "request_blocked": ("request blocked", "request_blocked"),
        "session_required": ("session_required",),
        "failed_fetch": ("failed to fetch",),
        "resource_http_403": ("server responded with a status of 403",),
        "chunk_load_error": ("chunkloaderror", "loading chunk"),
    }
    return sorted(key for key, candidates in phrases.items() if any(
        phrase in text for phrase in candidates))


def project_error_body(body: bytes) -> dict:
    if len(body) > BODY_LIMIT:
        return {"body_read": "over_limit_omitted"}
    text = body.decode("utf8", errors="replace")
    result = {"body_read": "bounded", "body_bytes": len(body),
              "public_error_markers": public_error_markers(text)}
    # Unknown values, even under code/message, are never copied into evidence.
    try:
        payload = json.loads(text)
    except (ValueError, RecursionError):
        payload = None
    allowed_codes = {"ACCESS_DENIED", "FORBIDDEN", "ROBOTS_DENIED", "REQUEST_BLOCKED",
                     "SESSION_REQUIRED", "UNAUTHORIZED", "RATE_LIMITED"}
    if isinstance(payload, dict):
        codes = [payload.get("code"), payload.get("errorCode")]
        if isinstance(payload.get("error"), dict):
            codes.append(payload["error"].get("code"))
        result["public_error_codes"] = sorted({c for c in codes
                                               if isinstance(c, str) and c in allowed_codes})
    return result


async def browser_runtime(browser, *, channel: str | None) -> dict:
    result = {"headless": True, "channel": channel or "default_headless_shell",
              "actual_executable": None, "version": getattr(browser, "version", None)}
    try:
        session = await browser.new_browser_cdp_session()
        processes = await session.send("SystemInfo.getProcessInfo")
        for process in processes.get("processInfo", []):
            if process.get("type") == "browser":
                # Only this browser's executable; no command line/profile/IDs.
                executable = Path(f"/proc/{int(process['id'])}/exe").readlink()
                result["actual_executable"] = str(executable)
        await session.detach()
    except Exception:  # noqa: BLE001 - diagnostics must not mask normal collection
        result["executable_probe"] = "unavailable"
    return result


class AccessDiagnostics:
    def __init__(self):
        self.session = None
        self.requests: dict[str, dict] = {}
        self.enabled = False

    async def start(self, context, page):
        self.session = await context.new_cdp_session(page)
        self.session.on("Network.requestWillBeSent", self._request)
        self.session.on("Network.dataReceived", self._data)
        self.session.on("Network.loadingFinished", self._finished)
        self.session.on("Network.loadingFailed", self._failed)
        await self.session.send("Network.enable", {
            "maxTotalBufferSize": 2 * BODY_LIMIT, "maxResourceBufferSize": BODY_LIMIT,
            "maxPostDataSize": 0,
        })
        self.enabled = True

    def _request(self, event):
        req = event.get("request", {})
        path = public_path(req.get("url", ""))
        if path and len(self.requests) < 512:
            self.requests[event["requestId"]] = {
                "path": path, "method": req.get("method"), "decoded_bytes": 0,
                "done": asyncio.Event(), "failed": False,
            }

    def _data(self, event):
        row = self.requests.get(event["requestId"])
        if row:
            row["decoded_bytes"] += max(0, event.get("dataLength", 0))

    def _finished(self, event):
        row = self.requests.get(event["requestId"])
        if row:
            row["done"].set()

    def _failed(self, event):
        row = self.requests.get(event["requestId"])
        if row:
            row["failed"] = True
            row["done"].set()

    async def error(self, response) -> dict:
        result = {"content_type": None, "body_read": "diagnostics_unavailable"}
        try:
            value = await asyncio.wait_for(response.header_value("content-type"), BODY_TIMEOUT)
            mime = (value or "").split(";", 1)[0].strip().lower()
            result["content_type"] = mime if mime in {
                "text/html", "text/plain", "application/json", "application/problem+json"
            } else "other_or_missing"
            if not self.enabled:
                return result
            matches = [(key, row) for key, row in self.requests.items()
                       if row["path"] == public_path(response.request.url)
                       and row["method"] == response.request.method]
            if len(matches) != 1:
                return {**result, "body_read": "ambiguous_or_missing_request_omitted"}
            key, row = matches[0]
            await asyncio.wait_for(row["done"].wait(), BODY_TIMEOUT)
            if row["failed"] or row["decoded_bytes"] > BODY_LIMIT:
                return {**result, "body_read": "failed_or_oversized_omitted"}
            if result["content_type"] == "other_or_missing":
                return {**result, "body_read": "unsupported_type_omitted"}
            payload = await asyncio.wait_for(self.session.send(
                "Network.getResponseBody", {"requestId": key}), BODY_TIMEOUT)
            raw = payload.get("body", "")
            if len(raw) > BODY_LIMIT * 4 // 3 + 4:
                return {**result, "body_read": "over_limit_omitted"}
            body = base64.b64decode(raw, validate=True) if payload.get(
                "base64Encoded") else raw.encode("utf8")
            return {**result, **project_error_body(body)}
        except Exception as exc:  # noqa: BLE001 - never expose CDP/session error details
            return {**result, "body_read": "bounded_read_unavailable",
                    "diagnostic_error_class": type(exc).__name__}

    async def close(self):
        if self.session:
            with suppress(Exception):
                await self.session.detach()
        self.requests.clear()
