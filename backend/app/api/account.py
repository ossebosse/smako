"""Optional established OIDC login. No local passwords or email-based ownership.

Authlib validates authorization state, PKCE, nonce and signed ID-token claims.
Only an opaque keyed owner digest is retained in the signed HttpOnly session.
"""

from __future__ import annotations

import hashlib
import hmac
import os

from app.api.beta_ops import _require_same_origin
from app.config import get_settings
from app.services.beta_observability import pseudonymous_actor
from app.services.personal_store import PersonalConflict, read_state
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(prefix="/api/account", tags=["account"])
ENV_KEYS = ("SMAKO_OIDC_ISSUER_URL", "SMAKO_OIDC_CLIENT_ID", "SMAKO_OIDC_CLIENT_SECRET")


def configured():
    return all(os.environ.get(k, "").strip() for k in ENV_KEYS)


def verified_owner(request):
    owner = request.scope.get("session", {}).get("account_owner")
    if isinstance(owner, str) and len(owner) == 64 and all(c in "0123456789abcdef" for c in owner):
        return owner
    return None


def status(request=None):
    signed_in = bool(request is not None and verified_owner(request))
    return {
        "status": "SIGNED_IN"
        if signed_in
        else "SIGN_IN_AVAILABLE"
        if configured()
        else "DATA_BLOCKED",
        "message": "Privat skafferi på ditt verifierade Smakokonto."
        if signed_in
        else "Gästskafferi i denna webbläsare. Logga in om du vill spara på konto."
        if configured()
        else "Privat gästskafferi i denna webbläsare. Kontoinloggning och kontosynk är inte aktiverade.",
        "operator_steps": "Sätt SMAKO_OIDC_ISSUER_URL, SMAKO_OIDC_CLIENT_ID och SMAKO_OIDC_CLIENT_SECRET privat på servern. Registrera https://beta.smako.nu/api/account/callback hos en etablerad OIDC-leverantör och kör verklig inloggningsacceptans. Ingen tjänst har beställts.",
    }


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
        raise HTTPException(503, status()["operator_steps"])
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
        return RedirectResponse(
            "/personal#account", status_code=303, headers={"Cache-Control": "no-store"}
        )
    except Exception as exc:
        # Neither tokens nor provider exception text may enter logs or UI.
        raise HTTPException(
            401, "Inloggningen kunde inte verifieras. Försök igen från Smako."
        ) from exc


@router.post("/logout")
def logout(request: Request):
    _require_same_origin(request, get_settings())
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
        "message": "Gästskafferi, profil och planer har flyttats till det verifierade kontot.",
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
