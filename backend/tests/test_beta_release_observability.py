from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter, sleep
from types import SimpleNamespace
from typing import Any

import pytest
from app.api import beta_ops as beta_ops_module
from app.api.beta_ops import router
from app.config import Settings
from app.main import api_documentation_config
from app.services import beta_observability as beta_observability_module
from app.services.beta_observability import (
    BetaRequestMiddleware,
    SlidingWindowRateLimiter,
    latest_refresh_status,
    pseudonymous_network,
    reload_active_price_universe,
)
from app.services.plan_store import PlanStore
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from grocery_data.app.storage import (
    create_database_engine,
    create_schema,
    create_session_factory,
)
from grocery_data.app.storage.models import (
    BetaFeedbackModel,
    BetaRequestMetricModel,
    FrontendErrorModel,
    ProductAnalyticsEventModel,
)


def _application(tmp_path: Path, **updates: Any) -> tuple[FastAPI, Any, Settings]:
    database = tmp_path / "beta.sqlite"
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )
    create_schema(engine)
    factory = create_session_factory(engine)
    values: dict[str, Any] = {
        "price_universe_required": False,
        "secret_key": "s" * 40,
        "beta_admin_token": "a" * 40,
        "app_version": "1.2.3",
        "build_id": "build-abc",
        "refresh_report_dir": tmp_path / "refresh",
        "refresh_runner_status_path": tmp_path / "operations" / "refresh-runner-status.json",
        "plan_store_path": tmp_path / "plans.sqlite3",
    }
    values.update(updates)
    settings = Settings(**values)
    application = FastAPI()
    application.state.community_session_factory = factory
    application.state.beta_settings = settings
    application.state.plan_store = PlanStore(settings.plan_store_path)
    application.add_middleware(
        BetaRequestMiddleware,
        settings_factory=lambda: settings,
    )
    application.include_router(router)
    return application, factory, settings


def test_health_and_ready_are_cheap_and_traceable(tmp_path: Path) -> None:
    application, _, _ = _application(tmp_path)
    client = TestClient(application)

    health = client.get("/health")
    ready = client.get("/ready")

    assert health.status_code == 200
    assert health.json() == {
        "status": "ok",
        "app_version": "1.2.3",
        "build_id": "build-abc",
    }
    assert ready.status_code == 200
    assert ready.json()["database"] == "ok"
    assert ready.json()["status"] == "ready"
    assert health.headers["X-Request-ID"]


def test_ready_fails_closed_when_prices_are_required_but_absent(
    tmp_path: Path,
) -> None:
    application, _, _ = _application(tmp_path, price_universe_required=True)
    response = TestClient(application).get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["price_universe"]["active"] is False


def test_ready_keeps_fresh_contexts_available_when_one_source_is_excluded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, _, _ = _application(tmp_path, price_universe_required=True)
    monkeypatch.setattr(
        beta_ops_module,
        "active_price_status",
        lambda _settings: {
            "active": True,
            "status": "degraded",
            "price_universe_id": "pu-partial-freshness",
            "usable_context_count": 4,
            "excluded_stale_context_count": 1,
            "excluded_stale_context_ids": ["primat:coop:730400"],
        },
    )

    response = TestClient(application).get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["price_universe"]["status"] == "degraded"
    assert response.json()["price_universe"]["excluded_stale_context_count"] == 1


def test_feedback_is_pseudonymous_and_emits_first_party_event(tmp_path: Path) -> None:
    application, factory, _ = _application(tmp_path)
    response = TestClient(application).post(
        "/api/feedback",
        headers={"X-Anonymous-Session-ID": "anonymous-session-123456"},
        json={
            "category": "wrong_recipe",
            "message": "  Instruktionen saknar ett steg. ",
            "page_context": "/plans/result",
            "plan_id": "plan-1",
        },
    )

    assert response.status_code == 201
    session = factory()
    try:
        feedback = session.scalars(select(BetaFeedbackModel)).one()
        event = session.scalars(
            select(ProductAnalyticsEventModel).where(
                ProductAnalyticsEventModel.event_name == "feedback_created"
            )
        ).one()
        assert feedback.actor_hash
        assert feedback.actor_hash != "anonymous-session-123456"
        assert feedback.message == "Instruktionen saknar ett steg."
        assert feedback.app_version == "1.2.3"
        assert feedback.build_id == "build-abc"
        assert event.actor_hash == feedback.actor_hash
    finally:
        session.close()


