"""Actual Authlib state/nonce/PKCE/signature flow against an offline test IdP."""

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest
from app.api import account
from app.config import Settings
from authlib.integrations.httpx_client._compat import httpx2 as httpx
from authlib.jose import JsonWebKey, jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def oidc(monkeypatch, tmp_path):
    issuer = "https://oidc.example.test"
    for key, value in zip(
        account.ENV_KEYS, [issuer, "offline-client", "offline-secret"], strict=True
    ):
        monkeypatch.setenv(key, value)
    settings = Settings(
        plan_store_path=tmp_path / "oidc-plans.sqlite",
        public_base_url="https://beta.smako.nu", secret_key="offline-test-signing-key-" * 3
    )
    monkeypatch.setattr(account, "get_settings", lambda: settings)
    from app.api import plan
    monkeypatch.setattr(plan, "get_settings", lambda: settings)
    app = FastAPI()
    account.install_account(app)
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True, options={"kid": "offline-key"})
    state = {"sub": "account-one", "nonce": None, "challenge": None, "token_requests": 0}

    def transport(request):
        if request.url.path.endswith("openid-configuration"):
            return httpx.Response(
                200,
                json={
                    "issuer": issuer,
                    "authorization_endpoint": issuer + "/authorize",
                    "token_endpoint": issuer + "/token",
                    "jwks_uri": issuer + "/jwks",
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "response_types_supported": ["code"],
                    "subject_types_supported": ["public"],
                    "token_endpoint_auth_methods_supported": ["client_secret_basic"],
                },
            )
        if request.url.path == "/jwks":
            return httpx.Response(200, json={"keys": [key.as_dict(is_private=False)]})
        assert request.url.path == "/token"
        form = parse_qs(request.content.decode())
        verifier = form["code_verifier"][0]
        assert (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
            == state["challenge"]
        )
        state["token_requests"] += 1
        claims = {
            "iss": issuer,
            "sub": state["sub"],
            "aud": "offline-client",
            "iat": int(time.time()),
            "exp": int(time.time()) + 300,
            "nonce": state["nonce"],
            "email": "same@example.test",
        }
        signed = jwt.encode({"alg": "RS256", "kid": "offline-key"}, claims, key).decode()
        return httpx.Response(
            200,
            json={
                "access_token": "offline-unused-token",
                "token_type": "Bearer",
                "id_token": signed,
            },
        )

    app.state.smako_oidc.client_kwargs["transport"] = httpx.MockTransport(transport)
    yield app, state


def begin(client, state):
    response = client.get(
        "/api/account/login", follow_redirects=False, headers={"Origin": "https://beta.smako.nu"}
    )
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["scope"] == ["openid"] and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://beta.smako.nu/api/account/callback"]
    state.update(nonce=query["nonce"][0], challenge=query["code_challenge"][0])
    return query["state"][0]


def finish(client, value):
    return client.get(
        "/api/account/callback",
        params={"code": "offline-code", "state": value},
        follow_redirects=False,
    )


def test_oidc_verified_owner_logout_and_distinct_subjects_despite_equal_email(oidc):
    app, state = oidc
    with TestClient(app, base_url="https://beta.smako.nu") as client:
        value = begin(client, state)
        response = finish(client, value)
        assert response.status_code == 303
        cookie = response.headers["set-cookie"]
        assert all(
            flag in cookie.lower()
            for flag in ("httponly", "secure", "samesite=lax", "max-age=86400")
        )
        assert client.get("/api/account/status").json()["status"] == "SIGNED_IN"
        first = json.loads(base64.b64decode(client.cookies.get("smako_account").split(".")[0]))["account_owner"]
        assert (
            client.post(
                "/api/account/logout", headers={"Origin": "https://beta.smako.nu"}
            ).status_code
            == 200
        )
        assert client.get("/api/account/status").json()["status"] == "SIGN_IN_AVAILABLE"
        state["sub"] = "account-two"
        assert finish(client, begin(client, state)).status_code == 303
        second = json.loads(base64.b64decode(client.cookies.get("smako_account").split(".")[0]))["account_owner"]
        assert second != first
        assert state["token_requests"] == 2


@pytest.mark.parametrize("failure", ["state", "nonce"])
def test_oidc_rejects_invalid_state_or_nonce_without_authenticated_access(oidc, failure):
    app, state = oidc
    with TestClient(app, base_url="https://beta.smako.nu") as client:
        value = begin(client, state)
        if failure == "state":
            value = "not-the-saved-state"
        else:
            state["nonce"] = "not-the-saved-nonce"
        response = finish(client, value)
        assert response.status_code == 401
        assert "offline-unused-token" not in response.text
        assert client.get("/api/account/status").json()["status"] == "SIGN_IN_AVAILABLE"
