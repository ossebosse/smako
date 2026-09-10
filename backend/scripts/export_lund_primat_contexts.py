"""Bootstrap exact Lund Primat context evidence with one bounded resolve.

The transport implementation is shared with ``benchmark_lund_phase_c``. In
bootstrap mode it permits only one GET to ``/stores/resolve`` and disables all
product, catalog, and offer methods. No live call occurs without the explicit
operator flag.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_root in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from app.services.primat_phase_c_export import (
    BoundedPrimatPhaseCExporter,
    PrimatPhaseCExportError,
    PrimatPhaseCInvariant,
    load_active_physical_stores,
    write_closed_json,
)
from scripts.benchmark_lund_phase_c import (
    _BoundedPrimatProvider,
    _file_state,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-request, credential-free Primat context bootstrap for Lund."
    )
    parser.add_argument(
        "--allow-bounded-primat-context-bootstrap",
        action="store_true",
        help="Required explicit operator opt-in; otherwise no provider is constructed.",
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=PROJECT_ROOT / ".lund_phase_c_20260823.sqlite",
    )
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_bounded_primat_context_bootstrap:
        raise PrimatPhaseCExportError(
            "explicit --allow-bounded-primat-context-bootstrap is required",
            invariant=PrimatPhaseCInvariant.EXPLICIT_OPT_IN_MISSING,
        )
    database = args.database.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("context bootstrap refuses to overwrite an existing file")
    before = _file_state(database)
    physical_stores = load_active_physical_stores(database)
    provider = _BoundedPrimatProvider.load(
        max_requests=1,
        context_bootstrap=True,
    )
    try:
        exporter = BoundedPrimatPhaseCExporter(
            provider,
            physical_stores,
            postal_code=args.postal_code,
        )
        contexts = await exporter.resolve_once()
        transport = provider.transport_report
        expected_endpoint = "/stores/resolve"
        if (
            transport.get("requests") != 1
            or transport.get("denied_requests") != 0
            or transport.get("endpoints") != {expected_endpoint: 1}
            or any(status in {"401", "403", "429"} for status in (transport.get("statuses") or {}))
        ):
            raise PrimatPhaseCExportError(
                "bounded context transport contract failed",
                invariant=PrimatPhaseCInvariant.TRANSPORT_CONTRACT_INVALID,
            )
        bundle = exporter.context_bundle()
    finally:
        await provider.aclose()
    after = _file_state(database)
    if before != after:
        raise PrimatPhaseCExportError(
            "context bootstrap changed the immutable database",
            invariant=PrimatPhaseCInvariant.IMMUTABLE_DATABASE_CHANGED,
        )
    written = write_closed_json(output, bundle)
    return {
        "status": "PASS",
        "database_unchanged": True,
        "transport": transport,
        "contexts": [
            {
                "chain": row.export.chain.value,
                "context_id": row.export.context_id,
                "physical_store_id": row.physical_store.id,
                "identity_basis": row.identity.basis.value,
                "coverage": row.export.coverage.value,
            }
            for row in contexts
        ],
        "output": {
            "file": output.name,
            "bytes": written["bytes"],
            "sha256": _sha256(output),
            "credentials_included": written["credentials_included"],
            "headers_included": written["headers_included"],
            "cookies_included": written["cookies_included"],
            "raw_responses_included": written["raw_responses_included"],
        },
    }


def _closed_stop_result(exc: Exception) -> dict[str, Any]:
    """Return only allowlisted failure facts; never copy exception text."""

    error_type = type(exc).__name__
    codes = {
        "PriceProviderAccessChallengeError": "access_challenge_stop",
        "PriceProviderAuthenticationError": "authentication_stop",
        "PriceProviderRateLimitError": "rate_limit_stop",
        "ValidationError": "closed_schema_stop",
        "FileExistsError": "output_exists_stop",
    }
    result: dict[str, Any] = {
        "status": "STOPPED",
        "error_code": codes.get(error_type, "provider_or_io_stop"),
        "error_type": error_type,
        "credentials_included": False,
        "raw_http_included": False,
    }
    if isinstance(exc, PrimatPhaseCExportError):
        result["error_code"] = exc.safe_error_code
        result["contract_invariant"] = exc.invariant.value
        if exc.chain is not None:
            result["chain"] = exc.chain.value
    return result


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 - never copy provider material into output
        result = _closed_stop_result(exc)
        exit_code = 1
    else:
        exit_code = 0
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
