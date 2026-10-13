"""Explicit source relay operator commands; no automatic scheduling."""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import sqlite3
import subprocess
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from uuid import uuid4

from grocery_data.app.connectors.willys.client import WillysClient
from grocery_data.app.connectors.willys.connector import WillysConnector
from grocery_data.app.domain import GeographicArea
from grocery_data.app.services.collector import GroceryCollector
from grocery_data.app.services.durable_files import atomic_write_bytes, require_free_space
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock
from grocery_data.app.services.prepared_universe_activation import PreparedUniverseArtifactStore
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore
from grocery_data.app.services.source_artifact import (
    APPROVED_WILLYS_CONTEXTS,
    SourceArtifactError,
    export_source_artifact,
    import_source_candidate,
    verify_source_artifact,
)
from grocery_data.app.storage import create_database_engine, create_schema, create_session_factory
from grocery_data.relay_config import RelayTransport


def _json(value):
    print(json.dumps(value, ensure_ascii=False, default=str))


async def collect(args):
    if any(
        os.getenv(k)
        for k in (
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
            "http_proxy",
            "https_proxy",
            "all_proxy",
        )
    ):
        raise SourceArtifactError("local relay does not support proxy configuration")
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with RefreshRunLock(root / "local-collection.lock"):
        from grocery_data.relay_storage import collection_capacity
        collection_capacity(root)
        run = root / "runs" / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex}"
        run.mkdir(parents=True, exist_ok=False)
        database = run / "candidate.sqlite3"
        # Durable WAL avoids Windows' costly per-row journal replacement; FULL
        # synchronization is retained. This is an isolated candidate database.
        with sqlite3.connect(database) as db:
            if db.execute("PRAGMA journal_mode=WAL").fetchone()[0] != "wal":
                raise SourceArtifactError("local candidate WAL setup failed")
            if db.execute("PRAGMA synchronous").fetchone()[0] != 2:
                raise SourceArtifactError("durable FULL synchronization is required")
        engine = create_database_engine("sqlite+pysqlite:///" + database.as_posix())
        create_schema(engine)
        factory = create_session_factory(engine)
        raw = FilesystemRawSnapshotStore(run / "raw")
        client = WillysClient(requests_per_second=1)
        count = 0
        request_budget = 1500
        statuses = Counter()
        challenges = 0
        started_at = datetime.now(UTC)
        started = monotonic()
        collection_seconds = min(7200, max(0, getattr(args, "collection_seconds", 7200)))

        async def bound(request):
            nonlocal count
            if count >= request_budget or monotonic() - started > collection_seconds:
                raise SourceArtifactError("bounded local collection stopped")
            count += 1
            if count % 100 == 0:
                require_free_space(run, required_bytes=8 * 1024**2, reserve_bytes=64 * 1024**2)
                atomic_write_bytes(run / "progress.json", json.dumps({"requests": count, "request_budget": request_budget,
                    "runtime_seconds": round(monotonic()-started, 3), "status": "collecting"}).encode())

        client._client.event_hooks["request"].append(bound)

        async def record_response(response):
            nonlocal challenges
            statuses[str(response.status_code)] += 1
            if "html" in response.headers.get("content-type", "").lower():
                await response.aread()
                body = response.text[:4096].lower()
                challenges += any(x in body for x in ("request blocked", "captcha", "challenge"))

        client._client.event_hooks["response"].append(record_response)
        from grocery_data.app.services.willys_municipal_scope import relay_municipality
        municipality = relay_municipality(root, getattr(args, "municipality", None))
        area = GeographicArea(city="Lund")
        connector = WillysConnector(client=client, allowed_store_ids=APPROVED_WILLYS_CONTEXTS)
        if municipality:
            from grocery_data.app.domain.municipality import municipality_name
            area = GeographicArea(city=municipality_name(municipality), mode="municipality", municipality_code=municipality)
            connector = WillysConnector(client=client)
            discovery = await connector.fetch_stores(area)
            selected = connector.parse_stores(discovery, ["live:registry"] * len(discovery.documents), area)
            connector.allowed_store_ids = frozenset(s.external_id for s in selected)
            request_budget = min(5900, 1000 * len(selected) + 100)
            atomic_write_bytes(run / "municipality-inventory.json", json.dumps(connector.municipality_inventory, ensure_ascii=False).encode())
            if not selected:
                await connector.aclose()
                engine.dispose()
                raise SourceArtifactError("no verified municipal online contexts")
        from grocery_data.app.services.catalog_checkpoint import CatalogCheckpoints
        checkpoints = CatalogCheckpoints(root / "store-checkpoints", area=area,
            boundary=connector.municipality_boundary, parser_version=connector.parser_version,
            deadline=started + collection_seconds)
        connector.checkpoints = checkpoints
        status = "failed"
        try:
            result = await GroceryCollector(factory, raw).collect_area(
                connector, area, auto_promote=False,
                scope_key=area.city.casefold() if municipality else None
            )
            destination = root / "completed" / f"{result.snapshot_id}.smako-source"
            export_source_artifact(
                factory, raw, result.snapshot_id, destination,
                original_request_count=count + checkpoints.reused_requests,
                collection_started_at=min(started_at, checkpoints.oldest),
                municipality_boundary=connector.municipality_boundary
            )
            verified = verify_source_artifact(destination)
            status = "complete"
            return {
                "status": "complete",
                "artifact": str(destination),
                "sha256": verified.artifact_sha256,
                "source": "willys",
                "collection_location": "LOCAL_RELAY",
                "requests": count,
                "rows": verified.manifest.row_count,
                "products": verified.manifest.product_count,
                "started_at": started_at,
                "finished_at": datetime.now(UTC),
                "runtime_seconds": round(monotonic() - started, 3),
                "http_statuses": dict(statuses),
                "challenges": challenges,
                "artifact_bytes": destination.stat().st_size,
                "validation": "PASS",
                "completion": {
                    k: v.model_dump(mode="json") for k, v in verified.completion.items()
                },
            }
        except Exception:
            if checkpoints.deferred:
                status = "deferred"
                return {"status": status, "stores": checkpoints.stores,
                        "requests": count, "reason": "collection_window"}
            raise
        finally:
            await connector.aclose()
            engine.dispose()
            atomic_write_bytes(
                run / "collection-metrics.json",
                json.dumps(
                    {
                        "status": status,
                        "started_at": started_at.isoformat(),
                        "finished_at": datetime.now(UTC).isoformat(),
                        "runtime_seconds": round(monotonic() - started, 3),
                        "requests": count,
                        "reused_requests": checkpoints.reused_requests,
                        "stores": checkpoints.stores,
                        "http_statuses": dict(statuses),
                        "challenges": challenges,
                        "http_errors": sum(v for k, v in statuses.items() if int(k) >= 400),
                    }
                ).encode(),
            )


