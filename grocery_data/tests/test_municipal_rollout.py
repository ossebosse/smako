"""Municipal orchestration over existing leases, source policies and journals."""
import json
import os
from datetime import UTC, datetime, timedelta

import pytest

from deploy.scripts import run_daily_refresh as runner
from grocery_data.app.services.area_membership import collection_area
from grocery_data.app.services.municipal_rollout import (
    add_municipality,
    municipal_environment,
    refresh_scopes,
    scoped_environment,
)


@pytest.fixture
def registry(tmp_path, monkeypatch):
    env = {
        "MUNICIPAL_COLLECTION_SCOPE_PATH": str(tmp_path / "municipalities.json"),
        "GROCERY_DATABASE_URL": "sqlite:///" + (tmp_path / "grocery.sqlite").as_posix(),
        "PRICE_UNIVERSE_CACHE_ROOT": str(tmp_path / "price-universes"),
        "REFRESH_CITY": "Lund", "REFRESH_MUNICIPALITY_CODE": "1281",
        "REFRESH_POSTAL_CODE": "22350", "COOP_MUNICIPALITY_CODE": "1281",
        "COOP_MUNICIPAL_OFFERS_ENABLED": "true", "COOP_XTRA_OFFERS_ENABLED": "true",
        "COOP_ONLINE_CONTEXT_IDS": "730400", "COOP_ALLOW_FULL_CRAWL": "true",
        "HEMKOP_MUNICIPAL_OFFERS_ENABLED": "true", "LIDL_MUNICIPAL_ENABLED": "true", "LIDL_MUNICIPALITY_CODE": "1281",
        "PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS": "own:coop:730400,own:hemkop:4123",
    }
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    add_municipality("1280", "21120", environment=env, persist=True)
    return env


def test_additive_idempotent_registry_and_exact_chain_bindings(registry):
    from grocery_data.app.services.coop_offer_job import configuration
    from grocery_data.app.services.willys_municipal_scope import load_build_scopes

    first = add_municipality("1280", "21120", environment=registry)
    assert first == add_municipality("1280", "21120", environment=registry, persist=True)
    assert load_build_scopes() == {"22350": "1281", "21120": "1280"}
    scopes = {s["municipality_code"]: s for s in refresh_scopes(registry)}
    assert collection_area("Lund", environment=registry).municipality_code == "1281"
    assert collection_area("Malmö", environment=registry).municipality_code == "1280"
    assert scopes["1281"]["required_context_ids"] == ["own:coop:730400", "own:hemkop:4123"]
    malmo = scoped_environment(scopes["1280"], registry)
    assert malmo["COOP_ONLINE_CONTEXT_IDS"] == "730400"
    assert malmo["PRICE_UNIVERSE_REQUIRED_CONTEXT_IDS"] == ""
    assert configuration(malmo)[1]["municipality_code"] == "1280"
    assert "1280" in malmo["DEMAND_REFRESH_STATE_PATH"]
    with pytest.raises(ValueError, match="current operation"):
        collection_area("Lund", environment=malmo)
    with pytest.raises(ValueError, match="match"):
        configuration(registry | {"REFRESH_CITY": "Malmö"})
    with pytest.raises(ValueError, match="unique"):
        add_municipality("1480", "21120", environment=registry, persist=True)
    assert len(refresh_scopes(registry)) == 2
    with pytest.raises(ValueError):
        add_municipality("../bad", "12345", environment=registry, persist=True)


def test_context_restores_environment_on_failed_scope(registry):
    before = dict(os.environ)
    malmo = next(s for s in refresh_scopes() if s["municipality_code"] == "1280")
    with pytest.raises(RuntimeError), municipal_environment(malmo):
        assert os.environ["REFRESH_CITY"] == "Malmö"
        raise RuntimeError("failed municipal refresh")
    assert dict(os.environ) == before


def test_third_municipality_uses_registered_key_without_new_hardcoded_city(registry):
    from grocery_data import __main__ as cli
    from grocery_data.app.api.geography import resolve_postal_scope
    from grocery_data.app.domain import Chain

    add_municipality("1480", "41110", environment=registry, persist=True)
    scopes = refresh_scopes(registry)
    assert len(scopes) == 3
    assert collection_area("Göteborg", environment=registry).municipality_code == "1480"
    assert resolve_postal_scope("41110").resolved_city == "Göteborg"
    assert resolve_postal_scope("41111").resolved_city is None
    goteborg = next(s for s in scopes if s["municipality_code"] == "1480")
    with municipal_environment(goteborg):
        targets, _skipped = cli._collect_all_plan(["Göteborg"], selected_chains=frozenset({Chain.HEMKOP}))
        assert not targets  # Exact municipal context planner owns this work.


