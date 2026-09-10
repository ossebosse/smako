"""Collect a credential-free Lund Primat cache without running optimizers."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_root in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.services.primat_frozen_cache_collect import (
    build_frozen_external_cache,
    canonical_ingredient_query_surface,
    load_eligible_primat_contexts,
    revalidate_primat_contexts,
)
from app.services.primat_phase_c_export import write_closed_json
from scripts.benchmark_lund_phase_c import _BoundedPrimatProvider

from grocery_data.app.domain import Chain


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Bounded 48-ingredient Primat collector; never runs a meal or basket optimizer."
        )
    )
    parser.add_argument(
        "--allow-bounded-primat-frozen-cache-collection",
        action="store_true",
        help="required explicit operator opt-in before provider construction",
    )
    parser.add_argument("--city", default="Lund")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument(
        "--database",
        type=Path,
        required=True,
        help="explicit immutable SQLite database; no default database is used",
    )
    parser.add_argument(
        "--context-id",
        action="append",
        required=True,
        help="expected eligible primat: ICA context; repeat exactly twice",
    )
    parser.add_argument("--max-age-hours", type=float, default=48.0)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_state(path: Path) -> dict[str, Any]:
    resolved = path.resolve(strict=True)
    stat = resolved.stat()
    sidecars: dict[str, dict[str, Any]] = {}
    for suffix in ("-journal", "-shm", "-wal"):
        sidecar = resolved.with_name(resolved.name + suffix)
        sidecars[suffix] = (
            {
                "exists": True,
                "bytes": sidecar.stat().st_size,
                "sha256": _sha256(sidecar),
            }
            if sidecar.exists()
            else {"exists": False, "bytes": 0, "sha256": None}
        )
    return {
        "file": resolved.name,
        "bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "sha256": _sha256(resolved),
        "sidecars": sidecars,
    }


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_bounded_primat_frozen_cache_collection:
        raise PermissionError("explicit bounded frozen-cache opt-in is required")
    if args.city.casefold().strip() != "lund":
        raise ValueError("this bounded collector is restricted to Lund")
    postal_code = "".join(character for character in args.postal_code if character.isdigit())
    if len(postal_code) != 5:
        raise ValueError("postal_code must contain exactly five digits")
    output = args.output.resolve()
    temporary = output.with_name(output.name + ".tmp")
    if output.exists() or temporary.exists():
        raise FileExistsError("frozen-cache collector refuses to overwrite output")
    requested = frozenset(str(value).strip() for value in args.context_id)
    if (
        len(args.context_id) != 2
        or len(requested) != 2
        or any(not value.startswith("primat:ica:") for value in requested)
    ):
        raise ValueError("collector requires exactly two unique Primat ICA context IDs")

    database = args.database.resolve(strict=True)
    database_before = _file_state(database)
    evaluated_at = datetime.now(tz=UTC)
    eligible = load_eligible_primat_contexts(
        database,
        city=args.city,
        max_age_hours=args.max_age_hours,
        now=evaluated_at,
        chains=frozenset({Chain.ICA}),
    )
    eligible_ids = frozenset(row.provider_context_id for row in eligible)
    if eligible_ids != requested or len(eligible) != 2:
        raise ValueError("explicit contexts do not equal the complete eligible ICA scope")
    surface = canonical_ingredient_query_surface()

    provider = _BoundedPrimatProvider.load(max_requests=49, context_bootstrap=False)
    try:
        resolution = await provider.resolve_store_candidates(postal_code)
        contexts = revalidate_primat_contexts(
            resolution,
            eligible,
            city=args.city,
        )
        native_store_ids = sorted(row.store.store_id for row in contexts)
        if len(native_store_ids) != 2:
            raise ValueError("current Primat resolution lacks the exact two-context scope")

        collected = []
        query_counts: list[dict[str, Any]] = []
        for item in surface.items:
            requests_before = int(provider.transport_report.get("requests", 0))
            rows = await provider.search_products(item.query, native_store_ids)
            requests_after = int(provider.transport_report.get("requests", 0))
            if requests_after != requests_before + 1:
                raise RuntimeError("canonical ingredient did not spend exactly one request")
            collected.extend(rows)
            by_store = Counter(row.store_id for row in rows)
            query_counts.append(
                {
                    "canonical": item.canonical,
                    "product_rows": len(rows),
                    "contexts_with_rows": sum(
                        native_store_id in by_store for native_store_id in native_store_ids
                    ),
                }
            )

        transport = provider.transport_report
        if (
            transport.get("requests") != 49
            or transport.get("denied_requests") != 0
            or transport.get("endpoints")
            != {"/products": 48, "/stores/resolve": 1}
            or transport.get("statuses") != {"200": 49}
            or transport.get("max_concurrency") != 1
        ):
            raise RuntimeError("bounded 49-request Primat transport contract failed")
        bundle = build_frozen_external_cache(resolution, contexts, collected)
    finally:
        await provider.aclose()

    if _file_state(database) != database_before:
        raise RuntimeError("bounded frozen-cache collector changed the immutable database")
    written = write_closed_json(output, bundle)
    if _file_state(database) != database_before:
        raise RuntimeError("frozen-cache export changed the immutable database")
    products_by_context = Counter(product.store_id for product in bundle.products)
    return {
        "status": "PASS",
        "database": database.name,
        "database_unchanged": True,
        "optimizer_runs": 0,
        "transport": transport,
        "surface": {
            "schema_version": surface.schema_version,
            "sha256": surface.sha256,
            "canonical_ingredients": len(surface.items),
            "queries": len(query_counts),
            "representative_basket_ingredients": len(surface.representative_basket),
            "zero_result_queries": sum(row["product_rows"] == 0 for row in query_counts),
            "queries_with_both_contexts": sum(
                row["contexts_with_rows"] == 2 for row in query_counts
            ),
        },
        "contexts": [
            {
                "context_id": row.eligible.provider_context_id,
                "chain": row.eligible.chain.value,
                "coverage": row.eligible.coverage.value,
                "mapping_confidence": row.eligible.confidence.value,
                "data_age_hours_at_start": float(row.eligible.data_age_hours),
                "products": products_by_context[row.store.store_id],
            }
            for row in contexts
        ],
        "output": {
            "file": output.name,
            "bytes": written["bytes"],
            "sha256": _sha256(output),
            "schema_version": bundle.schema_version,
            "stores": len(bundle.stores),
            "products": len(bundle.products),
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
        "error_code": codes.get(type(exc).__name__, "eligibility_transport_or_schema_stop"),
        "error_type": type(exc).__name__,
        "optimizer_runs": 0,
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
    except Exception as exc:  # noqa: BLE001 - never expose provider material
        result = _closed_stop_result(exc)
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