def push(args):
    transport = getattr(args, "transport", None) or RelayTransport(ssh_host=args.host)
    verified = verify_source_artifact(args.artifact)
    digest = verified.artifact_sha256
    encoded = base64.b64encode(args.artifact.read_bytes()).decode("ascii")
    # Stream over SSH into the existing ops container as the data owner. The
    # SSH login need not own /srv/smako/data or gain extra host privileges.
    script = f"""from pathlib import Path
from hashlib import sha256
from uuid import uuid4
import base64, os
from grocery_data.app.services.durable_files import _fsync_directory, require_free_space
def require(condition, message):
 if not condition: raise ValueError(message)
payload=base64.b64decode({encoded!r},validate=True)
require(sha256(payload).hexdigest()=={digest!r}, 'transport hash mismatch')
root=Path({transport.inbox!r})
parent=root.parent
for directory in (parent,root):
 require(not directory.is_symlink(), 'inbox cannot be a symlink')
 directory.mkdir(mode=0o700,exist_ok=True)
 os.chmod(directory,0o700)
target=root/({digest!r}+'.smako-source')
require(not target.is_symlink(), 'inbox artifact cannot be a symlink')
if target.exists():
 require(sha256(target.read_bytes()).hexdigest()=={digest!r}, 'inbox collision')
else:
 require_free_space(root,required_bytes=len(payload),reserve_bytes=512*1024*1024)
 temporary=root/('.'+uuid4().hex+'.partial')
 try:
  fd=os.open(temporary,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
  with os.fdopen(fd,'wb') as handle:
   require(handle.write(payload)==len(payload), 'short upload write')
   handle.flush();os.fsync(handle.fileno())
  try: os.link(temporary,target)
  except FileExistsError:
   require(sha256(target.read_bytes()).hexdigest()=={digest!r}, 'inbox collision')
  _fsync_directory(root)
 finally:
  temporary.unlink(missing_ok=True)
print('uploaded_to_inbox_only')
"""
    subprocess.run(
        [
            "ssh",
            "-oBatchMode=yes",
            "-oConnectTimeout=15",
            transport.ssh_host,
            "docker",
            "exec",
            "-i",
            "--user",
            "10001:10001",
            transport.container,
            "python",
            "-",
        ],
        input=script,
        text=True,
        capture_output=True,
        check=True,
        timeout=180,
    )
    return {
        "status": "uploaded",
        "sha256": digest,
        "inbox_artifact": f"{transport.inbox}/{digest}.smako-source",
        "active_data_modified": False,
    }


