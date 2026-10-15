from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from grocery_data.app.api.dependencies import get_session
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.enums import ConnectorStatus
from grocery_data.app.services.freshness import FreshnessPolicy, FreshnessState, assess_freshness
from grocery_data.app.services.price_context_audit import PriceContextAuditor
from grocery_data.app.storage.models import ConnectorHealthModel

router = APIRouter(tags=["operations"])
SessionDep = Annotated[Session, Depends(get_session)]


def _model_or_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        return dict(dump(mode="json"))
    if isinstance(value, dict):
        return dict(value)
    raise TypeError("status must be a Pydantic model or mapping")


def _universe_scope(city: str) -> str:
    return f"city:{city.casefold().strip()}"


@router.get("/price-universe/status")
def price_universe_status(
    request: Request,
    city: Annotated[str, Query(min_length=1)] = "Lund",
    postal_code: Annotated[str, Query(pattern=r"^\d{5}$")] = "22350",
) -> dict[str, Any]:
    """Return injected active-universe state without rebuilding it in a request."""

    scope = _universe_scope(city)
    manager = getattr(request.app.state, "price_universe_manager", None)
    if manager is None:
        artifact_store = getattr(request.app.state, "price_universe_artifact_store", None)
        try:
            manifest = artifact_store.read_active(city) if artifact_store is not None else None
        except ValueError:
            return {
                "city": city.strip(),
                "scope": scope,
                "postal_code": postal_code,
                "status": "broken_manifest",
                "active": False,
                "rebuild_during_request": False,
                "live_provider_requests": 0,
            }
        if manifest is not None:
            settings = GroceryDataSettings.from_env()
            freshness = assess_freshness(
                manifest.oldest_observed_at,
                policy=FreshnessPolicy(
                    warning_age_hours=settings.price_age_warning_hours,
                    stale_age_hours=settings.max_price_age_hours,
                ),
            )
            return {
                "city": city.strip(),
                "scope": scope,
                "postal_code": postal_code,
                "status": "active",
                "active": True,
                "universe_id": manifest.universe_id,
                "built_at": manifest.built_at,
                "activated_at": manifest.activated_at,
                "snapshot_ids": manifest.snapshot_ids,
                "product_count": manifest.product_count,
                "canonical_index_count": manifest.canonical_index_count,
                "oldest_price_age_hours": freshness.age_hours,
                "freshness": freshness.state.value,
                "basket_eligible": freshness.retained_observation_usable,
                "cache_state": "persistent_active_manifest",
                "rebuild_during_request": False,
                "live_provider_requests": 0,
            }
        return {
            "city": city.strip(),
            "scope": scope,
            "postal_code": postal_code,
            "status": "inactive",
            "active": False,
            "rebuild_during_request": False,
            "live_provider_requests": 0,
        }
    status = _model_or_mapping(manager.status(scope))
    active = manager.get_active(scope)
    payload = {
        "city": city.strip(),
        "scope": scope,
        "postal_code": postal_code,
        "status": "active" if active is not None else "inactive",
        "active": active is not None,
        "rebuild_during_request": False,
        "live_provider_requests": 0,
        **status,
    }
    # Public status intentionally exposes only operational metadata. Parser
    # versions and raw hashes stay behind explicit debug tooling.
    payload.pop("raw_snapshot_hash", None)
    payload.pop("parser_version", None)
    return payload


