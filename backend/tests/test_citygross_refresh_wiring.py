"""City Gross municipal sources through ordinary build and publication wiring."""
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from grocery_data.app.services import citygross_municipal_job as job


async def test_every_ordinary_rebuild_reads_citygross_sources_without_mutating_base(
    tmp_path, monkeypatch,
):
    from app.services import production_price_universe_build as builder

    from grocery_data import __main__ as cli
    from grocery_data.app.services import coop_offer_job

    source = tmp_path / "base.sqlite"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE complete_base(id)")
        db.execute("INSERT INTO complete_base VALUES ('preserved')")
    seen, receipts = [], []

    async def build(database, *args, **kwargs):
        with closing(sqlite3.connect(database)) as db:
            assert db.execute("SELECT id FROM complete_base").fetchone()[0] == "preserved"
        seen.append(kwargs)
        return {"price_universe_id": "built", "snapshot_ids": ["original-source"]}

    expected = {"citygross_municipal_enabled": True, "citygross_sources": [
        {"database": "immutable-citygross-own", "snapshot_ids": ["original-source"],
         "inventory": {"municipality_code": "1280"}},
    ]}
    monkeypatch.setattr(builder, "build_city_price_universe", build)
    monkeypatch.setattr(coop_offer_job, "source_inputs", lambda **kwargs: {})
    monkeypatch.setattr(coop_offer_job, "record_build", lambda **kwargs: None)
    monkeypatch.setattr(job, "source_inputs", lambda **kwargs: expected)
    monkeypatch.setattr(job, "record_build", lambda **kwargs: receipts.append(kwargs))
    monkeypatch.setenv("ICA_STRUCTURED_OFFERS_ENABLED", "false")
    for _ in range(2):
        await cli._build_production_price_universe(
            database=source, city="Malmö", postal_code="21120", external_cache=None,
            output=tmp_path / "candidate.json", max_price_age_hours=48,
        )
    assert seen == [expected, expected]
    assert len(receipts) == 2
    assert all(r["city"] == "Malmö" for r in receipts)
    assert all(r["result"]["snapshot_ids"] == ["original-source"] for r in receipts)


@pytest.mark.parametrize(
    "failure", ["reload_rejected", "reload_unavailable", "publication_failed", "success"],
)
def test_ordinary_runner_records_citygross_publication_only_after_actual_reload(
    tmp_path, monkeypatch, failure,
):
    from backend.tests.test_production_deployment import (
        _configure_refresh_runner,
        _FakeArtifactStore,
    )
    from deploy.scripts import run_daily_refresh as runner
    from grocery_data.app.services.prepared_universe_activation import (
        ActivePreparedUniverseManifest,
    )

    now = datetime.now(UTC)
    store = _FakeArtifactStore()
    previous = ActivePreparedUniverseManifest(
        city="Lund", scope_id="city:lund", universe_id="base", built_at=now,
        activated_at=now, oldest_observed_at=now, snapshot_ids=("base-source",),
        product_count=1, canonical_index_count=1,
        artifact_file="artifacts/" + "a" * 64 + ".json", artifact_sha256="a" * 64,
        artifact_bytes=100,
    ).model_dump_json().encode()
    store.active = previous
    statuses = _configure_refresh_runner(monkeypatch, store, tmp_path)
    monkeypatch.setenv("DEMAND_REFRESH_ENABLED", "false")
    monkeypatch.setenv("CITYGROSS_MUNICIPAL_ENABLED", "true")
    monkeypatch.setenv("CITYGROSS_MUNICIPALITY_CODE", "1281")
    monkeypatch.setenv("CITYGROSS_MUNICIPAL_BUILD_CITY", "Lund")
    monkeypatch.setenv("CITYGROSS_MUNICIPAL_ROOT", str(tmp_path / "citygross"))
    root, config = job.configuration()
    path = job.location(root, config)
    job.write(path, {"selection": {"stores": [], "next_inventory_check": (
        now + timedelta(days=3)
    ).isoformat()}})
    job.record_build(city="Lund", result={
        "price_universe_id": "new", "snapshot_ids": ["citygross-snapshot"],
    })
    monkeypatch.setattr(
        runner, "_active_disk_universe_id",
        lambda *args, **kwargs: "new" if store.active == b"promoted-manifest" else "base",
    )
    if failure == "publication_failed":
        monkeypatch.setattr(
            runner.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1),
        )

    def reload():
        if failure == "reload_rejected":
            raise runner.RuntimeReloadRejected("injected")
        if failure == "reload_unavailable":
            raise runner.RuntimeReloadUnavailable("injected")
        return {"old_price_universe_id": "base", "new_price_universe_id": "new", "changed": True}

    monkeypatch.setattr(runner, "_reload_runtime", reload)
    code = runner.main()
    record = job.read(path)["publication"]
    assert bool(record.get("last_reload_at")) == (failure == "success")
    assert code == {
        "success": 0, "publication_failed": 1, "reload_rejected": 1, "reload_unavailable": 2,
    }[failure]
    if failure in {"publication_failed", "reload_rejected"}:
        assert store.active == previous
        assert not record.get("last_published_at")
    if failure == "reload_unavailable":
        assert record["last_published_at"] and not record.get("last_reload_at")
        assert record["status"] == "publication_or_reload_pending"
    assert statuses[-1]["exit_code"] == code


