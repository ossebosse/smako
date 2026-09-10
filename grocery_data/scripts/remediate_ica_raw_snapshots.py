"""Selectively remove runtime/session material from verified ICA raw snapshots.

The manifest is intentionally closed: this command never discovers mutation
targets from a broad glob.  Without ``--apply`` it performs every validation
but does not modify files or databases.
"""

# ruff: noqa: ISC004 - split manifest literals keep the closed target list auditable.

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grocery_data.app.connectors.ica.models import (
    initial_data_from_html,
    sanitized_initial_data_payload,
)
from grocery_data.app.connectors.ica.parser import IcaParser
from grocery_data.app.domain import (
    Chain,
    CoverageLevel,
    GeographicArea,
    RawBatch,
    RawFetch,
    SourceStore,
)
from grocery_data.app.monitoring.schema_fingerprint import (
    SchemaFingerprint,
    fingerprint_json,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_FIXED_FETCHED_AT = datetime(2026, 8, 21, tzinfo=UTC)
_SANITIZED_CONNECTOR_VERSION = "ica-v2-remediated"
_SENSITIVE_KEY_FRAGMENTS = (
    b'"accesstoken"',
    b'"publicaccesstoken"',
    b'"sessionid"',
    b'"i3sessionid"',
    b'"map_api_key"',
    b'"storecookie"',
)


@dataclass(frozen=True)
class TargetGroup:
    raw_root: Path
    database: Path | None
    expected_database_references: int
    locations: tuple[str, ...]


_GROUPS = (
    TargetGroup(
        raw_root=_PROJECT_ROOT / ".ica_recipe_raw",
        database=_PROJECT_ROOT / ".ica_recipe_benchmark.sqlite",
        expected_database_references=3,
        locations=(
            "ica/1003452/f74203def89c42e3b02a90685e852904/"
            "20260821T194528134285Z_0000_offers_page_cd3b3099.bin",
            "ica/1088004/f74203def89c42e3b02a90685e852904/"
            "20260821T194529740532Z_0000_offers_page_a8035267.bin",
            "ica/chain/f74203def89c42e3b02a90685e852904/"
            "20260821T194525949803Z_0000_stores_page_4e21cfc4.bin",
        ),
    ),
    TargetGroup(
        raw_root=_PROJECT_ROOT / "raw_snapshots" / "cross_chain_phase2",
        database=_PROJECT_ROOT / "cross_chain_phase2.sqlite",
        expected_database_references=8,
        locations=(
            "ica/1003452/ca776b706b2747bb80381283c7393118/"
            "20260821T170413553551Z_0000_offers_page_13fb3585.bin",
            "ica/1003569/02ccf7f3bf744e1dbc1c99e000dfc70e/"
            "20260821T170436309683Z_0000_offers_page_a30bf240.bin",
            "ica/1004037/02ccf7f3bf744e1dbc1c99e000dfc70e/"
            "20260821T170427992098Z_0000_offers_page_a8b91bcf.bin",
            "ica/1004490/02ccf7f3bf744e1dbc1c99e000dfc70e/"
            "20260821T170425066499Z_0000_offers_page_ee05de7d.bin",
            "ica/1004492/02ccf7f3bf744e1dbc1c99e000dfc70e/"
            "20260821T170430764616Z_0000_offers_page_e1230073.bin",
            "ica/1088004/ca776b706b2747bb80381283c7393118/"
            "20260821T170416509966Z_0000_offers_page_7a8402b8.bin",
            "ica/chain/02ccf7f3bf744e1dbc1c99e000dfc70e/"
            "20260821T170423059009Z_0000_stores_page_a6fab409.bin",
            "ica/chain/ca776b706b2747bb80381283c7393118/"
            "20260821T170411389231Z_0000_stores_page_a384a055.bin",
        ),
    ),
    TargetGroup(
        raw_root=_PROJECT_ROOT / "raw_snapshots",
        database=None,
        expected_database_references=0,
        locations=(
            "ica/1003452/canary-bc046af2667d4cc7b6ac01755d4a2a68/"
            "20260821T164447789273Z_0000_offers_page_2c59c92a.bin",
            "ica/1003452/canary-d741541db7154f8387999a6abf9c71dd/"
            "20260821T164323583903Z_0000_offers_page_c7aa09c4.bin",
            "ica/1003793/canary-cfd36793caef4275ac1e99a47a9cb202/"
            "20260821T164329896044Z_0000_offers_page_a44702c0.bin",
            "ica/1004490/canary-d45e56380d8d4e099606f0155a02db1b/"
            "20260821T164454287442Z_0000_offers_page_78ee34e8.bin",
            "ica/chain/canary-2d6f03aafaed4ae0ab570a267ab56964/"
            "20260821T164321416949Z_0000_stores_page_b42ebd0f.bin",
            "ica/chain/canary-9743a1a50a934f5fb51af103f7d0ad62/"
            "20260821T164446447867Z_0000_stores_page_e0ad3911.bin",
            "ica/chain/canary-9a861c8eda7041ae8bb9ba34b2d02029/"
            "20260821T164327837189Z_0000_stores_page_454856d3.bin",
            "ica/chain/canary-b0b5c5db7a1e42aeadcf32062d5d42f1/"
            "20260821T164225892731Z_0000_stores_page_d3d2d112.bin",
            "ica/chain/canary-b5657435b250421ab5a9ecf79d1c135c/"
            "20260821T164452371714Z_0000_stores_page_70c45a4f.bin",
            "ica/chain/canary-da68f22eb3ef4421bf4eb991892317fa/"
            "20260821T164221176721Z_0000_stores_page_61255ddc.bin",
        ),
    ),
    TargetGroup(
        raw_root=_PROJECT_ROOT / "raw_snapshots" / "ica_phase2",
        database=_PROJECT_ROOT / "ica_phase2.sqlite",
        expected_database_references=32,
        locations=(
            "ica/1003452/12e5150736664b23a11303f6467a5428/"
            "20260821T164751949092Z_0000_offers_page_14361eec.bin",
            "ica/1003569/8a61a46c530a4e5e886c050476244eea/"
            "20260821T164815034661Z_0000_offers_page_05602f99.bin",
            "ica/1004037/8a61a46c530a4e5e886c050476244eea/"
            "20260821T164807191650Z_0000_offers_page_ee194b8f.bin",
            "ica/1004490/8a61a46c530a4e5e886c050476244eea/"
            "20260821T164801603353Z_0000_offers_page_a041c3fd.bin",
            "ica/1004492/8a61a46c530a4e5e886c050476244eea/"
            "20260821T164809616205Z_0000_offers_page_277f3f4e.bin",
            "ica/1088004/12e5150736664b23a11303f6467a5428/"
            "20260821T164754134237Z_0000_offers_page_bb22893b.bin",
            "ica/chain/12e5150736664b23a11303f6467a5428/"
            "20260821T164750061675Z_0000_stores_page_dd4a736e.bin",
            "ica/chain/8a61a46c530a4e5e886c050476244eea/"
            "20260821T164759769505Z_0000_stores_page_5258d242.bin",
        ),
    ),
)


def _kind(location: str) -> str:
    if "_stores_page_" in location:
        return "stores_page"
    if "_offers_page_" in location:
        return "offers_page"
    raise ValueError(f"unrecognized ICA remediation target kind: {location}")


def _contains_sensitive_key(payload: bytes) -> bool:
    lowered = payload.lower()
    return any(fragment in lowered for fragment in _SENSITIVE_KEY_FRAGMENTS)


def _raw_fetch(payload: bytes, *, kind: str, store_id: str | None) -> RawFetch:
    return RawFetch(
        chain=Chain.ICA,
        store_external_id=store_id,
        kind=kind,
        method="GET",
        url="https://www.ica.se/sanitized-replay",
        fetched_at=_FIXED_FETCHED_AT,
        http_status=200,
        content_type="application/json" if payload.lstrip().startswith(b"{") else "text/html",
        payload=payload,
        connector_version="ica-remediation-parity",
    )


def _parser_projection(payload: bytes, *, kind: str, location: str) -> object:
    parser = IcaParser()
    store_id = Path(location).parts[1] if kind == "offers_page" else None
    batch = RawBatch(
        chain=Chain.ICA,
        documents=(_raw_fetch(payload, kind=kind, store_id=store_id),),
    )
    if kind == "offers_page":
        store = SourceStore(
            chain=Chain.ICA,
            external_id=str(store_id),
            name="ICA remediation parity store",
            online_shopping=True,
            coverage=CoverageLevel.OFFERS_ONLY,
            raw_reference="raw:parity-store",
            source_fields={"store_id": store_id},
        )
        return parser.parse_catalog(batch, ["raw:parity"], store).model_dump(mode="json")

    data = initial_data_from_html(payload)
    result_store = data.get("resultStore")
    cards = result_store.get("storeCards", []) if isinstance(result_store, dict) else []
    areas = {
        str(address.get("municipality") or address.get("city") or "").strip()
        for card in cards
        if isinstance(card, dict)
        and isinstance((address := card.get("address")), dict)
        and (address.get("municipality") or address.get("city"))
    }
    if not areas:
        areas = {"Lund"}
    return {
        area: [
            store.model_dump(mode="json")
            for store in parser.parse_stores(
                batch,
                ["raw:parity"],
                GeographicArea(city=area),
            )
        ]
        for area in sorted(areas)
    }


def _atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f".{path.name}.ica-sanitized-{os.getpid()}.tmp")
    if temporary.exists():
        raise FileExistsError(f"refusing to reuse remediation temporary: {temporary}")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _request_fingerprint(row: sqlite3.Row, payload_hash: str) -> str:
    query = json.loads(row["query"]) if isinstance(row["query"], str) else row["query"]
    body = {
        "chain": row["chain"],
        "store_external_id": row["store_external_id"],
        "kind": row["kind"],
        "method": str(row["method"]).upper(),
        "url": row["url"],
        "query": query or {},
        "page_number": row["page_number"],
        "payload_hash": payload_hash,
    }
    return hashlib.sha256(
        json.dumps(
            body,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def _prepare_payloads() -> tuple[dict[Path, bytes], dict[Path, bytes], int]:
    originals: dict[Path, bytes] = {}
    sanitized: dict[Path, bytes] = {}
    parity = 0
    seen: set[Path] = set()
    for group in _GROUPS:
        for location in group.locations:
            path = (group.raw_root / location).resolve()
            if group.raw_root.resolve() not in path.parents:
                raise ValueError(f"ICA remediation target escapes raw root: {location}")
            if path in seen:
                raise ValueError(f"duplicate ICA remediation target: {location}")
            seen.add(path)
            original = path.read_bytes()
            kind = _kind(location)
            clean = sanitized_initial_data_payload(original, kind=kind)
            if _contains_sensitive_key(clean):
                raise ValueError(f"sanitizer retained forbidden ICA key: {location}")
            if _parser_projection(original, kind=kind, location=location) != _parser_projection(
                clean,
                kind=kind,
                location=location,
            ):
                raise ValueError(f"ICA parser parity failed: {location}")
            parity += 1
            originals[path] = original
            sanitized[path] = clean
    if len(seen) != 29 or parity != 29:
        raise ValueError("ICA remediation manifest must contain exactly 29 parity-checked files")
    return originals, sanitized, parity


def _schema_plan(
    rows: list[sqlite3.Row],
    payloads: dict[str, bytes],
) -> tuple[dict[str, SchemaFingerprint], dict[str, str]]:
    grouped: dict[tuple[str | None, str], list[tuple[str, object]]] = defaultdict(list)
    for row in rows:
        payload = json.loads(payloads[row["payload_location"]])
        grouped[(row["store_external_id"], row["kind"])].append((row["id"], payload))
    schemas: dict[str, SchemaFingerprint] = {}
    row_schemas: dict[str, str] = {}
    for (store_id, kind), values in grouped.items():
        fingerprint = fingerprint_json([payload for _, payload in values])
        schema_key = kind if store_id is None else f"{store_id}:{kind}"
        schemas[schema_key] = fingerprint
        for row_id, _ in values:
            row_schemas[row_id] = fingerprint.digest
    return schemas, row_schemas


def _remediate_database(
    group: TargetGroup,
    originals: dict[Path, bytes],
    sanitized: dict[Path, bytes],
    *,
    apply: bool,
) -> tuple[int, int]:
    if group.database is None:
        return 0, 0
    connection = sqlite3.connect(group.database)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in group.locations)
    rows = list(
        connection.execute(
            f"""
            SELECT * FROM raw_snapshots
            WHERE chain = 'ica' AND payload_location IN ({placeholders})
            ORDER BY catalog_snapshot_id, created_at, id
            """,
            group.locations,
        )
    )
    if len(rows) != group.expected_database_references:
        raise ValueError(
            f"unexpected ICA DB reference count for {group.database.name}: {len(rows)}"
        )
    observed_locations = {row["payload_location"] for row in rows}
    if observed_locations != set(group.locations):
        raise ValueError(f"ICA DB target-set mismatch for {group.database.name}")
    snapshot_ids = sorted({row["catalog_snapshot_id"] for row in rows})
    snapshot_placeholders = ",".join("?" for _ in snapshot_ids)
    all_snapshot_rows = list(
        connection.execute(
            f"""
            SELECT * FROM raw_snapshots
            WHERE catalog_snapshot_id IN ({snapshot_placeholders})
            ORDER BY catalog_snapshot_id, created_at, id
            """,
            snapshot_ids,
        )
    )
    if len(all_snapshot_rows) != len(rows) or any(
        row["chain"] != "ica" or row["payload_location"] not in observed_locations
        for row in all_snapshot_rows
    ):
        raise ValueError(
            f"affected ICA snapshots contain unmanifested raw rows: {group.database.name}"
        )

    paths = {location: (group.raw_root / location).resolve() for location in group.locations}
    payloads = {location: sanitized[path] for location, path in paths.items()}
    rows_by_snapshot: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in all_snapshot_rows:
        rows_by_snapshot[row["catalog_snapshot_id"]].append(row)

    metadata: dict[str, dict[str, object]] = {}
    snapshot_updates: dict[str, tuple[str, dict[str, Any]]] = {}
    for snapshot_id, snapshot_rows in rows_by_snapshot.items():
        schemas, row_schemas = _schema_plan(snapshot_rows, payloads)
        for row in snapshot_rows:
            clean = payloads[row["payload_location"]]
            payload_hash = hashlib.sha256(clean).hexdigest()
            metadata[row["id"]] = {
                "payload_hash": payload_hash,
                "payload_size": len(clean),
                "content_type": f"application/json; profile=sanitized-{row['kind']}",
                "request_fingerprint": _request_fingerprint(row, payload_hash),
                "schema_fingerprint": row_schemas[row["id"]],
            }
        snapshot_fingerprint = fingerprint_json(
            {key: fingerprint.digest for key, fingerprint in schemas.items()}
        ).digest
        snapshot_row = connection.execute(
            "SELECT metrics FROM catalog_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        if snapshot_row is None:
            raise ValueError(f"missing ICA catalog snapshot: {snapshot_id}")
        metrics = json.loads(snapshot_row["metrics"] or "{}")
        metrics["schemas"] = {
            key: fingerprint.model_dump(mode="json") for key, fingerprint in sorted(schemas.items())
        }
        metrics["schema_diff"] = None
        metrics["raw_security_remediation"] = {
            "profile": "ica-public-ssr-v1",
            "raw_rows": len(snapshot_rows),
        }
        snapshot_updates[snapshot_id] = (snapshot_fingerprint, metrics)

    if not apply:
        connection.close()
        return len(rows), len(snapshot_ids)

    replaced: list[Path] = []
    connection.isolation_level = None
    connection.execute("BEGIN IMMEDIATE")
    try:
        for row in all_snapshot_rows:
            values = metadata[row["id"]]
            connection.execute(
                """
                UPDATE raw_snapshots
                SET payload_hash = ?, payload_size = ?, content_type = ?,
                    request_fingerprint = ?, connector_version = ?, schema_fingerprint = ?
                WHERE id = ?
                """,
                (
                    values["payload_hash"],
                    values["payload_size"],
                    values["content_type"],
                    values["request_fingerprint"],
                    _SANITIZED_CONNECTOR_VERSION,
                    values["schema_fingerprint"],
                    row["id"],
                ),
            )
        for snapshot_id, (schema_fingerprint, metrics) in snapshot_updates.items():
            connection.execute(
                "UPDATE catalog_snapshots SET schema_fingerprint = ?, metrics = ? WHERE id = ?",
                (
                    schema_fingerprint,
                    json.dumps(metrics, ensure_ascii=False, separators=(",", ":")),
                    snapshot_id,
                ),
            )
            connection.execute(
                """
                UPDATE connector_health SET schema_fingerprint = ?
                WHERE active_snapshot_id = ?
                """,
                (schema_fingerprint, snapshot_id),
            )
        for path in paths.values():
            _atomic_write(path, sanitized[path])
            replaced.append(path)

        for row in all_snapshot_rows:
            path = paths[row["payload_location"]]
            values = metadata[row["id"]]
            if hashlib.sha256(path.read_bytes()).hexdigest() != values["payload_hash"]:
                raise ValueError(f"post-write ICA payload hash mismatch: {row['payload_location']}")
        connection.execute("COMMIT")
    except BaseException:
        connection.execute("ROLLBACK")
        for path in replaced:
            _atomic_write(path, originals[path])
        raise
    finally:
        connection.close()
    return len(rows), len(snapshot_ids)


def _verify_database(group: TargetGroup, sanitized: dict[Path, bytes]) -> None:
    if group.database is None:
        return
    connection = sqlite3.connect(f"file:{group.database.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in group.locations)
    rows = list(
        connection.execute(
            f"""
            SELECT * FROM raw_snapshots
            WHERE chain = 'ica' AND payload_location IN ({placeholders})
            """,
            group.locations,
        )
    )
    if len(rows) != group.expected_database_references:
        raise ValueError(f"post-migration ICA DB count mismatch: {group.database.name}")
    for row in rows:
        payload = (group.raw_root / row["payload_location"]).read_bytes()
        expected_hash = hashlib.sha256(payload).hexdigest()
        if (
            payload != sanitized[(group.raw_root / row["payload_location"]).resolve()]
            or row["payload_hash"] != expected_hash
            or row["payload_size"] != len(payload)
            or row["request_fingerprint"] != _request_fingerprint(row, expected_hash)
            or not str(row["content_type"]).startswith("application/json")
        ):
            raise ValueError(f"post-migration ICA DB integrity mismatch: {group.database.name}")
    connection.close()


def _raw_roots() -> tuple[Path, ...]:
    roots = {_PROJECT_ROOT / "raw_snapshots", _PROJECT_ROOT / ".ica_recipe_raw"}
    roots.update(
        path for path in _PROJECT_ROOT.iterdir() if path.is_dir() and path.name.endswith(".raw")
    )
    return tuple(sorted(roots))


def _workspace_sensitive_file_count() -> int:
    affected = 0
    for root in _raw_roots():
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in {".bin", ".json"}:
                affected += int(_contains_sensitive_key(path.read_bytes()))
    return affected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="atomically replace only the 29 manifest files and update linked metadata",
    )
    args = parser.parse_args()

    originals, sanitized, parity = _prepare_payloads()
    database_rows = 0
    snapshots = 0
    for group in _GROUPS:
        rows, group_snapshots = _remediate_database(
            group,
            originals,
            sanitized,
            apply=args.apply,
        )
        database_rows += rows
        snapshots += group_snapshots

    if args.apply:
        orphan_group = next(group for group in _GROUPS if group.database is None)
        for location in orphan_group.locations:
            path = (orphan_group.raw_root / location).resolve()
            _atomic_write(path, sanitized[path])
        for group in _GROUPS:
            _verify_database(group, sanitized)
        for path, expected in sanitized.items():
            if path.read_bytes() != expected or _contains_sensitive_key(expected):
                raise ValueError("post-migration ICA file verification failed")

    sensitive_files = _workspace_sensitive_file_count()
    if args.apply and sensitive_files:
        raise ValueError(f"raw-root sensitive-key deny scan failed for {sensitive_files} files")
    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "dry-run",
                "manifest_files": len(sanitized),
                "parser_parity": parity,
                "database_rows": database_rows,
                "catalog_snapshots": snapshots,
                "raw_files_with_forbidden_keys": sensitive_files,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
