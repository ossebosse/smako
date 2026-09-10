"""Run a sanitized, repeatable benchmark through the public plan API.

Run this file from the repository root. The benchmark deliberately exercises
``POST /api/plan`` through FastAPI's TestClient so validation, configuration,
provider selection and response serialization are included in the measurement.
Only a small result summary is printed; environment variables and API keys are
never included in the output.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_VERIFICATION_RANK = {
    "VERIFIED": 0,
    "VERIFIED_WITH_ESTIMATES": 1,
    "UNVERIFIED": 2,
    "INVALID": 3,
}


def _verification_rank(value: object) -> int:
    return _VERIFICATION_RANK.get(str(value or "UNVERIFIED").strip().upper(), 2)


def _single_store_sort_key(row: dict[str, Any]) -> tuple[object, ...]:
    total = row.get("total")
    try:
        numeric_total = float(total)
    except (TypeError, ValueError):
        numeric_total = float("inf")
    return (
        _verification_rank(row.get("verification_status")),
        numeric_total,
        str(row.get("store_name") or "").casefold(),
        str(row.get("store_id") or ""),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmarka POST /api/plan och skriv ett sanerat JSON-sammandrag."
        )
    )
    parser.add_argument("--postal-code", default="22350")
    parser.add_argument("--recipes", type=int, default=5)
    parser.add_argument("--servings", type=int, default=4)
    parser.add_argument("--max-stores", type=int, default=2)
    parser.add_argument(
        "--strategy", choices=("legacy", "optimized"), default="optimized"
    )
    parser.add_argument("--candidate-count", type=int, default=80)
    parser.add_argument("--beam-width", type=int, default=30)
    parser.add_argument(
        "--diversity",
        choices=("cheapest", "balanced", "varied"),
        default="balanced",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=1,
        help="repeat the identical request in one process to measure warm-cache behavior",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="optional immutable JSON path; an existing report is never overwritten",
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "federated", "mock", "own", "primat"),
        default="auto",
        help="Prisprovider för just benchmarkprocessen (standard: auto).",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Begär intern debugstatistik; bara ett sanerat utdrag skrivs ut.",
    )
    return parser


def _redact(value: object) -> str:
    """Remove credential-looking fragments from operational error messages."""

    text = str(value)
    patterns = (
        (
            r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s,;]+",
            r"\1[REDACTED]",
        ),
        (
            r"(?i)((?:api[_-]?key|token|secret)\s*[:=]\s*)[^\s,;]+",
            r"\1[REDACTED]",
        ),
        (r"(?i)\b(?:sk|primat_live)_[A-Za-z0-9_-]+\b", "[REDACTED]"),
    )
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text)
    return text[:1000]


def _basket_summary(basket: dict[str, Any]) -> dict[str, Any]:
    stores: list[dict[str, Any]] = []
    for store in basket.get("stores", []):
        items = [
            {
                "ingredient": item.get("ingredient"),
                "product_id": item.get("product_id"),
                "product": item.get("product_name"),
                "verification_status": item.get("verification_status"),
                "canonical_food": item.get("canonical_food"),
                "food_family": item.get("food_family"),
                "product_role": item.get("product_role"),
                "product_form": item.get("product_form"),
                "semantic_confidence": item.get("semantic_confidence"),
                "semantic_evidence": item.get("semantic_evidence", []),
                "sale_model": item.get("sale_model"),
                "sale_price": item.get("sale_price"),
                "sale_unit": item.get("sale_unit"),
                "comparison_price": item.get("comparison_price"),
                "comparison_unit": item.get("comparison_unit"),
                "packages": item.get("packages_needed"),
                "package_quantity": item.get("package_quantity"),
                "package_unit": item.get("package_unit"),
                "usable_quantity": item.get("usable_quantity"),
                "usable_unit": item.get("usable_unit"),
                "unit": item.get("unit"),
                "required_quantity": item.get("required_quantity"),
                "purchased_quantity": item.get("purchased_quantity"),
                "purchased_unit": item.get("purchased_unit"),
                "purchased_usable_quantity": item.get(
                    "purchased_usable_quantity"
                ),
                "surplus_quantity": item.get("waste_quantity"),
                "quantity_confidence": item.get("quantity_confidence"),
                "variable_weight": item.get("variable_weight", False),
                "package_price": item.get("unit_price"),
                "total": item.get("total_price"),
                "purchase_warning": item.get("purchase_warning"),
                "source": item.get("source_provenance"),
            }
            for item in store.get("items", [])
        ]
        stores.append(
            {
                "store_id": store.get("store_id"),
                "store": store.get("store_name"),
                "subtotal": store.get("subtotal"),
                "products": items,
            }
        )
    return {
        "total": basket.get("total"),
        "verification_status": basket.get("verification_status"),
        "verification_warnings": basket.get("verification_warnings", []),
        "store_count": len(stores),
        "max_stores": basket.get("max_stores"),
        "savings_vs_single_store": basket.get("savings_vs_single_store"),
        "stores": stores,
    }


def _summary(data: dict[str, Any], wall_seconds: float) -> dict[str, Any]:
    optimization = data.get("optimization") or {}
    legacy = data.get("legacy_comparison")
    basket = data.get("optimized_basket") or {}
    debug_info = data.get("debug_info") or {}
    quality = data.get("quality") or {}
    basket_audit = quality.get("basket_audit") or {}
    nutrition = quality.get("nutrition") or {}
    diversity = quality.get("diversity") or {}
    surplus = data.get("surplus") or {}
    store_tradeoff = data.get("store_tradeoff") or {}

    complete_single_store = [
        row
        for row in data.get("single_store_options", [])
        if row.get("is_complete")
    ]
    cheapest_single = min(
        complete_single_store,
        key=_single_store_sort_key,
        default=None,
    )

    result: dict[str, Any] = {
        "provider": data.get("data_source"),
        "strategy": data.get("strategy"),
        "location": data.get("location"),
        "postal_code": data.get("postal_code"),
        "recipes": [
            {
                "name": recipe.get("name"),
                "servings": recipe.get("servings"),
            }
            for recipe in data.get("recipes", [])
        ],
        "basket": _basket_summary(basket),
        "portions": data.get("portions"),
        "price_per_portion": data.get("price_per_portion"),
        "cheapest_single_store": (
            {
                "store": cheapest_single.get("store_name"),
                "total": cheapest_single.get("total"),
                "verification_status": cheapest_single.get("verification_status"),
                "verification_warnings": cheapest_single.get(
                    "verification_warnings", []
                ),
            }
            if cheapest_single
            else None
        ),
        "runtime_seconds": round(wall_seconds, 4),
        "timings_seconds": optimization.get("timings_seconds", {}),
        "search": {
            "economic_ingredients": optimization.get("economic_ingredients", 0),
            "candidates_generated": optimization.get(
                "candidate_recipes_generated", 0
            ),
            "candidates_valid": optimization.get("candidate_recipes_valid", 0),
            "candidates_structurally_valid": optimization.get(
                "candidate_recipes_structurally_valid", 0
            ),
            "candidates_nutrition_rejected": optimization.get(
                "candidate_recipes_nutrition_rejected", 0
            ),
            "candidates_analyzed": optimization.get(
                "candidate_recipes_analyzed", 0
            ),
            "candidate_search_pool": optimization.get(
                "candidate_recipes_search_pool", 0
            ),
            "states_evaluated": optimization.get("states_evaluated", 0),
            "basket_calculations": optimization.get("basket_calculations", 0),
            "cache_hits": optimization.get("basket_cache_hits", 0),
            "cache_misses": optimization.get("basket_cache_misses", 0),
            "cache_hit_rate": optimization.get("basket_cache_hit_rate", 0),
        },
        "legacy": (
            {
                "total": legacy.get("total"),
                "savings": legacy.get("savings"),
            }
            if legacy
            else {
                "total": basket.get("total")
                if data.get("strategy") == "legacy"
                else None,
                "savings": 0 if data.get("strategy") == "legacy" else None,
            }
        ),
        "quality": (
            {
                "status": quality.get("status"),
                "basket_audit": {
                    "status": basket_audit.get("status"),
                    "verification_status": basket_audit.get("verification_status"),
                    "verification_warnings": basket_audit.get(
                        "verification_warnings", []
                    ),
                    "ingredients_checked": basket_audit.get(
                        "ingredients_checked", 0
                    ),
                    "deficits": len(basket_audit.get("deficits", [])),
                    "unknown_quantities": basket_audit.get(
                        "unknown_quantities", 0
                    ),
                    "totals_reconciled": basket_audit.get("totals_reconciled"),
                    "calculated_total": basket_audit.get("calculated_total"),
                    "reported_total": basket_audit.get("reported_total"),
                    "total_reconciliation_errors": basket_audit.get(
                        "total_reconciliation_errors", []
                    ),
                },
                "nutrition": {
                    "status": nutrition.get("status"),
                    "average_kcal_per_serving": nutrition.get(
                        "average_kcal_per_serving"
                    ),
                    "min_kcal_per_serving": nutrition.get(
                        "min_kcal_per_serving"
                    ),
                    "average_protein_g_per_serving": nutrition.get(
                        "average_protein_g_per_serving"
                    ),
                    "min_protein_g_per_serving": nutrition.get(
                        "min_protein_g_per_serving"
                    ),
                    "average_vegetable_g_per_serving": nutrition.get(
                        "average_vegetable_g_per_serving"
                    ),
                },
                "diversity": {
                    "status": diversity.get("status"),
                    "threshold": diversity.get("threshold"),
                    "max_pairwise_similarity": diversity.get(
                        "max_pairwise_similarity"
                    ),
                },
            }
            if quality
            else None
        ),
        "surplus": (
            {
                "estimated_surplus_value": surplus.get(
                    "estimated_surplus_value", 0
                ),
                "unit_totals": surplus.get("unit_totals", []),
                "items": [
                    {
                        "ingredient": item.get("canonical_name"),
                        "required_quantity": item.get("required_quantity"),
                        "purchased_usable_quantity": item.get(
                            "purchased_usable_quantity"
                        ),
                        "surplus_quantity": item.get("surplus_quantity"),
                        "surplus_percent": item.get("surplus_percent"),
                        "unit": item.get("unit"),
                        "estimated_surplus_value": item.get(
                            "estimated_surplus_value"
                        ),
                        "quantity_confidence": item.get("quantity_confidence"),
                        "products": [
                            product.get("product_name")
                            for product in item.get("selected_products", [])
                        ],
                    }
                    for item in surplus.get("items", [])
                ],
            }
            if surplus
            else None
        ),
        "store_tradeoff": store_tradeoff or None,
        "warnings": [_redact(row) for row in data.get("warnings", [])],
    }
    if debug_info:
        result["debug"] = {
            "search_stats": debug_info.get("search_stats", {}),
            "marginal_costs": debug_info.get("marginal_costs", []),
            "basket_verification": debug_info.get("basket_verification", {}),
        }
    return result


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = _parser().parse_args(argv)

    # Override provider before importing the app. No credential is accepted as
    # a CLI argument, preventing it from leaking into shell history or output.
    os.environ["PRICE_PROVIDER"] = args.provider

    from app.main import app
    from fastapi.testclient import TestClient

    payload = {
        "postal_code": args.postal_code,
        "recipes": args.recipes,
        "servings": args.servings,
        "max_stores": args.max_stores,
        "use_member_prices": False,
        "optimization_iterations": 0,
        "strategy": args.strategy,
        "candidate_recipe_count": args.candidate_count,
        "beam_width": args.beam_width,
        "diversity_mode": args.diversity,
        "debug": args.debug,
    }

    if args.repeats < 1:
        raise ValueError("repeats must be at least one")
    started = perf_counter()
    request_runtimes: list[float] = []
    startup_seconds = 0.0
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            startup_seconds = perf_counter() - started
            response = None
            for _ in range(args.repeats):
                request_started = perf_counter()
                response = client.post("/api/plan", json=payload)
                request_runtimes.append(perf_counter() - request_started)
                if response.status_code != 200:
                    break
            assert response is not None
    except Exception as exc:  # noqa: BLE001 - benchmark must only print safe output
        wall_seconds = perf_counter() - started
        print(
            json.dumps(
                {
                    "provider": args.provider,
                    "strategy": args.strategy,
                    "error": f"Plananropet misslyckades ({type(exc).__name__})",
                    "runtime_seconds": round(wall_seconds, 4),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1
    wall_seconds = perf_counter() - started

    if response.status_code != 200:
        try:
            body = response.json()
            detail = body.get("detail", "Plananropet misslyckades")
        except (ValueError, AttributeError):
            detail = "Plananropet returnerade ett icke-JSON-fel"
        print(
            json.dumps(
                {
                    "provider": args.provider,
                    "strategy": args.strategy,
                    "status_code": response.status_code,
                    "error": _redact(detail),
                    "runtime_seconds": round(wall_seconds, 4),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 1

    result = _summary(
        response.json(),
        startup_seconds + (request_runtimes[0] if request_runtimes else 0.0),
    )
    result["benchmark_runtime"] = {
        "startup_seconds": round(startup_seconds, 4),
        "request_seconds": [round(value, 4) for value in request_runtimes],
        "cold_end_to_end_seconds": round(
            startup_seconds + (request_runtimes[0] if request_runtimes else 0.0),
            4,
        ),
        "warm_request_seconds": (
            round(request_runtimes[-1], 4) if len(request_runtimes) > 1 else None
        ),
        "total_process_seconds": round(wall_seconds, 4),
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with args.json_output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(rendered)
            output.write("\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
