"""Public-beta feedback/telemetry endpoints and operator status surfaces."""

from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import re
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from app.config import Settings, get_settings
from app.services.beta_observability import (
    active_price_status,
    admin_aggregates,
    database_ready,
    latest_refresh_status,
    plan_store_ready,
    price_universe_id,
    pseudonymous_actor,
    reload_active_price_universe,
)
from app.services.plan_store import PlanStore
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from grocery_data.app.api.community_evidence import get_community_session
from grocery_data.app.storage.community_evidence import pseudonymous_actor_hash
from grocery_data.app.storage.models import (
    BetaFeedbackModel,
    BetaRequestMetricModel,
    CommunityEvidenceObservationModel,
    CommunityReceiptIngestionModel,
    FrontendErrorModel,
    PrivacyErasureSuppressionModel,
    ProductAnalyticsEventModel,
)

router = APIRouter(tags=["beta operations"])
SessionDep = Annotated[Session, Depends(get_community_session)]

FeedbackCategory = Literal[
    "something_broken",
    "wrong_price",
    "wrong_recipe",
    "missing_store",
    "suggestion",
    "other",
]
AnalyticsEventName = Literal[
    "planner_opened",
    "plan_requested",
    "plan_succeeded",
    "plan_failed",
    "diet_selected",
    "mode_selected",
    "max_stores_selected",
    "membership_enabled",
    "recipe_opened",
    "recipe_replaced",
    "shopping_list_opened",
    "product_report_created",
    "feedback_created",
    "barcode_scan_success",
    "barcode_scan_unknown",
]
_PROPERTY_KEYS = {
    "diet",
    "mode",
    "max_stores",
    "membership_program",
    "latency_ms",
    "total",
    "price_per_portion",
    "outcome",
    "error_code",
    "recipes",
    "servings",
    "actual_stores",
}
_SAFE_CODE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_SECRETISH = re.compile(
    r"(?i)((?:token|password|cookie|authorization)\s*[:=]\s*(?:bearer\s+)?\S+|"
    r"bearer\s+\S+)"
)
_URL_QUERY = re.compile(r"https?://[^\s?#]+(?:\?[^\s#]*)?(?:#[^\s]*)?")
_LOCAL_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_STORED_DIGEST = re.compile(r"^[0-9a-fA-F]{64}$")
_SUPPRESSION_ACTION = "SUPPRESS_ON_RESTORE"


def _settings(request: Request) -> Settings:
    configured = getattr(request.app.state, "beta_settings", None)
    return configured if isinstance(configured, Settings) else get_settings()


def _session_id(request: Request, supplied: str | None) -> str | None:
    return supplied or getattr(request.state, "anonymous_session_id", None)


def _release_fields(request: Request) -> dict[str, str | None]:
    settings = _settings(request)
    return {
        "app_version": settings.app_version,
        "build_id": settings.build_id,
        "price_universe_id": price_universe_id(settings),
    }


class RecipeFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)
    recipe_index: int = Field(ge=0, le=20)
    taste: int | None = Field(default=None, ge=1, le=5)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    portion_size: Literal["small", "right", "large"] | None = None
    actual_minutes: int | None = Field(default=None, ge=1, le=600)

    @model_validator(mode="after")
    def not_empty(self):
        if all(getattr(self, k) is None for k in ("taste", "difficulty", "portion_size", "actual_minutes")):
            raise ValueError("Ange minst ett omdöme eller faktisk tillagningstid.")
        return self


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: FeedbackCategory
    message: str = Field(min_length=1, max_length=4000)
    anonymous_session_id: str | None = Field(default=None, min_length=16, max_length=128)
    page_context: str = Field(min_length=1, max_length=128)
    plan_id: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=320)
    recipe_feedback: RecipeFeedback | None = None

    @field_validator("message", "page_context", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> str:
        return " ".join(str(value).split())

    @field_validator("page_context")
    @classmethod
    def safe_page_context(cls, value: str) -> str:
        if "?" in value or "#" in value or "://" in value:
            raise ValueError("page_context must not contain a URL or query")
        return value

    @field_validator("email")
    @classmethod
    def basic_optional_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if any(character in normalized for character in "\r\n") or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized
        ):
            raise ValueError("email is invalid")
        return normalized


