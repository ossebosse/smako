"""Consumer-safe exact-GTIN lookup from the active local PriceUniverse."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.promotion_pricing import MembershipProgram

from .product import OfferMetadata


class ProductLookupIdentity(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    name: str
    brand: str | None = None
    package_description: str | None = None
    gtin: str


class ProductLookupPrice(BaseModel):
    model_config = ConfigDict(frozen=True)

    product_id: str
    grocery_context_id: str
    physical_store_id: str | None = None
    store_display_name: str
    chain: str | None = None
    regular_price: float = Field(gt=0)
    effective_price: float = Field(gt=0)
    current_public_price: float | None = Field(default=None, gt=0)
    member_price: float | None = Field(default=None, gt=0)
    membership_program: MembershipProgram | None = None
    offers: list[OfferMetadata] = Field(default_factory=list)
    price_context_type: str | None = None
    availability_label: str = "Okänd fysisk tillgänglighet"
    source_provider: str | None = None
    source_channel: str | None = None
    source_snapshot_id: str | None = None
    source_observed_at: datetime | None = None


class ProductLookupResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    found: bool
    gtin: str
    product: ProductLookupIdentity | None = None
    identities: list[ProductLookupIdentity] = Field(default_factory=list)
    prices: list[ProductLookupPrice] = Field(default_factory=list)
    ambiguous_identity: bool = False
    price_universe_id: str | None = None
    live_provider_calls: int = 0


__all__ = ["ProductLookupIdentity", "ProductLookupPrice", "ProductLookupResponse"]
