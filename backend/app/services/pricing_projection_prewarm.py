"""Process-start preparation of the immutable pricing semantics projection.

The serialized PriceUniverse deliberately remains independent of deployment
policy.  The active process does, however, use one stable
``EconomicIngredientSelector`` policy for every request.  Preparing that
price-independent semantic view immediately after activation moves the
otherwise request-cold work into process startup without creating a second
universe or evaluating any user eligibility.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date
from time import perf_counter
from typing import Literal

from app.config import Settings
from app.services.economic_ingredient_selector import EconomicIngredientSelector
from app.services.meal_plan_optimizer import MealPlanService
from app.services.performance_trace import (
    increment_performance_counter,
    performance_span,
)
from app.services.price_universe_runtime import (
    GLOBAL_PREPARED_PRICE_UNIVERSES,
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
)
from app.services.user_pricing import (
    current_pricing_date,
    prepare_economic_pool_for_pricing,
    project_economic_pool,
)

from grocery_data.app.domain.promotion_pricing import UserPricingContext


@dataclass(frozen=True, slots=True)
class PricingProjectionPrewarmReport:
    """Sanitized result for one process-local projection preparation."""

    status: Literal["not_run", "miss_filled", "hit", "superseded"]
    universe_id: str | None
    selector_identity: str | None
    duration_seconds: float
    cache_entries: int
    public_projection_prepared: bool = False
    live_provider_requests: int = 0


def _selector_for_startup(settings: Settings) -> EconomicIngredientSelector:
    """Construct the exact request selector without retaining source secrets."""

    offline_settings = replace(
        settings,
        price_provider="mock",
        primat_api_key=None,
        own_grocery_base_url=None,
        openai_api_key=None,
        allow_mock_fallback=False,
    )
    return MealPlanService(offline_settings).economic_selector


def precompute_pricing_semantics(
    settings: Settings,
    prepared: PreparedPriceUniverse | None,
    *,
    manager: PreparedPriceUniverseManager = GLOBAL_PREPARED_PRICE_UNIVERSES,
    selector: EconomicIngredientSelector | None = None,
    on_date: date | None = None,
) -> PricingProjectionPrewarmReport:
    """Fill semantic and public/date projections for the active universe.

    The public view is common to every user and is therefore process data, not
    a membership-profile cache. Membership eligibility and quantity-dependent
    checkout remain request-time concerns. A concurrently activated
    replacement owns a distinct cache, so warming an older object can never
    contaminate the new active universe.
    """

    if prepared is None:
        return PricingProjectionPrewarmReport(
            status="not_run",
            universe_id=None,
            selector_identity=None,
            duration_seconds=0.0,
            cache_entries=0,
        )

    active_selector = selector or _selector_for_startup(settings)
    selector_identity = active_selector.cache_identity
    freshness_view = prepared.request_view(
        stale_age_hours=settings.max_price_age_hours,
    )
    cache_key = (
        f"pricing-semantics:{selector_identity}:"
        f"freshness:{freshness_view.cache_identity}"
    )
    target_date = on_date or current_pricing_date()
    public_context = UserPricingContext()
    public_cache_key = (
        f"{public_context.cache_identity}:{target_date.isoformat()}:"
        f"{selector_identity}:freshness:{freshness_view.cache_identity}"
    )
    before = prepared.pricing_projection_cache.stats
    started = perf_counter()
    with performance_span("pricing_semantics_startup_precompute"):
        projection_base = prepared.pricing_projection_cache.get_or_compute(
            cache_key,
            lambda: prepare_economic_pool_for_pricing(
                freshness_view.economic_pool,
                selector=active_selector,
            ),
        )
        prepared.pricing_projection_cache.get_or_compute(
            public_cache_key,
            lambda: project_economic_pool(
                projection_base,
                public_context,
                selector=active_selector,
                on_date=target_date,
            ),
        )
    duration_seconds = perf_counter() - started
    after = prepared.pricing_projection_cache.stats

    current = manager.get_active(prepared.universe.key.scope_id)
    if current is not prepared:
        status: Literal["not_run", "miss_filled", "hit", "superseded"] = (
            "superseded"
        )
        increment_performance_counter("pricing_semantics_startup_superseded")
    elif after.hits > before.hits:
        status = "hit"
        increment_performance_counter("pricing_semantics_startup_cache_hits")
    else:
        status = "miss_filled"
        increment_performance_counter("pricing_semantics_startup_cache_misses")

    return PricingProjectionPrewarmReport(
        status=status,
        universe_id=prepared.universe.universe_id,
        selector_identity=selector_identity,
        duration_seconds=duration_seconds,
        cache_entries=after.entries,
        public_projection_prepared=True,
    )


__all__ = [
    "PricingProjectionPrewarmReport",
    "precompute_pricing_semantics",
]