class FeedbackResponse(BaseModel):
    id: str
    created_at: datetime


class AnalyticsEventRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_name: AnalyticsEventName
    anonymous_session_id: str | None = Field(default=None, min_length=16, max_length=128)
    page_context: str | None = Field(default=None, max_length=128)
    plan_id: str | None = Field(default=None, min_length=1, max_length=128)
    properties: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_properties(self) -> AnalyticsEventRequest:
        unknown = set(self.properties) - _PROPERTY_KEYS
        if unknown:
            raise ValueError(f"unsupported analytics properties: {sorted(unknown)}")
        for key, value in self.properties.items():
            if isinstance(value, bool) or value is None:
                raise ValueError(f"analytics property {key} has an invalid value")
            if key in {"max_stores", "recipes", "servings", "actual_stores"}:
                if not isinstance(value, int) or not 1 <= value <= 20:
                    raise ValueError(f"analytics property {key} must be a small integer")
            elif key in {"latency_ms", "total", "price_per_portion"}:
                if not isinstance(value, (int, float)) or not 0 <= float(value) <= 1_000_000:
                    raise ValueError(f"analytics property {key} must be a bounded number")
            elif not isinstance(value, str) or not _SAFE_CODE.fullmatch(value):
                raise ValueError(f"analytics property {key} must be a stable code")
        if self.page_context and any(marker in self.page_context for marker in ("?", "#", "://")):
            raise ValueError("page_context must not contain a URL or query")
        return self


class AcceptedResponse(BaseModel):
    accepted: Literal[True] = True


class PrivacyErasureRequest(BaseModel):
    """Validated only after FastAPI has parsed an opaque JSON object.

    Manual validation at the route boundary prevents Pydantic's normal 422
    response from echoing a rejected session capability back in ``input``.
    """

    model_config = ConfigDict(extra="forbid")

    anonymous_session_id: str

    @field_validator("anonymous_session_id")
    @classmethod
    def high_entropy_local_capability(cls, value: str) -> str:
        if _STORED_DIGEST.fullmatch(value):
            raise ValueError("stored digests are not accepted")
        if not _LOCAL_SESSION_ID.fullmatch(value) or len(set(value)) < 8:
            raise ValueError("invalid local session capability")
        return value


class PrivacyErasureResponse(BaseModel):
    plans_deleted: int = Field(ge=0)
    plan_revisions_deleted: int = Field(ge=0)
    feedback_deleted: int = Field(ge=0)
    analytics_events_deleted: int = Field(ge=0)
    frontend_errors_deleted: int = Field(ge=0)
    request_metrics_deleted: int = Field(ge=0)
    community_observations_unlinked: int = Field(ge=0)
    receipt_ingestions_unlinked: int = Field(ge=0)
    suppression_events_added: int = Field(ge=0)


class FrontendErrorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anonymous_session_id: str | None = Field(default=None, min_length=16, max_length=128)
    route: str = Field(min_length=1, max_length=256)
    error_code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    message: str = Field(min_length=1, max_length=2000)
    plan_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("route")
    @classmethod
    def safe_route(cls, value: str) -> str:
        if not value.startswith("/") or any(marker in value for marker in ("?", "#", "://")):
            raise ValueError("route must be an origin-relative path without query")
        return value


def _sanitize_error_message(value: str) -> str:
    normalized = " ".join(value.split())
    normalized = _SECRETISH.sub("[REDACTED]", normalized)
    normalized = _URL_QUERY.sub("[URL_REDACTED]", normalized)
    return normalized[:500]


def _origin(value: str) -> tuple[str, str] | None:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return parsed.scheme.casefold(), parsed.netloc.casefold()


def _require_same_origin(request: Request, settings: Settings) -> None:
    fetch_site = request.headers.get("Sec-Fetch-Site")
    if fetch_site and fetch_site.casefold() not in {"same-origin", "none"}:
        raise HTTPException(
            status_code=403,
            detail="Raderingen måste startas från den här webbplatsen.",
            headers={"X-Error-Code": "privacy_erasure_cross_origin"},
        )
    supplied = request.headers.get("Origin")
    if not supplied:
        return
    expected = settings.public_base_url or str(request.base_url)
    if _origin(supplied) != _origin(expected):
        raise HTTPException(
            status_code=403,
            detail="Raderingen måste startas från den här webbplatsen.",
            headers={"X-Error-Code": "privacy_erasure_cross_origin"},
        )


