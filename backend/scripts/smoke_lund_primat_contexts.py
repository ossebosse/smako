"""Bounded product/price smoke for explicitly mapped Primat Lund contexts."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_root in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.services.primat_context_smoke_export import primat_context_smoke_bundle
from app.services.primat_phase_c_export import write_closed_json
from app.services.primat_store_discovery_export import primat_store_discovery_bundle
from scripts.benchmark_lund_phase_c import _BoundedPrimatProvider, _file_state

from grocery_data.app.services.provider_store_identity import (
    read_primat_store_discovery_bundle,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Two-request Primat smoke: one resolve plus one multi-context product query."
    )
    parser.add_argument(
        "--allow-bounded-primat-context-smoke",
        action="store_true",
        help="Required explicit operator opt-in; otherwise no provider is constructed.",
    )
    parser.add_argument("--city", default="Lund")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="explicit immutable SQLite database containing verified mappings",
    )
    parser.add_argument("--store-discovery", type=Path, required=True)
    parser.add_argument(
        "--context-id",
        action="append",
        required=True,
        help="Verified primat: context ID; repeat for each mapped context.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verified_context_ids(database: Path, *, city: str) -> frozenset[str]:
    """Read strong persisted mappings through immutable/query-only SQLite."""

    resolved = database.resolve(strict=True)
    connection = sqlite3.connect(
        f"file:{resolved.as_posix()}?mode=ro&immutable=1",
        uri=True,
    )
    try:
        tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        required = {
            "physical_stores",
            "provider_store_identity_mappings",
            "store_context_links",
        }
        if not required <= tables:
            raise ValueError("explicit database lacks provider mapping schema")
        rows = connection.execute(
            """
            SELECT m.provider_context_id
            FROM provider_store_identity_mappings AS m
            JOIN physical_stores AS p ON p.id = m.physical_store_id
            JOIN store_context_links AS l
              ON l.physical_store_id = m.physical_store_id
             AND l.grocery_context_id = m.provider_context_id
             AND l.source_provider = m.provider
            WHERE lower(trim(p.city)) = lower(trim(?))
              AND p.is_active = 1
              AND m.provider = 'primat'
              AND m.status = 'verified'
              AND m.is_active = 1
              AND l.is_active = 1
            ORDER BY m.provider_context_id
            """,
            (city,),
        )
        return frozenset(str(row[0]) for row in rows if row[0] is not None)
    finally:
        connection.close()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_bounded_primat_context_smoke:
        raise PermissionError("explicit bounded Primat context-smoke opt-in is required")
    if args.city.casefold().strip() != "lund":
        raise ValueError("this bounded milestone smoke is restricted to Lund")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Primat context smoke refuses to overwrite an existing file")
    baseline = read_primat_store_discovery_bundle(
        args.store_discovery,
        max_bytes=5_000_000,
    )
    requested = frozenset(str(value).strip() for value in args.context_id if str(value).strip())
    if not requested or len(requested) != len(args.context_id) or len(requested) > 100:
        raise ValueError("context smoke requires 1..100 unique non-empty context IDs")
    database = args.database.resolve(strict=True)
    database_before = _file_state(database)
    verified_contexts = _verified_context_ids(database, city=args.city)
    if requested - verified_contexts:
        raise ValueError("context smoke requires a strong persisted verified mapping")
    baseline_by_context = {row.provider_context_id: row for row in baseline.items}
    if requested - baseline_by_context.keys():
        raise ValueError("context smoke requested an ID absent from the mapping discovery")

    provider = _BoundedPrimatProvider.load(max_requests=2, context_bootstrap=False)
    try:
        resolution = await provider.resolve_store_candidates(args.postal_code)
        current = primat_store_discovery_bundle(resolution)
        current_by_context = {row.provider_context_id: row for row in current.items}
        if requested - current_by_context.keys():
            raise ValueError("mapped context disappeared from current Primat resolution")
        if any(
            baseline_by_context[context_id].identity_fingerprint
            != current_by_context[context_id].identity_fingerprint
            for context_id in requested
        ):
            raise ValueError("Primat store identity drifted since mapping discovery")
        store_ids = sorted(context_id.removeprefix("primat:") for context_id in requested)
        products = await provider.search_products("mjölk", store_ids)
        product_response = provider.last_response_metadata()
        transport = provider.transport_report
        if (
            transport.get("requests") != 2
            or transport.get("denied_requests") != 0
            or transport.get("endpoints") != {"/products": 1, "/stores/resolve": 1}
            or transport.get("statuses") != {"200": 2}
            or transport.get("max_concurrency") != 1
        ):
            raise RuntimeError("bounded Primat context-smoke transport contract failed")
        bundle = primat_context_smoke_bundle(
            resolution,
            products,
            requested_context_ids=requested,
            mapping_discovery_response_sha256=baseline.request.response_sha256,
            product_response=product_response,
        )
        written = write_closed_json(output, bundle)
    finally:
        await provider.aclose()
    if _file_state(database) != database_before:
        raise RuntimeError("Primat context smoke changed the immutable database")
    return {
        "status": "PASS",
        "database": database.name,
        "database_unchanged": True,
        "transport": transport,
        "contexts": [
            {
                "context_id": row.provider_context_id,
                "chain": row.chain.value,
                "product_rows": row.product_rows,
                "priced_product_rows": row.priced_product_rows,
                "provenance_valid": row.provenance_valid,
            }
            for row in bundle.items
        ],
        "output": {
            "file": output.name,
            "bytes": written["bytes"],
            "sha256": _sha256(output),
            "credentials_included": False,
            "headers_included": False,
            "cookies_included": False,
            "raw_response_body_included": False,
        },
    }


def _closed_stop_result(exc: Exception) -> dict[str, Any]:
    codes = {
        "PermissionError": "explicit_opt_in_missing",
        "PriceProviderAccessChallengeError": "access_challenge_stop",
        "PriceProviderAuthenticationError": "authentication_stop",
        "PriceProviderRateLimitError": "rate_limit_stop",
        "ValidationError": "closed_schema_stop",
        "FileExistsError": "output_exists_stop",
    }
    return {
        "status": "STOPPED",
        "error_code": codes.get(type(exc).__name__, "provider_schema_or_io_stop"),
        "error_type": type(exc).__name__,
        "credentials_included": False,
        "headers_included": False,
        "cookies_included": False,
        "raw_http_included": False,
    }


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - copy no provider material into output
        result = _closed_stop_result(exc)
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
