from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from grocery_data.app.domain.community_evidence import (
    CommunityEvidenceSource,
    CommunityEvidenceSubmission,
    CommunityEvidenceType,
    EvidenceVerificationStatus,
    ModerationDecision,
    ProductIdentityConfidence,
)
from grocery_data.app.domain.identifiers import normalize_gtin
from grocery_data.app.storage.models import (
    CommunityEvidenceModerationEventModel,
    CommunityEvidenceObservationModel,
    PhysicalStoreModel,
    StoreContextLinkModel,
    utcnow,
)


class CommunityEvidenceRateLimitError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class CommunityEvidenceCreateResult:
    observation: CommunityEvidenceObservationModel
    replayed: bool = False
    duplicate: bool = False


def pseudonymous_actor_hash(value: str | None) -> str:
    """Store a one-way pseudonym, never the caller's account/session identifier."""

    normalized = (value or "anonymous").strip()
    return hashlib.sha256(f"community-evidence:v1:{normalized}".encode()).hexdigest()


def _payload_sha256(payload: CommunityEvidenceSubmission) -> str:
    safe = payload.model_dump(
        mode="json",
        exclude={"anonymous_session_id", "user_id", "idempotency_key"},
    )
    encoded = json.dumps(
        safe,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _initial_trust(
    payload: CommunityEvidenceSubmission,
) -> tuple[ProductIdentityConfidence, Decimal]:
    if payload.gtin:
        identity = ProductIdentityConfidence.EXACT_GTIN
    elif payload.source_product_id:
        identity = ProductIdentityConfidence.EXACT_CHAIN_PRODUCT_ID
    elif payload.evidence_source is CommunityEvidenceSource.RECEIPT:
        identity = ProductIdentityConfidence.AMBIGUOUS
    else:
        identity = ProductIdentityConfidence.UNMATCHED

    confidence = {
        CommunityEvidenceSource.RECEIPT: Decimal("0.80"),
        CommunityEvidenceSource.BARCODE_SCAN: Decimal("0.75"),
        CommunityEvidenceSource.SHELF_PRICE: Decimal("0.65"),
        CommunityEvidenceSource.PHOTO: Decimal("0.60"),
        CommunityEvidenceSource.MANUAL: Decimal("0.40"),
        CommunityEvidenceSource.OTHER: Decimal("0.30"),
    }[payload.evidence_source]
    if payload.gtin and payload.evidence_source in {
        CommunityEvidenceSource.RECEIPT,
        CommunityEvidenceSource.BARCODE_SCAN,
    }:
        confidence += Decimal("0.15")
    if payload.receipt_ingestion_id and payload.gtin:
        confidence = Decimal("0.98")
    return identity, min(confidence, Decimal(1))


def _presence(payload: CommunityEvidenceSubmission) -> bool | None:
    if payload.physical_presence is not None:
        return payload.physical_presence
    if payload.evidence_type in {
        CommunityEvidenceType.PRODUCT_FOUND,
        CommunityEvidenceType.PRICE_DIFFERENCE,
        CommunityEvidenceType.LOCAL_PROMOTION,
        CommunityEvidenceType.PROMOTION_MISSING_FROM_APP,
        CommunityEvidenceType.RECEIPT_PURCHASE,
    }:
        return True
    if payload.evidence_type is CommunityEvidenceType.PRODUCT_NOT_FOUND:
        return False
    return None


class CommunityEvidenceRepository:
    """Persistence boundary that never reads or writes authoritative snapshot tables."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, evidence_id: str) -> CommunityEvidenceObservationModel | None:
        return self.session.get(CommunityEvidenceObservationModel, evidence_id)

    def create(
        self,
        payload: CommunityEvidenceSubmission,
        *,
        now: datetime | None = None,
        max_reports_per_hour: int = 60,
        duplicate_window_hours: float = 1.0,
        improbable_price_threshold: Decimal = Decimal(100000),
    ) -> CommunityEvidenceCreateResult:
        now = (now or utcnow()).astimezone(UTC)
        actor_hash = pseudonymous_actor_hash(payload.user_id or payload.anonymous_session_id)
        request_key = payload.idempotency_key or uuid4().hex
        existing = self.session.scalar(
            select(CommunityEvidenceObservationModel).where(
                CommunityEvidenceObservationModel.actor_hash == actor_hash,
                CommunityEvidenceObservationModel.idempotency_key == request_key,
            )
        )
        if existing is not None:
            return CommunityEvidenceCreateResult(existing, replayed=True)

        recent_count = self.session.scalar(
            select(func.count(CommunityEvidenceObservationModel.id)).where(
                CommunityEvidenceObservationModel.actor_hash == actor_hash,
                CommunityEvidenceObservationModel.created_at >= now - timedelta(hours=1),
            )
        )
        if int(recent_count or 0) >= max_reports_per_hour:
            raise CommunityEvidenceRateLimitError("community report rate limit exceeded")

        normalized_gtin = None
        if payload.gtin:
            normalized_gtin = normalize_gtin(payload.gtin).normalized_gtin

        resolved_store: PhysicalStoreModel | None = None
        unresolved_provider_store_id = payload.source_provider_store_id
        if payload.physical_store_id:
            physical_store = self.session.get(PhysicalStoreModel, payload.physical_store_id)
            if physical_store is not None and physical_store.is_active:
                resolved_store = physical_store
            else:
                # Preserve the unresolved caller provenance, but never relabel a
                # GroceryContext/provider id as a verified physical store.
                unresolved_provider_store_id = (
                    unresolved_provider_store_id or payload.physical_store_id
                )
        if resolved_store is None and payload.source_provider_store_id and payload.chain:
            physical_store = self.session.scalar(
                select(PhysicalStoreModel).where(
                    PhysicalStoreModel.chain == payload.chain.strip().casefold(),
                    PhysicalStoreModel.external_store_id == payload.source_provider_store_id,
                    PhysicalStoreModel.is_active.is_(True),
                )
            )
            if physical_store is not None:
                resolved_store = physical_store

        resolved_store_id = resolved_store.id if resolved_store is not None else None
        verified_context_id: str | None = None
        if resolved_store is not None and payload.grocery_context_id:
            context_link = self.session.scalar(
                select(StoreContextLinkModel)
                .where(
                    StoreContextLinkModel.physical_store_id == resolved_store.id,
                    StoreContextLinkModel.grocery_context_id == payload.grocery_context_id,
                    StoreContextLinkModel.is_active.is_(True),
                )
                .order_by(StoreContextLinkModel.id)
                .limit(1)
            )
            if context_link is not None:
                verified_context_id = context_link.grocery_context_id

        payload_hash = _payload_sha256(payload)
        duplicate = self.session.scalar(
            select(CommunityEvidenceObservationModel)
            .where(
                CommunityEvidenceObservationModel.actor_hash == actor_hash,
                CommunityEvidenceObservationModel.payload_sha256 == payload_hash,
                CommunityEvidenceObservationModel.created_at
                >= now - timedelta(hours=duplicate_window_hours),
            )
            .order_by(CommunityEvidenceObservationModel.created_at.desc())
            .limit(1)
        )
        if duplicate is not None:
            return CommunityEvidenceCreateResult(duplicate, duplicate=True)

        observed_at = payload.observed_at.astimezone(UTC)
        prices = tuple(
            price
            for price in (payload.shelf_price, payload.digital_price, payload.unit_price)
            if price is not None
        )
        store_required = payload.evidence_type in {
            CommunityEvidenceType.PRODUCT_FOUND,
            CommunityEvidenceType.PRODUCT_NOT_FOUND,
            CommunityEvidenceType.PRICE_DIFFERENCE,
            CommunityEvidenceType.LOCAL_PROMOTION,
            CommunityEvidenceType.PROMOTION_MISSING_FROM_APP,
            CommunityEvidenceType.RECEIPT_PURCHASE,
        }
        suspicious = (
            observed_at > now + timedelta(minutes=15)
            or any(price > improbable_price_threshold for price in prices)
            or (store_required and resolved_store_id is None)
        )
        identity, confidence = _initial_trust(payload)
        promotion = payload.promotion
        row = CommunityEvidenceObservationModel(
            observed_at=observed_at,
            actor_hash=actor_hash,
            idempotency_key=request_key,
            payload_sha256=payload_hash,
            evidence_type=payload.evidence_type.value,
            evidence_source=payload.evidence_source.value,
            initial_status=(
                EvidenceVerificationStatus.QUARANTINED.value
                if suspicious
                else EvidenceVerificationStatus.USER_REPORTED.value
            ),
            chain=(
                resolved_store.chain
                if resolved_store is not None
                else (payload.chain or "").strip().casefold() or None
            ),
            physical_store_id=resolved_store_id,
            source_provider_store_id=(
                resolved_store.external_store_id
                if resolved_store is not None
                else unresolved_provider_store_id
            ),
            store_identity_verified=resolved_store_id is not None,
            store_display_name=(
                resolved_store.name if resolved_store is not None else payload.store_display_name
            ),
            grocery_context_id=verified_context_id,
            gtin=normalized_gtin,
            source_product_id=payload.source_product_id,
            product_name=payload.product_name,
            brand=payload.brand,
            package_description=payload.package_description,
            physical_presence=_presence(payload),
            shelf_price=payload.shelf_price,
            digital_price=payload.digital_price,
            unit_price=payload.unit_price,
            price_unit=payload.price_unit,
            quantity=payload.quantity,
            promotion_eligibility=(promotion.eligibility.value if promotion else None),
            promotion_mechanism=(promotion.mechanism.value if promotion else None),
            promotion_regular_price=(promotion.regular_price if promotion else None),
            promotion_active_price=(promotion.active_price if promotion else None),
            promotion_required_quantity=(promotion.required_quantity if promotion else None),
            promotion_total_price=(promotion.total_price if promotion else None),
            promotion_percent_discount=(promotion.percent_discount if promotion else None),
            promotion_max_quantity=(promotion.max_quantity if promotion else None),
            promotion_member_program=(promotion.member_program if promotion else None),
            promotion_valid_from=(promotion.valid_from if promotion else None),
            promotion_valid_to=(promotion.valid_to if promotion else None),
            promotion_description=(promotion.description if promotion else None),
            receipt_ingestion_id=payload.receipt_ingestion_id,
            plan_id=payload.plan_id,
            price_snapshot_id=payload.price_snapshot_id,
            note=payload.note,
            identity_confidence=identity.value,
            evidence_confidence=confidence,
            created_at=now,
        )
        self.session.add(row)
        self.session.flush()
        return CommunityEvidenceCreateResult(row)

    def current_status(self, evidence_id: str) -> EvidenceVerificationStatus:
        row = self.get(evidence_id)
        if row is None:
            raise KeyError(evidence_id)
        latest = self.session.scalar(
            select(CommunityEvidenceModerationEventModel)
            .where(CommunityEvidenceModerationEventModel.evidence_id == evidence_id)
            .order_by(CommunityEvidenceModerationEventModel.created_at.desc())
            .limit(1)
        )
        return EvidenceVerificationStatus(latest.status if latest else row.initial_status)

    def moderate(
        self,
        evidence_id: str,
        decision: ModerationDecision,
        *,
        now: datetime | None = None,
    ) -> CommunityEvidenceModerationEventModel:
        if self.get(evidence_id) is None:
            raise KeyError(evidence_id)
        existing = self.session.scalar(
            select(CommunityEvidenceModerationEventModel).where(
                CommunityEvidenceModerationEventModel.evidence_id == evidence_id,
                CommunityEvidenceModerationEventModel.idempotency_key == decision.idempotency_key,
            )
        )
        if existing is not None:
            return existing
        event = CommunityEvidenceModerationEventModel(
            evidence_id=evidence_id,
            status=decision.status.value,
            reason=decision.reason,
            moderator_hash=pseudonymous_actor_hash(decision.moderator_id or "operator"),
            idempotency_key=decision.idempotency_key,
            created_at=(now or utcnow()).astimezone(UTC),
        )
        self.session.add(event)
        self.session.flush()
        return event

    def list_recent(
        self,
        *,
        physical_store_id: str | None = None,
        chain: str | None = None,
        evidence_type: CommunityEvidenceType | None = None,
        limit: int = 100,
    ) -> list[CommunityEvidenceObservationModel]:
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be 1..1000")
        statement = select(CommunityEvidenceObservationModel)
        if physical_store_id:
            statement = statement.where(
                CommunityEvidenceObservationModel.physical_store_id == physical_store_id
            )
        if chain:
            statement = statement.where(
                CommunityEvidenceObservationModel.chain == chain.strip().casefold()
            )
        if evidence_type:
            statement = statement.where(
                CommunityEvidenceObservationModel.evidence_type == evidence_type.value
            )
        return list(
            self.session.scalars(
                statement.order_by(CommunityEvidenceObservationModel.created_at.desc()).limit(limit)
            )
        )

    def privacy_safe_metrics(self) -> dict[str, object]:
        by_type = {
            str(name): int(count)
            for name, count in self.session.execute(
                select(
                    CommunityEvidenceObservationModel.evidence_type,
                    func.count(CommunityEvidenceObservationModel.id),
                ).group_by(CommunityEvidenceObservationModel.evidence_type)
            )
        }
        by_source = {
            str(name): int(count)
            for name, count in self.session.execute(
                select(
                    CommunityEvidenceObservationModel.evidence_source,
                    func.count(CommunityEvidenceObservationModel.id),
                ).group_by(CommunityEvidenceObservationModel.evidence_source)
            )
        }
        by_initial_status = {
            str(name): int(count)
            for name, count in self.session.execute(
                select(
                    CommunityEvidenceObservationModel.initial_status,
                    func.count(CommunityEvidenceObservationModel.id),
                ).group_by(CommunityEvidenceObservationModel.initial_status)
            )
        }
        effective_statuses: dict[str, int] = {}
        for evidence_id in self.session.scalars(
            select(CommunityEvidenceObservationModel.id)
        ):
            status = self.current_status(evidence_id).value
            effective_statuses[status] = effective_statuses.get(status, 0) + 1
        total = sum(by_type.values())
        decided = sum(
            effective_statuses.get(status, 0)
            for status in (
                EvidenceVerificationStatus.VALID.value,
                EvidenceVerificationStatus.REJECTED.value,
                EvidenceVerificationStatus.QUARANTINED.value,
            )
        )
        return {
            "total": total,
            "by_type": by_type,
            "by_source": by_source,
            "by_initial_status": by_initial_status,
            "by_effective_status": effective_statuses,
            "acceptance_rate": (
                effective_statuses.get(EvidenceVerificationStatus.VALID.value, 0)
                / decided
                if decided
                else None
            ),
        }


__all__ = [
    "CommunityEvidenceCreateResult",
    "CommunityEvidenceRateLimitError",
    "CommunityEvidenceRepository",
    "pseudonymous_actor_hash",
]
