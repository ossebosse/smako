"""Durable lifecycle with retained real source responses; no live price claims."""
import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from grocery_data.app.services import coop_offer_job as job
from grocery_data.tests.test_coop_municipality import inventory

NOW = datetime(2026, 9, 22, 10, tzinfo=UTC)


@pytest.fixture
def env(tmp_path):
    inv = inventory("1281", "Lund")
    inv["stores"] = [r for r in inv["stores"] if r["store"]["external_id"] in {"3839", "3658"}]
    seed = tmp_path / "seed.json"
    seed.write_text(json.dumps(inv), encoding="utf8")
    return {"COOP_MUNICIPAL_OFFERS_ROOT": str(tmp_path / "durable"),
            "COOP_MUNICIPAL_OFFERS_ENABLED": "true", "COOP_MUNICIPALITY_CODE": "1281",
            "COOP_MUNICIPAL_INVENTORY": str(seed), "REFRESH_CITY": "Lund"}


def closed_source(path, identity, snapshot="snapshot-1"):
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE catalog_snapshots(id,is_active,state,coverage); CREATE TABLE source_products(catalog_snapshot_id,chain,store_external_id);")
        db.execute("INSERT INTO catalog_snapshots VALUES (?,1,'promoted','offers_only')", (snapshot,))
        db.execute("INSERT INTO source_products VALUES (?,'coop',?)", (snapshot, identity))


async def test_restart_no_due_failure_expiry_recovery_and_withdrawal(env, monkeypatch):
    from grocery_data.scripts import collect_coop_physical_offers as collector
    calls = []
    mode = "success"
    async def collect(inv, selected, output):
        calls.append(sorted(selected))
        output.mkdir()
        (output / "sources").mkdir()
        if mode == "failure":
            return {"stores": [{"store_id": "3839", "status": "failed", "error_type": "TimeoutError"}]}
        closed_source(output / "own.sqlite", "3839", "snapshot-" + str(len(calls)))
        parsed = {"products": [] if mode == "empty" else [{"offers": [{"valid_from": "2026-09-21", "valid_to": "2026-09-23"}]}], "failures": []}
        job.write(output / "sources/3839-extracted.json", parsed)
        return {"stores": [{"store_id": "3839", "status": "rejected" if mode == "empty" else "partial_candidate",
            "observed_at": NOW.isoformat(), "source_hash": "source-evidence", "qualification": {"shared_blockers": []}}]}
    monkeypatch.setattr(collector, "collect", collect)
    await job.run_offer_job(environment=env, now=NOW)
    root, config = job.configuration(env)
    path = job.location(root, config)
    first = job.read(path)
    assert set(first["approved"]) == {"3839"}
    assert len(job.source_inputs(city="Lund", environment=env)["coop_offer_sources"]) == 1
    # Restart needs only the persisted root, not the developer seed or flags.
    restarted = {"COOP_MUNICIPAL_OFFERS_ROOT": str(root)}
    assert job.configuration(restarted)[1] == config
    assert (await job.run_offer_job(environment=restarted, now=NOW + timedelta(hours=1)))["status"] == "not_due"
    assert len(calls) == 1
    assert job.read(path)["approved"] == first["approved"]
    assert job.read(path)["selection"] == first["selection"]
    # A failed refresh retains only source references; it cannot refresh their age.
    mode = "failure"
    later = NOW + timedelta(hours=36)
    await job.run_offer_job(environment=env, now=later)
    failed = job.read(path)
    assert failed["approved"] == first["approved"]
    row = next(r for r in failed["selection"]["stores"] if r["store_id"] == "3839")
    assert row["status"] == "failed" and row["last_success"] == NOW.isoformat()
    assert datetime.fromisoformat(row["next_fetch_at"]) == later + timedelta(minutes=15)
    before = job.source_plan(environment=env, now=NOW)["fingerprint"]
    assert job.source_plan(environment=env, now=NOW + timedelta(hours=49))["fingerprint"] != before
    # Recovery replaces that exact store, while a confirmed withdrawal clears it.
    mode = "success"
    await job.run_offer_job(environment=env, now=later + timedelta(minutes=16))
    assert job.read(path)["approved"] != first["approved"]
    mode = "empty"
    await job.run_offer_job(environment=env, now=later + timedelta(hours=1))
    assert job.read(path)["approved"]["3839"] == []
    assert job.read(path)["last_outcomes"]["3839"]["status"] == "confirmed_no_qualified_rows"


