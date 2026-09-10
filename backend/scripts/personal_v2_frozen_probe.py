"""Compare same-snapshot legacy economics and exercise V2 without live I/O."""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import Settings
from app.models import PlanRequest
from app.services.meal_plan_optimizer import MealPlanService
from app.services.price_universe_runtime import (
    PreparedPriceUniverseArtifact,
    PreparedPriceUniverseManager,
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--legacy-only", action="store_true")
    args = parser.parse_args()
    prepared = PreparedPriceUniverseArtifact.model_validate_json(
        args.fixture.read_bytes()
    ).restore()
    manager = PreparedPriceUniverseManager()
    manager.activate(prepared)
    settings = Settings(
        price_provider="mock",
        price_universe_required=True,
        meal_plan_strategy="optimized",
        stable_candidate_search_enabled=True,
    )
    request = PlanRequest(
        recipes=5,
        servings=4,
        max_stores=2,
        diversity_mode="balanced",
        strategy="optimized",
        optimization_iterations=0,
    )
    evidence = {
        "fixture": prepared.universe.universe_id,
        "products": len(prepared.universe.products),
        "results": [],
    }
    service = MealPlanService(settings, price_universe_manager=manager)
    for phase in ("cold", "warm"):
        start = time.perf_counter()
        result = asyncio.run(service.create_plan(request))
        evidence["results"].append(
            {
                "kind": "legacy",
                "phase": phase,
                "seconds": round(time.perf_counter() - start, 3),
                "total": result.optimized_basket.total,
                "recipes": [r.name for r in result.recipes],
                "live_requests": result.data.live_chain_requests,
            }
        )
        print(json.dumps(evidence["results"][-1]), flush=True)
    if not args.legacy_only:
        from app.models.personal import ExtraNeed, MealSettings, PersonalPlanning
        from app.services.personal_planner import PersonalPlanner

        state = {
            "id": "synthetic",
            "revision": 0,
            "profile": None,
            "items": [],
            "events": {},
            "reservations": {},
        }
        variants = [
            ("standalone", []),
            (
                "breakfast_snack",
                [
                    MealSettings(meal_type="breakfast", count=1, servings=1),
                    MealSettings(meal_type="snack", count=1, servings=1),
                ],
            ),
            (
                "combined",
                [
                    MealSettings(meal_type="dinner", count=3, servings=4),
                    MealSettings(meal_type="breakfast", count=1, servings=1),
                    MealSettings(meal_type="snack", count=1, servings=1),
                ],
            ),
        ]
        for name, meals in variants:
            req = PlanRequest(
                recipes=0,
                diversity_mode="balanced",
                max_stores=2,
                personal=PersonalPlanning(
                    meals=meals,
                    extras=[
                        ExtraNeed(
                            query="mjölk 1,5 %",
                            quantity=1000,
                            unit="ml",
                            properties=["1,5 %"],
                            confirmed=True,
                        )
                    ],
                ),
            )
            start = time.perf_counter()
            try:
                result = PersonalPlanner(
                    req, settings, prepared, state, now=datetime(2026, 9, 10, 17, 30, tzinfo=UTC)
                ).create()
                row = {
                    "kind": name,
                    "status": "PASS",
                    "seconds": round(time.perf_counter() - start, 3),
                    "total": result.optimized_basket.total,
                    "stores": result.optimized_basket.store_count,
                    "portions": result.portions,
                }
            except Exception as exc:  # noqa: BLE001 - bounded probe records a sanitized outcome
                row = {
                    "kind": name,
                    "status": "FAIL",
                    "seconds": round(time.perf_counter() - start, 3),
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            evidence["results"].append(row)
            print(json.dumps(row), flush=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
