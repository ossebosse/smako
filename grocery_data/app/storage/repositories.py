from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.enums import (
    Chain,
    Confidence,
    ConnectorStatus,
    CoverageLevel,
    PhysicalStoreLifecycleState,
    PromotionType,
    SaleModel,
    SnapshotState,
    StoreContextRelationType,
    StoreDiscoveryErrorCode,
)
from grocery_data.app.domain.health import ConnectorHealth
from grocery_data.app.domain.identifiers import normalize_gtin
from grocery_data.app.domain.physical_price import (
    DigitalPriceCandidate,
    PhysicalIdentifierPreparation,
    PhysicalObservationAmendment,
    PhysicalObservationAmendmentKind,
    PhysicalObservationTimePrecision,
    PhysicalPriceObservation,
    PhysicalPriceSemantics,
    PhysicalValidationSession,
    PhysicalValidationSessionItem,
    PhysicalValidationSessionStatus,
    ProductIdentifierEvidence,
    ProductIdentifierEvidenceSource,
    ProductIdentifierType,
    SessionItemIdentifierStatus,
    ShelfIdentifierEvidence,
    canonical_physical_observation_payload,
    physical_observation_payload_sha256,
)
from grocery_data.app.domain.product import (
    CanonicalProduct,
    ParseFailure,
    SourceOffer,
    SourceProduct,
)
from grocery_data.app.domain.raw import RawFetch
from grocery_data.app.domain.source_strategy import SourceProvider
from grocery_data.app.domain.store import (
    PhysicalStore,
    ProviderStoreIdentityMapping,
    SourceStore,
    StoreContextLink,
)
from grocery_data.app.storage.models import (
    CatalogSnapshotModel,
    CollectorRunModel,
    ConnectorHealthModel,
    ExternalPriceCandidateModel,
    ParserFailureModel,
    PhysicalIdentifierPreparationModel,
    PhysicalObservationAmendmentModel,
    PhysicalObservationV2EvidenceModel,
    PhysicalPriceObservationModel,
    PhysicalStoreDiscoveryHealthModel,
    PhysicalStoreModel,
    PhysicalValidationComparisonVersionModel,
    PhysicalValidationSessionCandidateModel,
    PhysicalValidationSessionItemIdentifierModel,
    PhysicalValidationSessionItemModel,
    PhysicalValidationSessionModel,
    PhysicalValidationSessionReconciliationModel,
    PhysicalValidationSnapshotLockModel,
    PriceObservationModel,
    ProductIdentifierEvidenceModel,
    ProductModel,
    PromotionModel,
    ProviderStoreIdentityMappingModel,
    RawSnapshotModel,
    ShelfIdentifierEvidenceModel,
    SourceProductModel,
    StoreContextLinkModel,
    StoreModel,
    utcnow,
)


def _value(value: StrEnum | str) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def _aware(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)


def _positive_decimal(value: Decimal | float | str | None, *, field: str) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a valid decimal") from exc
    if not decimal_value.is_finite() or decimal_value <= 0:
        raise ValueError(f"{field} must be finite and greater than zero")
    return decimal_value


class SnapshotTransitionError(ValueError):
    """Raised when snapshot state would bypass the promotion pipeline."""


class PhysicalObservationAmendmentHeadConflict(ValueError):
    """Raised when an amendment attempts to branch from a stale item head."""

    def __init__(self, *, expected_head_id: str | None, supplied_head_id: str | None) -> None:
        self.expected_head_id = expected_head_id
        self.supplied_head_id = supplied_head_id
        super().__init__(
            "physical observation amendment head changed "
            f"(expected {expected_head_id!r}, supplied {supplied_head_id!r})"
        )


class PhysicalObservationAmendmentIntegrityError(RuntimeError):
    """Raised when immutable amendment storage is internally inconsistent."""


class StoreRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, chain: Chain | str, external_id: str) -> StoreModel | None:
        return self.session.scalar(
            select(StoreModel).where(
                StoreModel.chain == _value(chain),
                StoreModel.external_id == external_id,
            )
        )

    def upsert(
        self,
        source: SourceStore,
        *,
        seen_at: datetime | None = None,
        activate: bool | None = True,
    ) -> StoreModel:
        """Insert or update a source store using its stable chain/external ID key."""

        timestamp = _aware(seen_at or utcnow(), field="seen_at")
        model = self.get(source.chain, source.external_id)
        if model is None:
            model = StoreModel(
                chain=source.chain.value,
                external_id=source.external_id,
                first_seen_at=timestamp,
                is_active=False if activate is None else activate,
            )
            self.session.add(model)

        model.name = source.name
        model.address = source.address
        model.postal_code = source.postal_code
        model.city = source.city
        model.latitude = source.latitude
        model.longitude = source.longitude
        model.online_shopping = source.online_shopping
        model.coverage = source.coverage.value
        model.price_context_type = (
            source.price_context_type.value if source.price_context_type is not None else None
        )
        model.physical_store_external_id = source.physical_store_external_id
        model.raw_reference = source.raw_reference
        if activate is not None:
            model.is_active = activate
        model.last_seen_at = timestamp
        self.session.flush()
        return model

    def reconcile_scope(
        self,
        chain: Chain | str,
        *,
        city: str,
        seen_external_ids: set[str],
        deactivate_unseen: bool = True,
    ) -> tuple[int, int]:
        """Activate seen stores and optionally deactivate city peers after promotion.

        A normal city-wide run owns the complete set and may deactivate unseen
        peers.  A context-scoped run owns exactly one independently priced
        context and must leave other active contexts in the same city alone.
        """

        city_key = city.casefold().strip()
        if not city_key or not seen_external_ids:
            raise ValueError("city and at least one seen store are required for reconciliation")
        activated = 0
        deactivated = 0
        candidates = list(
            self.session.scalars(select(StoreModel).where(StoreModel.chain == _value(chain)))
        )
        for model in candidates:
            is_seen = model.external_id in seen_external_ids
            if not is_seen and (
                not deactivate_unseen
                or (model.city or "").casefold().strip() != city_key
            ):
                continue
            should_be_active = is_seen
            if model.is_active == should_be_active:
                continue
            model.is_active = should_be_active
            if should_be_active:
                activated += 1
            else:
                deactivated += 1
        self.session.flush()
        return activated, deactivated

    def list_for_chain(
        self,
        chain: Chain | str,
        *,
        active_only: bool = True,
    ) -> list[StoreModel]:
        statement: Select[tuple[StoreModel]] = select(StoreModel).where(
            StoreModel.chain == _value(chain)
        )
        if active_only:
            statement = statement.where(StoreModel.is_active.is_(True))
        return list(self.session.scalars(statement.order_by(StoreModel.name, StoreModel.id)))


class StoreDiscoveryDriftError(RuntimeError):
    """Raised when an empty discovery would incorrectly close every known store."""


@dataclass(frozen=True, slots=True)
class PhysicalStoreReconciliation:
    seen: int
    reactivated: int
    marked_not_seen: int


class PhysicalStoreRepository:
    """History-safe registry of official physical sites."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, physical_store_id: str) -> PhysicalStoreModel | None:
        return self.session.get(PhysicalStoreModel, physical_store_id)

    def get_by_external_id(
        self,
        chain: Chain | str,
        external_store_id: str,
    ) -> PhysicalStoreModel | None:
        if not external_store_id.strip():
            raise ValueError("external_store_id must not be blank")
        return self.session.scalar(
            select(PhysicalStoreModel).where(
                PhysicalStoreModel.chain == _value(chain),
                PhysicalStoreModel.external_store_id == external_store_id,
            )
        )

    def get_by_any_external_id(
        self,
        chain: Chain | str,
        external_store_id: str,
    ) -> PhysicalStoreModel | None:
        """Resolve one exact official primary ID or alias, never a display name."""

        identity = external_store_id.strip()
        if not identity:
            raise ValueError("external_store_id must not be blank")
        matches = [
            row
            for row in self.session.scalars(
                select(PhysicalStoreModel).where(
                    PhysicalStoreModel.chain == _value(chain)
                )
            )
            if identity
            in {
                row.external_store_id,
                *(row.external_store_aliases or []),
            }
        ]
        if len(matches) > 1:
            raise ValueError("official external store identity is ambiguous")
        return matches[0] if matches else None

    def upsert(
        self,
        source: PhysicalStore,
        *,
        seen_at: datetime | None = None,
    ) -> PhysicalStoreModel:
        timestamp = _aware(seen_at or source.last_seen_at, field="seen_at")
        by_id = self.get(source.id)
        external_identities = {
            identity
            for identity in (
                source.external_store_id,
                *source.external_store_aliases,
            )
            if identity is not None
        }
        by_external = {
            match.id: match
            for identity in external_identities
            if (match := self.get_by_any_external_id(source.chain, identity)) is not None
        }
        candidate_ids = set(by_external)
        if by_id is not None:
            candidate_ids.add(by_id.id)
        if len(candidate_ids) > 1:
            raise ValueError("physical-store ID conflicts with official external identity")
        model = by_id or next(iter(by_external.values()), None)
        if model is None:
            model = PhysicalStoreModel(
                id=source.id,
                chain=source.chain.value,
                discovered_at=source.discovered_at,
                created_at=source.discovered_at,
            )
            self.session.add(model)
        elif model.chain != source.chain.value:
            raise ValueError("physical-store identity cannot change chain")

        model.external_store_id = source.external_store_id
        model.external_store_aliases = list(source.external_store_aliases)
        model.name = source.name
        model.address = source.address
        model.postal_code = source.postal_code
        model.city = source.city
        model.latitude = source.latitude
        model.longitude = source.longitude
        model.official_source = source.official_source
        model.discovered_at = min(model.discovered_at, source.discovered_at)
        model.last_seen_at = max(model.last_seen_at or timestamp, timestamp)
        model.is_active = source.active
        model.lifecycle_state = source.lifecycle_state.value
        model.not_seen_at = source.not_seen_at
        model.updated_at = utcnow()
        self.session.flush()
        return model

    def list_for_city(
        self,
        city: str,
        *,
        chain: Chain | str | None = None,
        active_only: bool = False,
    ) -> list[PhysicalStoreModel]:
        city_key = city.casefold().strip()
        if not city_key:
            raise ValueError("city must not be blank")
        statement = select(PhysicalStoreModel).where(
            func.lower(func.trim(PhysicalStoreModel.city)) == city_key
        )
        if chain is not None:
            statement = statement.where(PhysicalStoreModel.chain == _value(chain))
        if active_only:
            statement = statement.where(PhysicalStoreModel.is_active.is_(True))
        return list(
            self.session.scalars(
                statement.order_by(
                    PhysicalStoreModel.chain,
                    PhysicalStoreModel.name,
                    PhysicalStoreModel.id,
                )
            )
        )

    def reconcile_discovery(
        self,
        chain: Chain | str,
        *,
        city: str,
        seen_physical_store_ids: set[str],
        observed_at: datetime | None = None,
    ) -> PhysicalStoreReconciliation:
        """Mark absent rows NOT_SEEN, never delete them.

        An empty successful-looking discovery is rejected as drift.  The caller
        must surface that run as degraded/broken rather than interpret it as all
        stores having closed.
        """

        if not seen_physical_store_ids:
            raise StoreDiscoveryDriftError(
                "empty physical-store discovery cannot reconcile an existing city"
            )
        timestamp = _aware(observed_at or utcnow(), field="observed_at")
        rows = self.list_for_city(city, chain=chain, active_only=False)
        known_ids = {row.id for row in rows}
        unknown_ids = seen_physical_store_ids - known_ids
        if unknown_ids:
            raise ValueError("seen store IDs must be upserted before reconciliation")

        reactivated = 0
        marked_not_seen = 0
        for row in rows:
            if row.id in seen_physical_store_ids:
                row.last_seen_at = max(row.last_seen_at, timestamp)
                if not row.is_active:
                    reactivated += 1
                row.is_active = True
                row.lifecycle_state = PhysicalStoreLifecycleState.ACTIVE.value
                row.not_seen_at = None
            elif row.is_active:
                row.is_active = False
                row.lifecycle_state = PhysicalStoreLifecycleState.NOT_SEEN.value
                row.not_seen_at = timestamp
                marked_not_seen += 1
            row.updated_at = utcnow()
        self.session.flush()
        return PhysicalStoreReconciliation(
            seen=len(seen_physical_store_ids),
            reactivated=reactivated,
            marked_not_seen=marked_not_seen,
        )


def _normalized_city(value: str) -> str:
    normalized = " ".join(value.casefold().split())
    if not normalized:
        raise ValueError("city must not be blank")
    return normalized


class PhysicalStoreDiscoveryHealthRepository:
    """Persist the last official-locator attempt without replacing registry LKG."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        chain: Chain | str,
        city: str,
    ) -> PhysicalStoreDiscoveryHealthModel | None:
        return self.session.scalar(
            select(PhysicalStoreDiscoveryHealthModel).where(
                PhysicalStoreDiscoveryHealthModel.chain == _value(chain),
                PhysicalStoreDiscoveryHealthModel.normalized_city == _normalized_city(city),
            )
        )

    def list_for_city(self, city: str) -> list[PhysicalStoreDiscoveryHealthModel]:
        return list(
            self.session.scalars(
                select(PhysicalStoreDiscoveryHealthModel)
                .where(
                    PhysicalStoreDiscoveryHealthModel.normalized_city
                    == _normalized_city(city)
                )
                .order_by(PhysicalStoreDiscoveryHealthModel.chain)
            )
        )

    def record(
        self,
        *,
        chain: Chain | str,
        city: str,
        status: ConnectorStatus,
        complete: bool,
        discovered_count: int,
        previous_count: int | None,
        observed_at: datetime,
        error_code: StoreDiscoveryErrorCode | None = None,
    ) -> PhysicalStoreDiscoveryHealthModel:
        if discovered_count < 0 or (previous_count is not None and previous_count < 0):
            raise ValueError("store discovery counts cannot be negative")
        if status == ConnectorStatus.HEALTHY and (not complete or error_code is not None):
            raise ValueError("healthy discovery health must be complete and error-free")
        if status != ConnectorStatus.HEALTHY and error_code is None:
            raise ValueError("non-healthy discovery health requires a closed error code")
        timestamp = _aware(observed_at, field="observed_at")
        normalized_city = _normalized_city(city)
        row = self.get(chain, city)
        if row is None:
            row = PhysicalStoreDiscoveryHealthModel(
                chain=_value(chain),
                normalized_city=normalized_city,
                created_at=timestamp,
            )
            self.session.add(row)
        row.city = city.strip()
        row.status = status.value
        row.complete = complete
        row.discovered_count = discovered_count
        row.previous_count = previous_count
        row.observed_at = timestamp
        row.error_code = error_code.value if error_code is not None else None
        row.updated_at = timestamp
        self.session.flush()
        return row


@dataclass(frozen=True, slots=True)
class StoreContextLinkReconciliation:
    verified: int
    reactivated: int
    deactivated: int


class StoreContextLinkRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        physical_store_id: str,
        *,
        source_provider: str,
        grocery_context_id: str,
    ) -> StoreContextLinkModel | None:
        return self.session.scalar(
            select(StoreContextLinkModel).where(
                StoreContextLinkModel.physical_store_id == physical_store_id,
                StoreContextLinkModel.source_provider == source_provider,
                StoreContextLinkModel.grocery_context_id == grocery_context_id,
            )
        )

    def upsert(self, link: StoreContextLink) -> StoreContextLinkModel:
        physical = self.session.get(PhysicalStoreModel, link.physical_store_id)
        if physical is None:
            raise LookupError(f"physical store {link.physical_store_id!r} does not exist")
        local = None
        if link.local_store_id is not None:
            local = self.session.get(StoreModel, link.local_store_id)
            if local is None:
                raise LookupError(f"local grocery context {link.local_store_id!r} does not exist")
            if local.chain != physical.chain:
                raise ValueError("physical store and local grocery context must share chain")

        model = self.get(
            link.physical_store_id,
            source_provider=link.source_provider.value,
            grocery_context_id=link.grocery_context_id,
        )
        if model is None:
            model = StoreContextLinkModel(
                physical_store_id=link.physical_store_id,
                grocery_context_id=link.grocery_context_id,
                source_provider=link.source_provider.value,
                linked_at=link.linked_at,
            )
            self.session.add(model)

        model.source_channel = link.source_channel.value
        model.local_store_id = local.id if local is not None else None
        model.pickup_point_external_id = link.pickup_point_external_id
        model.grocery_context_name = link.grocery_context_name
        model.price_context_type = (
            link.price_context_type.value if link.price_context_type is not None else None
        )
        model.coverage = link.coverage.value if link.coverage is not None else None
        model.relation_type = link.relation_type.value
        model.confidence = link.confidence.value
        model.evidence = link.evidence
        model.basket_eligible = link.basket_eligible
        model.offers_only = link.offers_only
        model.snapshot_id = link.snapshot_id
        model.observed_at = link.observed_at
        model.linked_at = min(model.linked_at, link.linked_at)
        model.last_verified_at = link.last_verified_at
        model.is_active = link.active
        model.updated_at = utcnow()
        self.session.flush()
        return model

    def list_for_physical_store(
        self,
        physical_store_id: str,
        *,
        active_only: bool = True,
    ) -> list[StoreContextLinkModel]:
        statement = select(StoreContextLinkModel).where(
            StoreContextLinkModel.physical_store_id == physical_store_id
        )
        if active_only:
            statement = statement.where(StoreContextLinkModel.is_active.is_(True))
        return list(
            self.session.scalars(
                statement.order_by(
                    StoreContextLinkModel.source_provider,
                    StoreContextLinkModel.grocery_context_id,
                )
            )
        )

    def list_for_context(
        self,
        *,
        source_provider: str,
        grocery_context_id: str,
        active_only: bool = True,
    ) -> list[StoreContextLinkModel]:
        statement = select(StoreContextLinkModel).where(
            StoreContextLinkModel.source_provider == source_provider,
            StoreContextLinkModel.grocery_context_id == grocery_context_id,
        )
        if active_only:
            statement = statement.where(StoreContextLinkModel.is_active.is_(True))
        return list(self.session.scalars(statement.order_by(StoreContextLinkModel.id)))

    def list_for_city(
        self,
        city: str,
        *,
        active_only: bool = True,
    ) -> list[StoreContextLinkModel]:
        city_key = city.casefold().strip()
        if not city_key:
            raise ValueError("city must not be blank")
        statement = (
            select(StoreContextLinkModel)
            .join(
                PhysicalStoreModel,
                PhysicalStoreModel.id == StoreContextLinkModel.physical_store_id,
            )
            .where(func.lower(func.trim(PhysicalStoreModel.city)) == city_key)
        )
        if active_only:
            statement = statement.where(StoreContextLinkModel.is_active.is_(True))
        return list(
            self.session.scalars(
                statement.order_by(
                    PhysicalStoreModel.chain,
                    PhysicalStoreModel.name,
                    StoreContextLinkModel.source_provider,
                    StoreContextLinkModel.grocery_context_id,
                )
            )
        )

    def reconcile_for_physical_store(
        self,
        physical_store_id: str,
        *,
        seen_context_keys: set[tuple[str, str]],
        verified_at: datetime | None = None,
        allow_empty: bool = False,
    ) -> StoreContextLinkReconciliation:
        if not seen_context_keys and not allow_empty:
            raise StoreDiscoveryDriftError("empty context discovery requires explicit opt-in")
        timestamp = _aware(verified_at or utcnow(), field="verified_at")
        rows = self.list_for_physical_store(physical_store_id, active_only=False)
        known = {(row.source_provider, row.grocery_context_id) for row in rows}
        if unseen := seen_context_keys - known:
            raise ValueError(f"context links must be upserted first ({len(unseen)} unknown)")
        reactivated = 0
        deactivated = 0
        for row in rows:
            is_seen = (row.source_provider, row.grocery_context_id) in seen_context_keys
            if is_seen:
                if not row.is_active:
                    reactivated += 1
                row.is_active = True
                row.last_verified_at = timestamp
            elif row.is_active:
                row.is_active = False
                deactivated += 1
            row.updated_at = utcnow()
        self.session.flush()
        return StoreContextLinkReconciliation(
            verified=len(seen_context_keys),
            reactivated=reactivated,
            deactivated=deactivated,
        )


class ProviderStoreIdentityMappingRepository:
    """Persist one current/LKG external identity state per store/provider."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(
        self,
        physical_store_id: str,
        *,
        provider: SourceProvider | str,
    ) -> ProviderStoreIdentityMappingModel | None:
        return self.session.scalar(
            select(ProviderStoreIdentityMappingModel).where(
                ProviderStoreIdentityMappingModel.physical_store_id == physical_store_id,
                ProviderStoreIdentityMappingModel.provider == _value(provider),
            )
        )

    def upsert(
        self,
        mapping: ProviderStoreIdentityMapping,
    ) -> ProviderStoreIdentityMappingModel:
        if self.session.get(PhysicalStoreModel, mapping.physical_store_id) is None:
            raise LookupError(
                f"physical store {mapping.physical_store_id!r} does not exist"
            )
        row = self.get(mapping.physical_store_id, provider=mapping.provider)
        if row is None:
            row = ProviderStoreIdentityMappingModel(
                physical_store_id=mapping.physical_store_id,
                provider=mapping.provider.value,
            )
            self.session.add(row)
        row.provider_context_id = mapping.provider_context_id
        row.provider_store_id = mapping.provider_store_id
        row.confidence = mapping.confidence.value
        row.status = mapping.status.value
        row.evidence = mapping.evidence
        row.verified_identity_fingerprint = mapping.verified_identity_fingerprint
        row.observed_identity_fingerprint = mapping.observed_identity_fingerprint
        row.candidate_context_id = mapping.candidate_context_id
        row.verified_at = mapping.verified_at
        row.last_checked_at = mapping.last_checked_at
        row.drift_detected_at = mapping.drift_detected_at
        row.is_active = mapping.active
        row.updated_at = utcnow()
        self.session.flush()
        return row

    def list_for_city(
        self,
        city: str,
        *,
        provider: SourceProvider | str | None = None,
        active_only: bool = True,
    ) -> list[ProviderStoreIdentityMappingModel]:
        city_key = city.casefold().strip()
        if not city_key:
            raise ValueError("city must not be blank")
        statement = (
            select(ProviderStoreIdentityMappingModel)
            .join(
                PhysicalStoreModel,
                PhysicalStoreModel.id
                == ProviderStoreIdentityMappingModel.physical_store_id,
            )
            .where(func.lower(func.trim(PhysicalStoreModel.city)) == city_key)
        )
        if provider is not None:
            statement = statement.where(
                ProviderStoreIdentityMappingModel.provider == _value(provider)
            )
        if active_only:
            statement = statement.where(
                ProviderStoreIdentityMappingModel.is_active.is_(True)
            )
        return list(
            self.session.scalars(
                statement.order_by(
                    PhysicalStoreModel.chain,
                    PhysicalStoreModel.name,
                    ProviderStoreIdentityMappingModel.provider,
                )
            )
        )


class PhysicalPriceObservationRepository:
    """Persist manual validation samples without touching catalog prices."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, observation: PhysicalPriceObservation) -> PhysicalPriceObservationModel:
        if self.session.get(PhysicalStoreModel, observation.physical_store_id) is None:
            raise LookupError(f"physical store {observation.physical_store_id!r} does not exist")
        existing = self.get(observation.id)
        values = {
            "physical_store_id": observation.physical_store_id,
            "gtin": observation.gtin,
            "product_name": observation.product_name,
            "shelf_price": observation.shelf_price,
            "comparison_price": observation.comparison_price,
            "comparison_unit": observation.comparison_unit,
            "promotion_type": (
                observation.promotion_type.value if observation.promotion_type is not None else None
            ),
            "member_only": observation.member_only,
            "multibuy_quantity": observation.multibuy_quantity,
            "multibuy_total_price": observation.multibuy_total_price,
            "promotion_text": observation.promotion_text,
            "observed_at": observation.observed_at,
            "source": observation.source,
            "confidence": observation.confidence.value,
            "notes": observation.notes,
            "photo_reference": observation.photo_reference,
            "validation_session_id": observation.validation_session_id,
            "validation_session_item_id": observation.validation_session_item_id,
            "price_semantics": (
                observation.price_semantics.value
                if observation.price_semantics is not None
                else None
            ),
            "identity_status": (
                observation.identity_status.value
                if observation.identity_status is not None
                else None
            ),
            "immutable_candidate_set_sha256": observation.immutable_candidate_set_sha256,
        }
        if existing is not None:
            if any(getattr(existing, field) != value for field, value in values.items()):
                raise ValueError("physical observation ID already exists with different data")
            v2 = self.session.get(PhysicalObservationV2EvidenceModel, observation.id)
            expected_v2 = (
                (
                    observation.identification_evidence.value
                    if observation.identification_evidence is not None
                    else None
                ),
                observation.regular_shelf_price,
                observation.weight_price_type.value
                if observation.weight_price_type is not None
                else None,
            )
            actual_v2 = (
                (v2.identification_evidence, v2.regular_shelf_price, v2.weight_price_type)
                if v2 is not None
                else (None, None, None)
            )
            if expected_v2 != actual_v2:
                raise ValueError("physical observation ID already exists with different V2 data")
            return existing
        row = PhysicalPriceObservationModel(id=observation.id, **values)
        self.session.add(row)
        self.session.flush()
        if observation.identification_evidence is not None:
            self.session.add(
                PhysicalObservationV2EvidenceModel(
                    observation_id=observation.id,
                    identification_evidence=observation.identification_evidence.value,
                    regular_shelf_price=observation.regular_shelf_price,
                    weight_price_type=(
                        observation.weight_price_type.value
                        if observation.weight_price_type is not None
                        else None
                    ),
                )
            )
            self.session.flush()
        return row

    def get(self, observation_id: str) -> PhysicalPriceObservationModel | None:
        return self.session.get(PhysicalPriceObservationModel, observation_id)

    def list_for_store(
        self,
        physical_store_id: str,
        *,
        limit: int = 1000,
        since: datetime | None = None,
    ) -> list[PhysicalPriceObservationModel]:
        if not 1 <= limit <= 50_000:
            raise ValueError("limit must be 1..50000")
        statement = select(PhysicalPriceObservationModel).where(
            PhysicalPriceObservationModel.physical_store_id == physical_store_id
        )
        if since is not None:
            statement = statement.where(
                PhysicalPriceObservationModel.observed_at >= _aware(since, field="since")
            )
        return list(
            self.session.scalars(
                statement.order_by(
                    PhysicalPriceObservationModel.observed_at.desc(),
                    PhysicalPriceObservationModel.id,
                ).limit(limit)
            )
        )

    def list_for_session(self, session_id: str) -> list[PhysicalPriceObservationModel]:
        return list(
            self.session.scalars(
                select(PhysicalPriceObservationModel)
                .where(PhysicalPriceObservationModel.validation_session_id == session_id)
                .order_by(
                    PhysicalPriceObservationModel.observed_at,
                    PhysicalPriceObservationModel.id,
                )
            )
        )

    def list_for_scope(
        self,
        *,
        chain: Chain | str | None = None,
        city: str | None = None,
        limit: int = 10_000,
        since: datetime | None = None,
    ) -> list[PhysicalPriceObservationModel]:
        if not 1 <= limit <= 50_000:
            raise ValueError("limit must be 1..50000")
        statement = select(PhysicalPriceObservationModel).join(
            PhysicalStoreModel,
            PhysicalStoreModel.id == PhysicalPriceObservationModel.physical_store_id,
        )
        if chain is not None:
            statement = statement.where(PhysicalStoreModel.chain == _value(chain))
        if city is not None:
            city_key = city.casefold().strip()
            if not city_key:
                raise ValueError("city must not be blank")
            statement = statement.where(
                func.lower(func.trim(PhysicalStoreModel.city)) == city_key
            )
        if since is not None:
            statement = statement.where(
                PhysicalPriceObservationModel.observed_at >= _aware(since, field="since")
            )
        return list(
            self.session.scalars(
                statement.order_by(
                    PhysicalPriceObservationModel.observed_at.desc(),
                    PhysicalPriceObservationModel.id,
                ).limit(limit)
            )
        )


def _physical_observation_amendment_from_row(
    row: PhysicalObservationAmendmentModel,
) -> PhysicalObservationAmendment:
    try:
        payload = PhysicalPriceObservation.model_validate_json(row.payload_json)
    except ValueError as exc:
        raise PhysicalObservationAmendmentIntegrityError(
            f"amendment {row.id!r} contains an invalid observation payload"
        ) from exc
    canonical_payload = canonical_physical_observation_payload(payload)
    if canonical_payload != row.payload_json:
        raise PhysicalObservationAmendmentIntegrityError(
            f"amendment {row.id!r} payload is not canonical JSON"
        )
    if physical_observation_payload_sha256(payload) != row.payload_sha256:
        raise PhysicalObservationAmendmentIntegrityError(
            f"amendment {row.id!r} payload hash does not match"
        )
    try:
        return PhysicalObservationAmendment(
            id=row.id,
            validation_session_id=row.validation_session_id,
            validation_session_item_id=row.validation_session_item_id,
            kind=row.kind,
            payload=payload,
            payload_schema_version=row.payload_schema_version,
            payload_sha256=row.payload_sha256,
            base_observation_id=row.base_observation_id,
            supersedes_amendment_id=row.supersedes_amendment_id,
            observed_at=row.observed_at,
            observed_at_precision=row.observed_at_precision,
            reason=row.reason,
            source=row.source,
            reference=row.reference,
            client_request_id=row.client_request_id,
            created_at=row.created_at,
        )
    except ValueError as exc:
        raise PhysicalObservationAmendmentIntegrityError(
            f"amendment {row.id!r} violates its immutable domain contract"
        ) from exc


