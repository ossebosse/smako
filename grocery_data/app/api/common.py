from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import case, exists, func, select
from sqlalchemy.orm import Session

from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.domain.enums import Chain, ConnectorStatus, CoverageLevel, SnapshotState
from grocery_data.app.monitoring.alerts import redact_secrets
from grocery_data.app.storage import ConnectorHealthRepository
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    ConnectorHealthModel,
    PriceObservationModel,
    SourceProductModel,
    StoreModel,
)


def decimal_number(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


def configured_max_price_age_hours() -> float:
    """Return the one process-level freshness threshold used by every API surface."""

    return GroceryDataSettings.from_env().max_price_age_hours


def _chain_value(chain: Chain | str) -> str:
    return chain.value if isinstance(chain, Chain) else str(chain)


def active_snapshots(
    session: Session,
    chain: Chain | str,
) -> list[CatalogSnapshotModel]:
    """Return every promoted scope for a chain, newest first.

    Snapshot promotion is intentionally scoped (for example Lund and Malmö may
    both be active). Consumer reads must therefore never assume one active row per
    chain.
    """

    return list(
        session.scalars(
            select(CatalogSnapshotModel)
            .where(
                CatalogSnapshotModel.chain == _chain_value(chain),
                CatalogSnapshotModel.is_active.is_(True),
            )
            .order_by(
                CatalogSnapshotModel.promoted_at.desc(),
                CatalogSnapshotModel.created_at.desc(),
                CatalogSnapshotModel.id,
            )
        )
    )


def active_snapshot(
    session: Session,
    chain: Chain | str,
    *,
    scope_key: str | None = None,
) -> CatalogSnapshotModel | None:
    chain_value = chain.value if isinstance(chain, Chain) else str(chain)
    if scope_key is None:
        health = ConnectorHealthRepository(session).get(chain_value)
        if health is not None and health.active_snapshot_id is not None:
            current = session.get(CatalogSnapshotModel, health.active_snapshot_id)
            if current is not None and current.is_active and current.chain == chain_value:
                return current

    statement = select(CatalogSnapshotModel).where(
        CatalogSnapshotModel.chain == chain_value,
        CatalogSnapshotModel.is_active.is_(True),
    )
    if scope_key is not None:
        statement = statement.where(
            func.lower(CatalogSnapshotModel.scope_key) == scope_key.casefold()
        )
    return session.scalar(
        statement.order_by(
            CatalogSnapshotModel.promoted_at.desc(),
            CatalogSnapshotModel.created_at.desc(),
            CatalogSnapshotModel.id,
        ).limit(1)
    )


def active_snapshot_for_store(
    session: Session,
    store: StoreModel,
) -> CatalogSnapshotModel | None:
    """Resolve the one active snapshot whose geographic scope owns ``store``.

    Collector scopes currently use the normalized city name. ``city:<name>`` is
    accepted as a compatibility form for early PoC snapshots. If neither form is
    present, lineage through source products is used as a conservative fallback.
    All queries are ordered and limited, so parallel active city scopes can never
    cause ``MultipleResultsFound``.
    """

    contains_store = exists(
        select(1).where(
            SourceProductModel.catalog_snapshot_id == CatalogSnapshotModel.id,
            SourceProductModel.store_id == store.id,
        )
    )
    city_scope = (store.city or "").strip().casefold()
    if city_scope:
        compatible_scopes = (city_scope, f"city:{city_scope}")
        scoped = session.scalar(
            select(CatalogSnapshotModel)
            .where(
                CatalogSnapshotModel.chain == store.chain,
                CatalogSnapshotModel.is_active.is_(True),
                func.lower(CatalogSnapshotModel.scope_key).in_(compatible_scopes),
                contains_store,
            )
            .order_by(
                case(
                    (func.lower(CatalogSnapshotModel.scope_key) == city_scope, 0),
                    else_=1,
                ),
                CatalogSnapshotModel.promoted_at.desc(),
                CatalogSnapshotModel.created_at.desc(),
                CatalogSnapshotModel.id,
            )
            .limit(1)
        )
        if scoped is not None:
            return scoped

    return session.scalar(
        select(CatalogSnapshotModel)
        .where(
            CatalogSnapshotModel.chain == store.chain,
            CatalogSnapshotModel.is_active.is_(True),
            contains_store,
        )
        .order_by(
            CatalogSnapshotModel.promoted_at.desc(),
            CatalogSnapshotModel.created_at.desc(),
            CatalogSnapshotModel.id,
        )
        .limit(1)
    )


def connector_health(session: Session, chain: Chain | str) -> ConnectorHealthModel | None:
    return ConnectorHealthRepository(session).get(chain)


def clean_metrics(raw: dict[str, Any] | None) -> dict[str, int | float]:
    """Expose only documented numeric metrics, never arbitrary stored context."""

    fields = (
        "stores_found",
        "stores_successful",
        "stores_failed",
        "products_fetched",
        "products_parsed",
        "products_quarantined",
        "products_with_price",
        "products_with_gtin",
        "products_with_package_quantity",
        "unknown_sale_model",
        "request_count",
        "http_error_count",
        "rate_limit_count",
        "runtime_ms",
    )
    result: dict[str, int | float] = {}
    source = raw or {}
    for field in fields:
        value = source.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        result[field] = value

    parsed = int(result.get("products_parsed", 0))
    quarantined = int(result.get("products_quarantined", 0))
    denominator = parsed + quarantined
    result["parse_success_rate"] = parsed / denominator if denominator else 0.0
    result["price_coverage"] = int(result.get("products_with_price", 0)) / parsed if parsed else 0.0
    result["gtin_coverage"] = int(result.get("products_with_gtin", 0)) / parsed if parsed else 0.0
    result["package_quantity_coverage"] = (
        int(result.get("products_with_package_quantity", 0)) / parsed if parsed else 0.0
    )
    result["unknown_sale_model_rate"] = (
        int(result.get("unknown_sale_model", 0)) / parsed if parsed else 0.0
    )
    return result


def _freshness(
    session: Session,
    chain: Chain | str,
    snapshot: CatalogSnapshotModel | None,
    *,
    now: datetime | None = None,
    max_age_hours: float | None = None,
) -> dict[str, Any]:
    max_age_hours = configured_max_price_age_hours() if max_age_hours is None else max_age_hours
    if max_age_hours <= 0:
        raise ValueError("max_age_hours must be greater than zero")
    chain_value = _chain_value(chain)
    health = connector_health(session, chain_value)
    observed_at = None
    if snapshot is not None:
        observed_at = session.scalar(
            select(func.min(PriceObservationModel.observed_at)).where(
                PriceObservationModel.catalog_snapshot_id == snapshot.id
            )
        )
        # A productless snapshot is never a useful catalog, but retaining the
        # collection start as a conservative provenance fallback is safer than
        # calling a newly promoted/replayed snapshot freshly observed.
        observed_at = observed_at or snapshot.created_at
    current_time = now or datetime.now(tz=UTC)
    age_hours = None
    if observed_at is not None:
        age_hours = max(0.0, (current_time - observed_at).total_seconds() / 3600)

    # ConnectorHealth is intentionally a chain-level latest-run signal in the
    # current PoC schema, while catalog snapshots are promoted independently per
    # geographic scope.  A failed Malmö run must therefore not make a healthy,
    # still-active Lund snapshot unusable (and a later successful scope must not
    # bless another scope either).  Consumer freshness follows the exact
    # promoted snapshot represented by the response; the health API exposes the
    # latest chain run separately.
    if snapshot is not None:
        status = (
            ConnectorStatus.HEALTHY.value
            if snapshot.is_active and snapshot.state == SnapshotState.PROMOTED.value
            else ConnectorStatus.UNKNOWN.value
        )
    else:
        status = ConnectorStatus.UNKNOWN.value
    is_stale = age_hours is not None and age_hours > max_age_hours
    if is_stale and status == ConnectorStatus.HEALTHY.value:
        status = ConnectorStatus.STALE.value
    coverage = (
        snapshot.coverage
        if snapshot is not None
        else health.coverage
        if health is not None
        else None
    )
    channel = "offers" if coverage == CoverageLevel.OFFERS_ONLY.value else "catalog"
    return {
        "chain": chain_value,
        "snapshot_id": snapshot.id if snapshot is not None else None,
        "scope_key": snapshot.scope_key if snapshot is not None else None,
        "observed_at": observed_at,
        "data_age_hours": round(age_hours, 3) if age_hours is not None else None,
        "connector_status": status,
        "coverage": coverage,
        "last_success_at": snapshot.promoted_at
        if snapshot is not None
        else health.last_success_at
        if health is not None
        else None,
        "is_stale": is_stale,
        "source_provider": "own",
        "source_channel": channel,
        "source_snapshot_id": snapshot.id if snapshot is not None else None,
        "source_observed_at": observed_at,
        "fallback_used": False,
        "source": {
            "provider": "own",
            "channel": channel,
            "snapshot_id": snapshot.id if snapshot is not None else None,
            "observed_at": observed_at,
            "coverage": coverage,
            "fallback_used": False,
        },
    }


def freshness_for_chain(
    session: Session,
    chain: Chain | str,
    *,
    now: datetime | None = None,
    max_age_hours: float | None = None,
) -> dict[str, Any]:
    return _freshness(
        session,
        chain,
        active_snapshot(session, chain),
        now=now,
        max_age_hours=max_age_hours,
    )


def freshness_for_snapshot(
    session: Session,
    snapshot: CatalogSnapshotModel,
    *,
    now: datetime | None = None,
    max_age_hours: float | None = None,
) -> dict[str, Any]:
    return _freshness(
        session,
        snapshot.chain,
        snapshot,
        now=now,
        max_age_hours=max_age_hours,
    )


def freshness_for_store(
    session: Session,
    store: StoreModel,
    *,
    now: datetime | None = None,
    max_age_hours: float | None = None,
) -> dict[str, Any]:
    return _freshness(
        session,
        store.chain,
        active_snapshot_for_store(session, store),
        now=now,
        max_age_hours=max_age_hours,
    )


def overall_status(statuses: list[str]) -> str:
    if ConnectorStatus.BROKEN.value in statuses:
        return ConnectorStatus.BROKEN.value
    if any(
        value in {ConnectorStatus.DEGRADED.value, ConnectorStatus.STALE.value} for value in statuses
    ):
        return ConnectorStatus.DEGRADED.value
    if ConnectorStatus.HEALTHY.value in statuses:
        return ConnectorStatus.HEALTHY.value
    return ConnectorStatus.UNKNOWN.value


def safe_warning(value: object) -> str:
    return redact_secrets(str(value))[:500]


def collection_metadata(
    session: Session,
    chains: set[str],
    *,
    snapshot_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Describe exactly the snapshots represented by a collection response."""

    snapshots: list[CatalogSnapshotModel] = []
    if snapshot_ids:
        snapshots = list(
            session.scalars(
                select(CatalogSnapshotModel)
                .where(
                    CatalogSnapshotModel.id.in_(snapshot_ids),
                    CatalogSnapshotModel.is_active.is_(True),
                )
                .order_by(
                    CatalogSnapshotModel.chain,
                    CatalogSnapshotModel.scope_key,
                    CatalogSnapshotModel.id,
                )
            )
        )
    elif chains:
        for chain in sorted(chains):
            snapshots.extend(active_snapshots(session, chain))

    freshness = [freshness_for_snapshot(session, snapshot) for snapshot in snapshots]
    represented_chains = {item["chain"] for item in freshness}
    for chain in sorted(chains - represented_chains):
        freshness.append(_freshness(session, chain, None))
    statuses = [item["connector_status"] for item in freshness]
    unique_snapshot_ids = {
        item["snapshot_id"] for item in freshness if item["snapshot_id"] is not None
    }
    single = freshness[0] if len(freshness) == 1 else None
    return {
        "snapshot_id": next(iter(unique_snapshot_ids)) if len(unique_snapshot_ids) == 1 else None,
        "observed_at": single["observed_at"] if single is not None else None,
        "data_age_hours": single["data_age_hours"] if single is not None else None,
        "connector_status": overall_status(statuses),
        "freshness": freshness,
    }
