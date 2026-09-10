from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from html import escape
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from grocery_data.app.config import GroceryDataSettings

FIELD_SESSION_COOKIE = "physical_check_session"
FIELD_LOGIN_CHALLENGE_COOKIE = "physical_check_login_challenge"
PHYSICAL_CHECK_CONTRACT = "product-identification-v2"
_COOKIE_VERSION = 1
_LOGIN_PATH = "/physical-check/login"
_LOGOUT_PATH = "/physical-check/logout"
_SESSION_PATH = "/physical-check/session"
_FIELD_DOCUMENT_PATHS = frozenset(
    {
        "/physical-check",
        "/physical-check/scanner-test",
    }
)
FIELD_CSRF_HEADER = "X-Physical-Check-CSRF"
_LOGIN_CHALLENGE_TTL_SECONDS = 300
_FIELD_STATIC_PATHS = frozenset(
    {
        "/static/physical-barcode-scanner.js",
        "/static/physical-check-api-errors.js",
        "/static/physical-check.css",
        "/static/physical-check.js",
    }
)


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _normalize_origin(value: str) -> str | None:
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username or parsed.password or parsed.path not in {"", "/"}:
            return None
        if parsed.query or parsed.fragment:
            return None
        port = parsed.port
    except ValueError:
        return None
    default_port = 443 if parsed.scheme == "https" else 80
    authority = parsed.hostname.casefold()
    if ":" in authority:
        authority = f"[{authority}]"
    if port is not None and port != default_port:
        authority = f"{authority}:{port}"
    return f"{parsed.scheme}://{authority}"


