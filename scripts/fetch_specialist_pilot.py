"""Collect only reviewed pilot pages through the shared lock and raw store.

This local research command never promotes a snapshot, changes active source
selection or writes prices. Each new attempt has its own immutable directory.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grocery_data.app.connectors.specialist_pilot import PILOT_PAGES, SpecialistPilotClient
from grocery_data.app.domain.raw import RawBatch
from grocery_data.app.services.axfood_detail_archive import atomic_bytes
from grocery_data.app.services.manual_refresh_operations import RefreshRunLock
from grocery_data.app.services.raw_storage import FilesystemRawSnapshotStore


async def collect(root: Path, *, opt_in: bool) -> bool:
    store = FilesystemRawSnapshotStore(root / "raw")
    attempt = root / "attempts" / uuid4().hex
    attempt.mkdir(parents=True)
    records = []
    for chain, pages in PILOT_PAGES.items():
        client = SpecialistPilotClient(chain, operator_opt_in=opt_in)
        snapshot_id = uuid4().hex
        for page in pages:
            try:
                document = await client.fetch(page)
            except (httpx.HTTPError, OSError, ValueError) as exc:
                # Exceptions can contain URLs or transport/session details.
                records.append({"chain": chain.value, "page": page, "error_type": type(exc).__name__})
                atomic_bytes(attempt / "records.json", json.dumps(records, ensure_ascii=False, indent=2).encode())
                print(json.dumps({"chain": chain.value, "page": page, "error_type": type(exc).__name__}), flush=True)
                break
            saved = store.save_batch(RawBatch(chain=chain, documents=(document,)), snapshot_id=snapshot_id)[0]
            records.append({"chain": chain.value, "page": page, "record": saved.model_dump(mode="json")})
            atomic_bytes(attempt / "records.json", json.dumps(records, ensure_ascii=False, indent=2).encode())
            print(json.dumps({"chain": chain.value, "page": page, "status": document.http_status,
                              "kind": document.kind, "source_sha256": saved.payload_hash}), flush=True)
            if client.stopped:
                break
    complete = len(records) == sum(len(pages) for pages in PILOT_PAGES.values()) and all(
        "record" in item and 200 <= item["record"]["http_status"] < 300
        and item["record"]["kind"] == "public_page" for item in records)
    atomic_bytes(attempt / "summary.json", json.dumps({
        "complete": complete, "records": len(records), "price_activation": False,
        "qualification": "research_only_pending_exact_product_and_delivery_contract_review",
    }, indent=2).encode())
    print(json.dumps({"attempt": str(attempt), "records": len(records),
                      "complete": complete, "price_activation": False}), flush=True)
    return complete


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--operation-lock", required=True, type=Path)
    parser.add_argument("--operator-opt-in", action="store_true")
    args = parser.parse_args()
    if not args.operator_opt_in:
        parser.error("The local source pilot requires explicit operator opt-in")
    with RefreshRunLock(args.operation_lock):
        complete = asyncio.run(collect(args.output, opt_in=True))
    return 0 if complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
