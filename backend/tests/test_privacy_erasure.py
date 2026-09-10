from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.api.beta_ops import router
from app.config import Settings
from app.services.beta_observability import BetaRequestMiddleware, pseudonymous_actor
from app.services.plan_store import PlanStore
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from grocery_data.app.domain.community_evidence import CommunityEvidenceSubmission
from grocery_data.app.storage import (
    CommunityEvidenceRepository,
    create_database_engine,
    create_schema,
    create_session_factory,
    pseudonymous_actor_hash,
)
from grocery_data.app.storage.models import (
    BetaFeedbackModel,
    BetaRequestMetricModel,
    CommunityEvidenceObservationModel,
    CommunityReceiptIngestionModel,
    FrontendErrorModel,
    PrivacyErasureSuppressionModel,
    ProductAnalyticsEventModel,
)


def _application(tmp_path: Path, **updates: object) -> tuple[FastAPI, object, Settings]:
    database = tmp_path / "privacy.sqlite3"
    engine = create_database_engine(
        f"sqlite+pysqlite:///{database.resolve().as_posix()}"
    )
    create_schema(engine)
    factory = create_session_factory(engine)
    values: dict[str, object] = {
        "price_universe_required": False,
        "secret_key": "privacy-test-key-000000000000000000000001",
        "beta_admin_token": "a" * 40,
        "app_version": "1.2.3",
        "build_id": "privacy-test-build",
        "plan_store_path": tmp_path / "plans.sqlite3",
        "privacy_erasure_rate_limit_requests": 3,
        "privacy_erasure_network_rate_limit_requests": 20,
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


def _insert_plan_revision(
    path: Path,
    *,
    plan_id: str,
    revision: int,
    owner_actor_hash: str | None,
) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO consumer_plan_revisions (
                plan_id, revision, parent_revision, created_at, operation,
                request_json, response_json, price_universe_id,
                diversity_mode, diet_preference, max_stores, meal_count,
                servings, app_version, build_id, owner_actor_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                revision,
                revision - 1 if revision > 1 else None,
                datetime.now(UTC).isoformat(),
                "created" if revision == 1 else "recipe_replaced",
                "{}",
                "{}",
                "price-universe:test",
                "balanced",
                "mixed",
                2,
                5,
                4,
                "1.2.3",
                "privacy-test-build",
                owner_actor_hash,
            ),
        )


def test_plan_store_erase_owned_is_atomic_scoped_and_idempotent(tmp_path: Path) -> None:
    store = PlanStore(tmp_path / "owned-plans.sqlite3")
    owner = "a" * 64
    other = "b" * 64
    _insert_plan_revision(store.path, plan_id="owned", revision=1, owner_actor_hash=owner)
    _insert_plan_revision(store.path, plan_id="owned", revision=2, owner_actor_hash=owner)
    _insert_plan_revision(store.path, plan_id="other", revision=1, owner_actor_hash=other)
    _insert_plan_revision(store.path, plan_id="legacy", revision=1, owner_actor_hash=None)

    assert store.owned_plan_ids(owner_actor_hash=owner) == ("owned",)
    result = store.erase_owned(owner_actor_hash=owner)
    repeated = store.erase_owned(owner_actor_hash=owner)

    assert result.plan_ids == ("owned",)
    assert result.plans_deleted == 1
    assert result.revisions_deleted == 2
    assert repeated.plans_deleted == repeated.revisions_deleted == 0
    with sqlite3.connect(store.path) as connection:
        remaining = connection.execute(
            "SELECT plan_id, owner_actor_hash FROM consumer_plan_revisions ORDER BY plan_id"
        ).fetchall()
    assert remaining == [("legacy", None), ("other", other)]