def _plan_store(request: Request, settings: Settings) -> PlanStore:
    configured = getattr(request.app.state, "plan_store", None)
    if (
        isinstance(configured, PlanStore)
        and configured.path == settings.plan_store_path.expanduser().resolve()
    ):
        return configured
    return PlanStore(settings.plan_store_path)


def _row_tombstone(settings: Settings, target_kind: str, target_id: str) -> str:
    key = settings.secret_key or "development-only-beta-identity-key"
    return hmac.new(
        key.encode(),
        f"privacy-erasure:v1:{target_kind}:{target_id}".encode(),
        hashlib.sha256,
    ).hexdigest()


def _add_suppression(
    session: Session,
    *,
    target_kind: str,
    target_record_id: str,
) -> bool:
    existing = session.scalar(
        select(PrivacyErasureSuppressionModel.id).where(
            PrivacyErasureSuppressionModel.target_kind == target_kind,
            PrivacyErasureSuppressionModel.target_record_id == target_record_id,
        )
    )
    if existing is not None:
        return False
    session.add(
        PrivacyErasureSuppressionModel(
            target_kind=target_kind,
            target_record_id=target_record_id,
            action=_SUPPRESSION_ACTION,
        )
    )
    return True


def _admin_authorized(
    request: Request,
    x_beta_admin_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = _settings(request).beta_admin_token
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="beta admin API is disabled",
        )
    supplied = x_beta_admin_token
    if not supplied and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.casefold() == "bearer":
            supplied = value
        elif scheme.casefold() == "basic":
            try:
                decoded = base64.b64decode(value, validate=True).decode("utf-8")
                supplied = decoded.partition(":")[2]
            except (ValueError, UnicodeDecodeError):
                supplied = None
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
            headers={"WWW-Authenticate": 'Basic realm="Beta admin"'},
        )


AdminAuth = Depends(_admin_authorized)


def _admin_mutation_authorized(
    request: Request,
    x_beta_admin_token: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = _settings(request).beta_admin_token
    if expected is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="beta admin API is disabled",
        )
    supplied = x_beta_admin_token
    if not supplied and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.casefold() == "bearer":
            supplied = value
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        )


AdminMutationAuth = Depends(_admin_mutation_authorized)


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    settings = _settings(request)
    return {
        "status": "ok",
        "app_version": settings.app_version,
        "build_id": settings.build_id,
    }


@router.get("/ready")
def ready(request: Request, postal_code: str | None = None) -> JSONResponse:
    settings = _settings(request)
    if postal_code is not None:
        from app.services.municipal_runtime import settings_for_city
        from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
        prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(postal_code, {})
        if prepared is None:
            return JSONResponse(status_code=503, content={"status": "not_ready", "price_universe": {"active": False, "status": "unavailable"}})
        settings = settings_for_city(settings, prepared.universe.key.scope_id.removeprefix("city:"))
    factory = getattr(request.app.state, "community_session_factory", None)
    db_ok, db_status = database_ready(factory)
    plans_ok, plan_status = plan_store_ready(settings.plan_store_path)
    prices = active_price_status(settings)
    prices_ok = (not settings.price_universe_required) or (
        bool(prices.get("active"))
        and prices.get("status") not in {"stale", "broken"}
        and prices.get("required_contexts_usable", True)
    )
    is_ready = db_ok and plans_ok and prices_ok
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content=json.loads(
            json.dumps(
                {
                    "status": "ready" if is_ready else "not_ready",
                    "database": db_status,
                    "plan_store": plan_status,
                    "price_universe": prices,
                    "app_version": settings.app_version,
                    "build_id": settings.build_id,
                    "features": {"complete_recipes_enabled": settings.complete_recipes_enabled},
                },
                default=str,
            )
        ),
    )


