import json
import zipfile
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path

import pytest

from grocery_data.app.domain import Chain, RawFetch
from grocery_data.app.services import source_artifact as m

NOW = datetime.now(UTC)


def artifact(tmp_path, observed=None):
    observed = observed or NOW - timedelta(minutes=2)
    documents = []

    def raw(kind, path, payload, ctx=None, query=None, page=None):
        documents.append(
            RawFetch(
                chain=Chain.WILLYS,
                store_external_id=ctx,
                kind=kind,
                method="POST" if kind == "store_activation" else "GET",
                url="https://www.willys.prod.axcsfprod.aws.axfoodapp.cloud/axfood/rest/v1/" + path,
                query=query or {},
                fetched_at=observed,
                http_status=200,
                content_type="application/json",
                payload=json.dumps(payload).encode(),
                connector_version="willys-v1",
                page_number=page,
            )
        )

    raw(
        "stores",
        "store",
        [
            {
                "storeId": x,
                "name": "Willys Lund " + x,
                "address": {"town": "Lund"},
                "onlineStore": True,
            }
            for x in m.APPROVED_WILLYS_CONTEXTS
        ],
    )
    product = json.loads(
        Path("grocery_data/app/connectors/willys/fixtures/fixed_package.json").read_text()
    )["results"][0]
    for ctx in m.APPROVED_WILLYS_CONTEXTS:
        raw(
            "store_activation",
            "store/activate",
            {},
            ctx,
            {"storeId": ctx, "activelySelected": "true", "forceAsPickingStore": "true"},
        )
        raw("store_context", "store/active", {"pickingStore": {"storeId": ctx}}, ctx)
        raw(
            "category_tree",
            "leftMenu/categorytree",
            {
                "id": "N00",
                "title": "Alla varor",
                "url": "",
                "children": [{"id": "N1", "title": "Pasta", "url": "/pasta", "children": []}],
            },
            ctx,
        )
        for n in range(4):
            data = []
            for i in range(n * 30, min(100, (n + 1) * 30)):
                row = deepcopy(product)
                row["code"] = f"product-{i}"
                data.append(row)
            raw(
                "catalog_page",
                "c/pasta",
                {"results": data, "pagination": {"currentPage": n, "numberOfPages": 4}},
                ctx,
                {"page": str(n), "size": "30"},
                n,
            )
    docs = tuple(documents)
    entries = tuple(
        m.PayloadEntry(
            metadata=d.model_dump(mode="json", exclude={"payload", "payload_hash"}),
            path=f"raw/{i:05d}.json",
            size=len(d.payload),
            sha256=sha256(d.payload).hexdigest(),
        )
        for i, d in enumerate(docs)
    )
    manifest = m.SourceManifest(
        context_ids=m.APPROVED_WILLYS_CONTEXTS,
        source_snapshot_id="0123456789abcdef0123456789abcdef",
        source_scope={"scope_key": "lund", "geographic_area": {"city": "Lund"}},
        collection_started_at=observed - timedelta(seconds=1),
        collection_finished_at=observed + timedelta(seconds=1),
        observed_from=observed,
        observed_to=observed,
        collector_version="willys-v1",
        parser_version="willys-parser-v3",
        normalizer_version="product-normalizer-v3-recipe-taxonomy",
        source_policy_version="willys-source-policy-v1",
        source_policy={
            "source_policy": "allow",
            "operator_opt_in": False,
            "store_allowlist": ["2176", "2354"],
            "requests_per_second": 1,
            "max_concurrency": 1,
        },
        row_count=200,
        product_count=100,
        request_count=len(docs) + 2,
        catalog_completion=m._willys_completion(docs),
        payloads=entries,
    )
    path = tmp_path / "valid.smako-source"
    m.write_source_artifact(manifest, docs, path)
    return path


