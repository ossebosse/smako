from types import SimpleNamespace

import pytest
from app.main import warm_preparation_status
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.parametrize("phase", ["not_run", "scheduled", "running", "partial", "failed"])
def test_incomplete_preparation_cannot_certify_a_warm_probe(monkeypatch, phase):
    application, client = _client(monkeypatch)
    application.state.source_facts_prewarm = {"status": phase, "library": {"status": "ready"},
        "universes": [{"universe_id": "lund", "status": "ready"},
                      {"universe_id": "malmo", "status": "ready"}]}
    response = client.get("/ready/preparation")
    assert response.status_code == 202
    assert response.json()["status"] == "not_ready"
    assert response.json()["preparation_status"] == phase


def _client(monkeypatch):
    monkeypatch.setattr(GLOBAL_PREPARED_PRICE_UNIVERSES, "active_universes", lambda: [
        SimpleNamespace(universe=SimpleNamespace(universe_id=name)) for name in ("lund", "malmo")])
    application = FastAPI()
    application.state.beta_settings = SimpleNamespace(build_id="warm-test")
    application.add_api_route("/ready/preparation", warm_preparation_status)
    return application, TestClient(application)


def test_warm_readiness_binds_both_active_universes_and_omits_error_details(monkeypatch):
    application, client = _client(monkeypatch)
    assert client.get("/ready/preparation").status_code == 202
    report = {"status": "ready", "library": {"status": "ready"},
        "error": "private internal exception/path", "universes": [
            {"universe_id": "old-lund", "status": "ready"},
            {"universe_id": "malmo", "status": "ready"}]}
    application.state.source_facts_prewarm = report
    response = client.get("/ready/preparation")
    assert response.status_code == 202
    report["universes"][0] = {"universe_id": "lund", "status": "ready"}
    response = client.get("/ready/preparation")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {"status": "ready", "preparation_status": "ready",
        "library_status": "ready", "build_id": "warm-test", "universes": [
            {"universe_id": "lund", "status": "ready"},
            {"universe_id": "malmo", "status": "ready"}]}
    report["library"]["status"] = "failed"
    assert client.get("/ready/preparation").status_code == 202


def test_empty_active_scope_never_counts_as_warm(monkeypatch):
    application, client = _client(monkeypatch)
    application.state.source_facts_prewarm = {"status": "ready", "library": {"status": "ready"}}
    monkeypatch.setattr(GLOBAL_PREPARED_PRICE_UNIVERSES, "active_universes", list)
    assert client.get("/ready/preparation").status_code == 202
