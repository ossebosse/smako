"""Fetch Axfood product-detail documents for an exact list of retailer codes.

Resumable, rate limited collection through the existing Willys/Hemköp clients,
under the existing shared operation lease. Only staging is writable. Failures
retain verified documents and their real observation time. Publishing creates
a new immutable release; it never changes runtime configuration or schedules.

    python scripts/fetch_axfood_product_details.py --chain willys \
        --codes codes.txt --catalog-proof codes-proof.json --run-id review-1 \
        --store-id 2851 --database <existing-db> --price-universe-root <existing-root>
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from collections import Counter
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from grocery_data.app.connectors.hemkop.client import HemkopClient, HemkopHttpError
from grocery_data.app.connectors.willys.client import WillysClient, WillysHttpError
from grocery_data.app.domain.enums import Chain, CoverageLevel
from grocery_data.app.domain.store import SourceStore
from grocery_data.app.services.axfood_detail_archive import (
    CODE,
    atomic_bytes,
    encoded,
    retain_response,
    selection_state,
)
from grocery_data.app.services.manual_refresh_operations import (
    RefreshRunLock,
    production_refresh_lock_path,
)


def _write(out: Path, code: str, raw) -> None:
    retain_response(out.parent, out.name, code, raw)


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chain", choices=("willys", "hemkop"), required=True)
    p.add_argument("--codes", type=Path)
    p.add_argument("--catalog-proof", type=Path)
    p.add_argument("--approved-snapshot", help="Use exact current approved DB catalogue rows as the queue")
    p.add_argument("--archive-root", type=Path, default=Path("D:/smako-data/axfood-product-details"))
    p.add_argument("--run-id", required=True)
    locks = p.add_mutually_exclusive_group(required=True)
    locks.add_argument("--database", type=Path, help="Existing data-plane DB for the shared operation lock")
    locks.add_argument("--operation-lock", type=Path, help="Exact existing local relay operation lease")
    p.add_argument("--price-universe-root", type=Path)
    p.add_argument("--limit", type=int, default=0, help="Bound this run; 0 processes the remaining exact list")
    p.add_argument("--base-release", type=Path, help="Copy a verified previous release to NEW staging")
    p.add_argument("--publish", action="store_true", help="Publish verified staging after successful collection")
    p.add_argument("--publish-only", action="store_true", help="Validate and freeze staging without network")
    p.add_argument("--store-id", required=True, help="Exact public store id recorded with each document")
    p.add_argument("--requests-per-second", type=float)
    args = p.parse_args()
    if args.approved_snapshot:
        if args.codes or args.catalog_proof or not args.database:
            p.error("--approved-snapshot requires --database and replaces --codes/--catalog-proof")
        codes = []  # Read the current catalogue under the existing data-plane lease.
    else:
        if args.codes is None or args.catalog_proof is None:
            p.error("provide --approved-snapshot or both --codes and --catalog-proof")
        codes = list(dict.fromkeys(c.strip() for c in args.codes.read_text(encoding="utf-8").splitlines() if c.strip()))
    if bad := [c for c in codes if not CODE.fullmatch(c)]:
        p.error(f"invalid product codes: {bad[:5]}")
    if not CODE.fullmatch(args.run_id) or args.limit < 0:
        p.error("invalid run ID or limit")
    cap = 1.0 if args.chain == "willys" else 0.1
    rate = cap if args.requests_per_second is None else args.requests_per_second
    if not math.isfinite(rate) or not 0 < rate <= cap:
        p.error(f"rate must be positive and at most {cap}/s")
    root = args.archive_root.resolve()
    staging = root / "staging" / args.run_id
    if not staging.resolve().is_relative_to(root / "staging"):
        p.error("staging leaves archive root")
    # Existing kernel lease, shared with refresh/backup/activation. A second
    # archive lease prevents two data planes from writing this staging root.
    if args.database is not None and args.price_universe_root is None:
        p.error("--database requires --price-universe-root")
    operation_lock = (args.operation_lock if args.operation_lock is not None
                      else production_refresh_lock_path(args.database, args.price_universe_root))
    with (RefreshRunLock(operation_lock),
          RefreshRunLock(root / ".writer.lock")):
        if args.approved_snapshot:
            from grocery_data.app.services.axfood_catalogue_queue import approved_catalogue_codes
            from grocery_data.app.storage import create_database_engine, create_session_factory

            if not args.database.is_file():
                raise ValueError("Approved catalogue database does not exist")
            engine = create_database_engine("sqlite:///" + args.database.resolve().as_posix())
            try:
                with create_session_factory(engine)() as session:
                    codes, proof = approved_catalogue_codes(session, args.approved_snapshot,
                                                           chain=args.chain, store_id=args.store_id)
                args.catalog_proof = staging / f"approved-catalogue-{args.chain}.json"
                atomic_bytes(args.catalog_proof, encoded(proof))
            finally:
                engine.dispose()
        from deploy.scripts.storage_maintenance import inventory, maintain_axfood_archives

        retention = maintain_axfood_archives(root, now=datetime.now(UTC), apply=True)
        if retention["status"] == "blocked":
            raise ValueError("Archive retention budget blocked")
        if args.base_release is not None:
            import shutil

            from grocery_data.app.services.axfood_detail_archive import verify_release

            base = args.base_release.resolve()
            if base.parent != root / "releases" or staging.exists():
                p.error("base must be this archive's release and staging must be new")
            manifest = verify_release(base)
            if retention["retained_bytes"] + inventory(base)[1] > retention["max_bytes"]:
                raise ValueError("Staging copy exceeds archive budget")
            for name in manifest["files"]:
                if name.startswith(("willys/", "hemkop/")):
                    target = staging / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(base / name, target)
        result = await collect(args, codes, staging, rate)
        if result == 0 and (args.publish or args.publish_only):
            from grocery_data.app.services.axfood_detail_archive import publish_release

            print(json.dumps({"release": str(publish_release(root, args.run_id))}), flush=True)
        return result


async def collect(args, codes, staging, rate):
    import hashlib

    staging.mkdir(parents=True, exist_ok=True)
    code_bytes = ("\n".join(codes) + "\n").encode()
    proof = json.loads(args.catalog_proof.read_bytes())
    if (proof.get("schema") != "smako-axfood-code-list-v1" or proof.get("chain") != args.chain
            or proof.get("codes_sha256") != hashlib.sha256(code_bytes).hexdigest()
            or args.store_id not in proof.get("store_external_ids", []) or not proof.get("catalogs")):
        raise ValueError("Code list/store does not match reviewed catalogue proof")
    code_path = staging / f"codes-{args.chain}.txt"
    if code_path.exists() and code_path.read_bytes() != code_bytes:
        raise ValueError("Run's exact code list changed; choose a new staging run")
    atomic_bytes(code_path, code_bytes)
    proof_path = staging / f"code-source-{args.chain}.json"
    if proof_path.exists() and proof_path.read_bytes() != encoded(proof):
        raise ValueError("Run's catalogue proof changed; choose new staging")
    atomic_bytes(proof_path, encoded(proof))
    if args.publish_only:
        return 0
    states = {code: selection_state(staging, args.chain, code) for code in codes}
    if any(state == "access_stopped" for state in states.values()):
        print(json.dumps({"stopped": "prior_access_stop_requires_review"}), flush=True)
        return 2
    todo = [c for c in codes if states[c] not in {
        "verified", "permanent_missing", "permanent_error", "waiting_after_error", "revoked", "invalid_identity", "unsafe_path"}]
    if args.limit:
        todo = todo[:args.limit]
    out = staging / args.chain
    chain = Chain(args.chain)
    store = SourceStore(chain=chain, external_id=args.store_id, name=f"{chain.value} {args.store_id}",
                        coverage=CoverageLevel.FULL_ONLINE_CATALOG, raw_reference="product-detail-fetch")
    if chain is Chain.WILLYS:
        client, stop = WillysClient(requests_per_second=rate), WillysHttpError
    else:
        client = HemkopClient(requests_per_second=rate, allowed_store_ids=[args.store_id])
        stop = HemkopHttpError
    print(json.dumps({"chain": chain.value, "codes": len(codes), "todo": len(todo),
                      "requests_per_second": client.requests_per_second,
                      "selection": dict(Counter(states.values())),
                      "codes_sha256": hashlib.sha256(code_bytes).hexdigest()}), flush=True)
    done = missing = 0
    from deploy.scripts.storage_maintenance import inventory, setting

    occupied = inventory(args.archive_root)[1]
    disk_budget = setting("AXFOOD_ARCHIVE_MAX_BYTES", 32 * 1024**3, 1, 1024**4)
    try:
        for code in todo:
            # Reserve a full bounded response plus metadata before networking.
            # The archive writer lease excludes concurrent writes/retention.
            if occupied + 4 * 1024 * 1024 + 65536 > disk_budget:
                raise ValueError("Archive byte budget exhausted")
            previous_bytes = sum(path.stat().st_size for path in out.glob(f"{code}.*") if path.is_file())
            try:
                raw = await client.fetch_product_detail(store, code)
            except stop as exc:
                raw = exc.raw
                retry_after = getattr(exc, "retry_after_raw", None)
                try:
                    retry_after = float(retry_after)
                except (TypeError, ValueError):
                    try:
                        retry_after = (parsedate_to_datetime(retry_after) - datetime.now(UTC)).total_seconds()
                    except (TypeError, ValueError):
                        retry_after = None
                if raw.kind in {"access_challenge", "rate_limit"} and raw.http_status == 200:
                    # Sanitized challenge bodies are not product documents.
                    atomic_bytes(out / f"{code}.attempt.json", encoded({"code": code, "chain": chain.value,
                        "http_status": 200, "access_stopped": True}))
                else:
                    retain_response(staging, chain.value, code, raw, retry_after=retry_after)
                if raw.http_status in (404, 410):
                    missing += 1
                    occupied += sum(path.stat().st_size for path in out.glob(f"{code}.*") if path.is_file()) - previous_bytes
                    continue
                print(json.dumps({"stopped": type(exc).__name__, "http_status": raw.http_status, "code": code}), flush=True)
                return 2
            _write(out, code, raw)
            occupied += sum(path.stat().st_size for path in out.glob(f"{code}.*") if path.is_file()) - previous_bytes
            done += 1
            if done % 25 == 0:
                print(json.dumps({"fetched": done, "missing": missing, "left": len(todo) - done - missing}), flush=True)
    finally:
        await client.aclose()
    print(json.dumps({"finished": True, "fetched": done, "missing": missing}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