async def import_and_activate(args):
    from contextlib import ExitStack

    from grocery_data.app.services.municipal_rollout import municipal_environment, scope_for_city
    scope_context = ExitStack()
    if os.name != "nt" and os.geteuid() == 0:
        raise SourceArtifactError("production import must run as the application ops UID, not root")
    from deploy.scripts.run_daily_refresh import (
        _confirm_loaded_runtime,
        _operations_lock,
        _reload_runtime,
        _run_locked,
        _write_status,
        build_refresh_command,
    )
    from grocery_data import __main__ as cli
    from grocery_data.app.services.snapshot_manager import SnapshotManager

    settings, engine, factory = cli._runtime()
    lock = _operations_lock()
    lock.acquire()
    try:
        result = await import_source_candidate(
            args.artifact, factory, FilesystemRawSnapshotStore(settings.raw_snapshot_root)
        )
        manager = SnapshotManager(factory)
        snapshot = manager.get(result["snapshot_id"])
        if snapshot.state == "promoted" and not snapshot.is_active:
            return {**result, "activation": "already_imported_superseded"}
        verified = verify_source_artifact(args.artifact)
        city = verified.manifest.source_scope.geographic_area.city
        scope = scope_for_city(city)
        if scope is not None:
            scope_context.enter_context(municipal_environment(scope))
        elif os.getenv("REFRESH_CITY", "Lund").casefold() != city.casefold():
            raise SourceArtifactError("source municipality differs from configured ordinary refresh city")
        active_store = PreparedUniverseArtifactStore(settings.price_universe_cache_root)
        active = active_store.read_active(city)
        if snapshot.is_active and active and snapshot.id in active.snapshot_ids:
            active_store.resolve_active_artifact(city, verify_hash=True)
            # A lost reload response must not force another expensive reload.
            # Only exact, scoped ready evidence can acknowledge an existing load.
            loaded = _confirm_loaded_runtime(active.universe_id) or _reload_runtime()
            if loaded.get("new_price_universe_id") != active.universe_id:
                raise SourceArtifactError("source published but runtime activation not confirmed")
            return {**result, "activation": "already_active", "universe_id": active.universe_id,
                    "active_universe_unchanged": True}
        if snapshot.state != "promoted":
            manager.promote(snapshot.id)
        command = build_refresh_command() + ["--chain", "citygross", "--no-external-refresh"]
        # Reuse the managed build/activation/LKG wrapper. Campaign jobs may run
        # when due; this route does not request a new base catalog collection.
        statuses = []
        def capture_status(status):
            statuses.append(status)
            _write_status(status)

        code = _run_locked(
            lock, started_at=datetime.now(UTC), command=command, run_kind="source_relay_import",
            status_writer=capture_status,
        )
        if code not in (0, 2):
            raise SourceArtifactError("normal PriceUniverse activation did not complete")
        activated = active_store.read_active(city)
        if activated is None or snapshot.id not in activated.snapshot_ids:
            raise SourceArtifactError("qualified source was not activated; existing LKG retained")
        active_store.resolve_active_artifact(city, verify_hash=True)
        if not statuses or statuses[-1].get("runtime_reload", {}).get("new_price_universe_id") != activated.universe_id:
            raise SourceArtifactError("source published but runtime activation not confirmed")
        return {
            **result,
            "universe_id": activated.universe_id,
            "activation": "normal_managed_refresh",
            "exit_code": code,
        }
    finally:
        scope_context.close()
        engine.dispose()
        lock.release()


def parser():
    p = argparse.ArgumentParser(
        description="Explicit validated OWN source relay; no background persistence"
    )
    sub = p.add_subparsers(dest="command", required=True)
    c = sub.add_parser("collect")
    c.add_argument("source", choices=["willys"])
    c.add_argument("--workspace", type=Path, required=True)
    c.add_argument("--municipality", help="Official municipality code; opt-in store-bound online catalogs")
    v = sub.add_parser("verify")
    v.add_argument("artifact", type=Path)
    s = sub.add_parser("push")
    s.add_argument("artifact", type=Path)
    s.add_argument("--host", choices=["smako"], required=True)
    i = sub.add_parser("import")
    i.add_argument("artifact", type=Path)
    return p


def main():
    if os.getenv("SMAKO_RECOVERY_READ_ONLY", "").lower() == "true":
        _json({"status": "unavailable", "code": "recovery_read_only"})
        return 3
    args = parser().parse_args()
    try:
        if args.command == "collect":
            result = asyncio.run(collect(args))
        elif args.command == "verify":
            value = verify_source_artifact(args.artifact)
            result = {
                "status": "verified",
                "sha256": value.artifact_sha256,
                "manifest": value.manifest.model_dump(mode="json", exclude={"payloads"}),
            }
        elif args.command == "push":
            result = push(args)
        else:
            result = asyncio.run(import_and_activate(args))
    except Exception as exc:  # noqa: BLE001 - redact at the operator boundary
        # Never print arbitrary request/credential-bearing exception bodies.
        from grocery_data.app.services.failure_diagnostics import failure_details
        _json({"status": "failed", "error_type": type(exc).__name__,
               "causes": failure_details(exc)})
        return 1
    _json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
