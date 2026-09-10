from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field


class IcaDiscoverySource(StrEnum):
    SSR_INITIAL_STATE = "ssr_initial_state"
    CATEGORY_PAGE = "category_page"
    SEARCH_PAGE = "search_page"
    OFFERS_PAGE = "offers_page"
    PRODUCT_DETAIL = "product_detail"
    STRUCTURED_BROWSER_RESPONSE = "structured_browser_response"


class ProductActiveState(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    NOT_SEEN_RECENTLY = "not_seen_recently"
    DISCONTINUED = "discontinued"
    UNKNOWN = "unknown"


class MetadataLevel(StrEnum):
    DISCOVERED_ID_ONLY = "discovered_id_only"
    BASIC_METADATA = "basic_metadata"
    PRICED = "priced"
    FULL_METADATA = "full_metadata"


class IcaRegistryObservation(BaseModel):
    external_product_id: str = Field(min_length=1)
    store_external_id: str = Field(min_length=1)
    source: IcaDiscoverySource
    source_page: str
    observed_at: datetime
    raw_snapshot_id: str | None = None
    name: str | None = None
    brand: str | None = None
    gtin: str | None = None
    category_path: list[str] = Field(default_factory=list)
    package_text: str | None = None
    sale_price: Decimal | None = None
    comparison_price: Decimal | None = None
    comparison_unit: str | None = None
    availability: str | None = None
    promotion: dict | None = None
    canonical_food: str | None = None
    sale_model: str | None = None
    semantic_confidence: str | None = None
    quantity_confidence: str | None = None


class BasketDataCoverage(BaseModel):
    requested_ingredients: int
    safely_priced_ingredients: int
    coverage_ratio: float
    complete_for_request: bool
    missing_ingredients: list[str] = Field(default_factory=list)
