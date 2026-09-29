"""Isolated ordinary refresh/reload acceptance with explicit source scope.

An optional frozen base must retain its real source observations. Without a
base, the existing OWN_SOURCES_ONLY configuration explicitly selects a private
Willys flyer instance; that is not complete federated Malmö release evidence.
Willys flyer collection is an explicitly labelled replay of immutable live OWN
databases, or an injected fetch error. The real runner launches a real child
CLI, publishes a real artifact and calls a real loopback application. External
network is blocked in every verification process. This does not claim a new
live retailer collection or authorize any production configuration change.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(REPO), str(REPO / "backend")]


def read(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def block_external_network():
    """Permit only the real local serving application; never a retailer retry."""
    count = {"blocked_external_attempts": 0, "loopback_connections": 0}
    original_lookup = socket.getaddrinfo
    original_connect = socket.socket.connect

    def local(host):
        if isinstance(host, bytes):
            host = host.decode("ascii")
        if host in {"localhost", ""}:
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False

    def lookup(host, *args, **kwargs):
        if not local(host):
            count["blocked_external_attempts"] += 1
            raise OSError("verification prohibits external network")
        return original_lookup(host, *args, **kwargs)

    def connect(sock, address):
        if isinstance(address, tuple):
            if not local(address[0]):
                count["blocked_external_attempts"] += 1
                raise OSError("verification prohibits external network")
            count["loopback_connections"] += 1
        return original_connect(sock, address)

    socket.getaddrinfo = lookup
    socket.socket.connect = connect
    return count


def configure(root, *, mode):
    config = read(root / "harness.json")
    city, postal = config["city"], config["postal"]
    os.environ.update(
        PYTHON_DOTENV_DISABLED="true", PYTHONIOENCODING="utf-8",
        APP_ENV="development", PUBLIC_BASE_URL=f"http://127.0.0.1:{config['port']}",
        SECRET_KEY=os.environ.get("VERIFY_SECRET_KEY", "isolated-verification-secret-not-production"),
        BETA_ADMIN_TOKEN=os.environ.get("VERIFY_ADMIN_TOKEN", "isolated-verification-local-admin"),
        PLAN_STORE_PATH=str(root / "plans.sqlite"),
        GROCERY_DATABASE_URL="sqlite+pysqlite:///" + (root / "grocery.sqlite").as_posix(),
        GROCERY_RAW_SNAPSHOT_ROOT=str(root / "raw"),
        PRICE_UNIVERSE_CACHE_ROOT=str(root / "price-universes"),
        PRICE_UNIVERSE_REQUIRED="false" if mode == "first" and not config["base"] else "true",
        PRICE_UNIVERSE_CITY=city,
        OWN_SOURCES_ONLY="true" if config["own_sources_only"] else "false",
        PRICE_UNIVERSE_PREWARM_ENABLED="false", PRICE_PROVIDER="own",
        INTERNAL_APP_BASE_URL=f"http://127.0.0.1:{config['port']}",
        REFRESH_CITY=city, REFRESH_POSTAL_CODE=postal,
        REFRESH_REPORT_DIR=str(root / "reports"),
        REFRESH_RUNNER_STATUS_PATH=str(root / "runner-status.json"),
        DEMAND_REFRESH_STATE_PATH=str(root / "demand.json"),
        # Explicit ordinary rebuilds use the runner's normal forced entry;
        # only the separate no-work probe asks the demand gate to skip.
        DEMAND_REFRESH_ENABLED="true" if mode == "not_due" else "false",
        WILLYS_FLYER_ROOT=str(root / "willys-flyer"),
        WILLYS_FLYER_INVENTORY=str(root / "inventory.json"),
        WILLYS_FLYER_BUILD_CITY=city,
        CITYGROSS_MUNICIPAL_ENABLED=str((root / "citygross/config.json").exists()).lower(),
        CITYGROSS_MUNICIPAL_ROOT=str(root / "citygross"),
        LIDL_MUNICIPAL_ROOT=str(root / "lidl"),
        LIDL_MUNICIPAL_ENABLED=str((root / "lidl/config.json").exists()).lower(),
        COOP_MUNICIPAL_OFFERS_ROOT=str(root / "municipal"),
        COOP_MUNICIPAL_OFFERS_ENABLED=str((root / "municipal/config.json").exists()).lower(),
        ICA_STRUCTURED_OFFERS_ROOT=str(root / "ica-structured-offers"),
        ICA_STRUCTURED_OFFERS_ENABLED=str((root / "ica-structured-offers").exists()).lower(),
        ICA_AREA_OFFER_CANDIDATES_ENABLED="false", COOP_XTRA_OFFERS_ENABLED="false",
        ICA_FLYER_PAID_ENABLED="false", ICA_FLYER_VISUAL_COMMAND_JSON="",
        WILLYS_COLLECTION_LOCATION="LOCAL_RELAY",
        SOURCE_RELAY_INBOX=str(root / "raw/source-inbox/willys"),
        WILLYS_MUNICIPAL_CONFIG=str(root / "willys-config.json")
        if (root / "willys-config.json").exists() else "",
        VERIFY_ROOT=str(root), VERIFY_MODE=mode,
    )
    if mode == "first":
        os.environ.update(WILLYS_FLYER_ENABLED="true",
                          WILLYS_FLYER_MUNICIPALITY_CODE=config["municipality"])
    else:
        # Restart reads the actual persisted municipality rather than env overrides.
        os.environ.pop("WILLYS_FLYER_ENABLED", None)
        os.environ.pop("WILLYS_FLYER_MUNICIPALITY_CODE", None)
    os.environ["PYTHONPATH"] = os.pathsep.join([str(REPO), str(REPO / "backend")])
    return config


def initialize(args):
    root = args.root.resolve()
    base = args.base.resolve(strict=True) if args.base else None
    if root.exists():
        raise ValueError("verification root must be new; existing work is never removed")
    inventory = read(args.inventory)
    if inventory["area"]["municipality_code"] != args.municipality:
        raise ValueError("inventory scope mismatch")
    root.mkdir(parents=True)
    if base:
        with (
            sqlite3.connect((base / "grocery.sqlite").as_uri() + "?mode=ro", uri=True) as source,
            sqlite3.connect(root / "grocery.sqlite") as destination,
        ):
            source.backup(destination)
        shutil.copytree(base / "price-universes", root / "price-universes")
        for name in ("municipal", "ica-structured-offers", "lidl", "citygross"):
            if (base / name).is_dir():
                shutil.copytree(base / name, root / name)
        for name in ("willys-config.json",):
            if (base / name).is_file():
                shutil.copyfile(base / name, root / name)
    else:
        from grocery_data.app.storage import create_database_engine, create_schema
        engine = create_database_engine("sqlite:///" + (root / "grocery.sqlite").as_posix())
        create_schema(engine)
        engine.dispose()
        (root / "price-universes").mkdir()
    if args.willys_source_artifact:
        original = args.willys_source_artifact.resolve(strict=True)
        target = root / "raw/source-inbox/willys" / (digest(original) + ".smako-source")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, target)
        save(root / "willys-config.json", {"schema": "willys-municipal-build-v1", "build_scopes": {args.postal: args.municipality}})
        save(root / "retained-main-proof.json", {"source": str(original), "sha256": digest(original),
            "scope": "normal immutable Willys source artifact import; no new retailer calls"})
    if args.retained_main_db:
        from grocery_data.app.services.snapshot_manager import SnapshotManager
        from grocery_data.app.storage import create_database_engine, create_session_factory
        source = args.retained_main_db.resolve(strict=True)
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src, sqlite3.connect(root / "grocery.sqlite") as dest:
            src.backup(dest)
        engine = create_database_engine("sqlite:///" + (root / "grocery.sqlite").as_posix())
        with sqlite3.connect(root / "grocery.sqlite") as db:
            unpromoted = [r[0] for r in db.execute("SELECT id FROM catalog_snapshots WHERE state='health_checked'")]
        for snapshot in unpromoted:
            SnapshotManager(create_session_factory(engine)).promote(snapshot)
        engine.dispose()
        save(root / "willys-config.json", {"schema": "willys-municipal-build-v1", "build_scopes": {args.postal: args.municipality}})
        save(root / "retained-main-proof.json", {"source": str(source), "sha256": digest(source),
            "promotion": "normal SnapshotManager independently validates copied health-checked snapshot",
            "source_observations_changed": False})
    if args.retained_citygross_root:
        source_root = args.retained_citygross_root.resolve(strict=True)
        cg_config = read(source_root / "config.json")
        if cg_config["municipality_code"] != args.municipality:
            raise ValueError("City Gross baseline municipality mismatch")
        cg_state = read(source_root / args.municipality / "source-state.json")
        copied = set()
        for refs in cg_state["approved"].values():
            for ref in refs:
                relative = ref["database"]
                if relative in copied:
                    continue
                original = (source_root / relative).resolve(strict=True)
                assert original.is_relative_to(source_root) and digest(original) == ref["sha256"]
                target = root / "citygross" / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                copied.add(relative)
        save(root / "citygross/config.json", cg_config)
        save(root / "citygross" / args.municipality / "source-state.json", cg_state)
        save(root / "retained-main-proof.json", {"source": str(source_root), "copied": sorted(copied),
            "source_observations_changed": False, "scope": "exact approved City Gross municipal baseline"})
    if args.retained_coop_base:
        from grocery_data.app.services import coop_offer_job as coop_job
        from grocery_data.app.services.coop_municipal_refresh import update_selection
        base_source = args.retained_coop_base.resolve(strict=True)
        base_inventory = read(base_source / "coverage.json")["inventory"]
        if base_inventory["area"]["municipality_code"] != args.municipality:
            raise ValueError("retained base belongs to another municipality")
        base_database = base_source / "collection/own.sqlite"
        destination = root / "municipal/retained-base.sqlite"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(base_database, destination)
        outcomes, refs = {}, {}
        with sqlite3.connect(destination) as db:
            for identity, observed in db.execute("SELECT sp.store_external_id,MIN(sp.fetched_at) FROM source_products sp JOIN catalog_snapshots cs ON cs.id=sp.catalog_snapshot_id WHERE cs.is_active=1 AND cs.state='promoted' GROUP BY sp.store_external_id"):
                windows = [{"valid_from": a, "valid_to": b} for a, b in db.execute("SELECT DISTINCT pr.valid_from,pr.valid_to FROM promotions pr JOIN stores s ON s.id=pr.store_id WHERE s.external_id=?", (identity,))]
                row = {"status": "success", "observed_at": observed, "windows": windows}
                outcomes[identity] = row
                refs[identity] = [coop_job.approved_reference(destination, identity, root=destination.parent, outcome=row)]
        config = {"enabled": True, "xtra_enabled": False, "municipality_code": args.municipality, "city": args.city}
        coop_job.write(destination.parent / "config.json", config)
        selection = update_selection(base_inventory, outcomes, now=datetime.now(UTC))
        coop_job.write(coop_job.location(destination.parent, config), {"inventory": base_inventory,
            "selection": selection, "approved": refs, "municipality_code": args.municipality})
        save(root / "retained-base-proof.json", {"source": str(base_database), "sha256": digest(base_database),
            "copy_sha256": digest(destination), "original_observations": sorted({r["observed_at"] for r in outcomes.values()}),
            "scope": "retained municipal Coop offers only; not a complete base; no new network or observation"})
    shutil.copyfile(args.inventory, root / "inventory.json")
    collection = args.collection.resolve(strict=True)
    coverage = read(collection / "coverage.json")
    for row in coverage["stores"]:
        if row["status"] == "success":
            path = collection / row["database"]
            if not path.resolve().is_relative_to(collection):
                raise ValueError("collection reference escaped immutable input")
            row["verification_database"] = str(path)
            row["verification_sha256"] = digest(path)
    save(root / "replay-input.json", coverage)
    save(root / "harness.json", {
        "city": args.city, "postal": args.postal, "municipality": args.municipality,
        "port": args.port, "base": str(base) if base else None,
        "base_database_sha256": digest(base / "grocery.sqlite") if base else None,
        "own_sources_only": True,
        "initialized_at": datetime.now(UTC), "production_activation": False,
        "scope": "isolated OWN_SOURCES_ONLY instance with retained municipal baseline; no full Malmö release claim",
        "collection_mode": "replay of separately live-collected immutable OWN databases",
    })


def inject_replay(root, *, failure):
    from grocery_data.scripts import collect_willys_flyers as collector

    async def collect(inventory, selected, output):
        del inventory
        source = read(root / "replay-input.json")
        outputs = []
        for row in source["stores"]:
            if row["store_id"] not in selected:
                continue
            if failure:
                outputs.append({"store_id": row["store_id"], "status": "failed",
                                "reason": "injected_transport_failure", "error_type": "InjectedFetchError"})
                continue
            result = dict(row)
            result["original_live_catalog_network_requests"] = result.get("actual_catalog_network_requests", 0)
            result["actual_catalog_network_requests"] = 0
            result["verification_fetch_mode"] = "immutable_database_replay"
            if row["status"] == "success":
                original = Path(row["verification_database"])
                if digest(original) != row["verification_sha256"]:
                    raise ValueError("immutable replay input changed")
                target = output / row["store_id"] / "own.sqlite"
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, target)
                result.update(database=str(target.relative_to(output)), resolved_database=str(target))
            outputs.append(result)
        save(output / "verification-replay.json", {
            "mode": "injected_fetch_failure" if failure else "immutable_database_replay",
            "external_price_requests": 0, "selected": sorted(selected), "stores": outputs,
        })
        return {"stores": outputs}

    collector.collect = collect
    # Other retained optional sources are explicit immutable replays too. A due
    # City Gross campaign timer must not make an unrelated live collection.
    from grocery_data.scripts import collect_citygross_municipality as cg_collector
    async def retained_citygross(inventory, selected, output):
        state = read(root / "citygross" / read(root / "harness.json")["municipality"] / "source-state.json")
        outcomes = []
        for identity in selected:
            original_row = dict(state.get("last_outcomes", {}).get(identity, {}))
            refs = state.get("approved", {}).get(identity, [])
            if not refs:
                outcomes.append({"store_id": identity, "status": "failed", "reason": "retained_fixture_missing"})
                continue
            ref = refs[0]
            original = root / "citygross" / ref["database"]
            assert digest(original) == ref["sha256"]
            target = output / identity / "own.sqlite"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original, target)
            original_row.update(store_id=identity, status="success", database=str(target.relative_to(output)),
                resolved_database=str(target), observed_at=ref["observed_at"], windows=ref["windows"],
                verification_fetch_mode="retained_citygross_replay", actual_catalog_network_requests=0)
            outcomes.append(original_row)
        save(output / "verification-retained-citygross.json", {"external_price_requests":0,"stores":outcomes})
        return {"stores":outcomes}
    cg_collector.collect = retained_citygross


def refresh_child(arguments):
    root = Path(os.environ["VERIFY_ROOT"])
    mode = os.environ["VERIFY_MODE"]
    network = block_external_network()
    inject_replay(root, failure=mode == "fetch_fail")
    from grocery_data import __main__ as cli
    original_build = cli._build_production_price_universe
    async def traced_build(**kwargs):
        try:
            return await original_build(**kwargs)
        except Exception:
            import traceback
            traceback.print_exc()
            raise
    cli._build_production_price_universe = traced_build
    try:
        return cli.main(arguments)
    finally:
        save(root / f"child-network-{mode}.json", network)


def serve(root, mode):
    config = configure(root, mode=mode)
    network = block_external_network()
    import uvicorn
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=config["port"],
                    log_level="error", access_log=False)
    finally:
        save(root / f"app-network-{mode}.json", network)


def prepared_state(root, config):
    from app.services.price_universe_runtime import PreparedPriceUniverseArtifact

    from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
    store = PreparedUniverseArtifactStore(root / "price-universes")
    path = store.resolve_active_artifact(config["city"], verify_hash=True)
    prepared = PreparedPriceUniverseArtifact.model_validate_json(path.read_bytes()).restore()
    records = [p.model_dump(mode="json") for p in prepared.universe.products if p.chain == "willys" and p.source_provenance.source_channel == "offers"]
    other = [p.model_dump(mode="json") for p in prepared.universe.products if not (p.chain == "willys" and p.source_provenance.source_channel == "offers")]
    return prepared, {
        "price_universe_id": prepared.universe.universe_id,
        "flyer_products": len(records),
        "flyer_product_signature": hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest(),
        "other_product_signature": hashlib.sha256(json.dumps(other, sort_keys=True).encode()).hexdigest(),
        "flyer_store_counts": dict(Counter(p["store_id"] for p in records)),
        "all_chain_counts": dict(Counter(p.chain for p in prepared.universe.products)),
        "source_observations": sorted({p["source_provenance"]["source_observed_at"] for p in records}),
        "source_snapshots": sorted({p["source_provenance"]["source_snapshot_id"] for p in records}),
    }


def phase(root, mode):
    config = configure(root, mode=mode)
    code_files = (
        "grocery_data/__main__.py", "deploy/scripts/run_daily_refresh.py",
        "grocery_data/app/services/willys_flyer_job.py",
        "grocery_data/app/connectors/willys/flyer_client.py",
        "grocery_data/app/connectors/willys/flyer_offers.py",
        "grocery_data/app/connectors/willys/flyer_inventory.py",
        "grocery_data/scripts/collect_willys_flyers.py",
        "grocery_data/app/services/offer_rows.py",
        "grocery_data/app/api/catalog.py",
        "backend/app/services/lidl_product_facts.py",
        "backend/app/services/basket_calculator.py",
        "backend/app/providers/willys_flyers.py",
        "backend/app/services/production_price_universe_build.py",
        "backend/app/providers/own.py",
        "backend/app/models/provenance.py",
        "backend/app/services/price_universe.py",
        "grocery_data/app/services/municipal_publication_receipts.py",
    )
    code_hashes = {name: digest(REPO / name) for name in code_files}
    network = block_external_network()
    import httpx

    from deploy.scripts import run_daily_refresh as runner
    from grocery_data.app.services import willys_flyer_job as job

    if mode in {"fetch_fail", "recovery"}:
        source_root, source_config = job.configuration()
        path = job.location(source_root, source_config)
        state = job.read(path)
        for row in state["selection"]["stores"]:
            if row["selected"]:
                row["next_fetch_at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
        job.write(path, state)
    original_command = runner.build_refresh_command

    def command():
        normal = original_command()
        return [sys.executable, str(Path(__file__).resolve()), "refresh-child", *normal[3:],
                "--chain", "willys", "--no-external-refresh"]

    runner.build_refresh_command = command
    ordinary_subprocess = subprocess.run

    def logged_subprocess(*args, **kwargs):
        with (root / f"refresh-{mode}.log").open("w", encoding="utf-8") as refresh_log:
            kwargs.update(stdout=refresh_log, stderr=subprocess.STDOUT)
            return ordinary_subprocess(*args, **kwargs)

    runner.subprocess.run = logged_subprocess
    log = (root / f"app-{mode}.log").open("w", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "serve", "--root", str(root), "--mode", mode],
        cwd=REPO, stdout=log, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    started = time.monotonic()
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{config['port']}", trust_env=False) as client:
            while True:
                if process.poll() is not None:
                    raise RuntimeError("private serving application exited; inspect its isolated log")
                try:
                    if client.get("/health").status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if time.monotonic() - started > 180:
                    raise RuntimeError("private application startup timed out")
                time.sleep(0.25)
            code = runner.main()
            if code not in {0, 2}:
                save(root / f"result-{mode}-failed.json", {
                    "mode": mode, "runner_exit": code,
                    "runner": read(root / "runner-status.json"), "parent_network": network,
                })
                raise RuntimeError("ordinary refresh failed; see retained private runner report")
            prepared, evidence = prepared_state(root, config)
            source_root, source_config = job.configuration()
            source_state = job.read(job.location(source_root, source_config))
            evidence.update(
                mode=mode, runner_exit=code, elapsed_seconds=time.monotonic() - started,
                runner=read(root / "runner-status.json"),
                source_configuration=source_config, source_state=source_state,
                parent_network=network, health=client.get("/health").status_code,
                ready=client.get("/ready").status_code,
                source_plan=job.source_plan(), production_activation=False,
                collection_kind="injected_fetch_failure" if mode == "fetch_fail" else "retained_live_data_replay",
                serving_process_id=process.pid, code_hashes_at_phase_start=code_hashes,
            )
            future = datetime.now(UTC) + timedelta(hours=49)
            evidence["expiry_probe"] = {
                "kind": "injected_future_test_clock_only", "at": future,
                "runtime_status": prepared.status(now=future).model_dump(mode="json"),
                "source_plan": job.source_plan(now=future), "observations_rewritten": False,
            }
            child_network = root / f"child-network-{mode}.json"
            if child_network.exists():
                evidence["child_network"] = read(child_network)
            save(root / f"result-{mode}.json", evidence)
            assert code in {0, 2}, evidence["runner"]
            assert evidence["health"] == 200 and evidence["ready"] == 200
            assert evidence["flyer_products"] > 0
            assert network["blocked_external_attempts"] == 0
            if mode == "not_due":
                assert evidence["runner"]["status"] == "not_due"
                assert not child_network.exists(), "not-due runner launched a rebuild"
                assert not evidence["source_plan"]["work_due"]
            else:
                assert evidence["child_network"]["blocked_external_attempts"] == 0
                assert source_state["publication"]["status"] == "reloaded"
                assert evidence["runner"]["runtime_reload"]["new_price_universe_id"] == evidence["price_universe_id"]
            print(json.dumps({key: evidence[key] for key in (
                "mode", "runner_exit", "flyer_products", "flyer_product_signature",
                "health", "ready", "elapsed_seconds",
            )}, ensure_ascii=False))
    finally:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        log.close()


def summarize(root):
    outcomes = [read(root / f"result-{mode}.json") for mode in (
        "first", "second", "restart", "not_due", "fetch_fail", "recovery", "rebuild",
    ) if (root / f"result-{mode}.json").exists()]
    final_hashes = outcomes[-1]["code_hashes_at_phase_start"]
    final = [r for r in outcomes if r.get("code_hashes_at_phase_start") == final_hashes]
    modes = {r["mode"] for r in final}
    assert {"not_due", "fetch_fail", "recovery"}.issubset(modes)
    # Fetch failure affects collection, while its valid LKG still goes through
    # a full successful ordinary rebuild, publication and serving reload.
    assert len(modes & {"first", "second", "restart", "rebuild", "fetch_fail", "recovery"}) >= 2
    assert len({r["flyer_product_signature"] for r in final}) == 1
    assert len({json.dumps(r["source_observations"]) for r in final}) == 1
    assert len({r["other_product_signature"] for r in final}) == 1
    assert len({r["serving_process_id"] for r in outcomes}) == len(outcomes)
    failure = next(r for r in final if r["mode"] == "fetch_fail")
    recovery = next(r for r in final if r["mode"] == "recovery")
    assert all(r["status"] == "failed" for r in failure["source_state"]["last_outcomes"].values())
    assert all(r["status"] == "success" for r in recovery["source_state"]["last_outcomes"].values())
    assert failure["source_snapshots"] == recovery["source_snapshots"]
    assert all(r["expiry_probe"]["runtime_status"]["usable_context_count"] == 0 for r in final)
    assert all(r["expiry_probe"]["runtime_status"]["status"] == "stale" for r in final)
    assert all(r["expiry_probe"]["source_plan"]["work_due"] for r in final)
    save(root / "ACCEPTANCE.json", {
        "status": "PASS", "production_activation": False,
        "scope": read(root / "harness.json")["scope"],
        "network": "loopback only; Willys flyer replay and injected failure; actual live source evidence separate",
        "verified_modes": [r["mode"] for r in final],
        "intermediate_code_modes": [r["mode"] for r in outcomes if r not in final],
        "intermediate_code_scope": "initial collection replay/publication and process restarts were executed; final code is compared separately",
        "final_code_hashes": final_hashes,
        "observation_times_preserved": True, "all_final_code_product_signatures_preserved": True,
        "flyer_products": recovery["flyer_products"],
        "flyer_store_counts": recovery["flyer_store_counts"],
        "flyer_product_signature": recovery["flyer_product_signature"],
        "price_universe_id": recovery["price_universe_id"],
        "source_snapshots": recovery["source_snapshots"],
        "expiry_probe_kind": "runtime and source-plan future clock, without observation rewrites",
        "expiry_probe_all_contexts_excluded": True,
    })


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "refresh-child":
        return refresh_child(sys.argv[2:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize", "phase", "serve", "run", "summarize"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--base", type=Path)
    parser.add_argument("--retained-coop-base", type=Path)
    parser.add_argument("--retained-main-db", type=Path)
    parser.add_argument("--willys-source-artifact", type=Path)
    parser.add_argument("--retained-citygross-root", type=Path)
    parser.add_argument("--inventory", type=Path)
    parser.add_argument("--collection", type=Path)
    parser.add_argument("--municipality", default="1280")
    parser.add_argument("--city", default="Malmö")
    parser.add_argument("--postal", default="21120")
    parser.add_argument("--port", type=int, default=18763)
    parser.add_argument("--mode", choices=("first", "second", "restart", "not_due", "fetch_fail", "recovery", "rebuild"))
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "initialize":
        initialize(args)
    elif args.action == "serve":
        serve(root, args.mode)
    elif args.action == "phase":
        phase(root, args.mode)
    elif args.action == "summarize":
        summarize(root)
    elif args.action == "run":
        for mode in ("first", "second", "restart", "not_due", "fetch_fail", "recovery"):
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "phase", "--root", str(root),
                            "--mode", mode], cwd=REPO, check=True)
        summarize(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