async def test_xtra_failure_independent_toggle_and_source_integrity(env, monkeypatch):
    from grocery_data.scripts import collect_coop_municipality as pipeline
    from grocery_data.scripts import collect_coop_physical_offers as collector
    async def collect(inv, selected, output):
        output.mkdir()
        closed_source(output / "own.sqlite", "3839")
        return {"stores": [{"store_id": "3839", "status": "partial_candidate", "observed_at": NOW.isoformat()}]}
    async def xtra(*a):
        raise TimeoutError("injected transport failure")
    monkeypatch.setattr(collector, "collect", collect)
    monkeypatch.setattr(pipeline, "collect_xtra", xtra)
    await job.run_offer_job(environment=env, now=NOW)
    enabled = env | {"COOP_XTRA_OFFERS_ENABLED": "true"}
    await job.run_offer_job(environment=enabled, now=NOW)
    root, config = job.configuration(enabled)
    state = job.read(job.location(root, config))
    assert state["last_outcomes"]["3658"]["status"] == "failed"
    assert len(job.source_inputs(city="Lund", environment=enabled)["coop_offer_sources"]) == 1
    assert job.source_inputs(city="Malmö", environment=enabled) == {}
    ref = state["approved"]["3839"][0]
    (root / ref["database"]).write_bytes(b"corrupt injected source")
    assert job.source_inputs(city="Lund", environment=enabled)["coop_offer_sources"] == []
    off = env | {"COOP_MUNICIPAL_OFFERS_ENABLED": "false"}
    await job.run_offer_job(environment=off, now=NOW)
    assert not job.configuration({"COOP_MUNICIPAL_OFFERS_ROOT": str(root)})[1]["enabled"]


def test_fetch_is_not_publication_and_reload_must_match_built_manifest(env):
    root, config = job.configuration(env)
    path = job.location(root, config)
    job.write(path, {"selection": {"stores": [], "next_inventory_check": (NOW + timedelta(days=3)).isoformat()},
                     "last_source_approval_at": NOW.isoformat()})
    job.record_build(city="Lund", result={"price_universe_id": "built-1", "snapshot_ids": ["s1"]}, environment=env)
    status = {"city": "Lund", "refresh_exit_code": 0, "runtime_reload": {"status": "deferred"}}
    job.record_publication(status=status, disk_universe_id="built-1", environment=env)
    state = job.read(path)
    assert state["publication"]["last_published_at"]
    assert not state["publication"].get("last_reload_at")
    status["runtime_reload"] = {"new_price_universe_id": "wrong-universe"}
    job.record_publication(status=status, disk_universe_id="built-1", environment=env)
    assert not job.read(path)["publication"].get("last_reload_at")
    status["runtime_reload"] = {"new_price_universe_id": "built-1"}
    job.record_publication(status=status, disk_universe_id="built-1", environment=env)
    successful = job.read(path)["publication"]
    assert successful["reloaded_fingerprint"] == job.read(path)["built"]["fingerprint"]
    status.update(refresh_exit_code=1, runtime_reload={"status": "not_attempted"})
    job.record_publication(status=status, disk_universe_id="rollback-base", environment=env)
    failed = job.read(path)["publication"]
    assert failed["last_reload_at"] == successful["last_reload_at"]
    assert failed["status"] == "publication_or_reload_pending"
    retry = datetime.fromisoformat(failed["retry_at"])
    assert not job.source_plan(environment=env, now=retry - timedelta(seconds=1))["publication_due"]
    # A base-only rebuild still needs reload retry even with unchanged Coop fingerprint.
    assert job.source_plan(environment=env, now=retry + timedelta(seconds=1))["publication_due"]


def test_real_response_schema_distinguishes_confirmed_empty_from_missing_feed():
    from grocery_data.tests.test_coop_physical_structured import parse
    def empty(envelope):
        envelope["captured_total"] = 0
        envelope["cards"] = []
        if envelope.get("declared_total") is not None:
            envelope["declared_total"] = 0
        for group in envelope["structured_offers"]["data"]["sortingGroups"]:
            group.update(offerAmount=0, offers=[])
    parsed, accepted, evidence = parse(mutate=empty)
    assert not parsed.products and not parsed.failures and not evidence["shared_blockers"]
    assert not accepted.products
    def missing(envelope):
        envelope["structured_offers"]["data"]["sortingGroups"] = []
    parsed, accepted, evidence = parse(mutate=missing)
    assert parsed.failures and evidence["shared_blockers"]
    assert not accepted.products


def test_transport_requires_store_bound_authoritative_zero():
    import copy

    from grocery_data.app.connectors.coop.browser import CoopBrowserOffersTransport
    from grocery_data.app.connectors.coop.structured_offers import confirmed_empty_response
    from grocery_data.tests.test_coop_physical_structured import source
    store, batch = source()
    evidence = json.loads(batch.documents[0].payload)["structured_offers"]
    for group in evidence["data"]["sortingGroups"]:
        group.update(offerAmount=0, offers=[])
    assert confirmed_empty_response([evidence], store)
    payload = CoopBrowserOffersTransport._sanitized_payload([],declared_total=None,store=store,structured_responses=[evidence])
    assert json.loads(payload)["captured_total"] == 0
    for patch in [{"http_status":503},{"store_external_id":"wrong"},{"ledger_account_number":"wrong"},
                  {"data":{"sortingGroups":[]}},{"data":None}]:
        changed = {**copy.deepcopy(evidence), **patch}
        assert not confirmed_empty_response([changed],store)
        with pytest.raises(RuntimeError):
            CoopBrowserOffersTransport._sanitized_payload([],declared_total=None,store=store,structured_responses=[changed])
