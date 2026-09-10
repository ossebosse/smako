"""Deterministic orchestration across grocery price providers.

The optimiser sees one ordinary :class:`GroceryPriceProvider`.  Source policy,
health/freshness, coverage eligibility and provider-native identifiers remain
at this boundary; no chain-specific source choice leaks into meal planning.
"""

from __future__ import annotations

import asyncio
import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from typing import Self

from app.errors import PriceProviderError
from app.models import OfferKind, Product, SaleModel, SourceProvenance, Store
from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain import Chain, CoverageLevel, is_complete_catalog_coverage
from grocery_data.app.domain.source_strategy import (
    CHAIN_SOURCE_STRATEGIES,
    ChainSourceStrategy,
    SourceChannel,
    SourceProvider,
    SourceRef,
    SourceRole,
    SourceSelection,
)

from .base import GroceryPriceProvider


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _chain(value: str) -> Chain | None:
    try:
        return Chain(value.casefold().strip())
    except ValueError:
        return None


def _coverage(value: object) -> CoverageLevel | None:
    try:
        return CoverageLevel(str(value).casefold())
    except ValueError:
        return None


def _key_text(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


class SourceResolutionDiagnostics(BaseModel):
    """Serializable explanation of one chain's catalog decision."""

    model_config = ConfigDict(frozen=True)

    chain: Chain
    context_id: str | None = None
    requested_provider: SourceProvider
    selected_provider: SourceProvider | None = None
    selected_channel: SourceChannel | None = None
    selected_role: SourceRole | None = None
    selected_snapshot_id: str | None = None
    fallback_available: bool = False
    fallback_used: bool = False
    basket_eligible: bool = False
    reason: str
    considered_stores: int = 0
    accepted_stores: int = 0
    rejected_stores: int = 0
    stale_stores: int = 0
    products_considered: dict[str, int] = Field(default_factory=dict)
    products_returned: int = 0
    rows_rejected: int = 0
    stale_rows: int = 0
    provider_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderBinding:
    """A provider plus explicit coverage/health facts for configured chains."""

    source: SourceRef
    provider: GroceryPriceProvider
    chains: frozenset[Chain]
    coverage_by_chain: Mapping[Chain, CoverageLevel] = field(default_factory=dict)
    healthy: bool = True
    observed_at: datetime | None = None
    snapshot_id: str | None = None

    def __post_init__(self) -> None:
        if not self.chains:
            raise ValueError("provider binding requires at least one chain")
        if any(chain not in self.chains for chain in self.coverage_by_chain):
            raise ValueError("coverage_by_chain contains an unbound chain")

    def coverage_for(self, chain: Chain, store: Store) -> CoverageLevel | None:
        declared = self.coverage_by_chain.get(chain)
        if declared is not None:
            return declared
        provenance = store.source_provenance
        return _coverage(
            store.coverage
            or store.tier
            or (provenance.coverage if provenance is not None else None)
        )

    def observed_for(self, store: Store) -> datetime | None:
        provenance = store.source_provenance
        return _utc(provenance.source_observed_at if provenance is not None else self.observed_at)

    def snapshot_for(self, store: Store) -> str | None:
        provenance = store.source_provenance
        return provenance.source_snapshot_id if provenance is not None else self.snapshot_id


@dataclass(frozen=True, slots=True)
class _EligibleStore:
    binding: ProviderBinding
    store: Store
    coverage: CoverageLevel
    observed_at: datetime
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class _Availability:
    chain: Chain
    source: SourceRef
    binding: ProviderBinding
    stores: tuple[_EligibleStore, ...]
    considered: int
    rejected: int
    stale: int
    reason: str

    @property
    def eligible(self) -> bool:
        return bool(self.stores)


@dataclass(frozen=True, slots=True)
class _ResolvedContext:
    selection: SourceSelection
    eligible: _EligibleStore
    public_store: Store


class SourceResolver:
    """Apply health, freshness, coverage and explicit-fallback policy."""

    def __init__(
        self,
        *,
        strategies: Mapping[Chain, ChainSourceStrategy] | None = None,
        allow_fallback: bool = False,
        own_sources_only: bool = False,
        max_price_age_hours: float = 48.0,
    ) -> None:
        if max_price_age_hours <= 0:
            raise ValueError("max_price_age_hours must be greater than zero")
        self.strategies = dict(strategies or CHAIN_SOURCE_STRATEGIES)
        self.allow_fallback = allow_fallback
        self.own_sources_only = own_sources_only
        self.max_price_age_hours = max_price_age_hours

    def availability(
        self,
        *,
        chain: Chain,
        binding: ProviderBinding,
        stores: Sequence[Store],
        now: datetime,
    ) -> _Availability:
        accepted: list[_EligibleStore] = []
        rejected = 0
        stale = 0
        if not binding.healthy:
            return _Availability(
                chain,
                binding.source,
                binding,
                (),
                len(stores),
                len(stores),
                0,
                "provider health is not healthy",
            )

        for store in stores:
            coverage = binding.coverage_for(chain, store)
            observed_at = binding.observed_for(store)
            snapshot_id = binding.snapshot_for(store)
            if coverage is None or not is_complete_catalog_coverage(coverage):
                rejected += 1
                continue
            if observed_at is None or snapshot_id is None:
                rejected += 1
                continue
            age_hours = (now - observed_at).total_seconds() / 3600
            if age_hours < -1 or age_hours > self.max_price_age_hours:
                rejected += 1
                stale += 1
                continue
            accepted.append(_EligibleStore(binding, store, coverage, observed_at, snapshot_id))

        if accepted:
            reason = "healthy, fresh and basket-compatible"
        elif stale:
            reason = "all basket-compatible contexts are stale"
        elif stores:
            reason = "contexts lack complete coverage or verifiable provenance"
        else:
            reason = "provider returned no contexts for this chain"
        return _Availability(
            chain,
            binding.source,
            binding,
            tuple(accepted),
            len(stores),
            rejected,
            stale,
            reason,
        )

    def resolve(
        self,
        chain: Chain,
        availabilities: Sequence[_Availability],
        *,
        provider_errors: Sequence[str] = (),
        strategy: ChainSourceStrategy | None = None,
        context_id: str | None = None,
    ) -> tuple[SourceSelection | None, _Availability | None, SourceResolutionDiagnostics]:
        strategy = strategy or self.strategies[chain]
        requested = strategy.primary_source
        by_source = {availability.source: availability for availability in availabilities}
        primary = by_source.get(requested)
        fallbacks = [
            by_source[source]
            for source in strategy.secondary_sources
            if source in by_source and by_source[source].eligible
        ]
        fallback_available = bool(fallbacks)

        if self.own_sources_only and requested.provider is not SourceProvider.OWN:
            reason = "primary provider excluded by OWN-only policy"
            selected = None
            chosen = None
        elif primary is not None and primary.eligible:
            selected = SourceSelection(
                chain=chain,
                source=requested,
                role=SourceRole.BASKET,
                fallback_used=False,
                reason="configured primary is healthy, fresh and basket-compatible",
            )
            chosen = primary
            reason = selected.reason
        elif fallback_available and self.allow_fallback and not self.own_sources_only:
            chosen = fallbacks[0]
            selected = SourceSelection(
                chain=chain,
                source=chosen.source,
                role=SourceRole.FALLBACK,
                fallback_used=True,
                reason="primary is ineligible; explicit fallback policy enabled",
            )
            reason = selected.reason
        else:
            selected = None
            chosen = None
            primary_reason = primary.reason if primary is not None else "primary unavailable"
            if fallback_available and not self.allow_fallback:
                reason = f"{primary_reason}; fallback available but not enabled"
            else:
                reason = primary_reason

        considered = sum(item.considered for item in availabilities)
        accepted = len(chosen.stores) if chosen is not None else 0
        diagnostic = SourceResolutionDiagnostics(
            chain=chain,
            context_id=context_id,
            requested_provider=requested.provider,
            selected_provider=selected.source.provider if selected else None,
            selected_channel=selected.source.channel if selected else None,
            selected_role=selected.role if selected else None,
            selected_snapshot_id=(
                chosen.stores[0].snapshot_id if chosen and chosen.stores else None
            ),
            fallback_available=fallback_available,
            fallback_used=bool(selected and selected.fallback_used),
            basket_eligible=selected is not None,
            reason=reason,
            considered_stores=considered,
            accepted_stores=accepted,
            rejected_stores=sum(item.rejected for item in availabilities),
            stale_stores=sum(item.stale for item in availabilities),
            provider_errors=tuple(provider_errors),
        )
        return selected, chosen, diagnostic


class FederatedGroceryPriceProvider(GroceryPriceProvider):
    """One snapshot-backed universe spanning all configured grocery chains."""

    source_name = "federated"
    attribution_text = "Verifierad prisdata från kedjespecifika OWN- och licensierade källor"
    attribution_url = None

    def __init__(
        self,
        bindings: Sequence[ProviderBinding],
        *,
        offer_bindings: Sequence[ProviderBinding] = (),
        strategies: Mapping[Chain, ChainSourceStrategy] | None = None,
        allow_fallback: bool = False,
        own_sources_only: bool = False,
        max_price_age_hours: float = 48.0,
        use_member_prices: bool = False,
        memberships: Mapping[Chain | str, bool] | None = None,
    ) -> None:
        super().__init__(use_member_prices=use_member_prices)
        self.bindings = tuple(bindings)
        self.offer_bindings = tuple(offer_bindings)
        self.resolver = SourceResolver(
            strategies=strategies,
            allow_fallback=allow_fallback,
            own_sources_only=own_sources_only,
            max_price_age_hours=max_price_age_hours,
        )
        self._contexts: dict[str, _ResolvedContext] = {}
        self._offer_contexts: dict[str, _ResolvedContext] = {}
        self._diagnostics: dict[Chain, SourceResolutionDiagnostics] = {}
        self._context_diagnostics: list[SourceResolutionDiagnostics] = []
        self._memberships = (
            {Chain(str(chain).casefold()): bool(enabled) for chain, enabled in memberships.items()}
            if memberships is not None
            else None
        )
        self._validate_bindings()

    def _validate_bindings(self) -> None:
        seen: set[tuple[Chain, SourceRef]] = set()
        for binding in (*self.bindings, *self.offer_bindings):
            for chain in binding.chains:
                key = (chain, binding.source)
                if key in seen:
                    raise ValueError(
                        f"duplicate provider binding for {chain.value}/{binding.source.provider.value}/"
                        f"{binding.source.channel.value}"
                    )
                seen.add(key)
        if any(binding.source.channel is not SourceChannel.CATALOG for binding in self.bindings):
            raise ValueError("basket provider bindings must use the catalog channel")
        if any(
            binding.source.channel is not SourceChannel.OFFERS for binding in self.offer_bindings
        ):
            raise ValueError("offer provider bindings must use the offers channel")

    @property
    def diagnostics(self) -> tuple[SourceResolutionDiagnostics, ...]:
        return tuple(self._diagnostics[chain] for chain in sorted(self._diagnostics, key=str))

    @property
    def context_diagnostics(self) -> tuple[SourceResolutionDiagnostics, ...]:
        """Per-policy diagnostics, including exact context overrides.

        The existing chain-level ``diagnostics`` contract remains stable.  A
        mixed-provider chain can additionally explain each override here
        without pretending that the whole chain selected one provider.
        """

        return tuple(
            sorted(
                self._context_diagnostics,
                key=lambda item: (item.chain.value, item.context_id or ""),
            )
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        seen: set[int] = set()
        for binding in (*self.bindings, *self.offer_bindings):
            provider = binding.provider
            if id(provider) in seen:
                continue
            seen.add(id(provider))
            close = getattr(provider, "aclose", None)
            if callable(close):
                await close()

    @staticmethod
    def _context_id(store: Store) -> str:
        chain = _chain(store.chain)
        chain_value = chain.value if chain is not None else _key_text(store.chain)
        context_type = store.price_context_type or "store"
        # Address/postcode/name are public, provider-independent facts.  They
        # avoid treating OWN and licensed observations of one logical context
        # as two stores while still keeping two same-chain stores distinct.
        location = "|".join(
            (
                _key_text(store.postal_code),
                _key_text(store.address),
                _key_text(store.name),
            )
        )
        digest = sha256(f"{chain_value}|{context_type}|{location}".encode()).hexdigest()[:16]
        return f"context:{chain_value}:{digest}"

    @staticmethod
    def _provenance(
        resolved: _ResolvedContext,
        *,
        product: Product | None = None,
    ) -> SourceProvenance:
        source = resolved.selection.source
        base = (
            product.source_provenance
            if product is not None
            else resolved.eligible.store.source_provenance
        )
        public = resolved.public_store
        native = resolved.eligible.store
        return SourceProvenance(
            source_provider=source.provider.value,
            source_channel=source.channel.value,
            source_snapshot_id=(
                base.source_snapshot_id if base is not None else resolved.eligible.snapshot_id
            ),
            source_observed_at=(
                base.source_observed_at if base is not None else resolved.eligible.observed_at
            ),
            source_role=resolved.selection.role.value,
            fallback_used=resolved.selection.fallback_used,
            chain=public.chain,
            store_id=public.store_id,
            store_name=public.name,
            provider_store_id=native.source_store_id or native.store_id,
            price_context=public.price_context_type,
            coverage=resolved.eligible.coverage.value,
            semantic_confidence=(
                product.semantic_confidence.value if product is not None else None
            ),
            quantity_confidence=(
                product.quantity_confidence.value if product is not None else None
            ),
            collection_location=base.collection_location if base is not None else None,
        )

    def _public_store(
        self,
        eligible: _EligibleStore,
        selection: SourceSelection,
    ) -> Store:
        native = eligible.store
        context_id = self._context_id(native)
        provisional = native.model_copy(
            update={
                "store_id": context_id,
                "source_store_id": native.source_store_id or native.store_id,
                "coverage": eligible.coverage.value,
            },
            deep=True,
        )
        resolved = _ResolvedContext(selection, eligible, provisional)
        return provisional.model_copy(
            update={"source_provenance": self._provenance(resolved)}, deep=True
        )

    async def _discover_binding(
        self,
        binding: ProviderBinding,
        postal_code: str,
    ) -> tuple[ProviderBinding, list[Store], str | None]:
        if self.resolver.own_sources_only and binding.source.provider is not SourceProvider.OWN:
            return binding, [], None
        try:
            stores = await binding.provider.find_stores(postal_code)
        except PriceProviderError as exc:
            return binding, [], f"{binding.source.provider.value}: {type(exc).__name__}: {exc}"
        return binding, stores, None

    @staticmethod
    def _aggregate_chain_diagnostics(
        strategy: ChainSourceStrategy,
        diagnostics: Sequence[SourceResolutionDiagnostics],
    ) -> SourceResolutionDiagnostics:
        if len(diagnostics) == 1 and diagnostics[0].context_id is None:
            return diagnostics[0]

        selected = [item for item in diagnostics if item.basket_eligible]
        providers = {item.selected_provider for item in selected if item.selected_provider}
        channels = {item.selected_channel for item in selected if item.selected_channel}
        roles = {item.selected_role for item in selected if item.selected_role}
        snapshots = {
            item.selected_snapshot_id for item in selected if item.selected_snapshot_id is not None
        }
        reasons = "; ".join(
            f"{item.context_id or 'chain-default'}: {item.reason}" for item in diagnostics
        )
        provider_errors = tuple(
            dict.fromkeys(error for item in diagnostics for error in item.provider_errors)
        )
        return SourceResolutionDiagnostics(
            chain=strategy.chain,
            requested_provider=strategy.primary_source.provider,
            selected_provider=next(iter(providers)) if len(providers) == 1 else None,
            selected_channel=next(iter(channels)) if len(channels) == 1 else None,
            selected_role=next(iter(roles)) if len(roles) == 1 else None,
            selected_snapshot_id=next(iter(snapshots)) if len(snapshots) == 1 else None,
            fallback_available=any(item.fallback_available for item in diagnostics),
            fallback_used=any(item.fallback_used for item in diagnostics),
            basket_eligible=bool(selected),
            reason=reasons,
            considered_stores=sum(item.considered_stores for item in diagnostics),
            accepted_stores=sum(item.accepted_stores for item in diagnostics),
            rejected_stores=sum(item.rejected_stores for item in diagnostics),
            stale_stores=sum(item.stale_stores for item in diagnostics),
            provider_errors=provider_errors,
        )

    async def find_stores(self, postal_code: str) -> list[Store]:
        self._contexts.clear()
        self._diagnostics.clear()
        self._context_diagnostics.clear()
        results = await asyncio.gather(
            *(self._discover_binding(binding, postal_code) for binding in self.bindings)
        )
        now = datetime.now(tz=UTC)
        stores_by_binding_chain: dict[tuple[int, Chain], list[Store]] = defaultdict(list)
        errors_by_chain: dict[Chain, list[str]] = defaultdict(list)
        for binding, stores, error in results:
            for chain in binding.chains:
                if error:
                    errors_by_chain[chain].append(error)
            for store in stores:
                chain = _chain(store.chain)
                if chain is not None and chain in binding.chains:
                    stores_by_binding_chain[(id(binding), chain)].append(store)

        public_stores: list[Store] = []
        for chain, strategy in self.resolver.strategies.items():
            override_ids = {override.context_id for override in strategy.context_overrides}
            policies = [
                (override.context_id, strategy.for_context(override.context_id))
                for override in strategy.context_overrides
            ]
            policies.append((None, strategy.model_copy(update={"context_overrides": ()})))
            chain_diagnostics: list[SourceResolutionDiagnostics] = []

            for context_id, policy in policies:
                availabilities: list[_Availability] = []
                for binding in self.bindings:
                    if chain not in binding.chains or binding.source not in (
                        policy.primary_source,
                        *policy.secondary_sources,
                    ):
                        continue
                    native_stores = stores_by_binding_chain.get((id(binding), chain), ())
                    scoped_stores = (
                        [store for store in native_stores if store.store_id == context_id]
                        if context_id is not None
                        else [
                            store for store in native_stores if store.store_id not in override_ids
                        ]
                    )
                    availabilities.append(
                        self.resolver.availability(
                            chain=chain,
                            binding=binding,
                            stores=scoped_stores,
                            now=now,
                        )
                    )

                selection, chosen, diagnostic = self.resolver.resolve(
                    chain,
                    availabilities,
                    provider_errors=errors_by_chain.get(chain, ()),
                    strategy=policy,
                    context_id=context_id,
                )
                chain_diagnostics.append(diagnostic)
                self._context_diagnostics.append(diagnostic)
                if selection is None or chosen is None:
                    continue
                for eligible in chosen.stores:
                    public = self._public_store(eligible, selection)
                    resolved = _ResolvedContext(selection, eligible, public)
                    # If duplicate source rows describe the same context, keep the
                    # nearest row deterministically. Never count providers as stores.
                    previous = self._contexts.get(public.store_id)
                    if previous is not None:
                        previous_distance = previous.public_store.distance_km
                        new_distance = public.distance_km
                        if previous_distance is not None and (
                            new_distance is None or previous_distance <= new_distance
                        ):
                            continue
                        public_stores.remove(previous.public_store)
                    self._contexts[public.store_id] = resolved
                    public_stores.append(public)

            self._diagnostics[chain] = self._aggregate_chain_diagnostics(
                strategy,
                chain_diagnostics,
            )

        if not public_stores:
            reasons = "; ".join(f"{item.chain.value}: {item.reason}" for item in self.diagnostics)
            raise PriceProviderError(f"Inga verifierade federerade butikskontexter: {reasons}")
        return sorted(
            public_stores,
            key=lambda store: (
                store.distance_km is None,
                store.distance_km if store.distance_km is not None else float("inf"),
                store.chain.casefold(),
                store.name.casefold(),
            ),
        )

    async def find_offer_stores(self, postal_code: str) -> list[Store]:
        """Discover explicit offer contexts without admitting them to baskets."""

        self._offer_contexts.clear()
        now = datetime.now(tz=UTC)
        public_stores: list[Store] = []
        for binding in self.offer_bindings:
            finder = getattr(binding.provider, "find_offer_stores", None)
            try:
                native_stores = (
                    await finder(postal_code)
                    if callable(finder)
                    else await binding.provider.find_stores(postal_code)
                )
            except PriceProviderError:
                continue
            for native in native_stores:
                chain = _chain(native.chain)
                if chain is None or chain not in binding.chains or not binding.healthy:
                    continue
                strategy = self.resolver.strategies.get(chain)
                if strategy is None or strategy.offer_source != binding.source:
                    continue
                observed_at = binding.observed_for(native)
                snapshot_id = binding.snapshot_for(native)
                if observed_at is None or snapshot_id is None:
                    continue
                age_hours = (now - observed_at).total_seconds() / 3600
                if age_hours < -1 or age_hours > self.resolver.max_price_age_hours:
                    continue
                coverage = binding.coverage_for(chain, native) or CoverageLevel.OFFERS_ONLY
                eligible = _EligibleStore(
                    binding=binding,
                    store=native,
                    coverage=coverage,
                    observed_at=observed_at,
                    snapshot_id=snapshot_id,
                )
                selection = SourceSelection(
                    chain=chain,
                    source=binding.source,
                    role=SourceRole.OFFERS,
                    reason="configured explicit offer source",
                )
                public = self._public_store(eligible, selection)
                resolved = _ResolvedContext(selection, eligible, public)
                self._offer_contexts[public.store_id] = resolved
                public_stores.append(public)
        return sorted(
            {store.store_id: store for store in public_stores}.values(),
            key=lambda store: (store.chain.casefold(), store.name.casefold()),
        )

    def _rewrite_product(
        self,
        product: Product,
        resolved: _ResolvedContext,
    ) -> Product | None:
        provenance = product.source_provenance
        observed_at = _utc(
            provenance.source_observed_at
            if provenance is not None
            else resolved.eligible.observed_at
        )
        if observed_at is None:
            return None
        age_hours = (datetime.now(tz=UTC) - observed_at).total_seconds() / 3600
        if age_hours < -1 or age_hours > self.resolver.max_price_age_hours:
            return None
        offers = list(product.offers)
        member_price = product.member_price
        # The federated provider builds one shared artifact. Member contracts
        # are retained below, but they must never drive its flattened checkout
        # fields; request-time UserPricingContext performs that projection.
        membership_enabled = False
        active_source_offers = product.active_offers()
        member_single_prices = [
            offer.price
            for offer in active_source_offers
            if offer.required_packages == 1
            and (offer.kind is OfferKind.MEMBER or offer.member_program is not None)
        ]
        if product.member_price is not None:
            member_single_prices.append(product.member_price)

        def is_member_derived(value: float | None) -> bool:
            if value is None:
                return False
            return any(abs(value - member_price) <= 0.005 for member_price in member_single_prices)

        member_effective_selected = is_member_derived(product.effective_price)
        member_sale_selected = is_member_derived(product.sale_price)
        member_piece_selected = is_member_derived(product.piece_price)
        rewritten = product.model_copy(
            update={
                "store_id": resolved.public_store.store_id,
                "store_name": resolved.public_store.name,
                "chain": resolved.public_store.chain.casefold(),
                "price_context_type": resolved.public_store.price_context_type,
                "coverage": resolved.eligible.coverage.value,
                "member_price": member_price,
                "offers": offers,
                "effective_price": product.price,
                "source_provenance": self._provenance(resolved, product=product),
            },
            deep=True,
        )
        non_fixed = rewritten.sale_model in {
            SaleModel.SOLD_BY_WEIGHT,
            SaleModel.SOLD_BY_PIECE,
            SaleModel.VARIABLE_WEIGHT_PACKAGE,
        }
        capped_single_prices = [
            offer.price
            for offer in rewritten.active_offers()
            if offer.required_packages == 1
            and offer.max_quantity is not None
            and (
                offer.kind is OfferKind.CAMPAIGN
                or offer.kind is OfferKind.MEMBER
                and membership_enabled
            )
        ]
        uncapped_single_prices = [
            offer.price
            for offer in rewritten.active_offers()
            if offer.required_packages == 1
            and offer.max_quantity is None
            and (
                offer.kind is OfferKind.CAMPAIGN
                or offer.kind is OfferKind.MEMBER
                and membership_enabled
            )
        ]

        def is_capped_single_price(value: float | None) -> bool:
            if value is None:
                return False
            matches_cap = any(abs(value - price) <= 0.005 for price in capped_single_prices)
            has_uncapped_equivalent = any(
                abs(value - price) <= 0.005 for price in uncapped_single_prices
            )
            return matches_cap and not has_uncapped_equivalent

        eligible_prices = [rewritten.price]
        # Some adapters expose a current public price without a separate
        # promotion row. Preserve that observation unless it is the member
        # price selected by a member-enabled underlying adapter or a capped
        # non-fixed campaign whose source purchase-unit cap cannot yet be
        # mapped safely to recipe quantity.
        if (membership_enabled or not member_effective_selected) and not (
            non_fixed and is_capped_single_price(product.effective_price)
        ):
            eligible_prices.append(float(product.effective_price))
        for offer in rewritten.active_offers():
            if offer.required_packages != 1:
                continue
            if (
                offer.kind is OfferKind.CAMPAIGN
                or offer.kind is OfferKind.MEMBER
                and membership_enabled
            ) and (not non_fixed or offer.max_quantity is None):
                eligible_prices.append(offer.price)
        if (
            membership_enabled
            and rewritten.member_price is not None
            and not (non_fixed and is_capped_single_price(rewritten.member_price))
        ):
            eligible_prices.append(rewritten.member_price)
        effective_price = min(eligible_prices)
        checkout_updates: dict[str, object] = {"effective_price": effective_price}

        if non_fixed:
            # Preserve ordinary/public source rate fields unless they are
            # demonstrably the disabled member price or an unenforceable
            # capped promotion.  Some adapters carry legitimate public rates
            # only in sale_price/piece_price and no normalized OfferMetadata.
            capped_sale_selected = is_capped_single_price(product.sale_price)
            if capped_sale_selected or (not membership_enabled and member_sale_selected):
                checkout_updates["sale_price"] = effective_price
                if (
                    capped_sale_selected
                    and rewritten.sale_model is SaleModel.VARIABLE_WEIGHT_PACKAGE
                ):
                    checkout_updates["sale_unit"] = None
            if is_capped_single_price(product.piece_price) or (
                not membership_enabled and member_piece_selected
            ):
                checkout_updates["piece_price"] = effective_price
            if is_capped_single_price(product.comparison_price) or (
                not membership_enabled and is_member_derived(product.comparison_price)
            ):
                checkout_updates["comparison_price"] = None
                checkout_updates["comparison_unit"] = None
        elif not membership_enabled and (member_sale_selected or member_piece_selected):
            # Underlying adapters intentionally load all member observations
            # when any chain membership is enabled. Keep even fixed-package
            # checkout metadata from exposing another chain's member-derived
            # sale/piece fields; the fixed checkout itself uses effective_price.
            public_checkout_prices = [rewritten.price]
            public_checkout_prices.extend(
                offer.price
                for offer in rewritten.active_offers()
                if offer.kind is OfferKind.CAMPAIGN
                and offer.required_packages == 1
                and (rewritten.sale_model is SaleModel.FIXED_PACKAGE or offer.max_quantity is None)
            )
            public_checkout_price = min(public_checkout_prices)
            if member_sale_selected:
                checkout_updates["sale_price"] = public_checkout_price
            if member_piece_selected:
                checkout_updates["piece_price"] = public_checkout_price
                checkout_updates["sale_price"] = public_checkout_price

        return rewritten.model_copy(update=checkout_updates, deep=True)

    @staticmethod
    def _product_key(product: Product) -> tuple[str, str]:
        return product.store_id, product.gtin or product.product_id

    def _deduplicate(self, products: Sequence[Product]) -> list[Product]:
        selected: dict[tuple[str, str], Product] = {}
        for product in products:
            key = self._product_key(product)
            current = selected.get(key)
            if current is None or (
                product.source_provenance is not None
                and current.source_provenance is not None
                and product.source_provenance.source_observed_at
                > current.source_provenance.source_observed_at
            ):
                selected[key] = product
        return sorted(
            selected.values(),
            key=lambda product: (
                product.store_name.casefold(),
                product.name.casefold(),
                product.product_id,
            ),
        )

    def _record_products(
        self,
        resolved: _ResolvedContext,
        *,
        considered: int,
        returned: int,
        rejected: int = 0,
        stale: int = 0,
        error: str | None = None,
    ) -> None:
        chain = resolved.selection.chain
        current = self._diagnostics.get(chain)
        if current is None:
            return
        by_provider = dict(current.products_considered)
        provider = resolved.selection.source.provider.value
        by_provider[provider] = by_provider.get(provider, 0) + considered
        errors = (*current.provider_errors, error) if error else current.provider_errors
        self._diagnostics[chain] = current.model_copy(
            update={
                "products_considered": by_provider,
                "products_returned": current.products_returned + returned,
                "rows_rejected": current.rows_rejected + rejected,
                "stale_rows": current.stale_rows + stale,
                "provider_errors": errors,
            }
        )

    def _resolved(self, store_id: str) -> _ResolvedContext:
        try:
            return self._contexts[store_id]
        except KeyError as exc:
            raise PriceProviderError(
                "Okänd federerad butikskontext; kör find_stores innan produktanrop"
            ) from exc

    async def search_products(self, query: str, store_ids: list[str]) -> list[Product]:
        if not query.strip() or not store_ids:
            return []
        grouped: dict[int, tuple[ProviderBinding, list[_ResolvedContext]]] = {}
        for store_id in dict.fromkeys(store_ids):
            resolved = self._resolved(store_id)
            key = id(resolved.eligible.binding)
            if key not in grouped:
                grouped[key] = (resolved.eligible.binding, [])
            grouped[key][1].append(resolved)

        products: list[Product] = []
        failures = 0
        for binding, contexts in grouped.values():
            native_ids = [context.eligible.store.store_id for context in contexts]
            by_native = {context.eligible.store.store_id: context for context in contexts}
            try:
                raw = await binding.provider.search_products(query, native_ids)
            except PriceProviderError as exc:
                failures += 1
                for context in contexts:
                    self._record_products(
                        context,
                        considered=0,
                        returned=0,
                        error=f"{type(exc).__name__}: {exc}",
                    )
                continue
            stats: dict[str, list[int]] = {native_id: [0, 0, 0] for native_id in by_native}
            unmapped = 0
            for product in raw:
                context = by_native.get(product.store_id)
                if context is None:
                    unmapped += 1
                    continue
                row_stats = stats[product.store_id]
                row_stats[0] += 1
                rewritten = self._rewrite_product(product, context)
                if rewritten is None:
                    row_stats[2] += 1
                    continue
                products.append(rewritten)
                row_stats[1] += 1
            for context in contexts:
                considered, accepted, stale = stats[context.eligible.store.store_id]
                self._record_products(
                    context,
                    considered=considered,
                    returned=accepted,
                    rejected=considered - accepted,
                    stale=stale,
                )
            if unmapped:
                self._record_products(
                    contexts[0],
                    considered=unmapped,
                    returned=0,
                    rejected=unmapped,
                )
        if failures == len(grouped) and not products:
            raise PriceProviderError("Alla valda federerade produktkällor misslyckades")
        return self._deduplicate(products)

    async def get_store_products(self, store_id: str) -> list[Product]:
        resolved = self._resolved(store_id)
        try:
            raw = await resolved.eligible.binding.provider.get_store_products(
                resolved.eligible.store.store_id
            )
        except PriceProviderError as exc:
            self._record_products(
                resolved,
                considered=0,
                returned=0,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise
        matching = [
            product for product in raw if product.store_id == resolved.eligible.store.store_id
        ]
        rewritten = [
            candidate
            for product in matching
            if (candidate := self._rewrite_product(product, resolved)) is not None
        ]
        stale = len(matching) - len(rewritten)
        self._record_products(
            resolved,
            considered=len(raw),
            returned=len(rewritten),
            rejected=len(raw) - len(rewritten),
            stale=stale,
        )
        return self._deduplicate(rewritten)

    async def get_offers(self, store_id: str) -> list[Product]:
        catalog_context = self._contexts.get(store_id)
        resolved = self._offer_contexts.get(store_id)
        if resolved is None and catalog_context is not None:
            strategy = self.resolver.strategies[catalog_context.selection.chain]
            # A same-provider catalog may expose its own promotions when no
            # distinct offer channel was configured. A configured OWN offers
            # channel must never be replaced by a licensed catalog silently.
            if strategy.offer_source is None:
                resolved = catalog_context
            else:
                offer_binding = next(
                    (
                        binding
                        for binding in self.offer_bindings
                        if binding.source == strategy.offer_source
                        and catalog_context.selection.chain in binding.chains
                        and binding.provider is catalog_context.eligible.binding.provider
                    ),
                    None,
                )
                if offer_binding is not None:
                    # The same explicit OWN adapter can serve /catalog and
                    # /offers for a full context.  Change the source channel,
                    # never its context or provider, and do not admit any
                    # offers-only store to the basket universe.
                    eligible = _EligibleStore(
                        binding=offer_binding,
                        store=catalog_context.eligible.store,
                        coverage=catalog_context.eligible.coverage,
                        observed_at=catalog_context.eligible.observed_at,
                        snapshot_id=catalog_context.eligible.snapshot_id,
                    )
                    selection = SourceSelection(
                        chain=catalog_context.selection.chain,
                        source=offer_binding.source,
                        role=SourceRole.OFFERS,
                        reason="configured offer channel on the selected provider/context",
                    )
                    resolved = _ResolvedContext(
                        selection,
                        eligible,
                        catalog_context.public_store,
                    )
        if resolved is None:
            raise PriceProviderError(
                "Konfigurerad offerkälla saknar en verifierad mappning till denna kontext"
            )
        strategy = self.resolver.strategies[resolved.selection.chain]
        configured = strategy.offer_source
        if configured is not None and resolved.eligible.binding.source != configured:
            raise PriceProviderError(
                "Konfigurerad offerkälla saknar en verifierad mappning till denna kontext"
            )
        raw = await resolved.eligible.binding.provider.get_offers(resolved.eligible.store.store_id)
        return self._deduplicate(
            [
                candidate
                for product in raw
                if product.store_id == resolved.eligible.store.store_id
                if (candidate := self._rewrite_product(product, resolved)) is not None
            ]
        )


__all__ = [
    "FederatedGroceryPriceProvider",
    "ProviderBinding",
    "SourceResolutionDiagnostics",
    "SourceResolver",
]
