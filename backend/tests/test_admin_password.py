"""Browser-admin password login, kept in sync with the deployed beta runtime."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest
from app.config import Settings
from app.services.admin_password import hash_password, valid_password_hash, verify_password
from fastapi.testclient import TestClient
from tests.test_beta_release_observability import _application


def _basic(username: str, password: str) -> dict[str, str]:
    encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {encoded}"}


def test_hash_round_trip_and_format() -> None:
    encoded = hash_password("rätt lösenord")
    assert valid_password_hash(encoded)
    assert verify_password("rätt lösenord", encoded)
    assert not verify_password("fel", encoded)
    assert not verify_password("x" * 1025, encoded)
    assert not verify_password("rätt lösenord", "pbkdf2_sha256:1:00:00")
    assert hash_password("rätt lösenord") != encoded


def test_settings_reject_malformed_password_hash() -> None:
    with pytest.raises(ValueError, match="BETA_ADMIN_PASSWORD_HASH"):
        Settings(price_universe_required=False, beta_admin_password_hash="plaintext")


def test_password_hash_replaces_token_for_browser_login(tmp_path: Path) -> None:
    token = "a" * 40
    application, _, _ = _application(tmp_path, beta_admin_password_hash=hash_password("hemligt"))
    client = TestClient(application)

    assert client.get("/api/admin/status", headers=_basic("admin", "hemligt")).status_code == 200
    assert client.get("/api/admin/status", headers=_basic("admin", "fel")).status_code == 401
    assert client.get("/api/admin/status", headers=_basic("annan", "hemligt")).status_code == 401
    # With a password hash configured, the operational token is no longer a browser password.
    assert client.get("/api/admin/status", headers=_basic("admin", token)).status_code == 401
    bearer = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/admin/status", headers=bearer).status_code == 200

    page = client.get("/admin", headers=_basic("admin", "hemligt"))
    assert page.status_code == 200
    assert "Drift & priser" in page.text
    assert page.headers["Cache-Control"] == "no-store"


def test_admin_stores_rejects_unknown_municipality(tmp_path: Path) -> None:
    application, _, _ = _application(tmp_path)
    client = TestClient(application)
    response = client.get(
        "/api/admin/stores",
        params={"city": "Stockholm"},
        headers={"Authorization": "Bearer " + "a" * 40},
    )
    assert response.status_code == 422
