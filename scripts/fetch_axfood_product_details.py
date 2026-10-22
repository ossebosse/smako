"""Fetch Axfood product-detail documents for an exact list of retailer codes.

Read-only, resumable and rate limited through the existing Willys/Hemköp
clients. Each code is written once as ``<code>.json`` (the raw body) plus
``<code>.meta.json`` (URL, time, status, payload hash). No cookies, headers or
session values are stored. A rate-limit or access-challenge response stops the
run; rerunning continues with the codes that are still missing.

    python scripts/fetch_axfood_product_details.py --chain willys \
        --codes codes.txt --output .local/axfood-details/willys --store-id 2851
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from grocery_data.app.connectors.hemkop.client import HemkopClient, HemkopHttpError
from grocery_data.app.connectors.willys.client import WillysClient, WillysHttpError
from grocery_data.app.domain.enums import Chain, CoverageLevel
from grocery_data.app.domain.store import SourceStore

_CODE = re.compile(r"^[0-9A-Za-z_-]{1,40}$")


def _write(out: Path, code: str, raw) -> None:
    meta = {"code": code, "chain": raw.chain.value, "url": raw.url, "query": raw.query,
            "fetched_at": raw.fetched_at.isoformat(), "http_status": raw.http_status,
            "content_type": raw.content_type, "payload_sha256": raw.payload_hash,
            "connector_version": raw.connector_version, "store_external_id": raw.store_external_id}
    if raw.http_status == 200:
        (out / f"{code}.json").write_bytes(raw.payload)
    (out / f"{code}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


async def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--chain", choices=("willys", "hemkop"), required=True)
    p.add_argument("--codes", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--store-id", required=True, help="Exact public store id recorded with each document")
    p.add_argument("--requests-per-second", type=float)
    args = p.parse_args()
    codes = list(dict.fromkeys(c.strip() for c in args.codes.read_text(encoding="utf-8").splitlines() if c.strip()))
    if bad := [c for c in codes if not _CODE.fullmatch(c)]:
        p.error(f"invalid product codes: {bad[:5]}")
    args.output.mkdir(parents=True, exist_ok=True)
    todo = [c for c in codes if not (args.output / f"{c}.meta.json").exists()]
    chain = Chain(args.chain)
    store = SourceStore(chain=chain, external_id=args.store_id, name=f"{chain.value} {args.store_id}",
                        coverage=CoverageLevel.FULL_ONLINE_CATALOG, raw_reference="product-detail-fetch")
    if chain is Chain.WILLYS:
        client, stop = WillysClient(requests_per_second=args.requests_per_second), WillysHttpError
    else:
        client = HemkopClient(requests_per_second=args.requests_per_second, allowed_store_ids=[args.store_id])
        stop = HemkopHttpError
    print(json.dumps({"chain": chain.value, "codes": len(codes), "todo": len(todo),
                      "requests_per_second": client.requests_per_second}), flush=True)
    done = missing = 0
    try:
        for code in todo:
            try:
                raw = await client.fetch_product_detail(store, code)
            except stop as exc:
                if exc.raw.http_status in (404, 410):
                    _write(args.output, code, exc.raw)
                    missing += 1
                    continue
                print(json.dumps({"stopped": str(exc), "http_status": exc.raw.http_status, "code": code}), flush=True)
                return 2
            _write(args.output, code, raw)
            done += 1
            if done % 100 == 0:
                print(json.dumps({"fetched": done, "missing": missing, "left": len(todo) - done - missing}), flush=True)
    finally:
        await client.aclose()
    print(json.dumps({"finished": True, "fetched": done, "missing": missing}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
