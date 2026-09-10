import pytest

from grocery_data.app.domain import Chain, CoverageLevel
from grocery_data.app.domain.source_strategy import (
    OWN_CATALOG,
    PRIMAT_CATALOG,
    ChainSourceStrategy,
    ContextSourceStrategy,
    SourceProvider,
    SourceRole,
    SourceUnavailableError,
    source_strategy_for,
)


def test_willys_uses_own_and_never_silently_falls_back() -> None:
    strategy = source_strategy_for(Chain.WILLYS)

    selected = strategy.select_catalog_source({OWN_CATALOG, PRIMAT_CATALOG})
    assert selected.source.provider == SourceProvider.OWN
    assert selected.role == SourceRole.PRIMARY
    assert selected.fallback_used is False

    with pytest.raises(SourceUnavailableError, match="explicit opt-in"):
        strategy.select_catalog_source({PRIMAT_CATALOG})

    fallback = strategy.select_catalog_source({PRIMAT_CATALOG}, allow_fallback=True)
    assert fallback.source.provider == SourceProvider.PRIMAT
    assert fallback.role == SourceRole.FALLBACK
    assert fallback.fallback_used is True


def test_ica_source_roles_are_explicit() -> None:
    strategy = source_strategy_for(Chain.ICA)

    assert strategy.primary_source == PRIMAT_CATALOG
    assert strategy.context_overrides == ()
    assert (
        source_strategy_for(Chain.ICA, context_id="context:ica:not-yet-verified").primary_source
        == PRIMAT_CATALOG
    )
    assert strategy.offer_source is not None
    assert strategy.offer_source.provider == SourceProvider.OWN
    assert strategy.offer_source.channel.value == "offers"
    assert strategy.enrichment_source is not None
    assert strategy.enrichment_source.channel.value == "registry"


def test_context_override_is_exact_and_does_not_change_chain_default() -> None:
    strategy = ChainSourceStrategy(
        chain=Chain.ICA,
        primary_source=PRIMAT_CATALOG,
        context_overrides=(
            ContextSourceStrategy(
                context_id="context:ica:gunnesbo",
                primary_source=OWN_CATALOG,
                secondary_sources=(PRIMAT_CATALOG,),
            ),
        ),
    )

    assert strategy.primary_source == PRIMAT_CATALOG
    assert strategy.for_context("context:ica:gunnesbo").primary_source == OWN_CATALOG
    assert strategy.for_context("context:ica:gunnesbo ").primary_source == OWN_CATALOG
    assert strategy.for_context("context:ica:gunnesb").primary_source == PRIMAT_CATALOG
    assert strategy.configured_catalog_sources == (PRIMAT_CATALOG, OWN_CATALOG)


def test_context_override_rejects_duplicate_logical_context_identity() -> None:
    override = ContextSourceStrategy(
        context_id="context:ica:gunnesbo",
        primary_source=OWN_CATALOG,
    )
    with pytest.raises(ValueError, match="unique context IDs"):
        ChainSourceStrategy(
            chain=Chain.ICA,
            primary_source=PRIMAT_CATALOG,
            context_overrides=(override, override),
        )


def test_coop_uses_verified_own_catalog_with_explicit_primat_fallback() -> None:
    strategy = source_strategy_for(Chain.COOP)

    assert strategy.primary_source == OWN_CATALOG
    assert strategy.secondary_sources == (PRIMAT_CATALOG,)
    assert strategy.offer_source is not None
    assert strategy.offer_source.provider == SourceProvider.OWN
    assert strategy.offer_source.channel.value == "offers"

    selected = strategy.select_catalog_source({OWN_CATALOG, PRIMAT_CATALOG})
    assert selected.source == OWN_CATALOG
    assert selected.fallback_used is False

    with pytest.raises(SourceUnavailableError, match="explicit opt-in"):
        strategy.select_catalog_source({PRIMAT_CATALOG})

    fallback = strategy.select_catalog_source({PRIMAT_CATALOG}, allow_fallback=True)
    assert fallback.source == PRIMAT_CATALOG
    assert fallback.fallback_used is True

    with pytest.raises(ValueError, match="verified full catalog"):
        strategy.with_verified_own_catalog(CoverageLevel.PARTIAL_CATALOG)

    verified = strategy.with_verified_own_catalog(CoverageLevel.FULL_CATALOG)
    assert verified.primary_source == OWN_CATALOG
    assert verified.secondary_sources[0] == PRIMAT_CATALOG
    assert source_strategy_for(Chain.COOP).primary_source == OWN_CATALOG


def test_citygross_uses_verified_own_and_never_silently_falls_back() -> None:
    strategy = source_strategy_for(Chain.CITY_GROSS)

    assert strategy.primary_source == OWN_CATALOG
    assert strategy.secondary_sources == (PRIMAT_CATALOG,)
    assert strategy.offer_source is not None
    assert strategy.offer_source.provider is SourceProvider.OWN

    selected = strategy.select_catalog_source({OWN_CATALOG, PRIMAT_CATALOG})
    assert selected.source == OWN_CATALOG
    assert selected.role is SourceRole.PRIMARY
    assert selected.fallback_used is False

    with pytest.raises(SourceUnavailableError, match="explicit opt-in"):
        strategy.select_catalog_source({PRIMAT_CATALOG})

    fallback = strategy.select_catalog_source({PRIMAT_CATALOG}, allow_fallback=True)
    assert fallback.source == PRIMAT_CATALOG
    assert fallback.role is SourceRole.FALLBACK
    assert fallback.fallback_used is True


def test_hemkop_uses_verified_own_and_never_silently_falls_back() -> None:
    strategy = source_strategy_for(Chain.HEMKOP)

    assert strategy.primary_source == OWN_CATALOG
    assert strategy.secondary_sources == (PRIMAT_CATALOG,)
    assert strategy.offer_source is not None
    assert strategy.offer_source.provider is SourceProvider.OWN

    selected = strategy.select_catalog_source({OWN_CATALOG, PRIMAT_CATALOG})
    assert selected.source == OWN_CATALOG
    assert selected.role is SourceRole.PRIMARY
    assert selected.fallback_used is False

    with pytest.raises(SourceUnavailableError, match="explicit opt-in"):
        strategy.select_catalog_source({PRIMAT_CATALOG})

    fallback = strategy.select_catalog_source({PRIMAT_CATALOG}, allow_fallback=True)
    assert fallback.source == PRIMAT_CATALOG
    assert fallback.role is SourceRole.FALLBACK
    assert fallback.fallback_used is True


def test_lidl_uses_licensed_catalog_and_separate_own_offers() -> None:
    strategy = source_strategy_for(Chain.LIDL)

    assert strategy.primary_source == PRIMAT_CATALOG
    assert strategy.secondary_sources == ()
    assert strategy.offer_source is not None
    assert strategy.offer_source.provider is SourceProvider.OWN
    assert strategy.offer_source.channel.value == "offers"
    selected = strategy.select_catalog_source({PRIMAT_CATALOG})
    assert selected.source == PRIMAT_CATALOG
    assert selected.role is SourceRole.PRIMARY
    assert selected.fallback_used is False
    with pytest.raises(SourceUnavailableError, match="not configured"):
        strategy.select_catalog_source({OWN_CATALOG}, requested_source=OWN_CATALOG)
