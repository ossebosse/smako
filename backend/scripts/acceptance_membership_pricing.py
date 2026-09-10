"""Offline acceptance benchmark for request-time membership pricing.

Every scenario loads the same active, hash-verified PriceUniverse.  A
fail-closed provider sentinel proves that membership changes only re-run local
pricing and optimization; any accidental grocery-provider call aborts the run.
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
from app.services.meal_plan_optimizer import MealPlanService
from app.services.price_universe_runtime import PreparedPriceUniverseManager

from grocery_data.app.domain.promotion_pricing import MembershipProgram
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)


class OfflineSentinelProvider:
    source_name = "offline_sentinel"
    attribution_text = None
    attribution_url = None

    async def find_stores(self, _postal_code: str) -> list[Any]:
        raise AssertionError("membership acceptance attempted a live store request")

    async def search_products(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("membership acceptance attempted a live product request")

    async def get_store_products(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("membership acceptance attempted a live catalog request")

    async def get_offers(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        raise AssertionError("membership acceptance attempted a live offer request")

    async def aclose(self) -> None:
        return None


def _shopping_rows(plan: Any) -> list[dict[str, Any]]:
    return [
        {
            "ingredient": item.ingredient,
            "product_id": item.product_id,
            "product": item.product_name,
            "store": group.store_name,
            "store_id": item.store_id,
            "chain": item.chain,
            "packages": item.packages_needed,
            "unit_price": item.unit_price,
            "regular_unit_price": item.regular_unit_price,
            "line_total": item.total_price,
            "regular_line_total": item.regular_total_price,
            "price_contract_id": item.price_contract_id,
            "eligibility": item.eligibility.value,
            "mechanism": item.price_mechanism.value,
            "membership_program": (
                item.membership_program.value
                if item.membership_program is not None
                else None
            ),
            "membership_required": item.membership_required,
            "offer": item.offer_description,
            "source": (
                item.source_provenance.source_provider
                if item.source_provenance is not None
                else None
            ),
            "snapshot_id": (
                item.source_provenance.source_snapshot_id
                if item.source_provenance is not None
                else None
            ),
        }
        for group in plan.optimized_basket.stores
        for item in group.items
    ]


def _summary(
    plan: Any,
    *,
    label: str,
    seconds: float,
    memberships: tuple[MembershipProgram, ...],
) -> dict[str, Any]:
    if plan.data is None or plan.data.live_chain_requests != 0:
        raise AssertionError("membership benchmark did not stay offline")
    if plan.optimized_basket.store_count > 2:
        raise AssertionError("membership benchmark exceeded max_stores=2")
    rows = _shopping_rows(plan)
    member_rows = [row for row in rows if row["membership_required"]]
    for row in member_rows:
        if row["membership_program"] not in {program.value for program in memberships}:
            raise AssertionError("basket contains an unauthorized member contract")
    return {
        "label": label,
        "memberships": [program.value for program in memberships],
        "runtime_seconds": round(seconds, 4),
        "total": plan.optimized_basket.total,
        "price_per_portion": plan.price_per_portion,
        "stores": [group.store_name for group in plan.optimized_basket.stores],
        "recipes": [recipe.name for recipe in plan.recipes],
        "membership_programs_used": [
            program.value for program in plan.membership_programs_used
        ],
        "membership_dependent_products": member_rows,
        "shopping_list": rows,
        "price_universe_id": plan.data.price_universe_id,
        "provider_calls": plan.data.live_chain_requests,
        "price_status": plan.data.status,
        "timings_ms": (
            ((plan.debug_info or {}).get("performance") or {}).get("timings_ms", {})
        ),
        "operation_counters": (
            ((plan.debug_info or {}).get("performance") or {}).get(
                "operation_counters",
                {},
            )
        ),
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

    async def execute(
        label: str,
        memberships: tuple[MembershipProgram, ...],
    ) -> dict[str, Any]:
        request = PlanRequest(
            postal_code="22350",
            recipes=5,
            servings=4,
            max_stores=2,
            diversity_mode="balanced",
            diet_preference="mixed",
            membership_programs=memberships,
            strategy="optimized",
            optimization_iterations=0,
            candidate_recipe_count=80,
            beam_width=30,
            debug=True,
        )
        started = perf_counter()
        plan = await service.create_plan(request)
        return _summary(
            plan,
            label=label,
            seconds=perf_counter() - started,
            memberships=memberships,
        )

    scenarios = (
        ("NO_MEMBERSHIPS_COLD", ()),
        ("NO_MEMBERSHIPS_WARM", ()),
        (
            "ALL_SUPPORTED_MEMBERSHIPS",
            (
                MembershipProgram.COOP_MEMBER,
                MembershipProgram.HEMKOP_MEMBER,
            ),
        ),
        (
            "ALL_SUPPORTED_MEMBERSHIPS_WARM",
            (
                MembershipProgram.COOP_MEMBER,
                MembershipProgram.HEMKOP_MEMBER,
            ),
        ),
        ("ICA_ONLY", (MembershipProgram.ICA_STAMMIS,)),
        ("COOP_ONLY", (MembershipProgram.COOP_MEMBER,)),
        ("HEMKOP_ONLY", (MembershipProgram.HEMKOP_MEMBER,)),
        ("LIDL_PLUS_ONLY", (MembershipProgram.LIDL_PLUS,)),
    )

    sentinel = OfflineSentinelProvider()
    original_factory = optimizer_module.create_price_provider
    optimizer_module.create_price_provider = lambda *_args, **_kwargs: sentinel
    try:
        runs = [await execute(label, programs) for label, programs in scenarios]
    finally:
        optimizer_module.create_price_provider = original_factory

    universe_ids = {run["price_universe_id"] for run in runs}
    if universe_ids != {prepared.universe.universe_id}:
        raise AssertionError("membership scenarios did not use one shared universe")
    if any(run["provider_calls"] != 0 for run in runs):
        raise AssertionError("membership scenarios performed provider calls")

    report = {
        "schema_version": "membership-pricing-acceptance-v1",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "city": city,
        "postal_code": "22350",
        "recipes": 5,
        "servings": 4,
        "max_stores": 2,
        "diet": "mixed",
        "mode": "balanced",
        "price_universe_id": prepared.universe.universe_id,
        "artifact_load_seconds": round(load_seconds, 4),
        "network_policy": "fail_closed_offline_sentinel",
        "provider_calls_during_planning": 0,
        "runs": runs,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output = output_root / f"membership-pricing-acceptance-{stamp}.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--city", default="Lund")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/membership-pricing"),
    )
    args = parser.parse_args()
    output = asyncio.run(run(args.city, args.output_root))
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
