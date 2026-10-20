"""Expire unused municipal attempt groups, preserving the current reference graph."""
from __future__ import annotations

import os
import re
import sqlite3
import stat
from datetime import timedelta
from pathlib import Path

from deploy.scripts.municipal_backup import SOURCE_ROOTS, current_files, recovery_roots
from deploy.scripts.storage_maintenance import (
    inventory,
    read_json,
    remove_owned,
    safe_root,
    setting,
)
from grocery_data.app.services.snapshot_retention import TOMBSTONE, strings

ATTEMPT = re.compile(r"^(\d{8}T\d{6}-[0-9a-f]{8}(?:[0-9a-f]{4})?)(?:\.sqlite(?:-wal|-shm|-journal)?|-raw)?$")
IDENTITY = re.compile(r"\d{8}T\d{6}-[0-9a-f]{8}(?:[0-9a-f]{4})?")


def prune_scope(root, *, protected_tokens, required_raw, now, apply=False):
    """Handle both flat ICA groups and other adapters' attempts directories."""
    root = safe_root(root)
    groups = {}
    if not root.exists():
        return {"removed": [], "reclaimable_bytes": 0}
    for parent in (root, root / "attempts"):
        safe_root(parent)
        if not parent.exists():
            continue
        for path in parent.iterdir():
            match = ATTEMPT.fullmatch(path.name)
            if match:
                groups.setdefault(match[1], []).append(path)
    protected = set(protected_tokens) | set(sorted(groups, reverse=True)[:2])
    cutoff = (now - timedelta(days=setting("STORAGE_SOURCE_RETENTION_DAYS", 14, 7, 365))).timestamp()
    candidates = []
    for identity, paths in groups.items():
        if identity in protected:
            continue
        inspected = [(path, inventory(path)) for path in paths]
        if any(info[2] >= cutoff for _, info in inspected):
            continue
        # Copied source databases can still refer to an older attempt's raw
        # bodies. Protect their owner group even if the current pointer does
        # not mention its directory name.
        owns_required_raw = False
        for path, (tree, _, _) in inspected:
            for name, info in tree.items():
                if not stat.S_ISREG(info[4]):
                    continue
                parts = (path / name).parts
                if any(parts[offset:] in required_raw for offset in range(len(parts))):
                    owns_required_raw = True
                    break
        if not owns_required_raw:
            candidates.extend(inspected)
    result = {"removed": [], "reclaimable_bytes": 0}
    for path, (tree, size, _) in candidates:
        remove_owned(path.parent, path, tree, apply=apply)
        result["removed"].append(path.name)
        result["reclaimable_bytes"] += size
    return result


def maintain(*, now, apply=False):
    # Validate hashes, WAL absence and every accepted reference using the same
    # graph as backup/restore. Missing or unreadable authority fails closed.
    recovery = current_files()
    roots = recovery_roots()
    required_raw, protected = set(), set()
    for path in recovery.values():
        if path.suffix == ".json":
            for value in strings(read_json(path)):
                protected.update(IDENTITY.findall(value))
        elif path.suffix in {".sqlite", ".sqlite3", ".db"}:
            with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
                tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "raw_snapshots" not in tables:
                    continue
                for (location,) in db.execute(
                    "SELECT r.payload_location FROM raw_snapshots r "
                    "JOIN catalog_snapshots s ON s.id=r.catalog_snapshot_id "
                    "WHERE json_extract(s.metrics,?) IS NULL", ("$." + TOMBSTONE,)):
                    relative = Path(location)
                    if relative.is_absolute() or ".." in relative.parts:
                        raise ValueError("unsafe municipal raw dependency")
                    required_raw.add(relative.parts)
    result = {"kind": "municipal_attempts", "removed": [], "reclaimable_bytes": 0,
              "applied": apply}
    for variable, default in SOURCE_ROOTS.items():
        base = safe_root(Path(os.getenv(variable, str(roots["grocery"] / default))))
        if not base.exists():
            continue
        for scope in base.iterdir():
            if not re.fullmatch(r"\d{4}", scope.name):
                continue
            safe_root(scope)
            states = [scope / name for name in ("source-state.json", "structured-source.json", "latest-failure.json")
                      if (scope / name).exists()]
            if not states:
                continue
            # Preserve diagnostic/partial references as well as approved ones.
            tokens = protected.copy()
            for state in states:
                for value in strings(read_json(state)):
                    tokens.update(IDENTITY.findall(value))
            row = prune_scope(scope, protected_tokens=tokens, required_raw=required_raw,
                              now=now, apply=apply)
            result["removed"].extend(f"{default}/{scope.name}/{name}" for name in row["removed"])
            result["reclaimable_bytes"] += row["reclaimable_bytes"]
    return result
