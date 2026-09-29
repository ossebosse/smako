from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    CoverageLevel,
    PhysicalStoreLifecycleState,
    PriceContextType,
    ProviderStoreMappingStatus,
    StoreContextRelationType,
    StoreIdentityMatchConfidence,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider


class GeographicArea(BaseModel):
    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    city: str = Field(min_length=1)
    mode: Literal["locality", "municipality"] = "locality"
    municipality_code: str | None = Field(default=None, pattern=r"^\d{4}$")
    postal_codes: tuple[str, ...] = ()
    latitude: Decimal | None = None
    longitude: Decimal | None = None

    @field_validator("city")
    @classmethod
    def normalize_city(cls, value: str) -> str:
        return value.strip()


    @model_validator(mode="after")
    def validate_municipality(self) -> GeographicArea:
        if self.mode == "municipality":
            from grocery_data.app.domain.municipality import municipality_name

            if not self.municipality_code:
                raise ValueError("municipality mode requires an official municipality code")
            if municipality_name(self.municipality_code).casefold() != self.city.casefold():
                raise ValueError("city must be the municipality's official name in municipality mode")
        elif self.municipality_code is not None:
            raise ValueError("municipality code requires explicit municipality mode")
        return self

    @property
    def area_key(self) -> str:
        return f"municipality:SE:{self.municipality_code}" if self.mode == "municipality" else self.city


class SourceScopeDescriptor(BaseModel):
    """Persisted collection ownership separated from geographic filtering.

    ``scope_key`` identifies an independently promotable snapshot/context.  It
    may therefore contain connector-neutral context components and must never
    be passed to a store parser as though it were a city.  ``geographic_area``
    retains the real area that was supplied to collection and replay.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    scope_key: str = Field(min_length=1, max_length=255)
    geographic_area: GeographicArea

    @field_validator("scope_key")
    @classmethod
    def normalize_scope_key(cls, value: str) -> str:
        return value.strip()


class SourceStore(BaseModel):
    """A store fact from one chain, before consumer-specific mapping."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    chain: Chain
    external_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    online_shopping: bool | None = None
    coverage: CoverageLevel
    price_context_type: PriceContextType | None = None
    physical_store_external_id: str | None = Field(default=None, min_length=1)
    raw_reference: str
    source_fields: dict[str, Any] = Field(default_factory=dict)

    @property
    def stable_key(self) -> str:
        return f"{self.chain.value}:{self.external_id}"