class PhysicalObservationAmendmentRepository:
    """Append and read post-completion observation evidence without rewrites."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, amendment_id: str) -> PhysicalObservationAmendment | None:
        row = self.session.get(PhysicalObservationAmendmentModel, amendment_id)
        return _physical_observation_amendment_from_row(row) if row is not None else None

    def idempotency_lookup(
        self,
        session_id: str,
        item_id: str,
        client_request_id: str,
    ) -> PhysicalObservationAmendment | None:
        row = self.session.scalar(
            select(PhysicalObservationAmendmentModel).where(
                PhysicalObservationAmendmentModel.validation_session_id == session_id,
                PhysicalObservationAmendmentModel.validation_session_item_id == item_id,
                PhysicalObservationAmendmentModel.client_request_id == client_request_id,
            )
        )
        return _physical_observation_amendment_from_row(row) if row is not None else None

    def amendments_for_session(
        self,
        session_id: str,
    ) -> tuple[PhysicalObservationAmendment, ...]:
        rows = self.session.scalars(
            select(PhysicalObservationAmendmentModel)
            .where(
                PhysicalObservationAmendmentModel.validation_session_id == session_id
            )
            .order_by(
                PhysicalObservationAmendmentModel.created_at,
                PhysicalObservationAmendmentModel.id,
            )
        )
        return tuple(_physical_observation_amendment_from_row(row) for row in rows)

    def amendments_for_item(
        self,
        item_id: str,
    ) -> tuple[PhysicalObservationAmendment, ...]:
        rows = self.session.scalars(
            select(PhysicalObservationAmendmentModel)
            .where(
                PhysicalObservationAmendmentModel.validation_session_item_id == item_id
            )
            .order_by(
                PhysicalObservationAmendmentModel.created_at,
                PhysicalObservationAmendmentModel.id,
            )
        )
        return tuple(_physical_observation_amendment_from_row(row) for row in rows)

    def head_for_item(self, item_id: str) -> PhysicalObservationAmendment | None:
        amendments = self.amendments_for_item(item_id)
        superseded_ids = {
            amendment.supersedes_amendment_id
            for amendment in amendments
            if amendment.supersedes_amendment_id is not None
        }
        heads = tuple(
            amendment for amendment in amendments if amendment.id not in superseded_ids
        )
        if len(heads) > 1:
            raise PhysicalObservationAmendmentIntegrityError(
                f"item {item_id!r} has multiple amendment heads"
            )
        return heads[0] if heads else None

    def add_amendment(
        self,
        amendment: PhysicalObservationAmendment,
    ) -> PhysicalObservationAmendment:
        replay = self.idempotency_lookup(
            amendment.validation_session_id,
            amendment.validation_session_item_id,
            amendment.client_request_id,
        )
        if replay is not None:
            if replay.model_dump(exclude={"created_at"}) != amendment.model_dump(
                exclude={"created_at"}
            ):
                raise ValueError(
                    "client_request_id already exists with a different amendment"
                )
            return replay
        if self.session.get(PhysicalObservationAmendmentModel, amendment.id) is not None:
            raise ValueError("physical observation amendment ID already exists")

        validation_session = self.session.get(
            PhysicalValidationSessionModel,
            amendment.validation_session_id,
        )
        if validation_session is None:
            raise LookupError(
                f"physical validation session {amendment.validation_session_id!r} "
                "does not exist"
            )
        if validation_session.status != PhysicalValidationSessionStatus.COMPLETED.value:
            raise ValueError("physical observation amendments require a completed session")
        if validation_session.completed_at is None:
            raise PhysicalObservationAmendmentIntegrityError(
                "completed validation session has no completion timestamp"
            )
        session_item = self.session.get(
            PhysicalValidationSessionItemModel,
            amendment.validation_session_item_id,
        )
        if session_item is None or session_item.session_id != amendment.validation_session_id:
            raise LookupError("physical validation session item does not belong to session")
        if amendment.payload.physical_store_id != validation_session.physical_store_id:
            raise ValueError("amendment payload physical store does not match session")
        if (
            amendment.payload.immutable_candidate_set_sha256
            != session_item.candidate_set_sha256
        ):
            raise ValueError("amendment payload candidate set does not match session item")
        if amendment.observed_at_precision is PhysicalObservationTimePrecision.VISIT_WINDOW and not (
            validation_session.started_at
            <= amendment.observed_at
            <= validation_session.completed_at
        ):
            raise ValueError("visit-window observation must fall within the session visit")

        current_head = self.head_for_item(amendment.validation_session_item_id)
        expected_head_id = current_head.id if current_head is not None else None
        if amendment.supersedes_amendment_id != expected_head_id:
            raise PhysicalObservationAmendmentHeadConflict(
                expected_head_id=expected_head_id,
                supplied_head_id=amendment.supersedes_amendment_id,
            )

        base_observation: PhysicalPriceObservationModel | None = None
        if amendment.base_observation_id is not None:
            base_observation = self.session.get(
                PhysicalPriceObservationModel,
                amendment.base_observation_id,
            )
            if base_observation is None:
                raise LookupError(
                    f"base observation {amendment.base_observation_id!r} does not exist"
                )
            if (
                base_observation.validation_session_id
                != amendment.validation_session_id
                or base_observation.validation_session_item_id
                != amendment.validation_session_item_id
            ):
                raise ValueError("base observation does not belong to amendment item")
            if amendment.payload.id != base_observation.id:
                raise ValueError("correction payload must retain the base observation ID")

        item_observation_id = self.session.scalar(
            select(PhysicalPriceObservationModel.id).where(
                PhysicalPriceObservationModel.validation_session_id
                == amendment.validation_session_id,
                PhysicalPriceObservationModel.validation_session_item_id
                == amendment.validation_session_item_id,
            )
        )
        if amendment.kind is PhysicalObservationAmendmentKind.LATE_CAPTURE:
            if item_observation_id is not None:
                raise ValueError("late capture cannot replace an existing observation")
        elif current_head is None:
            if base_observation is None or item_observation_id != base_observation.id:
                raise ValueError("initial correction must identify the item's base observation")
        else:
            item_amendments = self.amendments_for_item(
                amendment.validation_session_item_id
            )
            lineage_base_ids = {
                row.base_observation_id
                for row in item_amendments
                if row.base_observation_id is not None
            }
            if len(lineage_base_ids) > 1:
                raise PhysicalObservationAmendmentIntegrityError(
                    "amendment chain contains multiple base observations"
                )
            lineage_base_id = next(iter(lineage_base_ids), None)
            if lineage_base_id is None:
                if amendment.base_observation_id is not None:
                    raise ValueError(
                        "late-capture correction cannot introduce a base observation"
                    )
            elif amendment.base_observation_id not in {None, lineage_base_id}:
                raise ValueError("correction must preserve the amendment chain base")
            if amendment.payload.id != current_head.payload.id:
                raise ValueError("correction payload must retain the amendment chain ID")

        canonical_payload = canonical_physical_observation_payload(amendment.payload)
        row = PhysicalObservationAmendmentModel(
            id=amendment.id,
            validation_session_id=amendment.validation_session_id,
            validation_session_item_id=amendment.validation_session_item_id,
            kind=amendment.kind.value,
            payload_json=canonical_payload,
            payload_schema_version=amendment.payload_schema_version,
            payload_sha256=amendment.payload_sha256,
            base_observation_id=amendment.base_observation_id,
            supersedes_amendment_id=amendment.supersedes_amendment_id,
            observed_at=amendment.observed_at,
            observed_at_precision=amendment.observed_at_precision.value,
            reason=amendment.reason,
            source=amendment.source,
            reference=amendment.reference,
            client_request_id=amendment.client_request_id,
            created_at=amendment.created_at or utcnow(),
        )
        self.session.add(row)
        self.session.flush()
        return _physical_observation_amendment_from_row(row)


def digital_candidate_sha256(candidate: DigitalPriceCandidate) -> str:
    payload = json.dumps(
        candidate.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def digital_candidate_set_sha256(
    candidates: Sequence[DigitalPriceCandidate],
) -> str:
    fingerprints = sorted(digital_candidate_sha256(candidate) for candidate in candidates)
    return hashlib.sha256("\n".join(fingerprints).encode("ascii")).hexdigest()


def validation_session_suggestion_sha256(
    items: Sequence[PhysicalValidationSessionItem],
) -> str:
    payload = [
        {
            "ordinal": item.ordinal,
            "stratum": item.stratum.value,
            "target_gtin": item.target_gtin,
            "target_product_name": item.target_product_name,
            "target_brand": item.target_brand,
            "target_category": item.target_category,
            "target_package_description": item.target_package_description,
            "target_product_id": item.target_product_id,
            "target_source_provider": item.target_source_provider,
            "target_grocery_context_id": item.target_grocery_context_id,
            "target_external_product_id": item.target_external_product_id,
            "target_store_external_id": item.target_store_external_id,
            "target_sale_model": item.target_sale_model.value,
            "identifier_status": item.identifier_status.value,
            "reasons": list(item.reasons),
            "candidate_set_sha256": item.candidate_set_sha256,
        }
        for item in sorted(items, key=lambda row: row.ordinal)
    ]
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class PhysicalValidationSessionReconciliation:
    id: str
    validation_session_id: str
    source_provider: str
    grocery_context_id: str
    source_snapshot_id: str
    reason: str
    reconciled_at: datetime


@dataclass(frozen=True, slots=True)
class PhysicalValidationSnapshotLock:
    id: str
    validation_session_id: str
    source_provider: str
    grocery_context_id: str
    source_snapshot_id: str
    candidate_count: int
    evidence_sha256: str
    locked_at: datetime


@dataclass(frozen=True, slots=True)
class PhysicalValidationComparisonVersion:
    id: str
    validation_session_id: str
    version_number: int
    version_kind: str
    source_snapshot_ids: tuple[str, ...]
    evidence_sha256: str
    freshness_threshold_hours: Decimal
    reason: str
    created_at: datetime


def _physical_validation_reconciliation_from_row(
    row: PhysicalValidationSessionReconciliationModel,
) -> PhysicalValidationSessionReconciliation:
    return PhysicalValidationSessionReconciliation(
        id=row.id,
        validation_session_id=row.validation_session_id,
        source_provider=row.source_provider,
        grocery_context_id=row.grocery_context_id,
        source_snapshot_id=row.source_snapshot_id,
        reason=row.reason,
        reconciled_at=row.reconciled_at,
    )


def _physical_validation_snapshot_lock_from_row(
    row: PhysicalValidationSnapshotLockModel,
) -> PhysicalValidationSnapshotLock:
    return PhysicalValidationSnapshotLock(
        id=row.id,
        validation_session_id=row.validation_session_id,
        source_provider=row.source_provider,
        grocery_context_id=row.grocery_context_id,
        source_snapshot_id=row.source_snapshot_id,
        candidate_count=row.candidate_count,
        evidence_sha256=row.evidence_sha256,
        locked_at=row.locked_at,
    )


def _physical_validation_comparison_version_from_row(
    row: PhysicalValidationComparisonVersionModel,
) -> PhysicalValidationComparisonVersion:
    return PhysicalValidationComparisonVersion(
        id=row.id,
        validation_session_id=row.validation_session_id,
        version_number=row.version_number,
        version_kind=row.version_kind,
        source_snapshot_ids=tuple(row.source_snapshot_ids),
        evidence_sha256=row.evidence_sha256,
        freshness_threshold_hours=row.freshness_threshold_hours,
        reason=row.reason,
        created_at=row.created_at,
    )


def _digital_candidate_from_session_row(
    row: PhysicalValidationSessionCandidateModel,
) -> DigitalPriceCandidate:
    return DigitalPriceCandidate(
        physical_store_id=row.physical_store_id,
        grocery_context_id=row.grocery_context_id,
        source_provider=row.source_provider,
        source_snapshot_id=row.source_snapshot_id,
        observed_at=row.observed_at,
        product_id=row.product_id,
        product_name=row.product_name,
        brand=row.brand,
        category=row.category,
        package_description=row.package_description,
        gtin=row.gtin,
        current_price=row.current_price,
        regular_price=row.regular_price,
        member_price=row.member_price,
        comparison_price=row.comparison_price,
        comparison_unit=row.comparison_unit,
        promotion_type=PromotionType(row.promotion_type) if row.promotion_type else None,
        member_only=row.member_only,
        multibuy_quantity=row.multibuy_quantity,
        multibuy_total_price=row.multibuy_total_price,
        sale_model=SaleModel(row.sale_model),
        common_product_score=row.common_product_score,
        recent_price_change=row.recent_price_change,
    )


class PhysicalValidationSessionRepository:
    """Persist one immutable, voluntary field sample and its digital evidence."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        validation_session: PhysicalValidationSession,
        items: Sequence[PhysicalValidationSessionItem],
    ) -> PhysicalValidationSessionModel:
        physical_store = self.session.get(
            PhysicalStoreModel,
            validation_session.physical_store_id,
        )
        if physical_store is None:
            raise LookupError("physical store does not exist")
        if not physical_store.is_active:
            raise ValueError("physical store is not active")
        if validation_session.chain != physical_store.chain:
            raise ValueError("validation session chain does not match physical store")
        if validation_session.store_name != physical_store.name:
            raise ValueError("validation session name does not match physical store")
        if not items:
            raise ValueError("validation session requires at least one suggestion")
        if len(items) > validation_session.target_count:
            raise ValueError("suggestions exceed target_count")
        if len({item.ordinal for item in items}) != len(items):
            raise ValueError("session item ordinals must be unique")
        for item in items:
            if item.session_id != validation_session.id:
                raise ValueError("session item belongs to another session")
            if digital_candidate_set_sha256(item.candidates) != item.candidate_set_sha256:
                raise ValueError("session candidate set fingerprint mismatch")
        if (
            validation_session_suggestion_sha256(items)
            != validation_session.suggestion_set_sha256
        ):
            raise ValueError("session suggestion fingerprint mismatch")
        if self.get_model(validation_session.id) is not None:
            raise ValueError("validation session already exists")

        row = PhysicalValidationSessionModel(
            id=validation_session.id,
            physical_store_id=validation_session.physical_store_id,
            chain=validation_session.chain,
            store_name=validation_session.store_name,
            status=validation_session.status.value,
            blind_capture=validation_session.blind_capture,
            target_count=validation_session.target_count,
            sampling_strategy=validation_session.sampling_strategy,
            notes=validation_session.notes,
            suggestion_set_sha256=validation_session.suggestion_set_sha256,
            started_at=validation_session.started_at,
            completed_at=validation_session.completed_at,
        )
        self.session.add(row)
        self.session.flush()
        for item in sorted(items, key=lambda value: value.ordinal):
            target_external_product_id = item.target_external_product_id
            target_store_external_id = item.target_store_external_id
            if (
                item.target_source_provider == SourceProvider.OWN.value
                and item.target_product_id is not None
            ):
                target_product = self.session.get(ProductModel, item.target_product_id)
                if target_product is None:
                    raise LookupError("selected OWN session product does not exist")
                if target_product.chain != validation_session.chain:
                    raise ValueError("selected session product belongs to another chain")
                target_external_product_id = target_product.external_product_id
                target_store_external_id = target_product.store_external_id
            identifier_evidence_id: str | None = None
            identifier_status = item.identifier_status
            if (
                item.target_gtin is None
                and identifier_status
                is not SessionItemIdentifierStatus.NOT_REQUIRED_WEIGHT
                and target_external_product_id is not None
                and target_store_external_id is not None
                and item.target_source_provider is not None
            ):
                cached = ProductIdentifierEvidenceRepository(self.session).for_product(
                    chain=Chain(validation_session.chain),
                    source_provider=item.target_source_provider,
                    scope_key=target_store_external_id,
                    external_product_id=target_external_product_id,
                )
                distinct_gtins = {row.identifier_value for row in cached}
                if len(distinct_gtins) == 1:
                    identifier_status = SessionItemIdentifierStatus.KNOWN_GTIN
                    identifier_evidence_id = cached[0].id
                elif len(distinct_gtins) > 1:
                    identifier_status = SessionItemIdentifierStatus.AMBIGUOUS_GTIN
            item_row = PhysicalValidationSessionItemModel(
                id=item.id,
                session_id=item.session_id,
                ordinal=item.ordinal,
                stratum=item.stratum.value,
                target_gtin=item.target_gtin,
                target_product_name=item.target_product_name,
                target_brand=item.target_brand,
                target_category=item.target_category,
                target_package_description=item.target_package_description,
                reasons=list(item.reasons),
                candidate_set_sha256=item.candidate_set_sha256,
            )
            self.session.add(item_row)
            self.session.flush()
            self.session.add(
                PhysicalValidationSessionItemIdentifierModel(
                    session_item_id=item.id,
                    target_product_id=item.target_product_id,
                    target_source_provider=item.target_source_provider,
                    target_grocery_context_id=item.target_grocery_context_id,
                    target_external_product_id=target_external_product_id,
                    target_store_external_id=target_store_external_id,
                    target_sale_model=item.target_sale_model.value,
                    identifier_status=identifier_status.value,
                    identifier_evidence_id=identifier_evidence_id,
                )
            )
            for candidate in item.candidates:
                fingerprint = digital_candidate_sha256(candidate)
                self.session.add(
                    PhysicalValidationSessionCandidateModel(
                        id=hashlib.sha256(
                            f"{item.id}:{fingerprint}".encode()
                        ).hexdigest()[:32],
                        session_item_id=item.id,
                        physical_store_id=candidate.physical_store_id,
                        grocery_context_id=candidate.grocery_context_id,
                        source_provider=candidate.source_provider,
                        source_snapshot_id=candidate.source_snapshot_id,
                        observed_at=candidate.observed_at,
                        product_id=candidate.product_id,
                        product_name=candidate.product_name,
                        brand=candidate.brand,
                        category=candidate.category,
                        package_description=candidate.package_description,
                        gtin=candidate.gtin,
                        current_price=candidate.current_price,
                        regular_price=candidate.regular_price,
                        member_price=candidate.member_price,
                        comparison_price=candidate.comparison_price,
                        comparison_unit=candidate.comparison_unit,
                        promotion_type=(
                            candidate.promotion_type.value
                            if candidate.promotion_type is not None
                            else None
                        ),
                        member_only=candidate.member_only,
                        multibuy_quantity=candidate.multibuy_quantity,
                        multibuy_total_price=candidate.multibuy_total_price,
                        sale_model=candidate.sale_model.value,
                        common_product_score=candidate.common_product_score,
                        recent_price_change=candidate.recent_price_change,
                        candidate_sha256=fingerprint,
                    )
                )
        self.session.flush()
        self._add_snapshot_locks(validation_session, items)
        self._create_identifier_preparation(validation_session.id, items)
        return row

    def _add_snapshot_locks(
        self,
        validation_session: PhysicalValidationSession,
        items: Sequence[PhysicalValidationSessionItem],
    ) -> tuple[PhysicalValidationSnapshotLock, ...]:
        grouped: dict[tuple[str, str, str], list[str]] = {}
        for item in items:
            for candidate in item.candidates:
                key = (
                    candidate.source_provider,
                    candidate.grocery_context_id,
                    candidate.source_snapshot_id,
                )
                grouped.setdefault(key, []).append(
                    f"{item.id}:{digital_candidate_sha256(candidate)}"
                )
        if not grouped:
            raise ValueError("validation session has no snapshot evidence to lock")
        locks: list[PhysicalValidationSnapshotLock] = []
        for (provider, context_id, snapshot_id), fingerprints in sorted(grouped.items()):
            evidence_sha256 = hashlib.sha256(
                "\n".join(sorted(fingerprints)).encode()
            ).hexdigest()
            row = PhysicalValidationSnapshotLockModel(
                id=hashlib.sha256(
                    (
                        f"{validation_session.id}:{provider}:{context_id}:"
                        f"{snapshot_id}:{evidence_sha256}"
                    ).encode()
                ).hexdigest()[:32],
                validation_session_id=validation_session.id,
                source_provider=provider,
                grocery_context_id=context_id,
                source_snapshot_id=snapshot_id,
                candidate_count=len(fingerprints),
                evidence_sha256=evidence_sha256,
                locked_at=validation_session.started_at,
            )
            self.session.add(row)
            locks.append(_physical_validation_snapshot_lock_from_row(row))
        self.session.flush()
        return tuple(locks)

    def snapshot_locks(
        self,
        session_id: str,
    ) -> tuple[PhysicalValidationSnapshotLock, ...]:
        rows = self.session.scalars(
            select(PhysicalValidationSnapshotLockModel)
            .where(
                PhysicalValidationSnapshotLockModel.validation_session_id == session_id
            )
            .order_by(
                PhysicalValidationSnapshotLockModel.source_provider,
                PhysicalValidationSnapshotLockModel.grocery_context_id,
                PhysicalValidationSnapshotLockModel.source_snapshot_id,
            )
        )
        return tuple(_physical_validation_snapshot_lock_from_row(row) for row in rows)

    def ensure_snapshot_locks(
        self,
        session_id: str,
    ) -> tuple[PhysicalValidationSnapshotLock, ...]:
        """Backfill only the compact lock for a legacy immutable session.

        Candidate and observation rows are read but never updated.  If a
        partial/different lock already exists, fail closed instead of silently
        changing the official comparison boundary.
        """

        preview = self.preview_snapshot_locks(session_id)
        existing = self.snapshot_locks(session_id)
        if existing:
            return existing
        locks: list[PhysicalValidationSnapshotLock] = []
        for lock in preview:
            row = PhysicalValidationSnapshotLockModel(
                id=lock.id,
                validation_session_id=lock.validation_session_id,
                source_provider=lock.source_provider,
                grocery_context_id=lock.grocery_context_id,
                source_snapshot_id=lock.source_snapshot_id,
                candidate_count=lock.candidate_count,
                evidence_sha256=lock.evidence_sha256,
                locked_at=lock.locked_at,
            )
            self.session.add(row)
            locks.append(_physical_validation_snapshot_lock_from_row(row))
        self.session.flush()
        return tuple(locks)

    def preview_snapshot_locks(
        self,
        session_id: str,
    ) -> tuple[PhysicalValidationSnapshotLock, ...]:
        """Derive the exact lock contract without writing legacy session rows."""

        validation_session = self.get(session_id)
        if validation_session is None:
            raise LookupError("validation session does not exist")
        grouped: dict[tuple[str, str, str], list[str]] = {}
        candidate_rows = self.session.scalars(
            select(PhysicalValidationSessionCandidateModel)
            .join(PhysicalValidationSessionItemModel)
            .where(PhysicalValidationSessionItemModel.session_id == session_id)
        )
        for candidate in candidate_rows:
            key = (
                candidate.source_provider,
                candidate.grocery_context_id,
                candidate.source_snapshot_id,
            )
            # Use the original fingerprint stored with the immutable row.  A
            # database Numeric round-trip may add trailing zeroes to Decimal
            # values, but must not change the byte-level lock identity.
            grouped.setdefault(key, []).append(
                f"{candidate.session_item_id}:{candidate.candidate_sha256}"
            )
        expected = {
            key: (
                len(fingerprints),
                hashlib.sha256("\n".join(sorted(fingerprints)).encode()).hexdigest(),
            )
            for key, fingerprints in grouped.items()
        }
        existing = self.snapshot_locks(session_id)
        if existing:
            actual = {
                (
                    row.source_provider,
                    row.grocery_context_id,
                    row.source_snapshot_id,
                ): (row.candidate_count, row.evidence_sha256)
                for row in existing
            }
            if actual != expected:
                raise ValueError("stored snapshot lock differs from immutable candidates")
            return existing
        if not expected:
            raise ValueError("validation session has no snapshot evidence to lock")
        locks: list[PhysicalValidationSnapshotLock] = []
        for (provider, context_id, snapshot_id), (
            candidate_count,
            evidence_sha256,
        ) in sorted(expected.items()):
            lock = PhysicalValidationSnapshotLock(
                id=hashlib.sha256(
                    (
                        f"{validation_session.id}:{provider}:{context_id}:"
                        f"{snapshot_id}:{evidence_sha256}"
                    ).encode()
                ).hexdigest()[:32],
                validation_session_id=session_id,
                source_provider=provider,
                grocery_context_id=context_id,
                source_snapshot_id=snapshot_id,
                candidate_count=candidate_count,
                evidence_sha256=evidence_sha256,
                locked_at=validation_session.started_at,
            )
            locks.append(lock)
        return tuple(locks)

    def comparison_versions(
        self,
        session_id: str,
    ) -> tuple[PhysicalValidationComparisonVersion, ...]:
        rows = self.session.scalars(
            select(PhysicalValidationComparisonVersionModel)
            .where(
                PhysicalValidationComparisonVersionModel.validation_session_id
                == session_id
            )
            .order_by(PhysicalValidationComparisonVersionModel.version_number)
        )
        return tuple(
            _physical_validation_comparison_version_from_row(row) for row in rows
        )

    def add_comparison_version(
        self,
        *,
        session_id: str,
        version_kind: str,
        source_snapshot_ids: Sequence[str],
        evidence_sha256: str,
        freshness_threshold_hours: Decimal,
        reason: str,
        created_at: datetime,
    ) -> PhysicalValidationComparisonVersion:
        if self.get_model(session_id) is None:
            raise LookupError("validation session does not exist")
        normalized_kind = version_kind.strip()
        if normalized_kind not in {
            "amended_physical_evidence",
            "official_snapshot_lock",
            "post_visit_diagnostic",
        }:
            raise ValueError("unsupported physical comparison version kind")
        normalized_snapshots = tuple(sorted(set(source_snapshot_ids)))
        if not normalized_snapshots or any(not value.strip() for value in normalized_snapshots):
            raise ValueError("comparison version requires snapshot IDs")
        if not re.fullmatch(r"[0-9a-f]{64}", evidence_sha256):
            raise ValueError("comparison version evidence hash must be SHA-256")
        threshold = Decimal(freshness_threshold_hours)
        if not threshold.is_finite() or threshold <= 0:
            raise ValueError("freshness threshold must be positive")
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise ValueError("comparison version reason is required")
        timestamp = _aware(created_at, field="created_at")
        existing_versions = self.comparison_versions(session_id)
        expected = (
            normalized_kind,
            normalized_snapshots,
            evidence_sha256,
            threshold,
            normalized_reason,
        )
        for existing in existing_versions:
            actual = (
                existing.version_kind,
                existing.source_snapshot_ids,
                existing.evidence_sha256,
                existing.freshness_threshold_hours,
                existing.reason,
            )
            if actual == expected:
                return existing
        if normalized_kind == "official_snapshot_lock" and any(
            row.version_kind == normalized_kind for row in existing_versions
        ):
            raise ValueError("official comparison version is already locked")
        version_number = (
            max((row.version_number for row in existing_versions), default=0) + 1
        )
        row = PhysicalValidationComparisonVersionModel(
            id=hashlib.sha256(
                (
                    f"{session_id}:{version_number}:{normalized_kind}:"
                    f"{evidence_sha256}"
                ).encode()
            ).hexdigest()[:32],
            validation_session_id=session_id,
            version_number=version_number,
            version_kind=normalized_kind,
            source_snapshot_ids=list(normalized_snapshots),
            evidence_sha256=evidence_sha256,
            freshness_threshold_hours=threshold,
            reason=normalized_reason,
            created_at=timestamp,
        )
        self.session.add(row)
        self.session.flush()
        return _physical_validation_comparison_version_from_row(row)

    def _create_identifier_preparation(
        self,
        session_id: str,
        items: Sequence[PhysicalValidationSessionItem],
    ) -> None:
        self._create_identifier_preparation_from_state(
            session_id,
            target_products=len(items),
        )

    def _create_identifier_preparation_from_state(
        self,
        session_id: str,
        *,
        target_products: int,
    ) -> None:
        states = tuple(
            SessionItemIdentifierStatus(value)
            for value in self.session.scalars(
                select(PhysicalValidationSessionItemIdentifierModel.identifier_status)
                .join(PhysicalValidationSessionItemModel)
                .where(PhysicalValidationSessionItemModel.session_id == session_id)
            )
        )
        weight = sum(
            state is SessionItemIdentifierStatus.NOT_REQUIRED_WEIGHT for state in states
        )
        known = sum(state is SessionItemIdentifierStatus.KNOWN_GTIN for state in states)
        cache_hits = int(
            self.session.scalar(
                select(func.count())
                .select_from(PhysicalValidationSessionItemIdentifierModel)
                .join(PhysicalValidationSessionItemModel)
                .where(
                    PhysicalValidationSessionItemModel.session_id == session_id,
                    PhysicalValidationSessionItemIdentifierModel.identifier_evidence_id.is_not(
                        None
                    ),
                )
            )
            or 0
        )
        self.session.add(
            PhysicalIdentifierPreparationModel(
                validation_session_id=session_id,
                target_products=target_products,
                known_gtin_before=known,
                cache_hits=cache_hits,
                weight_no_gtin_required=weight,
                true_unresolved=target_products - known - weight,
                request_limit=min(target_products + 2, 100),
            )
        )
        self.session.flush()

    def ensure_legacy_identifier_state(self, session_id: str) -> bool:
        """Add V2 companion state for a session created by the V1 server.

        The field UI and backend may be deployed at different moments during a
        local PoC.  V1 sessions have immutable items/candidates but no V2
        identifier companion rows.  Derivation is deliberately conservative:
        target identity is retained only when every frozen candidate has the
        same provider/context/product tuple, while sale model is retained only
        when it is unanimous.  Nothing is guessed by candidate order.

        The caller owns the transaction.  Returning ``True`` lets an API write
        or compatibility GET explicitly commit this additive backfill.
        """

        validation_session = self.get_model(session_id)
        if validation_session is None:
            raise LookupError("validation session does not exist")
        item_rows = list(
            self.session.scalars(
                select(PhysicalValidationSessionItemModel)
                .where(PhysicalValidationSessionItemModel.session_id == session_id)
                .order_by(PhysicalValidationSessionItemModel.ordinal)
            )
        )
        existing_item_ids = set(
            self.session.scalars(
                select(PhysicalValidationSessionItemIdentifierModel.session_item_id).where(
                    PhysicalValidationSessionItemIdentifierModel.session_item_id.in_(
                        [row.id for row in item_rows]
                    )
                )
            )
        )
        changed = False
        for item_row in item_rows:
            if item_row.id in existing_item_ids:
                continue
            candidates = self.candidates_for_item(item_row.id)
            identity_keys = {
                (
                    candidate.source_provider,
                    candidate.grocery_context_id,
                    candidate.product_id,
                )
                for candidate in candidates
            }
            target_product_id: str | None = None
            target_source_provider: str | None = None
            target_grocery_context_id: str | None = None
            target_external_product_id: str | None = None
            target_store_external_id: str | None = None
            if len(identity_keys) == 1:
                (
                    target_source_provider,
                    target_grocery_context_id,
                    target_product_id,
                ) = next(iter(identity_keys))
                if target_source_provider == SourceProvider.OWN.value:
                    target_product = self.session.get(ProductModel, target_product_id)
                    if (
                        target_product is not None
                        and target_product.chain == validation_session.chain
                    ):
                        target_external_product_id = target_product.external_product_id
                        target_store_external_id = target_product.store_external_id
                    else:
                        # A source product ID is not interchangeable with our
                        # internal ProductModel ID.  Fail closed if lineage is
                        # not present in this database.
                        target_product_id = None
                        target_source_provider = None
                        target_grocery_context_id = None

            sale_models = {candidate.sale_model for candidate in candidates}
            target_sale_model = (
                next(iter(sale_models)) if len(sale_models) == 1 else SaleModel.UNKNOWN
            )
            if target_sale_model in {
                SaleModel.SOLD_BY_WEIGHT,
                SaleModel.VARIABLE_WEIGHT_PACKAGE,
            }:
                identifier_status = SessionItemIdentifierStatus.NOT_REQUIRED_WEIGHT
            elif item_row.target_gtin:
                identifier_status = SessionItemIdentifierStatus.KNOWN_GTIN
            else:
                identifier_status = SessionItemIdentifierStatus.UNKNOWN_GTIN

            identifier_evidence_id: str | None = None
            if (
                identifier_status is SessionItemIdentifierStatus.UNKNOWN_GTIN
                and target_source_provider is not None
                and target_external_product_id is not None
                and target_store_external_id is not None
            ):
                cached = ProductIdentifierEvidenceRepository(self.session).for_product(
                    chain=Chain(validation_session.chain),
                    source_provider=target_source_provider,
                    scope_key=target_store_external_id,
                    external_product_id=target_external_product_id,
                )
                distinct_gtins = {row.identifier_value for row in cached}
                if len(distinct_gtins) == 1:
                    identifier_status = SessionItemIdentifierStatus.KNOWN_GTIN
                    identifier_evidence_id = cached[0].id
                elif len(distinct_gtins) > 1:
                    identifier_status = SessionItemIdentifierStatus.AMBIGUOUS_GTIN

            self.session.add(
                PhysicalValidationSessionItemIdentifierModel(
                    session_item_id=item_row.id,
                    target_product_id=target_product_id,
                    target_source_provider=target_source_provider,
                    target_grocery_context_id=target_grocery_context_id,
                    target_external_product_id=target_external_product_id,
                    target_store_external_id=target_store_external_id,
                    target_sale_model=target_sale_model.value,
                    identifier_status=identifier_status.value,
                    identifier_evidence_id=identifier_evidence_id,
                )
            )
            changed = True

        if changed:
            self.session.flush()
        if self.session.get(PhysicalIdentifierPreparationModel, session_id) is None:
            self._create_identifier_preparation_from_state(
                session_id,
                target_products=len(item_rows),
            )
            changed = True
        return changed

    def get_model(self, session_id: str) -> PhysicalValidationSessionModel | None:
        return self.session.get(PhysicalValidationSessionModel, session_id)

    def get(self, session_id: str) -> PhysicalValidationSession | None:
        row = self.get_model(session_id)
        if row is None:
            return None
        return PhysicalValidationSession(
            id=row.id,
            physical_store_id=row.physical_store_id,
            chain=row.chain,
            store_name=row.store_name,
            status=PhysicalValidationSessionStatus(row.status),
            blind_capture=row.blind_capture,
            target_count=row.target_count,
            sampling_strategy=row.sampling_strategy,
            notes=row.notes,
            suggestion_set_sha256=row.suggestion_set_sha256,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )

    def item_model(
        self,
        session_id: str,
        item_id: str,
    ) -> PhysicalValidationSessionItemModel | None:
        return self.session.scalar(
            select(PhysicalValidationSessionItemModel).where(
                PhysicalValidationSessionItemModel.id == item_id,
                PhysicalValidationSessionItemModel.session_id == session_id,
            )
        )

    def candidates_for_item(self, item_id: str) -> tuple[DigitalPriceCandidate, ...]:
        rows = self.session.scalars(
            select(PhysicalValidationSessionCandidateModel)
            .where(PhysicalValidationSessionCandidateModel.session_item_id == item_id)
            .order_by(
                PhysicalValidationSessionCandidateModel.source_provider,
                PhysicalValidationSessionCandidateModel.grocery_context_id,
                PhysicalValidationSessionCandidateModel.product_id,
            )
        )
        return tuple(_digital_candidate_from_session_row(row) for row in rows)

    def reconciliation(
        self,
        session_id: str,
    ) -> PhysicalValidationSessionReconciliation | None:
        row = self.session.scalar(
            select(PhysicalValidationSessionReconciliationModel).where(
                PhysicalValidationSessionReconciliationModel.validation_session_id
                == session_id
            )
        )
        return (
            _physical_validation_reconciliation_from_row(row)
            if row is not None
            else None
        )

    def add_reconciliation(
        self,
        *,
        session_id: str,
        source_provider: str,
        grocery_context_id: str,
        source_snapshot_id: str,
        reason: str,
        reconciled_at: datetime,
    ) -> PhysicalValidationSessionReconciliation:
        """Add one explicit, immutable post-visit comparison binding.

        Domain validation that the snapshot and every target match is owned by
        the reconciliation service.  This repository boundary still prevents
        a later call from silently replacing an already approved binding.
        """

        if self.get_model(session_id) is None:
            raise LookupError("validation session does not exist")
        if self.session.get(CatalogSnapshotModel, source_snapshot_id) is None:
            raise LookupError("catalog snapshot does not exist")
        normalized_provider = source_provider.strip()
        normalized_context = grocery_context_id.strip()
        normalized_reason = reason.strip()
        if not normalized_provider or not normalized_context:
            raise ValueError("source provider and grocery context are required")
        if not normalized_reason:
            raise ValueError("reconciliation reason is required")
        timestamp = _aware(reconciled_at, field="reconciled_at")
        existing = self.reconciliation(session_id)
        expected = (
            normalized_provider,
            normalized_context,
            source_snapshot_id,
            normalized_reason,
        )
        if existing is not None:
            actual = (
                existing.source_provider,
                existing.grocery_context_id,
                existing.source_snapshot_id,
                existing.reason,
            )
            if actual != expected:
                raise ValueError(
                    "validation session is already reconciled to different evidence"
                )
            return existing
        row = PhysicalValidationSessionReconciliationModel(
            id=hashlib.sha256(
                f"{session_id}:{source_snapshot_id}".encode()
            ).hexdigest()[:32],
            validation_session_id=session_id,
            source_provider=normalized_provider,
            grocery_context_id=normalized_context,
            source_snapshot_id=source_snapshot_id,
            reason=normalized_reason,
            reconciled_at=timestamp,
        )
        self.session.add(row)
        self.session.flush()
        return _physical_validation_reconciliation_from_row(row)

    def items(self, session_id: str) -> tuple[PhysicalValidationSessionItem, ...]:
        self.ensure_legacy_identifier_state(session_id)
        observation_ids = dict(
            self.session.execute(
                select(
                    PhysicalPriceObservationModel.validation_session_item_id,
                    PhysicalPriceObservationModel.id,
                ).where(PhysicalPriceObservationModel.validation_session_id == session_id)
            ).all()
        )
        rows = self.session.scalars(
            select(PhysicalValidationSessionItemModel)
            .where(PhysicalValidationSessionItemModel.session_id == session_id)
            .order_by(PhysicalValidationSessionItemModel.ordinal)
        )
        item_rows = list(rows)
        identifier_rows = {
            row.session_item_id: row
            for row in self.session.scalars(
                select(PhysicalValidationSessionItemIdentifierModel).where(
                    PhysicalValidationSessionItemIdentifierModel.session_item_id.in_(
                        [row.id for row in item_rows]
                    )
                )
            )
        }
        result: list[PhysicalValidationSessionItem] = []
        for row in item_rows:
            identifier = identifier_rows.get(row.id)
            identifier_evidence = (
                self.session.get(
                    ProductIdentifierEvidenceModel,
                    identifier.identifier_evidence_id,
                )
                if identifier is not None and identifier.identifier_evidence_id
                else None
            )
            candidates = self.candidates_for_item(row.id)
            result.append(
                PhysicalValidationSessionItem(
                id=row.id,
                session_id=row.session_id,
                ordinal=row.ordinal,
                stratum=PhysicalPriceSemantics(row.stratum),
                target_gtin=(
                    row.target_gtin
                    or (
                        identifier_evidence.identifier_value
                        if identifier_evidence is not None
                        and identifier_evidence.identifier_type
                        == ProductIdentifierType.GTIN.value
                        else None
                    )
                ),
                target_product_name=row.target_product_name,
                target_brand=row.target_brand,
                target_category=row.target_category,
                target_package_description=row.target_package_description,
                target_product_id=(
                    identifier.target_product_id if identifier is not None else None
                ),
                target_source_provider=(
                    identifier.target_source_provider if identifier is not None else None
                ),
                target_grocery_context_id=(
                    identifier.target_grocery_context_id if identifier is not None else None
                ),
                target_external_product_id=(
                    identifier.target_external_product_id if identifier is not None else None
                ),
                target_store_external_id=(
                    identifier.target_store_external_id if identifier is not None else None
                ),
                target_sale_model=(
                    SaleModel(identifier.target_sale_model)
                    if identifier is not None
                    else SaleModel.UNKNOWN
                ),
                identifier_status=(
                    SessionItemIdentifierStatus(identifier.identifier_status)
                    if identifier is not None
                    else SessionItemIdentifierStatus.KNOWN_GTIN
                    if row.target_gtin
                    else SessionItemIdentifierStatus.UNKNOWN_GTIN
                ),
                reasons=tuple(row.reasons or ()),
                candidate_set_sha256=row.candidate_set_sha256,
                candidates=candidates,
                captured_observation_id=observation_ids.get(row.id),
            )
            )
        return tuple(result)

    def preparation(self, session_id: str) -> PhysicalIdentifierPreparation | None:
        row = self.session.get(PhysicalIdentifierPreparationModel, session_id)
        if row is None:
            return None
        return PhysicalIdentifierPreparation(
            validation_session_id=row.validation_session_id,
            target_products=row.target_products,
            known_gtin_before=row.known_gtin_before,
            enriched_gtin=row.enriched_gtin,
            gtin_unavailable=row.gtin_unavailable,
            weight_no_gtin_required=row.weight_no_gtin_required,
            true_unresolved=row.true_unresolved,
            detail_requests=row.detail_requests,
            cache_hits=row.cache_hits,
            errors=row.errors,
            request_limit=row.request_limit,
        )

    def item_identifier_model(
        self,
        session_id: str,
        item_id: str,
    ) -> PhysicalValidationSessionItemIdentifierModel | None:
        return self.session.scalar(
            select(PhysicalValidationSessionItemIdentifierModel)
            .join(
                PhysicalValidationSessionItemModel,
                PhysicalValidationSessionItemModel.id
                == PhysicalValidationSessionItemIdentifierModel.session_item_id,
            )
            .where(
                PhysicalValidationSessionItemIdentifierModel.session_item_id == item_id,
                PhysicalValidationSessionItemModel.session_id == session_id,
            )
        )

    def complete(
        self,
        session_id: str,
        *,
        completed_at: datetime,
    ) -> PhysicalValidationSession:
        row = self.get_model(session_id)
        if row is None:
            raise LookupError("validation session does not exist")
        if row.status == PhysicalValidationSessionStatus.CANCELLED.value:
            raise ValueError("cancelled validation session cannot be completed")
        timestamp = _aware(completed_at, field="completed_at")
        if timestamp < row.started_at:
            raise ValueError("completed_at cannot precede started_at")
        row.status = PhysicalValidationSessionStatus.COMPLETED.value
        row.completed_at = timestamp
        self.session.flush()
        result = self.get(session_id)
        assert result is not None
        return result

    def reserve_identifier_detail_request(self, session_id: str) -> bool:
        row = self.session.get(PhysicalIdentifierPreparationModel, session_id)
        if row is None:
            raise LookupError("identifier preparation does not exist")
        if row.detail_requests >= row.request_limit:
            return False
        row.detail_requests += 1
        self.session.flush()
        return True

    def record_identifier_resolution(
        self,
        session_id: str,
        item_id: str,
        *,
        status: SessionItemIdentifierStatus,
        evidence_id: str | None = None,
        result: str,
    ) -> None:
        item = self.item_identifier_model(session_id, item_id)
        preparation = self.session.get(PhysicalIdentifierPreparationModel, session_id)
        if item is None or preparation is None:
            raise LookupError("session identifier state does not exist")
        prior = SessionItemIdentifierStatus(item.identifier_status)
        item.identifier_status = status.value
        item.identifier_evidence_id = evidence_id
        if prior in {
            SessionItemIdentifierStatus.UNKNOWN_GTIN,
            SessionItemIdentifierStatus.ENRICHMENT_ERROR,
        } and preparation.true_unresolved > 0 and result in {
            "enriched",
            "cache_hit",
            "unavailable",
        }:
            preparation.true_unresolved -= 1
        if result == "enriched":
            preparation.enriched_gtin += 1
        elif result == "cache_hit":
            preparation.cache_hits += 1
            preparation.enriched_gtin += 1
        elif result == "unavailable":
            preparation.gtin_unavailable += 1
        elif result == "error":
            preparation.errors += 1
        else:
            raise ValueError("unknown identifier resolution result")
        self.session.flush()


