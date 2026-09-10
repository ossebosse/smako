from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .provenance import SourceProvenance


class StorePickupOption(BaseModel):
    """A physical destination for one shared online price context."""

    model_config = ConfigDict(frozen=True)

    physical_store_id: str = Field(min_length=1)
    physical_store_external_id: str | None = Field(default=None, min_length=1)
    pickup_point_external_id: str | None = Field(default=None, min_length=1)
    name: str = Field(min_length=1)
    address: str | None = None
    postal_code: str | None = Field(default=None, min_length=5)
    city: str | None = Field(default=None, min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    relation_type: Literal["pickup_context"] = "pickup_context"
    confidence: str = Field(min_length=1)

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        digits = "".join(character for character in str(value) if character.isdigit())
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        return digits


class StoreServiceArea(BaseModel):
    """Evidence explaining why a non-physical context is eligible in an area."""

    model_config = ConfigDict(frozen=True)

    cities: tuple[str, ...] = ()
    postal_codes: tuple[str, ...] = ()
    availability_basis: Literal["verified_pickup_context"]
    requested_postal_code: str | None = Field(default=None, min_length=5)

    @field_validator("postal_codes", mode="before")
    @classmethod
    def normalize_postal_codes(cls, value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, str) or not isinstance(value, (list, tuple)):
            raise TypeError("postal_codes must be a sequence")
        normalized = {
            "".join(character for character in str(item) if character.isdigit())
            for item in value
        }
        if "" in normalized or any(len(item) != 5 for item in normalized):
            raise ValueError("postal_codes must contain exactly five digits")
        return tuple(sorted(normalized))

    @field_validator("requested_postal_code", mode="before")
    @classmethod
    def normalize_requested_postal_code(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        digits = "".join(character for character in str(value) if character.isdigit())
        if len(digits) != 5:
            raise ValueError("requested_postal_code must contain exactly five digits")
        return digits


class Store(BaseModel):
    """A grocery price context returned by a provider.

    Most rows are physical stores, but an explicitly labelled online store or
    fulfillment context is equally valid and must not impersonate one.
    """

    model_config = ConfigDict(frozen=True)

    store_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    chain: str = Field(min_length=1)
    city: str = Field(min_length=1)
    postal_code: str | None = Field(default=None, min_length=5)
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    distance_km: float | None = Field(default=None, ge=0)
    tier: str | None = None
    price_context_type: str | None = Field(default=None, min_length=1)
    physical_store_external_id: str | None = Field(default=None, min_length=1)
    source_store_id: str | None = Field(
        default=None,
        min_length=1,
        description="Provider-native context identifier used only at the adapter boundary",
    )
    coverage: str | None = Field(default=None, min_length=1)
    confirmed_at: str | None = None
    price_semantics: Literal["online_price"] | None = None
    price_label: str | None = Field(default=None, min_length=1)
    service_area: StoreServiceArea | None = None
    pickup_options: tuple[StorePickupOption, ...] = ()
    source_provenance: SourceProvenance | None = None

    @property
    def context_id(self) -> str:
        """Stable grocery-context identity used for store-count economics."""

        return self.store_id

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        digits = "".join(character for character in str(value) if character.isdigit())
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        return digits


class GroceryContext(Store):
    """Explicit name for the unified physical/online/fulfilment context model.

    It intentionally remains a ``Store`` subtype so existing provider and
    optimiser clients continue to work without chain-specific branching.
    """
