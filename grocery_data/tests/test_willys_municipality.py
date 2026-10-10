"""Saved official registry/boundaries; synthetic catalogue, explicit test clock."""
import gzip
import json
from copy import deepcopy
from datetime import datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from grocery_data.app.connectors.willys.connector import WillysConnector
from grocery_data.app.connectors.willys.municipality_inventory import build_inventory
from grocery_data.app.domain import GeographicArea, RawBatch, SourceScopeDescriptor
from grocery_data.app.domain.municipality import municipality_name
from grocery_data.app.services import source_artifact as m
from grocery_data.app.services.willys_municipal_scope import relay_municipality
from grocery_data.tests.test_source_artifact import artifact

FIXTURE = json.loads(gzip.decompress((Path(__file__).parent / "fixtures/willys-municipality-20260922.json.gz").read_bytes()))
RAW = RawBatch.model_validate(FIXTURE["registry"])


def inventory(code):
    area = GeographicArea(city=municipality_name(code), mode="municipality", municipality_code=code)
    return build_inventory(area, RAW, ["saved:official-registry"], FIXTURE["boundary-" + code])


@pytest.mark.parametrize("code,inside,online", [("1281", 3, 2), ("1280", 10, 4)])
def test_same_saved_register_and_geometry_code_selects_both_municipalities(code, inside, online):
    result = inventory(code)
    assert sum(r["geographic_evidence"]["status"] == "inside" for r in result["stores"]) == inside
    assert len(result["selected_store_ids"]) == online
    assert len(result["stores"]) + len(result["unresolved_registry_rows"]) == result["registry_rows"]
    assert result["unresolved_registry_rows"][0]["source_store_id"] == "2002"
    assert result["complete"] is False


def test_malmo_retains_limhamn_and_offline_oxie_not_just_address_city():
    rows = {r["store"]["external_id"]: r for r in inventory("1280")["stores"]}
    assert rows["2144"]["collection_selected"]
    assert rows["2879"]["geographic_evidence"]["status"] == "inside"
    assert rows["2879"]["collection_reason"] == "no_verified_online_catalog"
    assert not rows["2176"]["collection_selected"]


def test_missing_coordinates_stay_unknown_and_duplicate_ids_fail():
    rows = RAW.documents[0].json_payload()
    target = next(r for r in rows if str(r.get("storeId")) == "2176")
    target["address"]["latitude"] = target["address"]["longitude"] = None
    target["geoPoint"] = {}
    altered = RAW.model_copy(update={"documents": (RAW.documents[0].model_copy(update={"payload": json.dumps(rows).encode()}),)})
    area = GeographicArea(city="Lund", mode="municipality", municipality_code="1281")
    inv = build_inventory(area, altered, ["mutated:test"], FIXTURE["boundary-1281"])
    row = next(r for r in inv["stores"] if r["store"]["external_id"] == "2176")
    assert row["geographic_evidence"]["status"] == "unknown"
    assert not row["collection_selected"]
    rows.append(deepcopy(target))
    altered = RAW.model_copy(update={"documents": (RAW.documents[0].model_copy(update={"payload": json.dumps(rows).encode()}),)})
    with pytest.raises(ValueError, match="duplicate"):
        build_inventory(area, altered, ["mutated:test"], FIXTURE["boundary-1281"])


