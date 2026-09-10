"""Offline proof for membership-aware candidate generation and fixed-menu pricing.

The benchmark loads one active, hash-verified Lund PriceUniverse and never
contacts a grocery provider.  It deliberately separates three questions:

* does eligibility change the complete pre-shortlist economic ranking?
* can the exact same deterministic menu only become cheaper when memberships
  are added?
* does the normal 5x4 BALANCED planner remain offline and cache-safe when the
  membership context changes?

The real Fusilli Fullkorn row is found through its source-backed product/store
identity.  No production selection rule is special-cased for that product.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
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
from app.models import NormalizedIngredient, PlanRequest
from app.models.product import ProductCandidate
from app.services import meal_plan_optimizer as optimizer_module
from app.services.basket_calculator import BasketCalculator
from app.services.economic_ingredient_selector import _candidate_key
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
    price_contracts_for_candidate,
    project_economic_pool,
)

from grocery_data.app.domain.promotion_pricing import (
    MembershipProgram,
    PromotionEligibility,
    PromotionMechanism,
    UserPricingContext,
)
from grocery_data.app.services.prepared_universe_activation import (
    PreparedUniverseArtifactStore,
)

_TARGET_PRODUCT_NAME = "Fusilli Fullkorn Pasta"
_TARGET_PROVIDER_STORE_ID = "4123"
_FIXED_RECIPE_INDEXES = (0, 1, 2, 4, 5)
_MONEY_TOLERANCE = Decimal("0.005")


class OfflineSentinelProvider:
    """Fail closed if normal planning attempts any source/provider request."""

    source_name = "offline_sentinel"
    attribution_text = None
    attribution_url = None

    def __init__(self) -> None:
        self.calls = 0

    def _reject(self, operation: str) -> None:
        self.calls += 1
        raise AssertionError(f"membership coverage acceptance attempted live {operation}")

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


def _context(programs: tuple[MembershipProgram, ...]) -> UserPricingContext:
    return UserPricingContext(memberships=set(programs))


def _provider_store_id(candidate: ProductCandidate) -> str | None:
    provenance = candidate.source_provenance
    return provenance.provider_store_id if provenance is not None else None


def _identity(candidate: ProductCandidate) -> tuple[str, str]:
    return candidate.store_id, candidate.product_id


def _basket_rows(basket: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in basket.stores:
        for item in group.items:
            provenance = item.source_provenance
            contract_id = item.price_contract_id
            contract_reference_source = "basket_selected"
            if contract_id is None:
                snapshot_id = (
                    provenance.source_snapshot_id if provenance is not None else "unknown-snapshot"
                )
                payload = f"{snapshot_id}|{item.store_id}|{item.product_id}|regular"
                contract_id = (
                    "price-contract:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
                )
                contract_reference_source = "derived_regular_contract_identity"
            rows.append(
                {
                    "ingredient": item.ingredient,
                    "required_quantity": item.required_quantity,
                    "required_unit": item.unit,
                    "product_id": item.product_id,
                    "gtin": item.gtin,
                    "product": item.product_name,
                    "store_id": item.store_id,
                    "store": group.store_name,
                    "chain": item.chain,
                    "packages": item.packages_needed,
                    "line_total": item.total_price,
                    "eligibility": item.eligibility.value,
                    "mechanism": item.price_mechanism.value,
                    "membership_program": (
                        item.membership_program.value
                        if item.membership_program is not None
                        else None
                    ),
                    "price_contract_id": contract_id,
                    "price_contract_reference_source": contract_reference_source,
                    "source_provider": (
                        provenance.source_provider if provenance is not None else None
                    ),
                    "source_snapshot_id": (
                        provenance.source_snapshot_id if provenance is not None else None
                    ),
                    "source_observed_at": (
                        provenance.source_observed_at.isoformat()
                        if provenance is not None and provenance.source_observed_at is not None
                        else None
                    ),
                    "provider_store_id": (
                        provenance.provider_store_id if provenance is not None else None
                    ),
                    "price_context_type": item.price_context_type,
                    "coverage": item.coverage,
                }
            )
    return rows


def _safe_artifact_report_path(artifact_path: Path) -> str:
    """Return a repository-relative artifact reference without user identity."""

    resolved = artifact_path.resolve()
    try:
        relative = resolved.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("active artifact must be stored inside the repository") from exc
    return relative.as_posix()


def _top_timings(timings: dict[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    """Return the slowest numeric traced spans in stable descending order."""

    numeric = [
        (str(name), float(milliseconds))
        for name, milliseconds in timings.items()
        if isinstance(milliseconds, int | float)
    ]
    return [
        {"operation": name, "milliseconds": round(milliseconds, 3)}
        for name, milliseconds in sorted(
            numeric,
            key=lambda row: (-row[1], row[0]),
        )[:limit]
    ]


def _assert_monotonic(
    rows: dict[str, dict[str, Any]],
    *,
    baseline: str = "NO_MEMBERSHIPS",
) -> None:
    """Prove that every membership superset keeps the public basket feasible."""

    public_total = Decimal(str(rows[baseline]["total"]))
    for label, row in rows.items():
        total = Decimal(str(row["total"]))
        if total > public_total + _MONEY_TOLERANCE:
            raise AssertionError(
                "fixed-menu membership monotonicity failed: "
                f"{label}={total} > {baseline}={public_total}"
            )


def _validity_bucket(contract: Any, *, pricing_date: date) -> str:
    if contract.valid_from is not None and pricing_date < contract.valid_from:
        return "future"
    if contract.valid_to is not None and pricing_date > contract.valid_to:
        return "expired"
    if not contract.is_active(pricing_date):
        raise AssertionError(
            f"contract {contract.reference} is inactive without temporal explanation"
        )
    return "active_now"


def _empty_contract_counts() -> dict[str, int]:
    return {
        "total": 0,
        "active_now": 0,
        "expired": 0,
        "future": 0,
        "member_multibuy_total": 0,
        "active_member_multibuy": 0,
        "expired_member_multibuy": 0,
        "future_member_multibuy": 0,
    }


def _increment_member_counts(
    counts: dict[str, int],
    *,
    bucket: str,
    multibuy: bool,
) -> None:
    counts["total"] += 1
    counts[bucket] += 1
    if multibuy:
        counts["member_multibuy_total"] += 1
        counts[f"{bucket.removesuffix('_now')}_member_multibuy"] += 1


def _contract_audit(
    prepared: PreparedPriceUniverse,
    *,
    pricing_date: date,
) -> dict[str, Any]:
    """Count unique normalized contracts across every source product row."""

    seen_contracts: set[tuple[str, str, str]] = set()
    seen_products: set[tuple[str, str]] = set()
    generic_member = _empty_contract_counts()
    per_program_context: dict[tuple[str, str], dict[str, int]] = {}
    total_contracts = 0
    user_specific = 0
    store_names = {store.store_id: store.name for store in prepared.stores}

    for product in prepared.universe.products:
        product_identity = (product.store_id, product.product_id)
        seen_products.add(product_identity)
        candidate = ProductCandidate.from_product(product, match_score=1.0)
        for contract in price_contracts_for_candidate(candidate):
            identity = (product.store_id, product.product_id, contract.reference)
            if identity in seen_contracts:
                continue
            seen_contracts.add(identity)
            total_contracts += 1
            if contract.eligibility is PromotionEligibility.USER_SPECIFIC:
                user_specific += 1
            if contract.eligibility is not PromotionEligibility.MEMBER:
                continue
            if contract.membership_program is None:
                raise AssertionError(f"generic member contract lacks program: {contract.reference}")
            bucket = _validity_bucket(contract, pricing_date=pricing_date)
            multibuy = contract.mechanism is PromotionMechanism.MULTIBUY
            _increment_member_counts(
                generic_member,
                bucket=bucket,
                multibuy=multibuy,
            )
            context_id = contract.price_context_id or product.store_id
            context_counts = per_program_context.setdefault(
                (contract.membership_program.value, context_id),
                _empty_contract_counts(),
            )
            _increment_member_counts(
                context_counts,
                bucket=bucket,
                multibuy=multibuy,
            )

    if user_specific:
        raise AssertionError("USER_SPECIFIC contracts entered the shared PriceUniverse")
    context_rows = []
    for (program, context_id), counts in sorted(per_program_context.items()):
        context_rows.append(
            {
                "membership_program": program,
                "context_id": context_id,
                "context_name": store_names.get(context_id),
                **counts,
            }
        )
    return {
        "source_product_rows": len(prepared.universe.products),
        "unique_product_context_identities": len(seen_products),
        "unique_normalized_contracts": total_contracts,
        "generic_member": generic_member,
        "user_specific": user_specific,
        "deduplication_identity": (
            "price_context_id + source_product_id + normalized_contract_reference"
        ),
        "per_membership_program_context": context_rows,
    }


def _pricing_base(
    prepared: PreparedPriceUniverse,
    service: MealPlanService,
) -> Any:
    return prepared.pricing_projection_cache.get_or_compute(
        f"pricing-semantics:{service.economic_selector.cache_identity}",
        lambda: prepare_economic_pool_for_pricing(
            prepared.economic_pool,
            selector=service.economic_selector,
        ),
    )


def _projection(
    prepared: PreparedPriceUniverse,
    service: MealPlanService,
    base_pool: Any,
    programs: tuple[MembershipProgram, ...],
    *,
    pricing_date: date,
) -> Any:
    context = _context(programs)
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


def _candidate_diagnostic_row(
    candidate: ProductCandidate,
    *,
    rank: int,
    entry: Any,
    requirement: NormalizedIngredient,
    shortlist_identities: set[tuple[str, str]],
) -> dict[str, Any]:
    quote = BasketCalculator().quote_item(requirement, candidate)
    return {
        "rank_before_product_shortlist": rank,
        "product_id": candidate.product_id,
        "gtin": candidate.gtin,
        "product": candidate.product_name,
        "store_id": candidate.store_id,
        "store": candidate.store_name,
        "provider_store_id": _provider_store_id(candidate),
        "effective_package_price": candidate.effective_price,
        "typical_demand_total": float(quote.total_price),
        "economic_score": round(_candidate_key(entry, candidate)[0], 6),
        "selected_eligibility": candidate.selected_price_eligibility.value,
        "membership_program": (
            candidate.selected_membership_program.value
            if candidate.selected_membership_program is not None
            else None
        ),
        "survives_product_shortlist": _identity(candidate) in shortlist_identities,
    }


def _fusilli_probe(
    prepared: PreparedPriceUniverse,
    service: MealPlanService,
    base_pool: Any,
    *,
    pricing_date: date,
) -> dict[str, Any]:
    entry = next(row for row in service.economic_selector.taxonomy if row.canonical == "pasta")
    contexts = {
        "NO_MEMBERSHIPS": (),
        "HEMKOP_MEMBER": (MembershipProgram.HEMKOP_MEMBER,),
    }
    requirement = NormalizedIngredient(
        canonical_name="pasta",
        required_quantity=entry.typical_meal_quantity,
        unit=entry.expected_unit,
    )
    result: dict[str, Any] = {
        "product": _TARGET_PRODUCT_NAME,
        "provider_store_id": _TARGET_PROVIDER_STORE_ID,
        "ingredient_demand": requirement.model_dump(mode="json"),
        "scenarios": {},
    }
    target_identity: tuple[str, str] | None = None
    for label, programs in contexts.items():
        pool = _projection(
            prepared,
            service,
            base_pool,
            programs,
            pricing_date=pricing_date,
        )
        ranked = sorted(
            pool.semantic_candidates_by_name["pasta"],
            key=lambda candidate: _candidate_key(entry, candidate),
        )
        targets = [
            candidate
            for candidate in ranked
            if candidate.product_name == _TARGET_PRODUCT_NAME
            and (candidate.chain or "").casefold() == "hemkop"
            and _provider_store_id(candidate) == _TARGET_PROVIDER_STORE_ID
        ]
        if len(targets) != 1:
            raise AssertionError(
                f"expected one exact Karhogstorg Fusilli Fullkorn candidate, found {len(targets)}"
            )
        target = targets[0]
        if target_identity is None:
            target_identity = _identity(target)
        elif _identity(target) != target_identity:
            raise AssertionError("Fusilli identity changed between pricing contexts")
        shortlist = pool.candidates_by_name["pasta"]
        shortlist_identities = {_identity(candidate) for candidate in shortlist}
        target_rank = next(
            rank
            for rank, candidate in enumerate(ranked, start=1)
            if _identity(candidate) == target_identity
        )
        basket = service.basket_optimizer.optimize(
            [requirement],
            pool.candidates_by_name,
            prepared.stores,
            max_stores=2,
        )
        result["scenarios"][label] = {
            "membership_programs": [program.value for program in programs],
            "pre_shortlist_candidate_count": len(ranked),
            "product_shortlist_count": len(shortlist),
            "target": _candidate_diagnostic_row(
                target,
                rank=target_rank,
                entry=entry,
                requirement=requirement,
                shortlist_identities=shortlist_identities,
            ),
            "top_candidates_before_shortlist": [
                _candidate_diagnostic_row(
                    candidate,
                    rank=rank,
                    entry=entry,
                    requirement=requirement,
                    shortlist_identities=shortlist_identities,
                )
                for rank, candidate in enumerate(ranked[:15], start=1)
            ],
            "final_basket_total": basket.total,
            "final_selected_products": _basket_rows(basket),
        }

    public_target = result["scenarios"]["NO_MEMBERSHIPS"]["target"]
    member_target = result["scenarios"]["HEMKOP_MEMBER"]["target"]
    if public_target["effective_package_price"] != 15.09:
        raise AssertionError("Fusilli public regression is not 15.09 SEK")
    if member_target["effective_package_price"] != 10.0:
        raise AssertionError("Fusilli Klubb Hemkop regression is not 10.00 SEK")
    if (
        member_target["rank_before_product_shortlist"]
        >= public_target["rank_before_product_shortlist"]
    ):
        raise AssertionError("Hemkop membership did not improve Fusilli's upstream rank")
    if not member_target["survives_product_shortlist"]:
        raise AssertionError("member-priced Fusilli did not survive the product shortlist")
    return result


def _fixed_menu(
    prepared: PreparedPriceUniverse,
    service: MealPlanService,
    base_pool: Any,
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
    rows: dict[str, dict[str, Any]] = {}
    for label, programs in scenarios.items():
        pool = _projection(
            prepared,
            service,
            base_pool,
            programs,
            pricing_date=pricing_date,
        )
        missing = [
            ingredient.canonical_name
            for ingredient in ingredients
            if ingredient.canonical_name not in pool.candidates_by_name
        ]
        if missing:
            raise AssertionError(
                f"fixed menu is not priceable in {label}; missing {', '.join(missing)}"
            )
        basket = service.basket_optimizer.optimize(
            ingredients,
            pool.candidates_by_name,
            prepared.stores,
            max_stores=2,
        )
        basket_rows = _basket_rows(basket)
        allowed = set(programs)
        unauthorized = [
            row
            for row in basket_rows
            if row["membership_program"] is not None
            and MembershipProgram(row["membership_program"]) not in allowed
        ]
        if unauthorized:
            raise AssertionError(f"{label} selected unauthorized member contracts")
        rows[label] = {
            "membership_programs": [program.value for program in programs],
            "total": basket.total,
            "delta_vs_no_memberships": None,
            "stores": [group.store_name for group in basket.stores],
            "membership_dependent_products": [
                row for row in basket_rows if row["membership_program"] is not None
            ],
            "shopping_list": basket_rows,
        }

    public_total = Decimal(str(rows["NO_MEMBERSHIPS"]["total"]))
    for row in rows.values():
        row["delta_vs_no_memberships"] = float(
            (Decimal(str(row["total"])) - public_total).quantize(Decimal("0.01"))
        )
    _assert_monotonic(rows)
    return {
        "recipe_source": "deterministic MockRecipeGenerator templates",
        "recipes": [recipe.name for recipe in recipes],
        "servings_per_recipe": 4,
        "ingredients": [ingredient.model_dump(mode="json") for ingredient in ingredients],
        "max_stores": 2,
        "monotonicity_invariant": "PASS",
        "scenarios": rows,
    }


def _plan_summary(
    plan: Any,
    *,
    label: str,
    memberships: tuple[MembershipProgram, ...],
    elapsed_seconds: float,
) -> dict[str, Any]:
    if plan.data is None or plan.data.live_chain_requests != 0:
        raise AssertionError(f"{label} did not remain on offline PriceUniverse data")
    if plan.optimized_basket.store_count > 2:
        raise AssertionError(f"{label} exceeded max_stores=2")
    rows = _basket_rows(plan.optimized_basket)
    allowed = set(memberships)
    unauthorized = [
        row
        for row in rows
        if row["membership_program"] is not None
        and MembershipProgram(row["membership_program"]) not in allowed
    ]
    if unauthorized:
        raise AssertionError(f"{label} selected unauthorized member contracts")
    savings = plan.membership_savings
    if savings is None:
        raise AssertionError(f"{label} omitted same-basket membership savings")
    basket_total = Decimal(str(plan.optimized_basket.total))
    reported_total = Decimal(str(savings.basket_total_with_memberships))
    public_total = Decimal(str(savings.same_basket_public_total))
    reported_savings = Decimal(str(savings.amount))
    if abs(reported_total - basket_total) > _MONEY_TOLERANCE:
        raise AssertionError(f"{label} membership-savings basket total drifted")
    expected_savings = max(Decimal(0), public_total - basket_total)
    if abs(reported_savings - expected_savings) > _MONEY_TOLERANCE:
        raise AssertionError(f"{label} membership-savings arithmetic is inconsistent")
    member_rows = [row for row in rows if row["membership_program"] is not None]
    if savings.member_price_lines != len(member_rows):
        raise AssertionError(f"{label} member-price line attribution drifted")
    if not memberships and (
        abs(public_total - basket_total) > _MONEY_TOLERANCE or reported_savings != 0
    ):
        raise AssertionError("public plan does not reprice to the same exact basket total")
    performance = (plan.debug_info or {}).get("performance") or {}
    timings = performance.get("timings_ms", {})
    return {
        "label": label,
        "membership_programs": [program.value for program in memberships],
        "runtime_seconds": round(elapsed_seconds, 4),
        "total": plan.optimized_basket.total,
        "price_per_portion": plan.price_per_portion,
        "stores": [group.store_name for group in plan.optimized_basket.stores],
        "recipes": [recipe.name for recipe in plan.recipes],
        "membership_programs_used": [program.value for program in plan.membership_programs_used],
        "membership_dependent_products": member_rows,
        "shopping_list": rows,
        "membership_coverage": [row.model_dump(mode="json") for row in plan.membership_coverage],
        "membership_savings": {
            **savings.model_dump(mode="json"),
            "basis": "same_exact_products_and_quantities",
            "selected_product_identities": [
                {
                    "store_id": row["store_id"],
                    "product_id": row["product_id"],
                    "packages": row["packages"],
                }
                for row in rows
            ],
            "arithmetic_verified": True,
        },
        "provider_calls": plan.data.live_chain_requests,
        "price_universe_id": plan.data.price_universe_id,
        "timings_ms": timings,
        "top_10_cost_centers": _top_timings(timings),
        "operation_counters": performance.get("operation_counters", {}),
    }


async def _normal_plan_benchmark(
    service: MealPlanService,
    sentinel: OfflineSentinelProvider,
) -> dict[str, Any]:
    all_programs = tuple(sorted(MembershipProgram, key=lambda row: row.value))
    scenarios = (
        ("NO_MEMBERSHIPS_COLD", ()),
        ("NO_MEMBERSHIPS_WARM", ()),
        ("ALL_MEMBERSHIPS_REPLAN", all_programs),
        ("NO_MEMBERSHIPS_SWITCH_WARM", ()),
        ("ALL_MEMBERSHIPS_SWITCH_WARM", all_programs),
    )

    async def execute(
        label: str,
        programs: tuple[MembershipProgram, ...],
    ) -> dict[str, Any]:
        request = PlanRequest(
            postal_code="22350",
            recipes=5,
            servings=4,
            max_stores=2,
            diversity_mode="balanced",
            diet_preference="mixed",
            membership_programs=programs,
            strategy="optimized",
            optimization_iterations=0,
            candidate_recipe_count=80,
            beam_width=30,
            debug=True,
        )
        started = perf_counter()
        plan = await service.create_plan(request)
        return _plan_summary(
            plan,
            label=label,
            memberships=programs,
            elapsed_seconds=perf_counter() - started,
        )

    original_factory = optimizer_module.create_price_provider
    optimizer_module.create_price_provider = lambda *_args, **_kwargs: sentinel
    try:
        rows = [await execute(label, programs) for label, programs in scenarios]
    finally:
        optimizer_module.create_price_provider = original_factory
    if sentinel.calls:
        raise AssertionError("provider sentinel recorded a planning call")
    universe_ids = {row["price_universe_id"] for row in rows}
    if len(universe_ids) != 1:
        raise AssertionError("normal scenarios did not use one shared PriceUniverse")
    return {
        "request": {
            "postal_code": "22350",
            "dinners": 5,
            "servings": 4,
            "diet": "mixed",
            "mode": "balanced",
            "max_stores": 2,
        },
        "runs": rows,
        "provider_calls_during_planning": 0,
        "price_universe_rebuilds": 0,
    }


async def run(city: str, output_root: Path) -> Path:
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

    # Run the production planner before diagnostic projections so "cold" is a
    # real first request against the freshly loaded process-local caches.
    normal_plan = await _normal_plan_benchmark(service, sentinel)
    pricing_date = current_pricing_date()
    base_pool = _pricing_base(prepared, service)
    fusilli = _fusilli_probe(
        prepared,
        service,
        base_pool,
        pricing_date=pricing_date,
    )
    fixed_menu = _fixed_menu(
        prepared,
        service,
        base_pool,
        pricing_date=pricing_date,
    )
    contract_audit = _contract_audit(prepared, pricing_date=pricing_date)

    report = {
        "schema_version": "membership-coverage-acceptance-v1",
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "city": city,
        "pricing_date_europe_stockholm": pricing_date.isoformat(),
        "network_policy": "fail_closed_offline_sentinel",
        "provider_calls_during_planning": sentinel.calls,
        "price_universe": {
            "id": prepared.universe.universe_id,
            "artifact_path": _safe_artifact_report_path(artifact_path),
            "artifact_size_bytes": artifact_path.stat().st_size,
            "load_seconds": round(load_seconds, 4),
            "products": prepared.universe.stats.raw_products,
            "optimizer_products": prepared.universe.stats.canonical_mappings,
            "contexts": len(prepared.universe.indexes.context_order),
            "built_at": prepared.universe.built_at.isoformat(),
            "snapshot_ids": list(prepared.universe.key.snapshot_ids),
            "contract_audit": contract_audit,
        },
        "membership_aware_search_proof": fusilli,
        "fixed_menu": fixed_menu,
        "normal_menu": normal_plan,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")
    output = output_root / f"membership-coverage-acceptance-{stamp}.json"
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
        default=Path("reports/membership-coverage"),
    )
    args = parser.parse_args()
    output = asyncio.run(run(args.city, args.output_root))
    print(output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
