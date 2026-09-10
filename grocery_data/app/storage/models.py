from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(tz=UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Timezone-safe timestamps with a deterministic SQLite representation."""

    impl = DateTime
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "sqlite":
            return dialect.type_descriptor(String(40))
        return dialect.type_descriptor(DateTime(timezone=True))

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("timestamps must be timezone-aware")
        value = value.astimezone(UTC)
        if dialect.name == "sqlite":
            return value.isoformat(timespec="microseconds")
        return value

    def process_result_value(
        self,
        value: datetime | str | None,
        dialect: Dialect,
    ) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class StoreModel(Base):
    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("chain", "external_id", name="uq_stores_chain_external_id"),
        Index("ix_stores_chain_city_active", "chain", "city", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    postal_code: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    online_shopping: Mapped[bool | None] = mapped_column(Boolean)
    coverage: Mapped[str] = mapped_column(String(32), nullable=False)
    price_context_type: Mapped[str | None] = mapped_column(String(32))
    physical_store_external_id: Mapped[str | None] = mapped_column(String(255))
    raw_reference: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalStoreModel(Base):
    """Official physical site; deliberately not a catalog/price context."""

    __tablename__ = "physical_stores"
    __table_args__ = (
        UniqueConstraint(
            "chain",
            "external_store_id",
            name="uq_physical_stores_chain_external_id",
        ),
        Index(
            "ix_physical_stores_city_chain_active",
            "city",
            "chain",
            "is_active",
        ),
        Index("ix_physical_stores_lifecycle", "lifecycle_state", "not_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    external_store_id: Mapped[str | None] = mapped_column(String(255))
    external_store_aliases: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    postal_code: Mapped[str | None] = mapped_column(String(32))
    city: Mapped[str | None] = mapped_column(String(255))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(10, 7))
    official_source: Mapped[str] = mapped_column(Text, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    lifecycle_state: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    not_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class PhysicalStoreDiscoveryHealthModel(Base):
    """Last bounded official-locator outcome for one chain/city scope."""

    __tablename__ = "physical_store_discovery_health"
    __table_args__ = (
        UniqueConstraint(
            "chain",
            "normalized_city",
            name="uq_physical_store_discovery_health_scope",
        ),
        Index(
            "ix_physical_store_discovery_health_status_observed",
            "status",
            "observed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    city: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_city: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    complete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_count: Mapped[int | None] = mapped_column(Integer)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class StoreContextLinkModel(Base):
    """Many-to-many evidence link to OWN or external federated contexts."""

    __tablename__ = "store_context_links"
    __table_args__ = (
        UniqueConstraint(
            "physical_store_id",
            "source_provider",
            "grocery_context_id",
            name="uq_store_context_links_identity",
        ),
        Index(
            "ix_store_context_links_physical_active",
            "physical_store_id",
            "is_active",
        ),
        Index(
            "ix_store_context_links_context",
            "source_provider",
            "grocery_context_id",
        ),
        Index(
            "ix_store_context_links_pickup_point",
            "source_provider",
            "pickup_point_external_id",
        ),
        Index("ix_store_context_links_local_store", "local_store_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    physical_store_id: Mapped[str] = mapped_column(
        ForeignKey("physical_stores.id", ondelete="CASCADE"), nullable=False
    )
    grocery_context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_channel: Mapped[str] = mapped_column(String(32), nullable=False)
    local_store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))
    pickup_point_external_id: Mapped[str | None] = mapped_column(String(255))
    grocery_context_name: Mapped[str | None] = mapped_column(String(500))
    price_context_type: Mapped[str | None] = mapped_column(String(32))
    coverage: Mapped[str | None] = mapped_column(String(32))
    relation_type: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    basket_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    offers_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    snapshot_id: Mapped[str | None] = mapped_column(String(255))
    observed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    linked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_verified_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class ProviderStoreIdentityMappingModel(Base):
    """Persistent verified identity, unresolved result, or detected drift.

    One row owns the current/LKG relationship for a physical store and an
    external provider.  On drift, ``provider_context_id`` and
    ``verified_identity_fingerprint`` remain the last verified values while
    the candidate fields retain the new observation for operator review.
    """

    __tablename__ = "provider_store_identity_mappings"
    __table_args__ = (
        UniqueConstraint(
            "physical_store_id",
            "provider",
            name="uq_provider_store_identity_mapping_scope",
        ),
        Index(
            "ix_provider_store_identity_mapping_status",
            "provider",
            "status",
            "is_active",
        ),
        Index(
            "ix_provider_store_identity_mapping_context",
            "provider",
            "provider_context_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    physical_store_id: Mapped[str] = mapped_column(
        ForeignKey("physical_stores.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_context_id: Mapped[str | None] = mapped_column(String(255))
    provider_store_id: Mapped[str | None] = mapped_column(String(255))
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    verified_identity_fingerprint: Mapped[str | None] = mapped_column(String(64))
    observed_identity_fingerprint: Mapped[str | None] = mapped_column(String(64))
    candidate_context_id: Mapped[str | None] = mapped_column(String(255))
    verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    drift_detected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class PhysicalValidationSessionModel(Base):
    """One bounded, voluntary and privacy-preserving store visit."""

    __tablename__ = "physical_validation_sessions"
    __table_args__ = (
        Index(
            "ix_physical_validation_sessions_store_started",
            "physical_store_id",
            "started_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    physical_store_id: Mapped[str] = mapped_column(
        ForeignKey("physical_stores.id", ondelete="CASCADE"), nullable=False
    )
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    store_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    blind_capture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    sampling_strategy: Mapped[str] = mapped_column(
        String(64), nullable=False, default="stratified"
    )
    notes: Mapped[str | None] = mapped_column(Text)
    suggestion_set_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalValidationSessionItemModel(Base):
    """Immutable suggested identity and stratum within one field session."""

    __tablename__ = "physical_validation_session_items"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "ordinal",
            name="uq_physical_validation_session_item_ordinal",
        ),
        Index(
            "ix_physical_validation_session_items_session_stratum",
            "session_id",
            "stratum",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    stratum: Mapped[str] = mapped_column(String(32), nullable=False)
    target_gtin: Mapped[str | None] = mapped_column(String(32))
    target_product_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_brand: Mapped[str | None] = mapped_column(String(500))
    target_category: Mapped[str | None] = mapped_column(String(500))
    target_package_description: Mapped[str | None] = mapped_column(String(128))
    reasons: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    candidate_set_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalValidationSessionCandidateModel(Base):
    """Credential-free immutable digital row frozen when a session starts."""

    __tablename__ = "physical_validation_session_candidates"
    __table_args__ = (
        UniqueConstraint(
            "session_item_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            "product_id",
            name="uq_physical_validation_session_candidate_identity",
        ),
        Index(
            "ix_physical_validation_session_candidates_item_provider",
            "session_item_id",
            "source_provider",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_item_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_session_items.id", ondelete="CASCADE"), nullable=False
    )
    physical_store_id: Mapped[str] = mapped_column(String(64), nullable=False)
    grocery_context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(500))
    package_description: Mapped[str | None] = mapped_column(String(128))
    gtin: Mapped[str | None] = mapped_column(String(32))
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    regular_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    member_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    promotion_type: Mapped[str | None] = mapped_column(String(32))
    member_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    multibuy_quantity: Mapped[int | None] = mapped_column(Integer)
    multibuy_total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    sale_model: Mapped[str] = mapped_column(String(64), nullable=False)
    common_product_score: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    recent_price_change: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    candidate_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalValidationSessionReconciliationModel(Base):
    """Explicit post-visit binding to one immutable promoted snapshot.

    Session candidates remain the digital evidence frozen before the field
    visit.  This additive row records an operator-approved second comparison
    basis without modifying either that evidence or the physical observations.
    One session can be reconciled only once; a different snapshot therefore
    requires an explicit schema/workflow change rather than a silent overwrite.
    """

    __tablename__ = "physical_validation_session_reconciliations"
    __table_args__ = (
        UniqueConstraint(
            "validation_session_id",
            name="uq_physical_validation_session_reconciliation_session",
        ),
        Index(
            "ix_physical_validation_reconciliation_snapshot",
            "source_snapshot_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    validation_session_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    grocery_context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    reconciled_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalValidationSnapshotLockModel(Base):
    """Immutable snapshot identity frozen when a field session is created.

    The candidate rows remain the complete price evidence.  This compact lock
    makes their snapshot boundary explicit and independently auditable without
    modifying either candidates or later physical observations.
    """

    __tablename__ = "physical_validation_snapshot_locks"
    __table_args__ = (
        UniqueConstraint(
            "validation_session_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            name="uq_physical_validation_snapshot_lock_identity",
        ),
        Index(
            "ix_physical_validation_snapshot_locks_session",
            "validation_session_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    validation_session_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    grocery_context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False)
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalValidationComparisonVersionModel(Base):
    """Versioned comparison policy/basis; never a physical-price rewrite."""

    __tablename__ = "physical_validation_comparison_versions"
    __table_args__ = (
        UniqueConstraint(
            "validation_session_id",
            "version_number",
            name="uq_physical_validation_comparison_version_number",
        ),
        Index(
            "ix_physical_validation_comparison_versions_session_kind",
            "validation_session_id",
            "version_kind",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    validation_session_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    version_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_snapshot_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    evidence_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    freshness_threshold_hours: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class ProductIdentifierEvidenceModel(Base):
    """Explicit identifier evidence kept outside immutable price snapshots."""

    __tablename__ = "product_identifier_evidence"
    __table_args__ = (
        UniqueConstraint(
            "chain",
            "source_provider",
            "scope_key",
            "external_product_id",
            "identifier_type",
            "identifier_value",
            name="uq_product_identifier_evidence_fact",
        ),
        Index(
            "ix_product_identifier_evidence_chain_identifier",
            "chain",
            "identifier_type",
            "identifier_value",
            "is_active",
        ),
        Index(
            "ix_product_identifier_evidence_product",
            "chain",
            "source_provider",
            "scope_key",
            "external_product_id",
            "is_active",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False)
    source_product_id: Mapped[str | None] = mapped_column(String(255))
    external_product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier_type: Mapped[str] = mapped_column(String(32), nullable=False)
    identifier_value: Mapped[str] = mapped_column(String(255), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_payload_sha256: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class PhysicalValidationSessionItemIdentifierModel(Base):
    """Exact target identity and identifier state for one immutable item."""

    __tablename__ = "physical_validation_session_item_identifiers"
    __table_args__ = (
        Index(
            "ix_physical_session_item_identifier_status",
            "identifier_status",
        ),
    )

    session_item_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_session_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_product_id: Mapped[str | None] = mapped_column(String(255))
    target_source_provider: Mapped[str | None] = mapped_column(String(32))
    target_grocery_context_id: Mapped[str | None] = mapped_column(String(255))
    target_external_product_id: Mapped[str | None] = mapped_column(String(255))
    target_store_external_id: Mapped[str | None] = mapped_column(String(255))
    target_sale_model: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_status: Mapped[str] = mapped_column(String(64), nullable=False)
    identifier_evidence_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_identifier_evidence.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class PhysicalIdentifierPreparationModel(Base):
    """Monotonic bounded enrichment counters for one field session."""

    __tablename__ = "physical_identifier_preparations"

    validation_session_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_products: Mapped[int] = mapped_column(Integer, nullable=False)
    known_gtin_before: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enriched_gtin: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    gtin_unavailable: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weight_no_gtin_required: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    true_unresolved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    request_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


class PhysicalObservationV2EvidenceModel(Base):
    """V2 evidence fields without mutating the historical observation table."""

    __tablename__ = "physical_observation_v2_evidence"

    observation_id: Mapped[str] = mapped_column(
        ForeignKey("physical_price_observations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    identification_evidence: Mapped[str] = mapped_column(String(64), nullable=False)
    regular_shelf_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    weight_price_type: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class ShelfIdentifierEvidenceModel(Base):
    """Uninterpreted shelf-code scan; it is not a product/GTIN mapping."""

    __tablename__ = "shelf_identifier_evidence"
    __table_args__ = (
        Index(
            "ix_shelf_identifier_evidence_store_observed",
            "physical_store_id",
            "observed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    physical_store_id: Mapped[str] = mapped_column(
        ForeignKey("physical_stores.id", ondelete="CASCADE"), nullable=False
    )
    validation_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE")
    )
    validation_session_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("physical_validation_session_items.id", ondelete="CASCADE")
    )
    selected_source_product_id: Mapped[str | None] = mapped_column(String(255))
    raw_value: Mapped[str] = mapped_column(String(255), nullable=False)
    barcode_format: Mapped[str] = mapped_column(String(64), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class BarcodeScanDiagnosticModel(Base):
    """Privacy-minimal scanner telemetry for field reliability diagnostics.

    A row deliberately has no barcode value, product/store/session identity,
    network address, browser fingerprint or media reference.  It records only
    the bounded technical facts needed to compare scanner providers.
    """

    __tablename__ = "barcode_scan_diagnostics"
    __table_args__ = (
        Index("ix_barcode_scan_diagnostics_created", "created_at"),
        Index(
            "ix_barcode_scan_diagnostics_provider_outcome",
            "scanner_provider",
            "outcome",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    scanner_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    barcode_format: Mapped[str | None] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    failure_reason: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalPriceObservationModel(Base):
    """Manual ground-truth sample; never a catalog price observation."""

    __tablename__ = "physical_price_observations"
    __table_args__ = (
        UniqueConstraint(
            "validation_session_item_id",
            name="uq_physical_price_observation_session_item",
        ),
        Index(
            "ix_physical_price_observations_store_observed",
            "physical_store_id",
            "observed_at",
        ),
        Index(
            "ix_physical_price_observations_store_gtin_observed",
            "physical_store_id",
            "gtin",
            "observed_at",
        ),
        Index("ix_physical_price_observations_gtin", "gtin"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    physical_store_id: Mapped[str] = mapped_column(
        ForeignKey("physical_stores.id", ondelete="CASCADE"), nullable=False
    )
    gtin: Mapped[str | None] = mapped_column(String(32))
    product_name: Mapped[str | None] = mapped_column(String(1000))
    shelf_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    promotion_type: Mapped[str | None] = mapped_column(String(32))
    member_only: Mapped[bool | None] = mapped_column(Boolean)
    multibuy_quantity: Mapped[int | None] = mapped_column(Integer)
    multibuy_total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    promotion_text: Mapped[str | None] = mapped_column(String(1000))
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    photo_reference: Mapped[str | None] = mapped_column(Text)
    validation_session_id: Mapped[str | None] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE")
    )
    validation_session_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("physical_validation_session_items.id", ondelete="CASCADE")
    )
    price_semantics: Mapped[str | None] = mapped_column(String(32))
    identity_status: Mapped[str | None] = mapped_column(String(32))
    immutable_candidate_set_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PhysicalObservationAmendmentModel(Base):
    """Immutable post-completion evidence; never overwrites an observation."""

    __tablename__ = "physical_observation_amendments"
    __table_args__ = (
        UniqueConstraint(
            "validation_session_id",
            "validation_session_item_id",
            "client_request_id",
            name="uq_physical_observation_amendment_request",
        ),
        UniqueConstraint(
            "supersedes_amendment_id",
            name="uq_physical_observation_amendment_supersedes",
        ),
        CheckConstraint(
            "kind IN ('late_capture', 'correction')",
            name="ck_physical_observation_amendment_kind",
        ),
        CheckConstraint(
            "observed_at_precision IN "
            "('exact', 'minute', 'hour', 'day', 'visit_window', 'unknown')",
            name="ck_physical_observation_amendment_time_precision",
        ),
        CheckConstraint(
            "payload_schema_version = 1",
            name="ck_physical_observation_amendment_schema_version",
        ),
        CheckConstraint(
            "(kind = 'late_capture' AND base_observation_id IS NULL "
            "AND supersedes_amendment_id IS NULL) OR "
            "(kind = 'correction' AND (base_observation_id IS NOT NULL "
            "OR supersedes_amendment_id IS NOT NULL))",
            name="ck_physical_observation_amendment_chain",
        ),
        Index(
            "ix_physical_observation_amendments_session_created",
            "validation_session_id",
            "created_at",
        ),
        Index(
            "ix_physical_observation_amendments_item_created",
            "validation_session_item_id",
            "created_at",
        ),
        Index(
            "ux_physical_observation_amendments_item_root",
            "validation_session_item_id",
            unique=True,
            sqlite_where=text("supersedes_amendment_id IS NULL"),
            postgresql_where=text("supersedes_amendment_id IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    validation_session_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    validation_session_item_id: Mapped[str] = mapped_column(
        ForeignKey("physical_validation_session_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    payload_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    base_observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("physical_price_observations.id", ondelete="RESTRICT")
    )
    supersedes_amendment_id: Mapped[str | None] = mapped_column(
        ForeignKey("physical_observation_amendments.id", ondelete="RESTRICT")
    )
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    observed_at_precision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    reference: Mapped[str] = mapped_column(Text, nullable=False)
    client_request_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


@event.listens_for(PhysicalObservationAmendmentModel, "before_update")
@event.listens_for(PhysicalObservationAmendmentModel, "before_delete")
def _reject_physical_observation_amendment_mutation(
    _mapper: Any,
    _connection: Any,
    _target: PhysicalObservationAmendmentModel,
) -> None:
    raise ValueError("physical observation amendments are append-only")


class ExternalPriceCandidateModel(Base):
    """Credential-free licensed/provider snapshot row for physical validation.

    This cache is intentionally separate from catalog prices. Rows can validate
    manual observations but cannot be selected by the basket provider.
    """

    __tablename__ = "external_price_candidates"
    __table_args__ = (
        UniqueConstraint(
            "physical_store_id",
            "source_provider",
            "grocery_context_id",
            "source_snapshot_id",
            "product_id",
            name="uq_external_price_candidate_identity",
        ),
        Index(
            "ix_external_price_candidate_store_gtin_time",
            "physical_store_id",
            "gtin",
            "observed_at",
        ),
        Index(
            "ix_external_price_candidate_store_name_time",
            "physical_store_id",
            "normalized_product_name",
            "observed_at",
        ),
        Index(
            "ix_external_price_candidate_active_context",
            "physical_store_id",
            "source_provider",
            "grocery_context_id",
            "is_active",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    physical_store_id: Mapped[str] = mapped_column(
        ForeignKey("physical_stores.id", ondelete="CASCADE"), nullable=False
    )
    grocery_context_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_snapshot_id: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    product_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    normalized_product_name: Mapped[str] = mapped_column(String(1000), nullable=False)
    gtin: Mapped[str | None] = mapped_column(String(32))
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    regular_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    member_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    promotion_type: Mapped[str | None] = mapped_column(String(32))
    member_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    multibuy_quantity: Mapped[int | None] = mapped_column(Integer)
    multibuy_total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    sale_model: Mapped[str] = mapped_column(String(64), nullable=False)
    common_product_score: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, default=Decimal(0)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class CollectorRunModel(Base):
    __tablename__ = "collector_runs"
    __table_args__ = (Index("ix_collector_runs_chain_started", "chain", "started_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="running")
    connector_version: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(128))
    normalizer_version: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    successful: Mapped[bool | None] = mapped_column(Boolean)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    error_summary: Mapped[str | None] = mapped_column(Text)


class CatalogSnapshotModel(Base):
    __tablename__ = "catalog_snapshots"
    __table_args__ = (
        Index("ix_catalog_snapshots_chain_created", "chain", "created_at"),
        Index(
            "uq_catalog_snapshots_active_chain_scope",
            "chain",
            "scope_key",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_key: Mapped[str] = mapped_column(String(255), nullable=False, default="default")
    coverage: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False, default="fetched")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    collector_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("collector_runs.id", ondelete="SET NULL")
    )
    previous_active_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="SET NULL")
    )
    connector_version: Mapped[str] = mapped_column(String(128), nullable=False)
    parser_version: Mapped[str | None] = mapped_column(String(128))
    normalizer_version: Mapped[str | None] = mapped_column(String(128))
    schema_fingerprint: Mapped[str | None] = mapped_column(String(128))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    parsed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    validated_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    health_checked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    promoted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rejected_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    rejection_reason: Mapped[str | None] = mapped_column(Text)


class RawSnapshotModel(Base):
    __tablename__ = "raw_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "catalog_snapshot_id",
            "request_fingerprint",
            name="uq_raw_snapshots_catalog_request",
        ),
        Index("ix_raw_snapshots_chain_fetched", "chain", "fetched_at"),
        Index("ix_raw_snapshots_payload_hash", "payload_hash"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    collector_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("collector_runs.id", ondelete="SET NULL")
    )
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    store_external_id: Mapped[str | None] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(128), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    query: Mapped[dict[str, str]] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    http_status: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(255))
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_size: Mapped[int] = mapped_column(Integer, nullable=False)
    payload_location: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    connector_version: Mapped[str] = mapped_column(String(128), nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class SourceProductModel(Base):
    __tablename__ = "source_products"
    __table_args__ = (
        UniqueConstraint(
            "catalog_snapshot_id",
            "source_record_hash",
            name="uq_source_products_snapshot_record",
        ),
        Index(
            "ix_source_products_chain_store_external",
            "chain",
            "store_external_id",
            "external_product_id",
        ),
        Index(
            "ix_source_products_snapshot_store",
            "catalog_snapshot_id",
            "store_id",
        ),
        Index("ix_source_products_gtin", "gtin"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    raw_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    store_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_product_id: Mapped[str | None] = mapped_column(String(255))
    gtin: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(1000), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(500))
    category_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    regular_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    member_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    package_text: Mapped[str | None] = mapped_column(String(500))
    package_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    package_unit: Mapped[str | None] = mapped_column(String(32))
    drained_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    sale_unit: Mapped[str | None] = mapped_column(String(32))
    availability: Mapped[str | None] = mapped_column(String(255))
    average_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    increment_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    basket_type: Mapped[str | None] = mapped_column(String(128))
    raw_reference: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    parser_version: Mapped[str] = mapped_column(String(128), nullable=False)
    source_fields: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source_record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class ProductModel(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint(
            "source_product_id",
            "normalizer_version",
            name="uq_products_source_normalizer",
        ),
        Index("ix_products_canonical_food", "canonical_food"),
        Index("ix_products_chain_gtin", "chain", "gtin"),
        Index(
            "ix_products_snapshot_store_name",
            "catalog_snapshot_id",
            "store_id",
            "name",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    source_product_id: Mapped[str] = mapped_column(
        ForeignKey("source_products.id", ondelete="CASCADE"), nullable=False
    )
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    raw_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[str | None] = mapped_column(ForeignKey("stores.id", ondelete="SET NULL"))
    source_product_key: Mapped[str] = mapped_column(String(500), nullable=False)
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    store_external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    external_product_id: Mapped[str | None] = mapped_column(String(255))
    gtin: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(1000), nullable=False)
    brand: Mapped[str | None] = mapped_column(String(500))
    category_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    canonical_food: Mapped[str | None] = mapped_column(String(255))
    product_role: Mapped[str | None] = mapped_column(String(255))
    product_form: Mapped[str | None] = mapped_column(String(255))
    semantic_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    sale_model: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity_confidence: Mapped[str] = mapped_column(String(32), nullable=False)
    package_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    package_unit: Mapped[str | None] = mapped_column(String(32))
    usable_quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    usable_unit: Mapped[str | None] = mapped_column(String(32))
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    sale_unit: Mapped[str | None] = mapped_column(String(32))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    availability: Mapped[str | None] = mapped_column(String(255))
    raw_reference: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(128), nullable=False)
    normalizer_version: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class IcaProductRegistryModel(Base):
    __tablename__ = "ica_product_registry"
    __table_args__ = (
        UniqueConstraint("external_product_id", name="uq_ica_registry_external_product"),
        Index("ix_ica_registry_last_seen", "last_seen_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    external_product_id: Mapped[str] = mapped_column(String(255), nullable=False)
    gtin: Mapped[str | None] = mapped_column(String(32))
    name: Mapped[str | None] = mapped_column(String(1000))
    brand: Mapped[str | None] = mapped_column(String(500))
    package_text: Mapped[str | None] = mapped_column(String(500))
    category_path: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    canonical_food: Mapped[str | None] = mapped_column(String(255))
    metadata_level: Mapped[str] = mapped_column(String(32), nullable=False)
    metadata_confidence: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    active_state: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_full_metadata_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class IcaDiscoveryEventModel(Base):
    __tablename__ = "ica_discovery_events"
    __table_args__ = (
        UniqueConstraint("event_fingerprint", name="uq_ica_discovery_event_fingerprint"),
        Index("ix_ica_discovery_product_time", "registry_product_id", "observed_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    registry_product_id: Mapped[str] = mapped_column(
        ForeignKey("ica_product_registry.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_page: Mapped[str] = mapped_column(Text, nullable=False)
    raw_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="SET NULL")
    )
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    event_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)


class IcaStoreProductObservationModel(Base):
    __tablename__ = "ica_store_product_observations"
    __table_args__ = (
        Index(
            "ix_ica_observation_product_store_time",
            "registry_product_id",
            "store_id",
            "observed_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    registry_product_id: Mapped[str] = mapped_column(
        ForeignKey("ica_product_registry.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    raw_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="SET NULL")
    )
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    availability: Mapped[str | None] = mapped_column(String(255))
    promotion: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sale_model: Mapped[str | None] = mapped_column(String(64))
    semantic_confidence: Mapped[str | None] = mapped_column(String(32))
    quantity_confidence: Mapped[str | None] = mapped_column(String(32))
    metadata_level: Mapped[str] = mapped_column(String(32), nullable=False)


class IcaCategoryRegistryModel(Base):
    __tablename__ = "ica_category_registry"
    __table_args__ = (
        UniqueConstraint("store_id", "external_category_id", name="uq_ica_category_store_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    external_category_id: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_external_id: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    declared_product_count: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class IcaEnrichmentRunModel(Base):
    __tablename__ = "ica_enrichment_runs"
    __table_args__ = (Index("ix_ica_enrichment_store_finished", "store_id", "finished_at"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    store_id: Mapped[str] = mapped_column(ForeignKey("stores.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    challenge_encountered: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pages_visited: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    product_ids_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price_observations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    route_metrics: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    finished_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)


class PriceObservationModel(Base):
    __tablename__ = "price_observations"
    __table_args__ = (
        UniqueConstraint(
            "catalog_snapshot_id",
            "product_id",
            "store_id",
            name="uq_price_observations_snapshot_product_store",
        ),
        Index(
            "ix_price_observations_product_store_time",
            "product_id",
            "store_id",
            "observed_at",
        ),
        Index(
            "ix_price_observations_snapshot_source",
            "catalog_snapshot_id",
            "source_product_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    source_product_id: Mapped[str] = mapped_column(
        ForeignKey("source_products.id", ondelete="CASCADE"), nullable=False
    )
    store_id: Mapped[str] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    raw_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="SEK")
    sale_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    regular_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    member_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    comparison_unit: Mapped[str | None] = mapped_column(String(32))
    sale_unit: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class PromotionModel(Base):
    __tablename__ = "promotions"
    __table_args__ = (
        UniqueConstraint(
            "catalog_snapshot_id",
            "source_product_id",
            "store_id",
            "offer_fingerprint",
            name="uq_promotions_snapshot_offer",
        ),
        Index("ix_promotions_product_period", "product_id", "valid_from", "valid_to"),
        Index("ix_promotions_source_product", "source_product_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    source_product_id: Mapped[str] = mapped_column(
        ForeignKey("source_products.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    store_id: Mapped[str] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"), nullable=False
    )
    raw_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    price_observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("price_observations.id", ondelete="SET NULL")
    )
    offer_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    quantity: Mapped[int | None] = mapped_column(Integer)
    member_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_quantity: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)
    source_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    parser_version: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class CommunityEvidenceObservationModel(Base):
    """Append-only consumer evidence, isolated from source snapshots and prices."""

    __tablename__ = "community_evidence_observations"
    __table_args__ = (
        UniqueConstraint(
            "actor_hash",
            "idempotency_key",
            name="uq_community_evidence_actor_request",
        ),
        Index(
            "ix_community_evidence_store_product_time",
            "physical_store_id",
            "gtin",
            "observed_at",
        ),
        Index(
            "ix_community_evidence_type_created",
            "evidence_type",
            "created_at",
        ),
        Index("ix_community_evidence_payload_created", "payload_sha256", "created_at"),
        CheckConstraint(
            "initial_status IN ('USER_REPORTED', 'QUARANTINED')",
            name="ck_community_evidence_initial_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    observed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    actor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_source: Mapped[str] = mapped_column(String(32), nullable=False)
    initial_status: Mapped[str] = mapped_column(String(32), nullable=False)
    chain: Mapped[str | None] = mapped_column(String(32))
    physical_store_id: Mapped[str | None] = mapped_column(String(128))
    source_provider_store_id: Mapped[str | None] = mapped_column(String(255))
    store_identity_verified: Mapped[bool] = mapped_column(Boolean, nullable=False)
    store_display_name: Mapped[str | None] = mapped_column(String(500))
    grocery_context_id: Mapped[str | None] = mapped_column(String(255))
    gtin: Mapped[str | None] = mapped_column(String(32))
    source_product_id: Mapped[str | None] = mapped_column(String(500))
    product_name: Mapped[str | None] = mapped_column(String(1000))
    brand: Mapped[str | None] = mapped_column(String(500))
    package_description: Mapped[str | None] = mapped_column(String(500))
    physical_presence: Mapped[bool | None] = mapped_column(Boolean)
    shelf_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    digital_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    price_unit: Mapped[str | None] = mapped_column(String(32))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    promotion_eligibility: Mapped[str | None] = mapped_column(String(32))
    promotion_mechanism: Mapped[str | None] = mapped_column(String(32))
    promotion_regular_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    promotion_active_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    promotion_required_quantity: Mapped[int | None] = mapped_column(Integer)
    promotion_total_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    promotion_percent_discount: Mapped[Decimal | None] = mapped_column(Numeric(7, 4))
    promotion_max_quantity: Mapped[int | None] = mapped_column(Integer)
    promotion_member_program: Mapped[str | None] = mapped_column(String(100))
    promotion_valid_from: Mapped[date | None] = mapped_column(Date)
    promotion_valid_to: Mapped[date | None] = mapped_column(Date)
    promotion_description: Mapped[str | None] = mapped_column(Text)
    receipt_ingestion_id: Mapped[str | None] = mapped_column(
        ForeignKey("community_receipt_ingestions.id", ondelete="SET NULL")
    )
    plan_id: Mapped[str | None] = mapped_column(String(128))
    price_snapshot_id: Mapped[str | None] = mapped_column(String(255))
    note: Mapped[str | None] = mapped_column(Text)
    identity_confidence: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence_confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)


class CommunityEvidenceModerationEventModel(Base):
    """Append-only status history; the observation row is never rewritten."""

    __tablename__ = "community_evidence_moderation_events"
    __table_args__ = (
        UniqueConstraint(
            "evidence_id",
            "idempotency_key",
            name="uq_community_moderation_request",
        ),
        Index(
            "ix_community_moderation_evidence_created",
            "evidence_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    evidence_id: Mapped[str] = mapped_column(
        ForeignKey("community_evidence_observations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    moderator_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class CommunityReceiptIngestionModel(Base):
    """Privacy-safe receipt parsing audit without persisted raw text or image."""

    __tablename__ = "community_receipt_ingestions"
    __table_args__ = (
        UniqueConstraint(
            "actor_hash",
            "raw_sha256",
            name="uq_community_receipts_actor_fingerprint",
        ),
        Index("ix_community_receipts_created_status", "created_at", "status"),
        CheckConstraint("raw_retained IS FALSE", name="ck_community_receipts_no_raw_retention"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_id)
    actor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retailer: Mapped[str | None] = mapped_column(String(64))
    physical_store_id: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_name: Mapped[str] = mapped_column(String(128), nullable=False)
    raw_sha256: Mapped[str | None] = mapped_column(String(64))
    raw_retained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    raw_discarded_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    retention_expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    purchase_observed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    parsed_lines: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class BetaFeedbackModel(Base):
    """User-authored beta feedback with pseudonymous, non-public provenance."""

    __tablename__ = "beta_feedback"
    __table_args__ = (
        Index("ix_beta_feedback_created_category", "created_at", "category"),
        Index("ix_beta_feedback_plan", "plan_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    actor_hash: Mapped[str | None] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    page_context: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(128))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)
    price_universe_id: Mapped[str | None] = mapped_column(String(255))


class ProductAnalyticsEventModel(Base):
    """Minimal first-party product event; properties are API-allowlisted."""

    __tablename__ = "product_analytics_events"
    __table_args__ = (
        Index("ix_product_analytics_created_event", "created_at", "event_name"),
        Index("ix_product_analytics_actor_created", "actor_hash", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    actor_hash: Mapped[str | None] = mapped_column(String(64))
    event_name: Mapped[str] = mapped_column(String(64), nullable=False)
    page_context: Mapped[str | None] = mapped_column(String(128))
    plan_id: Mapped[str | None] = mapped_column(String(128))
    properties: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)
    price_universe_id: Mapped[str | None] = mapped_column(String(255))


class FrontendErrorModel(Base):
    """Sanitized browser failure metadata; no stack, URL query or payload."""

    __tablename__ = "frontend_errors"
    __table_args__ = (Index("ix_frontend_errors_created_code", "created_at", "error_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    actor_hash: Mapped[str | None] = mapped_column(String(64))
    route: Mapped[str] = mapped_column(String(256), nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    plan_id: Mapped[str | None] = mapped_column(String(128))
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)
    price_universe_id: Mapped[str | None] = mapped_column(String(255))


class BetaRequestMetricModel(Base):
    """Privacy-safe request latency/status row used by the beta admin aggregates."""

    __tablename__ = "beta_request_metrics"
    __table_args__ = (
        Index("ix_beta_request_metrics_created_endpoint", "created_at", "endpoint"),
        Index("ix_beta_request_metrics_status_created", "status_code", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    endpoint: Mapped[str] = mapped_column(String(256), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(64))
    plan_id: Mapped[str | None] = mapped_column(String(128))
    price_universe_id: Mapped[str | None] = mapped_column(String(255))
    app_version: Mapped[str] = mapped_column(String(64), nullable=False)
    build_id: Mapped[str] = mapped_column(String(128), nullable=False)


class PrivacyErasureSuppressionModel(Base):
    """Append-only, actor-free directive used when replaying an old backup.

    The target identifiers are opaque record/plan IDs. No former session,
    actor hash, contact value or deleted payload is retained here.
    """

    __tablename__ = "privacy_erasure_suppressions"
    __table_args__ = (
        UniqueConstraint(
            "target_kind",
            "target_record_id",
            name="uq_privacy_erasure_suppression_target",
        ),
        Index("ix_privacy_erasure_suppressions_created", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)
    target_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target_record_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="SUPPRESS_ON_RESTORE",
    )


class ParserFailureModel(Base):
    __tablename__ = "parser_failures"
    __table_args__ = (
        UniqueConstraint(
            "catalog_snapshot_id",
            "failure_fingerprint",
            name="uq_parser_failures_snapshot_failure",
        ),
        Index("ix_parser_failures_chain_code_created", "chain", "error_code", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    catalog_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    collector_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("collector_runs.id", ondelete="SET NULL")
    )
    raw_snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("raw_snapshots.id", ondelete="CASCADE"), nullable=False
    )
    chain: Mapped[str] = mapped_column(String(32), nullable=False)
    store_external_id: Mapped[str | None] = mapped_column(String(255))
    raw_record_reference: Mapped[str] = mapped_column(Text, nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), nullable=False)
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    parser_version: Mapped[str] = mapped_column(String(128), nullable=False)
    failure_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    sample: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utcnow)


class ConnectorHealthModel(Base):
    __tablename__ = "connector_health"

    chain: Mapped[str] = mapped_column(String(32), primary_key=True)
    coverage: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    active_snapshot_id: Mapped[str | None] = mapped_column(
        ForeignKey("catalog_snapshots.id", ondelete="SET NULL")
    )
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    schema_fingerprint: Mapped[str | None] = mapped_column(String(128))
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow, onupdate=utcnow
    )


@event.listens_for(CommunityEvidenceObservationModel, "before_update")
@event.listens_for(CommunityEvidenceObservationModel, "before_delete")
@event.listens_for(CommunityEvidenceModerationEventModel, "before_update")
@event.listens_for(CommunityEvidenceModerationEventModel, "before_delete")
@event.listens_for(CommunityReceiptIngestionModel, "before_update")
@event.listens_for(CommunityReceiptIngestionModel, "before_delete")
@event.listens_for(PrivacyErasureSuppressionModel, "before_update")
@event.listens_for(PrivacyErasureSuppressionModel, "before_delete")
def _reject_community_evidence_mutation(
    _mapper: Any,
    _connection: Any,
    _target: object,
) -> None:
    raise ValueError("community evidence records are append-only")
