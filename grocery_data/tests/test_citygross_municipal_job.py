"""Durable City Gross state with captured inventory and explicit fake transport."""
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from grocery_data.app.services import citygross_municipal_job as job
from grocery_data.tests.test_citygross_municipality import inventory

NOW = datetime(2026, 9, 23, 9, tzinfo=UTC)


@pytest.fixture
def env(tmp_path):
    seed = tmp_path / "inventory.json"
    seed.write_text(json.dumps(inventory()), encoding="utf8")
    return {"CITYGROSS_MUNICIPAL_ROOT": str(tmp_path / "durable"),
            "CITYGROSS_MUNICIPAL_ENABLED": "true", "CITYGROSS_MUNICIPALITY_CODE": "1280",
            "CITYGROSS_MUNICIPAL_INVENTORY": str(seed)}


async def test_retained_reference_restart_failure_backoff_expiry_recovery(env, monkeypatch):
    from grocery_data.scripts import collect_citygross_municipality as collector

    calls, mode = [], "success"

    async def collect(inv, selected, output):
        calls.append(sorted(selected))
        assert inv["selected_store_ids"] == ["3211"]
        if mode == "failure":
            return {"stores": [{"store_id": "3211", "status": "failed", "error_type": "TimeoutError"}]}
        output.mkdir()
        database = output / "own.sqlite"
        with sqlite3.connect(database) as db:
            db.executescript("CREATE TABLE catalog_snapshots(id,is_active,state,coverage); "
                             "CREATE TABLE source_products(catalog_snapshot_id,chain,store_external_id,fetched_at);")
            db.execute("INSERT INTO catalog_snapshots VALUES (?,1,'promoted','full_online_catalog')", (str(len(calls)),))
            db.execute("INSERT INTO source_products VALUES (?,'citygross','3211',?)", (str(len(calls)), NOW.isoformat()))
        return {"stores": [{"store_id": "3211", "status": "success",
                            "resolved_database": str(database), "observed_at": "2099-01-01T00:00:00Z"}]}

    monkeypatch.setattr(collector, "collect", collect)
    await job.run_source_job(environment=env, now=NOW)
    root, config = job.configuration(env)
    path = job.location(root, config)
    first = job.read(path)
    assert first["approved"]["3211"][0]["observed_at"] == NOW.isoformat()
    assert len(first["selection"]["stores"]) == 38
    assert len(job.source_inputs(city="Malmö", environment=env)["citygross_sources"]) == 1
    assert job.source_inputs(city="Lund", environment=env) == {}
    restarted = {"CITYGROSS_MUNICIPAL_ROOT": str(root)}
    assert job.configuration(restarted)[1] == config
    assert (await job.run_source_job(environment=restarted, now=NOW + timedelta(hours=1)))["status"] == "not_due"
    assert calls == [["3211"]]
    mode = "failure"
    failed_at = NOW + timedelta(hours=35)
    await job.run_source_job(environment=restarted, now=failed_at)
    failed = job.read(path)
    assert failed["approved"] == first["approved"]
    selected = next(r for r in failed["selection"]["stores"] if r["selected"])
    assert selected["last_success"] == NOW.isoformat()
    assert datetime.fromisoformat(selected["next_fetch_at"]) == failed_at + timedelta(minutes=15)
    assert job.source_plan(environment=restarted, now=NOW)["fingerprint"] != job.source_plan(
        environment=restarted, now=NOW + timedelta(hours=49))["fingerprint"]
    mode = "success"
    await job.run_source_job(environment=restarted, now=failed_at + timedelta(minutes=16))
    assert job.read(path)["approved"] != first["approved"]
    assert job.read(path)["approved"]["3211"][0]["observed_at"] == NOW.isoformat()


async def test_zero_city_persists_without_borrowed_store(env, tmp_path, monkeypatch):
    from grocery_data.scripts import collect_citygross_municipality as collector

    seed = tmp_path / "zero.json"
    seed.write_text(json.dumps(inventory("1281")), encoding="utf8")
    env.update(CITYGROSS_MUNICIPALITY_CODE="1281", CITYGROSS_MUNICIPAL_INVENTORY=str(seed))

    async def forbidden(*args):
        raise AssertionError("zero municipality must not request prices")

    monkeypatch.setattr(collector, "collect", forbidden)
    result = await job.run_source_job(environment=env, now=NOW)
    assert result["selected_store_ids"] == []
    assert result["outcomes"] == {}
    assert job.source_inputs(city="Lund", environment=env)["citygross_sources"] == []
    assert (await job.run_source_job(environment=env, now=NOW + timedelta(hours=1)))["external_price_requests"] == 0


def test_new_registry_observation_does_not_change_exact_source_binding():
    inv = inventory()
    previous = job.update_selection(inv, {"3211": {"status": "success", "observed_at": NOW.isoformat()}}, now=NOW)
    for row in inv["stores"]:
        for source in row["store"]["source_fields"]["discovery_sources"]:
            source["observed_at"] = "2026-09-24T09:00:00Z"
    # Official evidence validator rejects arbitrary modified rows. Rebuild from
    # identical official payloads with a new fetch time instead of trusting flags.
    from grocery_data.app.domain import RawBatch
    from grocery_data.tests.test_citygross_municipality import RAW
    raw = RawBatch.model_validate(RAW.model_dump())
    raw = raw.model_copy(update={"documents": tuple(d.model_copy(update={"fetched_at": NOW + timedelta(hours=1)}) for d in raw.documents)})
    refreshed = inventory(raw=raw)
    current = job.update_selection(refreshed, previous=previous, now=NOW + timedelta(hours=1))
    before = next(r for r in previous["stores"] if r["selected"])
    after = next(r for r in current["stores"] if r["selected"])
    assert before["source_signature"] == after["source_signature"]
    assert after["last_success"] == NOW.isoformat() and not after["due"]


@pytest.mark.parametrize("own_only", [True, False])
async def test_ordinary_refresh_requires_federated_cache_unless_explicit_own_only(
    tmp_path, monkeypatch, own_only,
):
    from grocery_data import __main__ as cli
    from grocery_data.tests.test_managed_refresh_cli import (
        _args,
        _collection,
        _patch_managed_runtime,
        _settings,
        _UniverseStore,
    )

    builds = []
    emitted = _patch_managed_runtime(monkeypatch, tmp_path, store=_UniverseStore(),
        collection=_collection(["Malmö"]), build_calls=builds)
    settings = _settings(tmp_path)
    settings.own_sources_only = own_only
    monkeypatch.setattr(cli.GroceryDataSettings, "from_env", staticmethod(lambda: settings))
    args = _args(tmp_path, ["Malmö"])
    args.no_external_refresh = True
    code = await cli._daily_refresh(args)
    assert bool(builds) is own_only
    assert code == (0 if own_only else 1)
    report = emitted[0]["external_provider"][0]
    assert report["provider_requests"] == 0
    if own_only:
        assert report["reason"] == "explicit_own_sources_only"


def test_legacy_daily_citygross_collection_is_replaced_only_for_configured_city(env, monkeypatch):
    from grocery_data import __main__ as cli
    from grocery_data.app.domain import Chain

    for key, value in env.items():
        monkeypatch.setenv(key, value)
    targets, skipped = cli._collect_all_plan(["Malmö"], selected_chains=frozenset({Chain.CITY_GROSS}))
    assert not targets
    assert skipped[0]["status"] == "not_applicable"
    assert skipped[0]["reason"] == "municipal City Gross job owns exact source selection"
