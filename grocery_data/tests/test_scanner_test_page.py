from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.main import create_app
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import PhysicalPriceObservationModel

ACCESS_TOKEN = "scanner-test-access-token-with-at-least-32-bytes"
ORIGIN = "https://field.example"


def _client() -> TestClient:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    settings = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=Path("unused-scanner-test-raw"),
        user_agent="scanner-test-page",
        field_mode_enabled=True,
        physical_check_access_token=ACCESS_TOKEN,
        field_public_origin=ORIGIN,
    )
    return TestClient(create_app(factory, settings=settings), base_url=ORIGIN)


def _login(client: TestClient) -> None:
    login_page = client.get("/physical-check/login")
    challenge_match = re.search(
        r'name="login_challenge" type="hidden" value="([^"]+)"',
        login_page.text,
    )
    assert challenge_match is not None
    response = client.post(
        "/physical-check/login",
        data={
            "access_token": ACCESS_TOKEN,
            "login_challenge": challenge_match.group(1),
        },
        headers={"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"},
        follow_redirects=False,
    )
    assert response.status_code == 303


def _observation_count(client: TestClient) -> int:
    with client.app.state.session_factory() as session:
        return int(
            session.scalar(select(func.count(PhysicalPriceObservationModel.id))) or 0
        )


def test_scanner_test_page_and_assets_require_field_authentication() -> None:
    client = _client()

    page = client.get("/physical-check/scanner-test", follow_redirects=False)
    javascript = client.get("/physical-check/scanner-test.js")
    stylesheet = client.get("/physical-check/scanner-test.css")

    assert page.status_code == 303
    assert page.headers["location"] == "/physical-check/login"
    assert javascript.status_code == 401
    assert stylesheet.status_code == 401

    _login(client)
    page = client.get("/physical-check/scanner-test")
    javascript = client.get("/physical-check/scanner-test.js")
    stylesheet = client.get("/physical-check/scanner-test.css")

    assert page.status_code == 200
    assert javascript.status_code == 200
    assert stylesheet.status_code == 200
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["permissions-policy"].startswith("camera=(self)")
    assert "/static/physical-barcode-scanner.js" in page.text
    assert "/physical-check/scanner-test.js" in page.text
    assert 'value="product" checked' in page.text
    assert 'value="shelf"' in page.text
    assert "Hyllkod" in page.text
    assert "shelf-barcode-length" in page.text
    assert ACCESS_TOKEN not in page.text


def test_scanner_test_is_read_only_and_does_not_expose_prices_or_admin() -> None:
    client = _client()
    _login(client)
    before = _observation_count(client)

    page = client.get("/physical-check/scanner-test")
    javascript = client.get("/physical-check/scanner-test.js")

    assert page.status_code == 200
    assert javascript.status_code == 200
    assert "digital-price-preview" not in page.text
    assert "digital-price-preview" not in javascript.text
    assert "/observations" not in javascript.text
    assert "/physical-check/scanner-diagnostics" in javascript.text
    assert "/physical-check/session" in javascript.text
    assert "if (response.status === 404) return;" in javascript.text
    assert "PhysicalPriceObservation" not in javascript.text
    assert "createBarcodeScanner" in javascript.text
    assert "normalizeGtin" in javascript.text
    assert 'mode: scannerMode' in javascript.text
    assert 'scanner_mode === "shelf"' in javascript.text
    assert "Array.from(String(scanResult.raw_value)).length" in javascript.text
    assert "Ingen GTIN-tolkning" in javascript.text
    assert _observation_count(client) == before == 0
    assert client.get("/admin/connectors/hemkop").status_code == 404
    assert client.get("/raw/snapshots").status_code == 404


def test_scanner_test_camera_is_user_started_and_shutdown_is_wired() -> None:
    source = Path("grocery_data/app/static/scanner-test.js").read_text(encoding="utf-8")
    function_start = source.index("async function startScanner()")
    scanner_create = source.index("createBarcodeScanner", function_start)
    click_binding = source.index('startButton.addEventListener("click", startScanner)')

    assert function_start < scanner_create < click_binding
    assert 'cancelButton.addEventListener("click"' in source
    assert 'window.addEventListener("pagehide", () => stopScanner())' in source
    assert 'window.addEventListener("beforeunload", () => stopScanner())' in source
    assert "activeScanner.stop()" in source
    assert "getUserMedia(" not in source


def test_shelf_scanner_diagnostics_never_normalize_or_submit_raw_code() -> None:
    source = Path("grocery_data/app/static/scanner-test.js").read_text(encoding="utf-8")
    shelf_branch_start = source.index('scanResult.scanner_mode === "shelf"')
    shelf_branch_end = source.index('rawValue.textContent =', shelf_branch_start)
    shelf_branch = source[shelf_branch_start:shelf_branch_end]

    assert "scanResult.raw_value" in shelf_branch
    assert "scanResult.format" in shelf_branch
    assert "normalized_gtin" not in shelf_branch
    assert "normalizeGtin" not in shelf_branch
    assert "recordDiagnostic" not in shelf_branch
    assert "fetch(" not in shelf_branch