def _product_identifier_from_row(
    row: ProductIdentifierEvidenceModel,
) -> ProductIdentifierEvidence:
    return ProductIdentifierEvidence(
        id=row.id,
        chain=Chain(row.chain),
        source_provider=row.source_provider,
        scope_key=row.scope_key,
        source_product_id=row.source_product_id,
        external_product_id=row.external_product_id,
        identifier_type=ProductIdentifierType(row.identifier_type),
        identifier_value=row.identifier_value,
        evidence_source=ProductIdentifierEvidenceSource(row.evidence_source),
        evidence_reference=row.evidence_reference,
        evidence_payload_sha256=row.evidence_payload_sha256,
        observed_at=row.observed_at,
        confidence=Confidence(row.confidence),
        active=row.is_active,
    )


class ProductIdentifierEvidenceRepository:
    """Accumulating explicit identifier registry with ambiguity visibility."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, evidence: ProductIdentifierEvidence) -> ProductIdentifierEvidenceModel:
        existing = self.session.scalar(
            select(ProductIdentifierEvidenceModel).where(
                ProductIdentifierEvidenceModel.chain == evidence.chain.value,
                ProductIdentifierEvidenceModel.source_provider == evidence.source_provider,
                ProductIdentifierEvidenceModel.scope_key == evidence.scope_key,
                ProductIdentifierEvidenceModel.external_product_id
                == evidence.external_product_id,
                ProductIdentifierEvidenceModel.identifier_type
                == evidence.identifier_type.value,
                ProductIdentifierEvidenceModel.identifier_value
                == evidence.identifier_value,
            )
        )
        if existing is not None:
            immutable = {
                "source_product_id": evidence.source_product_id,
                "evidence_source": evidence.evidence_source.value,
                "evidence_reference": evidence.evidence_reference,
                "evidence_payload_sha256": evidence.evidence_payload_sha256,
                "confidence": evidence.confidence.value,
            }
            if any(getattr(existing, field) != value for field, value in immutable.items()):
                raise ValueError("identifier evidence already exists with conflicting lineage")
            existing.observed_at = max(existing.observed_at, evidence.observed_at)
            existing.is_active = evidence.active
            self.session.flush()
            return existing
        row = ProductIdentifierEvidenceModel(
            id=evidence.id,
            chain=evidence.chain.value,
            source_provider=evidence.source_provider,
            scope_key=evidence.scope_key,
            source_product_id=evidence.source_product_id,
            external_product_id=evidence.external_product_id,
            identifier_type=evidence.identifier_type.value,
            identifier_value=evidence.identifier_value,
            evidence_source=evidence.evidence_source.value,
            evidence_reference=evidence.evidence_reference,
            evidence_payload_sha256=evidence.evidence_payload_sha256,
            observed_at=evidence.observed_at,
            confidence=evidence.confidence.value,
            is_active=evidence.active,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def for_product(
        self,
        *,
        chain: Chain,
        source_provider: str,
        scope_key: str,
        external_product_id: str,
        identifier_type: ProductIdentifierType = ProductIdentifierType.GTIN,
    ) -> tuple[ProductIdentifierEvidence, ...]:
        rows = self.session.scalars(
            select(ProductIdentifierEvidenceModel)
            .where(
                ProductIdentifierEvidenceModel.chain == chain.value,
                ProductIdentifierEvidenceModel.source_provider == source_provider,
                ProductIdentifierEvidenceModel.scope_key == scope_key,
                ProductIdentifierEvidenceModel.external_product_id == external_product_id,
                ProductIdentifierEvidenceModel.identifier_type == identifier_type.value,
                ProductIdentifierEvidenceModel.is_active.is_(True),
            )
            .order_by(
                ProductIdentifierEvidenceModel.observed_at.desc(),
                ProductIdentifierEvidenceModel.id,
            )
        )
        return tuple(_product_identifier_from_row(row) for row in rows)

    def resolve_gtin(
        self,
        *,
        chain: Chain,
        gtin: str,
        scope_key: str | None = None,
        source_provider: str | None = None,
    ) -> tuple[ProductIdentifierEvidence, ...]:
        normalized_gtin = normalize_gtin(gtin).normalized_gtin
        statement = select(ProductIdentifierEvidenceModel).where(
            ProductIdentifierEvidenceModel.chain == chain.value,
            ProductIdentifierEvidenceModel.identifier_type == ProductIdentifierType.GTIN.value,
            ProductIdentifierEvidenceModel.identifier_value == normalized_gtin,
            ProductIdentifierEvidenceModel.is_active.is_(True),
        )
        if scope_key is not None:
            statement = statement.where(
                ProductIdentifierEvidenceModel.scope_key == scope_key
            )
        if source_provider is not None:
            statement = statement.where(
                ProductIdentifierEvidenceModel.source_provider == source_provider
            )
        rows = self.session.scalars(
            statement.order_by(
                ProductIdentifierEvidenceModel.external_product_id,
                ProductIdentifierEvidenceModel.id,
            )
        )
        return tuple(_product_identifier_from_row(row) for row in rows)


class ShelfIdentifierEvidenceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, evidence: ShelfIdentifierEvidence) -> ShelfIdentifierEvidenceModel:
        store = self.session.get(PhysicalStoreModel, evidence.physical_store_id)
        if store is None:
            raise LookupError("physical store does not exist")
        if store.chain != evidence.chain.value:
            raise ValueError("shelf-code chain does not match physical store")
        if evidence.validation_session_id is not None:
            validation_session = self.session.get(
                PhysicalValidationSessionModel,
                evidence.validation_session_id,
            )
            if validation_session is None:
                raise LookupError("validation session does not exist")
            if validation_session.physical_store_id != evidence.physical_store_id:
                raise ValueError("shelf-code session belongs to another physical store")
            item = self.session.scalar(
                select(PhysicalValidationSessionItemModel).where(
                    PhysicalValidationSessionItemModel.id
                    == evidence.validation_session_item_id,
                    PhysicalValidationSessionItemModel.session_id
                    == evidence.validation_session_id,
                )
            )
            if item is None:
                raise LookupError("validation session item does not exist")
        row = ShelfIdentifierEvidenceModel(
            id=evidence.id,
            chain=evidence.chain.value,
            physical_store_id=evidence.physical_store_id,
            validation_session_id=evidence.validation_session_id,
            validation_session_item_id=evidence.validation_session_item_id,
            selected_source_product_id=evidence.selected_source_product_id,
            raw_value=evidence.raw_value,
            barcode_format=evidence.barcode_format,
            observed_at=evidence.observed_at,
            verified=False,
        )
        self.session.add(row)
        self.session.flush()
        return row


@dataclass(frozen=True, slots=True)
class ExternalPriceSnapshotImport:
    source_provider: str
    grocery_context_id: str
    source_snapshot_id: str
    products: int
    deactivated_rows: int


def _normalized_product_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def _external_candidate_values(candidate: DigitalPriceCandidate) -> dict[str, object]:
    return {
        "physical_store_id": candidate.physical_store_id,
        "grocery_context_id": candidate.grocery_context_id,
        "source_provider": candidate.source_provider,
        "source_snapshot_id": candidate.source_snapshot_id,
        "observed_at": candidate.observed_at,
        "product_id": candidate.product_id,
        "product_name": candidate.product_name,
        "normalized_product_name": _normalized_product_name(candidate.product_name),
        "gtin": candidate.gtin,
        "current_price": candidate.current_price,
        "regular_price": candidate.regular_price,
        "member_price": candidate.member_price,
        "comparison_price": candidate.comparison_price,
        "comparison_unit": candidate.comparison_unit,
        "promotion_type": (
            candidate.promotion_type.value if candidate.promotion_type is not None else None
        ),
        "member_only": candidate.member_only,
        "multibuy_quantity": candidate.multibuy_quantity,
        "multibuy_total_price": candidate.multibuy_total_price,
        "sale_model": candidate.sale_model.value,
        "common_product_score": candidate.common_product_score,
    }


class ExternalPriceCandidateRepository:
    """Immutable, credential-free cache of already licensed provider snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _provider(candidate: DigitalPriceCandidate) -> SourceProvider:
        try:
            provider = SourceProvider(candidate.source_provider)
        except ValueError as exc:
            raise ValueError("external price candidate has an unknown provider") from exc
        if provider is SourceProvider.OWN:
            raise ValueError("OWN candidates belong to catalog snapshots, not the external cache")
        return provider

    def _require_context_link(self, candidate: DigitalPriceCandidate) -> None:
        provider = self._provider(candidate)
        physical = self.session.get(PhysicalStoreModel, candidate.physical_store_id)
        if physical is None:
            raise LookupError(
                f"physical store {candidate.physical_store_id!r} does not exist"
            )
        link = self.session.scalar(
            select(StoreContextLinkModel).where(
                StoreContextLinkModel.physical_store_id == candidate.physical_store_id,
                StoreContextLinkModel.source_provider == provider.value,
                StoreContextLinkModel.grocery_context_id == candidate.grocery_context_id,
                StoreContextLinkModel.relation_type
                == StoreContextRelationType.EXACT_STORE_ONLINE_CONTEXT.value,
                StoreContextLinkModel.confidence.in_(
                    (Confidence.EXACT.value, Confidence.HIGH.value)
                ),
                StoreContextLinkModel.is_active.is_(True),
            )
        )
        if link is None:
            raise LookupError("external candidate lacks an active exact store-context link")

    def get_identity(self, candidate: DigitalPriceCandidate) -> ExternalPriceCandidateModel | None:
        return self.session.scalar(
            select(ExternalPriceCandidateModel).where(
                ExternalPriceCandidateModel.physical_store_id == candidate.physical_store_id,
                ExternalPriceCandidateModel.source_provider == candidate.source_provider,
                ExternalPriceCandidateModel.grocery_context_id == candidate.grocery_context_id,
                ExternalPriceCandidateModel.source_snapshot_id == candidate.source_snapshot_id,
                ExternalPriceCandidateModel.product_id == candidate.product_id,
            )
        )

    def add_immutable(self, candidate: DigitalPriceCandidate) -> ExternalPriceCandidateModel:
        self._require_context_link(candidate)
        values = _external_candidate_values(candidate)
        existing = self.get_identity(candidate)
        if existing is not None:
            if any(getattr(existing, field) != value for field, value in values.items()):
                raise ValueError("external snapshot identity already exists with different data")
            return existing
        row = ExternalPriceCandidateModel(**values, is_active=False)
        self.session.add(row)
        self.session.flush()
        return row

    def import_snapshot(
        self,
        candidates: Sequence[DigitalPriceCandidate],
    ) -> ExternalPriceSnapshotImport:
        """Atomically make one closed provider/context snapshot current.

        A repeated snapshot ID must contain the exact same product identity set.
        This prevents a partial retry from silently becoming the active cache.
        """

        if not candidates:
            raise ValueError("external snapshot import requires at least one candidate")
        first = candidates[0]
        scope = (
            first.physical_store_id,
            first.source_provider,
            first.grocery_context_id,
            first.source_snapshot_id,
        )
        if any(
            (
                candidate.physical_store_id,
                candidate.source_provider,
                candidate.grocery_context_id,
                candidate.source_snapshot_id,
            )
            != scope
            for candidate in candidates
        ):
            raise ValueError("external snapshot candidates must share one exact context scope")
        product_ids = {candidate.product_id for candidate in candidates}
        if len(product_ids) != len(candidates):
            raise ValueError("external snapshot product identities must be unique")

        self._require_context_link(first)
        existing_snapshot_rows = list(
            self.session.scalars(
                select(ExternalPriceCandidateModel).where(
                    ExternalPriceCandidateModel.physical_store_id == first.physical_store_id,
                    ExternalPriceCandidateModel.source_provider == first.source_provider,
                    ExternalPriceCandidateModel.grocery_context_id == first.grocery_context_id,
                    ExternalPriceCandidateModel.source_snapshot_id == first.source_snapshot_id,
                )
            )
        )
        existing_by_product = {
            row.product_id: row for row in existing_snapshot_rows
        }
        existing_snapshot_ids = set(existing_by_product)
        if existing_snapshot_ids and existing_snapshot_ids != product_ids:
            raise ValueError("repeated external snapshot has a different product identity set")
        for candidate in candidates:
            values = _external_candidate_values(candidate)
            existing = existing_by_product.get(candidate.product_id)
            if existing is not None:
                if any(getattr(existing, field) != value for field, value in values.items()):
                    raise ValueError(
                        "external snapshot identity already exists with different data"
                    )
                continue
            self.session.add(ExternalPriceCandidateModel(**values, is_active=False))
        self.session.flush()

        rows = list(
            self.session.scalars(
                select(ExternalPriceCandidateModel).where(
                    ExternalPriceCandidateModel.physical_store_id == first.physical_store_id,
                    ExternalPriceCandidateModel.source_provider == first.source_provider,
                    ExternalPriceCandidateModel.grocery_context_id == first.grocery_context_id,
                )
            )
        )
        deactivated = 0
        for row in rows:
            should_be_active = row.source_snapshot_id == first.source_snapshot_id
            if row.is_active and not should_be_active:
                deactivated += 1
            row.is_active = should_be_active
        self.session.flush()
        return ExternalPriceSnapshotImport(
            source_provider=first.source_provider,
            grocery_context_id=first.grocery_context_id,
            source_snapshot_id=first.source_snapshot_id,
            products=len(candidates),
            deactivated_rows=deactivated,
        )

    def matching_observation(
        self,
        observation: PhysicalPriceObservation,
    ) -> list[ExternalPriceCandidateModel]:
        statement = select(ExternalPriceCandidateModel).where(
            ExternalPriceCandidateModel.physical_store_id == observation.physical_store_id
        )
        if observation.gtin is not None:
            statement = statement.where(ExternalPriceCandidateModel.gtin == observation.gtin)
        else:
            statement = statement.where(
                ExternalPriceCandidateModel.normalized_product_name
                == _normalized_product_name(observation.product_name or "")
            )
        return list(
            self.session.scalars(
                statement.order_by(
                    ExternalPriceCandidateModel.observed_at.desc(),
                    ExternalPriceCandidateModel.source_provider,
                    ExternalPriceCandidateModel.source_snapshot_id,
                    ExternalPriceCandidateModel.product_id,
                )
            )
        )

    def active_for_store(
        self,
        physical_store_id: str,
        *,
        limit: int,
    ) -> list[ExternalPriceCandidateModel]:
        if not 1 <= limit <= 5000:
            raise ValueError("limit must be 1..5000")
        return list(
            self.session.scalars(
                select(ExternalPriceCandidateModel)
                .where(
                    ExternalPriceCandidateModel.physical_store_id == physical_store_id,
                    ExternalPriceCandidateModel.is_active.is_(True),
                )
                .order_by(
                    ExternalPriceCandidateModel.product_name,
                    ExternalPriceCandidateModel.source_provider,
                    ExternalPriceCandidateModel.product_id,
                )
                .limit(limit)
            )
        )


