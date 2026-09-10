from __future__ import annotations

import re
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from grocery_data.app.api.physical_check import _csv_safe_cell
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.field_security import (
    FIELD_CSRF_HEADER,
    FIELD_LOGIN_CHALLENGE_COOKIE,
    FIELD_SESSION_COOKIE,
    PHYSICAL_CHECK_CONTRACT,
    FieldLoginChallengeCodec,
    FieldSessionCodec,
    InMemoryRateLimiter,
)
from grocery_data.app.main import create_app
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import PhysicalStoreModel

ACCESS_TOKEN = "field-test-access-token-with-at-least-32-bytes"
ORIGIN = "https://field.example"
QUICK_TUNNEL_ORIGIN = "https://temporary-field-check.trycloudflare.com"


def _settings(**overrides: object) -> GroceryDataSettings:
    values: dict[str, object] = {
        "database_url": "sqlite+pysqlite:///:memory:",
        "raw_snapshot_root": Path("unused-raw"),
        "user_agent": "field-security-test",
        "field_mode_enabled": True,
        "physical_check_access_token": ACCESS_TOKEN,
        "field_public_origin": ORIGIN,
    }
    values.update(overrides)
    return GroceryDataSettings(**values)  # type: ignore[arg-type]


def _client(settings: GroceryDataSettings | None = None, **kwargs: object) -> TestClient:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    return TestClient(
        create_app(factory, settings=settings or _settings()),
        base_url=ORIGIN,
        **kwargs,  # type: ignore[arg-type]
    )


def _login_challenge(client: TestClient) -> str:
    response = client.get("/physical-check/login", follow_redirects=False)
    assert response.status_code == 200
    match = re.search(r'name="login_challenge" type="hidden" value="([^"]+)"', response.text)
    assert match is not None
    return match.group(1)


def _login(
    client: TestClient,
    token: str = ACCESS_TOKEN,
    *,
    headers: dict[str, str] | None = None,
):
    challenge = _login_challenge(client)
    request_headers = {"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}
    if headers:
        request_headers.update(headers)
    return client.post(
        "/physical-check/login",
        data={"access_token": token, "login_challenge": challenge},
        headers=request_headers,
        follow_redirects=False,
    )


def _csrf(client: TestClient) -> str:
    response = client.get("/physical-check/session")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def test_field_mode_is_off_by_default_and_enabled_mode_requires_strong_token() -> None:
    default = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=Path("unused-raw"),
        user_agent="field-security-test",
    )
    assert default.field_mode_enabled is False

    with pytest.raises(ValueError, match="PHYSICAL_CHECK_ACCESS_TOKEN"):
        replace(default, field_mode_enabled=True)
    with pytest.raises(ValueError, match="at least 32 bytes"):
        replace(
            default,
            field_mode_enabled=True,
            physical_check_access_token="too-short",
        )
    configured = replace(
        default,
        field_mode_enabled=True,
        physical_check_access_token=ACCESS_TOKEN,
    )
    assert ACCESS_TOKEN not in repr(configured)


def test_login_issues_only_short_lived_secure_httponly_samesite_cookie() -> None:
    client = _client()
    login_page = client.get("/physical-check/login")

    assert login_page.status_code == 200
    assert ACCESS_TOKEN not in login_page.text
    assert 'name="login_challenge" type="hidden"' in login_page.text
    assert "/static/physical-check.css?v=20260827-field2" in login_page.text
    assert "style-src 'self'" in login_page.headers["content-security-policy"]
    challenge_cookie = login_page.headers["set-cookie"]
    assert f"{FIELD_LOGIN_CHALLENGE_COOKIE}=" in challenge_cookie
    assert "Max-Age=300" in challenge_cookie
    assert "Path=/physical-check/login" in challenge_cookie
    assert "HttpOnly" in challenge_cookie
    assert "Secure" in challenge_cookie
    assert "SameSite=strict" in challenge_cookie
    response = _login(client)

    assert response.status_code == 303
    assert response.headers["location"] == "/physical-check"
    cookie = response.headers["set-cookie"]
    assert f"{FIELD_SESSION_COOKIE}=" in cookie
    assert "Max-Age=3600" in cookie
    assert "Path=/physical-check" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert ACCESS_TOKEN not in cookie
    assert ACCESS_TOKEN not in response.headers["location"]
    assert client.get("/physical-check").status_code == 200


