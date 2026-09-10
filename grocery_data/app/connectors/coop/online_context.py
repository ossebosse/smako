from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    CoverageLevel,
    PriceContextType,
    StoreContextRelationType,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.domain.store import PhysicalStore, SourceStore, StoreContextLink

if TYPE_CHECKING:
    from grocery_data.app.services.store_coverage import GroceryContextEvidence


class CoopOnlineContextDefinition(BaseModel):
    """Allowlisted identity for one Coop assortment/price context.

    Coop's ``store`` request parameter identifies the online production unit,
    not a physical store. The neutral display name and lack of a physical-store
    identity are deliberate safeguards against presenting an online price as a
    shelf price.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    external_context_id: str = Field(pattern=r"^\d+$", max_length=255)
    display_name: str = Field(min_length=1, max_length=500)
    geographic_scope: str = Field(min_length=1, max_length=255)
    context_type: Literal[PriceContextType.ONLINE_FULFILLMENT] = (
        PriceContextType.ONLINE_FULFILLMENT
    )
    price_semantics: Literal["online_price"] = "online_price"
    evidence_reference: str = Field(min_length=1, max_length=2000)

    @field_validator("display_name", "geographic_scope", "evidence_reference")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Coop online context evidence text must not be blank")
        return normalized

    @property
    def grocery_context_id(self) -> str:
        return f"own:coop:{self.external_context_id}"

    def as_source_store(
        self,
        *,
        coverage: CoverageLevel = CoverageLevel.PARTIAL_CATALOG,
        raw_reference: str | None = None,
    ) -> SourceStore:
        """Project the regional context into the connector's store boundary."""

        return SourceStore(
            chain=Chain.COOP,
            external_id=self.external_context_id,
            name=self.display_name,
            online_shopping=True,
            coverage=coverage,
            price_context_type=PriceContextType.ONLINE_FULFILLMENT,
            physical_store_external_id=None,
            raw_reference=raw_reference or self.evidence_reference,
            source_fields={
                "geographic_scope": self.geographic_scope,
                "price_semantics": self.price_semantics,
            },
        )

    def as_context_evidence(
        self,
        *,
        coverage: CoverageLevel | None = None,
        basket_eligible: bool = False,
        snapshot_id: str | None = None,
        observed_at: datetime | None = None,
        local_store_id: str | None = None,
    ) -> GroceryContextEvidence:
        """Project the same identity for store coverage/federation reporting.

        Importing here keeps the connector model independent of service setup.
        Eligibility remains false unless a promoted complete snapshot is passed.
        """

        from grocery_data.app.services.store_coverage import GroceryContextEvidence

        if basket_eligible and (
            coverage is None
            or not is_complete_catalog_coverage(coverage)
            or snapshot_id is None
            or observed_at is None
        ):
            raise ValueError("basket eligibility requires a complete observed snapshot")
        return GroceryContextEvidence(
            grocery_context_id=self.grocery_context_id,
            chain=Chain.COOP,
            name=self.display_name,
            price_context_type=PriceContextType.ONLINE_FULFILLMENT,
            source_provider=SourceProvider.OWN,
            source_channel=SourceChannel.CATALOG,
            coverage=coverage,
            basket_eligible=basket_eligible,
            snapshot_id=snapshot_id,
            observed_at=observed_at,
            local_store_id=local_store_id,
        )