def test_admin_recent_feedback_is_bounded_newest_first_and_has_no_actor(
    tmp_path: Path,
) -> None:
    application, factory, _ = _application(tmp_path)
    session = factory()
    base = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
    try:
        for index in range(25):
            session.add(
                BetaFeedbackModel(
                    created_at=base + timedelta(minutes=index),
                    actor_hash=f"private-actor-{index}",
                    category="suggestion",
                    message=f"feedback-{index}",
                    page_context="/plan",
                    plan_id=f"plan-{index}",
                    contact_email="tester@example.test" if index == 24 else None,
                    app_version="1.2.3",
                    build_id="build-abc",
                    price_universe_id="price-universe:test",
                )
            )
        session.commit()
    finally:
        session.close()

    client = TestClient(application)
    assert client.get("/api/admin/status").status_code == 401
    response = client.get(
        "/api/admin/status",
        headers={"X-Beta-Admin-Token": "a" * 40},
    )

    assert response.status_code == 200
    recent = response.json()["metrics"]["recent_feedback"]
    assert len(recent) == 20
    assert recent[0]["message"] == "feedback-24"
    assert recent[-1]["message"] == "feedback-5"
    assert recent[0]["contact_email"] == "tester@example.test"
    assert all("actor_hash" not in row for row in recent)
    assert "private-actor" not in response.text


def test_feedback_categories_and_context_are_stable_and_strict(tmp_path: Path) -> None:
    application, _, _ = _application(tmp_path)
    client = TestClient(application)
    payload = {
        "category": "unknown_category",
        "message": "x",
        "page_context": "/?token=secret",
        "cookies": "must-not-be-accepted",
    }

    response = client.post("/api/feedback", json=payload)

    assert response.status_code == 422


def test_analytics_accepts_only_bounded_allowlisted_properties(tmp_path: Path) -> None:
    application, factory, _ = _application(tmp_path)
    client = TestClient(application)
    accepted = client.post(
        "/api/analytics/events",
        json={
            "event_name": "plan_succeeded",
            "anonymous_session_id": "analytics-session-123456",
            "page_context": "/plan",
            "properties": {
                "diet": "vegetarian",
                "mode": "balanced",
                "max_stores": 2,
                "latency_ms": 9123.4,
                "total": 255.08,
                "price_per_portion": 12.75,
                "recipes": 5,
                "servings": 4,
                "actual_stores": 2,
            },
        },
    )
    rejected = client.post(
        "/api/analytics/events",
        json={
            "event_name": "plan_succeeded",
            "properties": {"raw_url": "https://example.test/?secret=x"},
        },
    )

    assert accepted.status_code == 202
    assert accepted.json() == {"accepted": True}
    assert rejected.status_code == 422
    session = factory()
    try:
        row = session.scalars(
            select(ProductAnalyticsEventModel).where(
                ProductAnalyticsEventModel.event_name == "plan_succeeded"
            )
        ).one()
        assert row.properties["total"] == 255.08
    finally:
        session.close()


def test_frontend_error_redacts_credentials_and_url_queries(tmp_path: Path) -> None:
    application, factory, _ = _application(tmp_path)
    response = TestClient(application).post(
        "/api/frontend-errors",
        json={
            "route": "/plans/result",
            "error_code": "render_failed",
            "message": (
                "Failed https://example.test/path?token=abc "
                "Authorization: Bearer super-secret"
            ),
        },
    )

    assert response.status_code == 202
    session = factory()
    try:
        row = session.scalars(select(FrontendErrorModel)).one()
        assert "super-secret" not in row.message
        assert "token=abc" not in row.message
        assert "[REDACTED]" in row.message
        assert "[URL_REDACTED]" in row.message
    finally:
        session.close()