def test_valid_container_preserves_original_observation_and_complete_pages(tmp_path):
    p = artifact(tmp_path)
    v = m.verify_source_artifact(p, now=NOW)
    assert all(d.fetched_at == NOW - timedelta(minutes=2) for d in v.documents)
    assert {c.pages_fetched for c in v.completion.values()} == {4}


def test_truncated_container_is_rejected(tmp_path):
    p = artifact(tmp_path)
    bad = tmp_path / "truncated.smako-source"
    bad.write_bytes(p.read_bytes()[:-40])
    with pytest.raises(m.SourceArtifactError):
        m.verify_source_artifact(bad, now=NOW)


def test_tampered_payload_rejected(tmp_path):
    p = artifact(tmp_path)
    bad = tmp_path / "tampered.smako-source"
    with zipfile.ZipFile(p) as src, zipfile.ZipFile(bad, "w") as dst:
        for name in src.namelist():
            dst.writestr(name, b"{}" if name == "raw/00000.json" else src.read(name))
    with pytest.raises(m.SourceArtifactError):
        m.verify_source_artifact(bad, now=NOW)


def test_stale_artifact_cannot_be_refreshed_by_import(tmp_path):
    p = artifact(tmp_path)
    with pytest.raises(m.SourceArtifactError, match="stale"):
        m.verify_source_artifact(p, now=NOW + timedelta(hours=49))


def test_future_artifact_rejected(tmp_path):
    p = artifact(tmp_path)
    with pytest.raises(m.SourceArtifactError, match="interval"):
        m.verify_source_artifact(p, now=NOW - timedelta(hours=1))


@pytest.mark.asyncio
async def test_duplicate_import_and_normal_source_promotion(tmp_path):
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )

    p = artifact(tmp_path)
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw = FilesystemRawSnapshotStore(tmp_path / "raw")
    a = await m.import_source_candidate(p, factory, raw)
    b = await m.import_source_candidate(p, factory, raw)
    assert a["snapshot_id"] == b["snapshot_id"] and b["status"] == "duplicate"
    manager = SnapshotManager(factory)
    assert not manager.get(a["snapshot_id"]).is_active
    promoted = manager.promote(a["snapshot_id"])
    assert promoted.is_active
    bad = tmp_path / "bad.smako-source"
    bad.write_bytes(p.read_bytes()[:-40])
    with pytest.raises(m.SourceArtifactError):
        await m.import_source_candidate(bad, factory, raw)
    assert manager.get(a["snapshot_id"]).is_active
    assert all(
        x.observed_at == NOW - timedelta(minutes=2) for x in manager.products(a["snapshot_id"])
    )
    engine.dispose()


def rewrite_manifest(source, target, transform, *, remove=None):
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w") as dst:
        manifest = json.loads(src.read("manifest.json"))
        transform(manifest)
        body = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
        for name in src.namelist():
            if name in {"manifest.json", "manifest.sha256", remove}:
                continue
            dst.writestr(name, src.read(name))
        dst.writestr("manifest.json", body)
        dst.writestr("manifest.sha256", sha256(body).hexdigest())


def test_forged_complete_flag_cannot_replace_missing_page_evidence(tmp_path):
    p = artifact(tmp_path)
    bad = tmp_path / "missing.smako-source"
    with zipfile.ZipFile(p) as src:
        last = json.loads(src.read("manifest.json"))["payloads"][-1]["path"]
    rewrite_manifest(p, bad, lambda body: body["payloads"].pop(), remove=last)
    with pytest.raises(m.SourceArtifactError, match="incomplete"):
        m.verify_source_artifact(bad, now=NOW)


def test_rehashed_forged_product_count_rejected_before_import(tmp_path):
    p = artifact(tmp_path)
    bad = tmp_path / "count.smako-source"
    rewrite_manifest(p, bad, lambda body: body.update(row_count=1))
    with pytest.raises(m.SourceArtifactError, match="counts"):
        m.verify_source_artifact(bad, now=NOW)


