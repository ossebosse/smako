from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from grocery_data.app.api.common import active_snapshots, freshness_for_snapshot
from grocery_data.app.api.dependencies import get_session
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.connectors import SOURCE_COVERAGE
from grocery_data.app.domain.enums import Chain, ConnectorStatus, is_complete_catalog_coverage
from grocery_data.app.domain.source_strategy import (
    SourceProvider,
    SourceRef,
    SourceUnavailableError,
    source_strategy_for,
)
from grocery_data.app.services.freshness import FreshnessPolicy, assess_freshness

router = APIRouter(prefix="/sources", tags=["sources"])
SessionDep = Annotated[Session, Depends(get_session)]


def _source_ref(value: SourceRef | None) -> dict[str, str] | None:
    if value is None:
        return None
    return {
        "provider": value.provider.value,
        "channel": value.channel.value,
    }


def _strategy_status(
    session: Session,
    chain: Chain,
    settings: GroceryDataSettings,
) -> dict[str, Any]:
    descriptor = SOURCE_COVERAGE[chain]
    try:
        strategy = source_strategy_for(chain)
    except SourceUnavailableError:
        # During connector discovery a chain may deliberately exist in the
        # enum before an accepted source strategy exists. That absence is
        # visible and fail-closed instead of being filled by an implicit source.
        return {
            "chain": chain.value,
            "own_coverage": descriptor.source_coverage.value,
            "implemented": descriptor.implemented,
            "basket_primary": None,
            "basket_fallbacks": [],
            "offers_primary": None,
            "enrichment": None,
            "selected_provider": None,
            "fallback_enabled": settings.allow_provider_fallback,
            "fallback_used": False,
            "own_sources_only": settings.own_sources_only,
            "basket_eligible": False,
            "eligibility_reason": "no accepted source strategy",
            "own_snapshots": [],
        }

    snapshot_rows = active_snapshots(session, chain)
    snapshots: list[dict[str, Any]] = []
    policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    for snapshot in snapshot_rows:
        freshness = freshness_for_snapshot(
            session,
            snapshot,
            max_age_hours=settings.max_price_age_hours,
        )
        age = freshness["data_age_hours"]
        fresh = age is not None and not freshness["is_stale"]
        coverage_eligible = is_complete_catalog_coverage(snapshot.coverage)
        healthy = freshness["connector_status"] == ConnectorStatus.HEALTHY.value
        production_freshness = assess_freshness(
            freshness["observed_at"],
            policy=policy,
            broken=freshness["connector_status"] == ConnectorStatus.BROKEN.value,
        )
        snapshots.append(
            {
                "snapshot_id": snapshot.id,
                "scope_key": snapshot.scope_key,
                "coverage": snapshot.coverage,
                "observed_at": freshness["observed_at"],
                "data_age_hours": age,
                "health": freshness["connector_status"],
                "fresh": fresh,
                "freshness_state": production_freshness.state.value,
                "freshness_warning": production_freshness.warning,
                "basket_eligible": healthy and fresh and coverage_eligible,
                "source": {
                    "provider": SourceProvider.OWN.value,
                    "channel": freshness["source_channel"],
                    "snapshot_id": snapshot.id,
                    "observed_at": freshness["observed_at"],
                    "coverage": snapshot.coverage,
                    "fallback_used": False,
                },
            }
        )

    own_eligible = any(item["basket_eligible"] for item in snapshots)
    primary = strategy.primary_source
    selected_provider: str | None = None
    eligible: bool | None
    reason: str
    if settings.own_sources_only and primary.provider is not SourceProvider.OWN:
        eligible = False
        reason = "configured primary is excluded by OWN_SOURCES_ONLY"
    elif primary.provider is SourceProvider.OWN:
        eligible = own_eligible
        if eligible:
            selected_provider = SourceProvider.OWN.value
            reason = "healthy fresh promoted complete OWN snapshot"
        else:
            reason = "OWN primary has no healthy fresh promoted basket-compatible snapshot"
    else:
        # This service owns collector state, not external-provider health. It
        # must not claim that Primat/licensed data is healthy without observing
        # the runtime provider. The federated resolver performs that check.
        eligible = None
        reason = "external provider eligibility is resolved at provider runtime"

    fallback_available = bool(strategy.secondary_sources)
    fallback_candidate = (
        strategy.secondary_sources[0].provider.value
        if fallback_available and not settings.own_sources_only
        else None
    )
    return {
        "chain": chain.value,
        "own_coverage": descriptor.source_coverage.value,
        "implemented": descriptor.implemented,
        "basket_primary": _source_ref(primary),
        "basket_fallbacks": [_source_ref(item) for item in strategy.secondary_sources],
        "offers_primary": _source_ref(strategy.offer_source),
        "enrichment": _source_ref(strategy.enrichment_source),
        "selected_provider": selected_provider,
        "fallback_enabled": settings.allow_provider_fallback,
        # Status describes configuration and current own snapshots. No actual
        # provider request occurred, therefore reporting fallback_used=true
        # here would be misleading.
        "fallback_used": False,
        "fallback_available": fallback_candidate,
        "own_sources_only": settings.own_sources_only,
        "max_price_age_hours": settings.max_price_age_hours,
        "price_age_warning_hours": settings.price_age_warning_hours,
        "basket_eligible": eligible,
        "eligibility_reason": reason,
        "own_snapshots": snapshots,
    }


@router.get("/status")
def source_status(session: SessionDep) -> dict[str, Any]:
    settings = GroceryDataSettings.from_env()
    items = [_strategy_status(session, chain, settings) for chain in Chain]
    return {
        "checked_at": datetime.now(tz=UTC),
        "own_sources_only": settings.own_sources_only,
        "allow_provider_fallback": settings.allow_provider_fallback,
        "max_price_age_hours": settings.max_price_age_hours,
        "price_age_warning_hours": settings.price_age_warning_hours,
        "items": items,
        "summary": {
            "chains": len(items),
            "own_primary_chains": sum(
                item["basket_primary"] is not None
                and item["basket_primary"]["provider"] == SourceProvider.OWN.value
                for item in items
            ),
            "external_primary_chains": sum(
                item["basket_primary"] is not None
                and item["basket_primary"]["provider"] != SourceProvider.OWN.value
                for item in items
            ),
            "own_basket_eligible_chains": sum(item["basket_eligible"] is True for item in items),
            "fallbacks_used": 0,
        },
    }


__all__ = ["router"]