def test_privacy_erasure_removes_owned_beta_data_and_unlinks_evidence(
    tmp_path: Path,
    caplog,
) -> None:  # type: ignore[no-untyped-def]
    application, factory, settings = _application(tmp_path)
    local_session_id = str(uuid4())
    owner_session_id = str(uuid4())
    unrelated_local_id = str(uuid4())
    beta_hash = pseudonymous_actor(local_session_id, settings)
    owner_hash = pseudonymous_actor(owner_session_id, settings)
    unrelated_beta_hash = pseudonymous_actor(unrelated_local_id, settings)
    community_hash = pseudonymous_actor_hash(local_session_id)
    assert beta_hash and owner_hash and unrelated_beta_hash

    _insert_plan_revision(
        settings.plan_store_path,
        plan_id="owned-plan-a",
        revision=1,
        owner_actor_hash=owner_hash,
    )
    _insert_plan_revision(
        settings.plan_store_path,
        plan_id="owned-plan-a",
        revision=2,
        owner_actor_hash=owner_hash,
    )
    _insert_plan_revision(
        settings.plan_store_path,
        plan_id="owned-plan-b",
        revision=1,
        owner_actor_hash=owner_hash,
    )
    _insert_plan_revision(
        settings.plan_store_path,
        plan_id="legacy-plan",
        revision=1,
        owner_actor_hash=None,
    )
    _insert_plan_revision(
        settings.plan_store_path,
        plan_id="other-plan",
        revision=1,
        owner_actor_hash="c" * 64,
    )

    now = datetime.now(UTC)
    with factory() as session:  # type: ignore[operator]
        feedback = BetaFeedbackModel(
            actor_hash=beta_hash,
            category="other",
            message="Please delete",
            page_context="/",
            plan_id="owned-plan-a",
            contact_email="person@example.test",
            app_version="1.2.3",
            build_id="privacy-test-build",
            price_universe_id="price-universe:test",
        )
        unrelated_feedback = BetaFeedbackModel(
            actor_hash=unrelated_beta_hash,
            category="other",
            message="Keep",
            page_context="/",
            contact_email="other@example.test",
            app_version="1.2.3",
            build_id="privacy-test-build",
        )
        analytics = ProductAnalyticsEventModel(
            actor_hash=beta_hash,
            event_name="planner_opened",
            page_context="/",
            plan_id="owned-plan-a",
            properties={},
            app_version="1.2.3",
            build_id="privacy-test-build",
        )
        frontend_error = FrontendErrorModel(
            actor_hash=beta_hash,
            route="/",
            error_code="test_error",
            message="safe",
            plan_id="owned-plan-a",
            app_version="1.2.3",
            build_id="privacy-test-build",
        )
        owned_metric = BetaRequestMetricModel(
            request_id="owned-metric-request",
            endpoint="/api/plans/{plan_id}",
            method="GET",
            duration_ms=10.0,
            status_code=200,
            plan_id="owned-plan-a",
            app_version="1.2.3",
            build_id="privacy-test-build",
        )
        unrelated_metric = BetaRequestMetricModel(
            request_id="unrelated-metric-request",
            endpoint="/api/plans/{plan_id}",
            method="GET",
            duration_ms=11.0,
            status_code=200,
            plan_id="other-plan",
            app_version="1.2.3",
            build_id="privacy-test-build",
        )
        session.add_all(
            [
                feedback,
                unrelated_feedback,
                analytics,
                frontend_error,
                owned_metric,
                unrelated_metric,
            ]
        )
        evidence = CommunityEvidenceRepository(session).create(
            CommunityEvidenceSubmission(
                evidence_type="PRODUCT_MISSING_FROM_APP",
                anonymous_session_id=local_session_id,
                idempotency_key="privacy-evidence-request-0001",
                observed_at=now,
                product_name="Testpasta 500 g",
                note="Evidence fact must remain",
            )
        ).observation
        receipt = CommunityReceiptIngestionModel(
            actor_hash=community_hash,
            retailer="hemkop",
            status="PARSED",
            parser_name="test",
            raw_sha256="d" * 64,
            raw_retained=False,
            raw_discarded_at=now,
            retention_expires_at=now,
            purchase_observed_at=now,
            parsed_lines=[{"description": "Testpasta", "paid_price": "10.00"}],
            warnings=[],
        )
        session.add(receipt)
        session.commit()
        target_ids = {
            "feedback": feedback.id,
            "analytics": analytics.id,
            "frontend": frontend_error.id,
            "metric": owned_metric.id,
            "evidence": evidence.id,
            "receipt": receipt.id,
        }

    caplog.set_level(logging.INFO, logger="beta.request")
    client = TestClient(application)
    response = client.post(
        "/api/privacy/erase",
        json={"anonymous_session_id": local_session_id},
        headers={
            "Cookie": f"beta_session={owner_session_id}",
            "Origin": "http://testserver",
            "Sec-Fetch-Site": "same-origin",
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "beta_session=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert response.json() == {
        "plans_deleted": 2,
        "plan_revisions_deleted": 3,
        "feedback_deleted": 1,
        "analytics_events_deleted": 1,
        "frontend_errors_deleted": 1,
        "request_metrics_deleted": 1,
        "community_observations_unlinked": 1,
        "receipt_ingestions_unlinked": 1,
        "suppression_events_added": 8,
    }
    for secret in (local_session_id, beta_hash, community_hash, owner_hash):
        assert secret not in response.text
        assert all(secret not in record.message for record in caplog.records)

    metric_future = application.state.beta_last_metric_future
    if metric_future is not None:
        metric_future.result(timeout=2)
    with factory() as session:  # type: ignore[operator]
        assert session.get(BetaFeedbackModel, target_ids["feedback"]) is None
        assert session.get(ProductAnalyticsEventModel, target_ids["analytics"]) is None
        assert session.get(FrontendErrorModel, target_ids["frontend"]) is None
        assert session.get(BetaRequestMetricModel, target_ids["metric"]) is None
        assert session.scalar(
            select(BetaFeedbackModel).where(
                BetaFeedbackModel.actor_hash == unrelated_beta_hash
            )
        ) is not None
        assert session.scalar(
            select(BetaRequestMetricModel).where(
                BetaRequestMetricModel.request_id == "unrelated-metric-request"
            )
        ) is not None
        preserved_evidence = session.get(
            CommunityEvidenceObservationModel,
            target_ids["evidence"],
        )
        preserved_receipt = session.get(
            CommunityReceiptIngestionModel,
            target_ids["receipt"],
        )
        assert preserved_evidence is not None
        assert preserved_evidence.product_name == "Testpasta 500 g"
        assert preserved_evidence.note == "Evidence fact must remain"
        assert preserved_evidence.actor_hash != community_hash
        assert preserved_receipt is not None
        assert preserved_receipt.parsed_lines[0]["paid_price"] == "10.00"
        assert preserved_receipt.actor_hash != community_hash
        assert preserved_evidence.actor_hash != preserved_receipt.actor_hash
        suppressions = list(session.scalars(select(PrivacyErasureSuppressionModel)))
        assert len(suppressions) == 8
        assert all(row.action == "SUPPRESS_ON_RESTORE" for row in suppressions)
        assert all(
            local_session_id not in row.target_record_id
            and beta_hash not in row.target_record_id
            and community_hash not in row.target_record_id
            for row in suppressions
        )

    with sqlite3.connect(settings.plan_store_path) as connection:
        remaining_plans = connection.execute(
            "SELECT DISTINCT plan_id FROM consumer_plan_revisions ORDER BY plan_id"
        ).fetchall()
    assert remaining_plans == [("legacy-plan",), ("other-plan",)]

    repeated = client.post(
        "/api/privacy/erase",
        json={"anonymous_session_id": local_session_id},
        headers={"Cookie": f"beta_session={owner_session_id}"},
    )
    assert repeated.status_code == 200
    assert all(value == 0 for value in repeated.json().values())


def test_privacy_erasure_rejects_digests_cross_origin_and_is_rate_limited(
    tmp_path: Path,
) -> None:
    application, _, _ = _application(
        tmp_path,
        privacy_erasure_rate_limit_requests=1,
        privacy_erasure_network_rate_limit_requests=10,
    )
    client = TestClient(application)
    digest = "a" * 64

    rejected_digest = client.post(
        "/api/privacy/erase",
        json={"anonymous_session_id": digest},
        headers={"X-Anonymous-Session-ID": str(uuid4())},
    )
    assert rejected_digest.status_code == 422
    assert digest not in rejected_digest.text

    cross_origin = client.post(
        "/api/privacy/erase",
        json={"anonymous_session_id": str(uuid4())},
        headers={
            "Origin": "https://attacker.example",
            "Sec-Fetch-Site": "cross-site",
            "X-Anonymous-Session-ID": str(uuid4()),
        },
    )
    assert cross_origin.status_code == 403
    assert cross_origin.headers["X-Error-Code"] == "privacy_erasure_cross_origin"

    session_id = str(uuid4())
    accepted = client.post(
        "/api/privacy/erase",
        json={"anonymous_session_id": session_id},
        headers={"X-Anonymous-Session-ID": session_id},
    )
    limited = client.post(
        "/api/privacy/erase",
        json={"anonymous_session_id": session_id},
        headers={"X-Anonymous-Session-ID": session_id},
    )
    assert accepted.status_code == 200
    assert limited.status_code == 429
    assert limited.headers["Retry-After"]
