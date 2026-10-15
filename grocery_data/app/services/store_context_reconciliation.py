from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    ConnectorStatus,
    CoverageLevel,
    PriceContextType,
    SnapshotState,
    is_complete_catalog_coverage,
)
from grocery_data.app.domain.source_strategy import SourceChannel, SourceProvider
from grocery_data.app.services.store_coverage import (
    ExactStoreIdentityMatcher,
    GroceryContextEvidence,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    PhysicalStoreModel,
    PriceObservationModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
)
from grocery_data.app.storage.repositories import StoreContextLinkRepository

_SECRET_SHAPED_CONTEXT_VALUE = re.compile(
    r"(?:\bauthorization\s*[:=]|\bbearer\s+[a-z0-9._~-]+|"
    r"\bcookie\s*[:=]|\bsessionid\s*=)",
    flags=re.IGNORECASE,
)


class PhysicalIdentityBasis(StrEnum):
    """Exact, independently checkable basis for an external context link."""

    OFFICIAL_EXTERNAL_ID = "official_external_id"
    OFFICIAL_ADDRESS_POSTAL_CODE = "official_address_postal_code"
    OFFICIAL_COORDINATES = "official_coordinates"


class CredentialFreePhysicalIdentity(BaseModel):
    """Whitelisted physical identity facts from a provider-neutral export.

    The model intentionally has no provider credential, request-header or
    session fields. ``extra='forbid'`` makes an export containing one fail
    closed instead of silently persisting it as evidence.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)

    basis: PhysicalIdentityBasis
    official_external_store_id: str | None = Field(default=None, min_length=1)
    address: str | None = Field(default=None, min_length=1)
    postal_code: str | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)

    @field_validator("postal_code", mode="before")
    @classmethod
    def normalize_postal_code(cls, value: object) -> str | None:
        if value is None or not str(value).strip():
            return None
        digits = "".join(character for character in str(value) if character.isdigit())
        if len(digits) != 5:
            raise ValueError("postal_code must contain exactly five digits")
        return digits

    @model_validator(mode="after")
    def require_selected_identity(self) -> CredentialFreePhysicalIdentity:
        if (
            self.basis == PhysicalIdentityBasis.OFFICIAL_EXTERNAL_ID
            and self.official_external_store_id is None
        ):
            raise ValueError("official_external_id basis requires an official store ID")
        if self.basis == PhysicalIdentityBasis.OFFICIAL_ADDRESS_POSTAL_CODE and not (
            self.address and self.postal_code
        ):
            raise ValueError("official_address_postal_code basis requires address and postal code")
        if self.basis == PhysicalIdentityBasis.OFFICIAL_COORDINATES and (
            self.latitude is None or self.longitude is None
        ):
            raise ValueError("official_coordinates basis requires both coordinates")
        return self


class CredentialFreeContextExport(BaseModel):
    """Sanitized context projection imported from any external provider.

    Basket and offer eligibility are derived below. They are deliberately not
    accepted as input claims. Provider-native IDs are kept in ``context_id``;
    only the separately labelled official identity may link a physical store.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        allow_inf_nan=False,
        populate_by_name=True,
    )

    schema_version: Literal["grocery-context-evidence-v1"] = Field(
        alias="schema",
    )
    provider: SourceProvider
    source_channel: SourceChannel = SourceChannel.CATALOG
    context_id: str = Field(min_length=1, max_length=255)
    chain: Chain
    name: str = Field(min_length=1, max_length=500)
    city: str | None = Field(default=None, max_length=255)
    price_context_type: PriceContextType | None = None
    coverage: CoverageLevel | None = None
    source_snapshot_id: str | None = Field(default=None, min_length=1, max_length=255)
    source_observed_at: datetime | None = None
    connector_status: ConnectorStatus
    active: bool = True
    physical_identity: CredentialFreePhysicalIdentity

    @field_validator("source_observed_at")
    @classmethod
    def require_aware_observed_at(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("source_observed_at must be timezone-aware")
        return value.astimezone(UTC) if value is not None else None

    @model_validator(mode="after")
    def external_and_replayable(self) -> CredentialFreeContextExport:
        if self.provider == SourceProvider.OWN:
            raise ValueError("OWN evidence must be projected from the local snapshot database")
        if self.source_channel == SourceChannel.REGISTRY:
            raise ValueError("registry enrichment is not a price context")
        if self.source_channel == SourceChannel.OFFERS and self.coverage not in {
            None,
            CoverageLevel.OFFERS_ONLY,
        }:
            raise ValueError("an offer export cannot claim catalog coverage")
        if (self.source_snapshot_id is None) != (self.source_observed_at is None):
            raise ValueError("snapshot ID and observation time must be present together")
        return self

    def to_evidence(
        self,
        *,
        now: datetime,
        max_age_hours: float,
    ) -> GroceryContextEvidence:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if max_age_hours <= 0:
            raise ValueError("max_age_hours must be greater than zero")
        identity = self.physical_identity
        external_id = (
            identity.official_external_store_id
            if identity.basis == PhysicalIdentityBasis.OFFICIAL_EXTERNAL_ID
            else None
        )
        address = (
            identity.address
            if identity.basis == PhysicalIdentityBasis.OFFICIAL_ADDRESS_POSTAL_CODE
            else None
        )
        postal_code = (
            identity.postal_code
            if identity.basis == PhysicalIdentityBasis.OFFICIAL_ADDRESS_POSTAL_CODE
            else None
        )
        latitude = (
            identity.latitude
            if identity.basis == PhysicalIdentityBasis.OFFICIAL_COORDINATES
            else None
        )
        longitude = (
            identity.longitude
            if identity.basis == PhysicalIdentityBasis.OFFICIAL_COORDINATES
            else None
        )
        has_observation = bool(self.source_snapshot_id and self.source_observed_at)
        fresh = False
        if self.source_observed_at is not None:
            age_hours = (
                now.astimezone(UTC) - self.source_observed_at.astimezone(UTC)
            ).total_seconds() / 3600
            fresh = -1 <= age_hours
        healthy = self.connector_status in {ConnectorStatus.HEALTHY, ConnectorStatus.STALE}
        offers_only = bool(
            self.active
            and healthy
            and has_observation
            and fresh
            and self.source_channel == SourceChannel.OFFERS
            and self.coverage in {None, CoverageLevel.OFFERS_ONLY}
        )
        basket_eligible = bool(
            self.active
            and healthy
            and has_observation
            and fresh
            and self.source_channel == SourceChannel.CATALOG
            and self.coverage is not None
            and is_complete_catalog_coverage(self.coverage)
        )
        return GroceryContextEvidence(
            grocery_context_id=self.context_id,
            chain=self.chain,
            name=self.name,
            city=self.city,
            address=address,
            postal_code=postal_code,
            latitude=latitude,
            longitude=longitude,
            # This is explicitly an official identity, never a provider-native
            # store ID inferred from a name.
            physical_store_external_id=external_id,
            price_context_type=self.price_context_type,
            source_provider=self.provider,
            source_channel=self.source_channel,
            coverage=(
                CoverageLevel.OFFERS_ONLY
                if self.source_channel == SourceChannel.OFFERS and self.coverage is None
                else self.coverage
            ),
            basket_eligible=basket_eligible,
            offers_only=offers_only,
            snapshot_id=self.source_snapshot_id,
            observed_at=self.source_observed_at,
            active=self.active and healthy,
        )


class CredentialFreeContextBundle(BaseModel):
    """Closed envelope for an operator-supplied external context snapshot."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        populate_by_name=True,
    )

    schema_version: Literal["grocery-context-evidence-bundle-v1"] = Field(
        alias="schema",
    )
    postal_code: str = Field(pattern=r"^\d{5}$")
    captured_at: datetime
    items: tuple[CredentialFreeContextExport, ...] = Field(min_length=1, max_length=10_000)

    @field_validator("captured_at")
    @classmethod
    def require_aware_captured_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("captured_at must be timezone-aware")
        return value.astimezone(UTC)


def read_credential_free_context_bundle(
    path: Path,
    *,
    max_bytes: int = 100_000_000,
) -> CredentialFreeContextBundle:
    """Read one bounded, UTF-8, closed bundle; loose legacy roots fail closed."""

    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    resolved = path.resolve(strict=True)
    if not resolved.is_file():
        raise ValueError("context export must be a regular file")
    with resolved.open("rb") as source:
        encoded = source.read(max_bytes + 1)
    if len(encoded) > max_bytes:
        raise ValueError("context export exceeds the 100 MB import limit")
    if not encoded:
        raise ValueError("context export must not be empty")

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"context export contains duplicate key: {key}")
            result[key] = value
        return result

    payload = json.loads(encoded.decode("utf-8"), object_pairs_hook=closed_object)
    bundle = CredentialFreeContextBundle.model_validate(payload)

    def reject_secret_shaped_values(value: object) -> None:
        if isinstance(value, Mapping):
            for nested in value.values():
                reject_secret_shaped_values(nested)
        elif isinstance(value, list):
            for nested in value:
                reject_secret_shaped_values(nested)
        elif isinstance(value, str) and _SECRET_SHAPED_CONTEXT_VALUE.search(value):
            raise ValueError("context export contains a credential-shaped value")

    reject_secret_shaped_values(payload)
    return bundle


class CredentialFreeContextImporter:
    """Parse a closed, sanitized provider export without making live calls."""

    @staticmethod
    def import_rows(
        rows: Iterable[CredentialFreeContextExport | Mapping[str, Any]],
        *,
        now: datetime | None = None,
        max_age_hours: float = 48.0,
    ) -> tuple[GroceryContextEvidence, ...]:
        timestamp = now or datetime.now(tz=UTC)
        if timestamp.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        if max_age_hours <= 0:
            raise ValueError("max_age_hours must be greater than zero")
        contexts: list[GroceryContextEvidence] = []
        keys: set[tuple[SourceProvider, str]] = set()
        for row in rows:
            export = (
                row
                if isinstance(row, CredentialFreeContextExport)
                else CredentialFreeContextExport.model_validate(row)
            )
            key = (export.provider, export.context_id)
            if key in keys:
                raise ValueError(
                    f"duplicate context evidence for {export.provider.value}:{export.context_id}"
                )
            keys.add(key)
            contexts.append(export.to_evidence(now=timestamp, max_age_hours=max_age_hours))
        return tuple(
            sorted(
                contexts,
                key=lambda item: (
                    item.chain.value,
                    item.source_provider.value,
                    item.grocery_context_id,
                ),
            )
        )


class OwnContextEvidenceProjector:
    """Derive OWN contexts from local rows and their promoted snapshots only."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def project_city(self, city: str) -> tuple[GroceryContextEvidence, ...]:
        city_key = city.casefold().strip()
        if not city_key:
            raise ValueError("city must not be blank")
        stores = list(
            self.session.scalars(
                select(StoreModel)
                .where(
                    StoreModel.is_active.is_(True),
                    func.lower(func.trim(StoreModel.city)) == city_key,
                )
                .order_by(StoreModel.chain, StoreModel.name, StoreModel.id)
            )
        )
        return tuple(self._project(store) for store in stores)

    def _project(self, store: StoreModel) -> GroceryContextEvidence:
        snapshot = self._promoted_snapshot_for_store(store)
        observed_at: datetime | None = None
        if snapshot is not None:
            observed_at = self.session.scalar(
                select(func.min(PriceObservationModel.observed_at)).where(
                    PriceObservationModel.catalog_snapshot_id == snapshot.id,
                    PriceObservationModel.store_id == store.id,
                )
            )
            observed_at = observed_at or snapshot.created_at
        try:
            coverage = CoverageLevel(store.coverage)
        except ValueError:
            coverage = None
        try:
            price_context = (
                PriceContextType(store.price_context_type)
                if store.price_context_type is not None
                else None
            )
        except ValueError:
            price_context = None
        channel = (
            SourceChannel.OFFERS if coverage == CoverageLevel.OFFERS_ONLY else SourceChannel.CATALOG
        )
        external_id: str | None = store.external_id
        physical_external_id = store.physical_store_external_id

        # Willys' catalog is observed only after the public frontend has
        # activated an exact online/picking store. Older promoted snapshots
        # predate the typed context columns, but retain both the exact store ID
        # and ``online_shopping=true``. Preserve that verified semantic without
        # claiming that the price is a physical shelf price.
        if (
            store.chain == Chain.WILLYS.value
            and price_context is None
            and store.online_shopping is True
            and coverage == CoverageLevel.FULL_CATALOG
        ):
            price_context = PriceContextType.ONLINE_STORE
            physical_external_id = physical_external_id or store.external_id
        address = store.address
        postal_code = store.postal_code
        latitude = store.latitude
        longitude = store.longitude

        # An ICA/Coop OWN offer row is linkable only when the connector has
        # preserved an explicit official physical-store identity. Exact-looking
        # names or addresses alone do not prove that the offer context belongs
        # to that store.
        if channel == SourceChannel.OFFERS and store.chain in {Chain.ICA.value, Chain.COOP.value}:
            # The physical registry came from the separate official locator.
            # Equal IDs across those two independently collected namespaces are
            # proof; a similar display name is not. This also upgrades older
            # offer snapshots created before StoreModel gained an explicit
            # physical_store_external_id field.
            physical_external_id = physical_external_id or self._official_external_id(store)
            if physical_external_id is None:
                external_id = None
                address = None
                postal_code = None
                latitude = None
                longitude = None

        # Lidl's currently verified `public-default-region` feed is a national/
        # regional offer context. It must remain useful at /offers while never
        # masquerading as a price observation for either physical Lund store.
        if store.chain == Chain.LIDL.value and (
            store.external_id == "public-default-region"
            or price_context == PriceContextType.REGIONAL
        ):
            external_id = None
            physical_external_id = None
            address = None
            postal_code = None
            latitude = None
            longitude = None

        return GroceryContextEvidence(
            # Stable across database rebuilds. ``local_store_id`` below is the
            # database-local FK used to read the promoted snapshot.
            grocery_context_id=f"own:{store.chain}:{store.external_id}",
            chain=Chain(store.chain),
            name=store.name,
            city=store.city,
            address=address,
            postal_code=postal_code,
            latitude=latitude,
            longitude=longitude,
            external_store_id=external_id,
            physical_store_external_id=physical_external_id,
            price_context_type=price_context,
            source_provider=SourceProvider.OWN,
            source_channel=channel,
            coverage=coverage,
            basket_eligible=bool(
                snapshot is not None
                and coverage is not None
                and is_complete_catalog_coverage(coverage)
            ),
            offers_only=bool(snapshot is not None and coverage == CoverageLevel.OFFERS_ONLY),
            snapshot_id=snapshot.id if snapshot is not None else None,
            observed_at=observed_at,
            active=store.is_active,
            local_store_id=store.id,
        )

    def _official_external_id(self, store: StoreModel) -> str | None:
        rows = list(
            self.session.scalars(
                select(PhysicalStoreModel).where(
                    PhysicalStoreModel.chain == store.chain,
                    PhysicalStoreModel.external_store_id == store.external_id,
                    PhysicalStoreModel.is_active.is_(True),
                )
            )
        )
        if len(rows) != 1:
            return None
        return rows[0].external_store_id

    def _promoted_snapshot_for_store(
        self,
        store: StoreModel,
    ) -> CatalogSnapshotModel | None:
        contains_store = exists(
            select(1).where(
                SourceProductModel.catalog_snapshot_id == CatalogSnapshotModel.id,
                SourceProductModel.store_id == store.id,
            )
        )
        return self.session.scalar(
            select(CatalogSnapshotModel)
            .where(
                CatalogSnapshotModel.chain == store.chain,
                CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
                CatalogSnapshotModel.is_active.is_(True),
                contains_store,
            )
            .order_by(
                CatalogSnapshotModel.promoted_at.desc(),
                CatalogSnapshotModel.created_at.desc(),
                CatalogSnapshotModel.id,
            )
            .limit(1)
        )


class ContextLinkDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    physical_store_id: str
    grocery_context_id: str
    source_provider: SourceProvider
    source_channel: SourceChannel
    confidence: Confidence
    evidence: str


class ContextReconciliationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    city: str
    contexts_considered: int
    physical_stores_considered: int
    links_written: int
    links_deactivated: int = 0
    linked_physical_stores: tuple[str, ...]
    missing_physical_stores: tuple[str, ...]
    decisions: tuple[ContextLinkDecision, ...]


class ExactStoreContextReconciler:
    """Persist only exact/structured links; never fuzzy-match store names."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def reconcile_city(
        self,
        city: str,
        contexts: Sequence[GroceryContextEvidence],
        *,
        verified_at: datetime | None = None,
        authoritative_sources: set[tuple[Chain, SourceProvider, SourceChannel]] | None = None,
        allow_empty_authoritative_sources: bool = False,
    ) -> ContextReconciliationResult:
        city_key = city.casefold().strip()
        if not city_key:
            raise ValueError("city must not be blank")
        timestamp = verified_at or datetime.now(tz=UTC)
        if timestamp.tzinfo is None:
            raise ValueError("verified_at must be timezone-aware")
        timestamp = timestamp.astimezone(UTC)
        physical_stores = list(
            self.session.scalars(
                select(PhysicalStoreModel)
                .where(
                    PhysicalStoreModel.is_active.is_(True),
                    func.lower(func.trim(PhysicalStoreModel.city)) == city_key,
                )
                .order_by(PhysicalStoreModel.chain, PhysicalStoreModel.name)
            )
        )
        repository = StoreContextLinkRepository(self.session)
        authoritative = authoritative_sources or set()
        context_sources = {
            (context.chain, context.source_provider, context.source_channel) for context in contexts
        }
        empty_authoritative = authoritative - context_sources
        if empty_authoritative and not allow_empty_authoritative_sources:
            labels = ", ".join(
                f"{chain.value}/{provider.value}/{channel.value}"
                for chain, provider, channel in sorted(
                    empty_authoritative,
                    key=lambda item: (item[0].value, item[1].value, item[2].value),
                )
            )
            raise ValueError(
                f"authoritative context projection is empty for {labels}; drift rejected"
            )
        linked: set[str] = set()
        decisions: list[ContextLinkDecision] = []
        links_written = 0
        links_deactivated = 0
        seen_by_physical_source: dict[
            tuple[str, Chain, SourceProvider, SourceChannel], set[str]
        ] = {}
        for physical in physical_stores:
            for match in ExactStoreIdentityMatcher.physical_to_context(physical, contexts):
                if not self._policy_allows(physical, match.context):
                    continue
                repository.upsert(match.as_link(physical.id, verified_at=timestamp))
                links_written += 1
                linked.add(physical.id)
                decisions.append(
                    ContextLinkDecision(
                        physical_store_id=physical.id,
                        grocery_context_id=match.context.grocery_context_id,
                        source_provider=match.context.source_provider,
                        source_channel=match.context.source_channel,
                        confidence=match.confidence,
                        evidence=match.evidence,
                    )
                )
                seen_by_physical_source.setdefault(
                    (
                        physical.id,
                        match.context.chain,
                        match.context.source_provider,
                        match.context.source_channel,
                    ),
                    set(),
                ).add(match.context.grocery_context_id)
        # Deactivation is opt-in and scoped to one chain/provider/channel whose
        # export the operator declared complete. An ICA-only Primat export can
        # therefore never retire Coop/Lidl Primat links, and a missing provider
        # export can never retire OWN links. Empty scopes fail closed unless
        # separately acknowledged.
        for physical in physical_stores:
            physical_chain = Chain(physical.chain)
            for chain, provider, channel in authoritative:
                if physical_chain != chain:
                    continue
                seen = seen_by_physical_source.get(
                    (physical.id, chain, provider, channel),
                    set(),
                )
                existing = self.session.scalars(
                    select(StoreContextLinkModel).where(
                        StoreContextLinkModel.physical_store_id == physical.id,
                        StoreContextLinkModel.source_provider == provider.value,
                        StoreContextLinkModel.source_channel == channel.value,
                    )
                )
                for row in existing:
                    should_be_active = row.grocery_context_id in seen
                    if row.is_active and not should_be_active:
                        row.is_active = False
                        row.last_verified_at = timestamp
                        links_deactivated += 1
        self.session.flush()
        ids = {row.id for row in physical_stores}
        return ContextReconciliationResult(
            city=city.strip(),
            contexts_considered=len(contexts),
            physical_stores_considered=len(physical_stores),
            links_written=links_written,
            links_deactivated=links_deactivated,
            linked_physical_stores=tuple(sorted(linked)),
            missing_physical_stores=tuple(sorted(ids - linked)),
            decisions=tuple(
                sorted(
                    decisions,
                    key=lambda item: (
                        item.physical_store_id,
                        item.source_provider.value,
                        item.grocery_context_id,
                    ),
                )
            ),
        )

    @staticmethod
    def _policy_allows(
        physical: PhysicalStoreModel,
        context: GroceryContextEvidence,
    ) -> bool:
        if context.chain.value != physical.chain:
            return False
        if (
            context.source_provider == SourceProvider.OWN
            and context.source_channel == SourceChannel.OFFERS
            and context.chain in {Chain.ICA, Chain.COOP}
        ):
            return bool(
                context.physical_store_external_id
                in ExactStoreIdentityMatcher.external_identities(physical)
            )
        return not (
            context.chain == Chain.LIDL
            and context.source_channel == SourceChannel.OFFERS
            and (
                context.price_context_type == PriceContextType.REGIONAL
                or context.grocery_context_id == "public-default-region"
                or context.external_store_id == "public-default-region"
            )
        )


__all__ = [
    "ContextLinkDecision",
    "ContextReconciliationResult",
    "CredentialFreeContextBundle",
    "CredentialFreeContextExport",
    "CredentialFreeContextImporter",
    "CredentialFreePhysicalIdentity",
    "ExactStoreContextReconciler",
    "OwnContextEvidenceProjector",
    "PhysicalIdentityBasis",
    "read_credential_free_context_bundle",
]
