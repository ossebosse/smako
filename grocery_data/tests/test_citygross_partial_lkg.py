"""Injected transport/state regression: partial campaigns cannot replace valid full LKG."""
import json
import sqlite3
from datetime import UTC, datetime, timedelta

from grocery_data.app.services import citygross_municipal_job as job
from grocery_data.tests.test_citygross_municipality import inventory


async def test_partial_success_preserves_full_lkg_retry_then_expires_and_recovers(tmp_path, monkeypatch):
    from grocery_data.scripts import collect_citygross_municipality as collector

    started = datetime(2026, 9, 23, 9, tzinfo=UTC)
    partial_at = started + timedelta(hours=1, seconds=1)
    expired_full_at = started + timedelta(hours=49)
    recovered_at = expired_full_at + timedelta(minutes=15)
    seed = tmp_path / "captured-inventory.json"
    seed.write_text(json.dumps(inventory()), encoding="utf-8")
    environment = {"CITYGROSS_MUNICIPAL_ROOT": str(tmp_path / "state"),
        "CITYGROSS_MUNICIPAL_ENABLED": "true", "CITYGROSS_MUNICIPALITY_CODE": "1280",
        "CITYGROSS_MUNICIPAL_INVENTORY": str(seed)}
    calls = []
    fixtures = [
        ("full-1", "full_online_catalog", started),
        ("offers-2", "offers_only", partial_at),
        ("full-3", "full_online_catalog", recovered_at),
    ]

    async def injected_collect(captured_inventory, selected, output):
        assert captured_inventory["selected_store_ids"] == ["3211"]
        assert selected == {"3211"}
        snapshot, coverage, observed = fixtures[len(calls)]
        calls.append(snapshot)
        output.mkdir()
        database = output / ("offers.sqlite" if coverage == "offers_only" else "own.sqlite")
        with sqlite3.connect(database) as db:
            db.executescript("CREATE TABLE catalog_snapshots(id,is_active,state,coverage);"
                             "CREATE TABLE source_products(catalog_snapshot_id,chain,store_external_id,fetched_at);")
            db.execute("INSERT INTO catalog_snapshots VALUES (?,1,'promoted',?)", (snapshot, coverage))
            db.execute("INSERT INTO source_products VALUES (?,'citygross','3211',?)",
                       (snapshot, observed.isoformat()))
        return {"stores": [{"store_id": "3211", "status": "success", "coverage": coverage,
            "resolved_database": str(database), "observed_at": "2099-01-01T00:00:00Z",
            "full_catalog_outcome": {"status": "failed", "error_type": "InjectedTimeout"}
                if coverage == "offers_only" else None,
            "windows": [{"valid_from": "2026-09-21", "valid_to": "2026-10-04"}]}]}

    monkeypatch.setattr(collector, "collect", injected_collect)
    await job.run_source_job(environment=environment, now=started)
    root, config = job.configuration(environment)
    state_path = job.location(root, config)
    first = job.read(state_path)
    original_refs = first["approved"]["3211"]
    assert original_refs[0]["observed_at"] == started.isoformat()

    # Explicit scheduler fault injection requests an early refresh. Source
    # observations, snapshots, bytes and approval evidence are not altered.
    next(r for r in first["selection"]["stores"] if r["selected"])["next_fetch_at"] = partial_at.isoformat()
    job.write(state_path, first)
    await job.run_source_job(environment=environment, now=partial_at)
    partial = job.read(state_path)
    assert partial["approved"]["3211"] == original_refs
    retained_offer = partial["partial_approved"]["3211"][0]
    assert retained_offer["coverage"] == "offers_only"
    assert retained_offer["observed_at"] == partial_at.isoformat()
    selection = next(r for r in partial["selection"]["stores"] if r["selected"])
    assert selection["status"] == "partial_offers_retained_full_lkg"
    assert selection["failed_attempts"] == 1
    assert selection["last_success"] == started.isoformat()
    assert datetime.fromisoformat(selection["next_fetch_at"]) == partial_at + timedelta(minutes=15)

    restarted_environment = {"CITYGROSS_MUNICIPAL_ROOT": str(root)}
    assert job.configuration(restarted_environment)[1] == config
    inputs = job.source_inputs(city="Malmö", environment=restarted_environment, now=partial_at)
    assert [s["snapshot_ids"] for s in inputs["citygross_sources"]] == [["full-1"]]
    assert (await job.run_source_job(environment=restarted_environment,
                                   now=partial_at + timedelta(minutes=1)))["status"] == "not_due"
    assert calls == ["full-1", "offers-2"]

    # At 49 h the full catalog is expired; the independently captured partial
    # source is still 47:59:59 old. Exactly one source is selected for the store.
    inputs = job.source_inputs(city="Malmö", environment=restarted_environment, now=expired_full_at)
    assert [s["snapshot_ids"] for s in inputs["citygross_sources"]] == [["offers-2"]]
    assert inputs["citygross_sources"][0]["store_ids"] == ["3211"]
    assert job.read(state_path)["approved"]["3211"] == original_refs
    assert job.source_plan(environment=restarted_environment, now=partial_at)["fingerprint"] != (
        job.source_plan(environment=restarted_environment, now=expired_full_at)["fingerprint"])
    assert calls == ["full-1", "offers-2"]  # Clock checks made no collector/network calls.

    await job.run_source_job(environment=restarted_environment, now=recovered_at)
    recovered = job.read(state_path)
    assert recovered["approved"]["3211"][0]["snapshots"] == ["full-3"]
    assert recovered["approved"]["3211"][0]["observed_at"] == recovered_at.isoformat()
    assert not recovered["partial_approved"].get("3211")
    selection = next(r for r in recovered["selection"]["stores"] if r["selected"])
    assert selection["failed_attempts"] == 0
    assert selection["last_success"] == recovered_at.isoformat()
    assert [s["snapshot_ids"] for s in job.source_inputs(city="Malmö", environment=restarted_environment,
            now=recovered_at)["citygross_sources"]] == [["full-3"]]
    assert calls == ["full-1", "offers-2", "full-3"]
