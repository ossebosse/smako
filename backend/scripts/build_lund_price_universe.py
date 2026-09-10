"""Build one closed Lund PriceUniverse artifact from promoted local snapshots.

This is refresh/admin work.  The SQLite database and optional licensed-provider
cache are opened read-only, all socket access is denied during the build, and
the destination is written atomically only after the complete prepared
universe validates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
for import_root in (PROJECT_ROOT, BACKEND_DIR):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a zero-network prepared Lund PriceUniverse artifact."
    )
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--external-cache", type=Path)
    parser.add_argument("--own-only", action="store_true")
    parser.add_argument("--city", default="Lund")
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--max-price-age-hours", type=float, default=48.0)
    parser.add_argument("--output", type=Path, required=True)
    return parser


async def _build(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    from app.services.production_price_universe_build import build_city_price_universe

    postal_code = "".join(character for character in args.postal_code if character.isdigit())
    if len(postal_code) != 5:
        raise ValueError("postal-code must contain five digits")
    if args.max_price_age_hours <= 0:
        raise ValueError("max-price-age-hours must be positive")
    if args.own_only and args.external_cache is not None:
        raise ValueError("--own-only cannot be combined with --external-cache")
    if not args.own_only and args.external_cache is None:
        raise ValueError("federated build requires --external-cache")
    if args.output.exists():
        raise FileExistsError("output already exists")
    result = await build_city_price_universe(
        database=args.database,
        city=args.city,
        postal_code=postal_code,
        external_cache=None if args.own_only else args.external_cache,
        output=args.output,
        max_price_age_hours=args.max_price_age_hours,
    )
    return result, 0 if result.get("status") == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)
    try:
        result, exit_code = asyncio.run(_build(args))
    except Exception as exc:  # noqa: BLE001 - never copy paths/payloads/secrets
        result = {
            "build": "lund_price_universe",
            "status": "FAIL",
            "error_type": type(exc).__name__,
        }
        exit_code = 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
