"""Bounded retention of Smako-owned, reproducible files and completed backups.

All mutations require the caller's existing production operation lease. There
is deliberately no traversal of /var/tmp, Docker volumes or arbitrary release
archives. Unknown names, symlinks, incomplete manifests and current pointers
are never interpreted as disposable data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from datetime import UTC, datetime, timedelta
from pathlib import Path

BUNDLE = re.compile(r"\d{8}T\d{6}Z")
BLOB = re.compile(r"[0-9a-f]{64}\.json")
STAGING = re.compile(r"\.\d{8}T\d{6}Z\.[0-9a-f]{32}\.tmp")
REPORT = re.compile(r"(?:daily-refresh|source-retry)-\d{8}T\d{6}\.\d{6}Z-[0-9a-f]{8}\.json")


def setting(name, default, minimum, maximum):
    value = int(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} outside supported retention range")
    return value


def safe_root(path):
    """Reject link/junction components before resolving, including the root."""
    path = Path(path).absolute()
    for part in [path, *path.parents]:
        if part.is_symlink() or (hasattr(part, "is_junction") and part.is_junction()):
            raise ValueError("maintenance root contains a link")
    if path.exists() and not path.is_dir():
        raise ValueError("maintenance root is not a directory")
    return path.resolve()


def inventory(path):
    """A bounded-memory walk; never follow a link or remove a special file."""
    entries, size, newest = {}, 0, 0.0
    pending = [path]
    while pending:
        current = pending.pop()
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("maintenance candidate contains a link")
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            raise ValueError("maintenance candidate contains a special file")
        entries[current.relative_to(path).as_posix()] = (
            info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_mode)
        newest = max(newest, info.st_mtime)
        if stat.S_ISDIR(info.st_mode):
            pending.extend(current.iterdir())
        else:
            size += info.st_size
        if len(entries) > 100_000:
            raise ValueError("maintenance candidate exceeds inventory bound")
    return entries, size, newest


def remove_owned(root, path, expected, *, apply):
    root = safe_root(root)
    if path.parent != root or path.resolve().parent != root:
        raise ValueError("maintenance candidate escaped its exact parent")
    if inventory(path)[0] != expected:
        raise ValueError("maintenance candidate changed during inventory")
    if apply:
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path, *, limit=4 * 1024 * 1024):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("maintenance metadata is missing, linked or oversized")
    return json.loads(path.read_bytes())


def backup_inventory(path, *, verify=False):
    tree, size, newest = inventory(path)
    payload = read_json(path / "manifest.json")
    if payload.get("schema_version") != "grocery-beta-backup-v1":
        raise ValueError("unknown backup schema")
    rows = payload.get("files")
    if not isinstance(rows, list) or not rows:
        raise ValueError("incomplete backup manifest")
    declared = set()
    for row in rows:
        relative = row["path"]
        if (not isinstance(relative, str) or "\\" in relative
                or Path(relative).is_absolute() or ".." in Path(relative).parts
                or Path(relative).as_posix() != relative or relative in declared):
            raise ValueError("unsafe backup manifest path")
        declared.add(relative)
        candidate = path / relative
        if (relative not in tree or not stat.S_ISREG(tree[relative][4])
                or type(row.get("bytes")) is not int or row["bytes"] != tree[relative][2]
                or not re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", ""))):
            raise ValueError("incomplete backup file")
        if verify and sha256(candidate) != row["sha256"]:
            raise ValueError("retained recovery backup failed checksum verification")
    actual = {name for name, info in tree.items() if stat.S_ISREG(info[4])}
    if actual != declared | {"manifest.json"}:
        raise ValueError("backup contains undeclared files")
    return tree, size, newest


def maintain_backups(root, *, now, apply=False):
    """Run BEFORE allocation as well as after success; keep two verified copies.

    Count/byte ceilings supplement the age limit. A minimum of two complete
    backups wins over a ceiling; that exception is explicit in the receipt.
    Unrecognized historical backups and privacy ledgers are outside this policy.
    """
    root = safe_root(root)
    count = setting("BACKUP_MAX_COUNT", 3, 2, 365)
    days = setting("BACKUP_RETENTION_DAYS", 14, 1, 365)
    budget = setting("BACKUP_MAX_BYTES", 32 * 1024**3, 1, 1024**4)
    result = {"kind": "backups", "removed": [], "reclaimable_bytes": 0,
              "protected": [], "unknown": [], "max_count": count, "max_bytes": budget}
    if not root.exists():
        return result
    bundles = []
    for path in sorted(root.iterdir(), reverse=True):
        if not BUNDLE.fullmatch(path.name):
            continue
        try:
            stamp = datetime.strptime(path.name, "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
            if stamp > now:
                raise ValueError("backup is from the future")
            tree, size, newest = backup_inventory(path)
        except (OSError, ValueError, KeyError, TypeError):
            result["unknown"].append(path.name)
            continue
        bundles.append((path, stamp, tree, size))
    # Re-read hashes of the recovery floor before deleting any old copy.
    for path, _, _, _ in bundles[:2]:
        backup_inventory(path, verify=True)
        result["protected"].append(path.name)
    retained_bytes = sum(row[3] for row in bundles[:2])
    retained_count = min(2, len(bundles))
    for path, stamp, tree, size in bundles[2:]:
        expired = stamp < now - timedelta(days=days)
        if expired or retained_count >= count or retained_bytes + size > budget:
            remove_owned(root, path, tree, apply=apply)
            result["removed"].append(path.name)
            result["reclaimable_bytes"] += size
        else:
            retained_count += 1
            retained_bytes += size
    # A dead worker may leave its private staging directory. The lease
    # excludes any live backup writer; retain a full day for diagnosis.
    for path in root.iterdir():
        if STAGING.fullmatch(path.name):
            tree, size, newest = inventory(path)
            if newest < (now - timedelta(days=1)).timestamp():
                remove_owned(root, path, tree, apply=apply)
                result["removed"].append(path.name)
                result["reclaimable_bytes"] += size
    result.update(retained_bytes=retained_bytes, retained_count=retained_count,
                  minimum_exceeds_budget=retained_bytes > budget, applied=apply)
    return result


def maintain_artifacts(root, *, now, apply=False):
    """Only unreferenced content-addressed blobs older than the reader grace."""
    root = safe_root(root)
    result = {"kind": "price_artifacts", "removed": [], "reclaimable_bytes": 0}
    if not root.exists():
        return result
    safe_root(root / "active")
    blobs = safe_root(root / "artifacts")
    protected = set()
    manifests = list((root / "active").glob("*.json"))
    # No authority is not permission to discard an entire cache.
    if not manifests:
        result["status"] = "no_active_manifest"
        return result
    observed = {}
    for manifest in manifests:
        data = read_json(manifest)
        value = data.get("artifact_file", "")
        if not re.fullmatch(r"artifacts/[0-9a-f]{64}\.json", value):
            raise ValueError("invalid active artifact reference")
        artifact = root / value
        inventory(artifact)
        if (artifact.stat().st_size != data.get("artifact_bytes")
                or sha256(artifact) != data.get("artifact_sha256")):
            raise ValueError("active artifact failed verification; no cleanup")
        protected.add(artifact.name)
        observed[manifest] = sha256(manifest)
    days = setting("STORAGE_ARTIFACT_GRACE_DAYS", 2, 1, 30)
    cutoff = (now - timedelta(days=days)).timestamp()
    for path in sorted(blobs.iterdir()) if blobs.exists() else []:
        if not BLOB.fullmatch(path.name) or path.name in protected:
            continue
        tree, size, newest = inventory(path)
        if newest >= cutoff:
            continue
        if any(sha256(p) != digest for p, digest in observed.items()):
            raise ValueError("active pointer changed under maintenance lease")
        remove_owned(blobs, path, tree, apply=apply)
        result["removed"].append(path.name)
        result["reclaimable_bytes"] += size
    result.update(protected=sorted(protected), applied=apply)
    return result


def maintain_build_staging(universe, *, now, apply=False):
    root = safe_root(universe) / "refresh-candidates"
    safe_root(root)
    result = {"kind": "build_staging", "removed": [], "reclaimable_bytes": 0}
    if not root.exists():
        return result
    for path in root.iterdir():
        # TemporaryDirectory from managed build; never arbitrary directories
        # or named operator-provided candidates.
        if not re.fullmatch(r"\.price-universe-source-[a-z0-9_]{8}", path.name):
            continue
        tree, size, newest = inventory(path)
        if newest < (now - timedelta(days=1)).timestamp():
            remove_owned(root, path, tree, apply=apply)
            result["removed"].append(path.name)
            result["reclaimable_bytes"] += size
    result["applied"] = apply
    return result


def maintain_reports(root, *, now, apply=False):
    root = safe_root(root)
    result = {"kind": "refresh_reports", "removed": [], "reclaimable_bytes": 0}
    if not root.exists():
        return result
    days = setting("STORAGE_REPORT_RETENTION_DAYS", 14, 1, 365)
    count = setting("STORAGE_REPORT_MAX_COUNT", 128, 2, 10_000)
    paths = sorted((p for p in root.iterdir() if REPORT.fullmatch(p.name)),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    for index, path in enumerate(paths):
        tree, size, newest = inventory(path)
        if index >= 2 and (index >= count or newest < (now - timedelta(days=days)).timestamp()):
            remove_owned(root, path, tree, apply=apply)
            result["removed"].append(path.name)
            result["reclaimable_bytes"] += size
    result["applied"] = apply
    return result


def run_locked(*, now=None, apply=False):
    """Called under RefreshRunLock by backup, refresh and installation paths."""
    now = now or datetime.now(UTC)
    universe = safe_root(os.environ["PRICE_UNIVERSE_CACHE_ROOT"])
    work = [
        (maintain_backups, Path(os.getenv("BACKUP_ROOT", "/srv/app/var/backups"))),
        (maintain_artifacts, universe),
        (maintain_artifacts, universe / "external-provider-cache"),
        (maintain_build_staging, universe),
        (maintain_reports, Path(os.getenv("REFRESH_REPORT_DIR", str(universe.parent / "reports/refresh")))),
    ]
    rows = []
    for function, root in work:
        try:
            rows.append(function(root, now=now, apply=apply))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            rows.append({"kind": function.__name__, "status": "blocked",
                         "error_type": type(exc).__name__})
    result = {"schema": "smako-storage-maintenance-v1", "observed_at": now.isoformat(),
              "status": "blocked" if any(r.get("status") == "blocked" for r in rows) else "complete",
              "applied": apply, "categories": rows,
              "reclaimable_bytes": sum(r.get("reclaimable_bytes", 0) for r in rows)}
    if apply:
        from grocery_data.app.services.durable_files import atomic_write_bytes
        # One overwritten receipt, not an ever-growing cleanup log.
        target = universe.parent / "reports/operations/storage-maintenance.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_bytes(target, json.dumps(result, sort_keys=True).encode())
        target.chmod(0o600)
    return result


def main():
    import argparse

    from deploy.scripts.backup_sqlite import configured_database_paths
    from grocery_data.app.services.manual_refresh_operations import (
        RefreshRunLock,
        production_refresh_lock_path,
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply retention; default is inventory only")
    args = parser.parse_args()
    databases = configured_database_paths()
    lock = RefreshRunLock(production_refresh_lock_path(
        databases["grocery/grocery_data.sqlite"], Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"])))
    lock.acquire()
    try:
        print(json.dumps(run_locked(apply=args.apply), sort_keys=True))
    finally:
        lock.release()


def run_due_locked(*, now=None):
    """Reuse the refresh worker's lease, at most once per six hours."""
    now = now or datetime.now(UTC)
    root = Path(os.environ["PRICE_UNIVERSE_CACHE_ROOT"]).parent
    receipt = root / "reports/operations/storage-maintenance.json"
    if receipt.exists():
        data = read_json(receipt)
        observed = datetime.fromisoformat(data["observed_at"])
        if observed <= now < observed + timedelta(hours=6) and data.get("status") == "complete":
            return None
    return run_locked(now=now, apply=True)


if __name__ == "__main__":
    main()
