from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.config import Settings
from app.models.basket import BasketVerificationStatus
from app.services.plan_prewarm import (
    BackendStandardPlanPrewarmRunner,
    prewarm_active_price_universe,
    standard_plan_prewarm_config,
)

from grocery_data.app.services.plan_prewarm import (
    PlanPrewarmStatusRegistry,
    StandardPlanPrewarmProfile,
)


class _MenuCache:
    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0

    @property
    def stats(self) -> SimpleNamespace:
        return SimpleNamespace(hits=self.hits, misses=self.misses)


class _Prepared:
    def __init__(self) -> None:
        self.universe = SimpleNamespace(
            universe_id="universe-1",
            key=SimpleNamespace(
                scope_id="city:lund",
                postal_codes=("22350",),
                membership_map={
                    "ica": False,
                    "coop": False,
                    "willys": False,
                    "hemkop": False,
                    "citygross": False,
                    "lidl": False,
                },
            ),
        )
        self.menu_search_cache = _MenuCache()

    def status(self, **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(status="fresh")


class _Manager:
    def __init__(self, prepared: _Prepared) -> None:
        self.prepared = prepared

    def get_active(self, scope_id: str):  # type: ignore[no-untyped-def]
        return self.prepared if scope_id == "city:lund" else None


class _PlanService:
    def __init__(self, prepared: _Prepared, *, fail: bool = False) -> None:
        self.prepared = prepared
        self.fail = fail
        self.keys: set[str] = set()
        self.requests = []

    async def create_plan(self, request):  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("secret provider detail")
        self.requests.append(request)
        key = request.model_dump_json()
        if key in self.keys:
            self.prepared.menu_search_cache.hits += 1
        else:
            self.keys.add(key)
            self.prepared.menu_search_cache.misses += 1
        return SimpleNamespace(
            data=SimpleNamespace(
                price_universe_id="universe-1",
                live_chain_requests=0,
            ),
            optimized_basket=SimpleNamespace(
                verification_status=BasketVerificationStatus.VERIFIED,
            ),
        )


def test_prewarm_is_operator_opt_in_by_default() -> None:
    assert Settings().price_universe_prewarm_enabled is False
    assert standard_plan_prewarm_config(Settings()).enabled is False


@pytest.mark.asyncio
async def test_backend_runner_fills_then_hits_same_process_cache_without_live_sources() -> None:
    prepared = _Prepared()
    manager = _Manager(prepared)
    service = _PlanService(prepared)
    received_settings: list[Settings] = []

    def service_factory(settings, received_manager):  # type: ignore[no-untyped-def]
        assert received_manager is manager
        received_settings.append(settings)
        return service

    runner = BackendStandardPlanPrewarmRunner(
        Settings(price_provider="federated", primat_api_key="must-not-be-used"),
        manager,  # type: ignore[arg-type]
        scope_id="city:lund",
        universe_id="universe-1",
        service_factory=service_factory,
    )
    profile = StandardPlanPrewarmProfile(mode="balanced", max_stores=2)

    cold = await runner(profile)
    warm = await runner(profile)

    assert cold.cache_outcome == "miss_filled"
    assert warm.cache_outcome == "hit"
    assert cold.live_provider_requests == warm.live_provider_requests == 0
    assert all(settings.price_provider == "mock" for settings in received_settings)
    assert all(settings.primat_api_key is None for settings in received_settings)
    assert all(settings.own_grocery_base_url is None for settings in received_settings)
    assert all(settings.openai_api_key is None for settings in received_settings)
    assert all(settings.price_universe_required for settings in received_settings)
    assert service.requests[0].model_fields_set == {
        "postal_code",
        "recipes",
        "servings",
        "max_stores",
        "use_member_prices",
        "optimization_iterations",
        "strategy",
        "candidate_recipe_count",
        "beam_width",
        "diversity_mode",
        "debug",
    }


@pytest.mark.asyncio
async def test_prewarm_failure_is_reported_but_active_universe_remains_unchanged() -> None:
    prepared = _Prepared()
    manager = _Manager(prepared)
    service = _PlanService(prepared, fail=True)
    settings = Settings(
        price_universe_prewarm_enabled=True,
        price_universe_prewarm_modes=("balanced",),
        price_universe_prewarm_max_stores=(2,),
    )
    registry = PlanPrewarmStatusRegistry()

    report = await prewarm_active_price_universe(
        settings,
        manager=manager,  # type: ignore[arg-type]
        status_registry=registry,
        service_factory=lambda _settings, _manager: service,
    )

    assert report.status == "failed"
    assert report.profiles_failed == 1
    assert report.items[0].error_type == "RuntimeError"
    assert report.universe_remained_active is True
    assert manager.get_active("city:lund") is prepared
    assert "secret provider" not in report.model_dump_json()
    assert registry.get("city:lund") == report
