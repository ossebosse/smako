"""Safe boundary for future retailer-authorized personal offers.

No implementation in this module accepts passwords or performs retailer
login. A concrete provider may only be added for an approved OAuth/OIDC,
partner-API or equivalent authorization flow. Shared PriceUniverse builds do
not import this module and therefore cannot ingest user-specific contracts.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator

from grocery_data.app.domain import Chain
from grocery_data.app.domain.promotion_pricing import (
    PriceContract,
    PromotionEligibility,
)


class RetailerConnectionStatus(StrEnum):
    NOT_IMPLEMENTED = "not_implemented"
    PENDING_AUTHORIZATION = "pending_authorization"
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ERROR = "error"


class RetailerAccountConnection(BaseModel):
    """Non-secret metadata for an approved future authorization connection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connection_id: str = Field(min_length=1, max_length=255)
    owner_reference: str = Field(
        min_length=1,
        max_length=255,
        description="Opaque application user/session reference; never a retailer login.",
    )
    chain: Chain
    provider: str = Field(min_length=1, max_length=100)
    status: RetailerConnectionStatus = RetailerConnectionStatus.NOT_IMPLEMENTED
    scopes: tuple[str, ...] = ()
    created_at: datetime
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def normalize_timestamps(self) -> RetailerAccountConnection:
        for field_name in ("created_at", "expires_at"):
            value = getattr(self, field_name)
            if value is None:
                continue
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
            object.__setattr__(self, field_name, value.astimezone(UTC))
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        return self


class PersonalOfferOverlay(BaseModel):
    """Per-user contracts that are never serialized into the shared universe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: str = Field(min_length=1, max_length=255)
    contracts: tuple[PriceContract, ...] = ()

    @model_validator(mode="after")
    def require_personal_contracts(self) -> PersonalOfferOverlay:
        if any(
            contract.eligibility is not PromotionEligibility.USER_SPECIFIC
            for contract in self.contracts
        ):
            raise ValueError("personal overlay accepts only USER_SPECIFIC contracts")
        return self


class PersonalOfferProvider(Protocol):
    """Pluggable approved-integration interface; no retailer is implemented."""

    async def get_personal_offers(
        self,
        connection: RetailerAccountConnection,
    ) -> PersonalOfferOverlay: ...

    async def get_activated_coupons(
        self,
        connection: RetailerAccountConnection,
    ) -> PersonalOfferOverlay: ...


class NoPersonalOfferProvider:
    """Explicit disabled implementation used until an approved API exists."""

    async def get_personal_offers(
        self,
        connection: RetailerAccountConnection,
    ) -> PersonalOfferOverlay:
        return PersonalOfferOverlay(
            version=f"not-implemented:{connection.chain.value}",
        )

    async def get_activated_coupons(
        self,
        connection: RetailerAccountConnection,
    ) -> PersonalOfferOverlay:
        return PersonalOfferOverlay(
            version=f"not-implemented:{connection.chain.value}",
        )


__all__ = [
    "NoPersonalOfferProvider",
    "PersonalOfferOverlay",
    "PersonalOfferProvider",
    "RetailerAccountConnection",
    "RetailerConnectionStatus",
]
