from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from grocery_data.app.api.dependencies import get_session
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.services.price_context_audit import (
    PriceContextAuditor,
    PriceContextAuditReport,
)

router = APIRouter(tags=["price-contexts"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/stores/price-contexts", response_model=PriceContextAuditReport)
def audit_price_contexts(
    session: SessionDep,
    city: Annotated[str, Query(min_length=1, max_length=255)],
) -> PriceContextAuditReport:
    """Explain exactly one persisted price-context state per physical store."""

    settings = GroceryDataSettings.from_env()
    return PriceContextAuditor(
        session,
        max_price_age_hours=settings.max_price_age_hours,
    ).audit(city)


__all__ = ["router"]