@router.post("/api/feedback", response_model=FeedbackResponse, status_code=201)
def create_feedback(
    payload: FeedbackRequest,
    request: Request,
    session: SessionDep,
) -> FeedbackResponse:
    settings = _settings(request)
    message = payload.message
    if payload.recipe_feedback is not None:
        from app.api.plan import _plan_actor_hash, _store
        from app.services.plan_store import (
            PlanNotFoundError,
            PlanOwnerMismatchError,
            PlanReadOnlyError,
        )
        if not payload.plan_id:
            raise HTTPException(422, "Receptåterkoppling kräver en sparad plan.")
        feedback = payload.recipe_feedback
        try:
            saved = _store(request).get_owned(payload.plan_id, owner_actor_hash=_plan_actor_hash(request, settings), revision=feedback.revision)
        except (PlanNotFoundError, PlanOwnerMismatchError, PlanReadOnlyError) as exc:
            raise HTTPException(404, "Planrevisionen finns inte i din session.") from exc
        if feedback.recipe_index >= len(saved.plan.recipes):
            raise HTTPException(422, "Receptet saknas i planrevisionen.")
        recipe = saved.plan.recipes[feedback.recipe_index]
        from app.services.recipe_candidate_validator import recipe_id
        design = getattr(recipe, "design", None)
        bound = {**feedback.model_dump(), "recipe_hash": recipe_id(recipe), "name": recipe.name,
                 "design": {k: getattr(design, k) for k in ("base_id", "version", "variant_id", "content_sha256")} if design else None}
        # Existing feedback persistence, privacy export/erasure and moderation
        # remain authoritative. No recipe or another person's plan is modified.
        message = json.dumps({"recipe_feedback": bound, "message": message}, ensure_ascii=False)
    row = BetaFeedbackModel(
        actor_hash=pseudonymous_actor(_session_id(request, payload.anonymous_session_id), settings),
        category=payload.category,
        message=message,
        page_context=payload.page_context,
        plan_id=payload.plan_id,
        contact_email=payload.email,
        **_release_fields(request),
    )
    session.add(row)
    session.flush()
    session.add(
        ProductAnalyticsEventModel(
            actor_hash=row.actor_hash,
            event_name="feedback_created",
            page_context=payload.page_context,
            plan_id=payload.plan_id,
            properties={},
            **_release_fields(request),
        )
    )
    session.commit()
    return FeedbackResponse(id=row.id, created_at=row.created_at)


@router.post(
    "/api/analytics/events",
    response_model=AcceptedResponse,
    status_code=202,
)
def create_analytics_event(
    payload: AnalyticsEventRequest,
    request: Request,
    session: SessionDep,
) -> AcceptedResponse:
    settings = _settings(request)
    session.add(
        ProductAnalyticsEventModel(
            actor_hash=pseudonymous_actor(
                _session_id(request, payload.anonymous_session_id), settings
            ),
            event_name=payload.event_name,
            page_context=payload.page_context,
            plan_id=payload.plan_id,
            properties=payload.properties,
            **_release_fields(request),
        )
    )
    session.commit()
    return AcceptedResponse()


@router.post(
    "/api/frontend-errors",
    response_model=AcceptedResponse,
    status_code=202,
)
def create_frontend_error(
    payload: FrontendErrorRequest,
    request: Request,
    session: SessionDep,
) -> AcceptedResponse:
    settings = _settings(request)
    session.add(
        FrontendErrorModel(
            actor_hash=pseudonymous_actor(
                _session_id(request, payload.anonymous_session_id), settings
            ),
            route=payload.route,
            error_code=payload.error_code,
            message=_sanitize_error_message(payload.message),
            plan_id=payload.plan_id,
            **_release_fields(request),
        )
    )
    session.commit()
    return AcceptedResponse()


