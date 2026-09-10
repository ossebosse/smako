from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.api.common import (
    clean_metrics,
    freshness_for_chain,
    overall_status,
    safe_warning,
)
from grocery_data.app.api.dependencies import get_session
from grocery_data.app.api.sources import _strategy_status
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.connectors import SOURCE_COVERAGE
from grocery_data.app.domain.enums import Chain, ConnectorStatus
from grocery_data.app.monitoring import SchemaDiff
from grocery_data.app.storage import ConnectorHealthRepository
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    ParserFailureModel,
)

router = APIRouter(tags=["health"])
SessionDep = Annotated[Session, Depends(get_session)]


def _operational_status(latest_run_status: str, snapshot_status: str) -> str:
    """Combine latest-run health with the active snapshot's usability."""

    statuses = {latest_run_status, snapshot_status}
    for status in (
        ConnectorStatus.BROKEN.value,
        ConnectorStatus.DEGRADED.value,
        ConnectorStatus.STALE.value,
        ConnectorStatus.HEALTHY.value,
    ):
        if status in statuses:
            return status
    return ConnectorStatus.UNKNOWN.value


def _recent_runs(session: Session, chain: Chain, *, limit: int = 10) -> list[dict]:
    rows = session.scalars(
        select(CollectorRunModel)
        .where(CollectorRunModel.chain == chain.value)
        .order_by(CollectorRunModel.started_at.desc(), CollectorRunModel.id.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "status": row.status,
            "successful": row.successful,
            "connector_version": row.connector_version,
            "parser_version": row.parser_version,
            "normalizer_version": row.normalizer_version,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "metrics": clean_metrics(row.metrics),
            "error_summary": safe_warning(row.error_summary) if row.error_summary else None,
        }
        for row in rows
    ]


def _failure_groups(session: Session, chain: Chain, *, limit: int = 10) -> list[dict]:
    statement = (
        select(
            ParserFailureModel.error_code,
            func.count(ParserFailureModel.id).label("count"),
            func.max(ParserFailureModel.created_at).label("latest_at"),
        )
        .where(ParserFailureModel.chain == chain.value)
        .group_by(ParserFailureModel.error_code)
        .order_by(func.count(ParserFailureModel.id).desc(), ParserFailureModel.error_code)
        .limit(limit)
    )
    groups = []
    for code, count, latest_at in session.execute(statement):
        rows = session.scalars(
            select(ParserFailureModel)
            .where(
                ParserFailureModel.chain == chain.value,
                ParserFailureModel.error_code == code,
            )
            .order_by(ParserFailureModel.created_at.desc(), ParserFailureModel.id.desc())
            .limit(3)
        )
        examples = [sample for row in rows if (sample := _safe_failure_sample(row.sample))]
        groups.append(
            {
                "error_code": code,
                "count": count,
                "latest_at": latest_at,
                "examples": examples,
            }
        )
    return groups


def _safe_failure_sample(raw: object) -> dict[str, str]:
    """Return a tiny canonical allow-list, never arbitrary parser context."""

    if not isinstance(raw, dict):
        return {}
    aliases = {
        "external_product_id": ("external_product_id", "code"),
        "name": ("name",),
        "package_text": ("package_text", "productLine2"),
        "price_unit": ("price_unit", "priceUnit"),
    }
    result: dict[str, str] = {}
    for output_name, source_names in aliases.items():
        value = next((raw.get(name) for name in source_names if raw.get(name) is not None), None)
        if isinstance(value, (str, int, float, bool)):
            result[output_name] = safe_warning(value)
    return result


def _safe_schema_path(value: str) -> str:
    """Bound and redact the schema path even though it contains no source value."""

    return safe_warning(value[:300])


def _safe_schema_diff(raw: object, *, limit: int = 50) -> dict | None:
    """Expose only validated structural paths/types, never arbitrary metrics."""

    if not isinstance(raw, dict):
        return None
    try:
        schema_diff = SchemaDiff.model_validate(raw)
    except ValueError:
        return None
    if not schema_diff.has_changes:
        return None

    added = [_safe_schema_path(path) for path in schema_diff.added[:limit]]
    removed = [_safe_schema_path(path) for path in schema_diff.removed[:limit]]
    type_changed = [
        {
            "path": _safe_schema_path(change.path),
            "old_types": [kind.value for kind in change.old_types],
            "new_types": [kind.value for kind in change.new_types],
        }
        for change in schema_diff.type_changed[:limit]
    ]
    return {
        "added": added,
        "removed": removed,
        "type_changed": type_changed,
        "total_added": len(schema_diff.added),
        "total_removed": len(schema_diff.removed),
        "total_type_changed": len(schema_diff.type_changed),
        "truncated": (
            len(schema_diff.added) > limit
            or len(schema_diff.removed) > limit
            or len(schema_diff.type_changed) > limit
        ),
    }


