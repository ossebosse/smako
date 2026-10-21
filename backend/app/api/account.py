"""Smako membership with local credentials and optional established OIDC login.

Authlib validates authorization state, PKCE, nonce and signed ID-token claims.
Only an opaque keyed owner digest is retained in the signed HttpOnly session.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from typing import Annotated, Any

from app.api.beta_ops import _require_same_origin
from app.config import get_settings
from app.services.beta_observability import pseudonymous_actor
from app.services.member_accounts import (
    COOKIE,
    SESSION_SECONDS,
    AccountExists,
    AuthThrottled,
    MemberAccounts,
)
from app.services.personal_store import PersonalConflict, read_state
from fastapi import APIRouter, Body, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/account", tags=["account"])
ENV_KEYS = ("SMAKO_OIDC_ISSUER_URL", "SMAKO_OIDC_CLIENT_ID", "SMAKO_OIDC_CLIENT_SECRET")


def configured():
    return all(os.environ.get(k, "").strip() for k in ENV_KEYS)


def verified_owner(request):
    token = getattr(request, "cookies", {}).get(COOKIE)
    if token:
        # Cache only within this HTTP request; a later request rechecks revocation.
        if not hasattr(request.state, "member_owner"):
            request.state.member_owner = member_store(request).owner(token)
        if request.state.member_owner:
            return request.state.member_owner
    owner = request.scope.get("session", {}).get("account_owner")
    if isinstance(owner, str) and len(owner) == 64 and all(c in "0123456789abcdef" for c in owner):
        return owner
    return None


def status(request=None):
    signed_in = bool(request is not None and verified_owner(request))
    return {
        "status": "SIGNED_IN"
        if signed_in
        else "SIGN_IN_AVAILABLE",
        "message": "Du är medlem. Ditt skafferi sparas på ditt Smakokonto."
        if signed_in
        else "Du är gäst: högst 3 recept per meny och 2 portioner per recept. Skapa konto för att spara ditt skafferi och planera mer.",
        "membership": "member" if signed_in else "guest",
        "guest_limits": {"recipes": 3, "servings": 2},
        "registration_available": True,
        "oidc_available": configured(),
    }


def member_store(request):
    from app.api.plan import _store
    return MemberAccounts(_store(request))


def credentials(payload, request):
    _require_same_origin(request, get_settings())
    if not isinstance(payload, dict):
        raise HTTPException(422, "Ange e-postadress och lösenord.")
    email, password = payload.get("email"), payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        raise HTTPException(422, "Ange e-postadress och lösenord.")
    email = email.strip().casefold()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(422, "Ange en giltig e-postadress.")
    if not 12 <= len(password) <= 128:
        raise HTTPException(422, "Lösenordet ska vara mellan 12 och 128 tecken.")
    store = member_store(request)
    try:
        store.throttle(email, request.client.host if request.client else "unknown")
    except AuthThrottled as exc:
        raise HTTPException(429, "För många försök. Försök igen om 15 minuter.",
                            headers={"Retry-After": "900"}) from exc
    return store, email, password


def signed_in_response(request, response, store, owner, *, expected_password_hash=None):
    token = store.create_session(owner, expected_password_hash=expected_password_hash)
    if token is None:
        raise HTTPException(401, "Lösenordet har ändrats. Logga in igen.")
    store.logout(request.cookies.get(COOKIE))
    if "session" in request.scope:
        request.session.clear()
    response.set_cookie(COOKIE, token, max_age=SESSION_SECONDS,
                        httponly=True, secure=(get_settings().public_base_url or "").startswith("https://")
                        or request.url.scheme == "https", samesite="lax", path="/")
    response.headers["Cache-Control"] = "private, no-store"
    return {"status": "SIGNED_IN"}


@router.post("/register", status_code=201)
def register(payload: Annotated[Any, Body()], request: Request, response: Response):
    store, email, password = credentials(payload, request)
    try:
        owner, recovery = store.register(email, password)
    except AccountExists as exc:
        raise HTTPException(409, "Kontot kunde inte skapas. Prova att logga in eller återställa kontot.") from exc
    return {**signed_in_response(request, response, store, owner), "recovery_code": recovery}


@router.post("/login")
def password_login(payload: Annotated[Any, Body()], request: Request, response: Response):
    store, email, password = credentials(payload, request)
    identity = store.authenticate(email, password)
    if not identity:
        raise HTTPException(401, "E-postadressen eller lösenordet är fel.")
    owner, encoded = identity
    return signed_in_response(request, response, store, owner, expected_password_hash=encoded)


@router.post("/recover")
def recover(payload: Annotated[Any, Body()], request: Request, response: Response):
    store, email, password = credentials(payload, request)
    code = payload.get("recovery_code")
    if not isinstance(code, str) or not 1 <= len(code) <= 128:
        raise HTTPException(422, "Ange din återställningskod.")
    replacement = store.recover(email, code.strip(), password)
    if not replacement:
        raise HTTPException(401, "E-postadressen eller återställningskoden är fel.")
    response.headers["Cache-Control"] = "private, no-store"
    return {"status": "PASSWORD_RESET", "recovery_code": replacement}


def install_account(app):
    app.include_router(router)
    if not configured():
        return
    from authlib.integrations.starlette_client import OAuth
    from starlette.middleware.sessions import SessionMiddleware

    settings = get_settings()
    issuer = os.environ["SMAKO_OIDC_ISSUER_URL"].rstrip("/")
    if not issuer.startswith("https://") or not settings.public_base_url.startswith("https://"):
        raise RuntimeError("OIDC requires configured HTTPS issuer and public origin")
    if len(settings.secret_key) < 32:
        raise RuntimeError("OIDC requires a production session signing key")
    oauth = OAuth()
    oauth.register(
        "smako",
        client_id=os.environ["SMAKO_OIDC_CLIENT_ID"],
        client_secret=os.environ["SMAKO_OIDC_CLIENT_SECRET"],
        server_metadata_url=f"{issuer}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid", "code_challenge_method": "S256"},
    )
    app.state.smako_oidc = oauth.create_client("smako")
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="smako_account",
        https_only=True,
        same_site="lax",
        max_age=86400,
    )


@router.get("/status")
def account_status(request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    return status(request)


@router.get("/login")
async def login(request: Request):
    if not configured() or not hasattr(request.app.state, "smako_oidc"):
        raise HTTPException(503, "Extern inloggning är inte aktiverad. Logga in med e-post och lösenord.")
    settings = get_settings()
    _require_same_origin(request, settings)
    return await request.app.state.smako_oidc.authorize_redirect(
        request, settings.public_base_url.rstrip("/") + "/api/account/callback"
    )


@router.get("/callback")
async def callback(request: Request):
    client = getattr(request.app.state, "smako_oidc", None)
    if client is None:
        raise HTTPException(503, "Kontoinloggning är inte konfigurerad.")
    try:
        token = await client.authorize_access_token(request)
        # Authlib populates this only after validating the ID token and nonce.
        claims = token.get("userinfo")
        if (
            not claims
            or claims.get("iss", "").rstrip("/") != os.environ["SMAKO_OIDC_ISSUER_URL"].rstrip("/")
            or not claims.get("sub")
        ):
            raise ValueError("unverified OIDC owner")
        material = f"smako-account-v1:{claims['iss']}:{claims['sub']}".encode()
        owner = hmac.new(get_settings().secret_key.encode(), material, hashlib.sha256).hexdigest()
        request.session.clear()
        request.session["account_owner"] = owner
        member_store(request).logout(request.cookies.get(COOKIE))
        response = RedirectResponse(
            "/personal#account", status_code=303, headers={"Cache-Control": "no-store"}
        )
        response.delete_cookie(COOKIE, path="/")
        return response
    except Exception as exc:
        # Neither tokens nor provider exception text may enter logs or UI.
        raise HTTPException(
            401, "Inloggningen kunde inte verifieras. Försök igen från Smako."
        ) from exc


@router.post("/logout")
def logout(request: Request, response: Response):
    _require_same_origin(request, get_settings())
    member_store(request).logout(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")
    response.headers["Cache-Control"] = "private, no-store"
    if "session" in request.scope:
        request.session.clear()
    return {"status": "SIGNED_OUT"}


class MigrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    guest_revision: int = Field(ge=0)
    account_revision: int = Field(ge=0)
    confirm_move_to_verified_account: bool


@router.post("/migrate-guest")
def migrate_guest(payload: MigrationRequest, request: Request):
    from app.api.plan import _store

    settings = get_settings()
    _require_same_origin(request, settings)
    owner = verified_owner(request)
    guest = pseudonymous_actor(getattr(request.state, "anonymous_session_id", None), settings)
    if not owner or not guest or not payload.confirm_move_to_verified_account:
        raise HTTPException(
            403, "Verifierad inloggning, gästägarsession och uttrycklig flytt krävs."
        )
    store = _store(request)
    with store._connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        source, target = read_state(connection, guest), read_state(connection, owner)
        if (
            source["revision"] != payload.guest_revision
            or target["revision"] != payload.account_revision
        ):
            raise PersonalConflict("Skafferiet ändrades. Läs om före kontoflytt.")
        if target["id"]:
            raise PersonalConflict(
                "Kontot har redan personliga data. Automatisk sammanslagning stöds inte; gästskafferiet är bevarat."
            )
        if not source["id"]:
            raise PersonalConflict("Det finns inget gästskafferi att flytta.")
        connection.execute(
            "UPDATE personal_private_state SET owner_actor_hash = ?, revision = revision + 1 WHERE id = ?",
            (owner, source["id"]),
        )
        connection.execute(
            "UPDATE consumer_plan_revisions SET owner_actor_hash = ? WHERE owner_actor_hash = ?",
            (owner, guest),
        )
    return {
        "status": "MOVED",
        "message": "Gästskafferi, profil och planer har flyttats till ditt konto.",
    }


@router.get("/guest-migration-preview")
def migration_preview(request: Request, response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    from app.api.plan import _store

    if not verified_owner(request):
        raise HTTPException(403, "Verifierad inloggning krävs.")
    guest = pseudonymous_actor(getattr(request.state, "anonymous_session_id", None), get_settings())
    with _store(request)._connect() as connection:
        source = read_state(connection, guest)
        target = read_state(connection, verified_owner(request))
    return {
        "guest_revision": source["revision"],
        "account_revision": target["revision"],
        "guest_items": len(source["items"]),
        "guest_profile": source["profile"] is not None,
        "can_move": bool(source["id"] and not target["id"]),
    }