def test_manifest_cannot_hide_private_material_in_ignored_nested_fields(tmp_path):
    p = artifact(tmp_path)
    bad = tmp_path / "credential.smako-source"
    rewrite_manifest(
        p, bad, lambda body: body["source_scope"].update(cookie="synthetic-private-cookie")
    )
    with pytest.raises(m.SourceArtifactError):
        m.verify_source_artifact(bad, now=NOW)


@pytest.mark.asyncio
async def test_imported_aging_observations_do_not_become_fresh(tmp_path):
    from grocery_data.app.services.freshness import assess_freshness
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )

    observed = NOW - timedelta(hours=40)
    p = artifact(tmp_path, observed)
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    result = await m.import_source_candidate(
        p, factory, FilesystemRawSnapshotStore(tmp_path / "raw")
    )
    rows = SnapshotManager(factory).products(result["snapshot_id"])
    assert all(row.observed_at == observed for row in rows)
    assert assess_freshness(min(row.observed_at for row in rows), now=NOW).state.value == "aging"
    assert (
        assess_freshness(
            min(row.observed_at for row in rows), now=NOW + timedelta(hours=9)
        ).state.value
        == "stale"
    )
    engine.dispose()


@pytest.mark.asyncio
async def test_inbox_rejects_bad_arrival_and_promotes_valid_candidate(tmp_path):
    from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
    from grocery_data.app.services.snapshot_manager import SnapshotManager
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )

    source = artifact(tmp_path)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    digest = sha256(source.read_bytes()).hexdigest()
    (inbox / (digest + ".smako-source")).write_bytes(source.read_bytes())
    bad = b"truncated"
    bad_hash = sha256(bad).hexdigest()
    (inbox / (bad_hash + ".smako-source")).write_bytes(bad)
    (inbox / "unfinished.partial").write_bytes(bad)
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    raw = FilesystemRawSnapshotStore(tmp_path / "raw")
    results = await m.import_source_inbox(factory, raw, inbox)
    assert len(results) == 2
    valid = next(r for r in results if "snapshot_id" in r)
    assert SnapshotManager(factory).get(valid["snapshot_id"]).is_active
    assert (inbox / "processed" / (digest + ".smako-source")).is_file()
    assert (inbox / "rejected" / (bad_hash + ".smako-source")).is_file()
    assert (inbox / "unfinished.partial").is_file()
    duplicate = await m.import_source_candidate(source, factory, raw)
    assert duplicate["status"] == "duplicate"
    replacement = tmp_path / "same-age.smako-source"
    rewrite_manifest(source, replacement, lambda body: body.update(source_snapshot_id="f" * 32))
    with pytest.raises(m.SourceArtifactError, match="newer active"):
        await m.import_source_candidate(replacement, factory, raw)
    assert SnapshotManager(factory).get(valid["snapshot_id"]).is_active
    engine.dispose()


def test_local_relay_disables_only_direct_willys(monkeypatch):
    from grocery_data import __main__ as cli

    monkeypatch.setenv("WILLYS_COLLECTION_LOCATION", "VPS_DIRECT")
    before, _ = cli._collect_all_plan(["Lund"])
    monkeypatch.setenv("WILLYS_COLLECTION_LOCATION", "LOCAL_RELAY")
    after, skipped = cli._collect_all_plan(["Lund"])
    assert after == [target for target in before if target[0] != Chain.WILLYS]
    assert any(row.get("collection_location") == "LOCAL_RELAY" for row in skipped)
    with pytest.raises(m.SourceArtifactError, match="direct collection is disabled"):
        cli._collection_connector(Chain.WILLYS)


