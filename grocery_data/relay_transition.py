"""Preserve a stopped relay generation under its existing locks; never import.

The old workspace/inbox remains in place. The next generation MUST use different
workspace and inbox paths. The archive is a resumable content-addressed evidence
set, not a fabricated last-success receipt. No source bytes are rewritten.
"""

import argparse
import hashlib
import json
import sqlite3
import time
import zipfile
from contextlib import ExitStack
from pathlib import Path

from grocery_data.app.services.durable_files import atomic_write_bytes
from grocery_data.app.services.manual_refresh_operations import (
    RefreshAlreadyRunningError,
    RefreshRunLock,
    production_refresh_lock_path,
)


def preserve(
    *,
    archive: Path,
    workspace: Path | None = None,
    inbox: Path | None = None,
    database: Path | None = None,
    price_root: Path | None = None,
    wait_seconds=0,
):
    if not workspace and not inbox:
        raise ValueError("workspace or inbox required")
    if inbox and (not database or not price_root):
        raise ValueError("inbox requires the actual database and universe lock identity")
    roots = [p.resolve(strict=True) for p in (workspace, inbox) if p]
    archive = archive.resolve()
    if any(archive == p or archive.is_relative_to(p) or p.is_relative_to(archive) for p in roots):
        raise ValueError("archive must be separate from source state")
    lock_paths = []
    if workspace:
        lock_paths.extend(
            workspace / name for name in ("local-workflow.lock", "local-collection.lock")
        )
    if inbox:
        lock_paths.append(production_refresh_lock_path(database, price_root))
    deadline = time.monotonic() + wait_seconds
    with ExitStack() as stack:
        for path in lock_paths:
            while True:
                try:
                    stack.enter_context(RefreshRunLock(path))
                    break
                except RefreshAlreadyRunningError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(min(1, max(0, deadline - time.monotonic())))
        files = {}
        receipts = []
        for label, root in (("workspace", workspace), ("inbox", inbox)):
            if root is None:
                continue
            for path in sorted(root.rglob("*")):
                if path.is_symlink():
                    raise ValueError("source symlink requires explicit operator review")
                if path.is_file() and (
                    path.suffix == ".smako-source"
                    or path.name in {"last-success.json", "last-qualified-source.json"}
                ):
                    data = path.read_bytes()
                    digest = hashlib.sha256(data).hexdigest()
                    key = label + "/" + path.relative_to(root).as_posix()
                    files[key] = {
                        "sha256": digest,
                        "bytes": len(data),
                        "kind": "artifact" if path.suffix == ".smako-source" else "receipt",
                    }
                    if path.name == "last-success.json":
                        receipts.append(json.loads(data))
                    target = archive / "objects" / digest
                    if target.exists():
                        if target.read_bytes() != data:
                            raise ValueError("archive object collision")
                    else:
                        atomic_write_bytes(target, data)
        published = set()
        received = set()
        if database:
            active = json.loads((price_root / "active/city-lund.json").read_bytes())
            with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
                for sid, state, active_flag, metrics in db.execute(
                    "SELECT id,state,is_active,metrics FROM catalog_snapshots"
                ):
                    digest = json.loads(metrics or "{}").get("source_artifact", {}).get("sha256")
                    if digest:
                        received.add(digest)
                        if active_flag and state == "promoted" and sid in active["snapshot_ids"]:
                            published.add(digest)
        acknowledged = {
            r.get("sha256")
            for r in receipts
            if r.get("server", {}).get("activation") in {"normal_managed_refresh", "already_active"}
        }
        inbox_hashes = {
            v["sha256"]
            for k, v in files.items()
            if k.startswith("inbox/") and v["kind"] == "artifact"
        }
        for item in files.values():
            if item["kind"] != "artifact":
                continue
            digest = item["sha256"]
            with zipfile.ZipFile(archive / "objects" / digest) as z:
                manifest = json.loads(z.read("manifest.json"))
            item["source_scope"] = manifest["source_scope"]
            item["observed_from"] = manifest["observed_from"]
            item["source_snapshot_id"] = manifest["source_snapshot_id"]
            item["status"] = (
                "acknowledged"
                if digest in acknowledged
                else "published_without_local_receipt"
                if digest in published
                else "received_not_published"
                if digest in received | inbox_hashes
                else "pending_delivery"
            )
            item["disposition"] = "preserved_in_old_generation_not_routed_to_new_contract"
        report = {
            "schema": "smako-relay-transition-v1",
            "files": files,
            "source_files_unchanged": True,
            "imports_performed": 0,
            "new_success_receipts_written": 0,
        }
        content = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
        inventory_id = hashlib.sha256(content).hexdigest()
        atomic_write_bytes(archive / "inventories" / (inventory_id + ".json"), content)
        atomic_write_bytes(archive / "latest.json", content)
        return {**report, "inventory_sha256": inventory_id}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("archive", "workspace", "inbox", "database", "price-root"):
        p.add_argument("--" + name, type=Path, required=name == "archive")
    p.add_argument("--wait-seconds", type=float, default=300)
    args = p.parse_args()
    print(json.dumps(preserve(**vars(args))))


if __name__ == "__main__":
    main()
