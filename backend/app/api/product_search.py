"""Anonymous local product search. Saved plans and source adapters are not accessed."""

from datetime import UTC, datetime
from time import perf_counter

from app.config import get_settings
from app.services.price_universe_runtime import GLOBAL_PREPARED_PRICE_UNIVERSES
from app.services.product_search import ProductSearchRequest
from fastapi import APIRouter, HTTPException, Response

router = APIRouter(prefix="/api", tags=["product search"])


@router.post("/product-search")
def search_products(request: ProductSearchRequest, response: Response) -> dict:
    started = perf_counter()
    request = request.model_copy(update={"membership_price_policy": "all_advertised"})
    prepared = GLOBAL_PREPARED_PRICE_UNIVERSES.get_for_request(request.postal_code, {})
    if prepared is None:
        raise HTTPException(422, "Det finns inget aktiverat prisunderlag för postnumret.")
    if request.view == "unit" and request.unit is None:
        raise HTTPException(422, "Välj kg, liter eller styck för jämförbara jämförpriser.")
    settings = get_settings()
    result = prepared.product_search_index.search(
        request,
        now=datetime.now(tz=UTC),
        stale_hours=settings.max_price_age_hours,
        warning_hours=settings.price_age_warning_hours,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Server-Timing"] = f"search;dur={(perf_counter() - started) * 1000:.2f}"
    return result