_SENSITIVE_NAMES = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "key",
    "password",
    "secret",
    "session",
    "session_id",
    "token",
}
_SENSITIVE_COMPACT_NAMES = {
    "accesstoken",
    "apikey",
    "authkey",
    "authtoken",
    "bearertoken",
    "clientsecret",
    "clientid",
    "clienttoken",
    "csrftoken",
    "idtoken",
    "ocpapimsubscriptionkey",
    "privatekey",
    "refreshtoken",
    "secretkey",
    "sessionid",
    "sessiontoken",
    "subscriptionkey",
}
_PUBLIC_PAGINATION_NAMES = {
    "nextpagetoken",
    "pagetoken",
    "paginationtoken",
}


def _is_sensitive(name: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
    compact = normalized.replace("_", "")
    if compact in _PUBLIC_PAGINATION_NAMES:
        return False
    return (
        normalized in _SENSITIVE_NAMES
        or any(
            marker in normalized
            for marker in ("access_token", "auth_token", "bearer_token", "client_secret")
        )
        or compact in _SENSITIVE_COMPACT_NAMES
    )


def _sanitise_query(query: dict[str, str]) -> dict[str, str]:
    return {key: "[REDACTED]" if _is_sensitive(key) else str(value) for key, value in query.items()}


def _sanitise_url(url: str) -> str:
    parsed = urlsplit(url)
    safe_query = [
        (key, "[REDACTED]" if _is_sensitive(key) else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(safe_query), parsed.fragment)
    )


class RawSnapshotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_fetch(
        self,
        fetch: RawFetch,
        *,
        catalog_snapshot_id: str,
        payload_location: str,
        collector_run_id: str | None = None,
        schema_fingerprint: str | None = None,
    ) -> RawSnapshotModel:
        """Persist lineage metadata; payload bytes belong in raw snapshot storage."""

        catalog = self.session.get(CatalogSnapshotModel, catalog_snapshot_id)
        if catalog is None:
            raise LookupError(f"catalog snapshot {catalog_snapshot_id!r} does not exist")
        if catalog.chain != fetch.chain.value:
            raise ValueError("raw fetch chain must match its catalog snapshot")
        if not payload_location.strip():
            raise ValueError("payload_location is required")

        safe_url = _sanitise_url(fetch.url)
        safe_query = _sanitise_query(fetch.query)
        fingerprint_body = {
            "chain": fetch.chain.value,
            "store_external_id": fetch.store_external_id,
            "kind": fetch.kind,
            "method": fetch.method.upper(),
            "url": safe_url,
            "query": safe_query,
            "page_number": fetch.page_number,
            "payload_hash": fetch.payload_hash,
        }
        request_fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_body,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
        ).hexdigest()

        existing = self.session.scalar(
            select(RawSnapshotModel).where(
                RawSnapshotModel.catalog_snapshot_id == catalog_snapshot_id,
                RawSnapshotModel.request_fingerprint == request_fingerprint,
            )
        )
        if existing is not None:
            return existing

        model = RawSnapshotModel(
            catalog_snapshot_id=catalog_snapshot_id,
            collector_run_id=collector_run_id,
            chain=fetch.chain.value,
            store_external_id=fetch.store_external_id,
            kind=fetch.kind,
            method=fetch.method.upper(),
            url=safe_url,
            query=safe_query,
            fetched_at=_aware(fetch.fetched_at, field="fetched_at"),
            http_status=fetch.http_status,
            content_type=fetch.content_type,
            payload_hash=fetch.payload_hash,
            payload_size=len(fetch.payload),
            payload_location=payload_location,
            request_fingerprint=request_fingerprint,
            connector_version=fetch.connector_version,
            page_number=fetch.page_number,
            schema_fingerprint=schema_fingerprint,
        )
        self.session.add(model)
        self.session.flush()
        return model


class PriceObservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(
        self,
        *,
        catalog_snapshot_id: str,
        product_id: str,
        source_product_id: str,
        store_id: str,
        raw_snapshot_id: str,
        observed_at: datetime,
        sale_price: Decimal | float | str | None = None,
        regular_price: Decimal | float | str | None = None,
        member_price: Decimal | float | str | None = None,
        comparison_price: Decimal | float | str | None = None,
        comparison_unit: str | None = None,
        sale_unit: str | None = None,
        currency: str = "SEK",
    ) -> PriceObservationModel:
        """Append one observation, idempotently within a catalog snapshot."""

        currency = currency.strip().upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter ISO-style code")

        existing = self.session.scalar(
            select(PriceObservationModel).where(
                PriceObservationModel.catalog_snapshot_id == catalog_snapshot_id,
                PriceObservationModel.product_id == product_id,
                PriceObservationModel.store_id == store_id,
            )
        )
        if existing is not None:
            return existing

        model = PriceObservationModel(
            catalog_snapshot_id=catalog_snapshot_id,
            product_id=product_id,
            source_product_id=source_product_id,
            store_id=store_id,
            raw_snapshot_id=raw_snapshot_id,
            observed_at=_aware(observed_at, field="observed_at"),
            currency=currency,
            sale_price=_positive_decimal(sale_price, field="sale_price"),
            regular_price=_positive_decimal(regular_price, field="regular_price"),
            member_price=_positive_decimal(member_price, field="member_price"),
            comparison_price=_positive_decimal(comparison_price, field="comparison_price"),
            comparison_unit=comparison_unit,
            sale_unit=sale_unit,
        )
        self.session.add(model)
        self.session.flush()
        return model

    def history(self, *, product_id: str, store_id: str) -> list[PriceObservationModel]:
        return list(
            self.session.scalars(
                select(PriceObservationModel)
                .where(
                    PriceObservationModel.product_id == product_id,
                    PriceObservationModel.store_id == store_id,
                )
                .order_by(PriceObservationModel.observed_at, PriceObservationModel.id)
            )
        )

    def history_by_source_key(
        self,
        *,
        chain: Chain | str,
        source_product_key: str,
        store_id: str,
    ) -> list[PriceObservationModel]:
        """Price history across immutable snapshot-specific product versions."""

        return list(
            self.session.scalars(
                select(PriceObservationModel)
                .join(ProductModel, ProductModel.id == PriceObservationModel.product_id)
                .where(
                    ProductModel.chain == _value(chain),
                    ProductModel.source_product_key == source_product_key,
                    PriceObservationModel.store_id == store_id,
                )
                .order_by(PriceObservationModel.observed_at, PriceObservationModel.id)
            )
        )

    def at_time(
        self,
        *,
        product_id: str,
        store_id: str,
        at: datetime,
    ) -> PriceObservationModel | None:
        timestamp = _aware(at, field="at")
        return self.session.scalar(
            select(PriceObservationModel)
            .where(
                PriceObservationModel.product_id == product_id,
                PriceObservationModel.store_id == store_id,
                PriceObservationModel.observed_at <= timestamp,
            )
            .order_by(PriceObservationModel.observed_at.desc())
            .limit(1)
        )

    def at_time_by_source_key(
        self,
        *,
        chain: Chain | str,
        source_product_key: str,
        store_id: str,
        at: datetime,
    ) -> PriceObservationModel | None:
        timestamp = _aware(at, field="at")
        return self.session.scalar(
            select(PriceObservationModel)
            .join(ProductModel, ProductModel.id == PriceObservationModel.product_id)
            .where(
                ProductModel.chain == _value(chain),
                ProductModel.source_product_key == source_product_key,
                PriceObservationModel.store_id == store_id,
                PriceObservationModel.observed_at <= timestamp,
            )
            .order_by(PriceObservationModel.observed_at.desc())
            .limit(1)
        )


