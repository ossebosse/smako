"""Freeze or verify the production planner's exact economic golden results.

The runner is deliberately offline: it loads the active hash-verified
``PriceUniverse`` once and replaces the provider factory with a fail-closed
sentinel.  ``freeze`` writes a new immutable report; ``verify`` replays the
same inputs and retail-calendar date and requires byte-equivalent semantic
fingerprints.

Wall-clock measurements are useful evidence but are not part of economic
identity.  Recipe instructions are retained in the report, while the economic
fingerprint covers recipe identity/quantities, normalized demands, selected
products/packages/contracts, stores, prices, source provenance, nutrition and
diversity results.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
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
from app.services.ingredient_normalizer import IngredientNormalizer
from app.services.meal_plan_optimizer import MealPlanService
from app.services.price_universe_runtime import (
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
)
from app.services.recipe_generator import MockRecipeGenerator
from app.services.user_pricing import (
    current_pricing_date,
    prepare_economic_pool_for_pricing,
    project_economic_pool,
)

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    UserPricingContext,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)

_FIXED_RECIPE_INDEXES = (0, 1, 2, 4, 5)
_SCHEMA_VERSION = "production-planner-golden-v1"


class OfflineSentinelProvider:
    """Fail closed if a planner request attempts a live source operation."""

    source_name = "offline_sentinel"
    attribution_text = None
    attribution_url = None

    def __init__(self) -> None:
        self.calls = 0

    def _reject(self, operation: str) -> None:
        self.calls += 1
        raise AssertionError(f"golden benchmark attempted live {operation}")

    async def find_stores(self, _postal_code: str) -> list[Any]:
        self._reject("store lookup")

    async def search_products(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        self._reject("product search")

    async def get_store_products(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        self._reject("catalog request")

    async def get_offers(self, *_args: Any, **_kwargs: Any) -> list[Any]:
        self._reject("offer request")

    async def aclose(self) -> None:
        return None


def semantic_fingerprint(payload: Any) -> str:
    """Return a stable SHA-256 over one JSON-compatible semantic payload."""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("golden artifact must be inside the repository") from exc


def _contract_reference(item: Any) -> tuple[str, str]:
    if item.price_contract_id is not None:
        return item.price_contract_id, "basket_selected"
    provenance = item.source_provenance
    snapshot_id = (
        provenance.source_snapshot_id if provenance is not None else "unknown-snapshot"
    )
    payload = f"{snapshot_id}|{item.store_id}|{item.product_id}|regular"
    return (
        "price-contract:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24],
        "derived_regular_contract_identity",
    )


def _recipe_semantics(recipe: Any) -> dict[str, Any]:
    ingredients = [ingredient.model_dump(mode="json") for ingredient in recipe.ingredients]
    ingredients.sort(
        key=lambda row: (
            str(row.get("canonical_name") or row["name"]).casefold(),
            str(row["unit"]),
            float(row["quantity"]),
            str(row["name"]).casefold(),
        )
    )
    return {
        "name": recipe.name,
        "servings": recipe.servings,
        "ingredients": ingredients,
    }


def _full_recipes(recipes: list[Any]) -> list[dict[str, Any]]:
    rows = [recipe.model_dump(mode="json") for recipe in recipes]
    return sorted(rows, key=lambda row: (str(row["name"]).casefold(), str(row["name"])))


def _canonical_ingredients(ingredients: list[Any]) -> list[dict[str, Any]]:
    rows = [ingredient.model_dump(mode="json") for ingredient in ingredients]
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("canonical_name") or "").casefold(),
            str(row.get("unit") or ""),
            float(row.get("quantity") or 0),
        ),
    )


def _basket_semantics(basket: Any) -> dict[str, Any]:
    stores: list[dict[str, Any]] = []
    for group in basket.stores:
        items: list[dict[str, Any]] = []
        for item in group.items:
            contract_id, reference_source = _contract_reference(item)
            row = item.model_dump(mode="json")
            row["selected_price_contract_reference"] = contract_id
            row["selected_price_contract_reference_source"] = reference_source
            items.append(row)
        items.sort(
            key=lambda row: (
                str(row["ingredient"]).casefold(),
                str(row["product_id"]),
                str(row["selected_price_contract_reference"]),
            )
        )
        stores.append(
            {
                "store_id": group.store_id,
                "store_name": group.store_name,
                "subtotal": group.subtotal,
                "items": items,
            }
        )
    stores.sort(key=lambda row: (str(row["store_id"]), str(row["store_name"])))
    return {
        "total": basket.total,
        "max_stores": basket.max_stores,
        "store_count": basket.store_count,
        "verification_status": basket.verification_status.value,
        "total_reconciled": basket.total_reconciled,
        "stores": stores,
    }


def _price_data_semantics(data: Any) -> dict[str, Any]:
    if data is None:
        raise AssertionError("golden plan omitted PriceUniverse provenance")
    return {
        "price_universe_id": data.price_universe_id,
        "built_at": data.built_at.isoformat(),
        "snapshot_ids": sorted(data.snapshot_ids),
        "product_count": data.product_count,
        "canonical_index_count": data.canonical_index_count,
        "status": data.status,
        "live_chain_requests": data.live_chain_requests,
    }


def _plan_semantics(plan: Any, request: PlanRequest) -> dict[str, Any]:
    if plan.data is None or plan.data.live_chain_requests != 0:
        raise AssertionError("golden planner did not remain offline")
    if plan.quality is None or plan.quality.status.value != "PASS":
        raise AssertionError("golden planner quality audit did not pass")
    if plan.optimized_basket.store_count > request.max_stores:
        raise AssertionError("golden planner exceeded max_stores")
    recipes = sorted(
        (_recipe_semantics(recipe) for recipe in plan.recipes),
        key=lambda row: (str(row["name"]).casefold(), str(row["name"])),
    )
    membership_savings = (
        plan.membership_savings.model_dump(mode="json")
        if plan.membership_savings is not None
        else None
    )
    return {
        "request": request.model_dump(mode="json", exclude={"debug"}),
        "recipes": recipes,
        "canonical_ingredients": _canonical_ingredients(plan.ingredients),
        "basket": _basket_semantics(plan.optimized_basket),
        "price_per_portion": plan.price_per_portion,
        "portions": plan.portions,
        "quality": plan.quality.model_dump(mode="json"),
        "membership_programs_used": sorted(
            program.value for program in plan.membership_programs_used
        ),
        "membership_savings": membership_savings,
        "price_data": _price_data_semantics(plan.data),
    }


def _plan_report(
    plan: Any,
    request: PlanRequest,
    *,
    elapsed_seconds: float,
) -> dict[str, Any]:
    semantics = _plan_semantics(plan, request)
    basket = semantics["basket"]
    selected_contracts = [
        {
            "store_id": store["store_id"],
            "product_id": item["product_id"],
            "contract_id": item["selected_price_contract_reference"],
            "eligibility": item["eligibility"],
            "mechanism": item["price_mechanism"],
            "membership_program": item["membership_program"],
            "packages": item["packages_needed"],
            "line_total": item["total_price"],
        }
        for store in basket["stores"]
        for item in store["items"]
    ]
    selected_contracts.sort(
        key=lambda row: (str(row["store_id"]), str(row["product_id"]))
    )
    return {
        "runtime_observation_seconds": round(elapsed_seconds, 6),
        "semantic_fingerprint": semantic_fingerprint(semantics),
        "input": semantics["request"],
        # Pydantic's explicit-field set is semantically relevant: diversity
        # presets intentionally distinguish an omitted default from a user
        # supplied override with the same numeric value.  Persist it alongside
        # the value payload so isolated benchmark workers replay the same
        # request rather than a superficially equal but different one.
        "input_fields_set": sorted(request.model_fields_set),
        "recipes": _full_recipes(plan.recipes),
        "canonical_ingredients": semantics["canonical_ingredients"],
        "selected_basket": basket,
        "selected_price_contracts": selected_contracts,
        "total": plan.optimized_basket.total,
        "price_per_portion": plan.price_per_portion,
        "nutrition": plan.quality.nutrition.model_dump(mode="json"),
        "diversity": plan.quality.diversity.model_dump(mode="json"),
        "basket_audit": plan.quality.basket_audit.model_dump(mode="json"),
        "membership_programs_used": semantics["membership_programs_used"],
        "membership_savings": semantics["membership_savings"],
        "provenance": semantics["price_data"],
    }


def _base_projection(prepared: PreparedPriceUniverse, service: MealPlanService) -> Any:
    return prepared.pricing_projection_cache.get_or_compute(
        f"pricing-semantics:{service.economic_selector.cache_identity}",
        lambda: prepare_economic_pool_for_pricing(
            prepared.economic_pool,
            selector=service.economic_selector,
        ),
    )


def _membership_projection(
    prepared: PreparedPriceUniverse,
    service: MealPlanService,
    base_pool: Any,
    programs: tuple[MembershipProgram, ...],
    *,
    pricing_date: date,
) -> Any:
    context = UserPricingContext(memberships=set(programs))
    key = (
        f"{context.cache_identity}:{pricing_date.isoformat()}:"
        f"{service.economic_selector.cache_identity}"
    )
    return prepared.pricing_projection_cache.get_or_compute(
        key,
        lambda: project_economic_pool(
            base_pool,
            context,
            selector=service.economic_selector,
            on_date=pricing_date,
        ),
    )


def _fixed_menu_report(
    prepared: PreparedPriceUniverse,
    service: MealPlanService,
    *,
    pricing_date: date,
) -> dict[str, Any]:
    all_recipes = MockRecipeGenerator().generate_recipes((), count=7, servings=4)
    recipes = [all_recipes[index] for index in _FIXED_RECIPE_INDEXES]
    ingredients = IngredientNormalizer().normalize_and_aggregate(recipes)
    all_programs = tuple(sorted(MembershipProgram, key=lambda row: row.value))
    scenarios = {
        "NO_MEMBERSHIPS": (),
        "ICA_ONLY": (MembershipProgram.ICA_STAMMIS,),
        "COOP_ONLY": (MembershipProgram.COOP_MEMBER,),
        "HEMKOP_ONLY": (MembershipProgram.HEMKOP_MEMBER,),
        "LIDL_PLUS_ONLY": (MembershipProgram.LIDL_PLUS,),
        "WILLYS_PLUS_ONLY": (MembershipProgram.WILLYS_PLUS,),
        "ALL_MEMBERSHIPS": all_programs,
    }
    base_pool = _base_projection(prepared, service)
    rows: dict[str, Any] = {}
    for label, programs in scenarios.items():
        pool = _membership_projection(
            prepared,
            service,
            base_pool,
            programs,
            pricing_date=pricing_date,
        )
        missing = sorted(
            ingredient.canonical_name
            for ingredient in ingredients
            if ingredient.canonical_name not in pool.candidates_by_name
        )
        if missing:
            raise AssertionError(f"fixed golden menu missing candidates: {', '.join(missing)}")
        basket = service.basket_optimizer.optimize(
            ingredients,
            pool.candidates_by_name,
            prepared.stores,
            max_stores=2,
        )
        context = UserPricingContext(memberships=set(programs))
        audit = service.basket_auditor.audit(
            ingredients,
            basket,
            user_pricing_context=context,
        )
        if not audit.passed:
            raise AssertionError(f"fixed golden basket audit failed for {label}")
        basket_semantics = _basket_semantics(basket)
        row_semantics = {
            "membership_programs": sorted(program.value for program in programs),
            "basket": basket_semantics,
            "basket_audit": audit.model_dump(mode="json"),
        }
        rows[label] = {
            **row_semantics,
            "semantic_fingerprint": semantic_fingerprint(row_semantics),
        }

    request = PlanRequest(
        postal_code="22350",
        recipes=5,
        servings=4,
        max_stores=2,
        diversity_mode="balanced",
        diet_preference="mixed",
        strategy="optimized",
        optimization_iterations=0,
        candidate_recipe_count=80,
        beam_width=30,
    )
    nutrition_validator = service._nutrition_for(request)
    nutrition = service._nutrition_summary(nutrition_validator.validate_recipes(recipes))
    diversity_policy = service._diversity_policy_for(request, request.diversity_mode)
    diversity = service._diversity_summary(
        service._culinary_report(recipes),
        diversity_policy,
    )
    semantics = {
        "recipes": sorted(
            (_recipe_semantics(recipe) for recipe in recipes),
            key=lambda row: (str(row["name"]).casefold(), str(row["name"])),
        ),
        "canonical_ingredients": _canonical_ingredients(ingredients),
        "nutrition": nutrition.model_dump(mode="json"),
        "diversity": diversity.model_dump(mode="json"),
        "quality_status": {
            "nutrition": nutrition.status.value,
            "diversity": diversity.status.value,
            "note": (
                "frozen diagnostic result; the historical fixed-menu pricing "
                "benchmark did not require these policies to pass"
            ),
        },
        "scenarios": rows,
        "price_universe_id": prepared.universe.universe_id,
        "pricing_date": pricing_date.isoformat(),
    }
    return {
        "semantic_fingerprint": semantic_fingerprint(semantics),
        "recipes": _full_recipes(recipes),
        "canonical_ingredients": semantics["canonical_ingredients"],
        "nutrition": semantics["nutrition"],
        "diversity": semantics["diversity"],
        "quality_status": semantics["quality_status"],
        "scenarios": rows,
    }


def _request(
    *,
    mode: str,
    max_stores: int,
    diet: str = "mixed",
    memberships: tuple[MembershipProgram, ...] = (),
) -> PlanRequest:
    return PlanRequest(
        postal_code="22350",
        recipes=5,
        servings=4,
        max_stores=max_stores,
        diversity_mode=mode,
        diet_preference=diet,
        membership_programs=memberships,
        strategy="optimized",
        optimization_iterations=0,
        candidate_recipe_count=80,
        beam_width=30,
        debug=False,
    )


async def _build_suite(
    city: str,
    *,
    pricing_date: date,
) -> dict[str, Any]:
    base_settings = Settings.from_env()
    settings = replace(
        base_settings,
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
    all_programs = tuple(sorted(MembershipProgram, key=lambda row: row.value))
    scenarios = (
        (
            "balanced_max2_no_memberships",
            _request(mode="balanced", max_stores=2),
        ),
        (
            "balanced_max2_all_memberships",
            _request(mode="balanced", max_stores=2, memberships=all_programs),
        ),
        ("cheapest_max1", _request(mode="cheapest", max_stores=1)),
        ("cheapest_max2", _request(mode="cheapest", max_stores=2)),
        ("cheapest_max3", _request(mode="cheapest", max_stores=3)),
        (
            "vegetarian_balanced_max2",
            _request(mode="balanced", max_stores=2, diet="vegetarian"),
        ),
    )

    original_factory = optimizer_module.create_price_provider
    original_pricing_date = optimizer_module.current_pricing_date
    optimizer_module.create_price_provider = lambda *_args, **_kwargs: sentinel
    optimizer_module.current_pricing_date = lambda: pricing_date
    dynamic_rows: dict[str, Any] = {}
    try:
        for scenario_id, request in scenarios:
            started = perf_counter()
            plan = await service.create_plan(request)
            dynamic_rows[scenario_id] = _plan_report(
                plan,
                request,
                elapsed_seconds=perf_counter() - started,
            )
    finally:
        optimizer_module.create_price_provider = original_factory
        optimizer_module.current_pricing_date = original_pricing_date
    if sentinel.calls:
        raise AssertionError("golden planner touched a live provider")

    fixed = _fixed_menu_report(
        prepared,
        service,
        pricing_date=pricing_date,
    )
    scenario_fingerprints = {
        scenario_id: row["semantic_fingerprint"]
        for scenario_id, row in sorted(dynamic_rows.items())
    }
    scenario_fingerprints["fixed_menu_membership"] = fixed["semantic_fingerprint"]
    suite_identity = {
        "schema_version": _SCHEMA_VERSION,
        "price_universe_id": prepared.universe.universe_id,
        "artifact_sha256": _file_sha256(artifact_path),
        "pricing_date_europe_stockholm": pricing_date.isoformat(),
        "scenario_fingerprints": scenario_fingerprints,
    }
    return {
        "schema_version": _SCHEMA_VERSION,
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "city": city,
        "pricing_date_europe_stockholm": pricing_date.isoformat(),
        "network_policy": "fail_closed_offline_sentinel",
        "provider_calls_during_planning": sentinel.calls,
        "price_universe": {
            "id": prepared.universe.universe_id,
            "artifact_path": _repository_relative(artifact_path),
            "artifact_sha256": suite_identity["artifact_sha256"],
            "artifact_size_bytes": artifact_path.stat().st_size,
            "load_observation_seconds": round(load_seconds, 6),
            "built_at": prepared.universe.built_at.isoformat(),
            "snapshot_ids": sorted(prepared.universe.key.snapshot_ids),
            "products": prepared.universe.stats.raw_products,
            "optimizer_products": prepared.universe.stats.canonical_mappings,
            "contexts": len(prepared.universe.indexes.context_order),
        },
        "dynamic_scenarios": dynamic_rows,
        "fixed_menu_membership": fixed,
        "scenario_fingerprints": scenario_fingerprints,
        "semantic_fingerprint": semantic_fingerprint(suite_identity),
        "fingerprint_contract": {
            "included": [
                "frozen input",
                "recipe identity and ingredient quantities",
                "canonical ingredient demands",
                "selected products, packages and price contracts",
                "stores and price contexts",
                "total and price per portion",
                "nutrition, diversity and basket audit",
                "source provenance and PriceUniverse identity",
            ],
            "excluded": [
                "generated_at",
                "wall-clock runtimes",
                "recipe instructions and display-only ordering",
            ],
        },
    }


def _write_new(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"refusing to overwrite frozen golden: {path}")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _normalized_label(value: str | None) -> str:
    if value is None:
        return ""
    normalized = "-".join(value.strip().casefold().split())
    if not normalized or any(not (character.isalnum() or character == "-") for character in normalized):
        raise ValueError("golden label must contain only letters, numbers, spaces or hyphens")
    return f"-{normalized}"


async def _freeze(city: str, output_root: Path, *, label: str | None = None) -> Path:
    pricing_date = current_pricing_date()
    suite = await _build_suite(city, pricing_date=pricing_date)
    universe_short = str(suite["price_universe"]["id"]).split(":")[-1][:12]
    output = output_root / (
        f"production-planner-golden-{pricing_date.isoformat()}-{universe_short}"
        f"{_normalized_label(label)}.json"
    )
    _write_new(output, suite)
    return output


async def _verify(golden: Path, output_root: Path) -> Path:
    expected = json.loads(golden.read_text(encoding="utf-8"))
    if expected.get("schema_version") != _SCHEMA_VERSION:
        raise ValueError("unsupported golden schema")
    pricing_date = date.fromisoformat(expected["pricing_date_europe_stockholm"])
    city = str(expected["city"])
    actual = await _build_suite(city, pricing_date=pricing_date)
    expected_universe = expected["price_universe"]["id"]
    actual_universe = actual["price_universe"]["id"]
    if actual_universe != expected_universe:
        raise AssertionError(
            f"active PriceUniverse changed: {actual_universe} != {expected_universe}"
        )
    expected_rows = expected["scenario_fingerprints"]
    actual_rows = actual["scenario_fingerprints"]
    comparisons = {
        scenario_id: {
            "expected": expected_rows.get(scenario_id),
            "actual": actual_rows.get(scenario_id),
            "matches": expected_rows.get(scenario_id) == actual_rows.get(scenario_id),
        }
        for scenario_id in sorted(set(expected_rows) | set(actual_rows))
    }
    passed = all(row["matches"] for row in comparisons.values())
    report = {
        "schema_version": "production-planner-golden-verification-v1",
        "generated_at_utc": datetime.now(tz=UTC).isoformat(),
        "golden_path": _repository_relative(golden),
        "price_universe_id": actual_universe,
        "pricing_date_europe_stockholm": pricing_date.isoformat(),
        "expected_suite_fingerprint": expected["semantic_fingerprint"],
        "actual_suite_fingerprint": actual["semantic_fingerprint"],
        "scenario_comparisons": comparisons,
        "status": "PASS" if passed else "FAIL",
        "provider_calls_during_planning": actual["provider_calls_during_planning"],
    }
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output = output_root / f"production-planner-golden-verification-{stamp}.json"
    _write_new(output, report)
    if not passed:
        failed = ", ".join(
            scenario_id for scenario_id, row in comparisons.items() if not row["matches"]
        )
        raise AssertionError(f"economic golden mismatch: {failed}; report={output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("freeze", "verify"))
    parser.add_argument("--city", default="Lund")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/planner-performance/golden"),
    )
    parser.add_argument("--golden", type=Path)
    parser.add_argument(
        "--label",
        help=(
            "optional immutable baseline label, for example store-cap-v1; "
            "used only when freezing"
        ),
    )
    args = parser.parse_args()
    if args.action == "verify" and args.golden is None:
        parser.error("verify requires --golden")
    output = (
        asyncio.run(_freeze(args.city, args.output_root, label=args.label))
        if args.action == "freeze"
        else asyncio.run(_verify(args.golden, args.output_root))
    )
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
