from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from grocery_data.app.api.dependencies import get_session
from grocery_data.app.config import GroceryDataSettings
from grocery_data.app.services.store_coverage import StoreCoverageAuditor, StoreCoverageReport

router = APIRouter(tags=["store-coverage"])
SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/stores/coverage", response_model=StoreCoverageReport)
def store_coverage(
    session: SessionDep,
    city: Annotated[str, Query(min_length=1, max_length=255)],
) -> StoreCoverageReport:
    """Report physical sites separately from their eligible price contexts."""

    settings = GroceryDataSettings.from_env()
    return StoreCoverageAuditor(
        session,
        max_price_age_hours=settings.max_price_age_hours,
    ).audit(city)