@dataclass(frozen=True)
class PersistedProductBundle:
    source_product: SourceProductModel
    product: ProductModel
    price_observation: PriceObservationModel
    promotions: tuple[PromotionModel, ...]


def _json_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


class ProductBundleRepository:
    """Atomic persistence boundary for one parsed and normalized source record."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def persist(
        self,
        *,
        source: SourceProduct,
        canonical: CanonicalProduct,
        catalog_snapshot_id: str,
        raw_snapshot_id: str,
        store_id: str,
        parser_version: str | None = None,
    ) -> PersistedProductBundle:
        parser_version = parser_version or canonical.parser_version
        self._validate_lineage(
            source=source,
            canonical=canonical,
            catalog_snapshot_id=catalog_snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            store_id=store_id,
        )

        # A savepoint prevents a partially written bundle if promotion parsing or a
        # late constraint fails. The caller still controls the outer transaction.
        with self.session.begin_nested():
            source_row = self._source_product(
                source=source,
                catalog_snapshot_id=catalog_snapshot_id,
                raw_snapshot_id=raw_snapshot_id,
                store_id=store_id,
                parser_version=parser_version,
            )
            product = self._canonical_product(canonical, source_row)
            observation = PriceObservationRepository(self.session).add(
                catalog_snapshot_id=catalog_snapshot_id,
                product_id=product.id,
                source_product_id=source_row.id,
                store_id=store_id,
                raw_snapshot_id=raw_snapshot_id,
                observed_at=canonical.observed_at,
                sale_price=source.sale_price,
                regular_price=source.regular_price,
                member_price=source.member_price,
                comparison_price=source.comparison_price,
                comparison_unit=source.comparison_unit,
                sale_unit=source.sale_unit,
            )
            promotions = tuple(
                self._promotion(
                    offer,
                    catalog_snapshot_id=catalog_snapshot_id,
                    source_product=source_row,
                    product=product,
                    price_observation=observation,
                    store_id=store_id,
                    raw_snapshot_id=raw_snapshot_id,
                    parser_version=parser_version,
                )
                for offer in source.offers
            )
            self.session.flush()

        return PersistedProductBundle(
            source_product=source_row,
            product=product,
            price_observation=observation,
            promotions=promotions,
        )

    def _validate_lineage(
        self,
        *,
        source: SourceProduct,
        canonical: CanonicalProduct,
        catalog_snapshot_id: str,
        raw_snapshot_id: str,
        store_id: str,
    ) -> None:
        catalog = self.session.get(CatalogSnapshotModel, catalog_snapshot_id)
        raw = self.session.get(RawSnapshotModel, raw_snapshot_id)
        store = self.session.get(StoreModel, store_id)
        if catalog is None or raw is None or store is None:
            raise LookupError("catalog snapshot, raw snapshot and store must all exist")
        if raw.catalog_snapshot_id != catalog.id:
            raise ValueError("raw snapshot must belong to the catalog snapshot")
        expected_chain = source.chain.value
        if not (
            catalog.chain == raw.chain == store.chain == canonical.chain.value == expected_chain
        ):
            raise ValueError("all product bundle lineage must belong to one chain")
        if not (source.store_external_id == canonical.store_external_id == store.external_id):
            raise ValueError("all product bundle lineage must belong to one store")
        _aware(source.fetched_at, field="source.fetched_at")
        _aware(canonical.observed_at, field="canonical.observed_at")

    def _source_product(
        self,
        *,
        source: SourceProduct,
        catalog_snapshot_id: str,
        raw_snapshot_id: str,
        store_id: str,
        parser_version: str,
    ) -> SourceProductModel:
        source_data = source.model_dump(mode="json")
        source_record_hash = _json_hash(source_data)
        existing = self.session.scalar(
            select(SourceProductModel).where(
                SourceProductModel.catalog_snapshot_id == catalog_snapshot_id,
                SourceProductModel.source_record_hash == source_record_hash,
            )
        )
        if existing is not None:
            return existing

        row = SourceProductModel(
            catalog_snapshot_id=catalog_snapshot_id,
            raw_snapshot_id=raw_snapshot_id,
            store_id=store_id,
            chain=source.chain.value,
            store_external_id=source.store_external_id,
            external_product_id=source.external_product_id,
            gtin=source.gtin,
            name=source.name,
            brand=source.brand,
            category_path=list(source.category_path),
            sale_price=source.sale_price,
            regular_price=source.regular_price,
            member_price=source.member_price,
            comparison_price=source.comparison_price,
            comparison_unit=source.comparison_unit,
            package_text=source.package_text,
            package_quantity=source.package_quantity,
            package_unit=source.package_unit,
            drained_quantity=source.drained_quantity,
            sale_unit=source.sale_unit,
            availability=source.availability,
            average_weight_kg=source.average_weight_kg,
            increment_value=source.increment_value,
            basket_type=source.basket_type,
            raw_reference=source.raw_reference,
            fetched_at=source.fetched_at,
            parser_version=parser_version,
            source_fields=source.source_fields,
            source_record_hash=source_record_hash,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def _canonical_product(
        self,
        canonical: CanonicalProduct,
        source: SourceProductModel,
    ) -> ProductModel:
        row = self.session.scalar(
            select(ProductModel).where(
                ProductModel.source_product_id == source.id,
                ProductModel.normalizer_version == canonical.normalizer_version,
            )
        )
        if row is None:
            row = ProductModel(
                source_product_id=source.id,
                catalog_snapshot_id=source.catalog_snapshot_id,
                raw_snapshot_id=source.raw_snapshot_id,
                store_id=source.store_id,
                chain=canonical.chain.value,
                store_external_id=canonical.store_external_id,
                source_product_key=canonical.source_product_key,
            )
            self.session.add(row)

        row.external_product_id = canonical.external_product_id
        row.gtin = canonical.gtin
        row.name = canonical.name
        row.brand = canonical.brand
        row.category_path = list(canonical.category_path)
        row.canonical_food = canonical.canonical_food
        row.product_role = canonical.product_role
        row.product_form = canonical.product_form
        row.semantic_confidence = canonical.semantic_confidence.value
        row.sale_model = canonical.sale_model.value
        row.quantity_confidence = canonical.quantity_confidence.value
        row.package_quantity = canonical.package_quantity
        row.package_unit = canonical.package_unit
        row.usable_quantity = canonical.usable_quantity
        row.usable_unit = canonical.usable_unit
        row.sale_price = canonical.sale_price
        row.sale_unit = canonical.sale_unit
        row.unit_price = canonical.unit_price
        row.comparison_price = canonical.comparison_price
        row.comparison_unit = canonical.comparison_unit
        row.availability = canonical.availability
        row.raw_reference = canonical.raw_reference
        row.parser_version = canonical.parser_version
        row.normalizer_version = canonical.normalizer_version
        row.observed_at = canonical.observed_at
        self.session.flush()
        return row

    def _promotion(
        self,
        offer: SourceOffer,
        *,
        catalog_snapshot_id: str,
        source_product: SourceProductModel,
        product: ProductModel,
        price_observation: PriceObservationModel,
        store_id: str,
        raw_snapshot_id: str,
        parser_version: str,
    ) -> PromotionModel:
        offer_fingerprint = _json_hash(offer.model_dump(mode="json"))
        row = self.session.scalar(
            select(PromotionModel).where(
                PromotionModel.catalog_snapshot_id == catalog_snapshot_id,
                PromotionModel.source_product_id == source_product.id,
                PromotionModel.store_id == store_id,
                PromotionModel.offer_fingerprint == offer_fingerprint,
            )
        )
        if row is not None:
            return row
        row = PromotionModel(
            catalog_snapshot_id=catalog_snapshot_id,
            source_product_id=source_product.id,
            product_id=product.id,
            store_id=store_id,
            raw_snapshot_id=raw_snapshot_id,
            price_observation_id=price_observation.id,
            offer_fingerprint=offer_fingerprint,
            external_id=offer.external_id,
            type=offer.type.value,
            valid_from=offer.valid_from,
            valid_to=offer.valid_to,
            price=offer.price,
            quantity=offer.quantity,
            member_only=offer.member_only,
            max_quantity=offer.max_quantity,
            description=offer.description,
            source_payload=offer.source_payload,
            parser_version=parser_version,
        )
        self.session.add(row)
        self.session.flush()
        return row


class ParserFailureRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(
        self,
        failure: ParseFailure,
        *,
        chain: Chain,
        catalog_snapshot_id: str,
        raw_snapshot_id: str,
        store_external_id: str | None = None,
        collector_run_id: str | None = None,
    ) -> ParserFailureModel:
        raw = self.session.get(RawSnapshotModel, raw_snapshot_id)
        catalog = self.session.get(CatalogSnapshotModel, catalog_snapshot_id)
        if raw is None or catalog is None:
            raise LookupError("catalog snapshot and raw snapshot must exist")
        if raw.catalog_snapshot_id != catalog.id or raw.chain != chain.value:
            raise ValueError("parse failure lineage is inconsistent")
        fingerprint = _json_hash(
            {
                "raw_snapshot_id": raw_snapshot_id,
                "raw_record_reference": failure.raw_record_reference,
                "error_code": failure.error_code,
                "error_message": failure.error_message,
                "parser_version": failure.parser_version,
            }
        )
        existing = self.session.scalar(
            select(ParserFailureModel).where(
                ParserFailureModel.catalog_snapshot_id == catalog_snapshot_id,
                ParserFailureModel.failure_fingerprint == fingerprint,
            )
        )
        if existing is not None:
            return existing
        row = ParserFailureModel(
            catalog_snapshot_id=catalog_snapshot_id,
            collector_run_id=collector_run_id,
            raw_snapshot_id=raw_snapshot_id,
            chain=chain.value,
            store_external_id=store_external_id,
            raw_record_reference=failure.raw_record_reference,
            error_code=failure.error_code,
            error_message=failure.error_message,
            parser_version=failure.parser_version,
            failure_fingerprint=fingerprint,
            sample=failure.sample,
        )
        self.session.add(row)
        self.session.flush()
        return row


class CollectorRunRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def start(
        self,
        *,
        chain: Chain,
        connector_version: str,
        scope: dict[str, Any] | None = None,
        parser_version: str | None = None,
        normalizer_version: str | None = None,
        started_at: datetime | None = None,
    ) -> CollectorRunModel:
        row = CollectorRunModel(
            chain=chain.value,
            scope=dict(scope or {}),
            status="running",
            connector_version=connector_version,
            parser_version=parser_version,
            normalizer_version=normalizer_version,
            started_at=_aware(started_at or utcnow(), field="started_at"),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def finish(
        self,
        run_id: str,
        *,
        successful: bool,
        metrics: dict[str, Any],
        error_summary: str | None = None,
        finished_at: datetime | None = None,
    ) -> CollectorRunModel:
        row = self.session.get(CollectorRunModel, run_id)
        if row is None:
            raise LookupError(f"collector run {run_id!r} does not exist")
        if row.finished_at is not None:
            return row
        row.successful = successful
        row.status = "succeeded" if successful else "failed"
        row.metrics = dict(metrics)
        row.error_summary = error_summary
        row.finished_at = _aware(finished_at or utcnow(), field="finished_at")
        self.session.flush()
        return row


@dataclass(frozen=True)
class ActiveCatalogRow:
    product: ProductModel
    price: PriceObservationModel


class CatalogReadRepository:
    """Consumer reads constrained to promoted per-chain snapshots."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_active(
        self,
        *,
        chain: Chain | str,
        scope_key: str | None = None,
        store_external_id: str | None = None,
        query: str | None = None,
        canonical_foods: set[str] | None = None,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[ActiveCatalogRow]:
        if offset < 0 or not 1 <= limit <= 50_000:
            raise ValueError("offset must be non-negative and limit must be 1..50000")
        statement = (
            select(ProductModel, PriceObservationModel)
            .join(
                PriceObservationModel,
                PriceObservationModel.product_id == ProductModel.id,
            )
            .join(
                CatalogSnapshotModel,
                CatalogSnapshotModel.id == PriceObservationModel.catalog_snapshot_id,
            )
            .join(StoreModel, StoreModel.id == PriceObservationModel.store_id)
            .where(
                CatalogSnapshotModel.chain == _value(chain),
                CatalogSnapshotModel.is_active.is_(True),
            )
        )
        if scope_key is not None:
            statement = statement.where(CatalogSnapshotModel.scope_key == scope_key)
        if store_external_id is not None:
            statement = statement.where(StoreModel.external_id == store_external_id)
        if query and query.strip():
            statement = statement.where(ProductModel.name.ilike(f"%{query.strip()}%"))
        if canonical_foods:
            statement = statement.where(ProductModel.canonical_food.in_(canonical_foods))
        statement = (
            statement.order_by(ProductModel.name, StoreModel.external_id)
            .offset(offset)
            .limit(limit)
        )
        return [
            ActiveCatalogRow(product=row[0], price=row[1])
            for row in self.session.execute(statement)
        ]

    def source_products(
        self,
        snapshot_id: str,
        *,
        offset: int = 0,
        limit: int = 1000,
    ) -> list[SourceProductModel]:
        if offset < 0 or not 1 <= limit <= 50_000:
            raise ValueError("offset must be non-negative and limit must be 1..50000")
        return list(
            self.session.scalars(
                select(SourceProductModel)
                .where(SourceProductModel.catalog_snapshot_id == snapshot_id)
                .order_by(SourceProductModel.id)
                .offset(offset)
                .limit(limit)
            )
        )