def _latest_schema_check(session: Session, chain: Chain) -> dict | None:
    """Describe the newest candidate's persisted structural change evidence."""

    row = session.scalar(
        select(CatalogSnapshotModel)
        .where(CatalogSnapshotModel.chain == chain.value)
        .order_by(CatalogSnapshotModel.created_at.desc(), CatalogSnapshotModel.id.desc())
        .limit(1)
    )
    if row is None:
        return None
    schema_diff = _safe_schema_diff((row.metrics or {}).get("schema_diff"))
    if schema_diff is None:
        return None
    return {
        "snapshot_id": row.id,
        "scope_key": row.scope_key,
        "state": row.state,
        **schema_diff,
    }


def _connector_response(
    session: Session,
    chain: Chain,
    *,
    include_detail: bool,
) -> dict:
    descriptor = SOURCE_COVERAGE[chain]
    row = ConnectorHealthRepository(session).get(chain)
    settings = GroceryDataSettings.from_env()
    freshness = freshness_for_chain(
        session,
        chain,
        max_age_hours=settings.max_price_age_hours,
    )
    freshness["coverage"] = freshness["coverage"] or descriptor.source_coverage.value
    latest_run_status = row.status if row is not None else ConnectorStatus.UNKNOWN.value
    operational_status = _operational_status(
        latest_run_status,
        freshness["connector_status"],
    )
    response = {
        **freshness,
        # ``status`` is the user-facing worst operational state.  The two
        # contributing signals remain explicit so a stale active snapshot is
        # distinguishable from a newly broken collection run.
        "status": operational_status,
        "latest_run_status": latest_run_status,
        "implemented": descriptor.implemented,
        "acceptance_contract_passed": descriptor.acceptance_contract_passed,
        "missing_acceptance_checks": list(descriptor.missing_acceptance_checks),
        "limitation": descriptor.limitation,
        "checked_at": row.checked_at if row is not None else None,
        "metrics": clean_metrics(row.metrics if row is not None else None),
        "warnings": [safe_warning(item) for item in (row.warnings if row is not None else [])],
        "schema_fingerprint": row.schema_fingerprint if row is not None else None,
        "source_strategy": _strategy_status(
            session,
            chain,
            settings,
        ),
    }
    if include_detail:
        response["recent_runs"] = _recent_runs(session, chain)
        response["recent_errors"] = _failure_groups(session, chain)
        response["schema_diff"] = _latest_schema_check(session, chain)
    return response


@router.get("/health")
def health(session: SessionDep) -> dict:
    connectors = [_connector_response(session, chain, include_detail=False) for chain in Chain]
    known = [item for item in connectors if item["status"] != ConnectorStatus.UNKNOWN.value]
    return {
        "status": overall_status([item["status"] for item in connectors]),
        "checked_at": datetime.now(tz=UTC),
        "connectors_total": len(connectors),
        "connectors_known": len(known),
        "connectors_healthy": sum(
            item["status"] == ConnectorStatus.HEALTHY.value for item in connectors
        ),
        "connectors_degraded": sum(
            item["status"] in {ConnectorStatus.DEGRADED.value, ConnectorStatus.STALE.value}
            for item in connectors
        ),
        "connectors_broken": sum(
            item["status"] == ConnectorStatus.BROKEN.value for item in connectors
        ),
    }


@router.get("/health/connectors")
def connectors_health(session: SessionDep) -> dict:
    items = [_connector_response(session, chain, include_detail=False) for chain in Chain]
    return {
        "items": items,
        "count": len(items),
        "connector_status": overall_status([item["status"] for item in items]),
    }


@router.get("/health/connectors/{chain}")
def connector_health_detail(
    chain: Chain,
    session: SessionDep,
) -> dict:
    return _connector_response(session, chain, include_detail=True)