def municipal_artifact(tmp_path, monkeypatch, code):
    legacy = m.verify_source_artifact(artifact(tmp_path))
    inv = inventory(code)
    area = GeographicArea.model_validate(inv["area"])
    observed = RAW.documents[0].fetched_at

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return observed + timedelta(minutes=2)

    monkeypatch.setattr(m, "datetime", Clock)
    docs = [RAW.documents[0]]
    template = [d for d in legacy.documents if d.store_external_id == "2176"]
    for context in inv["selected_store_ids"]:
        for doc in template:
            payload = doc.json_payload()
            query = doc.query.copy()
            if doc.kind == "store_activation":
                query["storeId"] = context
            if doc.kind == "store_context":
                payload = {"pickingStore": {"storeId": context}}
            docs.append(doc.model_copy(update={"store_external_id": context, "query": query,
                "payload": json.dumps(payload).encode(), "fetched_at": observed}))
    docs = tuple(docs)
    contexts = tuple(inv["selected_store_ids"])
    boundary = FIXTURE["boundary-" + code]
    entries = tuple(m.PayloadEntry(metadata=d.model_dump(mode="json", exclude={"payload", "payload_hash"}),
        path=f"raw/{i:05d}.json", size=len(d.payload), sha256=sha256(d.payload).hexdigest()) for i, d in enumerate(docs))
    manifest = legacy.manifest.model_copy(update={
        "parser_version": m.WillysParser.parser_version,
        "context_ids": contexts, "source_scope": SourceScopeDescriptor(scope_key=area.city.casefold(), geographic_area=area),
        "municipality_boundary": boundary, "source_policy_version": "willys-municipality-policy-v1",
        "source_policy": legacy.manifest.source_policy.model_copy(update={"store_allowlist": contexts}),
        "row_count": 100 * len(contexts), "product_count": 100, "request_count": len(docs) + 2,
        "catalog_completion": m._willys_completion(docs, area=area, boundary=boundary, contexts=contexts),
        "collection_started_at": observed - timedelta(seconds=1), "collection_finished_at": observed + timedelta(seconds=1),
        "observed_from": observed, "observed_to": observed, "payloads": entries})
    destination = tmp_path / (code + ".smako-source")
    m.write_source_artifact(manifest, docs, destination)
    return destination


@pytest.mark.parametrize("code", ["1281", "1280"])
def test_municipal_artifact_independently_recomputes_all_contexts(tmp_path, monkeypatch, code):
    path = municipal_artifact(tmp_path, monkeypatch, code)
    verified = m.verify_source_artifact(path)
    assert set(verified.completion) == set(inventory(code)["selected_store_ids"])
    assert verified.manifest.observed_from == RAW.documents[0].fetched_at
    with pytest.raises(m.SourceArtifactError, match="stale"):
        m.verify_source_artifact(path, now=RAW.documents[0].fetched_at + timedelta(hours=48))


def test_wrong_municipality_and_context_are_rejected(tmp_path, monkeypatch):
    from grocery_data.tests.test_source_artifact import rewrite_manifest
    path = municipal_artifact(tmp_path, monkeypatch, "1281")
    bad = tmp_path / "wrong.smako-source"
    rewrite_manifest(path, bad, lambda body: body["source_scope"]["geographic_area"].update(city="Malmö", municipality_code="1280"))
    with pytest.raises(m.SourceArtifactError):
        m.verify_source_artifact(bad)


def test_persistent_relay_scope_survives_restart_and_cannot_change_silently(tmp_path):
    assert relay_municipality(tmp_path, "1281") == "1281"
    assert relay_municipality(tmp_path) == "1281"
    with pytest.raises(ValueError, match="separate"):
        relay_municipality(tmp_path, "1280")


def test_municipal_relay_not_due_makes_no_external_requests_after_restart(tmp_path):
    from datetime import UTC

    from grocery_data.local_relay import run

    now = datetime.now(UTC)
    relay_municipality(tmp_path, "1280")
    (tmp_path / "last-success.json").write_text(json.dumps({"municipality_code": "1280",
        "observed_from": (now - timedelta(hours=34)).isoformat(), "sha256": "1" * 64}))

    def forbidden(*args):
        raise AssertionError("unexpected external request")

    for _ in range(2):
        assert run(tmp_path, collect=forbidden, push=forbidden, activate=forbidden, now=now) == 0
    assert all("not_due" in p.read_text() for p in (tmp_path / "logs").glob("*.jsonl"))