def test_persistent_municipal_selection_and_publication_deadline_survive_restart(tmp_path):
    now = datetime.now(UTC)
    environment = {
        "GROCERY_DATABASE_URL": "sqlite:///" + (tmp_path / "own.sqlite").as_posix(),
        "CITYGROSS_MUNICIPAL_ROOT": str(tmp_path / "citygross"),
        "CITYGROSS_MUNICIPAL_ENABLED": "true", "CITYGROSS_MUNICIPALITY_CODE": "1280",
    }
    root, config = job.configuration(environment)
    job.write(root / "config.json", config)
    state = {"selection": {
        "next_inventory_check": (now + timedelta(days=3)).isoformat(), "stores": [{
            "store_id": "verified-from-inventory", "selected": True,
            "next_fetch_at": (now + timedelta(hours=35)).isoformat(),
        }],
    }, "approved": {"verified-from-inventory": [{
        "sha256": "a" * 64, "snapshots": ["original"], "observed_at": now.isoformat(),
    }]}}
    job.write(job.location(root, config), state)
    plan = job.source_plan(environment=environment, now=now)
    state["publication"] = {"reloaded_fingerprint": plan["fingerprint"], "status": "reloaded"}
    job.write(job.location(root, config), state)
    restart = {k: v for k, v in environment.items() if k not in {
        "CITYGROSS_MUNICIPAL_ENABLED", "CITYGROSS_MUNICIPALITY_CODE",
    }}
    persisted = job.source_plan(environment=restart, now=now + timedelta(hours=34))
    assert persisted["enabled"] and not persisted["work_due"]
    assert persisted["external_price_requests"] == 0
    assert persisted["fingerprint"] == plan["fingerprint"]
    due = job.source_plan(environment=restart, now=now + timedelta(hours=35))
    assert due["due_store_ids"] == ["verified-from-inventory"]
    expired = job.source_plan(environment=restart, now=now + timedelta(hours=48))
    assert expired["fingerprint"] != plan["fingerprint"]
    assert expired["publication_due"] and expired["external_price_requests"] == 0
    assert job.read(job.location(root, config))["approved"] == state["approved"]


def test_invalid_optional_citygross_configuration_does_not_break_base(tmp_path):
    environment = {
        "CITYGROSS_MUNICIPAL_ENABLED": "true", "CITYGROSS_MUNICIPALITY_CODE": "not-a-code",
        "CITYGROSS_MUNICIPAL_ROOT": str(tmp_path),
    }
    assert not job.source_plan(environment=environment)["work_due"]
    assert job.source_inputs(city="Lund", environment=environment)[
        "citygross_source_errors"
    ][0]["status"] == "optional_configuration_error"


def test_ordinary_demand_tick_uses_municipal_source_timer_and_performs_no_network(
    tmp_path, monkeypatch,
):
    import socket

    from deploy.scripts import run_daily_refresh as runner
    from grocery_data.app.services import coop_offer_job

    now = datetime.now(UTC)
    database = tmp_path / "base.sqlite"
    # Municipal source data live in their own approved databases. The ordinary
    # planner must not invent a missing base observation by querying this DB.
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE independent_base_marker(value)")
    artifact = tmp_path / "artifact.json"
    artifact.write_text(json.dumps({"stores": [{
        "store_id": "context:verified-citygross", "chain": "citygross",
        "source_provenance": {"source_provider": "own", "source_channel": "catalog",
                              "provider_store_id": "official-source-id"},
    }]}))

    class Store:
        def __init__(self, *args):
            pass

        def read_active(self, *args):
            return SimpleNamespace(universe_id="published")

        def resolve_active_artifact(self, *args, **kwargs):
            return artifact

    source_due = False

    def municipal_plan(**kwargs):
        return {"enabled": True, "fingerprint": "same-original-snapshot", "work_due": source_due,
                "stores": [{"next_fetch_at": (now + timedelta(hours=35)).isoformat()}]}

    monkeypatch.setattr(runner, "PreparedUniverseArtifactStore", Store)
    monkeypatch.setattr(job, "source_plan", municipal_plan)
    monkeypatch.setattr(coop_offer_job, "source_plan", lambda **kwargs: {
        "enabled": False, "fingerprint": "disabled-coop", "work_due": False, "stores": [],
    })

    def forbidden_network(*args, **kwargs):
        raise AssertionError("local demand inspection must not perform a network request")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)
    state_path = tmp_path / "demand.json"
    environment = {
        "PRICE_UNIVERSE_CACHE_ROOT": str(tmp_path / "pu"), "REFRESH_CITY": "Malmö",
        "GROCERY_DATABASE_URL": "sqlite:///" + database.as_posix(),
        "DEMAND_REFRESH_STATE_PATH": str(state_path),
    }
    initial = runner.demand_refresh_plan(now=now, environment=environment)
    state_path.write_text(json.dumps(initial["state"] | {
        "published_sources": initial["source_fingerprint"], "last_success_at": now.isoformat(),
    }))
    idle = runner.demand_refresh_plan(now=now, environment=environment)
    assert not idle["work_due"] and idle["due_sources"] == [] and idle["sources"] == {}
    assert idle["external_price_requests"] == 0
    source_due = True
    due = runner.demand_refresh_plan(now=now, environment=environment)
    assert due["work_due"] and due["reasons"] == ["citygross_municipal_work_due"]
    assert due["external_price_requests"] == 0
