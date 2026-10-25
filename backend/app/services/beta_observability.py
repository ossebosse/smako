"""Privacy-safe operational primitives for the small public beta.

The module deliberately stores no request body, IP address, cookie, access
token or raw browser stack. It is infrastructure telemetry, not a second
product-data system.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import re
import sqlite3
from collections import OrderedDict, deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from statistics import median
from threading import BoundedSemaphore, Lock
from time import monotonic, perf_counter
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.config import Settings
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
from fastapi import Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from grocery_data.app.storage.models import (
    BetaFeedbackModel,
    BetaRequestMetricModel,
    CommunityEvidenceObservationModel,
    ConnectorHealthModel,
    FrontendErrorModel,
    ProductAnalyticsEventModel,
)

LOGGER = logging.getLogger("beta.request")
_ADMIN_RECENT_ROW_LIMIT = 20
_REFRESH_REPORT_SCAN_LIMIT = 50
_METRIC_PENDING_LIMIT = 256
# Telemetry is deliberately best-effort. One background writer prevents a
# locked grocery database from blocking the ASGI loop; the semaphore bounds
# queued work, after which metrics are dropped with a privacy-safe log event.
_METRIC_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="beta-metrics",
)
_METRIC_SLOTS = BoundedSemaphore(_METRIC_PENDING_LIMIT)
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_SESSION_ID = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
_PLAN_PATH = re.compile(r"/plans/([A-Za-z0-9_-]{1,128})(?:/|$)")


def _scope_id(settings: Settings) -> str:
    city = " ".join(settings.price_universe_city.casefold().split())
    return f"city:{city}"


def active_price_status(settings: Settings, *, now: datetime | None = None) -> dict[str, Any]:
    """Return sanitized in-memory universe status without provider work."""

    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active(_scope_id(settings))
    if prepared is None:
        return {"active": False, "status": "unavailable"}
    evaluated_at = now or datetime.now(UTC)
    usable, _stale, ages = prepared._context_partition(
        now=evaluated_at, stale_age_hours=settings.max_price_age_hours
    )
    from app.services.municipal_runtime import required_contexts
    missing = sorted(required_contexts(settings, prepared) - set(usable))
    status = prepared.status(
        now=evaluated_at,
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    return {
        "active": True,
        "required_contexts_usable": not missing,
        "missing_required_context_ids": missing,
        "usable_context_ids": usable,
        "requires_attention": bool(missing)
        or status.status in {"stale", "broken"}
        or any(age >= settings.price_age_warning_hours for age in ages.values()),
        "warning_age_hours": settings.price_age_warning_hours,
        "stale_age_hours": settings.max_price_age_hours,
        "status": status.status,
        "price_universe_id": status.price_universe_id,
        "built_at": status.built_at,
        "oldest_price_age_hours": status.oldest_price_age_hours,
        "oldest_usable_price_age_hours": status.oldest_usable_price_age_hours,
        "hours_until_oldest_usable_stale": (status.hours_until_oldest_usable_stale),
        "usable_context_count": status.usable_context_count,
        "excluded_stale_context_count": status.excluded_stale_context_count,
        "excluded_stale_context_ids": status.excluded_stale_context_ids,
        "retained_older_base_context_ids": status.retained_older_base_context_ids,
        "base_price_policy": status.base_price_policy,
        "product_count": status.product_count,
    }


def price_universe_id(settings: Settings) -> str | None:
    # Request evidence needs the exact active identity, not a readiness scan.
    # Dynamic ages and campaign applicability remain in active_price_status.
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_active(_scope_id(settings))
    return prepared.universe.universe_id if prepared is not None else None


def pseudonymous_actor(session_id: str | None, settings: Settings) -> str | None:
    if not session_id:
        return None
    key = settings.secret_key or "development-only-beta-identity-key"
    return hmac.new(key.encode(), session_id.encode(), hashlib.sha256).hexdigest()


def pseudonymous_network(host: str | None, settings: Settings) -> str:
    """Hash a coarse network prefix for ephemeral abuse control only.

    IPv4 addresses are reduced to /24 and IPv6 to /64 before keyed hashing.
    The raw address/prefix is never persisted or logged. Non-IP test/local
    clients share one conservative unknown-network bucket.
    """

    try:
        address = ipaddress.ip_address(host or "")
    except ValueError:
        bucket = "unknown-network"
    else:
        prefix = 24 if address.version == 4 else 64
        network = ipaddress.ip_network(f"{address}/{prefix}", strict=False)
        bucket = f"ipv{address.version}:{network.network_address}/{prefix}"
    key = settings.secret_key or "development-only-beta-identity-key"
    return hmac.new(
        key.encode(),
        f"network:{bucket}".encode(),
        hashlib.sha256,
    ).hexdigest()


class SlidingWindowRateLimiter:
    """Small process-local limiter for the documented single-worker beta.

    Community/receipt writes retain their existing database-backed anti-abuse
    checks. This limiter protects CPU-heavy planner and lightweight feedback
    endpoints. Multi-worker deployments need a shared limiter before scaling
    beyond the initial beta.
    """

    def __init__(
        self,
        clock: Callable[[], float] = monotonic,
        *,
        max_keys: int = 20_000,
        sweep_every: int = 64,
    ) -> None:
        if max_keys < 2:
            raise ValueError("max_keys must be at least two")
        if sweep_every < 1:
            raise ValueError("sweep_every must be at least one")
        self._clock = clock
        self._lock = Lock()
        self._max_keys = max_keys
        self._sweep_every = sweep_every
        self._operations = 0
        self._events: OrderedDict[tuple[str, str], tuple[deque[float], int]] = OrderedDict()

    @property
    def key_count(self) -> int:
        with self._lock:
            return len(self._events)

    def _sweep_expired(self, now: float) -> None:
        for key, (events, window_seconds) in list(self._events.items()):
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                self._events.pop(key, None)

    def acquire(
        self,
        *,
        scope: str,
        actor: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        now = self._clock()
        cutoff = now - window_seconds
        key = (scope, actor)
        with self._lock:
            self._operations += 1
            if self._operations % self._sweep_every == 0:
                self._sweep_expired(now)
            stored = self._events.get(key)
            if stored is None:
                while len(self._events) >= self._max_keys:
                    self._events.popitem(last=False)
                events: deque[float] = deque()
                self._events[key] = (events, window_seconds)
            else:
                events, _stored_window = stored
                self._events[key] = (events, window_seconds)
            while events and events[0] <= cutoff:
                events.popleft()
            self._events.move_to_end(key)
            if len(events) >= limit:
                retry = max(1, int(events[0] + window_seconds - now) + 1)
                return False, retry
            events.append(now)
        return True, 0


def _rate_policy(
    path: str,
    method: str,
    settings: Settings,
) -> tuple[str, int, int, int] | None:
    if method != "POST":
        return None
    if path == "/api/plan" or path == "/api/plans" or path.startswith("/api/plans/"):
        return (
            "planner",
            settings.planner_rate_limit_requests,
            settings.planner_network_rate_limit_requests,
            settings.planner_rate_limit_window_seconds,
        )
    if path == "/api/feedback":
        return (
            "feedback",
            settings.feedback_rate_limit_requests,
            settings.feedback_network_rate_limit_requests,
            settings.feedback_rate_limit_window_seconds,
        )
    if path == "/api/frontend-errors":
        return (
            "frontend_error",
            settings.frontend_error_rate_limit_requests,
            settings.frontend_error_network_rate_limit_requests,
            settings.frontend_error_rate_limit_window_seconds,
        )
    if path == "/api/analytics/events":
        return (
            "analytics",
            settings.analytics_rate_limit_requests,
            settings.analytics_network_rate_limit_requests,
            settings.analytics_rate_limit_window_seconds,
        )
    if path == "/api/community-evidence/receipt":
        return (
            "receipt",
            settings.receipt_rate_limit_requests,
            settings.receipt_network_rate_limit_requests,
            settings.receipt_rate_limit_window_seconds,
        )
    if path == "/api/community-evidence":
        return (
            "community",
            settings.community_rate_limit_requests,
            settings.community_network_rate_limit_requests,
            settings.community_rate_limit_window_seconds,
        )
    if path == "/api/privacy/erase":
        return (
            "privacy_erasure",
            settings.privacy_erasure_rate_limit_requests,
            settings.privacy_erasure_network_rate_limit_requests,
            settings.privacy_erasure_rate_limit_window_seconds,
        )
    return None


def _extract_plan_id(path: str) -> str | None:
    match = _PLAN_PATH.search(path)
    return match.group(1) if match else None


def _safe_endpoint(request: Request) -> str:
    route = request.scope.get("route")
    template = getattr(route, "path", None)
    return str(template)[:256] if template else request.url.path[:256]


def _persist_request_metric(
    factory: sessionmaker[Session],
    values: dict[str, Any],
) -> None:
    session: Session | None = None
    try:
        session = factory()
        session.add(BetaRequestMetricModel(**values))
        session.commit()
    except Exception:  # noqa: BLE001 - optional telemetry must never affect request
        if session is not None:
            session.rollback()
        LOGGER.warning(
            json.dumps(
                {
                    "event": "telemetry_persist_failed",
                    "request_id": values["request_id"],
                },
                separators=(",", ":"),
            )
        )
    finally:
        if session is not None:
            session.close()


def _metric_done(future: Future[None]) -> None:
    try:
        future.result()
    finally:
        _METRIC_SLOTS.release()


def _submit_request_metric(
    factory: sessionmaker[Session] | None,
    values: dict[str, Any],
) -> Future[None] | None:
    if factory is None:
        return None
    if not _METRIC_SLOTS.acquire(blocking=False):
        LOGGER.warning(
            json.dumps(
                {
                    "event": "telemetry_dropped",
                    "reason": "queue_full",
                    "request_id": values["request_id"],
                },
                separators=(",", ":"),
            )
        )
        return None
    try:
        future = _METRIC_EXECUTOR.submit(_persist_request_metric, factory, values)
    except BaseException:
        _METRIC_SLOTS.release()
        raise
    future.add_done_callback(_metric_done)
    return future


def _should_persist_request_metric(path: str) -> bool:
    if path in {
        "/",
        "/health",
        "/ready",
        "/manifest.webmanifest",
        "/service-worker.js",
        "/openapi.json",
        "/docs",
        "/redoc",
    }:
        return False
    return not path.startswith(("/static/", "/scanner-assets/", "/admin", "/api/admin/"))


class BetaRequestMiddleware(BaseHTTPMiddleware):
    """Request IDs, privacy-safe structured logs and lightweight rate limits."""

    def __init__(self, app: Any, *, settings_factory: Callable[[], Settings]) -> None:
        super().__init__(app)
        self.settings_factory = settings_factory
        self.limiter = SlidingWindowRateLimiter(max_keys=settings_factory().rate_limit_max_keys)

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        settings = self.settings_factory()
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request_id = (
            supplied_request_id if _REQUEST_ID.fullmatch(supplied_request_id) else uuid4().hex
        )
        supplied_session = request.headers.get("X-Anonymous-Session-ID", "")
        cookie_session = request.cookies.get("beta_session", "")
        if _SESSION_ID.fullmatch(supplied_session):
            anonymous_session_id = supplied_session
            set_cookie = False
        elif _SESSION_ID.fullmatch(cookie_session):
            anonymous_session_id = cookie_session
            set_cookie = False
        else:
            anonymous_session_id = uuid4().hex
            set_cookie = True
        request.state.request_id = request_id
        request.state.anonymous_session_id = anonymous_session_id

        policy = _rate_policy(request.url.path, request.method, settings)
        if policy is not None:
            scope, session_limit, network_limit, window = policy
            actor = pseudonymous_actor(anonymous_session_id, settings) or "anonymous"
            network_actor = pseudonymous_network(
                request.client.host if request.client is not None else None,
                settings,
            )
            network_allowed, network_retry = self.limiter.acquire(
                scope=f"network:{scope}",
                actor=network_actor,
                limit=network_limit,
                window_seconds=window,
            )
            allowed, retry_after = self.limiter.acquire(
                scope=f"session:{scope}",
                actor=actor,
                limit=session_limit,
                window_seconds=window,
            )
            if not network_allowed:
                allowed = False
                retry_after = max(retry_after, network_retry)
            if not allowed:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "detail": "För många förfrågningar. Försök igen senare.",
                        "error_code": "rate_limited",
                    },
                    headers={"Retry-After": str(retry_after)},
                )
                response.headers["X-Request-ID"] = request_id
                LOGGER.info(
                    json.dumps(
                        {
                            "event": "http_request",
                            "request_id": request_id,
                            "endpoint": request.url.path[:256],
                            "method": request.method,
                            "duration_ms": 0.0,
                            "status": 429,
                            "error_code": "rate_limited",
                            "plan_id": _extract_plan_id(request.url.path),
                            "price_universe_id": price_universe_id(settings),
                        },
                        separators=(",", ":"),
                        default=str,
                    )
                )
                return response

        started = perf_counter()
        incident_started_at = datetime.now(UTC).isoformat()
        incident_universe_id = price_universe_id(settings)
        status_code = 500
        error_code: str | None = None
        failure = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            if status_code >= 400:
                error_code = response.headers.get("X-Error-Code") or f"http_{status_code}"
        except BaseException as exc:
            failure = exc
            error_code = "internal_error"
            raise
        finally:
            if status_code >= 500 and (failure is None or isinstance(failure, Exception)):
                from app.services.app_incidents import record_http_failure
                record_http_failure(request, settings, error=failure, status=status_code,
                                    started_at=incident_started_at,
                                    universe_id=incident_universe_id)
            duration_ms = round((perf_counter() - started) * 1000, 3)
            log_row = {
                "event": "http_request",
                "request_id": request_id,
                "endpoint": _safe_endpoint(request),
                "method": request.method,
                "duration_ms": duration_ms,
                "status": status_code,
                "error_code": error_code,
                "plan_id": _extract_plan_id(request.url.path),
                "price_universe_id": price_universe_id(settings),
            }
            LOGGER.info(json.dumps(log_row, separators=(",", ":"), default=str))
            metric_future: Future[None] | None = None
            if _should_persist_request_metric(request.url.path):
                factory: sessionmaker[Session] | None = getattr(
                    request.app.state,
                    "community_session_factory",
                    None,
                )
                metric_future = _submit_request_metric(
                    factory,
                    {
                        "request_id": request_id,
                        "endpoint": _safe_endpoint(request),
                        "method": request.method,
                        "duration_ms": duration_ms,
                        "status_code": status_code,
                        "error_code": error_code,
                        "plan_id": _extract_plan_id(request.url.path),
                        "price_universe_id": price_universe_id(settings),
                        "app_version": settings.app_version,
                        "build_id": settings.build_id,
                    },
                )
            request.app.state.beta_last_metric_future = metric_future
        response.headers["X-Request-ID"] = request_id
        if set_cookie and not getattr(
            request.state,
            "suppress_beta_session_cookie",
            False,
        ):
            response.set_cookie(
                "beta_session",
                anonymous_session_id,
                max_age=60 * 60 * 24 * 180,
                httponly=True,
                secure=settings.app_env == "production",
                samesite="lax",
            )
        return response


def _next_daily_schedule(
    schedule: str | None,
    *,
    now: datetime,
) -> tuple[str | None, str | None]:
    if not schedule:
        return None, None
    parts = schedule.split()
    if len(parts) != 2 or not re.fullmatch(r"\d{2}:\d{2}", parts[0]):
        return None, None
    hours, minutes = (int(value) for value in parts[0].split(":"))
    if hours > 23 or minutes > 59:
        return None, None
    if parts[1] != "Europe/Stockholm":
        return None, None
    try:
        zone = ZoneInfo(parts[1])
    except ZoneInfoNotFoundError:
        return None, None
    evaluated = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    local_now = evaluated.astimezone(zone)
    candidate = datetime(
        local_now.year,
        local_now.month,
        local_now.day,
        hours,
        minutes,
        tzinfo=zone,
    )
    if candidate <= local_now:
        next_date = local_now.date() + timedelta(days=1)
        candidate = datetime(
            next_date.year,
            next_date.month,
            next_date.day,
            hours,
            minutes,
            tzinfo=zone,
        )
    return candidate.isoformat(), candidate.astimezone(UTC).isoformat()


def _safe_status_string(value: object, *, max_length: int = 255) -> str | None:
    if not isinstance(value, str) or not value or len(value) > max_length:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.:+\-]+", value):
        return None
    return value


def _refresh_runner_status(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"available": False, "status": "not_run"}
    except (OSError, json.JSONDecodeError):
        return {"available": False, "status": "invalid_status"}
    if not isinstance(payload, dict) or payload.get("schema_version") != (
        "production-refresh-runner-v1"
    ):
        return {"available": False, "status": "invalid_status"}
    runtime = payload.get("runtime_reload")
    if isinstance(payload.get("municipalities"), list):
        rows = [{"municipality_code": _safe_status_string(row.get("municipality_code")),
                 "exit_code": row.get("exit_code") if type(row.get("exit_code")) is int else None,
                 "error_type": _safe_status_string(row.get("error_type"))}
                for row in payload["municipalities"] if isinstance(row, dict)]
        return {"available": True, "status": payload.get("status") if payload.get("status") in {"complete", "degraded", "failed"} else "unknown",
                "municipalities": rows, "exit_code": payload.get("exit_code"),
                "runtime_activated_at_attempt": None,
                "completed_at": _safe_status_string(payload.get("completed_at"), max_length=64)}
    runtime = runtime if isinstance(runtime, dict) else {}
    runtime_status = _safe_status_string(runtime.get("status"), max_length=64)
    new_id = _safe_status_string(runtime.get("new_price_universe_id"))
    disk_id = _safe_status_string(runtime.get("disk_price_universe_id"))
    if runtime_status is None and new_id is not None:
        runtime_status = "succeeded"
    runtime_allowlist = {
        "status": runtime_status or "unknown",
        "old_price_universe_id": _safe_status_string(runtime.get("old_price_universe_id")),
        "new_price_universe_id": new_id,
        "disk_price_universe_id": disk_id,
        "changed": runtime.get("changed") if isinstance(runtime.get("changed"), bool) else None,
        "pricing_projection": _safe_status_string(runtime.get("pricing_projection"), max_length=64),
        "plan_prewarm": _safe_status_string(runtime.get("plan_prewarm"), max_length=64),
        "error_type": _safe_status_string(runtime.get("error_type"), max_length=64),
        "reason": _safe_status_string(runtime.get("reason"), max_length=64),
    }
    rollback = payload.get("disk_manifest_rollback")
    rollback = rollback if isinstance(rollback, dict) else {}
    rollback_allowlist = {
        "status": _safe_status_string(rollback.get("status"), max_length=64),
        "candidate_artifact_retained": rollback.get("candidate_artifact_retained")
        if isinstance(rollback.get("candidate_artifact_retained"), bool)
        else None,
        "error_type": _safe_status_string(rollback.get("error_type"), max_length=64),
        "reason": _safe_status_string(rollback.get("reason"), max_length=64),
    }
    exit_code = payload.get("exit_code")
    exit_code = (
        exit_code if isinstance(exit_code, int) and not isinstance(exit_code, bool) else None
    )
    refresh_exit = payload.get("refresh_exit_code")
    refresh_exit = (
        refresh_exit
        if isinstance(refresh_exit, int) and not isinstance(refresh_exit, bool)
        else None
    )
    deferred = runtime_allowlist["status"] == "deferred"
    failed = exit_code not in {0, 2} or runtime_allowlist["status"] in {
        "failed",
        "not_attempted",
        "unknown",
    }
    runner_status = "failed" if failed else "degraded" if deferred else "complete"
    return {
        "available": True,
        "status": runner_status,
        "started_at": _safe_status_string(payload.get("started_at"), max_length=64),
        "completed_at": _safe_status_string(payload.get("completed_at"), max_length=64),
        "city": _safe_status_string(payload.get("city"), max_length=128),
        "refresh_exit_code": refresh_exit,
        "exit_code": exit_code,
        "error_type": _safe_status_string(payload.get("error_type"), max_length=64),
        "runtime_reload": runtime_allowlist,
        "disk_manifest_rollback": rollback_allowlist,
        "runtime_activated_at_attempt": False if deferred else not failed,
        "lkg_retained": True if failed else None if deferred else False,
        "lkg_or_runtime_not_activated": failed or deferred,
        "operator_action": "restart_or_retry_runtime_reload" if deferred else None,
    }


def _source_retry_status(path: Path) -> dict[str, Any]:
    """Read only the bounded recovery runner's explicit safe contract."""

    try:
        payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"available": False, "status": "not_run"}
    except (OSError, json.JSONDecodeError):
        return {"available": False, "status": "invalid_status"}
    if not isinstance(payload, dict) or payload.get("schema_version") != ("source-retry-runner-v1"):
        return {"available": False, "status": "invalid_status"}
    status = _safe_status_string(payload.get("status"), max_length=64)
    exit_code = payload.get("exit_code")
    return {
        "available": True,
        "status": status or "unknown",
        "started_at": _safe_status_string(payload.get("started_at"), max_length=64),
        "completed_at": _safe_status_string(payload.get("completed_at"), max_length=64),
        "exit_code": (
            exit_code if isinstance(exit_code, int) and not isinstance(exit_code, bool) else None
        ),
        "reason": _safe_status_string(payload.get("reason"), max_length=96),
        "error_type": _safe_status_string(payload.get("error_type"), max_length=64),
    }


