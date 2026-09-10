from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.domain.enums import (
    Chain,
    CoverageLevel,
    is_complete_catalog_coverage,
)


class SourceProvider(StrEnum):
    """A provider boundary, independent from the role it has for one chain."""

    OWN = "own"
    PRIMAT = "primat"
    LICENSED = "licensed"


class SourceChannel(StrEnum):
    CATALOG = "catalog"
    OFFERS = "offers"
    REGISTRY = "registry"


class SourceRole(StrEnum):
    BASKET = "basket"
    PRIMARY = "primary"
    FALLBACK = "fallback"
    OFFERS = "offers"
    ENRICHMENT = "enrichment"


class SourceRef(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: SourceProvider
    channel: SourceChannel = SourceChannel.CATALOG


class SourceSelection(BaseModel):
    """An auditable source choice made by explicit orchestration."""

    model_config = ConfigDict(frozen=True)

    chain: Chain
    source: SourceRef
    role: SourceRole
    fallback_used: bool = False
    reason: str


class SourceUnavailableError(RuntimeError):
    pass


class ContextSourceStrategy(BaseModel):
    """Exact source policy for one normalized grocery context.

    ``context_id`` is matched only against :attr:`Store.store_id` at the
    federated boundary.  Names, addresses and provider-native IDs are
    deliberately not considered here: an upstream verified mapping must first
    normalize every provider row to the same stable ``GroceryContext.id``.
    """

    model_config = ConfigDict(frozen=True)

    context_id: str = Field(min_length=1, max_length=255)
    primary_source: SourceRef
    secondary_sources: tuple[SourceRef, ...] = ()

    @field_validator("context_id")
    @classmethod
    def normalize_context_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("context_id must not be blank")
        return normalized

    @model_validator(mode="after")
    def unique_catalog_sources(self) -> ContextSourceStrategy:
        sources = (self.primary_source, *self.secondary_sources)
        if any(source.channel != SourceChannel.CATALOG for source in sources):
            raise ValueError("context catalog sources must use the catalog channel")
        if len(set(sources)) != len(sources):
            raise ValueError("context catalog sources must be unique")
        return self


class ChainSourceStrategy(BaseModel):
    """Declare source roles without silently switching between providers.

    Merely listing a secondary source does not enable it. Consumers must pass
    ``allow_fallback=True`` or request that exact source explicitly.
    """

    model_config = ConfigDict(frozen=True)

    chain: Chain
    primary_source: SourceRef
    secondary_sources: tuple[SourceRef, ...] = ()
    offer_source: SourceRef | None = None
    enrichment_source: SourceRef | None = None
    context_overrides: tuple[ContextSourceStrategy, ...] = ()

    @property
    def basket_primary(self) -> SourceRef:
        """Role-oriented alias retained beside the original persisted name."""

        return self.primary_source

    @property
    def basket_fallbacks(self) -> tuple[SourceRef, ...]:
        return self.secondary_sources

    @property
    def offers_primary(self) -> SourceRef | None:
        return self.offer_source

    @property
    def enrichment(self) -> SourceRef | None:
        return self.enrichment_source

    @model_validator(mode="after")
    def unique_catalog_sources(self) -> ChainSourceStrategy:
        sources = (self.primary_source, *self.secondary_sources)
        if any(source.channel != SourceChannel.CATALOG for source in sources):
            raise ValueError("primary and secondary sources must use the catalog channel")
        if len(set(sources)) != len(sources):
            raise ValueError("catalog sources must be unique")
        if self.offer_source is not None and self.offer_source.channel != SourceChannel.OFFERS:
            raise ValueError("offer_source must use the offers channel")
        if (
            self.enrichment_source is not None
            and self.enrichment_source.channel != SourceChannel.REGISTRY
        ):
            raise ValueError("enrichment_source must use the registry channel")
        context_ids = [override.context_id for override in self.context_overrides]
        if len(set(context_ids)) != len(context_ids):
            raise ValueError("context source overrides must have unique context IDs")
        return self

    @property
    def configured_catalog_sources(self) -> tuple[SourceRef, ...]:
        """All sources that factory wiring may need for this chain.

        Merely including a source here does not make it eligible.  Selection
        still happens per context and fallback remains opt-in.
        """

        ordered = [self.primary_source, *self.secondary_sources]
        for override in self.context_overrides:
            ordered.extend((override.primary_source, *override.secondary_sources))
        return tuple(dict.fromkeys(ordered))

    def context_override_for(self, context_id: str) -> ContextSourceStrategy | None:
        """Return the exact override for ``context_id``; never fuzzy-match."""

        normalized = context_id.strip()
        return next(
            (override for override in self.context_overrides if override.context_id == normalized),
            None,
        )

    def for_context(self, context_id: str) -> ChainSourceStrategy:
        """Materialize the catalog policy for one exact grocery context."""

        override = self.context_override_for(context_id)
        if override is None:
            return self.model_copy(update={"context_overrides": ()})
        return self.model_copy(
            update={
                "primary_source": override.primary_source,
                "secondary_sources": override.secondary_sources,
                "context_overrides": (),
            }
        )

    def select_catalog_source(
        self,
        available_sources: set[SourceRef],
        *,
        requested_source: SourceRef | None = None,
        allow_fallback: bool = False,
    ) -> SourceSelection:
        """Select a catalog source and fail visibly when policy disallows it."""

        configured = (self.primary_source, *self.secondary_sources)
        if requested_source is not None:
            if requested_source not in configured:
                raise SourceUnavailableError(
                    f"{requested_source.provider.value} is not configured for {self.chain.value}"
                )
            if requested_source not in available_sources:
                raise SourceUnavailableError(
                    f"requested source {requested_source.provider.value} is unavailable "
                    f"for {self.chain.value}"
                )
            fallback = requested_source != self.primary_source
            return SourceSelection(
                chain=self.chain,
                source=requested_source,
                role=SourceRole.FALLBACK if fallback else SourceRole.PRIMARY,
                fallback_used=fallback,
                reason="explicit source request",
            )

        if self.primary_source in available_sources:
            return SourceSelection(
                chain=self.chain,
                source=self.primary_source,
                role=SourceRole.PRIMARY,
                reason="configured primary source is available",
            )

        available_secondary = next(
            (source for source in self.secondary_sources if source in available_sources),
            None,
        )
        if available_secondary is not None and not allow_fallback:
            raise SourceUnavailableError(
                f"primary source {self.primary_source.provider.value} is unavailable for "
                f"{self.chain.value}; fallback requires explicit opt-in"
            )
        if available_secondary is not None:
            return SourceSelection(
                chain=self.chain,
                source=available_secondary,
                role=SourceRole.FALLBACK,
                fallback_used=True,
                reason="explicit fallback opt-in",
            )
        raise SourceUnavailableError(
            f"no configured catalog source is available for {self.chain.value}"
        )

    def with_verified_own_catalog(self, coverage: CoverageLevel) -> ChainSourceStrategy:
        """Promote OWN only after complete catalog coverage has been accepted."""

        if not is_complete_catalog_coverage(coverage):
            raise ValueError("OWN can become primary only for verified full catalog coverage")
        own = SourceRef(provider=SourceProvider.OWN)
        if self.primary_source == own:
            return self
        secondaries = tuple(dict.fromkeys((self.primary_source, *self.secondary_sources)).keys())
        secondaries = tuple(source for source in secondaries if source != own)
        return self.model_copy(update={"primary_source": own, "secondary_sources": secondaries})


OWN_CATALOG = SourceRef(provider=SourceProvider.OWN)
PRIMAT_CATALOG = SourceRef(provider=SourceProvider.PRIMAT)
OWN_OFFERS = SourceRef(provider=SourceProvider.OWN, channel=SourceChannel.OFFERS)
OWN_REGISTRY = SourceRef(provider=SourceProvider.OWN, channel=SourceChannel.REGISTRY)


CHAIN_SOURCE_STRATEGIES: dict[Chain, ChainSourceStrategy] = {
    Chain.WILLYS: ChainSourceStrategy(
        chain=Chain.WILLYS,
        primary_source=OWN_CATALOG,
        secondary_sources=(PRIMAT_CATALOG,),
        offer_source=OWN_OFFERS,
    ),
    Chain.ICA: ChainSourceStrategy(
        chain=Chain.ICA,
        primary_source=PRIMAT_CATALOG,
        offer_source=OWN_OFFERS,
        enrichment_source=OWN_REGISTRY,
    ),
    # Coop OWN is the accepted complete catalogue for the independently priced
    # regional online-fulfillment context 730400.  Physical-store offers remain
    # a separate OWN channel: a pickup relation never turns the online price
    # into a claimed shelf price.  Primat remains visible only as an explicit
    # operator-selected fallback.
    Chain.COOP: ChainSourceStrategy(
        chain=Chain.COOP,
        primary_source=OWN_CATALOG,
        secondary_sources=(PRIMAT_CATALOG,),
        offer_source=OWN_OFFERS,
    ),
    # City Gross OWN is complete for the explicitly verified Hyllie online
    # store context. Primat is listed only as an explicit fallback: selection
    # never switches to it unless callers opt in to fallback behavior.
    Chain.CITY_GROSS: ChainSourceStrategy(
        chain=Chain.CITY_GROSS,
        primary_source=OWN_CATALOG,
        secondary_sources=(PRIMAT_CATALOG,),
        offer_source=OWN_OFFERS,
    ),
    # Hemköp OWN is the accepted complete online catalogue for an explicitly
    # activated store context. Primat remains visible only as an operator-
    # selected fallback; catalogue promotions are the OWN offers channel.
    Chain.HEMKOP: ChainSourceStrategy(
        chain=Chain.HEMKOP,
        primary_source=OWN_CATALOG,
        secondary_sources=(PRIMAT_CATALOG,),
        offer_source=OWN_OFFERS,
    ),
    # Lidl's own verified public surface contains current/upcoming published
    # products and offers only. It is therefore never a basket catalog; the
    # licensed broad source remains primary while OWN is an explicit offer
    # channel with its own regional context and provenance.
    Chain.LIDL: ChainSourceStrategy(
        chain=Chain.LIDL,
        primary_source=PRIMAT_CATALOG,
        offer_source=OWN_OFFERS,
    ),
}


def source_strategy_for(
    chain: Chain,
    *,
    context_id: str | None = None,
) -> ChainSourceStrategy:
    try:
        strategy = CHAIN_SOURCE_STRATEGIES[chain]
    except KeyError as exc:
        raise SourceUnavailableError(f"no source strategy is configured for {chain.value}") from exc
    return strategy.for_context(context_id) if context_id is not None else strategy
