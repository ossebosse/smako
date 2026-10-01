import json
import sqlite3

from app.config import get_settings
from app.recovery import app
from app.services.beta_observability import pseudonymous_actor
from app.services.plan_store import PlanStore
from fastapi.testclient import TestClient


def test_lossless_owned_read_revisions_and_denied_operations(tmp_path, monkeypatch):
    path = tmp_path / "plans.sqlite"
    monkeypatch.setenv("PLAN_STORE_PATH", str(path))
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "test-recovery-" * 4)
    PlanStore(path)
    owner = pseudonymous_actor("creator-session-12345678", get_settings())
    payload = {
        "future_field": {"deposit": 3.25, "conditional_choice": ["a", "b"]},
        "nutrition_status": "unknown",
        "quantity": 0.73,
    }
    with sqlite3.connect(path) as db:
        for revision in (1, 2):
            db.execute(
                "INSERT INTO consumer_plan_revisions (plan_id,revision,parent_revision,created_at,operation,request_json,response_json,diversity_mode,diet_preference,max_stores,meal_count,servings,owner_actor_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    "test-plan",
                    revision,
                    revision - 1 or None,
                    "2026-10-01T10:00:00+00:00",
                    "created",
                    "{}",
                    json.dumps({**payload, "revision_marker": revision}),
                    "free",
                    "none",
                    2,
                    5,
                    4,
                    owner,
                ),
            )
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    before = path.read_bytes()
    with TestClient(app) as client:
        headers = {"X-Anonymous-Session-ID": "creator-session-12345678"}
        response = client.get("/api/plans/test-plan", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["plan"] == {**payload, "revision_marker": 2}
        assert (
            client.get("/api/plans/test-plan?revision=1", headers=headers).json()["plan"][
                "revision_marker"
            ]
            == 1
        )
        assert (
            client.get(
                "/api/plans/test-plan",
                headers={"X-Anonymous-Session-ID": "different-session-12345678"},
            ).status_code
            == 403
        )
        assert client.get("/api/plans/missing", headers=headers).status_code == 404
        for route in (
            "/api/plans",
            "/api/plan",
            "/api/plans/test-plan/replace-product",
            "/api/personal/plans/test-plan/actions",
            "/api/internal/price-universe/reload",
            "/api/account/migrate-guest",
        ):
            r = client.post(route, json={})
            assert r.status_code == 503 and r.json()["code"] == "recovery_read_only"
        assert client.get("/ready").json()["planning"] is False
    assert path.read_bytes() == before


def test_import_and_refresh_refuse_recovery_mode(monkeypatch, capsys):
    from deploy.scripts import run_daily_refresh
    from grocery_data import source_cli

    monkeypatch.setenv("SMAKO_RECOVERY_READ_ONLY", "true")
    assert source_cli.main() == 3
    assert run_daily_refresh.main() == 3
    assert capsys.readouterr().out.count("recovery_read_only") == 2


def test_uncheckpointed_wal_refuses_reading_instead_of_losing_revisions(tmp_path, monkeypatch):
    path = tmp_path / "plans.sqlite"
    monkeypatch.setenv("PLAN_STORE_PATH", str(path))
    monkeypatch.setenv("APP_ENV", "development")
    PlanStore(path)
    db = sqlite3.connect(path)
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("CREATE TABLE checkpoint_probe (value TEXT)")
        db.commit()
        with TestClient(app) as client:
            assert client.get("/ready").status_code == 503
            assert client.get("/api/plans/missing").status_code == 503
            db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            assert client.get("/ready").status_code == 200
            assert client.get("/api/plans/missing").status_code == 404
    finally:
        db.close()
