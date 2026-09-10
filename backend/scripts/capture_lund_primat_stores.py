"""Capture one replayable Primat Lund store list behind a one-request fence."""

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

from app.services.primat_phase_c_export import write_closed_json
from app.services.primat_store_discovery_export import (
    primat_store_discovery_bundle,
    store_discovery_output_summary,
)
from scripts.benchmark_lund_phase_c import _BoundedPrimatProvider, _file_state


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="One-request, sanitized Primat store discovery for Lund."
    )
    parser.add_argument(
        "--allow-bounded-primat-store-discovery",
        action="store_true",
        help="Required explicit operator opt-in; otherwise no provider is constructed.",
    )
    parser.add_argument("--city", default="Lund")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument(
        "--database",
        type=Path,
        help="optional explicit immutable SQLite registry; no default database is opened",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "raw_snapshots/primat/store-discovery-lund.json",
    )
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    if not args.allow_bounded_primat_store_discovery:
        raise PermissionError("explicit bounded Primat store-discovery opt-in is required")
    if args.city.casefold().strip() != "lund":
        raise ValueError("this bounded milestone capture is restricted to Lund")
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Primat store discovery refuses to overwrite an existing file")
    database = (
        args.database.resolve(strict=True)
        if getattr(args, "database", None) is not None
        else None
    )
    database_before = _file_state(database) if database is not None else None
    provider = _BoundedPrimatProvider.load(max_requests=1, context_bootstrap=True)
    try:
        resolution = await provider.resolve_store_candidates(args.postal_code)
        transport = provider.transport_report
        if (
            transport.get("requests") != 1
            or transport.get("denied_requests") != 0
            or transport.get("endpoints") != {"/stores/resolve": 1}
            or transport.get("statuses") != {"200": 1}
            or transport.get("max_concurrency") != 1
        ):
            raise RuntimeError("bounded Primat store transport contract failed")
        bundle = primat_store_discovery_bundle(resolution)
        if bundle.city.casefold().strip() != "lund":
            raise ValueError("Primat response locality does not prove Lund scope")
        written = write_closed_json(output, bundle)
    finally:
        await provider.aclose()
    if database is not None and _file_state(database) != database_before:
        raise RuntimeError("Primat store discovery changed the immutable database")
    return {
        "status": "PASS",
        "database": database.name if database is not None else None,
        "database_unchanged": database is None or _file_state(database) == database_before,
        "transport": transport,
        "discovery": store_discovery_output_summary(bundle),
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
