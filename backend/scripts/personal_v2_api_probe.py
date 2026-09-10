"""Read-only pricing probe; writes no saved plan or real pantry inventory."""

import argparse
import json
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="https://beta.smako.nu")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = {
        "postal_code": "22350",
        "recipes": 5,
        "servings": 4,
        "max_stores": 2,
        "diversity_mode": "balanced",
        "strategy": "optimized",
        "optimization_iterations": 0,
    }
    evidence = {"baseline": "legacy dinner request", "runs": []}
    with httpx.Client(timeout=180) as client:
        for _ in range(2):
            start = time.perf_counter()
            response = client.post(args.base + "/api/plan", json=payload)
            elapsed = time.perf_counter() - start
            data = response.json()
            evidence["runs"].append(
                {
                    "http": response.status_code,
                    "seconds": round(elapsed, 3),
                    "total": data.get("optimized_basket", {}).get("total"),
                    "version": data.get("app_version"),
                    "prices": data.get("data", {}).get("price_universe_id"),
                    "live_chain_requests": data.get("data", {}).get("live_chain_requests"),
                }
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