@pytest.mark.asyncio
async def test_operator_import_uses_normal_activation_and_duplicate_or_failure_preserves_lkg(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from sqlalchemy import select

    from deploy.scripts import run_daily_refresh as runner
    from grocery_data import __main__ as cli
    from grocery_data import source_cli
    from grocery_data.app.services.manual_refresh_operations import RefreshRunLock
    from grocery_data.app.storage import (
        create_database_engine,
        create_schema,
        create_session_factory,
    )
    from grocery_data.app.storage.models import CatalogSnapshotModel

    p = artifact(tmp_path)
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    create_schema(engine)
    factory = create_session_factory(engine)
    settings = SimpleNamespace(
        raw_snapshot_root=tmp_path / "raw", price_universe_cache_root=tmp_path / "universes"
    )
    monkeypatch.setattr(cli, "_runtime", lambda: (settings, engine, factory))
    # Keep the in-memory candidate database available for the duplicate assertion.
    monkeypatch.setattr(engine, "dispose", lambda: None)
    monkeypatch.setattr(source_cli.os, "geteuid", lambda: 10001, raising=False)
    monkeypatch.setattr(runner, "_operations_lock", lambda: RefreshRunLock(tmp_path / "ops.lock"))
    state = SimpleNamespace(active=None, bytes=b"original-lkg", builds=0)

    class Store:
        def __init__(self, *args):
            pass

        def read_active(self, city):
            return state.active

        def resolve_active_artifact(self, city, verify_hash):
            assert verify_hash
            return tmp_path / "immutable.json"

    monkeypatch.setattr(source_cli, "PreparedUniverseArtifactStore", Store)
    monkeypatch.setattr(
        runner, "build_refresh_command", lambda: ["python", "-m", "grocery_data", "daily-refresh"]
    )

    def managed(lock, *, command, run_kind, started_at, status_writer):
        assert lock.info is not None
        assert command[-3:] == ["--chain", "citygross", "--no-external-refresh"]
        assert run_kind == "source_relay_import"
        with factory() as session:
            snapshot = session.scalar(
                select(CatalogSnapshotModel).where(CatalogSnapshotModel.is_active.is_(True))
            )
            assert snapshot.state == "promoted"
            state.active = SimpleNamespace(
                snapshot_ids=(snapshot.id,), universe_id="normal-universe"
            )
        state.bytes = b"normal-activated-manifest"
        state.builds += 1
        status_writer({"runtime_reload": {"new_price_universe_id": "normal-universe"}})
        return 0

    monkeypatch.setattr(runner, "_run_locked", managed)
    monkeypatch.setattr(runner, "_write_status", lambda value: None)
    monkeypatch.setattr(runner, "_confirm_loaded_runtime", lambda expected: None)
    monkeypatch.setattr(runner, "_reload_runtime", lambda: {"new_price_universe_id": "normal-universe"})
    result = await source_cli.import_and_activate(SimpleNamespace(artifact=p))
    assert result["activation"] == "normal_managed_refresh" and state.builds == 1
    duplicate = await source_cli.import_and_activate(SimpleNamespace(artifact=p))
    assert duplicate["activation"] == "already_active" and state.builds == 1
    monkeypatch.setattr(runner, "_reload_runtime", lambda: {"status": "deferred"})
    with pytest.raises(m.SourceArtifactError, match="runtime activation"):
        await source_cli.import_and_activate(SimpleNamespace(artifact=p))

    def confirmed(expected):
        assert expected == state.active.universe_id == "normal-universe"
        return {"new_price_universe_id": expected, "confirmation": "scoped_readiness"}

    def forbidden_reload():
        raise AssertionError("Already loaded duplicate must not trigger another reload")

    monkeypatch.setattr(runner, "_confirm_loaded_runtime", confirmed)
    monkeypatch.setattr(runner, "_reload_runtime", forbidden_reload)
    acknowledged = await source_cli.import_and_activate(SimpleNamespace(artifact=p))
    assert acknowledged["activation"] == "already_active"
    assert acknowledged["universe_id"] == "normal-universe" and state.builds == 1
    before = state.bytes
    bad = tmp_path / "truncated-again.smako-source"
    bad.write_bytes(p.read_bytes()[:-100])
    with pytest.raises(m.SourceArtifactError):
        await source_cli.import_and_activate(SimpleNamespace(artifact=bad))
    assert state.bytes == before and state.builds == 1
