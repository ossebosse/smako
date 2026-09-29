"""Opt-in browser shadow collection; independent evidence, no promotion."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import platform
from pathlib import Path

from grocery_data.app.connectors.ica.unattended_search import IcaUnattendedSearchTransport
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--price-universe-root", type=Path, required=True)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--max-scrolls", type=int, default=250)
    parser.add_argument("--browser-channel", choices=["chromium"])
    parser.add_argument("--access-diagnostics", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("evidence output already exists; choose a new run path")
    queries = args.query or ["mjölk"]
    lock = production_refresh_lock_path(args.database, args.price_universe_root)
    with RefreshRunLock(lock):
        result = asyncio.run(IcaUnattendedSearchTransport(
            max_scrolls=args.max_scrolls, browser_channel=args.browser_channel,
            access_diagnostics=args.access_diagnostics).collect(queries))
        result["environment"] = {
            "uid": os.getuid() if hasattr(os, "getuid") else None,
            "gid": os.getgid() if hasattr(os, "getgid") else None,
            "python": platform.python_version(), "shared_operation_lock": True,
            "browser": "unmodified Playwright Chromium headless, anonymous context",
        }
        module = Path(__file__).parents[1] / "app/connectors/ica/unattended_search.py"
        result["transport_sha256"] = hashlib.sha256(module.read_bytes()).hexdigest()
        diagnostic_module = module.with_name("access_diagnostics.py")
        result["diagnostics_sha256"] = hashlib.sha256(diagnostic_module.read_bytes()).hexdigest()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation also refuses a competing writer; no active files
        # are resolved or mutated by this diagnostic collector.
        with args.output.open("x", encoding="utf8") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
    print(json.dumps({key: result[key] for key in (
        "status", "blocker", "runtime_seconds", "candidate_validated", "promoted")},
        ensure_ascii=True))
    return 0 if result["candidate_validated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
