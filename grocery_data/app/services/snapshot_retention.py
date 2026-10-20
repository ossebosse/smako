"""Retire old, inactive source payloads while preserving provenance metadata.

The caller holds the shared production lease. Current prices, LKG, published
lineage, source incidents and field-evidence references always win over age.
Only the large parsed rows and raw bodies expire; import identities and their
original observation times remain, with an explicit retirement tombstone.
SQLite reuses freed pages instead of requiring an exclusive full VACUUM.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path

from deploy.scripts.storage_maintenance import inventory, read_json, safe_root, setting, sha256

OWNED = {"catalog_snapshots", "raw_snapshots", "source_products", "products",
         "price_observations", "promotions", "parser_failures"}
TOMBSTONE = "storage_payload_retired_at"


def quoted(name):
    return '"' + name.replace('"', '""') + '"'


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from strings(child)


def protected_snapshots(connection, *, universe, operations):
    """Read authoritative pointers and explicit evidence locks, never infer age."""
    protected = set()
    for root in (universe / "active", universe / "external-provider-cache/active", operations):
        safe_root(root)
        if root.exists():
            for path in root.rglob("*.json"):
                if path.name == "storage-maintenance.json":
                    continue
                protected.update(strings(read_json(path)))
    tables = {row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    for table in tables - OWNED:
        columns = {row[1] for row in connection.execute(f"PRAGMA table_info({quoted(table)})")}
        # These identifiers also occur without a relational FK, for example
        # store links and immutable physical-validation locks.
        for column in columns & {"snapshot_id", "source_snapshot_id", "active_snapshot_id"}:
            protected.update(row[0] for row in connection.execute(
                f"SELECT DISTINCT {quoted(column)} FROM {quoted(table)} WHERE {quoted(column)} IS NOT NULL"))
        if "source_snapshot_ids" in columns:
            for (encoded,) in connection.execute(f"SELECT source_snapshot_ids FROM {quoted(table)}"):
                protected.update(strings(json.loads(encoded)))
        # Never cascade away or detach a reference belonging to another system.
        for fk in connection.execute(f"PRAGMA foreign_key_list({quoted(table)})"):
            target, column, target_column = fk[2:5]
            if target not in OWNED:
                continue
            if target_column != "id":
                raise ValueError("unrecognized snapshot evidence relationship")
            projection = "id" if target == "catalog_snapshots" else "catalog_snapshot_id"
            protected.update(row[0] for row in connection.execute(
                f"SELECT DISTINCT t.{quoted(projection)} FROM {quoted(target)} t "
                f"JOIN {quoted(table)} r ON r.{quoted(column)}=t.id"))
    for table in OWNED - {"catalog_snapshots"}:
        for fk in connection.execute(f"PRAGMA foreign_key_list({quoted(table)})"):
            target, column = fk[2:4]
            if target in {"products", "source_products"}:
                protected.update(row[0] for row in connection.execute(
                    f"SELECT DISTINCT t.catalog_snapshot_id FROM {quoted(target)} t "
                    f"JOIN {quoted(table)} r ON r.{quoted(column)}=t.id "
                    "WHERE r.catalog_snapshot_id<>t.catalog_snapshot_id"))
    return protected


def maintain(database, raw_root, *, universe, operations, now, apply=False):
    database = Path(database).absolute()
    safe_root(database.parent)
    if database.is_symlink() or not database.is_file():
        raise ValueError("source retention requires a regular existing database")
    raw_root = safe_root(raw_root)
    days = setting("STORAGE_SOURCE_RETENTION_DAYS", 14, 7, 365)
    limit = setting("STORAGE_SOURCE_RETIRE_BATCH", 32, 1, 128)
    result = {"kind": "source_history", "retired": [], "raw_files_removed": 0,
              "reclaimable_bytes": 0, "applied": apply}
    with sqlite3.connect(database.as_uri() + ("?mode=rw" if apply else "?mode=ro"),
                         uri=True, timeout=5) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not OWNED <= tables or "collector_runs" not in tables:
            result["status"] = "unsupported_database"
            return result
        protected = protected_snapshots(connection, universe=universe, operations=operations)
        for identity, previous in connection.execute(
                "SELECT id,previous_active_snapshot_id FROM ("
                "SELECT id,previous_active_snapshot_id,is_active,"
                "row_number() OVER (PARTITION BY chain,scope_key ORDER BY created_at DESC,id DESC) AS n "
                "FROM catalog_snapshots) WHERE is_active=1 OR n<=2"):
            protected.add(identity)
            if previous:
                protected.add(previous)
        cutoff = (now - timedelta(days=days)).isoformat()
        candidates = connection.execute(
            "SELECT s.id,s.metrics FROM catalog_snapshots s "
            "JOIN collector_runs r ON r.id=s.collector_run_id "
            "WHERE s.is_active=0 AND s.state IN ('promoted','rejected') AND r.finished_at IS NOT NULL "
            "AND julianday(s.created_at)<julianday(?) AND json_extract(s.metrics,?) IS NULL ORDER BY s.created_at,s.id",
            (cutoff, "$." + TOMBSTONE))
        selected_rows = []
        for identity, metrics in candidates:
            if identity in protected:
                continue
            selected_rows.append((identity, json.loads(metrics)))
            if len(selected_rows) >= limit:
                break
        candidates.close()
        for identity, metadata in selected_rows:
            # Retain raw metadata for original timestamps, hashes and import
            # receipts. Its bodies may be removed only after this transaction.
            if apply:
                # One snapshot per transaction: never hold the writer lock
                # across an entire historical backlog. Recheck field-evidence
                # references that the web app may have created meanwhile.
                connection.execute("BEGIN IMMEDIATE")
                if identity in protected_snapshots(connection, universe=universe, operations=operations):
                    connection.rollback()
                    continue
                for table in ("price_observations", "promotions", "products",
                              "source_products", "parser_failures"):
                    connection.execute(f"DELETE FROM {quoted(table)} WHERE catalog_snapshot_id=?", (identity,))
                metadata[TOMBSTONE] = now.isoformat()
                metadata["storage_retention_days"] = days
                connection.execute("UPDATE catalog_snapshots SET metrics=? WHERE id=?",
                                   (json.dumps(metadata, sort_keys=True), identity))
                connection.commit()
            result["retired"].append(identity)
        # Crash-safe: later runs also finish bodies belonging to already
        # retired snapshots. Never unlink a body referenced by a live snapshot.
        selected = result["retired"] or [""]
        pending = connection.execute(
            "SELECT r.payload_location,r.payload_hash,r.payload_size,r.catalog_snapshot_id "
            "FROM raw_snapshots r JOIN catalog_snapshots s ON s.id=r.catalog_snapshot_id "
            "WHERE json_extract(s.metrics,?) IS NOT NULL OR s.id IN ("
            + ",".join("?" for _ in selected) + ")",
            ("$." + TOMBSTONE, *selected))
        for location, digest, size, identity in pending:
            if identity in protected:
                continue
            relative = Path(location)
            if relative.is_absolute() or ".." in relative.parts or "\\" in location:
                raise ValueError("raw retention reference escaped its root")
            path = raw_root / relative
            safe_root(path.parent)
            if not path.exists():
                continue
            references = connection.execute(
                "SELECT s.id FROM raw_snapshots r JOIN catalog_snapshots s ON s.id=r.catalog_snapshot_id "
                "WHERE r.payload_location=? AND json_extract(s.metrics,?) IS NULL AND s.id NOT IN ("
                + ",".join("?" for _ in selected) + ") LIMIT 1",
                (location, "$." + TOMBSTONE, *selected)).fetchone()
            if references:
                continue
            tree, actual, _ = inventory(path)
            if actual != size or sha256(path) != digest:
                raise ValueError("retired raw body changed; no removal")
            if apply:
                if inventory(path)[0] != tree:
                    raise ValueError("retired raw body changed during maintenance")
                path.unlink()
                parent = path.parent
                while parent != raw_root:
                    try:
                        parent.rmdir()
                    except OSError:
                        break
                    parent = parent.parent
            result["raw_files_removed"] += 1
            result["reclaimable_bytes"] += actual
        result["reusable_database_bytes"] = (
            connection.execute("PRAGMA freelist_count").fetchone()[0]
            * connection.execute("PRAGMA page_size").fetchone()[0])
    return result


def compact_candidate_copy(database, raw_root, *, now):
    """Compact only a newly copied municipal candidate; its source stays intact."""
    universe = Path(os.getenv("PRICE_UNIVERSE_CACHE_ROOT", "var/price_universes"))
    return maintain(database, raw_root, universe=universe,
                    operations=universe.parent / "reports/operations",
                    now=now, apply=True)