class PhysicalStore(BaseModel):
    """An official physical site, independent of every price context.

    ``id`` is the registry identity.  ``external_store_id`` is optional because
    not every official locator exposes one; callers must then supply a stable ID
    derived from exact official evidence rather than a fuzzy name match.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    id: str = Field(min_length=1, max_length=64)
    chain: Chain
    external_store_id: str | None = Field(default=None, min_length=1, max_length=255)
    external_store_aliases: tuple[str, ...] = ()
    name: str = Field(min_length=1, max_length=500)
    address: str | None = Field(default=None, max_length=500)
    postal_code: str | None = None
    city: str | None = Field(default=None, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    official_source: str = Field(min_length=1, max_length=2000)
    discovered_at: datetime
    last_seen_at: datetime
    active: bool = True
    lifecycle_state: PhysicalStoreLifecycleState = PhysicalStoreLifecycleState.ACTIVE
    not_seen_at: datetime | None = None

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        digits = "".join(character for character in str(value) if character.isdigit())
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        return digits

    @field_validator("city", "address", mode="before")
    @classmethod
    def trim_optional_text(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        return str(value).strip()

    @field_validator("external_store_aliases", mode="before")
    @classmethod
    def normalize_external_store_aliases(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise TypeError("external_store_aliases must be a closed list of store IDs")
        normalized = tuple(str(item).strip() for item in value)
        if any(not item or len(item) > 255 for item in normalized):
            raise ValueError("external store aliases must be 1..255 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("external store aliases must be unique")
        return normalized

    @field_validator("discovered_at", "last_seen_at", "not_seen_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("physical-store timestamps must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> PhysicalStore:
        if (
            self.external_store_id is not None
            and self.external_store_id in self.external_store_aliases
        ):
            raise ValueError("primary external store ID cannot also be an alias")
        if self.last_seen_at < self.discovered_at:
            raise ValueError("last_seen_at cannot precede discovered_at")
        if self.lifecycle_state == PhysicalStoreLifecycleState.ACTIVE:
            if not self.active or self.not_seen_at is not None:
                raise ValueError("active physical stores cannot have NOT_SEEN state")
        elif self.active or self.not_seen_at is None:
            raise ValueError("NOT_SEEN stores must be inactive and retain not_seen_at")
        return self


class StoreContextLink(BaseModel):
    """Many-to-many link from a physical site to a federated price context.

    External providers need not fabricate a row in the local ``stores`` table.
    Their stable federated context ID remains in ``grocery_context_id`` while
    ``local_store_id`` is populated only for a real local context row.
    """

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    physical_store_id: str = Field(min_length=1, max_length=64)
    grocery_context_id: str = Field(min_length=1, max_length=255)
    source_provider: SourceProvider
    source_channel: SourceChannel = SourceChannel.CATALOG
    local_store_id: str | None = Field(default=None, min_length=1, max_length=32)
    pickup_point_external_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description=(
            "Provider-native pickup destination identity. This is relation metadata "
            "and must never be used as the grocery price-context identity."
        ),
    )
    grocery_context_name: str | None = Field(default=None, max_length=500)
    price_context_type: PriceContextType | None = None
    coverage: CoverageLevel | None = None
    relation_type: StoreContextRelationType
    confidence: Confidence
    evidence: str | None = Field(default=None, max_length=2000)
    basket_eligible: bool = False
    offers_only: bool = False
    snapshot_id: str | None = Field(default=None, max_length=255)
    observed_at: datetime | None = None
    linked_at: datetime
    last_verified_at: datetime
    active: bool = True

    @field_validator("observed_at", "linked_at", "last_verified_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("store-context timestamps must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_eligibility(self) -> StoreContextLink:
        if self.last_verified_at < self.linked_at:
            raise ValueError("last_verified_at cannot precede linked_at")
        if self.coverage == CoverageLevel.OFFERS_ONLY and self.basket_eligible:
            raise ValueError("offers-only context cannot be basket eligible")
        if self.offers_only and self.basket_eligible:
            raise ValueError("offers-only context cannot be basket eligible")
        if self.local_store_id is not None and self.source_provider != SourceProvider.OWN:
            raise ValueError("only OWN contexts may reference the local stores table")
        if (
            self.pickup_point_external_id is not None
            and self.relation_type != StoreContextRelationType.PICKUP_CONTEXT
        ):
            raise ValueError("pickup-point identity requires a PICKUP_CONTEXT relation")
        return self


class ProviderStoreIdentityMapping(BaseModel):
    """Current verified/LKG provider mapping or an explicit unresolved state."""

    model_config = ConfigDict(frozen=True, allow_inf_nan=False)

    physical_store_id: str = Field(min_length=1, max_length=64)
    provider: SourceProvider
    provider_context_id: str | None = Field(default=None, min_length=1, max_length=255)
    provider_store_id: str | None = Field(default=None, min_length=1, max_length=255)
    confidence: StoreIdentityMatchConfidence
    status: ProviderStoreMappingStatus
    evidence: str | None = Field(default=None, max_length=2000)
    verified_identity_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    observed_identity_fingerprint: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
    )
    candidate_context_id: str | None = Field(default=None, min_length=1, max_length=255)
    verified_at: datetime | None = None
    last_checked_at: datetime
    drift_detected_at: datetime | None = None
    active: bool = True

    @field_validator("verified_at", "last_checked_at", "drift_detected_at")
    @classmethod
    def require_mapping_timestamp(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("provider-store mapping timestamps must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def validate_mapping_state(self) -> ProviderStoreIdentityMapping:
        strong = {
            StoreIdentityMatchConfidence.EXACT_ID,
            StoreIdentityMatchConfidence.EXACT_ADDRESS,
            StoreIdentityMatchConfidence.EXACT_NAME_AND_POSTAL,
            StoreIdentityMatchConfidence.STRONG_GEO,
        }
        if self.status == ProviderStoreMappingStatus.VERIFIED:
            if (
                self.provider_context_id is None
                or self.provider_store_id is None
                or self.verified_identity_fingerprint is None
                or self.observed_identity_fingerprint
                != self.verified_identity_fingerprint
                or self.verified_at is None
                or self.confidence not in strong
                or self.candidate_context_id is not None
                or self.drift_detected_at is not None
            ):
                raise ValueError("verified provider mapping requires current strong identity")
        elif self.status == ProviderStoreMappingStatus.UNRESOLVED:
            if (
                self.provider_context_id is not None
                or self.verified_identity_fingerprint is not None
                or self.verified_at is not None
                or self.drift_detected_at is not None
                or self.confidence in strong
            ):
                raise ValueError("unresolved provider mapping cannot claim verified identity")
        elif (
            self.provider_context_id is None
            or self.provider_store_id is None
            or self.verified_identity_fingerprint is None
            or self.verified_at is None
            or self.observed_identity_fingerprint is None
            or self.candidate_context_id is None
            or self.drift_detected_at is None
        ):
            raise ValueError("mapping drift must retain LKG and observed candidate identity")
        if self.verified_at is not None and self.last_checked_at < self.verified_at:
            raise ValueError("last_checked_at cannot precede verified_at")
        return self
