from __future__ import annotations

from math import ceil
from typing import Any

from pydantic import BaseModel, ConfigDict


class CityGrossSchemaError(ValueError):
    """The public City Gross response no longer satisfies its observed contract."""


class CityGrossCatalogPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: tuple[dict[str, Any], ...]
    total_count: int
    page_size: int
    current_page: int
    total_pages: int


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CityGrossSchemaError(f"City Gross {field} must be an explicit integer")
    return value


def validated_catalog_page(
    payload: object,
    *,
    requested_skip: int,
    requested_take: int,
    expected_store_id: str,
) -> CityGrossCatalogPage:
    """Validate one Loop54 page without filling any missing traversal evidence."""

    if not isinstance(payload, dict):
        raise CityGrossSchemaError("City Gross catalog page must be an object")
    if "items" not in payload:
        raise CityGrossSchemaError("City Gross catalog page items field is missing")
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raise CityGrossSchemaError("City Gross catalog page items must be a list")
    if requested_skip < 0 or requested_take <= 0:
        raise ValueError("requested skip/take are invalid")

    total_count = _integer(payload.get("totalCount"), "totalCount")
    page_size = _integer(payload.get("pageSize"), "pageSize")
    current_page = _integer(payload.get("currentPage"), "currentPage")
    total_pages = _integer(payload.get("totalPages"), "totalPages")
    if total_count < 0 or page_size <= 0 or current_page < 0 or total_pages < 0:
        raise CityGrossSchemaError("City Gross pagination bounds are invalid")
    if page_size != requested_take:
        raise CityGrossSchemaError("City Gross did not return the requested page size")
    if requested_skip != current_page * page_size:
        raise CityGrossSchemaError("City Gross did not return the requested offset/page")
    expected_pages = ceil(total_count / page_size) if total_count else 0
    if total_pages != expected_pages:
        raise CityGrossSchemaError("City Gross totalPages is inconsistent with totalCount")
    if total_count == 0:
        if current_page != 0 or raw_items:
            raise CityGrossSchemaError("City Gross empty catalog pagination is inconsistent")
    elif current_page >= total_pages:
        raise CityGrossSchemaError("City Gross currentPage exceeds totalPages")

    expected_rows = min(page_size, max(total_count - requested_skip, 0))
    if len(raw_items) != expected_rows:
        raise CityGrossSchemaError(
            "City Gross page row count is inconsistent with pagination metadata"
        )

    items: list[dict[str, Any]] = []
    for position, row in enumerate(raw_items):
        if not isinstance(row, dict):
            raise CityGrossSchemaError(f"City Gross item {position} must be an object")
        product_id = str(row.get("id") or "").strip()
        if not product_id:
            raise CityGrossSchemaError(f"City Gross item {position} lacks product identity")
        store_details = row.get("productStoreDetails")
        if not isinstance(store_details, dict):
            raise CityGrossSchemaError(f"City Gross item {product_id} lacks productStoreDetails")
        actual_store_id = str(store_details.get("id") or "").strip()
        if actual_store_id != expected_store_id:
            raise CityGrossSchemaError(f"City Gross item {product_id} has another price context")
        items.append(row)

    return CityGrossCatalogPage(
        items=tuple(items),
        total_count=total_count,
        page_size=page_size,
        current_page=current_page,
        total_pages=total_pages,
    )