def _runner_runtime_identity(
    runner: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    runtime = runner.get("runtime_reload")
    runtime = runtime if isinstance(runtime, dict) else {}
    expected = runtime.get("disk_price_universe_id") or runtime.get("new_price_universe_id")
    active = active_price_status(settings)
    active_id = active.get("price_universe_id") if active.get("active") else None
    comparable = isinstance(expected, str) and isinstance(active_id, str)
    return {
        "active_runtime_price_universe_id": active_id,
        "runner_old_price_universe_id": runtime.get("old_price_universe_id"),
        "runner_new_price_universe_id": runtime.get("new_price_universe_id"),
        "disk_price_universe_id": runtime.get("disk_price_universe_id"),
        "active_matches_expected_disk_or_new": (active_id == expected) if comparable else None,
        "runtime_disk_id_mismatch": (active_id != expected) if comparable else None,
    }


def _read_refresh_report(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _refresh_report_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    summary = summary if isinstance(summary, dict) else {}
    status = _safe_status_string(summary.get("status"), max_length=64)
    exit_code = summary.get("exit_code")
    exit_code = (
        exit_code if isinstance(exit_code, int) and not isinstance(exit_code, bool) else None
    )
    timing = payload.get("timing_seconds")
    timing = timing if isinstance(timing, dict) else {}
    duration = timing.get("total")
    duration = (
        float(duration)
        if isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= 0
        else None
    )
    own = payload.get("own_collection")
    own = own if isinstance(own, dict) else {}
    own_rows = own.get("results")
    own_rows = own_rows if isinstance(own_rows, list) else []
    external_rows = payload.get("external_provider")
    external_rows = external_rows if isinstance(external_rows, list) else []
    rows = [row for row in [*own_rows, *external_rows] if isinstance(row, dict)]
    healthy_statuses = {"complete", "fresh", "healthy", "success", "succeeded"}
    healthy = sum(
        _safe_status_string(row.get("status"), max_length=64) in healthy_statuses for row in rows
    )
    return {
        "completed_at": _safe_status_string(payload.get("completed_at"), max_length=64),
        "duration_seconds": duration,
        "status": status,
        "exit_code": exit_code,
        "source_summary": {
            "total": len(rows),
            "healthy": healthy,
            "requiring_attention": len(rows) - healthy,
            "lkg_used": sum(bool(row.get("lkg_used") or row.get("fallback_used")) for row in rows),
        },
    }


def _last_successful_refresh(candidates: list[Path]) -> dict[str, Any] | None:
    for path in candidates[:_REFRESH_REPORT_SCAN_LIMIT]:
        payload = _read_refresh_report(path)
        if payload is None:
            continue
        summary = _refresh_report_summary(payload)
        if (
            summary["status"] == "complete"
            and summary["exit_code"] == 0
            and summary["completed_at"] is not None
        ):
            return summary
    return None


def latest_refresh_status(
    settings: Settings,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Read a strict allowlist from the newest daily-refresh report."""

    evaluated_at = now or datetime.now(tz=UTC)
    next_local, next_utc = _next_daily_schedule(
        settings.daily_refresh_schedule,
        now=evaluated_at,
    )
    prices = active_price_status(settings, now=evaluated_at)
    price_attention = settings.price_universe_required and (
        not prices.get("active") or prices.get("requires_attention", False)
    )
    runner = _refresh_runner_status(settings.refresh_runner_status_path)
    runner["runtime_identity"] = _runner_runtime_identity(runner, settings)
    runner_requires_attention = runner.get("status") in {"failed", "degraded"}
    source_retry = _source_retry_status(settings.source_retry_status_path)
    retry_next_local, retry_next_utc = _next_daily_schedule(
        settings.coop_retry_schedule,
        now=evaluated_at,
    )
    source_retry.update(
        {
            "schedule": settings.coop_retry_schedule,
            "next_scheduled_at": retry_next_local,
            "next_scheduled_at_utc": retry_next_utc,
        }
    )
    source_retry_requires_attention = source_retry.get("status") in {
        "configuration_error",
        "failed",
        "invalid_status",
        "skipped_operation_lock_held",
        "unknown",
    }
    directory = settings.refresh_report_dir.resolve()
    candidates = sorted(directory.glob("refresh-report-*.json"), reverse=True)
    last_successful = _last_successful_refresh(candidates)
    if not candidates:
        return {
            "available": False,
            "schedule": settings.daily_refresh_schedule,
            "next_scheduled_at": next_local,
            "next_scheduled_at_utc": next_utc,
            "runner": runner,
            "source_retry": source_retry,
            "requires_attention": (
                runner_requires_attention or source_retry_requires_attention or price_attention
            ),
            "planning_readiness": prices,
            "last_successful": None,
        }
    path = candidates[0]
    payload = _read_refresh_report(path)
    if payload is None:
        return {
            "available": False,
            "status": "invalid_report",
            "schedule": settings.daily_refresh_schedule,
            "next_scheduled_at": next_local,
            "next_scheduled_at_utc": next_utc,
            "runner": runner,
            "source_retry": source_retry,
            "requires_attention": True,
            "last_successful": last_successful,
        }
    own_rows = payload.get("own_collection", {}).get("results", [])
    external_rows = payload.get("external_provider", [])
    sources = [
        {
            "provider": row.get("source_provider") or row.get("provider") or "own",
            "chain": row.get("chain"),
            "context": row.get("grocery_context_id") or row.get("city"),
            "status": row.get("status"),
            "age_hours": row.get("active_snapshot_age_hours") or row.get("age_hours"),
            "lkg_used": bool(row.get("lkg_used") or row.get("fallback_used")),
            "warnings": list(row.get("warnings") or ()),
            "operational_warnings": list(row.get("operational_warnings") or ()),
            "freshness": row.get("freshness"),
            "hours_until_stale": row.get("hours_until_stale"),
            "stale_at": row.get("stale_at"),
            "next_expected_source_refresh": row.get("next_expected_source_refresh"),
            "source_will_expire_before_next_refresh": bool(
                row.get("source_will_expire_before_next_refresh")
            ),
            "retry_required": bool(row.get("retry_required")),
            "diagnostic_code": _safe_status_string(row.get("diagnostic_code"), max_length=96),
        }
        for row in [*own_rows, *external_rows]
        if isinstance(row, dict)
    ]
    summary = _refresh_report_summary(payload)
    source_failed = summary["status"] != "complete" or summary["exit_code"] != 0
    source_requires_retry = any(bool(row.get("retry_required")) for row in sources)
    return {
        "available": True,
        "completed_at": summary["completed_at"],
        "duration_seconds": summary["duration_seconds"],
        "status": summary["status"],
        "exit_code": summary["exit_code"],
        "sources": sources,
        "planning_readiness": prices,
        "price_universes": [
            {
                key: row.get(key)
                for key in (
                    "city",
                    "status",
                    "usable",
                    "universe_id",
                    "activation_status",
                    "build_error",
                    "build_skipped_reason",
                    "active_unchanged",
                )
            }
            for row in payload.get("price_universes", [])
            if isinstance(row, dict)
        ],
        "schedule": settings.daily_refresh_schedule,
        "next_scheduled_at": next_local,
        "next_scheduled_at_utc": next_utc,
        "runner": runner,
        "source_retry": source_retry,
        "requires_attention": (
            runner_requires_attention
            or source_retry_requires_attention
            or price_attention
            or any(
                row.get("build_error")
                for row in payload.get("price_universes", [])
                if isinstance(row, dict)
            )
            or source_failed
            or source_requires_retry
        ),
        "last_successful": last_successful,
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * fraction + 0.999999)))
    return round(ordered[index], 3)


def admin_aggregates(session: Session, settings: Settings) -> dict[str, Any]:
    """Return a small, privacy-safe 24-hour beta operations summary."""

    since = datetime.now(tz=UTC) - timedelta(hours=24)
    metrics = list(
        session.scalars(
            select(BetaRequestMetricModel).where(BetaRequestMetricModel.created_at >= since)
        )
    )
    planner = [
        row
        for row in metrics
        if row.endpoint in {"/api/plan", "/api/plans"} and row.method == "POST"
    ]
    latencies = [row.duration_ms for row in planner]
    successes = sum(row.status_code < 400 for row in planner)
    failures = len(planner) - successes
    analytics = list(
        session.scalars(
            select(ProductAnalyticsEventModel).where(ProductAnalyticsEventModel.created_at >= since)
        )
    )
    unique_sessions = len({row.actor_hash for row in analytics if row.actor_hash})
    feedback_count = int(
        session.scalar(
            select(func.count())
            .select_from(BetaFeedbackModel)
            .where(BetaFeedbackModel.created_at >= since)
        )
        or 0
    )
    recent_feedback = [
        {
            "feedback_id": row.id,
            "created_at": row.created_at,
            "category": row.category,
            "page_context": row.page_context,
            "message": row.message,
            "contact_email": row.contact_email,
            "plan_id": row.plan_id,
            "app_version": row.app_version,
            "build_id": row.build_id,
            "price_universe_id": row.price_universe_id,
        }
        for row in session.scalars(
            select(BetaFeedbackModel)
            .order_by(BetaFeedbackModel.created_at.desc(), BetaFeedbackModel.id.desc())
            .limit(_ADMIN_RECENT_ROW_LIMIT)
        )
    ]
    community_count = int(
        session.scalar(
            select(func.count())
            .select_from(CommunityEvidenceObservationModel)
            .where(CommunityEvidenceObservationModel.created_at >= since)
        )
        or 0
    )
    recent_errors = [
        {
            "created_at": row.created_at,
            "error_code": row.error_code,
            "route": row.route,
            "plan_id": row.plan_id,
        }
        for row in session.scalars(
            select(FrontendErrorModel).order_by(FrontendErrorModel.created_at.desc()).limit(20)
        )
    ]
    source_health = [
        {
            "chain": row.chain,
            "status": row.status,
            "coverage": row.coverage,
            "last_success_at": row.last_success_at,
            "checked_at": row.checked_at,
            "active_snapshot_id": row.active_snapshot_id,
            "warnings": row.warnings,
        }
        for row in session.scalars(
            select(ConnectorHealthModel).order_by(ConnectorHealthModel.chain)
        )
    ]
    recent_request_errors = [
        {
            "created_at": row.created_at,
            "endpoint": row.endpoint,
            "status_code": row.status_code,
            "error_code": row.error_code,
            "request_id": row.request_id,
            "plan_id": row.plan_id,
        }
        for row in session.scalars(
            select(BetaRequestMetricModel)
            .where(BetaRequestMetricModel.status_code >= 400)
            .order_by(BetaRequestMetricModel.created_at.desc())
            .limit(20)
        )
    ]
    distributions: dict[str, dict[str, int]] = {
        "diet": {},
        "mode": {},
        "max_stores": {},
    }
    plan_totals: list[float] = []
    portions: list[float] = []
    for row in analytics:
        for key, distribution in distributions.items():
            value = row.properties.get(key)
            if value is not None:
                rendered = str(value)
                distribution[rendered] = distribution.get(rendered, 0) + 1
        if row.event_name == "plan_succeeded":
            if isinstance(row.properties.get("total"), (int, float)):
                plan_totals.append(float(row.properties["total"]))
            if isinstance(row.properties.get("price_per_portion"), (int, float)):
                portions.append(float(row.properties["price_per_portion"]))
    return {
        "window_hours": 24,
        "unique_anonymous_sessions": unique_sessions,
        "plans": {
            "requested": len(planner),
            "succeeded": successes,
            "failed": failures,
            "success_rate": round(successes / len(planner), 4) if planner else None,
            "failure_rate": round(failures / len(planner), 4) if planner else None,
            "median_latency_ms": round(median(latencies), 3) if latencies else None,
            "p95_latency_ms": _percentile(latencies, 0.95),
            "average_total": round(sum(plan_totals) / len(plan_totals), 2) if plan_totals else None,
            "average_price_per_portion": round(sum(portions) / len(portions), 2)
            if portions
            else None,
        },
        "distributions": distributions,
        "community_reports": community_count,
        "feedback": feedback_count,
        "recent_feedback": recent_feedback,
        "report_rate_per_plan": round(community_count / successes, 4) if successes else None,
        "recent_frontend_errors": recent_errors,
        "recent_request_errors": recent_request_errors,
        "source_health": source_health,
    }


def database_ready(factory: sessionmaker[Session] | None) -> tuple[bool, str]:
    if factory is None:
        return False, "session_factory_unavailable"
    session = factory()
    try:
        session.execute(text("SELECT 1"))
        # Fail readiness when the deployment forgot the Alembic upgrade. The
        # probes are local metadata reads and never contact grocery providers.
        for table in (
            "community_evidence_observations",
            "beta_feedback",
            "product_analytics_events",
            "frontend_errors",
            "beta_request_metrics",
        ):
            session.execute(text(f"SELECT 1 FROM {table} WHERE 1 = 0"))
        return True, "ok"
    except SQLAlchemyError:
        return False, "database_unavailable"
    finally:
        session.close()


def plan_store_ready(path: Any) -> tuple[bool, str]:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        return False, "plan_store_unavailable"
    try:
        with sqlite3.connect(resolved, timeout=2.0) as connection:
            connection.execute("SELECT 1 FROM consumer_plan_revisions WHERE 1 = 0")
        return True, "ok"
    except sqlite3.Error:
        return False, "plan_store_unavailable"


async def reload_active_price_universe(
    application: Any,
    settings: Settings,
    *,
    artifact_store_factory: Callable[[Any], Any] | None = None,
    staging_manager_factory: Callable[[], Any] | None = None,
    projection_builder: Callable[..., Any] | None = None,
    prewarm_runner: Callable[..., Any] | None = None,
    active_manager: Any = GLOBAL_PREPARED_PRICE_UNIVERSES,
) -> dict[str, Any]:
    """Validate and precompute a disk candidate before one atomic runtime swap."""

    from app.services.plan_prewarm import prewarm_active_price_universe
    from app.services.price_universe_runtime import PreparedPriceUniverseManager
    from app.services.pricing_projection_prewarm import precompute_pricing_semantics

    from grocery_data.app.services.prepared_universe_activation import (
        PreparedUniverseArtifactStore,
    )

    artifact_store_factory = artifact_store_factory or PreparedUniverseArtifactStore
    staging_manager_factory = staging_manager_factory or PreparedPriceUniverseManager
    projection_builder = projection_builder or precompute_pricing_semantics
    custom_prewarm_runner = prewarm_runner is not None
    prewarm_runner = prewarm_runner or prewarm_active_price_universe
    artifact = artifact_store_factory(settings.price_universe_cache_root).resolve_active_artifact(
        settings.price_universe_city
    )
    if artifact is None:
        raise RuntimeError("active PriceUniverse artifact is unavailable")
    staging_manager = staging_manager_factory()
    candidate = staging_manager.load_file_and_activate(artifact)
    current = active_manager.get_active(candidate.universe.key.scope_id)
    if current is not None and current.universe.universe_id == candidate.universe.universe_id:
        # The disk candidate has passed hash/schema validation. Preserve the
        # loaded object's expensive deterministic caches on a repeated delivery.
        return {
            "old_price_universe_id": current.universe.universe_id,
            "new_price_universe_id": current.universe.universe_id,
            "changed": False,
            "pricing_projection": "already_active",
            "plan_prewarm": "already_active",
        }
    projection = projection_builder(
        settings,
        candidate,
        manager=staging_manager,
    )
    if projection.status not in {"hit", "miss_filled"}:
        raise RuntimeError("PriceUniverse pricing projection could not be prepared")
    old = active_manager.activate(candidate)
    application.state.pricing_projection_prewarm = projection
    try:
        if settings.price_universe_prewarm_enabled and not custom_prewarm_runner:
            from app.services.plan_prewarm import schedule_plan_prewarm
            prewarm_status = schedule_plan_prewarm(application, settings, candidate, manager=active_manager)
        else:
            prewarm = await prewarm_runner(settings, manager=active_manager)
            application.state.plan_prewarm = prewarm
            prewarm_status = prewarm.status
    except Exception:  # pragma: no cover - defensive optional prewarm boundary
        LOGGER.exception("optional plan prewarm failed after valid universe activation")
        prewarm_status = "failed"
    old_id = old.universe.universe_id if old is not None else None
    new_id = candidate.universe.universe_id
    return {
        "old_price_universe_id": old_id,
        "new_price_universe_id": new_id,
        "changed": old_id != new_id,
        "pricing_projection": projection.status,
        "plan_prewarm": prewarm_status,
    }


__all__ = [
    "BetaRequestMiddleware",
    "SlidingWindowRateLimiter",
    "active_price_status",
    "admin_aggregates",
    "database_ready",
    "latest_refresh_status",
    "plan_store_ready",
    "price_universe_id",
    "pseudonymous_actor",
    "pseudonymous_network",
    "reload_active_price_universe",
]