class CoopPickupContextEvidence(BaseModel):
    """Explicit many-to-one relation from a physical pickup point to context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    physical_store_external_id: str = Field(min_length=1, max_length=255)
    physical_store_name: str = Field(min_length=1, max_length=500)
    pickup_point_external_id: str = Field(min_length=1, max_length=255)
    online_context_external_id: str = Field(pattern=r"^\d+$", max_length=255)
    evidence_kind: Literal[
        "public_fulfillment_response",
        "manual_browser_analytics",
    ]
    evidence_reference: str = Field(min_length=1, max_length=2000)

    @field_validator(
        "physical_store_external_id",
        "physical_store_name",
        "pickup_point_external_id",
        "evidence_reference",
    )
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Coop pickup evidence text must not be blank")
        return normalized

    @model_validator(mode="after")
    def identities_are_separate(self) -> CoopPickupContextEvidence:
        if len(
            {
                self.online_context_external_id,
                self.physical_store_external_id,
                self.pickup_point_external_id,
            }
        ) != 3:
            raise ValueError("online, physical-store and pickup-point identities must be separate")
        return self

    @property
    def confidence(self) -> Confidence:
        if self.evidence_kind == "public_fulfillment_response":
            return Confidence.EXACT
        return Confidence.HIGH


class CoopOnlineContextEvidenceBundle(BaseModel):
    """Sanitized discovery evidence; never writes mappings merely by loading."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    profile: Literal["coop-online-context-evidence-v1"]
    captured_at: datetime
    contexts: tuple[CoopOnlineContextDefinition, ...] = Field(min_length=1)
    pickup_relations: tuple[CoopPickupContextEvidence, ...] = ()

    @field_validator("captured_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Coop context evidence timestamp must be timezone-aware")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_references(self) -> CoopOnlineContextEvidenceBundle:
        context_ids = [context.external_context_id for context in self.contexts]
        if len(context_ids) != len(set(context_ids)):
            raise ValueError("Coop online context IDs must be unique")
        relation_keys: set[tuple[str, str, str]] = set()
        pickup_owners: dict[str, tuple[str, str]] = {}
        contexts_by_id = {context.external_context_id: context for context in self.contexts}
        for relation in self.pickup_relations:
            context = contexts_by_id.get(relation.online_context_external_id)
            if context is None:
                raise ValueError("Coop pickup relation references an unknown online context")
            if context.display_name.casefold() == relation.physical_store_name.casefold():
                raise ValueError("online context must retain a neutral, non-physical name")
            key = (
                relation.physical_store_external_id,
                relation.pickup_point_external_id,
                relation.online_context_external_id,
            )
            if key in relation_keys:
                raise ValueError("duplicate Coop pickup relation evidence")
            relation_keys.add(key)
            owner = (
                relation.physical_store_external_id,
                relation.online_context_external_id,
            )
            previous_owner = pickup_owners.setdefault(relation.pickup_point_external_id, owner)
            if previous_owner != owner:
                raise ValueError("Coop pickup-point identity has conflicting ownership")
        return self

    @classmethod
    def from_path(cls, path: Path) -> CoopOnlineContextEvidenceBundle:
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def context(self, external_context_id: str) -> CoopOnlineContextDefinition:
        matches = [
            context
            for context in self.contexts
            if context.external_context_id == external_context_id
        ]
        if len(matches) != 1:
            raise LookupError(f"no unique Coop online context {external_context_id!r}")
        return matches[0]

    def pickup_relation(
        self,
        physical_store_external_id: str,
    ) -> CoopPickupContextEvidence:
        matches = [
            relation
            for relation in self.pickup_relations
            if relation.physical_store_external_id == physical_store_external_id
        ]
        if len(matches) != 1:
            raise LookupError(
                "no unique evidence-backed Coop pickup relation for physical store "
                f"{physical_store_external_id!r}"
            )
        return matches[0]

    def as_pickup_link(
        self,
        physical_store: PhysicalStore,
        *,
        verified_at: datetime,
        coverage: CoverageLevel | None = None,
        basket_eligible: bool = False,
        snapshot_id: str | None = None,
        observed_at: datetime | None = None,
        local_store_id: str | None = None,
    ) -> StoreContextLink:
        """Create an explicit link; absence of evidence fails instead of fuzzing."""

        if physical_store.chain is not Chain.COOP:
            raise ValueError("Coop pickup evidence cannot link another chain")
        external_identities = {
            identity
            for identity in (
                physical_store.external_store_id,
                *physical_store.external_store_aliases,
            )
            if identity is not None
        }
        candidates = [
            relation
            for relation in self.pickup_relations
            if relation.physical_store_external_id in external_identities
        ]
        if len(candidates) != 1:
            raise LookupError("physical Coop store has no unique explicit pickup evidence")
        relation = candidates[0]
        context = self.context(relation.online_context_external_id)
        if basket_eligible and (
            coverage is None
            or not is_complete_catalog_coverage(coverage)
            or snapshot_id is None
            or observed_at is None
        ):
            raise ValueError("basket eligibility requires a complete observed snapshot")
        return StoreContextLink(
            physical_store_id=physical_store.id,
            grocery_context_id=context.grocery_context_id,
            source_provider=SourceProvider.OWN,
            source_channel=SourceChannel.CATALOG,
            local_store_id=local_store_id,
            pickup_point_external_id=relation.pickup_point_external_id,
            grocery_context_name=context.display_name,
            price_context_type=PriceContextType.ONLINE_FULFILLMENT,
            coverage=coverage,
            relation_type=StoreContextRelationType.PICKUP_CONTEXT,
            confidence=relation.confidence,
            evidence=f"{relation.evidence_kind}: {relation.evidence_reference}",
            basket_eligible=basket_eligible,
            snapshot_id=snapshot_id,
            observed_at=observed_at,
            linked_at=verified_at,
            last_verified_at=verified_at,
        )


__all__ = [
    "CoopOnlineContextDefinition",
    "CoopOnlineContextEvidenceBundle",
    "CoopPickupContextEvidence",
]
