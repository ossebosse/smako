from __future__ import annotations

import pytest
from app.config import Settings
from app.models import PlanRequest
from app.providers import FederatedGroceryPriceProvider
from app.providers.factory import create_price_provider

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.enums import DEFAULT_SOURCE_CHAINS
from grocery_data.app.domain.source_strategy import (
    CHAIN_SOURCE_STRATEGIES,
    OWN_CATALOG,
    PRIMAT_CATALOG,
    ChainSourceStrategy,
    ContextSourceStrategy,
    SourceProvider,
)


@pytest.mark.asyncio
async def test_explicit_federated_factory_wires_strategy_roles_and_flags() -> None:
    provider = create_price_provider(
        Settings(
            price_provider="federated",
            own_grocery_base_url="https://own.example",
            primat_api_key="test-key",
            allow_provider_fallback=True,
            max_price_age_hours=24,
        ),
        memberships={"hemkop": True, "ica": False},
    )
    assert isinstance(provider, FederatedGroceryPriceProvider)
    try:
        assert provider.resolver.allow_fallback is True
        assert provider.use_member_prices is False
        assert provider.resolver.own_sources_only is False
        assert provider.resolver.max_price_age_hours == 24
        by_provider = {binding.source.provider: binding for binding in provider.bindings}
        assert {Chain.WILLYS, Chain.HEMKOP, Chain.CITY_GROSS}.issubset(
            by_provider[SourceProvider.OWN].chains
        )
        assert Chain.ICA not in by_provider[SourceProvider.OWN].chains
        assert by_provider[SourceProvider.PRIMAT].chains == frozenset(DEFAULT_SOURCE_CHAINS)
        assert by_provider[SourceProvider.PRIMAT].coverage_by_chain[Chain.ICA] is (
            CoverageLevel.FULL_CATALOG
        )
        assert provider.offer_bindings
        assert all(binding.provider.use_member_prices for binding in provider.bindings)
        assert all(
            binding.source.provider is SourceProvider.OWN for binding in provider.offer_bindings
        )
        assert provider.offer_bindings[0].chains == frozenset(DEFAULT_SOURCE_CHAINS)
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_factory_wires_inactive_exact_context_sources_without_changing_chain_default() -> None:
    strategies = dict(CHAIN_SOURCE_STRATEGIES)
    strategies[Chain.ICA] = ChainSourceStrategy(
        chain=Chain.ICA,
        primary_source=PRIMAT_CATALOG,
        context_overrides=(
            ContextSourceStrategy(
                context_id="context:ica:verified-own",
                primary_source=OWN_CATALOG,
                secondary_sources=(PRIMAT_CATALOG,),
            ),
        ),
    )
    provider = create_price_provider(
        Settings(
            price_provider="federated",
            own_grocery_base_url="https://own.example",
            primat_api_key="test-key",
        ),
        source_strategies=strategies,
    )
    assert isinstance(provider, FederatedGroceryPriceProvider)
    try:
        own_binding = next(
            binding
            for binding in provider.bindings
            if binding.source.provider is SourceProvider.OWN
        )
        assert Chain.ICA in own_binding.chains
        assert provider.resolver.strategies[Chain.ICA].primary_source == PRIMAT_CATALOG
        assert (
            provider.resolver.strategies[Chain.ICA]
            .context_override_for("context:ica:verified-own")
            .primary_source
            == OWN_CATALOG
        )
    finally:
        await provider.aclose()


@pytest.mark.asyncio
async def test_auto_selects_federation_when_both_real_provider_boundaries_exist() -> None:
    provider = create_price_provider(
        Settings(
            price_provider="auto",
            own_grocery_base_url="https://own.example",
            primat_api_key="test-key",
        )
    )
    assert isinstance(provider, FederatedGroceryPriceProvider)
    await provider.aclose()


@pytest.mark.asyncio
async def test_federation_uses_one_configured_72_hour_freshness_policy() -> None:
    provider = create_price_provider(
        Settings(
            price_provider="federated",
            own_grocery_base_url="https://own.example",
            own_grocery_max_age_hours=12,
            max_price_age_hours=72,
            own_sources_only=True,
        )
    )
    assert isinstance(provider, FederatedGroceryPriceProvider)
    try:
        own_binding = next(
            binding
            for binding in provider.bindings
            if binding.source.provider is SourceProvider.OWN
        )
        assert provider.resolver.max_price_age_hours == 72
        assert own_binding.provider.max_age_hours == 72
    finally:
        await provider.aclose()

    own_only = create_price_provider(
        Settings(
            price_provider="own",
            own_grocery_base_url="https://own.example",
            own_grocery_max_age_hours=12,
            max_price_age_hours=72,
        )
    )
    try:
        assert own_only.max_age_hours == 12
    finally:
        await own_only.aclose()


@pytest.mark.asyncio
async def test_own_sources_only_is_an_explicit_federated_mode_without_primat() -> None:
    provider = create_price_provider(
        Settings(
            price_provider="federated",
            own_grocery_base_url="https://own.example",
            own_sources_only=True,
        )
    )
    assert isinstance(provider, FederatedGroceryPriceProvider)
    try:
        assert provider.resolver.own_sources_only is True
        assert {binding.source.provider for binding in provider.bindings} == {SourceProvider.OWN}
    finally:
        await provider.aclose()


def test_federated_mode_fails_visibly_when_required_boundary_is_missing() -> None:
    with pytest.raises(ValueError, match="OWN_GROCERY_BASE_URL"):
        create_price_provider(Settings(price_provider="federated", primat_api_key="test-key"))
    with pytest.raises(ValueError, match="PRIMAT_API_KEY"):
        create_price_provider(
            Settings(
                price_provider="federated",
                own_grocery_base_url="https://own.example",
            )
        )


def test_own_sources_only_never_silently_selects_external_provider() -> None:
    with pytest.raises(ValueError, match="OWN_GROCERY_BASE_URL"):
        create_price_provider(Settings(price_provider="auto", own_sources_only=True))
    with pytest.raises(ValueError, match="excludes"):
        create_price_provider(
            Settings(
                price_provider="primat",
                primat_api_key="test-key",
                own_sources_only=True,
            )
        )


def test_plan_request_memberships_are_chain_specific_and_backward_compatible() -> None:
    legacy = PlanRequest(use_member_prices=True)
    explicit = PlanRequest(
        use_member_prices=False,
        memberships={"hemkop": True, "ica": False},
    )

    assert legacy.memberships == {}
    assert explicit.memberships == {"hemkop": True, "ica": False}
    with pytest.raises(ValueError):
        PlanRequest(memberships={"unknown-chain": True})  # type: ignore[dict-item]


def test_federation_policy_flags_are_explicit_environment_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALLOW_PROVIDER_FALLBACK", "true")
    monkeypatch.setenv("OWN_SOURCES_ONLY", "true")
    monkeypatch.setenv("MAX_PRICE_AGE_HOURS", "36")

    settings = Settings.from_env()

    assert settings.allow_provider_fallback is True
    assert settings.own_sources_only is True
    assert settings.max_price_age_hours == 36