@router.post(
    "/api/privacy/erase",
    response_model=PrivacyErasureResponse,
)
def erase_anonymous_beta_data(
    payload: dict[str, object],
    request: Request,
    response: Response,
    session: SessionDep,
) -> PrivacyErasureResponse:
    """Erase one browser's beta data without accepting persisted digests.

    The caller's local capability identifies feedback/community rows. Saved
    plans use the independent HttpOnly request session established by the
    middleware. Authoritative prices and evidence facts are never touched.
    """

    settings = _settings(request)
    _require_same_origin(request, settings)
    try:
        validated = PrivacyErasureRequest.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Den lokala anonyma sessionen är ogiltig.",
            headers={"X-Error-Code": "privacy_erasure_invalid_session"},
        ) from exc

    local_session_id = validated.anonymous_session_id
    beta_actor_hash = pseudonymous_actor(local_session_id, settings)
    community_actor_hash = pseudonymous_actor_hash(local_session_id)
    from app.api.plan import _plan_actor_hash

    owner_actor_hash = _plan_actor_hash(request, settings)
    if beta_actor_hash is None or owner_actor_hash is None:
        raise HTTPException(
            status_code=503,
            detail="Den anonyma sessionen kunde inte behandlas.",
            headers={"X-Error-Code": "privacy_erasure_session_unavailable"},
        )

    store = _plan_store(request, settings)
    owned_plan_ids = store.owned_plan_ids(owner_actor_hash=owner_actor_hash)

    feedback_rows = list(
        session.scalars(
            select(BetaFeedbackModel).where(or_(
                BetaFeedbackModel.actor_hash == beta_actor_hash,
                # Version-bound recipe feedback can predate the tab's local
                # capability or use the owned-session fallback. These plan IDs
                # come from verified storage ownership, never the erase payload.
                BetaFeedbackModel.plan_id.in_(owned_plan_ids),
            ))
        )
    )
    analytics_rows = list(
        session.scalars(
            select(ProductAnalyticsEventModel).where(
                ProductAnalyticsEventModel.actor_hash == beta_actor_hash
            )
        )
    )
    frontend_rows = list(
        session.scalars(
            select(FrontendErrorModel).where(FrontendErrorModel.actor_hash == beta_actor_hash)
        )
    )
    metric_rows = (
        list(
            session.scalars(
                select(BetaRequestMetricModel).where(
                    BetaRequestMetricModel.plan_id.in_(owned_plan_ids)
                )
            )
        )
        if owned_plan_ids
        else []
    )
    community_rows = list(
        session.scalars(
            select(CommunityEvidenceObservationModel).where(
                CommunityEvidenceObservationModel.actor_hash == community_actor_hash
            )
        )
    )
    receipt_rows = list(
        session.scalars(
            select(CommunityReceiptIngestionModel).where(
                CommunityReceiptIngestionModel.actor_hash == community_actor_hash
            )
        )
    )

    suppression_events_added = 0
    for target_kind, rows in (
        ("beta_feedback", feedback_rows),
        ("analytics_event", analytics_rows),
        ("frontend_error", frontend_rows),
        ("request_metric", metric_rows),
        ("community_observation", community_rows),
        ("receipt_ingestion", receipt_rows),
    ):
        for row in rows:
            suppression_events_added += int(
                _add_suppression(
                    session,
                    target_kind=target_kind,
                    target_record_id=row.id,
                )
            )
    for plan_id in owned_plan_ids:
        suppression_events_added += int(
            _add_suppression(
                session,
                target_kind="saved_plan",
                target_record_id=plan_id,
            )
        )

    from app.services.personal_store import PersonalStore

    private_state_id = PersonalStore(store).read(owner_actor_hash)["id"]
    if private_state_id:
        suppression_events_added += int(
            _add_suppression(
                session, target_kind="private_state", target_record_id=private_state_id
            )
        )

    for row in community_rows:
        # Evidence facts remain append-only. This narrowly scoped Core update
        # changes only the identity link and deliberately bypasses the ORM's
        # general-purpose fact-mutation guard.
        session.execute(
            update(CommunityEvidenceObservationModel)
            .where(CommunityEvidenceObservationModel.id == row.id)
            .values(
                actor_hash=_row_tombstone(
                    settings,
                    "community_observation",
                    row.id,
                )
            )
            .execution_options(synchronize_session=False)
        )
    for row in receipt_rows:
        session.execute(
            update(CommunityReceiptIngestionModel)
            .where(CommunityReceiptIngestionModel.id == row.id)
            .values(actor_hash=_row_tombstone(settings, "receipt_ingestion", row.id))
            .execution_options(synchronize_session=False)
        )
    for rows in (feedback_rows, analytics_rows, frontend_rows, metric_rows):
        for row in rows:
            session.delete(row)
    session.commit()

    erased_plans = store.erase_owned(owner_actor_hash=owner_actor_hash)
    extra_plan_ids = tuple(set(erased_plans.plan_ids) - set(owned_plan_ids))
    extra_metrics_deleted = 0
    if extra_plan_ids:
        extra_metric_rows = list(
            session.scalars(
                select(BetaRequestMetricModel).where(
                    BetaRequestMetricModel.plan_id.in_(extra_plan_ids)
                )
            )
        )
        extra_metrics_deleted = len(extra_metric_rows)
        for row in extra_metric_rows:
            suppression_events_added += int(
                _add_suppression(
                    session,
                    target_kind="request_metric",
                    target_record_id=row.id,
                )
            )
            session.delete(row)
        for plan_id in extra_plan_ids:
            suppression_events_added += int(
                _add_suppression(
                    session,
                    target_kind="saved_plan",
                    target_record_id=plan_id,
                )
            )
        session.commit()

    request.state.suppress_beta_session_cookie = True
    if "session" in request.scope:
        request.session.clear()
    response.delete_cookie(
        "beta_session",
        path="/",
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return PrivacyErasureResponse(
        plans_deleted=erased_plans.plans_deleted,
        plan_revisions_deleted=erased_plans.revisions_deleted,
        feedback_deleted=len(feedback_rows),
        analytics_events_deleted=len(analytics_rows),
        frontend_errors_deleted=len(frontend_rows),
        request_metrics_deleted=len(metric_rows) + extra_metrics_deleted,
        community_observations_unlinked=len(community_rows),
        receipt_ingestions_unlinked=len(receipt_rows),
        suppression_events_added=suppression_events_added,
    )


def _admin_payload(session: Session, settings: Settings) -> dict[str, object]:
    return {
        "app_version": settings.app_version,
        "build_id": settings.build_id,
        "environment": settings.app_env,
        "price_universe": active_price_status(settings),
        "refresh": latest_refresh_status(settings),
        "metrics": admin_aggregates(session, settings),
    }


@router.get("/api/admin/status", dependencies=[AdminAuth])
def admin_status(
    request: Request,
    response: Response,
    session: SessionDep,
) -> dict[str, object]:
    response.headers["Cache-Control"] = "no-store"
    return _admin_payload(session, _settings(request))


@router.get("/admin", response_class=HTMLResponse, dependencies=[AdminAuth])
def admin_page(request: Request, session: SessionDep) -> HTMLResponse:
    payload = json.dumps(
        _admin_payload(session, _settings(request)),
        indent=2,
        default=str,
        ensure_ascii=False,
    )
    return HTMLResponse(
        "<!doctype html><html lang='sv'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta http-equiv='refresh' content='30'><title>Beta admin</title>"
        "<style>body{font:16px system-ui;max-width:78rem;margin:2rem auto;padding:0 1rem;"
        "background:#101711;color:#ecf7ed}pre{white-space:pre-wrap;background:#17221a;"
        "padding:1rem;border-radius:.7rem}</style></head><body>"
        "<h1>Beta admin</h1><p>Automatisk uppdatering var 30:e sekund.</p><pre>"
        f"{html.escape(payload)}</pre></body></html>",
        headers={"Cache-Control": "no-store"},
    )


@router.post(
    "/api/admin/reload-price-universe",
    dependencies=[AdminMutationAuth],
)
async def reload_price_universe(
    request: Request,
    response: Response,
    city: str | None = None,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    try:
        from app.services.municipal_runtime import settings_for_city
        settings = _settings(request)
        if city is not None:
            settings = settings_for_city(settings, city)
        return await reload_active_price_universe(request.app, settings)
    except (OSError, RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="PriceUniverse reload failed; current runtime was retained",
            headers={
                "X-Error-Code": "price_universe_reload_failed",
                "Cache-Control": "no-store",
            },
        ) from exc


__all__ = [
    "AcceptedResponse",
    "AnalyticsEventRequest",
    "FeedbackRequest",
    "FeedbackResponse",
    "FrontendErrorRequest",
    "PrivacyErasureRequest",
    "PrivacyErasureResponse",
    "router",
]
