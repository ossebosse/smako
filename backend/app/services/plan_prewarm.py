"""Offline standard-plan prewarming for one active prepared PriceUniverse.

The grocery-data refresh layer owns collection and atomic artifact activation.
This adapter deliberately lives in the serving application because the menu,
basket and package caches are process-local: warming them in a short-lived
collector process would have no effect on subsequent API requests.

Every run is bound to one already active universe.  It forces a local mock
provider boundary and disables OpenAI so a prewarm can neither contact a chain
nor an LLM.  The prepared universe remains the only possible price source; a
missing, stale or replaced universe fails the individual profile without
changing active state.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Protocol

from app.config import Settings
from app.models import PlanRequest, PlanResponse
from app.models.basket import BasketVerificationStatus
from app.models.diversity import DiversityMode
from app.services.meal_plan_optimizer import MealPlanService
from app.services.price_universe_runtime import (
    GLOBAL_PREPARED_PRICE_UNIVERSES,
    PreparedPriceUniverse,
    PreparedPriceUniverseManager,
)

from grocery_data.app.services.plan_prewarm import (
    GLOBAL_PLAN_PREWARM_STATUS,
    PlanPrewarmExecution,
    PlanPrewarmReport,
    PlanPrewarmStatusRegistry,
    StandardPlanPrewarmConfig,
    StandardPlanPrewarmProfile,
    prewarm_standard_plans,
)


class _PlanService(Protocol):
    async def create_plan(self, request: PlanRequest) -> PlanResponse: ...


PlanServiceFactory = Callable[
    [Settings, PreparedPriceUniverseManager],
    _PlanService,
]


def standard_plan_prewarm_config(settings: Settings) -> StandardPlanPrewarmConfig:
    """Project backend settings into the shared bounded prewarm contract."""

    return StandardPlanPrewarmConfig(
        enabled=settings.price_universe_prewarm_enabled,
        postal_code=settings.price_universe_prewarm_postal_code,
        modes=settings.price_universe_prewarm_modes,
        max_stores=settings.price_universe_prewarm_max_stores,
        recipes=settings.price_universe_prewarm_recipes,
        servings=settings.price_universe_prewarm_servings,
        candidate_recipe_count=settings.price_universe_prewarm_candidate_count,
        candidate_search_limit=settings.price_universe_prewarm_candidate_search_limit,
        beam_width=settings.price_universe_prewarm_beam_width,
    )


def _default_service_factory(
    settings: Settings,
    manager: PreparedPriceUniverseManager,
) -> MealPlanService:
    return MealPlanService(settings, price_universe_manager=manager)


class BackendStandardPlanPrewarmRunner:
    """Fill caches for deterministic profiles against one exact active universe."""

    def __init__(
        self,
        settings: Settings,
        manager: PreparedPriceUniverseManager,
        *,
        scope_id: str,
        universe_id: str,
        service_factory: PlanServiceFactory = _default_service_factory,
    ) -> None:
        self.manager = manager
        self.scope_id = scope_id
        self.universe_id = universe_id
        self.service_factory = service_factory
        # Even if production normally composes a federated provider, prewarm is
        # a closed local operation.  Mock is only an inert boundary here; the
        # strict active-universe check below remains the authoritative source.
        self.offline_settings = replace(
            settings,
            price_provider="mock",
            meal_plan_strategy="optimized",
            price_universe_required=True,
            primat_api_key=None,
            own_grocery_base_url=None,
            openai_api_key=None,
            allow_mock_fallback=False,
        )

    def _active(self) -> PreparedPriceUniverse:
        active = self.manager.get_active(self.scope_id)
        if active is None or active.universe.universe_id != self.universe_id:
            raise RuntimeError("prewarm universe is no longer active")
        status = active.status(
            warning_age_hours=self.offline_settings.price_age_warning_hours,
            stale_age_hours=self.offline_settings.max_price_age_hours,
        )
        if status.status == "stale":
            raise RuntimeError("prewarm universe is stale")
        return active

    async def __call__(self, profile: StandardPlanPrewarmProfile) -> PlanPrewarmExecution:
        active = self._active()
        if profile.postal_code not in active.universe.key.postal_codes:
            raise ValueError("prewarm postal code is outside the active universe")

        memberships = dict(active.universe.key.membership_map)
        if any(memberships.values()):
            raise ValueError(
                "standard prewarm profiles require a membership-free active universe"
            )
        request_values: dict[str, object] = {
            "postal_code": profile.postal_code,
            "recipes": profile.recipes,
            "servings": profile.servings,
            "max_stores": profile.max_stores,
            # These fields intentionally mirror the standard web request. The
            # menu cache includes Pydantic's explicit-field set in its key, so
            # adding otherwise equivalent defaults (for example memberships={})
            # would warm a different entry than the UI consumes.
            "use_member_prices": False,
            "optimization_iterations": 1,
            "strategy": "optimized",
            "candidate_recipe_count": profile.candidate_recipe_count,
            "beam_width": profile.beam_width,
            "diversity_mode": DiversityMode(profile.mode),
            "debug": False,
        }
        if profile.candidate_search_limit is not None:
            request_values["candidate_search_limit"] = profile.candidate_search_limit
        request = PlanRequest.model_validate(request_values)

        before = active.menu_search_cache.stats
        service = self.service_factory(self.offline_settings, self.manager)
        response = await service.create_plan(request)
        current = self._active()
        if current is not active:
            raise RuntimeError("active universe changed during prewarm")
        if response.data is None or response.data.price_universe_id != self.universe_id:
            raise ValueError("prewarm response did not use the requested universe")
        if response.data.live_chain_requests != 0:
            raise ValueError("prewarm response reported a live chain request")
        if (
            response.optimized_basket.verification_status
            is BasketVerificationStatus.INVALID
        ):
            raise ValueError("prewarm response failed basket verification")

        after = active.menu_search_cache.stats
        if after.hits > before.hits:
            cache_outcome = "hit"
        elif after.misses > before.misses:
            cache_outcome = "miss_filled"
        else:
            cache_outcome = "unchanged"
        return PlanPrewarmExecution(
            cache_outcome=cache_outcome,
            verified=True,
            live_provider_requests=0,
        )


async def prewarm_active_price_universe(
    settings: Settings,
    *,
    manager: PreparedPriceUniverseManager = GLOBAL_PREPARED_PRICE_UNIVERSES,
    status_registry: PlanPrewarmStatusRegistry = GLOBAL_PLAN_PREWARM_STATUS,
    service_factory: PlanServiceFactory = _default_service_factory,
) -> PlanPrewarmReport:
    """Optionally warm the serving process after its artifact was activated."""

    config = standard_plan_prewarm_config(settings)
    scope_id = f"city:{' '.join(settings.price_universe_city.casefold().split())}"
    active = manager.get_active(scope_id)
    universe_id = active.universe.universe_id if active is not None else None
    runner = (
        BackendStandardPlanPrewarmRunner(
            settings,
            manager,
            scope_id=scope_id,
            universe_id=universe_id,
            service_factory=service_factory,
        )
        if active is not None and config.enabled
        else None
    )
    report = await prewarm_standard_plans(
        universe_id=universe_id,
        activated=active is not None,
        config=config,
        runner=runner,
        is_active=lambda expected: (
            (current := manager.get_active(scope_id)) is not None
            and current.universe.universe_id == expected
        ),
    )
    status_registry.publish(scope_id, report)
    return report


__all__ = [
    "BackendStandardPlanPrewarmRunner",
    "PlanServiceFactory",
    "prewarm_active_price_universe",
    "standard_plan_prewarm_config",
]
