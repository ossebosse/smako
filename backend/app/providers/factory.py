from __future__ import annotations

from collections.abc import Mapping

from app.config import Settings

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.source_strategy import (
    CHAIN_SOURCE_STRATEGIES,
    OWN_CATALOG,
    OWN_OFFERS,
    PRIMAT_CATALOG,
    ChainSourceStrategy,
)

from .base import GroceryPriceProvider
from .federated import FederatedGroceryPriceProvider, ProviderBinding
from .mock import MockPriceProvider
from .own import OwnGroceryPriceProvider
from .primat import PrimatPriceProvider


def _federated_provider(
    settings: Settings,
    *,
    use_member_prices: bool,
    memberships: Mapping[str, bool] | None,
    strategies: Mapping[Chain, ChainSourceStrategy],
) -> FederatedGroceryPriceProvider:
    if not settings.own_grocery_base_url:
        raise ValueError("PRICE_PROVIDER=federated requires OWN_GROCERY_BASE_URL")
    if not settings.primat_api_key and not settings.own_sources_only:
        raise ValueError(
            "PRICE_PROVIDER=federated requires PRIMAT_API_KEY unless OWN_SOURCES_ONLY=true"
        )

    # Underlying adapters must retain member observations for any explicitly
    # enabled chain. The federated boundary then applies the per-chain policy;
    # loading them is not the same as making them eligible everywhere.
    load_member_prices = use_member_prices or any((memberships or {}).values())
    own = OwnGroceryPriceProvider(
        base_url=settings.own_grocery_base_url,
        # Federation has one eligibility clock across every provider. Keeping
        # a stricter, legacy OWN-only value here would make a 60-hour snapshot
        # fail inside the adapter even when the configured federated policy is
        # 72 hours. PRICE_PROVIDER=own retains OWN_GROCERY_MAX_AGE_HOURS below.
        max_age_hours=settings.max_price_age_hours,
        # Federation has an explicit OFFERS binding and its resolver never
        # admits that channel to basket contexts. Enabling the diagnostic
        # fetch path here therefore cannot promote OFFERS_ONLY to a catalog.
        include_offers_only=True,
        use_member_prices=load_member_prices,
    )
    own_catalog_chains = frozenset(
        chain
        for chain, strategy in strategies.items()
        if OWN_CATALOG in strategy.configured_catalog_sources
    )
    own_offer_chains = frozenset(
        chain
        for chain, strategy in strategies.items()
        if strategy.offer_source == OWN_OFFERS
    )
    bindings: list[ProviderBinding] = []
    offer_bindings: list[ProviderBinding] = []
    if own_catalog_chains:
        bindings.append(
            ProviderBinding(
                source=OWN_CATALOG,
                provider=own,
                chains=own_catalog_chains,
            )
        )
    if own_offer_chains:
        offer_bindings.append(
            ProviderBinding(
                source=OWN_OFFERS,
                provider=own,
                chains=own_offer_chains,
            )
        )

    if settings.primat_api_key:
        primat = PrimatPriceProvider(
            api_key=settings.primat_api_key,
            base_url=settings.primat_base_url,
            use_member_prices=load_member_prices,
        )
        primat_chains = frozenset(
            chain
            for chain, strategy in strategies.items()
            if PRIMAT_CATALOG in strategy.configured_catalog_sources
        )
        if primat_chains:
            bindings.append(
                ProviderBinding(
                    source=PRIMAT_CATALOG,
                    provider=primat,
                    chains=primat_chains,
                    # The licensed broad source is the declared basket source
                    # for these chain/context rows. Primat's public store shape
                    # does not always carry our internal CoverageLevel enum.
                    coverage_by_chain={
                        chain: CoverageLevel.FULL_CATALOG for chain in primat_chains
                    },
                )
            )

    return FederatedGroceryPriceProvider(
        bindings,
        offer_bindings=offer_bindings,
        strategies=strategies,
        allow_fallback=settings.allow_provider_fallback,
        own_sources_only=settings.own_sources_only,
        max_price_age_hours=settings.max_price_age_hours,
        use_member_prices=use_member_prices,
        memberships=memberships,
    )


def create_price_provider(
    settings: Settings,
    *,
    use_member_prices: bool = False,
    memberships: Mapping[str, bool] | None = None,
    source_strategies: Mapping[Chain, ChainSourceStrategy] | None = None,
) -> GroceryPriceProvider:
    """Create one provider boundary; fallback remains explicit and auditable."""

    mode = settings.price_provider
    if mode not in {"auto", "federated", "mock", "own", "primat"}:
        raise ValueError("PRICE_PROVIDER must be auto, federated, mock, own or primat")
    if settings.own_sources_only and mode == "primat":
        raise ValueError("OWN_SOURCES_ONLY=true excludes PRICE_PROVIDER=primat")
    if settings.own_sources_only and mode == "auto" and not settings.own_grocery_base_url:
        raise ValueError("OWN_SOURCES_ONLY=true requires OWN_GROCERY_BASE_URL")
    if mode == "auto" and (
        (settings.own_grocery_base_url and settings.primat_api_key)
        or (settings.own_grocery_base_url and settings.own_sources_only)
    ):
        mode = "federated"
    if mode == "federated":
        strategies = dict(source_strategies or CHAIN_SOURCE_STRATEGIES)
        return _federated_provider(
            settings,
            use_member_prices=use_member_prices,
            memberships=memberships,
            strategies=strategies,
        )
    if mode == "own":
        if not settings.own_grocery_base_url:
            raise ValueError("PRICE_PROVIDER=own requires OWN_GROCERY_BASE_URL")
        return OwnGroceryPriceProvider(
            base_url=settings.own_grocery_base_url,
            max_age_hours=settings.own_grocery_max_age_hours,
            include_offers_only=settings.own_grocery_include_offers_only,
            use_member_prices=use_member_prices,
        )
    if mode == "mock" or (mode == "auto" and not settings.primat_api_key):
        return MockPriceProvider(use_member_prices=use_member_prices)
    if not settings.primat_api_key:
        raise ValueError("PRICE_PROVIDER=primat requires PRIMAT_API_KEY")
    return PrimatPriceProvider(
        api_key=settings.primat_api_key,
        base_url=settings.primat_base_url,
        use_member_prices=use_member_prices,
    )