class FieldSessionCodec:
    """Issue opaque-enough signed field sessions without serialising the login token."""

    def __init__(
        self,
        access_token: str,
        *,
        ttl_seconds: int,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = hashlib.sha256(
            b"grocery-data/physical-check/session/v1\0" + access_token.encode("utf-8")
        ).digest()
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    def issue(self) -> str:
        issued_at = int(self._clock())
        payload = {
            "v": _COOKIE_VERSION,
            "iat": issued_at,
            "exp": issued_at + self.ttl_seconds,
            "sid": secrets.token_urlsafe(18),
            "csrf": secrets.token_urlsafe(24),
        }
        encoded = _base64url_encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        signature = _base64url_encode(
            hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}"

    def verify(self, value: str | None) -> dict[str, Any] | None:
        if not value or len(value) > 1024:
            return None
        try:
            encoded, supplied_signature = value.split(".", 1)
            expected_signature = _base64url_encode(
                hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return None
            payload = json.loads(_base64url_decode(encoded))
            now = int(self._clock())
            if (
                not isinstance(payload, dict)
                or payload.get("v") != _COOKIE_VERSION
                or not isinstance(payload.get("sid"), str)
                or len(payload["sid"]) < 16
                or not isinstance(payload.get("csrf"), str)
                or len(payload["csrf"]) < 24
                or not isinstance(payload.get("iat"), int)
                or not isinstance(payload.get("exp"), int)
                or payload["iat"] > now + 30
                or payload["exp"] <= now
                or payload["exp"] - payload["iat"] != self.ttl_seconds
            ):
                return None
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None
        return payload


class FieldLoginChallengeCodec:
    """Sign short-lived, pre-authentication double-submit challenges."""

    def __init__(
        self,
        access_token: str,
        *,
        ttl_seconds: int = _LOGIN_CHALLENGE_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._key = hashlib.sha256(
            b"grocery-data/physical-check/login-challenge/v1\0"
            + access_token.encode("utf-8")
        ).digest()
        self.ttl_seconds = ttl_seconds
        self._clock = clock

    def issue(self) -> str:
        issued_at = int(self._clock())
        payload = {
            "v": _COOKIE_VERSION,
            "iat": issued_at,
            "exp": issued_at + self.ttl_seconds,
            "nonce": secrets.token_urlsafe(24),
        }
        encoded = _base64url_encode(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        signature = _base64url_encode(
            hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
        )
        return f"{encoded}.{signature}"

    def verify(self, value: str | None) -> bool:
        if not value or len(value) > 1024:
            return False
        try:
            encoded, supplied_signature = value.split(".", 1)
            expected_signature = _base64url_encode(
                hmac.new(self._key, encoded.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                return False
            payload = json.loads(_base64url_decode(encoded))
            now = int(self._clock())
            return bool(
                isinstance(payload, dict)
                and payload.get("v") == _COOKIE_VERSION
                and isinstance(payload.get("nonce"), str)
                and len(payload["nonce"]) >= 24
                and isinstance(payload.get("iat"), int)
                and isinstance(payload.get("exp"), int)
                and payload["iat"] <= now + 30
                and payload["exp"] > now
                and payload["exp"] - payload["iat"] == self.ttl_seconds
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False


class InMemoryRateLimiter:
    """Small process-local sliding-window limiter for the optional field surface."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_identities: int = 10_000,
    ) -> None:
        if max_identities < 1:
            raise ValueError("max_identities must be positive")
        self._clock = clock
        self._max_identities = max_identities
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, bucket: str, identity: str, *, limit: int, window: int = 60) -> bool:
        now = self._clock()
        cutoff = now - window
        key = (bucket, identity)
        with self._lock:
            if key not in self._events and len(self._events) >= self._max_identities:
                for existing_key, existing_events in tuple(self._events.items()):
                    while existing_events and existing_events[0] <= cutoff:
                        existing_events.popleft()
                    if not existing_events:
                        del self._events[existing_key]
                if len(self._events) >= self._max_identities:
                    # A random-identity flood must not turn into unbounded
                    # process memory. Refuse new identities until the bounded
                    # window has expired instead of evicting active limits.
                    return False
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    @property
    def identity_count(self) -> int:
        with self._lock:
            return len(self._events)


@dataclass(frozen=True, slots=True)
class FieldSecurityContext:
    settings: GroceryDataSettings
    codec: FieldSessionCodec
    login_challenge_codec: FieldLoginChallengeCodec
    limiter: InMemoryRateLimiter
    trusted_proxy_networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]

    @classmethod
    def from_settings(cls, settings: GroceryDataSettings) -> FieldSecurityContext:
        token = settings.physical_check_access_token
        if not settings.field_mode_enabled or token is None:
            raise ValueError("field security requires enabled field mode and an access token")
        networks = tuple(
            ipaddress.ip_network(value, strict=False)
            for value in settings.field_trusted_proxy_cidrs
        )
        if settings.field_public_origin is not None:
            normalized = _normalize_origin(settings.field_public_origin)
            if normalized is None or not normalized.startswith("https://"):
                raise ValueError("FIELD_PUBLIC_ORIGIN must be an HTTPS origin without a path")
        return cls(
            settings=settings,
            codec=FieldSessionCodec(token, ttl_seconds=settings.field_session_ttl_seconds),
            login_challenge_codec=FieldLoginChallengeCodec(token),
            limiter=InMemoryRateLimiter(),
            trusted_proxy_networks=networks,
        )

    def client_identity(self, request: Request) -> str:
        peer_text = request.client.host if request.client is not None else "unknown"
        try:
            peer = ipaddress.ip_address(peer_text)
        except ValueError:
            return peer_text
        if not any(peer in network for network in self.trusted_proxy_networks):
            return str(peer)
        forwarded = request.headers.get("x-forwarded-for", "")
        try:
            chain = [
                ipaddress.ip_address(value.strip())
                for value in forwarded.split(",")
                if value.strip()
            ]
        except ValueError:
            return str(peer)
        for address in reversed(chain):
            if not any(address in network for network in self.trusted_proxy_networks):
                return str(address)
        return str(chain[0]) if chain else str(peer)

    def expected_origin(self, request: Request) -> str | None:
        if self.settings.field_public_origin is not None:
            return _normalize_origin(self.settings.field_public_origin)
        # Quick Tunnel TLS terminates before the loopback HTTP hop. Trust
        # neither X-Forwarded-Proto nor X-Forwarded-Host; compare the browser's
        # HTTPS Origin with the ordinary Host that reached this ASGI app.
        return _normalize_origin(f"https://{request.headers.get('host', '')}")


def _apply_field_security_headers(
    response: Response,
    *,
    document: bool = False,
) -> Response:
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault(
        "Permissions-Policy",
        "camera=(self), geolocation=(), microphone=()",
    )
    response.headers.setdefault(
        "Content-Security-Policy",
        (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; img-src 'self' data:; media-src 'self' blob:; "
            "object-src 'none'; base-uri 'none'; form-action 'self'; "
            "frame-ancestors 'none'"
            if document
            else "default-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        ),
    )
    return response


def _login_page(
    context: FieldSecurityContext,
    *,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    challenge = context.login_challenge_codec.issue()
    error_markup = (
        f'<p class="error" role="alert">{escape(error)}</p>' if error else ""
    )
    html = f"""<!doctype html>
<html lang="sv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f4f7f2">
<title>Logga in till fältläge</title>
<link rel="stylesheet" href="/static/physical-check.css?v=20260827-field2"></head><body>
<main><header class="page-header"><p class="eyebrow">SKYDDAT FÄLTLÄGE</p>
<h1>Fysiskt prisstickprov</h1>
<p class="lede">Logga in med den tillfälliga åtkomstkod som är konfigurerad på fältdatorn.</p>
</header><section class="card setup-card">{error_markup}
<form method="post" action="{_LOGIN_PATH}">
<input name="login_challenge" type="hidden" value="{escape(challenge, quote=True)}">
<label for="access-token">Åtkomstkod</label>
<input id="access-token" name="access_token" type="password" required
 autocomplete="current-password" autofocus>
<button class="primary" type="submit">Logga in</button></form>
</section></main></body></html>"""
    response = HTMLResponse(
        html,
        status_code=status_code,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": (
                "default-src 'none'; style-src 'self'; form-action 'self'; "
                "base-uri 'none'; frame-ancestors 'none'"
            ),
        },
    )
    response.set_cookie(
        FIELD_LOGIN_CHALLENGE_COOKIE,
        challenge,
        max_age=context.login_challenge_codec.ttl_seconds,
        path=_LOGIN_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return _apply_field_security_headers(response, document=True)


def _clear_login_challenge(response: Response) -> Response:
    response.delete_cookie(
        FIELD_LOGIN_CHALLENGE_COOKIE,
        path=_LOGIN_PATH,
        secure=True,
        httponly=True,
        samesite="strict",
    )
    return response


def field_login_router() -> APIRouter:
    router = APIRouter(include_in_schema=False)

    @router.get(_LOGIN_PATH)
    def login_page(request: Request) -> Response:
        context: FieldSecurityContext = request.app.state.field_security
        if context.codec.verify(request.cookies.get(FIELD_SESSION_COOKIE)) is not None:
            return RedirectResponse("/physical-check", status_code=303)
        return _login_page(context)

    @router.post(_LOGIN_PATH)
    async def login(request: Request) -> Response:
        context: FieldSecurityContext = request.app.state.field_security
        if not _login_origin_is_valid(request, context):
            return _clear_login_challenge(
                JSONResponse({"detail": "request origin rejected"}, status_code=403)
            )
        identity = context.client_identity(request)
        if not context.limiter.allow(
            "login",
            identity,
            limit=context.settings.field_login_attempts_per_minute,
        ):
            return _clear_login_challenge(
                JSONResponse(
                    {"detail": "too many login attempts"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            )
        if request.headers.get("content-type", "").split(";", 1)[0].strip().casefold() != (
            "application/x-www-form-urlencoded"
        ):
            return _clear_login_challenge(
                JSONResponse({"detail": "unsupported media type"}, status_code=415)
            )
        body = await request.body()
        if len(body) > 4096:
            return _clear_login_challenge(
                JSONResponse({"detail": "invalid credentials"}, status_code=401)
            )
        try:
            form = parse_qs(
                body.decode("utf-8"),
                strict_parsing=True,
                max_num_fields=4,
            )
            submitted = form["access_token"][0]
            supplied_challenge = form["login_challenge"][0]
        except (UnicodeDecodeError, ValueError, KeyError, IndexError):
            submitted = ""
            supplied_challenge = ""
        cookie_challenge = request.cookies.get(FIELD_LOGIN_CHALLENGE_COOKIE)
        if (
            not cookie_challenge
            or not hmac.compare_digest(supplied_challenge, cookie_challenge)
            or not context.login_challenge_codec.verify(cookie_challenge)
        ):
            return _clear_login_challenge(
                JSONResponse({"detail": "login challenge rejected"}, status_code=403)
            )
        expected = context.settings.physical_check_access_token or ""
        if not hmac.compare_digest(submitted.encode("utf-8"), expected.encode("utf-8")):
            # Consume the submitted challenge and rotate it before another
            # credential attempt can be made from the returned form.
            return _login_page(context, error="Ogiltig åtkomstkod.", status_code=401)
        response = RedirectResponse("/physical-check", status_code=303)
        response.set_cookie(
            FIELD_SESSION_COOKIE,
            context.codec.issue(),
            max_age=context.settings.field_session_ttl_seconds,
            path="/physical-check",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
        return _clear_login_challenge(response)

    @router.post(_LOGOUT_PATH)
    def logout() -> Response:
        response = RedirectResponse(_LOGIN_PATH, status_code=303)
        response.delete_cookie(
            FIELD_SESSION_COOKIE,
            path="/physical-check",
            secure=True,
            httponly=True,
            samesite="lax",
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @router.get(_SESSION_PATH)
    def session_state(request: Request) -> Response:
        field_session = request.state.field_session
        return JSONResponse(
            {
                "csrf_token": field_session["csrf"],
                "expires_at": field_session["exp"],
                "physical_check_contract": PHYSICAL_CHECK_CONTRACT,
            },
            headers={"Cache-Control": "no-store"},
        )

    return router


def _origin_is_valid(request: Request, context: FieldSecurityContext) -> bool:
    origin = _normalize_origin(request.headers.get("origin", ""))
    expected = context.expected_origin(request)
    # Origin is the authoritative same-origin signal here.  Safari and
    # embedded iOS browser surfaces may legitimately send Sec-Fetch-Site as
    # ``none`` (rather than ``same-origin``) for a user-initiated navigation
    # and form submission.  Requiring one exact Fetch Metadata value caused
    # valid Quick Tunnel logins to fail even though the HTTPS Origin matched
    # the tunnel Host exactly.  Keep Fetch Metadata as a fail-closed signal
    # when the browser explicitly says cross-site, but do not use it as an
    # allowlist in place of the stronger Origin comparison.
    fetch_site = request.headers.get("sec-fetch-site", "").strip().casefold()
    return (
        origin is not None
        and expected is not None
        and hmac.compare_digest(origin, expected)
        and fetch_site != "cross-site"
    )


def _login_origin_is_valid(request: Request, context: FieldSecurityContext) -> bool:
    """Validate login navigation metadata without weakening authenticated writes.

    Some Safari/iOS form navigations omit ``Origin`` or send the opaque value
    ``null``. Those cases are safe only in combination with the signed,
    host-only, SameSite=Strict double-submit challenge validated by the login
    handler. An explicit web origin remains mandatory to match the configured
    field origin, and an explicit cross-site Fetch Metadata signal always
    fails closed.
    """

    fetch_site = request.headers.get("sec-fetch-site", "").strip().casefold()
    if fetch_site == "cross-site":
        return False
    expected = context.expected_origin(request)
    if expected is None:
        return False
    raw_origin = request.headers.get("origin")
    if raw_origin is None or raw_origin.strip().casefold() == "null":
        return True
    origin = _normalize_origin(raw_origin)
    return origin is not None and hmac.compare_digest(origin, expected)


class FieldModeBoundaryMiddleware(BaseHTTPMiddleware):
    """Fail-closed boundary for a dedicated field-mode deployment."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        context: FieldSecurityContext = request.app.state.field_security
        path = request.url.path
        method = request.method.upper()
        if path in _FIELD_STATIC_PATHS and method in {"GET", "HEAD"}:
            return _apply_field_security_headers(await call_next(request))
        if path == _LOGIN_PATH and method in {"GET", "POST"}:
            return _apply_field_security_headers(await call_next(request), document=True)
        if not path.startswith("/physical-check"):
            return _apply_field_security_headers(
                JSONResponse({"detail": "not found"}, status_code=404)
            )

        session = context.codec.verify(request.cookies.get(FIELD_SESSION_COOKIE))
        if session is None:
            if path in _FIELD_DOCUMENT_PATHS and method in {"GET", "HEAD"}:
                return _apply_field_security_headers(
                    RedirectResponse(_LOGIN_PATH, status_code=303)
                )
            return _apply_field_security_headers(
                JSONResponse({"detail": "field authentication required"}, status_code=401)
            )
        request.state.field_session = session

        if method not in {"GET", "HEAD"}:
            if not _origin_is_valid(request, context):
                return _apply_field_security_headers(
                    JSONResponse({"detail": "request origin rejected"}, status_code=403)
                )
            if path != _LOGOUT_PATH:
                supplied_csrf = request.headers.get(FIELD_CSRF_HEADER, "")
                if not hmac.compare_digest(supplied_csrf, session["csrf"]):
                    return _apply_field_security_headers(
                        JSONResponse({"detail": "CSRF token rejected"}, status_code=403)
                    )
            if path != _LOGOUT_PATH and (
                request.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
                != "application/json"
            ):
                return _apply_field_security_headers(
                    JSONResponse({"detail": "JSON request required"}, status_code=415)
                )
            # Bound writes by the signed field session itself. A deployment
            # must not make this limit bypassable by rotating forwarded IPs.
            identity = session["sid"]
            if not context.limiter.allow(
                "write",
                identity,
                limit=context.settings.field_write_requests_per_minute,
            ):
                return _apply_field_security_headers(
                    JSONResponse(
                        {"detail": "too many field writes"},
                        status_code=429,
                        headers={"Retry-After": "60"},
                    )
                )
        response = await call_next(request)
        return _apply_field_security_headers(
            response,
            document=path in _FIELD_DOCUMENT_PATHS,
        )


__all__ = [
    "FIELD_CSRF_HEADER",
    "FIELD_LOGIN_CHALLENGE_COOKIE",
    "FIELD_SESSION_COOKIE",
    "PHYSICAL_CHECK_CONTRACT",
    "FieldLoginChallengeCodec",
    "FieldModeBoundaryMiddleware",
    "FieldSecurityContext",
    "FieldSessionCodec",
    "InMemoryRateLimiter",
    "field_login_router",
]
