"""Offline acceptance run for the consumer planner milestone.

The script loads the already activated, hash-verified PriceUniverse and replaces
the grocery provider factory with a fail-closed sentinel.  Any accidental live
source call therefore fails the run instead of being hidden in a benchmark.
OpenAI is disabled for this acceptance run so recipe generation is deterministic
and the complete execution is network-free.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.config import Settings
from app.models import PlanRequest
from app.services import meal_plan_optimizer as optimizer_module
from app.services.diet_policy import recipe_respects_diet
from app.services.meal_plan_optimizer import MealPlanService
from app.services.price_universe_runtime import (
    PreparedPriceUniverseManager,
)

from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)


class OfflineSentinelProvider:
    """Provider shape that proves prepared-universe planning never performs I/O."""

    source_name = "offline_sentinel"
    attribution_text = None
    attribution_url = None

    async def find_stores(self, _postal_code: str) -> list[Any]:
        raise AssertionError("consumer acceptance attempted a live store request")

    async def search_products(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("consumer acceptance attempted a live product request")

    async def get_store_products(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("consumer acceptance attempted a live catalog request")

    async def get_offers(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("consumer acceptance attempted a live offer request")

    async def aclose(self) -> None:
        return None


def _shopping_rows(plan: Any) -> list[dict[str, Any]]:
    return [
        {
            "store": group.store_name,
            "product": item.product_name,
            "packages": item.packages_needed,
            "line_total": item.total_price,
            "chain": item.chain,
            "grocery_context_id": item.store_id,
            "price_context_type": item.price_context_type,
            "gtin": item.gtin,
        }
        for group in plan.optimized_basket.stores
        for item in group.items
    ]


def _summary(
    plan: Any,
    *,
    seconds: float,
    label: str,
    max_stores: int,
) -> dict[str, Any]:
    if len(plan.recipes) != 5 or any(not recipe.instructions for recipe in plan.recipes):
        raise AssertionError("acceptance plan does not contain five complete recipes")
    if plan.optimized_basket.store_count > max_stores:
        raise AssertionError("acceptance plan exceeds its max-store constraint")
    if plan.data is None or plan.data.live_chain_requests != 0:
        raise AssertionError("acceptance plan is not backed by an offline PriceUniverse")
    return {
        "label": label,
        "runtime_seconds": round(seconds, 4),
        "recipes": [recipe.name for recipe in plan.recipes],
        "total": plan.optimized_basket.total,
        "price_per_portion": plan.price_per_portion,
        "stores": [group.store_name for group in plan.optimized_basket.stores],
        "store_count": plan.optimized_basket.store_count,
        "one_store_total": (
            plan.store_tradeoff.one_store_total
            if plan.store_tradeoff is not None
            else min(
                (option.total for option in plan.single_store_options if option.is_complete),
                default=None,
            )
        ),
        "savings_vs_one_store": plan.optimized_basket.savings_vs_single_store,
        "shopping_list": _shopping_rows(plan),
        "price_universe_id": plan.data.price_universe_id,
        "price_status": plan.data.status,
        "oldest_price_age_hours": plan.data.oldest_price_age_hours,
        "provider_calls": plan.data.live_chain_requests,
        "recipe_source": plan.recipe_source,
        "quality_status": plan.quality.status if plan.quality else None,
    }


async def run(city: str, output_root: Path) -> Path:
    base = Settings.from_env()
    settings = replace(
        base,
        meal_plan_strategy="optimized",
        price_universe_required=True,
        allow_provider_fallback=False,
        allow_mock_fallback=False,
        openai_api_key=None,
    )
    artifact_store = PreparedUniverseArtifactStore(settings.price_universe_cache_root)
    artifact_path = artifact_store.resolve_active_artifact(city)
    if artifact_path is None:
        raise RuntimeError(f"no active PriceUniverse for {city}")

    manager = PreparedPriceUniverseManager()
    load_started = perf_counter()
    prepared = manager.load_file_and_activate(artifact_path)
    load_seconds = perf_counter() - load_started
    service = MealPlanService(settings, price_universe_manager=manager)
    sentinel = OfflineSentinelProvider()
    original_factory = optimizer_module.create_price_provider
    optimizer_module.create_price_provider = lambda *_args, **_kwargs: sentinel

    async def execute(label: str, *, mode: str, max_stores: int, diet: str = "mixed"):
        request = PlanRequest(
            postal_code="22350",
            recipes=5,
            servings=4,
            max_stores=max_stores,
            diversity_mode=mode,
            diet_preference=diet,
            memberships={},
            use_member_prices=False,
            strategy="optimized",
            optimization_iterations=0,
            candidate_recipe_count=80,
            beam_width=30,
        )
        started = perf_counter()
        plan = await service.create_plan(request)
        elapsed = perf_counter() - started
        if diet == "vegetarian" and not all(
            recipe_respects_diet(recipe, preference="vegetarian")
            for recipe in plan.recipes
        ):
            raise AssertionError("vegetarian acceptance plan contains animal flesh")
        return _summary(
            plan,
            seconds=elapsed,
            label=label,
            max_stores=max_stores,
        )

    try:
        cold = await execute("BALANCED max2 cold", mode="balanced", max_stores=2)
        warm = await execute("BALANCED max2 warm", mode="balanced", max_stores=2)
        cheapest_1 = await execute("CHEAPEST max1", mode="cheapest", max_stores=1)
        cheapest_2 = await execute("CHEAPEST max2", mode="cheapest", max_stores=2)
        cheapest_3 = await execute("CHEAPEST max3", mode="cheapest", max_stores=3)
        vegetarian = await execute(
            "VEGETARIAN BALANCED max2",
            mode="balanced",
            max_stores=2,
            diet="vegetarian",
        )
    finally:
        optimizer_module.create_price_provider = original_factory

    report = {
        "schema_version": "consumer-planner-acceptance-v1",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "city": city,
        "postal_code": "22350",
        "price_universe_id": prepared.universe.universe_id,
        "artifact_load_seconds": round(load_seconds, 4),
        "network_policy": "fail_closed_offline_sentinel",
        "openai_enabled": False,
        "runs": [cold, warm, cheapest_1, cheapest_2, cheapest_3, vegetarian],
    }
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output = output_root / f"consumer-planner-acceptance-{stamp}.json"
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="Lund")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/consumer"),
    )
    args = parser.parse_args()
    output = asyncio.run(run(args.city, args.output_root))
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
