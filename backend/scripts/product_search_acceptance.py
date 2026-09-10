"""Frozen artifact acceptance; blocks outbound sockets during load and retrieval."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from unittest.mock import patch

from app.services.price_universe_runtime import PreparedPriceUniverseManager
from app.services.product_search import ProductSearchRequest
from fastapi.encoders import jsonable_encoder


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    now = datetime.now(tz=UTC)
    evidence = {"at": now.isoformat(), "socket_calls": 0, "queries": {}}
    with patch("socket.socket.connect", side_effect=AssertionError("provider/network call")):
        start = perf_counter()
        prepared = PreparedPriceUniverseManager().load_file_and_activate(args.artifact)
        index = prepared.product_search_index
        evidence.update(
            load_seconds=perf_counter() - start,
            products=len(index.groups),
            rows=index.row_count,
            universe=prepared.universe.universe_id,
        )
        for query in ("kaffe", "mjölk", "kycklingfilé", "toalettpapper", "Bregott"):
            request = ProductSearchRequest(query=query)
            start = perf_counter()
            result = index.search(request, now=now)
            cold_ms = (perf_counter() - start) * 1000
            times = []
            for _ in range(20):
                start = perf_counter()
                assert index.search(request, now=now) == result
                times.append((perf_counter() - start) * 1000)
            evidence["queries"][query] = {
                "cold_ms": cold_ms,
                "warm_max_ms": max(times),
                "response": result,
            }
        # Actual artifact offers only; do not fabricate an acceptance example.
        campaigns, multiple = [], []
        for query in ("kaffe", "mjölk", "Bregott"):
            for view, dest in (("campaigns", campaigns), ("multiple", multiple)):
                found = index.search(ProductSearchRequest(query=query, view=view), now=now)
                dest.extend(found["results"][:2])
        evidence["campaign_examples"] = campaigns
        evidence["multiple_examples"] = multiple
        candidate = next((r for r in multiple if r["gtin"]), None)
        if candidate:
            evidence["gtin"] = index.search(ProductSearchRequest(query=candidate["gtin"]), now=now)
    args.output.write_text(
        json.dumps(jsonable_encoder(evidence), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "products": evidence["products"],
                "rows": evidence["rows"],
                "load_seconds": evidence["load_seconds"],
                "queries": {
                    q: {
                        "cold_ms": v["cold_ms"],
                        "warm_max_ms": v["warm_max_ms"],
                        "total": v["response"]["total"],
                        "top": [
                            (r["name"], r["best_price"], r["prices"][0]["unit_price"])
                            for r in v["response"]["results"][:3]
                        ],
                    }
                    for q, v in evidence["queries"].items()
                },
                "campaigns": len(campaigns),
                "multiple": len(multiple),
            },
            ensure_ascii=True,
        )
    )


if __name__ == "__main__":
    main()