def test_field_session_exposes_frontend_contract_without_secrets() -> None:
    client = _client()
    _login(client)

    response = client.get("/physical-check/session")

    assert response.status_code == 200
    assert response.json()["physical_check_contract"] == PHYSICAL_CHECK_CONTRACT
    assert ACCESS_TOKEN not in response.text


def test_tampered_or_expired_field_session_is_rejected() -> None:
    now = [1000.0]
    codec = FieldSessionCodec(ACCESS_TOKEN, ttl_seconds=60, clock=lambda: now[0])
    issued = codec.issue()

    assert codec.verify(issued) is not None
    assert codec.verify(issued[:-1] + ("A" if issued[-1] != "A" else "B")) is None
    now[0] = 1060.0
    assert codec.verify(issued) is None


def test_tampered_or_expired_login_challenge_is_rejected() -> None:
    now = [1000.0]
    codec = FieldLoginChallengeCodec(ACCESS_TOKEN, ttl_seconds=60, clock=lambda: now[0])
    issued = codec.issue()

    assert codec.verify(issued) is True
    assert codec.verify(issued[:-1] + ("A" if issued[-1] != "A" else "B")) is False
    now[0] = 1060.0
    assert codec.verify(issued) is False


def test_field_routes_require_authentication_and_mutations_require_csrf_and_origin() -> None:
    client = _client()
    assert client.get("/physical-check", follow_redirects=False).status_code == 303
    assert client.get("/physical-check/stores?city=Lund").status_code == 401
    _login(client)
    csrf = _csrf(client)
    payload = {
        "physical_store_id": "missing",
        "gtin": "7310865004703",
        "shelf_price": "29.90",
    }

    no_origin = client.post(
        "/physical-check/observations",
        json=payload,
        headers={FIELD_CSRF_HEADER: csrf},
    )
    wrong_origin = client.post(
        "/physical-check/observations",
        json=payload,
        headers={"Origin": "https://attacker.example", FIELD_CSRF_HEADER: csrf},
    )
    no_csrf = client.post(
        "/physical-check/observations",
        json=payload,
        headers={"Origin": ORIGIN},
    )
    wrong_media = client.post(
        "/physical-check/observations",
        content="physical_store_id=missing",
        headers={
            "Origin": ORIGIN,
            FIELD_CSRF_HEADER: csrf,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    accepted_by_boundary = client.post(
        "/physical-check/observations",
        json=payload,
        headers={"Origin": ORIGIN, FIELD_CSRF_HEADER: csrf},
    )

    assert no_origin.status_code == 403
    assert wrong_origin.status_code == 403
    assert no_csrf.status_code == 403
    assert wrong_media.status_code == 415
    assert accepted_by_boundary.status_code == 404


def test_authenticated_field_write_succeeds_without_exposing_admin_routes() -> None:
    client = _client()
    with client.app.state.session_factory() as session:
        now = datetime.now(tz=UTC)
        session.add(
            PhysicalStoreModel(
                id="field-write-store",
                chain="hemkop",
                external_store_id="field-write-store",
                name="Hemköp Lund Karhögstorg",
                address="Karhögstorg 2A",
                postal_code="223 58",
                city="Lund",
                official_source="field security test fixture",
                discovered_at=now,
                last_seen_at=now,
                is_active=True,
                lifecycle_state="active",
            )
        )
        session.commit()

    assert _login(client).status_code == 303
    response = client.post(
        "/physical-check/observations",
        json={
            "physical_store_id": "field-write-store",
            "gtin": "7310865004703",
            "shelf_price": "29.90",
        },
        headers={"Origin": ORIGIN, FIELD_CSRF_HEADER: _csrf(client)},
    )

    assert response.status_code == 201
    assert response.json()["catalog_price_updated"] is False
    assert client.get("/admin/connectors/hemkop").status_code == 404


def test_field_deployment_exposes_only_login_physical_routes_and_scanner_assets() -> None:
    client = _client()
    _login(client)

    stylesheet = client.get("/static/physical-check.css?v=20260828-scanner3")
    javascript = client.get("/static/physical-check.js?v=20260828-scanner3")
    api_errors = client.get("/static/physical-check-api-errors.js?v=20260829-identifiers2")
    scanner_bundle = client.get("/static/physical-barcode-scanner.js?v=20260828-scanner3")
    field_page = client.get("/physical-check")
    assert stylesheet.status_code == 200
    assert javascript.status_code == 200
    assert api_errors.status_code == 200
    assert scanner_bundle.status_code == 200
    assert field_page.status_code == 200
    for response in (stylesheet, javascript, api_errors, scanner_bundle, field_page):
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "no-referrer"
        assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert "script-src 'self'" in field_page.headers["content-security-policy"]
    assert "/physical-check/session" in javascript.text
    assert PHYSICAL_CHECK_CONTRACT in javascript.text
    assert "Stoppa och starta om scripts/start_field_server.ps1" in javascript.text
    assert "PhysicalCheckApiErrors" in javascript.text
    assert "X-Physical-Check-CSRF" in javascript.text
    assert ACCESS_TOKEN not in javascript.text
    assert ACCESS_TOKEN not in api_errors.text
    assert ACCESS_TOKEN not in scanner_bundle.text
    for forbidden in (
        "/",
        "/admin/connectors/willys",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/health/connectors",
        "/operations/price-universe",
        "/raw/snapshots",
        "/static/status.js",
        "/static/index.html",
    ):
        response = client.get(forbidden)
        assert response.status_code == 404, forbidden

    registered = {
        route.path
        for route in client.app.routes
        if getattr(route, "path", None) is not None
    }
    assert not any(
        path.startswith(("/admin", "/health", "/operations", "/raw"))
        for path in registered
    )
    assert "/openapi.json" not in registered


def test_login_rate_limit_ignores_untrusted_forwarded_for() -> None:
    client = _client(_settings(field_login_attempts_per_minute=2))
    first = _login(
        client,
        "wrong",
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    second = _login(
        client,
        "wrong",
        headers={"X-Forwarded-For": "198.51.100.2"},
    )
    limited = _login(
        client,
        headers={"X-Forwarded-For": "198.51.100.3"},
    )

    assert first.status_code == second.status_code == 401
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "60"


def test_quick_tunnel_origin_uses_https_host_and_ignores_forwarded_scheme_and_host() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    client = TestClient(
        create_app(factory, settings=_settings(field_public_origin=None)),
        base_url=QUICK_TUNNEL_ORIGIN,
    )

    rejected_challenge = _login_challenge(client)
    rejected = client.post(
        "/physical-check/login",
        data={"access_token": ACCESS_TOKEN, "login_challenge": rejected_challenge},
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "same-origin",
        },
        follow_redirects=False,
    )
    assert rejected.status_code == 403

    cross_site_challenge = _login_challenge(client)
    inconsistent_cross_site = client.post(
        "/physical-check/login",
        data={"access_token": ACCESS_TOKEN, "login_challenge": cross_site_challenge},
        headers={
            "Origin": QUICK_TUNNEL_ORIGIN,
            "Sec-Fetch-Site": "cross-site",
        },
        follow_redirects=False,
    )
    assert inconsistent_cross_site.status_code == 403

    accepted_challenge = _login_challenge(client)
    accepted = client.post(
        "/physical-check/login",
        data={"access_token": ACCESS_TOKEN, "login_challenge": accepted_challenge},
        headers={
            "Origin": QUICK_TUNNEL_ORIGIN,
            # iPhone/Safari and embedded browser surfaces may classify a
            # user-initiated form navigation as ``none``. The exact Origin
            # remains the authoritative same-origin check.
            "Sec-Fetch-Site": "none",
            "X-Forwarded-Proto": "http",
            "X-Forwarded-Host": "attacker.example",
        },
        follow_redirects=False,
    )
    assert accepted.status_code == 303


@pytest.mark.parametrize("origin", [None, "null"])
def test_login_accepts_safari_missing_or_null_origin_only_with_signed_challenge(
    origin: str | None,
) -> None:
    client = _client()
    challenge = _login_challenge(client)
    headers = {"Sec-Fetch-Site": "none"}
    if origin is not None:
        headers["Origin"] = origin

    accepted = client.post(
        "/physical-check/login",
        data={"access_token": ACCESS_TOKEN, "login_challenge": challenge},
        headers=headers,
        follow_redirects=False,
    )

    assert accepted.status_code == 303
    assert f"{FIELD_LOGIN_CHALLENGE_COOKIE}=\"\"" in accepted.headers["set-cookie"]


def test_login_rejects_missing_or_tampered_challenge_and_clears_cookie() -> None:
    no_challenge_client = _client()
    missing = no_challenge_client.post(
        "/physical-check/login",
        data={"access_token": ACCESS_TOKEN},
        headers={"Sec-Fetch-Site": "none"},
        follow_redirects=False,
    )
    assert missing.status_code == 403
    assert missing.json()["detail"] == "login challenge rejected"

    tampered_client = _client()
    challenge = _login_challenge(tampered_client)
    tampered = tampered_client.post(
        "/physical-check/login",
        data={
            "access_token": ACCESS_TOKEN,
            "login_challenge": challenge[:-1]
            + ("A" if challenge[-1] != "A" else "B"),
        },
        headers={"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert tampered.status_code == 403
    assert tampered.json()["detail"] == "login challenge rejected"
    cleared = tampered.headers["set-cookie"]
    assert f"{FIELD_LOGIN_CHALLENGE_COOKIE}=\"\"" in cleared
    assert "Max-Age=0" in cleared


def test_trusted_proxy_chain_and_write_rate_limit_are_bounded() -> None:
    proxy_settings = _settings(
        field_login_attempts_per_minute=1,
        field_write_requests_per_minute=1,
        field_trusted_proxy_cidrs=("127.0.0.0/8",),
    )
    client = _client(proxy_settings, client=("127.0.0.1", 50000))
    first_identity = _login(
        client,
        "wrong",
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    second_identity = _login(
        client,
        headers={"X-Forwarded-For": "198.51.100.2"},
    )
    assert first_identity.status_code == 401
    assert second_identity.status_code == 303

    csrf = _csrf(client)
    write_headers = {"Origin": ORIGIN, FIELD_CSRF_HEADER: csrf}
    payload = {
        "physical_store_id": "missing",
        "gtin": "7310865004703",
        "shelf_price": "29.90",
    }
    first_write = client.post(
        "/physical-check/observations",
        json=payload,
        headers=write_headers,
    )
    limited_write = client.post(
        "/physical-check/observations",
        json=payload,
        headers=write_headers,
    )
    assert first_write.status_code == 404
    assert limited_write.status_code == 429


def test_rate_limiter_identity_storage_is_bounded_and_expired_keys_are_reclaimed() -> None:
    now = [1000.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0], max_identities=2)

    assert limiter.allow("login", "one", limit=1)
    assert limiter.allow("login", "two", limit=1)
    assert limiter.identity_count == 2
    assert limiter.allow("login", "three", limit=1) is False
    assert limiter.identity_count == 2

    now[0] = 1061.0
    assert limiter.allow("login", "three", limit=1)
    assert limiter.identity_count == 1


@pytest.mark.parametrize("prefix", ["=", "+", "-", "@", "  ="])
def test_field_csv_export_neutralizes_spreadsheet_formula_prefixes(prefix: str) -> None:
    value = f"{prefix}HYPERLINK(\"https://attacker.invalid\")"

    assert _csv_safe_cell(value) == f"'{value}"
    assert _csv_safe_cell("ordinary product") == "ordinary product"