@router.get("/operations/daily-refresh/status")
def daily_refresh_status(
    session: SessionDep,
    city: Annotated[str, Query(min_length=1)] = "Lund",
) -> dict[str, Any]:
    """Derive current area readiness solely from persisted local evidence."""

    settings = GroceryDataSettings.from_env()
    now = datetime.now(tz=UTC)
    policy = FreshnessPolicy(
        warning_age_hours=settings.price_age_warning_hours,
        stale_age_hours=settings.max_price_age_hours,
    )
    audit = PriceContextAuditor(
        session,
        max_price_age_hours=settings.max_price_age_hours,
    ).audit(city, now=now)
    health = {
        row.chain: row
        for row in session.scalars(select(ConnectorHealthModel).order_by(ConnectorHealthModel.chain))
    }
    stores = []
    for chain in audit.chains.values():
        connector = health.get(chain.chain.value)
        for store in chain.stores:
            own_broken = bool(
                store.price_source == "own"
                and connector is not None
                and connector.status == ConnectorStatus.BROKEN.value
                # Connector health is currently chain-level. Bind the signal
                # to its retained active snapshot so a failed Malmö scope
                # cannot mark an unrelated Lund context broken.
                and connector.active_snapshot_id == store.snapshot_id
            )
            freshness = assess_freshness(
                store.observed_at,
                now=now,
                policy=policy,
                broken=own_broken,
                broken_reason="latest OWN connector refresh failed; LKG retained",
            )
            stores.append(
                {
                    "physical_store_id": store.physical_store_id,
                    "chain": store.chain.value,
                    "store": store.name,
                    "price_context_state": store.state.value,
                    "price_source": store.price_source,
                    "grocery_context_id": store.grocery_context_id,
                    "snapshot_id": store.snapshot_id,
                    "observed_at": store.observed_at,
                    "age_hours": freshness.age_hours,
                    "freshness": freshness.state.value,
                    "warning": freshness.warning,
                    "basket_eligible": store.basket_eligible and freshness.retained_observation_usable,
                    "lkg_retained": own_broken and store.snapshot_id is not None,
                    "lkg_usable": own_broken and freshness.retained_observation_usable,
                    "reason": store.reason,
                }
            )

    chain_rows: dict[str, dict[str, Any]] = {}
    for chain_name, chain in audit.chains.items():
        chain_stores = [row for row in stores if row["chain"] == chain_name]
        chain_rows[chain_name] = {
            "physical_stores": chain.physical_stores,
            "fresh_full_basket_contexts": sum(
                row["basket_eligible"] and row["freshness"] == FreshnessState.FRESH.value
                for row in chain_stores
            ),
            "aging_full_basket_contexts": sum(
                row["basket_eligible"] and row["freshness"] == FreshnessState.AGING.value
                for row in chain_stores
            ),
            "stale_or_broken": sum(
                row["freshness"]
                in {FreshnessState.STALE.value, FreshnessState.BROKEN.value}
                for row in chain_stores
            ),
            "price_context_states": chain.state_counts,
            "alert": (
                "7 physical stores, 0 fresh full basket price contexts"
                if chain_name == "coop"
                and chain.physical_stores == 7
                and chain.full_basket_contexts == 0
                else None
            ),
        }

    basket_rows = [row for row in stores if row["basket_eligible"]]
    oldest_age = max(
        (float(row["age_hours"]) for row in basket_rows if row["age_hours"] is not None),
        default=None,
    )
    statuses = {row["freshness"] for row in basket_rows}
    if FreshnessState.BROKEN.value in statuses:
        area_state = FreshnessState.BROKEN
    elif FreshnessState.STALE.value in statuses:
        area_state = FreshnessState.STALE
    elif FreshnessState.AGING.value in statuses:
        area_state = FreshnessState.AGING
    elif basket_rows:
        area_state = FreshnessState.FRESH
    else:
        area_state = FreshnessState.BROKEN
    return {
        "city": city.strip(),
        "checked_at": now,
        "status": area_state.value,
        "warning_age_hours": policy.warning_age_hours,
        "stale_age_hours": policy.stale_age_hours,
        "oldest_basket_price_age_hours": oldest_age,
        "physical_stores": audit.physical_stores,
        "explained_states": audit.explained_states,
        "basket_capable": len(basket_rows),
        "chains": chain_rows,
        "stores": stores,
        "meal_generation_live_requests": 0,
        "physical_validation_required": False,
        "coop_gap_non_blocking": True,
        "future_coop_resolution_paths": [
            "Primat exposes strongly matchable full contexts",
            "official partner API",
            "manual mapping verified with strong identity evidence",
        ],
    }


__all__ = ["router"]
