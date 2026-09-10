"""Offline acceptance against an explicit, frozen beta PriceUniverse artifact."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import asdict, replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT)]
parser = argparse.ArgumentParser()
parser.add_argument("--artifact", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--original-backend", type=Path)
parser.add_argument("--matrix", action="store_true")
args = parser.parse_args()
if args.original_backend:
    sys.path.insert(0, str(args.original_backend))

from app.config import Settings
from app.models import PlanRequest
from app.services import meal_plan_optimizer as module
from app.services import price_universe_runtime as runtime
from app.services.diet_policy import recipe_respects_diet
from app.services.recipe_profile import RecipeProfileBuilder

from backend.scripts.benchmark_planner_golden import OfflineSentinelProvider, _request
from grocery_data.app.domain.promotion_pricing import MembershipProgram


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 9, 10, 0, tzinfo=UTC).astimezone(tz)


async def main():
    module.datetime = runtime.datetime = FrozenDatetime
    module.current_pricing_date = lambda: FrozenDatetime.now(UTC).date()
    settings = replace(Settings.from_env(), openai_api_key=None,
                       stable_candidate_search_enabled=True, price_universe_required=True,
                       allow_provider_fallback=False, allow_mock_fallback=False)
    manager = runtime.PreparedPriceUniverseManager()
    prepared = manager.load_file_and_activate(args.artifact)
    sentinel = OfflineSentinelProvider()
    module.create_price_provider = lambda *a, **k: sentinel
    service = module.MealPlanService(settings, price_universe_manager=manager)
    generated = service._generate_candidate_recipes
    captured = []

    async def capture(*a, **k):
        result = await generated(*a, **k)
        captured[:] = result[0]
        return result

    service._generate_candidate_recipes = capture
    output = {"artifact_sha256": hashlib.sha256(args.artifact.read_bytes()).hexdigest(),
              "universe": prepared.universe.universe_id,
              "evaluated_at": FrozenDatetime.now(UTC).isoformat(), "runs": {}}
    scenarios = [("standard", {}), ("warm_varied", {"diversity_mode": "varied"})]
    if args.matrix:
        scenarios += [("zero_budget", {"varied_budget_percent": 0}),
                      ("vegetarian", {"diet_preference": "vegetarian"}),
                      ("vegan", {"diet_preference": "vegan"}),
                      ("one_store", {"max_stores": 1}),
                      ("three", {"recipes": 3}), ("seven", {"recipes": 7}),
                      ("members", {"membership_programs": list(MembershipProgram)})]
    for name, changes in scenarios:
        request = _request(mode="balanced", max_stores=2).model_dump(mode="json", exclude_unset=True)
        request.update(changes, debug=True)
        request = PlanRequest.model_validate(request)
        started = perf_counter()
        plan = await service.create_plan(request)
        for option in plan.plans.values():
            assert option.optimized_basket.store_count <= request.max_stores
            assert option.quality.basket_audit.passed
            assert all(recipe_respects_diet(r, preference=request.diet_preference,
                       avoid_ingredients=request.avoid_ingredients) for r in option.recipes)
        varied = plan.plans["varied"]
        assert varied.optimized_basket.total <= varied.budget_ceiling
        output["runs"][name] = {"seconds": perf_counter() - started,
                                 "plan": plan.model_dump(mode="json"),
                                 "candidates": [{"recipe": r.model_dump(mode="json"),
                                                 "profile": asdict(RecipeProfileBuilder().build(r))}
                                                for r in captured]}
        output["provider_calls"] = sentinel.calls
        args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(name, round(perf_counter() - started, 3),
              {str(k): (v.optimized_basket.total, v.variation_target_met,
                         getattr(v, "inter_plan_distance", None)) for k, v in plan.plans.items()}, flush=True)
    assert sentinel.calls == 0


if __name__ == "__main__":
    asyncio.run(main())
