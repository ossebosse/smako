"""Bounded facts-only details; never called by the consumer or relay."""

import argparse
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from grocery_data.app.connectors.willys.client import WillysClient


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", default="reports/private/fishfree-selection.json")
    parser.add_argument("--output", default="reports/private/fishfree-details.json")
    args = parser.parse_args()
    selected = json.loads(Path(args.selection).read_bytes())
    # Shared eight ingredients, one ordinary dry lentil and one ordinary pasta.
    if args.selection.endswith("fishfree-selection.json"):
        selected = selected[:8] + [
            r for r in selected if r["code"] in {"101289938_ST", "101548685_ST"}
        ]
    target = Path(args.output)
    assert not target.exists()
    prior = {
        r["selection"]["code"]
        for p in Path("reports/private").glob("fishfree-details*.json")
        for r in json.loads(p.read_bytes())
    }
    assert not prior & {r["code"] for r in selected}, "Do not repeat a fetched product"
    assert len(prior | {r["code"] for r in selected}) <= 30
    client = WillysClient()
    output = []
    try:
        for row in selected:
            try:
                detail = await client.fetch_product_detail(
                    SimpleNamespace(external_id=row["store"]), row["code"]
                )
                payload = detail.json_payload()
                assert isinstance(payload, dict) and payload.get("code") == row["code"]
                output.append({"selection": row, "detail": detail.model_dump(mode="json")})
                target.write_text(json.dumps(output, ensure_ascii=False), encoding="utf8")
                print(
                    json.dumps({"code": row["code"], "status": "FETCHED", "fields": list(payload)}),
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001 - stop at any detail failure; record type only
                output.append({"selection": row, "status": "STOPPED", "error": type(exc).__name__})
                target.write_text(json.dumps(output, ensure_ascii=False), encoding="utf8")
                print(
                    json.dumps(
                        {"code": row["code"], "status": "STOPPED", "error": type(exc).__name__}
                    ),
                    flush=True,
                )
                break
    finally:
        await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
