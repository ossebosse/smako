"""Injected failures prove capture, never the historical 500's cause."""
import json
import sqlite3
import time
from types import SimpleNamespace

import pytest
from app.api import plan as api
from app.config import Settings
from app.services import app_incidents
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient


@pytest.mark.parametrize("kind", ["unexpected", "handled"])
def test_owned_status_failure_retains_chain_without_secrets(monkeypatch, tmp_path, kind):
    from app import main
    settings = Settings(price_provider="mock", plan_store_path=tmp_path / "plans.sqlite3")
    monkeypatch.setattr(api, "get_settings", lambda: settings)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    from app.services.beta_observability import BetaRequestMiddleware
    app = FastAPI(lifespan=main.lifespan)
    app.add_middleware(BetaRequestMiddleware, settings_factory=lambda: settings)
    app.include_router(api.router)
    calls = []

    async def broken(*_):
        calls.append(True)
        from app.services.plan_jobs import report_stage
        report_stage("saving")
        try:
            raise RuntimeError("PRIVATE-TOKEN-AND-PLAN")
        except RuntimeError as exc:
            if kind == "handled":
                raise HTTPException(500, "generic") from exc
            raise TypeError("PRIVATE-COOKIE") from exc

    monkeypatch.setattr(api, "_run_admitted_plan", broken)
    with TestClient(app, raise_server_exceptions=False) as client:
        start = client.post("/api/plans", json={"recipes": 3, "servings": 2},
                            headers={"Prefer": "respond-async", "X-Request-ID": "accepted-test-123"})
        assert start.status_code == 202
        url = start.json()["status_url"]
        for _ in range(100):
            response = client.get(url, headers={"X-Request-ID": "status-test-456"})
            if response.status_code != 202:
                break
            time.sleep(.01)
        assert response.status_code == 500
        path = tmp_path / "app-incidents.json"
        assert path.exists(), "The original code loses the exception evidence"
        before = path.read_bytes()
        assert client.get(url, headers={"X-Anonymous-Session-ID": "another-owner-12345"}).status_code == 404
        assert path.read_bytes() == before
        for _ in range(3):
            assert client.get(url).status_code == 500
        index = json.loads(path.read_bytes())
        assert len(index["incidents"]) == 1
        row = index["incidents"][0]
        assert row["job_id"] == url.rsplit("/", 1)[1]
        assert row["start_request_id"] == "accepted-test-123"
        assert row["first_request_id"] == "status-test-456"
        assert row["job_outcome"] == "failed" and row["stage"] == "saving"
        assert row["occurrences"] == 4
        assert any(c["type"] == "RuntimeError" for c in row["exception"]["chain"])
        assert any(f["function"] == "broken" for c in row["exception"]["chain"] for f in c["frames"])
        assert "PRIVATE-" not in path.read_text()
        assert "another-owner" not in path.read_text()
        assert len(calls) == 1
        with sqlite3.connect(settings.plan_store_path) as db:
            assert db.execute("SELECT COUNT(*) FROM consumer_plan_revisions").fetchone()[0] == 0


def test_capture_disk_failure_preserves_original_failure(monkeypatch, tmp_path, caplog):
    settings = Settings(plan_store_path=tmp_path / "plans.sqlite3")
    request = SimpleNamespace(state=SimpleNamespace(request_id="request-test-123"),
        scope={}, method="GET", app=SimpleNamespace(state=SimpleNamespace()))
    def fail(*args):
        raise OSError("private path or key")
    monkeypatch.setattr(app_incidents, "atomic_write_bytes", fail)
    assert app_incidents.record_http_failure(request, settings, error=TypeError("private"),
        status=500, started_at="time", universe_id=None) is None
    assert "app_incident_write_failed type=OSError" in caplog.text
    assert "private" not in caplog.text


def test_bounded_index_and_read_only_reader(tmp_path):
    import runpy
    from pathlib import Path
    read_app_evidence = runpy.run_path(str(Path(__file__).parents[2] /
        "scripts/app_incident_status.py"))["read_app_evidence"]
    settings = Settings(plan_store_path=tmp_path / "plans.sqlite3")
    request = SimpleNamespace(state=SimpleNamespace(request_id="request-test-123"),
        scope={}, method="GET", app=SimpleNamespace(state=SimpleNamespace()))
    for number in range(70):
        app_incidents.record_http_failure(request, settings, error=None, status=500,
            started_at="time", universe_id=f"universe-{number}")
    path = tmp_path / "app-incidents.json"
    assert path.stat().st_size <= app_incidents.MAX_BYTES
    assert len(json.loads(path.read_bytes())["incidents"]) == 64
    db_path = tmp_path / "metrics.sqlite"
    with sqlite3.connect(db_path) as db:
        db.execute("CREATE TABLE beta_request_metrics(request_id,created_at,endpoint,method,"
                   "status_code,error_code,duration_ms,plan_id,price_universe_id,build_id)")
    before = path.read_bytes(), db_path.read_bytes()
    data = read_app_evidence(database=db_path, plan_store=settings.plan_store_path,
                             request_id="request-test-123")
    assert data["status"] == "observed"
    assert len(data["exception_evidence"]["incidents"]) == 20
    assert before == (path.read_bytes(), db_path.read_bytes())