_TRANSITIONS: dict[str, set[str]] = {
    SnapshotState.FETCHED.value: {
        SnapshotState.PARSED.value,
        SnapshotState.REJECTED.value,
    },
    SnapshotState.PARSED.value: {
        SnapshotState.VALIDATED.value,
        SnapshotState.REJECTED.value,
    },
    SnapshotState.VALIDATED.value: {
        SnapshotState.HEALTH_CHECKED.value,
        SnapshotState.REJECTED.value,
    },
    SnapshotState.HEALTH_CHECKED.value: {
        SnapshotState.PROMOTED.value,
        SnapshotState.REJECTED.value,
    },
    SnapshotState.PROMOTED.value: set(),
    SnapshotState.REJECTED.value: set(),
}


class SnapshotRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        chain: Chain | str,
        coverage: CoverageLevel | str,
        connector_version: str,
        scope_key: str = "default",
        collector_run_id: str | None = None,
        parser_version: str | None = None,
        normalizer_version: str | None = None,
        schema_fingerprint: str | None = None,
        metrics: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> CatalogSnapshotModel:
        model = CatalogSnapshotModel(
            chain=_value(chain),
            coverage=_value(coverage),
            connector_version=connector_version,
            scope_key=scope_key,
            collector_run_id=collector_run_id,
            parser_version=parser_version,
            normalizer_version=normalizer_version,
            schema_fingerprint=schema_fingerprint,
            metrics=dict(metrics or {}),
            state=SnapshotState.FETCHED.value,
            is_active=False,
            created_at=_aware(created_at or utcnow(), field="created_at"),
        )
        self.session.add(model)
        self.session.flush()
        return model

    def get(self, snapshot_id: str, *, lock: bool = False) -> CatalogSnapshotModel | None:
        statement = select(CatalogSnapshotModel).where(CatalogSnapshotModel.id == snapshot_id)
        if lock:
            statement = statement.with_for_update()
        return self.session.scalar(statement)

    def transition(
        self,
        snapshot_id: str,
        state: SnapshotState | str,
        *,
        at: datetime | None = None,
        rejection_reason: str | None = None,
    ) -> CatalogSnapshotModel:
        target_state = _value(state)
        if target_state == SnapshotState.PROMOTED.value:
            return self.promote(snapshot_id, at=at)

        model = self.get(snapshot_id, lock=True)
        if model is None:
            raise LookupError(f"catalog snapshot {snapshot_id!r} does not exist")
        if model.state == target_state:
            return model
        if target_state not in _TRANSITIONS.get(model.state, set()):
            raise SnapshotTransitionError(
                f"invalid catalog snapshot transition {model.state!r} -> {target_state!r}"
            )

        timestamp = _aware(at or utcnow(), field="at")
        model.state = target_state
        if target_state == SnapshotState.PARSED.value:
            model.parsed_at = timestamp
        elif target_state == SnapshotState.VALIDATED.value:
            model.validated_at = timestamp
        elif target_state == SnapshotState.HEALTH_CHECKED.value:
            model.health_checked_at = timestamp
        elif target_state == SnapshotState.REJECTED.value:
            model.rejected_at = timestamp
            model.rejection_reason = rejection_reason or "snapshot rejected"
            model.is_active = False
        self.session.flush()
        return model

    def mark_ready(self, snapshot_id: str, *, at: datetime | None = None) -> CatalogSnapshotModel:
        """Advance a newly fetched snapshot through the deterministic pipeline."""

        progress = (
            SnapshotState.FETCHED,
            SnapshotState.PARSED,
            SnapshotState.VALIDATED,
            SnapshotState.HEALTH_CHECKED,
        )
        model = self.get(snapshot_id)
        if model is None:
            raise LookupError(f"catalog snapshot {snapshot_id!r} does not exist")
        states = [state.value for state in progress]
        if model.state not in states:
            raise SnapshotTransitionError(
                f"snapshot in state {model.state!r} cannot be marked ready"
            )
        for state in progress[states.index(model.state) + 1 :]:
            self.transition(snapshot_id, state, at=at)
        model = self.get(snapshot_id)
        if model is None:  # pragma: no cover - guarded above
            raise LookupError(snapshot_id)
        return model

    def promote(
        self,
        snapshot_id: str,
        *,
        at: datetime | None = None,
    ) -> CatalogSnapshotModel:
        """Atomically replace the active snapshot for only the target chain.

        The enclosing SQLAlchemy transaction is the atomic boundary. If its commit
        fails (or the caller rolls back), the previous active snapshot remains active.
        """

        model = self.get(snapshot_id, lock=True)
        if model is None:
            raise LookupError(f"catalog snapshot {snapshot_id!r} does not exist")
        if model.state == SnapshotState.PROMOTED.value and model.is_active:
            return model
        if model.state != SnapshotState.HEALTH_CHECKED.value:
            raise SnapshotTransitionError("only a health-checked snapshot can be promoted")

        active_rows = list(
            self.session.scalars(
                select(CatalogSnapshotModel)
                .where(
                    CatalogSnapshotModel.chain == model.chain,
                    CatalogSnapshotModel.scope_key == model.scope_key,
                    CatalogSnapshotModel.is_active.is_(True),
                )
                .with_for_update()
            )
        )
        previous = active_rows[0] if active_rows else None
        for active in active_rows:
            active.is_active = False
        # Avoid transiently violating the per-chain unique active index. This flush is
        # still uncommitted and therefore rolls back with the outer transaction.
        if active_rows:
            self.session.flush()

        timestamp = _aware(at or utcnow(), field="at")
        model.previous_active_snapshot_id = previous.id if previous else None
        model.state = SnapshotState.PROMOTED.value
        model.is_active = True
        model.promoted_at = timestamp
        self.session.flush()
        return model

    def reject(
        self,
        snapshot_id: str,
        *,
        reason: str,
        at: datetime | None = None,
    ) -> CatalogSnapshotModel:
        return self.transition(
            snapshot_id,
            SnapshotState.REJECTED,
            at=at,
            rejection_reason=reason,
        )

    def active(
        self,
        chain: Chain | str,
        *,
        scope_key: str = "default",
    ) -> CatalogSnapshotModel | None:
        return self.session.scalar(
            select(CatalogSnapshotModel).where(
                CatalogSnapshotModel.chain == _value(chain),
                CatalogSnapshotModel.scope_key == scope_key,
                CatalogSnapshotModel.is_active.is_(True),
            )
        )

    def last_known_good(
        self,
        chain: Chain | str,
        *,
        scope_key: str = "default",
    ) -> CatalogSnapshotModel | None:
        active = self.active(chain, scope_key=scope_key)
        if active is not None:
            return active
        return self.session.scalar(
            select(CatalogSnapshotModel)
            .where(
                CatalogSnapshotModel.chain == _value(chain),
                CatalogSnapshotModel.scope_key == scope_key,
                CatalogSnapshotModel.state == SnapshotState.PROMOTED.value,
            )
            .order_by(CatalogSnapshotModel.promoted_at.desc())
            .limit(1)
        )

    def list_for_chain(
        self,
        chain: Chain | str,
        *,
        limit: int = 100,
    ) -> list[CatalogSnapshotModel]:
        if not 1 <= limit <= 10_000:
            raise ValueError("limit must be 1..10000")
        return list(
            self.session.scalars(
                select(CatalogSnapshotModel)
                .where(CatalogSnapshotModel.chain == _value(chain))
                .order_by(CatalogSnapshotModel.created_at.desc())
                .limit(limit)
            )
        )


class ConnectorHealthRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, chain: Chain | str) -> ConnectorHealthModel | None:
        return self.session.get(ConnectorHealthModel, _value(chain))

    def upsert(self, health: ConnectorHealth) -> ConnectorHealthModel:
        model = self.get(health.chain)
        if model is None:
            model = ConnectorHealthModel(chain=health.chain.value)
            self.session.add(model)
        model.coverage = health.coverage.value
        model.status = health.status.value
        model.last_success_at = (
            _aware(health.last_success_at, field="last_success_at")
            if health.last_success_at
            else None
        )
        model.checked_at = _aware(health.checked_at, field="checked_at")
        model.active_snapshot_id = health.active_snapshot_id
        model.metrics = health.metrics.model_dump(mode="json")
        model.warnings = list(health.warnings)
        model.schema_fingerprint = health.schema_fingerprint
        model.updated_at = utcnow()
        self.session.flush()
        return model


__all__ = [
    "ActiveCatalogRow",
    "CatalogReadRepository",
    "CollectorRunRepository",
    "ConnectorHealthRepository",
    "ExternalPriceCandidateRepository",
    "ExternalPriceSnapshotImport",
    "ParserFailureRepository",
    "PersistedProductBundle",
    "PhysicalObservationAmendmentHeadConflict",
    "PhysicalObservationAmendmentIntegrityError",
    "PhysicalObservationAmendmentRepository",
    "PhysicalPriceObservationRepository",
    "PhysicalStoreDiscoveryHealthRepository",
    "PhysicalStoreReconciliation",
    "PhysicalStoreRepository",
    "PhysicalValidationComparisonVersion",
    "PhysicalValidationSessionReconciliation",
    "PhysicalValidationSessionRepository",
    "PhysicalValidationSnapshotLock",
    "PriceObservationRepository",
    "ProductBundleRepository",
    "ProductIdentifierEvidenceRepository",
    "ProviderStoreIdentityMappingRepository",
    "RawSnapshotRepository",
    "ShelfIdentifierEvidenceRepository",
    "SnapshotRepository",
    "SnapshotTransitionError",
    "StoreContextLinkReconciliation",
    "StoreContextLinkRepository",
    "StoreDiscoveryDriftError",
    "StoreRepository",
    "digital_candidate_set_sha256",
    "digital_candidate_sha256",
    "validation_session_suggestion_sha256",
]