def test_rate_limits_are_per_anonymous_session_and_configurable(tmp_path: Path) -> None:
    application, _, _ = _application(
        tmp_path,
        feedback_rate_limit_requests=2,
        feedback_rate_limit_window_seconds=60,
    )
    client = TestClient(application)
    payload = {
        "category": "suggestion",
        "message": "Förslag",
        "page_context": "/",
    }

    assert client.post("/api/feedback", json=payload).status_code == 201
    assert client.post("/api/feedback", json=payload).status_code == 201
    limited = client.post("/api/feedback", json=payload)
    other = TestClient(application).post(
        "/api/feedback",
        headers={"X-Anonymous-Session-ID": "another-session-123456"},
        json=payload,
    )

    assert limited.status_code == 429
    assert limited.json()["error_code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1
    assert other.status_code == 201


def test_sliding_window_limiter_expires_old_events() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(clock=lambda: now[0])

    assert limiter.acquire(scope="x", actor="a", limit=1, window_seconds=60)[0]
    assert not limiter.acquire(scope="x", actor="a", limit=1, window_seconds=60)[0]
    now[0] = 61
    assert limiter.acquire(scope="x", actor="a", limit=1, window_seconds=60)[0]


def test_sliding_window_limiter_evicts_expired_keys_and_stays_bounded() -> None:
    now = [0.0]
    limiter = SlidingWindowRateLimiter(
        clock=lambda: now[0],
        max_keys=3,
        sweep_every=1,
    )

    for actor in ("a", "b", "c", "d"):
        assert limiter.acquire(
            scope="session:feedback",
            actor=actor,
            limit=2,
            window_seconds=60,
        )[0]
        assert limiter.key_count <= 3
    assert limiter.key_count == 3

    now[0] = 61
    assert limiter.acquire(
        scope="session:feedback",
        actor="fresh",
        limit=2,
        window_seconds=60,
    )[0]
    assert limiter.key_count == 1


def test_rotating_session_ids_cannot_bypass_coarse_network_limit(tmp_path: Path) -> None:
    application, _, _ = _application(
        tmp_path,
        feedback_rate_limit_requests=1,
        feedback_network_rate_limit_requests=3,
        feedback_rate_limit_window_seconds=60,
    )
    client = TestClient(application)
    payload = {
        "category": "suggestion",
        "message": "Förslag",
        "page_context": "/",
    }

    responses = [
        client.post(
            "/api/feedback",
            headers={"X-Anonymous-Session-ID": f"rotated-session-{index:08d}"},
            json=payload,
        )
        for index in range(4)
    ]

    assert [response.status_code for response in responses] == [201, 201, 201, 429]
    assert responses[-1].json()["error_code"] == "rate_limited"


@pytest.mark.parametrize(
    ("path", "updates"),
    [
        (
            "/api/community-evidence",
            {
                "community_rate_limit_requests": 1,
                "community_network_rate_limit_requests": 2,
            },
        ),
        (
            "/api/community-evidence/receipt",
            {
                "receipt_rate_limit_requests": 1,
                "receipt_network_rate_limit_requests": 2,
            },
        ),
    ],
)
def test_rotating_report_identity_cannot_bypass_community_network_limit(
    tmp_path: Path,
    path: str,
    updates: dict[str, int],
) -> None:
    application, _, _ = _application(tmp_path, **updates)

    @application.post(path)
    def accepted() -> dict[str, bool]:
        return {"accepted": True}

    client = TestClient(application)
    responses = [
        client.post(
            path,
            headers={"X-Anonymous-Session-ID": f"rotated-report-{index:08d}"},
            json={"anonymous_session_id": f"payload-identity-{index:08d}"},
        )
        for index in range(3)
    ]

    assert [response.status_code for response in responses] == [200, 200, 429]


def test_network_identity_is_coarse_keyed_and_never_contains_raw_address() -> None:
    settings = Settings(secret_key="s" * 40, price_universe_required=False)

    first = pseudonymous_network("198.51.100.10", settings)
    same_prefix = pseudonymous_network("198.51.100.240", settings)
    other_prefix = pseudonymous_network("198.51.101.10", settings)

    assert first == same_prefix
    assert first != other_prefix
    assert "198.51" not in first


def test_structured_request_log_and_metric_exclude_query_and_cookie(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    application, factory, _ = _application(tmp_path)

    @application.get("/api/test-observed")
    def observed() -> dict[str, bool]:
        return {"ok": True}

    caplog.set_level(logging.INFO, logger="beta.request")
    response = TestClient(application).get(
        "/api/test-observed?token=must-not-log",
        headers={"Cookie": "session=must-not-log"},
    )

    assert response.status_code == 200
    application.state.beta_last_metric_future.result(timeout=2)
    messages = [record.message for record in caplog.records if "http_request" in record.message]
    assert messages
    parsed = json.loads(messages[-1])
    assert parsed["endpoint"] == "/api/test-observed"
    assert "must-not-log" not in messages[-1]
    session = factory()
    try:
        metric = session.scalars(select(BetaRequestMetricModel)).one()
        assert metric.endpoint == "/api/test-observed"
        assert metric.request_id == response.headers["X-Request-ID"]
    finally:
        session.close()


def test_probes_skip_metrics_and_slow_telemetry_never_delays_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, factory, _ = _application(tmp_path)
    calls: list[object] = []

    def slow_persist(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))
        sleep(0.3)

    monkeypatch.setattr(
        beta_observability_module,
        "_persist_request_metric",
        slow_persist,
    )
    client = TestClient(application)
    started = perf_counter()
    health = client.get("/health")
    ready = client.get("/ready")
    elapsed = perf_counter() - started

    assert health.status_code == 200
    assert ready.status_code == 200
    assert elapsed < 0.2
    assert calls == []
    session = factory()
    try:
        assert list(session.scalars(select(BetaRequestMetricModel))) == []
    finally:
        session.close()


def test_normal_metric_write_is_off_request_thread_and_still_persists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, factory, _ = _application(tmp_path)

    @application.get("/api/nonblocking-metric")
    def observed() -> dict[str, bool]:
        return {"ok": True}

    real_persist = beta_observability_module._persist_request_metric

    def delayed_persist(*args: Any, **kwargs: Any) -> None:
        sleep(0.25)
        real_persist(*args, **kwargs)

    monkeypatch.setattr(
        beta_observability_module,
        "_persist_request_metric",
        delayed_persist,
    )
    started = perf_counter()
    response = TestClient(application).get("/api/nonblocking-metric")
    elapsed = perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 0.2
    application.state.beta_last_metric_future.result(timeout=2)
    session = factory()
    try:
        metric = session.scalars(select(BetaRequestMetricModel)).one()
        assert metric.endpoint == "/api/nonblocking-metric"
    finally:
        session.close()


def test_admin_status_is_protected_and_aggregated(tmp_path: Path) -> None:
    refresh_dir = tmp_path / "refresh"
    refresh_dir.mkdir()
    (refresh_dir / "refresh-report-20260901T040000Z-test.json").write_text(
        json.dumps(
            {
                "completed_at": "2026-09-01T04:05:00Z",
                "summary": {"status": "complete", "exit_code": 0},
                "timing_seconds": {"total": 300.0},
                "own_collection": {
                    "results": [
                        {
                            "source_provider": "own",
                            "chain": "hemkop",
                            "grocery_context_id": "own:hemkop:4123",
                            "status": "healthy",
                            "active_snapshot_age_hours": 0.2,
                            "lkg_used": False,
                        }
                    ]
                },
                "external_provider": [],
            }
        ),
        encoding="utf-8",
    )
    runner_path = tmp_path / "operations" / "refresh-runner-status.json"
    runner_path.parent.mkdir()
    runner_path.write_text(
        json.dumps(
            {
                "schema_version": "production-refresh-runner-v1",
                "started_at": "2026-09-01T03:17:00+00:00",
                "completed_at": "2026-09-01T03:47:00+00:00",
                "city": "Lund",
                "refresh_exit_code": 0,
                "exit_code": 1,
                "runtime_reload": {
                    "status": "failed",
                    "error_type": "RuntimeError",
                    "secret": "must-not-leak",
                },
                "disk_manifest_rollback": {
                    "status": "restored_previous",
                    "candidate_artifact_retained": True,
                    "secret": "must-not-leak",
                },
                "untrusted": {"token": "must-not-leak"},
            }
        ),
        encoding="utf-8",
    )
    application, _, _ = _application(
        tmp_path,
        refresh_report_dir=refresh_dir,
        refresh_runner_status_path=runner_path,
        daily_refresh_schedule="04:00 Europe/Stockholm",
    )
    client = TestClient(application)

    assert client.get("/api/admin/status").status_code == 401
    response = client.get(
        "/api/admin/status",
        headers={"X-Beta-Admin-Token": "a" * 40},
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    payload = response.json()
    assert payload["app_version"] == "1.2.3"
    assert payload["refresh"]["status"] == "complete"
    assert payload["refresh"]["sources"][0]["context"] == "own:hemkop:4123"
    assert payload["refresh"]["runner"]["status"] == "failed"
    assert payload["refresh"]["runner"]["runtime_reload"]["error_type"] == (
        "RuntimeError"
    )
    assert payload["refresh"]["runner"]["lkg_retained"] is True
    assert payload["refresh"]["runner"]["disk_manifest_rollback"] == {
        "status": "restored_previous",
        "candidate_artifact_retained": True,
        "error_type": None,
        "reason": None,
    }
    assert payload["refresh"]["requires_attention"] is True
    assert "failure_rate" in payload["metrics"]["plans"]
    assert "recent_request_errors" in payload["metrics"]
    assert "credentials" not in json.dumps(payload).casefold()
    assert "must-not-leak" not in json.dumps(payload)


def test_admin_mutation_rejects_basic_and_admin_responses_are_not_cached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    application, _, _ = _application(tmp_path)
    client = TestClient(application)
    token = "a" * 40
    encoded = base64.b64encode(f"operator:{token}".encode()).decode()
    basic = {"Authorization": f"Basic {encoded}"}

    assert client.get("/api/admin/status", headers=basic).status_code == 200
    rejected = client.post("/api/admin/reload-price-universe", headers=basic)
    assert rejected.status_code == 401

    async def reload_stub(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "old_price_universe_id": "old",
            "new_price_universe_id": "new",
            "changed": True,
        }

    monkeypatch.setattr(
        beta_ops_module,
        "reload_active_price_universe",
        reload_stub,
    )
    reloaded = client.post(
        "/api/admin/reload-price-universe",
        headers={"Authorization": f"Bearer {token}"},
    )
    page = client.get("/admin", headers=basic)

    assert reloaded.status_code == 200
    assert reloaded.headers["Cache-Control"] == "no-store"
    assert reloaded.json()["new_price_universe_id"] == "new"
    assert page.status_code == 200
    assert page.headers["Cache-Control"] == "no-store"


def test_refresh_status_reports_timeout_and_next_daily_schedule(tmp_path: Path) -> None:
    runner = tmp_path / "runner.json"
    runner.write_text(
        json.dumps(
            {
                "schema_version": "production-refresh-runner-v1",
                "started_at": "2026-09-01T03:17:00+00:00",
                "completed_at": "2026-09-01T04:02:00+00:00",
                "city": "Lund",
                "refresh_exit_code": None,
                "exit_code": 1,
                "error_type": "TimeoutExpired",
                "runtime_reload": {"status": "not_attempted"},
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        price_universe_required=False,
        refresh_report_dir=tmp_path / "missing-refresh-reports",
        refresh_runner_status_path=runner,
        daily_refresh_schedule="03:17 Europe/Stockholm",
    )

    before = latest_refresh_status(
        settings,
        now=datetime.fromisoformat("2026-09-01T00:00:00+00:00"),
    )
    after = latest_refresh_status(
        settings,
        now=datetime.fromisoformat("2026-09-01T02:00:00+00:00"),
    )

    assert before["runner"]["status"] == "failed"
    assert before["runner"]["error_type"] == "TimeoutExpired"
    assert before["runner"]["lkg_retained"] is True
    assert before["next_scheduled_at"] == "2026-09-01T03:17:00+02:00"
    assert before["next_scheduled_at_utc"] == "2026-09-01T01:17:00+00:00"
    assert after["next_scheduled_at"] == "2026-09-02T03:17:00+02:00"


def test_deferred_runtime_reload_is_degraded_and_exposes_safe_id_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = tmp_path / "runner.json"
    runner.write_text(
        json.dumps(
            {
                "schema_version": "production-refresh-runner-v1",
                "started_at": "2026-09-01T03:17:00+00:00",
                "completed_at": "2026-09-01T03:47:00+00:00",
                "city": "Lund",
                "refresh_exit_code": 0,
                "exit_code": 2,
                "runtime_reload": {
                    "status": "deferred",
                    "reason": "app_unavailable",
                    "error_type": "RuntimeReloadUnavailable",
                    "disk_price_universe_id": "price-universe:new",
                    "secret": "must-not-leak",
                },
                "disk_manifest_rollback": {
                    "status": "not_attempted",
                    "reason": "candidate_retained_for_restart",
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        beta_observability_module,
        "active_price_status",
        lambda _settings: {
            "active": True,
            "status": "fresh",
            "price_universe_id": "price-universe:old",
        },
    )

    status = latest_refresh_status(
        Settings(
            price_universe_required=False,
            refresh_report_dir=tmp_path / "missing-refresh-reports",
            refresh_runner_status_path=runner,
        )
    )

    parsed = status["runner"]
    assert parsed["status"] == "degraded"
    assert status["requires_attention"] is True
    assert parsed["runtime_activated_at_attempt"] is False
    assert parsed["lkg_retained"] is None
    assert parsed["lkg_or_runtime_not_activated"] is True
    assert parsed["operator_action"] == "restart_or_retry_runtime_reload"
    assert parsed["runtime_reload"]["reason"] == "app_unavailable"
    assert parsed["disk_manifest_rollback"]["reason"] == (
        "candidate_retained_for_restart"
    )
    assert parsed["runtime_identity"]["active_runtime_price_universe_id"] == (
        "price-universe:old"
    )
    assert parsed["runtime_identity"]["disk_price_universe_id"] == (
        "price-universe:new"
    )
    assert parsed["runtime_identity"]["runtime_disk_id_mismatch"] is True
    assert "must-not-leak" not in json.dumps(status)


def test_latest_failed_refresh_keeps_explicit_last_successful_attempt(
    tmp_path: Path,
) -> None:
    refresh_dir = tmp_path / "refresh"
    refresh_dir.mkdir()
    older = refresh_dir / "refresh-report-20260831T040000Z-success.json"
    newer = refresh_dir / "refresh-report-20260901T040000Z-failed.json"
    older.write_text(
        json.dumps(
            {
                "completed_at": "2026-08-31T04:05:00Z",
                "summary": {"status": "complete", "exit_code": 0},
                "timing_seconds": {"total": 301.25},
                "own_collection": {
                    "results": [
                        {"status": "healthy", "lkg_used": False},
                        {"status": "fresh", "lkg_used": True},
                    ]
                },
                "external_provider": [],
            }
        ),
        encoding="utf-8",
    )
    newer.write_text(
        json.dumps(
            {
                "completed_at": "2026-09-01T04:02:00Z",
                "summary": {"status": "failed", "exit_code": 1},
                "timing_seconds": {"total": 122.0},
                "own_collection": {"results": [{"status": "failed"}]},
                "external_provider": [],
            }
        ),
        encoding="utf-8",
    )

    status = latest_refresh_status(
        Settings(
            price_universe_required=False,
            refresh_report_dir=refresh_dir,
            refresh_runner_status_path=tmp_path / "missing-runner.json",
        )
    )

    assert status["status"] == "failed"
    assert status["completed_at"] == "2026-09-01T04:02:00Z"
    assert status["requires_attention"] is True
    assert status["last_successful"] == {
        "completed_at": "2026-08-31T04:05:00Z",
        "duration_seconds": 301.25,
        "status": "complete",
        "exit_code": 0,
        "source_summary": {
            "total": 2,
            "healthy": 2,
            "requiring_attention": 0,
            "lkg_used": 1,
        },
    }


@pytest.mark.parametrize(
    "schedule",
    ["cron-expression", "03:17 UTC", "24:00 Europe/Stockholm"],
)
def test_unparsable_refresh_schedule_truthfully_has_no_next_run(
    tmp_path: Path,
    schedule: str,
) -> None:
    status = latest_refresh_status(
        Settings(
            price_universe_required=False,
            refresh_report_dir=tmp_path / "missing",
            refresh_runner_status_path=tmp_path / "missing-runner.json",
            daily_refresh_schedule=schedule,
        ),
        now=datetime.fromisoformat("2026-09-01T00:00:00+00:00"),
    )

    assert status["next_scheduled_at"] is None
    assert status["next_scheduled_at_utc"] is None


def test_refresh_runner_and_network_limits_load_from_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = tmp_path / "operations" / "refresh-runner-status.json"
    monkeypatch.setenv("REFRESH_RUNNER_STATUS_PATH", str(runner))
    monkeypatch.setenv("FEEDBACK_RATE_LIMIT_REQUESTS", "7")
    monkeypatch.setenv("FEEDBACK_NETWORK_RATE_LIMIT_REQUESTS", "35")
    monkeypatch.setenv("RATE_LIMIT_MAX_KEYS", "1234")

    settings = Settings.from_env()

    assert settings.refresh_runner_status_path == runner
    assert settings.feedback_rate_limit_requests == 7
    assert settings.feedback_network_rate_limit_requests == 35
    assert settings.rate_limit_max_keys == 1234


@pytest.mark.asyncio
async def test_reload_validates_projection_before_atomic_swap() -> None:
    old = SimpleNamespace(universe=SimpleNamespace(universe_id="old"))
    candidate = SimpleNamespace(universe=SimpleNamespace(universe_id="new"))
    events: list[str] = []

    class Store:
        def __init__(self, _root: Path) -> None:
            pass

        def resolve_active_artifact(self, city: str) -> Path:
            assert city == "Lund"
            return Path("candidate.json")

    class Staging:
        def load_file_and_activate(self, path: Path) -> Any:
            assert path == Path("candidate.json")
            events.append("validated")
            return candidate

    class Active:
        def activate(self, prepared: Any) -> Any:
            assert prepared is candidate
            events.append("swapped")
            return old

    def project(_settings: Settings, prepared: Any, *, manager: Any) -> Any:
        assert prepared is candidate
        assert isinstance(manager, Staging)
        events.append("projected")
        return SimpleNamespace(status="miss_filled")

    async def prewarm(_settings: Settings, *, manager: Any) -> Any:
        assert isinstance(manager, Active)
        events.append("prewarmed")
        return SimpleNamespace(status="complete")

    application = SimpleNamespace(state=SimpleNamespace())
    result = await reload_active_price_universe(
        application,
        Settings(price_universe_required=False),
        artifact_store_factory=Store,
        staging_manager_factory=Staging,
        projection_builder=project,
        prewarm_runner=prewarm,
        active_manager=Active(),
    )

    assert events == ["validated", "projected", "swapped", "prewarmed"]
    assert result["old_price_universe_id"] == "old"
    assert result["new_price_universe_id"] == "new"
    assert result["changed"] is True


@pytest.mark.asyncio
async def test_reload_failure_keeps_last_known_good_runtime() -> None:
    swaps: list[Any] = []

    class Store:
        def __init__(self, _root: Path) -> None:
            pass

        def resolve_active_artifact(self, _city: str) -> Path:
            return Path("broken.json")

    class BrokenStaging:
        def load_file_and_activate(self, _path: Path) -> Any:
            raise ValueError("hash mismatch")

    class Active:
        def activate(self, prepared: Any) -> None:
            swaps.append(prepared)

    with pytest.raises(ValueError, match="hash mismatch"):
        await reload_active_price_universe(
            SimpleNamespace(state=SimpleNamespace()),
            Settings(price_universe_required=False),
            artifact_store_factory=Store,
            staging_manager_factory=BrokenStaging,
            active_manager=Active(),
        )

    assert swaps == []


def test_production_settings_require_https_and_long_secrets() -> None:
    with pytest.raises(ValueError, match="RATE_LIMIT_MAX_KEYS"):
        Settings(price_universe_required=False, rate_limit_max_keys=1)
    with pytest.raises(ValueError, match="greater than its session limit"):
        Settings(
            price_universe_required=False,
            feedback_rate_limit_requests=10,
            feedback_network_rate_limit_requests=10,
        )
    with pytest.raises(ValueError, match="PUBLIC_BASE_URL"):
        Settings(app_env="production")
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            app_env="production",
            public_base_url="https://beta.example",
            secret_key="short",
            beta_admin_token="a" * 40,
        )
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            app_env="production",
            public_base_url="https://beta.example",
            secret_key="replace-with-at-least-32-random-bytes",
            beta_admin_token="a" * 40,
        )
    with pytest.raises(ValueError, match="BETA_ADMIN_TOKEN"):
        Settings(
            app_env="production",
            public_base_url="https://beta.example",
            secret_key="s" * 40,
            beta_admin_token="replace-with-a-different-32-byte-value",
        )
    with pytest.raises(ValueError, match="must be different"):
        Settings(
            app_env="production",
            app_version="0.1.0-beta.1",
            build_id="git-abcdef1234",
            public_base_url="https://beta.example",
            secret_key="x" * 40,
            beta_admin_token="x" * 40,
        )
    with pytest.raises(ValueError, match="APP_VERSION"):
        Settings(
            app_env="production",
            app_version="replace-with-version",
            build_id="git-abcdef1234",
            public_base_url="https://beta.example",
            secret_key="s" * 40,
            beta_admin_token="a" * 40,
        )
    for build_id in ("local", "unknown", "replace-with-build-id", ""):
        with pytest.raises(ValueError, match="BUILD_ID"):
            Settings(
                app_env="production",
                app_version="0.1.0-beta",
                build_id=build_id,
                public_base_url="https://beta.example",
                secret_key="s" * 40,
                beta_admin_token="a" * 40,
            )
    valid = Settings(
        app_env="production",
        app_version="0.1.0-beta.1+sha.abcdef",
        build_id="git-abcdef1234",
        public_base_url="https://beta.example",
        secret_key="s" * 40,
        beta_admin_token="a" * 40,
    )
    assert valid.build_id == "git-abcdef1234"


def test_production_disables_interactive_api_documentation() -> None:
    production = Settings(
        app_env="production",
        app_version="0.1.0-beta.1",
        build_id="git-abcdef1234",
        public_base_url="https://beta.example",
        secret_key="s" * 40,
        beta_admin_token="a" * 40,
    )

    assert api_documentation_config(production) == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert api_documentation_config(Settings(price_universe_required=False)) == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }
