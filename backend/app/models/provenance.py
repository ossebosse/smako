from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from grocery_data.app.domain.price_context_evidence import PriceContextEvidence


class SourceProvenance(BaseModel):
    """Consumer-safe lineage for one provider observation.

    The first four fields are the original public contract.  Federation adds
    optional, backward-compatible context fields so a selected basket row can
    always answer *which chain/context, which provider and which snapshot* it
    came from.  Provider-native store identifiers remain diagnostic metadata;
    ``store_id`` is the stable federated grocery-context identity seen by the
    optimiser.
    """

    model_config = ConfigDict(frozen=True)

    source_provider: str = Field(min_length=1)
    source_channel: str = Field(min_length=1)
    source_snapshot_id: str = Field(min_length=1)
    source_observed_at: datetime
    source_role: str | None = Field(default=None, min_length=1)
    fallback_used: bool = False
    chain: str | None = Field(default=None, min_length=1)
    store_id: str | None = Field(default=None, min_length=1)
    store_name: str | None = Field(default=None, min_length=1)
    provider_store_id: str | None = Field(default=None, min_length=1)
    price_context: str | None = Field(default=None, min_length=1)
    price_context_evidence: PriceContextEvidence | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    coverage: str | None = Field(default=None, min_length=1)
    semantic_confidence: str | None = Field(default=None, min_length=1)
    quantity_confidence: str | None = Field(default=None, min_length=1)
    # Retailer namespace, never an inferred GTIN or a cross-channel price join.
    retailer_product_id: str | None = Field(default=None, exclude_if=lambda value: value is None)
    retailer_id_namespace: str | None = Field(default=None, exclude_if=lambda value: value is None)
    retailer_identity_source_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$", exclude_if=lambda value: value is None
    )
    # Explicit retailer purchase limit, separate from discounted promotion caps.
    maximum_purchase_units: int | None = Field(
        default=None, ge=1, exclude_if=lambda value: value is None
    )
    official_product_url: str | None = Field(default=None, exclude_if=lambda value: value is None)
    quantity_limit_source_url: str | None = Field(default=None, exclude_if=lambda value: value is None)
    # Omit absent transport metadata to preserve existing immutable product hashes.
    collection_location: Literal["LOCAL_RELAY"] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )


class GlobalProductIdentity(BaseModel):
    """Optional cross-chain identity; a price always remains context-specific."""

    model_config = ConfigDict(frozen=True)

    gtin: str = Field(pattern=r"^\d{8,14}$")
