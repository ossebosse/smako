from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import inspect, select

from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.main import create_app
from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import BarcodeScanDiagnosticModel
from grocery_data.tests.test_physical_check_api import _client


def test_scanner_diagnostics_store_only_bounded_non_identifying_telemetry() -> None:
    client, factory = _client()
    events = (
        {
            "scanner_provider": "zxing",
            "outcome": "success",
            "barcode_format": "EAN_13",
            "duration_ms": 800,
        },
        {
            "scanner_provider": "zxing",
            "outcome": "no_match",
            "barcode_format": "EAN_8",
            "duration_ms": 1200,
        },
        {
            "scanner_provider": "native_barcode_detector",
            "outcome": "failure",
            "duration_ms": 2500,
            "failure_reason": "no_barcode_detected",
        },
        {
            "scanner_provider": "manual",
            "outcome": "manual_fallback",
        },
    )

    for event in events:
        response = client.post("/physical-check/scanner-diagnostics", json=event)
        assert response.status_code == 201, response.text
        assert response.json()["barcode_value_recorded"] is False
        assert response.json()["camera_media_recorded"] is False
        assert response.json()["identifying_data_recorded"] is False

    metrics = client.get("/physical-check/scanner-diagnostics/metrics")
    assert metrics.status_code == 200
    assert metrics.json() == {
        "scan_attempts": 3,
        "successful_scans": 2,
        "failed_scans": 1,
        "manual_fallbacks": 1,
        "no_matches": 1,
        "median_scan_time_ms": 1000.0,
        "events": 4,
        "by_provider": {
            "zxing": {
                "events": 2,
                "successful_scans": 2,
                "failed_scans": 0,
                "no_matches": 1,
            },
            "native_barcode_detector": {
                "events": 1,
                "successful_scans": 0,
                "failed_scans": 1,
                "no_matches": 0,
            },
            "manual": {
                "events": 1,
                "successful_scans": 0,
                "failed_scans": 0,
                "no_matches": 0,
            },
        },
        "barcode_values_recorded": False,
        "camera_media_recorded": False,
        "identifying_data_recorded": False,
    }
    with factory() as session:
        rows = tuple(session.scalars(select(BarcodeScanDiagnosticModel)))
    assert len(rows) == 4
    columns = {column.key for column in inspect(BarcodeScanDiagnosticModel).columns}
    assert columns.isdisjoint(
        {
            "raw_value",
            "normalized_gtin",
            "gtin",
            "physical_store_id",
            "validation_session_id",
            "ip_address",
            "user_agent",
            "camera_frame",
            "video",
            "photo",
        }
    )


def test_scanner_diagnostic_schema_rejects_barcode_and_arbitrary_error_data() -> None:
    client, factory = _client()
    leaked_barcode = client.post(
        "/physical-check/scanner-diagnostics",
        json={
            "scanner_provider": "zxing",
            "outcome": "success",
            "barcode_format": "EAN_13",
            "duration_ms": 500,
            "raw_value": "7310865004703",
        },
    )
    arbitrary_error = client.post(
        "/physical-check/scanner-diagnostics",
        json={
            "scanner_provider": "zxing",
            "outcome": "failure",
            "failure_reason": "stack trace with local path",
        },
    )
    inconsistent_manual = client.post(
        "/physical-check/scanner-diagnostics",
        json={"scanner_provider": "manual", "outcome": "success"},
    )

    assert leaked_barcode.status_code == 422
    assert arbitrary_error.status_code == 422
    assert inconsistent_manual.status_code == 422
    with factory() as session:
        assert tuple(session.scalars(select(BarcodeScanDiagnosticModel))) == ()


def test_scanner_diagnostics_are_inside_field_auth_and_csrf_boundary() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    settings = GroceryDataSettings(
        database_url="sqlite+pysqlite:///:memory:",
        raw_snapshot_root=Path("unused-raw"),
        user_agent="scanner-diagnostics-test",
        field_mode_enabled=True,
        physical_check_access_token="scanner-test-access-token-with-32-bytes-minimum",
        field_public_origin="https://field.example",
    )
    client = TestClient(
        create_app(create_session_factory(engine), settings=settings),
        base_url="https://field.example",
    )

    assert client.get("/physical-check/scanner-diagnostics/metrics").status_code == 401
    assert (
        client.post(
            "/physical-check/scanner-diagnostics",
            json={
                "scanner_provider": "zxing",
                "outcome": "success",
                "barcode_format": "EAN_13",
                "duration_ms": 500,
            },
        ).status_code
        == 401
    )