def test_adoption_preserves_enabled_sources_in_existing_durable_configuration(tmp_path):
    env = {"MUNICIPAL_COLLECTION_SCOPE_PATH": str(tmp_path / "registry.json"),
           "GROCERY_DATABASE_URL": "sqlite:///" + (tmp_path / "grocery.sqlite").as_posix()}
    for folder in ("coop-municipal-offers", "lidl-municipal"):
        root = tmp_path / folder
        root.mkdir()
        (root / "config.json").write_text(json.dumps({"enabled": True, "xtra_enabled": True,
            "municipality_code": "1281", "city": "Lund"}))
    result = add_municipality("1280", "21120", environment=env)
    assert {"coop", "xtra", "lidl", "willys"}.issubset(result["refresh_scopes"]["1281"]["sources"])


def test_first_manifest_bootstrap_and_persistent_backoff(registry, monkeypatch, tmp_path):
    malmo = next(s for s in refresh_scopes() if s["municipality_code"] == "1280")
    commands = []
    monkeypatch.setattr(runner, "_run_locked", lambda *a, **k: commands.append(k["command"]) or 1)
    monkeypatch.setattr(runner, "_write_status", lambda value: None)
    with municipal_environment(malmo):
        now = datetime.now(UTC)
        plan = runner.demand_refresh_plan(now=now)
        assert plan["bootstrap"] and plan["work_due"]
        assert runner._run_demand_locked(object(), started_at=now) == 1
        assert len(commands) == 1
        assert commands[0][commands[0].index("--city") + 1] == "Malmö"
        assert not runner.demand_refresh_plan(now=now + timedelta(minutes=1))["work_due"]
        assert runner.demand_refresh_plan(now=now + timedelta(minutes=16))["work_due"]
    assert runner.demand_refresh_plan(now=now, environment=registry)["work_due"]


def test_shared_lease_covers_both_scopes_and_failure_does_not_skip_next(registry, monkeypatch):
    events, statuses = [], []

    class Lease:
        def acquire(self): events.append("acquire")
        def release(self): events.append("release")

    def refresh(lock, **kwargs):
        events.append(os.environ["REFRESH_CITY"])
        if os.environ["REFRESH_CITY"] == "Lund":
            raise ValueError("failed source")
        return 0

    monkeypatch.setenv("DEMAND_REFRESH_ENABLED", "true")
    monkeypatch.setattr(runner, "_operations_lock", Lease)
    monkeypatch.setattr(runner, "_run_demand_locked", refresh)
    monkeypatch.setattr(runner, "_write_status", statuses.append)
    # Registry JSON is sorted on disk, so force an order to exercise failure first.
    from grocery_data.app.services import municipal_rollout
    scopes = sorted(refresh_scopes(), key=lambda s: s["city"])
    monkeypatch.setattr(municipal_rollout, "refresh_scopes", lambda: scopes)
    assert runner.main() == 1
    assert events == ["acquire", "Lund", "Malmö", "release"]
    assert statuses[-1]["municipalities"][0]["error_type"] == "ValueError"
    assert os.environ["REFRESH_CITY"] == "Lund"


def test_relay_keeps_per_municipality_workspaces_and_receipts(tmp_path):
    from grocery_data.local_relay import run_municipalities
    from grocery_data.relay_config import RelayTransport

    roots = []
    def run_scope(root, **kwargs):
        roots.append(root)
        code = json.loads((root / "source-scope.json").read_bytes())["municipality_code"]
        assert root.name == "municipality-" + code
        return int(code == "1280")

    assert run_municipalities(tmp_path, RelayTransport(), scopes=[
        {"municipality_code": "1280"}, {"municipality_code": "1281"}], run_scope=run_scope) == 1
    assert len(roots) == 2 and roots[0] != roots[1]
    assert (tmp_path / "municipal-relay-status.json").exists()