def test_connector_cannot_treat_missing_boundary_as_municipal_evidence():
    connector = WillysConnector()
    with pytest.raises(ValueError, match="boundary"):
        connector.parse_stores(RAW, ["saved"], GeographicArea(city="Lund", mode="municipality", municipality_code="1281"))


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["1281", "1280"])
async def test_import_needs_explicit_config_and_uses_normal_own_idempotently(tmp_path, monkeypatch, code):
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.services.willys_municipal_scope import approved_snapshot_stores
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )
    path = municipal_artifact(tmp_path, monkeypatch, code)
    database = tmp_path / "own.sqlite"
    engine = create_database_engine("sqlite+pysqlite:///" + database.as_posix())
    create_schema(engine)
    factory = create_session_factory(engine)
    raw = FilesystemRawSnapshotStore(tmp_path / "raw")
    monkeypatch.delenv("WILLYS_MUNICIPAL_CONFIG", raising=False)
    with pytest.raises(ValueError, match="not enabled"):
        await m.import_source_candidate(path, factory, raw)
    config = tmp_path / "municipal.json"
    config.write_text(json.dumps({"schema": "willys-municipal-build-v1", "build_scopes": {"12345": code}}))
    monkeypatch.setenv("WILLYS_MUNICIPAL_CONFIG", str(config))
    first = await m.import_source_candidate(path, factory, raw)
    SnapshotManager(factory).promote(first["snapshot_id"])
    second = await m.import_source_candidate(path, factory, raw)
    assert second["status"] == "duplicate" and first["snapshot_id"] == second["snapshot_id"]
    assert set(approved_snapshot_stores(database, "12345")) == set(inventory(code)["selected_store_ids"])
    engine.dispose()


@pytest.mark.asyncio
async def test_scope_migration_requires_identical_raw_observations_not_just_same_dates(tmp_path, monkeypatch):
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )
    from grocery_data.tests.test_source_artifact import rewrite_manifest

    municipal = municipal_artifact(tmp_path, monkeypatch, "1281")
    legacy = tmp_path / "legacy-national-register.smako-source"

    def legacy_scope(body):
        body["municipality_boundary"] = None
        body["source_scope"] = {"scope_key": "lund", "geographic_area": {"city": "Lund"}}
        body["source_policy_version"] = "willys-source-policy-v1"

    rewrite_manifest(municipal, legacy, legacy_scope)
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw = FilesystemRawSnapshotStore(tmp_path / "raw")
    old = await m.import_source_candidate(legacy, factory, raw)
    SnapshotManager(factory).promote(old["snapshot_id"])
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"schema": "willys-municipal-build-v1", "build_scopes": {"22350": "1281"}}))
    monkeypatch.setenv("WILLYS_MUNICIPAL_CONFIG", str(config))
    verified = m.verify_source_artifact(municipal)
    altered = list(verified.documents)
    i = next(i for i, d in enumerate(altered) if d.kind == "catalog_page")
    payload = altered[i].json_payload()
    payload["results"][0]["priceValue"] = 19.5
    altered[i] = altered[i].model_copy(update={"payload": json.dumps(payload).encode()})
    entries = tuple(m.PayloadEntry(metadata=d.model_dump(mode="json", exclude={"payload", "payload_hash"}),
        path=f"raw/{i:05d}.json", size=len(d.payload), sha256=sha256(d.payload).hexdigest()) for i, d in enumerate(altered))
    changed = tmp_path / "changed-price-same-time.smako-source"
    m.write_source_artifact(verified.manifest.model_copy(update={"payloads": entries}), tuple(altered), changed)
    with pytest.raises(m.SourceArtifactError, match="newer active"):
        await m.import_source_candidate(changed, factory, raw)
    migrated = await m.import_source_candidate(municipal, factory, raw)
    snapshot = SnapshotManager(factory).get(migrated["snapshot_id"])
    assert snapshot.metrics["requalification_without_new_price_observation"] is True
    SnapshotManager(factory).promote(snapshot.id)
    repeated = await m.import_source_candidate(legacy, factory, raw)
    assert repeated["status"] == "duplicate"
    assert not SnapshotManager(factory).get(repeated["snapshot_id"]).is_active
    legacy_new_container = tmp_path / "legacy-new-container.smako-source"
    rewrite_manifest(legacy, legacy_new_container, lambda body: body.update(source_snapshot_id="f" * 32))
    with pytest.raises(m.SourceArtifactError, match="legacy relay"):
        await m.import_source_candidate(legacy_new_container, factory, raw)
    engine.dispose()
